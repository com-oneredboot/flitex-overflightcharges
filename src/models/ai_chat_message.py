"""AIChatMessage SQLAlchemy model for AI chat messages.

Stores follow-up chat messages and AI responses linked to an AI review
session. Each message has a role ("user" or "assistant"), message text,
and an optional prompt field for assistant messages containing the Ollama
prompt used to generate the response.

Validates Requirements: 8.4, 8.5
"""

from sqlalchemy import Column, String, Text, TIMESTAMP, Index, func
from sqlalchemy.dialects.postgresql import UUID

import uuid
from src.database import Base


class AIChatMessage(Base):
    """
    SQLAlchemy model for AI chat messages.

    Persists follow-up chat messages and AI responses linked to an AI
    review session via session_id. User messages store the message text,
    while assistant messages also store the Ollama prompt used to generate
    the response.

    Maps to calculations.ai_chat_messages table.

    Validates Requirements: 8.4, 8.5
    """

    __tablename__ = "ai_chat_messages"
    __table_args__ = (
        # Index on session_id for efficient retrieval of chat history
        Index("idx_ai_chat_messages_session_id", "session_id"),
        {"schema": "calculations"},
    )

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Internal primary key",
    )

    # External message identifier (unique)
    message_id = Column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="External message identifier",
    )

    # Link to AI review session
    session_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Links to ai_review_sessions.session_id",
    )

    # Message role: "user" or "assistant"
    role = Column(
        String(10),
        nullable=False,
        comment='Message role: "user" or "assistant"',
    )

    # Message content
    message = Column(
        Text,
        nullable=False,
        comment="Message content",
    )

    # Ollama prompt (for assistant messages only)
    prompt = Column(
        Text,
        nullable=True,
        comment="Ollama prompt for assistant messages only",
    )

    # Timestamp
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Message timestamp",
    )

    def __repr__(self) -> str:
        """String representation of AIChatMessage model."""
        return (
            f"<AIChatMessage(id='{self.id}', "
            f"message_id='{self.message_id}', "
            f"session_id='{self.session_id}', "
            f"role='{self.role}')>"
        )
