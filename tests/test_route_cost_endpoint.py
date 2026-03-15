"""Tests for Route Cost calculation API endpoint.

This module tests the REST API endpoint for route cost calculation:
- POST /api/route-costs - Calculate route cost

Tests the enhanced pipeline: RouteParser → FIRIntersectionEngine →
DualValidator → ChargeCalculator → SessionBuilder → LLMAuditor (async)

Validates Requirements: 10.1, 12.1, 13.3
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from decimal import Decimal
from uuid import uuid4

from src.schemas.route_cost import RouteCostResponse, FIRChargeBreakdown
from src.exceptions import ParsingException, ValidationException
from src.services.route_parser import TokenResolutionResult, TokenRecord, Waypoint
from src.services.fir_intersection_engine import FIRIntersectionResult, FIRCrossingRecord
from src.services.dual_validator import DualValidationResult


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    return db


@pytest.fixture
def client(mock_db):
    """Create test client with mocked dependencies."""
    env_vars = {
        "DATABASE_URL": "postgresql://user:pass@localhost/db",
        "CORS_ORIGINS": "http://localhost:4200",
        "LOG_LEVEL": "INFO",
    }

    mock_result = MagicMock()
    mock_result.scalar.return_value = "2a8de75b4840"
    mock_db.execute.return_value = mock_result
    mock_db.close = MagicMock()

    with patch.dict(os.environ, env_vars):
        with patch("src.main.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])

            from src.main import app
            from src.database import get_db

            def override_get_db():
                yield mock_db

            app.dependency_overrides[get_db] = override_get_db

            yield TestClient(app)

            app.dependency_overrides.clear()


def _make_token_result(waypoints=None):
    """Build a minimal TokenResolutionResult for mocking."""
    wps = waypoints or [
        Waypoint(identifier="KJFK", latitude=40.6, longitude=-73.8),
        Waypoint(identifier="CYYZ", latitude=43.7, longitude=-79.6),
    ]
    return TokenResolutionResult(
        tokens=[],
        resolved_waypoints=wps,
        unresolved_tokens=[],
        route_linestring_coords=[(-73.8, 40.6), (-79.6, 43.7)],
    )


def _make_fir_result(crossings=None):
    """Build a minimal FIRIntersectionResult for mocking."""
    cxs = crossings or []
    total_km = sum(c.segment_distance_km for c in cxs)
    total_nm = sum(c.segment_distance_nm for c in cxs)
    return FIRIntersectionResult(
        crossings=cxs,
        total_distance_km=total_km,
        total_distance_nm=total_nm,
        chain_continuity_failures=[],
    )


def _make_crossing(icao="KZNY", fir_name="New York FIR", country="US",
                   dist_km=500.0, dist_nm=270.0):
    return FIRCrossingRecord(
        sequence=1,
        icao_code=icao,
        fir_name=fir_name,
        country=country,
        country_code=country,
        entry_point=(40.0, -74.0),
        exit_point=(42.0, -78.0),
        segment_distance_km=dist_km,
        segment_distance_nm=dist_nm,
        gc_entry_exit_distance_km=dist_km * 0.98,
        gc_entry_exit_distance_nm=dist_nm * 0.98,
        segment_geometry={"type": "LineString", "coordinates": []},
        calculation_method="postgis_geography",
    )


def _make_validation_result():
    return DualValidationResult(
        postgis_fir_list=["KZNY"],
        shapely_fir_list=["KZNY"],
        fir_lists_match=True,
        max_distance_divergence_pct=0.5,
        flagged_for_review=False,
        per_fir_comparison=[],
    )


# Patch targets for the enhanced pipeline components in route_cost_routes
_PARSER = "src.routes.route_cost_routes.RouteParser"
_FIR_ENGINE = "src.routes.route_cost_routes.FIRIntersectionEngine"
_DUAL_VALIDATOR = "src.routes.route_cost_routes.DualValidator"
_CHARGE_CALC = "src.routes.route_cost_routes.DefaultOverflightChargeCalculator"
_SESSION_BUILDER = "src.routes.route_cost_routes.SessionBuilder"
_LLM_AUDITOR = "src.routes.route_cost_routes.LLMAuditor"


class TestCalculateRouteCost:
    """Tests for POST /api/route-costs endpoint using the enhanced pipeline."""

    def _patch_pipeline(self, crossings=None, charges=None):
        """Return a dict of patch context managers for the full pipeline."""
        crossing_list = [_make_crossing()] if crossings is None else crossings
        default_charge = {
            "icao_code": "KZNY",
            "fir_name": "New York FIR",
            "country": "US",
            "country_code": "US",
            "formula_code": "US_STANDARD",
            "formula_version": 1,
            "formula_effective_date": "2024-01-01",
            "unit_rate": 50.0,
            "unit_rate_source": "eurocontrol",
            "unit_rate_effective_date": "2024-01-01",
            "distance_factor": 1.0,
            "weight_factor": 1.0,
            "charge_amount": 25200.0,
            "currency": "USD",
            "charge_in_usd": 25200.0,
            "exchange_rate": 1.0,
            "exchange_rate_date": "2024-01-01",
            "distance_used_km": 500.0,
            "distance_method": "segment",
            "bilateral_exemption": None,
            "charge_type": "overflight",
            "justification": "Standard overflight charge",
        }
        charge_list = [default_charge] if charges is None else charges

        patches = {}

        # RouteParser
        p_parser = patch(_PARSER)
        mock_parser_cls = p_parser.start()
        mock_parser_cls.return_value.parse_route_enhanced.return_value = _make_token_result()
        patches["parser"] = (p_parser, mock_parser_cls)

        # FIRIntersectionEngine
        p_fir = patch(_FIR_ENGINE)
        mock_fir_cls = p_fir.start()
        mock_fir_cls.return_value.compute_fir_crossings.return_value = _make_fir_result(crossing_list)
        patches["fir_engine"] = (p_fir, mock_fir_cls)

        # DualValidator
        p_dv = patch(_DUAL_VALIDATOR)
        mock_dv_cls = p_dv.start()
        mock_dv_cls.return_value.validate.return_value = _make_validation_result()
        patches["dual_validator"] = (p_dv, mock_dv_cls)

        # ChargeCalculator
        p_cc = patch(_CHARGE_CALC)
        mock_cc_cls = p_cc.start()
        mock_cc_cls.return_value.calculate_fir_charge.side_effect = charge_list
        patches["charge_calc"] = (p_cc, mock_cc_cls)

        # SessionBuilder
        calc_id = uuid4()
        p_sb = patch(_SESSION_BUILDER)
        mock_sb_cls = p_sb.start()
        mock_sb_cls.return_value.build_data_provenance.return_value = {}
        mock_sb_cls.return_value.build_session.return_value = {"session": {"calculation_id": str(calc_id)}}
        mock_sb_cls.return_value.store_session.return_value = calc_id
        patches["session_builder"] = (p_sb, mock_sb_cls)

        # LLMAuditor
        p_llm = patch(_LLM_AUDITOR)
        mock_llm_cls = p_llm.start()
        mock_llm_cls.return_value.audit_async.return_value = None
        patches["llm_auditor"] = (p_llm, mock_llm_cls)

        return patches, calc_id

    def _stop_patches(self, patches):
        for p, _ in patches.values():
            p.stop()

    def test_calculate_route_cost_success(self, client):
        """Test successful route cost calculation via the enhanced pipeline."""
        patches, calc_id = self._patch_pipeline()
        try:
            request_data = {
                "route_string": "KJFK DCT CYYZ",
                "origin": "KJFK",
                "destination": "CYYZ",
                "aircraft_type": "B738",
                "mtow_kg": 79000.0,
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
        finally:
            self._stop_patches(patches)

    def test_calculate_route_cost_invalid_route_string(self, client):
        """Test 400 response for invalid route string."""
        p_parser = patch(_PARSER)
        mock_parser_cls = p_parser.start()
        mock_parser_cls.return_value.parse_route_enhanced.side_effect = ParsingException(
            "Invalid route format"
        )
        try:
            request_data = {
                "route_string": "INVALID",
                "origin": "KJFK",
                "destination": "CYYZ",
                "aircraft_type": "B738",
                "mtow_kg": 79000.0,
            }

            response = client.post("/api/route-costs", json=request_data)

            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
        finally:
            p_parser.stop()

    def test_calculate_route_cost_validation_error_missing_fields(self, client):
        """Test 422 response for missing required fields."""
        request_data = {
            "route_string": "KJFK DCT CYYZ",
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
            "mtow_kg": -1000.0,
        }

        response = client.post("/api/route-costs", json=request_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_calculate_route_cost_validation_error_invalid_icao_code(self, client):
        """Test 422 response for invalid ICAO code format."""
        request_data = {
            "route_string": "KJFK DCT CYYZ",
            "origin": "KJ",
            "destination": "CYYZ",
            "aircraft_type": "B738",
            "mtow_kg": 79000.0,
        }

        response = client.post("/api/route-costs", json=request_data)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_calculate_route_cost_empty_fir_breakdown(self, client):
        """Test calculation with no FIR crossings."""
        patches, calc_id = self._patch_pipeline(crossings=[], charges=[])
        try:
            request_data = {
                "route_string": "KJFK",
                "origin": "KJFK",
                "destination": "KJFK",
                "aircraft_type": "B738",
                "mtow_kg": 79000.0,
            }

            response = client.post("/api/route-costs", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert float(data["total_cost"]) == 0.0
            assert len(data["fir_breakdown"]) == 0
        finally:
            self._stop_patches(patches)

    def test_calculate_route_cost_multiple_firs(self, client):
        """Test calculation with multiple FIR crossings."""
        crossings = [
            _make_crossing("KZNY", "New York FIR", "US", 500.0, 270.0),
            _make_crossing("CZYZ", "Toronto FIR", "CA", 300.0, 162.0),
        ]
        crossings[1] = FIRCrossingRecord(
            sequence=2,
            icao_code="CZYZ",
            fir_name="Toronto FIR",
            country="CA",
            country_code="CA",
            entry_point=(42.0, -78.0),
            exit_point=(43.7, -79.6),
            segment_distance_km=300.0,
            segment_distance_nm=162.0,
            gc_entry_exit_distance_km=294.0,
            gc_entry_exit_distance_nm=158.8,
            segment_geometry={"type": "LineString", "coordinates": []},
            calculation_method="postgis_geography",
        )
        charges = [
            {
                "icao_code": "KZNY",
                "fir_name": "New York FIR",
                "country": "US",
                "country_code": "US",
                "formula_code": "US_STANDARD",
                "formula_version": 1,
                "formula_effective_date": "2024-01-01",
                "unit_rate": 50.0,
                "unit_rate_source": "eurocontrol",
                "charge_amount": 40000.0,
                "currency": "USD",
                "charge_in_usd": 40000.0,
                "exchange_rate": 1.0,
                "distance_used_km": 500.0,
                "distance_method": "segment",
                "bilateral_exemption": None,
                "charge_type": "overflight",
                "justification": "Standard overflight charge",
            },
            {
                "icao_code": "CZYZ",
                "fir_name": "Toronto FIR",
                "country": "CA",
                "country_code": "CA",
                "formula_code": "CA_STANDARD",
                "formula_version": 1,
                "formula_effective_date": "2024-01-01",
                "unit_rate": 40.0,
                "unit_rate_source": "eurocontrol",
                "charge_amount": 24000.0,
                "currency": "USD",
                "charge_in_usd": 24000.0,
                "exchange_rate": 1.0,
                "distance_used_km": 300.0,
                "distance_method": "segment",
                "bilateral_exemption": None,
                "charge_type": "overflight",
                "justification": "Standard overflight charge",
            },
        ]
        patches, calc_id = self._patch_pipeline(crossings=crossings, charges=charges)
        try:
            request_data = {
                "route_string": "KJFK DCT CYYZ",
                "origin": "KJFK",
                "destination": "CYYZ",
                "aircraft_type": "B738",
                "mtow_kg": 80000.0,
            }

            response = client.post("/api/route-costs", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert float(data["total_cost"]) == 64000.0
            assert len(data["fir_breakdown"]) == 2
            assert data["fir_breakdown"][0]["icao_code"] == "KZNY"
            assert data["fir_breakdown"][1]["icao_code"] == "CZYZ"
        finally:
            self._stop_patches(patches)
