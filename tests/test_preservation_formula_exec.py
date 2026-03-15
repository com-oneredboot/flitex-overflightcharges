"""Preservation property tests for formula execution.

Property 2: Preservation - Single-line Expression Evaluation & Complete Response Structure

These tests verify that EXISTING behavior is preserved:
- Single-line arithmetic expressions evaluate correctly via eval()
- When all FIRs have valid single-line formulas, calculate_route_cost() returns
  a complete RouteCostResponse with all FIR charges summed into total_cost

These tests MUST PASS on UNFIXED code — they only exercise non-buggy inputs.

**Validates: Requirements 3.1, 3.2, 3.6**
"""

import uuid
from decimal import Decimal
from unittest.mock import Mock

from hypothesis import given, settings, strategies as st, assume
from sqlalchemy.orm import Session

from src.services.cost_calculator import CostCalculator
from src.services.route_parser import Waypoint
from src.models.formula import Formula
from src.models.route_calculation import RouteCalculation
from src.schemas.route_cost import FIRChargeBreakdown


# --- Strategies ---


def numeric_literal_strategy():
    """Generate numeric literals suitable for formula expressions."""
    return st.sampled_from([
        "0.1", "0.5", "1.0", "2.0", "3.0", "5.0", "10.0", "100.0", "0.01", "0.001",
    ])


def operator_strategy():
    """Generate arithmetic operators."""
    return st.sampled_from(["+", "-", "*"])


@st.composite
def single_line_expression_strategy(draw):
    """Generate random single-line arithmetic expressions using mtow_kg, distance_km,
    numeric literals, and operators (+, -, *).

    Produces expressions like:
      mtow_kg * 0.5 + distance_km * 2.0
      distance_km * 10.0 - mtow_kg * 0.001
      mtow_kg * 1.0 + 100.0
    """
    # Build an expression with 2-3 terms to keep it simple and avoid
    # division-by-zero or overly complex expressions
    num_terms = draw(st.integers(min_value=2, max_value=3))
    terms = []
    for i in range(num_terms):
        var = draw(st.sampled_from(["mtow_kg", "distance_km"]))
        coeff = draw(numeric_literal_strategy())
        terms.append(f"{var} * {coeff}")

    # Join terms with operators
    expr = terms[0]
    for term in terms[1:]:
        op = draw(operator_strategy())
        expr = f"{expr} {op} {term}"

    return expr


def positive_float_strategy():
    """Generate positive floats suitable for mtow_kg and distance_km."""
    return st.floats(min_value=1.0, max_value=50000.0, allow_nan=False, allow_infinity=False)


# --- Helpers ---


def _make_formula(country_code: str, formula_code: str, formula_logic: str) -> Formula:
    """Create a Formula object with the given logic."""
    return Formula(
        country_code=country_code,
        formula_code=formula_code,
        formula_logic=formula_logic,
        description=f"Test formula for {country_code}",
        effective_date="2024-01-01",
        currency="USD",
        version_number=1,
        is_active=True,
        created_by="test_user",
    )


def _make_fir_mock(icao_code: str, fir_name: str, country_code: str):
    """Create a mock FIR object."""
    fir = Mock()
    fir.icao_code = icao_code
    fir.fir_name = fir_name
    fir.country_code = country_code
    return fir


def _make_fir_crossing_mock(icao_code: str):
    """Create a mock FIR crossing result."""
    crossing = Mock()
    crossing.icao_code = icao_code
    return crossing


def _create_calculator_with_session():
    """Create a CostCalculator with a mocked session that handles flush/commit."""
    mock_session = Mock(spec=Session)
    mock_session.add = Mock()
    mock_session.commit = Mock()
    mock_session.refresh = Mock()

    def mock_flush():
        for call in mock_session.add.call_args_list:
            obj = call[0][0]
            if isinstance(obj, RouteCalculation):
                obj.id = uuid.uuid4()

    mock_session.flush = Mock(side_effect=mock_flush)

    calculator = CostCalculator(mock_session)
    return calculator, mock_session


# --- Property Tests ---


