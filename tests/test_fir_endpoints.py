"""Tests for versioned FIR management API endpoints.

This module tests the REST API endpoints for versioned FIR management:
- GET /api/iata-firs - List all active FIRs
- GET /api/iata-firs/{icao_code} - Get active FIR by ICAO code
- POST /api/iata-firs - Create new FIR (version 1)
- PUT /api/iata-firs/{icao_code} - Update FIR (creates new version)
- DELETE /api/iata-firs/{icao_code} - Soft-delete FIR
- GET /api/iata-firs/{icao_code}/history - Get version history
- POST /api/iata-firs/{icao_code}/rollback - Rollback to version number
- GET /api/coverage-health - Get FIR-formula coverage data

Validates Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
"""

import os
import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from src.models.iata_fir import IataFir
from src.exceptions import FIRNotFoundException, DuplicateFIRException


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def client(mock_db):
    """Create test client with mocked database dependency."""
    env_vars = {
        "DATABASE_URL": "postgresql://user:pass@localhost/db",
        "CORS_ORIGINS": "http://localhost:4200",
        "LOG_LEVEL": "INFO",
    }
    with patch.dict(os.environ, env_vars):
        from src.main import app
        from src.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        yield TestClient(app)
        app.dependency_overrides.clear()


@pytest.fixture
def sample_fir():
    """Create a sample versioned FIR object for testing."""
    return IataFir(
        id=uuid.uuid4(),
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
        version_number=1,
        is_active=True,
        activation_date=datetime.now(timezone.utc),
        deactivation_date=None,
        effective_date=None,
        created_at=datetime.now(timezone.utc),
        created_by="api-user",
    )


class TestGetAllFIRs:
    """Tests for GET /api/iata-firs endpoint."""

    def test_get_all_firs_success(self, client, sample_fir):
        """Test successful retrieval of all active FIRs."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_all_active_firs.return_value = [sample_fir]

            response = client.get("/api/iata-firs")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["icao_code"] == "EGLL"
            assert data[0]["fir_name"] == "London FIR"
            assert data[0]["country_code"] == "GB"
            assert data[0]["version_number"] == 1
            assert data[0]["is_active"] is True

    def test_get_all_firs_empty(self, client):
        """Test retrieval when no active FIRs exist."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_all_active_firs.return_value = []

            response = client.get("/api/iata-firs")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0


class TestGetFIRByCode:
    """Tests for GET /api/iata-firs/{icao_code} endpoint."""

    def test_get_fir_by_code_success(self, client, sample_fir):
        """Test successful retrieval of active FIR by ICAO code."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_active_fir.return_value = sample_fir

            response = client.get("/api/iata-firs/EGLL")

            assert response.status_code == 200
            data = response.json()
            assert data["icao_code"] == "EGLL"
            assert data["fir_name"] == "London FIR"
            assert data["version_number"] == 1

    def test_get_fir_by_code_not_found(self, client):
        """Test 404 response when no active FIR found."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_active_fir.return_value = None

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
                "avoid_status": False,
            }

            response = client.post("/api/iata-firs", json=fir_data)

            assert response.status_code == 201
            data = response.json()
            assert data["icao_code"] == "EGLL"
            assert data["version_number"] == 1
            # Verify created_by defaults to "api-user"
            mock_service.return_value.create_fir.assert_called_once()
            call_kwargs = mock_service.return_value.create_fir.call_args
            assert call_kwargs.kwargs["created_by"] == "api-user"

    def test_create_fir_with_custom_created_by(self, client, sample_fir):
        """Test FIR creation with custom X-Created-By header."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.create_fir.return_value = sample_fir

            fir_data = {
                "icao_code": "EGLL",
                "fir_name": "London FIR",
                "country_code": "GB",
                "country_name": "United Kingdom",
                "geojson_geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            }

            response = client.post(
                "/api/iata-firs",
                json=fir_data,
                headers={"X-Created-By": "test-user"},
            )

            assert response.status_code == 201
            call_kwargs = mock_service.return_value.create_fir.call_args
            assert call_kwargs.kwargs["created_by"] == "test-user"

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
        """Test successful FIR update (creates new version)."""
        updated_fir = IataFir(
            id=uuid.uuid4(),
            icao_code="EGLL",
            fir_name="London FIR Updated",
            country_code="GB",
            country_name="United Kingdom",
            geojson_geometry=sample_fir.geojson_geometry,
            bbox_min_lon=-5.0,
            bbox_min_lat=49.0,
            bbox_max_lon=2.0,
            bbox_max_lat=61.0,
            avoid_status=False,
            version_number=2,
            is_active=True,
            activation_date=datetime.now(timezone.utc),
            deactivation_date=None,
            effective_date=None,
            created_at=datetime.now(timezone.utc),
            created_by="api-user",
        )

        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.update_fir.return_value = updated_fir

            update_data = {"fir_name": "London FIR Updated"}

            response = client.put("/api/iata-firs/EGLL", json=update_data)

            assert response.status_code == 200
            data = response.json()
            assert data["fir_name"] == "London FIR Updated"
            assert data["version_number"] == 2

    def test_update_fir_not_found(self, client):
        """Test 404 response when updating non-existent FIR."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.update_fir.side_effect = FIRNotFoundException(
                message="FIR with ICAO code 'XXXX' not found"
            )

            update_data = {"fir_name": "Updated Name"}

            response = client.put("/api/iata-firs/XXXX", json=update_data)

            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()

    def test_update_fir_validation_error(self, client):
        """Test 422 response for validation errors."""
        update_data = {"fir_name": ""}  # Empty string - violates min_length=1

        response = client.put("/api/iata-firs/EGLL", json=update_data)

        assert response.status_code == 422


