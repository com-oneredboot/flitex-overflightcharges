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


class TestAirwayDesignator:
    """Tests for _is_airway_designator method.

    Validates: Requirements 1.1
    """

    @pytest.fixture
    def parser(self):
        return RouteParser()

    @pytest.mark.parametrize("token", ["J174", "UL9", "N562A", "A1B", "UM860"])
    def test_recognises_valid_airway_designators(self, parser, token):
        assert parser._is_airway_designator(token) is True

    @pytest.mark.parametrize("token", ["NATW", "NATA", "NATZ"])
    def test_excludes_nat_track_codes(self, parser, token):
        assert parser._is_airway_designator(token) is False

    @pytest.mark.parametrize("token", ["AB", "A1"])
    def test_rejects_tokens_shorter_than_3_chars(self, parser, token):
        assert parser._is_airway_designator(token) is False

    @pytest.mark.parametrize("token", ["AB1234", "AIRWAY1"])
    def test_rejects_tokens_longer_than_5_chars(self, parser, token):
        assert parser._is_airway_designator(token) is False

    @pytest.mark.parametrize("token", ["DCT", "MERIT", "KJFK", "ABCDE"])
    def test_rejects_tokens_without_digits(self, parser, token):
        assert parser._is_airway_designator(token) is False


class TestClassifyToken:
    """Tests for _classify_token method.

    Validates: Requirements 1.1, 1.2, 1.3
    """

    @pytest.fixture
    def parser(self):
        return RouteParser()

    @pytest.mark.parametrize("token", ["DCT", "SID", "STAR", "DIRECT", "AIRWAY"])
    def test_classifies_keywords(self, parser, token):
        assert parser._classify_token(token) == "keyword"

    @pytest.mark.parametrize("token", ["J174", "UL9", "N562A", "UM860"])
    def test_classifies_airway_designators(self, parser, token):
        assert parser._classify_token(token) == "airway"

    @pytest.mark.parametrize("token", ["NATW", "NATA", "NATZ"])
    def test_classifies_nat_tracks(self, parser, token):
        assert parser._classify_token(token) == "nat_track"

    @pytest.mark.parametrize("token", ["5000N/04900W", "4530N/01200E"])
    def test_classifies_coordinates(self, parser, token):
        assert parser._classify_token(token) == "coordinate"

    @pytest.mark.parametrize("token", ["KJFK", "MERIT", "EGLL", "CYYZ"])
    def test_classifies_waypoints(self, parser, token):
        assert parser._classify_token(token) == "waypoint"

    def test_keyword_takes_priority_over_other_classifications(self, parser):
        """Keywords are checked first in the pipeline."""
        for kw in RouteParser.ROUTE_KEYWORDS:
            assert parser._classify_token(kw) == "keyword"

    def test_airway_takes_priority_over_nat_track(self, parser):
        """NAT codes are excluded from airway detection, so NAT[A-Z] → nat_track."""
        # NAT + letter is 4 chars but has no digit → not airway → nat_track
        assert parser._classify_token("NATW") == "nat_track"

    def test_pipeline_order_airway_before_waypoint(self, parser):
        """A token like UL9 should be airway, not waypoint."""
        assert parser._classify_token("UL9") == "airway"


