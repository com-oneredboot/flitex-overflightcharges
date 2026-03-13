"""Property-based tests for formula query operations.

These tests verify universal properties for querying formulas using Hypothesis.
Each property test runs with a minimum of 100 iterations.

Feature: regional-formula-support

NOTE: These tests require a PostgreSQL database. They will be skipped if
PostgreSQL is not available. To run these tests, ensure PostgreSQL is running
and DATABASE_URL environment variable is set.
"""

import pytest
from datetime import date
from hypothesis import given, settings, strategies as st, assume
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

from src.models.formula import Formula
from src.services.formula_service import FormulaService
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


@pytest.fixture
def formula_service(test_db):
    """Create a FormulaService instance for testing."""
    return FormulaService(test_db)


class TestQueryProperties:
    """Property-based tests for formula query operations."""

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
        created_by=st.text(min_size=1, max_size=255),
        # Generate additional formulas with different country codes
        other_country_code=st.text(
            alphabet=st.characters(whitelist_categories=("Lu",), min_codepoint=65, max_codepoint=90),
            min_size=2,
            max_size=2
        )
    )
    def test_property_11_query_by_country_code(
        self,
        test_db,
        country_code,
        description,
        formula_code,
        formula_logic,
        currency,
        version_number,
        created_by,
        other_country_code
    ):
        """
        **Validates: Requirements 6.1**
        
        Property 11: Query by Country Code
        
        For any country code, querying the database with filter
        Formula.country_code == code should return only formulas where
        country_code equals that specific code, and should not return any
        formulas with country_code=NULL or different country codes.
        """
        # Ensure other_country_code is different from country_code
        assume(other_country_code != country_code)
        
        # Insert formula with target country_code
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
        
        # Insert formula with different country_code
        formula2 = Formula(
            country_code=other_country_code,
            description=f"{description}_other",
            formula_code=f"{formula_code}_other",
            formula_logic=f"{formula_logic}_other",
            effective_date=date.today(),
            currency=currency,
            version_number=version_number,
            is_active=True,
            created_by=created_by
        )
        test_db.add(formula2)
        
        # Insert regional formula (country_code=NULL)
        formula3 = Formula(
            country_code=None,
            description=f"{description}_regional",
            formula_code=f"{formula_code}_regional",
            formula_logic=f"{formula_logic}_regional",
            effective_date=date.today(),
            currency=currency,
            version_number=version_number,
            is_active=True,
            created_by=created_by
        )
        test_db.add(formula3)
        
        test_db.commit()
        
        # Query by target country_code
        results = test_db.query(Formula).filter(
            Formula.country_code == country_code
        ).all()
        
        # Verify only formulas with matching country_code are returned
        assert len(results) >= 1, f"Should find at least 1 formula with country_code={country_code}"
        
        for formula in results:
            assert formula.country_code == country_code, \
                f"Query returned formula with country_code={formula.country_code}, expected {country_code}"
            assert formula.country_code is not None, \
                "Query should not return regional formulas (country_code=NULL)"
        
        # Verify formulas with other country codes are not returned
        result_ids = {f.id for f in results}
        assert formula2.id not in result_ids, \
            f"Query should not return formula with different country_code={other_country_code}"
        assert formula3.id not in result_ids, \
            "Query should not return regional formula (country_code=NULL)"

    @settings(max_examples=100, deadline=None)
    @given(
        description=st.text(min_size=1, max_size=100),
        formula_code=st.text(min_size=1, max_size=50),
        formula_logic=st.text(min_size=1),
        currency=st.text(min_size=3, max_size=3, alphabet=st.characters(whitelist_categories=('Lu',))),
        version_number=st.integers(min_value=1, max_value=100),
        created_by=st.text(min_size=1, max_size=255),
        other_description=st.text(min_size=1, max_size=100)
    )
    def test_property_12_query_by_description(
        self,
        test_db,
        formula_service,
        description,
        formula_code,
        formula_logic,
        currency,
        version_number,
        created_by,
        other_description
    ):
        """
        **Validates: Requirements 6.2**
        
        Property 12: Query by Description
        
        For any description string, querying the database with filter
        Formula.description == description should return only formulas
        where description equals that exact string.
        """
        # Ensure other_description is different from description
        assume(other_description != description)
        
        # Insert formula with target description
        formula1 = Formula(
            country_code="CA",
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
        
        # Insert formula with different description
        formula2 = Formula(
            country_code="US",
            description=other_description,
            formula_code=f"{formula_code}_other",
            formula_logic=f"{formula_logic}_other",
            effective_date=date.today(),
            currency=currency,
            version_number=version_number,
            is_active=True,
            created_by=created_by
        )
        test_db.add(formula2)
        
        test_db.commit()
        
        # Query by description using service method
        results = formula_service.get_formulas_by_description(description)
        
        # Verify only formulas with matching description are returned
        assert len(results) >= 1, f"Should find at least 1 formula with description={description}"
        
        for formula in results:
            assert formula.description == description, \
                f"Query returned formula with description={formula.description}, expected {description}"
        
        # Verify formulas with other descriptions are not returned
        result_ids = {f.id for f in results}
        assert formula2.id not in result_ids, \
            f"Query should not return formula with different description={other_description}"

    @settings(max_examples=100, deadline=None)
    @given(
        regional_description=st.text(min_size=1, max_size=100),
        country_code=st.text(
            alphabet=st.characters(whitelist_categories=("Lu",), min_codepoint=65, max_codepoint=90),
            min_size=2,
            max_size=2
        ),
        country_description=st.text(min_size=1, max_size=100),
        formula_code=st.text(min_size=1, max_size=50),
        formula_logic=st.text(min_size=1),
        currency=st.text(min_size=3, max_size=3, alphabet=st.characters(whitelist_categories=('Lu',))),
        version_number=st.integers(min_value=1, max_value=100),
        created_by=st.text(min_size=1, max_size=255)
    )
    def test_property_13_regional_formula_identification(
        self,
        test_db,
        formula_service,
        regional_description,
        country_code,
        country_description,
        formula_code,
        formula_logic,
        currency,
        version_number,
        created_by
    ):
        """
        **Validates: Requirements 6.3, 6.4**
        
        Property 13: Regional Formula Identification
        
        For any formula record, if country_code is NULL, then is_regional()
        should return True and the formula should be included in queries
        filtering for Formula.country_code.is_(None), and excluded from
        queries filtering for Formula.country_code.isnot(None).
        """
        # Insert regional formula (country_code=NULL)
        regional_formula = Formula(
            country_code=None,
            description=regional_description,
            formula_code=formula_code,
            formula_logic=formula_logic,
            effective_date=date.today(),
            currency=currency,
            version_number=version_number,
            is_active=True,
            created_by=created_by
        )
        test_db.add(regional_formula)
        
        # Insert country formula
        country_formula = Formula(
            country_code=country_code,
            description=country_description,
            formula_code=f"{formula_code}_country",
            formula_logic=f"{formula_logic}_country",
            effective_date=date.today(),
            currency=currency,
            version_number=version_number,
            is_active=True,
            created_by=created_by
        )
        test_db.add(country_formula)
        
        test_db.commit()
        test_db.refresh(regional_formula)
        test_db.refresh(country_formula)
        
        # Test is_regional() method
        assert regional_formula.is_regional() is True, \
            "Regional formula (country_code=NULL) should return True for is_regional()"
        assert country_formula.is_regional() is False, \
            "Country formula should return False for is_regional()"
        
        # Test query for regional formulas (country_code IS NULL)
        regional_results = formula_service.get_regional_formulas()
        regional_ids = {f.id for f in regional_results}
        
        assert regional_formula.id in regional_ids, \
            "Regional formula should be included in query for country_code IS NULL"
        assert country_formula.id not in regional_ids, \
            "Country formula should be excluded from query for country_code IS NULL"
        
        # Test query for country formulas (country_code IS NOT NULL)
        country_results = formula_service.get_country_formulas()
        country_ids = {f.id for f in country_results}
        
        assert country_formula.id in country_ids, \
            "Country formula should be included in query for country_code IS NOT NULL"
        assert regional_formula.id not in country_ids, \
            "Regional formula should be excluded from query for country_code IS NOT NULL"

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
    def test_property_14_backward_compatibility_of_country_queries(
        self,
        test_db,
        formula_service,
        country_code,
        description,
        formula_code,
        formula_logic,
        currency,
        version_number,
        created_by
    ):
        """
        **Validates: Requirements 7.1**
        
        Property 14: Backward Compatibility of Country Queries
        
        For any query pattern that filters by country_code with a non-NULL value
        (e.g., Formula.country_code == "CA"), the query should return the same
        set of formula records before and after the migration, with identical
        field values.
        
        This test simulates the "after migration" state by verifying that
        country formulas can be queried correctly and return expected data.
        """
        # Insert country formula
        formula = Formula(
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
        test_db.add(formula)
        test_db.commit()
        test_db.refresh(formula)
        
        # Store original values
        original_id = formula.id
        original_country_code = formula.country_code
        original_description = formula.description
        original_formula_code = formula.formula_code
        original_formula_logic = formula.formula_logic
        original_effective_date = formula.effective_date
        original_currency = formula.currency
        original_version_number = formula.version_number
        original_is_active = formula.is_active
        original_created_by = formula.created_by
        
        # Query by country_code (simulating existing query pattern)
        result = formula_service.get_active_formula(country_code)
        
        # Verify the query returns the formula
        assert result is not None, \
            f"Query by country_code={country_code} should return a formula"
        
        # Verify all field values are preserved (backward compatibility)
        assert result.id == original_id, "ID should be preserved"
        assert result.country_code == original_country_code, "country_code should be preserved"
        assert result.description == original_description, "description should be preserved"
        assert result.formula_code == original_formula_code, "formula_code should be preserved"
        assert result.formula_logic == original_formula_logic, "formula_logic should be preserved"
        assert result.effective_date == original_effective_date, "effective_date should be preserved"
        assert result.currency == original_currency, "currency should be preserved"
        assert result.version_number == original_version_number, "version_number should be preserved"
        assert result.is_active == original_is_active, "is_active should be preserved"
        assert result.created_by == original_created_by, "created_by should be preserved"
        
        # Verify country_code is not NULL (backward compatibility)
        assert result.country_code is not None, \
            "Country formula should have non-NULL country_code for backward compatibility"
