"""IataFir SQLAlchemy model for FIR boundary data with versioning support."""

from sqlalchemy import (
    Column, String, Boolean, Integer, Date, DECIMAL, TIMESTAMP,
    func, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from src.database import Base


class IataFir(Base):
    """
    SQLAlchemy model for IATA FIR (Flight Information Region) data.

    Stores FIR boundary information including GeoJSON geometry, bounding box
    coordinates, and avoidance status for overflight charge calculations.
    Uses UUID primary key with full version history tracking — rows are
    immutable once created (no updated_at column).

    Validates Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 2.1
    """

    __tablename__ = "iata_firs"

    # Primary key (Requirement 1.1)
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for FIR record",
    )

    # FIR identification (Requirement 1.2)
    icao_code = Column(
        String(4),
        nullable=False,
        index=True,
        comment="ICAO code (4 uppercase alphanumeric)",
    )
    fir_name = Column(String(255), nullable=False, comment="FIR name")
    country_code = Column(
        String(2), nullable=False, comment="ISO 3166-1 alpha-2 country code"
    )

    # Geometry data (Requirement 1.8)
    geojson_geometry = Column(
        JSONB, nullable=False, comment="GeoJSON geometry for FIR boundary"
    )

    # Bounding box coordinates (Requirement 1.8)
    bbox_min_lon = Column(DECIMAL(10, 6), comment="Minimum longitude of bounding box")
    bbox_min_lat = Column(DECIMAL(10, 6), comment="Minimum latitude of bounding box")
    bbox_max_lon = Column(DECIMAL(10, 6), comment="Maximum longitude of bounding box")
    bbox_max_lat = Column(DECIMAL(10, 6), comment="Maximum latitude of bounding box")

    # Status (Requirement 1.8)
    avoid_status = Column(
        Boolean, default=False, comment="Whether this FIR should be avoided"
    )

    # Versioning columns — standard set (Requirements 1.3, 1.4, 1.5, 1.6, 1.7)
    version_number = Column(
        Integer,
        nullable=False,
        comment="Version number for this FIR (starts at 1)",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this version is currently active",
    )
    effective_date = Column(
        Date,
        nullable=True,
        comment="Business date when this FIR version takes effect",
    )
    activation_date = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="System timestamp when this version became active",
    )
    deactivation_date = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="System timestamp when this version was deactivated",
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp",
    )
    created_by = Column(
        String(255),
        nullable=False,
        comment="User who created this FIR version",
    )

    # NO updated_at — rows are immutable (Requirement 1.9)

    # Indexes and constraints (Requirements 1.10, 2.1)
    __table_args__ = (
        # Unique constraint on (icao_code, version_number) (Requirement 1.10)
        UniqueConstraint(
            "icao_code", "version_number", name="unique_icao_version"
        ),
        # Partial unique index: only one active FIR per ICAO code (Requirement 2.1)
        Index(
            "unique_active_fir",
            "icao_code",
            "is_active",
            unique=True,
            postgresql_where=(Column("is_active") == True),
        ),
        # Index on country_code for coverage view joins
        Index("idx_iata_firs_country_code", "country_code"),
        # Index on avoid_status for filtering
        Index("idx_iata_firs_avoid_status", "avoid_status"),
    )

    def __repr__(self) -> str:
        """String representation of IataFir model."""
        return (
            f"<IataFir(id='{self.id}', "
            f"icao_code='{self.icao_code}', "
            f"fir_name='{self.fir_name}', "
            f"version_number={self.version_number}, "
            f"is_active={self.is_active})>"
        )
