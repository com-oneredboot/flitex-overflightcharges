"""Unit tests for RouteParser service.

Tests the ICAO route parsing and FIR crossing identification functionality.
"""

import pytest
from unittest.mock import Mock
from src.services.route_parser import RouteParser, Waypoint
from src.exceptions import ParsingException
from src.models.iata_fir import IataFir


class TestRouteParser:
    """Test suite for RouteParser service."""
    
    @pytest.fixture
    def parser(self):
        """Create a RouteParser instance."""
        return RouteParser()
    
    @pytest.fixture
    def sample_firs(self):
        """Create sample FIR records for testing."""
        # Create mock FIR with simple rectangular geometry
        fir1 = Mock(spec=IataFir)
        fir1.icao_code = "KZNY"
        fir1.fir_name = "New York FIR"
        fir1.country_code = "US"
        fir1.geojson_geometry = {
            "type": "Polygon",
            "coordinates": [[
                [-75.0, 39.0],
                [-72.0, 39.0],
                [-72.0, 42.0],
                [-75.0, 42.0],
                [-75.0, 39.0]
            ]]
        }
        
        fir2 = Mock(spec=IataFir)
        fir2.icao_code = "CZYZ"
        fir2.fir_name = "Toronto FIR"
        fir2.country_code = "CA"
        fir2.geojson_geometry = {
            "type": "Polygon",
            "coordinates": [[
                [-81.0, 42.0],
                [-78.0, 42.0],
                [-78.0, 45.0],
                [-81.0, 45.0],
                [-81.0, 42.0]
            ]]
        }
        
        return [fir1, fir2]
    
    # Test parse_route() method
    
    def test_parse_route_simple_route(self, parser):
        """Test parsing a simple route with two airports."""
        route_string = "KJFK DCT CYYZ"
        waypoints = parser.parse_route(route_string)
        
        assert len(waypoints) == 2
        assert waypoints[0].identifier == "KJFK"
        assert waypoints[1].identifier == "CYYZ"
        assert isinstance(waypoints[0].latitude, float)
        assert isinstance(waypoints[0].longitude, float)
    
    def test_parse_route_single_waypoint(self, parser):
        """Test parsing a route with a single waypoint."""
        route_string = "KJFK"
        waypoints = parser.parse_route(route_string)
        
        assert len(waypoints) == 1
        assert waypoints[0].identifier == "KJFK"
    
    def test_parse_route_multiple_waypoints(self, parser):
        """Test parsing a route with multiple waypoints."""
        route_string = "KJFK KBOS CYYZ"
        waypoints = parser.parse_route(route_string)
        
        assert len(waypoints) == 3
        assert waypoints[0].identifier == "KJFK"
        assert waypoints[1].identifier == "KBOS"
        assert waypoints[2].identifier == "CYYZ"
    
    def test_parse_route_filters_route_keywords(self, parser):
        """Test that route keywords are filtered out."""
        route_string = "KJFK DCT KBOS DIRECT CYYZ"
        waypoints = parser.parse_route(route_string)
        
        # Should only have the three airports, not DCT or DIRECT
        assert len(waypoints) == 3
        identifiers = [w.identifier for w in waypoints]
        assert "DCT" not in identifiers
        assert "DIRECT" not in identifiers
    
    def test_parse_route_case_insensitive(self, parser):
        """Test that route parsing is case insensitive."""
        route_string = "kjfk dct cyyz"
        waypoints = parser.parse_route(route_string)
        
        assert len(waypoints) == 2
        assert waypoints[0].identifier == "KJFK"
        assert waypoints[1].identifier == "CYYZ"
    
    def test_parse_route_empty_string_raises_exception(self, parser):
        """Test that empty route string raises ParsingException."""
        with pytest.raises(ParsingException) as exc_info:
            parser.parse_route("")
        
        assert "cannot be empty" in str(exc_info.value).lower()
    
    def test_parse_route_whitespace_only_raises_exception(self, parser):
        """Test that whitespace-only route string raises ParsingException."""
        with pytest.raises(ParsingException) as exc_info:
            parser.parse_route("   ")
        
        assert "cannot be empty" in str(exc_info.value).lower()
    
    def test_parse_route_only_keywords_raises_exception(self, parser):
        """Test that route with only keywords raises ParsingException."""
        with pytest.raises(ParsingException) as exc_info:
            parser.parse_route("DCT DIRECT SID STAR")
        
        assert "no valid waypoints" in str(exc_info.value).lower()
    
    def test_parse_route_unknown_waypoints_filtered(self, parser):
        """Test that unknown waypoints are filtered out."""
        route_string = "KJFK UNKNOWN1 CYYZ"
        waypoints = parser.parse_route(route_string)
        
        # Should only have the two known airports
        assert len(waypoints) == 2
        assert waypoints[0].identifier == "KJFK"
        assert waypoints[1].identifier == "CYYZ"
    
    def test_parse_route_all_unknown_raises_exception(self, parser):
        """Test that route with all unknown waypoints raises ParsingException."""
        with pytest.raises(ParsingException) as exc_info:
            parser.parse_route("UNKNOWN1 UNKNOWN2 UNKNOWN3")
        
        assert "no valid waypoints" in str(exc_info.value).lower()
    
    # Test identify_fir_crossings() method
    
    def test_identify_fir_crossings_single_fir(self, parser, sample_firs):
        """Test identifying FIR crossing for a waypoint within one FIR."""
        # Create waypoint within KZNY FIR bounds
        waypoints = [Waypoint("TEST1", 40.5, -73.5)]
        
        crossed_firs = parser.identify_fir_crossings(waypoints, sample_firs)
        
        assert len(crossed_firs) == 1
        assert "KZNY" in crossed_firs
    
    def test_identify_fir_crossings_multiple_firs(self, parser, sample_firs):
        """Test identifying multiple FIR crossings."""
        # Create waypoints in different FIRs
        waypoints = [
            Waypoint("TEST1", 40.5, -73.5),  # In KZNY
            Waypoint("TEST2", 43.5, -79.5),  # In CZYZ
        ]
        
        crossed_firs = parser.identify_fir_crossings(waypoints, sample_firs)
        
        assert len(crossed_firs) == 2
        assert "KZNY" in crossed_firs
        assert "CZYZ" in crossed_firs
    
    def test_identify_fir_crossings_no_duplicates(self, parser, sample_firs):
        """Test that duplicate FIR crossings are not returned."""
        # Create multiple waypoints in the same FIR
        waypoints = [
            Waypoint("TEST1", 40.5, -73.5),  # In KZNY
            Waypoint("TEST2", 41.0, -73.0),  # Also in KZNY
        ]
        
        crossed_firs = parser.identify_fir_crossings(waypoints, sample_firs)
        
        # Should only return KZNY once
        assert len(crossed_firs) == 1
        assert crossed_firs[0] == "KZNY"
    
    def test_identify_fir_crossings_no_firs(self, parser):
        """Test identifying FIR crossings with no FIRs available."""
        waypoints = [Waypoint("TEST1", 40.5, -73.5)]
        
        crossed_firs = parser.identify_fir_crossings(waypoints, [])
        
        assert len(crossed_firs) == 0
    
    def test_identify_fir_crossings_empty_waypoints_raises_exception(self, parser, sample_firs):
        """Test that empty waypoints list raises ParsingException."""
        with pytest.raises(ParsingException) as exc_info:
            parser.identify_fir_crossings([], sample_firs)
        
        assert "without waypoints" in str(exc_info.value).lower()
    
    def test_identify_fir_crossings_waypoint_outside_all_firs(self, parser, sample_firs):
        """Test waypoint that doesn't fall within any FIR."""
        # Create waypoint outside all FIR bounds
        waypoints = [Waypoint("TEST1", 0.0, 0.0)]
        
        crossed_firs = parser.identify_fir_crossings(waypoints, sample_firs)
        
        assert len(crossed_firs) == 0
    
    def test_identify_fir_crossings_invalid_geometry_skipped(self, parser):
        """Test that FIRs with invalid geometry are skipped."""
        # Create FIR with invalid geometry
        fir_invalid = Mock(spec=IataFir)
        fir_invalid.icao_code = "INVALID"
        fir_invalid.geojson_geometry = {"type": "InvalidType"}
        
        waypoints = [Waypoint("TEST1", 40.5, -73.5)]
        
        # Should not raise exception, just skip invalid FIR
        crossed_firs = parser.identify_fir_crossings(waypoints, [fir_invalid])
        
        assert len(crossed_firs) == 0
    
    def test_identify_fir_crossings_preserves_order(self, parser, sample_firs):
        """Test that FIR crossings are returned in order of crossing."""
        waypoints = [
            Waypoint("TEST1", 40.5, -73.5),  # In KZNY (first)
            Waypoint("TEST2", 43.5, -79.5),  # In CZYZ (second)
        ]
        
        crossed_firs = parser.identify_fir_crossings(waypoints, sample_firs)
        
        # Order should match waypoint order
        assert crossed_firs[0] == "KZNY"
        assert crossed_firs[1] == "CZYZ"
    
    # Test Waypoint dataclass
    
    def test_waypoint_creation(self):
        """Test creating a Waypoint instance."""
        waypoint = Waypoint("KJFK", 40.6413, -73.7781)
        
        assert waypoint.identifier == "KJFK"
        assert waypoint.latitude == 40.6413
        assert waypoint.longitude == -73.7781
    
    def test_waypoint_repr(self):
        """Test Waypoint string representation."""
        waypoint = Waypoint("KJFK", 40.6413, -73.7781)
        repr_str = repr(waypoint)
        
        assert "KJFK" in repr_str
        assert "40.6413" in repr_str
        assert "-73.7781" in repr_str
    
    # Integration tests
    
    def test_parse_and_identify_integration(self, parser, sample_firs):
        """Test full workflow: parse route and identify FIR crossings."""
        route_string = "KJFK DCT CYYZ"
        
        # Parse route
        waypoints = parser.parse_route(route_string)
        assert len(waypoints) == 2
        
        # Identify FIR crossings
        # Note: With real coordinates, KJFK and CYYZ may not fall within our mock FIRs
        crossed_firs = parser.identify_fir_crossings(waypoints, sample_firs)
        
        # Just verify it doesn't raise an exception
        assert isinstance(crossed_firs, list)
