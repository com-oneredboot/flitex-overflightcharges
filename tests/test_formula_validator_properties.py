"""Property-based tests for FormulaValidator.

Tests universal properties of the validation pipeline including syntax
validation, test execution, Black formatting idempotence, hash determinism,
formula storage, duplicate detection, and error specificity.

Requirements: 11.1, 11.3, 11.4, 11.6, 11.7, 11.8, 11.9, 11.10
"""

import hashlib
import pytest
from datetime import date
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from unittest.mock import Mock
from uuid import uuid4

import black

from src.exceptions import (
    FormulaDuplicateError,
    FormulaSyntaxError,
    FormulaValidationError,
)
from src.formula_execution.formula_validator import FormulaValidator
from src.models.formula import Formula


# Strategy for generating valid Python function code
@st.composite
def valid_formula_code(draw):
    """Generate valid formula code with calculate function."""
    multiplier = draw(st.floats(min_value=0.1, max_value=100.0))
    currency = draw(st.sampled_from(['USD', 'EUR', 'GBP', 'CAD']))
    
    code = f"""
def calculate(distance, weight, context):
    cost = distance * {multiplier}
    return {{
        'cost': cost,
        'currency': '{currency}',
        'usd_cost': cost
    }}
"""
    return code


# Strategy for generating invalid Python syntax
@st.composite
def invalid_syntax_code(draw):
    """Generate code with syntax errors."""
    error_type = draw(st.sampled_from([
        'missing_colon',
        'missing_comma',
        'invalid_indentation',
        'unclosed_bracket'
    ]))
    
    if error_type == 'missing_colon':
        return "def calculate(distance, weight, context)\n    return {}"
    elif error_type == 'missing_comma':
        return "def calculate(distance, weight, context):\n    return {'a': 1 'b': 2}"
    elif error_type == 'invalid_indentation':
        return "def calculate(distance, weight, context):\ncost = 10\n    return {}"
    else:  # unclosed_bracket
        return "def calculate(distance, weight, context):\n    return {'a': 1"


# Strategy for generating code without calculate function
@st.composite
def code_without_calculate(draw):
    """Generate valid Python code without calculate function."""
    func_name = draw(st.sampled_from(['compute', 'process', 'run', 'execute']))
    return f"""
def {func_name}(distance, weight, context):
    return {{'cost': 100, 'currency': 'USD', 'usd_cost': 100}}
"""


@pytest.fixture
def db_session(mocker):
    """Mock database session."""
    session = mocker.Mock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    return session


@pytest.fixture
def formula_executor(mocker):
    """Mock formula executor."""
    executor = mocker.Mock()
    executor.execute_formula.return_value = {
        'cost': 100.0,
        'currency': 'USD',
        'usd_cost': 100.0
    }
    return executor


@pytest.fixture
def validator(db_session, formula_executor):
    """Create FormulaValidator instance."""
    return FormulaValidator(db_session, formula_executor)


class TestProperty15SyntaxValidation:
    """Property 15: Syntax Validation
    
    For any formula code submitted for validation, if it contains Python
    syntax errors, the validator should reject it before attempting
    execution or formatting.
    
    **Validates: Requirements 11.1**
    """
    
    @given(code=invalid_syntax_code())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_syntax_rejected(self, validator, code):
        """Test that any code with syntax errors is rejected."""
        with pytest.raises(FormulaSyntaxError):
            validator._check_syntax(code)
    
    @given(code=valid_formula_code())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_valid_syntax_accepted(self, validator, code):
        """Test that valid Python syntax passes."""
        # Should not raise exception
        validator._check_syntax(code)


class TestProperty16TestExecutionRequirement:
    """Property 16: Test Execution Requirement
    
    For any formula submitted for validation, the validator should execute
    a test calculation with sample data, and if the test fails, reject
    the formula.
    
    **Validates: Requirements 11.3**
    """
    
    @given(code=valid_formula_code())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_successful_execution_passes(self, validator, code, formula_executor):
        """Test that formulas passing test execution are accepted."""
        # Mock successful execution
        formula_executor.execute_formula.return_value = {
            'cost': 100.0,
            'currency': 'USD',
            'usd_cost': 100.0
        }
        
        # Should not raise exception
        validator._test_execution(code)
    
    @given(code=valid_formula_code())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_execution_failure_rejected(self, validator, code, formula_executor):
        """Test that formulas failing test execution are rejected."""
        from src.exceptions import FormulaExecutionError
        
        # Mock execution failure
        formula_executor.execute_formula.side_effect = FormulaExecutionError(
            "Test execution failed"
        )
        
        with pytest.raises(FormulaValidationError) as exc_info:
            validator._test_execution(code)
        
        assert exc_info.value.details['reason'] == 'test_execution_failed'
    
    @given(code=valid_formula_code())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_missing_result_fields_rejected(self, validator, code, formula_executor):
        """Test that formulas returning incomplete results are rejected."""
        # Mock incomplete result
        formula_executor.execute_formula.return_value = {
            'cost': 100.0
            # Missing 'currency' and 'usd_cost'
        }
        
        with pytest.raises(FormulaValidationError) as exc_info:
            validator._test_execution(code)
        
        assert exc_info.value.details['reason'] == 'missing_result_fields'


