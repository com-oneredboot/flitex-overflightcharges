"""Route validation API endpoint.

This module provides a REST API endpoint for validating ICAO route strings
against the navigation database:
- POST /api/route/validate - Validate route string and return resolved waypoints,
  FIR crossings, and unresolved identifiers.

Uses the lightweight validate_route_string() which does simple first-match
resolution without requiring flight plan context (origin/destination/flight_date).

Validates Requirements: 3.1, 3.2, 3.3, 3.5
"""

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.exceptions import ParsingException
from src.schemas.reference import (
    RouteValidationRequest,
    RouteValidationResponse,
    ResolvedWaypoint,
)
from src.services.route_parser import RouteParser

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/route", tags=["Route Validation"])


@router.post(
    "/validate",
    response_model=RouteValidationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid or empty route string"},
        500: {"description": "Internal server error"},
    },
)
async def validate_route(
    request: RouteValidationRequest,
    db: Session = Depends(get_db),
) -> RouteValidationResponse | JSONResponse:
    """Validate an ICAO route string against the navigation database.

    Uses lightweight validate_route_string() for simple first-match
    waypoint resolution without flight plan context. No proximity
    disambiguation or jump detection.

    - All waypoints resolved → 200, valid=true, unresolved=[]
    - Some waypoints unresolved → 200, valid=false, unresolved=[...]
    - No waypoints resolved → 400 with detail and unresolved list
    - Empty/whitespace route string → 400 with detail message
    - Database failure → 500 with generic error message

    Validates Requirements: 3.1, 3.2, 3.3, 3.5

    Args:
        request: RouteValidationRequest with route_string
        db: Database session (injected)

    Returns:
        RouteValidationResponse on success/partial success, or JSONResponse on error
    """
    route_parser = RouteParser()

    # --- Validate route string (lightweight, no flight plan context) ---
    try:
        token_result = route_parser.validate_route_string(
            request.route_string, db
        )
    except ParsingException as e:
        # Distinguish "empty route" from "no valid waypoints"
        unresolved = e.details.get("unresolved", []) if e.details else []

        if unresolved:
            logger.warning(
                "Route validation failed – no valid waypoints",
                extra={
                    "route_string": request.route_string,
                    "unresolved": unresolved,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "detail": "No valid waypoints found",
                    "unresolved": unresolved,
                },
            )

        logger.warning(
            "Route validation failed – empty route string",
            extra={"route_string": request.route_string, "error": e.message},
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Route string cannot be empty"},
        )
    except Exception as e:
        logger.error(
            "Route validation internal error",
            extra={"route_string": request.route_string, "error": str(e)},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    waypoints = token_result.resolved_waypoints
    unresolved = [tr.raw for tr in token_result.unresolved_tokens]

    # --- Identify FIR crossings (best-effort) ---
    try:
        fir_crossings = route_parser.identify_fir_crossings_db(waypoints, db)
    except Exception as e:
        logger.warning(
            "FIR spatial analysis failed – returning incomplete crossings",
            extra={"route_string": request.route_string, "error": str(e)},
        )
        fir_crossings = []

    # --- Build response ---
    resolved_waypoints = [
        ResolvedWaypoint(
            identifier=wp.identifier,
            latitude=wp.latitude,
            longitude=wp.longitude,
            source_table=wp.source_table,
        )
        for wp in waypoints
    ]

    return RouteValidationResponse(
        valid=len(unresolved) == 0,
        waypoints=resolved_waypoints,
        fir_crossings=fir_crossings,
        unresolved=unresolved,
    )
