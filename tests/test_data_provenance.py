"""Unit tests for SessionBuilder.build_data_provenance (Task 8.4).

Tests the data provenance assembly that queries the database for actual
version info about FIR boundaries, unit rates, nav data, exchange rates,
and formulas.

Validates Requirements: 10.9
"""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.services.route_parser import TokenResolutionResult, TokenRecord, Waypoint
from src.services.session_builder import SessionBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token_result(**overrides) -> TokenResolutionResult:
    """Build a minimal TokenResolutionResult for testing."""
    defaults = {
        "tokens": [],
        "resolved_waypoints": [
            Waypoint(identifier="KJFK", latitude=40.6, longitude=-73.8, source_table="airports"),
            Waypoint(identifier="MERIT", latitude=42.0, longitude=-60.0, source_table="nav_waypoints"),
            Waypoint(identifier="EGLL", latitude=51.5, longitude=-0.5, source_table="airports"),
        ],
        "unresolved_tokens": [],
        "route_linestring_coords": [(-73.8, 40.6), (-60.0, 42.0), (-0.5, 51.5)],
    }
    defaults.update(overrides)
    return TokenResolutionResult(**defaults)


def _make_charges() -> list[dict]:
    """Build a minimal charges list for testing."""
    return [
        {
            "icao_code": "KZNY",
            "formula_code": "EUROCONTROL",
            "formula_version": 2,
            "exchange_rate_date": "2024-06-01",
        },
        {
            "icao_code": "EGTT",
            "formula_code": "UK_FORMULA",
            "formula_version": 1,
            "exchange_rate_date": "2024-05-15",
        },
    ]


# ---------------------------------------------------------------------------
# Tests: build_data_provenance (full assembly)
# ---------------------------------------------------------------------------

class TestBuildDataProvenance:
    """Tests for the top-level build_data_provenance method."""

    def test_returns_all_required_sections(self):
        """Provenance dict contains all five required top-level keys."""
        builder = SessionBuilder()
        db = MagicMock()
        # Make DB queries return empty results
        db.execute.return_value.fetchone.return_value = None

        result = builder.build_data_provenance(
            token_result=_make_token_result(),
            charges=_make_charges(),
            db=db,
        )

        assert "fir_boundaries" in result
        assert "unit_rates" in result
        assert "nav_data" in result
        assert "exchange_rates" in result
        assert "formulas" in result

    def test_returns_correct_structure_with_db_data(self):
        """Provenance sections have the expected keys from the design schema."""
        builder = SessionBuilder()
        db = MagicMock()

        # Mock FIR boundaries query
        fir_row = MagicMock()
        fir_row.cnt = 245
        fir_row.latest = datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc)

        # Mock unit rates query
        rates_row = MagicMock()
        rates_row.latest_period = date(2024, 7, 31)
        rates_row.latest_from = date(2024, 7, 1)

        db.execute.return_value.fetchone.side_effect = [fir_row, rates_row]

        result = builder.build_data_provenance(
            token_result=_make_token_result(),
            charges=_make_charges(),
            db=db,
        )

        # FIR boundaries
        fir = result["fir_boundaries"]
        assert fir["source"] == "reference.fir_boundaries"
        assert fir["version_id"] is not None
        assert "2024-03-15" in fir["effective_date"]

        # Unit rates
        ur = result["unit_rates"]
        assert ur["source"] == "EUROCONTROL"
        assert ur["last_updated"] == "2024-07-31"
        assert ur["scrape_date"] == "2024-07-01"

        # Nav data
        nav = result["nav_data"]
        assert set(nav["tables_used"]) == {"airports", "nav_waypoints"}

        # Exchange rates
        ex = result["exchange_rates"]
        assert ex["date"] == "2024-06-01"
        assert ex["source"] == "EUROCONTROL"

        # Formulas
        fm = result["formulas"]
        assert "EUROCONTROL" in fm["formulas_used"]
        assert "UK_FORMULA" in fm["formulas_used"]
        assert fm["registry_version"] == "2"


# ---------------------------------------------------------------------------
# Tests: _provenance_fir_boundaries
# ---------------------------------------------------------------------------

class TestProvenanceFirBoundaries:
    """Tests for FIR boundary provenance extraction."""

    def test_returns_defaults_when_db_empty(self):
        builder = SessionBuilder()
        db = MagicMock()
        row = MagicMock()
        row.latest = None
        row.cnt = 0
        db.execute.return_value.fetchone.return_value = row

        result = builder._provenance_fir_boundaries(db)

        assert result["source"] == "reference.fir_boundaries"
        assert result["version_id"] is None
        assert result["effective_date"] is None
        assert result["airac_cycle"] is None

    def test_returns_version_info_when_data_exists(self):
        builder = SessionBuilder()
        db = MagicMock()
        row = MagicMock()
        row.cnt = 300
        row.latest = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        db.execute.return_value.fetchone.return_value = row

        result = builder._provenance_fir_boundaries(db)

        assert result["version_id"] == "fir-300-2024-06-01"
        assert "2024-06-01" in result["effective_date"]

    def test_handles_db_exception_gracefully(self):
        builder = SessionBuilder()
        db = MagicMock()
        db.execute.side_effect = Exception("connection lost")

        result = builder._provenance_fir_boundaries(db)

        assert result["source"] == "reference.fir_boundaries"
        assert result["version_id"] is None


