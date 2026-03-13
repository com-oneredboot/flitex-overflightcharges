"""Tests for Route Cost calculation API endpoint.

This module tests the REST API endpoint for route cost calculation:
- POST /api/route-costs - Calculate route cost

Validates Requirements: 5.1, 5.2, 5.8, 5.9, 9.6, 11.5
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from decimal import Decimal
from uuid import uuid4

from src.schemas.route_cost import RouteCostResponse, FIRChargeBreakdown
from src.exceptions import ParsingException, ValidationException


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def client(mock_db):
    """Create test client with mocked dependencies."""
    env_vars = {
        "DATABASE_URL": "postgresql://user:pass@localhost/db",
        "CORS_ORIGINS": "http://localhost:4200",
        "LOG_LEVEL": "INFO"
    }
    
    # Mock the schema verification
    mock_result = MagicMock()
    mock_result.scalar.return_value = "2a8de75b4840"
    mock_db.execute.return_value = mock_result
    mock_db.close = MagicMock()
    
    with patch.dict(os.environ, env_vars):
        with patch("src.main.get_db") as mock_get_db:
            # Mock get_db to return our mock session
            mock_get_db.return_value = iter([mock_db])
            
            # Import app after patching
            from src.main import app
            from src.database import get_db
            
            # Override the dependency
            def override_get_db():
                yield mock_db
            
            app.dependency_overrides[get_db] = override_get_db
            
            yield TestClient(app)
            
            # Clean up
            app.dependency_overrides.clear()


@pytest.fixture
def sample_route_cost_response():
    """Create a sample route cost response for testing."""
    calculation_id = uuid4()
    return RouteCostResponse(
        calculation_id=calculation_id,
        total_cost=Decimal("25200.00"),
        currency="USD",
        fir_breakdown=[
            FIRChargeBreakdown(
                icao_code="KZNY",
                fir_name="New York FIR",
                country_code="US",
                charge_amount=Decimal("25200.00"),
                currency="USD"
            )
        ]
    )


class TestCalculateRouteCost:
    """Tests for POST /api/route-costs endpoint."""
    
    def test_calculate_route_cost_success(self, client, sample_route_cost_response):
        """Test successful route cost calculation."""
        with patch("src.routes.route_cost_routes.CostCalculator") as mock_calculator:
            mock_calculator.return_value.calculate_route_cost.return_value = sample_route_cost_response
            
            request_data = {
                "route_string": "KJFK DCT CYYZ",
                "origin": "KJFK",
                "destination": "CYYZ",
                "aircraft_type": "B738",
                "mtow_kg": 79000.0
            }
            
            response = client.post("/api/route-costs", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "calculation_id" in data
            assert "total_cost" in data
            assert "currency" in data
            assert "fir_breakdown" in data
            assert data["currency"] == "USD"
            assert len(data["fir_breakdown"]) == 1
            assert data["fir_breakdown"][0]["icao_code"] == "KZNY"
    
    def test_calculate_route_cost_invalid_route_string(self, client):
        """Test 400 response for invalid route string."""
        with patch("src.routes.route_cost_routes.CostCalculator") as mock_calculator:
            mock_calculator.return_value.calculate_route_cost.side_effect = ParsingException(
                "Invalid route format"
            )
            
            request_data = {
                "route_string": "INVALID",
                "origin": "KJFK",
                "destination": "CYYZ",
                "aircraft_type": "B738",
                "mtow_kg": 79000.0
            }
            
            response = client.post("/api/route-costs", json=request_data)
            
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
    
    def test_calculate_route_cost_validation_error_missing_fields(self, client):
        """Test 422 response for missing required fields."""
        request_data = {
            "route_string": "KJFK DCT CYYZ",
            # Missing origin, destination, aircraft_type, mtow_kg
        }
        
        response = client.post("/api/route-costs", json=request_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_calculate_route_cost_validation_error_invalid_mtow(self, client):
        """Test 422 response for invalid MTOW (must be > 0)."""
        request_data = {
            "route_string": "KJFK DCT CYYZ",
            "origin": "KJFK",
            "destination": "CYYZ",
            "aircraft_type": "B738",
            "mtow_kg": -1000.0  # Invalid: negative
        }
        
        response = client.post("/api/route-costs", json=request_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_calculate_route_cost_validation_error_invalid_icao_code(self, client):
        """Test 422 response for invalid ICAO code format."""
        request_data = {
            "route_string": "KJFK DCT CYYZ",
            "origin": "KJ",  # Invalid: too short
            "destination": "CYYZ",
            "aircraft_type": "B738",
            "mtow_kg": 79000.0
        }
        
        response = client.post("/api/route-costs", json=request_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_calculate_route_cost_empty_fir_breakdown(self, client):
        """Test calculation with no FIR crossings."""
        calculation_id = uuid4()
        empty_response = RouteCostResponse(
            calculation_id=calculation_id,
            total_cost=Decimal("0.00"),
            currency="USD",
            fir_breakdown=[]
        )
        
        with patch("src.routes.route_cost_routes.CostCalculator") as mock_calculator:
            mock_calculator.return_value.calculate_route_cost.return_value = empty_response
            
            request_data = {
                "route_string": "KJFK",
                "origin": "KJFK",
                "destination": "KJFK",
                "aircraft_type": "B738",
                "mtow_kg": 79000.0
            }
            
            response = client.post("/api/route-costs", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            assert float(data["total_cost"]) == 0.0
            assert len(data["fir_breakdown"]) == 0
    
    def test_calculate_route_cost_multiple_firs(self, client):
        """Test calculation with multiple FIR crossings."""
        calculation_id = uuid4()
        multi_fir_response = RouteCostResponse(
            calculation_id=calculation_id,
            total_cost=Decimal("64000.00"),
            currency="USD",
            fir_breakdown=[
                FIRChargeBreakdown(
                    icao_code="KZNY",
                    fir_name="New York FIR",
                    country_code="US",
                    charge_amount=Decimal("40000.00"),
                    currency="USD"
                ),
                FIRChargeBreakdown(
                    icao_code="CZYZ",
                    fir_name="Toronto FIR",
                    country_code="CA",
                    charge_amount=Decimal("24000.00"),
                    currency="USD"
                )
            ]
        )
        
        with patch("src.routes.route_cost_routes.CostCalculator") as mock_calculator:
            mock_calculator.return_value.calculate_route_cost.return_value = multi_fir_response
            
            request_data = {
                "route_string": "KJFK DCT CYYZ",
                "origin": "KJFK",
                "destination": "CYYZ",
                "aircraft_type": "B738",
                "mtow_kg": 80000.0
            }
            
            response = client.post("/api/route-costs", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            assert float(data["total_cost"]) == 64000.0
            assert len(data["fir_breakdown"]) == 2
            assert data["fir_breakdown"][0]["icao_code"] == "KZNY"
            assert data["fir_breakdown"][1]["icao_code"] == "CZYZ"
