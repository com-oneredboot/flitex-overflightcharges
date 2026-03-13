"""FIR management API endpoints.

This module provides REST API endpoints for managing FIR (Flight Information Region) data:
- GET /api/iata-firs - List all FIRs
- GET /api/iata-firs/{icao_code} - Get single FIR
- POST /api/iata-firs - Create new FIR
- PUT /api/iata-firs/{icao_code} - Update FIR
- DELETE /api/iata-firs/{icao_code} - Delete FIR

Validates Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 1.8, 9.6, 11.3
"""

import logging
import time
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas.fir import FIRCreate, FIRUpdate, FIRResponse
from src.services.fir_service import FIRService
from src.exceptions import FIRNotFoundException, DuplicateFIRException

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/iata-firs", tags=["FIR Management"])


@router.get("", response_model=List[FIRResponse], status_code=status.HTTP_200_OK)
async def get_all_firs(db: Session = Depends(get_db)) -> List[FIRResponse]:
    """
    Get list of all FIR records.
    
    Validates Requirement: 1.1
    
    Args:
        db: Database session (injected)
    
    Returns:
        List of all FIR records
    """
    start_time = time.time()
    
    try:
        fir_service = FIRService(db)
        firs = fir_service.get_all_firs()
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "Retrieved all FIRs",
            extra={
                "method": "GET",
                "path": "/api/iata-firs",
                "status_code": 200,
                "duration_ms": duration_ms,
                "count": len(firs)
            }
        )
        
        return firs
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to retrieve FIRs: {str(e)}",
            extra={
                "method": "GET",
                "path": "/api/iata-firs",
                "status_code": 500,
                "duration_ms": duration_ms,
                "error": str(e)
            }
        )
        raise


@router.get("/{icao_code}", response_model=FIRResponse, status_code=status.HTTP_200_OK)
async def get_fir_by_code(
    icao_code: str,
    db: Session = Depends(get_db)
) -> FIRResponse:
    """
    Get single FIR record by ICAO code.
    
    Validates Requirements: 1.2, 1.7
    
    Args:
        icao_code: ICAO code (4 uppercase alphanumeric)
        db: Database session (injected)
    
    Returns:
        FIR record
    
    Raises:
        FIRNotFoundException: If FIR with icao_code does not exist (404)
    """
    start_time = time.time()
    
    try:
        fir_service = FIRService(db)
        fir = fir_service.get_fir_by_code(icao_code)
        
        if not fir:
            raise FIRNotFoundException(
                message=f"FIR with ICAO code '{icao_code}' not found",
                details={"icao_code": icao_code}
            )
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Retrieved FIR: {icao_code}",
            extra={
                "method": "GET",
                "path": f"/api/iata-firs/{icao_code}",
                "status_code": 200,
                "duration_ms": duration_ms,
                "icao_code": icao_code
            }
        )
        
        return fir
    except FIRNotFoundException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"FIR not found: {icao_code}",
            extra={
                "method": "GET",
                "path": f"/api/iata-firs/{icao_code}",
                "status_code": 404,
                "duration_ms": duration_ms,
                "icao_code": icao_code
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to retrieve FIR {icao_code}: {str(e)}",
            extra={
                "method": "GET",
                "path": f"/api/iata-firs/{icao_code}",
                "status_code": 500,
                "duration_ms": duration_ms,
                "icao_code": icao_code,
                "error": str(e)
            }
        )
        raise


