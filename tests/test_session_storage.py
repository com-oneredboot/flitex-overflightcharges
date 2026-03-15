"""Unit tests for SessionBuilder.store_session (Task 8.3).

Tests session JSONB storage into calculations.overflight_calculation_sessions
and derived summary record creation in route_calculations and fir_charges.

Validates Requirements: 11.1, 11.2, 11.3, 11.4
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

from src.services.session_builder import SessionBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(**overrides) -> dict:
    """Build a minimal but complete Calculation Session dict."""
    calc_id = str(uuid.uuid4())
    base = {
        "session": {
            "calculation_id": calc_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "calculator_version": "2.0.0",
            "user_id": None,
        },
        "input": {
            "route_string": "KJFK DCT EGLL",
            "origin": "KJFK",
            "destination": "EGLL",
            "aircraft_type": "B738",
            "mtow_kg": 70000,
            "flight_number": "BA178",
            "flight_date": "2024-06-15",
            "callsign": None,
        },
        "route_resolution": {
            "tokens": [],
            "resolved_waypoints": [],
            "unresolved": [],
            "route_linestring": {"type": "LineString", "coordinates": []},
            "total_distance_km": 5500.0,
            "total_distance_nm": 2970.0,
        },
        "fir_crossings": [
            {
                "sequence": 1,
                "icao_code": "KZNY",
                "fir_name": "New York Oceanic",
                "country": "United States",
                "country_code": "US",
                "entry_point": {"lat": 40.6, "lon": -73.8},
                "exit_point": {"lat": 45.0, "lon": -50.0},
                "segment_distance_km": 2200.0,
                "segment_distance_nm": 1188.0,
                "gc_entry_exit_distance_km": 2180.0,
                "gc_entry_exit_distance_nm": 1177.0,
                "segment_geometry": {"type": "LineString", "coordinates": []},
                "calculation_method": "postgis_geography",
            },
        ],
        "fir_charges": [
            {
                "icao_code": "KZNY",
                "fir_name": "New York Oceanic",
                "country": "United States",
                "country_code": "US",
                "formula_code": "EUROCONTROL",
                "formula_version": 1,
                "formula_effective_date": "2024-01-01",
                "unit_rate": 60.0,
                "unit_rate_source": "eurocontrol_unit_rates",
                "unit_rate_effective_date": "2024-01-01",
                "distance_factor": 11.88,
                "weight_factor": 3.74,
                "charge_amount": 250.00,
                "currency": "USD",
                "charge_in_usd": 250.00,
                "exchange_rate": 1.0,
                "exchange_rate_date": "2024-01-01",
                "distance_used_km": 2200.0,
                "distance_method": "segment",
                "bilateral_exemption": None,
                "charge_type": "overflight",
                "justification": "test",
            },
        ],
        "totals": {
            "by_currency": {"USD": 250.00},
            "total_usd": 250.00,
            "total_eur": 227.27,
            "fir_count": 1,
            "countries_count": 1,
        },
        "validation": {
            "dual_system": {},
            "llm_sanity_check": {"verdict": "pending"},
            "chain_continuity": {"all_valid": True, "failures": []},
        },
        "data_provenance": {},
        "comparison": {
            "invoice_match_keys": {
                "flight_number": "BA178",
                "date": "2024-06-15",
                "origin": "KJFK",
                "destination": "EGLL",
            },
            "flown_route_available": False,
            "flown_calculation_id": None,
            "planned_vs_flown_delta": None,
        },
    }
    _deep_update(base, overrides)
    return base


def _deep_update(d: dict, u: dict) -> dict:
    for k, v in u.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            _deep_update(d[k], v)
        else:
            d[k] = v
    return d