class TestProperty17BlackFormattingIdempotence:
    """Property 17: Black Formatting Idempotence
    
    For any formula code that passes validation, formatting it with Black
    should produce formatted code, and formatting that result again should
    produce identical output (idempotence).
    
    **Validates: Requirements 11.4**
    """
    
    @given(code=valid_formula_code())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_formatting_idempotence(self, validator, code):
        """Test that Black formatting is idempotent."""
        # Format once
        formatted_once = validator._format_code(code)
        
        # Format again
        formatted_twice = validator._format_code(formatted_once)
        
        # Should be identical
        assert formatted_once == formatted_twice
    
    @given(code=valid_formula_code())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_formatting_produces_valid_code(self, validator, code):
        """Test that formatted code is still valid Python."""
        formatted = validator._format_code(code)
        
        # Should be valid Python syntax
        validator._check_syntax(formatted)
    
    @given(code=valid_formula_code())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_formatting_preserves_calculate_function(self, validator, code):
        """Test that formatting preserves the calculate function."""
        formatted = validator._format_code(code)
        
        # Should still have calculate function
        validator._verify_calculate_function(formatted)


class TestProperty18HashComputationDeterminism:
    """Property 18: Hash Computation Determinism
    
    For any formula code, computing the SHA256 hash twice on the same
    formatted code should produce identical hash values.
    
    **Validates: Requirements 11.6**
    """
    
    @given(code=valid_formula_code())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_hash_determinism(self, validator, code):
        """Test that hash computation is deterministic."""
        hash1 = validator._compute_hash(code)
        hash2 = validator._compute_hash(code)
        
        assert hash1 == hash2
    
    @given(code=valid_formula_code())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_hash_format(self, validator, code):
        """Test that hash is 64-character hex string."""
        hash_value = validator._compute_hash(code)
        
        # Should be 64-character hex string (SHA256)
        assert len(hash_value) == 64
        assert all(c in '0123456789abcdef' for c in hash_value)
    
    @given(
        code1=valid_formula_code(),
        code2=valid_formula_code()
    )
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_different_code_different_hash(self, validator, code1, code2):
        """Test that different code produces different hash (with high probability)."""
        # Skip if codes are identical
        assume(code1 != code2)
        
        hash1 = validator._compute_hash(code1)
        hash2 = validator._compute_hash(code2)
        
        # Different code should produce different hash
        # (collision is theoretically possible but extremely unlikely)
        assert hash1 != hash2
    
    @given(code=valid_formula_code())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_hash_matches_manual_computation(self, validator, code):
        """Test that hash matches manual SHA256 computation."""
        validator_hash = validator._compute_hash(code)
        manual_hash = hashlib.sha256(code.encode('utf-8')).hexdigest()
        
        assert validator_hash == manual_hash


class TestProperty19FormulaStorageWithHash:
    """Property 19: Formula Storage with Hash
    
    For any valid formula that passes validation, saving it to the database
    should store both the formula code in formula_logic column and the
    SHA256 hash in formula_hash column.
    
    **Validates: Requirements 1.1, 11.7, 11.10**
    """
    
    @given(
        code=valid_formula_code(),
        country_code=st.sampled_from(['US', 'CA', 'GB', 'FR', 'DE']),
        currency=st.sampled_from(['USD', 'EUR', 'GBP', 'CAD'])
    )
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_formula_stored_with_hash(
        self,
        validator,
        code,
        country_code,
        currency,
        db_session
    ):
        """Test that saved formula includes hash."""
        formula = validator.validate_and_save(
            formula_code=code,
            country_code=country_code,
            description=f'{country_code} Formula',
            formula_code_id=f'{country_code}_FORMULA',
            effective_date=date(2024, 1, 1),
            currency=currency,
            created_by='test@example.com'
        )
        
        # Verify formula has hash
        assert formula.formula_hash is not None
        assert len(formula.formula_hash) == 64
        
        # Verify formula has code
        assert formula.formula_logic is not None
        assert 'calculate' in formula.formula_logic
    
    @given(code=valid_formula_code())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_stored_hash_matches_code(self, validator, code, db_session):
        """Test that stored hash matches the formatted code."""
        formula = validator.validate_and_save(
            formula_code=code,
            country_code='US',
            description='Test',
            formula_code_id='TEST',
            effective_date=date(2024, 1, 1),
            currency='USD',
            created_by='test@example.com'
        )
        
        # Compute hash of stored code
        expected_hash = validator._compute_hash(formula.formula_logic)
        
        # Should match stored hash
        assert formula.formula_hash == expected_hash
    
    @given(code=valid_formula_code())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_formula_stored_with_bytecode(self, validator, code, db_session):
        """Test that saved formula includes compiled bytecode."""
        formula = validator.validate_and_save(
            formula_code=code,
            country_code='US',
            description='Test',
            formula_code_id='TEST',
            effective_date=date(2024, 1, 1),
            currency='USD',
            created_by='test@example.com'
        )
        
        # Verify formula has bytecode
        assert formula.formula_bytecode is not None
        assert isinstance(formula.formula_bytecode, bytes)


