"""Property-based tests for EuroControlRateLoader.

These tests verify universal properties across many generated inputs using Hypothesis.
Each property test runs with a minimum of 100 iterations.

Feature: python-formula-execution-system
"""

from datetime import date, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from src.formula_execution.eurocontrol_loader import EuroControlRateLoader


# Strategy for generating valid country codes (2-letter ISO codes)
country_code_strategy = st.text(
    alphabet=st.characters(min_codepoint=65, max_codepoint=90),  # A-Z
    min_size=2,
    max_size=2,
)

# Strategy for generating valid dates
date_strategy = st.dates(
    min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)
)

# Strategy for generating valid unit rates
unit_rate_strategy = st.floats(
    min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False
)

# Strategy for generating valid exchange rates
exchange_rate_strategy = st.one_of(
    st.none(),
    st.floats(
        min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False
    ),
)

# Strategy for generating currency codes
currency_strategy = st.one_of(
    st.none(),
    st.sampled_from(["EUR", "USD", "GBP", "CAD", "JPY", "CHF"]),
)

# Strategy for generating country names
country_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs")
    ),
    min_size=3,
    max_size=50,
)


def generate_rate_row(
    country_code: str,
    date_from: date,
    date_to: date,
    unit_rate: float,
    ex_rate_to_eur: float | None,
    currency: str | None,
    country_name: str,
) -> tuple:
    """Generate a database row tuple for EuroControl rates."""
    return (
        country_code,
        date_from,
        date_to,
        unit_rate,
        ex_rate_to_eur,
        currency,
        country_name,
    )


@st.composite
def rate_row_strategy(draw):
    """Strategy for generating valid rate rows."""
    country_code = draw(country_code_strategy)
    date_from = draw(date_strategy)
    # Ensure date_to is after date_from
    days_duration = draw(st.integers(min_value=1, max_value=365))
    date_to = date_from + timedelta(days=days_duration)
    unit_rate = draw(unit_rate_strategy)
    ex_rate_to_eur = draw(exchange_rate_strategy)
    currency = draw(currency_strategy)
    country_name = draw(country_name_strategy)

    return generate_rate_row(
        country_code,
        date_from,
        date_to,
        unit_rate,
        ex_rate_to_eur,
        currency,
        country_name,
    )


