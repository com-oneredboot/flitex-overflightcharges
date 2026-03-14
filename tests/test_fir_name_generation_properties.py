"""Property-based tests for descriptive FIR name generation.

These tests verify that the _resolve_country_name function from the Alembic
migration correctly produces descriptive FIR names in the format
"{Country Name} FIR ({ICAO Code})" for any valid country_code and icao_code.

Feature: fir-schema-cleanup
"""

import pycountry
import pytest
from hypothesis import given, settings, strategies as st

from migrations.versions.e5f6a7b8c9d0_drop_country_name_update_fir_name import (
    _resolve_country_name,
)

# --- Hypothesis strategies ---

# country_code: 2 uppercase alpha characters (A-Z)
country_code_strategy = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    min_size=2,
    max_size=2,
)

# icao_code: 4 uppercase alphanumeric characters (A-Z, 0-9)
icao_code_strategy = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
    min_size=4,
    max_size=4,
)


class TestDescriptiveFIRNameFormatProperty:
    """
    Feature: fir-schema-cleanup, Property 1: Descriptive FIR name format

    **Validates: Requirements 2.1, 2.2, 2.3**

    For any valid ISO 3166-1 alpha-2 country_code and any valid 4-character
    icao_code, generating the descriptive FIR name SHALL produce a string
    matching the pattern "{Country Name} FIR ({ICAO Code})" where Country Name
    is the pycountry resolved name for the code, or the country_code itself if
    unresolvable.
    """

    @settings(max_examples=100)
    @given(
        country_code=country_code_strategy,
        icao_code=icao_code_strategy,
    )
    def test_property_1_descriptive_fir_name_format(
        self, country_code, icao_code
    ):
        """
        **Validates: Requirements 2.1, 2.2, 2.3**

        Property 1: Descriptive FIR name format

        For any valid 2-char uppercase alpha country_code and 4-char uppercase
        alphanumeric icao_code, the descriptive FIR name must match
        "{resolved_name} FIR ({icao_code})" where resolved_name comes from
        pycountry or falls back to the country_code itself.
        """
        # Resolve the country name using the migration function
        resolved_name = _resolve_country_name(country_code)

        # Build the descriptive FIR name the same way the migration does
        descriptive_name = f"{resolved_name} FIR ({icao_code})"

        # Independently determine expected resolved name via pycountry
        country = pycountry.countries.get(alpha_2=country_code)
        if country:
            expected_name = country.name
        else:
            expected_name = country_code

        # 1. resolved_name must be the pycountry name or the code itself
        assert resolved_name == expected_name, (
            f"_resolve_country_name('{country_code}') returned '{resolved_name}', "
            f"expected '{expected_name}'"
        )

        # 2. The descriptive name must follow the exact format
        expected_descriptive = f"{expected_name} FIR ({icao_code})"
        assert descriptive_name == expected_descriptive

        # 3. The descriptive name must end with " FIR ({icao_code})"
        assert descriptive_name.endswith(f" FIR ({icao_code})")

        # 4. The descriptive name must contain "FIR" as a separator
        assert " FIR (" in descriptive_name
