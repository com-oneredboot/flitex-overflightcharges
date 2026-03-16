"""FastAPI application for flitex-overflightcharges microservice.

This module creates and configures the FastAPI application with:
- Environment variable configuration and validation
- CORS middleware
- Global exception handling
- Database schema version verification
- Structured JSON logging
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.logging_config import configure_logging
from src.database import get_db, engine
from src.exceptions import ServiceException
from src.routes import fir_routes, flown_search_routes, formula_routes, freshness_routes, invoice_search_routes, route_cost_routes, monitoring_routes, reference_routes, route_validation_routes, summary_review_routes

# Configure structured logging
configure_logging()
logger = logging.getLogger(__name__)


def validate_environment_variables() -> dict[str, str]:
    """Validate and load required environment variables.
    
    Validates that all required environment variables are present and logs
    all configuration values except sensitive credentials.
    
    Returns:
        Dictionary of configuration values
    
    Raises:
        SystemExit: If required environment variables are missing
    """
    required_vars = ["DATABASE_URL", "CORS_ORIGINS", "LOG_LEVEL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(
            f"Missing required environment variables: {', '.join(missing_vars)}",
            extra={"missing_variables": missing_vars}
        )
        sys.exit(1)
    
    config = {
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "CORS_ORIGINS": os.getenv("CORS_ORIGINS"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL"),
        "PORT": os.getenv("PORT", "8000"),
        "WORKERS": os.getenv("WORKERS", "4"),
    }
    
    # Log all configuration values except DATABASE_URL
    safe_config = {k: v for k, v in config.items() if k != "DATABASE_URL"}
    logger.info(
        "Configuration loaded successfully",
        extra={"configuration": safe_config}
    )
    
    return config


def verify_database_schema() -> None:
    """Verify database schema version matches latest migration.
    
    Checks that the database schema is up-to-date by querying the
    alembic_version_overflightcharges table.
    
    Raises:
        SystemExit: If schema verification fails or database is not accessible
    """
    try:
        # Get a database session
        db_gen = get_db()
        db = next(db_gen)
        
        try:
            # Query the alembic version table
            result = db.execute(
                text("SELECT version_num FROM alembic_version_overflightcharges")
            )
            version = result.scalar()
            
            if version:
                logger.info(
                    f"Database schema version verified: {version}",
                    extra={"schema_version": version}
                )
            else:
                logger.error("No database schema version found. Run migrations first.")
                sys.exit(1)
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            f"Database schema verification failed: {str(e)}",
            extra={"error": str(e)}
        )
        sys.exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.
    
    Handles startup and shutdown events for the FastAPI application.
    On startup: validates environment variables, verifies database schema,
    and initializes formula execution components.
    
    Args:
        app: FastAPI application instance
    
    Yields:
        None
    """
    # Startup
    logger.info("Starting flitex-overflightcharges service")
    
    # Validate environment variables
    config = validate_environment_variables()
    
    # Verify database schema version
    verify_database_schema()
    
    # Initialize formula execution components (Task 12.1)
    try:
        from src.formula_execution.redis_config import RedisConfig
        from src.formula_execution.constants_provider import ConstantsProvider
        from src.formula_execution.eurocontrol_loader import EuroControlRateLoader
        from src.formula_execution.formula_cache import FormulaCache
        from src.formula_execution.formula_executor import FormulaExecutor
        from src.formula_execution.formula_validator import FormulaValidator
        
        logger.info("Initializing formula execution components")
        
        # Initialize Redis client
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                RedisConfig.initialize(redis_url)
                redis_client = RedisConfig.get_client()
                logger.info("Redis client initialized successfully")
            except Exception as e:
                logger.warning(
                    f"Redis initialization failed, caching will be disabled: {str(e)}",
                    extra={"error": str(e)}
                )
                redis_client = None
        else:
            logger.warning("REDIS_URL not configured, caching will be disabled")
            redis_client = None
        
        # Initialize ConstantsProvider and load constants
        constants_provider = ConstantsProvider()
        context = constants_provider.get_execution_context()
        constants_count = len(context.get("CURRENCY_CONSTANTS", {})) + \
                         len(context.get("COUNTRY_NAME_CONSTANTS", {})) + \
                         len(context.get("FIR_NAMES_PER_COUNTRY", {})) + \
                         len(context.get("CANADA_TSC_AERODROMES", []))
        logger.info(
            f"Constants loaded successfully",
            extra={
                "currencies": len(context.get("CURRENCY_CONSTANTS", {})),
                "countries": len(context.get("COUNTRY_NAME_CONSTANTS", {})),
                "fir_names": len(context.get("FIR_NAMES_PER_COUNTRY", {})),
                "canada_aerodromes": len(context.get("CANADA_TSC_AERODROMES", []))
            }
        )
        
        # Initialize EuroControlRateLoader and load rates
        db_gen = get_db()
        db = next(db_gen)
        try:
            rate_loader = EuroControlRateLoader(db)
            rates = rate_loader.load_rates()
            rates_count = sum(len(country_rates) for country_rates in rates.values())
            logger.info(
                f"EuroControl rates loaded successfully",
                extra={
                    "countries": len(rates),
                    "total_rates": rates_count
                }
            )
        finally:
            db.close()
        
        # Initialize FormulaCache
        cache = FormulaCache(redis_client)
        logger.info("FormulaCache initialized")
        
        # Initialize FormulaExecutor with all dependencies
        # Note: FormulaExecutor needs a db_session per request, so we store the factory
        app.state.constants_provider = constants_provider
        app.state.rate_loader = rate_loader
        app.state.cache = cache
        app.state.redis_client = redis_client
        
        logger.info(
            "Formula execution system startup complete",
            extra={
                "constants_loaded": constants_count,
                "eurocontrol_rates_loaded": rates_count,
                "redis_enabled": redis_client is not None
            }
        )
        
    except Exception as e:
        logger.error(
            f"Failed to initialize formula execution components: {str(e)}",
            extra={"error": str(e)},
            exc_info=True
        )
        # Don't fail startup if formula components fail to initialize
        # This allows the service to start even if Redis or other components are unavailable
        logger.warning("Service starting with formula execution components disabled")
    
    logger.info("Service startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down flitex-overflightcharges service")
    
    # Close Redis connection
    try:
        from src.formula_execution.redis_config import RedisConfig
        RedisConfig.close()
        logger.info("Redis connection closed")
    except Exception as e:
        logger.warning(f"Error closing Redis connection: {str(e)}")


