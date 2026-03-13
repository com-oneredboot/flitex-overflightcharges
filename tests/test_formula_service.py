"""Unit tests for FormulaService CRUD operations with versioning."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import date
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.services.formula_service import FormulaService
from src.models.formula import Formula
from src.schemas.formula import FormulaCreate, FormulaUpdate
from src.exceptions import FormulaNotFoundException, ValidationException


@pytest.fixture
def mock_session():
    """Create a mock SQLAlchemy session."""
    return Mock(spec=Session)


@pytest.fixture
def formula_service(mock_session):
    """Create a FormulaService instance with mock session."""
    return FormulaService(mock_session)


@pytest.fixture
def sample_formula_data():
    """Create sample formula data for testing."""
    return {
        "country_code": "US",
        "description": "United States",
        "formula_code": "US_STANDARD",
        "formula_logic": "charge = mtow_kg * 0.05 * distance_km",
        "effective_date": date(2024, 1, 1),
        "currency": "USD"
    }


@pytest.fixture
def sample_formula(sample_formula_data):
    """Create a sample Formula model instance."""
    return Formula(
        **sample_formula_data,
        version_number=1,
        is_active=True,
        created_by="test_user"
    )


class TestGetAllActiveFormulas:
    """Tests for get_all_active_formulas method."""
    
    def test_get_all_active_formulas_returns_list(self, formula_service, mock_session, sample_formula):
        """Test that get_all_active_formulas returns list of active formulas."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [sample_formula]
        
        # Act
        result = formula_service.get_all_active_formulas()
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == sample_formula
        mock_session.query.assert_called_once_with(Formula)
    
    def test_get_all_active_formulas_returns_empty_list(self, formula_service, mock_session):
        """Test that get_all_active_formulas returns empty list when no active formulas."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        
        # Act
        result = formula_service.get_all_active_formulas()
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 0


class TestGetActiveFormula:
    """Tests for get_active_formula method."""
    
    def test_get_active_formula_returns_formula(self, formula_service, mock_session, sample_formula):
        """Test that get_active_formula returns active formula for country."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_formula
        
        # Act
        result = formula_service.get_active_formula("US")
        
        # Assert
        assert result == sample_formula
        mock_session.query.assert_called_once_with(Formula)
    
    def test_get_active_formula_returns_none(self, formula_service, mock_session):
        """Test that get_active_formula returns None when no active formula."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        # Act
        result = formula_service.get_active_formula("XX")
        
        # Assert
        assert result is None


class TestCreateFormula:
    """Tests for create_formula method."""
    
    @patch('src.services.formula_service.logger')
    def test_create_formula_success(self, mock_logger, formula_service, mock_session, sample_formula_data):
        """Test successful formula creation with version 1."""
        # Arrange
        formula_create = FormulaCreate(**sample_formula_data, created_by="test_user")
        
        # Act
        result = formula_service.create_formula(formula_create, "test_user")
        
        # Assert
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
        assert result.country_code == sample_formula_data["country_code"]
        assert result.version_number == 1
        assert result.is_active is True
        assert result.created_by == "test_user"
        
        # Verify logging
        mock_logger.info.assert_called_once()
    
    def test_create_formula_invalid_syntax_raises_exception(self, formula_service, mock_session):
        """Test that creating formula with invalid syntax raises ValidationException."""
        # Arrange
        invalid_data = {
            "country_code": "US",
            "description": "United States",
            "formula_code": "US_STANDARD",
            "formula_logic": "invalid python syntax (",
            "effective_date": date(2024, 1, 1),
            "currency": "USD",
            "created_by": "test_user"
        }
        formula_create = FormulaCreate(**invalid_data)
        
        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            formula_service.create_formula(formula_create, "test_user")
        
        assert "Invalid formula syntax" in str(exc_info.value)
        assert exc_info.value.status_code == 400
    
    def test_create_formula_integrity_error_raises_exception(self, formula_service, mock_session, sample_formula_data):
        """Test that IntegrityError during creation raises ValidationException."""
        # Arrange
        formula_create = FormulaCreate(**sample_formula_data, created_by="test_user")
        mock_session.commit.side_effect = IntegrityError("statement", "params", "orig")
        
        # Act & Assert
        with pytest.raises(ValidationException):
            formula_service.create_formula(formula_create, "test_user")
        
        mock_session.rollback.assert_called_once()


class TestUpdateFormula:
    """Tests for update_formula method."""
    
    @patch('src.services.formula_service.logger')
    def test_update_formula_success(self, mock_logger, formula_service, mock_session, sample_formula):
        """Test successful formula update creates new version."""
        # Arrange
        update_data = FormulaUpdate(
            formula_logic="charge = mtow_kg * 0.06 * distance_km",
            created_by="test_user"
        )
        
        # Mock get_active_formula
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_formula
        
        # Act
        result = formula_service.update_formula("US", update_data, "test_user")
        
        # Assert
        assert sample_formula.is_active is False  # Old version deactivated
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        assert result.version_number == 2
        assert result.is_active is True
        assert result.created_by == "test_user"
        
        # Verify logging
        mock_logger.info.assert_called_once()
    
    def test_update_formula_not_found_raises_exception(self, formula_service, mock_session):
        """Test that updating non-existent formula raises FormulaNotFoundException."""
        # Arrange
        update_data = FormulaUpdate(
            formula_logic="charge = mtow_kg * 0.06 * distance_km",
            created_by="test_user"
        )
        
        # Mock get_active_formula to return None
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        # Act & Assert
        with pytest.raises(FormulaNotFoundException) as exc_info:
            formula_service.update_formula("XX", update_data, "test_user")
        
        assert "XX" in str(exc_info.value)
        assert exc_info.value.status_code == 404
    
    def test_update_formula_invalid_syntax_raises_exception(self, formula_service, mock_session, sample_formula):
        """Test that updating with invalid syntax raises ValidationException."""
        # Arrange
        update_data = FormulaUpdate(
            formula_logic="invalid python syntax (",
            created_by="test_user"
        )
        
        # Mock get_active_formula
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_formula
        
        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            formula_service.update_formula("US", update_data, "test_user")
        
        assert "Invalid formula syntax" in str(exc_info.value)
        assert exc_info.value.status_code == 400
    
    def test_update_formula_partial_update(self, formula_service, mock_session, sample_formula):
        """Test that partial update preserves unchanged fields."""
        # Arrange
        original_formula_code = sample_formula.formula_code
        update_data = FormulaUpdate(
            formula_logic="charge = mtow_kg * 0.06 * distance_km",
            created_by="test_user"
        )
        
        # Mock get_active_formula
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_formula
        
        # Act
        result = formula_service.update_formula("US", update_data, "test_user")
        
        # Assert
        assert result.formula_code == original_formula_code  # Unchanged


class TestDeleteFormula:
    """Tests for delete_formula method."""
    
    @patch('src.services.formula_service.logger')
    def test_delete_formula_success(self, mock_logger, formula_service, mock_session, sample_formula):
        """Test successful deletion of all formula versions."""
        # Arrange
        formula_v2 = Formula(
            country_code="US",
            formula_code="US_STANDARD",
            formula_logic="charge = mtow_kg * 0.06 * distance_km",
            effective_date=date(2024, 2, 1),
            currency="USD",
            version_number=2,
            is_active=False,
            created_by="test_user"
        )
        
        # Mock query to return multiple versions
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [sample_formula, formula_v2]
        
        # Act
        result = formula_service.delete_formula("US")
        
        # Assert
        assert result is True
        assert mock_session.delete.call_count == 2
        mock_session.commit.assert_called_once()
        
        # Verify logging
        mock_logger.info.assert_called_once()
    
    def test_delete_formula_not_found_raises_exception(self, formula_service, mock_session):
        """Test that deleting non-existent formula raises FormulaNotFoundException."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        
        # Act & Assert
        with pytest.raises(FormulaNotFoundException) as exc_info:
            formula_service.delete_formula("XX")
        
        assert "XX" in str(exc_info.value)
        assert exc_info.value.status_code == 404


