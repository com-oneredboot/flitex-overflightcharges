"""Formula Validator with validation pipeline.

This module provides the FormulaValidator class which validates Python formula
code before saving to the database. The validation pipeline includes syntax
checking, calculate function verification, test execution, Black formatting,
linting, hash computation, and duplicate detection.

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10
"""

import ast
import hashlib
import logging
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

import black
from sqlalchemy.orm import Session

from src.exceptions import (
    FormulaDuplicateError,
    FormulaLintError,
    FormulaSyntaxError,
    FormulaValidationError,
)
from src.formula_execution.formula_executor import FormulaExecutor
from src.models.formula import Formula

logger = logging.getLogger(__name__)


class FormulaValidator:
    """Validates formulas before saving to database.
    
    This class implements a comprehensive validation pipeline that ensures
    formula code is syntactically correct, properly formatted, and executable
    before being stored in the database.
    
    Validation Pipeline:
    1. Syntax checking (ast.parse)
    2. Calculate function verification
    3. Test execution with sample data
    4. Black formatting
    5. Linting (flake8)
    6. SHA256 hash computation
    7. Duplicate detection
    8. Database save
    
    Attributes:
        _db_session: SQLAlchemy database session
        _executor: FormulaExecutor for test execution
    """
    
    def __init__(
        self,
        db_session: Session,
        executor: FormulaExecutor
    ):
        """Initialize validator with dependencies.
        
        Args:
            db_session: SQLAlchemy session for database queries
            executor: FormulaExecutor for test execution
        
        Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8
        """
        self._db_session = db_session
        self._executor = executor
        
        logger.info("FormulaValidator initialized")
    
    def _check_syntax(self, code: str) -> None:
        """Check for Python syntax errors.
        
        Uses ast.parse to validate Python syntax. Raises FormulaSyntaxError
        if the code contains syntax errors.
        
        Args:
            code: Python code to validate
        
        Raises:
            FormulaSyntaxError: Code contains syntax errors
        
        Requirements: 11.1
        """
        try:
            ast.parse(code)
            logger.debug("Syntax check passed")
        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            logger.error(
                "Syntax validation failed",
                extra={
                    "error_type": "FormulaSyntaxError",
                    "line": e.lineno,
                    "offset": e.offset,
                    "syntax_error_msg": e.msg
                }
            )
            raise FormulaSyntaxError(
                error_msg,
                details={
                    "line": e.lineno,
                    "offset": e.offset,
                    "message": e.msg
                }
            )
    
    def _verify_calculate_function(self, code: str) -> None:
        """Verify calculate function exists with correct signature.
        
        Parses the code AST to check for a function named 'calculate'
        with the expected parameters (distance, weight, context).
        
        Args:
            code: Python code to validate
        
        Raises:
            FormulaValidationError: Missing calculate function or incorrect signature
        
        Requirements: 11.2
        """
        try:
            tree = ast.parse(code)
            
            # Find calculate function
            calculate_func = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == 'calculate':
                    calculate_func = node
                    break
            
            if calculate_func is None:
                error_msg = "Formula must define a 'calculate' function"
                logger.error(
                    "Calculate function verification failed",
                    extra={
                        "error_type": "FormulaValidationError",
                        "reason": "missing_calculate_function"
                    }
                )
                raise FormulaValidationError(
                    error_msg,
                    details={"reason": "missing_calculate_function"}
                )
            
            # Verify function signature (should have 3 parameters: distance, weight, context)
            args = calculate_func.args
            param_names = [arg.arg for arg in args.args]
            
            expected_params = ['distance', 'weight', 'context']
            if param_names != expected_params:
                error_msg = (
                    f"Calculate function must have parameters "
                    f"(distance, weight, context), got ({', '.join(param_names)})"
                )
                logger.error(
                    "Calculate function signature incorrect",
                    extra={
                        "error_type": "FormulaValidationError",
                        "reason": "incorrect_signature",
                        "expected": expected_params,
                        "actual": param_names
                    }
                )
                raise FormulaValidationError(
                    error_msg,
                    details={
                        "reason": "incorrect_signature",
                        "expected": expected_params,
                        "actual": param_names
                    }
                )
            
            logger.debug("Calculate function verification passed")
            
        except FormulaValidationError:
            raise
        except Exception as e:
            error_msg = f"Failed to verify calculate function: {str(e)}"
            logger.error(
                "Calculate function verification error",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            )
            raise FormulaValidationError(
                error_msg,
                details={
                    "reason": "verification_error",
                    "error": str(e)
                }
            )
    
    def _test_execution(self, code: str) -> None:
        """Execute formula with sample data to ensure it runs.
        
        Creates a temporary formula in the database and executes it with
        sample data to verify it runs without errors.
        
        Sample data:
        - distance: 1000.0 nautical miles
        - weight: 50.0 tonnes
        - context: All required fields with sample values
        
        Args:
            code: Python code to test
        
        Raises:
            FormulaValidationError: Test execution failed
        
        Requirements: 11.3
        """
        import uuid
        from src.exceptions import (
            FormulaExecutionError,
            FormulaSyntaxError,
            FormulaTimeoutError,
            SecurityViolationError
        )
        
        # Sample test data
        test_distance = 1000.0
        test_weight = 50.0
        test_context = {
            'firTag': 'TEST',
            'arrival': 'KJFK',
            'departure': 'EGLL',
            'isFirstFir': True,
            'isLastFir': False,
            'firName': 'Test FIR',
            'originCountry': 'GB',
            'destinationCountry': 'US'
        }
        
        # Create temporary formula for testing
        test_formula_id = uuid.uuid4()
        test_formula = Formula(
            id=test_formula_id,
            country_code='XX',  # Use 2-letter code for test
            description='Test formula for validation',
            formula_code='TEST_VALIDATION',
            formula_logic=code,
            effective_date=date.today(),
            currency='USD',
            version_number=1,
            is_active=False,
            created_by='validator'
        )
        
        try:
            # Add to session but don't commit
            self._db_session.add(test_formula)
            self._db_session.flush()
            
            # Execute formula with test data
            result = self._executor.execute_formula(
                test_formula_id,
                test_distance,
                test_weight,
                test_context
            )
            
            # Verify result has required fields
            required_fields = ['cost', 'currency', 'usd_cost']
            missing_fields = [f for f in required_fields if f not in result]
            if missing_fields:
                error_msg = f"Test execution result missing required fields: {missing_fields}"
                logger.error(
                    "Test execution validation failed",
                    extra={
                        "error_type": "FormulaValidationError",
                        "reason": "missing_result_fields",
                        "missing_fields": missing_fields
                    }
                )
                raise FormulaValidationError(
                    error_msg,
                    details={
                        "reason": "missing_result_fields",
                        "missing_fields": missing_fields
                    }
                )
            
            logger.debug(
                "Test execution passed",
                extra={
                    "cost": result.get('cost'),
                    "currency": result.get('currency')
                }
            )
            
        except (FormulaSyntaxError, FormulaExecutionError, FormulaTimeoutError, 
                SecurityViolationError) as e:
            error_msg = f"Test execution failed: {str(e)}"
            logger.error(
                "Test execution failed",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            )
            raise FormulaValidationError(
                error_msg,
                details={
                    "reason": "test_execution_failed",
                    "error_type": type(e).__name__,
                    "error": str(e)
                }
            )
        except FormulaValidationError:
            raise
        except Exception as e:
            error_msg = f"Test execution error: {str(e)}"
            logger.error(
                "Test execution error",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            )
            raise FormulaValidationError(
                error_msg,
                details={
                    "reason": "test_execution_error",
                    "error": str(e)
                }
            )
        finally:
            # Rollback to remove test formula
            self._db_session.rollback()
    
    def _format_code(self, code: str) -> str:
        """Format code using Black formatter.
        
        Applies Black formatting to ensure consistent code style.
        
        Args:
            code: Python code to format
        
        Returns:
            Formatted Python code
        
        Requirements: 11.4
        """
        try:
            formatted_code = black.format_str(code, mode=black.Mode())
            logger.debug("Code formatting completed")
            return formatted_code
        except Exception as e:
            # If Black formatting fails, log warning but continue with original code
            logger.warning(
                "Black formatting failed, using original code",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            )
            return code
    
    def _lint_code(self, code: str) -> list[str]:
        """Run linting checks and return warnings.
        
        Uses flake8 to check code quality. Returns list of warnings/errors.
        
        Args:
            code: Python code to lint
        
        Returns:
            List of linting warnings/errors
        
        Raises:
            FormulaLintError: Critical linting errors found
        
        Requirements: 11.5
        """
        warnings = []
        
        try:
            # Write code to temporary file for flake8
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                delete=False
            ) as temp_file:
                temp_file.write(code)
                temp_path = Path(temp_file.name)
            
            try:
                # Run flake8 with relaxed settings
                result = subprocess.run(
                    [
                        'flake8',
                        '--max-line-length=100',
                        '--ignore=E501,W503',  # Ignore line length and line break warnings
                        str(temp_path)
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.stdout:
                    warnings = result.stdout.strip().split('\n')
                    
                    # Filter out the temp file path from warnings
                    warnings = [
                        w.replace(str(temp_path), '<formula>')
                        for w in warnings if w.strip()
                    ]
                    
                    # Check for critical errors (E9xx, F8xx)
                    critical_errors = [
                        w for w in warnings
                        if any(code in w for code in ['E9', 'F8'])
                    ]
                    
                    if critical_errors:
                        error_msg = f"Critical linting errors: {'; '.join(critical_errors)}"
                        logger.error(
                            "Linting validation failed",
                            extra={
                                "error_type": "FormulaLintError",
                                "errors": critical_errors
                            }
                        )
                        raise FormulaLintError(
                            error_msg,
                            details={"errors": critical_errors}
                        )
                    
                    if warnings:
                        logger.debug(
                            "Linting warnings found",
                            extra={"warnings": warnings}
                        )
                else:
                    logger.debug("Linting passed with no warnings")
                
            finally:
                # Clean up temp file
                temp_path.unlink(missing_ok=True)
                
        except subprocess.TimeoutExpired:
            logger.warning("Flake8 linting timed out, skipping lint check")
        except FileNotFoundError:
            logger.warning("Flake8 not found, skipping lint check")
        except FormulaLintError:
            raise
        except Exception as e:
            logger.warning(
                "Linting check failed, skipping",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            )
        
        return warnings
    
    def _compute_hash(self, code: str) -> str:
        """Compute SHA256 hash of formatted code.
        
        Args:
            code: Python code to hash
        
        Returns:
            SHA256 hash as hexadecimal string
        
        Requirements: 11.6
        """
        hash_value = hashlib.sha256(code.encode('utf-8')).hexdigest()
        logger.debug(f"Computed hash: {hash_value[:16]}...")
        return hash_value
    
    def _check_duplicate(self, code_hash: str) -> bool:
        """Check if formula with same hash exists.
        
        Args:
            code_hash: SHA256 hash to check
        
        Returns:
            True if duplicate exists, False otherwise
        
        Requirements: 11.8
        """
        existing = self._db_session.query(Formula).filter(
            Formula.formula_hash == code_hash
        ).first()
        
        if existing:
            logger.warning(
                "Duplicate formula detected",
                extra={
                    "hash": code_hash[:16],
                    "existing_id": str(existing.id)
                }
            )
            return True
        
        return False
    
    def validate_and_save(
        self,
        formula_code: str,
        country_code: Optional[str],
        description: str,
        formula_code_id: str,
        effective_date: date,
        currency: str,
        created_by: str,
        version_number: Optional[int] = None
    ) -> Formula:
        """Validate formula and save to database.
        
        Runs the complete validation pipeline:
        1. Syntax checking
        2. Calculate function verification
        3. Test execution
        4. Black formatting
        5. Linting
        6. Hash computation
        7. Duplicate detection
        8. Database save
        
        Args:
            formula_code: Python code to validate
            country_code: ISO country code or None for regional
            description: Human-readable description
            formula_code_id: Formula code identifier
            effective_date: When formula becomes effective
            currency: ISO currency code
            created_by: User creating the formula
            version_number: Optional version number (auto-increments if None)
        
        Returns:
            Saved Formula model instance
        
        Raises:
            FormulaSyntaxError: Syntax errors in code
            FormulaValidationError: Missing calculate function or test failed
            FormulaDuplicateError: Formula with same hash already exists
            FormulaLintError: Linting checks failed
        
        Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10
        """
        logger.info(
            "Starting formula validation",
            extra={
                "country_code": country_code,
                "formula_code_id": formula_code_id,
                "created_by": created_by
            }
        )
        
        # Step 1: Check syntax
        self._check_syntax(formula_code)
        
        # Step 2: Verify calculate function
        self._verify_calculate_function(formula_code)
        
        # Step 3: Test execution
        self._test_execution(formula_code)
        
        # Step 4: Format with Black
        formatted_code = self._format_code(formula_code)
        
        # Step 5: Lint code
        lint_warnings = self._lint_code(formatted_code)
        
        # Step 6: Compute hash
        code_hash = self._compute_hash(formatted_code)
        
        # Step 7: Check for duplicates
        if self._check_duplicate(code_hash):
            error_msg = f"Formula with hash {code_hash[:16]}... already exists"
            raise FormulaDuplicateError(
                error_msg,
                details={"hash": code_hash}
            )
        
        # Step 8: Compile to bytecode
        from RestrictedPython import compile_restricted
        
        bytecode = compile_restricted(
            formatted_code,
            filename=f"<formula_{formula_code_id}>",
            mode='exec'
        )
        
        if bytecode is None:
            error_msg = "Formula compilation failed - restricted operation detected"
            logger.error(
                "Bytecode compilation failed",
                extra={"error_type": "FormulaValidationError"}
            )
            raise FormulaValidationError(
                error_msg,
                details={"reason": "compilation_failed"}
            )
        
        # Convert bytecode to bytes for storage
        import marshal
        bytecode_bytes = marshal.dumps(bytecode)
        
        # Step 9: Determine version number
        if version_number is None:
            max_version = self._db_session.query(Formula.version_number).filter(
                Formula.country_code == country_code
            ).order_by(Formula.version_number.desc()).first()
            
            version_number = (max_version[0] + 1) if max_version else 1
        
        # Step 10: Create and save formula
        formula = Formula(
            country_code=country_code,
            description=description,
            formula_code=formula_code_id,
            formula_logic=formatted_code,
            effective_date=effective_date,
            currency=currency,
            version_number=version_number,
            is_active=True,
            created_by=created_by,
            formula_hash=code_hash,
            formula_bytecode=bytecode_bytes
        )
        
        self._db_session.add(formula)
        self._db_session.commit()
        
        logger.info(
            "Formula validated and saved successfully",
            extra={
                "formula_id": str(formula.id),
                "country_code": country_code,
                "version": version_number,
                "hash": code_hash[:16],
                "lint_warnings": len(lint_warnings)
            }
        )
        
        return formula
