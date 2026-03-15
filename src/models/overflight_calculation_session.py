"""OverflightCalculationSession SQLAlchemy model for calculation sessions.

Stores complete calculation session objects as JSONB with indexed columns
for efficient querying by flight, route, and time.

Validates Requirements: 11.1, 21.6
"""

from sqlalchemy import Column, String, Date, DECIMAL, TIMESTAMP, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB

import uuid
from src.database import Base


class OverflightCalculationSession(Base):
    """
    SQLAlchemy model for overflight calculation sessions.

    Primary storage for calculation sessions. The session_data JSONB column
    contains the complete Calculation Session object. Indexed columns enable
    efficient querying by calculation_id, flight number/date, origin/destination,
    and creation time.

    Maps to calculations.overflight_calculation_sessions table.

    Validates Requirements: 11.1, 11.2, 21.6
    """

    __tablename__ = "overflight_calculation_sessions"
    __table_args__ = (
        # Composite index on (flight_number, flight_date) for flight-based lookups
        Index(
            "idx_calc_sessions_flight_number_date",
            "flight_number",
            "flight_date",
        ),
        # Composite index on (origin, destination) for route-based lookups
        Index(
            "idx_calc_sessions_origin_destination",
            "origin",
            "destination",
        ),
        # Index on created_at for time-range queries
        Index("idx_calc_sessions_created_at", "created_at"),
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
    calculation_id = Column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
        comment="External session identifier (unique, used as FK target)",
    )

    # Session type: planned or flown (Requirement 21.6)
    session_type = Column(
        String(20),
        nullable=False,
        server_default="planned",
        comment="Session type: planned or flown (Requirement 21.6)",
    )

    # Complete Calculation Session JSON
    session_data = Column(
        JSONB,
        nullable=False,
        comment="Complete Calculation Session JSON object",
    )

    # Indexed query columns
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
    flight_number = Column(
        String(20),
        nullable=True,
        comment="Flight number for matching",
    )
    flight_date = Column(
        Date,
        nullable=True,
        comment="Flight date for matching",
    )
    aircraft_type = Column(
        String(10),
        nullable=False,
        comment="Aircraft type code",
    )
    mtow_kg = Column(
        DECIMAL(10, 2),
        nullable=False,
        comment="Maximum Takeoff Weight in kilograms",
    )
    calculator_version = Column(
        String(20),
        nullable=False,
        comment="Calculator version string",
    )
    user_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User who triggered calculation",
    )

    # Timestamp
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp",
    )

    def __repr__(self) -> str:
        """String representation of OverflightCalculationSession model."""
        return (
            f"<OverflightCalculationSession(id='{self.id}', "
            f"calculation_id='{self.calculation_id}', "
            f"origin='{self.origin}', "
            f"destination='{self.destination}')>"
        )
