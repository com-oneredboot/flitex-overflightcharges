"""Unit tests for Monitoring Pydantic schemas."""

import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from pydantic import ValidationError
from src.schemas.monitoring import (
    HealthResponse,
    CalculationSummary,
    MetricsResponse
)


class TestHealthResponse:
    """Tests for HealthResponse schema."""
    
    def test_valid_health_response_healthy(self):
        """Test creating HealthResponse with healthy status."""
        timestamp = datetime.now()
        response = HealthResponse(
            status="healthy",
            service="flitex-overflightcharges",
            timestamp=timestamp,
            database="connected"
        )
        assert response.status == "healthy"
        assert response.service == "flitex-overflightcharges"
        assert response.timestamp == timestamp
        assert response.database == "connected"
    
    def test_valid_health_response_unhealthy(self):
        """Test creating HealthResponse with unhealthy status."""
        timestamp = datetime.now()
        response = HealthResponse(
            status="unhealthy",
            service="flitex-overflightcharges",
            timestamp=timestamp,
            database="disconnected"
        )
        assert response.status == "unhealthy"
        assert response.service == "flitex-overflightcharges"
        assert response.timestamp == timestamp
        assert response.database == "disconnected"
    
    def test_status_required(self):
        """Test that status is required."""
        with pytest.raises(ValidationError) as exc_info:
            HealthResponse(
                service="flitex-overflightcharges",
                timestamp=datetime.now(),
                database="connected"
            )
        assert "status" in str(exc_info.value)
    
    def test_service_required(self):
        """Test that service is required."""
        with pytest.raises(ValidationError) as exc_info:
            HealthResponse(
                status="healthy",
                timestamp=datetime.now(),
                database="connected"
            )
        assert "service" in str(exc_info.value)
    
    def test_timestamp_required(self):
        """Test that timestamp is required."""
        with pytest.raises(ValidationError) as exc_info:
            HealthResponse(
                status="healthy",
                service="flitex-overflightcharges",
                database="connected"
            )
        assert "timestamp" in str(exc_info.value)
    
    def test_database_required(self):
        """Test that database is required."""
        with pytest.raises(ValidationError) as exc_info:
            HealthResponse(
                status="healthy",
                service="flitex-overflightcharges",
                timestamp=datetime.now()
            )
        assert "database" in str(exc_info.value)


class TestCalculationSummary:
    """Tests for CalculationSummary schema."""
    
    def test_valid_calculation_summary(self):
        """Test creating CalculationSummary with valid data."""
        calc_id = uuid4()
        timestamp = datetime.now()
        summary = CalculationSummary(
            id=calc_id,
            route_string="KJFK DCT CYYZ",
            origin="KJFK",
            destination="CYYZ",
            total_cost=Decimal("224.25"),
            calculation_timestamp=timestamp
        )
        assert summary.id == calc_id
        assert summary.route_string == "KJFK DCT CYYZ"
        assert summary.origin == "KJFK"
        assert summary.destination == "CYYZ"
        assert summary.total_cost == Decimal("224.25")
        assert summary.calculation_timestamp == timestamp
    
    def test_id_required(self):
        """Test that id is required."""
        with pytest.raises(ValidationError) as exc_info:
            CalculationSummary(
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="CYYZ",
                total_cost=Decimal("224.25"),
                calculation_timestamp=datetime.now()
            )
        assert "id" in str(exc_info.value)
    
    def test_route_string_required(self):
        """Test that route_string is required."""
        with pytest.raises(ValidationError) as exc_info:
            CalculationSummary(
                id=uuid4(),
                origin="KJFK",
                destination="CYYZ",
                total_cost=Decimal("224.25"),
                calculation_timestamp=datetime.now()
            )
        assert "route_string" in str(exc_info.value)
    
    def test_origin_required(self):
        """Test that origin is required."""
        with pytest.raises(ValidationError) as exc_info:
            CalculationSummary(
                id=uuid4(),
                route_string="KJFK DCT CYYZ",
                destination="CYYZ",
                total_cost=Decimal("224.25"),
                calculation_timestamp=datetime.now()
            )
        assert "origin" in str(exc_info.value)
    
    def test_destination_required(self):
        """Test that destination is required."""
        with pytest.raises(ValidationError) as exc_info:
            CalculationSummary(
                id=uuid4(),
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                total_cost=Decimal("224.25"),
                calculation_timestamp=datetime.now()
            )
        assert "destination" in str(exc_info.value)
    
    def test_total_cost_required(self):
        """Test that total_cost is required."""
        with pytest.raises(ValidationError) as exc_info:
            CalculationSummary(
                id=uuid4(),
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="CYYZ",
                calculation_timestamp=datetime.now()
            )
        assert "total_cost" in str(exc_info.value)
    
    def test_calculation_timestamp_required(self):
        """Test that calculation_timestamp is required."""
        with pytest.raises(ValidationError) as exc_info:
            CalculationSummary(
                id=uuid4(),
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="CYYZ",
                total_cost=Decimal("224.25")
            )
        assert "calculation_timestamp" in str(exc_info.value)
    
    def test_calculation_summary_from_attributes_config(self):
        """Test that CalculationSummary has from_attributes config."""
        assert CalculationSummary.model_config.get("from_attributes") is True


