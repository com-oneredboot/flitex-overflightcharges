"""Monitoring API routes for health and metrics endpoints.

This module provides health check and metrics endpoints for monitoring
service status and usage statistics.

Validates Requirements: 7.1-7.5, 8.1-8.6
"""

import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.database import get_db
from src.exceptions import DatabaseException
from src.models.route_calculation import RouteCalculation
from src.schemas.monitoring import (
    HealthResponse,
    MetricsResponse,
    CalculationSummary,
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["monitoring"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is unhealthy"},
    },
)
async def health_check(db: Session = Depends(get_db)) -> HealthResponse | JSONResponse:
    """Health check endpoint with database connectivity verification.
    
    Checks database connectivity by executing a simple query and returns
    service health status with response time.
    
    Args:
        db: Database session dependency
    
    Returns:
        HealthResponse with status, service name, timestamp, and database status
        
    Validates Requirements:
        - 7.1: GET /health endpoint returns service status
        - 7.2: Check database connectivity
        - 7.3: Return 200 with status "healthy" when DB accessible
        - 7.4: Return 503 with status "unhealthy" when DB not accessible
        - 7.5: Include response_time_ms in response
    """
    start_time = time.time()
    
    try:
        # Test database connectivity with simple query (Requirement 7.2)
        db.execute(text("SELECT 1"))
        
        # Calculate response time
        response_time_ms = round((time.time() - start_time) * 1000, 2)
        
        # Log successful health check
        logger.info(
            "Health check passed",
            extra={
                "database_status": "connected",
                "response_time_ms": response_time_ms,
            }
        )
        
        # Return healthy status (Requirement 7.3)
        return HealthResponse(
            status="healthy",
            service="flitex-overflightcharges",
            timestamp=datetime.now(),
            database="connected",
        )
        
    except OperationalError as e:
        # Calculate response time
        response_time_ms = round((time.time() - start_time) * 1000, 2)
        
        # Log database connection failure
        logger.error(
            f"Health check failed: Database not accessible - {str(e)}",
            extra={
                "database_status": "disconnected",
                "response_time_ms": response_time_ms,
                "error": str(e),
            }
        )
        
        # Return unhealthy status with 503 (Requirement 7.4)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "flitex-overflightcharges",
                "timestamp": datetime.now().isoformat(),
                "database": "disconnected",
            }
        )


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Metrics retrieved successfully"},
        503: {"description": "Database not accessible"},
    },
)
async def get_metrics(db: Session = Depends(get_db)) -> MetricsResponse | JSONResponse:
    """Metrics endpoint for service usage statistics.
    
    Retrieves service metrics including total calculations, average cost,
    and recent calculations from the database.
    
    Args:
        db: Database session dependency
    
    Returns:
        MetricsResponse with total_calculations, average_cost, cache_hit_rate,
        and recent_calculations
        
    Validates Requirements:
        - 8.1: GET /metrics endpoint returns service metrics
        - 8.2: Calculate total_calculations from database
        - 8.3: Calculate average_cost from stored calculations
        - 8.4: Calculate cache_hit_rate if caching implemented (optional)
        - 8.5: Retrieve last 10 calculations
        - 8.6: Return 503 if database not accessible
    """
    start_time = time.time()
    
    try:
        # Calculate total_calculations (Requirement 8.2)
        total_calculations = db.query(func.count(RouteCalculation.id)).scalar() or 0
        
        # Calculate average_cost (Requirement 8.3)
        avg_cost_result = db.query(func.avg(RouteCalculation.total_cost)).scalar()
        average_cost = Decimal(str(avg_cost_result)) if avg_cost_result else Decimal("0.00")
        
        # Retrieve last 10 calculations ordered by timestamp DESC (Requirement 8.5)
        recent_calcs = (
            db.query(RouteCalculation)
            .order_by(RouteCalculation.calculation_timestamp.desc())
            .limit(10)
            .all()
        )
        
        # Convert to CalculationSummary objects
        recent_calculations: List[CalculationSummary] = [
            CalculationSummary(
                id=calc.id,
                route_string=calc.route_string,
                origin=calc.origin,
                destination=calc.destination,
                total_cost=calc.total_cost,
                calculation_timestamp=calc.calculation_timestamp,
            )
            for calc in recent_calcs
        ]
        
        # Cache hit rate is optional (Requirement 8.4)
        # Not implemented yet, so set to None
        cache_hit_rate = None
        
        # Calculate response time
        response_time_ms = round((time.time() - start_time) * 1000, 2)
        
        # Log metrics retrieval
        logger.info(
            "Metrics retrieved successfully",
            extra={
                "total_calculations": total_calculations,
                "average_cost": float(average_cost),
                "response_time_ms": response_time_ms,
            }
        )
        
        # Return metrics response
        return MetricsResponse(
            total_calculations=total_calculations,
            average_cost=average_cost,
            cache_hit_rate=cache_hit_rate,
            recent_calculations=recent_calculations,
        )
        
    except OperationalError as e:
        # Calculate response time
        response_time_ms = round((time.time() - start_time) * 1000, 2)
        
        # Log database connection failure
        logger.error(
            f"Metrics retrieval failed: Database not accessible - {str(e)}",
            extra={
                "response_time_ms": response_time_ms,
                "error": str(e),
            }
        )
        
        # Return 503 if database not accessible (Requirement 8.6)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Database not accessible"}
        )
