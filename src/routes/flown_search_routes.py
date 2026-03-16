"""Flown Data Search API endpoint.

Provides a search endpoint for querying the flights_flown_data table
with flexible criteria and match confidence scoring.

POST /api/flights-flown/search — Search flown records by flight plan criteria.

Validates Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9
"""

import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.flights_flown_data import FlightsFlownData
from src.schemas.flown_search import (
    FlownRecordResponse,
    FlownSearchRequest,
    FlownSearchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/flights-flown", tags=["Flown Data Search"])

# Maximum number of results to return per search
MAX_RESULTS = 50

# Default date range window in days
DEFAULT_DATE_RANGE_DAYS = 7


def _parse_date(date_str: str) -> date:
    """Parse a YYYY-MM-DD string into a date object.

    Args:
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        Parsed date object.

    Raises:
        HTTPException: If the date format is invalid.
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Expected YYYY-MM-DD",
        )


def _compute_match_confidence(
    record: FlightsFlownData,
    search_flight_number: str,
    search_origin: str,
    search_destination: str,
    search_date: date | None,
) -> str:
    """Compute match confidence for a flown record against search criteria.

    Confidence is based on how many of the 4 primary fields match precisely:
    - "exact": all 4 match (flight_number exact case-insensitive, origin,
      destination, date exact day)
    - "partial": 2-3 match
    - "fuzzy": 0-1 match

    Note: flight_number comparison here is exact case-insensitive (not substring).
    The ILIKE substring is used for the query filter, but confidence scoring
    uses exact match.

    Args:
        record: The database record to evaluate.
        search_flight_number: The search flight number for exact comparison.
        search_origin: The search origin airport code.
        search_destination: The search destination airport code.
        search_date: The exact search date (midpoint), or None if not determinable.

    Returns:
        "exact", "partial", or "fuzzy".
    """
    matches = 0

    # Flight number: exact case-insensitive match
    if record.flight_number and record.flight_number.upper() == search_flight_number.upper():
        matches += 1

    # Origin: exact case-insensitive match
    if record.origin and record.origin.upper() == search_origin.upper():
        matches += 1

    # Destination: exact case-insensitive match
    if record.destination and record.destination.upper() == search_destination.upper():
        matches += 1

    # Date: exact day match
    if search_date and record.date == search_date:
        matches += 1

    if matches == 4:
        return "exact"
    elif matches >= 2:
        return "partial"
    else:
        return "fuzzy"


# Confidence sort order: exact first, then partial, then fuzzy
_CONFIDENCE_ORDER = {"exact": 0, "partial": 1, "fuzzy": 2}


@router.post("/search", response_model=FlownSearchResponse)
async def search_flown_data(
    request: FlownSearchRequest,
    db: Session = Depends(get_db),
) -> FlownSearchResponse:
    """Search flown flight data with flexible criteria and confidence scoring.

    Requires all 4 primary fields: flight_number, origin, destination, and
    at least one of date_from/date_to. Returns matched records with
    match_confidence classification, ordered by confidence descending then
    date descending, limited to 50 results.

    The route_string is NOT accepted as a search parameter.

    Validates Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9

    Args:
        request: Search criteria with required and optional fields.
        db: Database session (injected).

    Returns:
        FlownSearchResponse with matched records and total count.

    Raises:
        HTTPException: 400 if required fields are missing or dates are invalid.
        JSONResponse: 500 if a database error occurs.
    """
    # Validate all 4 primary fields are present
    if not request.flight_number or not request.origin or not request.destination:
        raise HTTPException(
            status_code=400,
            detail="All four primary search fields (flight_number, origin, destination, flight_date) are required",
        )

    if not request.date_from and not request.date_to:
        raise HTTPException(
            status_code=400,
            detail="All four primary search fields (flight_number, origin, destination, flight_date) are required",
        )

    # Parse dates
    date_from: date
    date_to: date

    if request.date_from and request.date_to:
        date_from = _parse_date(request.date_from)
        date_to = _parse_date(request.date_to)
    elif request.date_from:
        date_from = _parse_date(request.date_from)
        date_to = date_from + timedelta(days=DEFAULT_DATE_RANGE_DAYS)
    else:
        date_to = _parse_date(request.date_to)
        date_from = date_to - timedelta(days=DEFAULT_DATE_RANGE_DAYS)

    # Determine the "exact" search date for confidence scoring.
    # If both date_from and date_to are provided and equal, that's the exact date.
    # If only one is provided, use that as the reference date.
    # Otherwise, no exact date match is possible.
    search_date: date | None = None
    if request.date_from and request.date_to:
        df = _parse_date(request.date_from)
        dt = _parse_date(request.date_to)
        if df == dt:
            search_date = df
    elif request.date_from:
        search_date = _parse_date(request.date_from)
    elif request.date_to:
        search_date = _parse_date(request.date_to)

    try:
        # Build SQLAlchemy query
        query = db.query(FlightsFlownData)

        # flight_number: case-insensitive ILIKE substring match
        query = query.filter(
            FlightsFlownData.flight_number.ilike(f"%{request.flight_number}%")
        )

        # origin: exact case-insensitive match
        query = query.filter(
            func.upper(FlightsFlownData.origin) == request.origin.upper()
        )

        # destination: exact case-insensitive match
        query = query.filter(
            func.upper(FlightsFlownData.destination) == request.destination.upper()
        )

        # date: BETWEEN date_from and date_to
        query = query.filter(
            FlightsFlownData.date.between(date_from, date_to)
        )

        # Optional: registration exact case-insensitive match
        if request.registration:
            query = query.filter(
                func.upper(FlightsFlownData.registration) == request.registration.upper()
            )

        # Optional: aircraft_type exact case-insensitive match
        if request.aircraft_type:
            query = query.filter(
                func.upper(FlightsFlownData.aircraft_type) == request.aircraft_type.upper()
            )

        # Execute query (fetch more than limit to allow sorting by confidence)
        records = query.all()

        # Compute match_confidence for each record
        results_with_confidence: list[tuple[FlightsFlownData, str]] = []
        for record in records:
            confidence = _compute_match_confidence(
                record=record,
                search_flight_number=request.flight_number,
                search_origin=request.origin,
                search_destination=request.destination,
                search_date=search_date,
            )
            results_with_confidence.append((record, confidence))

        # Sort by confidence descending (exact → partial → fuzzy), then date descending
        results_with_confidence.sort(
            key=lambda x: (_CONFIDENCE_ORDER.get(x[1], 3), -(x[0].date.toordinal() if x[0].date else 0))
        )

        # Limit to MAX_RESULTS
        results_with_confidence = results_with_confidence[:MAX_RESULTS]

        # Build response
        response_results = []
        for record, confidence in results_with_confidence:
            response_results.append(
                FlownRecordResponse(
                    flight_id=str(record.flight_id),
                    flight_number=record.flight_number,
                    registration=record.registration,
                    date=record.date.isoformat() if record.date else "",
                    origin=record.origin,
                    destination=record.destination,
                    aircraft_type=record.aircraft_type,
                    distance=record.distance,
                    cost=float(record.cost) if record.cost is not None else None,
                    match_confidence=confidence,
                )
            )

        return FlownSearchResponse(
            results=response_results,
            total_count=len(response_results),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Database error during flown data search: %s", str(e), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
