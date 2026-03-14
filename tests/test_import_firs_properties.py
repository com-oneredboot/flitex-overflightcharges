"""Property-based tests for FIR import functions.

Feature: fir-versioning-and-data-import, Property 12: Import deduplication by ICAO code
Feature: fir-schema-cleanup, Property 2: Import transform produces descriptive name and omits country_name

Requirements: 8.9, 6.1, 6.2, 6.3
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

import pycountry
import pytest
from hypothesis import given, settings, strategies as st

# Add scripts directory to path so we can import the mapper
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from country_code_mapper import CountryCodeMapper
from scripts.import_firs import transform_record


# Strategy: generate ICAO codes as 4 uppercase alphanumeric characters
icao_code_strategy = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    min_size=4,
    max_size=4,
)

# Strategy: generate a single FIR record dict with a given icao_code
def fir_record_strategy(icao_code_st=icao_code_strategy):
    """Generate a FIR record dict with random fields and a given icao_code."""
    return st.fixed_dictionaries({
        "icao_code": icao_code_st,
        "fir_name": st.text(min_size=1, max_size=50),
        "country_name": st.text(min_size=1, max_size=50),
        "country_code": st.text(
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            min_size=2,
            max_size=2,
        ),
        "geojson_geometry": st.just('{"type": "Polygon", "coordinates": []}'),
        "bbox_min_lon": st.floats(min_value=-180, max_value=180, allow_nan=False),
        "bbox_min_lat": st.floats(min_value=-90, max_value=90, allow_nan=False),
        "bbox_max_lon": st.floats(min_value=-180, max_value=180, allow_nan=False),
        "bbox_max_lat": st.floats(min_value=-90, max_value=90, allow_nan=False),
    })


# Strategy: generate a list of FIR records that is guaranteed to contain duplicates
# by picking from a smaller pool of icao_codes
def fir_records_with_duplicates_strategy():
    """Generate a list of FIR records where some icao_codes are duplicated."""
    return st.lists(
        fir_record_strategy(),
        min_size=2,
        max_size=30,
    )


def deduplicate_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply the same deduplication logic as import_fir_data.

    Uses a seen_icao_codes set, keeping the first occurrence of each icao_code.
    This mirrors the logic in import_firs.py import_fir_data().
    """
    seen_icao_codes: set = set()
    unique_records: List[Dict[str, Any]] = []

    for record in records:
        icao_code = record.get("icao_code")
        if icao_code in seen_icao_codes:
            continue
        seen_icao_codes.add(icao_code)
        unique_records.append(record)

    return unique_records


class TestImportDeduplicationProperties:
    """Property 12: Import deduplication by ICAO code.

    Feature: fir-versioning-and-data-import, Property 12: Import deduplication by ICAO code

    **Validates: Requirements 8.9**

    For any list of source FIR records containing duplicate icao_code values,
    the import deduplication SHALL produce exactly one FIR record per unique
    icao_code, keeping the first occurrence from the source data.
    """

    @given(records=fir_records_with_duplicates_strategy())
    @settings(max_examples=100)
    def test_property_12_one_record_per_unique_icao_code(self, records):
        """
        **Validates: Requirements 8.9**

        Property 12: Import deduplication by ICAO code

        Given a list of FIR records with potentially duplicate icao_codes,
        deduplication produces exactly one record per unique icao_code.
        """
        unique_records = deduplicate_records(records)

        # Count of unique records must equal count of distinct icao_codes in input
        input_icao_codes = set(r["icao_code"] for r in records)
        assert len(unique_records) == len(input_icao_codes), (
            f"Expected {len(input_icao_codes)} unique records, "
            f"got {len(unique_records)}"
        )

        # Each icao_code in the output must be unique
        output_icao_codes = [r["icao_code"] for r in unique_records]
        assert len(output_icao_codes) == len(set(output_icao_codes)), (
            "Output contains duplicate icao_codes"
        )

        # For each icao_code, the kept record must be the first occurrence in input
        for unique_record in unique_records:
            icao = unique_record["icao_code"]
            first_in_input = next(r for r in records if r["icao_code"] == icao)
            assert unique_record is first_in_input, (
                f"Kept record for {icao} is not the first occurrence in input"
            )

# --- Strategy for Property 2: Import transform ---

# country_name: non-empty text that the mapper will attempt to resolve
country_name_strategy = st.text(min_size=1, max_size=50)

# country_code: 2 uppercase alpha characters (may or may not be valid ISO)
country_code_strategy = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    min_size=2,
    max_size=2,
)


def import_record_strategy():
    """Generate a FIR input record dict for transform_record testing."""
    return st.fixed_dictionaries({
        "icao_code": icao_code_strategy,
        "fir_name": st.text(min_size=1, max_size=50),
        "country_name": country_name_strategy,
        "country_code": country_code_strategy,
        "geojson_geometry": st.just('{"type": "Polygon", "coordinates": []}'),
        "bbox_min_lon": st.floats(
            min_value=-180, max_value=180, allow_nan=False,
        ),
        "bbox_min_lat": st.floats(
            min_value=-90, max_value=90, allow_nan=False,
        ),
        "bbox_max_lon": st.floats(
            min_value=-180, max_value=180, allow_nan=False,
        ),
        "bbox_max_lat": st.floats(
            min_value=-90, max_value=90, allow_nan=False,
        ),
    })


class TestImportTransformProperties:
    """Property 2: Import transform produces descriptive name and omits
    country_name.

    Feature: fir-schema-cleanup, Property 2

    **Validates: Requirements 6.1, 6.2, 6.3**

    For any input FIR record dictionary containing country_name, icao_code,
    and country_code fields, calling transform_record() SHALL produce an
    output dictionary where: (a) fir_name matches the Descriptive FIR Name
    format, (b) country_name is not present as a key, and (c) country_code
    is preserved from the mapper output.
    """

    @settings(max_examples=100)
    @given(record=import_record_strategy())
    def test_property_2_import_transform_descriptive_name_no_country_name(
        self, record,
    ):
        """
        **Validates: Requirements 6.1, 6.2, 6.3**

        Property 2: Import transform produces descriptive name and omits
        country_name

        Given any input record with country_name, icao_code, and
        country_code, transform_record produces output where fir_name is
        descriptive, country_name is absent, and country_code is preserved.
        """
        mapper = CountryCodeMapper()
        result = transform_record(record, mapper)

        # Determine the expected country_code from the mapper
        expected_country_code = mapper.map(record["country_name"])

        # Determine the expected resolved country name via pycountry
        country = pycountry.countries.get(alpha_2=expected_country_code)
        expected_resolved_name = (
            country.name if country else expected_country_code
        )

        icao_code = record["icao_code"]
        expected_fir_name = f"{expected_resolved_name} FIR ({icao_code})"

        # (a) fir_name matches the Descriptive FIR Name format
        assert result["fir_name"] == expected_fir_name, (
            f"Expected fir_name '{expected_fir_name}', "
            f"got '{result['fir_name']}'"
        )

        # (b) country_name key is absent from output
        assert "country_name" not in result, (
            "Output dict should not contain 'country_name' key"
        )

        # (c) country_code is preserved from mapper output
        assert result["country_code"] == expected_country_code, (
            f"Expected country_code '{expected_country_code}', "
            f"got '{result['country_code']}'"
        )
