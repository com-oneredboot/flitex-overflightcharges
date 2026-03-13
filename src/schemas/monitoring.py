"""Pydantic schemas for monitoring endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Response schema for health check endpoint."""

    status: str = Field(..., description="Service health status: 'healthy' or 'unhealthy'")
    service: str = Field(..., description="Service name")
    timestamp: datetime = Field(..., description="Health check timestamp")
    database: str = Field(..., description="Database connection status: 'connected' or 'disconnected'")


class CalculationSummary(BaseModel):
    """Summary of a route calculation for metrics."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Calculation ID")
    route_string: str = Field(..., description="ICAO route string")
    origin: str = Field(..., description="Origin airport code")
    destination: str = Field(..., description="Destination airport code")
    total_cost: Decimal = Field(..., description="Total calculated cost")
    calculation_timestamp: datetime = Field(..., description="When the calculation was performed")


class MetricsResponse(BaseModel):
    """Response schema for metrics endpoint."""

    total_calculations: int = Field(..., description="Total number of calculations performed")
    average_cost: Decimal = Field(..., description="Average cost across all calculations")
    cache_hit_rate: Optional[float] = Field(None, description="Cache hit rate if caching is implemented")
    recent_calculations: List[CalculationSummary] = Field(..., description="Last 10 calculations")
