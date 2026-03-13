"""Unit tests for Formula SQLAlchemy model."""

import pytest
from datetime import date
from uuid import UUID
from sqlalchemy import inspect
from src.models.formula import Formula


def test_formula_table_name():
    """Test that Formula model has correct table name."""
    assert Formula.__tablename__ == "formulas"


def test_formula_columns():
    """Test that Formula model has all required columns."""
    mapper = inspect(Formula)
    column_names = {col.key for col in mapper.columns}
    
    expected_columns = {
        "id",
        "country_code",
        "description",  # Added for regional formula support
        "formula_code",
        "formula_logic",
        "effective_date",
        "currency",
        "version_number",
        "is_active",
        "created_at",
        "created_by",
    }
    
    assert column_names == expected_columns


def test_formula_primary_key():
    """Test that id is the primary key."""
    mapper = inspect(Formula)
    primary_keys = [col.name for col in mapper.primary_key]
    
    assert primary_keys == ["id"]


def test_formula_indexes():
    """Test that Formula model has required indexes."""
    mapper = inspect(Formula)
    index_names = {idx.name for idx in mapper.local_table.indexes}
    
    expected_indexes = {
        "idx_formulas_country_active",
        "idx_formulas_version",
        "idx_formulas_created_at",
        "unique_active_formula",
    }
    
    assert expected_indexes.issubset(index_names)


def test_formula_unique_constraints():
    """Test that Formula model has required unique constraints."""
    mapper = inspect(Formula)
    constraint_names = {
        constraint.name
        for constraint in mapper.local_table.constraints
        if hasattr(constraint, 'name') and constraint.name
    }
    
    assert "unique_country_version" in constraint_names


def test_formula_nullable_constraints():
    """Test that required columns are not nullable."""
    mapper = inspect(Formula)
    
    # Required columns (not nullable)
    required_columns = {
        "id",
        "description",  # Added for regional formula support
        "formula_code",
        "formula_logic",
        "effective_date",
        "currency",
        "version_number",
        "is_active",
        "created_at",
        "created_by",
    }
    
    # Nullable columns (country_code is nullable for regional formulas)
    nullable_columns = {
        "country_code",
    }
    
    for col in mapper.columns:
        if col.key in required_columns:
            assert not col.nullable, f"Column {col.key} should not be nullable"
        elif col.key in nullable_columns:
            assert col.nullable, f"Column {col.key} should be nullable"


def test_formula_repr():
    """Test the string representation of Formula model."""
    formula = Formula(
        country_code="US",
        formula_code="US_STANDARD",
        formula_logic="return mtow_kg * 0.5",
        effective_date=date(2024, 1, 1),
        currency="USD",
        version_number=1,
        is_active=True,
        created_by="admin",
    )
    
    repr_str = repr(formula)
    assert "US" in repr_str
    assert "version_number=1" in repr_str
    assert "is_active=True" in repr_str


def test_formula_column_types():
    """Test that columns have correct data types."""
    mapper = inspect(Formula)
    
    # Check specific column types
    id_col = mapper.columns["id"]
    assert "UUID" in str(id_col.type)
    
    country_code_col = mapper.columns["country_code"]
    assert str(country_code_col.type) == "VARCHAR(2)"
    
    formula_code_col = mapper.columns["formula_code"]
    assert str(formula_code_col.type) == "VARCHAR(50)"
    
    formula_logic_col = mapper.columns["formula_logic"]
    assert str(formula_logic_col.type) == "TEXT"
    
    currency_col = mapper.columns["currency"]
    assert str(currency_col.type) == "VARCHAR(3)"
    
    version_number_col = mapper.columns["version_number"]
    assert str(version_number_col.type) == "INTEGER"
    
    is_active_col = mapper.columns["is_active"]
    assert str(is_active_col.type) == "BOOLEAN"
    
    created_by_col = mapper.columns["created_by"]
    assert str(created_by_col.type) == "VARCHAR(255)"


