"""Unit tests for FirCharge SQLAlchemy model."""

import pytest
from decimal import Decimal
from sqlalchemy import inspect
from src.models.fir_charge import FirCharge


def test_fir_charge_table_name():
    """Test that FirCharge model has correct table name."""
    assert FirCharge.__tablename__ == "fir_charges"


def test_fir_charge_columns():
    """Test that FirCharge model has all required columns."""
    mapper = inspect(FirCharge)
    column_names = {col.key for col in mapper.columns}
    
    expected_columns = {
        "id",
        "calculation_id",
        "icao_code",
        "fir_name",
        "country_code",
        "charge_amount",
        "currency",
    }
    
    assert column_names == expected_columns


def test_fir_charge_primary_key():
    """Test that id is the primary key."""
    mapper = inspect(FirCharge)
    primary_keys = [col.name for col in mapper.primary_key]
    
    assert primary_keys == ["id"]


def test_fir_charge_indexes():
    """Test that FirCharge model has required indexes (Requirements 22.10, 22.11, 22.12)."""
    mapper = inspect(FirCharge)
    index_names = {idx.name for idx in mapper.local_table.indexes}
    
    expected_indexes = {
        "idx_fir_charges_calculation_id",
        "idx_fir_charges_icao_code",
        "idx_fir_charges_country_code",
    }
    
    assert expected_indexes.issubset(index_names)


def test_fir_charge_foreign_keys():
    """Test that FirCharge model has required foreign keys (Requirements 22.13, 22.14)."""
    mapper = inspect(FirCharge)
    
    # Get foreign key constraints
    foreign_keys = mapper.local_table.foreign_keys
    
    # Should have 2 foreign keys
    assert len(foreign_keys) == 2
    
    # Check calculation_id foreign key
    calculation_fk = None
    icao_code_fk = None
    
    for fk in foreign_keys:
        if fk.parent.name == "calculation_id":
            calculation_fk = fk
        elif fk.parent.name == "icao_code":
            icao_code_fk = fk
    
    # Verify calculation_id foreign key (Requirement 22.13)
    assert calculation_fk is not None, "Foreign key on calculation_id not found"
    assert calculation_fk.column.table.name == "route_calculations"
    assert calculation_fk.column.name == "id"
    assert calculation_fk.ondelete == "CASCADE", "Foreign key should have CASCADE on delete"
    
    # Verify icao_code foreign key (Requirement 22.14)
    assert icao_code_fk is not None, "Foreign key on icao_code not found"
    assert icao_code_fk.column.table.name == "iata_firs"
    assert icao_code_fk.column.name == "icao_code"


def test_fir_charge_nullable_constraints():
    """Test that required columns are not nullable."""
    mapper = inspect(FirCharge)
    
    # All columns are required (not nullable)
    required_columns = {
        "id",
        "calculation_id",
        "icao_code",
        "fir_name",
        "country_code",
        "charge_amount",
        "currency",
    }
    
    for col in mapper.columns:
        if col.key in required_columns:
            assert not col.nullable, f"Column {col.key} should not be nullable"


def test_fir_charge_repr():
    """Test the string representation of FirCharge model."""
    fir_charge = FirCharge(
        icao_code="KZNY",
        fir_name="New York FIR",
        country_code="US",
        charge_amount=Decimal("250.00"),
        currency="USD",
    )
    
    repr_str = repr(fir_charge)
    assert "KZNY" in repr_str
    assert "New York FIR" in repr_str
    assert "charge_amount=250.00" in repr_str


def test_fir_charge_column_types():
    """Test that columns have correct data types."""
    mapper = inspect(FirCharge)
    
    # Check specific column types
    id_col = mapper.columns["id"]
    assert "UUID" in str(id_col.type)
    
    calculation_id_col = mapper.columns["calculation_id"]
    assert "UUID" in str(calculation_id_col.type)
    
    icao_code_col = mapper.columns["icao_code"]
    assert str(icao_code_col.type) == "VARCHAR(4)"
    
    fir_name_col = mapper.columns["fir_name"]
    assert str(fir_name_col.type) == "VARCHAR(255)"
    
    country_code_col = mapper.columns["country_code"]
    assert str(country_code_col.type) == "VARCHAR(2)"
    
    charge_amount_col = mapper.columns["charge_amount"]
    assert "DECIMAL" in str(charge_amount_col.type)
    
    currency_col = mapper.columns["currency"]
    assert str(currency_col.type) == "VARCHAR(3)"


def test_fir_charge_default_values():
    """Test that columns have correct default values."""
    mapper = inspect(FirCharge)
    
    # Check id has UUID default
    id_col = mapper.columns["id"]
    assert id_col.default is not None


def test_fir_charge_calculation_id_index():
    """Test that index on calculation_id exists (Requirement 22.10)."""
    mapper = inspect(FirCharge)
    
    # Find the calculation_id index
    calculation_id_index = None
    for idx in mapper.local_table.indexes:
        if idx.name == "idx_fir_charges_calculation_id":
            calculation_id_index = idx
            break
    
    assert calculation_id_index is not None, "Index idx_fir_charges_calculation_id not found"
    
    # Check that it includes calculation_id column
    index_columns = [col.name for col in calculation_id_index.columns]
    assert "calculation_id" in index_columns


def test_fir_charge_icao_code_index():
    """Test that index on icao_code exists (Requirement 22.11)."""
    mapper = inspect(FirCharge)
    
    # Find the icao_code index
    icao_code_index = None
    for idx in mapper.local_table.indexes:
        if idx.name == "idx_fir_charges_icao_code":
            icao_code_index = idx
            break
    
    assert icao_code_index is not None, "Index idx_fir_charges_icao_code not found"
    
    # Check that it includes icao_code column
    index_columns = [col.name for col in icao_code_index.columns]
    assert "icao_code" in index_columns


def test_fir_charge_country_code_index():
    """Test that index on country_code exists (Requirement 22.12)."""
    mapper = inspect(FirCharge)
    
    # Find the country_code index
    country_code_index = None
    for idx in mapper.local_table.indexes:
        if idx.name == "idx_fir_charges_country_code":
            country_code_index = idx
            break
    
    assert country_code_index is not None, "Index idx_fir_charges_country_code not found"
    
    # Check that it includes country_code column
    index_columns = [col.name for col in country_code_index.columns]
    assert "country_code" in index_columns


def test_fir_charge_decimal_precision():
    """Test that DECIMAL columns have correct precision and scale."""
    mapper = inspect(FirCharge)
    
    # Check charge_amount precision (12, 2)
    charge_amount_col = mapper.columns["charge_amount"]
    assert charge_amount_col.type.precision == 12
    assert charge_amount_col.type.scale == 2


def test_fir_charge_relationships():
    """Test that FirCharge model has correct relationships."""
    mapper = inspect(FirCharge)
    
    # Check that relationships exist
    relationships = {rel.key for rel in mapper.relationships}
    
    expected_relationships = {"calculation", "fir"}
    assert expected_relationships.issubset(relationships)
