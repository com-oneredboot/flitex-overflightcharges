"""
Country Code Mapper Utility

Maps country_name strings from the SQLite FIR source database to ISO 3166-1
alpha-2 country codes. The SQLite source has empty country_code for all 284 rows,
so mapping relies on country_name → ISO code with a curated dictionary for edge
cases (compound names, region codes, city-based FIR names).

Requirements: 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.11
"""

import logging
import re
from typing import Dict

import pycountry

logger = logging.getLogger(__name__)


class CountryCodeMapper:
    """Maps country_name strings from SQLite source to ISO 3166-1 alpha-2 codes.

    Strategy:
        1. Check MANUAL_OVERRIDES dictionary first
        2. Try pycountry lookup by name
        3. Handle parenthetical qualifiers: extract parent country from "Territory (Parent)"
        4. Handle compound names: split on " / " and map first country
        5. Fallback: return "XX" and log warning
    """

    MANUAL_OVERRIDES: Dict[str, str] = {
        "Brunei / Malaysia": "BN",
        "French Guiana (France)": "FR",
        "EUR": "EU",
        "IRKUTSK": "RU",
        "MAGADAN OCEANIC EAST": "RU",
        "cocesna": "HN",
        "UK": "GB",
    }

    def map(self, country_name: str) -> str:
        """Map a country_name string to an ISO 3166-1 alpha-2 code.

        Args:
            country_name: The country name string from the SQLite source.

        Returns:
            A 2-character uppercase alphabetic string. Returns "XX" if unmappable.
        """
        if not country_name or not country_name.strip():
            logger.warning("Empty country_name provided, using fallback 'XX'")
            return "XX"

        name = country_name.strip()

        # 1. Check manual overrides first
        if name in self.MANUAL_OVERRIDES:
            return self.MANUAL_OVERRIDES[name]

        # 2. Try pycountry lookup by name
        code = self._pycountry_lookup(name)
        if code:
            return code

        # 3. Handle parenthetical qualifiers: "Territory (Parent)" → lookup Parent
        parent = self._extract_parent_from_parenthetical(name)
        if parent:
            code = self._pycountry_lookup(parent)
            if code:
                return code

        # 4. Handle compound names: "Country A / Country B" → lookup first
        first_country = self._extract_first_from_compound(name)
        if first_country:
            code = self._pycountry_lookup(first_country)
            if code:
                return code

        # 5. Fallback
        logger.warning(
            "Could not map country_name '%s' to ISO code, using fallback 'XX'",
            country_name,
        )
        return "XX"

    def _pycountry_lookup(self, name: str) -> str | None:
        """Attempt to resolve a name to an alpha-2 code via pycountry.

        Tries exact lookup first, then fuzzy search.

        Returns:
            The 2-char uppercase alpha code, or None if not found.
        """
        try:
            country = pycountry.countries.lookup(name)
            return country.alpha_2
        except LookupError:
            pass

        try:
            results = pycountry.countries.search_fuzzy(name)
            if results:
                return results[0].alpha_2
        except LookupError:
            pass

        return None

    @staticmethod
    def _extract_parent_from_parenthetical(name: str) -> str | None:
        """Extract the parent country from 'Territory (Parent)' format.

        Returns:
            The parent country name, or None if pattern doesn't match.
        """
        match = re.match(r"^.+\(([^)]+)\)\s*$", name)
        if match:
            return match.group(1).strip()
        return None

    @staticmethod
    def _extract_first_from_compound(name: str) -> str | None:
        """Extract the first country from 'Country A / Country B' format.

        Returns:
            The first country name, or None if no ' / ' separator found.
        """
        if " / " in name:
            return name.split(" / ")[0].strip()
        return None