# Create FastAPI application
app = FastAPI(
    title="flitex-overflightcharges",
    description="Overflight charges calculation microservice",
    version="1.0.0",
    lifespan=lifespan
)


# Configure CORS middleware
cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Created-By"],
)


# Register routers
app.include_router(fir_routes.router)
app.include_router(flown_search_routes.router)
app.include_router(formula_routes.router)
app.include_router(freshness_routes.router)
app.include_router(invoice_search_routes.router)
app.include_router(route_cost_routes.router)
app.include_router(monitoring_routes.router)
app.include_router(reference_routes.router)
app.include_router(route_validation_routes.router)
app.include_router(summary_review_routes.router)


# Exception handlers (Task 12.3)

@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException) -> JSONResponse:
    """Handle custom service exceptions.
    
    Args:
        request: The incoming request
        exc: The service exception
    
    Returns:
        JSON response with error details
    """
    logger.error(
        f"Service exception: {exc.message}",
        extra={
            "error_message": exc.message,
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )


# Formula execution exception handlers (Requirements 8.4, 8.5, 9.1, 9.2, 9.3, 9.4)

from src.exceptions import (
    FormulaNotFoundError,
    FormulaSyntaxError,
    FormulaExecutionError,
    FormulaTimeoutError,
    SecurityViolationError,
    FormulaValidationError,
    FormulaDuplicateError,
    FormulaLintError
)


@app.exception_handler(FormulaNotFoundError)
async def formula_not_found_handler(request: Request, exc: FormulaNotFoundError) -> JSONResponse:
    """Handle FormulaNotFoundError (404).
    
    Args:
        request: The incoming request
        exc: The formula not found exception
    
    Returns:
        JSON response with 404 status
    """
    logger.warning(
        f"Formula not found: {exc.message}",
        extra={
            "error_message": exc.message,
            "path": request.url.path,
            "method": request.method,
            "details": exc.details
        }
    )
    
    return JSONResponse(
        status_code=404,
        content={
            "error": "Formula not found",
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(FormulaSyntaxError)
async def formula_syntax_error_handler(request: Request, exc: FormulaSyntaxError) -> JSONResponse:
    """Handle FormulaSyntaxError (400).
    
    Args:
        request: The incoming request
        exc: The formula syntax exception
    
    Returns:
        JSON response with 400 status
    """
    logger.error(
        f"Formula syntax error: {exc.message}",
        extra={
            "error_message": exc.message,
            "path": request.url.path,
            "method": request.method,
            "details": exc.details
        }
    )
    
    return JSONResponse(
        status_code=400,
        content={
            "error": "Syntax error",
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(FormulaExecutionError)
async def formula_execution_error_handler(request: Request, exc: FormulaExecutionError) -> JSONResponse:
    """Handle FormulaExecutionError (500).
    
    Args:
        request: The incoming request
        exc: The formula execution exception
    
    Returns:
        JSON response with 500 status
    """
    logger.error(
        f"Formula execution error: {exc.message}",
        extra={
            "error_message": exc.message,
            "path": request.url.path,
            "method": request.method,
            "details": exc.details
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Execution error",
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(FormulaTimeoutError)
async def formula_timeout_error_handler(request: Request, exc: FormulaTimeoutError) -> JSONResponse:
    """Handle FormulaTimeoutError (500).
    
    Args:
        request: The incoming request
        exc: The formula timeout exception
    
    Returns:
        JSON response with 500 status
    """
    logger.error(
        f"Formula timeout: {exc.message}",
        extra={
            "error_message": exc.message,
            "path": request.url.path,
            "method": request.method,
            "details": exc.details
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Timeout",
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(SecurityViolationError)
async def security_violation_error_handler(request: Request, exc: SecurityViolationError) -> JSONResponse:
    """Handle SecurityViolationError (500).
    
    Args:
        request: The incoming request
        exc: The security violation exception
    
    Returns:
        JSON response with 500 status
    """
    logger.error(
        f"Security violation: {exc.message}",
        extra={
            "error_message": exc.message,
            "path": request.url.path,
            "method": request.method,
            "details": exc.details
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Security violation",
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(FormulaValidationError)
async def formula_validation_error_handler(request: Request, exc: FormulaValidationError) -> JSONResponse:
    """Handle FormulaValidationError (400).
    
    Args:
        request: The incoming request
        exc: The formula validation exception
    
    Returns:
        JSON response with 400 status
    """
    logger.warning(
        f"Formula validation failed: {exc.message}",
        extra={
            "error_message": exc.message,
            "path": request.url.path,
            "method": request.method,
            "details": exc.details
        }
    )
    
    return JSONResponse(
        status_code=400,
        content={
            "error": "Validation failed",
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(FormulaDuplicateError)
async def formula_duplicate_error_handler(request: Request, exc: FormulaDuplicateError) -> JSONResponse:
    """Handle FormulaDuplicateError (400).
    
    Args:
        request: The incoming request
        exc: The formula duplicate exception
    
    Returns:
        JSON response with 400 status
    """
    logger.warning(
        f"Duplicate formula detected: {exc.message}",
        extra={
            "error_message": exc.message,
            "path": request.url.path,
            "method": request.method,
            "details": exc.details
        }
    )
    
    return JSONResponse(
        status_code=400,
        content={
            "error": "Duplicate formula",
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(FormulaLintError)
async def formula_lint_error_handler(request: Request, exc: FormulaLintError) -> JSONResponse:
    """Handle FormulaLintError (400).
    
    Args:
        request: The incoming request
        exc: The formula lint exception
    
    Returns:
        JSON response with 400 status
    """
    logger.warning(
        f"Formula linting failed: {exc.message}",
        extra={
            "error_message": exc.message,
            "path": request.url.path,
            "method": request.method,
            "details": exc.details
        }
    )
    
    return JSONResponse(
        status_code=400,
        content={
            "error": "Lint failed",
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions.
    
    Catches any exceptions not handled by specific handlers and returns
    a generic 500 error response while logging the full exception details.
    
    Args:
        request: The incoming request
        exc: The unhandled exception
    
    Returns:
        JSON response with generic error message
    """
    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={
            "error": str(exc),
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Dependency injection functions (Task 12.2)

def get_formula_executor(
    request: Request,
    db: Session = Depends(get_db)
) -> "FormulaExecutor":
    """Dependency function to get FormulaExecutor instance.
    
    Retrieves components from app.state and creates a FormulaExecutor
    instance with the current database session.
    
    Args:
        request: FastAPI request object (provides access to app.state)
        db: Database session (injected)
    
    Returns:
        FormulaExecutor instance configured with all dependencies
    
    Raises:
        RuntimeError: If formula execution components not initialized
    """
    from src.formula_execution.formula_executor import FormulaExecutor
    
    if not hasattr(request.app.state, "constants_provider"):
        raise RuntimeError("Formula execution components not initialized")
    
    return FormulaExecutor(
        db_session=db,
        cache=request.app.state.cache,
        constants_provider=request.app.state.constants_provider,
        rate_loader=request.app.state.rate_loader
    )


def get_formula_validator(
    request: Request,
    db: Session = Depends(get_db)
) -> "FormulaValidator":
    """Dependency function to get FormulaValidator instance.
    
    Retrieves components from app.state and creates a FormulaValidator
    instance with the current database session and executor.
    
    Args:
        request: FastAPI request object (provides access to app.state)
        db: Database session (injected)
    
    Returns:
        FormulaValidator instance configured with executor
    
    Raises:
        RuntimeError: If formula execution components not initialized
    """
    from src.formula_execution.formula_validator import FormulaValidator
    from src.formula_execution.formula_executor import FormulaExecutor
    
    if not hasattr(request.app.state, "constants_provider"):
        raise RuntimeError("Formula execution components not initialized")
    
    # Create executor for validator
    executor = FormulaExecutor(
        db_session=db,
        cache=request.app.state.cache,
        constants_provider=request.app.state.constants_provider,
        rate_loader=request.app.state.rate_loader
    )
    
    return FormulaValidator(db_session=db, executor=executor)


def get_constants_provider(request: Request) -> "ConstantsProvider":
    """Dependency function to get ConstantsProvider instance.
    
    Retrieves the ConstantsProvider from app.state that was initialized
    at application startup.
    
    Args:
        request: FastAPI request object (provides access to app.state)
    
    Returns:
        ConstantsProvider instance
    
    Raises:
        RuntimeError: If formula execution components not initialized
    """
    from src.formula_execution.constants_provider import ConstantsProvider
    
    if not hasattr(request.app.state, "constants_provider"):
        raise RuntimeError("Formula execution components not initialized")
    
    return request.app.state.constants_provider


def get_rate_loader(request: Request) -> "EuroControlRateLoader":
    """Dependency function to get EuroControlRateLoader instance.
    
    Retrieves the EuroControlRateLoader from app.state that was initialized
    at application startup.
    
    Args:
        request: FastAPI request object (provides access to app.state)
    
    Returns:
        EuroControlRateLoader instance
    
    Raises:
        RuntimeError: If formula execution components not initialized
    """
    from src.formula_execution.eurocontrol_loader import EuroControlRateLoader
    
    if not hasattr(request.app.state, "rate_loader"):
        raise RuntimeError("Formula execution components not initialized")
    
    return request.app.state.rate_loader


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint.
    
    Returns:
        Service information
    """
    return {
        "service": "flitex-overflightcharges",
        "version": "1.0.0",
        "status": "running"
    }
