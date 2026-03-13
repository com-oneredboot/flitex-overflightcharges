"""Unit tests for CostCalculator service.

Tests the core calculation engine that orchestrates route parsing,
FIR crossing detection, formula application, and result storage.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from src.services.cost_calculator import CostCalculator
from src.services.route_parser import Waypoint
from src.models.iata_fir import IataFir
from src.models.formula import Formula
from src.models.route_calculation import RouteCalculation
from src.models.fir_charge import FirCharge
from src.exceptions import ParsingException, ValidationException


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = Mock(spec=Session)
    session.add = Mock()
    session.flush = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    return session


@pytest.fixture
def calculator(mock_session):
    """Create a CostCalculator instance with mocked dependencies."""
    return CostCalculator(mock_session)


@pytest.fixture
def sample_fir():
    """Create a sample FIR for testing."""
    return IataFir(
        icao_code="KZNY",
        fir_name="New York FIR",
        country_code="US",
        country_name="United States",
        geojson_geometry={
            "type": "Polygon",
            "coordinates": [[
                [-80.0, 35.0],
                [-70.0, 35.0],
                [-70.0, 45.0],
                [-80.0, 45.0],
                [-80.0, 35.0]
            ]]
        }
    )


@pytest.fixture
def sample_formula():
    """Create a sample formula for testing."""
    return Formula(
        country_code="US",
        formula_code="US_STANDARD",
        formula_logic="mtow_kg * 0.5 + distance_km * 2.0",
        effective_date="2024-01-01",
        currency="USD",
        version_number=1,
        is_active=True,
        created_by="test_user"
    )


class TestCostCalculatorInit:
    """Tests for CostCalculator initialization."""
    
    def test_init_creates_dependencies(self, mock_session):
        """Test that initialization creates required service dependencies."""
        calculator = CostCalculator(mock_session)
        
        assert calculator.session == mock_session
        assert calculator.route_parser is not None
        assert calculator.fir_service is not None
        assert calculator.formula_service is not None


class TestApplyFormula:
    """Tests for apply_formula method."""
    
    def test_apply_formula_simple_calculation(self, calculator, sample_formula):
        """Test formula application with simple calculation."""
        # Formula: mtow_kg * 0.5 + distance_km * 2.0
        # With mtow_kg=50000, distance_km=100
        # Expected: 50000 * 0.5 + 100 * 2.0 = 25000 + 200 = 25200
        
        result = calculator.apply_formula(sample_formula, 50000.0, 100.0)
        
        assert isinstance(result, Decimal)
        assert result == Decimal("25200.00")
    
    def test_apply_formula_with_zero_values(self, calculator, sample_formula):
        """Test formula application with zero values."""
        result = calculator.apply_formula(sample_formula, 0.0, 0.0)
        
        assert result == Decimal("0.00")
    
    def test_apply_formula_with_math_functions(self, calculator):
        """Test formula application with math functions."""
        formula = Formula(
            country_code="US",
            formula_code="US_COMPLEX",
            formula_logic="max(mtow_kg * 0.001, 100) + min(distance_km, 500)",
            effective_date="2024-01-01",
            currency="USD",
            version_number=1,
            is_active=True,
            created_by="test_user"
        )
        
        # With mtow_kg=50000, distance_km=600
        # max(50000 * 0.001, 100) = max(50, 100) = 100
        # min(600, 500) = 500
        # Total: 100 + 500 = 600
        result = calculator.apply_formula(formula, 50000.0, 600.0)
        
        assert result == Decimal("600.00")
    
    def test_apply_formula_negative_result_becomes_zero(self, calculator):
        """Test that negative formula results are set to zero."""
        formula = Formula(
            country_code="US",
            formula_code="US_NEGATIVE",
            formula_logic="mtow_kg * -1.0",
            effective_date="2024-01-01",
            currency="USD",
            version_number=1,
            is_active=True,
            created_by="test_user"
        )
        
        result = calculator.apply_formula(formula, 1000.0, 100.0)
        
        assert result == Decimal("0.00")
    
    def test_apply_formula_invalid_syntax_raises_exception(self, calculator):
        """Test that invalid formula syntax raises ValidationException."""
        formula = Formula(
            country_code="US",
            formula_code="US_INVALID",
            formula_logic="invalid syntax here!",
            effective_date="2024-01-01",
            currency="USD",
            version_number=1,
            is_active=True,
            created_by="test_user"
        )
        
        with pytest.raises(ValidationException) as exc_info:
            calculator.apply_formula(formula, 50000.0, 100.0)
        
        assert "Formula execution failed" in str(exc_info.value)


class TestCalculateRouteCost:
    """Tests for calculate_route_cost method."""
    
    def test_calculate_route_cost_success(
        self,
        calculator,
        mock_session,
        sample_fir,
        sample_formula
    ):
        """Test successful route cost calculation."""
        # Mock route parser
        waypoints = [
            Waypoint("KJFK", 40.6413, -73.7781),
            Waypoint("CYYZ", 43.6777, -79.6248)
        ]
        calculator.route_parser.parse_route = Mock(return_value=waypoints)
        calculator.route_parser.identify_fir_crossings = Mock(return_value=["KZNY"])
        
        # Mock FIR service
        calculator.fir_service.get_all_firs = Mock(return_value=[sample_fir])
        calculator.fir_service.get_fir_by_code = Mock(return_value=sample_fir)
        
        # Mock formula service
        calculator.formula_service.get_active_formula = Mock(return_value=sample_formula)
        
        # Mock session to set calculation_id
        def mock_flush():
            # Simulate database assigning an ID
            import uuid
            for call in mock_session.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, RouteCalculation):
                    obj.id = uuid.uuid4()
        
        mock_session.flush.side_effect = mock_flush
        
        # Execute calculation
        result = calculator.calculate_route_cost(
            route_string="KJFK DCT CYYZ",
            origin="KJFK",
            destination="CYYZ",
            aircraft_type="B738",
            mtow_kg=79000.0
        )
        
        # Verify result
        assert result.total_cost > 0
        assert result.currency == "USD"
        assert len(result.fir_breakdown) == 1
        assert result.fir_breakdown[0].icao_code == "KZNY"
        assert result.fir_breakdown[0].fir_name == "New York FIR"
        
        # Verify database operations
        assert mock_session.add.call_count >= 2  # RouteCalculation + FirCharge
        assert mock_session.flush.called
        assert mock_session.commit.called
    
    def test_calculate_route_cost_no_fir_crossings(
        self,
        calculator,
        mock_session
    ):
        """Test calculation with no FIR crossings."""
        # Mock route parser
        waypoints = [Waypoint("KJFK", 40.6413, -73.7781)]
        calculator.route_parser.parse_route = Mock(return_value=waypoints)
        calculator.route_parser.identify_fir_crossings = Mock(return_value=[])
        
        # Mock FIR service
        calculator.fir_service.get_all_firs = Mock(return_value=[])
        
        # Mock session to set calculation_id
        def mock_flush():
            import uuid
            for call in mock_session.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, RouteCalculation):
                    obj.id = uuid.uuid4()
        
        mock_session.flush.side_effect = mock_flush
        
        # Execute calculation
        result = calculator.calculate_route_cost(
            route_string="KJFK",
            origin="KJFK",
            destination="KJFK",
            aircraft_type="B738",
            mtow_kg=79000.0
        )
        
        # Verify result
        assert result.total_cost == Decimal("0.00")
        assert len(result.fir_breakdown) == 0
        
        # Verify calculation record was still stored
        assert mock_session.add.called
        assert mock_session.commit.called
    
    def test_calculate_route_cost_missing_formula(
        self,
        calculator,
        mock_session,
        sample_fir
    ):
        """Test calculation when formula is missing for a FIR country."""
        # Mock route parser
        waypoints = [Waypoint("KJFK", 40.6413, -73.7781)]
        calculator.route_parser.parse_route = Mock(return_value=waypoints)
        calculator.route_parser.identify_fir_crossings = Mock(return_value=["KZNY"])
        
        # Mock FIR service
        calculator.fir_service.get_all_firs = Mock(return_value=[sample_fir])
        calculator.fir_service.get_fir_by_code = Mock(return_value=sample_fir)
        
        # Mock formula service to return None (no formula)
        calculator.formula_service.get_active_formula = Mock(return_value=None)
        
        # Mock session to set calculation_id
        def mock_flush():
            import uuid
            for call in mock_session.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, RouteCalculation):
                    obj.id = uuid.uuid4()
        
        mock_session.flush.side_effect = mock_flush
        
        # Execute calculation
        result = calculator.calculate_route_cost(
            route_string="KJFK",
            origin="KJFK",
            destination="KJFK",
            aircraft_type="B738",
            mtow_kg=79000.0
        )
        
        # Verify result - FIR should be excluded from total
        assert result.total_cost == Decimal("0.00")
        assert len(result.fir_breakdown) == 0
    
    def test_calculate_route_cost_invalid_route_raises_exception(
        self,
        calculator
    ):
        """Test that invalid route string raises ParsingException."""
        # Mock route parser to raise exception
        calculator.route_parser.parse_route = Mock(
            side_effect=ParsingException("Invalid route format")
        )
        
        # Execute calculation and expect exception
        with pytest.raises(ParsingException):
            calculator.calculate_route_cost(
                route_string="INVALID",
                origin="KJFK",
                destination="CYYZ",
                aircraft_type="B738",
                mtow_kg=79000.0
            )
    
    def test_calculate_route_cost_multiple_firs(
        self,
        calculator,
        mock_session
    ):
        """Test calculation with multiple FIR crossings."""
        # Create multiple FIRs
        fir1 = IataFir(
            icao_code="KZNY",
            fir_name="New York FIR",
            country_code="US",
            country_name="United States",
            geojson_geometry={"type": "Polygon", "coordinates": []}
        )
        fir2 = IataFir(
            icao_code="CZYZ",
            fir_name="Toronto FIR",
            country_code="CA",
            country_name="Canada",
            geojson_geometry={"type": "Polygon", "coordinates": []}
        )
        
        # Create formulas for both countries
        formula_us = Formula(
            country_code="US",
            formula_code="US_STANDARD",
            formula_logic="mtow_kg * 0.5",
            effective_date="2024-01-01",
            currency="USD",
            version_number=1,
            is_active=True,
            created_by="test_user"
        )
        formula_ca = Formula(
            country_code="CA",
            formula_code="CA_STANDARD",
            formula_logic="mtow_kg * 0.3",
            effective_date="2024-01-01",
            currency="USD",
            version_number=1,
            is_active=True,
            created_by="test_user"
        )
        
        # Mock route parser
        waypoints = [
            Waypoint("KJFK", 40.6413, -73.7781),
            Waypoint("CYYZ", 43.6777, -79.6248)
        ]
        calculator.route_parser.parse_route = Mock(return_value=waypoints)
        calculator.route_parser.identify_fir_crossings = Mock(
            return_value=["KZNY", "CZYZ"]
        )
        
        # Mock FIR service
        calculator.fir_service.get_all_firs = Mock(return_value=[fir1, fir2])
        calculator.fir_service.get_fir_by_code = Mock(
            side_effect=lambda code: fir1 if code == "KZNY" else fir2
        )
        
        # Mock formula service
        calculator.formula_service.get_active_formula = Mock(
            side_effect=lambda code: formula_us if code == "US" else formula_ca
        )
        
        # Mock session to set calculation_id
        def mock_flush():
            import uuid
            for call in mock_session.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, RouteCalculation):
                    obj.id = uuid.uuid4()
        
        mock_session.flush.side_effect = mock_flush
        
        # Execute calculation
        result = calculator.calculate_route_cost(
            route_string="KJFK DCT CYYZ",
            origin="KJFK",
            destination="CYYZ",
            aircraft_type="B738",
            mtow_kg=80000.0
        )
        
        # Verify result
        # US: 80000 * 0.5 = 40000
        # CA: 80000 * 0.3 = 24000
        # Total: 64000
        assert result.total_cost == Decimal("64000.00")
        assert len(result.fir_breakdown) == 2
        assert result.fir_breakdown[0].icao_code == "KZNY"
        assert result.fir_breakdown[1].icao_code == "CZYZ"
