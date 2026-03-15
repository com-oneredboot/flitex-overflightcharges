"""Pydantic response schemas for reference data API endpoints.

Defines request/response schemas for airport search, aircraft search,
and route validation endpoints.

Validates Requirements: 2.1, 2.3, 3.2, 3.3, 8.1, 9.1, 9.3, 21.5
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


def _to_camel(name: str) -> str:
    """Convert snake_case field name to camelCase for JSON serialization."""
    parts = name.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class AirportResponse(BaseModel):
    """Response schema for airport reference data.

    Returned by GET /api/reference/airports endpoint.

    Validates Requirements: 2.1, 2.2
    """

    ident: str = Field(
        ...,
        description="ICAO airport identifier",
    )
    iata: Optional[str] = Field(
        None,
        description="IATA airport code",
    )
    name: Optional[str] = Field(
        None,
        description="Airport name",
    )
    city: Optional[str] = Field(
        None,
        description="City where the airport is located",
    )
    country: Optional[str] = Field(
        None,
        description="Country where the airport is located",
    )

    model_config = ConfigDict(from_attributes=True)


class AircraftResponse(BaseModel):
    """Response schema for aircraft reference data.

    Returned by GET /api/reference/aircrafts endpoint.
    The `details` JSONB field contains aircraft specifications
    including `mass_max` (MTOW in kg).

    Validates Requirements: 2.3, 2.4
    """

    model: str = Field(
        ...,
        description="Aircraft model designator",
    )
    details: dict = Field(
        ...,
        description="Aircraft specification details (JSONB), includes mass_max for MTOW",
    )

    model_config = ConfigDict(from_attributes=True)


class RouteValidationRequest(BaseModel):
    """Request schema for route string validation.

    Validates Requirements: 3.1, 3.2, 3.3
    """

    route_string: str = Field(
        ...,
        min_length=1,
        description="ICAO-formatted flight route string (e.g., 'KJFK DCT CYYZ DCT EGLL')",
    )


class ResolvedWaypoint(BaseModel):
    """A waypoint identifier resolved against the navigation database.

    Contains the coordinates and source table for a successfully
    resolved waypoint.

    Validates Requirements: 3.2
    """

    identifier: str = Field(
        ...,
        description="Waypoint identifier as it appeared in the route string",
    )
    latitude: float = Field(
        ...,
        description="Latitude of the resolved waypoint",
    )
    longitude: float = Field(
        ...,
        description="Longitude of the resolved waypoint",
    )
    source_table: str = Field(
        ...,
        description="Reference table that resolved this waypoint (e.g., airports, nav_waypoints)",
    )


class FIRCrossing(BaseModel):
    """A Flight Information Region crossed by the validated route.

    Extended with distance fields from the FIR intersection engine:
    segment distance (actual path through FIR), great circle entry/exit
    distance, entry/exit points, distance method, and charge type.

    Supports camelCase serialization for JSON API responses via alias_generator.

    Validates Requirements: 3.5, 8.1, 9.1, 9.3, 21.5
    """

    icao_code: str = Field(
        ...,
        description="ICAO code of the FIR",
    )
    fir_name: str = Field(
        ...,
        description="Name of the FIR",
    )
    country: Optional[str] = Field(
        None,
        description="Country of the FIR",
    )
    segment_distance_km: Optional[float] = Field(
        default=None,
        description="Segment distance through FIR in kilometers (actual path length)",
    )
    segment_distance_nm: Optional[float] = Field(
        default=None,
        description="Segment distance through FIR in nautical miles (actual path length)",
    )
    gc_entry_exit_distance_km: Optional[float] = Field(
        default=None,
        description="Great circle distance between entry and exit points in kilometers",
    )
    gc_entry_exit_distance_nm: Optional[float] = Field(
        default=None,
        description="Great circle distance between entry and exit points in nautical miles",
    )
    entry_point: Optional[dict] = Field(
        default=None,
        description="Entry point into FIR as {lat, lon}",
    )
    exit_point: Optional[dict] = Field(
        default=None,
        description="Exit point from FIR as {lat, lon}",
    )
    distance_method: Optional[str] = Field(
        default=None,
        description="Distance method used for charge calculation: 'segment' or 'gc_entry_exit'",
    )
    charge_type: Optional[str] = Field(
        default="overflight",
        description="Charge type: 'overflight' (default), extensible for future types",
    )

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=_to_camel,
        populate_by_name=True,
    )


class RouteValidationResponse(BaseModel):
    """Response schema for route string validation.

    Contains the validation result including resolved waypoints,
    FIR crossings, and any unresolved identifiers.

    Validates Requirements: 3.2, 3.3
    """

    valid: bool = Field(
        ...,
        description="True if all waypoint identifiers were resolved successfully",
    )
    waypoints: list[ResolvedWaypoint] = Field(
        ...,
        description="Ordered list of resolved waypoints with coordinates",
    )
    fir_crossings: list[FIRCrossing] = Field(
        ...,
        description="FIR regions crossed by the route, ordered by first encounter",
    )
    unresolved: list[str] = Field(
        ...,
        description="List of waypoint identifiers that could not be resolved (empty on success)",
    )
