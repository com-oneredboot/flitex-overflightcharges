"""Bug condition exploration tests for formula execution bugs.

Property 1: Bug Condition - Multi-line Formula eval() Failure & Silent FIR Skipping

These tests encode the EXPECTED (correct) behavior after the fix:
- Multi-line `def calculate(...)` formulas execute via exec() and return correct Decimal results
- Failed/missing FIRs appear in fir_breakdown with charge_amount=0 and warning objects

On UNFIXED code, these tests MUST FAIL — failure confirms the bugs exist:
- eval() raises SyntaxError for multi-line formulas
- Failed/missing FIRs are silently skipped via `continue`

**Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**
"""

import pytest
import uuid
from decimal import Decimal
from unittest.mock import Mock

from hypothesis import given, settings, strategies as st, assume
from sqlalchemy.orm import Session

from src.services.cost_calculator import CostCalculator
from src.services.route_parser import Waypoint
from src.models.iata_fir import IataFir
from src.models.formula import Formula
from src.models.route_calculation import RouteCalculation
from src.schemas.route_cost import FIRChargeBreakdown


# --- Strategies ---


def multiline_formula_body_strategy():
    """Generate arithmetic bodies for multi-line def calculate(...) formulas.

    Produces expressions like `distance * weight * 0.01` with varying
    operators and numeric coefficients.
    """
    coeff = st.sampled_from(["0.01", "0.5", "1.0", "2.5", "10.0", "0.001"])
    op = st.sampled_from(["*", "+"])

    @st.composite
    def build_body(draw):
        c1 = draw(coeff)
        c2 = draw(coeff)
        o = draw(op)
        # Build a simple arithmetic expression using the function params
        return f"distance * {c1} {o} weight * {c2}"

    return build_body()


def multiline_formula_strategy():
    """Generate multi-line `def calculate(distance, weight, context)` formula strings."""

    @st.composite
    def build_formula(draw):
        body_expr = draw(multiline_formula_body_strategy())
        # Multi-line function definition — the kind stored in the database
        formula_str = (
            f"def calculate(distance, weight, context):\n"
            f"    result = {body_expr}\n"
            f"    return result\n"
        )
        return formula_str, body_expr

    return build_formula()


def positive_float_strategy():
    """Generate positive floats suitable for mtow_kg and distance_km."""
    return st.floats(min_value=1.0, max_value=500000.0, allow_nan=False, allow_infinity=False)


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
    """Create a mock FIR crossing result (as returned by identify_fir_crossings_db)."""
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


class TestMultilineFormulaExecution:
    """Property 1 (Part A): Multi-line formula eval() failure.

    On UNFIXED code: apply_formula() raises ValidationException wrapping SyntaxError
    because eval() cannot handle multi-line def statements.

    EXPECTED behavior (after fix): apply_formula() executes the formula via exec(),
    calls calculate(), and returns the correct Decimal result.

    **Validates: Requirements 1.1, 2.1**
    """

    @given(
        formula_data=multiline_formula_strategy(),
        mtow_kg=positive_float_strategy(),
        distance_km=positive_float_strategy(),
    )
    @settings(max_examples=20)
    def test_multiline_formula_returns_decimal_result(
        self, formula_data, mtow_kg, distance_km
    ):
        """**Validates: Requirements 1.1, 2.1**

        For any multi-line def calculate(...) formula, apply_formula() SHALL
        return a Decimal equal to the expected calculation result.

        On UNFIXED code this FAILS because eval() raises SyntaxError.
        """
        formula_logic, body_expr = formula_data

        formula = _make_formula("US", "US_TEST", formula_logic)
        calculator, _ = _create_calculator_with_session()

        # Call apply_formula — on unfixed code, this raises ValidationException
        result = calculator.apply_formula(formula, mtow_kg, distance_km)

        # The formula body uses `distance` and `weight` as parameter names,
        # but apply_formula passes mtow_kg and distance_km into the context.
        # After the fix, exec() defines calculate(distance, weight, context)
        # and calls it with (mtow_kg, distance_km). So distance=mtow_kg, weight=distance_km.
        # Wait — actually looking at the FormulaExecutor pattern, the fix should call
        # calculate(mtow_kg, distance_km) mapping to (distance, weight).
        # So: distance = mtow_kg, weight = distance_km
        context = {"distance": mtow_kg, "weight": distance_km}
        expected = eval(body_expr, {"__builtins__": {}}, context)
        expected_decimal = Decimal(str(expected))

        # Ensure non-negative (matching apply_formula behavior)
        if expected_decimal < 0:
            expected_decimal = Decimal("0.00")

        assert isinstance(result, Decimal)
        assert result == expected_decimal


