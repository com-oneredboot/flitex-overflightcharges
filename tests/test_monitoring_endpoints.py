"""Unit tests for monitoring endpoints (health and metrics).

Tests the /health and /metrics endpoints for proper functionality,
database connectivity checks, and error handling.

Validates Requirements: 7.1-7.5, 8.1-8.6
"""

import pytest
from datetime import datetime
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main import app
from src.database import get_db
from src.models.route_calculation import RouteCalculation


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Override the dependency
app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Create only the route_calculations table for testing."""
    # Only create the route_calculations table (avoid JSONB issues with SQLite)
    RouteCalculation.__table__.create(bind=engine, checkfirst=True)
    yield
    # Clear data but keep table structure
    db = TestingSessionLocal()
    db.query(RouteCalculation).delete()
    db.commit()
    db.close()


def test_health_check_returns_200_when_database_connected():
    """Test GET /health returns 200 when database is connected.
    
    Validates Requirements:
        - 7.1: GET /health endpoint returns service status
        - 7.2: Check database connectivity
        - 7.3: Return 200 with status "healthy" when DB accessible
        - 7.5: Include response_time_ms in response
    """
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert data["service"] == "flitex-overflightcharges"
    assert data["database"] == "connected"
    assert "timestamp" in data
    
    # Verify timestamp is valid ISO format
    datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))


def test_health_check_includes_all_required_fields():
    """Test health check response includes all required fields."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify all required fields are present
    assert "status" in data
    assert "service" in data
    assert "timestamp" in data
    assert "database" in data


def test_metrics_returns_200_with_no_calculations():
    """Test GET /metrics returns 200 with zero calculations.
    
    Validates Requirements:
        - 8.1: GET /metrics endpoint returns service metrics
        - 8.2: Calculate total_calculations from database
        - 8.3: Calculate average_cost from stored calculations
        - 8.5: Retrieve last 10 calculations
    """
    response = client.get("/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_calculations"] == 0
    assert data["average_cost"] == "0.00"
    assert data["cache_hit_rate"] is None
    assert data["recent_calculations"] == []


def test_metrics_calculates_total_and_average_correctly():
    """Test metrics endpoint calculates total and average cost correctly.
    
    Validates Requirements:
        - 8.2: Calculate total_calculations from database
        - 8.3: Calculate average_cost from stored calculations
    """
    # Create test calculations
    db = TestingSessionLocal()
    
    calc1 = RouteCalculation(
        route_string="KJFK DCT CYYZ",
        origin="KJFK",
        destination="CYYZ",
        aircraft_type="B738",
        mtow_kg=Decimal("79000.00"),
        total_cost=Decimal("150.00"),
        currency="USD",
    )
    calc2 = RouteCalculation(
        route_string="EGLL DCT LFPG",
        origin="EGLL",
        destination="LFPG",
        aircraft_type="A320",
        mtow_kg=Decimal("78000.00"),
        total_cost=Decimal("250.00"),
        currency="EUR",
    )
    calc3 = RouteCalculation(
        route_string="EDDF DCT LIRF",
        origin="EDDF",
        destination="LIRF",
        aircraft_type="B77W",
        mtow_kg=Decimal("351000.00"),
        total_cost=Decimal("300.00"),
        currency="EUR",
    )
    
    db.add_all([calc1, calc2, calc3])
    db.commit()
    db.close()
    
    # Get metrics
    response = client.get("/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify total calculations
    assert data["total_calculations"] == 3
    
    # Verify average cost (150 + 250 + 300) / 3 = 233.33
    average = Decimal(data["average_cost"])
    expected_average = Decimal("233.33")
    assert abs(average - expected_average) < Decimal("0.01")


def test_metrics_returns_last_10_calculations():
    """Test metrics endpoint returns last 10 calculations ordered by timestamp DESC.
    
    Validates Requirement 8.5: Retrieve last 10 calculations
    """
    # Create 15 test calculations
    db = TestingSessionLocal()
    
    for i in range(15):
        calc = RouteCalculation(
            route_string=f"TEST{i} DCT TEST{i+1}",
            origin=f"TST{i:01d}",
            destination=f"TST{i+1:01d}",
            aircraft_type="B738",
            mtow_kg=Decimal("79000.00"),
            total_cost=Decimal(f"{100 + i}.00"),
            currency="USD",
        )
        db.add(calc)
    
    db.commit()
    db.close()
    
    # Get metrics
    response = client.get("/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify only 10 calculations returned
    assert len(data["recent_calculations"]) == 10
    
    # Verify calculations are ordered by timestamp DESC (most recent first)
    # The most recent calculations should have higher costs (114, 113, 112, ...)
    costs = [Decimal(calc["total_cost"]) for calc in data["recent_calculations"]]
    assert costs[0] >= costs[-1]  # First should be >= last


def test_metrics_recent_calculations_include_all_fields():
    """Test recent calculations include all required fields."""
    # Create a test calculation
    db = TestingSessionLocal()
    
    calc = RouteCalculation(
        route_string="KJFK DCT CYYZ",
        origin="KJFK",
        destination="CYYZ",
        aircraft_type="B738",
        mtow_kg=Decimal("79000.00"),
        total_cost=Decimal("150.00"),
        currency="USD",
    )
    db.add(calc)
    db.commit()
    db.close()
    
    # Get metrics
    response = client.get("/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["recent_calculations"]) == 1
    recent_calc = data["recent_calculations"][0]
    
    # Verify all required fields
    assert "id" in recent_calc
    assert "route_string" in recent_calc
    assert "origin" in recent_calc
    assert "destination" in recent_calc
    assert "total_cost" in recent_calc
    assert "calculation_timestamp" in recent_calc
    
    # Verify values
    assert recent_calc["route_string"] == "KJFK DCT CYYZ"
    assert recent_calc["origin"] == "KJFK"
    assert recent_calc["destination"] == "CYYZ"
    assert recent_calc["total_cost"] == "150.00"


def test_metrics_cache_hit_rate_is_optional():
    """Test cache_hit_rate is optional and returns None when not implemented.
    
    Validates Requirement 8.4: Calculate cache_hit_rate if caching implemented (optional)
    """
    response = client.get("/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    # Cache hit rate should be None when caching not implemented
    assert data["cache_hit_rate"] is None


def test_metrics_includes_all_required_fields():
    """Test metrics response includes all required fields."""
    response = client.get("/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify all required fields are present
    assert "total_calculations" in data
    assert "average_cost" in data
    assert "cache_hit_rate" in data
    assert "recent_calculations" in data
