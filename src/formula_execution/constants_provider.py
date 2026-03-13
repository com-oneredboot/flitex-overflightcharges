"""
Constants Provider

Loads and provides constants and utilities for formula execution context.
This component is responsible for building the execution context dictionary
that formulas use during execution.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 6.5
"""

import math
from typing import Any

from src.constants import (
    CANADA_TSC_AERODROMES,
    COUNTRY_NAME_CONSTANTS,
    CURRENCY_CONSTANTS,
    FIR_NAMES_PER_COUNTRY,
    convert_nm_to_km,
)


class ConstantsProvider:
    """
    Provides constants and utilities for formula execution context.

    This class loads currency, country, FIR, and aerodrome constants at
    initialization and provides them in an execution context dictionary.
    It also includes math functions and utility functions needed by formulas.

    Attributes:
        _currency_constants: Dictionary of ISO 4217 currency codes
        _country_name_constants: Dictionary of country names
        _fir_names_per_country: Dictionary of FIR names per country
        _canada_tsc_aerodromes: List of Canada TSC aerodromes
        _convert_nm_to_km: Function to convert nautical miles to kilometers
    """

    def __init__(self) -> None:
        """
        Initialize and load all constants.

        Loads currency, country, FIR, and aerodrome constants from the
        constants package. These are loaded once at initialization and
        reused for all formula executions.

        Requirements: 6.5
        """
        self._currency_constants = CURRENCY_CONSTANTS
        self._country_name_constants = COUNTRY_NAME_CONSTANTS
        self._fir_names_per_country = FIR_NAMES_PER_COUNTRY
        self._canada_tsc_aerodromes = CANADA_TSC_AERODROMES
        self._convert_nm_to_km = convert_nm_to_km

    def get_execution_context(self) -> dict[str, Any]:
        """
        Build execution context dictionary for formulas.

        Returns a dictionary containing all constants, utilities, and math
        functions that formulas need during execution. This context is
        provided as the global namespace for formula execution.

        Returns:
            Dictionary containing:
            - Math functions: sqrt, pow, abs, ceil, floor, round
            - CURRENCY_CONSTANTS: dict of ISO 4217 currency codes
            - COUNTRY_NAME_CONSTANTS: dict of country names
            - FIR_NAMES_PER_COUNTRY: dict of FIR names per country
            - CANADA_TSC_AERODROMES: list of Canada TSC aerodromes
            - convert_nm_to_km: function to convert nautical miles to km

        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6

        Example:
            >>> provider = ConstantsProvider()
            >>> context = provider.get_execution_context()
            >>> context['sqrt'](16)
            4.0
            >>> context['convert_nm_to_km'](100)
            185.2
        """
        return {
            # Math functions (Requirement 3.1)
            "sqrt": math.sqrt,
            "pow": pow,
            "abs": abs,
            "ceil": math.ceil,
            "floor": math.floor,
            "round": round,
            # Currency constants (Requirement 3.2)
            "CURRENCY_CONSTANTS": self._currency_constants,
            # Country name constants (Requirement 3.3)
            "COUNTRY_NAME_CONSTANTS": self._country_name_constants,
            # FIR names per country (Requirement 3.4)
            "FIR_NAMES_PER_COUNTRY": self._fir_names_per_country,
            # Canada TSC aerodromes (Requirement 3.5)
            "CANADA_TSC_AERODROMES": self._canada_tsc_aerodromes,
            # Utility function (Requirement 3.6)
            "convert_nm_to_km": self._convert_nm_to_km,
        }

    def reload_constants(self) -> None:
        """
        Reload all constants from the constants package.

        This method allows runtime updates of constants by re-importing
        them from the constants package. Useful for hot-reloading constants
        without restarting the application.

        Note: This requires the constants modules to be reloaded first,
        which is typically done at the application level.

        Requirements: 6.5
        """
        # Re-import constants to get latest values
        from src.constants import (
            CANADA_TSC_AERODROMES,
            COUNTRY_NAME_CONSTANTS,
            CURRENCY_CONSTANTS,
            FIR_NAMES_PER_COUNTRY,
            convert_nm_to_km,
        )

        self._currency_constants = CURRENCY_CONSTANTS
        self._country_name_constants = COUNTRY_NAME_CONSTANTS
        self._fir_names_per_country = FIR_NAMES_PER_COUNTRY
        self._canada_tsc_aerodromes = CANADA_TSC_AERODROMES
        self._convert_nm_to_km = convert_nm_to_km
