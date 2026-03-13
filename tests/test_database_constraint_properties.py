"""Property-based tests for database constraint validation.

These tests verify universal properties for database constraints using Hypothesis.
Each property test runs with a minimum of 100 iterations.

Feature: regional-formula-support

NOTE: These tests require a PostgreSQL database. They will be skipped if
PostgreSQL is not available. To run these tests, ensure PostgreSQL is running
and DATABASE_URL environment variable is set.
"""

import pytest
from datetime import date
from hypothesis import given, settings, strategies as st
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
import os

from src.models.formula import Formula
from src.database import Base


# Check if PostgreSQL is available
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


# Skip all tests in this module if PostgreSQL is not available
pytestmark = pytest.mark.skipif(
    not is_postgres_available(),
    reason="Requires PostgreSQL database. Set DATABASE_URL environment variable."
)


@pytest.fixture(scope="function")
def test_db():
    """Create a test database session for each test."""
    database_url = os.getenv("DATABASE_URL")
    engine = create_engine(database_url, echo=False)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    # Cleanup
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


class TestDatabaseConstraintProperties:
    """Property-based tests for database constraint validation."""

    @settings(max_examples=100, deadline=None)
    @given(
        description=st.text(min_size=1, max_size=100),
        formula_code=st.text(min_size=1, max_size=50),
        formula_logic=st.text(min_size=1),
        currency=st.text(min_size=3, max_size=3, alphabet=st.characters(whitelist_categories=('Lu',))),
        version_number=st.integers(min_value=1, max_value=100),
        created_by=st.text(min_size=1, max_size=255)
    )
    def test_property_1_nullable_country_code_acceptance(
        self,
        test_db,
        description,
        formula_code,
        formula_logic,
        currency,
        version_number,
        created_by
    ):
        """
        **Validates: Requirements 1.1, 9.4**
        
        Property 1: Nullable Country Code Acceptance
        
        For any valid formula data with country_code=NULL and a non-null description,
        inserting the formula into the database should succeed without constraint violations.
        """
        # Create formula with NULL country_code
        formula = Formula(
            country_code=None,  # NULL for regional formula
            description=description,
            formula_code=formula_code,
            formula_logic=formula_logic,
            effective_date=date.today(),
            currency=currency,
            version_number=version_number,
            is_active=True,
            created_by=created_by
        )
        
        # Insert into database
        test_db.add(formula)
        test_db.commit()  # Should not raise
        
        # Verify insertion succeeded
        assert formula.id is not None, "Formula should have an ID after commit"
        assert formula.country_code is None, "country_code should be NULL"
        assert formula.description == description, "description should be preserved"
        
        # Verify we can query it back
        retrieved = test_db.query(Formula).filter(Formula.id == formula.id).first()
        assert retrieved is not None, "Should be able to retrieve the formula"
        assert retrieved.country_code is None, "Retrieved formula should have NULL country_code"

    @settings(max_examples=100, deadline=None)
    @given(
        formula_code=st.text(min_size=1, max_size=50),
        formula_logic=st.text(min_size=1),
        currency=st.text(min_size=3, max_size=3, alphabet=st.characters(whitelist_categories=('Lu',))),
        version_number=st.integers(min_value=1, max_value=100),
        created_by=st.text(min_size=1, max_size=255)
    )
    def test_property_2_description_required_for_regional_formulas(
        self,
        test_db,
        formula_code,
        formula_logic,
        currency,
        version_number,
        created_by
    ):
        """
        **Validates: Requirements 1.2, 2.2**
        
        Property 2: Description Required for Regional Formulas
        
        For any formula data with country_code=NULL, attempting to insert without
        a description (description=NULL or empty) should fail with a NOT NULL
        constraint violation.
        """
        # Attempt to create formula with NULL country_code and NULL description
        formula = Formula(
            country_code=None,
            description=None,  # NULL description should fail
            formula_code=formula_code,
            formula_logic=formula_logic,
            effective_date=date.today(),
            currency=currency,
            version_number=version_number,
            is_active=True,
            created_by=created_by
        )
        
        test_db.add(formula)
        
        # Should raise IntegrityError for NOT NULL constraint
        with pytest.raises(IntegrityError) as exc_info:
            test_db.commit()
        
        # Verify the error is related to description
        error_str = str(exc_info.value).lower()
        assert "description" in error_str or "not null" in error_str, \
            f"Expected description NOT NULL error, got: {exc_info.value}"

    @settings(max_examples=100, deadline=None)
    @given(
        country_code=st.text(
            alphabet=st.characters(whitelist_categories=("Lu",), min_codepoint=65, max_codepoint=90),
            min_size=2,
            max_size=2
        ),
        description=st.text(min_size=1, max_size=100),
        formula_code=st.text(min_size=1, max_size=50),
        formula_logic=st.text(min_size=1),
        currency=st.text(min_size=3, max_size=3, alphabet=st.characters(whitelist_categories=('Lu',))),
        version_number=st.integers(min_value=1, max_value=100),
        created_by=st.text(min_size=1, max_size=255)
    )
    def test_property_3_country_formula_uniqueness(
        self,
        test_db,
        country_code,
        description,
        formula_code,
        formula_logic,
        currency,
        version_number,
        created_by
    ):
        """
        **Validates: Requirements 1.3, 8.1**
        
        Property 3: Country Formula Uniqueness
        
        For any country code and version number pair, attempting to insert a second
        formula with the same (country_code, version_number) should fail with a
        unique constraint violation.
        """
        # Insert first formula
        formula1 = Formula(
            country_code=country_code,
            description=description,
            formula_code=formula_code,
            formula_logic=formula_logic,
            effective_date=date.today(),
            currency=currency,
            version_number=version_number,
            is_active=True,
            created_by=created_by
        )
        
        test_db.add(formula1)
        test_db.commit()
        
        # Attempt to insert second formula with same country_code and version_number
        formula2 = Formula(
            country_code=country_code,  # Same country_code
            description=f"{description}_different",
            formula_code=f"{formula_code}_different",
            formula_logic=f"{formula_logic}_different",
            effective_date=date.today(),
            currency=currency,
            version_number=version_number,  # Same version_number
            is_active=False,  # Different is_active
            created_by=created_by
        )
        
        test_db.add(formula2)
        
        # Should raise IntegrityError for unique constraint violation
        with pytest.raises(IntegrityError) as exc_info:
            test_db.commit()
        
        # Verify the error is related to unique constraint
        error_str = str(exc_info.value).lower()
        assert ("unique" in error_str or "duplicate" in error_str), \
            f"Expected unique constraint error, got: {exc_info.value}"

    @settings(max_examples=100, deadline=None)
    @given(
        description=st.text(min_size=1, max_size=100),
        formula_code=st.text(min_size=1, max_size=50),
        formula_logic=st.text(min_size=1),
        currency=st.text(min_size=3, max_size=3, alphabet=st.characters(whitelist_categories=('Lu',))),
        version_number=st.integers(min_value=1, max_value=100),
        created_by=st.text(min_size=1, max_size=255)
    )
    def test_property_15_regional_formula_uniqueness(
        self,
        test_db,
        description,
        formula_code,
        formula_logic,
        currency,
        version_number,
        created_by
    ):
        """
        **Validates: Requirements 8.2, 8.3**
        
        Property 15: Regional Formula Uniqueness
        
        For any description string with country_code=NULL, attempting to insert a
        second active formula with the same description and country_code=NULL should
        fail with an application-level validation error indicating a duplicate
        regional formula exists.
        
        Note: This tests application-level uniqueness since PostgreSQL treats NULL
        values as distinct in unique constraints.
        """
        # Import the insert function to test application-level validation
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        import port_formulas
        
        # Insert first regional formula
        success1 = port_formulas.insert_formula_into_database(
            test_db,
            country_code=None,
            description=description,
            formula_code=formula_code,
            formula_logic=formula_logic,
            created_by=created_by
        )
        
        assert success1 is True, "First regional formula should be inserted successfully"
        test_db.commit()
        
        # Attempt to insert second regional formula with same description
        success2 = port_formulas.insert_formula_into_database(
            test_db,
            country_code=None,  # Same NULL country_code
            description=description,  # Same description
            formula_code=f"{formula_code}_different",
            formula_logic=f"{formula_logic}_different",
            created_by=created_by
        )
        
        # Application-level check should prevent duplicate (returns False)
        assert success2 is False, \
            f"Duplicate regional formula with description '{description}' should be rejected"
        
        # Verify only one formula exists with this description
        count = test_db.query(Formula).filter(
            Formula.country_code.is_(None),
            Formula.description == description
        ).count()
        
        assert count == 1, \
            f"Should have exactly 1 regional formula with description '{description}', found {count}"
