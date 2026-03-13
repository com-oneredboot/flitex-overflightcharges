"""Property-based tests for FormulaExecutor error reporting.

This module contains property-based tests that verify error reporting clarity
across all failure scenarios.

Feature: python-formula-execution-system
Property 11: Error Reporting Clarity

Requirements: 9.1, 9.2, 9.3, 9.5
"""

import pytest
import uuid
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock

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


def create_formula_executor():
    """Create a FormulaExecutor instance with mocked dependencies."""
    mock_db_session = Mock()
    mock_cache = Mock(spec=FormulaCache)
    mock_cache.get_result.return_value = None
    mock_cache.get_bytecode.return_value = None
    mock_cache._enabled = True
    
    mock_constants_provider = Mock(spec=ConstantsProvider)
    mock_constants_provider.get_execution_context.return_value = {
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
    
    mock_rate_loader = Mock(spec=EuroControlRateLoader)
    mock_rate_loader.get_rates.return_value = {}
    
    executor = FormulaExecutor(
        db_session=mock_db_session,
        cache=mock_cache,
        constants_provider=mock_constants_provider,
        rate_loader=mock_rate_loader,
        timeout_seconds=1.0
    )
    
    return executor, mock_db_session


@given(
    distance=st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False),
    weight=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False),
    context=st.fixed_dictionaries({
        'firTag': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'arrival': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'departure': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'isFirstFir': st.booleans(),
        'isLastFir': st.booleans(),
        'firName': st.text(min_size=1, max_size=50),
        'originCountry': st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',))),
        'destinationCountry': st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',)))
    })
)
@settings(max_examples=100, deadline=None)
def test_formula_not_found_error_clarity(distance, weight, context):
    """
    **Validates: Requirements 9.1, 9.5**
    
    Property 11: Error Reporting Clarity (FormulaNotFoundError)
    
    For any formula execution that fails because the formula doesn't exist,
    the system should return a descriptive error message indicating:
    - The specific failure type (FormulaNotFoundError)
    - The formula_id that was not found
    - An appropriate HTTP status code (404)
    """
    executor, mock_db_session = create_formula_executor()
    formula_id = uuid.uuid4()
    
    # Arrange: Formula doesn't exist
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    
    # Act & Assert
    with pytest.raises(FormulaNotFoundError) as exc_info:
        executor.execute_formula(
            formula_id=formula_id,
            distance=distance,
            weight=weight,
            context=context
        )
    
    # Verify error clarity
    error = exc_info.value
    
    # 1. Error message should be descriptive
    assert len(error.message) > 0, "Error message should not be empty"
    assert "not found" in error.message.lower(), "Error message should indicate formula was not found"
    
    # 2. Error should include formula_id in details
    assert 'formula_id' in error.details, "Error details should include formula_id"
    assert str(formula_id) in error.details['formula_id'], "Error details should contain the actual formula_id"
    
    # 3. Error should have correct status code
    assert error.status_code == 404, "FormulaNotFoundError should have 404 status code"
    
    # 4. Error type should be identifiable
    assert type(error).__name__ == 'FormulaNotFoundError', "Error type should be FormulaNotFoundError"


