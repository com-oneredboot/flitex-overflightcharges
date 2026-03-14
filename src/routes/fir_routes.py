"""Versioned FIR management API endpoints.

This module provides REST API endpoints for managing versioned FIR
(Flight Information Region) data:
- GET /api/iata-firs - List all active FIRs
- GET /api/iata-firs/{icao_code} - Get active FIR by ICAO code
- POST /api/iata-firs - Create new FIR (version 1)
- PUT /api/iata-firs/{icao_code} - Update FIR (creates new version)
- DELETE /api/iata-firs/{icao_code} - Soft-delete FIR
- GET /api/iata-firs/{icao_code}/history - Get version history
- POST /api/iata-firs/{icao_code}/rollback - Rollback to version number
- GET /api/coverage-health - Get FIR-formula coverage data from view

Validates Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
"""

import logging
import time
from typing import List

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas.fir import (
    FIRCreate,
    FIRUpdate,
    FIRResponse,
    FIRRollbackRequest,
    CoverageHealthResponse,
    CoverageDetail,
)
from src.services.fir_service import FIRService
from src.exceptions import FIRNotFoundException, DuplicateFIRException

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["FIR Management"])


@router.get("/iata-firs", response_model=List[FIRResponse], status_code=status.HTTP_200_OK)
async def get_all_firs(db: Session = Depends(get_db)) -> List[FIRResponse]:
    """
    Get list of all active FIR records.

    Returns only FIRs where is_active=True, representing the current
    active version for each ICAO code.

    Validates Requirement: 7.1

    Args:
        db: Database session (injected)

    Returns:
        List of all active FIR records
    """
    start_time = time.time()

    try:
        fir_service = FIRService(db)
        firs = fir_service.get_all_active_firs()

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "Retrieved all active FIRs",
            extra={
                "method": "GET",
                "path": "/api/iata-firs",
                "status_code": 200,
                "duration_ms": duration_ms,
                "count": len(firs),
            },
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
                "error": str(e),
            },
        )
        raise


@router.get("/iata-firs/{icao_code}", response_model=FIRResponse, status_code=status.HTTP_200_OK)
async def get_fir_by_code(
    icao_code: str,
    db: Session = Depends(get_db),
) -> FIRResponse:
    """
    Get active FIR record by ICAO code.

    Returns the single active FIR version for the given ICAO code.

    Validates Requirements: 7.1, 7.7

    Args:
        icao_code: ICAO code (4 uppercase alphanumeric)
        db: Database session (injected)

    Returns:
        Active FIR record

    Raises:
        FIRNotFoundException: If no active FIR exists for icao_code (404)
    """
    start_time = time.time()

    try:
        fir_service = FIRService(db)
        fir = fir_service.get_active_fir(icao_code)

        if not fir:
            raise FIRNotFoundException(
                message=f"FIR with ICAO code '{icao_code}' not found",
                details={"icao_code": icao_code},
            )

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Retrieved FIR: {icao_code}",
            extra={
                "method": "GET",
                "path": f"/api/iata-firs/{icao_code}",
                "status_code": 200,
                "duration_ms": duration_ms,
                "icao_code": icao_code,
            },
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
                "icao_code": icao_code,
            },
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
                "error": str(e),
            },
        )
        raise


@router.post("/iata-firs", response_model=FIRResponse, status_code=status.HTTP_201_CREATED)
async def create_fir(
    fir_data: FIRCreate,
    db: Session = Depends(get_db),
    x_created_by: str = Header(default="api-user", alias="X-Created-By"),
) -> FIRResponse:
    """
    Create new FIR record (version 1).

    Creates a new FIR with version_number=1 and is_active=True.

    Validates Requirements: 7.4, 7.7, 7.8

    Args:
        fir_data: FIR creation data
        db: Database session (injected)
        x_created_by: User identifier from header (defaults to "api-user")

    Returns:
        Created FIR record

    Raises:
        DuplicateFIRException: If active FIR already exists for icao_code (409)
        ValidationError: If input validation fails (422)
    """
    start_time = time.time()

    try:
        fir_service = FIRService(db)
        fir = fir_service.create_fir(fir_data, created_by=x_created_by)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Created FIR: {fir.icao_code}",
            extra={
                "method": "POST",
                "path": "/api/iata-firs",
                "status_code": 201,
                "duration_ms": duration_ms,
                "icao_code": fir.icao_code,
                "version_number": fir.version_number,
                "created_by": x_created_by,
            },
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
                "icao_code": fir_data.icao_code,
            },
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
                "error": str(e),
            },
        )
        raise


