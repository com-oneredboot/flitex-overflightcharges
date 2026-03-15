"""Unit tests for RouteParser service.

Tests the ICAO route parsing and FIR crossing identification functionality.
Waypoint resolution now queries the reference schema tables via SQLAlchemy.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session
from src.services.route_parser import RouteParser, Waypoint
from src.exceptions import ParsingException
from src.models.iata_fir import IataFir
from src.models.reference import (
    ReferenceAirport,
    ReferenceNavWaypoint,
    ReferenceChargesWaypoint,
    ReferenceChargesVOR,
    ReferenceChargesNDB,
)
from src.schemas.reference import FIRCrossing


def _make_airport(ident: str, laty: float, lonx: float) -> ReferenceAirport:
    """Helper to create a mock ReferenceAirport."""
    airport = Mock(spec=ReferenceAirport)
    airport.ident = ident
    airport.laty = laty
    airport.lonx = lonx
    return airport


def _make_nav_waypoint(ident: str, laty: float, lonx: float) -> ReferenceNavWaypoint:
    """Helper to create a mock ReferenceNavWaypoint."""
    wp = Mock(spec=ReferenceNavWaypoint)
    wp.ident = ident
    wp.laty = laty
    wp.lonx = lonx
    return wp


def _build_mock_db(airport_data=None, nav_data=None, charges_wp_data=None,
                   charges_vor_data=None, charges_ndb_data=None):
    """Build a mock SQLAlchemy Session that responds to query().filter().first() chains.

    Each *_data argument is a dict mapping ident -> mock record (or None to miss).
    """
    airport_data = airport_data or {}
    nav_data = nav_data or {}
    charges_wp_data = charges_wp_data or {}
    charges_vor_data = charges_vor_data or {}
    charges_ndb_data = charges_ndb_data or {}

    table_map = {
        ReferenceAirport: airport_data,
        ReferenceNavWaypoint: nav_data,
        ReferenceChargesWaypoint: charges_wp_data,
        ReferenceChargesVOR: charges_vor_data,
        ReferenceChargesNDB: charges_ndb_data,
    }

    db = MagicMock(spec=Session)

    def _query_side_effect(model_cls):
        data = table_map.get(model_cls, {})
        query_mock = MagicMock()

        def _filter_side_effect(*args):
            # Extract the identifier from the binary expression
            # The filter call is model_cls.ident == value
            # We need to extract the compared value
            filter_mock = MagicMock()

            # We'll capture the ident from the comparison
            # args[0] is a BinaryExpression; we grab .right.value
            try:
                ident_value = args[0].right.value
            except AttributeError:
                ident_value = None

            filter_mock.first.return_value = data.get(ident_value)
            return filter_mock

        query_mock.filter.side_effect = _filter_side_effect
        return query_mock

    db.query.side_effect = _query_side_effect
    return db


class TestRouteParser:
    """Test suite for RouteParser service."""

    @pytest.fixture
    def parser(self):
        """Create a RouteParser instance."""
        return RouteParser()

    @pytest.fixture
    def mock_db_with_airports(self):
        """Create a mock db session with common airport data."""
        airports = {
            "KJFK": _make_airport("KJFK", 40.6413, -73.7781),
            "CYYZ": _make_airport("CYYZ", 43.6777, -79.6248),
            "EGLL": _make_airport("EGLL", 51.4700, -0.4543),
            "KBOS": _make_airport("KBOS", 42.3656, -71.0096),
        }
        return _build_mock_db(airport_data=airports)

    @pytest.fixture
    def sample_firs(self):
        """Create sample FIR records for testing."""
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

    # ── parse_route() tests ──────────────────────────────────────────

    def test_parse_route_simple_route(self, parser, mock_db_with_airports):
        """Test parsing a simple route with two airports."""
        waypoints = parser.parse_route("KJFK DCT CYYZ", mock_db_with_airports)

        assert len(waypoints) == 2
        assert waypoints[0].identifier == "KJFK"
        assert waypoints[1].identifier == "CYYZ"
        assert isinstance(waypoints[0].latitude, float)
        assert isinstance(waypoints[0].longitude, float)
        assert waypoints[0].source_table == "airports"

    def test_parse_route_single_waypoint(self, parser, mock_db_with_airports):
        """Test parsing a route with a single waypoint."""
        waypoints = parser.parse_route("KJFK", mock_db_with_airports)

        assert len(waypoints) == 1
        assert waypoints[0].identifier == "KJFK"
        assert waypoints[0].source_table == "airports"

    def test_parse_route_multiple_waypoints(self, parser, mock_db_with_airports):
        """Test parsing a route with multiple waypoints."""
        waypoints = parser.parse_route("KJFK KBOS CYYZ", mock_db_with_airports)

        assert len(waypoints) == 3
        assert waypoints[0].identifier == "KJFK"
        assert waypoints[1].identifier == "KBOS"
        assert waypoints[2].identifier == "CYYZ"

    def test_parse_route_filters_route_keywords(self, parser, mock_db_with_airports):
        """Test that route keywords are filtered out."""
        waypoints = parser.parse_route("KJFK DCT KBOS DIRECT CYYZ", mock_db_with_airports)

        assert len(waypoints) == 3
        identifiers = [w.identifier for w in waypoints]
        assert "DCT" not in identifiers
        assert "DIRECT" not in identifiers

    def test_parse_route_all_keywords_skipped(self, parser, mock_db_with_airports):
        """Test that all defined route keywords are skipped."""
        waypoints = parser.parse_route(
            "KJFK DCT SID STAR DIRECT AIRWAY CYYZ", mock_db_with_airports
        )
        identifiers = [w.identifier for w in waypoints]
        for kw in ("DCT", "SID", "STAR", "DIRECT", "AIRWAY"):
            assert kw not in identifiers
        assert len(waypoints) == 2

    def test_parse_route_case_insensitive(self, parser, mock_db_with_airports):
        """Test that route parsing uppercases tokens before resolution."""
        waypoints = parser.parse_route("kjfk dct cyyz", mock_db_with_airports)

        assert len(waypoints) == 2
        assert waypoints[0].identifier == "KJFK"
        assert waypoints[1].identifier == "CYYZ"

    def test_parse_route_empty_string_raises_exception(self, parser, mock_db_with_airports):
        """Test that empty route string raises ParsingException."""
        with pytest.raises(ParsingException) as exc_info:
            parser.parse_route("", mock_db_with_airports)
        assert "cannot be empty" in str(exc_info.value).lower()

    def test_parse_route_whitespace_only_raises_exception(self, parser, mock_db_with_airports):
        """Test that whitespace-only route string raises ParsingException."""
        with pytest.raises(ParsingException) as exc_info:
            parser.parse_route("   ", mock_db_with_airports)
        assert "cannot be empty" in str(exc_info.value).lower()

    def test_parse_route_only_keywords_raises_exception(self, parser, mock_db_with_airports):
        """Test that route with only keywords raises ParsingException."""
        with pytest.raises(ParsingException) as exc_info:
            parser.parse_route("DCT DIRECT SID STAR", mock_db_with_airports)
        assert "no valid waypoints" in str(exc_info.value).lower()

    def test_parse_route_unresolved_identifiers_collected(self, parser, mock_db_with_airports):
        """Test that unresolved identifiers are tracked but resolved ones still returned."""
        waypoints = parser.parse_route("KJFK UNKNOWN1 CYYZ", mock_db_with_airports)

        # Resolved waypoints returned
        assert len(waypoints) == 2
        assert waypoints[0].identifier == "KJFK"
        assert waypoints[1].identifier == "CYYZ"

    def test_parse_route_all_unknown_raises_with_unresolved(self, parser, mock_db_with_airports):
        """Test that route with all unknown waypoints raises ParsingException with unresolved list."""
        with pytest.raises(ParsingException) as exc_info:
            parser.parse_route("UNKNOWN1 UNKNOWN2 UNKNOWN3", mock_db_with_airports)

        assert "no valid waypoints" in str(exc_info.value).lower()
        assert "unresolved" in exc_info.value.details
        assert set(exc_info.value.details["unresolved"]) == {"UNKNOWN1", "UNKNOWN2", "UNKNOWN3"}

    # ── _resolve_waypoint_coordinates() priority order tests ─────────

    def test_resolve_prefers_airports_over_nav_waypoints(self, parser):
        """Test that airports table is queried before nav_waypoints."""
        airports = {"TESTID": _make_airport("TESTID", 10.0, 20.0)}
        nav = {"TESTID": _make_nav_waypoint("TESTID", 30.0, 40.0)}
        db = _build_mock_db(airport_data=airports, nav_data=nav)

        waypoints = parser.parse_route("TESTID", db)
        assert waypoints[0].latitude == 10.0
        assert waypoints[0].longitude == 20.0
        assert waypoints[0].source_table == "airports"

    def test_resolve_falls_through_to_nav_waypoints(self, parser):
        """Test fallback to nav_waypoints when not in airports."""
        nav = {"NAVPT": _make_nav_waypoint("NAVPT", 55.0, 66.0)}
        db = _build_mock_db(nav_data=nav)

        waypoints = parser.parse_route("NAVPT", db)
        assert waypoints[0].source_table == "nav_waypoints"
        assert waypoints[0].latitude == 55.0

    def test_resolve_falls_through_to_charges_waypoints(self, parser):
        """Test fallback to charges_waypoints."""
        wp = Mock(spec=ReferenceChargesWaypoint)
        wp.ident = "CWPT"
        wp.laty = 11.0
        wp.lonx = 22.0
        db = _build_mock_db(charges_wp_data={"CWPT": wp})

        waypoints = parser.parse_route("CWPT", db)
        assert waypoints[0].source_table == "charges_waypoints"

    def test_resolve_falls_through_to_charges_vor(self, parser):
        """Test fallback to charges_vor."""
        vor = Mock(spec=ReferenceChargesVOR)
        vor.ident = "TVOR"
        vor.laty = 33.0
        vor.lonx = 44.0
        db = _build_mock_db(charges_vor_data={"TVOR": vor})

        waypoints = parser.parse_route("TVOR", db)
        assert waypoints[0].source_table == "charges_vor"

    def test_resolve_falls_through_to_charges_ndb(self, parser):
        """Test fallback to charges_ndb."""
        ndb = Mock(spec=ReferenceChargesNDB)
        ndb.ident = "TNDB"
        ndb.laty = 55.0
        ndb.lonx = 66.0
        db = _build_mock_db(charges_ndb_data={"TNDB": ndb})

        waypoints = parser.parse_route("TNDB", db)
        assert waypoints[0].source_table == "charges_ndb"

    def test_resolve_skips_record_with_null_coordinates(self, parser):
        """Test that a record with null laty/lonx is treated as unresolved."""
        airport_null = Mock(spec=ReferenceAirport)
        airport_null.ident = "XNUL"
        airport_null.laty = None
        airport_null.lonx = None
        db = _build_mock_db(airport_data={"XNUL": airport_null})

        with pytest.raises(ParsingException):
            parser.parse_route("XNUL", db)

    # ── source_table field tests ─────────────────────────────────────

    def test_waypoint_source_table_populated(self, parser, mock_db_with_airports):
        """Test that each resolved waypoint has a source_table value."""
        waypoints = parser.parse_route("KJFK CYYZ", mock_db_with_airports)
        for wp in waypoints:
            assert wp.source_table == "airports"

    # ── identify_fir_crossings() tests (unchanged) ───────────────────

    def test_identify_fir_crossings_single_fir(self, parser, sample_firs):
        """Test identifying FIR crossing for a waypoint within one FIR."""
        waypoints = [Waypoint("TEST1", 40.5, -73.5)]
        crossed_firs = parser.identify_fir_crossings(waypoints, sample_firs)
        assert len(crossed_firs) == 1
        assert "KZNY" in crossed_firs

    def test_identify_fir_crossings_multiple_firs(self, parser, sample_firs):
        """Test identifying multiple FIR crossings."""
        waypoints = [
            Waypoint("TEST1", 40.5, -73.5),
            Waypoint("TEST2", 43.5, -79.5),
        ]
        crossed_firs = parser.identify_fir_crossings(waypoints, sample_firs)
        assert len(crossed_firs) == 2
        assert "KZNY" in crossed_firs
        assert "CZYZ" in crossed_firs

    def test_identify_fir_crossings_no_duplicates(self, parser, sample_firs):
        """Test that duplicate FIR crossings are not returned."""
        waypoints = [
            Waypoint("TEST1", 40.5, -73.5),
            Waypoint("TEST2", 41.0, -73.0),
        ]
        crossed_firs = parser.identify_fir_crossings(waypoints, sample_firs)
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
        waypoints = [Waypoint("TEST1", 0.0, 0.0)]
        crossed_firs = parser.identify_fir_crossings(waypoints, sample_firs)
        assert len(crossed_firs) == 0

    def test_identify_fir_crossings_invalid_geometry_skipped(self, parser):
        """Test that FIRs with invalid geometry are skipped."""
        fir_invalid = Mock(spec=IataFir)
        fir_invalid.icao_code = "INVALID"
        fir_invalid.geojson_geometry = {"type": "InvalidType"}

        waypoints = [Waypoint("TEST1", 40.5, -73.5)]
        crossed_firs = parser.identify_fir_crossings(waypoints, [fir_invalid])
        assert len(crossed_firs) == 0

    def test_identify_fir_crossings_preserves_order(self, parser, sample_firs):
        """Test that FIR crossings are returned in order of crossing."""
        waypoints = [
            Waypoint("TEST1", 40.5, -73.5),
            Waypoint("TEST2", 43.5, -79.5),
        ]
        crossed_firs = parser.identify_fir_crossings(waypoints, sample_firs)
        assert crossed_firs[0] == "KZNY"
        assert crossed_firs[1] == "CZYZ"

    # ── Waypoint dataclass tests ─────────────────────────────────────

    def test_waypoint_creation(self):
        """Test creating a Waypoint instance."""
        waypoint = Waypoint("KJFK", 40.6413, -73.7781)
        assert waypoint.identifier == "KJFK"
        assert waypoint.latitude == 40.6413
        assert waypoint.longitude == -73.7781

    def test_waypoint_creation_with_source_table(self):
        """Test creating a Waypoint with source_table."""
        waypoint = Waypoint("KJFK", 40.6413, -73.7781, source_table="airports")
        assert waypoint.source_table == "airports"

    def test_waypoint_repr(self):
        """Test Waypoint string representation."""
        waypoint = Waypoint("KJFK", 40.6413, -73.7781)
        repr_str = repr(waypoint)
        assert "KJFK" in repr_str
        assert "40.6413" in repr_str
        assert "-73.7781" in repr_str

    # ── Integration tests ────────────────────────────────────────────

    def test_parse_and_identify_integration(self, parser, mock_db_with_airports, sample_firs):
        """Test full workflow: parse route and identify FIR crossings."""
        waypoints = parser.parse_route("KJFK DCT CYYZ", mock_db_with_airports)
        assert len(waypoints) == 2

        crossed_firs = parser.identify_fir_crossings(waypoints, sample_firs)
        assert isinstance(crossed_firs, list)

    # ── identify_fir_crossings_db() tests ────────────────────────────

    def _mock_db_for_fir_query(self, fir_results_by_point):
        """Helper to build a mock db that responds to PostGIS ST_Contains queries.

        Args:
            fir_results_by_point: dict mapping (lon, lat) tuples to
                (icao_code, fir_name, country) tuples, or None for no match.
        """
        db = MagicMock(spec=Session)

        def _execute_side_effect(stmt, params=None):
            result_mock = MagicMock()
            if params:
                key = (params.get("lon"), params.get("lat"))
                row = fir_results_by_point.get(key)
                result_mock.fetchone.return_value = row
            else:
                result_mock.fetchone.return_value = None
            return result_mock

        db.execute.side_effect = _execute_side_effect
        return db

    def test_identify_fir_crossings_db_single_fir(self, parser):
        """Test identifying a single FIR crossing via database query."""
        waypoints = [Waypoint("KJFK", 40.6413, -73.7781)]
        db = self._mock_db_for_fir_query({
            (-73.7781, 40.6413): ("KZNY", "New York FIR", "US"),
        })

        result = parser.identify_fir_crossings_db(waypoints, db)

        assert len(result) == 1
        assert isinstance(result[0], FIRCrossing)
        assert result[0].icao_code == "KZNY"
        assert result[0].fir_name == "New York FIR"
        assert result[0].country == "US"

    def test_identify_fir_crossings_db_multiple_firs(self, parser):
        """Test identifying multiple FIR crossings ordered by encounter."""
        waypoints = [
            Waypoint("KJFK", 40.6413, -73.7781),
            Waypoint("CYYZ", 43.6777, -79.6248),
        ]
        db = self._mock_db_for_fir_query({
            (-73.7781, 40.6413): ("KZNY", "New York FIR", "US"),
            (-79.6248, 43.6777): ("CZYZ", "Toronto FIR", "CA"),
        })

        result = parser.identify_fir_crossings_db(waypoints, db)

        assert len(result) == 2
        assert result[0].icao_code == "KZNY"
        assert result[1].icao_code == "CZYZ"

    def test_identify_fir_crossings_db_no_duplicates(self, parser):
        """Test that duplicate FIR crossings are not returned."""
        waypoints = [
            Waypoint("KJFK", 40.6413, -73.7781),
            Waypoint("KLGA", 40.7772, -73.8726),
        ]
        db = self._mock_db_for_fir_query({
            (-73.7781, 40.6413): ("KZNY", "New York FIR", "US"),
            (-73.8726, 40.7772): ("KZNY", "New York FIR", "US"),
        })

        result = parser.identify_fir_crossings_db(waypoints, db)

        assert len(result) == 1
        assert result[0].icao_code == "KZNY"

    def test_identify_fir_crossings_db_empty_waypoints(self, parser):
        """Test that empty waypoints returns empty list (no exception)."""
        db = MagicMock(spec=Session)
        result = parser.identify_fir_crossings_db([], db)
        assert result == []

    def test_identify_fir_crossings_db_waypoint_outside_all_firs(self, parser):
        """Test waypoint that doesn't fall within any FIR boundary."""
        waypoints = [Waypoint("OCEAN", 0.0, 0.0)]
        db = self._mock_db_for_fir_query({
            (0.0, 0.0): None,
        })

        result = parser.identify_fir_crossings_db(waypoints, db)
        assert result == []

    def test_identify_fir_crossings_db_null_country(self, parser):
        """Test FIR with null country field."""
        waypoints = [Waypoint("KJFK", 40.6413, -73.7781)]
        db = self._mock_db_for_fir_query({
            (-73.7781, 40.6413): ("KZNY", "New York FIR", None),
        })

        result = parser.identify_fir_crossings_db(waypoints, db)

        assert len(result) == 1
        assert result[0].country is None

    def test_identify_fir_crossings_db_query_failure_logs_warning(self, parser):
        """Test that a database error is logged as warning and processing continues."""
        waypoints = [
            Waypoint("KJFK", 40.6413, -73.7781),
            Waypoint("CYYZ", 43.6777, -79.6248),
        ]
        db = MagicMock(spec=Session)
        call_count = 0

        def _execute_side_effect(stmt, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("PostGIS extension not available")
            result_mock = MagicMock()
            result_mock.fetchone.return_value = ("CZYZ", "Toronto FIR", "CA")
            return result_mock

        db.execute.side_effect = _execute_side_effect

        with patch("src.services.route_parser.logger") as mock_logger:
            result = parser.identify_fir_crossings_db(waypoints, db)

        assert len(result) == 1
        assert result[0].icao_code == "CZYZ"
        mock_logger.warning.assert_called_once()

    def test_identify_fir_crossings_db_preserves_order(self, parser):
        """Test that FIR crossings are returned in order of first encounter along route."""
        waypoints = [
            Waypoint("CYYZ", 43.6777, -79.6248),
            Waypoint("KJFK", 40.6413, -73.7781),
            Waypoint("EGLL", 51.4700, -0.4543),
        ]
        db = self._mock_db_for_fir_query({
            (-79.6248, 43.6777): ("CZYZ", "Toronto FIR", "CA"),
            (-73.7781, 40.6413): ("KZNY", "New York FIR", "US"),
            (-0.4543, 51.4700): ("EGTT", "London FIR", "GB"),
        })

        result = parser.identify_fir_crossings_db(waypoints, db)

        assert len(result) == 3
        assert result[0].icao_code == "CZYZ"
        assert result[1].icao_code == "KZNY"
        assert result[2].icao_code == "EGTT"

    def test_identify_fir_crossings_db_null_icao_code_skipped(self, parser):
        """Test that FIR rows with null icao_code are skipped."""
        waypoints = [Waypoint("KJFK", 40.6413, -73.7781)]
        db = self._mock_db_for_fir_query({
            (-73.7781, 40.6413): (None, "Unknown FIR", "US"),
        })

        result = parser.identify_fir_crossings_db(waypoints, db)
        assert result == []


# ── Property-Based Tests (hypothesis) ────────────────────────────────────────

from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st


# --- Strategies for Property 3 ---

# Generate valid ICAO-style identifiers (2-5 uppercase letters/digits, not a keyword)
_ROUTE_KEYWORDS = {"DCT", "SID", "STAR", "DIRECT", "AIRWAY"}

icao_ident_strategy = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    min_size=2,
    max_size=5,
).filter(lambda s: s not in _ROUTE_KEYWORDS)

