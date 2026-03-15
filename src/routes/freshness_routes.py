"""Data freshness API endpoint.

Provides a GET endpoint to check the staleness of EUROCONTROL unit rate
data, the current AIRAC cycle, and FIR boundary summary information.

- GET /api/data-freshness — Return freshness status for all data sources

Validates Requirements: 15.1, 15.2, 15.3
"""

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.services.freshness_checker import FreshnessChecker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Data Freshness"])


@router.get(
    "/api/data-freshness",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Data freshness status retrieved successfully"},
        500: {"description": "Internal error while checking freshness"},
    },
)
async def check_data_freshness(
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Check staleness of EUROCONTROL unit rates, AIRAC cycle, and FIR boundaries.

    Delegates to ``FreshnessChecker.check_freshness`` which queries the
    database for the latest unit rate period, derives the current AIRAC
    cycle, and summarises FIR boundary data.

    Returns:
        JSON with ``unit_rates``, ``airac_cycle``, and ``fir_boundaries``
        sections.

    Validates Requirements: 15.1, 15.2, 15.3
    """
    try:
        checker = FreshnessChecker()
        result = checker.check_freshness(db)
        return JSONResponse(status_code=200, content=result)
    except Exception as exc:
        logger.error(
            "Data freshness check failed: %s",
            str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc),
                "detail": "Failed to check data freshness",
            },
        )
