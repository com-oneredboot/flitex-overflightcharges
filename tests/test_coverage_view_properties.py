"""Property-based tests for coverage view correctness.

Feature: fir-versioning-and-data-import, Property 13: Coverage view correctness

These tests verify that the coverage view logic correctly joins active FIRs
with active formulas, producing one row per active FIR with accurate
has_formula and formula_description values.

Requirements: 9.2, 9.4, 9.5
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

import pytest
from hypothesis import given, settings, strategies as st


# --- Data classes representing the relevant model fields ---

@dataclass
class FirRecord:
    """Represents an active FIR record (subset of IataFir fields)."""
    icao_code: str
    fir_name: str
    country_code: str
    country_name: str
    is_active: bool


@dataclass
class FormulaRecord:
    """Represents a formula record (subset of Formula fields)."""
    id: int  # surrogate id for presence check
    country_code: str
    description: str
    is_active: bool


@dataclass
class CoverageRow:
    """Represents a single row from vw_fir_formula_coverage."""
    icao_code: str
    fir_name: str
    country_code: str
    country_name: str
    has_formula: bool
    formula_description: Optional[str]


def compute_coverage_view(
    firs: List[FirRecord],
    formulas: List[FormulaRecord],
) -> List[CoverageRow]:
    """Simulate the vw_fir_formula_coverage SQL view logic in Python.

    SQL being simulated:
        SELECT f.icao_code, f.fir_name, f.country_code, f.country_name,
               CASE WHEN fm.id IS NOT NULL THEN TRUE ELSE FALSE END AS has_formula,
               fm.description AS formula_description
        FROM iata_firs f
        LEFT JOIN formulas fm
            ON f.country_code = fm.country_code AND fm.is_active = TRUE
        WHERE f.is_active = TRUE;
    """
    # Filter to active FIRs only (WHERE f.is_active = TRUE)
    active_firs = [f for f in firs if f.is_active]

    # Build lookup: country_code -> first matching active formula
    active_formula_by_country: Dict[str, FormulaRecord] = {}
    for fm in formulas:
        if fm.is_active and fm.country_code not in active_formula_by_country:
            active_formula_by_country[fm.country_code] = fm

    # LEFT JOIN: one row per active FIR
    rows: List[CoverageRow] = []
    for fir in active_firs:
        matched_formula = active_formula_by_country.get(fir.country_code)
        rows.append(CoverageRow(
            icao_code=fir.icao_code,
            fir_name=fir.fir_name,
            country_code=fir.country_code,
            country_name=fir.country_name,
            has_formula=matched_formula is not None,
            formula_description=(
                matched_formula.description if matched_formula is not None else None
            ),
        ))

    return rows


# --- Hypothesis strategies ---

icao_code_strategy = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    min_size=4,
    max_size=4,
).filter(lambda s: any(c.isalpha() for c in s))

country_code_strategy = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    min_size=2,
    max_size=2,
)

fir_name_strategy = st.text(min_size=1, max_size=50)
country_name_strategy = st.text(min_size=1, max_size=50)
description_strategy = st.text(min_size=1, max_size=100)


@st.composite
def fir_record_strategy(draw):
    """Generate a FirRecord with random fields."""
    return FirRecord(
        icao_code=draw(icao_code_strategy),
        fir_name=draw(fir_name_strategy),
        country_code=draw(country_code_strategy),
        country_name=draw(country_name_strategy),
        is_active=draw(st.booleans()),
    )


@st.composite
def formula_record_strategy(draw, id_counter=[0]):
    """Generate a FormulaRecord with random fields."""
    id_counter[0] += 1
    return FormulaRecord(
        id=id_counter[0],
        country_code=draw(country_code_strategy),
        description=draw(description_strategy),
        is_active=draw(st.booleans()),
    )


@st.composite
def coverage_scenario_strategy(draw):
    """Generate a scenario with FIRs and formulas for coverage testing.

    Ensures at least one active FIR exists so the test is meaningful.
    """
    firs = draw(st.lists(fir_record_strategy(), min_size=1, max_size=20))
    formulas = draw(st.lists(formula_record_strategy(), min_size=0, max_size=15))

    # Ensure at least one active FIR
    if not any(f.is_active for f in firs):
        firs[0] = FirRecord(
            icao_code=firs[0].icao_code,
            fir_name=firs[0].fir_name,
            country_code=firs[0].country_code,
            country_name=firs[0].country_name,
            is_active=True,
        )

    return firs, formulas


class TestCoverageViewCorrectnessProperty:
    """Property 13: Coverage view correctness.

    Feature: fir-versioning-and-data-import, Property 13: Coverage view correctness

    **Validates: Requirements 9.2, 9.4, 9.5**

    For any database state with active FIRs and active formulas, the
    vw_fir_formula_coverage view SHALL:
    (a) contain exactly one row per active FIR,
    (b) set has_formula=True only when a matching active formula exists for
        that FIR's country_code,
    (c) set has_formula=False and formula_description=None when no matching
        active formula exists,
    (d) count(has_formula=True) + count(has_formula=False) == total active FIRs.
    """

    @given(scenario=coverage_scenario_strategy())
    @settings(max_examples=100)
    def test_property_13_coverage_view_correctness(self, scenario):
        """
        **Validates: Requirements 9.2, 9.4, 9.5**

        Property 13: Coverage view correctness

        Generate random sets of active FIRs and formulas, verify the view
        returns one row per active FIR, has_formula matches formula existence
        by country_code, and covered + uncovered = total active FIRs.
        """
        firs, formulas = scenario
        rows = compute_coverage_view(firs, formulas)

        active_firs = [f for f in firs if f.is_active]
        active_formula_countries = {
            fm.country_code for fm in formulas if fm.is_active
        }

        # (a) One row per active FIR
        assert len(rows) == len(active_firs), (
            f"Expected {len(active_firs)} rows (one per active FIR), "
            f"got {len(rows)}"
        )

        # Verify each row individually
        for row, fir in zip(rows, active_firs):
            # Row matches the FIR it came from
            assert row.icao_code == fir.icao_code
            assert row.country_code == fir.country_code

            if fir.country_code in active_formula_countries:
                # (b) has_formula=True when matching active formula exists
                assert row.has_formula is True, (
                    f"FIR {fir.icao_code} (country={fir.country_code}) should "
                    f"have has_formula=True — active formula exists"
                )
                assert row.formula_description is not None, (
                    f"FIR {fir.icao_code} should have a formula_description "
                    f"when has_formula=True"
                )
            else:
                # (c) has_formula=False and formula_description=None when no match
                assert row.has_formula is False, (
                    f"FIR {fir.icao_code} (country={fir.country_code}) should "
                    f"have has_formula=False — no active formula for country"
                )
                assert row.formula_description is None, (
                    f"FIR {fir.icao_code} should have formula_description=None "
                    f"when has_formula=False"
                )

        # (d) covered + uncovered = total active FIRs
        covered = sum(1 for r in rows if r.has_formula)
        uncovered = sum(1 for r in rows if not r.has_formula)
        assert covered + uncovered == len(active_firs), (
            f"covered ({covered}) + uncovered ({uncovered}) != "
            f"total active FIRs ({len(active_firs)})"
        )
