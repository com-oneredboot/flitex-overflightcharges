"""Route validation API endpoint.

This module provides a REST API endpoint for validating ICAO route strings
against the navigation database:
- POST /api/route/validate - Validate route string and return resolved waypoints,
  FIR crossings, and unresolved identifiers.

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

    Resolves each waypoint identifier against reference tables, identifies
    FIR crossings via PostGIS spatial analysis, and returns the full
    validation result.

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

    # --- Parse route and resolve waypoints ---
    try:
        waypoints = route_parser.parse_route(request.route_string, db)
    except ParsingException as e:
        # Distinguish "empty route" from "no valid waypoints"
        unresolved = e.details.get("unresolved", []) if e.details else []

        if unresolved:
            # No waypoints resolved at all → 400 with unresolved list
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

        # Empty / whitespace route string
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

    # --- Collect unresolved identifiers ---
    # parse_route only returns resolved waypoints; re-scan the tokens to find
    # identifiers that were silently skipped (partial resolution case).
    resolved_idents = {wp.identifier for wp in waypoints}
    tokens = request.route_string.strip().upper().split()
    unresolved = [
        t for t in tokens
        if t not in RouteParser.ROUTE_KEYWORDS and t not in resolved_idents
    ]

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