class TestExpandNatTrack:
    """Tests for _expand_nat_track method.

    Validates: Requirements 2.1, 2.2, 2.3, 2.4
    """

    @pytest.fixture
    def parser(self):
        return RouteParser()

    def _mock_db_with_nat(self, route_str, valid_from="2026-02-17 00:00:00", valid_to="2026-02-17 23:59:59"):
        """Build a mock db that returns a NAT track row."""
        db = MagicMock(spec=Session)
        row = MagicMock()
        row.__getitem__ = lambda self, idx: route_str if idx == 0 else None
        db.execute.return_value.fetchone.return_value = row
        return db

    def _mock_db_no_nat(self):
        """Build a mock db that returns no NAT track."""
        db = MagicMock(spec=Session)
        db.execute.return_value.fetchone.return_value = None
        return db

    def test_expand_found_track_returns_waypoints(self, parser):
        """When a NAT track is found, returns ordered waypoint list."""
        db = self._mock_db_with_nat("JOOPY 49/50 50/40 52/30 53/20 MALOT GISTI")
        from datetime import date
        result = parser._expand_nat_track("NATA", date(2026, 2, 17), db)

        assert result is not None
        assert len(result) == 7
        # First waypoint is a named waypoint
        assert result[0] == {"ident": "JOOPY", "lat": None, "lon": None}
        # Second is a coordinate: 49N 50W
        assert result[1] == {"ident": "49/50", "lat": 49.0, "lon": -50.0}
        # Third coordinate
        assert result[2] == {"ident": "50/40", "lat": 50.0, "lon": -40.0}
        # Last named waypoint
        assert result[6] == {"ident": "GISTI", "lat": None, "lon": None}

    def test_expand_not_found_returns_none(self, parser):
        """When NAT track is not found for the date, returns None."""
        db = self._mock_db_no_nat()
        from datetime import date
        result = parser._expand_nat_track("NATZ", date(2026, 2, 17), db)

        assert result is None

    def test_expand_queries_with_correct_params(self, parser):
        """Verifies the SQL query uses the correct track_id and flight date."""
        db = self._mock_db_no_nat()
        from datetime import date, datetime
        flight_date = date(2026, 3, 15)
        parser._expand_nat_track("NATB", flight_date, db)

        db.execute.assert_called_once()
        call_args = db.execute.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", call_args[0][1])
        assert params["track_id"] == "NATB"
        assert params["flight_dt"] == datetime.combine(flight_date, datetime.min.time())

    def test_expand_empty_route_returns_none(self, parser):
        """When the NAT track has an empty route string, returns None."""
        db = self._mock_db_with_nat("")
        from datetime import date
        result = parser._expand_nat_track("NATA", date(2026, 2, 17), db)

        assert result is None

    def test_expand_db_error_returns_none(self, parser):
        """When the database query fails, returns None gracefully."""
        db = MagicMock(spec=Session)
        db.execute.side_effect = Exception("Connection refused")
        from datetime import date
        result = parser._expand_nat_track("NATA", date(2026, 2, 17), db)

        assert result is None

    def test_coordinate_parsing_two_digit_lon(self, parser):
        """Coordinate 49/50 parses to lat=49.0, lon=-50.0."""
        wp = parser._parse_nat_route_waypoint("49/50")
        assert wp == {"ident": "49/50", "lat": 49.0, "lon": -50.0}

    def test_coordinate_parsing_three_digit_lon(self, parser):
        """Coordinate 52/120 parses to lat=52.0, lon=-120.0."""
        wp = parser._parse_nat_route_waypoint("52/120")
        assert wp == {"ident": "52/120", "lat": 52.0, "lon": -120.0}

    def test_named_waypoint_returns_null_coords(self, parser):
        """Named waypoints have None lat/lon — need separate resolution."""
        wp = parser._parse_nat_route_waypoint("MALOT")
        assert wp == {"ident": "MALOT", "lat": None, "lon": None}


