"""Tests for Formula management API endpoints.

This module tests the REST API endpoints for Formula management:
- GET /api/formulas - List all active formulas
- GET /api/formulas/{country_code} - Get active formula for country
- POST /api/formulas - Create new formula (version 1)
- PUT /api/formulas/{country_code} - Update formula (creates new version)
- DELETE /api/formulas/{country_code} - Delete all formula versions
- GET /api/formulas/{country_code}/history - Get all versions ordered by version DESC
- POST /api/formulas/{country_code}/rollback - Rollback to specified version

Validates Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.7, 3.8, 3.9, 9.6, 11.3, 21.6, 21.7, 21.8, 21.9
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import date, datetime
from uuid import uuid4

from src.models.formula import Formula
from src.exceptions import FormulaNotFoundException, ValidationException


@pytest.fixture
def mock_env_and_db():
    """Mock environment variables and database for testing."""
    env_vars = {
        "DATABASE_URL": "postgresql://user:pass@localhost/db",
        "CORS_ORIGINS": "http://localhost:4200",
        "LOG_LEVEL": "INFO"
    }
    
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = "2a8de75b4840"
    mock_db.execute.return_value = mock_result
    
    with patch.dict(os.environ, env_vars):
        with patch("src.main.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            yield mock_db


@pytest.fixture
def client(mock_env_and_db):
    """Create test client with mocked dependencies."""
    from src.main import app
    return TestClient(app)


@pytest.fixture
def sample_formula():
    """Create a sample Formula object for testing."""
    return Formula(
        id=uuid4(),
        country_code="US",
        formula_code="US_STANDARD",
        formula_logic="def calculate(mtow_kg, distance_km): return mtow_kg * distance_km * 0.05",
        effective_date=date(2024, 1, 1),
        currency="USD",
        version_number=1,
        is_active=True,
        created_at=datetime.now(),
        created_by="admin"
    )


class TestGetAllFormulas:
    """Tests for GET /api/formulas endpoint."""
    
    def test_get_all_formulas_success(self, client, sample_formula):
        """Test successful retrieval of all active formulas."""
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.get_all_active_formulas.return_value = [sample_formula]
            
            response = client.get("/api/formulas")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["country_code"] == "US"
            assert data[0]["formula_code"] == "US_STANDARD"
            assert data[0]["version_number"] == 1
            assert data[0]["is_active"] is True
    
    def test_get_all_formulas_empty(self, client):
        """Test retrieval when no formulas exist."""
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.get_all_active_formulas.return_value = []
            
            response = client.get("/api/formulas")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0


class TestGetFormulaByCountry:
    """Tests for GET /api/formulas/{country_code} endpoint."""
    
    def test_get_formula_success(self, client, sample_formula):
        """Test successful retrieval of formula by country code."""
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.get_active_formula.return_value = sample_formula
            
            response = client.get("/api/formulas/US")
            
            assert response.status_code == 200
            data = response.json()
            assert data["country_code"] == "US"
            assert data["formula_code"] == "US_STANDARD"
            assert data["is_active"] is True
    
    def test_get_formula_not_found(self, client):
        """Test 404 response when formula not found."""
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.get_active_formula.return_value = None
            
            response = client.get("/api/formulas/XX")
            
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "XX" in data["detail"]


class TestCreateFormula:
    """Tests for POST /api/formulas endpoint."""
    
    def test_create_formula_success(self, client, sample_formula):
        """Test successful formula creation."""
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.create_formula.return_value = sample_formula
            
            formula_data = {
                "country_code": "US",
                "formula_code": "US_STANDARD",
                "formula_logic": "def calculate(mtow_kg, distance_km): return mtow_kg * distance_km * 0.05",
                "effective_date": "2024-01-01",
                "currency": "USD",
                "created_by": "admin"
            }
            
            response = client.post("/api/formulas", json=formula_data)
            
            assert response.status_code == 201
            data = response.json()
            assert data["country_code"] == "US"
            assert data["version_number"] == 1
            assert data["is_active"] is True
    
    def test_create_formula_invalid_syntax(self, client):
        """Test 400 response when formula syntax is invalid."""
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.create_formula.side_effect = ValidationException(
                message="Invalid formula syntax: unexpected EOF"
            )
            
            formula_data = {
                "country_code": "US",
                "formula_code": "US_STANDARD",
                "formula_logic": "def calculate(mtow_kg, distance_km):",
                "effective_date": "2024-01-01",
                "currency": "USD",
                "created_by": "admin"
            }
            
            response = client.post("/api/formulas", json=formula_data)
            
            assert response.status_code == 400
            data = response.json()
            assert "syntax" in data["detail"].lower()
    
    def test_create_formula_validation_error(self, client):
        """Test 422 response when input validation fails."""
        formula_data = {
            "country_code": "USA",  # Invalid: should be 2 letters
            "formula_code": "US_STANDARD",
            "formula_logic": "def calculate(mtow_kg, distance_km): return mtow_kg * distance_km * 0.05",
            "effective_date": "2024-01-01",
            "currency": "USD",
            "created_by": "admin"
        }
        
        response = client.post("/api/formulas", json=formula_data)
        
        assert response.status_code == 422


class TestUpdateFormula:
    """Tests for PUT /api/formulas/{country_code} endpoint."""
    
    def test_update_formula_success(self, client):
        """Test successful formula update (creates new version)."""
        updated_formula = Formula(
            id=uuid4(),
            country_code="US",
            formula_code="US_STANDARD_V2",
            formula_logic="def calculate(mtow_kg, distance_km): return mtow_kg * distance_km * 0.06",
            effective_date=date(2024, 6, 1),
            currency="USD",
            version_number=2,
            is_active=True,
            created_at=datetime.now(),
            created_by="admin"
        )
        
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.update_formula.return_value = updated_formula
            
            update_data = {
                "formula_code": "US_STANDARD_V2",
                "formula_logic": "def calculate(mtow_kg, distance_km): return mtow_kg * distance_km * 0.06",
                "effective_date": "2024-06-01",
                "currency": "USD",
                "created_by": "admin"
            }
            
            response = client.put("/api/formulas/US", json=update_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["country_code"] == "US"
            assert data["version_number"] == 2
            assert data["is_active"] is True
    
    def test_update_formula_not_found(self, client):
        """Test 404 response when formula not found for update."""
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.update_formula.side_effect = FormulaNotFoundException(
                message="No active formula found for country code: XX"
            )
            
            update_data = {
                "formula_code": "XX_STANDARD",
                "created_by": "admin"
            }
            
            response = client.put("/api/formulas/XX", json=update_data)
            
            assert response.status_code == 404
    
    def test_update_formula_invalid_syntax(self, client):
        """Test 400 response when updated formula syntax is invalid."""
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.update_formula.side_effect = ValidationException(
                message="Invalid formula syntax: unexpected EOF"
            )
            
            update_data = {
                "formula_logic": "def calculate(mtow_kg, distance_km):",
                "created_by": "admin"
            }
            
            response = client.put("/api/formulas/US", json=update_data)
            
            assert response.status_code == 400


class TestDeleteFormula:
    """Tests for DELETE /api/formulas/{country_code} endpoint."""
    
    def test_delete_formula_success(self, client):
        """Test successful deletion of all formula versions."""
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.delete_formula.return_value = True
            
            response = client.delete("/api/formulas/US")
            
            assert response.status_code == 204
    
    def test_delete_formula_not_found(self, client):
        """Test 404 response when formula not found for deletion."""
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.delete_formula.side_effect = FormulaNotFoundException(
                message="No formulas found for country code: XX"
            )
            
            response = client.delete("/api/formulas/XX")
            
            assert response.status_code == 404


class TestGetFormulaHistory:
    """Tests for GET /api/formulas/{country_code}/history endpoint."""
    
    def test_get_formula_history_success(self, client):
        """Test successful retrieval of formula version history."""
        formulas = [
            Formula(
                id=uuid4(),
                country_code="US",
                formula_code="US_STANDARD_V2",
                formula_logic="def calculate(mtow_kg, distance_km): return mtow_kg * distance_km * 0.06",
                effective_date=date(2024, 6, 1),
                currency="USD",
                version_number=2,
                is_active=True,
                created_at=datetime.now(),
                created_by="admin"
            ),
            Formula(
                id=uuid4(),
                country_code="US",
                formula_code="US_STANDARD",
                formula_logic="def calculate(mtow_kg, distance_km): return mtow_kg * distance_km * 0.05",
                effective_date=date(2024, 1, 1),
                currency="USD",
                version_number=1,
                is_active=False,
                created_at=datetime.now(),
                created_by="admin"
            )
        ]
        
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.get_formula_history.return_value = formulas
            
            response = client.get("/api/formulas/US/history")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["version_number"] == 2
            assert data[0]["is_active"] is True
            assert data[1]["version_number"] == 1
            assert data[1]["is_active"] is False
    
    def test_get_formula_history_not_found(self, client):
        """Test 404 response when no formula history exists."""
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.get_formula_history.side_effect = FormulaNotFoundException(
                message="No formula history found for country code: XX"
            )
            
            response = client.get("/api/formulas/XX/history")
            
            assert response.status_code == 404


class TestRollbackFormula:
    """Tests for POST /api/formulas/{country_code}/rollback endpoint."""
    
    def test_rollback_formula_success(self, client):
        """Test successful formula rollback to previous version."""
        rolled_back_formula = Formula(
            id=uuid4(),
            country_code="US",
            formula_code="US_STANDARD",
            formula_logic="def calculate(mtow_kg, distance_km): return mtow_kg * distance_km * 0.05",
            effective_date=date(2024, 1, 1),
            currency="USD",
            version_number=1,
            is_active=True,
            created_at=datetime.now(),
            created_by="admin"
        )
        
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.rollback_formula.return_value = rolled_back_formula
            
            rollback_data = {"version_number": 1}
            
            response = client.post("/api/formulas/US/rollback", json=rollback_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["country_code"] == "US"
            assert data["version_number"] == 1
            assert data["is_active"] is True
    
    def test_rollback_formula_version_not_found(self, client):
        """Test 404 response when specified version doesn't exist."""
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            mock_service.return_value.rollback_formula.side_effect = FormulaNotFoundException(
                message="Formula version 99 not found for country code: US"
            )
            
            rollback_data = {"version_number": 99}
            
            response = client.post("/api/formulas/US/rollback", json=rollback_data)
            
            assert response.status_code == 404
    
    def test_rollback_formula_validation_error(self, client):
        """Test 422 response when version_number is invalid."""
        rollback_data = {"version_number": 0}  # Invalid: must be > 0
        
        response = client.post("/api/formulas/US/rollback", json=rollback_data)
        
        assert response.status_code == 422
