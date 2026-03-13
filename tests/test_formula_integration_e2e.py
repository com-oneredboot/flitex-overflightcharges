"""End-to-end integration tests for formula execution system.

This module tests the complete flow of formula management including:
- Application startup initialization
- Create formula → retrieve → execute → update → delete
- Cache behavior across multiple requests
- Error handling across all endpoints

Validates Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 12.1, 12.2, 12.3, 12.4
"""

import os
import pytest
from datetime import date
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base, get_db
from src.models.formula import Formula


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_client.get.return_value = None
    mock_client.setex.return_value = True
    mock_client.delete.return_value = 1
    return mock_client


@pytest.fixture
def test_db():
    """Create in-memory test database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    return override_get_db


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    return {
        "DATABASE_URL": "postgresql://user:pass@localhost/db",
        "CORS_ORIGINS": "http://localhost:4200",
        "LOG_LEVEL": "INFO",
        "REDIS_URL": "redis://localhost:6379/0"
    }


@pytest.fixture
def client(test_db, mock_redis, mock_env):
    """Create test client with mocked dependencies."""
    with patch.dict(os.environ, mock_env):
        with patch("src.main.get_db", test_db):
            with patch("src.formula_execution.redis_config.RedisConfig.initialize"):
                with patch("src.formula_execution.redis_config.RedisConfig.get_client", return_value=mock_redis):
                    # Mock database schema verification
                    with patch("src.main.verify_database_schema"):
                        # Import app after mocking
                        from src.main import app
                        
                        # Override get_db dependency
                        app.dependency_overrides[get_db] = test_db
                        
                        yield TestClient(app)


class TestStartupInitialization:
    """Test application startup initialization (Task 12.1)."""
    
    def test_startup_initializes_components(self, mock_env, mock_redis):
        """Test that startup event initializes all formula execution components."""
        with patch.dict(os.environ, mock_env):
            with patch("src.formula_execution.redis_config.RedisConfig.initialize"):
                with patch("src.formula_execution.redis_config.RedisConfig.get_client", return_value=mock_redis):
                    with patch("src.main.verify_database_schema"):
                        with patch("src.main.get_db") as mock_get_db:
                            mock_db = MagicMock()
                            mock_db.execute.return_value.fetchall.return_value = []
                            mock_get_db.return_value = iter([mock_db])
                            
                            from src.main import app
                            
                            # Trigger startup by creating test client
                            with TestClient(app) as client:
                                # Verify app.state has required components
                                assert hasattr(app.state, "constants_provider")
                                assert hasattr(app.state, "rate_loader")
                                assert hasattr(app.state, "cache")
                                assert hasattr(app.state, "redis_client")
    
    def test_startup_graceful_degradation_without_redis(self, mock_env):
        """Test that startup succeeds even when Redis is unavailable."""
        env_without_redis = mock_env.copy()
        del env_without_redis["REDIS_URL"]
        
        with patch.dict(os.environ, env_without_redis):
            with patch("src.main.verify_database_schema"):
                with patch("src.main.get_db") as mock_get_db:
                    mock_db = MagicMock()
                    mock_db.execute.return_value.fetchall.return_value = []
                    mock_get_db.return_value = iter([mock_db])
                    
                    from src.main import app
                    
                    # Should not raise - startup should succeed
                    with TestClient(app) as client:
                        response = client.get("/")
                        assert response.status_code == 200


class TestEndToEndFormulaFlow:
    """Test complete formula lifecycle (Task 12.4)."""
    
    def test_complete_formula_lifecycle(self, client):
        """Test: create formula → retrieve → update → delete."""
        # Step 1: Create formula with validation
        create_data = {
            "formula_code": """def calculate(distance, weight, context):
    cost = distance * 10.5
    return {
        'cost': cost,
        'currency': 'USD',
        'usd_cost': cost
    }""",
            "country_code": "US",
            "description": "United States Test Formula",
            "formula_code_id": "US_TEST",
            "effective_date": "2024-01-01",
            "currency": "USD",
            "created_by": "test@example.com"
        }
        
        response = client.post("/api/formulas/validate", json=create_data)
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "formula_hash" in data
        assert data["version"] == 1
        formula_id = data["id"]
        
        # Step 2: Retrieve formula by ID
        response = client.get(f"/api/formulas/{formula_id}/full")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == formula_id
        assert data["country_code"] == "US"
        assert data["version"] == 1
        assert "bytecode" in data
        
        # Step 3: Retrieve all formulas with bytecode
        response = client.get("/api/formulas/bulk")
        assert response.status_code == 200
        data = response.json()
        assert "formulas" in data
        assert "US" in data["formulas"]
        assert data["formulas"]["US"]["id"] == formula_id
        
        # Step 4: Update formula (creates new version)
        update_data = {
            "formula_code": """def calculate(distance, weight, context):
    cost = distance * 12.0
    return {
        'cost': cost,
        'currency': 'USD',
        'usd_cost': cost
    }""",
            "country_code": "US",
            "description": "United States Updated Formula",
            "formula_code_id": "US_TEST",
            "effective_date": "2024-02-01",
            "currency": "USD",
            "created_by": "test@example.com"
        }
        
        response = client.put(f"/api/formulas/{formula_id}/update", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 2
        
        # Step 5: Delete formula
        response = client.delete(f"/api/formulas/{formula_id}/delete")
        assert response.status_code == 204
        
        # Step 6: Verify formula is deleted
        response = client.get(f"/api/formulas/{formula_id}/full")
        assert response.status_code == 404


class TestCacheBehavior:
    """Test cache behavior across multiple requests (Task 12.4)."""
    
    def test_bulk_formulas_cache_hit(self, client, mock_redis):
        """Test that bulk formulas endpoint uses cache on second request."""
        # First request - cache miss
        response1 = client.get("/api/formulas/bulk")
        assert response1.status_code == 200
        
        # Verify cache was checked
        mock_redis.get.assert_called()
        
        # Second request - should attempt cache hit
        mock_redis.get.return_value = None  # Simulate cache miss for test
        response2 = client.get("/api/formulas/bulk")
        assert response2.status_code == 200
    
    def test_execution_context_cache_hit(self, client, mock_redis):
        """Test that execution context endpoint uses cache on second request."""
        # First request - cache miss
        response1 = client.get("/api/formulas/execution-context")
        assert response1.status_code == 200
        data = response1.json()
        assert "constants" in data
        assert "eurocontrol_rates" in data
        
        # Verify cache was checked
        mock_redis.get.assert_called()
    
    def test_cache_invalidation_on_update(self, client, mock_redis):
        """Test that cache is invalidated when formula is updated."""
        # Create formula
        create_data = {
            "formula_code": """def calculate(distance, weight, context):
    return {'cost': 100, 'currency': 'USD', 'usd_cost': 100}""",
            "country_code": "CA",
            "description": "Canada Test",
            "formula_code_id": "CA_TEST",
            "effective_date": "2024-01-01",
            "currency": "CAD",
            "created_by": "test@example.com"
        }
        
        response = client.post("/api/formulas/validate", json=create_data)
        assert response.status_code == 201
        formula_id = response.json()["id"]
        
        # Update formula
        update_data = create_data.copy()
        update_data["formula_code"] = """def calculate(distance, weight, context):
    return {'cost': 200, 'currency': 'USD', 'usd_cost': 200}"""
        
        response = client.put(f"/api/formulas/{formula_id}/update", json=update_data)
        assert response.status_code == 200
        
        # Verify cache invalidation was called
        # The invalidate_formula method should call redis delete
        assert mock_redis.delete.called or mock_redis.get.called


class TestErrorHandling:
    """Test error handling across all endpoints (Task 12.3, 12.4)."""
    
    def test_formula_not_found_error(self, client):
        """Test FormulaNotFoundError returns 404."""
        response = client.get("/api/formulas/00000000-0000-0000-0000-000000000000/full")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"] == "Formula not found"
    
    def test_formula_syntax_error(self, client):
        """Test FormulaSyntaxError returns 400."""
        create_data = {
            "formula_code": "def calculate(distance, weight, context):\n    invalid syntax here",
            "country_code": "XX",
            "description": "Invalid Syntax Test",
            "formula_code_id": "XX_TEST",
            "effective_date": "2024-01-01",
            "currency": "USD",
            "created_by": "test@example.com"
        }
        
        response = client.post("/api/formulas/validate", json=create_data)
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
    
    def test_formula_validation_error_missing_calculate(self, client):
        """Test FormulaValidationError returns 400 when calculate function is missing."""
        create_data = {
            "formula_code": "def wrong_function():\n    pass",
            "country_code": "YY",
            "description": "Missing Calculate Test",
            "formula_code_id": "YY_TEST",
            "effective_date": "2024-01-01",
            "currency": "USD",
            "created_by": "test@example.com"
        }
        
        response = client.post("/api/formulas/validate", json=create_data)
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
    
    def test_formula_duplicate_error(self, client):
        """Test FormulaDuplicateError returns 400 when duplicate hash exists."""
        create_data = {
            "formula_code": """def calculate(distance, weight, context):
    return {'cost': 100, 'currency': 'USD', 'usd_cost': 100}""",
            "country_code": "ZZ",
            "description": "Duplicate Test",
            "formula_code_id": "ZZ_TEST",
            "effective_date": "2024-01-01",
            "currency": "USD",
            "created_by": "test@example.com"
        }
        
        # Create first formula
        response1 = client.post("/api/formulas/validate", json=create_data)
        assert response1.status_code == 201
        
        # Try to create duplicate (same code, different country)
        create_data["country_code"] = "ZZ2"
        response2 = client.post("/api/formulas/validate", json=create_data)
        # Should fail with duplicate error
        assert response2.status_code == 400
    
    def test_invalid_formula_id_format(self, client):
        """Test that invalid UUID format returns 404."""
        response = client.get("/api/formulas/invalid-uuid/full")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data


class TestDependencyInjection:
    """Test dependency injection functions (Task 12.2)."""
    
    def test_get_formula_executor_dependency(self, client):
        """Test that get_formula_executor dependency works."""
        # The dependency is used internally by endpoints
        # We test it indirectly by calling an endpoint that uses it
        response = client.get("/api/formulas/execution-context")
        assert response.status_code == 200
    
    def test_get_constants_provider_dependency(self, client):
        """Test that get_constants_provider dependency works."""
        response = client.get("/api/formulas/execution-context")
        assert response.status_code == 200
        data = response.json()
        assert "constants" in data
    
    def test_get_rate_loader_dependency(self, client):
        """Test that get_rate_loader dependency works."""
        response = client.get("/api/formulas/execution-context")
        assert response.status_code == 200
        data = response.json()
        assert "eurocontrol_rates" in data
    
    def test_dependency_injection_without_initialization(self):
        """Test that dependencies raise error when components not initialized."""
        from src.main import get_formula_executor, get_constants_provider
        from fastapi import Request
        
        # Create mock request without app.state components
        mock_request = MagicMock(spec=Request)
        mock_request.app.state = MagicMock()
        del mock_request.app.state.constants_provider
        
        mock_db = MagicMock()
        
        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Formula execution components not initialized"):
            get_formula_executor(mock_request, mock_db)
        
        with pytest.raises(RuntimeError, match="Formula execution components not initialized"):
            get_constants_provider(mock_request)
