"""OverflightChargesAnomaly SQLAlchemy model for anomaly baselines.

Statistical baselines per origin→destination pair for anomaly detection,
built from LLM assessments and historical calculations.

Validates Requirements: 14.1
"""

from sqlalchemy import Column, String, Integer, DECIMAL, TIMESTAMP, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB

import uuid
from src.database import Base


class OverflightChargesAnomaly(Base):
    """
    SQLAlchemy model for overflight charges anomaly baselines.

    Stores expected FIR count range, expected total charge range, and
    expected FIR sequence patterns per origin→destination pair. Initially
    seeded from LLM assessments, then progressively weighted with
    statistical data as calculation volume increases.

    Maps to calculations.overflight_charges_anomalies table.

    Validates Requirements: 14.1
    """

    __tablename__ = "overflight_charges_anomalies"
    __table_args__ = (
        # Unique index on (origin, destination)
        Index(
            "idx_anomalies_origin_destination",
            "origin",
            "destination",
            unique=True,
        ),
        {"schema": "calculations"},
    )

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Internal primary key",
    )

    # Route pair
    origin = Column(
        String(4),
        nullable=False,
        comment="Origin airport ICAO code",
    )
    destination = Column(
        String(4),
        nullable=False,
        comment="Destination airport ICAO code",
    )

    # Expected FIR count range
    expected_fir_count_min = Column(
        Integer,
        nullable=True,
        comment="Minimum expected FIR count",
    )
    expected_fir_count_max = Column(
        Integer,
        nullable=True,
        comment="Maximum expected FIR count",
    )

    # Expected charge range (USD)
    expected_charge_min = Column(
        DECIMAL(12, 2),
        nullable=True,
        comment="Minimum expected total charge (USD)",
    )
    expected_charge_max = Column(
        DECIMAL(12, 2),
        nullable=True,
        comment="Maximum expected total charge (USD)",
    )

    # Expected FIR sequence patterns
    expected_fir_sequence = Column(
        JSONB,
        nullable=True,
        comment="Expected FIR sequence patterns",
    )

    # Baseline tracking
    sample_count = Column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of calculations in baseline",
    )
    baseline_source = Column(
        String(20),
        nullable=False,
        server_default="llm",
        comment="Source: llm, statistical, hybrid",
    )

    # Timestamps
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last update timestamp",
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp",
    )

    def __repr__(self) -> str:
        """String representation of OverflightChargesAnomaly model."""
        return (
            f"<OverflightChargesAnomaly(id='{self.id}', "
            f"origin='{self.origin}', "
            f"destination='{self.destination}', "
            f"sample_count={self.sample_count})>"
        )