@router.put("/iata-firs/{icao_code}", response_model=FIRResponse, status_code=status.HTTP_200_OK)
async def update_fir(
    icao_code: str,
    fir_data: FIRUpdate,
    db: Session = Depends(get_db),
    x_created_by: str = Header(default="api-user", alias="X-Created-By"),
) -> FIRResponse:
    """
    Update existing FIR by creating a new version.

    Deactivates the current active version and creates a new version with
    incremented version_number.

    Validates Requirements: 7.5, 7.7, 7.8

    Args:
        icao_code: ICAO code of FIR to update
        fir_data: FIR update data (partial updates supported)
        db: Database session (injected)
        x_created_by: User identifier from header (defaults to "api-user")

    Returns:
        Newly created FIR version

    Raises:
        FIRNotFoundException: If no active FIR exists for icao_code (404)
        DuplicateFIRException: If integrity constraint violated (409)
    """
    start_time = time.time()

    try:
        fir_service = FIRService(db)
        fir = fir_service.update_fir(icao_code, fir_data, created_by=x_created_by)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Updated FIR: {icao_code}",
            extra={
                "method": "PUT",
                "path": f"/api/iata-firs/{icao_code}",
                "status_code": 200,
                "duration_ms": duration_ms,
                "icao_code": icao_code,
                "version_number": fir.version_number,
                "created_by": x_created_by,
            },
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
                "icao_code": icao_code,
            },
        )
        raise
    except DuplicateFIRException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"Integrity constraint violated for FIR update: {icao_code}",
            extra={
                "method": "PUT",
                "path": f"/api/iata-firs/{icao_code}",
                "status_code": 409,
                "duration_ms": duration_ms,
                "icao_code": icao_code,
            },
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
                "error": str(e),
            },
        )
        raise


@router.delete("/iata-firs/{icao_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fir(
    icao_code: str,
    db: Session = Depends(get_db),
) -> None:
    """
    Soft-delete FIR record.

    Sets is_active=False and deactivation_date=now() on the current active
    version. No physical row removal.

    Validates Requirements: 7.6, 7.7

    Args:
        icao_code: ICAO code of FIR to soft-delete
        db: Database session (injected)

    Returns:
        None (204 No Content)

    Raises:
        FIRNotFoundException: If no active FIR exists for icao_code (404)
    """
    start_time = time.time()

    try:
        fir_service = FIRService(db)
        fir_service.soft_delete_fir(icao_code)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Soft-deleted FIR: {icao_code}",
            extra={
                "method": "DELETE",
                "path": f"/api/iata-firs/{icao_code}",
                "status_code": 204,
                "duration_ms": duration_ms,
                "icao_code": icao_code,
            },
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
                "icao_code": icao_code,
            },
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
                "error": str(e),
            },
        )
        raise


@router.get(
    "/iata-firs/{icao_code}/history",
    response_model=List[FIRResponse],
    status_code=status.HTTP_200_OK,
)
async def get_fir_history(
    icao_code: str,
    db: Session = Depends(get_db),
) -> List[FIRResponse]:
    """
    Get all FIR versions for an ICAO code ordered by version DESC.

    Returns complete version history for the specified ICAO code, with
    most recent version first.

    Validates Requirements: 7.2, 7.7

    Args:
        icao_code: ICAO code
        db: Database session (injected)

    Returns:
        List of FIR records ordered by version_number descending

    Raises:
        FIRNotFoundException: If no versions exist for icao_code (404)
    """
    start_time = time.time()

    try:
        fir_service = FIRService(db)
        firs = fir_service.get_fir_history(icao_code)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Retrieved FIR history for: {icao_code}",
            extra={
                "method": "GET",
                "path": f"/api/iata-firs/{icao_code}/history",
                "status_code": 200,
                "duration_ms": duration_ms,
                "icao_code": icao_code,
                "version_count": len(firs),
            },
        )

        return firs
    except FIRNotFoundException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"No FIR history found for: {icao_code}",
            extra={
                "method": "GET",
                "path": f"/api/iata-firs/{icao_code}/history",
                "status_code": 404,
                "duration_ms": duration_ms,
                "icao_code": icao_code,
            },
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to retrieve FIR history for {icao_code}: {str(e)}",
            extra={
                "method": "GET",
                "path": f"/api/iata-firs/{icao_code}/history",
                "status_code": 500,
                "duration_ms": duration_ms,
                "icao_code": icao_code,
                "error": str(e),
            },
        )
        raise


