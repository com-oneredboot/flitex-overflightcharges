"""Unit tests for IataFir SQLAlchemy model."""

import pytest
from decimal import Decimal
from sqlalchemy import inspect
from src.models.iata_fir import IataFir


def test_iata_fir_table_name():
    """Test that IataFir model has correct table name."""
    assert IataFir.__tablename__ == "iata_firs"


def test_iata_fir_columns():
    """Test that IataFir model has all required columns."""
    mapper = inspect(IataFir)
    column_names = {col.key for col in mapper.columns}
    
    expected_columns = {
        "icao_code",
        "fir_name",
        "country_code",
        "country_name",
        "geojson_geometry",
        "bbox_min_lon",
        "bbox_min_lat",
        "bbox_max_lon",
        "bbox_max_lat",
        "avoid_status",
        "created_at",
        "updated_at",
    }
    
    assert column_names == expected_columns


def test_iata_fir_primary_key():
    """Test that icao_code is the primary key."""
    mapper = inspect(IataFir)
    primary_keys = [col.name for col in mapper.primary_key]
    
    assert primary_keys == ["icao_code"]


def test_iata_fir_indexes():
    """Test that IataFir model has required indexes."""
    mapper = inspect(IataFir)
    index_names = {idx.name for idx in mapper.local_table.indexes}
    
    expected_indexes = {
        "idx_iata_firs_country_code",
        "idx_iata_firs_avoid_status",
    }
    
    assert expected_indexes.issubset(index_names)


def test_iata_fir_nullable_constraints():
    """Test that required columns are not nullable."""
    mapper = inspect(IataFir)
    
    # Required columns (not nullable)
    required_columns = {
        "icao_code",
        "fir_name",
        "country_code",
        "country_name",
        "geojson_geometry",
        "created_at",
        "updated_at",
    }
    
    for col in mapper.columns:
        if col.key in required_columns:
            assert not col.nullable, f"Column {col.key} should not be nullable"


def test_iata_fir_optional_columns():
    """Test that optional columns are nullable."""
    mapper = inspect(IataFir)
    
    # Optional columns (nullable)
    optional_columns = {
        "bbox_min_lon",
        "bbox_min_lat",
        "bbox_max_lon",
        "bbox_max_lat",
    }
    
    for col in mapper.columns:
        if col.key in optional_columns:
            assert col.nullable, f"Column {col.key} should be nullable"


def test_iata_fir_repr():
    """Test the string representation of IataFir model."""
    fir = IataFir(
        icao_code="KJFK",
        fir_name="New York FIR",
        country_code="US",
        country_name="United States",
        geojson_geometry={"type": "Polygon", "coordinates": []},
    )
    
    repr_str = repr(fir)
    assert "KJFK" in repr_str
    assert "New York FIR" in repr_str
    assert "US" in repr_str


def test_iata_fir_column_types():
    """Test that columns have correct data types."""
    mapper = inspect(IataFir)
    
    # Check specific column types
    icao_code_col = mapper.columns["icao_code"]
    assert str(icao_code_col.type) == "VARCHAR(4)"
    
    fir_name_col = mapper.columns["fir_name"]
    assert str(fir_name_col.type) == "VARCHAR(255)"
    
    country_code_col = mapper.columns["country_code"]
    assert str(country_code_col.type) == "VARCHAR(2)"
    
    avoid_status_col = mapper.columns["avoid_status"]
    assert str(avoid_status_col.type) == "BOOLEAN"
    
    # Check DECIMAL columns
    bbox_min_lon_col = mapper.columns["bbox_min_lon"]
    assert "DECIMAL" in str(bbox_min_lon_col.type)
