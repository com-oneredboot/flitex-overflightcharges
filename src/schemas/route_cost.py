"""Pydantic schemas for Route Cost calculation data validation."""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from uuid import UUID as PyUUID


class RouteCostRequest(BaseModel):
    """
    Schema for route cost calculation request.
    
    Validates Requirements: 9.1, 9.2, 9.5
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

    Validates Requirements: 9a.1, 9a.2, 9a.3, 12a.1, 12a.2, 12a.3, 12a.4
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


class RouteCostResponse(BaseModel):
    """
    Schema for route cost calculation response.
    
    Includes total cost, currency, and per-FIR breakdown.
    """
    
    calculation_id: PyUUID = Field(
        ...,
        description="Unique calculation identifier"
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
        description="Per-FIR charge breakdown"
    )
    
    model_config = {
        "from_attributes": True
    }
