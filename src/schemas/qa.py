"""Pydantic schemas for QA Route String Testing data validation.

Validates Requirements: 2.3, 4.2, 5.4, 7.2, 10.2, 10.3
"""

from enum import Enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class FlightPlanImportResponse(BaseModel):
    """Summary of a flight plan Excel import operation.

    Validates Requirement: 5.4
    """

    total_rows: int
    imported: int
    skipped: int


class FlightPlanResponse(BaseModel):
    """Response schema for a single flight plan record."""

    id: int
    scheduled_departure_dtmz: Optional[datetime] = None
    departure_icao_aerodrome_code: Optional[str] = None
    destination_aerodrome_code: Optional[str] = None
    operational_icao_carrier_code: Optional[str] = None
    flight_number: Optional[str] = None
    release_number: Optional[int] = None
    aircraft_type: Optional[str] = None
    icao_route: Optional[str] = None
    total_estimated_elapsed_time: Optional[str] = None
    alternate_aerodrome_list: Optional[str] = None
    hash_code: Optional[str] = None
    created_at: Optional[datetime] = None
    source_file: Optional[str] = None

    model_config = {"from_attributes": True}


class FlightPlanListResponse(BaseModel):
    """Paginated list of flight plans."""

    items: list[FlightPlanResponse]
    total: int
    page: int
    page_size: int


class TestRunCreate(BaseModel):
    """Request schema for creating a new test run.

    Validates Requirement: 6.1
    """

    notes: Optional[str] = None
    created_by: Optional[str] = None


class TestRunResponse(BaseModel):
    """Response schema for a test run record.

    Validates Requirement: 7.2
    """

    id: str
    commit_sha: str
    run_timestamp: datetime
    status: str
    total_flight_plans: int
    completed_count: int
    failed_count: int
    notes: Optional[str] = None
    fir_boundary_hash: Optional[str] = None
    created_by: Optional[str] = None
    reviewed_count: int
    total_results: int
    pass_count: int = 0
    warning_count: int = 0
    fail_count: int = 0

    model_config = {"from_attributes": True}


class TestRunListResponse(BaseModel):
    """Paginated list of test runs.

    Validates Requirement: 7.1
    """

    items: list[TestRunResponse]
    total: int
    page: int
    page_size: int


class TestRunResultResponse(BaseModel):
    """Response schema for a single test run result.

    Validates Requirement: 7.2
    """

    id: str
    flight_plan_id: int
    departure_icao_aerodrome_code: Optional[str] = None
    destination_aerodrome_code: Optional[str] = None
    operational_icao_carrier_code: Optional[str] = None
    flight_number: Optional[str] = None
    icao_route: Optional[str] = None
    resolved_waypoints: Optional[list] = None
    fir_crossings: Optional[list] = None
    unresolved_tokens: Optional[list] = None
    parse_duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    health_status: Optional[str] = None
    latest_verdict: Optional[str] = None
    latest_reviewer_notes: Optional[str] = None

    model_config = {"from_attributes": True}


class TestRunDetailResponse(BaseModel):
    """Detailed test run response with paginated results.

    Validates Requirement: 7.3
    """

    run: TestRunResponse
    results: list[TestRunResultResponse]
    total_results: int
    page: int
    page_size: int


class ReviewVerdictCreate(BaseModel):
    """Request schema for submitting a review verdict.

    Validates Requirements: 4.2, 8.1
    """

    verdict: str
    reviewer_notes: Optional[str] = None
    reviewed_by: str

    @field_validator("verdict")
    @classmethod
    def validate_verdict(cls, v: str) -> str:
        """Validate verdict is one of the allowed values.

        Validates Requirement: 4.2
        """
        allowed = {"correct", "incorrect", "needs_investigation"}
        if v.lower() not in allowed:
            raise ValueError(f"verdict must be one of: {', '.join(allowed)}")
        return v.lower()


class ReviewVerdictResponse(BaseModel):
    """Response schema for a review verdict record.

    Validates Requirement: 8.2
    """

    id: str
    test_run_result_id: str
    verdict: str
    reviewer_notes: Optional[str] = None
    reviewed_by: str
    reviewed_at: datetime

    model_config = {"from_attributes": True}


class ComparisonCategory(str, Enum):
    """Categories for run comparison results.

    Validates Requirement: 10.2
    """

    unchanged = "unchanged"
    improved = "improved"
    regressed = "regressed"
    changed = "changed"


class ComparisonItem(BaseModel):
    """Per-flight-plan comparison detail between two runs.

    Validates Requirement: 10.2
    """

    flight_plan_id: int
    departure_icao_aerodrome_code: Optional[str] = None
    destination_aerodrome_code: Optional[str] = None
    icao_route: Optional[str] = None
    category: ComparisonCategory
    diff_details: Optional[dict] = None


class RunComparisonRequest(BaseModel):
    """Request schema for comparing two test runs.

    Validates Requirement: 10.1
    """

    run_id_1: str
    run_id_2: str


class RunComparisonResponse(BaseModel):
    """Response schema for a run comparison report.

    Validates Requirements: 10.2, 10.3
    """

    run_1_id: str
    run_2_id: str
    summary: dict
    items: list[ComparisonItem]