class TestProperty20DuplicateDetection:
    """Property 20: Duplicate Detection
    
    For any formula submitted for validation, if a formula with an identical
    SHA256 hash already exists in the database, the validator should reject
    the save with a duplicate formula error.
    
    **Validates: Requirements 11.8**
    """
    
    @given(code=valid_formula_code())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_duplicate_hash_rejected(self, validator, code, db_session):
        """Test that duplicate hash is rejected."""
        # Mock existing formula with same hash
        existing_formula = Mock(spec=Formula)
        existing_formula.id = uuid4()
        db_session.query.return_value.filter.return_value.first.return_value = existing_formula
        
        with pytest.raises(FormulaDuplicateError) as exc_info:
            validator.validate_and_save(
                formula_code=code,
                country_code='US',
                description='Test',
                formula_code_id='TEST',
                effective_date=date(2024, 1, 1),
                currency='USD',
                created_by='test@example.com'
            )
        
        assert "already exists" in str(exc_info.value)
        assert 'hash' in exc_info.value.details
    
    @given(code=valid_formula_code())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unique_hash_accepted(self, validator, code, db_session):
        """Test that unique hash is accepted."""
        # Mock no existing formula
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Should not raise exception
        formula = validator.validate_and_save(
            formula_code=code,
            country_code='US',
            description='Test',
            formula_code_id='TEST',
            effective_date=date(2024, 1, 1),
            currency='USD',
            created_by='test@example.com'
        )
        
        assert formula is not None


class TestProperty21ValidationErrorSpecificity:
    """Property 21: Validation Error Specificity
    
    For any formula that fails validation (syntax, missing calculate function,
    test execution failure, or duplicate hash), the error message should
    specifically indicate which validation step failed.
    
    **Validates: Requirements 11.9**
    """
    
    @given(code=invalid_syntax_code())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_syntax_error_specificity(self, validator, code):
        """Test that syntax errors are specific."""
        with pytest.raises(FormulaSyntaxError) as exc_info:
            validator._check_syntax(code)
        
        # Error should mention syntax
        assert "Syntax error" in str(exc_info.value)
        # Should include line number
        assert exc_info.value.details.get('line') is not None
    
    @given(code=code_without_calculate())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_missing_calculate_error_specificity(self, validator, code):
        """Test that missing calculate function error is specific."""
        with pytest.raises(FormulaValidationError) as exc_info:
            validator._verify_calculate_function(code)
        
        # Error should mention calculate function
        assert "calculate" in str(exc_info.value).lower()
        # Should have specific reason
        assert exc_info.value.details['reason'] == 'missing_calculate_function'
    
    @given(code=valid_formula_code())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_execution_error_specificity(self, validator, code, formula_executor):
        """Test that execution errors are specific."""
        from src.exceptions import FormulaExecutionError
        
        # Mock execution failure
        formula_executor.execute_formula.side_effect = FormulaExecutionError(
            "Division by zero"
        )
        
        with pytest.raises(FormulaValidationError) as exc_info:
            validator._test_execution(code)
        
        # Error should mention test execution
        assert "Test execution failed" in str(exc_info.value)
        # Should have specific reason
        assert exc_info.value.details['reason'] == 'test_execution_failed'
    
    @given(code=valid_formula_code())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_duplicate_error_specificity(self, validator, code, db_session):
        """Test that duplicate errors are specific."""
        # Mock existing formula
        existing_formula = Mock(spec=Formula)
        existing_formula.id = uuid4()
        db_session.query.return_value.filter.return_value.first.return_value = existing_formula
        
        with pytest.raises(FormulaDuplicateError) as exc_info:
            validator.validate_and_save(
                formula_code=code,
                country_code='US',
                description='Test',
                formula_code_id='TEST',
                effective_date=date(2024, 1, 1),
                currency='USD',
                created_by='test@example.com'
            )
        
        # Error should mention duplicate
        assert "already exists" in str(exc_info.value)
        # Should include hash
        assert 'hash' in exc_info.value.details
    
    @given(code=valid_formula_code())
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_all_errors_have_details(self, validator, code, formula_executor, db_session):
        """Test that all validation errors include details dictionary."""
        from src.exceptions import FormulaExecutionError
        
        # Test various error scenarios
        error_scenarios = [
            # Syntax error
            (lambda: validator._check_syntax("def invalid syntax"), FormulaSyntaxError),
            # Missing calculate
            (lambda: validator._verify_calculate_function("def other(): pass"), FormulaValidationError),
        ]
        
        for scenario_func, expected_exception in error_scenarios:
            try:
                scenario_func()
            except expected_exception as e:
                # All errors should have details
                assert hasattr(e, 'details')
                assert isinstance(e.details, dict)
            except Exception:
                # Skip if scenario doesn't apply
                pass
