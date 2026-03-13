"""Unit tests for RouteCalculation SQLAlchemy model."""

import pytest
from decimal import Decimal
from sqlalchemy import inspect
from src.models.route_calculation import RouteCalculation


def test_route_calculation_table_name():
    """Test that RouteCalculation model has correct table name."""
    assert RouteCalculation.__tablename__ == "route_calculations"


def test_route_calculation_columns():
    """Test that RouteCalculation model has all required columns."""
    mapper = inspect(RouteCalculation)
    column_names = {col.key for col in mapper.columns}
    
    expected_columns = {
        "id",
        "route_string",
        "origin",
        "destination",
        "aircraft_type",
        "mtow_kg",
        "total_cost",
        "currency",
        "calculation_timestamp",
    }
    
    assert column_names == expected_columns


def test_route_calculation_primary_key():
    """Test that id is the primary key."""
    mapper = inspect(RouteCalculation)
    primary_keys = [col.name for col in mapper.primary_key]
    
    assert primary_keys == ["id"]


def test_route_calculation_indexes():
    """Test that RouteCalculation model has required indexes."""
    mapper = inspect(RouteCalculation)
    index_names = {idx.name for idx in mapper.local_table.indexes}
    
    expected_indexes = {
        "idx_route_calculations_timestamp",
        "idx_route_calculations_origin",
        "idx_route_calculations_destination",
    }
    
    assert expected_indexes.issubset(index_names)


def test_route_calculation_nullable_constraints():
    """Test that required columns are not nullable."""
    mapper = inspect(RouteCalculation)
    
    # All columns are required (not nullable)
    required_columns = {
        "id",
        "route_string",
        "origin",
        "destination",
        "aircraft_type",
        "mtow_kg",
        "total_cost",
        "currency",
        "calculation_timestamp",
    }
    
    for col in mapper.columns:
        if col.key in required_columns:
            assert not col.nullable, f"Column {col.key} should not be nullable"


def test_route_calculation_repr():
    """Test the string representation of RouteCalculation model."""
    calculation = RouteCalculation(
        route_string="KJFK DCT CYYZ",
        origin="KJFK",
        destination="CYYZ",
        aircraft_type="B737",
        mtow_kg=Decimal("70000.00"),
        total_cost=Decimal("1500.00"),
        currency="USD",
    )
    
    repr_str = repr(calculation)
    assert "KJFK" in repr_str
    assert "CYYZ" in repr_str
    assert "total_cost=1500.00" in repr_str


def test_route_calculation_column_types():
    """Test that columns have correct data types."""
    mapper = inspect(RouteCalculation)
    
    # Check specific column types
    id_col = mapper.columns["id"]
    assert "UUID" in str(id_col.type)
    
    route_string_col = mapper.columns["route_string"]
    assert str(route_string_col.type) == "TEXT"
    
    origin_col = mapper.columns["origin"]
    assert str(origin_col.type) == "VARCHAR(4)"
    
    destination_col = mapper.columns["destination"]
    assert str(destination_col.type) == "VARCHAR(4)"
    
    aircraft_type_col = mapper.columns["aircraft_type"]
    assert str(aircraft_type_col.type) == "VARCHAR(10)"
    
    mtow_kg_col = mapper.columns["mtow_kg"]
    assert "DECIMAL" in str(mtow_kg_col.type)
    
    total_cost_col = mapper.columns["total_cost"]
    assert "DECIMAL" in str(total_cost_col.type)
    
    currency_col = mapper.columns["currency"]
    assert str(currency_col.type) == "VARCHAR(3)"
    
    calculation_timestamp_col = mapper.columns["calculation_timestamp"]
    assert "TIMESTAMP" in str(calculation_timestamp_col.type)


def test_route_calculation_default_values():
    """Test that columns have correct default values."""
    mapper = inspect(RouteCalculation)
    
    # Check id has UUID default
    id_col = mapper.columns["id"]
    assert id_col.default is not None
    
    # Check calculation_timestamp has server default
    timestamp_col = mapper.columns["calculation_timestamp"]
    assert timestamp_col.server_default is not None


def test_route_calculation_timestamp_index():
    """Test that index on calculation_timestamp exists."""
    mapper = inspect(RouteCalculation)
    
    # Find the timestamp index
    timestamp_index = None
    for idx in mapper.local_table.indexes:
        if idx.name == "idx_route_calculations_timestamp":
            timestamp_index = idx
            break
    
    assert timestamp_index is not None, "Index idx_route_calculations_timestamp not found"
    
    # Check that it includes calculation_timestamp column
    index_columns = [col.name for col in timestamp_index.columns]
    assert "calculation_timestamp" in index_columns


def test_route_calculation_origin_index():
    """Test that index on origin exists."""
    mapper = inspect(RouteCalculation)
    
    # Find the origin index
    origin_index = None
    for idx in mapper.local_table.indexes:
        if idx.name == "idx_route_calculations_origin":
            origin_index = idx
            break
    
    assert origin_index is not None, "Index idx_route_calculations_origin not found"
    
    # Check that it includes origin column
    index_columns = [col.name for col in origin_index.columns]
    assert "origin" in index_columns


def test_route_calculation_destination_index():
    """Test that index on destination exists."""
    mapper = inspect(RouteCalculation)
    
    # Find the destination index
    destination_index = None
    for idx in mapper.local_table.indexes:
        if idx.name == "idx_route_calculations_destination":
            destination_index = idx
            break
    
    assert destination_index is not None, "Index idx_route_calculations_destination not found"
    
    # Check that it includes destination column
    index_columns = [col.name for col in destination_index.columns]
    assert "destination" in index_columns


def test_route_calculation_decimal_precision():
    """Test that DECIMAL columns have correct precision and scale."""
    mapper = inspect(RouteCalculation)
    
    # Check mtow_kg precision (10, 2)
    mtow_kg_col = mapper.columns["mtow_kg"]
    assert mtow_kg_col.type.precision == 10
    assert mtow_kg_col.type.scale == 2
    
    # Check total_cost precision (12, 2)
    total_cost_col = mapper.columns["total_cost"]
    assert total_cost_col.type.precision == 12
    assert total_cost_col.type.scale == 2