@router.post(
    "/iata-firs/{icao_code}/rollback",
    response_model=FIRResponse,
    status_code=status.HTTP_200_OK,
)
async def rollback_fir(
    icao_code: str,
    rollback_data: FIRRollbackRequest,
    db: Session = Depends(get_db),
) -> FIRResponse:
    """
    Rollback to a specified FIR version.

    Deactivates the current active version and activates the specified
    version number. The specified version must exist for the ICAO code.

    Validates Requirements: 7.3, 7.7

    Args:
        icao_code: ICAO code
        rollback_data: Rollback request with version_number
        db: Database session (injected)

    Returns:
        Activated FIR version

    Raises:
        FIRNotFoundException: If specified version doesn't exist (404)
    """
    start_time = time.time()

    try:
        fir_service = FIRService(db)
        fir = fir_service.rollback_fir(
            icao_code=icao_code,
            version_number=rollback_data.version_number,
        )

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Rolled back FIR for: {icao_code}",
            extra={
                "method": "POST",
                "path": f"/api/iata-firs/{icao_code}/rollback",
                "status_code": 200,
                "duration_ms": duration_ms,
                "icao_code": icao_code,
                "version_number": rollback_data.version_number,
            },
        )

        return fir
    except FIRNotFoundException:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            f"FIR version not found for rollback: {icao_code} v{rollback_data.version_number}",
            extra={
                "method": "POST",
                "path": f"/api/iata-firs/{icao_code}/rollback",
                "status_code": 404,
                "duration_ms": duration_ms,
                "icao_code": icao_code,
                "version_number": rollback_data.version_number,
            },
        )
        raise
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to rollback FIR for {icao_code}: {str(e)}",
            extra={
                "method": "POST",
                "path": f"/api/iata-firs/{icao_code}/rollback",
                "status_code": 500,
                "duration_ms": duration_ms,
                "icao_code": icao_code,
                "error": str(e),
            },
        )
        raise


@router.get(
    "/coverage-health",
    response_model=CoverageHealthResponse,
    status_code=status.HTTP_200_OK,
)
async def get_coverage_health(
    db: Session = Depends(get_db),
) -> CoverageHealthResponse:
    """
    Get FIR-formula coverage health data.

    Queries the vw_fir_formula_coverage view to return coverage metrics
    showing which active FIRs have formula coverage and which do not.

    Validates Requirements: 7.8

    Args:
        db: Database session (injected)

    Returns:
        Coverage health response with totals and per-FIR details
    """
    start_time = time.time()

    try:
        result = db.execute(
            text("SELECT icao_code, fir_name, country_code, has_formula, formula_description FROM vw_fir_formula_coverage ORDER BY icao_code")
        )
        rows = result.fetchall()

        details = []
        covered = 0
        uncovered = 0

        for row in rows:
            has_formula = bool(row.has_formula)
            if has_formula:
                covered += 1
            else:
                uncovered += 1

            details.append(
                CoverageDetail(
                    icao_code=row.icao_code,
                    fir_name=row.fir_name,
                    country_code=row.country_code,
                    has_formula=has_formula,
                    formula_description=row.formula_description,
                )
            )

        total = covered + uncovered

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "Retrieved coverage health data",
            extra={
                "method": "GET",
                "path": "/api/coverage-health",
                "status_code": 200,
                "duration_ms": duration_ms,
                "total_active_firs": total,
                "covered_firs": covered,
                "uncovered_firs": uncovered,
            },
        )

        return CoverageHealthResponse(
            total_active_firs=total,
            covered_firs=covered,
            uncovered_firs=uncovered,
            details=details,
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to retrieve coverage health: {str(e)}",
            extra={
                "method": "GET",
                "path": "/api/coverage-health",
                "status_code": 500,
                "duration_ms": duration_ms,
                "error": str(e),
            },
        )
        raise
