"""SQLAlchemy models for QA route string testing schema.

Models for the QA regression testing harness: flight plans, test runs,
test run results, and manual review verdicts. All tables live in the
dedicated `qa` PostgreSQL schema.

Validates Requirements: 1.2, 2.1, 3.1, 4.1
"""

import uuid

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from src.database import Base


class QAFlightPlan(Base):
    """Reference ICAO flight plan data imported from Excel files.

    Maps to qa.flight_plans table. Stores real operational route strings
    used as test cases for the RouteParser QA harness.
    """

    __tablename__ = "flight_plans"
    __table_args__ = (
        UniqueConstraint("hash_code", name="uq_qa_flight_plans_hash_code"),
        Index("idx_qa_fp_departure", "departure_icao_aerodrome_code"),
        Index("idx_qa_fp_destination", "destination_aerodrome_code"),
        Index("idx_qa_fp_carrier", "operational_icao_carrier_code"),
        {"schema": "qa"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    scheduled_departure_dtmz = Column(TIMESTAMP)
    departure_icao_aerodrome_code = Column(String)
    operational_icao_carrier_code = Column(String)
    flight_number = Column(String)
    release_number = Column(Integer)
    aircraft_type = Column(String)
    icao_route = Column(Text)
    destination_aerodrome_code = Column(String)
    total_estimated_elapsed_time = Column(String)
    alternate_aerodrome_list = Column(Text)
    hash_code = Column(String)
    created_at = Column(TIMESTAMP, server_default=text("now()"))
    source_file = Column(String)

    def __repr__(self) -> str:
        return (
            f"<QAFlightPlan(id={self.id}, "
            f"departure={self.departure_icao_aerodrome_code}, "
            f"destination={self.destination_aerodrome_code})>"
        )


class QATestRun(Base):
    """Batch test execution record with code and data version tracking.

    Maps to qa.test_runs table. Each run processes all flight plans
    through the current RouteParser and records the git commit SHA
    and FIR boundary hash for traceability.
    """

    __tablename__ = "test_runs"
    __table_args__ = (
        Index("idx_qa_tr_timestamp", "run_timestamp"),
        {"schema": "qa"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commit_sha = Column(String)
    run_timestamp = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    notes = Column(Text)
    fir_boundary_hash = Column(String)
    status = Column(String, default="pending", server_default="pending")
    total_flight_plans = Column(Integer)
    completed_count = Column(Integer, default=0, server_default="0")
    failed_count = Column(Integer, default=0, server_default="0")
    created_by = Column(String)

    results = relationship("QATestRunResult", back_populates="test_run")

    def __repr__(self) -> str:
        return (
            f"<QATestRun(id={self.id}, "
            f"status={self.status}, "
            f"commit_sha={self.commit_sha})>"
        )


class QATestRunResult(Base):
    """Per-flight-plan parser output for a test run.

    Maps to qa.test_run_results table. Stores resolved waypoints,
    FIR crossings, and unresolved tokens as JSONB for queryability
    and cross-run comparison.
    """

    __tablename__ = "test_run_results"
    __table_args__ = (
        UniqueConstraint("test_run_id", "flight_plan_id", name="uq_qa_trr_run_plan"),
        Index("idx_qa_trr_run", "test_run_id"),
        Index("idx_qa_trr_plan", "flight_plan_id"),
        {"schema": "qa"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_run_id = Column(UUID(as_uuid=True), ForeignKey("qa.test_runs.id"))
    flight_plan_id = Column(Integer, ForeignKey("qa.flight_plans.id"))
    resolved_waypoints = Column(JSONB)
    fir_crossings = Column(JSONB)
    unresolved_tokens = Column(JSONB)
    parse_duration_ms = Column(Integer)
    error_message = Column(Text)
    health_status = Column(String)
    created_at = Column(TIMESTAMP, server_default=text("now()"))

    test_run = relationship("QATestRun", back_populates="results")
    flight_plan = relationship("QAFlightPlan")
    reviews = relationship("QATestRunReview", back_populates="result")

    def __repr__(self) -> str:
        return (
            f"<QATestRunResult(id={self.id}, "
            f"test_run_id={self.test_run_id}, "
            f"flight_plan_id={self.flight_plan_id})>"
        )


class QATestRunReview(Base):
    """Manual expert review verdict for a test run result.

    Maps to qa.test_run_reviews table. Each submission creates a new
    record to preserve review history; the latest review is determined
    by reviewed_at timestamp.
    """

    __tablename__ = "test_run_reviews"
    __table_args__ = (
        Index("idx_qa_rev_result", "test_run_result_id"),
        {"schema": "qa"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_run_result_id = Column(
        UUID(as_uuid=True), ForeignKey("qa.test_run_results.id")
    )
    verdict = Column(String)
    reviewer_notes = Column(Text)
    reviewed_by = Column(String)
    reviewed_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    result = relationship("QATestRunResult", back_populates="reviews")

    def __repr__(self) -> str:
        return (
            f"<QATestRunReview(id={self.id}, "
            f"verdict={self.verdict}, "
            f"reviewed_by={self.reviewed_by})>"
        )
