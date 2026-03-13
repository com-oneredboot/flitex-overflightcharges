"""
Unit Tests for ConstantsProvider

Tests the ConstantsProvider class that loads and provides constants
and utilities for formula execution context.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 6.5
"""

import math

import pytest

from src.formula_execution.constants_provider import ConstantsProvider


class TestConstantsProvider:
    """Test suite for ConstantsProvider class."""

    @pytest.fixture
    def provider(self) -> ConstantsProvider:
        """Create a ConstantsProvider instance for testing."""
        return ConstantsProvider()

    def test_initialization(self, provider: ConstantsProvider) -> None:
        """Test that ConstantsProvider initializes successfully."""
        assert provider is not None
        assert provider._currency_constants is not None
        assert provider._country_name_constants is not None
        assert provider._fir_names_per_country is not None
        assert provider._canada_tsc_aerodromes is not None
        assert provider._convert_nm_to_km is not None

    def test_get_execution_context_returns_dict(
        self, provider: ConstantsProvider
    ) -> None:
        """Test that get_execution_context returns a dictionary."""
        context = provider.get_execution_context()
        assert isinstance(context, dict)

    def test_execution_context_contains_math_functions(
        self, provider: ConstantsProvider
    ) -> None:
        """
        Test that execution context contains all required math functions.

        Requirements: 3.1
        """
        context = provider.get_execution_context()

        # Verify all math functions are present
        assert "sqrt" in context
        assert "pow" in context
        assert "abs" in context
        assert "ceil" in context
        assert "floor" in context
        assert "round" in context

        # Verify they are callable
        assert callable(context["sqrt"])
        assert callable(context["pow"])
        assert callable(context["abs"])
        assert callable(context["ceil"])
        assert callable(context["floor"])
        assert callable(context["round"])

    def test_math_functions_work_correctly(
        self, provider: ConstantsProvider
    ) -> None:
        """Test that math functions in context work correctly."""
        context = provider.get_execution_context()

        assert context["sqrt"](16) == 4.0
        assert context["pow"](2, 3) == 8
        assert context["abs"](-5) == 5
        assert context["ceil"](3.2) == 4
        assert context["floor"](3.8) == 3
        assert context["round"](3.6) == 4

    def test_execution_context_contains_currency_constants(
        self, provider: ConstantsProvider
    ) -> None:
        """
        Test that execution context contains currency constants.

        Requirements: 3.2
        """
        context = provider.get_execution_context()

        assert "CURRENCY_CONSTANTS" in context
        assert isinstance(context["CURRENCY_CONSTANTS"], dict)
        assert len(context["CURRENCY_CONSTANTS"]) > 0

        # Verify some common currencies
        assert "USD" in context["CURRENCY_CONSTANTS"]
        assert "EUR" in context["CURRENCY_CONSTANTS"]
        assert "CAD" in context["CURRENCY_CONSTANTS"]

    def test_execution_context_contains_country_name_constants(
        self, provider: ConstantsProvider
    ) -> None:
        """
        Test that execution context contains country name constants.

        Requirements: 3.3
        """
        context = provider.get_execution_context()

        assert "COUNTRY_NAME_CONSTANTS" in context
        assert isinstance(context["COUNTRY_NAME_CONSTANTS"], dict)
        assert len(context["COUNTRY_NAME_CONSTANTS"]) > 0

    def test_execution_context_contains_fir_names_per_country(
        self, provider: ConstantsProvider
    ) -> None:
        """
        Test that execution context contains FIR names per country.

        Requirements: 3.4
        """
        context = provider.get_execution_context()

        assert "FIR_NAMES_PER_COUNTRY" in context
        assert isinstance(context["FIR_NAMES_PER_COUNTRY"], dict)
        assert len(context["FIR_NAMES_PER_COUNTRY"]) > 0

    def test_execution_context_contains_canada_tsc_aerodromes(
        self, provider: ConstantsProvider
    ) -> None:
        """
        Test that execution context contains Canada TSC aerodromes.

        Requirements: 3.5
        """
        context = provider.get_execution_context()

        assert "CANADA_TSC_AERODROMES" in context
        assert isinstance(context["CANADA_TSC_AERODROMES"], list)
        assert len(context["CANADA_TSC_AERODROMES"]) > 0

    def test_execution_context_contains_convert_nm_to_km(
        self, provider: ConstantsProvider
    ) -> None:
        """
        Test that execution context contains convert_nm_to_km utility.

        Requirements: 3.6
        """
        context = provider.get_execution_context()

        assert "convert_nm_to_km" in context
        assert callable(context["convert_nm_to_km"])

    def test_convert_nm_to_km_works_correctly(
        self, provider: ConstantsProvider
    ) -> None:
        """Test that convert_nm_to_km function works correctly."""
        context = provider.get_execution_context()

        # Test conversion: 1 nautical mile = 1.852 kilometers
        assert context["convert_nm_to_km"](1) == pytest.approx(1.852)
        assert context["convert_nm_to_km"](100) == pytest.approx(185.2)
        assert context["convert_nm_to_km"](0) == 0

    def test_reload_constants(self, provider: ConstantsProvider) -> None:
        """
        Test that reload_constants method works without errors.

        Requirements: 6.5
        """
        # Get initial context
        context_before = provider.get_execution_context()

        # Reload constants
        provider.reload_constants()

        # Get context after reload
        context_after = provider.get_execution_context()

        # Verify context still has all required keys
        assert set(context_before.keys()) == set(context_after.keys())

    def test_execution_context_has_all_required_keys(
        self, provider: ConstantsProvider
    ) -> None:
        """Test that execution context has all required keys."""
        context = provider.get_execution_context()

        required_keys = {
            "sqrt",
            "pow",
            "abs",
            "ceil",
            "floor",
            "round",
            "CURRENCY_CONSTANTS",
            "COUNTRY_NAME_CONSTANTS",
            "FIR_NAMES_PER_COUNTRY",
            "CANADA_TSC_AERODROMES",
            "convert_nm_to_km",
        }

        assert set(context.keys()) == required_keys

    def test_multiple_calls_return_consistent_context(
        self, provider: ConstantsProvider
    ) -> None:
        """Test that multiple calls to get_execution_context return consistent data."""
        context1 = provider.get_execution_context()
        context2 = provider.get_execution_context()

        # Verify same keys
        assert set(context1.keys()) == set(context2.keys())

        # Verify same constant values
        assert context1["CURRENCY_CONSTANTS"] == context2["CURRENCY_CONSTANTS"]
        assert (
            context1["COUNTRY_NAME_CONSTANTS"]
            == context2["COUNTRY_NAME_CONSTANTS"]
        )
        assert (
            context1["FIR_NAMES_PER_COUNTRY"]
            == context2["FIR_NAMES_PER_COUNTRY"]
        )
        assert (
            context1["CANADA_TSC_AERODROMES"]
            == context2["CANADA_TSC_AERODROMES"]
        )
