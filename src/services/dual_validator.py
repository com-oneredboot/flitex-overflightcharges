"""Dual-System Validator for PostGIS vs Shapely FIR intersection comparison.

This module provides the DualValidator class that runs Shapely-based planar
intersection independently and compares results against PostGIS geodesic
intersection. Every route calculation is validated by both systems to detect
spatial computation errors during early rollout.

The validator compares:
- FIR lists (which FIRs each system identifies)
- Per-FIR distances (segment length divergence)
- Flags routes for review when lists differ or divergence exceeds 2%

Validates Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
"""

import logging
from dataclasses import dataclass, field

from shapely.geometry import LineString
from shapely import wkb
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.fir_intersection_engine import FIRCrossingRecord

logger = logging.getLogger(__name__)


@dataclass
class DualValidationResult:
    """Result of dual-system validation comparison.

    Captures the FIR lists from both PostGIS and Shapely, whether they match,
    the maximum distance divergence percentage, and per-FIR comparison details.

    Validates Requirements: 12.2, 12.3, 12.4, 12.5
    """

    postgis_fir_list: list[str] = field(default_factory=list)
    shapely_fir_list: list[str] = field(default_factory=list)
    fir_lists_match: bool = True
    max_distance_divergence_pct: float = 0.0
    flagged_for_review: bool = False  # True if lists differ or divergence > 2%
    per_fir_comparison: list[dict] = field(default_factory=list)


# Approximate conversion factor: 1 degree of latitude ≈ 111.32 km
_DEG_TO_KM = 111.32


