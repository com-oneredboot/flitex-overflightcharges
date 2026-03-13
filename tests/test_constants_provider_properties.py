"""Property-based tests for ConstantsProvider.

These tests verify universal properties across many generated inputs using Hypothesis.
Each property test runs with a minimum of 100 iterations.

Feature: python-formula-execution-system
"""

import math
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from src.formula_execution.constants_provider import ConstantsProvider


class TestConstantsProviderProperties:
    """Property-based tests for ConstantsProvider execution context."""

    @pytest.fixture
    def provider(self) -> ConstantsProvider:
        """Create a ConstantsProvider instance for testing."""
        return ConstantsProvider()

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(iteration=st.integers(min_value=0, max_value=1000))
    def test_property_2_execution_context_completeness(
        self, provider: ConstantsProvider, iteration: int
    ) -> None:
        """
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.8, 10.3**

        Property 2: Execution Context Completeness

        For any formula execution, the execution context should contain all
        required elements: math functions (sqrt, pow, abs, ceil, floor, round),
        CURRENCY_CONSTANTS, COUNTRY_NAME_CONSTANTS, FIR_NAMES_PER_COUNTRY,
        CANADA_TSC_AERODROMES, convert_nm_to_km function, and eurocontrol_rates
        (for EuroControl formulas).

        Note: This test verifies the base execution context from ConstantsProvider.
        The eurocontrol_rates requirement (3.8, 10.3) will be validated when
        EuroControlRateLoader is integrated with the execution context.
        """
        # Get execution context
        context = provider.get_execution_context()

        # Verify context is a dictionary
        assert isinstance(
            context, dict
        ), "Execution context must be a dictionary"

        # Verify all required math functions are present (Requirement 3.1)
        required_math_functions = ["sqrt", "pow", "abs", "ceil", "floor", "round"]
        for func_name in required_math_functions:
            assert (
                func_name in context
            ), f"Math function '{func_name}' missing from execution context"
            assert callable(
                context[func_name]
            ), f"'{func_name}' must be callable"

        # Verify math functions are the correct functions
        assert context["sqrt"] == math.sqrt, "sqrt must be math.sqrt"
        assert context["pow"] == pow, "pow must be built-in pow"
        assert context["abs"] == abs, "abs must be built-in abs"
        assert context["ceil"] == math.ceil, "ceil must be math.ceil"
        assert context["floor"] == math.floor, "floor must be math.floor"
        assert context["round"] == round, "round must be built-in round"

        # Verify CURRENCY_CONSTANTS is present and is a dict (Requirement 3.2)
        assert (
            "CURRENCY_CONSTANTS" in context
        ), "CURRENCY_CONSTANTS missing from execution context"
        assert isinstance(
            context["CURRENCY_CONSTANTS"], dict
        ), "CURRENCY_CONSTANTS must be a dictionary"
        assert (
            len(context["CURRENCY_CONSTANTS"]) > 0
        ), "CURRENCY_CONSTANTS must not be empty"

        # Verify COUNTRY_NAME_CONSTANTS is present and is a dict (Requirement 3.3)
        assert (
            "COUNTRY_NAME_CONSTANTS" in context
        ), "COUNTRY_NAME_CONSTANTS missing from execution context"
        assert isinstance(
            context["COUNTRY_NAME_CONSTANTS"], dict
        ), "COUNTRY_NAME_CONSTANTS must be a dictionary"
        assert (
            len(context["COUNTRY_NAME_CONSTANTS"]) > 0
        ), "COUNTRY_NAME_CONSTANTS must not be empty"

        # Verify FIR_NAMES_PER_COUNTRY is present and is a dict (Requirement 3.4)
        assert (
            "FIR_NAMES_PER_COUNTRY" in context
        ), "FIR_NAMES_PER_COUNTRY missing from execution context"
        assert isinstance(
            context["FIR_NAMES_PER_COUNTRY"], dict
        ), "FIR_NAMES_PER_COUNTRY must be a dictionary"
        assert (
            len(context["FIR_NAMES_PER_COUNTRY"]) > 0
        ), "FIR_NAMES_PER_COUNTRY must not be empty"

        # Verify CANADA_TSC_AERODROMES is present and is a list (Requirement 3.5)
        assert (
            "CANADA_TSC_AERODROMES" in context
        ), "CANADA_TSC_AERODROMES missing from execution context"
        assert isinstance(
            context["CANADA_TSC_AERODROMES"], list
        ), "CANADA_TSC_AERODROMES must be a list"
        assert (
            len(context["CANADA_TSC_AERODROMES"]) > 0
        ), "CANADA_TSC_AERODROMES must not be empty"

        # Verify convert_nm_to_km is present and is callable (Requirement 3.6)
        assert (
            "convert_nm_to_km" in context
        ), "convert_nm_to_km missing from execution context"
        assert callable(
            context["convert_nm_to_km"]
        ), "convert_nm_to_km must be callable"

        # Verify convert_nm_to_km works correctly
        # Test with a known value: 1 nautical mile = 1.852 kilometers
        result = context["convert_nm_to_km"](1.0)
        assert isinstance(
            result, (int, float)
        ), "convert_nm_to_km must return a numeric value"
        assert (
            abs(result - 1.852) < 0.001
        ), "convert_nm_to_km(1.0) should return approximately 1.852"

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        call_count=st.integers(min_value=1, max_value=10),
        iteration=st.integers(min_value=0, max_value=1000),
    )
    def test_property_2_execution_context_consistency(
        self, provider: ConstantsProvider, call_count: int, iteration: int
    ) -> None:
        """
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

        Property 2: Execution Context Completeness (Consistency)

        For any number of calls to get_execution_context, the returned
        context should always contain the same keys and the same constant
        values. This ensures consistency across multiple formula executions.
        """
        # Get execution context multiple times
        contexts = [provider.get_execution_context() for _ in range(call_count)]

        # Verify all contexts have the same keys
        first_keys = set(contexts[0].keys())
        for i, context in enumerate(contexts[1:], start=1):
            assert set(context.keys()) == first_keys, (
                f"Context {i} has different keys than context 0. "
                f"Expected: {first_keys}, Got: {set(context.keys())}"
            )

        # Verify constant values are identical across all contexts
        for i in range(1, len(contexts)):
            assert (
                contexts[i]["CURRENCY_CONSTANTS"]
                == contexts[0]["CURRENCY_CONSTANTS"]
            ), f"CURRENCY_CONSTANTS differs between context 0 and context {i}"
            assert (
                contexts[i]["COUNTRY_NAME_CONSTANTS"]
                == contexts[0]["COUNTRY_NAME_CONSTANTS"]
            ), f"COUNTRY_NAME_CONSTANTS differs between context 0 and context {i}"
            assert (
                contexts[i]["FIR_NAMES_PER_COUNTRY"]
                == contexts[0]["FIR_NAMES_PER_COUNTRY"]
            ), f"FIR_NAMES_PER_COUNTRY differs between context 0 and context {i}"
            assert (
                contexts[i]["CANADA_TSC_AERODROMES"]
                == contexts[0]["CANADA_TSC_AERODROMES"]
            ), f"CANADA_TSC_AERODROMES differs between context 0 and context {i}"

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        test_value=st.floats(
            min_value=0.1,
            max_value=10000.0,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    def test_property_2_math_functions_work_correctly(
        self, provider: ConstantsProvider, test_value: float
    ) -> None:
        """
        **Validates: Requirements 3.1**

        Property 2: Execution Context Completeness (Math Functions)

        For any positive numeric value, the math functions in the execution
        context should work correctly and produce expected results.
        """
        context = provider.get_execution_context()

        # Test sqrt
        sqrt_result = context["sqrt"](test_value)
        assert isinstance(
            sqrt_result, float
        ), "sqrt should return a float"
        assert sqrt_result >= 0, "sqrt should return non-negative value"
        # Verify sqrt is correct: sqrt(x)^2 should equal x (within floating point precision)
        assert abs(sqrt_result * sqrt_result - test_value) < 0.001 * test_value

        # Test pow
        pow_result = context["pow"](test_value, 2)
        assert isinstance(
            pow_result, (int, float)
        ), "pow should return a numeric value"
        assert abs(pow_result - test_value * test_value) < 0.001 * abs(
            test_value * test_value
        )

        # Test abs
        abs_result = context["abs"](test_value)
        assert abs_result >= 0, "abs should return non-negative value"
        assert abs_result == test_value, "abs of positive value should equal itself"

        # Test abs with negative value
        abs_neg_result = context["abs"](-test_value)
        assert abs_neg_result >= 0, "abs should return non-negative value"
        assert abs_neg_result == test_value, "abs of negative value should be positive"

        # Test ceil
        ceil_result = context["ceil"](test_value)
        assert isinstance(ceil_result, int), "ceil should return an integer"
        assert ceil_result >= test_value, "ceil should round up"
        assert ceil_result - test_value < 1, "ceil should be at most 1 greater"

        # Test floor
        floor_result = context["floor"](test_value)
        assert isinstance(floor_result, int), "floor should return an integer"
        assert floor_result <= test_value, "floor should round down"
        assert test_value - floor_result < 1, "floor should be at most 1 less"

        # Test round
        round_result = context["round"](test_value)
        assert isinstance(round_result, int), "round should return an integer"
        assert abs(round_result - test_value) <= 0.5, "round should be within 0.5"

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        nautical_miles=st.floats(
            min_value=0.1,
            max_value=100000.0,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    def test_property_3_convert_nm_to_km_accuracy(
        self, provider: ConstantsProvider, nautical_miles: float
    ) -> None:
        """
        **Validates: Requirements 3.6**

        Property 3: Convert NM to KM Accuracy

        For any positive distance in nautical miles, converting to kilometers
        using convert_nm_to_km should return the distance multiplied by 1.852.
        """
        context = provider.get_execution_context()

        # Get the convert_nm_to_km function from context
        convert_nm_to_km = context["convert_nm_to_km"]

        # Convert nautical miles to kilometers
        result = convert_nm_to_km(nautical_miles)

        # Verify result is numeric
        assert isinstance(
            result, (int, float)
        ), "convert_nm_to_km must return a numeric value"

        # Verify the conversion is accurate: result should equal nautical_miles * 1.852
        expected = nautical_miles * 1.852
        
        # Use relative tolerance for floating point comparison
        # Allow 0.01% relative error to account for floating point precision
        relative_tolerance = 0.0001
        absolute_tolerance = abs(expected * relative_tolerance)
        
        assert abs(result - expected) <= absolute_tolerance, (
            f"convert_nm_to_km({nautical_miles}) returned {result}, "
            f"expected {expected} (difference: {abs(result - expected)})"
        )

        # Verify the result is positive for positive input
        assert result > 0, "convert_nm_to_km must return positive value for positive input"

        # Verify the conversion factor is exactly 1.852
        # by checking the ratio
        ratio = result / nautical_miles
        assert abs(ratio - 1.852) <= 1e-10, (
            f"Conversion factor should be 1.852, but got {ratio}"
        )
