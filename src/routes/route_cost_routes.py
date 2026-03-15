"""Route Cost calculation API endpoint.

This module provides REST API endpoint for calculating overflight charges:
- POST /api/route-costs - Calculate route cost

Validates Requirements: 5.1, 5.2, 5.8, 5.9, 9.6, 11.5
"""

import logging
import time

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas.route_cost import RouteCostRequest, RouteCostResponse
from src.services.cost_calculator import CostCalculator
from src.exceptions import ParsingException, ValidationException

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/route-costs", tags=["Route Cost Calculation"])


@router.post("", response_model=RouteCostResponse, status_code=status.HTTP_200_OK)
async def calculate_route_cost(
    request: RouteCostRequest,
    db: Session = Depends(get_db)
) -> RouteCostResponse:
    """
    Calculate overflight charges for a flight route.
    
    Accepts route details including ICAO route string, origin, destination,
    aircraft type, and MTOW. Returns total cost with per-FIR breakdown.
    
    Validates Requirements: 5.1, 5.2, 5.8, 5.9, 9.6, 11.5
    
    Args:
        request: Route cost calculation request with all required fields
        db: Database session (injected)
    
    Returns:
        Route cost response with total_cost, currency, fir_breakdown, calculation_id
    
    Raises:
        ParsingException: If route_string is invalid (400)
        ValidationException: If validation fails (422)
    """
    start_time = time.time()
    
    try:
        # Initialize cost calculator
        cost_calculator = CostCalculator(db)
        
        # Perform calculation
        result = cost_calculator.calculate_route_cost(
            route_string=request.route_string,
            origin=request.origin,
            destination=request.destination,
            aircraft_type=request.aircraft_type,
            mtow_kg=request.mtow_kg
        )
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Log calculation with route_string, total_cost, calculation_duration_ms (Requirement 11.5)
        logger.info(
            "Route cost calculation completed",
            extra={
                "method": "POST",
                "path": "/api/route-costs",
                "status_code": 200,
                "duration_ms": duration_ms,
                "route_string": request.route_string,
                "total_cost": float(result.total_cost),
                "calculation_duration_ms": duration_ms,
                "calculation_id": str(result.calculation_id),
                "fir_count": len(result.fir_breakdown)
            }
        )
        
        return result
        
    except ParsingException as e:
        duration_ms = (time.time() - start_time) * 1000
        
        # Log parsing error (Requirement 5.9)
        logger.warning(
            f"Invalid route string: {e.message}",
            extra={
                "method": "POST",
                "path": "/api/route-costs",
                "status_code": 400,
                "duration_ms": duration_ms,
                "route_string": request.route_string,
                "error": e.message
            }
        )
        raise
        
    except ValidationException as e:
        duration_ms = (time.time() - start_time) * 1000
        
        # Log validation error (Requirement 9.6)
        logger.warning(
            f"Validation error: {e.message}",
            extra={
                "method": "POST",
                "path": "/api/route-costs",
                "status_code": 422,
                "duration_ms": duration_ms,
                "error": e.message
            }
        )
        raise
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        
        # Log unexpected error
        logger.error(
            f"Unexpected error in route cost calculation: {str(e)}",
            extra={
                "method": "POST",
                "path": "/api/route-costs",
                "status_code": 500,
                "duration_ms": duration_ms,
                "route_string": request.route_string,
                "error": str(e)
            },
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "detail": "An unexpected error occurred during route cost calculation",
                "status_code": 500
            }
        )
