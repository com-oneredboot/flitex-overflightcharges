"""Formula management API endpoints.

This module provides REST API endpoints for managing country-specific overflight charge formulas:
- GET /api/formulas - List all active formulas
- GET /api/formulas/{country_code} - Get active formula for country
- POST /api/formulas - Create new formula (version 1)
- PUT /api/formulas/{country_code} - Update formula (creates new version)
- DELETE /api/formulas/{country_code} - Delete all formula versions
- GET /api/formulas/{country_code}/history - Get all versions ordered by version DESC
- POST /api/formulas/{country_code}/rollback - Rollback to specified version

Validates Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.7, 3.8, 3.9, 9.6, 11.3, 21.6, 21.7, 21.8, 21.9
"""

import logging
import time
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas.formula import FormulaCreate, FormulaUpdate, FormulaRollback, FormulaResponse
from src.services.formula_service import FormulaService
from src.exceptions import FormulaNotFoundException, ValidationException
from src.models.formula import Formula

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/formulas", tags=["Formula Management"])


@router.get("", response_model=List[FormulaResponse], status_code=status.HTTP_200_OK)
async def get_all_formulas(db: Session = Depends(get_db)) -> List[FormulaResponse]:
    """
    Get list of all active formulas.
    
    Returns only formulas where is_active=true, representing the current
    active version for each country.
    
    Validates Requirement: 3.1
    
    Args:
        db: Database session (injected)
    
    Returns:
        List of all active formula records
    """
    start_time = time.time()
    
    try:
        formula_service = FormulaService(db)
        formulas = formula_service.get_all_active_formulas()
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "Retrieved all active formulas",
            extra={
                "method": "GET",
                "path": "/api/formulas",
                "status_code": 200,
                "duration_ms": duration_ms,
                "count": len(formulas)
            }
        )
        
        return formulas
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to retrieve formulas: {str(e)}",
            extra={
                "method": "GET",
                "path": "/api/formulas",
                "status_code": 500,
                "duration_ms": duration_ms,
                "error": str(e)
            }
        )
        raise


@router.get("/{country_code}", response_model=FormulaResponse, status_code=status.HTTP_200_OK)
async def get_formula_by_country(
    country_code: str,
    db: Session = Depends(get_db)
) -> FormulaResponse:
    """
    Get active formula for a specific country.
    
    Returns the single active formula version for the given country code.
    
    Validates Requirements: 3.2, 3.8
    
    Args:
        country_code: ISO 3166-1 alpha-2 country code (2 uppercase letters)
        db: Database session (injected)
    
    Returns:
        Active formula record for the country
    
    Raises:
        FormulaNotFoundException: If no active formula exists for country (404)
    """
    start_time = time.time()
    
    try:
        formula_service = FormulaService(db)
        formula = formula_service.get_active_formula(country_code)
        
        if not formula:
            raise FormulaNotFoundException(
                message=f"No active formula found for country code: {country_code}",
                details={"country_code": country_code}
            )
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Retrieved formula for country: {country_code}",
            extra={
                "method": "GET",
                "path": f"/api/formulas/{country_code}",
                "status_code": 200,
                "duration_ms": duration_ms,
                "country_code": country_code
            }
        )
        
        return formula
    except FormulaNotFoundException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Formula not found for country: {country_code}",
            extra={
                "method": "GET",
                "path": f"/api/formulas/{country_code}",
                "status_code": 404,
                "duration_ms": duration_ms,
                "country_code": country_code
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to retrieve formula for {country_code}: {str(e)}",
            extra={
                "method": "GET",
                "path": f"/api/formulas/{country_code}",
                "status_code": 500,
                "duration_ms": duration_ms,
                "country_code": country_code,
                "error": str(e)
            }
        )
        raise