class TestParseLatLon:
    """Tests for _parse_lat_lon ICAO coordinate parsing.

    Validates: Requirements 4.1, 4.2, 4.3
    """

    @pytest.fixture
    def parser(self):
        return RouteParser()

    # --- Valid coordinate parsing ---

    def test_basic_north_west(self, parser):
        """5000N/04900W → lat=50.0, lon=-49.0"""
        result = parser._parse_lat_lon("5000N/04900W")
        assert result == (50.0, -49.0)

    def test_basic_north_east(self, parser):
        """4530N/01200E → lat=45.5, lon=12.0"""
        result = parser._parse_lat_lon("4530N/01200E")
        assert result == (45.5, 12.0)

    def test_zero_coordinates(self, parser):
        """0000N/00000E → lat=0.0, lon=0.0"""
        result = parser._parse_lat_lon("0000N/00000E")
        assert result == (0.0, 0.0)

    def test_south_east(self, parser):
        """3345S/15130E → lat=-33.75, lon=151.5"""
        result = parser._parse_lat_lon("3345S/15130E")
        assert result == (-33.75, 151.5)

    def test_south_west(self, parser):
        """2300S/04300W → lat=-23.0, lon=-43.0"""
        result = parser._parse_lat_lon("2300S/04300W")
        assert result == (-23.0, -43.0)

    def test_max_latitude_north(self, parser):
        """9000N/00000E → lat=90.0, lon=0.0"""
        result = parser._parse_lat_lon("9000N/00000E")
        assert result == (90.0, 0.0)

    def test_max_latitude_south(self, parser):
        """9000S/00000E → lat=-90.0, lon=0.0"""
        result = parser._parse_lat_lon("9000S/00000E")
        assert result == (-90.0, 0.0)

    def test_max_longitude_east(self, parser):
        """0000N/18000E → lat=0.0, lon=180.0"""
        result = parser._parse_lat_lon("0000N/18000E")
        assert result == (0.0, 180.0)

    def test_max_longitude_west(self, parser):
        """0000N/18000W → lat=0.0, lon=-180.0"""
        result = parser._parse_lat_lon("0000N/18000W")
        assert result == (0.0, -180.0)

    def test_minutes_conversion(self, parser):
        """5130N/00045W → lat=51.5, lon=-0.75"""
        result = parser._parse_lat_lon("5130N/00045W")
        assert result == (51.5, -0.75)

    # --- Invalid coordinates ---

    def test_latitude_exceeds_90(self, parser):
        """9100N/00000E → None (latitude > 90)"""
        result = parser._parse_lat_lon("9100N/00000E")
        assert result is None

    def test_longitude_exceeds_180(self, parser):
        """0000N/18100E → None (longitude > 180)"""
        result = parser._parse_lat_lon("0000N/18100E")
        assert result is None

    def test_invalid_lat_minutes(self, parser):
        """5060N/01200E → None (minutes=60 is invalid)"""
        result = parser._parse_lat_lon("5060N/01200E")
        assert result is None

    def test_invalid_lon_minutes(self, parser):
        """5000N/01260E → None (minutes=60 is invalid)"""
        result = parser._parse_lat_lon("5000N/01260E")
        assert result is None

    # --- Non-matching tokens ---

    def test_non_coordinate_token(self, parser):
        """Regular waypoint identifier returns None."""
        assert parser._parse_lat_lon("MERIT") is None

    def test_nat_coordinate_format(self, parser):
        """NAT DD/DDD format does not match ICAO lat/lon pattern."""
        assert parser._parse_lat_lon("49/50") is None

    def test_missing_hemisphere(self, parser):
        """Missing hemisphere letter returns None."""
        assert parser._parse_lat_lon("5000/04900") is None

    def test_empty_string(self, parser):
        """Empty string returns None."""
        assert parser._parse_lat_lon("") is None

    def test_partial_format(self, parser):
        """Incomplete format returns None."""
        assert parser._parse_lat_lon("50N/049W") is None

    def test_lowercase_rejected(self, parser):
        """Lowercase hemisphere letters don't match."""
        assert parser._parse_lat_lon("5000n/04900w") is None


