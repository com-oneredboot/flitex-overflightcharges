"""
Basic tests for FormulaExecutor methods.

Tests the execute_formula, execute_batch, and invalidate_cache methods
implemented in tasks 6.2, 6.3, and 6.4.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.2, 5.5, 8.2, 8.3
"""

import pytest
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

from src.formula_execution.formula_executor import FormulaExecutor
from src.formula_execution.formula_cache import FormulaCache
from src.formula_execution.constants_provider import ConstantsProvider
from src.formula_execution.eurocontrol_loader import EuroControlRateLoader
from src.models.formula import Formula
from src.exceptions import FormulaNotFoundException, InvalidSyntaxException, ServiceException


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return Mock()


@pytest.fixture
def mock_cache():
    """Create a mock FormulaCache."""
    cache = Mock(spec=FormulaCache)
    cache._enabled = True
    cache.get_result.return_value = None
    cache.get_bytecode.return_value = None
    return cache


@pytest.fixture
def constants_provider():
    """Create a real ConstantsProvider."""
    return ConstantsProvider()


@pytest.fixture
def mock_rate_loader():
    """Create a mock EuroControlRateLoader."""
    loader = Mock(spec=EuroControlRateLoader)
    loader.get_rates.return_value = {}
    return loader


@pytest.fixture
def executor(mock_db_session, mock_cache, constants_provider, mock_rate_loader):
    """Create a FormulaExecutor instance."""
    return FormulaExecutor(
        db_session=mock_db_session,
        cache=mock_cache,
        constants_provider=constants_provider,
        rate_loader=mock_rate_loader,
        timeout_seconds=1.0
    )


class TestExecuteFormula:
    """Test suite for execute_formula method."""
    
    def test_execute_formula_success(self, executor, mock_db_session, mock_cache):
        """Test successful formula execution.
        
        Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.2, 8.3
        """
        # Create a test formula
        formula_id = uuid4()
        formula = Formula(
            id=formula_id,
            country_code="US",
            description="Test Formula",
            formula_code="TEST_FORMULA",
            formula_logic="""
def calculate(distance, weight, context):
    cost = distance * 10 + weight * 5
    return {
        'cost': cost,
        'currency': 'USD',
        'usd_cost': cost
    }
""",
            effective_date="2024-01-01",
            currency="USD",
            version_number=1,
            is_active=True,
            created_by="test@example.com"
        )
        
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = formula
        mock_db_session.query.return_value = mock_query
        
        # Execute formula
        result = executor.execute_formula(
            formula_id=formula_id,
            distance=100.0,
            weight=50.0,
            context={
                'firTag': 'TEST',
                'arrival': 'DEST',
                'departure': 'ORIG',
                'isFirstFir': True,
                'isLastFir': False,
                'firName': 'Test FIR',
                'originCountry': 'US',
                'destinationCountry': 'CA'
            }
        )
        
        # Verify result
        assert result['cost'] == 1250.0  # 100 * 10 + 50 * 5
        assert result['currency'] == 'USD'
        assert result['usd_cost'] == 1250.0
        
        # Verify cache was called
        assert mock_cache.store_bytecode.called
        assert mock_cache.store_result.called
    
    def test_execute_formula_not_found(self, executor, mock_db_session):
        """Test formula not found error.
        
        Requirements: 8.2
        """
        formula_id = uuid4()
        
        # Mock database query to return None
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query
        
        # Execute formula should raise FormulaNotFoundException
        with pytest.raises(FormulaNotFoundException) as exc_info:
            executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={}
            )
        
        assert str(formula_id) in str(exc_info.value)
    
    def test_execute_formula_syntax_error(self, executor, mock_db_session, mock_cache):
        """Test formula with syntax errors.
        
        Requirements: 4.1
        """
        formula_id = uuid4()
        formula = Formula(
            id=formula_id,
            country_code="US",
            description="Test Formula",
            formula_code="TEST_FORMULA",
            formula_logic="def calculate(distance, weight, context):\n    return {invalid syntax",
            effective_date="2024-01-01",
            currency="USD",
            version_number=1,
            is_active=True,
            created_by="test@example.com"
        )
        
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = formula
        mock_db_session.query.return_value = mock_query
        
        # Execute formula should raise InvalidSyntaxException
        with pytest.raises(InvalidSyntaxException):
            executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={}
            )
    
    def test_execute_formula_missing_calculate_function(self, executor, mock_db_session, mock_cache):
        """Test formula without calculate function.
        
        Requirements: 4.1
        """
        formula_id = uuid4()
        formula = Formula(
            id=formula_id,
            country_code="US",
            description="Test Formula",
            formula_code="TEST_FORMULA",
            formula_logic="x = 10",  # No calculate function
            effective_date="2024-01-01",
            currency="USD",
            version_number=1,
            is_active=True,
            created_by="test@example.com"
        )
        
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = formula
        mock_db_session.query.return_value = mock_query
        
        # Execute formula should raise ServiceException
        with pytest.raises(ServiceException) as exc_info:
            executor.execute_formula(
                formula_id=formula_id,
                distance=100.0,
                weight=50.0,
                context={}
            )
        
        assert "calculate" in str(exc_info.value).lower()


