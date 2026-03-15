"""Unit tests for the route validation endpoint POST /api/route/validate.

Tests cover:
- Successful full validation (all waypoints resolved, FIR crossings returned)
- Partial resolution (some waypoints unresolved, valid=false)
- Empty / whitespace route string → 400
- No waypoints resolved → 400 with unresolved list
- FIR spatial analysis failure → 200 with empty fir_crossings
- Database connection failure → 500

Validates Requirements: 3.1, 3.2, 3.3, 3.5
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from src.services.route_parser import Waypoint
from src.schemas.reference import FIRCrossing
from src.exceptions import ParsingException


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


class TestRouteValidationEndpoint:
    """Tests for POST /api/route/validate."""

    def test_successful_full_validation(self, client, mock_db):
        """All waypoints resolved → 200, valid=true, unresolved=[]."""
        waypoints = [
            Waypoint(identifier="KJFK", latitude=40.6413, longitude=-73.7781, source_table="airports"),
            Waypoint(identifier="CYYZ", latitude=43.6777, longitude=-79.6248, source_table="airports"),
        ]
        fir_crossings = [
            FIRCrossing(icao_code="KZNY", fir_name="New York Oceanic", country="US"),
        ]

        with patch(
            "src.routes.route_validation_routes.RouteParser"
        ) as MockParser:
            instance = MockParser.return_value
            instance.parse_route.return_value = waypoints
            instance.identify_fir_crossings_db.return_value = fir_crossings
            MockParser.ROUTE_KEYWORDS = {"DCT", "SID", "STAR", "DIRECT", "AIRWAY"}

            response = client.post(
                "/api/route/validate",
                json={"route_string": "KJFK DCT CYYZ"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert len(data["waypoints"]) == 2
        assert data["waypoints"][0]["identifier"] == "KJFK"
        assert data["waypoints"][0]["source_table"] == "airports"
        assert data["waypoints"][1]["identifier"] == "CYYZ"
        assert len(data["fir_crossings"]) == 1
        assert data["fir_crossings"][0]["icaoCode"] == "KZNY"
        assert data["fir_crossings"][0]["chargeType"] == "overflight"
        assert data["unresolved"] == []

    def test_partial_resolution(self, client, mock_db):
        """Some waypoints unresolved → 200, valid=false, unresolved=[...]."""
        waypoints = [
            Waypoint(identifier="KJFK", latitude=40.6413, longitude=-73.7781, source_table="airports"),
        ]

        with patch(
            "src.routes.route_validation_routes.RouteParser"
        ) as MockParser:
            instance = MockParser.return_value
            instance.parse_route.return_value = waypoints
            instance.identify_fir_crossings_db.return_value = []
            # ROUTE_KEYWORDS is a class attribute, keep it accessible
            MockParser.ROUTE_KEYWORDS = {"DCT", "SID", "STAR", "DIRECT", "AIRWAY"}

            response = client.post(
                "/api/route/validate",
                json={"route_string": "KJFK DCT XXXXX"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["unresolved"] == ["XXXXX"]
        assert len(data["waypoints"]) == 1
        assert data["waypoints"][0]["identifier"] == "KJFK"

    def test_empty_route_string_returns_400(self, client, mock_db):
        """Empty route string → 400 with detail message."""
        with patch(
            "src.routes.route_validation_routes.RouteParser"
        ) as MockParser:
            instance = MockParser.return_value
            instance.parse_route.side_effect = ParsingException(
                "Route string cannot be empty",
                details={"route_string": ""},
            )

            response = client.post(
                "/api/route/validate",
                json={"route_string": "   "},
            )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "Route string cannot be empty"

    def test_no_waypoints_resolved_returns_400(self, client, mock_db):
        """No waypoints resolved → 400 with unresolved list."""
        with patch(
            "src.routes.route_validation_routes.RouteParser"
        ) as MockParser:
            instance = MockParser.return_value
            instance.parse_route.side_effect = ParsingException(
                "No valid waypoints found in route string",
                details={
                    "route_string": "XXXXX YYYYY",
                    "tokens": ["XXXXX", "YYYYY"],
                    "unresolved": ["XXXXX", "YYYYY"],
                },
            )

            response = client.post(
                "/api/route/validate",
                json={"route_string": "XXXXX YYYYY"},
            )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "No valid waypoints found"
        assert data["unresolved"] == ["XXXXX", "YYYYY"]

    def test_fir_analysis_failure_returns_200_with_empty_crossings(self, client, mock_db):
        """FIR spatial analysis failure → 200 with empty fir_crossings."""
        waypoints = [
            Waypoint(identifier="KJFK", latitude=40.6413, longitude=-73.7781, source_table="airports"),
        ]

        with patch(
            "src.routes.route_validation_routes.RouteParser"
        ) as MockParser:
            instance = MockParser.return_value
            instance.parse_route.return_value = waypoints
            instance.identify_fir_crossings_db.side_effect = Exception("PostGIS error")
            MockParser.ROUTE_KEYWORDS = {"DCT", "SID", "STAR", "DIRECT", "AIRWAY"}

            response = client.post(
                "/api/route/validate",
                json={"route_string": "KJFK"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["fir_crossings"] == []
        assert len(data["waypoints"]) == 1

    def test_database_failure_returns_500(self, client, mock_db):
        """Database connection failure → 500."""
        with patch(
            "src.routes.route_validation_routes.RouteParser"
        ) as MockParser:
            instance = MockParser.return_value
            instance.parse_route.side_effect = Exception("Connection refused")

            response = client.post(
                "/api/route/validate",
                json={"route_string": "KJFK DCT CYYZ"},
            )

        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Internal server error"

    def test_route_keywords_not_in_unresolved(self, client, mock_db):
        """Route keywords (DCT, SID, etc.) should not appear in unresolved list."""
        waypoints = [
            Waypoint(identifier="KJFK", latitude=40.6413, longitude=-73.7781, source_table="airports"),
            Waypoint(identifier="EGLL", latitude=51.4775, longitude=-0.4614, source_table="airports"),
        ]

        with patch(
            "src.routes.route_validation_routes.RouteParser"
        ) as MockParser:
            instance = MockParser.return_value
            instance.parse_route.return_value = waypoints
            instance.identify_fir_crossings_db.return_value = []
            MockParser.ROUTE_KEYWORDS = {"DCT", "SID", "STAR", "DIRECT", "AIRWAY"}

            response = client.post(
                "/api/route/validate",
                json={"route_string": "KJFK DCT SID STAR EGLL"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["unresolved"] == []

    def test_response_schema_structure(self, client, mock_db):
        """Response contains all required fields with correct types."""
        waypoints = [
            Waypoint(identifier="KJFK", latitude=40.6413, longitude=-73.7781, source_table="airports"),
        ]
        fir_crossings = [
            FIRCrossing(icao_code="KZNY", fir_name="New York Oceanic", country="US"),
        ]

        with patch(
            "src.routes.route_validation_routes.RouteParser"
        ) as MockParser:
            instance = MockParser.return_value
            instance.parse_route.return_value = waypoints
            instance.identify_fir_crossings_db.return_value = fir_crossings
            MockParser.ROUTE_KEYWORDS = {"DCT", "SID", "STAR", "DIRECT", "AIRWAY"}

            response = client.post(
                "/api/route/validate",
                json={"route_string": "KJFK"},
            )

        data = response.json()
        assert isinstance(data["valid"], bool)
        assert isinstance(data["waypoints"], list)
        assert isinstance(data["fir_crossings"], list)
        assert isinstance(data["unresolved"], list)

        wp = data["waypoints"][0]
        assert isinstance(wp["identifier"], str)
        assert isinstance(wp["latitude"], float)
        assert isinstance(wp["longitude"], float)
        assert isinstance(wp["source_table"], str)

        fir = data["fir_crossings"][0]
        assert isinstance(fir["icaoCode"], str)
        assert isinstance(fir["firName"], str)
        assert fir["chargeType"] == "overflight"

    def test_pydantic_validation_rejects_missing_route_string(self, client, mock_db):
        """Missing route_string in request body → 422 (Pydantic validation)."""
        response = client.post("/api/route/validate", json={})
        assert response.status_code == 422
