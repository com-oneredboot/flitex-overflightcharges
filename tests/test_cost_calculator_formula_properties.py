"""Property-based tests for CostCalculator formula field population.

Tests that the CostCalculator correctly populates formula details
in FIRChargeBreakdown entries from the active Formula object.

Feature: planned-flight-summary
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock
from datetime import date

from hypothesis import given, settings, strategies as st, assume
from sqlalchemy.orm import Session

from src.services.cost_calculator import CostCalculator
from src.services.route_parser import Waypoint
from src.models.iata_fir import IataFir
from src.models.formula import Formula
from src.models.route_calculation import RouteCalculation
from src.schemas.route_cost import FIRChargeBreakdown


# --- Strategies ---

def formula_code_strategy():
    """Generate valid formula codes like 'US_STANDARD', 'CA_FORMULA'."""
    return st.from_regex(r"[A-Z]{2}_[A-Z]{3,10}", fullmatch=True)


def version_number_strategy():
    """Generate valid version numbers (positive integers)."""
    return st.integers(min_value=1, max_value=100)


def country_code_strategy():
    """Generate 2-letter uppercase country codes."""
    return st.from_regex(r"[A-Z]{2}", fullmatch=True)


def icao_code_strategy():
    """Generate 4-letter uppercase ICAO codes."""
    return st.from_regex(r"[A-Z]{4}", fullmatch=True)


def formula_logic_strategy():
    """Generate safe formula logic expressions."""
    return st.sampled_from([
        "mtow_kg * 0.5",
        "mtow_kg * 0.3 + distance_km * 2.0",
        "max(mtow_kg * 0.001, 100)",
        "distance_km * 1.5",
        "mtow_kg * 0.1 + 50",
    ])


def description_strategy():
    """Generate formula descriptions."""
    return st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Z"), whitelist_characters=" -"),
        min_size=1,
        max_size=50,
    ).filter(lambda s: s.strip() != "")


def effective_date_strategy():
    """Generate effective dates."""
    return st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))


def currency_strategy():
    """Generate 3-letter currency codes."""
    return st.sampled_from(["USD", "EUR", "GBP", "CAD", "CHF"])


# --- Helpers ---

def _create_calculator_with_mocks(
    fir_icao: str,
    fir_name: str,
    country_code: str,
    formula: Formula,
):
    """Create a CostCalculator with mocked dependencies for a single FIR crossing."""
    mock_session = Mock(spec=Session)
    mock_session.add = Mock()
    mock_session.flush = Mock()
    mock_session.commit = Mock()
    mock_session.refresh = Mock()

    import uuid

    def mock_flush():
        for call in mock_session.add.call_args_list:
            obj = call[0][0]
            if isinstance(obj, RouteCalculation):
                obj.id = uuid.uuid4()

    mock_session.flush.side_effect = mock_flush

    calculator = CostCalculator(mock_session)

    # Mock route parser
    waypoints = [Waypoint("ORIG", 40.0, -74.0), Waypoint("DEST", 50.0, -1.0)]
    calculator.route_parser.parse_route = Mock(return_value=waypoints)
    calculator.route_parser.identify_fir_crossings = Mock(return_value=[fir_icao])

    # Mock FIR service
    fir = Mock()
    fir.icao_code = fir_icao
    fir.fir_name = fir_name
    fir.country_code = country_code
    calculator.fir_service.get_all_firs = Mock(return_value=[fir])
    calculator.fir_service.get_fir_by_code = Mock(return_value=fir)

    # Mock formula service
    calculator.formula_service.get_active_formula = Mock(return_value=formula)

    return calculator


# --- Property Tests ---


class TestFormulaFieldPopulation:
    """Property 17: Backend FIR breakdown includes formula details from active formula.

    Validates: Requirements 9a.1, 9a.2, 9a.4
    """

    @given(
        fir_icao=icao_code_strategy(),
        country_code=country_code_strategy(),
        f_code=formula_code_strategy(),
        f_version=version_number_strategy(),
        f_logic=formula_logic_strategy(),
        f_description=description_strategy(),
        f_effective_date=effective_date_strategy(),
        f_currency=currency_strategy(),
    )
    @settings(max_examples=20)
    def test_fir_breakdown_contains_formula_code_and_version(
        self,
        fir_icao,
        country_code,
        f_code,
        f_version,
        f_logic,
        f_description,
        f_effective_date,
        f_currency,
    ):
        """**Validates: Requirements 9a.1, 9a.2, 9a.4**

        For any FIR crossing with an active formula, the FIRChargeBreakdown
        contains formula_code and formula_version matching the formula.
        """
        # Feature: planned-flight-summary, Property 17: Backend FIR breakdown includes formula details from active formula

        formula = Formula(
            country_code=country_code,
            formula_code=f_code,
            formula_logic=f_logic,
            description=f_description,
            effective_date=f_effective_date,
            currency=f_currency,
            version_number=f_version,
            is_active=True,
            created_by="test_user",
        )

        calculator = _create_calculator_with_mocks(
            fir_icao=fir_icao,
            fir_name=f"{fir_icao} FIR",
            country_code=country_code,
            formula=formula,
        )

        result = calculator.calculate_route_cost(
            route_string="ORIG DCT DEST",
            origin="ORIG",
            destination="DEST",
            aircraft_type="B738",
            mtow_kg=50000.0,
        )

        assert len(result.fir_breakdown) == 1
        breakdown = result.fir_breakdown[0]

        # Property 17: formula_code and formula_version match the formula
        assert breakdown.formula_code == f_code
        assert breakdown.formula_version == f_version


class TestFullFormulaDetails:
    """Property 21: Backend FIR breakdown includes full formula details.

    Validates: Requirements 12a.1, 12a.2, 12a.3, 12a.5
    """

    @given(
        fir_icao=icao_code_strategy(),
        country_code=country_code_strategy(),
        f_code=formula_code_strategy(),
        f_version=version_number_strategy(),
        f_logic=formula_logic_strategy(),
        f_description=description_strategy(),
        f_effective_date=effective_date_strategy(),
        f_currency=currency_strategy(),
    )
    @settings(max_examples=20)
    def test_fir_breakdown_contains_full_formula_details(
        self,
        fir_icao,
        country_code,
        f_code,
        f_version,
        f_logic,
        f_description,
        f_effective_date,
        f_currency,
    ):
        """**Validates: Requirements 12a.1, 12a.2, 12a.3, 12a.5**

        For any FIR crossing with an active formula, the FIRChargeBreakdown
        contains formula_description, formula_logic, and effective_date
        matching the formula object.
        """
        # Feature: planned-flight-summary, Property 21: Backend FIR breakdown includes full formula details

        formula = Formula(
            country_code=country_code,
            formula_code=f_code,
            formula_logic=f_logic,
            description=f_description,
            effective_date=f_effective_date,
            currency=f_currency,
            version_number=f_version,
            is_active=True,
            created_by="test_user",
        )

        calculator = _create_calculator_with_mocks(
            fir_icao=fir_icao,
            fir_name=f"{fir_icao} FIR",
            country_code=country_code,
            formula=formula,
        )

        result = calculator.calculate_route_cost(
            route_string="ORIG DCT DEST",
            origin="ORIG",
            destination="DEST",
            aircraft_type="B738",
            mtow_kg=50000.0,
        )

        assert len(result.fir_breakdown) == 1
        breakdown = result.fir_breakdown[0]

        # Property 21: full formula details match the formula object
        assert breakdown.formula_description == f_description
        assert breakdown.formula_logic == f_logic
        assert breakdown.effective_date == str(f_effective_date)