def test_formula_default_values():
    """Test that columns have correct default values."""
    mapper = inspect(Formula)
    
    # Check is_active default
    is_active_col = mapper.columns["is_active"]
    assert is_active_col.default is not None
    
    # Check id has UUID default
    id_col = mapper.columns["id"]
    assert id_col.default is not None


def test_formula_composite_index():
    """Test that composite index on (country_code, is_active) exists."""
    mapper = inspect(Formula)
    
    # Find the composite index
    composite_index = None
    for idx in mapper.local_table.indexes:
        if idx.name == "idx_formulas_country_active":
            composite_index = idx
            break
    
    assert composite_index is not None, "Composite index idx_formulas_country_active not found"
    
    # Check that it includes both columns
    index_columns = [col.name for col in composite_index.columns]
    assert "country_code" in index_columns
    assert "is_active" in index_columns


def test_formula_unique_active_constraint():
    """Test that unique partial constraint on (country_code, is_active) WHERE is_active=true exists."""
    mapper = inspect(Formula)
    
    # Find the unique active formula index
    unique_active_index = None
    for idx in mapper.local_table.indexes:
        if idx.name == "unique_active_formula":
            unique_active_index = idx
            break
    
    assert unique_active_index is not None, "Unique active formula index not found"
    assert unique_active_index.unique is True, "Index should be unique"



def test_is_regional_with_null_country_code():
    """Test is_regional() returns True when country_code is None."""
    formula = Formula(
        country_code=None,
        description="EuroControl",
        formula_code="EUROCONTROL_FORMULA",
        formula_logic="return mtow_kg * 0.5",
        effective_date=date(2024, 1, 1),
        currency="EUR",
        version_number=1,
        is_active=True,
        created_by="admin",
    )
    
    assert formula.is_regional() is True


def test_is_regional_with_country_code():
    """Test is_regional() returns False when country_code is not None."""
    formula = Formula(
        country_code="US",
        description="United States",
        formula_code="US_FORMULA",
        formula_logic="return mtow_kg * 0.5",
        effective_date=date(2024, 1, 1),
        currency="USD",
        version_number=1,
        is_active=True,
        created_by="admin",
    )
    
    assert formula.is_regional() is False


def test_is_country_specific_with_country_code():
    """Test is_country_specific() returns True when country_code is not None."""
    formula = Formula(
        country_code="CA",
        description="Canada",
        formula_code="CA_FORMULA",
        formula_logic="return mtow_kg * 0.5",
        effective_date=date(2024, 1, 1),
        currency="CAD",
        version_number=1,
        is_active=True,
        created_by="admin",
    )
    
    assert formula.is_country_specific() is True


def test_is_country_specific_with_null_country_code():
    """Test is_country_specific() returns False when country_code is None."""
    formula = Formula(
        country_code=None,
        description="Oceanic",
        formula_code="OCEANIC_FORMULA",
        formula_logic="return mtow_kg * 0.5",
        effective_date=date(2024, 1, 1),
        currency="USD",
        version_number=1,
        is_active=True,
        created_by="admin",
    )
    
    assert formula.is_country_specific() is False


def test_helper_methods_are_complementary():
    """Test that is_regional() and is_country_specific() are complementary."""
    # Test with regional formula
    regional_formula = Formula(
        country_code=None,
        description="EuroControl",
        formula_code="EUROCONTROL_FORMULA",
        formula_logic="return mtow_kg * 0.5",
        effective_date=date(2024, 1, 1),
        currency="EUR",
        version_number=1,
        is_active=True,
        created_by="admin",
    )
    
    assert regional_formula.is_regional() is True
    assert regional_formula.is_country_specific() is False
    
    # Test with country formula
    country_formula = Formula(
        country_code="US",
        description="United States",
        formula_code="US_FORMULA",
        formula_logic="return mtow_kg * 0.5",
        effective_date=date(2024, 1, 1),
        currency="USD",
        version_number=1,
        is_active=True,
        created_by="admin",
    )
    
    assert country_formula.is_regional() is False
    assert country_formula.is_country_specific() is True
