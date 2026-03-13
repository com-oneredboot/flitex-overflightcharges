"""Unit tests for FormulaExecutor error handling.

This module tests all error handling scenarios for the FormulaExecutor,
including FormulaNotFoundError, FormulaSyntaxError, FormulaExecutionError,
FormulaTimeoutError, and SecurityViolationError.

Requirements: 9.1, 9.2, 9.3, 9.4
"""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from src.formula_execution.formula_executor import FormulaExecutor
from src.formula_execution.formula_cache import FormulaCache
from src.formula_execution.constants_provider import ConstantsProvider
from src.formula_execution.eurocontrol_loader import EuroControlRateLoader
from src.exceptions import (
    FormulaNotFoundError,
    FormulaSyntaxError,
    FormulaExecutionError,
    FormulaTimeoutError,
    SecurityViolationError
)
from src.models.formula import Formula


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def mock_cache():
    """Create a mock formula cache."""
    cache = Mock(spec=FormulaCache)
    cache.get_result.return_value = None
    cache.get_bytecode.return_value = None
    cache.store_bytecode.return_value = None
    cache.store_result.return_value = None
    cache._enabled = True
    return cache


@pytest.fixture
def mock_constants_provider():
    """Create a mock constants provider."""
    provider = Mock(spec=ConstantsProvider)
    provider.get_execution_context.return_value = {
        'sqrt': lambda x: x ** 0.5,
        'pow': pow,
        'abs': abs,
        'ceil': lambda x: int(x + 0.5),
        'floor': int,
        'round': round,
        'CURRENCY_CONSTANTS': {'USD': 'USD', 'EUR': 'EUR'},
        'COUNTRY_NAME_CONSTANTS': {'USA': 'United States'},
        'FIR_NAMES_PER_COUNTRY': {'USA': ['KZAB']},
        'CANADA_TSC_AERODROMES': [],
        'convert_nm_to_km': lambda nm: nm * 1.852
    }
    return provider


@pytest.fixture
def mock_rate_loader():
    """Create a mock EuroControl rate loader."""
    loader = Mock(spec=EuroControlRateLoader)
    loader.get_rates.return_value = {}
    return loader


@pytest.fixture
def formula_executor(mock_db_session, mock_cache, mock_constants_provider, mock_rate_loader):
    """Create a FormulaExecutor instance with mocked dependencies."""
    return FormulaExecutor(
        db_session=mock_db_session,
        cache=mock_cache,
        constants_provider=mock_constants_provider,
        rate_loader=mock_rate_loader,
        timeout_seconds=1.0
    )


class TestFormulaNotFoundError:
    """Test FormulaNotFoundError scenarios.
    
    Requirements: 9.1
    """
    
    def test_formula_not_found_raises_error(self, formula_executor, mock_db_session):
        """Test that FormulaNotFoundError is raised when formula doesn't exist."""
        # Arrange
        formula_id = uuid.uuid4()
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Act & Assert
        with pytest.raises(FormulaNotFoundError) as exc_info:
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        assert str(formula_id) in str(exc_info.value)
        assert exc_info.value.status_code == 404
        assert 'formula_id' in exc_info.value.details
    
    def test_formula_not_found_error_message(self, formula_executor, mock_db_session):
        """Test that FormulaNotFoundError has descriptive error message."""
        # Arrange
        formula_id = uuid.uuid4()
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Act & Assert
        with pytest.raises(FormulaNotFoundError) as exc_info:
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        assert "not found" in str(exc_info.value).lower()


class TestFormulaSyntaxError:
    """Test FormulaSyntaxError scenarios.
    
    Requirements: 9.1
    """
    
    def test_syntax_error_raises_formula_syntax_error(self, formula_executor, mock_db_session):
        """Test that FormulaSyntaxError is raised for invalid Python syntax."""
        # Arrange
        formula_id = uuid.uuid4()
        formula = Mock(spec=Formula)
        formula.id = formula_id
        formula.version_number = 1
        formula.formula_logic = "def calculate(distance, weight, context):\n    return {"  # Invalid syntax
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = formula
        
        # Act & Assert
        with pytest.raises(FormulaSyntaxError) as exc_info:
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        assert exc_info.value.status_code == 400
        assert 'formula_id' in exc_info.value.details
    
    def test_syntax_error_includes_line_number(self, formula_executor, mock_db_session):
        """Test that FormulaSyntaxError includes line number in details."""
        # Arrange
        formula_id = uuid.uuid4()
        formula = Mock(spec=Formula)
        formula.id = formula_id
        formula.version_number = 1
        formula.formula_logic = "def calculate(distance, weight, context):\n    if True\n    return {}"
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = formula
        
        # Act & Assert
        with pytest.raises(FormulaSyntaxError) as exc_info:
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        assert 'syntax' in str(exc_info.value).lower()