@router.post("", response_model=FormulaResponse, status_code=status.HTTP_201_CREATED)
async def create_formula(
    formula_data: FormulaCreate,
    db: Session = Depends(get_db)
) -> FormulaResponse:
    """
    Create new formula record (version 1).
    
    Creates a new formula with version_number=1 and is_active=true.
    Validates Python syntax before creation.
    
    Validates Requirements: 3.3, 3.9, 9.6
    
    Args:
        formula_data: Formula creation data
        db: Database session (injected)
    
    Returns:
        Created formula record
    
    Raises:
        ValidationException: If formula syntax is invalid (400)
        ValidationError: If input validation fails (422)
    """
    start_time = time.time()
    
    try:
        formula_service = FormulaService(db)
        formula = formula_service.create_formula(
            formula_data=formula_data,
            created_by=formula_data.created_by
        )
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Created formula for country: {formula.country_code}",
            extra={
                "method": "POST",
                "path": "/api/formulas",
                "status_code": 201,
                "duration_ms": duration_ms,
                "country_code": formula.country_code,
                "version_number": formula.version_number
            }
        )
        
        return formula
    except ValidationException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Formula validation failed for country: {formula_data.country_code}",
            extra={
                "method": "POST",
                "path": "/api/formulas",
                "status_code": 400,
                "duration_ms": duration_ms,
                "country_code": formula_data.country_code
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to create formula: {str(e)}",
            extra={
                "method": "POST",
                "path": "/api/formulas",
                "status_code": 500,
                "duration_ms": duration_ms,
                "error": str(e)
            }
        )
        raise


@router.put("/{country_code}", response_model=FormulaResponse, status_code=status.HTTP_200_OK)
async def update_formula(
    country_code: str,
    formula_data: FormulaUpdate,
    db: Session = Depends(get_db)
) -> FormulaResponse:
    """
    Update formula by creating new version.
    
    Deactivates the current active version and creates a new version with
    incremented version_number. Validates Python syntax before update.
    
    Validates Requirements: 3.4, 3.8, 3.9, 9.6
    
    Args:
        country_code: ISO 3166-1 alpha-2 country code
        formula_data: Formula update data (partial updates supported)
        db: Database session (injected)
    
    Returns:
        Newly created formula version
    
    Raises:
        FormulaNotFoundException: If no active formula exists for country (404)
        ValidationException: If formula syntax is invalid (400)
        ValidationError: If input validation fails (422)
    """
    start_time = time.time()
    
    try:
        formula_service = FormulaService(db)
        formula = formula_service.update_formula(
            country_code=country_code,
            formula_data=formula_data,
            created_by=formula_data.created_by
        )
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Updated formula for country: {country_code}",
            extra={
                "method": "PUT",
                "path": f"/api/formulas/{country_code}",
                "status_code": 200,
                "duration_ms": duration_ms,
                "country_code": country_code,
                "version_number": formula.version_number
            }
        )
        
        return formula
    except FormulaNotFoundException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Formula not found for update: {country_code}",
            extra={
                "method": "PUT",
                "path": f"/api/formulas/{country_code}",
                "status_code": 404,
                "duration_ms": duration_ms,
                "country_code": country_code
            }
        )
        raise
    except ValidationException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Formula validation failed for country: {country_code}",
            extra={
                "method": "PUT",
                "path": f"/api/formulas/{country_code}",
                "status_code": 400,
                "duration_ms": duration_ms,
                "country_code": country_code
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to update formula for {country_code}: {str(e)}",
            extra={
                "method": "PUT",
                "path": f"/api/formulas/{country_code}",
                "status_code": 500,
                "duration_ms": duration_ms,
                "country_code": country_code,
                "error": str(e)
            }
        )
        raise


