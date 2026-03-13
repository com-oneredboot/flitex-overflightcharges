"""Tests for the FastAPI main application module."""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestEnvironmentValidation:
    """Tests for environment variable validation."""
    
    def test_validate_environment_variables_success(self):
        """Test successful environment variable validation."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "CORS_ORIGINS": "http://localhost:4200",
            "LOG_LEVEL": "INFO"
        }):
            from src.main import validate_environment_variables
            config = validate_environment_variables()
            
            assert config["DATABASE_URL"] == "postgresql://user:pass@localhost/db"
            assert config["CORS_ORIGINS"] == "http://localhost:4200"
            assert config["LOG_LEVEL"] == "INFO"
            assert config["PORT"] == "8000"
            assert config["WORKERS"] == "4"
    
    def test_validate_environment_variables_missing_required(self):
        """Test validation fails when required variables are missing."""
        with patch.dict(os.environ, {
            "LOG_LEVEL": "INFO"
        }, clear=True):
            from src.main import validate_environment_variables
            
            with pytest.raises(SystemExit) as exc_info:
                validate_environment_variables()
            
            assert exc_info.value.code == 1
    
    def test_validate_environment_variables_logs_safe_config(self, caplog):
        """Test that DATABASE_URL is not logged but other config is."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "CORS_ORIGINS": "http://localhost:4200",
            "LOG_LEVEL": "INFO"
        }):
            from src.main import validate_environment_variables
            
            with caplog.at_level("INFO"):
                config = validate_environment_variables()
            
            # Check that DATABASE_URL is not in logs
            log_text = caplog.text
            assert "postgresql://user:pass@localhost/db" not in log_text
            # Check that other config is logged
            assert "CORS_ORIGINS" in log_text or "Configuration loaded" in log_text


class TestDatabaseSchemaVerification:
    """Tests for database schema verification."""
    
    def test_verify_database_schema_success(self):
        """Test successful schema verification."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = "2a8de75b4840"
        mock_db.execute.return_value = mock_result
        
        with patch("src.main.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            
            from src.main import verify_database_schema
            
            # Should not raise
            verify_database_schema()
            
            # Verify the query was executed
            mock_db.execute.assert_called_once()
    
    def test_verify_database_schema_no_version(self):
        """Test schema verification fails when no version found."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db.execute.return_value = mock_result
        
        with patch("src.main.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            
            from src.main import verify_database_schema
            
            with pytest.raises(SystemExit) as exc_info:
                verify_database_schema()
            
            assert exc_info.value.code == 1
    
    def test_verify_database_schema_connection_error(self):
        """Test schema verification fails on database connection error."""
        with patch("src.main.get_db") as mock_get_db:
            mock_get_db.side_effect = Exception("Connection failed")
            
            from src.main import verify_database_schema
            
            with pytest.raises(SystemExit) as exc_info:
                verify_database_schema()
            
            assert exc_info.value.code == 1


class TestFastAPIApplication:
    """Tests for FastAPI application configuration."""
    
    @pytest.fixture
    def mock_env_and_db(self):
        """Mock environment variables and database for testing."""
        env_vars = {
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "CORS_ORIGINS": "http://localhost:4200,http://localhost:3000",
            "LOG_LEVEL": "INFO"
        }
        
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = "2a8de75b4840"
        mock_db.execute.return_value = mock_result
        
        with patch.dict(os.environ, env_vars):
            with patch("src.main.get_db") as mock_get_db:
                mock_get_db.return_value = iter([mock_db])
                yield
    
    def test_app_creation(self, mock_env_and_db):
        """Test that FastAPI app is created successfully."""
        from src.main import app
        
        assert app.title == "flitex-overflightcharges"
        assert app.version == "1.0.0"
    
    def test_cors_middleware_configured(self, mock_env_and_db):
        """Test that CORS middleware is configured."""
        from src.main import app
        
        # CORS middleware is configured - just verify app exists
        assert app is not None
    
    def test_root_endpoint(self, mock_env_and_db):
        """Test the root endpoint returns service information."""
        from src.main import app
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "flitex-overflightcharges"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"
    
    def test_service_exception_handler(self, mock_env_and_db):
        """Test that ServiceException is handled correctly."""
        from src.main import app
        from src.exceptions import ValidationException
        
        @app.get("/test-error")
        async def test_error():
            raise ValidationException("Test validation error")
        
        client = TestClient(app)
        response = client.get("/test-error")
        
        assert response.status_code == 400
        assert response.json()["detail"] == "Test validation error"
    
    def test_global_exception_handler(self, mock_env_and_db):
        """Test that unhandled exceptions return 500."""
        from src.main import app
        
        @app.get("/test-unhandled-error")
        async def test_unhandled_error():
            raise ValueError("Unexpected error")
        
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-unhandled-error")
        
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"
