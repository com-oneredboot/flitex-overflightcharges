"""Unit tests verifying country_name has been removed from all FIR schemas and model.

Validates Requirements: 1.3, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

import pytest
from sqlalchemy import inspect
from src.schemas.fir import (
    FIRBase, FIRCreate, FIRUpdate, FIRResponse, CoverageDetail,
    CoverageHealthResponse,
)
from src.models.iata_fir import IataFir


class TestPydanticSchemasNoCountryName:
    """Verify country_name is absent from all FIR Pydantic schemas."""

    def test_fir_base_no_country_name(self):
        """FIRBase schema must not contain a country_name field. (Req 3.1)"""
        assert "country_name" not in FIRBase.model_fields

    def test_fir_create_no_country_name(self):
        """FIRCreate schema must not contain a country_name field. (Req 3.2)"""
        assert "country_name" not in FIRCreate.model_fields

    def test_fir_update_no_country_name(self):
        """FIRUpdate schema must not contain a country_name field. (Req 3.3)"""
        assert "country_name" not in FIRUpdate.model_fields

    def test_fir_response_no_country_name(self):
        """FIRResponse schema must not contain a country_name field. (Req 3.4)"""
        assert "country_name" not in FIRResponse.model_fields

    def test_coverage_detail_no_country_name(self):
        """CoverageDetail schema must not contain a country_name field. (Req 3.5)"""
        assert "country_name" not in CoverageDetail.model_fields

    def test_coverage_health_response_no_country_name_in_details(self):
        """CoverageHealthResponse nested details must not contain country_name. (Req 3.6)"""
        # CoverageHealthResponse.details is List[CoverageDetail]
        assert "country_name" not in CoverageDetail.model_fields
        assert "country_name" not in CoverageHealthResponse.model_fields


class TestIataFirModelNoCountryName:
    """Verify country_name is absent from the IataFir SQLAlchemy model."""

    def test_iata_fir_no_country_name_column(self):
        """IataFir model must not have a country_name column. (Req 1.3)"""
        mapper = inspect(IataFir)
        column_names = {col.key for col in mapper.columns}
        assert "country_name" not in column_names

    def test_iata_fir_table_no_country_name(self):
        """IataFir.__table__.columns must not include country_name. (Req 1.3)"""
        table_column_names = {col.name for col in IataFir.__table__.columns}
        assert "country_name" not in table_column_names
