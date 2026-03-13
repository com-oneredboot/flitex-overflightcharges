"""Unit tests for FIR Pydantic schemas."""

import pytest
from datetime import datetime
from pydantic import ValidationError
from src.schemas.fir import FIRBase, FIRCreate, FIRUpdate, FIRResponse


class TestFIRBase:
    """Tests for FIRBase schema."""
    
    def test_valid_fir_base(self):
        """Test creating FIRBase with valid data."""
        fir = FIRBase(
            icao_code="KJFK",
            fir_name="New York FIR",
            country_code="US",
            country_name="United States",
            geojson_geometry={
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
            }
        )
        assert fir.icao_code == "KJFK"
        assert fir.fir_name == "New York FIR"
        assert fir.country_code == "US"
        assert fir.country_name == "United States"
        assert fir.avoid_status is False
    
    def test_valid_fir_with_bbox(self):
        """Test creating FIRBase with bounding box coordinates."""
        fir = FIRBase(
            icao_code="EGTT",
            fir_name="London FIR",
            country_code="GB",
            country_name="United Kingdom",
            geojson_geometry={
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
            },
            bbox_min_lon=-10.5,
            bbox_min_lat=49.5,
            bbox_max_lon=2.0,
            bbox_max_lat=61.0,
            avoid_status=True
        )
        assert fir.bbox_min_lon == -10.5
        assert fir.bbox_min_lat == 49.5
        assert fir.bbox_max_lon == 2.0
        assert fir.bbox_max_lat == 61.0
        assert fir.avoid_status is True
    
    def test_icao_code_must_be_uppercase(self):
        """Test that lowercase ICAO code is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FIRBase(
                icao_code="kjfk",
                fir_name="New York FIR",
                country_code="US",
                country_name="United States",
                geojson_geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
            )
        assert "ICAO code must be uppercase" in str(exc_info.value)
    
    def test_icao_code_must_be_alphanumeric(self):
        """Test that ICAO code with special characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FIRBase(
                icao_code="KJ-K",
                fir_name="New York FIR",
                country_code="US",
                country_name="United States",
                geojson_geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
            )
        assert "ICAO code must be alphanumeric" in str(exc_info.value)
    
    def test_icao_code_must_be_4_characters(self):
        """Test that ICAO code with wrong length is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FIRBase(
                icao_code="KJF",
                fir_name="New York FIR",
                country_code="US",
                country_name="United States",
                geojson_geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
            )
        assert "String should have at least 4 characters" in str(exc_info.value)
    
    def test_country_code_must_be_uppercase(self):
        """Test that lowercase country code is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FIRBase(
                icao_code="KJFK",
                fir_name="New York FIR",
                country_code="us",
                country_name="United States",
                geojson_geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
            )
        assert "Country code must be uppercase" in str(exc_info.value)
    
    def test_country_code_must_be_letters_only(self):
        """Test that country code with numbers is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FIRBase(
                icao_code="KJFK",
                fir_name="New York FIR",
                country_code="U2",
                country_name="United States",
                geojson_geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
            )
        assert "Country code must contain only letters" in str(exc_info.value)
    
    def test_country_code_must_be_2_characters(self):
        """Test that country code with wrong length is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FIRBase(
                icao_code="KJFK",
                fir_name="New York FIR",
                country_code="USA",
                country_name="United States",
                geojson_geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
            )
        assert "String should have at most 2 characters" in str(exc_info.value)
    
    def test_geojson_must_have_type(self):
        """Test that GeoJSON without type field is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FIRBase(
                icao_code="KJFK",
                fir_name="New York FIR",
                country_code="US",
                country_name="United States",
                geojson_geometry={"coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
            )
        assert "GeoJSON geometry must have a 'type' field" in str(exc_info.value)
    
    def test_geojson_must_have_valid_type(self):
        """Test that GeoJSON with invalid type is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FIRBase(
                icao_code="KJFK",
                fir_name="New York FIR",
                country_code="US",
                country_name="United States",
                geojson_geometry={"type": "InvalidType", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
            )
        assert "GeoJSON type must be one of" in str(exc_info.value)
    
    def test_geojson_polygon_must_have_coordinates(self):
        """Test that GeoJSON Polygon without coordinates is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FIRBase(
                icao_code="KJFK",
                fir_name="New York FIR",
                country_code="US",
                country_name="United States",
                geojson_geometry={"type": "Polygon"}
            )
        assert "must have 'coordinates' field" in str(exc_info.value)
    
    def test_geojson_geometry_collection_must_have_geometries(self):
        """Test that GeoJSON GeometryCollection without geometries is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FIRBase(
                icao_code="KJFK",
                fir_name="New York FIR",
                country_code="US",
                country_name="United States",
                geojson_geometry={"type": "GeometryCollection"}
            )
        assert "must have 'geometries' field" in str(exc_info.value)
    
    def test_geojson_multipolygon(self):
        """Test that valid MultiPolygon GeoJSON is accepted."""
        fir = FIRBase(
            icao_code="KJFK",
            fir_name="New York FIR",
            country_code="US",
            country_name="United States",
            geojson_geometry={
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]]
            }
        )
        assert fir.geojson_geometry["type"] == "MultiPolygon"


class TestFIRCreate:
    """Tests for FIRCreate schema."""
    
    def test_fir_create_inherits_from_base(self):
        """Test that FIRCreate has all FIRBase fields."""
        fir = FIRCreate(
            icao_code="KJFK",
            fir_name="New York FIR",
            country_code="US",
            country_name="United States",
            geojson_geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
        )
        assert fir.icao_code == "KJFK"
        assert fir.fir_name == "New York FIR"


class TestFIRUpdate:
    """Tests for FIRUpdate schema."""
    
    def test_fir_update_all_fields_optional(self):
        """Test that FIRUpdate can be created with no fields."""
        fir = FIRUpdate()
        assert fir.fir_name is None
        assert fir.country_name is None
        assert fir.geojson_geometry is None
    
    def test_fir_update_partial_update(self):
        """Test that FIRUpdate can update only some fields."""
        fir = FIRUpdate(fir_name="Updated FIR Name", avoid_status=True)
        assert fir.fir_name == "Updated FIR Name"
        assert fir.avoid_status is True
        assert fir.country_name is None
    
    def test_fir_update_validates_geojson_if_provided(self):
        """Test that FIRUpdate validates GeoJSON structure if provided."""
        with pytest.raises(ValidationError) as exc_info:
            FIRUpdate(geojson_geometry={"invalid": "structure"})
        assert "GeoJSON geometry must have a 'type' field" in str(exc_info.value)


class TestFIRResponse:
    """Tests for FIRResponse schema."""
    
    def test_fir_response_includes_timestamps(self):
        """Test that FIRResponse includes created_at and updated_at."""
        now = datetime.now()
        fir = FIRResponse(
            icao_code="KJFK",
            fir_name="New York FIR",
            country_code="US",
            country_name="United States",
            geojson_geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            created_at=now,
            updated_at=now
        )
        assert fir.created_at == now
        assert fir.updated_at == now
    
    def test_fir_response_from_attributes_config(self):
        """Test that FIRResponse has from_attributes config."""
        assert FIRResponse.model_config.get("from_attributes") is True