@router.post("", response_model=FIRResponse, status_code=status.HTTP_201_CREATED)
async def create_fir(
    fir_data: FIRCreate,
    db: Session = Depends(get_db)
) -> FIRResponse:
    """
    Create new FIR record.
    
    Validates Requirements: 1.3, 1.6, 1.8, 9.6
    
    Args:
        fir_data: FIR creation data
        db: Database session (injected)
    
    Returns:
        Created FIR record
    
    Raises:
        DuplicateFIRException: If FIR with icao_code already exists (409)
        ValidationError: If input validation fails (422)
    """
    start_time = time.time()
    
    try:
        fir_service = FIRService(db)
        fir = fir_service.create_fir(fir_data)
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Created FIR: {fir.icao_code}",
            extra={
                "method": "POST",
                "path": "/api/iata-firs",
                "status_code": 201,
                "duration_ms": duration_ms,
                "icao_code": fir.icao_code
            }
        )
        
        return fir
    except DuplicateFIRException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Duplicate FIR: {fir_data.icao_code}",
            extra={
                "method": "POST",
                "path": "/api/iata-firs",
                "status_code": 409,
                "duration_ms": duration_ms,
                "icao_code": fir_data.icao_code
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to create FIR: {str(e)}",
            extra={
                "method": "POST",
                "path": "/api/iata-firs",
                "status_code": 500,
                "duration_ms": duration_ms,
                "error": str(e)
            }
        )
        raise


@router.put("/{icao_code}", response_model=FIRResponse, status_code=status.HTTP_200_OK)
async def update_fir(
    icao_code: str,
    fir_data: FIRUpdate,
    db: Session = Depends(get_db)
) -> FIRResponse:
    """
    Update existing FIR record.
    
    Validates Requirements: 1.4, 1.7, 9.6
    
    Args:
        icao_code: ICAO code of FIR to update
        fir_data: FIR update data (partial updates supported)
        db: Database session (injected)
    
    Returns:
        Updated FIR record
    
    Raises:
        FIRNotFoundException: If FIR with icao_code does not exist (404)
        ValidationError: If input validation fails (422)
    """
    start_time = time.time()
    
    try:
        fir_service = FIRService(db)
        fir = fir_service.update_fir(icao_code, fir_data)
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Updated FIR: {icao_code}",
            extra={
                "method": "PUT",
                "path": f"/api/iata-firs/{icao_code}",
                "status_code": 200,
                "duration_ms": duration_ms,
                "icao_code": icao_code
            }
        )
        
        return fir
    except FIRNotFoundException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"FIR not found for update: {icao_code}",
            extra={
                "method": "PUT",
                "path": f"/api/iata-firs/{icao_code}",
                "status_code": 404,
                "duration_ms": duration_ms,
                "icao_code": icao_code
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to update FIR {icao_code}: {str(e)}",
            extra={
                "method": "PUT",
                "path": f"/api/iata-firs/{icao_code}",
                "status_code": 500,
                "duration_ms": duration_ms,
                "icao_code": icao_code,
                "error": str(e)
            }
        )
        raise


@router.delete("/{icao_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fir(
    icao_code: str,
    db: Session = Depends(get_db)
) -> None:
    """
    Delete FIR record.
    
    Validates Requirements: 1.5, 1.7
    
    Args:
        icao_code: ICAO code of FIR to delete
        db: Database session (injected)
    
    Returns:
        None (204 No Content)
    
    Raises:
        FIRNotFoundException: If FIR with icao_code does not exist (404)
    """
    start_time = time.time()
    
    try:
        fir_service = FIRService(db)
        fir_service.delete_fir(icao_code)
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Deleted FIR: {icao_code}",
            extra={
                "method": "DELETE",
                "path": f"/api/iata-firs/{icao_code}",
                "status_code": 204,
                "duration_ms": duration_ms,
                "icao_code": icao_code
            }
        )
    except FIRNotFoundException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"FIR not found for deletion: {icao_code}",
            extra={
                "method": "DELETE",
                "path": f"/api/iata-firs/{icao_code}",
                "status_code": 404,
                "duration_ms": duration_ms,
                "icao_code": icao_code
            }
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to delete FIR {icao_code}: {str(e)}",
            extra={
                "method": "DELETE",
                "path": f"/api/iata-firs/{icao_code}",
                "status_code": 500,
                "duration_ms": duration_ms,
                "icao_code": icao_code,
                "error": str(e)
            }
        )
        raise