@router.delete("/{country_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_formula(
    country_code: str,
    db: Session = Depends(get_db)
) -> None:
    """
    Delete all formula versions for a country.
    
    Removes all version records for the specified country code.
    
    Validates Requirements: 3.5, 3.8
    
    Args:
        country_code: ISO 3166-1 alpha-2 country code
        db: Database session (injected)
    
    Returns:
        None (204 No Content)
    
    Raises:
        FormulaNotFoundException: If no formulas exist for country (404)
    """
    start_time = time.time()
    
    try:
        formula_service = FormulaService(db)
        formula_service.delete_formula(country_code)
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Deleted all formulas for country: {country_code}",
            extra={
                "method": "DELETE",
                "path": f"/api/formulas/{country_code}",
                "status_code": 204,
                "duration_ms": duration_ms,
                "country_code": country_code
            }
        )
    except FormulaNotFoundException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Formula not found for deletion: {country_code}",
            extra={
                "method": "DELETE",
                "path": f"/api/formulas/{country_code}",
                "status_code": 404,
                "duration_ms": duration_ms,
                "country_code": country_code
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to delete formula for {country_code}: {str(e)}",
            extra={
                "method": "DELETE",
                "path": f"/api/formulas/{country_code}",
                "status_code": 500,
                "duration_ms": duration_ms,
                "country_code": country_code,
                "error": str(e)
            }
        )
        raise


@router.get("/{country_code}/history", response_model=List[FormulaResponse], status_code=status.HTTP_200_OK)
async def get_formula_history(
    country_code: str,
    db: Session = Depends(get_db)
) -> List[FormulaResponse]:
    """
    Get all formula versions for a country ordered by version DESC.
    
    Returns complete version history for the specified country, with most
    recent version first.
    
    Validates Requirements: 3.7, 21.6
    
    Args:
        country_code: ISO 3166-1 alpha-2 country code
        db: Database session (injected)
    
    Returns:
        List of formula records ordered by version_number descending
    
    Raises:
        FormulaNotFoundException: If no formulas exist for country (404)
    """
    start_time = time.time()
    
    try:
        formula_service = FormulaService(db)
        formulas = formula_service.get_formula_history(country_code)
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Retrieved formula history for country: {country_code}",
            extra={
                "method": "GET",
                "path": f"/api/formulas/{country_code}/history",
                "status_code": 200,
                "duration_ms": duration_ms,
                "country_code": country_code,
                "version_count": len(formulas)
            }
        )
        
        return formulas
    except FormulaNotFoundException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"No formula history found for country: {country_code}",
            extra={
                "method": "GET",
                "path": f"/api/formulas/{country_code}/history",
                "status_code": 404,
                "duration_ms": duration_ms,
                "country_code": country_code
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to retrieve formula history for {country_code}: {str(e)}",
            extra={
                "method": "GET",
                "path": f"/api/formulas/{country_code}/history",
                "status_code": 500,
                "duration_ms": duration_ms,
                "country_code": country_code,
                "error": str(e)
            }
        )
        raise


@router.post("/{country_code}/rollback", response_model=FormulaResponse, status_code=status.HTTP_200_OK)
async def rollback_formula(
    country_code: str,
    rollback_data: FormulaRollback,
    db: Session = Depends(get_db)
) -> FormulaResponse:
    """
    Rollback to a specified formula version.
    
    Deactivates the current active version and activates the specified
    version number. The specified version must exist for the country.
    
    Validates Requirements: 3.8, 21.8, 21.9
    
    Args:
        country_code: ISO 3166-1 alpha-2 country code
        rollback_data: Rollback request with version_number
        db: Database session (injected)
    
    Returns:
        Activated formula version
    
    Raises:
        FormulaNotFoundException: If specified version doesn't exist (404)
    """
    start_time = time.time()
    
    try:
        formula_service = FormulaService(db)
        formula = formula_service.rollback_formula(
            country_code=country_code,
            version_number=rollback_data.version_number
        )
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Rolled back formula for country: {country_code}",
            extra={
                "method": "POST",
                "path": f"/api/formulas/{country_code}/rollback",
                "status_code": 200,
                "duration_ms": duration_ms,
                "country_code": country_code,
                "version_number": rollback_data.version_number
            }
        )
        
        return formula
    except FormulaNotFoundException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Formula version not found for rollback: {country_code} v{rollback_data.version_number}",
            extra={
                "method": "POST",
                "path": f"/api/formulas/{country_code}/rollback",
                "status_code": 404,
                "duration_ms": duration_ms,
                "country_code": country_code,
                "version_number": rollback_data.version_number
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to rollback formula for {country_code}: {str(e)}",
            extra={
                "method": "POST",
                "path": f"/api/formulas/{country_code}/rollback",
                "status_code": 500,
                "duration_ms": duration_ms,
                "country_code": country_code,
                "error": str(e)
            }
        )
        raise



