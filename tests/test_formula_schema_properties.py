"""Property-based tests for Formula Pydantic schemas.

These tests verify universal properties across many generated inputs using Hypothesis.
Each property test runs with a minimum of 100 iterations.

Feature: regional-formula-support
"""

import pytest
from datetime import date
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from src.schemas.formula import FormulaBase, FormulaCreate


class TestFormulaSchemaProperties:
    """Property-based tests for Formula schema validation."""

    @settings(max_examples=100, deadline=None)
    @given(
        country_code=st.one_of(
            st.none(),
            st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',)))
        ),
        formula_code=st.text(min_size=1, max_size=50),
        formula_logic=st.text(min_size=1),
        currency=st.text(min_size=3, max_size=3, alphabet=st.characters(whitelist_categories=('Lu',))),
        effective_date=st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31))
    )
    def test_property_7_pydantic_description_validation(
        self,
        country_code,
        formula_code,
        formula_logic,
        currency,
        effective_date
    ):
        """
        **Validates: Requirements 4.3**
        
        Property 7: Pydantic Description Validation
        
        For any formula data with all required fields except description,
        attempting to create a FormulaBase or FormulaCreate Pydantic instance
        should raise a validation error indicating description is required.
        """
        # Attempt to create FormulaBase without description field
        with pytest.raises(ValidationError) as exc_info:
            FormulaBase(
                country_code=country_code,
                formula_code=formula_code,
                formula_logic=formula_logic,
                effective_date=effective_date,
                currency=currency
                # description intentionally omitted
            )
        
        # Verify the error mentions 'description'
        error_str = str(exc_info.value)
        assert "description" in error_str.lower(), \
            f"Expected 'description' in validation error, got: {error_str}"

    @settings(max_examples=100, deadline=None)
    @given(
        country_code=st.one_of(
            st.none(),
            st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',)))
        ),
        description=st.text(min_size=1, max_size=100),
        formula_code=st.text(min_size=1, max_size=50),
        formula_logic=st.text(min_size=1),
        currency=st.text(min_size=3, max_size=3, alphabet=st.characters(whitelist_categories=('Lu',))),
        effective_date=st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)),
        created_by=st.text(min_size=1, max_size=255)
    )
    def test_property_7_description_empty_string_rejected(
        self,
        country_code,
        description,
        formula_code,
        formula_logic,
        currency,
        effective_date,
        created_by
    ):
        """
        **Validates: Requirements 4.3**
        
        Property 7: Pydantic Description Validation (Empty String)
        
        For any formula data with description as empty string,
        attempting to create a FormulaCreate Pydantic instance
        should raise a validation error.
        """
        # Attempt to create FormulaCreate with empty description
        with pytest.raises(ValidationError) as exc_info:
            FormulaCreate(
                country_code=country_code,
                description="",  # Empty string should be rejected
                formula_code=formula_code,
                formula_logic=formula_logic,
                effective_date=effective_date,
                currency=currency,
                created_by=created_by
            )
        
        # Verify the error mentions 'description' or string length
        error_str = str(exc_info.value)
        assert ("description" in error_str.lower() or "at least 1 character" in error_str.lower()), \
            f"Expected description validation error, got: {error_str}"

    @settings(max_examples=100, deadline=None)
    @given(
        invalid_country_code=st.one_of(
            # Not exactly 2 characters
            st.text(min_size=0, max_size=1, alphabet=st.characters(whitelist_categories=('Lu',))),
            st.text(min_size=3, max_size=10, alphabet=st.characters(whitelist_categories=('Lu',))),
            # Not uppercase
            st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Ll',))),
            # Not alphabetic
            st.text(min_size=2, max_size=2, alphabet='0123456789'),
            # Mixed case
            st.just("Us"),
            st.just("uS")
        ),
        description=st.text(min_size=1, max_size=100),
        formula_code=st.text(min_size=1, max_size=50),
        formula_logic=st.text(min_size=1),
        currency=st.text(min_size=3, max_size=3, alphabet=st.characters(whitelist_categories=('Lu',))),
        effective_date=st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31))
    )
    def test_property_8_pydantic_country_code_validation_invalid(
        self,
        invalid_country_code,
        description,
        formula_code,
        formula_logic,
        currency,
        effective_date
    ):
        """
        **Validates: Requirements 4.4, 7.3**
        
        Property 8: Pydantic Country Code Validation (Invalid Codes)
        
        For any country_code value that is not NULL, not exactly 2 characters,
        not uppercase, or not alphabetic, attempting to create a FormulaBase
        Pydantic instance should raise a validation error.
        """
        # Attempt to create FormulaBase with invalid country_code
        with pytest.raises(ValidationError) as exc_info:
            FormulaBase(
                country_code=invalid_country_code,
                description=description,
                formula_code=formula_code,
                formula_logic=formula_logic,
                effective_date=effective_date,
                currency=currency
            )
        
        # Verify the error is related to country_code validation
        error_str = str(exc_info.value)
        assert ("country" in error_str.lower() or 
                "2 characters" in error_str.lower() or
                "uppercase" in error_str.lower() or
                "letters" in error_str.lower()), \
            f"Expected country_code validation error, got: {error_str}"

    @settings(max_examples=100, deadline=None)
    @given(
        valid_country_code=st.one_of(
            st.none(),
            st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',)))
        ),
        description=st.text(min_size=1, max_size=100),
        formula_code=st.text(min_size=1, max_size=50),
        formula_logic=st.text(min_size=1),
        currency=st.text(min_size=3, max_size=3, alphabet=st.characters(whitelist_categories=('Lu',))),
        effective_date=st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31))
    )
    def test_property_8_pydantic_country_code_validation_valid(
        self,
        valid_country_code,
        description,
        formula_code,
        formula_logic,
        currency,
        effective_date
    ):
        """
        **Validates: Requirements 4.4, 7.3**
        
        Property 8: Pydantic Country Code Validation (Valid Codes)
        
        For NULL and valid 2-character uppercase alphabetic country codes,
        creating a FormulaBase Pydantic instance should succeed.
        """
        # Create FormulaBase with valid country_code (None or 2 uppercase letters)
        formula = FormulaBase(
            country_code=valid_country_code,
            description=description,
            formula_code=formula_code,
            formula_logic=formula_logic,
            effective_date=effective_date,
            currency=currency
        )
        
        # Verify the formula was created successfully
        assert formula.country_code == valid_country_code
        assert formula.description == description
        assert formula.formula_code == formula_code
        assert formula.formula_logic == formula_logic
        assert formula.effective_date == effective_date
        assert formula.currency == currency
