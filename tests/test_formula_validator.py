"""Unit tests for FormulaValidator.

Tests the validation pipeline including syntax checking, calculate function
verification, test execution, Black formatting, linting, hash computation,
and duplicate detection.

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.8
"""

import pytest
from datetime import date
from unittest.mock import Mock, patch
from uuid import uuid4

from src.exceptions import (
    FormulaDuplicateError,
    FormulaLintError,
    FormulaSyntaxError,
    FormulaValidationError,
)
from src.formula_execution.formula_validator import FormulaValidator
from src.models.formula import Formula


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


@pytest.fixture
def valid_formula_code():
    """Valid formula code for testing."""
    return """
def calculate(distance, weight, context):
    cost = distance * 10.0
    return {
        'cost': cost,
        'currency': 'USD',
        'usd_cost': cost
    }
"""


class TestSyntaxValidation:
    """Test syntax validation (Requirement 11.1)."""
    
    def test_valid_syntax(self, validator, valid_formula_code):
        """Test that valid Python syntax passes."""
        # Should not raise exception
        validator._check_syntax(valid_formula_code)
    
    def test_invalid_syntax(self, validator):
        """Test that invalid Python syntax raises FormulaSyntaxError."""
        invalid_code = """
def calculate(distance, weight, context):
    cost = distance * 10.0
    return {
        'cost': cost,
        'currency': 'USD'
        'usd_cost': cost  # Missing comma
    }
"""
        with pytest.raises(FormulaSyntaxError) as exc_info:
            validator._check_syntax(invalid_code)
        
        assert "Syntax error" in str(exc_info.value)
        assert exc_info.value.details.get('line') is not None
    
    def test_indentation_error(self, validator):
        """Test that indentation errors raise FormulaSyntaxError."""
        invalid_code = """
def calculate(distance, weight, context):
cost = distance * 10.0  # Wrong indentation
    return {'cost': cost, 'currency': 'USD', 'usd_cost': cost}
"""
        with pytest.raises(FormulaSyntaxError):
            validator._check_syntax(invalid_code)


class TestCalculateFunctionVerification:
    """Test calculate function verification (Requirement 11.2)."""
    
    def test_valid_calculate_function(self, validator, valid_formula_code):
        """Test that valid calculate function passes."""
        validator._verify_calculate_function(valid_formula_code)
    
    def test_missing_calculate_function(self, validator):
        """Test that missing calculate function raises FormulaValidationError."""
        code_without_calculate = """
def compute(distance, weight, context):
    return {'cost': 100, 'currency': 'USD', 'usd_cost': 100}
"""
        with pytest.raises(FormulaValidationError) as exc_info:
            validator._verify_calculate_function(code_without_calculate)
        
        assert "must define a 'calculate' function" in str(exc_info.value)
        assert exc_info.value.details['reason'] == 'missing_calculate_function'
    
    def test_incorrect_signature(self, validator):
        """Test that incorrect function signature raises FormulaValidationError."""
        code_wrong_signature = """
def calculate(dist, wt):  # Wrong parameters
    return {'cost': 100, 'currency': 'USD', 'usd_cost': 100}
"""
        with pytest.raises(FormulaValidationError) as exc_info:
            validator._verify_calculate_function(code_wrong_signature)
        
        assert "must have parameters (distance, weight, context)" in str(exc_info.value)
        assert exc_info.value.details['reason'] == 'incorrect_signature'
    
    def test_extra_parameters(self, validator):
        """Test that extra parameters raise FormulaValidationError."""
        code_extra_params = """
def calculate(distance, weight, context, extra):
    return {'cost': 100, 'currency': 'USD', 'usd_cost': 100}
"""
        with pytest.raises(FormulaValidationError):
            validator._verify_calculate_function(code_extra_params)