# New endpoints for Task 10: Formula Execution System

@router.get("/bulk", response_model=dict, status_code=status.HTTP_200_OK)
async def get_all_formulas_with_bytecode(db: Session = Depends(get_db)) -> dict:
    """
    Get all formulas with bytecode (bulk fetch with Redis cache).
    
    Returns all active formulas indexed by country_code or "EuroControl" for regional formulas.
    Bytecode is returned as base64-encoded string. Results are cached in Redis.
    
    Validates Requirements: 8.1, 8.2, 5.1, 5.2
    
    Args:
        db: Database session (injected)
    
    Returns:
        Dictionary with formulas indexed by country_code, cached_at timestamp, and cache_ttl_seconds
    
    Example Response:
        {
            "formulas": {
                "US": {
                    "id": "123e4567-...",
                    "country_code": "US",
                    "description": "United States",
                    "bytecode": "<base64-encoded-bytecode>",
                    "version": 1,
                    "currency": "USD"
                },
                "EuroControl": {
                    "id": "789e4567-...",
                    "country_code": null,
                    "description": "EuroControl",
                    "bytecode": "<base64-encoded-bytecode>",
                    "version": 1,
                    "currency": "EUR"
                }
            },
            "cached_at": "2024-01-01T12:00:00Z",
            "cache_ttl_seconds": 3600
        }
    """
    import base64
    from datetime import datetime, timezone
    from src.formula_execution.formula_cache import FormulaCache
    from src.formula_execution.redis_config import get_redis_client
    
    start_time = time.time()
    
    try:
        # Initialize cache
        redis_client = get_redis_client()
        cache = FormulaCache(redis_client)
        
        # Try to get from cache first
        cache_key = "formulas:bulk:all"
        cached_result = None
        
        if redis_client:
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    import pickle
                    cached_result = pickle.loads(cached_data)
                    logger.info(
                        "Retrieved formulas from cache",
                        extra={
                            "method": "GET",
                            "path": "/api/formulas/bulk",
                            "status_code": 200,
                            "cache_hit": True,
                            "duration_ms": (time.time() - start_time) * 1000
                        }
                    )
                    return cached_result
            except Exception as e:
                logger.warning(f"Cache retrieval failed: {e}")
        
        # Cache miss - load from database
        formula_service = FormulaService(db)
        formulas = formula_service.get_all_active_formulas()
        
        # Build response dictionary indexed by country_code
        formulas_dict = {}
        for formula in formulas:
            # Use "EuroControl" as key for regional formulas (country_code is None)
            key = formula.country_code if formula.country_code else "EuroControl"
            
            # Encode bytecode as base64 if it exists
            bytecode_b64 = ""
            if formula.formula_bytecode:
                bytecode_b64 = base64.b64encode(formula.formula_bytecode).decode('utf-8')
            
            formulas_dict[key] = {
                "id": str(formula.id),
                "country_code": formula.country_code,
                "description": formula.description,
                "bytecode": bytecode_b64,
                "version": formula.version_number,
                "currency": formula.currency
            }
        
        # Build response
        response = {
            "formulas": formulas_dict,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_seconds": 3600
        }
        
        # Store in cache
        if redis_client:
            try:
                import pickle
                redis_client.setex(cache_key, 3600, pickle.dumps(response))
            except Exception as e:
                logger.warning(f"Cache storage failed: {e}")
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "Retrieved all formulas with bytecode",
            extra={
                "method": "GET",
                "path": "/api/formulas/bulk",
                "status_code": 200,
                "duration_ms": duration_ms,
                "count": len(formulas_dict),
                "cache_hit": False
            }
        )
        
        return response
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to retrieve formulas with bytecode: {str(e)}",
            extra={
                "method": "GET",
                "path": "/api/formulas/bulk",
                "status_code": 500,
                "duration_ms": duration_ms,
                "error": str(e)
            }
        )
        raise