# ---------------------------------------------------------------------------
# Tests: _provenance_unit_rates
# ---------------------------------------------------------------------------

class TestProvenanceUnitRates:
    """Tests for unit rate provenance extraction."""

    def test_returns_defaults_when_db_empty(self):
        builder = SessionBuilder()
        db = MagicMock()
        row = MagicMock()
        row.latest_period = None
        row.latest_from = None
        db.execute.return_value.fetchone.return_value = row

        result = builder._provenance_unit_rates(db)

        assert result["source"] == "EUROCONTROL"
        assert result["last_updated"] is None
        assert result["scrape_date"] is None

    def test_returns_dates_when_data_exists(self):
        builder = SessionBuilder()
        db = MagicMock()
        row = MagicMock()
        row.latest_period = date(2024, 12, 31)
        row.latest_from = date(2024, 12, 1)
        db.execute.return_value.fetchone.return_value = row

        result = builder._provenance_unit_rates(db)

        assert result["last_updated"] == "2024-12-31"
        assert result["scrape_date"] == "2024-12-01"

    def test_handles_db_exception_gracefully(self):
        builder = SessionBuilder()
        db = MagicMock()
        db.execute.side_effect = Exception("timeout")

        result = builder._provenance_unit_rates(db)

        assert result["source"] == "EUROCONTROL"
        assert result["last_updated"] is None


# ---------------------------------------------------------------------------
# Tests: _provenance_nav_data
# ---------------------------------------------------------------------------

class TestProvenanceNavData:
    """Tests for navigation data provenance extraction."""

    def test_extracts_unique_source_tables(self):
        builder = SessionBuilder()
        token_result = _make_token_result()

        result = builder._provenance_nav_data(token_result)

        assert result["tables_used"] == ["airports", "nav_waypoints"]
        assert result["airac_cycle"] is None

    def test_empty_waypoints_returns_empty_tables(self):
        builder = SessionBuilder()
        token_result = _make_token_result(resolved_waypoints=[])

        result = builder._provenance_nav_data(token_result)

        assert result["tables_used"] == []

    def test_includes_coordinate_and_nat_sources(self):
        builder = SessionBuilder()
        waypoints = [
            Waypoint(identifier="5000N", latitude=50.0, longitude=-49.0, source_table="coordinate"),
            Waypoint(identifier="NATW1", latitude=51.0, longitude=-40.0, source_table="plans.NATs"),
            Waypoint(identifier="EGLL", latitude=51.5, longitude=-0.5, source_table="airports"),
        ]
        token_result = _make_token_result(resolved_waypoints=waypoints)

        result = builder._provenance_nav_data(token_result)

        assert result["tables_used"] == ["airports", "coordinate", "plans.NATs"]


# ---------------------------------------------------------------------------
# Tests: _provenance_exchange_rates
# ---------------------------------------------------------------------------

class TestProvenanceExchangeRates:
    """Tests for exchange rate provenance extraction."""

    def test_picks_latest_date_from_charges(self):
        charges = [
            {"exchange_rate_date": "2024-01-15"},
            {"exchange_rate_date": "2024-06-01"},
            {"exchange_rate_date": "2024-03-10"},
        ]

        result = SessionBuilder._provenance_exchange_rates(charges)

        assert result["date"] == "2024-06-01"
        assert result["source"] == "EUROCONTROL"

    def test_handles_empty_charges(self):
        result = SessionBuilder._provenance_exchange_rates([])

        assert result["date"] is None
        assert result["source"] == "EUROCONTROL"

    def test_handles_missing_exchange_rate_date(self):
        charges = [{"formula_code": "X"}, {"exchange_rate_date": "2024-02-01"}]

        result = SessionBuilder._provenance_exchange_rates(charges)

        assert result["date"] == "2024-02-01"


# ---------------------------------------------------------------------------
# Tests: _provenance_formulas
# ---------------------------------------------------------------------------

class TestProvenanceFormulas:
    """Tests for formula registry provenance extraction."""

    def test_collects_distinct_formula_codes(self):
        charges = [
            {"formula_code": "EUROCONTROL", "formula_version": 2},
            {"formula_code": "UK_FORMULA", "formula_version": 1},
            {"formula_code": "EUROCONTROL", "formula_version": 2},
        ]

        result = SessionBuilder._provenance_formulas(charges)

        assert result["formulas_used"] == ["EUROCONTROL", "UK_FORMULA"]
        assert result["registry_version"] == "2"

    def test_handles_empty_charges(self):
        result = SessionBuilder._provenance_formulas([])

        assert result["formulas_used"] == []
        assert result["registry_version"] == "0"

    def test_handles_missing_formula_fields(self):
        charges = [{"icao_code": "KZNY"}]

        result = SessionBuilder._provenance_formulas(charges)

        assert result["formulas_used"] == []
        assert result["registry_version"] == "0"
