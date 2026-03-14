"""Property-based tests for CountryCodeMapper.

Feature: fir-versioning-and-data-import, Property 11: Country code mapper produces valid codes

These tests verify that the CountryCodeMapper always produces valid ISO 3166-1
alpha-2 codes (exactly 2 uppercase alphabetic characters) for any input string.

Requirements: 8.2, 8.11
"""

import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

# Add scripts directory to path so we can import the mapper
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from country_code_mapper import CountryCodeMapper


@pytest.fixture
def mapper():
    """Create a CountryCodeMapper instance."""
    return CountryCodeMapper()


# Strategy: generate a wide variety of strings including empty, whitespace,
# unicode, long strings, and typical country-name-like text.
random_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),  # exclude surrogates
    ),
    min_size=0,
    max_size=200,
)


class TestCountryCodeMapperProperties:
    """Property 11: Country code mapper produces valid codes.

    Feature: fir-versioning-and-data-import, Property 11: Country code mapper produces valid codes

    **Validates: Requirements 8.2, 8.11**

    For any country_name string, the CountryCodeMapper.map() method SHALL return
    a string of exactly 2 uppercase alphabetic characters. If the country_name
    is unmappable, the result SHALL be "XX".
    """

    @given(country_name=random_text)
    @settings(max_examples=100)
    def test_property_11_country_code_mapper_produces_valid_codes(self, country_name):
        """
        **Validates: Requirements 8.2, 8.11**

        Property 11: Country code mapper produces valid codes

        Generate random strings, verify output is always exactly 2 uppercase
        alpha characters or "XX".
        """
        mapper = CountryCodeMapper()
        result = mapper.map(country_name)

        # Output must be exactly 2 characters
        assert len(result) == 2, (
            f"Expected length 2, got {len(result)} for input '{country_name!r}': '{result}'"
        )

        # Output must be all alphabetic
        assert result.isalpha(), (
            f"Expected all alpha, got '{result}' for input '{country_name!r}'"
        )

        # Output must be all uppercase
        assert result.isupper(), (
            f"Expected all uppercase, got '{result}' for input '{country_name!r}'"
        )