class TestMetricsResponse:
    """Tests for MetricsResponse schema."""
    
    def test_valid_metrics_response_with_cache(self):
        """Test creating MetricsResponse with cache_hit_rate."""
        calc_id = uuid4()
        timestamp = datetime.now()
        recent_calcs = [
            CalculationSummary(
                id=calc_id,
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="CYYZ",
                total_cost=Decimal("224.25"),
                calculation_timestamp=timestamp
            )
        ]
        response = MetricsResponse(
            total_calculations=100,
            average_cost=Decimal("150.50"),
            cache_hit_rate=0.85,
            recent_calculations=recent_calcs
        )
        assert response.total_calculations == 100
        assert response.average_cost == Decimal("150.50")
        assert response.cache_hit_rate == 0.85
        assert len(response.recent_calculations) == 1
        assert response.recent_calculations[0].id == calc_id
    
    def test_valid_metrics_response_without_cache(self):
        """Test creating MetricsResponse without cache_hit_rate."""
        calc_id = uuid4()
        timestamp = datetime.now()
        recent_calcs = [
            CalculationSummary(
                id=calc_id,
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="CYYZ",
                total_cost=Decimal("224.25"),
                calculation_timestamp=timestamp
            )
        ]
        response = MetricsResponse(
            total_calculations=100,
            average_cost=Decimal("150.50"),
            recent_calculations=recent_calcs
        )
        assert response.total_calculations == 100
        assert response.average_cost == Decimal("150.50")
        assert response.cache_hit_rate is None
        assert len(response.recent_calculations) == 1
    
    def test_valid_metrics_response_empty_recent_calculations(self):
        """Test creating MetricsResponse with empty recent_calculations."""
        response = MetricsResponse(
            total_calculations=0,
            average_cost=Decimal("0.00"),
            recent_calculations=[]
        )
        assert response.total_calculations == 0
        assert response.average_cost == Decimal("0.00")
        assert response.cache_hit_rate is None
        assert response.recent_calculations == []
    
    def test_total_calculations_required(self):
        """Test that total_calculations is required."""
        with pytest.raises(ValidationError) as exc_info:
            MetricsResponse(
                average_cost=Decimal("150.50"),
                recent_calculations=[]
            )
        assert "total_calculations" in str(exc_info.value)
    
    def test_average_cost_required(self):
        """Test that average_cost is required."""
        with pytest.raises(ValidationError) as exc_info:
            MetricsResponse(
                total_calculations=100,
                recent_calculations=[]
            )
        assert "average_cost" in str(exc_info.value)
    
    def test_recent_calculations_required(self):
        """Test that recent_calculations is required."""
        with pytest.raises(ValidationError) as exc_info:
            MetricsResponse(
                total_calculations=100,
                average_cost=Decimal("150.50")
            )
        assert "recent_calculations" in str(exc_info.value)
    
    def test_cache_hit_rate_optional(self):
        """Test that cache_hit_rate is optional."""
        response = MetricsResponse(
            total_calculations=100,
            average_cost=Decimal("150.50"),
            cache_hit_rate=None,
            recent_calculations=[]
        )
        assert response.cache_hit_rate is None