@given(
    distance=st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False),
    weight=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False),
    context=st.fixed_dictionaries({
        'firTag': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'arrival': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'departure': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'isFirstFir': st.booleans(),
        'isLastFir': st.booleans(),
        'firName': st.text(min_size=1, max_size=50),
        'originCountry': st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',))),
        'destinationCountry': st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',)))
    }),
    syntax_error_type=st.sampled_from([
        "def calculate(distance, weight, context):\n    return {",  # Unclosed brace
        "def calculate(distance, weight, context)\n    return {}",  # Missing colon
        "def calculate(distance, weight, context):\nreturn {}",  # Bad indentation
    ])
)
@settings(max_examples=100, deadline=None)
def test_syntax_error_clarity(distance, weight, context, syntax_error_type):
    """
    **Validates: Requirements 9.1, 9.5**
    
    Property 11: Error Reporting Clarity (FormulaSyntaxError)
    
    For any formula execution that fails due to syntax errors,
    the system should return a descriptive error message indicating:
    - The specific failure type (FormulaSyntaxError)
    - Details about the syntax error
    - An appropriate HTTP status code (400)
    """
    executor, mock_db_session = create_formula_executor()
    formula_id = uuid.uuid4()
    
    # Arrange: Formula with syntax error
    formula = Mock(spec=Formula)
    formula.id = formula_id
    formula.version_number = 1
    formula.formula_logic = syntax_error_type
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = formula
    
    # Act & Assert
    with pytest.raises(FormulaSyntaxError) as exc_info:
        executor.execute_formula(
            formula_id=formula_id,
            distance=distance,
            weight=weight,
            context=context
        )
    
    # Verify error clarity
    error = exc_info.value
    
    # 1. Error message should be descriptive
    assert len(error.message) > 0, "Error message should not be empty"
    assert "syntax" in error.message.lower(), "Error message should indicate syntax error"
    
    # 2. Error should include formula_id in details
    assert 'formula_id' in error.details, "Error details should include formula_id"
    
    # 3. Error should have correct status code
    assert error.status_code == 400, "FormulaSyntaxError should have 400 status code"
    
    # 4. Error type should be identifiable
    assert type(error).__name__ == 'FormulaSyntaxError', "Error type should be FormulaSyntaxError"


@given(
    distance=st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False),
    weight=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False),
    context=st.fixed_dictionaries({
        'firTag': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'arrival': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'departure': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'isFirstFir': st.booleans(),
        'isLastFir': st.booleans(),
        'firName': st.text(min_size=1, max_size=50),
        'originCountry': st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',))),
        'destinationCountry': st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',)))
    }),
    execution_error_type=st.sampled_from([
        "def calculate(distance, weight, context):\n    raise ValueError('Test error')",
        "def calculate(distance, weight, context):\n    return 'not a dict'",
        "def calculate(distance, weight, context):\n    return {'cost': 100}",  # Missing fields
        "def other_function():\n    pass",  # Missing calculate function
    ])
)
@settings(max_examples=100, deadline=None)
def test_execution_error_clarity(distance, weight, context, execution_error_type):
    """
    **Validates: Requirements 9.2, 9.5**
    
    Property 11: Error Reporting Clarity (FormulaExecutionError)
    
    For any formula execution that fails during runtime,
    the system should return a descriptive error message indicating:
    - The specific failure type (FormulaExecutionError)
    - Details about what went wrong
    - An appropriate HTTP status code (500)
    """
    executor, mock_db_session = create_formula_executor()
    formula_id = uuid.uuid4()
    
    # Arrange: Formula with execution error
    formula = Mock(spec=Formula)
    formula.id = formula_id
    formula.version_number = 1
    formula.formula_logic = execution_error_type
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = formula
    
    # Act & Assert
    with pytest.raises(FormulaExecutionError) as exc_info:
        executor.execute_formula(
            formula_id=formula_id,
            distance=distance,
            weight=weight,
            context=context
        )
    
    # Verify error clarity
    error = exc_info.value
    
    # 1. Error message should be descriptive
    assert len(error.message) > 0, "Error message should not be empty"
    
    # 2. Error should include formula_id in details
    assert 'formula_id' in error.details, "Error details should include formula_id"
    
    # 3. Error should have correct status code
    assert error.status_code == 500, "FormulaExecutionError should have 500 status code"
    
    # 4. Error type should be identifiable
    assert type(error).__name__ == 'FormulaExecutionError', "Error type should be FormulaExecutionError"


