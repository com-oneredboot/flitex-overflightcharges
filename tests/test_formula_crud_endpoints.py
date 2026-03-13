"""Integration tests for Formula CRUD endpoints (Task 10).

This module tests the new REST API endpoints for Formula execution system:
- GET /api/formulas/bulk - Get all formulas with bytecode
- GET /api/formulas/{formula_id}/full - Get formula by ID (full record)
- GET /api/formulas/execution-context - Get execution context
- POST /api/formulas/validate - Create formula with validation
- PUT /api/formulas/{formula_id}/update - Update formula
- DELETE /api/formulas/{formula_id}/delete - Delete formula

Validates Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 1.2, 1.3, 3.1-3.8, 5.1, 5.2, 10.3, 11.1-11.10
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import date, datetime
from uuid import uuid4
import base64

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
def sample_formula_with_bytecode():
    """Create a sample Formula object with bytecode for testing."""
    import marshal
    code = compile("def calculate(distance, weight, context): return {'cost': 100, 'currency': 'USD', 'usd_cost': 100}", "<test>", "exec")
    bytecode = marshal.dumps(code)
    
    return Formula(
        id=uuid4(),
        country_code="US",
        description="United States",
        formula_code="US_STANDARD",
        formula_logic="def calculate(distance, weight, context): return {'cost': 100, 'currency': 'USD', 'usd_cost': 100}",
        effective_date=date(2024, 1, 1),
        currency="USD",
        version_number=1,
        is_active=True,
        created_at=datetime.now(),
        created_by="admin",
        formula_hash="abc123def456",
        formula_bytecode=bytecode
    )


class TestGetAllFormulasWithBytecode:
    """Tests for GET /api/formulas/bulk endpoint."""
    
    def test_get_all_formulas_with_bytecode_success(self, client, sample_formula_with_bytecode):
        """Test successful retrieval of all formulas with bytecode."""
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            with patch("src.routes.formula_routes.get_redis_client") as mock_redis:
                mock_redis.return_value = None  # Disable cache for test
                mock_service.return_value.get_all_active_formulas.return_value = [sample_formula_with_bytecode]
                
                response = client.get("/api/formulas/bulk")
                
                assert response.status_code == 200
                data = response.json()
                assert "formulas" in data
                assert "US" in data["formulas"]
                assert data["formulas"]["US"]["country_code"] == "US"
                assert "bytecode" in data["formulas"]["US"]
                assert data["formulas"]["US"]["version"] == 1
                assert "cached_at" in data
                assert "cache_ttl_seconds" in data
    
    def test_get_all_formulas_with_bytecode_regional(self, client):
        """Test retrieval includes regional formulas with EuroControl key."""
        regional_formula = Formula(
            id=uuid4(),
            country_code=None,  # Regional formula
            description="EuroControl",
            formula_code="EUROCONTROL",
            formula_logic="def calculate(distance, weight, context): return {'cost': 200, 'currency': 'EUR', 'usd_cost': 220}",
            effective_date=date(2024, 1, 1),
            currency="EUR",
            version_number=1,
            is_active=True,
            created_at=datetime.now(),
            created_by="admin",
            formula_hash="xyz789abc123",
            formula_bytecode=b"bytecode"
        )
        
        with patch("src.routes.formula_routes.FormulaService") as mock_service:
            with patch("src.routes.formula_routes.get_redis_client") as mock_redis:
                mock_redis.return_value = None
                mock_service.return_value.get_all_active_formulas.return_value = [regional_formula]
                
                response = client.get("/api/formulas/bulk")
                
                assert response.status_code == 200
                data = response.json()
                assert "EuroControl" in data["formulas"]
                assert data["formulas"]["EuroControl"]["country_code"] is None


class TestGetFormulaById:
    """Tests for GET /api/formulas/{formula_id}/full endpoint."""
    
    def test_get_formula_by_id_success(self, client, sample_formula_with_bytecode):
        """Test successful retrieval of formula by ID."""
        formula_id = str(sample_formula_with_bytecode.id)
        
        with patch("src.routes.formula_routes.Formula") as mock_formula_model:
            mock_query = MagicMock()
            mock_query.filter.return_value.first.return_value = sample_formula_with_bytecode
            
            with patch("src.database.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.query.return_value = mock_query
                mock_get_db.return_value = iter([mock_db])
                
                response = client.get(f"/api/formulas/{formula_id}/full")
                
                assert response.status_code == 200
                data = response.json()
                assert data["id"] == formula_id
                assert data["country_code"] == "US"
                assert data["formula_code_id"] == "US_STANDARD"
                assert "formula_code" in data
                assert "bytecode" in data
                assert data["version"] == 1
                assert data["formula_hash"] == "abc123def456"
    
    def test_get_formula_by_id_not_found(self, client):
        """Test 404 response when formula not found."""
        formula_id = str(uuid4())
        
        with patch("src.routes.formula_routes.Formula") as mock_formula_model:
            mock_query = MagicMock()
            mock_query.filter.return_value.first.return_value = None
            
            with patch("src.database.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.query.return_value = mock_query
                mock_get_db.return_value = iter([mock_db])
                
                response = client.get(f"/api/formulas/{formula_id}/full")
                
                assert response.status_code == 404
    
    def test_get_formula_by_id_invalid_uuid(self, client):
        """Test 404 response when UUID format is invalid."""
        response = client.get("/api/formulas/invalid-uuid/full")
        
        assert response.status_code == 404


class TestGetFormulaExecutionContext:
    """Tests for GET /api/formulas/execution-context endpoint."""
    
    def test_get_execution_context_success(self, client):
        """Test successful retrieval of execution context."""
        with patch("src.routes.formula_routes.ConstantsProvider") as mock_provider:
            with patch("src.routes.formula_routes.EuroControlRateLoader") as mock_loader:
                with patch("src.routes.formula_routes.get_redis_client") as mock_redis:
                    mock_redis.return_value = None
                    
                    # Mock constants provider
                    mock_provider.return_value.get_execution_context.return_value = {
                        "CURRENCY_CONSTANTS": {"USD": "USD", "EUR": "EUR"},
                        "COUNTRY_NAME_CONSTANTS": {"USA": "United States"},
                        "FIR_NAMES_PER_COUNTRY": {"USA": ["KZAB"]},
                        "CANADA_TSC_AERODROMES": []
                    }
                    
                    # Mock rate loader
                    mock_loader.return_value.load_rates.return_value = {
                        "GB": {"2024-01-01": {"unit_rate": 85.50}}
                    }
                    
                    response = client.get("/api/formulas/execution-context")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert "constants" in data
                    assert "utilities" in data
                    assert "math_functions" in data
                    assert "eurocontrol_rates" in data
                    assert "cached_at" in data
                    assert "cache_ttl_seconds" in data
                    assert data["math_functions"] == ["sqrt", "pow", "abs", "ceil", "floor", "round"]


class TestCreateFormulaWithValidation:
    """Tests for POST /api/formulas/validate endpoint."""
    
    def test_create_formula_with_validation_success(self, client, sample_formula_with_bytecode):
        """Test successful formula creation with validation."""
        with patch("src.routes.formula_routes.FormulaValidator") as mock_validator:
            with patch("src.routes.formula_routes.FormulaExecutor"):
                with patch("src.routes.formula_routes.FormulaCache"):
                    with patch("src.routes.formula_routes.ConstantsProvider"):
                        with patch("src.routes.formula_routes.EuroControlRateLoader"):
                            with patch("src.routes.formula_routes.get_redis_client") as mock_redis:
                                mock_redis.return_value = None
                                mock_validator.return_value.validate_and_save.return_value = sample_formula_with_bytecode
                                
                                formula_data = {
                                    "formula_code": "def calculate(distance, weight, context): return {'cost': 100, 'currency': 'USD', 'usd_cost': 100}",
                                    "country_code": "US",
                                    "description": "United States",
                                    "formula_code_id": "US_STANDARD",
                                    "effective_date": "2024-01-01",
                                    "currency": "USD",
                                    "created_by": "admin"
                                }
                                
                                response = client.post("/api/formulas/validate", json=formula_data)
                                
                                assert response.status_code == 201
                                data = response.json()
                                assert "id" in data
                                assert "formula_hash" in data
                                assert "version" in data
                                assert "message" in data
                                assert data["version"] == 1
    
    def test_create_formula_validation_error(self, client):
        """Test 400 response when validation fails."""
        from src.exceptions import ValidationException
        
        with patch("src.routes.formula_routes.FormulaValidator") as mock_validator:
            with patch("src.routes.formula_routes.FormulaExecutor"):
                with patch("src.routes.formula_routes.FormulaCache"):
                    with patch("src.routes.formula_routes.ConstantsProvider"):
                        with patch("src.routes.formula_routes.EuroControlRateLoader"):
                            with patch("src.routes.formula_routes.get_redis_client") as mock_redis:
                                mock_redis.return_value = None
                                mock_validator.return_value.validate_and_save.side_effect = ValidationException(
                                    message="Invalid formula syntax"
                                )
                                
                                formula_data = {
                                    "formula_code": "def calculate(distance, weight, context):",
                                    "country_code": "US",
                                    "description": "United States",
                                    "formula_code_id": "US_STANDARD",
                                    "effective_date": "2024-01-01",
                                    "currency": "USD",
                                    "created_by": "admin"
                                }
                                
                                response = client.post("/api/formulas/validate", json=formula_data)
                                
                                assert response.status_code == 400


class TestUpdateFormulaById:
    """Tests for PUT /api/formulas/{formula_id}/update endpoint."""
    
    def test_update_formula_success(self, client, sample_formula_with_bytecode):
        """Test successful formula update with version increment."""
        formula_id = str(sample_formula_with_bytecode.id)
        updated_formula = sample_formula_with_bytecode
        updated_formula.version_number = 2
        
        with patch("src.routes.formula_routes.Formula") as mock_formula_model:
            with patch("src.routes.formula_routes.FormulaValidator") as mock_validator:
                with patch("src.routes.formula_routes.FormulaExecutor"):
                    with patch("src.routes.formula_routes.FormulaCache"):
                        with patch("src.routes.formula_routes.ConstantsProvider"):
                            with patch("src.routes.formula_routes.EuroControlRateLoader"):
                                with patch("src.routes.formula_routes.get_redis_client") as mock_redis:
                                    mock_redis.return_value = None
                                    
                                    # Mock database query
                                    mock_query = MagicMock()
                                    mock_query.filter.return_value.first.return_value = sample_formula_with_bytecode
                                    
                                    with patch("src.database.get_db") as mock_get_db:
                                        mock_db = MagicMock()
                                        mock_db.query.return_value = mock_query
                                        mock_get_db.return_value = iter([mock_db])
                                        
                                        mock_validator.return_value.validate_and_save.return_value = updated_formula
                                        
                                        formula_data = {
                                            "formula_code": "def calculate(distance, weight, context): return {'cost': 150, 'currency': 'USD', 'usd_cost': 150}",
                                            "country_code": "US",
                                            "description": "United States Updated",
                                            "formula_code_id": "US_STANDARD_V2",
                                            "effective_date": "2024-06-01",
                                            "currency": "USD",
                                            "created_by": "admin"
                                        }
                                        
                                        response = client.put(f"/api/formulas/{formula_id}/update", json=formula_data)
                                        
                                        assert response.status_code == 200
                                        data = response.json()
                                        assert data["version"] == 2
    
    def test_update_formula_not_found(self, client):
        """Test 404 response when formula not found for update."""
        formula_id = str(uuid4())
        
        with patch("src.routes.formula_routes.Formula") as mock_formula_model:
            mock_query = MagicMock()
            mock_query.filter.return_value.first.return_value = None
            
            with patch("src.database.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.query.return_value = mock_query
                mock_get_db.return_value = iter([mock_db])
                
                formula_data = {
                    "formula_code": "def calculate(distance, weight, context): return {'cost': 150, 'currency': 'USD', 'usd_cost': 150}",
                    "country_code": "US",
                    "description": "United States",
                    "formula_code_id": "US_STANDARD",
                    "effective_date": "2024-01-01",
                    "currency": "USD",
                    "created_by": "admin"
                }
                
                response = client.put(f"/api/formulas/{formula_id}/update", json=formula_data)
                
                assert response.status_code == 404


class TestDeleteFormulaById:
    """Tests for DELETE /api/formulas/{formula_id}/delete endpoint."""
    
    def test_delete_formula_success(self, client, sample_formula_with_bytecode):
        """Test successful formula deletion."""
        formula_id = str(sample_formula_with_bytecode.id)
        
        with patch("src.routes.formula_routes.Formula") as mock_formula_model:
            with patch("src.routes.formula_routes.FormulaCache"):
                with patch("src.routes.formula_routes.get_redis_client") as mock_redis:
                    mock_redis.return_value = None
                    
                    # Mock database query
                    mock_query = MagicMock()
                    mock_query.filter.return_value.first.return_value = sample_formula_with_bytecode
                    
                    with patch("src.database.get_db") as mock_get_db:
                        mock_db = MagicMock()
                        mock_db.query.return_value = mock_query
                        mock_get_db.return_value = iter([mock_db])
                        
                        response = client.delete(f"/api/formulas/{formula_id}/delete")
                        
                        assert response.status_code == 204
    
    def test_delete_formula_not_found(self, client):
        """Test 404 response when formula not found for deletion."""
        formula_id = str(uuid4())
        
        with patch("src.routes.formula_routes.Formula") as mock_formula_model:
            mock_query = MagicMock()
            mock_query.filter.return_value.first.return_value = None
            
            with patch("src.database.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.query.return_value = mock_query
                mock_get_db.return_value = iter([mock_db])
                
                response = client.delete(f"/api/formulas/{formula_id}/delete")
                
                assert response.status_code == 404
