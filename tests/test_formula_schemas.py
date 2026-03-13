"""Unit tests for Formula Pydantic schemas."""

import pytest
from datetime import date, datetime
from uuid import uuid4
from pydantic import ValidationError
from src.schemas.formula import (
    FormulaBase,
    FormulaCreate,
    FormulaUpdate,
    FormulaRollback,
    FormulaResponse
)


class TestFormulaBase:
    """Tests for FormulaBase schema."""
    
    def test_valid_formula_base(self):
        """Test creating FormulaBase with valid data."""
        formula = FormulaBase(
            country_code="US",
            formula_code="US_STANDARD_2024",
            formula_logic="return mtow_kg * 0.05 * distance_km",
            effective_date=date(2024, 1, 1),
            currency="USD"
        )
        assert formula.country_code == "US"
        assert formula.formula_code == "US_STANDARD_2024"
        assert formula.formula_logic == "return mtow_kg * 0.05 * distance_km"
        assert formula.effective_date == date(2024, 1, 1)
        assert formula.currency == "USD"
    
    def test_country_code_must_be_uppercase(self):
        """Test that lowercase country code is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaBase(
                country_code="us",
                formula_code="US_STANDARD_2024",
                formula_logic="return mtow_kg * 0.05",
                effective_date=date(2024, 1, 1),
                currency="USD"
            )
        assert "Country code must be uppercase" in str(exc_info.value)
    
    def test_country_code_must_be_letters_only(self):
        """Test that country code with numbers is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaBase(
                country_code="U2",
                formula_code="US_STANDARD_2024",
                formula_logic="return mtow_kg * 0.05",
                effective_date=date(2024, 1, 1),
                currency="USD"
            )
        assert "Country code must contain only letters" in str(exc_info.value)
    
    def test_country_code_must_be_2_characters(self):
        """Test that country code with wrong length is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaBase(
                country_code="USA",
                formula_code="US_STANDARD_2024",
                formula_logic="return mtow_kg * 0.05",
                effective_date=date(2024, 1, 1),
                currency="USD"
            )
        assert "String should have at most 2 characters" in str(exc_info.value)
    
    def test_currency_must_be_uppercase(self):
        """Test that lowercase currency is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaBase(
                country_code="US",
                formula_code="US_STANDARD_2024",
                formula_logic="return mtow_kg * 0.05",
                effective_date=date(2024, 1, 1),
                currency="usd"
            )
        assert "Currency must be uppercase" in str(exc_info.value)
    
    def test_currency_must_be_letters_only(self):
        """Test that currency with numbers is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaBase(
                country_code="US",
                formula_code="US_STANDARD_2024",
                formula_logic="return mtow_kg * 0.05",
                effective_date=date(2024, 1, 1),
                currency="US1"
            )
        assert "Currency must contain only letters" in str(exc_info.value)
    
    def test_currency_must_be_3_characters(self):
        """Test that currency with wrong length is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaBase(
                country_code="US",
                formula_code="US_STANDARD_2024",
                formula_logic="return mtow_kg * 0.05",
                effective_date=date(2024, 1, 1),
                currency="US"
            )
        assert "String should have at least 3 characters" in str(exc_info.value)
    
    def test_formula_code_required(self):
        """Test that formula_code is required."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaBase(
                country_code="US",
                formula_logic="return mtow_kg * 0.05",
                effective_date=date(2024, 1, 1),
                currency="USD"
            )
        assert "formula_code" in str(exc_info.value)
    
    def test_formula_logic_required(self):
        """Test that formula_logic is required."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaBase(
                country_code="US",
                formula_code="US_STANDARD_2024",
                effective_date=date(2024, 1, 1),
                currency="USD"
            )
        assert "formula_logic" in str(exc_info.value)
    
    def test_formula_logic_cannot_be_empty(self):
        """Test that empty formula_logic is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaBase(
                country_code="US",
                formula_code="US_STANDARD_2024",
                formula_logic="",
                effective_date=date(2024, 1, 1),
                currency="USD"
            )
        assert "String should have at least 1 character" in str(exc_info.value)
    
    def test_effective_date_required(self):
        """Test that effective_date is required."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaBase(
                country_code="US",
                formula_code="US_STANDARD_2024",
                formula_logic="return mtow_kg * 0.05",
                currency="USD"
            )
        assert "effective_date" in str(exc_info.value)


