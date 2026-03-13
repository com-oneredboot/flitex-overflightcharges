"""Tests for FIR management API endpoints.

This module tests the REST API endpoints for FIR (Flight Information Region) management:
- GET /api/iata-firs - List all FIRs
- GET /api/iata-firs/{icao_code} - Get single FIR
- POST /api/iata-firs - Create new FIR
- PUT /api/iata-firs/{icao_code} - Update FIR
- DELETE /api/iata-firs/{icao_code} - Delete FIR

Validates Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 1.8, 9.6, 11.3
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime

from src.models.iata_fir import IataFir
from src.exceptions import FIRNotFoundException, DuplicateFIRException


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
def sample_fir():
    """Create a sample FIR object for testing."""
    return IataFir(
        icao_code="EGLL",
        fir_name="London FIR",
        country_code="GB",
        country_name="United Kingdom",
        geojson_geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
        bbox_min_lon=-5.0,
        bbox_min_lat=49.0,
        bbox_max_lon=2.0,
        bbox_max_lat=61.0,
        avoid_status=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


class TestGetAllFIRs:
    """Tests for GET /api/iata-firs endpoint."""
    
    def test_get_all_firs_success(self, client, sample_fir):
        """Test successful retrieval of all FIRs."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_all_firs.return_value = [sample_fir]
            
            response = client.get("/api/iata-firs")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["icao_code"] == "EGLL"
            assert data[0]["fir_name"] == "London FIR"
            assert data[0]["country_code"] == "GB"
    
    def test_get_all_firs_empty(self, client):
        """Test retrieval when no FIRs exist."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_all_firs.return_value = []
            
            response = client.get("/api/iata-firs")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0


class TestGetFIRByCode:
    """Tests for GET /api/iata-firs/{icao_code} endpoint."""
    
    def test_get_fir_by_code_success(self, client, sample_fir):
        """Test successful retrieval of single FIR."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_fir_by_code.return_value = sample_fir
            
            response = client.get("/api/iata-firs/EGLL")
            
            assert response.status_code == 200
            data = response.json()
            assert data["icao_code"] == "EGLL"
            assert data["fir_name"] == "London FIR"
    
    def test_get_fir_by_code_not_found(self, client):
        """Test 404 response when FIR not found."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_fir_by_code.return_value = None
            
            response = client.get("/api/iata-firs/XXXX")
            
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()


class TestCreateFIR:
    """Tests for POST /api/iata-firs endpoint."""
    
    def test_create_fir_success(self, client, sample_fir):
        """Test successful FIR creation."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.create_fir.return_value = sample_fir
            
            fir_data = {
                "icao_code": "EGLL",
                "fir_name": "London FIR",
                "country_code": "GB",
                "country_name": "United Kingdom",
                "geojson_geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
                "bbox_min_lon": -5.0,
                "bbox_min_lat": 49.0,
                "bbox_max_lon": 2.0,
                "bbox_max_lat": 61.0,
                "avoid_status": False
            }
            
            response = client.post("/api/iata-firs", json=fir_data)
            
            assert response.status_code == 201
            data = response.json()
            assert data["icao_code"] == "EGLL"
            assert data["fir_name"] == "London FIR"
    
    def test_create_fir_duplicate(self, client):
        """Test 409 response when creating duplicate FIR."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.create_fir.side_effect = DuplicateFIRException(
                message="FIR with ICAO code 'EGLL' already exists"
            )
            
            fir_data = {
                "icao_code": "EGLL",
                "fir_name": "London FIR",
                "country_code": "GB",
                "country_name": "United Kingdom",
                "geojson_geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            }
            
            response = client.post("/api/iata-firs", json=fir_data)
            
            assert response.status_code == 409
            data = response.json()
            assert "already exists" in data["detail"].lower()
    
    def test_create_fir_validation_error(self, client):
        """Test 422 response for validation errors."""
        fir_data = {
            "icao_code": "EG",  # Too short
            "fir_name": "London FIR",
            "country_code": "GB",
            "country_name": "United Kingdom",
            "geojson_geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
        }
        
        response = client.post("/api/iata-firs", json=fir_data)
        
        assert response.status_code == 422


class TestUpdateFIR:
    """Tests for PUT /api/iata-firs/{icao_code} endpoint."""
    
    def test_update_fir_success(self, client, sample_fir):
        """Test successful FIR update."""
        updated_fir = sample_fir
        updated_fir.fir_name = "London FIR Updated"
        
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.update_fir.return_value = updated_fir
            
            update_data = {
                "fir_name": "London FIR Updated"
            }
            
            response = client.put("/api/iata-firs/EGLL", json=update_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["fir_name"] == "London FIR Updated"
    
    def test_update_fir_not_found(self, client):
        """Test 404 response when updating non-existent FIR."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.update_fir.side_effect = FIRNotFoundException(
                message="FIR with ICAO code 'XXXX' not found"
            )
            
            update_data = {
                "fir_name": "Updated Name"
            }
            
            response = client.put("/api/iata-firs/XXXX", json=update_data)
            
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()
    
    def test_update_fir_validation_error(self, client):
        """Test 422 response for validation errors."""
        update_data = {
            "fir_name": ""  # Empty string - violates min_length=1
        }
        
        response = client.put("/api/iata-firs/EGLL", json=update_data)
        
        assert response.status_code == 422


class TestDeleteFIR:
    """Tests for DELETE /api/iata-firs/{icao_code} endpoint."""
    
    def test_delete_fir_success(self, client):
        """Test successful FIR deletion."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.delete_fir.return_value = True
            
            response = client.delete("/api/iata-firs/EGLL")
            
            assert response.status_code == 204
    
    def test_delete_fir_not_found(self, client):
        """Test 404 response when deleting non-existent FIR."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.delete_fir.side_effect = FIRNotFoundException(
                message="FIR with ICAO code 'XXXX' not found"
            )
            
            response = client.delete("/api/iata-firs/XXXX")
            
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()


class TestLogging:
    """Tests for API request logging."""
    
    def test_request_logging(self, client, sample_fir, caplog):
        """Test that API requests are logged with required fields."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_all_firs.return_value = [sample_fir]
            
            with caplog.at_level("INFO"):
                response = client.get("/api/iata-firs")
            
            assert response.status_code == 200
            
            # Check that log contains required fields
            log_records = [r for r in caplog.records if "Retrieved all FIRs" in r.message]
            assert len(log_records) > 0
            
            log_record = log_records[0]
            # Check for structured logging fields
            assert hasattr(log_record, "method") or "method" in str(log_record.__dict__)
            assert hasattr(log_record, "path") or "path" in str(log_record.__dict__)
            assert hasattr(log_record, "status_code") or "status_code" in str(log_record.__dict__)
            assert hasattr(log_record, "duration_ms") or "duration_ms" in str(log_record.__dict__)