class TestExecuteBatch:
    """Test suite for execute_batch method."""
    
    def test_execute_batch_success(self, executor, mock_db_session, mock_cache):
        """Test successful batch execution.
        
        Requirements: 5.5
        """
        # Create test formulas
        formula_id_1 = uuid4()
        formula_id_2 = uuid4()
        
        formula_1 = Formula(
            id=formula_id_1,
            country_code="US",
            description="Test Formula 1",
            formula_code="TEST_FORMULA_1",
            formula_logic="""
def calculate(distance, weight, context):
    return {'cost': 100.0, 'currency': 'USD', 'usd_cost': 100.0}
""",
            effective_date="2024-01-01",
            currency="USD",
            version_number=1,
            is_active=True,
            created_by="test@example.com"
        )
        
        formula_2 = Formula(
            id=formula_id_2,
            country_code="CA",
            description="Test Formula 2",
            formula_code="TEST_FORMULA_2",
            formula_logic="""
def calculate(distance, weight, context):
    return {'cost': 200.0, 'currency': 'CAD', 'usd_cost': 150.0}
""",
            effective_date="2024-01-01",
            currency="CAD",
            version_number=1,
            is_active=True,
            created_by="test@example.com"
        )
        
        # Mock database query to return different formulas
        def mock_query_side_effect(*args):
            mock_query = Mock()
            def filter_side_effect(*filter_args):
                mock_result = Mock()
                # Return formula based on which ID is being queried
                if hasattr(filter_args[0], 'right') and filter_args[0].right.value == formula_id_1:
                    mock_result.first.return_value = formula_1
                else:
                    mock_result.first.return_value = formula_2
                return mock_result
            mock_query.filter.side_effect = filter_side_effect
            return mock_query
        
        mock_db_session.query.side_effect = mock_query_side_effect
        
        # Execute batch
        executions = [
            {
                'formula_id': formula_id_1,
                'distance': 100.0,
                'weight': 50.0,
                'context': {}
            },
            {
                'formula_id': formula_id_2,
                'distance': 200.0,
                'weight': 75.0,
                'context': {}
            }
        ]
        
        results = executor.execute_batch(executions)
        
        # Verify results
        assert len(results) == 2
        assert results[0]['success'] is True
        assert results[0]['result']['cost'] == 100.0
        assert results[1]['success'] is True
        assert results[1]['result']['cost'] == 200.0
    
    def test_execute_batch_partial_failure(self, executor, mock_db_session, mock_cache):
        """Test batch execution with one failure.
        
        Requirements: 5.5
        """
        formula_id_1 = uuid4()
        formula_id_2 = uuid4()
        
        formula_1 = Formula(
            id=formula_id_1,
            country_code="US",
            description="Test Formula 1",
            formula_code="TEST_FORMULA_1",
            formula_logic="""
def calculate(distance, weight, context):
    return {'cost': 100.0, 'currency': 'USD', 'usd_cost': 100.0}
""",
            effective_date="2024-01-01",
            currency="USD",
            version_number=1,
            is_active=True,
            created_by="test@example.com"
        )
        
        # Mock database query
        def mock_query_side_effect(*args):
            mock_query = Mock()
            def filter_side_effect(*filter_args):
                mock_result = Mock()
                if hasattr(filter_args[0], 'right') and filter_args[0].right.value == formula_id_1:
                    mock_result.first.return_value = formula_1
                else:
                    mock_result.first.return_value = None  # Formula 2 not found
                return mock_result
            mock_query.filter.side_effect = filter_side_effect
            return mock_query
        
        mock_db_session.query.side_effect = mock_query_side_effect
        
        # Execute batch
        executions = [
            {
                'formula_id': formula_id_1,
                'distance': 100.0,
                'weight': 50.0,
                'context': {}
            },
            {
                'formula_id': formula_id_2,
                'distance': 200.0,
                'weight': 75.0,
                'context': {}
            }
        ]
        
        results = executor.execute_batch(executions)
        
        # Verify results
        assert len(results) == 2
        assert results[0]['success'] is True
        assert results[1]['success'] is False
        assert 'error' in results[1]


class TestInvalidateCache:
    """Test suite for invalidate_cache method."""
    
    def test_invalidate_cache(self, executor, mock_cache):
        """Test cache invalidation.
        
        Requirements: 5.2
        """
        formula_id = uuid4()
        
        # Invalidate cache
        executor.invalidate_cache(formula_id)
        
        # Verify cache invalidation was called
        mock_cache.invalidate_formula.assert_called_once_with(formula_id)
