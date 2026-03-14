"""Formula SQLAlchemy model for country-specific charge formulas."""

from sqlalchemy import Column, String, Text, Date, Integer, Boolean, TIMESTAMP, func, Index, UniqueConstraint, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
import uuid
from src.database import Base


class Formula(Base):
    """
    SQLAlchemy model for country-specific overflight charge formulas.
    
    Stores formula logic with version history tracking, supporting multiple
    versions per country with exactly one active version at any time.
    
    Validates Requirements: 3.6, 21.5, 22.4, 22.5, 22.6
    """
    
    __tablename__ = "formulas"
    
    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for formula record"
    )
    
    # Formula identification
    country_code = Column(
        String(2),
        nullable=True,  # Changed to support regional formulas
        comment="ISO 3166-1 alpha-2 country code (NULL for regional formulas)"
    )
    description = Column(
        Text,
        nullable=False,
        comment="Human-readable description (country name or region name)"
    )
    formula_code = Column(
        String(50),
        nullable=False,
        comment="Formula code identifier"
    )
    
    # Formula logic
    formula_logic = Column(
        Text,
        nullable=False,
        comment="Python code for charge calculation"
    )
    
    # Effective date and currency
    effective_date = Column(
        Date,
        nullable=False,
        comment="Date when formula becomes effective"
    )
    currency = Column(
        String(3),
        nullable=False,
        comment="ISO 4217 currency code"
    )
    
    # Version tracking
    version_number = Column(
        Integer,
        nullable=False,
        comment="Version number for this formula (starts at 1)"
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this version is currently active"
    )
    
    # Activation/deactivation timestamps (standard versioned column set)
    activation_date = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="System timestamp when this version became active"
    )
    deactivation_date = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="System timestamp when this version was deactivated"
    )
    
    # Audit fields
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp"
    )
    created_by = Column(
        String(255),
        nullable=False,
        comment="User who created this formula version"
    )
    
    # Python formula execution fields (Requirements 1.1, 11.7, 11.10)
    formula_hash = Column(
        String(64),
        nullable=True,  # Nullable for backward compatibility
        comment="SHA256 hash of formatted formula code for duplicate detection"
    )
    formula_bytecode = Column(
        LargeBinary,
        nullable=True,  # Nullable for backward compatibility
        comment="Compiled Python bytecode for formula execution"
    )
    
    # Indexes and constraints (Requirements 22.4, 22.5, 22.6)
    __table_args__ = (
        # Composite index for active formula lookups (Requirement 22.4)
        Index("idx_formulas_country_active", "country_code", "is_active"),
        
        # Index on version_number for version-based queries (Requirement 22.5)
        Index("idx_formulas_version", "version_number"),
        
        # Index on created_at for time-based queries (Requirement 22.6)
        Index("idx_formulas_created_at", "created_at"),
        
        # Index on formula_hash for duplicate detection (Requirements 11.7, 11.10)
        Index("idx_formulas_hash", "formula_hash"),
        
        # Unique constraint on (country_code, version_number)
        UniqueConstraint("country_code", "version_number", name="unique_country_version"),
        
        # Unique partial constraint: only one active formula per country
        # PostgreSQL syntax: UNIQUE (country_code, is_active) WHERE is_active = TRUE
        Index(
            "unique_active_formula",
            "country_code",
            "is_active",
            unique=True,
            postgresql_where=(Column("is_active") == True)
        ),
    )
    
    def __repr__(self) -> str:
        """String representation of Formula model."""
        return (
            f"<Formula(id='{self.id}', "
            f"country_code='{self.country_code}', "
            f"version_number={self.version_number}, "
            f"is_active={self.is_active})>"
        )
    def is_regional(self) -> bool:
        """
        Check if this is a regional formula.

        Returns:
            True if country_code is None (regional formula), False otherwise

        Validates: Requirement 6.3
        """
        return self.country_code is None

    def is_country_specific(self) -> bool:
        """
        Check if this is a country-specific formula.

        Returns:
            True if country_code is not None (country formula), False otherwise

        Validates: Requirement 6.3
        """
        return self.country_code is not None

