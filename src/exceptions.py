"""Custom exceptions for the flitex-overflightcharges service.

This module defines the exception hierarchy for service-specific errors,
following the pattern from flights-flown-ingestion service.
"""

from typing import Any, Dict, Optional


class ServiceException(Exception):
    """Base exception for service-specific errors.
    
    All custom exceptions inherit from this base class and include
    a status_code and optional details dictionary.
    """
    
    status_code: int = 500
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize the service exception.
        
        Args:
            message: Human-readable error message
            status_code: HTTP status code (defaults to class-level status_code)
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}


class FIRNotFoundException(ServiceException):
    """Raised when no active FIR exists for a given ICAO code or target version.
    
    This exception is raised when attempting to retrieve, update, soft-delete,
    or rollback a FIR record that does not exist in the database, or when a
    target version number does not exist for a given ICAO code during rollback.
    
    Requirements: 5.7, 5.8, 7.7
    """
    
    status_code = 404
    
    def __init__(
        self,
        message: str = "FIR not found",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


class FormulaNotFoundException(ServiceException):
    """Raised when formula not found for country.
    
    This exception is raised when attempting to retrieve, update, or delete
    a formula that does not exist for the specified country code.
    """
    
    status_code = 404
    
    def __init__(
        self,
        message: str = "Formula not found",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


class DuplicateFIRException(ServiceException):
    """Raised when a database integrity constraint is violated for FIR records.
    
    This exception is raised when a database integrity constraint is violated,
    such as attempting to create a duplicate active FIR for the same ICAO code
    (violating the partial unique index on active FIRs).
    
    Requirements: 5.7, 5.8, 7.8
    """
    
    status_code = 409
    
    def __init__(
        self,
        message: str = "FIR already exists",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


class ValidationException(ServiceException):
    """Raised when input validation fails.
    
    This exception is raised when request data fails validation checks
    beyond what Pydantic handles automatically.
    """
    
    status_code = 400
    
    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


class InvalidSyntaxException(ServiceException):
    """Raised when formula syntax is invalid.
    
    This exception is raised when formula_logic contains invalid Python syntax
    that cannot be parsed or executed.
    """
    
    status_code = 400
    
    def __init__(
        self,
        message: str = "Invalid formula syntax",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


class ParsingException(ServiceException):
    """Raised when route parsing fails.
    
    This exception is raised when an ICAO route string cannot be parsed
    due to invalid format or unrecognized waypoints.
    """
    
    status_code = 400
    
    def __init__(
        self,
        message: str = "Route parsing failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


class DatabaseException(ServiceException):
    """Raised when database operations fail.
    
    This exception is raised when database connectivity issues occur
    or database operations fail after retry attempts.
    """
    
    status_code = 503
    
    def __init__(
        self,
        message: str = "Database operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


# Formula Execution Exceptions (Requirements 9.1, 9.2, 9.3, 9.4)

class FormulaNotFoundError(ServiceException):
    """Raised when formula doesn't exist in database.
    
    This exception is raised when attempting to execute a formula
    that does not exist for the specified formula ID.
    
    Requirements: 9.1
    """
    
    status_code = 404
    
    def __init__(
        self,
        message: str = "Formula not found",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


class FormulaSyntaxError(ServiceException):
    """Raised when formula contains Python syntax errors.
    
    This exception is raised when formula code cannot be compiled
    due to invalid Python syntax.
    
    Requirements: 9.1
    """
    
    status_code = 400
    
    def __init__(
        self,
        message: str = "Formula has syntax errors",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


class FormulaExecutionError(ServiceException):
    """Raised when formula raises exception during execution.
    
    This exception is raised when a formula executes but raises
    an exception during calculation.
    
    Requirements: 9.2
    """
    
    status_code = 500
    
    def __init__(
        self,
        message: str = "Formula execution failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


class FormulaTimeoutError(ServiceException):
    """Raised when formula execution exceeds timeout threshold.
    
    This exception is raised when a formula takes longer than
    the configured timeout to execute.
    
    Requirements: 9.4
    """
    
    status_code = 500
    
    def __init__(
        self,
        message: str = "Formula execution timeout",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


class SecurityViolationError(ServiceException):
    """Raised when formula attempts restricted operation.
    
    This exception is raised when a formula attempts to use
    dangerous operations like imports, file access, or eval.
    
    Requirements: 9.3
    """
    
    status_code = 500
    
    def __init__(
        self,
        message: str = "Security violation detected",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


# Formula Validation Exceptions (Requirements 11.9)

class FormulaValidationError(ServiceException):
    """Raised when formula validation fails.
    
    This exception is raised when a formula fails validation checks
    such as missing calculate function or test execution failure.
    
    Requirements: 11.9
    """
    
    status_code = 400
    
    def __init__(
        self,
        message: str = "Formula validation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


class FormulaDuplicateError(ServiceException):
    """Raised when formula with identical hash already exists.
    
    This exception is raised when attempting to save a formula
    that has the same SHA256 hash as an existing formula.
    
    Requirements: 11.8, 11.9
    """
    
    status_code = 400
    
    def __init__(
        self,
        message: str = "Duplicate formula detected",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)


class FormulaLintError(ServiceException):
    """Raised when formula fails linting checks.
    
    This exception is raised when a formula fails code quality
    checks performed by the linter.
    
    Requirements: 11.5, 11.9
    """
    
    status_code = 400
    
    def __init__(
        self,
        message: str = "Formula linting failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=self.status_code, details=details)