class DualValidator:
    """Validator that runs Shapely planar intersection and compares with PostGIS results.

    For every route calculation, this validator independently computes FIR
    crossings using Shapely (planar geometry) and compares the results against
    the PostGIS (geodesic geography) results. Discrepancies are flagged for
    human review.

    Validates Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
    """

    DIVERGENCE_THRESHOLD_PCT = 2.0

    def validate(
        self,
        coordinates: list[tuple[float, float]],
        postgis_crossings: list[FIRCrossingRecord],
        db: Session,
    ) -> DualValidationResult:
        """Run Shapely intersection and compare with PostGIS results.

        Args:
            coordinates: Ordered list of (lon, lat) coordinate pairs.
            postgis_crossings: FIR crossing records from PostGIS intersection.
            db: SQLAlchemy database session for loading FIR geometries.

        Returns:
            DualValidationResult with comparison details.

        Validates Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
        """
        # 1. Extract PostGIS FIR list (ordered by sequence)
        postgis_fir_list = [c.icao_code for c in postgis_crossings]

        # Build a lookup of PostGIS distances keyed by icao_code.
        # If a FIR appears multiple times (re-entry), sum the distances.
        postgis_distances: dict[str, float] = {}
        for c in postgis_crossings:
            postgis_distances[c.icao_code] = (
                postgis_distances.get(c.icao_code, 0.0) + c.segment_distance_km
            )

        # 2. Run Shapely intersection independently
        shapely_results = self._shapely_intersection(coordinates, db)

        # 3. Extract Shapely FIR list
        shapely_fir_list = [r["icao_code"] for r in shapely_results]

        # Build Shapely distance lookup (icao_code -> distance_km)
        shapely_distances: dict[str, float] = {}
        for r in shapely_results:
            shapely_distances[r["icao_code"]] = (
                shapely_distances.get(r["icao_code"], 0.0) + r["distance_km"]
            )

        # 4. Compare FIR lists — use unique ordered lists for comparison
        fir_lists_match = postgis_fir_list == shapely_fir_list

        # 5. Compare per-FIR distances for FIRs present in both systems
        per_fir_comparison: list[dict] = []
        max_divergence_pct = 0.0

        # Collect all unique FIR codes from both systems
        all_fir_codes = list(
            dict.fromkeys(postgis_fir_list + shapely_fir_list)
        )

        for icao_code in all_fir_codes:
            postgis_dist = postgis_distances.get(icao_code)
            shapely_dist = shapely_distances.get(icao_code)

            # Compute divergence percentage
            if postgis_dist is not None and shapely_dist is not None:
                if postgis_dist > 0:
                    divergence_pct = (
                        abs(postgis_dist - shapely_dist) / postgis_dist * 100.0
                    )
                elif shapely_dist > 0:
                    # PostGIS is zero but Shapely is not — 100% divergence
                    divergence_pct = 100.0
                else:
                    # Both zero — no divergence
                    divergence_pct = 0.0
            else:
                # FIR only in one system — treat as 100% divergence
                divergence_pct = 100.0

            if divergence_pct > max_divergence_pct:
                max_divergence_pct = divergence_pct

            per_fir_comparison.append({
                "icao_code": icao_code,
                "postgis_distance_km": postgis_dist,
                "shapely_distance_km": shapely_dist,
                "divergence_pct": round(divergence_pct, 4),
            })

        # 6. Flag for review if FIR lists differ or max divergence > threshold
        flagged_for_review = (
            not fir_lists_match
            or max_divergence_pct > self.DIVERGENCE_THRESHOLD_PCT
        )

        if flagged_for_review:
            logger.warning(
                "Route flagged for review: fir_lists_match=%s, "
                "max_divergence=%.2f%%, threshold=%.2f%%",
                fir_lists_match,
                max_divergence_pct,
                self.DIVERGENCE_THRESHOLD_PCT,
            )

        # 7. Return complete DualValidationResult
        return DualValidationResult(
            postgis_fir_list=postgis_fir_list,
            shapely_fir_list=shapely_fir_list,
            fir_lists_match=fir_lists_match,
            max_distance_divergence_pct=round(max_divergence_pct, 4),
            flagged_for_review=flagged_for_review,
            per_fir_comparison=per_fir_comparison,
        )

    def _shapely_intersection(
        self,
        coordinates: list[tuple[float, float]],
        db: Session,
    ) -> list[dict]:
        """Compute FIR crossings using Shapely (planar geometry).

        Loads all FIR boundary geometries from the database, constructs a
        Shapely LineString from the route coordinates, and computes the
        intersection with each FIR polygon. Returns a list of dicts with
        icao_code, fir_name, and approximate distance in km.

        The distance is computed using planar geometry (degree-based length
        converted to approximate km), which will differ from PostGIS geodesic
        results — this difference is expected and is what the dual validation
        measures.

        Args:
            coordinates: Ordered list of (lon, lat) coordinate pairs.
            db: SQLAlchemy database session.

        Returns:
            List of dicts with keys: icao_code, fir_name, distance_km
            (planar length converted to approximate km). Only FIRs that
            the route actually intersects are included.

        Validates Requirements: 12.1
        """
        if not coordinates or len(coordinates) < 2:
            logger.info(
                "Insufficient coordinates (%d) for Shapely intersection",
                len(coordinates) if coordinates else 0,
            )
            return []

        # 1. Construct Shapely LineString from (lon, lat) coordinate pairs
        route_line = LineString(coordinates)

        # 2. Load all FIR boundary geometries from DB
        fir_boundaries = self._load_fir_boundaries(db)

        if not fir_boundaries:
            logger.warning("No FIR boundaries loaded from database")
            return []

        # 3. Intersect route line with each FIR polygon
        results: list[dict] = []
        for fir in fir_boundaries:
            fir_polygon = fir["geometry"]
            icao_code = fir["icao_code"]
            fir_name = fir["fir_name"]

            if not route_line.intersects(fir_polygon):
                continue

            intersection = route_line.intersection(fir_polygon)

            # Skip empty intersections
            if intersection.is_empty:
                continue

            # Calculate planar length and convert to approximate km
            # The length is in degrees; multiply by ~111.32 km/degree as
            # a rough mid-latitude approximation for planar comparison
            planar_length_deg = intersection.length
            distance_km = planar_length_deg * _DEG_TO_KM

            # Skip negligible intersections (noise threshold ~50m = 0.05 km)
            if distance_km < 0.05:
                continue

            results.append({
                "icao_code": icao_code,
                "fir_name": fir_name,
                "distance_km": distance_km,
            })

        # Sort by distance descending for consistent ordering
        results.sort(key=lambda r: r["icao_code"])

        logger.info(
            "Shapely intersection found %d FIR crossings",
            len(results),
        )
        return results

    def _load_fir_boundaries(self, db: Session) -> list[dict]:
        """Load all FIR boundary geometries from the database.

        Queries reference.fir_boundaries and converts each geometry from
        WKB (Well-Known Binary) to a Shapely geometry object.

        Args:
            db: SQLAlchemy database session.

        Returns:
            List of dicts with keys: icao_code, fir_name, geometry (Shapely).
        """
        sql = text("""
            SELECT
                icao_code,
                fir_name,
                ST_AsBinary(geometry) AS geom_wkb
            FROM reference.fir_boundaries
            WHERE geometry IS NOT NULL
              AND icao_code IS NOT NULL
        """)

        try:
            rows = db.execute(sql).fetchall()
        except Exception as e:
            logger.error("Failed to load FIR boundaries for Shapely: %s", str(e))
            raise

        boundaries: list[dict] = []
        for row in rows:
            try:
                geom = wkb.loads(bytes(row.geom_wkb))
                boundaries.append({
                    "icao_code": row.icao_code,
                    "fir_name": row.fir_name,
                    "geometry": geom,
                })
            except Exception as e:
                logger.warning(
                    "Failed to parse geometry for FIR %s: %s",
                    row.icao_code,
                    str(e),
                )
                continue

        logger.debug("Loaded %d FIR boundaries for Shapely validation", len(boundaries))
        return boundaries