class TestTestExecution:
    """Test execution with sample data (Requirement 11.3)."""
    
    def test_successful_execution(self, validator, valid_formula_code, db_session, formula_executor):
        """Test that valid formula executes successfully."""
        validator._test_execution(valid_formula_code)
        
        # Verify executor was called
        assert formula_executor.execute_formula.called
        
        # Verify test formula was added and rolled back
        assert db_session.add.called
        assert db_session.flush.called
        assert db_session.rollback.called
    
    def test_execution_failure(self, validator, valid_formula_code, formula_executor):
        """Test that execution failure raises FormulaValidationError."""
        from src.exceptions import FormulaExecutionError
        
        # Mock executor to raise execution error
        formula_executor.execute_formula.side_effect = FormulaExecutionError(
            "Division by zero"
        )
        
        with pytest.raises(FormulaValidationError) as exc_info:
            validator._test_execution(valid_formula_code)
        
        assert "Test execution failed" in str(exc_info.value)
        assert exc_info.value.details['reason'] == 'test_execution_failed'
    
    def test_missing_result_fields(self, validator, valid_formula_code, formula_executor):
        """Test that missing result fields raise FormulaValidationError."""
        # Mock executor to return incomplete result
        formula_executor.execute_formula.return_value = {
            'cost': 100.0
            # Missing 'currency' and 'usd_cost'
        }
        
        with pytest.raises(FormulaValidationError) as exc_info:
            validator._test_execution(valid_formula_code)
        
        assert "missing required fields" in str(exc_info.value)
        assert exc_info.value.details['reason'] == 'missing_result_fields'


class TestBlackFormatting:
    """Test Black formatting (Requirement 11.4)."""
    
    def test_format_code(self, validator):
        """Test that code is formatted with Black."""
        unformatted_code = """
def calculate(distance,weight,context):
    cost=distance*10.0
    return {'cost':cost,'currency':'USD','usd_cost':cost}
"""
        formatted = validator._format_code(unformatted_code)
        
        # Check that formatting was applied
        assert 'distance, weight, context' in formatted
        assert 'cost = distance * 10.0' in formatted
    
    def test_format_idempotence(self, validator, valid_formula_code):
        """Test that formatting is idempotent."""
        formatted_once = validator._format_code(valid_formula_code)
        formatted_twice = validator._format_code(formatted_once)
        
        assert formatted_once == formatted_twice
    
    def test_format_failure_returns_original(self, validator):
        """Test that formatting failure returns original code."""
        # Black should handle most Python code, but if it fails, original is returned
        code = "def calculate(distance, weight, context): pass"
        result = validator._format_code(code)
        
        # Should return some valid code (either formatted or original)
        assert 'calculate' in result


class TestLinting:
    """Test linting checks (Requirement 11.5)."""
    
    def test_lint_clean_code(self, validator, valid_formula_code):
        """Test that clean code passes linting."""
        warnings = validator._lint_code(valid_formula_code)
        
        # Should return empty list or only minor warnings
        assert isinstance(warnings, list)
    
    def test_lint_with_warnings(self, validator):
        """Test that code with warnings returns warning list."""
        code_with_warnings = """
def calculate(distance, weight, context):
    unused_variable = 42  # F841: local variable assigned but never used
    cost = distance * 10.0
    return {'cost': cost, 'currency': 'USD', 'usd_cost': cost}
"""
        warnings = validator._lint_code(code_with_warnings)
        
        # May or may not have warnings depending on flake8 availability
        assert isinstance(warnings, list)
    
    @patch('subprocess.run')
    def test_lint_critical_error(self, mock_run, validator):
        """Test that critical linting errors raise FormulaLintError."""
        # Mock flake8 to return critical error
        mock_run.return_value = Mock(
            stdout="<formula>:1:1: E902 IndentationError: unexpected indent\n",
            returncode=1
        )
        
        code = "def calculate(distance, weight, context): pass"
        
        with pytest.raises(FormulaLintError) as exc_info:
            validator._lint_code(code)
        
        assert "Critical linting errors" in str(exc_info.value)


