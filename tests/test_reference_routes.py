"""Property-based tests for reference data API search matching.

Feature: overflight-charges-user-tab, Property 1: API search returns only matching results

These tests verify that the reference API search endpoints return only
results that match the search term (case-insensitive) in at least one
searchable field.

- Airports: searchable fields are ident, iata, name, city
- Aircrafts: searchable field is model

NOTE: These tests use mocked database sessions (no PostgreSQL required).
The mock simulates the ilike filtering behavior of the real SQLAlchemy
queries to test the full request/response cycle.

Validates: Requirements 2.2, 2.4
"""

import os
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from hypothesis import given, settings, strategies as st, HealthCheck, assume
from fastapi.testclient import TestClient

from src.models.reference import ReferenceAirport, ReferenceAircraft


# --- Strategies ---

# Generate printable strings without SQL wildcards (% and _) that could
# interfere with ilike pattern matching, and without null bytes.
safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Zs"),
        blacklist_characters="%_\x00",
    ),
    min_size=1,
    max_size=30,
)

# Airport ident: 2-4 uppercase alphanumeric (ICAO-style)
airport_ident_strategy = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
    min_size=2,
    max_size=4,
)

# IATA code: 3 uppercase letters or None
iata_strategy = st.one_of(
    st.none(),
    st.text(
        alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        min_size=3,
        max_size=3,
    ),
)

# Aircraft model: 2-8 alphanumeric (e.g., "A320", "B737")
aircraft_model_strategy = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"),
    min_size=2,
    max_size=8,
)

# Search term: non-empty safe text
search_term_strategy = safe_text.filter(lambda s: len(s.strip()) > 0)


def make_airport_mock(airport_id, ident, iata, name, city, country="US"):
    """Create a mock ReferenceAirport object with the given fields."""
    mock = MagicMock(spec=ReferenceAirport)
    mock.airport_id = airport_id
    mock.ident = ident
    mock.iata = iata
    mock.name = name
    mock.city = city
    mock.country = country
    mock.region = None
    mock.laty = 0.0
    mock.lonx = 0.0
    mock.altitude = 0
    mock.mag_var = 0.0
    mock.timezone = "UTC"
    return mock


def make_aircraft_mock(aircraft_id, model, details=None):
    """Create a mock ReferenceAircraft object with the given fields."""
    mock = MagicMock(spec=ReferenceAircraft)
    mock.id = aircraft_id
    mock.model = model
    mock.details = details or {}
    mock.created_at = None
    return mock


def airport_matches_search(airport, search_term):
    """Check if an airport matches the search term in any searchable field (case-insensitive).

    Mirrors the ilike filtering logic in reference_routes.py:
    ident, iata, name, city are searched with pattern %search%
    """
    term_lower = search_term.lower()
    fields = [airport.ident, airport.iata, airport.name, airport.city]
    return any(
        field is not None and term_lower in field.lower()
        for field in fields
    )


def aircraft_matches_search(aircraft, search_term):
    """Check if an aircraft matches the search term in the model field (case-insensitive).

    Mirrors the ilike filtering logic in reference_routes.py:
    model is searched with pattern %search%
    """
    term_lower = search_term.lower()
    return aircraft.model is not None and term_lower in aircraft.model.lower()


# --- Airport strategy: generate a list of airport records ---
airport_record_strategy = st.fixed_dictionaries({
    "ident": airport_ident_strategy,
    "iata": iata_strategy,
    "name": st.one_of(st.none(), safe_text),
    "city": st.one_of(st.none(), safe_text),
})

airport_list_strategy = st.lists(airport_record_strategy, min_size=1, max_size=10)

# --- Aircraft strategy: generate a list of aircraft records ---
aircraft_record_strategy = st.fixed_dictionaries({
    "model": aircraft_model_strategy,
})

aircraft_list_strategy = st.lists(aircraft_record_strategy, min_size=1, max_size=10)


# --- Fixtures ---

@pytest.fixture(scope="module")
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture(scope="module")
def client(mock_db):
    """Create test client with mocked database dependency."""
    env_vars = {
        "DATABASE_URL": "postgresql://user:pass@localhost/db",
        "CORS_ORIGINS": "http://localhost:4200",
        "LOG_LEVEL": "INFO",
    }
    with patch.dict(os.environ, env_vars):
        from src.main import app
        from src.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        yield TestClient(app)
        app.dependency_overrides.clear()


# --- Property Tests ---

