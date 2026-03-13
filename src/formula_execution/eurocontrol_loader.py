"""
EuroControl Rate Loader

Pre-fetches EuroControl unit rates from PostgreSQL at application startup
to avoid repeated database queries during formula execution.

Requirements: 10.1, 10.2, 10.3, 10.4, 5.6
"""

import logging
from datetime import date
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class EuroControlRateLoader:
    """
    Loads and provides EuroControl unit rates for formula execution.

    This class pre-fetches EuroControl unit rates from the PostgreSQL database
    at application startup and structures them as a dictionary for O(1) lookup
    during formula execution. The rates are indexed by country code, date range,
    and include unit rates, exchange rates, and currency information.

    Attributes:
        _db_session: SQLAlchemy database session for querying rates
        _rates: Dictionary of rates indexed by country_code and date range
    """

    def __init__(self, db_session: Session) -> None:
        """
        Initialize loader with database session.

        Args:
            db_session: SQLAlchemy session for database queries

        Requirements: 10.1
        """
        self._db_session = db_session
        self._rates: dict[str, Any] = {}

    def load_rates(self) -> dict[str, Any]:
        """
        Load EuroControl rates from database.

        Queries the eurocontrol_unit_rates table and structures the data
        as a nested dictionary for efficient lookup. The structure is:
        {
            "country_code": {
                "date_from_YYYY-MM-DD": {
                    "date_from": date,
                    "date_to": date,
                    "unit_rate": float,
                    "ex_rate_to_eur": float | None,
                    "currency": str | None,
                    "country_name": str
                }
            }
        }

        Returns:
            Dictionary indexed by country code and date range containing
            unit rates, exchange rates, currency, and country names

        Requirements: 10.1, 10.2

        Example:
            >>> loader = EuroControlRateLoader(db_session)
            >>> rates = loader.load_rates()
            >>> rates["GB"]["2024-01-01"]["unit_rate"]
            85.50
        """
        try:
            # Query all rates from the database
            query = text("""
                SELECT 
                    country_code,
                    date_from,
                    date_to,
                    unit_rate,
                    ex_rate_to_eur,
                    currency,
                    country_name
                FROM eurocontrol_unit_rates
                ORDER BY country_code, date_from
            """)

            result = self._db_session.execute(query)
            rows = result.fetchall()

            # Structure rates as nested dictionary
            rates: dict[str, dict[str, dict[str, Any]]] = {}

            for row in rows:
                country_code = row[0]
                date_from = row[1]
                date_to = row[2]
                unit_rate = row[3]
                ex_rate_to_eur = row[4]
                currency = row[5]
                country_name = row[6]

                # Initialize country dict if not exists
                if country_code not in rates:
                    rates[country_code] = {}

                # Use date_from as key for the rate period
                date_key = (
                    date_from.isoformat()
                    if isinstance(date_from, date)
                    else str(date_from)
                )

                rates[country_code][date_key] = {
                    "date_from": date_from,
                    "date_to": date_to,
                    "unit_rate": float(unit_rate),
                    "ex_rate_to_eur": (
                        float(ex_rate_to_eur) if ex_rate_to_eur is not None else None
                    ),
                    "currency": currency,
                    "country_name": country_name,
                }

            self._rates = rates
            logger.info(
                f"Loaded EuroControl rates for {len(rates)} countries "
                f"with {sum(len(v) for v in rates.values())} total rate periods"
            )

            return self._rates

        except Exception as e:
            logger.error(f"Failed to load EuroControl rates: {e}")
            # Return empty dict on error to allow application to continue
            self._rates = {}
            return self._rates

    def get_rates(self) -> dict[str, Any]:
        """
        Return loaded rates dictionary.

        Returns the rates dictionary that was loaded by load_rates().
        If rates haven't been loaded yet, returns an empty dictionary.

        Returns:
            Dictionary of EuroControl rates indexed by country and date

        Requirements: 10.3

        Example:
            >>> loader = EuroControlRateLoader(db_session)
            >>> loader.load_rates()
            >>> rates = loader.get_rates()
            >>> "GB" in rates
            True
        """
        return self._rates

    def reload_rates(self) -> None:
        """
        Reload rates from database.

        Re-queries the database to refresh the rates dictionary. This is
        useful for runtime updates when rates are modified in the database
        without restarting the application.

        Requirements: 10.4

        Example:
            >>> loader = EuroControlRateLoader(db_session)
            >>> loader.load_rates()
            >>> # ... rates updated in database ...
            >>> loader.reload_rates()
        """
        logger.info("Reloading EuroControl rates from database")
        self.load_rates()

    def get_rate_for_date(
        self, country_code: str, target_date: date
    ) -> Optional[dict[str, Any]]:
        """
        Get the applicable rate for a specific country and date.

        Searches for the rate period that contains the target date by
        checking if target_date falls between date_from and date_to.

        Args:
            country_code: ISO country code (e.g., "GB", "FR")
            target_date: Date to find the applicable rate for

        Returns:
            Rate dictionary if found, None otherwise

        Example:
            >>> loader = EuroControlRateLoader(db_session)
            >>> loader.load_rates()
            >>> rate = loader.get_rate_for_date("GB", date(2024, 1, 15))
            >>> rate["unit_rate"]
            85.50
        """
        if country_code not in self._rates:
            return None

        # Find the rate period that contains the target date
        for date_key, rate_data in self._rates[country_code].items():
            date_from = rate_data["date_from"]
            date_to = rate_data["date_to"]

            if date_from <= target_date <= date_to:
                return rate_data

        return None
