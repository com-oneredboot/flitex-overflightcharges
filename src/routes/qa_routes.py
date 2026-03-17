"""QA Route String Testing API endpoints.

This module provides REST API endpoints for the QA regression testing harness:
- POST /api/qa/flight-plans/import — Upload Excel file for flight plan import
- GET  /api/qa/flight-plans — List flight plans (paginated)
- POST /api/qa/test-runs — Create and execute a test run
- GET  /api/qa/test-runs — List test runs (paginated)
- POST /api/qa/test-runs/compare — Compare two runs
- GET  /api/qa/test-runs/{run_id} — Get run detail with results
- POST /api/qa/test-runs/{run_id}/results/{result_id}/reviews — Submit review
- GET  /api/qa/test-runs/{run_id}/export/csv — Export results as CSV
- GET  /api/qa/test-runs/{run_id}/export/xlsx — Export results as Excel

Validates Requirements: 5.1, 6.1, 7.1, 7.3, 8.1, 9.1, 9.2, 10.1
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas.qa import (
    FlightPlanImportResponse,
    FlightPlanListResponse,
    TestRunCreate,
    TestRunResponse,
    TestRunListResponse,
    TestRunDetailResponse,
    ReviewVerdictCreate,
    ReviewVerdictResponse,
    RunComparisonRequest,
    RunComparisonResponse,
)
from src.services.qa_service import (
    import_flight_plans,
    get_flight_plans,
    create_test_run,
    execute_test_run,
    get_test_runs,
    get_test_run_detail,
    submit_review,
    get_review_history,
    export_results_csv,
    export_results_xlsx,
    compare_runs,
    delete_test_run,
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/qa", tags=["QA Route String Testing"])


# ---------------------------------------------------------------------------
# Flight Plan endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/flight-plans/import",
    response_model=FlightPlanImportResponse,
    status_code=status.HTTP_200_OK,
)
async def import_flight_plans_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> FlightPlanImportResponse:
    """Upload an Excel file and import flight plans into the QA store.

    Validates Requirement: 5.1
    """
    try:
        result = import_flight_plans(file.file, db, source_filename=file.filename or "")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/flight-plans",
    response_model=FlightPlanListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_flight_plans(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> FlightPlanListResponse:
    """Return a paginated list of imported flight plans.

    Validates Requirement: 5.1
    """
    result = get_flight_plans(page, page_size, db)
    return FlightPlanListResponse(**result)


# ---------------------------------------------------------------------------
# Test Run endpoints
# NOTE: /compare MUST be defined BEFORE /{run_id} so FastAPI does not
#       interpret "compare" as a run_id path parameter.
# ---------------------------------------------------------------------------


@router.post(
    "/test-runs",
    response_model=TestRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_and_execute_test_run(
    body: TestRunCreate,
    db: Session = Depends(get_db),
) -> TestRunResponse:
    """Create a new test run and execute it against all flight plans.

    Validates Requirements: 6.1
    """
    run = create_test_run(body.notes, body.created_by, db)
    run = execute_test_run(str(run.id), db)

    # Build review stats for the response
    from sqlalchemy import func
    from src.models.qa import QATestRunResult, QATestRunReview

    total_results = (
        db.query(func.count(QATestRunResult.id))
        .filter(QATestRunResult.test_run_id == run.id)
        .scalar()
    ) or 0

    reviewed_count = (
        db.query(func.count(func.distinct(QATestRunReview.test_run_result_id)))
        .join(QATestRunResult, QATestRunReview.test_run_result_id == QATestRunResult.id)
        .filter(QATestRunResult.test_run_id == run.id)
        .scalar()
    ) or 0

    # Health status breakdown
    health_rows = (
        db.query(QATestRunResult.health_status, func.count(QATestRunResult.id))
        .filter(QATestRunResult.test_run_id == run.id)
        .group_by(QATestRunResult.health_status)
        .all()
    )
    health_counts = {row[0]: row[1] for row in health_rows}

    return TestRunResponse(
        id=str(run.id),
        commit_sha=run.commit_sha or "",
        run_timestamp=run.run_timestamp,
        status=run.status or "pending",
        total_flight_plans=run.total_flight_plans or 0,
        completed_count=run.completed_count or 0,
        failed_count=run.failed_count or 0,
        notes=run.notes,
        fir_boundary_hash=run.fir_boundary_hash,
        created_by=run.created_by,
        reviewed_count=reviewed_count,
        total_results=total_results,
        pass_count=health_counts.get("pass", 0),
        warning_count=health_counts.get("warning", 0),
        fail_count=health_counts.get("fail", 0),
    )


@router.get(
    "/test-runs",
    response_model=TestRunListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_test_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> TestRunListResponse:
    """Return a paginated list of test runs ordered by timestamp descending.

    Validates Requirement: 7.1
    """
    result = get_test_runs(page, page_size, db)
    return TestRunListResponse(**result)


@router.post(
    "/test-runs/compare",
    response_model=RunComparisonResponse,
    status_code=status.HTTP_200_OK,
)
async def compare_test_runs(
    body: RunComparisonRequest,
    db: Session = Depends(get_db),
) -> RunComparisonResponse:
    """Compare two test runs and return categorized differences.

    Validates Requirement: 10.1
    """
    try:
        result = compare_runs(body.run_id_1, body.run_id_2, db)
        return RunComparisonResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/test-runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_test_run_endpoint(
    run_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete a test run and all its results and reviews."""
    try:
        delete_test_run(run_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/test-runs/{run_id}",
    response_model=TestRunDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_test_run_detail_endpoint(
    run_id: str,
    verdict: str | None = Query(None),
    has_error: bool | None = Query(None),
    departure: str | None = Query(None),
    destination: str | None = Query(None),
    health_status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=10000),
    db: Session = Depends(get_db),
) -> TestRunDetailResponse:
    """Return detailed results for a specific test run with optional filters.

    Validates Requirements: 7.1, 7.3
    """
    try:
        result = get_test_run_detail(
            run_id, db,
            verdict=verdict,
            has_error=has_error,
            departure=departure,
            destination=destination,
            health_status=health_status,
            page=page,
            page_size=page_size,
        )
        return TestRunDetailResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/test-runs/{run_id}/results/{result_id}/reviews",
    response_model=ReviewVerdictResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_review_endpoint(
    run_id: str,
    result_id: str,
    body: ReviewVerdictCreate,
    db: Session = Depends(get_db),
) -> ReviewVerdictResponse:
    """Submit a review verdict for a specific test run result.

    Validates Requirement: 8.1
    """
    try:
        review = submit_review(
            result_id,
            body.verdict,
            body.reviewer_notes,
            body.reviewed_by,
            db,
        )
        return ReviewVerdictResponse(
            id=str(review.id),
            test_run_result_id=str(review.test_run_result_id),
            verdict=review.verdict,
            reviewer_notes=review.reviewer_notes,
            reviewed_by=review.reviewed_by,
            reviewed_at=review.reviewed_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/test-runs/{run_id}/results/{result_id}/reviews",
    response_model=list[ReviewVerdictResponse],
    status_code=status.HTTP_200_OK,
)
async def get_review_history_endpoint(
    run_id: str,
    result_id: str,
    db: Session = Depends(get_db),
) -> list[ReviewVerdictResponse]:
    """Return all review records for a test run result, newest first."""
    reviews = get_review_history(result_id, db)
    return [
        ReviewVerdictResponse(
            id=str(r.id),
            test_run_result_id=str(r.test_run_result_id),
            verdict=r.verdict,
            reviewer_notes=r.reviewer_notes,
            reviewed_by=r.reviewed_by,
            reviewed_at=r.reviewed_at,
        )
        for r in reviews
    ]


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------


@router.get("/test-runs/{run_id}/export/csv", status_code=status.HTTP_200_OK)
async def export_csv_endpoint(
    run_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Export test run results as a downloadable CSV file.

    Validates Requirement: 9.1
    """
    try:
        csv_output = export_results_csv(run_id, db)
        return StreamingResponse(
            csv_output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=test_run_{run_id}.csv"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/test-runs/{run_id}/export/xlsx", status_code=status.HTTP_200_OK)
async def export_xlsx_endpoint(
    run_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Export test run results as a downloadable Excel file.

    Validates Requirement: 9.2
    """
    try:
        xlsx_output = export_results_xlsx(run_id, db)
        return StreamingResponse(
            xlsx_output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=test_run_{run_id}.xlsx"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
