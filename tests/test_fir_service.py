"""Unit tests for FIRService versioned CRUD operations."""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch, PropertyMock
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
        "avoid_status": False,
    }


@pytest.fixture
def sample_fir(sample_fir_data):
    """Create a sample IataFir model instance with versioning fields."""
    fir = IataFir(
        **sample_fir_data,
        version_number=1,
        is_active=True,
        created_by="test-user",
        activation_date=datetime.now(timezone.utc),
    )
    fir.id = uuid.uuid4()
    return fir


class TestGetAllActiveFirs:
    """Tests for get_all_active_firs method."""

    def test_get_all_active_firs_returns_list(self, fir_service, mock_session, sample_fir):
        """Test that get_all_active_firs returns a list of active FIR records."""
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [sample_fir]

        result = fir_service.get_all_active_firs()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == sample_fir
        mock_session.query.assert_called_once_with(IataFir)

    def test_get_all_active_firs_returns_empty_list(self, fir_service, mock_session):
        """Test that get_all_active_firs returns empty list when no active FIRs exist."""
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        result = fir_service.get_all_active_firs()

        assert isinstance(result, list)
        assert len(result) == 0


class TestGetActiveFir:
    """Tests for get_active_fir method."""

    def test_get_active_fir_returns_fir(self, fir_service, mock_session, sample_fir):
        """Test that get_active_fir returns FIR when found."""
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_fir

        result = fir_service.get_active_fir("KJFK")

        assert result == sample_fir
        mock_session.query.assert_called_once_with(IataFir)

    def test_get_active_fir_returns_none(self, fir_service, mock_session):
        """Test that get_active_fir returns None when FIR not found."""
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = fir_service.get_active_fir("XXXX")

        assert result is None


class TestCreateFir:
    """Tests for create_fir method (versioned)."""

    def test_create_fir_success(self, fir_service, mock_session, sample_fir_data):
        """Test successful FIR creation with versioning fields."""
        fir_create = FIRCreate(**sample_fir_data)

        mock_session.refresh = Mock(side_effect=lambda x: None)

        result = fir_service.create_fir(fir_create, created_by="test-user")

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
        assert result.icao_code == "KJFK"
        assert result.version_number == 1
        assert result.is_active is True
        assert result.created_by == "test-user"
        assert result.activation_date is not None

    def test_create_fir_integrity_error_raises_duplicate(self, fir_service, mock_session, sample_fir_data):
        """Test that IntegrityError during creation raises DuplicateFIRException."""
        fir_create = FIRCreate(**sample_fir_data)

        mock_session.commit.side_effect = IntegrityError("statement", "params", "orig")

        with pytest.raises(DuplicateFIRException):
            fir_service.create_fir(fir_create, created_by="test-user")

        mock_session.rollback.assert_called_once()


class TestUpdateFir:
    """Tests for update_fir method (versioned)."""

    def test_update_fir_success(self, fir_service, mock_session, sample_fir):
        """Test successful FIR update creates new version."""
        update_data = FIRUpdate(fir_name="Updated FIR Name", avoid_status=True)

        # Mock get_active_fir to return existing FIR
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_fir

        mock_session.refresh = Mock(side_effect=lambda x: None)

        result = fir_service.update_fir("KJFK", update_data, created_by="updater")

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        # Old version should be deactivated
        assert sample_fir.is_active is False
        assert sample_fir.deactivation_date is not None
        # New version should have incremented version_number
        assert result.version_number == 2
        assert result.is_active is True
        assert result.created_by == "updater"

    def test_update_fir_not_found_raises_exception(self, fir_service, mock_session):
        """Test that updating non-existent FIR raises FIRNotFoundException."""
        update_data = FIRUpdate(fir_name="Updated FIR Name")

        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        with pytest.raises(FIRNotFoundException) as exc_info:
            fir_service.update_fir("XXXX", update_data, created_by="updater")

        assert "XXXX" in str(exc_info.value)

    def test_update_fir_partial_update(self, fir_service, mock_session, sample_fir):
        """Test that partial update carries forward unchanged fields."""
        original_country_name = sample_fir.country_name
        update_data = FIRUpdate(fir_name="Updated FIR Name")

        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_fir

        mock_session.refresh = Mock(side_effect=lambda x: None)

        result = fir_service.update_fir("KJFK", update_data, created_by="updater")

        assert result.fir_name == "Updated FIR Name"
        assert result.country_name == original_country_name


class TestSoftDeleteFir:
    """Tests for soft_delete_fir method."""

    def test_soft_delete_fir_success(self, fir_service, mock_session, sample_fir):
        """Test successful FIR soft-delete sets is_active=False."""
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_fir

        result = fir_service.soft_delete_fir("KJFK")

        assert result is True
        assert sample_fir.is_active is False
        assert sample_fir.deactivation_date is not None
        mock_session.commit.assert_called_once()

    def test_soft_delete_fir_not_found_raises_exception(self, fir_service, mock_session):
        """Test that soft-deleting non-existent FIR raises FIRNotFoundException."""
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        with pytest.raises(FIRNotFoundException) as exc_info:
            fir_service.soft_delete_fir("XXXX")

        assert "XXXX" in str(exc_info.value)


class TestGetFirHistory:
    """Tests for get_fir_history method."""

    def test_get_fir_history_returns_versions(self, fir_service, mock_session, sample_fir):
        """Test that get_fir_history returns all versions."""
        v2 = IataFir(
            icao_code="KJFK", fir_name="Updated FIR", country_code="US",
            country_name="United States",
            geojson_geometry={"type": "Polygon", "coordinates": []},
            version_number=2, is_active=True, created_by="test-user",
        )
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [v2, sample_fir]

        result = fir_service.get_fir_history("KJFK")

        assert len(result) == 2

    def test_get_fir_history_not_found_raises_exception(self, fir_service, mock_session):
        """Test that history for non-existent ICAO raises FIRNotFoundException."""
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        with pytest.raises(FIRNotFoundException):
            fir_service.get_fir_history("XXXX")


class TestRollbackFir:
    """Tests for rollback_fir method."""

    def test_rollback_fir_not_found_raises_exception(self, fir_service, mock_session):
        """Test that rollback on non-existent FIR raises FIRNotFoundException."""
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        with pytest.raises(FIRNotFoundException):
            fir_service.rollback_fir("XXXX", 1)