@given(
    distance=st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False),
    weight=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False),
    context=st.fixed_dictionaries({
        'firTag': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'arrival': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'departure': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'isFirstFir': st.booleans(),
        'isLastFir': st.booleans(),
        'firName': st.text(min_size=1, max_size=50),
        'originCountry': st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',))),
        'destinationCountry': st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',)))
    })
)
@settings(max_examples=50, deadline=None)  # Fewer examples due to timeout test
def test_timeout_error_clarity(distance, weight, context):
    """
    **Validates: Requirements 9.4, 9.5**
    
    Property 11: Error Reporting Clarity (FormulaTimeoutError)
    
    For any formula execution that exceeds the timeout threshold,
    the system should return a descriptive error message indicating:
    - The specific failure type (FormulaTimeoutError)
    - The timeout duration
    - An appropriate HTTP status code (500)
    """
    executor, mock_db_session = create_formula_executor()
    formula_id = uuid.uuid4()
    
    # Arrange: Formula with infinite loop
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
        executor.execute_formula(
            formula_id=formula_id,
            distance=distance,
            weight=weight,
            context=context
        )
    
    # Verify error clarity
    error = exc_info.value
    
    # 1. Error message should be descriptive
    assert len(error.message) > 0, "Error message should not be empty"
    assert "timeout" in error.message.lower(), "Error message should indicate timeout"
    
    # 2. Error should include timeout duration in details
    assert 'timeout_seconds' in error.details, "Error details should include timeout_seconds"
    assert error.details['timeout_seconds'] == 1.0, "Error details should contain the actual timeout value"
    
    # 3. Error should have correct status code
    assert error.status_code == 500, "FormulaTimeoutError should have 500 status code"
    
    # 4. Error type should be identifiable
    assert type(error).__name__ == 'FormulaTimeoutError', "Error type should be FormulaTimeoutError"


@given(
    distance=st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False),
    weight=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False),
    context=st.fixed_dictionaries({
        'firTag': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'arrival': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'departure': st.text(min_size=4, max_size=4, alphabet=st.characters(whitelist_categories=('Lu',))),
        'isFirstFir': st.booleans(),
        'isLastFir': st.booleans(),
        'firName': st.text(min_size=1, max_size=50),
        'originCountry': st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',))),
        'destinationCountry': st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',)))
    })
)
@settings(max_examples=100, deadline=None)
def test_security_violation_error_clarity(distance, weight, context):
    """
    **Validates: Requirements 9.3, 9.5**
    
    Property 11: Error Reporting Clarity (SecurityViolationError)
    
    For any formula execution that attempts restricted operations,
    the system should return a descriptive error message indicating:
    - The specific failure type (SecurityViolationError)
    - Details about the security violation
    - An appropriate HTTP status code (500)
    """
    executor, mock_db_session = create_formula_executor()
    formula_id = uuid.uuid4()
    
    # Arrange: Formula with import statement (restricted operation)
    formula = Mock(spec=Formula)
    formula.id = formula_id
    formula.version_number = 1
    formula.formula_logic = """
import os
def calculate(distance, weight, context):
    return {'cost': 100.0, 'currency': 'USD', 'usd_cost': 100.0}
"""
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = formula
    
    # Act & Assert
    with pytest.raises(SecurityViolationError) as exc_info:
        executor.execute_formula(
            formula_id=formula_id,
            distance=distance,
            weight=weight,
            context=context
        )
    
    # Verify error clarity
    error = exc_info.value
    
    # 1. Error message should be descriptive
    assert len(error.message) > 0, "Error message should not be empty"
    assert "security" in error.message.lower() or "restricted" in error.message.lower() or "violation" in error.message.lower(), \
        "Error message should indicate security violation"
    
    # 2. Error should include formula_id in details
    assert 'formula_id' in error.details, "Error details should include formula_id"
    
    # 3. Error should have correct status code
    assert error.status_code == 500, "SecurityViolationError should have 500 status code"
    
    # 4. Error type should be identifiable
    assert type(error).__name__ == 'SecurityViolationError', "Error type should be SecurityViolationError"