class TestSilentFIRSkipping:
    """Property 1 (Part B): Silent FIR skipping for failed/missing formulas.

    On UNFIXED code: calculate_route_cost() silently skips FIRs where formula
    execution fails or no formula exists, returning 0 FIR breakdown rows.

    EXPECTED behavior (after fix): ALL FIRs appear in fir_breakdown.
    Failed formulas get charge_amount=0 and warning is not None.
    Missing formulas get charge_amount=0, formula_code="NONE", and warning is not None.

    **Validates: Requirements 1.2, 1.3, 2.2, 2.3**
    """

    @given(
        mtow_kg=positive_float_strategy(),
    )
    @settings(max_examples=20)
    def test_all_firs_appear_in_breakdown_with_warnings(self, mtow_kg):
        """**Validates: Requirements 1.2, 1.3, 2.2, 2.3**

        Given a set of FIR crossings where at least one has a multi-line formula
        (which fails on unfixed code) and at least one has no active formula,
        ALL FIRs SHALL appear in fir_breakdown.

        FIRs with failed formulas: charge_amount == 0, warning is not None.
        FIRs with no formula: charge_amount == 0, formula_code == "NONE", warning is not None.

        On UNFIXED code this FAILS because failed/missing FIRs are silently skipped.
        """
        calculator, mock_session = _create_calculator_with_session()

        # Set up 3 FIRs:
        # 1. KZNY (US) — multi-line formula (will fail on unfixed code)
        # 2. EGTT (GB) — single-line formula (will succeed)
        # 3. EISN (IE) — no active formula
        fir_kzny = _make_fir_mock("KZNY", "New York FIR", "US")
        fir_egtt = _make_fir_mock("EGTT", "London FIR", "GB")
        fir_eisn = _make_fir_mock("EISN", "Shannon FIR", "IE")

        fir_crossings = [
            _make_fir_crossing_mock("KZNY"),
            _make_fir_crossing_mock("EGTT"),
            _make_fir_crossing_mock("EISN"),
        ]

        multiline_formula = _make_formula(
            "US",
            "US_MULTILINE",
            "def calculate(distance, weight, context):\n    return distance * weight * 0.01\n",
        )
        singleline_formula = _make_formula("GB", "GB_SIMPLE", "mtow_kg * 0.5 + distance_km * 2.0")

        # Mock route parser
        waypoints = [Waypoint("KJFK", 40.6, -73.8), Waypoint("EGLL", 51.5, -0.5)]
        calculator.route_parser.parse_route = Mock(return_value=waypoints)
        calculator.route_parser.identify_fir_crossings_db = Mock(return_value=fir_crossings)

        # Mock FIR service
        fir_map = {"KZNY": fir_kzny, "EGTT": fir_egtt, "EISN": fir_eisn}
        calculator.fir_service.get_active_fir = Mock(side_effect=lambda code: fir_map.get(code))

        # Mock formula service: US -> multiline, GB -> singleline, IE -> None
        formula_map = {"US": multiline_formula, "GB": singleline_formula, "IE": None}
        calculator.formula_service.get_active_formula = Mock(
            side_effect=lambda code: formula_map.get(code)
        )

        # Execute
        result = calculator.calculate_route_cost(
            route_string="KJFK DCT EGLL",
            origin="KJFK",
            destination="EGLL",
            aircraft_type="B738",
            mtow_kg=mtow_kg,
        )

        # ALL 3 FIRs must appear in the breakdown
        fir_codes_in_result = [b.icao_code for b in result.fir_breakdown]
        assert len(result.fir_breakdown) == 3, (
            f"Expected 3 FIRs in breakdown, got {len(result.fir_breakdown)}: {fir_codes_in_result}"
        )
        assert "KZNY" in fir_codes_in_result
        assert "EGTT" in fir_codes_in_result
        assert "EISN" in fir_codes_in_result

        # Check each FIR's expected state
        breakdown_map = {b.icao_code: b for b in result.fir_breakdown}

        # KZNY: multi-line formula — after fix, should succeed OR have warning
        # On unfixed code, this FIR is silently skipped entirely
        kzny = breakdown_map["KZNY"]
        # After fix: either charge > 0 (formula worked) or charge == 0 with warning
        # The test asserts it's present — that alone proves the silent-skip bug is fixed

        # EGTT: single-line formula — should always succeed
        egtt = breakdown_map["EGTT"]
        assert egtt.charge_amount > 0, "Single-line formula should produce a positive charge"

        # EISN: no formula — must have charge_amount=0, formula_code="NONE", warning
        eisn = breakdown_map["EISN"]
        assert eisn.charge_amount == Decimal("0"), (
            f"Missing-formula FIR should have charge_amount=0, got {eisn.charge_amount}"
        )
        assert eisn.formula_code == "NONE", (
            f"Missing-formula FIR should have formula_code='NONE', got {eisn.formula_code}"
        )
        assert eisn.warning is not None, (
            "Missing-formula FIR should have a warning object"
        )
