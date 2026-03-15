"""TokenActionReason SQLAlchemy model for token action reason codes.

Reference table storing all reason codes used by the Route_Parser to
describe why a specific action was taken on a route token.

Validates Requirements: 20.2, 20.4
"""

from sqlalchemy import Column, String, Text, TIMESTAMP, func

from src.database import Base


class TokenActionReason(Base):
    """
    SQLAlchemy model for token action reason codes.

    Immutable reference table seeded with all reason codes used by the
    Route_Parser. Each reason code has a human-readable description and
    an action type (resolved, skipped, expanded, unresolved).

    Maps to calculations.token_action_reasons table.

    Validates Requirements: 20.2, 20.4
    """

    __tablename__ = "token_action_reasons"
    __table_args__ = {"schema": "calculations"}

    # Primary key
    reason_code = Column(
        String(50),
        primary_key=True,
        comment="Reason code identifier (e.g. AIRWAY_DESIGNATOR)",
    )

    # Action type
    action = Column(
        String(20),
        nullable=False,
        comment="Action type: resolved, skipped, expanded, unresolved",
    )

    # Human-readable description
    description = Column(
        Text,
        nullable=False,
        comment="Human-readable explanation of the reason code",
    )

    # Timestamp
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp",
    )

    def __repr__(self) -> str:
        """String representation of TokenActionReason model."""
        return (
            f"<TokenActionReason(reason_code='{self.reason_code}', "
            f"action='{self.action}')>"
        )
