"""FirCharge SQLAlchemy model for per-FIR charge breakdown."""

from sqlalchemy import Column, String, DECIMAL, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from src.database import Base


class FirCharge(Base):
    """
    SQLAlchemy model for per-FIR charge breakdown.
    
    Stores individual FIR charges for each route calculation, providing
    detailed breakdown of overflight charges by FIR region. Links to
    specific FIR versions via fir_id UUID FK; retains icao_code as
    denormalized display column.
    
    Validates Requirements: 4.1, 4.2, 4.3, 4.4, 6.3, 6.4, 22.10, 22.11, 22.12, 22.13
    """
    
    __tablename__ = "fir_charges"
    
    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for FIR charge record"
    )
    
    # Foreign keys
    calculation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("route_calculations.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to parent route calculation (Requirement 22.13)"
    )
    fir_id = Column(
        UUID(as_uuid=True),
        ForeignKey("iata_firs.id"),
        nullable=False,
        comment="Reference to FIR UUID (Requirement 4.1)"
    )
    icao_code = Column(
        String(4),
        nullable=False,
        comment="Denormalized ICAO code for display (Requirement 4.2)"
    )
    
    # FIR information
    fir_name = Column(
        String(255),
        nullable=False,
        comment="FIR name for display purposes"
    )
    country_code = Column(
        String(2),
        nullable=False,
        comment="ISO 3166-1 alpha-2 country code"
    )
    
    # Charge information
    charge_amount = Column(
        DECIMAL(12, 2),
        nullable=False,
        comment="Calculated charge for this FIR"
    )
    currency = Column(
        String(3),
        nullable=False,
        comment="ISO 4217 currency code"
    )
    
    # Relationships
    calculation = relationship(
        "RouteCalculation",
        backref="fir_charges",
        foreign_keys=[calculation_id]
    )
    fir = relationship(
        "IataFir",
        foreign_keys=[fir_id]
    )
    
    # Indexes (Requirements 22.10, 22.11, 22.12, 4.4)
    __table_args__ = (
        # Index on calculation_id for joining with route_calculations (Requirement 22.10)
        Index("idx_fir_charges_calculation_id", "calculation_id"),
        
        # Index on icao_code for FIR-based charge lookups (Requirement 22.11)
        Index("idx_fir_charges_icao_code", "icao_code"),
        
        # Index on country_code for country-based charge analysis (Requirement 22.12)
        Index("idx_fir_charges_country_code", "country_code"),
        
        # Index on fir_id for FIR UUID lookups (Requirement 4.4)
        Index("idx_fir_charges_fir_id", "fir_id"),
    )
    
    def __repr__(self) -> str:
        """String representation of FirCharge model."""
        return (
            f"<FirCharge(id='{self.id}', "
            f"icao_code='{self.icao_code}', "
            f"fir_name='{self.fir_name}', "
            f"charge_amount={self.charge_amount})>"
        )
