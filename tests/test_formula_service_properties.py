"""Property-based tests for Formula service operations.

These tests verify universal properties for Formula service CRUD operations using Hypothesis.
Each property test runs with a minimum of 100 iterations.

Feature: fir-versioning-and-data-import

NOTE: These tests require a PostgreSQL database. They will be skipped if
PostgreSQL is not available. To run these tests, ensure PostgreSQL is running
and DATABASE_URL environment variable is set.
"""

import uuid
import pytest
from datetime import date, datetime, timezone
from hypothesis import given, settings, strategies as st, HealthCheck
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

from src.models.formula import Formula
from src.schemas.formula import FormulaCreate, FormulaUpdate
from src.services.formula_service import FormulaService
from src.database import Base


# PostgreSQL rejects NUL (0x00) in text — use printable + common unicode, no surrogates/NUL
pg_safe_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="\x00",
    ),
)


def is_postgres_available():
    """Check if PostgreSQL database is available for testing."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or "postgresql" not in database_url:
        return False
    try:
        engine = create_engine(database_url, echo=False)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not is_postgres_available(),
    reason="Requires PostgreSQL database. Set DATABASE_URL environment variable.",
)


@pytest.fixture(scope="function")
def test_db():
    """Create a test database session for each test."""
    database_url = os.getenv("DATABASE_URL")
    engine = create_engine(database_url, echo=False)

    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)
    session = TestSession()

    yield session

    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# --- Hypothesis strategies for Formula data ---

country_code_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu",), min_codepoint=65, max_codepoint=90,
    ),
    min_size=2,
    max_size=2,
)

description_strategy = pg_safe_text.filter(lambda s: len(s.strip()) > 0).map(
    lambda s: s[:100]
).filter(lambda s: len(s) >= 1)

formula_code_strategy = pg_safe_text.filter(lambda s: len(s.strip()) > 0).map(
    lambda s: s[:50]
).filter(lambda s: len(s) >= 1)

currency_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu",), min_codepoint=65, max_codepoint=90,
    ),
    min_size=3,
    max_size=3,
)

created_by_strategy = pg_safe_text.filter(lambda s: len(s.strip()) > 0).map(
    lambda s: s[:100]
).filter(lambda s: len(s) >= 1)

# Valid Python expression for formula_logic — FormulaParser validates syntax via ast.parse
formula_logic_strategy = st.just("mtow * rate")


@st.composite
def formula_create_strategy(draw):
    """Generate a valid FormulaCreate schema instance with random data."""
    return FormulaCreate(
        country_code=draw(country_code_strategy),
        description=draw(description_strategy),
        formula_code=draw(formula_code_strategy),
        formula_logic=draw(formula_logic_strategy),
        effective_date=draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))),
        currency=draw(currency_strategy),
        created_by=draw(created_by_strategy),
    )


class TestFormulaActivationDeactivationTimestampsProperty:
    """
    Feature: fir-versioning-and-data-import, Property 10: Formula activation and deactivation timestamps

    **Validates: Requirements 6.4, 6.5**

    For any formula creation, the resulting record SHALL have a non-null
    activation_date set to approximately the current timestamp. For any formula
    deactivation (via update, delete, or rollback), the outgoing version SHALL
    have a non-null deactivation_date set to approximately the current timestamp.
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        formula_data=formula_create_strategy(),
        updated_by=created_by_strategy,
    )
    def test_property_10_formula_activation_and_deactivation_timestamps(
        self, test_db, formula_data, updated_by
    ):
        """
        **Validates: Requirements 6.4, 6.5**

        Property 10: Formula activation and deactivation timestamps

        Create formula, verify activation_date ≈ now(); update formula,
        verify deactivation_date ≈ now() on the outgoing version.
        """
        # Reset session state in case a previous iteration left it dirty
        test_db.rollback()

        # Clean up any existing formula with same country_code to avoid constraint violations
        test_db.query(Formula).filter(
            Formula.country_code == formula_data.country_code
        ).delete()
        test_db.commit()

        service = FormulaService(test_db)

        # --- Part 1: Create formula and verify activation_date ≈ now() ---
        before_create = datetime.now(timezone.utc)

        created_formula = service.create_formula(formula_data, formula_data.created_by)

        after_create = datetime.now(timezone.utc)

        # Requirement 6.4: activation_date set on creation
        assert created_formula.activation_date is not None, (
            "activation_date must not be None after creation"
        )
        assert before_create <= created_formula.activation_date <= after_create, (
            f"activation_date {created_formula.activation_date} not between "
            f"{before_create} and {after_create}"
        )

        # --- Part 2: Update formula and verify deactivation_date ≈ now() on old version ---
        update_data = FormulaUpdate(
            description=formula_data.description,
            formula_logic="mtow * rate * 2",
            created_by=updated_by,
        )

        before_update = datetime.now(timezone.utc)

        new_formula = service.update_formula(
            formula_data.country_code, update_data, updated_by
        )

        after_update = datetime.now(timezone.utc)

        # Refresh old version to see deactivation changes
        test_db.refresh(created_formula)

        # Requirement 6.5: deactivation_date set on outgoing version
        assert created_formula.deactivation_date is not None, (
            "deactivation_date must not be None on outgoing version after update"
        )
        assert before_update <= created_formula.deactivation_date <= after_update, (
            f"deactivation_date {created_formula.deactivation_date} not between "
            f"{before_update} and {after_update}"
        )

        # Verify the new version also has activation_date set
        assert new_formula.activation_date is not None, (
            "activation_date must not be None on new version after update"
        )
        assert before_update <= new_formula.activation_date <= after_update, (
            f"New version activation_date {new_formula.activation_date} not between "
            f"{before_update} and {after_update}"
        )