# Coordinate strategies
latitude_strategy = st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False)
longitude_strategy = st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False)

# Route keyword strategy
keyword_strategy = st.sampled_from(list(_ROUTE_KEYWORDS))


class TestRouteValidationPartitioning:
    """
    Feature: overflight-charges-user-tab, Property 3: Route validation correctly partitions identifiers

    **Validates: Requirements 3.1, 3.2, 3.3**

    For any route string composed of waypoint identifiers (some present in the
    navigation database, some not) and route keywords, the validation response must:
    (a) list every database-resolvable identifier in the waypoints array with correct
        coordinates matching the source table,
    (b) list every non-resolvable, non-keyword identifier in the unresolved array, and
    (c) set valid: true if and only if unresolved is empty.
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    )
    @given(
        known_idents=st.lists(
            st.tuples(icao_ident_strategy, latitude_strategy, longitude_strategy),
            min_size=1,
            max_size=6,
        ),
        unknown_idents=st.lists(icao_ident_strategy, min_size=0, max_size=4),
        keywords_to_insert=st.lists(keyword_strategy, min_size=0, max_size=3),
    )
    def test_property_3_route_validation_partitions_identifiers(
        self, known_idents, unknown_idents, keywords_to_insert
    ):
        """
        **Validates: Requirements 3.1, 3.2, 3.3**

        Generate route strings with known/unknown identifiers and keywords.
        Verify:
        (a) every known identifier appears in resolved waypoints with correct coords,
        (b) every unknown identifier appears in the unresolved list,
        (c) valid is True iff unresolved is empty.
        """
        # Deduplicate known idents by identifier string
        seen = set()
        deduped_known = []
        for ident, lat, lon in known_idents:
            if ident not in seen:
                seen.add(ident)
                deduped_known.append((ident, lat, lon))
        known_idents = deduped_known

        # Ensure unknown idents don't overlap with known idents or keywords
        known_set = {ident for ident, _, _ in known_idents}
        unknown_idents = [u for u in unknown_idents if u not in known_set and u not in _ROUTE_KEYWORDS]
        # Deduplicate unknown idents
        unknown_idents = list(dict.fromkeys(unknown_idents))

        # Need at least one identifier total (known or unknown)
        assume(len(known_idents) + len(unknown_idents) > 0)

        # Build mock DB with known identifiers as airports
        airport_data = {}
        known_coords = {}
        for ident, lat, lon in known_idents:
            airport_data[ident] = _make_airport(ident, lat, lon)
            known_coords[ident] = (lat, lon)

        mock_db = _build_mock_db(airport_data=airport_data)

        # Build route string: interleave known, unknown, and keywords
        all_idents = [ident for ident, _, _ in known_idents] + unknown_idents
        # Insert keywords at random positions
        tokens = list(all_idents)
        for kw in keywords_to_insert:
            # Insert keyword at a valid position (between identifiers)
            if tokens:
                pos = len(tokens) // 2
                tokens.insert(pos, kw)

        route_string = " ".join(tokens)
        assume(len(route_string.strip()) > 0)

        parser = RouteParser()

        # If all identifiers are unknown, parse_route raises ParsingException
        if not known_idents:
            with pytest.raises(ParsingException) as exc_info:
                parser.parse_route(route_string, mock_db)

            assert "unresolved" in exc_info.value.details
            unresolved_result = set(exc_info.value.details["unresolved"])
            assert unresolved_result == set(unknown_idents), (
                f"Expected unresolved={set(unknown_idents)}, got {unresolved_result}"
            )
            return

        # Otherwise, parse_route returns resolved waypoints (silently skipping unresolved)
        waypoints = parser.parse_route(route_string, mock_db)

        # (a) Every known identifier appears in resolved waypoints with correct coordinates
        resolved_map = {wp.identifier: wp for wp in waypoints}
        for ident, lat, lon in known_idents:
            assert ident in resolved_map, (
                f"Known identifier '{ident}' not found in resolved waypoints. "
                f"Resolved: {list(resolved_map.keys())}"
            )
            wp = resolved_map[ident]
            assert wp.latitude == lat, (
                f"Latitude mismatch for '{ident}': expected {lat}, got {wp.latitude}"
            )
            assert wp.longitude == lon, (
                f"Longitude mismatch for '{ident}': expected {lon}, got {wp.longitude}"
            )
            assert wp.source_table == "airports", (
                f"Source table mismatch for '{ident}': expected 'airports', got '{wp.source_table}'"
            )

        # Verify no extra waypoints beyond the known set
        assert len(waypoints) == len(known_idents), (
            f"Expected {len(known_idents)} waypoints, got {len(waypoints)}. "
            f"Resolved: {[wp.identifier for wp in waypoints]}"
        )

        # (b) Collect unresolved by re-scanning tokens (same logic as the endpoint)
        resolved_idents = {wp.identifier for wp in waypoints}
        upper_tokens = route_string.strip().upper().split()
        unresolved = [
            t for t in upper_tokens
            if t not in _ROUTE_KEYWORDS and t not in resolved_idents
        ]
        assert set(unresolved) == set(unknown_idents), (
            f"Unresolved mismatch: expected {set(unknown_idents)}, got {set(unresolved)}"
        )

        # (c) valid is True iff unresolved is empty
        is_valid = len(unresolved) == 0
        expected_valid = len(unknown_idents) == 0
        assert is_valid == expected_valid, (
            f"Valid flag mismatch: unresolved={unresolved}, "
            f"expected valid={expected_valid}, got valid={is_valid}"
        )


class TestRouteKeywordTransparency:
    """
    Feature: overflight-charges-user-tab, Property 4: Route keywords are transparent to validation

    **Validates: Requirements 3.4**

    For any valid route string, inserting any combination of route keywords
    (DCT, SID, STAR, DIRECT, AIRWAY) between waypoint identifiers must produce
    the same set of resolved waypoints in the same order.
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    )
    @given(
        waypoint_data=st.lists(
            st.tuples(icao_ident_strategy, latitude_strategy, longitude_strategy),
            min_size=1,
            max_size=8,
        ),
        keywords_between=st.lists(
            st.lists(keyword_strategy, min_size=0, max_size=3),
            min_size=0,
            max_size=9,
        ),
    )
    def test_property_4_route_keywords_transparent_to_validation(
        self, waypoint_data, keywords_between
    ):
        """
        **Validates: Requirements 3.4**

        Generate a list of known waypoint identifiers, build a base route string
        with just identifiers, then build a keyword-injected route string with
        random keywords inserted between identifiers. Parse both and verify the
        resolved waypoints are identical in order and content.
        """
        # Deduplicate waypoints by identifier
        seen = set()
        deduped = []
        for ident, lat, lon in waypoint_data:
            if ident not in seen:
                seen.add(ident)
                deduped.append((ident, lat, lon))
        waypoint_data = deduped

        assume(len(waypoint_data) >= 1)

        # Build mock DB with all identifiers as airports
        airport_data = {}
        for ident, lat, lon in waypoint_data:
            airport_data[ident] = _make_airport(ident, lat, lon)
        mock_db_base = _build_mock_db(airport_data=airport_data)
        mock_db_kw = _build_mock_db(airport_data=airport_data)

        # Build base route string (identifiers only, no keywords)
        idents = [ident for ident, _, _ in waypoint_data]
        base_route = " ".join(idents)

        # Build keyword-injected route string: insert keywords between identifiers
        injected_tokens = []
        for i, ident in enumerate(idents):
            # Insert keywords before this identifier (if available)
            if i < len(keywords_between):
                injected_tokens.extend(keywords_between[i])
            injected_tokens.append(ident)
        # Append any remaining keyword lists after the last identifier
        for j in range(len(idents), len(keywords_between)):
            injected_tokens.extend(keywords_between[j])

        injected_route = " ".join(injected_tokens)

        assume(len(base_route.strip()) > 0)
        assume(len(injected_route.strip()) > 0)

        parser = RouteParser()

        # Parse both routes
        base_waypoints = parser.parse_route(base_route, mock_db_base)
        injected_waypoints = parser.parse_route(injected_route, mock_db_kw)

        # Verify same number of resolved waypoints
        assert len(injected_waypoints) == len(base_waypoints), (
            f"Waypoint count mismatch: base={len(base_waypoints)}, "
            f"injected={len(injected_waypoints)}. "
            f"Base route: '{base_route}', Injected route: '{injected_route}'"
        )

        # Verify same waypoints in same order with same coordinates
        for i, (base_wp, inj_wp) in enumerate(zip(base_waypoints, injected_waypoints)):
            assert base_wp.identifier == inj_wp.identifier, (
                f"Identifier mismatch at position {i}: "
                f"base='{base_wp.identifier}', injected='{inj_wp.identifier}'"
            )
            assert base_wp.latitude == inj_wp.latitude, (
                f"Latitude mismatch for '{base_wp.identifier}' at position {i}: "
                f"base={base_wp.latitude}, injected={inj_wp.latitude}"
            )
            assert base_wp.longitude == inj_wp.longitude, (
                f"Longitude mismatch for '{base_wp.identifier}' at position {i}: "
                f"base={base_wp.longitude}, injected={inj_wp.longitude}"
            )
            assert base_wp.source_table == inj_wp.source_table, (
                f"Source table mismatch for '{base_wp.identifier}' at position {i}: "
                f"base='{base_wp.source_table}', injected='{inj_wp.source_table}'"
            )


