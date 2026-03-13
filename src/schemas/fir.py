"""Pydantic schemas for FIR (Flight Information Region) data validation."""

from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional
from datetime import datetime


class FIRBase(BaseModel):
    """
    Base schema for FIR data with common fields and validation.
    
    Validates Requirements: 9.1, 9.2, 9.3, 9.4
    """
    
    icao_code: str = Field(
        ...,
        min_length=4,
        max_length=4,
        description="ICAO code (4 uppercase alphanumeric characters)"
    )
    fir_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="FIR name"
    )
    country_code: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code"
    )
    country_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Country name"
    )
    geojson_geometry: Dict[str, Any] = Field(
        ...,
        description="GeoJSON geometry for FIR boundary"
    )
    bbox_min_lon: Optional[float] = Field(
        None,
        description="Minimum longitude of bounding box"
    )
    bbox_min_lat: Optional[float] = Field(
        None,
        description="Minimum latitude of bounding box"
    )
    bbox_max_lon: Optional[float] = Field(
        None,
        description="Maximum longitude of bounding box"
    )
    bbox_max_lat: Optional[float] = Field(
        None,
        description="Maximum latitude of bounding box"
    )
    avoid_status: bool = Field(
        default=False,
        description="Whether this FIR should be avoided"
    )
    
    @field_validator("icao_code")
    @classmethod
    def validate_icao_code(cls, v: str) -> str:
        """
        Validate ICAO code pattern: 4 uppercase alphanumeric characters.
        
        Validates Requirement: 9.3
        """
        if not v.isupper():
            raise ValueError("ICAO code must be uppercase")
        if not v.isalnum():
            raise ValueError("ICAO code must be alphanumeric")
        if len(v) != 4:
            raise ValueError("ICAO code must be exactly 4 characters")
        return v
    
    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        """
        Validate country code pattern: 2 uppercase letters.
        
        Validates Requirement: 9.4
        """
        if not v.isupper():
            raise ValueError("Country code must be uppercase")
        if not v.isalpha():
            raise ValueError("Country code must contain only letters")
        if len(v) != 2:
            raise ValueError("Country code must be exactly 2 characters")
        return v
    
    @field_validator("geojson_geometry")
    @classmethod
    def validate_geojson_geometry(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate GeoJSON geometry structure.
        
        Validates Requirement: 9.4
        """
        if not isinstance(v, dict):
            raise ValueError("GeoJSON geometry must be a dictionary")
        
        if "type" not in v:
            raise ValueError("GeoJSON geometry must have a 'type' field")
        
        valid_types = [
            "Point", "MultiPoint", "LineString", "MultiLineString",
            "Polygon", "MultiPolygon", "GeometryCollection"
        ]
        if v["type"] not in valid_types:
            raise ValueError(
                f"GeoJSON type must be one of: {', '.join(valid_types)}"
            )
        
        if v["type"] != "GeometryCollection" and "coordinates" not in v:
            raise ValueError(
                f"GeoJSON geometry of type '{v['type']}' must have 'coordinates' field"
            )
        
        if v["type"] == "GeometryCollection" and "geometries" not in v:
            raise ValueError(
                "GeoJSON GeometryCollection must have 'geometries' field"
            )
        
        return v


class FIRCreate(FIRBase):
    """
    Schema for creating a new FIR record.
    
    Inherits all fields and validation from FIRBase.
    """
    pass


class FIRUpdate(BaseModel):
    """
    Schema for updating an existing FIR record.
    
    All fields are optional to support partial updates.
    """
    
    fir_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="FIR name"
    )
    country_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Country name"
    )
    geojson_geometry: Optional[Dict[str, Any]] = Field(
        None,
        description="GeoJSON geometry for FIR boundary"
    )
    bbox_min_lon: Optional[float] = Field(
        None,
        description="Minimum longitude of bounding box"
    )
    bbox_min_lat: Optional[float] = Field(
        None,
        description="Minimum latitude of bounding box"
    )
    bbox_max_lon: Optional[float] = Field(
        None,
        description="Maximum longitude of bounding box"
    )
    bbox_max_lat: Optional[float] = Field(
        None,
        description="Maximum latitude of bounding box"
    )
    avoid_status: Optional[bool] = Field(
        None,
        description="Whether this FIR should be avoided"
    )
    
    @field_validator("geojson_geometry")
    @classmethod
    def validate_geojson_geometry(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Validate GeoJSON geometry structure if provided.
        
        Validates Requirement: 9.4
        """
        if v is None:
            return v
        
        if not isinstance(v, dict):
            raise ValueError("GeoJSON geometry must be a dictionary")
        
        if "type" not in v:
            raise ValueError("GeoJSON geometry must have a 'type' field")
        
        valid_types = [
            "Point", "MultiPoint", "LineString", "MultiLineString",
            "Polygon", "MultiPolygon", "GeometryCollection"
        ]
        if v["type"] not in valid_types:
            raise ValueError(
                f"GeoJSON type must be one of: {', '.join(valid_types)}"
            )
        
        if v["type"] != "GeometryCollection" and "coordinates" not in v:
            raise ValueError(
                f"GeoJSON geometry of type '{v['type']}' must have 'coordinates' field"
            )
        
        if v["type"] == "GeometryCollection" and "geometries" not in v:
            raise ValueError(
                "GeoJSON GeometryCollection must have 'geometries' field"
            )
        
        return v


class FIRResponse(FIRBase):
    """
    Schema for FIR response data.
    
    Includes all fields from FIRBase plus timestamps.
    """
    
    created_at: datetime = Field(
        ...,
        description="Record creation timestamp"
    )
    updated_at: datetime = Field(
        ...,
        description="Record last update timestamp"
    )
    
    model_config = {
        "from_attributes": True
    }