class TestTrySidStarStrip:
    """Tests for _try_sid_star_strip method.

    SID/STAR suffix stripping resolves tokens that failed standard resolution
    by trimming procedure suffixes: 6-char tokens trim last 1, 7-char tokens
    trim last 2, then retry resolution with the trimmed identifier.

    Validates: Requirements 3.1, 3.2, 3.3, 3.4
    """

    @pytest.fixture
    def parser(self):
        return RouteParser()

    @pytest.fixture
    def reference_point(self):
        """KJFK coordinates as a reference point."""
        return (40.6413, -73.7781)

    def test_6char_token_trims_last_1(self, parser, reference_point):
        """A 6-character token like MERIT1 should trim to MERIT (5 chars)."""
        db = _build_mock_db(
            nav_data={"MERIT": _make_nav_waypoint("MERIT", 40.0, -74.0)}
        )
        result = parser._try_sid_star_strip("MERIT1", reference_point, db)

        assert result is not None
        assert result["latitude"] == 40.0
        assert result["longitude"] == -74.0
        assert result["source_table"] == "nav_waypoints"
        assert result["original_token"] == "MERIT1"
        assert result["trimmed_to"] == "MERIT"

    def test_7char_token_trims_last_2(self, parser, reference_point):
        """A 7-character token like MERIT1A should trim to MERIT (5 chars)."""
        db = _build_mock_db(
            nav_data={"MERIT": _make_nav_waypoint("MERIT", 40.0, -74.0)}
        )
        result = parser._try_sid_star_strip("MERIT1A", reference_point, db)

        assert result is not None
        assert result["latitude"] == 40.0
        assert result["longitude"] == -74.0
        assert result["source_table"] == "nav_waypoints"
        assert result["original_token"] == "MERIT1A"
        assert result["trimmed_to"] == "MERIT"

    def test_5char_token_returns_none(self, parser, reference_point):
        """A 5-character token should not be stripped (not a SID/STAR suffix)."""
        db = _build_mock_db(
            nav_data={"MERI": _make_nav_waypoint("MERI", 40.0, -74.0)}
        )
        result = parser._try_sid_star_strip("MERIT", reference_point, db)
        assert result is None

    def test_8char_token_returns_none(self, parser, reference_point):
        """An 8-character token should not be stripped."""
        db = _build_mock_db(
            nav_data={"MERIT": _make_nav_waypoint("MERIT", 40.0, -74.0)}
        )
        result = parser._try_sid_star_strip("MERIT1AB", reference_point, db)
        assert result is None

    def test_4char_token_returns_none(self, parser, reference_point):
        """A 4-character token should not be stripped."""
        db = _build_mock_db()
        result = parser._try_sid_star_strip("ABCD", reference_point, db)
        assert result is None

    def test_trimmed_identifier_not_found_returns_none(self, parser, reference_point):
        """When the trimmed identifier doesn't resolve, return None."""
        db = _build_mock_db()  # No data in any table
        result = parser._try_sid_star_strip("ZZZZZ1", reference_point, db)
        assert result is None

    def test_resolves_from_airports_table(self, parser, reference_point):
        """Trimmed identifier should resolve from airports (highest priority)."""
        db = _build_mock_db(
            airport_data={"KLGAB": _make_airport("KLGAB", 35.0, -106.0)}
        )
        result = parser._try_sid_star_strip("KLGAB1", reference_point, db)

        assert result is not None
        assert result["source_table"] == "airports"
        assert result["original_token"] == "KLGAB1"
        assert result["trimmed_to"] == "KLGAB"

    def test_empty_token_returns_none(self, parser, reference_point):
        """An empty token should not be stripped."""
        db = _build_mock_db()
        result = parser._try_sid_star_strip("", reference_point, db)
        assert result is None

    def test_preserves_original_token_and_trimmed_identifier(self, parser, reference_point):
        """Result must contain both original_token and trimmed_to for audit trail."""
        db = _build_mock_db(
            nav_data={"BETTE": _make_nav_waypoint("BETTE", 51.0, -1.0)}
        )
        result = parser._try_sid_star_strip("BETTE2", reference_point, db)

        assert result is not None
        assert result["original_token"] == "BETTE2"
        assert result["trimmed_to"] == "BETTE"

    def test_7char_trims_to_5_not_6(self, parser, reference_point):
        """A 7-char token should trim 2 chars (to 5), not 1 char (to 6)."""
        # Only the 5-char identifier exists, not the 6-char one
        db = _build_mock_db(
            nav_data={"BETTE": _make_nav_waypoint("BETTE", 51.0, -1.0)}
        )
        result = parser._try_sid_star_strip("BETTE2A", reference_point, db)

        assert result is not None
        assert result["trimmed_to"] == "BETTE"