class TestSingleLineExpressionPreservation:
    """Property 2 (Part A): Single-line expression evaluation preservation.

    Verifies that apply_formula() with single-line arithmetic expressions
    returns the same Decimal result as eval() with the same context.

    These tests MUST PASS on unfixed code — single-line expressions work
    correctly with the existing eval() implementation.

    **Validates: Requirements 3.1, 3.6**
    """

    @given(
        expression=single_line_expression_strategy(),
        mtow_kg=positive_float_strategy(),
        distance_km=positive_float_strategy(),
    )
    @settings(max_examples=20)
    def test_single_line_formula_matches_eval(self, expression, mtow_kg, distance_km):
        """**Validates: Requirements 3.1**

        For any single-line arithmetic expression using mtow_kg, distance_km,
        and operators (+, -, *), apply_formula() SHALL return a Decimal equal
        to eval() of the same expression with the same context.
        """
        context = {
            "mtow_kg": mtow_kg,
            "distance_km": distance_km,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
        }

        # Compute expected result via eval (the same mechanism apply_formula uses)
        expected_raw = eval(expression, {"__builtins__": {}}, context)
        expected = Decimal(str(expected_raw))
        if expected < 0:
            expected = Decimal("0.00")

        # Call apply_formula
        formula = _make_formula("XX", "XX_TEST", expression)
        calculator, _ = _create_calculator_with_session()
        result = calculator.apply_formula(formula, mtow_kg, distance_km)

        assert isinstance(result, Decimal)
        assert result == expected, (
            f"Expression '{expression}' with mtow_kg={mtow_kg}, distance_km={distance_km}: "
            f"expected {expected}, got {result}"
        )


class TestCompleteResponsePreservation:
    """Property 2 (Part B): Complete response structure preservation.

    When all FIRs have valid single-line formulas, calculate_route_cost()
    returns a complete RouteCostResponse with all FIR charges summed into total_cost.

    These tests MUST PASS on unfixed code — complete FIR sets with valid
    single-line formulas work correctly with the existing implementation.

    **Validates: Requirements 3.2**
    """

    @given(
        mtow_kg=positive_float_strategy(),
        expr_a=single_line_expression_strategy(),
        expr_b=single_line_expression_strategy(),
    )
    @settings(max_examples=20)
    def test_all_firs_present_and_total_equals_sum(self, mtow_kg, expr_a, expr_b):
        """**Validates: Requirements 3.2**

        Given a set of FIR crossings where ALL FIRs have valid single-line
        formulas, the response SHALL contain all FIRs in fir_breakdown and
        total_cost SHALL equal the sum of individual charge_amounts.
        """
        # Skip expressions that would produce negative charges (clamped to 0)
        # to keep the test focused on the structural property
        calculator, mock_session = _create_calculator_with_session()

        # Set up 2 FIRs, both with valid single-line formulas
        fir_egtt = _make_fir_mock("EGTT", "London FIR", "GB")
        fir_lfff = _make_fir_mock("LFFF", "Paris FIR", "FR")

        fir_crossings = [
            _make_fir_crossing_mock("EGTT"),
            _make_fir_crossing_mock("LFFF"),
        ]

        formula_gb = _make_formula("GB", "GB_SIMPLE", expr_a)
        formula_fr = _make_formula("FR", "FR_SIMPLE", expr_b)

        # Mock route parser
        waypoints = [Waypoint("EGLL", 51.5, -0.5), Waypoint("LFPG", 49.0, 2.5)]
        calculator.route_parser.parse_route = Mock(return_value=waypoints)
        calculator.route_parser.identify_fir_crossings_db = Mock(return_value=fir_crossings)

        # Mock FIR service
        fir_map = {"EGTT": fir_egtt, "LFFF": fir_lfff}
        calculator.fir_service.get_active_fir = Mock(side_effect=lambda code: fir_map.get(code))

        # Mock formula service — both countries have valid single-line formulas
        formula_map = {"GB": formula_gb, "FR": formula_fr}
        calculator.formula_service.get_active_formula = Mock(
            side_effect=lambda code: formula_map.get(code)
        )

        # Execute
        result = calculator.calculate_route_cost(
            route_string="EGLL DCT LFPG",
            origin="EGLL",
            destination="LFPG",
            aircraft_type="A320",
            mtow_kg=mtow_kg,
        )

        # ALL FIRs must appear in the breakdown
        fir_codes = [b.icao_code for b in result.fir_breakdown]
        assert len(result.fir_breakdown) == 2, (
            f"Expected 2 FIRs in breakdown, got {len(result.fir_breakdown)}: {fir_codes}"
        )
        assert "EGTT" in fir_codes
        assert "LFFF" in fir_codes

        # total_cost must equal sum of individual charges
        sum_of_charges = sum(b.charge_amount for b in result.fir_breakdown)
        assert result.total_cost == sum_of_charges, (
            f"total_cost ({result.total_cost}) != sum of charges ({sum_of_charges})"
        )

        # Each charge must be a non-negative Decimal
        for breakdown in result.fir_breakdown:
            assert isinstance(breakdown.charge_amount, Decimal)
            assert breakdown.charge_amount >= 0
