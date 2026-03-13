"""Pydantic schemas for Route Cost calculation data validation."""

from pydantic import BaseModel, Field, field_validator
from typing import List
from decimal import Decimal
from uuid import UUID


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


class FIRChargeBreakdown(BaseModel):
    """
    Schema for per-FIR charge breakdown in route cost response.
    """
    
    icao_code: str = Field(
        ...,
        description="FIR ICAO code"
    )
    fir_name: str = Field(
        ...,
        description="FIR name"
    )
    country_code: str = Field(
        ...,
        description="Country code"
    )
    charge_amount: Decimal = Field(
        ...,
        description="Charge amount for this FIR"
    )
    currency: str = Field(
        ...,
        description="Currency code"
    )


class RouteCostResponse(BaseModel):
    """
    Schema for route cost calculation response.
    
    Includes total cost, currency, and per-FIR breakdown.
    """
    
    calculation_id: UUID = Field(
        ...,
        description="Unique calculation identifier"
    )
    total_cost: Decimal = Field(
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