def _build_mock_db_multi(airport_data=None, nav_data=None, charges_wp_data=None,
                         charges_vor_data=None, charges_ndb_data=None):
    """Build a mock SQLAlchemy Session that supports both .first() and .all().

    Each *_data argument is a dict mapping ident -> list of mock records.
    This supports _resolve_with_proximity which calls .all() to get multiple
    candidates for the same identifier.
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
            filter_mock = MagicMock()
            try:
                ident_value = args[0].right.value
            except AttributeError:
                ident_value = None

            records = data.get(ident_value, [])
            # Support both list and single-record values for backwards compat
            if not isinstance(records, list):
                records = [records]
            filter_mock.all.return_value = records
            filter_mock.first.return_value = records[0] if records else None
            return filter_mock

        query_mock.filter.side_effect = _filter_side_effect
        return query_mock

    db.query.side_effect = _query_side_effect
    return db


class TestHaversineNm:
    """Tests for the _haversine_nm static method."""

    @pytest.fixture
    def parser(self):
        return RouteParser()

    def test_same_point_returns_zero(self, parser):
        """Distance from a point to itself is zero."""
        assert parser._haversine_nm(40.0, -74.0, 40.0, -74.0) == 0.0

    def test_known_distance_jfk_to_heathrow(self, parser):
        """KJFK (40.6413, -73.7781) to EGLL (51.4700, -0.4543) ≈ 2999 nm."""
        dist = parser._haversine_nm(40.6413, -73.7781, 51.4700, -0.4543)
        # Known great-circle distance is approximately 2999 nm
        assert 2950 < dist < 3050

    def test_short_distance(self, parser):
        """KJFK to KLGA (nearby airports) should be < 10 nm."""
        dist = parser._haversine_nm(40.6413, -73.7781, 40.7772, -73.8726)
        assert dist < 10.0

    def test_antipodal_points(self, parser):
        """Distance between antipodal points ≈ 10800 nm (half circumference)."""
        dist = parser._haversine_nm(0.0, 0.0, 0.0, 180.0)
        assert 10790 < dist < 10810

    def test_symmetry(self, parser):
        """Distance A→B equals distance B→A."""
        d1 = parser._haversine_nm(40.0, -74.0, 51.0, -0.5)
        d2 = parser._haversine_nm(51.0, -0.5, 40.0, -74.0)
        assert abs(d1 - d2) < 0.001


class TestResolveWithProximity:
    """Tests for _resolve_with_proximity method.

    Validates: Requirements 5.1, 5.2, 5.3
    """

    @pytest.fixture
    def parser(self):
        return RouteParser()

    @pytest.fixture
    def kjfk_ref(self):
        """KJFK coordinates as reference point (lat, lon)."""
        return (40.6413, -73.7781)

    def test_single_candidate_returned(self, parser, kjfk_ref):
        """When one candidate exists, it is returned with distance."""
        db = _build_mock_db_multi(
            airport_data={"CYYZ": [_make_airport("CYYZ", 43.6777, -79.6248)]}
        )
        result = parser._resolve_with_proximity("CYYZ", kjfk_ref, db)

        assert len(result) == 1
        assert result[0]["identifier"] == "CYYZ"
        assert result[0]["latitude"] == 43.6777
        assert result[0]["longitude"] == -79.6248
        assert result[0]["source_table"] == "airports"
        assert result[0]["distance_nm"] > 0

    def test_multiple_candidates_sorted_by_distance(self, parser, kjfk_ref):
        """When multiple candidates exist, they are sorted closest first."""
        # Two nav_waypoints with same ident but different locations
        near = _make_nav_waypoint("TESTP", 41.0, -74.0)   # Near KJFK
        far = _make_nav_waypoint("TESTP", 10.0, 20.0)     # Far from KJFK
        db = _build_mock_db_multi(
            nav_data={"TESTP": [near, far]}
        )
        result = parser._resolve_with_proximity("TESTP", kjfk_ref, db)

        assert len(result) == 2
        assert result[0]["distance_nm"] < result[1]["distance_nm"]
        assert result[0]["latitude"] == 41.0  # Near one is first

    def test_candidates_from_multiple_tables(self, parser, kjfk_ref):
        """Candidates from different reference tables are all returned."""
        airport = _make_airport("MULTI", 42.0, -75.0)
        nav_wp = _make_nav_waypoint("MULTI", 50.0, 0.0)
        db = _build_mock_db_multi(
            airport_data={"MULTI": [airport]},
            nav_data={"MULTI": [nav_wp]},
        )
        result = parser._resolve_with_proximity("MULTI", kjfk_ref, db)

        assert len(result) == 2
        source_tables = {c["source_table"] for c in result}
        assert "airports" in source_tables
        assert "nav_waypoints" in source_tables

    def test_no_candidates_returns_empty(self, parser, kjfk_ref):
        """When no candidates exist, returns empty list."""
        db = _build_mock_db_multi()
        result = parser._resolve_with_proximity("ZZZZZ", kjfk_ref, db)
        assert result == []

    def test_null_coordinates_skipped(self, parser, kjfk_ref):
        """Records with null laty/lonx are excluded from candidates."""
        null_record = Mock(spec=ReferenceAirport)
        null_record.ident = "XNUL"
        null_record.laty = None
        null_record.lonx = None
        db = _build_mock_db_multi(airport_data={"XNUL": [null_record]})

        result = parser._resolve_with_proximity("XNUL", kjfk_ref, db)
        assert result == []

    def test_origin_airport_as_reference_for_first_waypoint(self, parser):
        """Using origin airport coords as reference selects the closest candidate.

        Validates: Requirement 5.3
        """
        # Origin is in Europe (EGLL)
        egll_ref = (51.4700, -0.4543)
        # Two candidates: one in Europe, one in North America
        europe_wp = _make_nav_waypoint("AMBI", 50.0, 2.0)
        america_wp = _make_nav_waypoint("AMBI", 35.0, -80.0)
        db = _build_mock_db_multi(
            nav_data={"AMBI": [europe_wp, america_wp]}
        )
        result = parser._resolve_with_proximity("AMBI", egll_ref, db)

        assert len(result) == 2
        # European candidate should be first (closest to EGLL)
        assert result[0]["latitude"] == 50.0
        assert result[0]["longitude"] == 2.0

    def test_distance_nm_is_positive(self, parser, kjfk_ref):
        """All returned distances are non-negative."""
        db = _build_mock_db_multi(
            airport_data={"CYYZ": [_make_airport("CYYZ", 43.6777, -79.6248)]}
        )
        result = parser._resolve_with_proximity("CYYZ", kjfk_ref, db)
        for candidate in result:
            assert candidate["distance_nm"] >= 0


class TestApplyJumpDetection:
    """Tests for _apply_jump_detection method.

    Validates: Requirements 6.1, 6.2, 6.3, 6.4
    """

    @pytest.fixture
    def parser(self):
        return RouteParser()

    @pytest.fixture
    def kjfk_ref(self):
        """KJFK coordinates as reference point (lat, lon)."""
        return (40.6413, -73.7781)

    def test_close_candidate_selected(self, parser, kjfk_ref):
        """A candidate within 2500nm is selected."""
        candidates = [{
            "identifier": "CYYZ",
            "latitude": 43.6777,
            "longitude": -79.6248,
            "source_table": "airports",
            "distance_nm": 300.0,
        }]
        selected, discarded = parser._apply_jump_detection(candidates, kjfk_ref)

        assert selected is not None
        assert selected["identifier"] == "CYYZ"
        assert len(discarded) == 0

    def test_far_candidate_discarded(self, parser, kjfk_ref):
        """A candidate beyond 2500nm is discarded."""
        candidates = [{
            "identifier": "RJTT",
            "latitude": 35.5533,
            "longitude": 139.7811,
            "source_table": "airports",
            "distance_nm": 5900.0,
        }]
        selected, discarded = parser._apply_jump_detection(candidates, kjfk_ref)

        assert selected is None
        assert len(discarded) == 1
        assert discarded[0]["identifier"] == "RJTT"

    def test_mixed_candidates_selects_closest_within_threshold(self, parser, kjfk_ref):
        """With mixed candidates, selects closest within threshold, discards far ones."""
        candidates = [
            {
                "identifier": "NEAR",
                "latitude": 42.0,
                "longitude": -75.0,
                "source_table": "nav_waypoints",
                "distance_nm": 100.0,
            },
            {
                "identifier": "FAR",
                "latitude": -33.0,
                "longitude": 151.0,
                "source_table": "nav_waypoints",
                "distance_nm": 8600.0,
            },
        ]
        selected, discarded = parser._apply_jump_detection(candidates, kjfk_ref)

        assert selected is not None
        assert selected["identifier"] == "NEAR"
        assert len(discarded) == 1
        assert discarded[0]["identifier"] == "FAR"

    def test_all_candidates_exceed_threshold(self, parser, kjfk_ref):
        """When all candidates exceed 2500nm, selected is None.

        Validates: Requirement 6.2 — ALL_CANDIDATES_EXCEED_MAX_JUMP
        """
        candidates = [
            {
                "identifier": "FAR1",
                "latitude": -33.0,
                "longitude": 151.0,
                "source_table": "airports",
                "distance_nm": 8600.0,
            },
            {
                "identifier": "FAR2",
                "latitude": 35.0,
                "longitude": 139.0,
                "source_table": "airports",
                "distance_nm": 5900.0,
            },
        ]
        selected, discarded = parser._apply_jump_detection(candidates, kjfk_ref)

        assert selected is None
        assert len(discarded) == 2

    def test_empty_candidates_returns_none(self, parser, kjfk_ref):
        """Empty candidate list returns None selected and empty discarded."""
        selected, discarded = parser._apply_jump_detection([], kjfk_ref)
        assert selected is None
        assert discarded == []

    def test_exactly_at_threshold_is_not_discarded(self, parser, kjfk_ref):
        """A candidate at exactly 2500nm should NOT be discarded."""
        candidates = [{
            "identifier": "EDGE",
            "latitude": 50.0,
            "longitude": 0.0,
            "source_table": "airports",
            "distance_nm": 2500.0,
        }]
        selected, discarded = parser._apply_jump_detection(candidates, kjfk_ref)

        assert selected is not None
        assert selected["identifier"] == "EDGE"
        assert len(discarded) == 0

    def test_just_over_threshold_is_discarded(self, parser, kjfk_ref):
        """A candidate at 2500.01nm should be discarded."""
        candidates = [{
            "identifier": "OVER",
            "latitude": 50.0,
            "longitude": 0.0,
            "source_table": "airports",
            "distance_nm": 2500.01,
        }]
        selected, discarded = parser._apply_jump_detection(candidates, kjfk_ref)

        assert selected is None
        assert len(discarded) == 1

    def test_recalculates_distance_when_missing(self, parser):
        """When distance_nm is not in candidate dict, it is calculated."""
        ref = (0.0, 0.0)
        candidates = [{
            "identifier": "NEAR",
            "latitude": 1.0,
            "longitude": 1.0,
            "source_table": "airports",
            # No distance_nm key
        }]
        selected, discarded = parser._apply_jump_detection(candidates, ref)

        assert selected is not None
        assert "distance_nm" in selected
        assert selected["distance_nm"] > 0

    def test_max_jump_constant_is_2500(self, parser):
        """Verify the MAX_WAYPOINT_JUMP_NM constant is 2500."""
        assert parser.MAX_WAYPOINT_JUMP_NM == 2500
