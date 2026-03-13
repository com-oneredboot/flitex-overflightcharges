"""Formula Executor with RestrictedPython sandbox.

This module provides the FormulaExecutor class which executes Python formula
code in a sandboxed environment using RestrictedPython. The executor blocks
dangerous operations (imports, file system access, eval, exec) while allowing
formulas to access pre-loaded constants and utilities.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

import logging
import signal
from typing import Any, Optional
from uuid import UUID

from RestrictedPython import compile_restricted
from RestrictedPython.Guards import (
    safe_builtins, 
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    safer_getattr,
    safe_globals
)

import operator
from sqlalchemy.orm import Session

from src.formula_execution.constants_provider import ConstantsProvider
from src.formula_execution.eurocontrol_loader import EuroControlRateLoader
from src.formula_execution.formula_cache import FormulaCache

logger = logging.getLogger(__name__)


def _inplacevar(op, x, y):
    """Safe implementation of in-place operations for RestrictedPython.
    
    Handles augmented assignment operators like +=, -=, *=, etc.
    RestrictedPython passes the operator name as a string.
    """
    ops = {
        '+=': operator.add,
        '-=': operator.sub,
        '*=': operator.mul,
        '/=': operator.truediv,
        '//=': operator.floordiv,
        '%=': operator.mod,
        '**=': operator.pow,
        '&=': operator.and_,
        '|=': operator.or_,
        '^=': operator.xor,
        '>>=': operator.rshift,
        '<<=': operator.lshift,
    }
    if op in ops:
        return ops[op](x, y)
    # Fallback: if op is already a callable (shouldn't happen but be safe)
    if callable(op):
        return op(x, y)
    raise ValueError(f"Unsupported in-place operator: {op}")


class FormulaExecutor:
    """Executes formulas in a restricted Python sandbox.
    
    This class provides secure formula execution using RestrictedPython to
    create a sandbox that blocks dangerous operations while allowing formulas
    to access pre-loaded constants and utilities.
    
    The sandbox blocks:
    - All import statements
    - File system access (open, file operations)
    - Database access from within formula code
    - Dangerous built-ins (eval, exec, compile, __import__)
    - External library calls
    
    The sandbox allows:
    - Math functions (sqrt, pow, abs, ceil, floor, round)
    - Safe built-ins (min, max, len, range, enumerate, zip, map, filter, sum)
    - Pre-loaded constants (currencies, countries, FIRs, aerodromes)
    - Utility functions (convert_nm_to_km)
    - EuroControl rates data
    
    Attributes:
        _db_session: SQLAlchemy database session
        _cache: Redis cache for bytecode and results
        _constants_provider: Provider for constants and utilities
        _rate_loader: Loader for EuroControl rates
        _timeout_seconds: Execution timeout in seconds
        _safe_globals: Safe global namespace for formula execution
    """
    
    # Safe built-ins whitelist (Requirements 2.6)
    SAFE_BUILTINS = {
        'abs': abs,
        'round': round,
        'min': min,
        'max': max,
        'len': len,
        'range': range,
        'enumerate': enumerate,
        'zip': zip,
        'map': map,
        'filter': filter,
        'sum': sum,
        'next': next,
        'True': True,
        'False': False,
        'None': None,
        'bool': bool,
        'int': int,
        'float': float,
        'str': str,
        'list': list,
        'dict': dict,
        'tuple': tuple,
        'set': set,
        '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
        '_unpack_sequence_': guarded_unpack_sequence,
        '_getiter_': iter,
        '_getattr_': safer_getattr,
        '_getitem_': lambda obj, key: obj[key],
        '_inplacevar_': _inplacevar,
    }
    
    # Blocked built-ins (Requirements 2.6)
    BLOCKED_BUILTINS = {
        'eval', 'exec', 'compile', '__import__',
        'open', 'input', 'file', 'execfile',
        'reload', 'vars', 'dir', 'globals', 'locals',
        '__builtins__'
    }
    
    def __init__(
        self,
        db_session: Session,
        cache: FormulaCache,
        constants_provider: ConstantsProvider,
        rate_loader: EuroControlRateLoader,
        timeout_seconds: float = 1.0
    ):
        """Initialize executor with dependencies.
        
        Args:
            db_session: SQLAlchemy session for database queries
            cache: Redis cache for bytecode and results
            constants_provider: Provider for constants and utilities
            rate_loader: Loader for EuroControl rates
            timeout_seconds: Execution timeout in seconds (default: 1.0)
        
        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
        """
        self._db_session = db_session
        self._cache = cache
        self._constants_provider = constants_provider
        self._rate_loader = rate_loader
        self._timeout_seconds = timeout_seconds
        
        # Build safe globals namespace
        self._safe_globals = self._build_safe_globals()
        
        logger.info(
            "FormulaExecutor initialized",
            extra={
                "timeout_seconds": timeout_seconds,
                "cache_enabled": cache._enabled if cache else False
            }
        )
    
    def _build_safe_globals(self) -> dict[str, Any]:
        """Build safe global namespace for formula execution.
        
        Combines safe built-ins with constants and utilities from the
        ConstantsProvider and EuroControl rates from the RateLoader.
        
        Returns:
            Dictionary containing safe globals for formula execution
        
        Requirements: 2.6, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.8, 10.3
        """
        # Start with safe built-ins
        safe_globals = self.SAFE_BUILTINS.copy()
        
        # Add constants and utilities from ConstantsProvider
        execution_context = self._constants_provider.get_execution_context()
        safe_globals.update(execution_context)
        
        # Add EuroControl rates
        safe_globals['eurocontrol_rates'] = self._rate_loader.get_rates()
        
        # Ensure blocked built-ins are not present
        for blocked in self.BLOCKED_BUILTINS:
            safe_globals.pop(blocked, None)
        
        return safe_globals
    
    def _timeout_handler(self, signum: int, frame: Any) -> None:
        """Signal handler for execution timeout.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        
        Raises:
            TimeoutError: Always raised when timeout occurs
        
        Requirements: 2.5
        """
        raise TimeoutError("Formula execution exceeded timeout")
    
    def _setup_timeout(self) -> None:
        """Set up execution timeout using signal.alarm.
        
        Configures SIGALRM signal handler and sets alarm for timeout.
        Only works on Unix-like systems.
        
        Requirements: 2.5
        """
        # Set up signal handler for timeout
        signal.signal(signal.SIGALRM, self._timeout_handler)
        # Set alarm for timeout (converts float to int, rounds up)
        signal.alarm(int(self._timeout_seconds + 0.5))
    
    def _cancel_timeout(self) -> None:
        """Cancel execution timeout.
        
        Disables the alarm to prevent timeout after execution completes.
        
        Requirements: 2.5
        """
        signal.alarm(0)
    
    def execute_formula(
        self,
        formula_id: UUID,
        distance: float,
        weight: float,
        context: dict
    ) -> dict:
        """Execute a formula with given parameters.
        
        This method loads a formula from the database, compiles it using
        RestrictedPython (with bytecode caching), and executes it in a
        sandboxed environment with pre-loaded constants and utilities.
        
        Args:
            formula_id: UUID of formula to execute
            distance: Distance in nautical miles
            weight: Weight in tonnes
            context: Dictionary with firTag, arrival, departure, isFirstFir,
                    isLastFir, firName, originCountry, destinationCountry
        
        Returns:
            Dictionary with cost, currency, usd_cost, and optional euroCost
        
        Raises:
            FormulaNotFoundError: Formula doesn't exist
            FormulaSyntaxError: Formula has syntax errors
            FormulaExecutionError: Formula raised exception during execution
            FormulaTimeoutError: Formula exceeded timeout threshold
            SecurityViolationError: Formula attempted restricted operation
        
        Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.2, 8.3, 9.1, 9.2, 9.3, 9.4, 9.5
        """
        import hashlib
        import json
        import traceback
        from src.models.formula import Formula
        from src.exceptions import (
            FormulaNotFoundError,
            FormulaSyntaxError,
            FormulaExecutionError,
            FormulaTimeoutError,
            SecurityViolationError
        )
        
        # Compute params hash for result caching
        params_str = f"{distance}:{weight}:{json.dumps(context, sort_keys=True)}"
        params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:16]
        
        # Check result cache first (if cache is available)
        cached_result = None
        if self._cache:
            cached_result = self._cache.get_result(formula_id, params_hash)
        
        if cached_result is not None:
            logger.debug(
                "Result cache hit",
                extra={
                    "formula_id": str(formula_id),
                    "params_hash": params_hash
                }
            )
            return cached_result
        
        # Load formula from database
        try:
            formula = self._db_session.query(Formula).filter(
                Formula.id == formula_id
            ).first()
            
            if formula is None:
                error_msg = f"Formula with id {formula_id} not found"
                logger.error(
                    "Formula not found",
                    extra={
                        "formula_id": str(formula_id),
                        "error_type": "FormulaNotFoundError"
                    }
                )
                raise FormulaNotFoundError(
                    error_msg,
                    details={"formula_id": str(formula_id)}
                )
        except FormulaNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "Database error loading formula",
                extra={
                    "formula_id": str(formula_id),
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            )
            raise FormulaExecutionError(
                f"Failed to load formula: {str(e)}",
                details={
                    "formula_id": str(formula_id),
                    "error_type": type(e).__name__
                }
            )
        
        # Check bytecode cache (if cache is available)
        cached_bytecode = None
        if self._cache:
            cached_bytecode = self._cache.get_bytecode(formula_id, formula.version_number)
        
        if cached_bytecode is not None:
            # Use cached bytecode
            logger.debug(
                "Bytecode cache hit",
                extra={
                    "formula_id": str(formula_id),
                    "version": formula.version_number
                }
            )
            bytecode = cached_bytecode
        else:
            # Compile formula code with RestrictedPython
            logger.debug(
                "Compiling formula",
                extra={
                    "formula_id": str(formula_id),
                    "version": formula.version_number
                }
            )
            
            try:
                bytecode = compile_restricted(
                    formula.formula_logic,
                    filename=f"<formula_{formula_id}>",
                    mode='exec'
                )
                
                # Check for compilation errors (RestrictedPython returns None on error)
                if bytecode is None:
                    error_msg = "Formula compilation failed - restricted operation detected"
                    logger.error(
                        "Security violation during compilation",
                        extra={
                            "formula_id": str(formula_id),
                            "error_type": "SecurityViolationError"
                        }
                    )
                    raise SecurityViolationError(
                        error_msg,
                        details={
                            "formula_id": str(formula_id),
                            "operation": "compilation"
                        }
                    )
                
                # Store compiled bytecode in cache (if cache is available)
                if self._cache:
                    self._cache.store_bytecode(
                        formula_id,
                        formula.version_number,
                    bytecode
                )
                
            except SecurityViolationError:
                raise
            except SyntaxError as e:
                error_msg = f"Formula has syntax errors: {str(e)}"
                logger.error(
                    "Formula syntax error",
                    extra={
                        "formula_id": str(formula_id),
                        "error_type": "FormulaSyntaxError",
                        "error_message": str(e),
                        "line": getattr(e, 'lineno', None),
                        "offset": getattr(e, 'offset', None)
                    }
                )
                raise FormulaSyntaxError(
                    error_msg,
                    details={
                        "formula_id": str(formula_id),
                        "error": str(e),
                        "line": getattr(e, 'lineno', None)
                    }
                )
            except Exception as e:
                logger.error(
                    "Unexpected compilation error",
                    extra={
                        "formula_id": str(formula_id),
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
                raise FormulaExecutionError(
                    f"Formula compilation failed: {str(e)}",
                    details={
                        "formula_id": str(formula_id),
                        "error_type": type(e).__name__
                    }
                )
        
        # Build execution context
        exec_globals = self._safe_globals.copy()
        # Explicitly set __builtins__ to prevent access to real builtins
        exec_globals['__builtins__'] = {}
        exec_locals = {}
        
        # Execute formula with timeout
        try:
            self._setup_timeout()
            
            try:
                # Execute the compiled bytecode
                exec(bytecode, exec_globals, exec_locals)
                
                # Get the calculate function
                if 'calculate' not in exec_locals:
                    error_msg = "Formula must define a 'calculate' function"
                    logger.error(
                        "Missing calculate function",
                        extra={
                            "formula_id": str(formula_id),
                            "error_type": "FormulaExecutionError"
                        }
                    )
                    raise FormulaExecutionError(
                        error_msg,
                        details={"formula_id": str(formula_id)}
                    )
                
                calculate_func = exec_locals['calculate']
                
                # Call the calculate function with parameters
                result = calculate_func(distance, weight, context)
                
                # Validate result has required fields
                if not isinstance(result, dict):
                    error_msg = "Formula must return a dictionary"
                    logger.error(
                        "Invalid formula return type",
                        extra={
                            "formula_id": str(formula_id),
                            "error_type": "FormulaExecutionError",
                            "return_type": type(result).__name__
                        }
                    )
                    raise FormulaExecutionError(
                        error_msg,
                        details={
                            "formula_id": str(formula_id),
                            "return_type": type(result).__name__
                        }
                    )
                
                required_fields = ['cost', 'currency', 'usd_cost']
                missing_fields = [f for f in required_fields if f not in result]
                if missing_fields:
                    error_msg = f"Formula result missing required fields: {missing_fields}"
                    logger.error(
                        "Missing required fields in result",
                        extra={
                            "formula_id": str(formula_id),
                            "error_type": "FormulaExecutionError",
                            "missing_fields": missing_fields
                        }
                    )
                    raise FormulaExecutionError(
                        error_msg,
                        details={
                            "formula_id": str(formula_id),
                            "missing_fields": missing_fields
                        }
                    )
                
                # Store result in cache (if cache is available)
                if self._cache:
                    self._cache.store_result(formula_id, params_hash, result)
                
                logger.info(
                    "Formula executed successfully",
                    extra={
                        "formula_id": str(formula_id),
                        "distance": distance,
                        "weight": weight,
                        "cost": result.get('cost'),
                        "currency": result.get('currency')
                    }
                )
                
                return result
                
            finally:
                self._cancel_timeout()
                
        except TimeoutError as e:
            error_msg = f"Formula execution exceeded timeout of {self._timeout_seconds}s"
            logger.error(
                "Formula execution timeout",
                extra={
                    "formula_id": str(formula_id),
                    "error_type": "FormulaTimeoutError",
                    "timeout_seconds": self._timeout_seconds,
                    "distance": distance,
                    "weight": weight,
                    "context": context
                }
            )
            raise FormulaTimeoutError(
                error_msg,
                details={
                    "formula_id": str(formula_id),
                    "timeout_seconds": self._timeout_seconds
                }
            )
        except ImportError as e:
            # ImportError indicates attempted import (security violation)
            error_msg = f"Security violation: attempted import operation"
            logger.error(
                "Security violation - import attempted",
                extra={
                    "formula_id": str(formula_id),
                    "error_type": "SecurityViolationError",
                    "error_message": str(e)
                }
            )
            raise SecurityViolationError(
                error_msg,
                details={
                    "formula_id": str(formula_id),
                    "operation": "import",
                    "error": str(e)
                }
            )
        except (FormulaNotFoundError, FormulaSyntaxError, FormulaExecutionError, 
                FormulaTimeoutError, SecurityViolationError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # Catch any other unexpected exceptions
            error_msg = f"Formula execution failed: {str(e)}"
            logger.error(
                "Formula execution failed",
                extra={
                    "formula_id": str(formula_id),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "distance": distance,
                    "weight": weight,
                    "context": context,
                    "traceback": traceback.format_exc()
                }
            )
            raise FormulaExecutionError(
                error_msg,
                details={
                    "formula_id": str(formula_id),
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            )
    
    def execute_batch(
        self,
        executions: list[dict]
    ) -> list[dict]:
        """Execute multiple formulas in a single request.
        
        This method processes a batch of formula execution requests,
        executing each formula in order. If one formula fails, processing
        continues with the remaining formulas.
        
        Args:
            executions: List of dicts with formula_id, distance, weight, context
        
        Returns:
            List of results or errors for each request in the same order
        
        Requirements: 5.5, 9.5
        """
        from src.exceptions import (
            FormulaNotFoundError,
            FormulaSyntaxError,
            FormulaExecutionError,
            FormulaTimeoutError,
            SecurityViolationError
        )
        
        results = []
        
        for i, execution in enumerate(executions):
            try:
                formula_id = execution['formula_id']
                distance = execution['distance']
                weight = execution['weight']
                context = execution['context']
                
                result = self.execute_formula(formula_id, distance, weight, context)
                
                results.append({
                    'success': True,
                    'result': result,
                    'formula_id': str(formula_id)
                })
                
            except (FormulaNotFoundError, FormulaSyntaxError, FormulaExecutionError,
                    FormulaTimeoutError, SecurityViolationError) as e:
                logger.warning(
                    f"Batch execution failed for request {i}",
                    extra={
                        "index": i,
                        "formula_id": str(execution.get('formula_id')),
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "status_code": getattr(e, 'status_code', 500)
                    }
                )
                
                results.append({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'formula_id': str(execution.get('formula_id')),
                    'status_code': getattr(e, 'status_code', 500)
                })
            except Exception as e:
                logger.warning(
                    f"Batch execution failed for request {i} with unexpected error",
                    extra={
                        "index": i,
                        "formula_id": str(execution.get('formula_id')),
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
                
                results.append({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'formula_id': str(execution.get('formula_id')),
                    'status_code': 500
                })
        
        logger.info(
            "Batch execution completed",
            extra={
                "total_requests": len(executions),
                "successful": sum(1 for r in results if r['success']),
                "failed": sum(1 for r in results if not r['success'])
            }
        )
        
        return results
    
    def invalidate_cache(self, formula_id: UUID) -> None:
        """Invalidate cached bytecode and results for a formula.
        
        This method removes all cached data (bytecode and execution results)
        for the specified formula. It should be called when a formula is
        updated or deleted.
        
        Args:
            formula_id: UUID of formula to invalidate
        
        Requirements: 5.2
        """
        if self._cache:
            self._cache.invalidate_formula(formula_id)
        
        logger.info(
            "Formula cache invalidated",
            extra={"formula_id": str(formula_id)}
        )

