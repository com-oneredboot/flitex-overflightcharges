"""IataFir SQLAlchemy model for FIR boundary data."""

from sqlalchemy import Column, String, Boolean, DECIMAL, TIMESTAMP, func, Index
from sqlalchemy.dialects.postgresql import JSONB
from src.database import Base


class IataFir(Base):
    """
    SQLAlchemy model for IATA FIR (Flight Information Region) data.
    
    Stores FIR boundary information including GeoJSON geometry, bounding box
    coordinates, and avoidance status for overflight charge calculations.
    
    Validates Requirements: 1.6, 22.1, 22.2, 22.3
    """
    
    __tablename__ = "iata_firs"
    
    # Primary key
    icao_code = Column(String(4), primary_key=True, comment="ICAO code (4 uppercase alphanumeric)")
    
    # FIR identification
    fir_name = Column(String(255), nullable=False, comment="FIR name")
    country_code = Column(String(2), nullable=False, comment="ISO 3166-1 alpha-2 country code")
    country_name = Column(String(255), nullable=False, comment="Country name")
    
    # Geometry data
    geojson_geometry = Column(JSONB, nullable=False, comment="GeoJSON geometry for FIR boundary")
    
    # Bounding box coordinates
    bbox_min_lon = Column(DECIMAL(10, 6), comment="Minimum longitude of bounding box")
    bbox_min_lat = Column(DECIMAL(10, 6), comment="Minimum latitude of bounding box")
    bbox_max_lon = Column(DECIMAL(10, 6), comment="Maximum longitude of bounding box")
    bbox_max_lat = Column(DECIMAL(10, 6), comment="Maximum latitude of bounding box")
    
    # Status
    avoid_status = Column(Boolean, default=False, comment="Whether this FIR should be avoided")
    
    # Timestamps
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp"
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Record last update timestamp"
    )
    
    # Indexes (Requirements 22.1, 22.2, 22.3)
    __table_args__ = (
        Index("idx_iata_firs_country_code", "country_code"),
        Index("idx_iata_firs_avoid_status", "avoid_status"),
    )
    
    def __repr__(self) -> str:
        """String representation of IataFir model."""
        return (
            f"<IataFir(icao_code='{self.icao_code}', "
            f"fir_name='{self.fir_name}', "
            f"country_code='{self.country_code}')>"
        )
