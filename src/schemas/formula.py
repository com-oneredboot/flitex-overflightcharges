"""Pydantic schemas for Formula data validation."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any
from datetime import date, datetime
from uuid import UUID


class FormulaBase(BaseModel):
    """
    Base schema for Formula data with common fields and validation.
    
    Validates Requirements: 4.3, 4.4, 9.1, 9.2, 9.4
    """
    
    country_code: Optional[str] = Field(
        None,
        description="ISO 3166-1 alpha-2 country code (null for regional formulas)"
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Human-readable description (country name or region name)"
    )
    formula_code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Formula identifier code"
    )
    formula_logic: str = Field(
        ...,
        min_length=1,
        description="Python code for formula calculation",
        serialization_alias="formula_expression"
    )
    effective_date: date = Field(
        ...,
        description="Date when formula becomes effective"
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code"
    )
    
    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate country code pattern: 2 uppercase letters or None for regional formulas.
        
        Validates Requirements: 4.4, 7.3
        """
        if v is None:
            return v  # Allow NULL for regional formulas
        
        if not v.isupper():
            raise ValueError("Country code must be uppercase")
        if not v.isalpha():
            raise ValueError("Country code must contain only letters")
        if len(v) != 2:
            raise ValueError("Country code must be exactly 2 characters")
        return v
    
    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """
        Validate currency pattern: 3 uppercase letters.
        
        Validates Requirement: 9.4
        """
        if not v.isupper():
            raise ValueError("Currency must be uppercase")
        if not v.isalpha():
            raise ValueError("Currency must contain only letters")
        if len(v) != 3:
            raise ValueError("Currency must be exactly 3 characters")
        return v


class FormulaCreate(FormulaBase):
    """
    Schema for creating a new formula record.
    
    Inherits all fields from FormulaBase and adds created_by.
    """
    
    created_by: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User who created the formula"
    )


class FormulaUpdate(BaseModel):
    """
    Schema for updating an existing formula record.
    
    All fields are optional except created_by to support partial updates.
    Creates a new version when applied.
    """
    
    description: Optional[str] = Field(
        None,
        min_length=1,
        description="Human-readable description (country name or region name)"
    )
    formula_code: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Formula identifier code"
    )
    formula_logic: Optional[str] = Field(
        None,
        min_length=1,
        description="Python code for formula calculation"
    )
    effective_date: Optional[date] = Field(
        None,
        description="Date when formula becomes effective"
    )
    currency: Optional[str] = Field(
        None,
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code"
    )
    created_by: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User who updated the formula"
    )
    
    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate currency pattern: 3 uppercase letters.
        
        Validates Requirement: 9.4
        """
        if v is None:
            return v
        
        if not v.isupper():
            raise ValueError("Currency must be uppercase")
        if not v.isalpha():
            raise ValueError("Currency must contain only letters")
        if len(v) != 3:
            raise ValueError("Currency must be exactly 3 characters")
        return v


class FormulaRollback(BaseModel):
    """
    Schema for rolling back to a specific formula version.
    """
    
    version_number: int = Field(
        ...,
        gt=0,
        description="Version number to rollback to"
    )
    
    @field_validator("version_number")
    @classmethod
    def validate_version_number(cls, v: int) -> int:
        """
        Validate version number is greater than 0.
        
        Validates Requirement: 9.4
        """
        if v <= 0:
            raise ValueError("Version number must be greater than 0")
        return v


class FormulaResponse(FormulaBase):
    """
    Schema for formula response data.
    
    Includes all fields from FormulaBase plus version info and timestamps.
    """
    
    id: UUID = Field(
        ...,
        description="Unique formula identifier"
    )
    version_number: int = Field(
        ...,
        description="Formula version number"
    )
    is_active: bool = Field(
        ...,
        description="Whether this version is currently active"
    )
    created_at: datetime = Field(
        ...,
        description="Record creation timestamp"
    )
    created_by: str = Field(
        ...,
        description="User who created this version"
    )
    
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "by_alias": True
    }


# New schemas for Task 10: Formula Execution and CRUD endpoints

class FormulaExecutionRequest(BaseModel):
    """
    Request schema for formula execution.
    
    Validates Requirements: 4.2, 4.3, 4.4, 8.3
    """
    
    formula_id: UUID = Field(
        ...,
        description="UUID of formula to execute"
    )
    distance: float = Field(
        ...,
        gt=0,
        description="Distance in nautical miles"
    )
    weight: float = Field(
        ...,
        gt=0,
        description="Weight in tonnes"
    )
    context: dict[str, Any] = Field(
        ...,
        description="Context data with firTag, arrival, departure, isFirstFir, isLastFir, firName, originCountry, destinationCountry"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "formula_id": "123e4567-e89b-12d3-a456-426614174000",
                "distance": 1500.5,
                "weight": 75.0,
                "context": {
                    "firTag": "EGTT",
                    "arrival": "EGLL",
                    "departure": "KJFK",
                    "isFirstFir": False,
                    "isLastFir": False,
                    "firName": "London",
                    "originCountry": "US",
                    "destinationCountry": "GB"
                }
            }
        }
    }


class FormulaExecutionResponse(BaseModel):
    """
    Response schema for formula execution.
    
    Validates Requirements: 4.5, 4.6, 8.5
    """
    
    cost: float = Field(
        ...,
        description="Calculated cost in formula currency"
    )
    currency: str = Field(
        ...,
        description="ISO 4217 currency code"
    )
    usd_cost: float = Field(
        ...,
        description="Cost converted to USD"
    )
    euro_cost: Optional[float] = Field(
        None,
        description="Cost in euros (for EuroControl formulas)"
    )
    execution_time_ms: float = Field(
        ...,
        description="Execution time in milliseconds"
    )
    cache_hit: bool = Field(
        ...,
        description="Whether result was cached"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "cost": 1250.50,
                "currency": "EUR",
                "usd_cost": 1375.55,
                "euro_cost": 1250.50,
                "execution_time_ms": 12.5,
                "cache_hit": False
            }
        }
    }


class FormulaValidationRequest(BaseModel):
    """
    Request schema for formula validation and save.
    
    Validates Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10
    """
    
    formula_code: str = Field(
        ...,
        description="Python code for formula"
    )
    country_code: Optional[str] = Field(
        None,
        min_length=2,
        max_length=2,
        description="ISO country code or None for regional"
    )
    description: str = Field(
        ...,
        description="Human-readable description"
    )
    formula_code_id: str = Field(
        ...,
        max_length=50,
        description="Formula code identifier"
    )
    effective_date: date = Field(
        ...,
        description="Effective date"
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="ISO currency code"
    )
    created_by: str = Field(
        ...,
        max_length=255,
        description="User creating formula"
    )
    
    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, v: Optional[str]) -> Optional[str]:
        """Validate country code pattern: 2 uppercase letters or None."""
        if v is None:
            return v
        if not v.isupper():
            raise ValueError("Country code must be uppercase")
        if not v.isalpha():
            raise ValueError("Country code must contain only letters")
        if len(v) != 2:
            raise ValueError("Country code must be exactly 2 characters")
        return v
    
    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate currency pattern: 3 uppercase letters."""
        if not v.isupper():
            raise ValueError("Currency must be uppercase")
        if not v.isalpha():
            raise ValueError("Currency must contain only letters")
        if len(v) != 3:
            raise ValueError("Currency must be exactly 3 characters")
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "formula_code": "def calculate(distance, weight, context):\n    return {'cost': distance * 10, 'currency': 'USD', 'usd_cost': distance * 10}",
                "country_code": "US",
                "description": "United States",
                "formula_code_id": "US_FORMULA",
                "effective_date": "2024-01-01",
                "currency": "USD",
                "created_by": "admin@example.com"
            }
        }
    }


