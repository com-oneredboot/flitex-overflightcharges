"""FIR Intersection Engine for spatial route-line × FIR-polygon computation.

This module provides the FIRIntersectionEngine class that performs PostGIS-based
intersection of route geometries with FIR boundary polygons to determine which
FIRs a route crosses, entry/exit points, segment distances, and great circle
distances. It also includes intersection deduplication, adjacent same-FIR merging,
boundary noise discard, and chain continuity validation.

The RouteCoordinateSource interface enables extensibility for different coordinate
sources (planned routes, ADS-B flown tracks) to reuse the same intersection logic.

Validates Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 8.1, 8.2, 8.3,
                        9.1, 9.2, 9.3, 18.1, 18.2, 19.1, 19.2, 21.3
"""

import json
import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class FIRCrossingRecord:
    """A single FIR crossing with full spatial data.

    Captures the complete spatial and distance information for one segment
    of a route passing through a Flight Information Region.

    Validates Requirements: 7.3, 8.1, 8.3, 9.1, 9.3, 10.6
    """

    sequence: int
    icao_code: str
    fir_name: str
    country: str
    country_code: str
    entry_point: tuple[float, float]  # (lat, lon)
    exit_point: tuple[float, float]   # (lat, lon)
    segment_distance_km: float
    segment_distance_nm: float
    gc_entry_exit_distance_km: float
    gc_entry_exit_distance_nm: float
    segment_geometry: dict  # GeoJSON LineString
    calculation_method: str  # "postgis_geography"


@dataclass
class FIRIntersectionResult:
    """Complete result of FIR intersection computation.

    Contains all FIR crossings with distances, total route distance,
    and any chain continuity validation failures.

    Validates Requirements: 7.7, 8.2
    """

    crossings: list[FIRCrossingRecord] = field(default_factory=list)
    total_distance_km: float = 0.0
    total_distance_nm: float = 0.0
    chain_continuity_failures: list[dict] = field(default_factory=list)  # Pairs where exit/entry gap > 10m


class RouteCoordinateSource(ABC):
    """Common interface for route coordinate sources.

    Enables the FIR Intersection Engine to accept coordinates from any source
    (decoded route string or ADS-B track positions) via a common interface,
    so that the same intersection algorithm can be reused for flown route
    FIR resolution in future specs.

    Validates Requirements: 21.3
    """

    @abstractmethod
    def get_coordinates(self) -> list[tuple[float, float]]:
        """Return ordered (lon, lat) coordinate pairs."""
        ...

    @abstractmethod
    def get_source_type(self) -> str:
        """Return source type identifier, e.g. 'planned' or 'flown'."""
        ...


