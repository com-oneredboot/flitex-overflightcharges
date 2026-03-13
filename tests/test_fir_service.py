"""Unit tests for FIRService CRUD operations."""

import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.services.fir_service import FIRService
from src.models.iata_fir import IataFir
from src.schemas.fir import FIRCreate, FIRUpdate
from src.exceptions import FIRNotFoundException, DuplicateFIRException


@pytest.fixture
def mock_session():
    """Create a mock SQLAlchemy session."""
    return Mock(spec=Session)


@pytest.fixture
def fir_service(mock_session):
    """Create a FIRService instance with mock session."""
    return FIRService(mock_session)


@pytest.fixture
def sample_fir_data():
    """Create sample FIR data for testing."""
    return {
        "icao_code": "KJFK",
        "fir_name": "New York FIR",
        "country_code": "US",
        "country_name": "United States",
        "geojson_geometry": {
            "type": "Polygon",
            "coordinates": [[[-74.0, 40.0], [-73.0, 40.0], [-73.0, 41.0], [-74.0, 41.0], [-74.0, 40.0]]]
        },
        "bbox_min_lon": -74.0,
        "bbox_min_lat": 40.0,
        "bbox_max_lon": -73.0,
        "bbox_max_lat": 41.0,
        "avoid_status": False
    }


@pytest.fixture
def sample_fir(sample_fir_data):
    """Create a sample IataFir model instance."""
    return IataFir(**sample_fir_data)


class TestGetAllFirs:
    """Tests for get_all_firs method."""
    
    def test_get_all_firs_returns_list(self, fir_service, mock_session, sample_fir):
        """Test that get_all_firs returns a list of FIR records."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.all.return_value = [sample_fir]
        
        # Act
        result = fir_service.get_all_firs()
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == sample_fir
        mock_session.query.assert_called_once_with(IataFir)
    
    def test_get_all_firs_returns_empty_list(self, fir_service, mock_session):
        """Test that get_all_firs returns empty list when no FIRs exist."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.all.return_value = []
        
        # Act
        result = fir_service.get_all_firs()
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 0


class TestGetFirByCode:
    """Tests for get_fir_by_code method."""
    
    def test_get_fir_by_code_returns_fir(self, fir_service, mock_session, sample_fir):
        """Test that get_fir_by_code returns FIR when found."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_fir
        
        # Act
        result = fir_service.get_fir_by_code("KJFK")
        
        # Assert
        assert result == sample_fir
        mock_session.query.assert_called_once_with(IataFir)
    
    def test_get_fir_by_code_returns_none(self, fir_service, mock_session):
        """Test that get_fir_by_code returns None when FIR not found."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        # Act
        result = fir_service.get_fir_by_code("XXXX")
        
        # Assert
        assert result is None


class TestCreateFir:
    """Tests for create_fir method."""
    
    def test_create_fir_success(self, fir_service, mock_session, sample_fir_data):
        """Test successful FIR creation."""
        # Arrange
        fir_create = FIRCreate(**sample_fir_data)
        
        # Mock get_fir_by_code to return None (FIR doesn't exist)
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        # Mock the created FIR
        created_fir = IataFir(**sample_fir_data)
        mock_session.refresh = Mock(side_effect=lambda x: setattr(x, 'created_at', '2024-01-01'))
        
        # Act
        result = fir_service.create_fir(fir_create)
        
        # Assert
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
        assert result.icao_code == sample_fir_data["icao_code"]
        assert result.fir_name == sample_fir_data["fir_name"]
    
    def test_create_fir_duplicate_raises_exception(self, fir_service, mock_session, sample_fir_data, sample_fir):
        """Test that creating duplicate FIR raises DuplicateFIRException."""
        # Arrange
        fir_create = FIRCreate(**sample_fir_data)
        
        # Mock get_fir_by_code to return existing FIR
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_fir
        
        # Act & Assert
        with pytest.raises(DuplicateFIRException) as exc_info:
            fir_service.create_fir(fir_create)
        
        assert "KJFK" in str(exc_info.value)
        assert exc_info.value.status_code == 409
    
    def test_create_fir_integrity_error_raises_exception(self, fir_service, mock_session, sample_fir_data):
        """Test that IntegrityError during creation raises DuplicateFIRException."""
        # Arrange
        fir_create = FIRCreate(**sample_fir_data)
        
        # Mock get_fir_by_code to return None
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        # Mock commit to raise IntegrityError
        mock_session.commit.side_effect = IntegrityError("statement", "params", "orig")
        
        # Act & Assert
        with pytest.raises(DuplicateFIRException):
            fir_service.create_fir(fir_create)
        
        mock_session.rollback.assert_called_once()


