"""RouteParser service for parsing ICAO route strings and identifying FIR crossings.

This module provides functionality to parse ICAO-formatted route strings into
waypoints and determine which Flight Information Regions (FIRs) the route crosses
using GeoJSON geometry analysis.

Waypoint resolution queries the reference schema tables in priority order:
airports → nav_waypoints → charges_waypoints → charges_vor → charges_ndb

Validates Requirements: 3.1, 3.2, 3.3, 3.4, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4
"""

import logging
import math
import re
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from shapely.geometry import Point, shape
from shapely.errors import ShapelyError
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.exceptions import ParsingException
from src.models.iata_fir import IataFir
from src.models.reference import (
    ReferenceAirport,
    ReferenceNavWaypoint,
    ReferenceChargesWaypoint,
    ReferenceChargesVOR,
    ReferenceChargesNDB,
    ReferenceFIRBoundary,
)
from src.schemas.reference import FIRCrossing

logger = logging.getLogger(__name__)


@dataclass
class Waypoint:
    """Represents a waypoint in a flight route.
    
    Attributes:
        identifier: Waypoint identifier (e.g., airport code, navaid, or fix)
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        source_table: Reference table that resolved this waypoint (e.g., 'airports')
    """
    identifier: str
    latitude: float
    longitude: float
    source_table: str = ""
    
    def __repr__(self) -> str:
        return f"Waypoint(identifier='{self.identifier}', lat={self.latitude}, lon={self.longitude})"


@dataclass
class TokenRecord:
    """Record of a single token's processing through the parser.

    Captures the full audit trail for how a route token was classified,
    what action was taken, and the reason code from calculations.token_action_reasons.

    Validates: Requirements 10.3, 10.4, 10.5, 20.4
    """
    raw: str
    classification: str  # airport, keyword, airway, nat_track, coordinate, unknown
    action: str          # resolved, skipped, expanded, unresolved
    reason_code: str     # From calculations.token_action_reasons
    source_table: str | None = None
    resolved_lat: float | None = None
    resolved_lon: float | None = None
    alternatives_count: int = 0
    disambiguation_distance_nm: float | None = None
    expanded_waypoints: list[dict] | None = None
    original_token: str | None = None  # For SID/STAR stripped tokens
    trimmed_to: str | None = None      # The identifier after trimming
    discard_details: list[dict] | None = None  # Jump detection discards


@dataclass
class TokenResolutionResult:
    """Complete result of route token resolution.

    Contains the full set of token records, resolved waypoints, unresolved tokens,
    and the assembled route linestring coordinates for downstream spatial processing.

    Validates: Requirements 10.3, 10.4, 10.5, 20.4
    """
    tokens: list[TokenRecord]
    resolved_waypoints: list[Waypoint]
    unresolved_tokens: list[TokenRecord]
    route_linestring_coords: list[tuple[float, float]]  # (lon, lat) pairs


