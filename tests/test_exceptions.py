"""Tests for custom exceptions module.

This module tests the exception hierarchy and ensures all exceptions
have the correct status codes and support optional details.
"""

import pytest
from hypothesis import given, strategies as st

from src.exceptions import (
    ServiceException,
    FIRNotFoundException,
    FormulaNotFoundException,
    DuplicateFIRException,
    ValidationException,
    InvalidSyntaxException,
    ParsingException,
    DatabaseException,
)


class TestServiceException:
    """Unit tests for ServiceException base class."""
    
    def test_default_initialization(self):
        """Test ServiceException with default parameters."""
        exc = ServiceException("Test error")
        assert exc.message == "Test error"
        assert exc.status_code == 500
        assert exc.details == {}
        assert str(exc) == "Test error"
    
    def test_custom_status_code(self):
        """Test ServiceException with custom status code."""
        exc = ServiceException("Test error", status_code=418)
        assert exc.status_code == 418
    
    def test_with_details(self):
        """Test ServiceException with details dictionary."""
        details = {"field": "value", "count": 42}
        exc = ServiceException("Test error", details=details)
        assert exc.details == details
    
    def test_with_all_parameters(self):
        """Test ServiceException with all parameters."""
        details = {"key": "value"}
        exc = ServiceException("Test error", status_code=400, details=details)
        assert exc.message == "Test error"
        assert exc.status_code == 400
        assert exc.details == details


class TestFIRNotFoundException:
    """Unit tests for FIRNotFoundException."""
    
    def test_default_initialization(self):
        """Test FIRNotFoundException with default message."""
        exc = FIRNotFoundException()
        assert exc.message == "FIR not found"
        assert exc.status_code == 404
        assert exc.details == {}
    
    def test_custom_message(self):
        """Test FIRNotFoundException with custom message."""
        exc = FIRNotFoundException("FIR KJFK not found")
        assert exc.message == "FIR KJFK not found"
        assert exc.status_code == 404
    
    def test_with_details(self):
        """Test FIRNotFoundException with details."""
        details = {"icao_code": "KJFK"}
        exc = FIRNotFoundException("FIR not found", details=details)
        assert exc.details == details
        assert exc.status_code == 404


class TestFormulaNotFoundException:
    """Unit tests for FormulaNotFoundException."""
    
    def test_default_initialization(self):
        """Test FormulaNotFoundException with default message."""
        exc = FormulaNotFoundException()
        assert exc.message == "Formula not found"
        assert exc.status_code == 404
        assert exc.details == {}
    
    def test_custom_message(self):
        """Test FormulaNotFoundException with custom message."""
        exc = FormulaNotFoundException("Formula for US not found")
        assert exc.message == "Formula for US not found"
        assert exc.status_code == 404
    
    def test_with_details(self):
        """Test FormulaNotFoundException with details."""
        details = {"country_code": "US"}
        exc = FormulaNotFoundException("Formula not found", details=details)
        assert exc.details == details


class TestDuplicateFIRException:
    """Unit tests for DuplicateFIRException."""
    
    def test_default_initialization(self):
        """Test DuplicateFIRException with default message."""
        exc = DuplicateFIRException()
        assert exc.message == "FIR already exists"
        assert exc.status_code == 409
        assert exc.details == {}
    
    def test_custom_message(self):
        """Test DuplicateFIRException with custom message."""
        exc = DuplicateFIRException("FIR KJFK already exists")
        assert exc.message == "FIR KJFK already exists"
        assert exc.status_code == 409
    
    def test_with_details(self):
        """Test DuplicateFIRException with details."""
        details = {"icao_code": "KJFK"}
        exc = DuplicateFIRException("FIR already exists", details=details)
        assert exc.details == details


class TestValidationException:
    """Unit tests for ValidationException."""
    
    def test_default_initialization(self):
        """Test ValidationException with default message."""
        exc = ValidationException()
        assert exc.message == "Validation failed"
        assert exc.status_code == 400
        assert exc.details == {}
    
    def test_custom_message(self):
        """Test ValidationException with custom message."""
        exc = ValidationException("Invalid ICAO code format")
        assert exc.message == "Invalid ICAO code format"
        assert exc.status_code == 400
    
    def test_with_details(self):
        """Test ValidationException with validation errors."""
        details = {
            "errors": [
                {"field": "icao_code", "message": "must be 4 characters"},
                {"field": "mtow_kg", "message": "must be positive"}
            ]
        }
        exc = ValidationException("Validation failed", details=details)
        assert exc.details == details


class TestInvalidSyntaxException:
    """Unit tests for InvalidSyntaxException."""
    
    def test_default_initialization(self):
        """Test InvalidSyntaxException with default message."""
        exc = InvalidSyntaxException()
        assert exc.message == "Invalid formula syntax"
        assert exc.status_code == 400
        assert exc.details == {}
    
    def test_custom_message(self):
        """Test InvalidSyntaxException with custom message."""
        exc = InvalidSyntaxException("Syntax error at line 5")
        assert exc.message == "Syntax error at line 5"
        assert exc.status_code == 400
    
    def test_with_details(self):
        """Test InvalidSyntaxException with syntax error details."""
        details = {"line": 5, "column": 10, "error": "unexpected token"}
        exc = InvalidSyntaxException("Invalid formula syntax", details=details)
        assert exc.details == details