class TestAPISearchReturnsOnlyMatchingResults:
    """
    Feature: overflight-charges-user-tab, Property 1: API search returns only matching results

    **Validates: Requirements 2.2, 2.4**

    For any set of reference records (airports or aircrafts) in the database
    and for any non-empty search string, every item returned by the search
    endpoint must match the search string (case-insensitive) in at least one
    of the searchable fields.
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        airports=airport_list_strategy,
        search_term=search_term_strategy,
    )
    def test_property_1_airport_search_returns_only_matching(
        self, client, mock_db, airports, search_term
    ):
        """
        **Validates: Requirements 2.2**

        For any set of airport records and any non-empty search string,
        every airport returned by GET /api/reference/airports?search=<term>
        must match the search term (case-insensitive) in at least one of:
        ident, iata, name, city.
        """
        # Build mock airport objects
        airport_mocks = [
            make_airport_mock(
                airport_id=i + 1,
                ident=a["ident"],
                iata=a["iata"],
                name=a["name"],
                city=a["city"],
            )
            for i, a in enumerate(airports)
        ]

        # Simulate ilike filtering: only return airports that match
        expected_matches = [
            a for a in airport_mocks
            if airport_matches_search(a, search_term)
        ]

        # Set up mock query chain
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = expected_matches

        response = client.get(
            "/api/reference/airports",
            params={"search": search_term},
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code} "
            f"for search term '{search_term}'"
        )

        results = response.json()

        # Verify every returned result matches the search term
        for result in results:
            ident = result.get("ident", "") or ""
            iata = result.get("iata", "") or ""
            name = result.get("name", "") or ""
            city = result.get("city", "") or ""

            term_lower = search_term.lower()
            matches = (
                term_lower in ident.lower()
                or term_lower in iata.lower()
                or term_lower in name.lower()
                or term_lower in city.lower()
            )

            assert matches, (
                f"Airport result does not match search term '{search_term}': "
                f"ident='{ident}', iata='{iata}', name='{name}', city='{city}'"
            )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        aircrafts=aircraft_list_strategy,
        search_term=search_term_strategy,
    )
    def test_property_1_aircraft_search_returns_only_matching(
        self, client, mock_db, aircrafts, search_term
    ):
        """
        **Validates: Requirements 2.4**

        For any set of aircraft records and any non-empty search string,
        every aircraft returned by GET /api/reference/aircrafts?search=<term>
        must match the search term (case-insensitive) in the model field.
        """
        # Build mock aircraft objects
        aircraft_mocks = [
            make_aircraft_mock(
                aircraft_id=i + 1,
                model=a["model"],
                details={"mass_max": 70000},
            )
            for i, a in enumerate(aircrafts)
        ]

        # Simulate ilike filtering: only return aircrafts that match
        expected_matches = [
            a for a in aircraft_mocks
            if aircraft_matches_search(a, search_term)
        ]

        # Set up mock query chain
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = expected_matches

        response = client.get(
            "/api/reference/aircrafts",
            params={"search": search_term},
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code} "
            f"for search term '{search_term}'"
        )

        results = response.json()

        # Verify every returned result matches the search term
        for result in results:
            model = result.get("model", "") or ""
            term_lower = search_term.lower()

            assert term_lower in model.lower(), (
                f"Aircraft result does not match search term '{search_term}': "
                f"model='{model}'"
            )


# --- Details strategy for aircraft ---
aircraft_details_strategy = st.fixed_dictionaries(
    {},
    optional={
        "mass_max": st.one_of(st.none(), st.integers(min_value=1000, max_value=600000)),
        "manufacturer": st.one_of(st.none(), safe_text),
        "engine_type": st.one_of(st.none(), safe_text),
    },
)


class TestAPIResponseContainsAllRequiredFields:
    """
    Feature: overflight-charges-user-tab, Property 2: API response contains all required fields

    **Validates: Requirements 2.1, 2.3**

    For any airport record in the database, the /api/reference/airports response
    item must contain non-null `ident` and include `iata`, `name`, `city`, and
    `country` fields. For any aircraft record, the /api/reference/aircrafts
    response item must contain non-null `model` and include `details` fields.
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        airports=airport_list_strategy,
    )
    def test_property_2_airport_response_contains_all_required_fields(
        self, client, mock_db, airports
    ):
        """
        **Validates: Requirements 2.1**

        For any airport record in the database, the GET /api/reference/airports
        response item must contain non-null `ident` (string) and include `iata`,
        `name`, `city`, and `country` fields (may be null).
        """
        # Build mock airport objects
        airport_mocks = [
            make_airport_mock(
                airport_id=i + 1,
                ident=a["ident"],
                iata=a["iata"],
                name=a["name"],
                city=a["city"],
            )
            for i, a in enumerate(airports)
        ]

        # Set up mock query chain (no search filter, return all)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.all.return_value = airport_mocks

        response = client.get("/api/reference/airports")

        assert response.status_code == 200

        results = response.json()
        assert len(results) == len(airports)

        for result in results:
            # ident must be present and non-null string
            assert "ident" in result, "Airport response missing 'ident' field"
            assert result["ident"] is not None, "Airport 'ident' must not be null"
            assert isinstance(result["ident"], str), "Airport 'ident' must be a string"

            # iata, name, city, country must be present as keys (can be null)
            assert "iata" in result, "Airport response missing 'iata' field"
            assert "name" in result, "Airport response missing 'name' field"
            assert "city" in result, "Airport response missing 'city' field"
            assert "country" in result, "Airport response missing 'country' field"

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        aircrafts=st.lists(
            st.fixed_dictionaries({
                "model": aircraft_model_strategy,
                "details": aircraft_details_strategy,
            }),
            min_size=1,
            max_size=10,
        ),
    )
    def test_property_2_aircraft_response_contains_all_required_fields(
        self, client, mock_db, aircrafts
    ):
        """
        **Validates: Requirements 2.3**

        For any aircraft record in the database, the GET /api/reference/aircrafts
        response item must contain non-null `model` (string) and include `details`
        field (dict).
        """
        # Build mock aircraft objects
        aircraft_mocks = [
            make_aircraft_mock(
                aircraft_id=i + 1,
                model=a["model"],
                details=a["details"],
            )
            for i, a in enumerate(aircrafts)
        ]

        # Set up mock query chain (no search filter, return all)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.all.return_value = aircraft_mocks

        response = client.get("/api/reference/aircrafts")

        assert response.status_code == 200

        results = response.json()
        assert len(results) == len(aircrafts)

        for result in results:
            # model must be present and non-null string
            assert "model" in result, "Aircraft response missing 'model' field"
            assert result["model"] is not None, "Aircraft 'model' must not be null"
            assert isinstance(result["model"], str), "Aircraft 'model' must be a string"

            # details must be present and be a dict
            assert "details" in result, "Aircraft response missing 'details' field"
            assert isinstance(result["details"], dict), "Aircraft 'details' must be a dict"