class TestUpdateFir:
    """Tests for update_fir method."""
    
    def test_update_fir_success(self, fir_service, mock_session, sample_fir):
        """Test successful FIR update."""
        # Arrange
        update_data = FIRUpdate(fir_name="Updated FIR Name", avoid_status=True)
        
        # Mock get_fir_by_code to return existing FIR
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_fir
        
        # Act
        result = fir_service.update_fir("KJFK", update_data)
        
        # Assert
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
        assert result.fir_name == "Updated FIR Name"
        assert result.avoid_status is True
    
    def test_update_fir_not_found_raises_exception(self, fir_service, mock_session):
        """Test that updating non-existent FIR raises FIRNotFoundException."""
        # Arrange
        update_data = FIRUpdate(fir_name="Updated FIR Name")
        
        # Mock get_fir_by_code to return None
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        # Act & Assert
        with pytest.raises(FIRNotFoundException) as exc_info:
            fir_service.update_fir("XXXX", update_data)
        
        assert "XXXX" in str(exc_info.value)
        assert exc_info.value.status_code == 404
    
    def test_update_fir_partial_update(self, fir_service, mock_session, sample_fir):
        """Test that partial update only changes specified fields."""
        # Arrange
        original_country_name = sample_fir.country_name
        update_data = FIRUpdate(fir_name="Updated FIR Name")
        
        # Mock get_fir_by_code to return existing FIR
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_fir
        
        # Act
        result = fir_service.update_fir("KJFK", update_data)
        
        # Assert
        assert result.fir_name == "Updated FIR Name"
        assert result.country_name == original_country_name  # Unchanged


class TestDeleteFir:
    """Tests for delete_fir method."""
    
    def test_delete_fir_success(self, fir_service, mock_session, sample_fir):
        """Test successful FIR deletion."""
        # Arrange
        # Mock get_fir_by_code to return existing FIR
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_fir
        
        # Act
        result = fir_service.delete_fir("KJFK")
        
        # Assert
        assert result is True
        mock_session.delete.assert_called_once_with(sample_fir)
        mock_session.commit.assert_called_once()
    
    def test_delete_fir_not_found_raises_exception(self, fir_service, mock_session):
        """Test that deleting non-existent FIR raises FIRNotFoundException."""
        # Arrange
        # Mock get_fir_by_code to return None
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        # Act & Assert
        with pytest.raises(FIRNotFoundException) as exc_info:
            fir_service.delete_fir("XXXX")
        
        assert "XXXX" in str(exc_info.value)
        assert exc_info.value.status_code == 404


class TestGetFirsByCountry:
    """Tests for get_firs_by_country method."""
    
    def test_get_firs_by_country_returns_list(self, fir_service, mock_session, sample_fir):
        """Test that get_firs_by_country returns list of FIRs for country."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [sample_fir]
        
        # Act
        result = fir_service.get_firs_by_country("US")
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == sample_fir
        mock_session.query.assert_called_once_with(IataFir)
    
    def test_get_firs_by_country_returns_empty_list(self, fir_service, mock_session):
        """Test that get_firs_by_country returns empty list when no FIRs found."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        
        # Act
        result = fir_service.get_firs_by_country("XX")
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 0
