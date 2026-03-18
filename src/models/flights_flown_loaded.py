"""SQLAlchemy model for the flights_flown_loaded table.

Read-only model used by the overflight-charges service to query
file load audit records. The table is owned/populated by the
flights-flown-ingestion service.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.database import Base


class FlightsFlownLoaded(Base):
    """Audit records from the flights_flown_loaded table (read-only).

    Each record represents a single file submission and tracks the
    complete processing lifecycle from submission through completion
    or failure.
    """

    __tablename__ = "flights_flown_loaded"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique process identifier",
    )
    filename = Column(
        String(255),
        nullable=False,
        comment="Original filename submitted for processing",
    )
    file_hash = Column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hash of file contents for duplicate detection",
    )
    file_size_bytes = Column(
        Integer,
        nullable=False,
        comment="File size in bytes",
    )
    status = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Processing status: pending, validating, parsing, completed, duplicate, failed",
    )
    error_message = Column(
        Text,
        nullable=True,
        comment="Error details if processing failed",
    )
    records_processed = Column(
        Integer,
        nullable=True,
        comment="Count of records successfully inserted into flights_flown_data",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when record was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when record was last updated",
    )
    processing_started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when processing began",
    )
    processing_completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when processing finished (success or failure)",
    )
    linked_to_original_id = Column(
        UUID(as_uuid=True),
        ForeignKey("flights_flown_loaded.id"),
        nullable=True,
        comment="Reference to original record if this is a duplicate file submission",
    )

    def __repr__(self) -> str:
        return (
            f"<FlightsFlownLoaded(id={self.id}, filename='{self.filename}', "
            f"status='{self.status}', records_processed={self.records_processed})>"
        )
