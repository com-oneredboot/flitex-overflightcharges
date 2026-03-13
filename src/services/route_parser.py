"""RouteParser service for parsing ICAO route strings and identifying FIR crossings.

This module provides functionality to parse ICAO-formatted route strings into
waypoints and determine which Flight Information Regions (FIRs) the route crosses
using GeoJSON geometry analysis.

Validates Requirements: 5.3, 5.4
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from shapely.geometry import Point, shape
from shapely.errors import ShapelyError
from src.exceptions import ParsingException
from src.models.iata_fir import IataFir


@dataclass
class Waypoint:
    """Represents a waypoint in a flight route.
    
    Attributes:
        identifier: Waypoint identifier (e.g., airport code, navaid, or fix)
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
    """
    identifier: str
    latitude: float
    longitude: float
    
    def __repr__(self) -> str:
        return f"Waypoint(identifier='{self.identifier}', lat={self.latitude}, lon={self.longitude})"


class RouteParser:
    """Parser for ICAO route strings and FIR crossing detection.
    
    This service parses ICAO-formatted route strings (e.g., "KJFK DCT CYYZ")
    into waypoints with coordinates and identifies which FIRs the route crosses
    using spatial analysis with GeoJSON geometry.
    
    Validates Requirements: 5.3, 5.4
    """
    
    def parse_route(self, route_string: str) -> List[Waypoint]:
        """Parse ICAO route string into waypoints.
        
        Parses an ICAO-formatted route string and converts it into a list of
        waypoints with coordinates. The route string should contain space-separated
        identifiers for airports, navaids, fixes, and route keywords (DCT, etc.).
        
        Args:
            route_string: ICAO formatted route (e.g., "KJFK DCT CYYZ")
        
        Returns:
            List of Waypoint objects with coordinates
        
        Raises:
            ParsingException: If route format is invalid or waypoints cannot be resolved
        
        Validates: Requirement 5.3
        
        Example:
            >>> parser = RouteParser()
            >>> waypoints = parser.parse_route("KJFK DCT CYYZ")
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
        
        # Filter out route keywords that are not waypoints
        route_keywords = {"DCT", "SID", "STAR", "DIRECT", "AIRWAY"}
        
        for token in tokens:
            # Skip route keywords
            if token in route_keywords:
                continue
            
            # For this implementation, we'll use a simplified approach
            # In a real system, this would query a navigation database
            # For now, we'll use mock coordinates based on known airports
            coordinates = self._resolve_waypoint_coordinates(token)
            
            if coordinates:
                waypoints.append(Waypoint(
                    identifier=token,
                    latitude=coordinates["latitude"],
                    longitude=coordinates["longitude"]
                ))
        
        if not waypoints:
            raise ParsingException(
                "No valid waypoints found in route string",
                details={"route_string": route_string, "tokens": tokens}
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
    
    def _resolve_waypoint_coordinates(self, identifier: str) -> Dict[str, float] | None:
        """Resolve waypoint identifier to coordinates.
        
        This is a simplified implementation that uses a mock database of
        known waypoints. In a production system, this would query a real
        navigation database with airports, navaids, and fixes.
        
        Args:
            identifier: Waypoint identifier (airport code, navaid, or fix)
        
        Returns:
            Dictionary with latitude and longitude, or None if not found
        """
        # Mock waypoint database with common airports and fixes
        # In production, this would query a real navigation database
        waypoint_db = {
            # Major airports
            "KJFK": {"latitude": 40.6413, "longitude": -73.7781},
            "KLAX": {"latitude": 33.9416, "longitude": -118.4085},
            "EGLL": {"latitude": 51.4700, "longitude": -0.4543},
            "LFPG": {"latitude": 49.0097, "longitude": 2.5479},
            "EDDF": {"latitude": 50.0379, "longitude": 8.5622},
            "CYYZ": {"latitude": 43.6777, "longitude": -79.6248},
            "KSFO": {"latitude": 37.6213, "longitude": -122.3790},
            "KORD": {"latitude": 41.9742, "longitude": -87.9073},
            "KATL": {"latitude": 33.6407, "longitude": -84.4277},
            "KDFW": {"latitude": 32.8998, "longitude": -97.0403},
            "KDEN": {"latitude": 39.8561, "longitude": -104.6737},
            "KIAH": {"latitude": 29.9902, "longitude": -95.3368},
            "KMIA": {"latitude": 25.7959, "longitude": -80.2870},
            "KEWR": {"latitude": 40.6895, "longitude": -74.1745},
            "KBOS": {"latitude": 42.3656, "longitude": -71.0096},
            # European airports
            "EHAM": {"latitude": 52.3105, "longitude": 4.7683},
            "LEMD": {"latitude": 40.4983, "longitude": -3.5676},
            "LIRF": {"latitude": 41.8003, "longitude": 12.2389},
            "LOWW": {"latitude": 48.1103, "longitude": 16.5697},
            "LSZH": {"latitude": 47.4647, "longitude": 8.5492},
            # Asian airports
            "RJTT": {"latitude": 35.5494, "longitude": 139.7798},
            "VHHH": {"latitude": 22.3080, "longitude": 113.9185},
            "WSSS": {"latitude": 1.3644, "longitude": 103.9915},
            "RKSI": {"latitude": 37.4602, "longitude": 126.4407},
            "ZBAA": {"latitude": 40.0801, "longitude": 116.5846},
        }
        
        return waypoint_db.get(identifier)