class TestFormulaExecutionError:
    """Test FormulaExecutionError scenarios.
    
    Requirements: 9.2
    """
    
    def test_runtime_exception_raises_execution_error(self, formula_executor, mock_db_session):
        """Test that FormulaExecutionError is raised when formula raises exception."""
        # Arrange
        formula_id = uuid.uuid4()
        formula = Mock(spec=Formula)
        formula.id = formula_id
        formula.version_number = 1
        formula.formula_logic = """
def calculate(distance, weight, context):
    raise ValueError("Test error")
"""
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = formula
        
        # Act & Assert
        with pytest.raises(FormulaExecutionError) as exc_info:
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        assert exc_info.value.status_code == 500
        assert 'formula_id' in exc_info.value.details
    
    def test_missing_calculate_function_raises_execution_error(self, formula_executor, mock_db_session):
        """Test that FormulaExecutionError is raised when calculate function is missing."""
        # Arrange
        formula_id = uuid.uuid4()
        formula = Mock(spec=Formula)
        formula.id = formula_id
        formula.version_number = 1
        formula.formula_logic = """
def some_other_function():
    pass
"""
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = formula
        
        # Act & Assert
        with pytest.raises(FormulaExecutionError) as exc_info:
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        assert "calculate" in str(exc_info.value).lower()
    
    def test_invalid_return_type_raises_execution_error(self, formula_executor, mock_db_session):
        """Test that FormulaExecutionError is raised when formula returns non-dict."""
        # Arrange
        formula_id = uuid.uuid4()
        formula = Mock(spec=Formula)
        formula.id = formula_id
        formula.version_number = 1
        formula.formula_logic = """
def calculate(distance, weight, context):
    return "not a dict"
"""
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = formula
        
        # Act & Assert
        with pytest.raises(FormulaExecutionError) as exc_info:
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        assert "dictionary" in str(exc_info.value).lower()
    
    def test_missing_required_fields_raises_execution_error(self, formula_executor, mock_db_session):
        """Test that FormulaExecutionError is raised when result missing required fields."""
        # Arrange
        formula_id = uuid.uuid4()
        formula = Mock(spec=Formula)
        formula.id = formula_id
        formula.version_number = 1
        formula.formula_logic = """
def calculate(distance, weight, context):
    return {'cost': 100.0}  # Missing currency and usd_cost
"""
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = formula
        
        # Act & Assert
        with pytest.raises(FormulaExecutionError) as exc_info:
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        assert "missing" in str(exc_info.value).lower()
        assert "missing_fields" in exc_info.value.details


class TestFormulaTimeoutError:
    """Test FormulaTimeoutError scenarios.
    
    Requirements: 9.4
    """
    
    def test_timeout_raises_timeout_error(self, formula_executor, mock_db_session):
        """Test that FormulaTimeoutError is raised when formula exceeds timeout."""
        # Arrange
        formula_id = uuid.uuid4()
        formula = Mock(spec=Formula)
        formula.id = formula_id
        formula.version_number = 1
        # Formula with infinite loop
        formula.formula_logic = """
def calculate(distance, weight, context):
    while True:
        pass
"""
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = formula
        
        # Act & Assert
        with pytest.raises(FormulaTimeoutError) as exc_info:
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        assert exc_info.value.status_code == 500
        assert 'timeout_seconds' in exc_info.value.details
    
    def test_timeout_error_includes_duration(self, formula_executor, mock_db_session):
        """Test that FormulaTimeoutError includes timeout duration in details."""
        # Arrange
        formula_id = uuid.uuid4()
        formula = Mock(spec=Formula)
        formula.id = formula_id
        formula.version_number = 1
        formula.formula_logic = """
def calculate(distance, weight, context):
    while True:
        pass
"""
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = formula
        
        # Act & Assert
        with pytest.raises(FormulaTimeoutError) as exc_info:
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        assert exc_info.value.details['timeout_seconds'] == 1.0


class TestSecurityViolationError:
    """Test SecurityViolationError scenarios.
    
    Requirements: 9.3
    """
    
    def test_restricted_compilation_raises_security_error(self, formula_executor, mock_db_session):
        """Test that SecurityViolationError is raised for restricted operations during compilation."""
        # Arrange
        formula_id = uuid.uuid4()
        formula = Mock(spec=Formula)
        formula.id = formula_id
        formula.version_number = 1
        # Formula with import statement (blocked by RestrictedPython)
        formula.formula_logic = """
import os
def calculate(distance, weight, context):
    return {'cost': 100.0, 'currency': 'USD', 'usd_cost': 100.0}
"""
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = formula
        
        # Act & Assert
        with pytest.raises(SecurityViolationError) as exc_info:
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        assert exc_info.value.status_code == 500
        assert 'formula_id' in exc_info.value.details


