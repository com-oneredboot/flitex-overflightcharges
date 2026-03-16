"""AIReviewSession SQLAlchemy model for AI review sessions.

Stores multi-persona AI review sessions including aggregated summaries,
charge comparisons, persona prompts, raw Ollama responses, and parsed
multi-persona results as JSONB. Linked to overflight calculation sessions
via calculation_id.

Validates Requirements: 8.1, 8.3
"""

from sqlalchemy import Column, String, Date, TIMESTAMP, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB

import uuid
from src.database import Base


class AIReviewSession(Base):
    """
    SQLAlchemy model for AI review sessions.

    Persists the complete AI review session data including the aggregated
    summary from all wizard steps, per-FIR charge comparison, persona
    prompts sent to Ollama, raw Ollama responses, and the parsed
    multi-persona result. Each regeneration creates a new record with
    a new session_id but the same calculation_id.

    Maps to calculations.ai_review_sessions table.

    Validates Requirements: 8.1, 8.3
    """

    __tablename__ = "ai_review_sessions"
    __table_args__ = (
        # Composite index on (flight_number, flight_date) for flight-based lookups
        Index(
            "idx_ai_review_sessions_flight_number_date",
            "flight_number",
            "flight_date",
        ),
        # Index on created_at for time-range queries
        Index("idx_ai_review_sessions_created_at", "created_at"),
        {"schema": "calculations"},
    )

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Internal primary key",
    )

    # External session identifier (unique)
    session_id = Column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
        comment="External session identifier",
    )

    # Link to overflight calculation session
    calculation_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Links to overflight_calculation_sessions.calculation_id",
    )

    # Flight identifiers for efficient lookups
    flight_number = Column(
        String(20),
        nullable=True,
        comment="Flight number for efficient lookups",
    )
    flight_date = Column(
        Date,
        nullable=True,
        comment="Flight date for efficient lookups",
    )

    # JSONB data columns
    aggregated_summary = Column(
        JSONB,
        nullable=False,
        comment="Complete Aggregated_Summary from all wizard steps",
    )
    charge_comparison = Column(
        JSONB,
        nullable=False,
        comment="Per-FIR charge comparison data",
    )
    persona_prompts = Column(
        JSONB,
        nullable=False,
        comment="Prompt text sent per persona to Ollama",
    )
    raw_responses = Column(
        JSONB,
        nullable=False,
        comment="Raw Ollama response per persona",
    )
    multi_persona_result = Column(
        JSONB,
        nullable=False,
        comment="Parsed Multi_Persona_Result",
    )

    # Timestamp
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp",
    )

    def __repr__(self) -> str:
        """String representation of AIReviewSession model."""
        return (
            f"<AIReviewSession(id='{self.id}', "
            f"session_id='{self.session_id}', "
            f"calculation_id='{self.calculation_id}')>"
        )