class TestDeleteFIR:
    """Tests for DELETE /api/iata-firs/{icao_code} endpoint."""

    def test_delete_fir_success(self, client):
        """Test successful FIR soft-delete."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.soft_delete_fir.return_value = True

            response = client.delete("/api/iata-firs/EGLL")

            assert response.status_code == 204

    def test_delete_fir_not_found(self, client):
        """Test 404 response when soft-deleting non-existent FIR."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.soft_delete_fir.side_effect = FIRNotFoundException(
                message="FIR with ICAO code 'XXXX' not found"
            )

            response = client.delete("/api/iata-firs/XXXX")

            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()


class TestGetFIRHistory:
    """Tests for GET /api/iata-firs/{icao_code}/history endpoint."""

    def test_get_history_success(self, client, sample_fir):
        """Test successful retrieval of FIR version history."""
        v2 = IataFir(
            id=uuid.uuid4(),
            icao_code="EGLL",
            fir_name="London FIR v2",
            country_code="GB",
            country_name="United Kingdom",
            geojson_geometry=sample_fir.geojson_geometry,
            bbox_min_lon=-5.0,
            bbox_min_lat=49.0,
            bbox_max_lon=2.0,
            bbox_max_lat=61.0,
            avoid_status=False,
            version_number=2,
            is_active=True,
            activation_date=datetime.now(timezone.utc),
            deactivation_date=None,
            effective_date=None,
            created_at=datetime.now(timezone.utc),
            created_by="api-user",
        )
        sample_fir.is_active = False
        sample_fir.deactivation_date = datetime.now(timezone.utc)

        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_fir_history.return_value = [v2, sample_fir]

            response = client.get("/api/iata-firs/EGLL/history")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["version_number"] == 2
            assert data[1]["version_number"] == 1

    def test_get_history_not_found(self, client):
        """Test 404 response when no history exists for ICAO code."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_fir_history.side_effect = FIRNotFoundException(
                message="FIR history not found for ICAO code: XXXX"
            )

            response = client.get("/api/iata-firs/XXXX/history")

            assert response.status_code == 404


class TestRollbackFIR:
    """Tests for POST /api/iata-firs/{icao_code}/rollback endpoint."""

    def test_rollback_success(self, client, sample_fir):
        """Test successful FIR rollback."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.rollback_fir.return_value = sample_fir

            response = client.post(
                "/api/iata-firs/EGLL/rollback",
                json={"version_number": 1},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["icao_code"] == "EGLL"
            assert data["version_number"] == 1

    def test_rollback_not_found(self, client):
        """Test 404 response when rollback target version doesn't exist."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.rollback_fir.side_effect = FIRNotFoundException(
                message="FIR version 99 not found for ICAO code: EGLL"
            )

            response = client.post(
                "/api/iata-firs/EGLL/rollback",
                json={"version_number": 99},
            )

            assert response.status_code == 404

    def test_rollback_invalid_version(self, client):
        """Test 422 response for invalid version number."""
        response = client.post(
            "/api/iata-firs/EGLL/rollback",
            json={"version_number": 0},  # Must be > 0
        )

        assert response.status_code == 422


class TestCoverageHealth:
    """Tests for GET /api/coverage-health endpoint."""

    def test_coverage_health_success(self, client, mock_db):
        """Test successful coverage health retrieval."""
        mock_rows = [
            MagicMock(
                icao_code="EGLL",
                fir_name="London FIR",
                country_code="GB",
                country_name="United Kingdom",
                has_formula=True,
                formula_description="UK overflight formula",
            ),
            MagicMock(
                icao_code="LFFF",
                fir_name="Paris FIR",
                country_code="FR",
                country_name="France",
                has_formula=False,
                formula_description=None,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        response = client.get("/api/coverage-health")

        assert response.status_code == 200
        data = response.json()
        assert data["total_active_firs"] == 2
        assert data["covered_firs"] == 1
        assert data["uncovered_firs"] == 1
        assert len(data["details"]) == 2
        assert data["details"][0]["has_formula"] is True
        assert data["details"][1]["has_formula"] is False
        assert data["details"][1]["formula_description"] is None

    def test_coverage_health_empty(self, client, mock_db):
        """Test coverage health with no active FIRs."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        response = client.get("/api/coverage-health")

        assert response.status_code == 200
        data = response.json()
        assert data["total_active_firs"] == 0
        assert data["covered_firs"] == 0
        assert data["uncovered_firs"] == 0
        assert len(data["details"]) == 0


class TestLogging:
    """Tests for API request logging."""

    def test_request_logging(self, client, sample_fir, caplog):
        """Test that API requests are logged with required fields."""
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_all_active_firs.return_value = [sample_fir]

            with caplog.at_level("INFO"):
                response = client.get("/api/iata-firs")

            assert response.status_code == 200

            log_records = [r for r in caplog.records if "Retrieved all active FIRs" in r.message]
            assert len(log_records) > 0

            log_record = log_records[0]
            assert hasattr(log_record, "method") or "method" in str(log_record.__dict__)
            assert hasattr(log_record, "path") or "path" in str(log_record.__dict__)
            assert hasattr(log_record, "status_code") or "status_code" in str(log_record.__dict__)
            assert hasattr(log_record, "duration_ms") or "duration_ms" in str(log_record.__dict__)