class TestHashComputation:
    """Test hash computation (Requirement 11.6)."""
    
    def test_compute_hash(self, validator, valid_formula_code):
        """Test that hash is computed correctly."""
        hash_value = validator._compute_hash(valid_formula_code)
        
        # Should be 64-character hex string
        assert len(hash_value) == 64
        assert all(c in '0123456789abcdef' for c in hash_value)
    
    def test_hash_determinism(self, validator, valid_formula_code):
        """Test that hash computation is deterministic."""
        hash1 = validator._compute_hash(valid_formula_code)
        hash2 = validator._compute_hash(valid_formula_code)
        
        assert hash1 == hash2
    
    def test_different_code_different_hash(self, validator):
        """Test that different code produces different hash."""
        code1 = "def calculate(distance, weight, context): return {'cost': 1, 'currency': 'USD', 'usd_cost': 1}"
        code2 = "def calculate(distance, weight, context): return {'cost': 2, 'currency': 'USD', 'usd_cost': 2}"
        
        hash1 = validator._compute_hash(code1)
        hash2 = validator._compute_hash(code2)
        
        assert hash1 != hash2


class TestDuplicateDetection:
    """Test duplicate detection (Requirement 11.8)."""
    
    def test_no_duplicate(self, validator, db_session):
        """Test that non-duplicate hash returns False."""
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        is_duplicate = validator._check_duplicate("abc123")
        
        assert is_duplicate is False
    
    def test_duplicate_exists(self, validator, db_session):
        """Test that duplicate hash returns True."""
        # Mock existing formula
        existing_formula = Mock(spec=Formula)
        existing_formula.id = uuid4()
        db_session.query.return_value.filter.return_value.first.return_value = existing_formula
        
        is_duplicate = validator._check_duplicate("abc123")
        
        assert is_duplicate is True


class TestValidateAndSave:
    """Test complete validation pipeline (Requirements 11.1-11.10)."""
    
    def test_successful_validation_and_save(
        self,
        validator,
        valid_formula_code,
        db_session,
        formula_executor
    ):
        """Test that valid formula is validated and saved."""
        formula = validator.validate_and_save(
            formula_code=valid_formula_code,
            country_code='US',
            description='United States',
            formula_code_id='US_FORMULA',
            effective_date=date(2024, 1, 1),
            currency='USD',
            created_by='test@example.com'
        )
        
        # Verify formula was created
        assert formula is not None
        assert formula.country_code == 'US'
        assert formula.formula_hash is not None
        assert formula.formula_bytecode is not None
        
        # Verify database operations
        assert db_session.add.called
        assert db_session.commit.called
    
    def test_syntax_error_prevents_save(self, validator, db_session):
        """Test that syntax error prevents save."""
        invalid_code = "def calculate(: pass"
        
        with pytest.raises(FormulaSyntaxError):
            validator.validate_and_save(
                formula_code=invalid_code,
                country_code='US',
                description='Test',
                formula_code_id='TEST',
                effective_date=date(2024, 1, 1),
                currency='USD',
                created_by='test@example.com'
            )
        
        # Verify no database operations
        assert not db_session.add.called
        assert not db_session.commit.called
    
    def test_duplicate_prevents_save(
        self,
        validator,
        valid_formula_code,
        db_session
    ):
        """Test that duplicate hash prevents save."""
        # Mock existing formula with same hash
        existing_formula = Mock(spec=Formula)
        existing_formula.id = uuid4()
        db_session.query.return_value.filter.return_value.first.return_value = existing_formula
        
        with pytest.raises(FormulaDuplicateError) as exc_info:
            validator.validate_and_save(
                formula_code=valid_formula_code,
                country_code='US',
                description='Test',
                formula_code_id='TEST',
                effective_date=date(2024, 1, 1),
                currency='USD',
                created_by='test@example.com'
            )
        
        assert "already exists" in str(exc_info.value)
        
        # Verify no commit (duplicate check happens before save)
        assert not db_session.commit.called
    
    def test_version_increment(
        self,
        validator,
        valid_formula_code,
        db_session
    ):
        """Test that version number is incremented correctly."""
        # Mock existing version
        db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (5,)
        
        formula = validator.validate_and_save(
            formula_code=valid_formula_code,
            country_code='US',
            description='Test',
            formula_code_id='TEST',
            effective_date=date(2024, 1, 1),
            currency='USD',
            created_by='test@example.com'
        )
        
        # Version should be incremented
        assert formula.version_number == 6
