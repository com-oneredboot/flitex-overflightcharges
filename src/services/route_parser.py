"""RouteParser service for parsing ICAO route strings and identifying FIR crossings.

This module provides functionality to parse ICAO-formatted route strings into
waypoints and determine which Flight Information Regions (FIRs) the route crosses
using GeoJSON geometry analysis.

Waypoint resolution queries the reference schema tables in priority order:
airports → nav_waypoints → charges_waypoints → charges_vor → charges_ndb

Validates Requirements: 3.1, 3.2, 3.3, 3.4, 5.3, 5.4
"""

import logging
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


class RouteParser:
    """Parser for ICAO route strings and FIR crossing detection.
    
    This service parses ICAO-formatted route strings (e.g., "KJFK DCT CYYZ")
    into waypoints with coordinates and identifies which FIRs the route crosses
    using spatial analysis with GeoJSON geometry.
    
    Validates Requirements: 5.3, 5.4
    """
    
    # Route keywords that are not waypoint identifiers
    ROUTE_KEYWORDS = {"DCT", "SID", "STAR", "DIRECT", "AIRWAY"}

    def parse_route(self, route_string: str, db: Session) -> List[Waypoint]:
        """Parse ICAO route string into waypoints resolved against the navigation database.
        
        Parses an ICAO-formatted route string and resolves each identifier against
        the reference schema tables. Route keywords (DCT, SID, STAR, DIRECT, AIRWAY)
        are skipped. Unresolved identifiers are collected and returned via
        ParsingException if no waypoints resolve, or silently skipped if some do.
        
        Args:
            route_string: ICAO formatted route (e.g., "KJFK DCT CYYZ")
            db: SQLAlchemy database session for querying reference tables
        
        Returns:
            List of Waypoint objects with coordinates and source_table
        
        Raises:
            ParsingException: If route format is invalid or no waypoints can be resolved.
                When some identifiers are unresolved, the exception details include
                an 'unresolved' key listing them.
        
        Validates: Requirements 3.1, 3.2, 3.3, 3.4
        
        Example:
            >>> parser = RouteParser()
            >>> waypoints = parser.parse_route("KJFK DCT CYYZ", db)
            >>> len(waypoints)
            2
        """
        if not route_string or not route_string.strip():
            raise ParsingException(
                "Route string cannot be empty",
                details={"route_string": route_string}
            )
        
        # Split route string into tokens
        tokens = route_string.strip().upper().split()
        
        if not tokens:
            raise ParsingException(
                "Route string must contain at least one waypoint",
                details={"route_string": route_string}
            )
        
        waypoints: List[Waypoint] = []
        unresolved: List[str] = []
        
        for token in tokens:
            # Skip route keywords
            if token in self.ROUTE_KEYWORDS:
                continue
            
            # Resolve against navigation database
            result = self._resolve_waypoint_coordinates(token, db)
            
            if result:
                waypoints.append(Waypoint(
                    identifier=token,
                    latitude=result["latitude"],
                    longitude=result["longitude"],
                    source_table=result["source_table"],
                ))
            else:
                unresolved.append(token)
        
        if not waypoints:
            raise ParsingException(
                "No valid waypoints found in route string",
                details={
                    "route_string": route_string,
                    "tokens": tokens,
                    "unresolved": unresolved,
                }
            )
        
        return waypoints
    
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
            record = db.query(model_cls).filter(model_cls.ident == identifier).first()
            if record and record.laty is not None and record.lonx is not None:
                return {
                    "latitude": record.laty,
                    "longitude": record.lonx,
                    "source_table": table_name,
                }

        return None