@router.get("/{formula_id}/full", response_model=dict, status_code=status.HTTP_200_OK)
async def get_formula_by_id(
    formula_id: str,
    db: Session = Depends(get_db)
) -> dict:
    """
    Get formula by ID (full DB record).
    
    Returns the complete formula record including all fields from the database.
    
    Validates Requirements: 8.2, 1.1, 1.2, 1.3
    
    Args:
        formula_id: UUID of the formula to retrieve
        db: Database session (injected)
    
    Returns:
        Complete formula record with all database fields
    
    Raises:
        FormulaNotFoundException: If formula doesn't exist (404)
    """
    import base64
    from uuid import UUID
    
    start_time = time.time()
    
    try:
        # Parse UUID
        try:
            uuid_obj = UUID(formula_id)
        except ValueError:
            raise FormulaNotFoundException(
                message=f"Invalid formula ID format: {formula_id}",
                details={"formula_id": formula_id}
            )
        
        # Query formula by ID
        formula = db.query(Formula).filter(Formula.id == uuid_obj).first()
        
        if not formula:
            raise FormulaNotFoundException(
                message=f"Formula not found: {formula_id}",
                details={"formula_id": formula_id}
            )
        
        # Encode bytecode as base64 if it exists
        bytecode_b64 = ""
        if formula.formula_bytecode:
            bytecode_b64 = base64.b64encode(formula.formula_bytecode).decode('utf-8')
        
        # Build response
        response = {
            "id": str(formula.id),
            "country_code": formula.country_code,
            "description": formula.description,
            "formula_code_id": formula.formula_code,
            "formula_code": formula.formula_logic,
            "bytecode": bytecode_b64,
            "version": formula.version_number,
            "currency": formula.currency,
            "effective_date": formula.effective_date.isoformat(),
            "formula_hash": formula.formula_hash,
            "is_active": formula.is_active,
            "created_at": formula.created_at.isoformat(),
            "created_by": formula.created_by
        }
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Retrieved formula by ID: {formula_id}",
            extra={
                "method": "GET",
                "path": f"/api/formulas/{formula_id}/full",
                "status_code": 200,
                "duration_ms": duration_ms,
                "formula_id": formula_id
            }
        )
        
        return response
        
    except FormulaNotFoundException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Formula not found: {formula_id}",
            extra={
                "method": "GET",
                "path": f"/api/formulas/{formula_id}/full",
                "status_code": 404,
                "duration_ms": duration_ms,
                "formula_id": formula_id
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to retrieve formula {formula_id}: {str(e)}",
            extra={
                "method": "GET",
                "path": f"/api/formulas/{formula_id}/full",
                "status_code": 500,
                "duration_ms": duration_ms,
                "formula_id": formula_id,
                "error": str(e)
            }
        )
        raise


