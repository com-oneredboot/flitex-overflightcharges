"""Tests for the data freshness API endpoint.

Validates Requirements: 15.1, 15.2, 15.3
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes.freshness_routes import router


@pytest.fixture()
def app():
    """Create a FastAPI app with the freshness router for testing."""
    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture()
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture()
def mock_db():
    """Create a mock database session."""
    return MagicMock()


class TestCheckDataFreshness:
    """Tests for GET /api/data-freshness endpoint."""

    def test_returns_freshness_data(self, app, mock_db):
        """Endpoint returns unit_rates, airac_cycle, and fir_boundaries sections."""
        freshness_response = {
            "unit_rates": {
                "latest_local_month": "2024-07",
                "is_stale": False,
                "source": "EUROCONTROL",
            },
            "airac_cycle": {
                "current_cycle": "2407",
                "effective_date": "2024-07-18",
            },
            "fir_boundaries": {
                "total_count": 245,
                "latest_update": "2024-03-15T10:00:00+00:00",
            },
        }

        with patch(
            "src.routes.freshness_routes.FreshnessChecker"
        ) as MockChecker:
            MockChecker.return_value.check_freshness.return_value = (
                freshness_response
            )

            # Override the DB dependency
            app.dependency_overrides[
                __import__(
                    "src.database", fromlist=["get_db"]
                ).get_db
            ] = lambda: mock_db

            client = TestClient(app)
            response = client.get("/api/data-freshness")

        assert response.status_code == 200
        data = response.json()
        assert "unit_rates" in data
        assert "airac_cycle" in data
        assert "fir_boundaries" in data
        assert data["unit_rates"]["source"] == "EUROCONTROL"

    def test_returns_stale_status(self, app, mock_db):
        """Endpoint correctly reports stale data when is_stale is True."""
        freshness_response = {
            "unit_rates": {
                "latest_local_month": "2024-01",
                "is_stale": True,
                "source": "EUROCONTROL",
            },
            "airac_cycle": {
                "current_cycle": "2407",
                "effective_date": "2024-07-18",
            },
            "fir_boundaries": {
                "total_count": 200,
                "latest_update": None,
            },
        }

        with patch(
            "src.routes.freshness_routes.FreshnessChecker"
        ) as MockChecker:
            MockChecker.return_value.check_freshness.return_value = (
                freshness_response
            )

            app.dependency_overrides[
                __import__(
                    "src.database", fromlist=["get_db"]
                ).get_db
            ] = lambda: mock_db

            client = TestClient(app)
            response = client.get("/api/data-freshness")

        assert response.status_code == 200
        data = response.json()
        assert data["unit_rates"]["is_stale"] is True
        assert data["unit_rates"]["latest_local_month"] == "2024-01"

    def test_returns_500_on_error(self, app, mock_db):
        """Endpoint returns 500 when FreshnessChecker raises an exception."""
        with patch(
            "src.routes.freshness_routes.FreshnessChecker"
        ) as MockChecker:
            MockChecker.return_value.check_freshness.side_effect = (
                RuntimeError("DB connection lost")
            )

            app.dependency_overrides[
                __import__(
                    "src.database", fromlist=["get_db"]
                ).get_db
            ] = lambda: mock_db

            client = TestClient(app)
            response = client.get("/api/data-freshness")

        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert "detail" in data