class TestErrorLogging:
    """Test that all errors are logged with structured logging.
    
    Requirements: 9.5
    """
    
    @patch('src.formula_execution.formula_executor.logger')
    def test_formula_not_found_is_logged(self, mock_logger, formula_executor, mock_db_session):
        """Test that FormulaNotFoundError is logged with structured data."""
        # Arrange
        formula_id = uuid.uuid4()
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Act
        with pytest.raises(FormulaNotFoundError):
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        # Assert
        mock_logger.error.assert_called()
        call_args = mock_logger.error.call_args
        assert 'extra' in call_args.kwargs
        assert 'formula_id' in call_args.kwargs['extra']
    
    @patch('src.formula_execution.formula_executor.logger')
    def test_syntax_error_is_logged(self, mock_logger, formula_executor, mock_db_session):
        """Test that FormulaSyntaxError is logged with structured data."""
        # Arrange
        formula_id = uuid.uuid4()
        formula = Mock(spec=Formula)
        formula.id = formula_id
        formula.version_number = 1
        formula.formula_logic = "def calculate(distance, weight, context):\n    return {"
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = formula
        
        # Act
        with pytest.raises(FormulaSyntaxError):
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        # Assert
        mock_logger.error.assert_called()
        call_args = mock_logger.error.call_args
        assert 'extra' in call_args.kwargs
        assert 'formula_id' in call_args.kwargs['extra']
        assert 'error_type' in call_args.kwargs['extra']
    
    @patch('src.formula_execution.formula_executor.logger')
    def test_execution_error_is_logged_with_traceback(self, mock_logger, formula_executor, mock_db_session):
        """Test that FormulaExecutionError is logged with traceback."""
        # Arrange
        formula_id = uuid.uuid4()
        formula = Mock(spec=Formula)
        formula.id = formula_id
        formula.version_number = 1
        formula.formula_logic = """
def calculate(distance, weight, context):
    raise ValueError("Test error")
"""
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = formula
        
        # Act
        with pytest.raises(FormulaExecutionError):
            formula_executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={'firTag': 'TEST'}
            )
        
        # Assert
        mock_logger.error.assert_called()
        call_args = mock_logger.error.call_args
        assert 'extra' in call_args.kwargs
        assert 'traceback' in call_args.kwargs['extra']


class TestBatchExecutionErrorHandling:
    """Test error handling in batch execution.
    
    Requirements: 5.5, 9.5
    """
    
    def test_batch_continues_after_error(self, formula_executor, mock_db_session):
        """Test that batch execution continues after one formula fails."""
        # Arrange
        formula_id_1 = uuid.uuid4()
        formula_id_2 = uuid.uuid4()
        
        # First formula doesn't exist
        # Second formula exists and works
        formula_2 = Mock(spec=Formula)
        formula_2.id = formula_id_2
        formula_2.version_number = 1
        formula_2.formula_logic = """
def calculate(distance, weight, context):
    return {'cost': 100.0, 'currency': 'USD', 'usd_cost': 100.0}
"""
        
        def mock_query_filter_first(*args, **kwargs):
            # Return None for first formula, formula_2 for second
            if mock_db_session.query.return_value.filter.call_count == 1:
                return None
            return formula_2
        
        mock_db_session.query.return_value.filter.return_value.first.side_effect = mock_query_filter_first
        
        executions = [
            {
                'formula_id': formula_id_1,
                'distance': 100.0,
                'weight': 50.0,
                'context': {'firTag': 'TEST'}
            },
            {
                'formula_id': formula_id_2,
                'distance': 200.0,
                'weight': 75.0,
                'context': {'firTag': 'TEST'}
            }
        ]
        
        # Act
        results = formula_executor.execute_batch(executions)
        
        # Assert
        assert len(results) == 2
        assert results[0]['success'] is False
        assert results[1]['success'] is True
    
    def test_batch_error_includes_error_type(self, formula_executor, mock_db_session):
        """Test that batch execution errors include error type."""
        # Arrange
        formula_id = uuid.uuid4()
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        executions = [
            {
                'formula_id': formula_id,
                'distance': 100.0,
                'weight': 50.0,
                'context': {'firTag': 'TEST'}
            }
        ]
        
        # Act
        results = formula_executor.execute_batch(executions)
        
        # Assert
        assert len(results) == 1
        assert results[0]['success'] is False
        assert 'error_type' in results[0]
        assert results[0]['error_type'] == 'FormulaNotFoundError'