@router.get("/execution-context", response_model=dict, status_code=status.HTTP_200_OK)
async def get_formula_execution_context(db: Session = Depends(get_db)) -> dict:
    """
    Get formula execution context (constants + EuroControl rates).
    
    Returns all constants, utilities, math functions, and EuroControl rates
    needed for formula execution. Results are cached in Redis.
    
    Validates Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.8, 10.3
    
    Args:
        db: Database session (injected)
    
    Returns:
        Dictionary containing constants, utilities, math_functions, and eurocontrol_rates
    
    Example Response:
        {
            "constants": {
                "currencies": {...},
                "countries": {...},
                "fir_names_per_country": {...},
                "canada_tsc_aerodromes": [...]
            },
            "utilities": {
                "convert_nm_to_km": "function to convert nautical miles to kilometers (multiply by 1.852)"
            },
            "math_functions": ["sqrt", "pow", "abs", "ceil", "floor", "round"],
            "eurocontrol_rates": {...},
            "cached_at": "2024-01-01T12:00:00Z",
            "cache_ttl_seconds": 900
        }
    """
    from datetime import datetime, timezone
    from src.formula_execution.constants_provider import ConstantsProvider
    from src.formula_execution.eurocontrol_loader import EuroControlRateLoader
    from src.formula_execution.redis_config import get_redis_client
    
    start_time = time.time()
    
    try:
        # Try to get from cache first
        redis_client = get_redis_client()
        cache_key = "formulas:execution_context"
        cached_result = None
        
        if redis_client:
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    import pickle
                    cached_result = pickle.loads(cached_data)
                    logger.info(
                        "Retrieved execution context from cache",
                        extra={
                            "method": "GET",
                            "path": "/api/formulas/execution-context",
                            "status_code": 200,
                            "cache_hit": True,
                            "duration_ms": (time.time() - start_time) * 1000
                        }
                    )
                    return cached_result
            except Exception as e:
                logger.warning(f"Cache retrieval failed: {e}")
        
        # Cache miss - build context
        constants_provider = ConstantsProvider()
        rate_loader = EuroControlRateLoader(db)
        
        # Load EuroControl rates
        eurocontrol_rates = rate_loader.load_rates()
        
        # Get execution context
        context = constants_provider.get_execution_context()
        
        # Build response
        response = {
            "constants": {
                "currencies": context.get("CURRENCY_CONSTANTS", {}),
                "countries": context.get("COUNTRY_NAME_CONSTANTS", {}),
                "fir_names_per_country": context.get("FIR_NAMES_PER_COUNTRY", {}),
                "canada_tsc_aerodromes": context.get("CANADA_TSC_AERODROMES", [])
            },
            "utilities": {
                "convert_nm_to_km": "function to convert nautical miles to kilometers (multiply by 1.852)"
            },
            "math_functions": ["sqrt", "pow", "abs", "ceil", "floor", "round"],
            "eurocontrol_rates": eurocontrol_rates,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_seconds": 900
        }
        
        # Store in cache (15 minutes TTL)
        if redis_client:
            try:
                import pickle
                redis_client.setex(cache_key, 900, pickle.dumps(response))
            except Exception as e:
                logger.warning(f"Cache storage failed: {e}")
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "Retrieved formula execution context",
            extra={
                "method": "GET",
                "path": "/api/formulas/execution-context",
                "status_code": 200,
                "duration_ms": duration_ms,
                "cache_hit": False
            }
        )
        
        return response
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to retrieve execution context: {str(e)}",
            extra={
                "method": "GET",
                "path": "/api/formulas/execution-context",
                "status_code": 500,
                "duration_ms": duration_ms,
                "error": str(e)
            }
        )
        raise


