"""Pydantic schemas for Route Cost calculation data validation.

Validates Requirements: 9.1, 9.2, 9.5, 10.1, 12.1, 13.3
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from uuid import UUID as PyUUID


class RouteCostRequest(BaseModel):
    """
    Schema for route cost calculation request.

    Accepts existing parameters plus flight_number, flight_date, and callsign
    for the enhanced calculation pipeline.

    Validates Requirements: 9.1, 9.2, 9.5, 10.2
    """

    route_string: str = Field(
        ...,
        min_length=1,
        description="ICAO-formatted flight route specification"
    )
    origin: str = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Origin airport ICAO code"
    )
    destination: str = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Destination airport ICAO code"
    )
    aircraft_type: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Aircraft type code"
    )
    mtow_kg: float = Field(
        ...,
        gt=0,
        description="Maximum Takeoff Weight in kilograms"
    )
    flight_number: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Flight number for session matching and invoice comparison"
    )
    flight_date: Optional[str] = Field(
        default=None,
        description="Flight date in YYYY-MM-DD format (used for NAT track lookup and session matching)"
    )
    callsign: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Aircraft callsign"
    )

    @field_validator("origin", "destination")
    @classmethod
    def validate_icao_code(cls, v: str) -> str:
        """
        Validate ICAO code pattern: 4 uppercase letters.

        Validates Requirement: 9.1
        """
        if not v.isupper():
            raise ValueError("ICAO code must be uppercase")
        if not v.isalpha():
            raise ValueError("ICAO code must contain only letters")
        if len(v) != 4:
            raise ValueError("ICAO code must be exactly 4 characters")
        return v

    @field_validator("mtow_kg")
    @classmethod
    def validate_mtow(cls, v: float) -> float:
        """
        Validate MTOW is greater than zero.

        Validates Requirement: 9.5
        """
        if v <= 0:
            raise ValueError("MTOW must be greater than zero")
        return v


class FIRWarning(BaseModel):
    """
    Schema for per-FIR warning when formula execution fails or no formula exists.

    Validates Requirements: 2.2, 2.3
    """

    message: str = Field(
        ...,
        description="Short warning message summary"
    )
    detail: str = Field(
        ...,
        description="Detailed error context including FIR code, country code, formula code, error type, and error message"
    )


class FIRChargeBreakdown(BaseModel):
    """
    Schema for per-FIR charge breakdown in route cost response.

    Includes distance data (segment and great circle) and entry/exit points
    from the enhanced FIR intersection pipeline.

    Validates Requirements: 8.1, 9.1, 9a.1, 9a.2, 9a.3, 12a.1, 12a.2, 12a.3, 12a.4
    """

    icao_code: str = Field(
        ...,
        description="FIR ICAO code"
    )
    fir_id: Optional[PyUUID] = Field(
        default=None,
        description="FIR UUID for database storage"
    )
    fir_name: str = Field(
        ...,
        description="FIR name"
    )
    country_code: str = Field(
        ...,
        description="Country code"
    )
    charge_amount: float = Field(
        ...,
        description="Charge amount for this FIR"
    )
    currency: str = Field(
        ...,
        description="Currency code"
    )
    formula_code: str = Field(
        ...,
        description="Formula code identifier used for the charge calculation"
    )
    formula_version: Optional[int] = Field(
        default=None,
        description="Version number of the formula used"
    )
    formula_description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the formula"
    )
    formula_logic: Optional[str] = Field(
        default=None,
        description="Formula calculation expression"
    )
    effective_date: Optional[str] = Field(
        default=None,
        description="Formula effective date in YYYY-MM-DD format"
    )
    warning: Optional[FIRWarning] = Field(
        default=None,
        description="Warning object when formula execution fails or no formula exists"
    )
    segment_distance_km: Optional[float] = Field(
        default=None,
        description="Segment distance through FIR in kilometers"
    )
    segment_distance_nm: Optional[float] = Field(
        default=None,
        description="Segment distance through FIR in nautical miles"
    )
    gc_entry_exit_distance_km: Optional[float] = Field(
        default=None,
        description="Great circle entry/exit distance in kilometers"
    )
    gc_entry_exit_distance_nm: Optional[float] = Field(
        default=None,
        description="Great circle entry/exit distance in nautical miles"
    )
    entry_point: Optional[dict] = Field(
        default=None,
        description="Entry point into FIR as {lat, lon}"
    )
    exit_point: Optional[dict] = Field(
        default=None,
        description="Exit point from FIR as {lat, lon}"
    )
    distance_method: Optional[str] = Field(
        default=None,
        description="Distance method used for charge: segment or gc_entry_exit"
    )
    charge_type: Optional[str] = Field(
        default="overflight",
        description="Charge type: overflight (default), extensible for future types"
    )
    unit_rate: Optional[float] = Field(
        default=None,
        description="Unit rate used in the charge calculation"
    )
    distance_factor: Optional[float] = Field(
        default=None,
        description="Distance factor (d/100) used in the charge calculation"
    )
    weight_factor: Optional[float] = Field(
        default=None,
        description="Weight factor sqrt(MTOW_t/50) used in the charge calculation"
    )


class CoverageGap(BaseModel):
    """A single coverage gap between consecutive FIR crossings."""
    after_fir_icao: str = Field(..., description="ICAO code of the FIR before the gap")
    before_fir_icao: str = Field(..., description="ICAO code of the FIR after the gap")
    exit_point: dict = Field(..., description="Exit point from preceding FIR as {lat, lon}")
    entry_point: dict = Field(..., description="Entry point into following FIR as {lat, lon}")
    gap_distance_nm: float = Field(..., description="Gap distance in nautical miles")


class CoverageSummary(BaseModel):
    """Aggregate coverage statistics for a route."""
    total_gap_distance_nm: float = Field(..., description="Sum of all gap distances in nm")
    gap_count: int = Field(..., description="Number of coverage gaps")
    coverage_pct: float = Field(..., description="FIR coverage percentage (0-100)")


class RouteCostResponse(BaseModel):
    """
    Schema for route cost calculation response.

    Includes calculation_id, total cost, currency, per-FIR breakdown with
    distance data, and total route distance.

    Validates Requirements: 10.1, 12.1, 13.3
    """

    calculation_id: PyUUID = Field(
        ...,
        description="Unique calculation identifier (calculationId in JSON)"
    )
    total_cost: float = Field(
        ...,
        description="Total overflight charge"
    )
    currency: str = Field(
        ...,
        description="Currency code"
    )
    fir_breakdown: List[FIRChargeBreakdown] = Field(
        ...,
        description="Per-FIR charge breakdown with distance data"
    )
    total_distance_km: Optional[float] = Field(
        default=None,
        description="Total route distance in kilometers"
    )
    total_distance_nm: Optional[float] = Field(
        default=None,
        description="Total route distance in nautical miles"
    )
    fir_count: Optional[int] = Field(
        default=None,
        description="Number of FIRs crossed"
    )
    coverage_gaps: List[CoverageGap] = Field(
        default_factory=list,
        description="Coverage gaps between FIR crossings"
    )
    coverage_summary: Optional[CoverageSummary] = Field(
        default=None,
        description="Aggregate coverage statistics"
    )

    model_config = {
        "from_attributes": True
    }