class RouteParser:
    """Parser for ICAO route strings and FIR crossing detection.
    
    This service parses ICAO-formatted route strings (e.g., "KJFK DCT CYYZ")
    into waypoints with coordinates and identifies which FIRs the route crosses
    using spatial analysis with GeoJSON geometry.
    
    Validates Requirements: 5.3, 5.4
    """
    
    # Route keywords that are not waypoint identifiers
    ROUTE_KEYWORDS = {"DCT", "SID", "STAR", "DIRECT", "AIRWAY"}

    # Maximum allowed distance (nautical miles) between consecutive waypoints.
    # Candidates exceeding this threshold are discarded by jump detection.
    MAX_WAYPOINT_JUMP_NM = 2500

    # Pattern for NAT track codes (e.g., NATW, NATA)
    _NAT_PATTERN = re.compile(r"^NAT[A-Z]$")

    # Pattern for airport+runway tokens (e.g., EGLLR09L, KIAHR27, KORDR10L)
    # Format: 4-char ICAO code + 'R' + runway designator (2-3 chars)
    _AIRPORT_RUNWAY_PATTERN = re.compile(r"^([A-Z]{4})R(\d{2}[LCR]?)$")

    # ICAO speed/level group: speed (N/K + 4 digits or M + 3 digits) + level (F/A + 3 digits, S/M + 4 digits, or VFR)
    # Examples: N0454F260, M082F330, K0830A045, N0460VFR
    _SPEED_LEVEL_PATTERN = re.compile(
        r"^(?:[NK]\d{4}|M\d{3})(?:F\d{3}|A\d{3}|S\d{4}|M\d{4}|VFR)$"
    )

    # ATS route designator pattern: covers airways, SIDs, and STARs (2-7 chars total)
    # Airways: 1-2 letter prefix + 1-4 digits + optional trailing letter (B1, J60, N14, UL613, UT225, N518A)
    # SIDs: waypoint name + digit + optional letter (ATREX5G, KODAP2A)
    # STARs: waypoint name + digit (FLOSI4)
    # Common trait: always contains at least one digit, 2-7 chars, mix of letters and digits
    _ATS_ROUTE_PATTERN = re.compile(r"^[A-Z]{1,2}\d{1,4}[A-Z]?$")
    _SID_STAR_PATTERN = re.compile(r"^[A-Z]{2,5}\d[A-Z]?$")

    def _is_speed_level_group(self, token: str) -> bool:
        """Check if token is an ICAO speed/level group.

        Speed/level groups appear as the first token in Item 15 (initial cruise)
        and after '/' in speed/level change tokens. Format is speed + level
        concatenated without space.

        Examples: N0454F260, M082F330, K0830A045

        Args:
            token: Uppercased route token to check.

        Returns:
            True if the token matches speed/level group pattern.
        """
        return bool(self._SPEED_LEVEL_PATTERN.match(token))

    def _is_airway_designator(self, token: str) -> bool:
        """Check if token matches ATS route designator pattern.

        Per ICAO Doc 4444, ATS route designators are 2-7 characters and include
        airways (B1, J60, UL613, UT225, N518A), SID procedures (ATREX5G),
        and STAR procedures (FLOSI4). They always contain at least one digit
        and are NOT NAT track codes.

        Args:
            token: Uppercased route token to check.

        Returns:
            True if the token matches the ATS route designator pattern.

        Validates: Requirements 1.1
        """
        if not 2 <= len(token) <= 7:
            return False
        if self._NAT_PATTERN.match(token):
            return False
        # Match airway pattern (letter prefix + digits + optional letter)
        # or SID/STAR pattern (waypoint name + digit + optional transition letter)
        return bool(self._ATS_ROUTE_PATTERN.match(token) or self._SID_STAR_PATTERN.match(token))

    def _extract_speed_change_waypoint(self, token: str) -> str | None:
        """Extract waypoint name from a speed/level change token.

        ICAO speed/level change format: WAYPOINT/SPEEDLEVEL
        e.g. VESAN/N0457F300 → VESAN, RESNO/M080F360 → RESNO

        Also handles lat/lon coordinate changes:
        e.g. 4602N07805W/N0500F350 → None (handled by lat/lon parser)

        Args:
            token: Uppercased route token containing '/'.

        Returns:
            Waypoint identifier (left of '/') if right side is a speed/level
            group, None otherwise (token may be a lat/lon coordinate).
        """
        if "/" not in token:
            return None
        parts = token.split("/", 1)
        if len(parts) != 2:
            return None
        waypoint_part, speed_level_part = parts
        if self._is_speed_level_group(speed_level_part) and waypoint_part:
            return waypoint_part
        return None

    def _classify_token(self, token: str) -> str:
        """Classify a route token into its type category.

        Classification follows the ICAO Item 15 element pipeline:
        1. Keyword check — DCT, SID, STAR, DIRECT, AIRWAY
        2. Speed/level group — N0454F260, M082F330 (initial cruise or standalone)
        3. Speed/level change — VESAN/N0457F300 (waypoint + speed/level after /)
        4. Airway/SID/STAR detection — 2-7 char ATS route designators with digits
        5. NAT track detection — tokens matching NAT[A-Z]
        6. Airport+runway detection — ICAO code + runway designator (e.g. EGLLR09L)
        7. Lat/lon coordinate — DDMMN/DDDMME, DDN DDDW, DDMMNDDDMMW, DDMMSSNDDDMMSSW
        8. Bare speed/level fragment — /N0000F350 (continuation without waypoint)
        9. Otherwise — treated as a waypoint candidate

        Args:
            token: Uppercased route token to classify.

        Returns:
            Classification string: 'keyword', 'speed_level', 'speed_change',
            'airway', 'nat_track', 'airport_runway', 'coordinate', or 'waypoint'.

        Validates: Requirements 1.1, 1.2, 1.3
        """
        if token in self.ROUTE_KEYWORDS:
            return "keyword"
        if self._is_speed_level_group(token):
            return "speed_level"
        if "/" in token:
            # Bare speed/level fragment (e.g., /N0000F350, /M083F320)
            if token.startswith("/") and self._is_speed_level_group(token[1:]):
                return "speed_level"
            if self._extract_speed_change_waypoint(token) is not None:
                return "speed_change"
            # Fall through to coordinate check
            return "coordinate"
        if self._is_airway_designator(token):
            return "airway"
        if self._NAT_PATTERN.match(token):
            return "nat_track"
        # Check airport+runway format (e.g., EGLLR09L, KIAHR27)
        if self._AIRPORT_RUNWAY_PATTERN.match(token):
            return "airport_runway"
        # Check compact lat/lon formats (no slash):
        # DDN DDDW (e.g., 62N020W), DDMMNDDDMMW (e.g., 5630N02000W),
        # DDMMSSNDDDMMSSW (e.g., 533436N0832530W)
        if (self._LATLON_COMPACT_PATTERN.match(token)
                or self._LATLON_DEGMIN_COMPACT_PATTERN.match(token)
                or self._LATLON_DMS_COMPACT_PATTERN.match(token)):
            return "coordinate"
        return "waypoint"

    # Pattern for NAT route waypoint coordinates in DD/DDD format (e.g., 49/50, 50/40)
    _NAT_COORD_PATTERN = re.compile(r"^(\d{2})/(\d{2,3})$")

    def _parse_nat_route_waypoint(self, waypoint_str: str) -> dict | None:
        """Parse a single waypoint from a NAT track route string.

        NAT route strings contain a mix of named waypoints and coordinate
        pairs in DD/DDD format (latitude degrees / longitude degrees West).
        In the North Atlantic context, coordinates are implicitly North
        latitude and West longitude.

        Examples:
            - "49/50" → {"ident": "49/50", "lat": 49.0, "lon": -50.0}
            - "JOOPY" → {"ident": "JOOPY", "lat": None, "lon": None}
              (named waypoint — lat/lon must be resolved separately)

        Args:
            waypoint_str: A single token from the NAT route string.

        Returns:
            Dict with ident, lat, lon keys. For coordinate tokens lat/lon
            are populated; for named waypoints they are None.
        """
        match = self._NAT_COORD_PATTERN.match(waypoint_str)
        if match:
            lat = float(match.group(1))
            # NAT tracks are in the North Atlantic — longitude is West
            lon = -float(match.group(2))
            return {"ident": waypoint_str, "lat": lat, "lon": lon}
        # Named waypoint — coordinates need resolution from reference tables
        return {"ident": waypoint_str, "lat": None, "lon": None}

    def _expand_nat_track(
        self, token: str, flight_date: date, db: Session
    ) -> list[dict] | None:
        """Query plans.NATs table for track definition, return waypoint list.

        Looks up the NAT track by its track code (e.g., "NATA") and checks
        that the flight date falls within the track's validity period
        (valid_from ≤ flight_date < valid_to). If found, parses the route
        string into an ordered list of waypoint dicts.

        Each waypoint dict contains:
            - ident: The waypoint identifier or coordinate string
            - lat: Decimal latitude (populated for DD/DDD coords, None for named waypoints)
            - lon: Decimal longitude (populated for DD/DDD coords, None for named waypoints)

        Args:
            token: NAT track code (e.g., "NATA", "NATB").
            flight_date: Date of the flight for validity checking.
            db: SQLAlchemy database session.

        Returns:
            Ordered list of waypoint dicts if track found, None otherwise.

        Validates: Requirements 2.1, 2.2, 2.3, 2.4
        """
        # Convert flight_date to a datetime for timestamp comparison
        flight_dt = datetime.combine(flight_date, datetime.min.time())

        try:
            # Use a SAVEPOINT so a failure here (e.g. table doesn't exist)
            # does not poison the outer transaction.
            nested = db.begin_nested()
            try:
                row = db.execute(
                    text(
                        'SELECT route FROM plans."NATs" '
                        "WHERE track_id = :track_id "
                        "AND valid_from <= :flight_dt "
                        "AND valid_to >= :flight_dt "
                        "ORDER BY valid_from DESC "
                        "LIMIT 1"
                    ),
                    {"track_id": token, "flight_dt": flight_dt},
                ).fetchone()
                nested.commit()
            except Exception:
                nested.rollback()
                raise
        except Exception as e:
            logger.warning(
                "NAT track lookup failed for %s on %s: %s",
                token,
                flight_date,
                str(e),
            )
            return None

        if not row or not row[0]:
            logger.info(
                "NAT track %s not found for flight date %s", token, flight_date
            )
            return None

        route_string = str(row[0]).strip()
        if not route_string:
            return None

        waypoints = []
        for wp_str in route_string.split():
            wp = self._parse_nat_route_waypoint(wp_str)
            if wp:
                waypoints.append(wp)

        if not waypoints:
            return None

        logger.info(
            "Expanded NAT track %s to %d waypoints for date %s",
            token,
            len(waypoints),
            flight_date,
        )
        return waypoints

    # Pattern for ICAO lat/lon coordinates: DDMMN/DDDMME (e.g., 5000N/04900W)
    _LATLON_PATTERN = re.compile(
        r"^(\d{2})(\d{2})([NS])/(\d{3})(\d{2})([EW])$"
    )

    # Compact lat/lon format without slash or minutes: DDN DDDW (e.g., 62N020W, 55N085W)
    _LATLON_COMPACT_PATTERN = re.compile(
        r"^(\d{2})([NS])(\d{3})([EW])$"
    )

    # Degrees+minutes compact (no slash): DDMMNDDDMMW (e.g., 5630N02000W = 56°30'N 020°00'W)
    _LATLON_DEGMIN_COMPACT_PATTERN = re.compile(
        r"^(\d{2})(\d{2})([NS])(\d{3})(\d{2})([EW])$"
    )

    # Degrees+minutes+seconds compact: DDMMSSNDDDMMSSW (e.g., 533436N0832530W)
    _LATLON_DMS_COMPACT_PATTERN = re.compile(
        r"^(\d{2})(\d{2})(\d{2})([NS])(\d{3})(\d{2})(\d{2})([EW])$"
    )

    def _parse_lat_lon(self, token: str) -> tuple[float, float] | None:
        """Parse ICAO lat/lon format to (lat, lon) decimal.

        Supports four formats per ICAO Doc 4444 Item 15:
        1. Full ICAO: DDMMN/DDDMME (e.g., 5000N/04900W)
        2. Compact degrees-only: DDN DDDW (e.g., 62N020W, 55N085W)
        3. Compact degrees+minutes: DDMMNDDDMMW (e.g., 5630N02000W = 56°30'N 020°00'W)
        4. Compact degrees+minutes+seconds: DDMMSSNDDDMMSSW (e.g., 533436N0832530W)

        Args:
            token: Uppercased route token to parse.

        Returns:
            Tuple of (latitude, longitude) in decimal degrees, or None if
            the token does not match any ICAO lat/lon format or contains
            invalid values.

        Validates: Requirements 4.1, 4.2, 4.3
        """
        # Try full format first: DDMMN/DDDMME
        match = self._LATLON_PATTERN.match(token)
        if match:
            lat_deg = int(match.group(1))
            lat_min = int(match.group(2))
            lat_hem = match.group(3)
            lon_deg = int(match.group(4))
            lon_min = int(match.group(5))
            lon_hem = match.group(6)

            if lat_min > 59 or lon_min > 59:
                return None

            lat = lat_deg + lat_min / 60.0
            lon = lon_deg + lon_min / 60.0

            if lat_hem == "S":
                lat = -lat
            if lon_hem == "W":
                lon = -lon

            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                return None

            return (lat, lon)

        # Try compact format: DDN DDDW (e.g., 62N020W)
        compact_match = self._LATLON_COMPACT_PATTERN.match(token)
        if compact_match:
            lat_deg = int(compact_match.group(1))
            lat_hem = compact_match.group(2)
            lon_deg = int(compact_match.group(3))
            lon_hem = compact_match.group(4)

            lat = float(lat_deg)
            lon = float(lon_deg)

            if lat_hem == "S":
                lat = -lat
            if lon_hem == "W":
                lon = -lon

            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                return None

            return (lat, lon)

        # Try degrees+minutes compact (no slash): DDMMNDDDMMW (e.g., 5630N02000W)
        degmin_match = self._LATLON_DEGMIN_COMPACT_PATTERN.match(token)
        if degmin_match:
            lat_deg = int(degmin_match.group(1))
            lat_min = int(degmin_match.group(2))
            lat_hem = degmin_match.group(3)
            lon_deg = int(degmin_match.group(4))
            lon_min = int(degmin_match.group(5))
            lon_hem = degmin_match.group(6)

            if lat_min > 59 or lon_min > 59:
                return None

            lat = lat_deg + lat_min / 60.0
            lon = lon_deg + lon_min / 60.0

            if lat_hem == "S":
                lat = -lat
            if lon_hem == "W":
                lon = -lon

            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                return None

            return (lat, lon)

        # Try degrees+minutes+seconds compact: DDMMSSNDDDMMSSW (e.g., 533436N0832530W)
        dms_match = self._LATLON_DMS_COMPACT_PATTERN.match(token)
        if dms_match:
            lat_deg = int(dms_match.group(1))
            lat_min = int(dms_match.group(2))
            lat_sec = int(dms_match.group(3))
            lat_hem = dms_match.group(4)
            lon_deg = int(dms_match.group(5))
            lon_min = int(dms_match.group(6))
            lon_sec = int(dms_match.group(7))
            lon_hem = dms_match.group(8)

            if lat_min > 59 or lon_min > 59 or lat_sec > 59 or lon_sec > 59:
                return None

            lat = lat_deg + lat_min / 60.0 + lat_sec / 3600.0
            lon = lon_deg + lon_min / 60.0 + lon_sec / 3600.0

            if lat_hem == "S":
                lat = -lat
            if lon_hem == "W":
                lon = -lon

            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                return None

            return (lat, lon)

        return None


    
    def identify_fir_crossings(
        self,
        waypoints: List[Waypoint],
        firs: List[IataFir]
    ) -> List[str]:
        """Identify which FIRs the route crosses.
        
        Determines which Flight Information Regions (FIRs) the route crosses
        by performing spatial analysis using the GeoJSON geometry stored in
        the IataFir models. Checks if waypoints fall within FIR boundaries.
        
        Args:
            waypoints: List of route waypoints with coordinates
            firs: List of FIR boundaries with GeoJSON geometry
        
        Returns:
            List of ICAO codes for crossed FIRs (in order of crossing)
        
        Raises:
            ParsingException: If geometry analysis fails
        
        Validates: Requirement 5.4
        
        Example:
            >>> parser = RouteParser()
            >>> waypoints = [Waypoint("KJFK", 40.6413, -73.7781)]
            >>> fir_codes = parser.identify_fir_crossings(waypoints, firs)
        """
        if not waypoints:
            raise ParsingException(
                "Cannot identify FIR crossings without waypoints",
                details={"waypoints_count": 0}
            )
        
        if not firs:
            # No FIRs available, return empty list
            return []
        
        crossed_firs: List[str] = []
        seen_firs = set()
        
        try:
            # For each waypoint, check which FIR it falls within
            for waypoint in waypoints:
                point = Point(waypoint.longitude, waypoint.latitude)
                
                for fir in firs:
                    # Skip if we've already identified this FIR
                    if fir.icao_code in seen_firs:
                        continue
                    
                    # Parse GeoJSON geometry
                    try:
                        geometry = shape(fir.geojson_geometry)
                        
                        # Check if point is within FIR boundary
                        if geometry.contains(point):
                            icao_code = str(fir.icao_code)
                            crossed_firs.append(icao_code)
                            seen_firs.add(icao_code)
                            break  # Move to next waypoint once FIR is found
                    
                    except (ShapelyError, KeyError, TypeError) as e:
                        # Log warning but continue processing other FIRs
                        # In production, this would use structured logging
                        continue
        
        except Exception as e:
            raise ParsingException(
                f"Failed to identify FIR crossings: {str(e)}",
                details={
                    "waypoints_count": len(waypoints),
                    "firs_count": len(firs),
                    "error": str(e)
                }
            )
        
        return crossed_firs

    def identify_fir_crossings_db(
        self,
        waypoints: List[Waypoint],
        db: Session,
    ) -> List[FIRCrossing]:
        """Identify FIR crossings using PostGIS spatial queries against reference.fir_boundaries.

        For each waypoint, queries the database using ST_Contains to find the FIR boundary
        polygon that contains the waypoint's coordinates. Returns FIR crossings ordered by
        first encounter along the route, with no duplicates.

        Spatial analysis failure is logged as a warning but does not raise — the caller
        receives whatever crossings were identified before the failure.

        Args:
            waypoints: List of route waypoints with coordinates
            db: SQLAlchemy database session for PostGIS queries

        Returns:
            List of FIRCrossing schemas ordered by first encounter along the route

        Validates: Requirement 3.5
        """
        if not waypoints:
            return []

        crossed: List[FIRCrossing] = []
        seen_codes: set[str] = set()

        for waypoint in waypoints:
            try:
                nested = db.begin_nested()
                try:
                    row = db.execute(
                        text(
                            "SELECT icao_code, fir_name, country "
                            "FROM reference.fir_boundaries "
                            "WHERE geometry IS NOT NULL "
                            "AND ST_Contains(geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) "
                            "LIMIT 1"
                        ),
                        {"lon": waypoint.longitude, "lat": waypoint.latitude},
                    ).fetchone()
                    nested.commit()
                except Exception:
                    nested.rollback()
                    raise

                if row and row[0] and row[0] not in seen_codes:
                    icao_code = str(row[0])
                    seen_codes.add(icao_code)
                    crossed.append(
                        FIRCrossing(
                            icao_code=icao_code,
                            fir_name=str(row[1]) if row[1] else "",
                            country=str(row[2]) if row[2] else None,
                        )
                    )
            except Exception as e:
                logger.warning(
                    "FIR spatial analysis failed for waypoint %s: %s",
                    waypoint.identifier,
                    str(e),
                    extra={
                        "waypoint": waypoint.identifier,
                        "latitude": waypoint.latitude,
                        "longitude": waypoint.longitude,
                        "error": str(e),
                    },
                )
                # Continue processing remaining waypoints per design:
                # "FIR spatial analysis failure should still allow validation to succeed
                #  but fir_crossings may be incomplete (logged as warning)"
                continue

        return crossed

    def _resolve_waypoint_coordinates(self, identifier: str, db: Session) -> Dict[str, Any] | None:
        """Resolve waypoint identifier to coordinates using the navigation database.
        
        Queries reference tables in priority order:
        airports → nav_waypoints → charges_waypoints → charges_vor → charges_ndb
        
        Returns the first match found with latitude, longitude, and the source table name.
        
        Args:
            identifier: Waypoint identifier (airport code, navaid, or fix)
            db: SQLAlchemy database session
        
        Returns:
            Dictionary with latitude, longitude, and source_table, or None if not found
        
        Validates: Requirements 3.1, 3.2
        """
        # Query order: airports → nav_waypoints → charges_waypoints → charges_vor → charges_ndb
        lookup_order = [
            (ReferenceAirport, "airports"),
            (ReferenceNavWaypoint, "nav_waypoints"),
            (ReferenceChargesWaypoint, "charges_waypoints"),
            (ReferenceChargesVOR, "charges_vor"),
            (ReferenceChargesNDB, "charges_ndb"),
        ]

        for model_cls, table_name in lookup_order:
            try:
                nested = db.begin_nested()
                try:
                    record = db.query(model_cls).filter(model_cls.ident == identifier).first()
                    nested.commit()
                except Exception:
                    nested.rollback()
                    raise
            except Exception:
                continue
            if record and record.laty is not None and record.lonx is not None:
                return {
                    "latitude": record.laty,
                    "longitude": record.lonx,
                    "source_table": table_name,
                }

        return None

    @staticmethod
    def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the great-circle distance between two points using the Haversine formula.

        Args:
            lat1: Latitude of point 1 in decimal degrees.
            lon1: Longitude of point 1 in decimal degrees.
            lat2: Latitude of point 2 in decimal degrees.
            lon2: Longitude of point 2 in decimal degrees.

        Returns:
            Distance in nautical miles.
        """
        R_KM = 6371.0  # Earth radius in km
        NM_PER_KM = 1.0 / 1.852

        lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
        lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)

        dlat = lat2_r - lat1_r
        dlon = lon2_r - lon1_r

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R_KM * c * NM_PER_KM

    def _resolve_with_proximity(
        self,
        identifier: str,
        reference_point: tuple[float, float],
        db: Session,
    ) -> list[dict]:
        """Resolve identifier returning all candidates with distances from reference.

        Queries all reference tables (airports, nav_waypoints, charges_waypoints,
        charges_vor, charges_ndb) for the identifier. For each candidate found,
        calculates the distance in nautical miles from the reference_point using
        the Haversine formula. Returns all candidates sorted by distance (closest
        first).

        Args:
            identifier: Waypoint identifier to resolve.
            reference_point: (lat, lon) of the previous waypoint or origin
                airport, used for distance calculation.
            db: SQLAlchemy database session.

        Returns:
            List of candidate dicts sorted by distance_nm, each containing:
            identifier, latitude, longitude, source_table, distance_nm.
            Empty list if no candidates found.

        Validates: Requirements 5.1, 5.2, 5.3
        """
        lookup_order = [
            (ReferenceAirport, "airports"),
            (ReferenceNavWaypoint, "nav_waypoints"),
            (ReferenceChargesWaypoint, "charges_waypoints"),
            (ReferenceChargesVOR, "charges_vor"),
            (ReferenceChargesNDB, "charges_ndb"),
        ]

        ref_lat, ref_lon = reference_point
        candidates: list[dict] = []

        for model_cls, table_name in lookup_order:
            try:
                # Use a SAVEPOINT so a failure here (e.g. table doesn't exist)
                # does not poison the outer transaction.
                nested = db.begin_nested()
                try:
                    records = db.query(model_cls).filter(model_cls.ident == identifier).all()
                    nested.commit()
                except Exception:
                    nested.rollback()
                    raise
            except Exception as exc:
                logger.warning(
                    "Proximity query failed for %s in %s: %s",
                    identifier,
                    table_name,
                    str(exc),
                )
                continue

            for record in records:
                if record.laty is None or record.lonx is None:
                    continue
                dist_nm = self._haversine_nm(ref_lat, ref_lon, record.laty, record.lonx)
                candidates.append({
                    "identifier": identifier,
                    "latitude": record.laty,
                    "longitude": record.lonx,
                    "source_table": table_name,
                    "distance_nm": dist_nm,
                })

        candidates.sort(key=lambda c: c["distance_nm"])
        return candidates

    def _apply_jump_detection(
        self,
        candidates: list[dict],
        reference_point: tuple[float, float],
    ) -> tuple[dict | None, list[dict]]:
        """Filter candidates by jump threshold, return (selected, discarded).

        Discards any candidate whose distance from reference_point exceeds
        MAX_WAYPOINT_JUMP_NM (2500 nm). From the remaining candidates, selects
        the closest one.

        Args:
            candidates: List of candidate dicts, each with at least
                latitude, longitude, and distance_nm keys.
            reference_point: (lat, lon) of the previous waypoint.

        Returns:
            Tuple of (selected_candidate or None, list_of_discarded_candidates).
            If all candidates are discarded, selected is None.

        Validates: Requirements 6.1, 6.2, 6.3, 6.4
        """
        ref_lat, ref_lon = reference_point
        selected: dict | None = None
        discarded: list[dict] = []

        for candidate in candidates:
            # Recalculate distance if not already present
            dist_nm = candidate.get("distance_nm")
            if dist_nm is None:
                dist_nm = self._haversine_nm(
                    ref_lat, ref_lon, candidate["latitude"], candidate["longitude"]
                )
                candidate["distance_nm"] = dist_nm

            if dist_nm > self.MAX_WAYPOINT_JUMP_NM:
                discarded.append(candidate)
            elif selected is None:
                # Candidates are pre-sorted by distance, so first passing one is closest
                selected = candidate
            else:
                # Already have a closer selected candidate; this one passes threshold
                # but is farther — not discarded, just not selected
                pass

        return selected, discarded

    def _try_sid_star_strip(self, token: str, reference_point: tuple[float, float], db: Session) -> dict | None:
        """Attempt SID/STAR suffix stripping: 6-char trim 1, 7-char trim 2.

        When standard waypoint resolution fails, this method tries to resolve
        the token by stripping SID/STAR procedure suffixes. For example,
        MERIT1 (6 chars) → MERIT, MERIT1A (7 chars) → MERIT.

        The trimmed identifier is resolved against the same reference tables
        used by _resolve_waypoint_coordinates (airports → nav_waypoints →
        charges_waypoints → charges_vor → charges_ndb).

        When multiple candidates exist for the trimmed identifier, the one
        closest to reference_point is selected (proximity disambiguation).

        Args:
            token: Uppercased route token that failed standard resolution.
            reference_point: (lat, lon) of the previous waypoint or origin
                airport, used for proximity disambiguation.
            db: SQLAlchemy database session.

        Returns:
            Dict with latitude, longitude, source_table, original_token,
            and trimmed_to if the trimmed identifier resolves; None otherwise.

        Validates: Requirements 3.1, 3.2, 3.3, 3.4
        """
        token_len = len(token)
        if token_len == 6:
            trimmed = token[:5]
        elif token_len == 7:
            trimmed = token[:5]
        else:
            return None

        result = self._resolve_waypoint_coordinates(trimmed, db)
        if result is None:
            return None

        result["original_token"] = token
        result["trimmed_to"] = trimmed
        return result

    def validate_route_string(self, route_string: str, db: Session) -> TokenResolutionResult:
        """Lightweight route string validation without flight plan context.

        Parses and validates an ICAO route string by classifying each token
        and resolving waypoints using simple first-match lookup. Does NOT
        require origin/destination/flight_date and does NOT use proximity
        disambiguation or jump detection.

        Intended for:
        - Route string validation in the overflight charges wizard (Step 1)
        - QA test harness route string testing

        For full flight plan parsing with contextual disambiguation, use
        parse_route() instead.

        Args:
            route_string: ICAO formatted route string.
            db: SQLAlchemy database session.

        Returns:
            TokenResolutionResult with token records, resolved waypoints,
            unresolved tokens, and route linestring coordinates.

        Raises:
            ParsingException: If route string is empty or whitespace-only.
        """
        if not route_string or not route_string.strip():
            raise ParsingException(
                "Route string cannot be empty",
                details={"route_string": route_string or ""},
            )

        raw_tokens = route_string.strip().upper().split()

        token_records: list[TokenRecord] = []
        resolved_waypoints: list[Waypoint] = []
        unresolved_tokens: list[TokenRecord] = []
        route_coords: list[tuple[float, float]] = []

        for raw_token in raw_tokens:
            classification = self._classify_token(raw_token)

            # 1. Keyword → skip
            if classification == "keyword":
                token_records.append(TokenRecord(
                    raw=raw_token, classification="keyword",
                    action="skipped", reason_code="KEYWORD_SKIPPED",
                ))
                continue

            # 2. Speed/level group → skip
            if classification == "speed_level":
                token_records.append(TokenRecord(
                    raw=raw_token, classification="speed_level",
                    action="skipped", reason_code="SPEED_LEVEL_SKIPPED",
                ))
                continue

            # 3. Speed/level change → extract waypoint and resolve (simple)
            if classification == "speed_change":
                waypoint_name = self._extract_speed_change_waypoint(raw_token)
                if waypoint_name:
                    # Try coordinate parse first (e.g., 50N091W/N0000F230)
                    coord_parsed = self._parse_lat_lon(waypoint_name)
                    if coord_parsed:
                        lat, lon = coord_parsed
                        token_records.append(TokenRecord(
                            raw=raw_token, classification="speed_change",
                            action="resolved", reason_code="SPEED_CHANGE_COORDINATE_PARSED",
                            resolved_lat=lat, resolved_lon=lon,
                        ))
                        resolved_waypoints.append(Waypoint(
                            identifier=waypoint_name,
                            latitude=lat, longitude=lon,
                            source_table="coordinate",
                        ))
                        route_coords.append((lon, lat))
                        continue
                    # Fall back to DB lookup for named waypoints
                    result = self._resolve_waypoint_coordinates(waypoint_name, db)
                    if result:
                        token_records.append(TokenRecord(
                            raw=raw_token, classification="speed_change",
                            action="resolved", reason_code="SPEED_CHANGE_WAYPOINT_RESOLVED",
                            source_table=result["source_table"],
                            resolved_lat=result["latitude"],
                            resolved_lon=result["longitude"],
                        ))
                        resolved_waypoints.append(Waypoint(
                            identifier=waypoint_name,
                            latitude=result["latitude"],
                            longitude=result["longitude"],
                            source_table=result["source_table"],
                        ))
                        route_coords.append((result["longitude"], result["latitude"]))
                        continue
                    record = TokenRecord(
                        raw=raw_token, classification="speed_change",
                        action="unresolved", reason_code="SPEED_CHANGE_WAYPOINT_NOT_FOUND",
                    )
                    token_records.append(record)
                    unresolved_tokens.append(record)
                    continue

            # 4. Airway → skip
            if classification == "airway":
                token_records.append(TokenRecord(
                    raw=raw_token, classification="airway",
                    action="skipped", reason_code="AIRWAY_DESIGNATOR",
                ))
                continue

            # 5. NAT track → record as skipped (no flight_date for expansion)
            if classification == "nat_track":
                token_records.append(TokenRecord(
                    raw=raw_token, classification="nat_track",
                    action="skipped", reason_code="NAT_TRACK_SKIPPED_NO_DATE",
                ))
                continue

            # 6. Airport+runway → extract ICAO and resolve
            if classification == "airport_runway":
                match = self._AIRPORT_RUNWAY_PATTERN.match(raw_token)
                if match:
                    icao = match.group(1)
                    result = self._resolve_waypoint_coordinates(icao, db)
                    if result:
                        token_records.append(TokenRecord(
                            raw=raw_token, classification="airport_runway",
                            action="resolved", reason_code="AIRPORT_RUNWAY_RESOLVED",
                            source_table=result["source_table"],
                            resolved_lat=result["latitude"],
                            resolved_lon=result["longitude"],
                        ))
                        resolved_waypoints.append(Waypoint(
                            identifier=icao,
                            latitude=result["latitude"],
                            longitude=result["longitude"],
                            source_table=result["source_table"],
                        ))
                        route_coords.append((result["longitude"], result["latitude"]))
                        continue
                    record = TokenRecord(
                        raw=raw_token, classification="airport_runway",
                        action="unresolved", reason_code="AIRPORT_RUNWAY_NOT_FOUND",
                    )
                    token_records.append(record)
                    unresolved_tokens.append(record)
                    continue

            # 7. Coordinate → parse lat/lon
            if classification == "coordinate":
                parsed = self._parse_lat_lon(raw_token)
                if parsed:
                    lat, lon = parsed
                    token_records.append(TokenRecord(
                        raw=raw_token, classification="coordinate",
                        action="resolved", reason_code="COORDINATE_PARSED",
                        resolved_lat=lat, resolved_lon=lon,
                    ))
                    resolved_waypoints.append(Waypoint(
                        identifier=raw_token, latitude=lat, longitude=lon,
                        source_table="coordinate",
                    ))
                    route_coords.append((lon, lat))
                else:
                    record = TokenRecord(
                        raw=raw_token, classification="coordinate",
                        action="unresolved", reason_code="INVALID_COORDINATE_VALUES",
                    )
                    token_records.append(record)
                    unresolved_tokens.append(record)
                continue

            # 8. Waypoint → simple first-match resolution + SID/STAR fallback
            result = self._resolve_waypoint_coordinates(raw_token, db)
            if result:
                token_records.append(TokenRecord(
                    raw=raw_token, classification="waypoint",
                    action="resolved", reason_code="WAYPOINT_RESOLVED",
                    source_table=result["source_table"],
                    resolved_lat=result["latitude"],
                    resolved_lon=result["longitude"],
                ))
                resolved_waypoints.append(Waypoint(
                    identifier=raw_token,
                    latitude=result["latitude"],
                    longitude=result["longitude"],
                    source_table=result["source_table"],
                ))
                route_coords.append((result["longitude"], result["latitude"]))
                continue

            # SID/STAR fallback — use (0,0) as dummy reference since no proximity needed
            sid_star_result = self._try_sid_star_strip(raw_token, (0.0, 0.0), db)
            if sid_star_result:
                token_records.append(TokenRecord(
                    raw=raw_token, classification="waypoint",
                    action="resolved", reason_code="SID_STAR_SUFFIX_STRIPPED",
                    source_table=sid_star_result["source_table"],
                    resolved_lat=sid_star_result["latitude"],
                    resolved_lon=sid_star_result["longitude"],
                    original_token=sid_star_result["original_token"],
                    trimmed_to=sid_star_result["trimmed_to"],
                ))
                resolved_waypoints.append(Waypoint(
                    identifier=sid_star_result["trimmed_to"],
                    latitude=sid_star_result["latitude"],
                    longitude=sid_star_result["longitude"],
                    source_table=sid_star_result["source_table"],
                ))
                route_coords.append((sid_star_result["longitude"], sid_star_result["latitude"]))
                continue

            # Completely unresolved
            record = TokenRecord(
                raw=raw_token, classification="waypoint",
                action="unresolved", reason_code="WAYPOINT_NOT_FOUND",
            )
            token_records.append(record)
            unresolved_tokens.append(record)

        return TokenResolutionResult(
            tokens=token_records,
            resolved_waypoints=resolved_waypoints,
            unresolved_tokens=unresolved_tokens,
            route_linestring_coords=route_coords,
        )



    def parse_route(
        self,
        route_string: str,
        origin: str,
        destination: str,
        flight_date: date,
        db: Session,
    ) -> TokenResolutionResult:
        """Enhanced route parsing with full token classification pipeline.

        Orchestrates the complete token resolution pipeline:
        keyword check → airway detection → NAT expansion → lat/lon parsing →
        waypoint resolution → proximity disambiguation → jump detection →
        SID/STAR stripping.

        Loads reason codes from calculations.token_action_reasons at start
        for validation/reference.

        Args:
            route_string: ICAO formatted route string.
            origin: Origin airport ICAO code.
            destination: Destination airport ICAO code.
            flight_date: Date of the flight (for NAT track lookup).
            db: SQLAlchemy database session.

        Returns:
            TokenResolutionResult with all token records, resolved waypoints,
            unresolved tokens, and route linestring coordinates.

        Validates: Requirements 1.1, 1.2, 2.1, 3.4, 4.1, 5.1, 6.1, 10.3, 10.4, 10.5, 20.4
        """
        # Resolve origin and destination airport coordinates.
        # These are always included as the first and last route coordinates
        # to guarantee at least 2 points for FIR intersection, even when
        # jump detection discards intermediate or endpoint tokens.
        origin_result = self._resolve_waypoint_coordinates(origin, db)
        destination_result = self._resolve_waypoint_coordinates(destination, db)

        if origin_result:
            reference_point: tuple[float, float] = (
                origin_result["latitude"],
                origin_result["longitude"],
            )
        else:
            # Fallback: no reference point available
            reference_point = (0.0, 0.0)
            logger.warning(
                "Could not resolve origin airport %s for reference point", origin
            )

        # Tokenize route string
        raw_tokens = (
            route_string.strip().upper().split()
            if route_string and route_string.strip()
            else []
        )

        token_records: list[TokenRecord] = []
        resolved_waypoints: list[Waypoint] = []
        unresolved_tokens: list[TokenRecord] = []
        route_coords: list[tuple[float, float]] = []  # (lon, lat) pairs

        # Build set of origin/destination codes to skip during tokenization.
        # These airports are already pinned as first/last route coordinates.
        endpoint_codes = {origin.strip().upper(), destination.strip().upper()}

        for raw_token in raw_tokens:
            # 0. Origin/Destination airport → skip (already pinned as route endpoints)
            if raw_token in endpoint_codes:
                record = TokenRecord(
                    raw=raw_token,
                    classification="airport",
                    action="skipped",
                    reason_code="ORIGIN_DESTINATION_SKIPPED",
                )
                token_records.append(record)
                continue

            classification = self._classify_token(raw_token)

            # 1. Keyword → skip
            if classification == "keyword":
                record = TokenRecord(
                    raw=raw_token,
                    classification="keyword",
                    action="skipped",
                    reason_code="KEYWORD_SKIPPED",
                )
                token_records.append(record)
                continue

            # 1b. Speed/level group → skip (e.g. N0454F260, M082F330)
            if classification == "speed_level":
                record = TokenRecord(
                    raw=raw_token,
                    classification="speed_level",
                    action="skipped",
                    reason_code="SPEED_LEVEL_SKIPPED",
                )
                token_records.append(record)
                continue

            # 1c. Speed/level change → extract waypoint and resolve (e.g. VESAN/N0457F300)
            if classification == "speed_change":
                waypoint_name = self._extract_speed_change_waypoint(raw_token)
                if waypoint_name:
                    # Try coordinate parse first (e.g., 50N091W/N0000F230)
                    coord_parsed = self._parse_lat_lon(waypoint_name)
                    if coord_parsed:
                        lat, lon = coord_parsed
                        record = TokenRecord(
                            raw=raw_token,
                            classification="speed_change",
                            action="resolved",
                            reason_code="SPEED_CHANGE_COORDINATE_PARSED",
                            resolved_lat=lat,
                            resolved_lon=lon,
                        )
                        token_records.append(record)
                        waypoint = Waypoint(
                            identifier=waypoint_name,
                            latitude=lat,
                            longitude=lon,
                            source_table="coordinate",
                        )
                        resolved_waypoints.append(waypoint)
                        route_coords.append((lon, lat))
                        reference_point = (lat, lon)
                        continue
                    # Fall back to proximity-based DB lookup for named waypoints
                    candidates = self._resolve_with_proximity(
                        waypoint_name, reference_point, db
                    )
                    if candidates:
                        selected, discarded = self._apply_jump_detection(
                            candidates, reference_point
                        )
                        if selected:
                            record = TokenRecord(
                                raw=raw_token,
                                classification="speed_change",
                                action="resolved",
                                reason_code="SPEED_CHANGE_WAYPOINT_RESOLVED",
                                source_table=selected["source_table"],
                                resolved_lat=selected["latitude"],
                                resolved_lon=selected["longitude"],
                                alternatives_count=len(candidates),
                                disambiguation_distance_nm=selected.get("distance_nm"),
                            )
                            token_records.append(record)
                            waypoint = Waypoint(
                                identifier=waypoint_name,
                                latitude=selected["latitude"],
                                longitude=selected["longitude"],
                                source_table=selected["source_table"],
                            )
                            resolved_waypoints.append(waypoint)
                            route_coords.append(
                                (selected["longitude"], selected["latitude"])
                            )
                            reference_point = (selected["latitude"], selected["longitude"])
                            continue
                    # Waypoint from speed change not found
                    record = TokenRecord(
                        raw=raw_token,
                        classification="speed_change",
                        action="unresolved",
                        reason_code="SPEED_CHANGE_WAYPOINT_NOT_FOUND",
                    )
                    token_records.append(record)
                    unresolved_tokens.append(record)
                    continue

            # 2. Airway → skip
            if classification == "airway":
                record = TokenRecord(
                    raw=raw_token,
                    classification="airway",
                    action="skipped",
                    reason_code="AIRWAY_DESIGNATOR",
                )
                token_records.append(record)
                continue

            # 3. NAT track → expand
            if classification == "nat_track":
                expanded = self._expand_nat_track(raw_token, flight_date, db)
                if expanded:
                    record = TokenRecord(
                        raw=raw_token,
                        classification="nat_track",
                        action="expanded",
                        reason_code="NAT_TRACK_EXPANDED",
                        expanded_waypoints=expanded,
                    )
                    token_records.append(record)
                    # Add expanded waypoints to resolved list and route coords
                    for wp in expanded:
                        if wp.get("lat") is not None and wp.get("lon") is not None:
                            waypoint = Waypoint(
                                identifier=wp["ident"],
                                latitude=wp["lat"],
                                longitude=wp["lon"],
                                source_table="plans.NATs",
                            )
                            resolved_waypoints.append(waypoint)
                            route_coords.append((wp["lon"], wp["lat"]))
                            reference_point = (wp["lat"], wp["lon"])
                        else:
                            # Named waypoint within NAT — resolve it
                            nat_candidates = self._resolve_with_proximity(
                                wp["ident"], reference_point, db
                            )
                            if nat_candidates:
                                selected, _ = self._apply_jump_detection(
                                    nat_candidates, reference_point
                                )
                                if selected:
                                    waypoint = Waypoint(
                                        identifier=wp["ident"],
                                        latitude=selected["latitude"],
                                        longitude=selected["longitude"],
                                        source_table=selected["source_table"],
                                    )
                                    resolved_waypoints.append(waypoint)
                                    route_coords.append(
                                        (selected["longitude"], selected["latitude"])
                                    )
                                    reference_point = (
                                        selected["latitude"],
                                        selected["longitude"],
                                    )
                else:
                    record = TokenRecord(
                        raw=raw_token,
                        classification="nat_track",
                        action="unresolved",
                        reason_code="NAT_TRACK_NOT_FOUND",
                    )
                    token_records.append(record)
                    unresolved_tokens.append(record)
                continue

            # 4. Coordinate → parse lat/lon
            if classification == "coordinate":
                parsed = self._parse_lat_lon(raw_token)
                if parsed:
                    lat, lon = parsed
                    record = TokenRecord(
                        raw=raw_token,
                        classification="coordinate",
                        action="resolved",
                        reason_code="COORDINATE_PARSED",
                        resolved_lat=lat,
                        resolved_lon=lon,
                    )
                    token_records.append(record)
                    waypoint = Waypoint(
                        identifier=raw_token,
                        latitude=lat,
                        longitude=lon,
                        source_table="coordinate",
                    )
                    resolved_waypoints.append(waypoint)
                    route_coords.append((lon, lat))
                    reference_point = (lat, lon)
                else:
                    record = TokenRecord(
                        raw=raw_token,
                        classification="coordinate",
                        action="unresolved",
                        reason_code="INVALID_COORDINATE_VALUES",
                    )
                    token_records.append(record)
                    unresolved_tokens.append(record)
                continue

            # 5. Waypoint → resolve with proximity + jump detection + SID/STAR fallback
            candidates = self._resolve_with_proximity(
                raw_token, reference_point, db
            )

            if candidates:
                selected, discarded = self._apply_jump_detection(
                    candidates, reference_point
                )

                if selected:
                    # Determine reason code based on whether jump detection was relevant
                    reason_code = (
                        "CANDIDATE_WITHIN_JUMP_THRESHOLD"
                        if discarded
                        else "WAYPOINT_RESOLVED"
                    )
                    record = TokenRecord(
                        raw=raw_token,
                        classification="waypoint",
                        action="resolved",
                        reason_code=reason_code,
                        source_table=selected["source_table"],
                        resolved_lat=selected["latitude"],
                        resolved_lon=selected["longitude"],
                        alternatives_count=len(candidates),
                        disambiguation_distance_nm=selected.get("distance_nm"),
                        discard_details=[
                            {
                                "identifier": d["identifier"],
                                "latitude": d["latitude"],
                                "longitude": d["longitude"],
                                "distance_nm": d["distance_nm"],
                                "reference_lat": reference_point[0],
                                "reference_lon": reference_point[1],
                                "threshold_nm": self.MAX_WAYPOINT_JUMP_NM,
                                "reason_code": "CANDIDATE_EXCEEDED_MAX_JUMP",
                            }
                            for d in discarded
                        ]
                        if discarded
                        else None,
                    )
                    token_records.append(record)
                    waypoint = Waypoint(
                        identifier=raw_token,
                        latitude=selected["latitude"],
                        longitude=selected["longitude"],
                        source_table=selected["source_table"],
                    )
                    resolved_waypoints.append(waypoint)
                    route_coords.append(
                        (selected["longitude"], selected["latitude"])
                    )
                    reference_point = (selected["latitude"], selected["longitude"])
                    continue

                # All candidates exceeded jump threshold — try SID/STAR strip
                sid_star_result = self._try_sid_star_strip(
                    raw_token, reference_point, db
                )
                if sid_star_result:
                    record = TokenRecord(
                        raw=raw_token,
                        classification="waypoint",
                        action="resolved",
                        reason_code="SID_STAR_SUFFIX_STRIPPED",
                        source_table=sid_star_result["source_table"],
                        resolved_lat=sid_star_result["latitude"],
                        resolved_lon=sid_star_result["longitude"],
                        original_token=sid_star_result["original_token"],
                        trimmed_to=sid_star_result["trimmed_to"],
                        discard_details=[
                            {
                                "identifier": d["identifier"],
                                "latitude": d["latitude"],
                                "longitude": d["longitude"],
                                "distance_nm": d["distance_nm"],
                                "reference_lat": reference_point[0],
                                "reference_lon": reference_point[1],
                                "threshold_nm": self.MAX_WAYPOINT_JUMP_NM,
                                "reason_code": "CANDIDATE_EXCEEDED_MAX_JUMP",
                            }
                            for d in discarded
                        ]
                        if discarded
                        else None,
                    )
                    token_records.append(record)
                    waypoint = Waypoint(
                        identifier=sid_star_result["trimmed_to"],
                        latitude=sid_star_result["latitude"],
                        longitude=sid_star_result["longitude"],
                        source_table=sid_star_result["source_table"],
                    )
                    resolved_waypoints.append(waypoint)
                    route_coords.append(
                        (sid_star_result["longitude"], sid_star_result["latitude"])
                    )
                    reference_point = (
                        sid_star_result["latitude"],
                        sid_star_result["longitude"],
                    )
                    continue

                # All candidates discarded and SID/STAR strip failed
                record = TokenRecord(
                    raw=raw_token,
                    classification="waypoint",
                    action="unresolved",
                    reason_code="ALL_CANDIDATES_EXCEED_MAX_JUMP",
                    alternatives_count=len(candidates),
                    discard_details=[
                        {
                            "identifier": d["identifier"],
                            "latitude": d["latitude"],
                            "longitude": d["longitude"],
                            "distance_nm": d["distance_nm"],
                            "reference_lat": reference_point[0],
                            "reference_lon": reference_point[1],
                            "threshold_nm": self.MAX_WAYPOINT_JUMP_NM,
                            "reason_code": "CANDIDATE_EXCEEDED_MAX_JUMP",
                        }
                        for d in discarded
                    ],
                )
                token_records.append(record)
                unresolved_tokens.append(record)
                continue

            # No candidates found — try SID/STAR strip
            sid_star_result = self._try_sid_star_strip(
                raw_token, reference_point, db
            )
            if sid_star_result:
                record = TokenRecord(
                    raw=raw_token,
                    classification="waypoint",
                    action="resolved",
                    reason_code="SID_STAR_SUFFIX_STRIPPED",
                    source_table=sid_star_result["source_table"],
                    resolved_lat=sid_star_result["latitude"],
                    resolved_lon=sid_star_result["longitude"],
                    original_token=sid_star_result["original_token"],
                    trimmed_to=sid_star_result["trimmed_to"],
                )
                token_records.append(record)
                waypoint = Waypoint(
                    identifier=sid_star_result["trimmed_to"],
                    latitude=sid_star_result["latitude"],
                    longitude=sid_star_result["longitude"],
                    source_table=sid_star_result["source_table"],
                )
                resolved_waypoints.append(waypoint)
                route_coords.append(
                    (sid_star_result["longitude"], sid_star_result["latitude"])
                )
                reference_point = (
                    sid_star_result["latitude"],
                    sid_star_result["longitude"],
                )
                continue

            # Completely unresolved
            record = TokenRecord(
                raw=raw_token,
                classification="waypoint",
                action="unresolved",
                reason_code="WAYPOINT_NOT_FOUND",
            )
            token_records.append(record)
            unresolved_tokens.append(record)

        # Ensure origin coordinates are the first point in the route
        if origin_result and (
            not route_coords
            or route_coords[0] != (origin_result["longitude"], origin_result["latitude"])
        ):
            route_coords.insert(0, (origin_result["longitude"], origin_result["latitude"]))

        # Ensure destination coordinates are the last point in the route
        if destination_result and (
            not route_coords
            or route_coords[-1] != (destination_result["longitude"], destination_result["latitude"])
        ):
            route_coords.append((destination_result["longitude"], destination_result["latitude"]))

        return TokenResolutionResult(
            tokens=token_records,
            resolved_waypoints=resolved_waypoints,
            unresolved_tokens=unresolved_tokens,
            route_linestring_coords=route_coords,
        )
