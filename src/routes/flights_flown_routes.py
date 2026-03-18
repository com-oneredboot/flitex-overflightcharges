"""Flights Flown Tab API endpoints.

Provides read-only paginated endpoints for querying flights_flown_loaded
and flights_flown_data tables.

GET /api/flights-flown/loaded — Paginated list of imported files.
GET /api/flights-flown/data   — Paginated list of flight records, optionally filtered by load_id.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.flights_flown_data import FlightsFlownData
from src.models.flights_flown_loaded import FlightsFlownLoaded
from src.schemas.flights_flown import (
    FlightsFlownDataListResponse,
    FlightsFlownDataResponse,
    FlightsFlownLoadedListResponse,
    FlightsFlownLoadedResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/flights-flown", tags=["Flights Flown"])


@router.get("/loaded", response_model=FlightsFlownLoadedListResponse)
async def get_flights_flown_loaded(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(5, ge=1, description="Number of records per page"),
    db: Session = Depends(get_db),
) -> FlightsFlownLoadedListResponse:
    """Return a paginated list of imported file records.

    Records are ordered by created_at descending (most recent first).
    Returns an empty list with total_count 0 when no records exist.
    """
    try:
        total_count = db.query(func.count(FlightsFlownLoaded.id)).scalar() or 0

        offset = (page - 1) * page_size
        records = (
            db.query(FlightsFlownLoaded)
            .order_by(FlightsFlownLoaded.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        results = [
            FlightsFlownLoadedResponse(
                id=str(record.id),
                filename=record.filename,
                status=record.status,
                records_processed=record.records_processed,
                created_at=record.created_at.isoformat() if record.created_at else "",
                updated_at=record.updated_at.isoformat() if record.updated_at else "",
                file_hash=record.file_hash,
                file_size_bytes=record.file_size_bytes,
                error_message=record.error_message,
                processing_started_at=record.processing_started_at.isoformat() if record.processing_started_at else None,
                processing_completed_at=record.processing_completed_at.isoformat() if record.processing_completed_at else None,
                linked_to_original_id=str(record.linked_to_original_id) if record.linked_to_original_id else None,
            )
            for record in records
        ]

        return FlightsFlownLoadedListResponse(
            results=results,
            total_count=total_count,
        )

    except Exception as e:
        logger.error("Database error fetching flights flown loaded: %s", str(e), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )


@router.get("/data", response_model=FlightsFlownDataListResponse)
async def get_flights_flown_data(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, description="Number of records per page"),
    load_id: Optional[UUID] = Query(None, description="Filter by load_id (UUID)"),
    db: Session = Depends(get_db),
) -> FlightsFlownDataListResponse:
    """Return a paginated list of flight data records.

    Records are ordered by date descending (most recent first).
    Optionally filtered by load_id to show only records from a specific import.
    Returns an empty list with total_count 0 when no records match.
    """
    try:
        query = db.query(FlightsFlownData)
        count_query = db.query(func.count(FlightsFlownData.flight_id))

        if load_id is not None:
            query = query.filter(FlightsFlownData.load_id == load_id)
            count_query = count_query.filter(FlightsFlownData.load_id == load_id)

        total_count = count_query.scalar() or 0

        offset = (page - 1) * page_size
        records = (
            query.order_by(FlightsFlownData.date.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        results = [
            FlightsFlownDataResponse(
                flight_id=str(record.flight_id),
                flight_number=record.flight_number,
                registration=record.registration,
                date=record.date.isoformat() if record.date else "",
                origin=record.origin,
                destination=record.destination,
                aircraft_type=record.aircraft_type,
                distance=record.distance,
                cost=float(record.cost) if record.cost is not None else None,
                user_number=record.user_number,
                load_id=str(record.load_id) if record.load_id else None,
            )
            for record in records
        ]

        return FlightsFlownDataListResponse(
            results=results,
            total_count=total_count,
        )

    except Exception as e:
        logger.error("Database error fetching flights flown data: %s", str(e), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