class TestGetFormulaHistory:
    """Tests for get_formula_history method."""
    
    def test_get_formula_history_returns_ordered_list(self, formula_service, mock_session, sample_formula):
        """Test that get_formula_history returns versions ordered by version DESC."""
        # Arrange
        formula_v2 = Formula(
            country_code="US",
            formula_code="US_STANDARD",
            formula_logic="charge = mtow_kg * 0.06 * distance_km",
            effective_date=date(2024, 2, 1),
            currency="USD",
            version_number=2,
            is_active=True,
            created_by="test_user"
        )
        
        # Mock query to return versions in DESC order
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [formula_v2, sample_formula]  # v2 first, v1 second
        
        # Act
        result = formula_service.get_formula_history("US")
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].version_number == 2
        assert result[1].version_number == 1
    
    def test_get_formula_history_not_found_raises_exception(self, formula_service, mock_session):
        """Test that getting history for non-existent country raises FormulaNotFoundException."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        
        # Act & Assert
        with pytest.raises(FormulaNotFoundException) as exc_info:
            formula_service.get_formula_history("XX")
        
        assert "XX" in str(exc_info.value)
        assert exc_info.value.status_code == 404


class TestRollbackFormula:
    """Tests for rollback_formula method."""
    
    @patch('src.services.formula_service.logger')
    def test_rollback_formula_success(self, mock_logger, formula_service, mock_session, sample_formula):
        """Test successful rollback to previous version."""
        # Arrange
        formula_v2 = Formula(
            country_code="US",
            formula_code="US_STANDARD",
            formula_logic="charge = mtow_kg * 0.06 * distance_km",
            effective_date=date(2024, 2, 1),
            currency="USD",
            version_number=2,
            is_active=True,
            created_by="test_user"
        )
        sample_formula.is_active = False
        
        # Mock get_active_formula to return v2
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        
        # First call returns v2 (current active), second call returns v1 (target)
        mock_query.first.side_effect = [formula_v2, sample_formula]
        
        # Act
        result = formula_service.rollback_formula("US", 1)
        
        # Assert
        assert formula_v2.is_active is False  # Current version deactivated
        assert sample_formula.is_active is True  # Target version activated
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
        
        # Verify logging
        mock_logger.info.assert_called_once()
    
    def test_rollback_formula_no_active_raises_exception(self, formula_service, mock_session):
        """Test that rollback without active formula raises FormulaNotFoundException."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        # Act & Assert
        with pytest.raises(FormulaNotFoundException) as exc_info:
            formula_service.rollback_formula("XX", 1)
        
        assert "No active formula found" in str(exc_info.value)
        assert exc_info.value.status_code == 404
    
    def test_rollback_formula_version_not_found_raises_exception(self, formula_service, mock_session, sample_formula):
        """Test that rollback to non-existent version raises FormulaNotFoundException."""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        
        # First call returns active formula, second call returns None (version not found)
        mock_query.first.side_effect = [sample_formula, None]
        
        # Act & Assert
        with pytest.raises(FormulaNotFoundException) as exc_info:
            formula_service.rollback_formula("US", 99)
        
        assert "version 99 not found" in str(exc_info.value)
        assert exc_info.value.status_code == 404


class TestValidateFormulaSyntax:
    """Tests for validate_formula_syntax method."""
    
    def test_validate_formula_syntax_valid(self, formula_service):
        """Test that valid Python syntax passes validation."""
        # Arrange
        valid_formula = "charge = mtow_kg * 0.05 * distance_km"
        
        # Act
        is_valid, error_message = formula_service.validate_formula_syntax(valid_formula)
        
        # Assert
        assert is_valid is True
        assert error_message is None
    
    def test_validate_formula_syntax_invalid(self, formula_service):
        """Test that invalid Python syntax fails validation."""
        # Arrange
        invalid_formula = "invalid python syntax ("
        
        # Act
        is_valid, error_message = formula_service.validate_formula_syntax(invalid_formula)
        
        # Assert
        assert is_valid is False
        assert error_message is not None
        assert "Syntax error" in error_message