class TestParsingException:
    """Unit tests for ParsingException."""
    
    def test_default_initialization(self):
        """Test ParsingException with default message."""
        exc = ParsingException()
        assert exc.message == "Route parsing failed"
        assert exc.status_code == 400
        assert exc.details == {}
    
    def test_custom_message(self):
        """Test ParsingException with custom message."""
        exc = ParsingException("Invalid route format")
        assert exc.message == "Invalid route format"
        assert exc.status_code == 400
    
    def test_with_details(self):
        """Test ParsingException with parsing error details."""
        details = {"route": "KJFK DCT INVALID", "position": 9}
        exc = ParsingException("Route parsing failed", details=details)
        assert exc.details == details


class TestDatabaseException:
    """Unit tests for DatabaseException."""
    
    def test_default_initialization(self):
        """Test DatabaseException with default message."""
        exc = DatabaseException()
        assert exc.message == "Database operation failed"
        assert exc.status_code == 503
        assert exc.details == {}
    
    def test_custom_message(self):
        """Test DatabaseException with custom message."""
        exc = DatabaseException("Connection timeout")
        assert exc.message == "Connection timeout"
        assert exc.status_code == 503
    
    def test_with_details(self):
        """Test DatabaseException with connection details."""
        details = {"host": "localhost", "port": 5432, "retry_count": 3}
        exc = DatabaseException("Database operation failed", details=details)
        assert exc.details == details


class TestExceptionInheritance:
    """Tests for exception inheritance hierarchy."""
    
    def test_all_exceptions_inherit_from_service_exception(self):
        """Test that all custom exceptions inherit from ServiceException."""
        exceptions = [
            FIRNotFoundException(),
            FormulaNotFoundException(),
            DuplicateFIRException(),
            ValidationException(),
            InvalidSyntaxException(),
            ParsingException(),
            DatabaseException(),
        ]
        
        for exc in exceptions:
            assert isinstance(exc, ServiceException)
            assert isinstance(exc, Exception)
    
    def test_all_exceptions_have_status_code(self):
        """Test that all exceptions have a status_code attribute."""
        exceptions = [
            (FIRNotFoundException(), 404),
            (FormulaNotFoundException(), 404),
            (DuplicateFIRException(), 409),
            (ValidationException(), 400),
            (InvalidSyntaxException(), 400),
            (ParsingException(), 400),
            (DatabaseException(), 503),
        ]
        
        for exc, expected_code in exceptions:
            assert hasattr(exc, 'status_code')
            assert exc.status_code == expected_code
    
    def test_all_exceptions_have_message_and_details(self):
        """Test that all exceptions have message and details attributes."""
        exceptions = [
            FIRNotFoundException(),
            FormulaNotFoundException(),
            DuplicateFIRException(),
            ValidationException(),
            InvalidSyntaxException(),
            ParsingException(),
            DatabaseException(),
        ]
        
        for exc in exceptions:
            assert hasattr(exc, 'message')
            assert hasattr(exc, 'details')
            assert isinstance(exc.message, str)
            assert isinstance(exc.details, dict)


class TestExceptionPropertyBased:
    """Property-based tests for exceptions."""
    
    @given(
        message=st.text(min_size=1, max_size=200),
        status_code=st.integers(min_value=400, max_value=599)
    )
    def test_service_exception_preserves_message_and_status(
        self, message, status_code
    ):
        """Property: ServiceException preserves message and status code."""
        exc = ServiceException(message, status_code=status_code)
        assert exc.message == message
        assert exc.status_code == status_code
        assert str(exc) == message
    
    @given(
        message=st.text(min_size=1, max_size=200),
        details=st.dictionaries(
            keys=st.text(min_size=1, max_size=50),
            values=st.one_of(
                st.text(max_size=100),
                st.integers(),
                st.booleans()
            ),
            max_size=10
        )
    )
    def test_exceptions_preserve_details(self, message, details):
        """Property: All exceptions preserve details dictionary."""
        exceptions = [
            FIRNotFoundException(message, details=details),
            FormulaNotFoundException(message, details=details),
            DuplicateFIRException(message, details=details),
            ValidationException(message, details=details),
            InvalidSyntaxException(message, details=details),
            ParsingException(message, details=details),
            DatabaseException(message, details=details),
        ]
        
        for exc in exceptions:
            assert exc.details == details
            assert exc.message == message
    
    @given(message=st.text(min_size=1, max_size=200))
    def test_not_found_exceptions_always_404(self, message):
        """Property: Not found exceptions always have status code 404."""
        fir_exc = FIRNotFoundException(message)
        formula_exc = FormulaNotFoundException(message)
        
        assert fir_exc.status_code == 404
        assert formula_exc.status_code == 404
    
    @given(message=st.text(min_size=1, max_size=200))
    def test_validation_exceptions_always_400(self, message):
        """Property: Validation-related exceptions always have status code 400."""
        validation_exc = ValidationException(message)
        syntax_exc = InvalidSyntaxException(message)
        parsing_exc = ParsingException(message)
        
        assert validation_exc.status_code == 400
        assert syntax_exc.status_code == 400
        assert parsing_exc.status_code == 400
    
    @given(message=st.text(min_size=1, max_size=200))
    def test_duplicate_exception_always_409(self, message):
        """Property: Duplicate exception always has status code 409."""
        exc = DuplicateFIRException(message)
        assert exc.status_code == 409
    
    @given(message=st.text(min_size=1, max_size=200))
    def test_database_exception_always_503(self, message):
        """Property: Database exception always has status code 503."""
        exc = DatabaseException(message)
        assert exc.status_code == 503
