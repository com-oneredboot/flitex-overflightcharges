"""Reference data API endpoints.

This module provides REST API endpoints for querying reference data:
- GET /api/reference/airports - List/search airports
- GET /api/reference/aircrafts - List/search aircraft models

Both endpoints support optional case-insensitive search filtering and
return 503 when the reference schema/tables have not been migrated.

Validates Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.reference import ReferenceAirport, ReferenceAircraft
from src.schemas.reference import AirportResponse, AircraftResponse

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/reference", tags=["Reference Data"])


@router.get(
    "/airports",
    response_model=list[AirportResponse],
    status_code=status.HTTP_200_OK,
)
async def get_airports(
    search: Optional[str] = Query(None, description="Case-insensitive search on ident, iata, name, city"),
    db: Session = Depends(get_db),
) -> list[AirportResponse] | JSONResponse:
    """Get list of airports, optionally filtered by search term.

    Searches case-insensitively against ident, iata, name, and city fields.
    Returns 200 with empty list when the table exists but has no data.
    Returns 503 when the reference schema/tables don't exist.

    Validates Requirements: 2.1, 2.2, 2.5, 2.6
    """
    try:
        query = db.query(ReferenceAirport)

        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    ReferenceAirport.ident.ilike(pattern),
                    ReferenceAirport.iata.ilike(pattern),
                    ReferenceAirport.name.ilike(pattern),
                    ReferenceAirport.city.ilike(pattern),
                )
            )

        airports = query.all()
        return airports

    except ProgrammingError as e:
        db.rollback()
        logger.warning(
            "Reference schema/tables not found",
            extra={"error": str(e)},
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Reference data migration has not been run. Execute 04-create-reference-tables.sql first."
            },
        )


@router.get(
    "/aircrafts",
    response_model=list[AircraftResponse],
    status_code=status.HTTP_200_OK,
)
async def get_aircrafts(
    search: Optional[str] = Query(None, description="Case-insensitive search on model"),
    db: Session = Depends(get_db),
) -> list[AircraftResponse] | JSONResponse:
    """Get list of aircraft models, optionally filtered by search term.

    Searches case-insensitively against the model field.
    Returns 200 with empty list when the table exists but has no data.
    Returns 503 when the reference schema/tables don't exist.

    Validates Requirements: 2.3, 2.4, 2.5, 2.6
    """
    try:
        query = db.query(ReferenceAircraft)

        if search:
            pattern = f"%{search}%"
            query = query.filter(ReferenceAircraft.model.ilike(pattern))

        aircrafts = query.all()
        return aircrafts

    except ProgrammingError as e:
        db.rollback()
        logger.warning(
            "Reference schema/tables not found",
            extra={"error": str(e)},
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Reference data migration has not been run. Execute 04-create-reference-tables.sql first."
            },
        )
