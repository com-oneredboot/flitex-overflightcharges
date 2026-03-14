"""Unit tests for CountryCodeMapper utility.

Tests the country_name → ISO 3166-1 alpha-2 mapping logic including
manual overrides, pycountry lookups, parenthetical extraction,
compound name splitting, and fallback behavior.

Requirements: 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.11
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from country_code_mapper import CountryCodeMapper


@pytest.fixture
def mapper():
    """Create a CountryCodeMapper instance."""
    return CountryCodeMapper()


class TestManualOverrides:
    """Tests for MANUAL_OVERRIDES dictionary edge cases."""

    def test_brunei_malaysia_compound(self, mapper):
        """Brunei / Malaysia → BN (Req 8.3)."""
        assert mapper.map("Brunei / Malaysia") == "BN"

    def test_french_guiana_parenthetical(self, mapper):
        """French Guiana (France) → FR (Req 8.4)."""
        assert mapper.map("French Guiana (France)") == "FR"

    def test_eur_region_code(self, mapper):
        """EUR → EU (EuroControl region pseudo-code) (Req 8.5)."""
        assert mapper.map("EUR") == "EU"

    def test_irkutsk_city_based(self, mapper):
        """IRKUTSK → RU (Russian city-based FIR) (Req 8.6)."""
        assert mapper.map("IRKUTSK") == "RU"

    def test_magadan_oceanic_east_city_based(self, mapper):
        """MAGADAN OCEANIC EAST → RU (Russian city-based FIR) (Req 8.6)."""
        assert mapper.map("MAGADAN OCEANIC EAST") == "RU"

    def test_cocesna_agency(self, mapper):
        """cocesna → HN (Central American agency → Honduras HQ) (Req 8.7)."""
        assert mapper.map("cocesna") == "HN"


class TestPycountryLookup:
    """Tests for pycountry-based name resolution."""

    def test_standard_country_name(self, mapper):
        assert mapper.map("United States") == "US"

    def test_standard_country_france(self, mapper):
        assert mapper.map("France") == "FR"

    def test_standard_country_germany(self, mapper):
        assert mapper.map("Germany") == "DE"

    def test_standard_country_japan(self, mapper):
        assert mapper.map("Japan") == "JP"

    def test_standard_country_brazil(self, mapper):
        assert mapper.map("Brazil") == "BR"


class TestParentheticalExtraction:
    """Tests for 'Territory (Parent)' pattern extraction (Req 8.4)."""

    def test_territory_with_parent(self, mapper):
        """Generic parenthetical pattern resolves to parent country."""
        result = mapper.map("Guadeloupe (France)")
        assert result == "FR"

    def test_territory_with_parent_whitespace(self, mapper):
        """Parenthetical with extra whitespace still works."""
        result = mapper.map("Some Territory (Germany) ")
        assert result == "DE"


class TestCompoundNames:
    """Tests for 'Country A / Country B' splitting (Req 8.3)."""

    def test_compound_maps_first_country(self, mapper):
        """Compound name maps to first listed country."""
        result = mapper.map("Australia / New Zealand")
        assert result == "AU"


class TestFallback:
    """Tests for unmappable names returning 'XX' (Req 8.11)."""

    def test_unmappable_name(self, mapper):
        assert mapper.map("XYZNOTACOUNTRY") == "XX"

    def test_empty_string(self, mapper):
        assert mapper.map("") == "XX"

    def test_whitespace_only(self, mapper):
        assert mapper.map("   ") == "XX"

    def test_none_like_empty(self, mapper):
        """None-like empty input returns fallback."""
        assert mapper.map("") == "XX"


class TestOutputFormat:
    """Tests that output is always exactly 2 uppercase alpha characters."""

    @pytest.mark.parametrize(
        "country_name",
        [
            "United States",
            "Brunei / Malaysia",
            "French Guiana (France)",
            "EUR",
            "IRKUTSK",
            "MAGADAN OCEANIC EAST",
            "cocesna",
            "XYZNOTACOUNTRY",
            "",
            "Japan",
        ],
    )
    def test_output_is_two_uppercase_alpha(self, mapper, country_name):
        result = mapper.map(country_name)
        assert len(result) == 2, f"Expected length 2, got {len(result)} for '{country_name}'"
        assert result.isalpha(), f"Expected alpha, got '{result}' for '{country_name}'"
        assert result.isupper(), f"Expected uppercase, got '{result}' for '{country_name}'"
