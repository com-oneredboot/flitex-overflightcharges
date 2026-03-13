"""
Unit Tests for EuroControlRateLoader

Tests the EuroControlRateLoader class that loads and provides EuroControl
unit rates for formula execution.

Requirements: 10.1, 10.2
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.formula_execution.eurocontrol_loader import EuroControlRateLoader


class TestEuroControlRateLoader:
    """Test suite for EuroControlRateLoader class."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session for testing."""
        return MagicMock()

    @pytest.fixture
    def loader(self, mock_db_session):
        """Create an EuroControlRateLoader instance for testing."""
        return EuroControlRateLoader(mock_db_session)

    @pytest.fixture
    def sample_rate_rows(self):
        """Sample rate data from database."""
        return [
            (
                "GB",
                date(2024, 1, 1),
                date(2024, 12, 31),
                85.50,
                1.0,
                "EUR",
                "United Kingdom",
            ),
            (
                "GB",
                date(2025, 1, 1),
                date(2025, 12, 31),
                90.00,
                1.0,
                "EUR",
                "United Kingdom",
            ),
            (
                "FR",
                date(2024, 1, 1),
                date(2024, 12, 31),
                75.25,
                1.0,
                "EUR",
                "France",
            ),
            (
                "US",
                date(2024, 1, 1),
                date(2024, 12, 31),
                100.00,
                0.92,
                "USD",
                "United States",
            ),
        ]

    def test_initialization(self, loader, mock_db_session):
        """
        Test that EuroControlRateLoader initializes successfully.

        Requirements: 10.1
        """
        assert loader is not None
        assert loader._db_session == mock_db_session
        assert loader._rates == {}

    def test_load_rates_from_database(
        self, loader, mock_db_session, sample_rate_rows
    ):
        """
        Test that load_rates successfully loads rates from database.

        Requirements: 10.1
        """
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_rate_rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        rates = loader.load_rates()

        # Verify database was queried
        assert mock_db_session.execute.called

        # Verify rates were loaded
        assert rates is not None
        assert isinstance(rates, dict)
        assert len(rates) > 0

    def test_rate_dictionary_structure(
        self, loader, mock_db_session, sample_rate_rows
    ):
        """
        Test that rates are structured as nested dictionary.

        Requirements: 10.2
        """
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_rate_rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        rates = loader.load_rates()

        # Verify structure: country_code -> date_key -> rate_data
        assert "GB" in rates
        assert "FR" in rates
        assert "US" in rates

        # Verify GB has two rate periods
        assert len(rates["GB"]) == 2
        assert "2024-01-01" in rates["GB"]
        assert "2025-01-01" in rates["GB"]

        # Verify rate data structure
        gb_rate = rates["GB"]["2024-01-01"]
        assert "date_from" in gb_rate
        assert "date_to" in gb_rate
        assert "unit_rate" in gb_rate
        assert "ex_rate_to_eur" in gb_rate
        assert "currency" in gb_rate
        assert "country_name" in gb_rate

        # Verify data types
        assert isinstance(gb_rate["date_from"], date)
        assert isinstance(gb_rate["date_to"], date)
        assert isinstance(gb_rate["unit_rate"], float)
        assert isinstance(gb_rate["currency"], str)
        assert isinstance(gb_rate["country_name"], str)

    def test_rate_values_are_correct(
        self, loader, mock_db_session, sample_rate_rows
    ):
        """Test that rate values are correctly loaded and converted."""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_rate_rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        rates = loader.load_rates()

        # Verify GB 2024 rate
        gb_rate = rates["GB"]["2024-01-01"]
        assert gb_rate["unit_rate"] == 85.50
        assert gb_rate["ex_rate_to_eur"] == 1.0
        assert gb_rate["currency"] == "EUR"
        assert gb_rate["country_name"] == "United Kingdom"
        assert gb_rate["date_from"] == date(2024, 1, 1)
        assert gb_rate["date_to"] == date(2024, 12, 31)

        # Verify US rate with different currency
        us_rate = rates["US"]["2024-01-01"]
        assert us_rate["unit_rate"] == 100.00
        assert us_rate["ex_rate_to_eur"] == 0.92
        assert us_rate["currency"] == "USD"

    def test_get_rates_returns_loaded_rates(
        self, loader, mock_db_session, sample_rate_rows
    ):
        """
        Test that get_rates returns the loaded rates dictionary.

        Requirements: 10.2
        """
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_rate_rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        loader.load_rates()

        # Get rates
        rates = loader.get_rates()

        # Verify rates are returned
        assert rates is not None
        assert isinstance(rates, dict)
        assert "GB" in rates
        assert "FR" in rates

    def test_get_rates_returns_empty_dict_before_load(self, loader):
        """Test that get_rates returns empty dict if rates not loaded."""
        rates = loader.get_rates()
        assert rates == {}

    def test_reload_rates_functionality(
        self, loader, mock_db_session, sample_rate_rows
    ):
        """
        Test that reload_rates re-queries the database.

        Requirements: 10.2
        """
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_rate_rows
        mock_db_session.execute.return_value = mock_result

        # Initial load
        loader.load_rates()
        initial_call_count = mock_db_session.execute.call_count

        # Reload rates
        loader.reload_rates()

        # Verify database was queried again
        assert mock_db_session.execute.call_count == initial_call_count + 1

    def test_load_rates_handles_null_exchange_rate(
        self, loader, mock_db_session
    ):
        """Test that load_rates handles null exchange rates correctly."""
        # Sample data with null exchange rate
        rows_with_null = [
            (
                "GB",
                date(2024, 1, 1),
                date(2024, 12, 31),
                85.50,
                None,  # Null exchange rate
                None,  # Null currency
                "United Kingdom",
            ),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows_with_null
        mock_db_session.execute.return_value = mock_result

        # Load rates
        rates = loader.load_rates()

        # Verify null values are handled
        gb_rate = rates["GB"]["2024-01-01"]
        assert gb_rate["ex_rate_to_eur"] is None
        assert gb_rate["currency"] is None

    def test_load_rates_handles_database_error(
        self, loader, mock_db_session
    ):
        """Test that load_rates handles database errors gracefully."""
        # Mock database error
        mock_db_session.execute.side_effect = Exception("Database error")

        # Load rates should not raise exception
        rates = loader.load_rates()

        # Verify empty dict is returned on error
        assert rates == {}
        assert loader.get_rates() == {}

    def test_load_rates_handles_empty_result(self, loader, mock_db_session):
        """Test that load_rates handles empty database result."""
        # Mock empty result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute.return_value = mock_result

        # Load rates
        rates = loader.load_rates()

        # Verify empty dict is returned
        assert rates == {}

    def test_multiple_rate_periods_per_country(
        self, loader, mock_db_session
    ):
        """Test that multiple rate periods per country are handled correctly."""
        # Sample data with multiple periods for same country
        rows = [
            (
                "GB",
                date(2023, 1, 1),
                date(2023, 12, 31),
                80.00,
                1.0,
                "EUR",
                "United Kingdom",
            ),
            (
                "GB",
                date(2024, 1, 1),
                date(2024, 12, 31),
                85.50,
                1.0,
                "EUR",
                "United Kingdom",
            ),
            (
                "GB",
                date(2025, 1, 1),
                date(2025, 12, 31),
                90.00,
                1.0,
                "EUR",
                "United Kingdom",
            ),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        rates = loader.load_rates()

        # Verify all periods are loaded
        assert len(rates["GB"]) == 3
        assert "2023-01-01" in rates["GB"]
        assert "2024-01-01" in rates["GB"]
        assert "2025-01-01" in rates["GB"]

        # Verify rates are different
        assert rates["GB"]["2023-01-01"]["unit_rate"] == 80.00
        assert rates["GB"]["2024-01-01"]["unit_rate"] == 85.50
        assert rates["GB"]["2025-01-01"]["unit_rate"] == 90.00

    def test_get_rate_for_date_finds_correct_rate(
        self, loader, mock_db_session, sample_rate_rows
    ):
        """Test that get_rate_for_date finds the correct rate for a date."""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_rate_rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        loader.load_rates()

        # Test finding rate for date within period
        rate = loader.get_rate_for_date("GB", date(2024, 6, 15))
        assert rate is not None
        assert rate["unit_rate"] == 85.50
        assert rate["date_from"] == date(2024, 1, 1)
        assert rate["date_to"] == date(2024, 12, 31)

    def test_get_rate_for_date_returns_none_for_unknown_country(
        self, loader, mock_db_session, sample_rate_rows
    ):
        """Test that get_rate_for_date returns None for unknown country."""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_rate_rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        loader.load_rates()

        # Test unknown country
        rate = loader.get_rate_for_date("XX", date(2024, 6, 15))
        assert rate is None

    def test_get_rate_for_date_returns_none_for_date_outside_range(
        self, loader, mock_db_session, sample_rate_rows
    ):
        """Test that get_rate_for_date returns None for date outside range."""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_rate_rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        loader.load_rates()

        # Test date outside all ranges
        rate = loader.get_rate_for_date("GB", date(2026, 6, 15))
        assert rate is None

    def test_get_rate_for_date_handles_boundary_dates(
        self, loader, mock_db_session, sample_rate_rows
    ):
        """Test that get_rate_for_date handles boundary dates correctly."""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_rate_rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        loader.load_rates()

        # Test start date
        rate = loader.get_rate_for_date("GB", date(2024, 1, 1))
        assert rate is not None
        assert rate["unit_rate"] == 85.50

        # Test end date
        rate = loader.get_rate_for_date("GB", date(2024, 12, 31))
        assert rate is not None
        assert rate["unit_rate"] == 85.50

    @patch("src.formula_execution.eurocontrol_loader.logger")
    def test_load_rates_logs_success(
        self, mock_logger, loader, mock_db_session, sample_rate_rows
    ):
        """Test that load_rates logs success message."""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_rate_rows
        mock_db_session.execute.return_value = mock_result

        # Load rates
        loader.load_rates()

        # Verify info log was called
        assert mock_logger.info.called

    @patch("src.formula_execution.eurocontrol_loader.logger")
    def test_load_rates_logs_error_on_failure(
        self, mock_logger, loader, mock_db_session
    ):
        """Test that load_rates logs error on database failure."""
        # Mock database error
        mock_db_session.execute.side_effect = Exception("Database error")

        # Load rates
        loader.load_rates()

        # Verify error log was called
        assert mock_logger.error.called

    @patch("src.formula_execution.eurocontrol_loader.logger")
    def test_reload_rates_logs_reload_message(
        self, mock_logger, loader, mock_db_session, sample_rate_rows
    ):
        """Test that reload_rates logs reload message."""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_rate_rows
        mock_db_session.execute.return_value = mock_result

        # Reload rates
        loader.reload_rates()

        # Verify info log was called with reload message
        assert mock_logger.info.called