class TestEuroControlRateLoaderProperties:
    """Property-based tests for EuroControlRateLoader rates structure."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session for testing."""
        return MagicMock()

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(rate_rows=st.lists(rate_row_strategy(), min_size=1, max_size=50))
    def test_property_13_eurocontrol_rates_structure(
        self, mock_db_session: MagicMock, rate_rows: list[tuple]
    ) -> None:
        """
        **Validates: Requirements 10.2**

        Property 13: EuroControl Rates Structure

        For any loaded EuroControl rates, the data structure should be a
        dictionary indexed by relevant keys (country, FIR, or date) allowing
        O(1) lookup.

        This test verifies:
        1. The rates structure is a dictionary (O(1) lookup at top level)
        2. Country codes are used as keys for O(1) country lookup
        3. Date keys are used within each country for O(1) date range lookup
        4. All rate entries have the required fields
        5. The structure supports efficient lookups without iteration
        """
        # Create loader instance
        loader = EuroControlRateLoader(mock_db_session)

        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rate_rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        rates = loader.load_rates()

        # Property 1: Rates structure must be a dictionary for O(1) lookup
        assert isinstance(
            rates, dict
        ), "Rates must be a dictionary for O(1) lookup"

        # Property 2: All country codes from input should be present as keys
        country_codes_in_input = {row[0] for row in rate_rows}
        for country_code in country_codes_in_input:
            assert (
                country_code in rates
            ), f"Country code '{country_code}' must be a key in rates dictionary"

        # Property 3: Each country's rates must be a dictionary for O(1) date lookup
        for country_code, country_rates in rates.items():
            assert isinstance(
                country_rates, dict
            ), f"Rates for country '{country_code}' must be a dictionary for O(1) lookup"

            # Property 4: Date keys must be strings in ISO format for consistent lookup
            for date_key in country_rates.keys():
                assert isinstance(
                    date_key, str
                ), f"Date key '{date_key}' must be a string"
                # Verify it's a valid ISO date format (YYYY-MM-DD)
                try:
                    date.fromisoformat(date_key)
                except ValueError:
                    pytest.fail(
                        f"Date key '{date_key}' is not in valid ISO format (YYYY-MM-DD)"
                    )

        # Property 5: All rate entries must have required fields for complete data access
        required_fields = [
            "date_from",
            "date_to",
            "unit_rate",
            "ex_rate_to_eur",
            "currency",
            "country_name",
        ]

        for country_code, country_rates in rates.items():
            for date_key, rate_data in country_rates.items():
                assert isinstance(
                    rate_data, dict
                ), f"Rate data for {country_code}[{date_key}] must be a dictionary"

                for field in required_fields:
                    assert (
                        field in rate_data
                    ), f"Rate data for {country_code}[{date_key}] missing required field '{field}'"

        # Property 6: Verify O(1) lookup capability by testing direct access
        # For any country code in the input, we should be able to access it directly
        for row in rate_rows:
            country_code = row[0]
            date_from = row[1]
            date_key = (
                date_from.isoformat()
                if isinstance(date_from, date)
                else str(date_from)
            )

            # This should be O(1) - direct dictionary access without iteration
            assert country_code in rates, f"Country '{country_code}' not found"
            assert (
                date_key in rates[country_code]
            ), f"Date key '{date_key}' not found for country '{country_code}'"

            # Verify we can access the rate data directly
            rate_data = rates[country_code][date_key]
            assert isinstance(rate_data, dict), "Rate data must be a dictionary"

        # Property 7: Verify data integrity - values match input
        # Note: When there are duplicate (country_code, date_from) pairs,
        # the loader overwrites with the last occurrence (correct behavior)
        # So we need to track the last occurrence of each (country_code, date_from) pair
        last_occurrence: dict[tuple[str, str], tuple] = {}
        for row in rate_rows:
            country_code = row[0]
            date_from = row[1]
            date_key = (
                date_from.isoformat()
                if isinstance(date_from, date)
                else str(date_from)
            )
            key = (country_code, date_key)
            last_occurrence[key] = row

        # Now verify that the loaded data matches the last occurrence of each key
        for (country_code, date_key), row in last_occurrence.items():
            date_from = row[1]
            date_to = row[2]
            unit_rate = row[3]
            ex_rate_to_eur = row[4]
            currency = row[5]
            country_name = row[6]

            rate_data = rates[country_code][date_key]

            # Verify all fields are correctly stored
            assert (
                rate_data["date_from"] == date_from
            ), f"date_from mismatch for {country_code}[{date_key}]"
            assert (
                rate_data["date_to"] == date_to
            ), f"date_to mismatch for {country_code}[{date_key}]"
            assert (
                rate_data["unit_rate"] == float(unit_rate)
            ), f"unit_rate mismatch for {country_code}[{date_key}]"
            assert rate_data["ex_rate_to_eur"] == (
                float(ex_rate_to_eur) if ex_rate_to_eur is not None else None
            ), f"ex_rate_to_eur mismatch for {country_code}[{date_key}]"
            assert (
                rate_data["currency"] == currency
            ), f"currency mismatch for {country_code}[{date_key}]"
            assert (
                rate_data["country_name"] == country_name
            ), f"country_name mismatch for {country_code}[{date_key}]"

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        rate_rows=st.lists(rate_row_strategy(), min_size=1, max_size=50),
        lookup_attempts=st.integers(min_value=1, max_value=10),
    )
    def test_property_13_o1_lookup_performance(
        self,
        mock_db_session: MagicMock,
        rate_rows: list[tuple],
        lookup_attempts: int,
    ) -> None:
        """
        **Validates: Requirements 10.2**

        Property 13: EuroControl Rates Structure (O(1) Lookup Performance)

        For any loaded EuroControl rates, lookups by country code and date
        should be O(1) operations (direct dictionary access without iteration).

        This test verifies that the structure supports constant-time lookups
        regardless of the number of countries or rate periods.
        """
        # Create loader instance
        loader = EuroControlRateLoader(mock_db_session)

        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rate_rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        rates = loader.load_rates()

        # Verify we can perform O(1) lookups for any rate in the input
        for _ in range(lookup_attempts):
            # Pick a random row from the input
            import random

            row = random.choice(rate_rows)
            country_code = row[0]
            date_from = row[1]
            date_key = (
                date_from.isoformat()
                if isinstance(date_from, date)
                else str(date_from)
            )

            # Perform O(1) lookup - direct dictionary access
            # This should not require iteration over all countries or dates
            assert country_code in rates, f"Country '{country_code}' not found"
            assert (
                date_key in rates[country_code]
            ), f"Date '{date_key}' not found for country '{country_code}'"

            # Access the rate data directly
            rate_data = rates[country_code][date_key]

            # Verify the data is accessible
            assert isinstance(rate_data, dict), "Rate data must be a dictionary"
            assert "unit_rate" in rate_data, "Rate data must contain unit_rate"

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(rate_rows=st.lists(rate_row_strategy(), min_size=1, max_size=50))
    def test_property_13_multiple_periods_per_country(
        self, mock_db_session: MagicMock, rate_rows: list[tuple]
    ) -> None:
        """
        **Validates: Requirements 10.2**

        Property 13: EuroControl Rates Structure (Multiple Periods)

        For any country with multiple rate periods, each period should be
        accessible via its date key, allowing O(1) lookup of any specific
        rate period.

        This test verifies that the structure correctly handles multiple
        rate periods for the same country without conflicts.
        """
        # Create loader instance
        loader = EuroControlRateLoader(mock_db_session)

        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rate_rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        rates = loader.load_rates()

        # Group input rows by country and track unique date keys
        # Note: When there are duplicate (country_code, date_from) pairs,
        # the loader overwrites with the last occurrence
        country_unique_periods: dict[str, dict[str, tuple]] = {}
        for row in rate_rows:
            country_code = row[0]
            date_from = row[1]
            date_key = (
                date_from.isoformat()
                if isinstance(date_from, date)
                else str(date_from)
            )
            
            if country_code not in country_unique_periods:
                country_unique_periods[country_code] = {}
            
            # Store the last occurrence for each date key
            country_unique_periods[country_code][date_key] = row

        # For each country, verify all unique periods are accessible
        for country_code, unique_periods in country_unique_periods.items():
            assert (
                country_code in rates
            ), f"Country '{country_code}' not found in rates"

            # Verify the number of unique periods matches
            assert len(rates[country_code]) == len(
                unique_periods
            ), f"Country '{country_code}' should have {len(unique_periods)} unique periods, but has {len(rates[country_code])}"

            # Verify each unique period is accessible by its date key
            for date_key, row in unique_periods.items():
                assert (
                    date_key in rates[country_code]
                ), f"Date key '{date_key}' not found for country '{country_code}'"

                # Verify the rate data matches the last occurrence
                rate_data = rates[country_code][date_key]
                assert (
                    rate_data["unit_rate"] == float(row[3])
                ), f"Unit rate mismatch for {country_code}[{date_key}]"

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(rate_rows=st.lists(rate_row_strategy(), min_size=0, max_size=50))
    def test_property_13_empty_and_non_empty_rates(
        self, mock_db_session: MagicMock, rate_rows: list[tuple]
    ) -> None:
        """
        **Validates: Requirements 10.2**

        Property 13: EuroControl Rates Structure (Empty Handling)

        For any loaded EuroControl rates (including empty results), the
        structure should always be a dictionary, maintaining the O(1)
        lookup property even when empty.
        """
        # Create loader instance
        loader = EuroControlRateLoader(mock_db_session)

        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rate_rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        rates = loader.load_rates()

        # Property: Rates must always be a dictionary
        assert isinstance(
            rates, dict
        ), "Rates must be a dictionary even when empty"

        # If input is empty, rates should be empty
        if len(rate_rows) == 0:
            assert len(rates) == 0, "Rates should be empty when input is empty"
        else:
            # If input is non-empty, rates should contain data
            assert len(rates) > 0, "Rates should contain data when input is non-empty"

            # Verify all countries are present
            country_codes = {row[0] for row in rate_rows}
            for country_code in country_codes:
                assert (
                    country_code in rates
                ), f"Country '{country_code}' should be in rates"