class FIRIntersectionEngine:
    """Engine for computing FIR crossings via PostGIS route-line × FIR-polygon intersection.

    Accepts an ordered sequence of (lon, lat) coordinates representing a route,
    constructs a PostGIS LineString, intersects it with FIR boundary polygons,
    and produces FIR crossing records with segment and great circle distances.

    Processing pipeline:
        1. Date line adjustment (if route crosses ±180° longitude)
        2. Build WKT LineString from coordinates
        3. Execute PostGIS ST_Intersection against reference.fir_boundaries
        4. Deduplicate intersection points within 10m tolerance
        5. Construct and order segments by route fraction
        6. Merge adjacent same-FIR segments (preserve legitimate re-entries)
        7. Discard boundary noise segments shorter than 50m
        8. Extract entry/exit points per FIR crossing
        9. Calculate segment distance (geodesic) in km and nm
        10. Calculate great circle entry/exit distance in km and nm
        11. Validate chain continuity (exit N ≈ entry N+1 within 10m)

    Validates Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7,
                            8.1, 8.2, 9.1, 9.2, 18.1, 19.1
    """

    NOISE_THRESHOLD_M = 50       # Discard segments shorter than this
    DEDUP_TOLERANCE_M = 10       # Merge intersection points within this distance
    CHAIN_CONTINUITY_M = 10      # Max gap between consecutive exit/entry points

    def compute_fir_crossings(
        self,
        coordinates: list[tuple[float, float]],  # (lon, lat) pairs
        db: Session,
    ) -> FIRIntersectionResult:
        """Main entry point: compute all FIR crossings for a route.

        Orchestrates the full intersection pipeline from coordinate input
        through to validated FIR crossing records with distances.

        Args:
            coordinates: Ordered list of (lon, lat) coordinate pairs.
            db: SQLAlchemy database session for PostGIS queries.

        Returns:
            FIRIntersectionResult with crossings, total distances, and
            any chain continuity failures.

        Validates Requirements: 7.1, 7.2, 8.2, 18.1, 19.1
        """
        # Edge case: empty coordinates or single point — no intersections possible
        if not coordinates or len(coordinates) < 2:
            logger.info(
                "Insufficient coordinates (%d) for FIR intersection — returning empty result",
                len(coordinates) if coordinates else 0,
            )
            return FIRIntersectionResult()

        # 1. Adjust coordinates for date line crossings (Req 18.1)
        adjusted_coords = self._adjust_for_dateline(coordinates)

        # 2. Build WKT LineString from adjusted coordinates (Req 7.1)
        route_wkt = self._build_route_linestring(adjusted_coords)

        # 3. Execute PostGIS intersection query (Req 7.2, 7.3, 7.4)
        raw_intersections = self._execute_postgis_intersection(route_wkt, db)

        # Edge case: no intersections found
        if not raw_intersections:
            logger.info("No FIR intersections found for route")
            return FIRIntersectionResult()

        # 4. Deduplicate intersections within 10m tolerance (Req 19.1)
        deduped = self._deduplicate_intersections(raw_intersections)

        # 5. Merge adjacent same-FIR segments and discard noise < 50m (Req 7.5, 7.6)
        merged = self._merge_adjacent_same_fir(deduped)

        # Edge case: all segments discarded as noise after merging
        if not merged:
            logger.info("All FIR segments discarded as noise after merging")
            return FIRIntersectionResult()

        # 6. Build FIRCrossingRecord for each segment
        crossings: list[FIRCrossingRecord] = []
        for idx, seg in enumerate(merged):
            entry_point = (seg["entry_lat"], seg["entry_lon"])
            exit_point = (seg["exit_lat"], seg["exit_lon"])

            # GC entry/exit distance (Req 9.1, 9.2)
            gc_km, gc_nm = self._calculate_gc_distance(entry_point, exit_point)

            record = FIRCrossingRecord(
                sequence=idx,
                icao_code=seg["icao_code"],
                fir_name=seg["fir_name"],
                country=seg["country"],
                country_code=seg["country_code"],
                entry_point=entry_point,
                exit_point=exit_point,
                segment_distance_km=seg["segment_distance_km"],
                segment_distance_nm=seg["segment_distance_nm"],
                gc_entry_exit_distance_km=gc_km,
                gc_entry_exit_distance_nm=gc_nm,
                segment_geometry=seg.get("segment_geojson", {}),
                calculation_method="postgis_geography",
            )
            crossings.append(record)

        # 7. Calculate total distance as sum of segment distances (Req 8.2)
        total_distance_km = sum(c.segment_distance_km for c in crossings)
        total_distance_nm = sum(c.segment_distance_nm for c in crossings)

        # 8. Validate chain continuity (Req 7.7)
        chain_failures = self._validate_chain_continuity(crossings)

        logger.info(
            "FIR intersection complete: %d crossings, %.2f km / %.2f nm total, %d chain failures",
            len(crossings),
            total_distance_km,
            total_distance_nm,
            len(chain_failures),
        )

        # 9. Return complete result
        return FIRIntersectionResult(
            crossings=crossings,
            total_distance_km=total_distance_km,
            total_distance_nm=total_distance_nm,
            chain_continuity_failures=chain_failures,
        )

    def _build_route_linestring(self, coordinates: list[tuple[float, float]]) -> str:
        """Build PostGIS-compatible WKT LineString from coordinates.

        Converts an ordered list of (lon, lat) coordinate pairs into a WKT
        LineString string with SRID=4326 for use in PostGIS spatial queries.

        Args:
            coordinates: Ordered list of (lon, lat) coordinate pairs.

        Returns:
            WKT LineString string with SRID prefix,
            e.g. 'SRID=4326;LINESTRING(-73.78 40.64, -0.46 51.47)'.

        Raises:
            ValueError: If coordinates list is empty or contains only one point.

        Validates Requirements: 7.1
        """
        if not coordinates:
            raise ValueError("Cannot build LineString from empty coordinate list")
        if len(coordinates) < 2:
            raise ValueError(
                "Cannot build LineString from a single point; "
                "at least two coordinate pairs are required"
            )

        coord_strs = [f"{lon} {lat}" for lon, lat in coordinates]
        return f"SRID=4326;LINESTRING({', '.join(coord_strs)})"

    def _adjust_for_dateline(
        self, coordinates: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        """Shift coordinates ±360° for routes crossing the International Date Line.

        Detects if consecutive coordinate pairs cross ±180° longitude and adjusts
        to maintain geometric continuity for PostGIS operations.

        Args:
            coordinates: Ordered list of (lon, lat) coordinate pairs.

        Returns:
            Adjusted list of (lon, lat) coordinate pairs with continuity preserved.

        Validates Requirements: 18.1, 18.2
        """
        if len(coordinates) <= 1:
            return list(coordinates)

        adjusted = [coordinates[0]]
        offset = 0.0

        for i in range(1, len(coordinates)):
            prev_lon = adjusted[i - 1][0]
            curr_lon = coordinates[i][0] + offset
            delta = curr_lon - prev_lon

            if abs(delta) > 180.0:
                # Crossing detected — shift to maintain continuity
                if delta > 0:
                    offset -= 360.0
                else:
                    offset += 360.0
                curr_lon = coordinates[i][0] + offset

            adjusted.append((curr_lon, coordinates[i][1]))

        return adjusted

    def _execute_postgis_intersection(self, route_wkt: str, db: Session) -> list[dict]:
        """Execute ST_Intersection query against reference.fir_boundaries.

        Runs the core PostGIS spatial query to find all FIR boundary intersections
        with the route line, returning raw results ordered by route fraction.
        Segments shorter than 50m (NOISE_THRESHOLD_M) are filtered out by the
        query's WHERE clause.

        Args:
            route_wkt: WKT LineString of the route (with SRID=4326 prefix).
            db: SQLAlchemy database session.

        Returns:
            List of dicts with intersection data: icao_code, fir_name, country,
            country_code, segment_geojson (parsed dict), segment_distance_km,
            segment_distance_nm, entry_lat, entry_lon, exit_lat, exit_lon,
            route_fraction. Results are ordered by route_fraction ascending.

        Validates Requirements: 7.2, 7.3, 7.4
        """
        sql = text("""
            WITH route AS (
                SELECT ST_GeogFromText(:route_wkt) AS geog,
                       ST_GeomFromText(:route_wkt, 4326) AS geom
            ),
            raw_intersections AS (
                SELECT
                    fb.icao_code,
                    fb.fir_name,
                    fb.country,
                    COALESCE(ifir.country_code, '') AS country_code,
                    ST_Intersection(r.geom, fb.geometry) AS raw_geom,
                    ST_Length(ST_Intersection(r.geog, fb.geometry::geography)) AS segment_length_m,
                    ST_LineLocatePoint(r.geom, ST_Centroid(ST_Intersection(r.geom, fb.geometry))) AS route_fraction
                FROM reference.fir_boundaries fb
                CROSS JOIN route r
                LEFT JOIN iata_firs ifir ON fb.icao_code = ifir.icao_code
                    AND ifir.is_active = true
                WHERE ST_Intersects(r.geom, fb.geometry)
                  AND ST_Length(ST_Intersection(r.geog, fb.geometry::geography)) > :noise_threshold
            ),
            intersections AS (
                SELECT
                    icao_code, fir_name, country, country_code,
                    CASE
                        WHEN ST_GeometryType(raw_geom) = 'ST_MultiLineString'
                            THEN ST_LineMerge(raw_geom)
                        ELSE raw_geom
                    END AS segment_geom,
                    segment_length_m,
                    route_fraction
                FROM raw_intersections
            )
            SELECT
                icao_code, fir_name, country, country_code,
                ST_AsGeoJSON(segment_geom) AS segment_geojson,
                segment_length_m / 1000.0 AS segment_distance_km,
                segment_length_m / 1852.0 AS segment_distance_nm,
                ST_Y(COALESCE(ST_StartPoint(segment_geom), ST_PointN(segment_geom, 1))) AS entry_lat,
                ST_X(COALESCE(ST_StartPoint(segment_geom), ST_PointN(segment_geom, 1))) AS entry_lon,
                ST_Y(COALESCE(ST_EndPoint(segment_geom), ST_PointN(segment_geom, ST_NPoints(segment_geom)))) AS exit_lat,
                ST_X(COALESCE(ST_EndPoint(segment_geom), ST_PointN(segment_geom, ST_NPoints(segment_geom)))) AS exit_lon,
                route_fraction
            FROM intersections
            ORDER BY route_fraction
        """)

        try:
            rows = db.execute(
                sql,
                {
                    "route_wkt": route_wkt,
                    "noise_threshold": self.NOISE_THRESHOLD_M,
                },
            ).fetchall()
        except Exception as e:
            logger.error("PostGIS intersection query failed: %s", str(e))
            raise

        results = []
        for row in rows:
            segment_geojson = json.loads(row.segment_geojson) if row.segment_geojson else None

            # Primary: use SQL-level COALESCE(ST_StartPoint, ST_PointN).
            # Fallback: extract first/last coordinate from GeoJSON geometry
            # so we never default to (0,0) which breaks chain continuity.
            entry_lat = float(row.entry_lat) if row.entry_lat is not None else None
            entry_lon = float(row.entry_lon) if row.entry_lon is not None else None
            exit_lat = float(row.exit_lat) if row.exit_lat is not None else None
            exit_lon = float(row.exit_lon) if row.exit_lon is not None else None

            if (entry_lat is None or exit_lat is None) and segment_geojson:
                coords = segment_geojson.get("coordinates", [])
                if segment_geojson.get("type") == "LineString" and len(coords) >= 2:
                    if entry_lat is None:
                        entry_lon, entry_lat = coords[0][0], coords[0][1]
                    if exit_lat is None:
                        exit_lon, exit_lat = coords[-1][0], coords[-1][1]
                elif segment_geojson.get("type") == "Point" and coords:
                    if entry_lat is None:
                        entry_lon, entry_lat = coords[0], coords[1]
                    if exit_lat is None:
                        exit_lon, exit_lat = coords[0], coords[1]
                elif segment_geojson.get("type") == "MultiLineString" and coords:
                    # Flatten: first coord of first line, last coord of last line
                    if entry_lat is None and coords[0]:
                        entry_lon, entry_lat = coords[0][0][0], coords[0][0][1]
                    if exit_lat is None and coords[-1]:
                        exit_lon, exit_lat = coords[-1][-1][0], coords[-1][-1][1]

            # Last resort: 0.0 (should never happen with the above fallbacks)
            entry_lat = entry_lat if entry_lat is not None else 0.0
            entry_lon = entry_lon if entry_lon is not None else 0.0
            exit_lat = exit_lat if exit_lat is not None else 0.0
            exit_lon = exit_lon if exit_lon is not None else 0.0

            results.append({
                "icao_code": row.icao_code,
                "fir_name": row.fir_name,
                "country": row.country,
                "country_code": row.country_code,
                "segment_geojson": segment_geojson,
                "segment_distance_km": float(row.segment_distance_km),
                "segment_distance_nm": float(row.segment_distance_nm),
                "entry_lat": entry_lat,
                "entry_lon": entry_lon,
                "exit_lat": exit_lat,
                "exit_lon": exit_lon,
                "route_fraction": float(row.route_fraction),
            })

        logger.info(
            "PostGIS intersection found %d FIR crossings for route",
            len(results),
        )
        return results

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great-circle distance between two points in meters.

        Uses the Haversine formula for short-distance comparisons such as
        deduplication tolerance and chain continuity checks.

        Args:
            lat1: Latitude of point 1 in decimal degrees.
            lon1: Longitude of point 1 in decimal degrees.
            lat2: Latitude of point 2 in decimal degrees.
            lon2: Longitude of point 2 in decimal degrees.

        Returns:
            Distance in meters.
        """
        R_M = 6_371_000.0  # Earth radius in meters

        lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
        lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)

        dlat = lat2_r - lat1_r
        dlon = lon2_r - lon1_r

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R_M * c

    def _deduplicate_intersections(self, intersections: list[dict]) -> list[dict]:
        """Merge intersection points within 10m tolerance.

        Removes duplicate intersection points caused by shared FIR boundaries
        to prevent spurious micro-segments. When two intersections have both
        entry and exit points within DEDUP_TOLERANCE_M of each other, the
        second is discarded and its distance is added to the first.

        Args:
            intersections: Raw intersection results from PostGIS, ordered by
                route_fraction.

        Returns:
            Deduplicated list of intersection results.

        Validates Requirements: 19.1, 19.2
        """
        if len(intersections) <= 1:
            return list(intersections)

        deduplicated: list[dict] = [intersections[0]]

        for candidate in intersections[1:]:
            merged = False
            for existing in deduplicated:
                entry_dist = self._haversine_m(
                    existing["entry_lat"], existing["entry_lon"],
                    candidate["entry_lat"], candidate["entry_lon"],
                )
                exit_dist = self._haversine_m(
                    existing["exit_lat"], existing["exit_lon"],
                    candidate["exit_lat"], candidate["exit_lon"],
                )
                if entry_dist <= self.DEDUP_TOLERANCE_M and exit_dist <= self.DEDUP_TOLERANCE_M:
                    # Same intersection from shared boundary — merge distances
                    existing["segment_distance_km"] += candidate["segment_distance_km"]
                    existing["segment_distance_nm"] += candidate["segment_distance_nm"]
                    merged = True
                    break
            if not merged:
                deduplicated.append(candidate)

        logger.debug(
            "Deduplication reduced %d intersections to %d",
            len(intersections),
            len(deduplicated),
        )
        return deduplicated

    def _merge_adjacent_same_fir(self, segments: list[dict]) -> list[dict]:
        """Merge only adjacent segments in the same FIR (preserve re-entries).

        When consecutive route segments fall within the same FIR due to boundary
        noise, merges them while preserving legitimate re-entries where the route
        exits and later re-enters the same FIR.

        Example:
            [FIR_A, FIR_A, FIR_B, FIR_A] → [FIR_A(merged), FIR_B, FIR_A]
            The last FIR_A is a legitimate re-entry and is NOT merged with the first.

        Merged segment takes the entry point of the first and exit point of the
        last, and sums the distances. Segments shorter than NOISE_THRESHOLD_M
        (50m) after merging are discarded as boundary noise.

        Args:
            segments: Ordered list of FIR segment dicts.

        Returns:
            Merged list of FIR segment dicts.

        Validates Requirements: 7.5, 7.6
        """
        if not segments:
            return []

        merged: list[dict] = [segments[0].copy()]

        for seg in segments[1:]:
            current = merged[-1]
            if seg["icao_code"] == current["icao_code"]:
                # Adjacent same-FIR — merge: keep first entry, take last exit, sum distances
                current["exit_lat"] = seg["exit_lat"]
                current["exit_lon"] = seg["exit_lon"]
                current["segment_distance_km"] += seg["segment_distance_km"]
                current["segment_distance_nm"] += seg["segment_distance_nm"]
                # Keep the later route_fraction for ordering context
                current["route_fraction"] = seg["route_fraction"]
                # Prefer the segment_geojson of the longer segment (or keep first)
                if seg.get("segment_geojson"):
                    current["segment_geojson"] = seg["segment_geojson"]
            else:
                merged.append(seg.copy())

        # Discard segments shorter than 50m (NOISE_THRESHOLD_M) as boundary noise
        noise_threshold_km = self.NOISE_THRESHOLD_M / 1000.0
        before_noise = len(merged)
        merged = [s for s in merged if s["segment_distance_km"] >= noise_threshold_km]

        logger.debug(
            "Merge reduced %d segments to %d (%d noise discarded)",
            len(segments),
            len(merged),
            before_noise - len(merged),
        )
        return merged

    def _calculate_gc_distance(
        self, point1: tuple[float, float], point2: tuple[float, float]
    ) -> tuple[float, float]:
        """Calculate great circle distance between two points.

        Uses the Haversine formula to compute the geodesic distance
        between entry and exit points of a FIR crossing.

        Args:
            point1: (lat, lon) of the first point.
            point2: (lat, lon) of the second point.

        Returns:
            Tuple of (distance_km, distance_nm).

        Validates Requirements: 9.1, 9.2
        """
        NM_IN_METERS = 1852.0

        distance_m = self._haversine_m(point1[0], point1[1], point2[0], point2[1])
        distance_km = distance_m / 1000.0
        distance_nm = distance_m / NM_IN_METERS

        return (distance_km, distance_nm)

    def _validate_chain_continuity(
        self, crossings: list[FIRCrossingRecord]
    ) -> list[dict]:
        """Check exit N ≈ entry N+1 within 10m for all consecutive pairs.

        Validates that for each consecutive pair of FIR crossings, the exit
        point of FIR N and the entry point of FIR N+1 are within 10 meters
        of each other. Flags any pair that fails this check.

        Args:
            crossings: Ordered list of FIR crossing records.

        Returns:
            List of failure dicts, each containing the pair indices, exit point,
            entry point, and gap distance in meters.

        Validates Requirements: 7.7
        """
        failures: list[dict] = []

        for i in range(len(crossings) - 1):
            current = crossings[i]
            next_crossing = crossings[i + 1]

            gap_m = self._haversine_m(
                current.exit_point[0], current.exit_point[1],
                next_crossing.entry_point[0], next_crossing.entry_point[1],
            )

            if gap_m > self.CHAIN_CONTINUITY_M:
                failures.append({
                    "pair": (i, i + 1),
                    "exit_point": current.exit_point,
                    "entry_point": next_crossing.entry_point,
                    "gap_distance_m": gap_m,
                })

        if failures:
            logger.warning(
                "Chain continuity validation found %d failure(s)",
                len(failures),
            )

        return failures