@router.post("/validate", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_formula_with_validation(
    formula_data: "FormulaValidationRequest",
    db: Session = Depends(get_db)
) -> dict:
    """
    Create formula with validation (POST /api/formulas).
    
    Validates formula code using FormulaValidator.validate_and_save which:
    - Checks Python syntax
    - Verifies calculate function exists
    - Executes test calculation
    - Formats code with Black
    - Runs linting checks
    - Computes SHA256 hash
    - Checks for duplicates
    - Stores hash in formula_hash column
    
    Validates Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10
    
    Args:
        formula_data: Formula validation request data
        db: Database session (injected)
    
    Returns:
        Created formula response with id, formula_hash, version, and message
    
    Raises:
        ValidationException: If validation fails (400)
    """
    from src.schemas.formula import FormulaValidationRequest
    from src.formula_execution.formula_validator import FormulaValidator
    from src.formula_execution.formula_executor import FormulaExecutor
    from src.formula_execution.formula_cache import FormulaCache
    from src.formula_execution.constants_provider import ConstantsProvider
    from src.formula_execution.eurocontrol_loader import EuroControlRateLoader
    from src.formula_execution.redis_config import get_redis_client
    
    start_time = time.time()
    
    try:
        # Initialize dependencies
        redis_client = get_redis_client()
        cache = FormulaCache(redis_client)
        constants_provider = ConstantsProvider()
        rate_loader = EuroControlRateLoader(db)
        rate_loader.load_rates()
        
        executor = FormulaExecutor(
            db_session=db,
            cache=cache,
            constants_provider=constants_provider,
            rate_loader=rate_loader
        )
        
        validator = FormulaValidator(db_session=db, executor=executor)
        
        # Validate and save formula
        formula = validator.validate_and_save(
            formula_code=formula_data.formula_code,
            country_code=formula_data.country_code,
            description=formula_data.description,
            formula_code_id=formula_data.formula_code_id,
            effective_date=formula_data.effective_date,
            currency=formula_data.currency,
            created_by=formula_data.created_by
        )
        
        # Build response
        response = {
            "id": str(formula.id),
            "formula_hash": formula.formula_hash,
            "version": formula.version_number,
            "message": "Formula validated and saved successfully"
        }
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Created formula with validation: {formula.country_code}",
            extra={
                "method": "POST",
                "path": "/api/formulas/validate",
                "status_code": 201,
                "duration_ms": duration_ms,
                "country_code": formula.country_code,
                "formula_id": str(formula.id)
            }
        )
        
        return response
        
    except ValidationException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Formula validation failed",
            extra={
                "method": "POST",
                "path": "/api/formulas/validate",
                "status_code": 400,
                "duration_ms": duration_ms
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to create formula: {str(e)}",
            extra={
                "method": "POST",
                "path": "/api/formulas/validate",
                "status_code": 500,
                "duration_ms": duration_ms,
                "error": str(e)
            }
        )
        raise


@router.put("/{formula_id}/update", response_model=dict, status_code=status.HTTP_200_OK)
async def update_formula_by_id(
    formula_id: str,
    formula_data: "FormulaValidationRequest",
    db: Session = Depends(get_db)
) -> dict:
    """
    Update formula by ID (PUT /api/formulas/{formula_id}).
    
    Updates formula with validation, increments version_number, and updates updated_at timestamp.
    Invalidates cache after update.
    
    Validates Requirements: 1.2, 1.3, 5.2, 11.1-11.10
    
    Args:
        formula_id: UUID of formula to update
        formula_data: Formula validation request data
        db: Database session (injected)
    
    Returns:
        Updated formula response with id, formula_hash, version, and message
    
    Raises:
        FormulaNotFoundException: If formula doesn't exist (404)
        ValidationException: If validation fails (400)
    """
    from uuid import UUID
    from src.schemas.formula import FormulaValidationRequest
    from src.formula_execution.formula_validator import FormulaValidator
    from src.formula_execution.formula_executor import FormulaExecutor
    from src.formula_execution.formula_cache import FormulaCache
    from src.formula_execution.constants_provider import ConstantsProvider
    from src.formula_execution.eurocontrol_loader import EuroControlRateLoader
    from src.formula_execution.redis_config import get_redis_client
    
    start_time = time.time()
    
    try:
        # Parse UUID
        try:
            uuid_obj = UUID(formula_id)
        except ValueError:
            raise FormulaNotFoundException(
                message=f"Invalid formula ID format: {formula_id}",
                details={"formula_id": formula_id}
            )
        
        # Get existing formula
        existing_formula = db.query(Formula).filter(Formula.id == uuid_obj).first()
        
        if not existing_formula:
            raise FormulaNotFoundException(
                message=f"Formula not found: {formula_id}",
                details={"formula_id": formula_id}
            )
        
        # Initialize dependencies
        redis_client = get_redis_client()
        cache = FormulaCache(redis_client)
        constants_provider = ConstantsProvider()
        rate_loader = EuroControlRateLoader(db)
        rate_loader.load_rates()
        
        executor = FormulaExecutor(
            db_session=db,
            cache=cache,
            constants_provider=constants_provider,
            rate_loader=rate_loader
        )
        
        validator = FormulaValidator(db_session=db, executor=executor)
        
        # Deactivate existing formula
        existing_formula.is_active = False
        db.commit()
        
        # Create new version with incremented version_number
        new_version = existing_formula.version_number + 1
        
        # Validate and save new version
        formula = validator.validate_and_save(
            formula_code=formula_data.formula_code,
            country_code=formula_data.country_code or existing_formula.country_code,
            description=formula_data.description,
            formula_code_id=formula_data.formula_code_id,
            effective_date=formula_data.effective_date,
            currency=formula_data.currency,
            created_by=formula_data.created_by,
            version_number=new_version
        )
        
        # Invalidate cache
        cache.invalidate_formula(uuid_obj)
        
        # Build response
        response = {
            "id": str(formula.id),
            "formula_hash": formula.formula_hash,
            "version": formula.version_number,
            "message": "Formula updated successfully"
        }
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Updated formula: {formula_id}",
            extra={
                "method": "PUT",
                "path": f"/api/formulas/{formula_id}/update",
                "status_code": 200,
                "duration_ms": duration_ms,
                "formula_id": formula_id,
                "new_version": new_version
            }
        )
        
        return response
        
    except (FormulaNotFoundException, ValidationException):
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Formula update failed: {formula_id}",
            extra={
                "method": "PUT",
                "path": f"/api/formulas/{formula_id}/update",
                "status_code": 404 if isinstance(e, FormulaNotFoundException) else 400,
                "duration_ms": duration_ms,
                "formula_id": formula_id
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to update formula {formula_id}: {str(e)}",
            extra={
                "method": "PUT",
                "path": f"/api/formulas/{formula_id}/update",
                "status_code": 500,
                "duration_ms": duration_ms,
                "formula_id": formula_id,
                "error": str(e)
            }
        )
        raise


