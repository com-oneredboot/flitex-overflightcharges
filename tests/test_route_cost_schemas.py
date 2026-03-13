"""Unit tests for Route Cost Pydantic schemas."""

import pytest
from decimal import Decimal
from uuid import uuid4
from pydantic import ValidationError
from src.schemas.route_cost import (
    RouteCostRequest,
    FIRChargeBreakdown,
    RouteCostResponse
)


class TestRouteCostRequest:
    """Tests for RouteCostRequest schema."""
    
    def test_valid_route_cost_request(self):
        """Test creating RouteCostRequest with valid data."""
        request = RouteCostRequest(
            route_string="KJFK DCT CYYZ",
            origin="KJFK",
            destination="CYYZ",
            aircraft_type="B738",
            mtow_kg=79000.0
        )
        assert request.route_string == "KJFK DCT CYYZ"
        assert request.origin == "KJFK"
        assert request.destination == "CYYZ"
        assert request.aircraft_type == "B738"
        assert request.mtow_kg == 79000.0
    
    def test_origin_must_be_uppercase(self):
        """Test that lowercase origin is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                origin="kjfk",
                destination="CYYZ",
                aircraft_type="B738",
                mtow_kg=79000.0
            )
        assert "ICAO code must be uppercase" in str(exc_info.value)
    
    def test_destination_must_be_uppercase(self):
        """Test that lowercase destination is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="cyyz",
                aircraft_type="B738",
                mtow_kg=79000.0
            )
        assert "ICAO code must be uppercase" in str(exc_info.value)
    
    def test_origin_must_be_letters_only(self):
        """Test that origin with numbers is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                origin="KJ1K",
                destination="CYYZ",
                aircraft_type="B738",
                mtow_kg=79000.0
            )
        assert "ICAO code must contain only letters" in str(exc_info.value)
    
    def test_destination_must_be_letters_only(self):
        """Test that destination with numbers is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="CY2Z",
                aircraft_type="B738",
                mtow_kg=79000.0
            )
        assert "ICAO code must contain only letters" in str(exc_info.value)
    
    def test_origin_must_be_4_characters(self):
        """Test that origin with wrong length is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                origin="KJF",
                destination="CYYZ",
                aircraft_type="B738",
                mtow_kg=79000.0
            )
        assert "String should have at least 4 characters" in str(exc_info.value)
    
    def test_destination_must_be_4_characters(self):
        """Test that destination with wrong length is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="CYYZZ",
                aircraft_type="B738",
                mtow_kg=79000.0
            )
        assert "String should have at most 4 characters" in str(exc_info.value)
    
    def test_mtow_must_be_positive(self):
        """Test that zero MTOW is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="CYYZ",
                aircraft_type="B738",
                mtow_kg=0.0
            )
        # Pydantic's gt constraint provides this error message
        assert "Input should be greater than 0" in str(exc_info.value)
    
    def test_mtow_cannot_be_negative(self):
        """Test that negative MTOW is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="CYYZ",
                aircraft_type="B738",
                mtow_kg=-1000.0
            )
        # Pydantic's gt constraint provides this error message
        assert "Input should be greater than 0" in str(exc_info.value)
    
    def test_route_string_required(self):
        """Test that route_string is required."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                origin="KJFK",
                destination="CYYZ",
                aircraft_type="B738",
                mtow_kg=79000.0
            )
        assert "route_string" in str(exc_info.value)
    
    def test_route_string_cannot_be_empty(self):
        """Test that empty route_string is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="",
                origin="KJFK",
                destination="CYYZ",
                aircraft_type="B738",
                mtow_kg=79000.0
            )
        assert "String should have at least 1 character" in str(exc_info.value)
    
    def test_origin_required(self):
        """Test that origin is required."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                destination="CYYZ",
                aircraft_type="B738",
                mtow_kg=79000.0
            )
        assert "origin" in str(exc_info.value)
    
    def test_destination_required(self):
        """Test that destination is required."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                aircraft_type="B738",
                mtow_kg=79000.0
            )
        assert "destination" in str(exc_info.value)
    
    def test_aircraft_type_required(self):
        """Test that aircraft_type is required."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="CYYZ",
                mtow_kg=79000.0
            )
        assert "aircraft_type" in str(exc_info.value)
    
    def test_aircraft_type_cannot_be_empty(self):
        """Test that empty aircraft_type is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="CYYZ",
                aircraft_type="",
                mtow_kg=79000.0
            )
        assert "String should have at least 1 character" in str(exc_info.value)
    
    def test_aircraft_type_max_length(self):
        """Test that aircraft_type exceeding max length is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="CYYZ",
                aircraft_type="B737800LONG",
                mtow_kg=79000.0
            )
        assert "String should have at most 10 characters" in str(exc_info.value)
    
    def test_mtow_required(self):
        """Test that mtow_kg is required."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostRequest(
                route_string="KJFK DCT CYYZ",
                origin="KJFK",
                destination="CYYZ",
                aircraft_type="B738"
            )
        assert "mtow_kg" in str(exc_info.value)


