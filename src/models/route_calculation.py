"""RouteCalculation SQLAlchemy model for calculation audit trail."""

from sqlalchemy import Column, String, Text, Integer, Date, DECIMAL, TIMESTAMP, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from src.database import Base


class RouteCalculation(Base):
    """
    SQLAlchemy model for route cost calculation audit trail.
    
    Stores all route cost calculations for compliance and auditing purposes,
    including route details, aircraft information, and calculated costs.
    
    Validates Requirements: 6.2, 22.7, 22.8, 22.9
    """
    
    __tablename__ = "route_calculations"
    
    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for calculation record"
    )
    
    # Route information
    route_string = Column(
        Text,
        nullable=False,
        comment="ICAO-formatted flight route specification"
    )
    origin = Column(
        String(4),
        nullable=False,
        comment="Origin airport ICAO code"
    )
    destination = Column(
        String(4),
        nullable=False,
        comment="Destination airport ICAO code"
    )
    
    # Aircraft information
    aircraft_type = Column(
        String(10),
        nullable=False,
        comment="Aircraft type code"
    )
    mtow_kg = Column(
        DECIMAL(10, 2),
        nullable=False,
        comment="Maximum Takeoff Weight in kilograms"
    )
    
    # Calculation results
    total_cost = Column(
        DECIMAL(12, 2),
        nullable=False,
        comment="Total calculated overflight charge"
    )
    currency = Column(
        String(3),
        nullable=False,
        comment="ISO 4217 currency code"
    )
    
    # Timestamp
    calculation_timestamp = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When the calculation was performed",
    )

    # Session linkage FK (Requirement 11.4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "calculations.overflight_calculation_sessions.calculation_id",
        ),
        nullable=True,
        comment="FK to calculations.overflight_calculation_sessions",
    )

    # Flight info columns
    flight_number = Column(
        String(20),
        nullable=True,
        comment="Flight number",
    )
    flight_date = Column(
        Date,
        nullable=True,
        comment="Flight date",
    )

    # Distance columns
    total_distance_km = Column(
        DECIMAL(12, 4),
        nullable=True,
        comment="Total route distance in km",
    )
    total_distance_nm = Column(
        DECIMAL(12, 4),
        nullable=True,
        comment="Total route distance in nm",
    )
    fir_count = Column(
        Integer,
        nullable=True,
        comment="Number of FIRs crossed",
    )

    # Relationships
    session = relationship(
        "OverflightCalculationSession",
        foreign_keys=[session_id],
    )
    
    # Indexes (Requirements 22.7, 22.8, 22.9)
    __table_args__ = (
        # Index on calculation_timestamp for time-range queries (Requirement 22.7)
        Index("idx_route_calculations_timestamp", "calculation_timestamp"),
        
        # Index on origin for origin-based lookups (Requirement 22.8)
        Index("idx_route_calculations_origin", "origin"),
        
        # Index on destination for destination-based lookups (Requirement 22.9)
        Index("idx_route_calculations_destination", "destination"),

        # Index on session_id for session-based lookups (Requirement 11.4)
        Index("idx_route_calculations_session_id", "session_id"),
    )
    
    def __repr__(self) -> str:
        """String representation of RouteCalculation model."""
        return (
            f"<RouteCalculation(id='{self.id}', "
            f"origin='{self.origin}', "
            f"destination='{self.destination}', "
            f"total_cost={self.total_cost})>"
        )