@router.delete("/{formula_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_formula_by_id(
    formula_id: str,
    db: Session = Depends(get_db)
) -> None:
    """
    Delete formula by ID (DELETE /api/formulas/{formula_id}).
    
    Deletes formula and invalidates cache.
    
    Validates Requirements: 5.2
    
    Args:
        formula_id: UUID of formula to delete
        db: Database session (injected)
    
    Returns:
        None (204 No Content)
    
    Raises:
        FormulaNotFoundException: If formula doesn't exist (404)
    """
    from uuid import UUID
    from src.formula_execution.formula_cache import FormulaCache
    from src.formula_execution.redis_config import get_redis_client
    
    start_time = time.time()
    
    try:
        # Parse UUID
        try:
            uuid_obj = UUID(formula_id)
        except ValueError:
            raise FormulaNotFoundException(
                message=f"Invalid formula ID format: {formula_id}",
                details={"formula_id": formula_id}
            )
        
        # Get formula
        formula = db.query(Formula).filter(Formula.id == uuid_obj).first()
        
        if not formula:
            raise FormulaNotFoundException(
                message=f"Formula not found: {formula_id}",
                details={"formula_id": formula_id}
            )
        
        # Delete formula
        db.delete(formula)
        db.commit()
        
        # Invalidate cache
        redis_client = get_redis_client()
        cache = FormulaCache(redis_client)
        cache.invalidate_formula(uuid_obj)
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Deleted formula: {formula_id}",
            extra={
                "method": "DELETE",
                "path": f"/api/formulas/{formula_id}/delete",
                "status_code": 204,
                "duration_ms": duration_ms,
                "formula_id": formula_id
            }
        )
        
    except FormulaNotFoundException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Formula not found for deletion: {formula_id}",
            extra={
                "method": "DELETE",
                "path": f"/api/formulas/{formula_id}/delete",
                "status_code": 404,
                "duration_ms": duration_ms,
                "formula_id": formula_id
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to delete formula {formula_id}: {str(e)}",
            extra={
                "method": "DELETE",
                "path": f"/api/formulas/{formula_id}/delete",
                "status_code": 500,
                "duration_ms": duration_ms,
                "formula_id": formula_id,
                "error": str(e)
            }
        )
        raise