class TestFIRChargeBreakdown:
    """Tests for FIRChargeBreakdown schema."""
    
    def test_valid_fir_charge_breakdown(self):
        """Test creating FIRChargeBreakdown with valid data."""
        breakdown = FIRChargeBreakdown(
            icao_code="KZNY",
            fir_name="New York FIR",
            country_code="US",
            charge_amount=Decimal("125.50"),
            currency="USD"
        )
        assert breakdown.icao_code == "KZNY"
        assert breakdown.fir_name == "New York FIR"
        assert breakdown.country_code == "US"
        assert breakdown.charge_amount == Decimal("125.50")
        assert breakdown.currency == "USD"
    
    def test_icao_code_required(self):
        """Test that icao_code is required."""
        with pytest.raises(ValidationError) as exc_info:
            FIRChargeBreakdown(
                fir_name="New York FIR",
                country_code="US",
                charge_amount=Decimal("125.50"),
                currency="USD"
            )
        assert "icao_code" in str(exc_info.value)
    
    def test_fir_name_required(self):
        """Test that fir_name is required."""
        with pytest.raises(ValidationError) as exc_info:
            FIRChargeBreakdown(
                icao_code="KZNY",
                country_code="US",
                charge_amount=Decimal("125.50"),
                currency="USD"
            )
        assert "fir_name" in str(exc_info.value)
    
    def test_country_code_required(self):
        """Test that country_code is required."""
        with pytest.raises(ValidationError) as exc_info:
            FIRChargeBreakdown(
                icao_code="KZNY",
                fir_name="New York FIR",
                charge_amount=Decimal("125.50"),
                currency="USD"
            )
        assert "country_code" in str(exc_info.value)
    
    def test_charge_amount_required(self):
        """Test that charge_amount is required."""
        with pytest.raises(ValidationError) as exc_info:
            FIRChargeBreakdown(
                icao_code="KZNY",
                fir_name="New York FIR",
                country_code="US",
                currency="USD"
            )
        assert "charge_amount" in str(exc_info.value)
    
    def test_currency_required(self):
        """Test that currency is required."""
        with pytest.raises(ValidationError) as exc_info:
            FIRChargeBreakdown(
                icao_code="KZNY",
                fir_name="New York FIR",
                country_code="US",
                charge_amount=Decimal("125.50")
            )
        assert "currency" in str(exc_info.value)


class TestRouteCostResponse:
    """Tests for RouteCostResponse schema."""
    
    def test_valid_route_cost_response(self):
        """Test creating RouteCostResponse with valid data."""
        calculation_id = uuid4()
        breakdown = [
            FIRChargeBreakdown(
                icao_code="KZNY",
                fir_name="New York FIR",
                country_code="US",
                charge_amount=Decimal("125.50"),
                currency="USD"
            ),
            FIRChargeBreakdown(
                icao_code="CZUL",
                fir_name="Montreal FIR",
                country_code="CA",
                charge_amount=Decimal("98.75"),
                currency="CAD"
            )
        ]
        response = RouteCostResponse(
            calculation_id=calculation_id,
            total_cost=Decimal("224.25"),
            currency="USD",
            fir_breakdown=breakdown
        )
        assert response.calculation_id == calculation_id
        assert response.total_cost == Decimal("224.25")
        assert response.currency == "USD"
        assert len(response.fir_breakdown) == 2
        assert response.fir_breakdown[0].icao_code == "KZNY"
        assert response.fir_breakdown[1].icao_code == "CZUL"
    
    def test_calculation_id_required(self):
        """Test that calculation_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostResponse(
                total_cost=Decimal("224.25"),
                currency="USD",
                fir_breakdown=[]
            )
        assert "calculation_id" in str(exc_info.value)
    
    def test_total_cost_required(self):
        """Test that total_cost is required."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostResponse(
                calculation_id=uuid4(),
                currency="USD",
                fir_breakdown=[]
            )
        assert "total_cost" in str(exc_info.value)
    
    def test_currency_required(self):
        """Test that currency is required."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostResponse(
                calculation_id=uuid4(),
                total_cost=Decimal("224.25"),
                fir_breakdown=[]
            )
        assert "currency" in str(exc_info.value)
    
    def test_fir_breakdown_required(self):
        """Test that fir_breakdown is required."""
        with pytest.raises(ValidationError) as exc_info:
            RouteCostResponse(
                calculation_id=uuid4(),
                total_cost=Decimal("224.25"),
                currency="USD"
            )
        assert "fir_breakdown" in str(exc_info.value)
    
    def test_fir_breakdown_can_be_empty_list(self):
        """Test that fir_breakdown can be an empty list."""
        response = RouteCostResponse(
            calculation_id=uuid4(),
            total_cost=Decimal("0.00"),
            currency="USD",
            fir_breakdown=[]
        )
        assert response.fir_breakdown == []
    
    def test_route_cost_response_from_attributes_config(self):
        """Test that RouteCostResponse has from_attributes config."""
        assert RouteCostResponse.model_config.get("from_attributes") is True