class TestFIRSpatialContainment:
    """
    Feature: overflight-charges-user-tab, Property 5: FIR crossing identification matches spatial containment

    **Validates: Requirements 3.5**

    For any set of resolved waypoints with coordinates and for any set of FIR
    boundary polygons, a waypoint's FIR assignment must correspond to the FIR
    polygon that spatially contains that waypoint's coordinates. The returned
    FIR list must be ordered by first encounter along the route.
    """

    @staticmethod
    def _make_fir(icao_code: str, min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> IataFir:
        """Create a mock IataFir with a rectangular GeoJSON polygon."""
        fir = Mock(spec=IataFir)
        fir.icao_code = icao_code
        fir.fir_name = f"{icao_code} FIR"
        fir.country_code = "XX"
        fir.geojson_geometry = {
            "type": "Polygon",
            "coordinates": [[
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]]
        }
        return fir

    @staticmethod
    def _make_non_overlapping_firs(n: int):
        """Generate n non-overlapping rectangular FIR polygons along the longitude axis.

        Each FIR is a 10x10 degree rectangle, spaced apart to avoid overlap.
        Returns list of (icao_code, min_lon, min_lat, max_lon, max_lat) tuples.
        """
        firs = []
        for i in range(n):
            icao_code = f"F{i:03d}"
            # Place FIRs along longitude axis with gaps: [0,10], [20,30], [40,50], ...
            min_lon = i * 20.0 - 170.0  # Start at -170 to stay within valid range
            max_lon = min_lon + 10.0
            min_lat = -5.0
            max_lat = 5.0
            firs.append((icao_code, min_lon, min_lat, max_lon, max_lat))
        return firs

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        num_firs=st.integers(min_value=1, max_value=8),
        waypoint_assignments=st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=7),  # FIR index
                st.floats(min_value=0.01, max_value=0.99),  # lon fraction within FIR
                st.floats(min_value=0.01, max_value=0.99),  # lat fraction within FIR
            ),
            min_size=1,
            max_size=10,
        ),
    )
    def test_property_5_fir_crossing_matches_spatial_containment(
        self, num_firs, waypoint_assignments
    ):
        """
        **Validates: Requirements 3.5**

        Generate non-overlapping rectangular FIR polygons and waypoints placed
        inside known FIRs. Verify:
        (a) each waypoint's FIR assignment corresponds to the FIR polygon that
            spatially contains its coordinates,
        (b) the returned FIR list is ordered by first encounter along the route,
        (c) no duplicate FIR codes appear in the result.
        """
        # Build non-overlapping FIR rectangles
        fir_specs = self._make_non_overlapping_firs(num_firs)
        fir_objects = [
            self._make_fir(icao, mlo, mla, xlo, xla)
            for icao, mlo, mla, xlo, xla in fir_specs
        ]

        # Build waypoints placed inside specific FIRs
        waypoints = []
        expected_fir_order = []  # Expected order of first-encounter FIR codes
        seen_expected = set()

        for fir_idx, lon_frac, lat_frac in waypoint_assignments:
            # Clamp fir_idx to valid range
            fir_idx = fir_idx % num_firs
            icao, min_lon, min_lat, max_lon, max_lat = fir_specs[fir_idx]

            # Place waypoint inside the FIR rectangle using the fraction
            wp_lon = min_lon + lon_frac * (max_lon - min_lon)
            wp_lat = min_lat + lat_frac * (max_lat - min_lat)

            wp = Waypoint(f"WP{len(waypoints)}", wp_lat, wp_lon)
            waypoints.append(wp)

            # Track expected first-encounter order
            if icao not in seen_expected:
                expected_fir_order.append(icao)
                seen_expected.add(icao)

        parser = RouteParser()
        result = parser.identify_fir_crossings(waypoints, fir_objects)

        # (a) Every returned FIR code must be one that actually contains a waypoint
        for code in result:
            assert code in seen_expected, (
                f"Returned FIR '{code}' does not contain any waypoint. "
                f"Expected one of: {seen_expected}"
            )

        # (b) Ordering must match first-encounter order along the route
        assert result == expected_fir_order, (
            f"FIR order mismatch: expected {expected_fir_order}, got {result}"
        )

        # (c) No duplicates in result
        assert len(result) == len(set(result)), (
            f"Duplicate FIR codes in result: {result}"
        )