class TestFormulaCreate:
    """Tests for FormulaCreate schema."""
    
    def test_formula_create_with_valid_data(self):
        """Test creating FormulaCreate with valid data."""
        formula = FormulaCreate(
            country_code="GB",
            formula_code="GB_STANDARD_2024",
            formula_logic="return mtow_kg * 0.08 * distance_km",
            effective_date=date(2024, 1, 1),
            currency="GBP",
            created_by="admin@example.com"
        )
        assert formula.country_code == "GB"
        assert formula.formula_code == "GB_STANDARD_2024"
        assert formula.created_by == "admin@example.com"
    
    def test_formula_create_requires_created_by(self):
        """Test that created_by is required."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaCreate(
                country_code="GB",
                formula_code="GB_STANDARD_2024",
                formula_logic="return mtow_kg * 0.08",
                effective_date=date(2024, 1, 1),
                currency="GBP"
            )
        assert "created_by" in str(exc_info.value)
    
    def test_formula_create_created_by_cannot_be_empty(self):
        """Test that empty created_by is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaCreate(
                country_code="GB",
                formula_code="GB_STANDARD_2024",
                formula_logic="return mtow_kg * 0.08",
                effective_date=date(2024, 1, 1),
                currency="GBP",
                created_by=""
            )
        assert "String should have at least 1 character" in str(exc_info.value)
    
    def test_formula_create_inherits_validators(self):
        """Test that FormulaCreate inherits validators from FormulaBase."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaCreate(
                country_code="us",
                formula_code="GB_STANDARD_2024",
                formula_logic="return mtow_kg * 0.08",
                effective_date=date(2024, 1, 1),
                currency="GBP",
                created_by="admin@example.com"
            )
        assert "Country code must be uppercase" in str(exc_info.value)


class TestFormulaUpdate:
    """Tests for FormulaUpdate schema."""
    
    def test_formula_update_all_fields_optional_except_created_by(self):
        """Test that FormulaUpdate requires only created_by."""
        formula = FormulaUpdate(created_by="admin@example.com")
        assert formula.formula_code is None
        assert formula.formula_logic is None
        assert formula.effective_date is None
        assert formula.currency is None
        assert formula.created_by == "admin@example.com"
    
    def test_formula_update_partial_update(self):
        """Test that FormulaUpdate can update only some fields."""
        formula = FormulaUpdate(
            formula_logic="return mtow_kg * 0.10 * distance_km",
            currency="EUR",
            created_by="admin@example.com"
        )
        assert formula.formula_logic == "return mtow_kg * 0.10 * distance_km"
        assert formula.currency == "EUR"
        assert formula.formula_code is None
        assert formula.effective_date is None
    
    def test_formula_update_validates_currency_if_provided(self):
        """Test that FormulaUpdate validates currency if provided."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaUpdate(
                currency="eu",
                created_by="admin@example.com"
            )
        # Pydantic validates length before custom validator runs
        assert "String should have at least 3 characters" in str(exc_info.value)
    
    def test_formula_update_requires_created_by(self):
        """Test that created_by is required even for updates."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaUpdate(formula_logic="return mtow_kg * 0.10")
        assert "created_by" in str(exc_info.value)
    
    def test_formula_update_currency_validation_accepts_none(self):
        """Test that None currency is accepted."""
        formula = FormulaUpdate(
            currency=None,
            created_by="admin@example.com"
        )
        assert formula.currency is None


class TestFormulaRollback:
    """Tests for FormulaRollback schema."""
    
    def test_formula_rollback_with_valid_version(self):
        """Test creating FormulaRollback with valid version number."""
        rollback = FormulaRollback(version_number=2)
        assert rollback.version_number == 2
    
    def test_formula_rollback_version_must_be_positive(self):
        """Test that version_number must be greater than 0."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaRollback(version_number=0)
        # Pydantic's gt constraint provides this error message
        assert "Input should be greater than 0" in str(exc_info.value)
    
    def test_formula_rollback_version_cannot_be_negative(self):
        """Test that negative version_number is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaRollback(version_number=-1)
        # Pydantic's gt constraint provides this error message
        assert "Input should be greater than 0" in str(exc_info.value)
    
    def test_formula_rollback_version_required(self):
        """Test that version_number is required."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaRollback()
        assert "version_number" in str(exc_info.value)


class TestFormulaResponse:
    """Tests for FormulaResponse schema."""
    
    def test_formula_response_with_all_fields(self):
        """Test creating FormulaResponse with all fields."""
        formula_id = uuid4()
        now = datetime.now()
        formula = FormulaResponse(
            id=formula_id,
            country_code="FR",
            formula_code="FR_STANDARD_2024",
            formula_logic="return mtow_kg * 0.06 * distance_km",
            effective_date=date(2024, 1, 1),
            currency="EUR",
            version_number=1,
            is_active=True,
            created_at=now,
            created_by="admin@example.com"
        )
        assert formula.id == formula_id
        assert formula.country_code == "FR"
        assert formula.formula_code == "FR_STANDARD_2024"
        assert formula.version_number == 1
        assert formula.is_active is True
        assert formula.created_at == now
        assert formula.created_by == "admin@example.com"
    
    def test_formula_response_version_number_required(self):
        """Test that version_number is required."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaResponse(
                id=uuid4(),
                country_code="FR",
                formula_code="FR_STANDARD_2024",
                formula_logic="return mtow_kg * 0.06",
                effective_date=date(2024, 1, 1),
                currency="EUR",
                is_active=True,
                created_at=datetime.now(),
                created_by="admin@example.com"
            )
        assert "version_number" in str(exc_info.value)
    
    def test_formula_response_is_active_required(self):
        """Test that is_active is required."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaResponse(
                id=uuid4(),
                country_code="FR",
                formula_code="FR_STANDARD_2024",
                formula_logic="return mtow_kg * 0.06",
                effective_date=date(2024, 1, 1),
                currency="EUR",
                version_number=1,
                created_at=datetime.now(),
                created_by="admin@example.com"
            )
        assert "is_active" in str(exc_info.value)
    
    def test_formula_response_from_attributes_config(self):
        """Test that FormulaResponse has from_attributes config."""
        assert FormulaResponse.model_config.get("from_attributes") is True
    
    def test_formula_response_inherits_validators(self):
        """Test that FormulaResponse inherits validators from FormulaBase."""
        with pytest.raises(ValidationError) as exc_info:
            FormulaResponse(
                id=uuid4(),
                country_code="fr",
                formula_code="FR_STANDARD_2024",
                formula_logic="return mtow_kg * 0.06",
                effective_date=date(2024, 1, 1),
                currency="EUR",
                version_number=1,
                is_active=True,
                created_at=datetime.now(),
                created_by="admin@example.com"
            )
        assert "Country code must be uppercase" in str(exc_info.value)