class FormulaCreateResponse(BaseModel):
    """
    Response schema for formula creation.
    
    Validates Requirements: 11.10
    """
    
    id: UUID = Field(
        ...,
        description="UUID of created formula"
    )
    formula_hash: str = Field(
        ...,
        description="SHA256 hash of formatted formula code"
    )
    version: int = Field(
        ...,
        description="Version number (always 1 for new formulas)"
    )
    message: str = Field(
        ...,
        description="Success message"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "323e4567-e89b-12d3-a456-426614174002",
                "formula_hash": "a3b2c1d4e5f6...",
                "version": 1,
                "message": "Formula validated and saved successfully"
            }
        }
    }


class FormulaUpdateResponse(BaseModel):
    """
    Response schema for formula update.
    
    Validates Requirements: 1.3, 11.10
    """
    
    id: UUID = Field(
        ...,
        description="UUID of updated formula"
    )
    formula_hash: str = Field(
        ...,
        description="SHA256 hash of formatted formula code"
    )
    version: int = Field(
        ...,
        description="New version number"
    )
    message: str = Field(
        ...,
        description="Success message"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "323e4567-e89b-12d3-a456-426614174002",
                "formula_hash": "b4c3d2e1f0a9...",
                "version": 2,
                "message": "Formula updated successfully"
            }
        }
    }


class FormulaBytecodeResponse(BaseModel):
    """
    Response schema for formula with bytecode.
    
    Used in GET /api/formulas endpoint for bulk fetch.
    Validates Requirements: 8.2, 5.1
    """
    
    id: UUID = Field(
        ...,
        description="UUID of formula"
    )
    country_code: Optional[str] = Field(
        None,
        description="ISO country code or None for regional"
    )
    description: str = Field(
        ...,
        description="Human-readable description"
    )
    bytecode: str = Field(
        ...,
        description="Base64-encoded compiled bytecode"
    )
    version: int = Field(
        ...,
        description="Version number"
    )
    currency: str = Field(
        ...,
        description="ISO currency code"
    )


class FormulaExecutionContextResponse(BaseModel):
    """
    Response schema for formula execution context.
    
    Provides constants, utilities, math functions, and EuroControl rates.
    Validates Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.8, 10.3
    """
    
    constants: dict[str, Any] = Field(
        ...,
        description="Currency, country, FIR, and aerodrome constants"
    )
    utilities: dict[str, str] = Field(
        ...,
        description="Utility function descriptions"
    )
    math_functions: list[str] = Field(
        ...,
        description="Available math functions"
    )
    eurocontrol_rates: dict[str, Any] = Field(
        ...,
        description="EuroControl unit rates indexed by country and date"
    )
    cached_at: datetime = Field(
        ...,
        description="Timestamp when context was cached"
    )
    cache_ttl_seconds: int = Field(
        ...,
        description="Cache TTL in seconds"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "constants": {
                    "currencies": {"USD": "USD", "EUR": "EUR"},
                    "countries": {"USA": "USA", "CANADA": "Canada"},
                    "fir_names_per_country": {"USA": ["KZAB", "PAZA"]},
                    "canada_tsc_aerodromes": []
                },
                "utilities": {
                    "convert_nm_to_km": "function to convert nautical miles to kilometers (multiply by 1.852)"
                },
                "math_functions": ["sqrt", "pow", "abs", "ceil", "floor", "round"],
                "eurocontrol_rates": {},
                "cached_at": "2024-01-01T12:00:00Z",
                "cache_ttl_seconds": 900
            }
        }
    }
