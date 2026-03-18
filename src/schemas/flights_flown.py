"""Pydantic schemas for Flights Flown tab endpoints.

Defines response schemas for the flights_flown_loaded and flights_flown_data
tables, used by the GET /api/flights-flown/loaded and GET /api/flights-flown/data
endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


class FlightsFlownLoadedResponse(BaseModel):
    """Response schema for a single flights_flown_loaded record.

    Represents an imported file's audit record including processing
    status, timestamps, and metadata.
    """

    id: str = Field(
        ...,
        description="Unique process identifier",
    )
    filename: str = Field(
        ...,
        description="Original filename submitted for processing",
    )
    status: str = Field(
        ...,
        description="Processing status: pending, validating, parsing, completed, duplicate, failed",
    )
    records_processed: Optional[int] = Field(
        None,
        description="Count of records successfully inserted",
    )
    created_at: str = Field(
        ...,
        description="Timestamp when record was created",
    )
    updated_at: str = Field(
        ...,
        description="Timestamp when record was last updated",
    )
    file_hash: str = Field(
        ...,
        description="SHA-256 hash of file contents for duplicate detection",
    )
    file_size_bytes: int = Field(
        ...,
        description="File size in bytes",
    )
    error_message: Optional[str] = Field(
        None,
        description="Error details if processing failed",
    )
    processing_started_at: Optional[str] = Field(
        None,
        description="Timestamp when processing began",
    )
    processing_completed_at: Optional[str] = Field(
        None,
        description="Timestamp when processing finished",
    )
    linked_to_original_id: Optional[str] = Field(
        None,
        description="Reference to original record if this is a duplicate submission",
    )


class FlightsFlownLoadedListResponse(BaseModel):
    """Paginated response for flights_flown_loaded records."""

    results: list[FlightsFlownLoadedResponse] = Field(
        ...,
        description="List of imported file records",
    )
    total_count: int = Field(
        ...,
        description="Total number of records matching the query",
    )


class FlightsFlownDataResponse(BaseModel):
    """Response schema for a single flights_flown_data record.

    Represents a flight record with route, aircraft, and cost details.
    """

    flight_id: str = Field(
        ...,
        description="Unique flight record identifier",
    )
    flight_number: str = Field(
        ...,
        description="Flight number",
    )
    registration: Optional[str] = Field(
        None,
        description="Aircraft registration number",
    )
    date: str = Field(
        ...,
        description="Flight date in YYYY-MM-DD format",
    )
    origin: str = Field(
        ...,
        description="Origin airport ICAO code",
    )
    destination: str = Field(
        ...,
        description="Destination airport ICAO code",
    )
    aircraft_type: Optional[str] = Field(
        None,
        description="Aircraft type designation",
    )
    distance: Optional[int] = Field(
        None,
        description="Flight distance in miles",
    )
    cost: Optional[float] = Field(
        None,
        description="Flight cost",
    )
    user_number: Optional[str] = Field(
        None,
        description="User identifier",
    )
    load_id: Optional[str] = Field(
        None,
        description="Reference to the flights_flown_loaded record",
    )


class FlightsFlownDataListResponse(BaseModel):
    """Paginated response for flights_flown_data records."""

    results: list[FlightsFlownDataResponse] = Field(
        ...,
        description="List of flight data records",
    )
    total_count: int = Field(
        ...,
        description="Total number of records matching the query",
    )
