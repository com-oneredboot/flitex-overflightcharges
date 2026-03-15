"""Unit tests for charge calculation interface and session builder stubs (Task 8.2).

Tests the ChargeCalculationInterface, DefaultOverflightChargeCalculator,
SessionBuilder._build_totals, and SessionBuilder._build_comparison_section.

Validates Requirements: 10.7, 10.8, 10.10, 21.1, 21.2, 21.4, 21.5
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from src.services.charge_calculation import (
    ChargeCalculationInterface,
    DefaultOverflightChargeCalculator,
    DEFAULT_EUR_TO_USD,
)
from src.services.fir_intersection_engine import FIRCrossingRecord
from src.services.session_builder import SessionBuilder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_fir_crossing(**overrides) -> FIRCrossingRecord:
    """Create a FIRCrossingRecord with sensible defaults."""
    defaults = {
        "sequence": 1,
        "icao_code": "EGTT",
        "fir_name": "London",
        "country": "United Kingdom",
        "country_code": "GB",
        "entry_point": (51.0, -1.0),
        "exit_point": (52.0, 0.0),
        "segment_distance_km": 185.2,
        "segment_distance_nm": 100.0,
        "gc_entry_exit_distance_km": 184.0,
        "gc_entry_exit_distance_nm": 99.3,
        "segment_geometry": {"type": "LineString", "coordinates": []},
        "calculation_method": "postgis_geography",
    }
    defaults.update(overrides)
    return FIRCrossingRecord(**defaults)


def _make_charge(**overrides) -> dict:
    """Create a charge dict matching the fir_charges schema."""
    defaults = {
        "icao_code": "EGTT",
        "fir_name": "London",
        "country": "United Kingdom",
        "country_code": "GB",
        "formula_code": "EUROCONTROL",
        "formula_version": 1,
        "formula_effective_date": "2024-01-01",
        "unit_rate": 85.5,
        "unit_rate_source": "eurocontrol_unit_rates",
        "unit_rate_effective_date": "2024-01-01",
        "distance_factor": 1.0,
        "weight_factor": 3.1623,
        "charge_amount": 150.00,
        "currency": "EUR",
        "charge_in_usd": 165.00,
        "exchange_rate": 1.0,
        "exchange_rate_date": "2024-01-01",
        "distance_used_km": 185.2,
        "distance_method": "segment",
        "bilateral_exemption": None,
        "charge_type": "overflight",
        "justification": "test charge",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# ChargeCalculationInterface tests
# ---------------------------------------------------------------------------

class TestChargeCalculationInterface:
    """Tests for the abstract ChargeCalculationInterface."""

    def test_interface_raises_not_implemented(self):
        """Base interface must raise NotImplementedError."""
        interface = ChargeCalculationInterface()
        crossing = _make_fir_crossing()
        db = MagicMock()

        with pytest.raises(NotImplementedError):
            interface.calculate_fir_charge(crossing, "B738", 70000.0, db)


# ---------------------------------------------------------------------------
# DefaultOverflightChargeCalculator tests
# ---------------------------------------------------------------------------

class TestDefaultOverflightChargeCalculator:
    """Tests for the default overflight charge calculator."""

    def test_charge_entry_has_required_fields(self):
        """Every charge dict must contain all schema fields."""
        calc = DefaultOverflightChargeCalculator()
        crossing = _make_fir_crossing()
        db = MagicMock()

        # Mock formula lookup to return None (no formula)
        with patch.object(calc, "_lookup_formula", return_value=None), \
             patch.object(calc, "_fetch_unit_rate", return_value=None):
            result = calc.calculate_fir_charge(crossing, "B738", 70000.0, db)

        required_keys = {
            "icao_code", "fir_name", "country", "country_code",
            "formula_code", "formula_version", "formula_effective_date",
            "unit_rate", "unit_rate_source", "unit_rate_effective_date",
            "distance_factor", "weight_factor", "charge_amount",
            "currency", "charge_in_usd", "exchange_rate",
            "exchange_rate_date", "distance_used_km", "distance_method",
            "bilateral_exemption", "charge_type", "justification",
        }
        assert required_keys.issubset(result.keys())

    def test_bilateral_exemption_is_null(self):
        """bilateral_exemption must be None for default overflight charges.

        Validates Requirement: 21.1
        """
        calc = DefaultOverflightChargeCalculator()
        crossing = _make_fir_crossing()
        db = MagicMock()

        with patch.object(calc, "_lookup_formula", return_value=None), \
             patch.object(calc, "_fetch_unit_rate", return_value=None):
            result = calc.calculate_fir_charge(crossing, "B738", 70000.0, db)

        assert result["bilateral_exemption"] is None

    def test_charge_type_is_overflight(self):
        """charge_type must default to 'overflight'.

        Validates Requirement: 21.5
        """
        calc = DefaultOverflightChargeCalculator()
        crossing = _make_fir_crossing()
        db = MagicMock()

        with patch.object(calc, "_lookup_formula", return_value=None), \
             patch.object(calc, "_fetch_unit_rate", return_value=None):
            result = calc.calculate_fir_charge(crossing, "B738", 70000.0, db)

        assert result["charge_type"] == "overflight"

    def test_distance_method_is_segment(self):
        """distance_method must be 'segment' for default calculation."""
        calc = DefaultOverflightChargeCalculator()
        crossing = _make_fir_crossing()
        db = MagicMock()

        with patch.object(calc, "_lookup_formula", return_value=None), \
             patch.object(calc, "_fetch_unit_rate", return_value=None):
            result = calc.calculate_fir_charge(crossing, "B738", 70000.0, db)

        assert result["distance_method"] == "segment"

    def test_charge_with_unit_rate(self):
        """Charge should be non-zero when unit rate data is available."""
        calc = DefaultOverflightChargeCalculator()
        crossing = _make_fir_crossing(segment_distance_nm=200.0)
        db = MagicMock()

        rate_data = {
            "unit_rate": 85.50,
            "ex_rate_to_eur": 1.0,
            "currency": "EUR",
            "date_from": date(2024, 1, 1),
            "date_to": date(2024, 12, 31),
            "country_name": "United Kingdom",
        }

        with patch.object(calc, "_lookup_formula", return_value=None), \
             patch.object(calc, "_fetch_unit_rate", return_value=rate_data):
            result = calc.calculate_fir_charge(crossing, "B738", 70000.0, db)

        assert result["charge_amount"] > 0
        assert result["charge_in_usd"] > 0
        assert result["unit_rate"] == 85.50

    def test_no_formula_uses_standard_calc(self):
        """When no formula exists, standard EUROCONTROL calc is used."""
        calc = DefaultOverflightChargeCalculator()
        crossing = _make_fir_crossing()
        db = MagicMock()

        with patch.object(calc, "_lookup_formula", return_value=None), \
             patch.object(calc, "_fetch_unit_rate", return_value=None):
            result = calc.calculate_fir_charge(crossing, "B738", 70000.0, db)

        assert result["formula_code"] == "NONE"
        assert result["formula_version"] == 0

    def test_icao_code_matches_crossing(self):
        """Charge icao_code must match the FIR crossing."""
        calc = DefaultOverflightChargeCalculator()
        crossing = _make_fir_crossing(icao_code="LFFF")
        db = MagicMock()

        with patch.object(calc, "_lookup_formula", return_value=None), \
             patch.object(calc, "_fetch_unit_rate", return_value=None):
            result = calc.calculate_fir_charge(crossing, "B738", 70000.0, db)

        assert result["icao_code"] == "LFFF"


# ---------------------------------------------------------------------------
# SessionBuilder._build_totals tests
# ---------------------------------------------------------------------------

class TestBuildTotals:
    """Tests for SessionBuilder._build_totals."""

    def setup_method(self):
        self.builder = SessionBuilder()

    def test_empty_charges(self):
        """Empty charges list produces zero totals."""
        result = self.builder._build_totals([])

        assert result["by_currency"] == {}
        assert result["total_usd"] == 0.0
        assert result["total_eur"] == 0.0
        assert result["fir_count"] == 0
        assert result["countries_count"] == 0

    def test_single_eur_charge(self):
        """Single EUR charge populates by_currency and totals correctly."""
        charges = [_make_charge(
            charge_amount=100.0, currency="EUR",
            charge_in_usd=110.0, country_code="FR",
        )]
        result = self.builder._build_totals(charges)

        assert result["by_currency"]["EUR"] == 100.0
        assert result["total_usd"] == 110.0
        assert result["total_eur"] == 100.0
        assert result["fir_count"] == 1
        assert result["countries_count"] == 1

    def test_multiple_currencies(self):
        """Charges in different currencies are grouped correctly."""
        charges = [
            _make_charge(charge_amount=100.0, currency="EUR",
                         charge_in_usd=110.0, country_code="FR"),
            _make_charge(charge_amount=200.0, currency="GBP",
                         charge_in_usd=250.0, country_code="GB"),
        ]
        result = self.builder._build_totals(charges)

        assert result["by_currency"]["EUR"] == 100.0
        assert result["by_currency"]["GBP"] == 200.0
        assert result["total_usd"] == 360.0
        assert result["fir_count"] == 2
        assert result["countries_count"] == 2

    def test_same_country_multiple_firs(self):
        """Multiple FIRs in the same country count as one country."""
        charges = [
            _make_charge(charge_amount=50.0, currency="EUR",
                         charge_in_usd=55.0, country_code="FR"),
            _make_charge(charge_amount=75.0, currency="EUR",
                         charge_in_usd=82.5, country_code="FR"),
        ]
        result = self.builder._build_totals(charges)

        assert result["by_currency"]["EUR"] == 125.0
        assert result["fir_count"] == 2
        assert result["countries_count"] == 1

    def test_eur_derived_from_usd_when_no_eur_bucket(self):
        """When no EUR charges exist, total_eur is derived from total_usd."""
        charges = [_make_charge(
            charge_amount=200.0, currency="GBP",
            charge_in_usd=250.0, country_code="GB",
        )]
        result = self.builder._build_totals(charges)

        expected_eur = round(250.0 / DEFAULT_EUR_TO_USD, 2)
        assert result["total_eur"] == expected_eur

    def test_totals_schema_keys(self):
        """Result must have exactly the required schema keys.

        Validates Requirement: 10.8
        """
        charges = [_make_charge()]
        result = self.builder._build_totals(charges)

        assert set(result.keys()) == {
            "by_currency", "total_usd", "total_eur",
            "fir_count", "countries_count",
        }


# ---------------------------------------------------------------------------
# SessionBuilder._build_comparison_section tests
# ---------------------------------------------------------------------------

class TestBuildComparisonSection:
    """Tests for SessionBuilder._build_comparison_section."""

    def setup_method(self):
        self.builder = SessionBuilder()

    def test_comparison_has_required_keys(self):
        """Comparison section must have all required schema keys.

        Validates Requirement: 10.10
        """
        input_data = {
            "origin": "KJFK",
            "destination": "EGLL",
            "flight_number": "BA178",
            "flight_date": "2024-06-15",
        }
        result = self.builder._build_comparison_section(input_data)

        assert "invoice_match_keys" in result
        assert "flown_route_available" in result
        assert "flown_calculation_id" in result
        assert "planned_vs_flown_delta" in result

    def test_flown_route_placeholders(self):
        """Flown route fields must be placeholder values.

        Validates Requirement: 21.2
        """
        input_data = {"origin": "KJFK", "destination": "EGLL"}
        result = self.builder._build_comparison_section(input_data)

        assert result["flown_route_available"] is False
        assert result["flown_calculation_id"] is None
        assert result["planned_vs_flown_delta"] is None

    def test_invoice_match_keys_populated(self):
        """Invoice match keys must be populated from input data."""
        input_data = {
            "origin": "KJFK",
            "destination": "EGLL",
            "flight_number": "BA178",
            "flight_date": "2024-06-15",
        }
        result = self.builder._build_comparison_section(input_data)
        keys = result["invoice_match_keys"]

        assert keys["flight_number"] == "BA178"
        assert keys["date"] == "2024-06-15"
        assert keys["origin"] == "KJFK"
        assert keys["destination"] == "EGLL"

    def test_missing_optional_fields(self):
        """Missing flight_number and flight_date should be None."""
        input_data = {"origin": "KJFK", "destination": "EGLL"}
        result = self.builder._build_comparison_section(input_data)
        keys = result["invoice_match_keys"]

        assert keys["flight_number"] is None
        assert keys["date"] is None

    def test_date_object_converted_to_string(self):
        """date objects in input_data should be converted to strings."""
        input_data = {
            "origin": "KJFK",
            "destination": "EGLL",
            "flight_date": date(2024, 6, 15),
        }
        result = self.builder._build_comparison_section(input_data)

        assert result["invoice_match_keys"]["date"] == "2024-06-15"
