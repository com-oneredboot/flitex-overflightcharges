"""Property-based tests for FIR API error status codes.

These tests verify that the FIR API returns correct HTTP status codes
for error conditions using Hypothesis-generated inputs with mocked DB
(same pattern as test_fir_endpoints.py).

Feature: fir-versioning-and-data-import

NOTE: These tests use mocked database sessions (no PostgreSQL required).
"""

import os
import uuid
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from hypothesis import given, settings, strategies as st, HealthCheck
from fastapi.testclient import TestClient

from src.models.iata_fir import IataFir
from src.exceptions import FIRNotFoundException, DuplicateFIRException


# --- Strategies ---

# ICAO code: 4 uppercase alphanumeric, must contain at least one letter
icao_code_strategy = st.tuples(
    st.text(
        alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        min_size=1,
        max_size=1,
    ),
    st.text(
        alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
        min_size=3,
        max_size=3,
    ),
).map(lambda t: t[0] + t[1])

version_number_strategy = st.integers(min_value=1, max_value=1000)


@pytest.fixture(scope="module")
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture(scope="module")
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


class TestAPIErrorStatusCodesProperty:
    """
    Feature: fir-versioning-and-data-import, Property 14: API error status codes

    **Validates: Requirements 7.7, 7.8**

    For any API request referencing a non-existent ICAO code or version number,
    the FIR API SHALL return HTTP 404. For any API request that would violate a
    database integrity constraint (e.g., duplicate active FIR), the FIR API SHALL
    return HTTP 409.
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(icao_code=icao_code_strategy)
    def test_property_14_get_nonexistent_fir_returns_404(
        self, client, icao_code
    ):
        """
        **Validates: Requirements 7.7**

        GET /api/iata-firs/{icao_code} returns 404 for non-existent ICAO codes.
        """
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_active_fir.return_value = None

            response = client.get(f"/api/iata-firs/{icao_code}")

            assert response.status_code == 404, (
                f"Expected 404 for non-existent ICAO code '{icao_code}', "
                f"got {response.status_code}"
            )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(icao_code=icao_code_strategy)
    def test_property_14_put_nonexistent_fir_returns_404(
        self, client, icao_code
    ):
        """
        **Validates: Requirements 7.7**

        PUT /api/iata-firs/{icao_code} returns 404 for non-existent ICAO codes.
        """
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.update_fir.side_effect = FIRNotFoundException(
                message=f"No active FIR found for ICAO code: {icao_code}"
            )

            update_data = {"fir_name": "Updated Name"}
            response = client.put(f"/api/iata-firs/{icao_code}", json=update_data)

            assert response.status_code == 404, (
                f"Expected 404 for PUT on non-existent ICAO code '{icao_code}', "
                f"got {response.status_code}"
            )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(icao_code=icao_code_strategy)
    def test_property_14_delete_nonexistent_fir_returns_404(
        self, client, icao_code
    ):
        """
        **Validates: Requirements 7.7**

        DELETE /api/iata-firs/{icao_code} returns 404 for non-existent ICAO codes.
        """
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.soft_delete_fir.side_effect = FIRNotFoundException(
                message=f"No active FIR found for ICAO code: {icao_code}"
            )

            response = client.delete(f"/api/iata-firs/{icao_code}")

            assert response.status_code == 404, (
                f"Expected 404 for DELETE on non-existent ICAO code '{icao_code}', "
                f"got {response.status_code}"
            )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(icao_code=icao_code_strategy)
    def test_property_14_history_nonexistent_fir_returns_404(
        self, client, icao_code
    ):
        """
        **Validates: Requirements 7.7**

        GET /api/iata-firs/{icao_code}/history returns 404 for non-existent ICAO codes.
        """
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.get_fir_history.side_effect = FIRNotFoundException(
                message=f"No FIR history found for ICAO code: {icao_code}"
            )

            response = client.get(f"/api/iata-firs/{icao_code}/history")

            assert response.status_code == 404, (
                f"Expected 404 for history of non-existent ICAO code '{icao_code}', "
                f"got {response.status_code}"
            )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        icao_code=icao_code_strategy,
        version_number=version_number_strategy,
    )
    def test_property_14_rollback_nonexistent_fir_returns_404(
        self, client, icao_code, version_number
    ):
        """
        **Validates: Requirements 7.7**

        POST /api/iata-firs/{icao_code}/rollback returns 404 for non-existent
        ICAO codes or version numbers.
        """
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.rollback_fir.side_effect = FIRNotFoundException(
                message=f"FIR version {version_number} not found for ICAO code: {icao_code}"
            )

            response = client.post(
                f"/api/iata-firs/{icao_code}/rollback",
                json={"version_number": version_number},
            )

            assert response.status_code == 404, (
                f"Expected 404 for rollback of non-existent ICAO code '{icao_code}' "
                f"v{version_number}, got {response.status_code}"
            )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(icao_code=icao_code_strategy)
    def test_property_14_create_duplicate_fir_returns_409(
        self, client, icao_code
    ):
        """
        **Validates: Requirements 7.8**

        POST /api/iata-firs returns 409 when DuplicateFIRException is raised
        (constraint violation).
        """
        with patch("src.routes.fir_routes.FIRService") as mock_service:
            mock_service.return_value.create_fir.side_effect = DuplicateFIRException(
                message=f"FIR with ICAO code '{icao_code}' already exists"
            )

            fir_data = {
                "icao_code": icao_code,
                "fir_name": "Test FIR",
                "country_code": "GB",
                "country_name": "United Kingdom",
                "geojson_geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            }

            response = client.post("/api/iata-firs", json=fir_data)

            assert response.status_code == 409, (
                f"Expected 409 for duplicate FIR with ICAO code '{icao_code}', "
                f"got {response.status_code}"
            )
