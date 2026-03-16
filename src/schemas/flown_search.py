"""Pydantic schemas for Flown Data Search endpoint.

Defines request/response schemas for searching the flights_flown_data table
and returning matched records with confidence scoring.

Validates Requirements: 1.1, 1.6
"""

from pydantic import BaseModel, Field
from typing import Optional


class FlownSearchRequest(BaseModel):
    """Request schema for searching flown flight data.

    All four primary fields (flight_number, origin, destination, and at least
    one of date_from/date_to) are required for a valid search. Registration
    and aircraft_type are optional additional filters.

    Validates Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
    """

    flight_number: Optional[str] = Field(
        None,
        description="Flight number for substring matching (case-insensitive)",
    )
    origin: Optional[str] = Field(
        None,
        description="Origin airport ICAO code (exact match, case-insensitive)",
    )
    destination: Optional[str] = Field(
        None,
        description="Destination airport ICAO code (exact match, case-insensitive)",
    )
    date_from: Optional[str] = Field(
        None,
        description="Start of date range in YYYY-MM-DD format",
    )
    date_to: Optional[str] = Field(
        None,
        description="End of date range in YYYY-MM-DD format",
    )
    registration: Optional[str] = Field(
        None,
        description="Aircraft registration number (exact match, case-insensitive)",
    )
    aircraft_type: Optional[str] = Field(
        None,
        description="Aircraft type designation (exact match, case-insensitive)",
    )


class FlownRecordResponse(BaseModel):
    """Response schema for a single matched flown record.

    Includes all flight data fields plus a match_confidence classification
    indicating how closely the record matches the search criteria.

    Validates Requirements: 1.6
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
    match_confidence: str = Field(
        ...,
        description="Match confidence: 'exact', 'partial', or 'fuzzy'",
    )


class FlownSearchResponse(BaseModel):
    """Response schema for flown data search results.

    Contains the list of matched records and total count.

    Validates Requirements: 1.1, 1.7
    """

    results: list[FlownRecordResponse] = Field(
        ...,
        description="List of matched flown records with confidence scoring",
    )
    total_count: int = Field(
        ...,
        description="Total number of matched records",
    )
