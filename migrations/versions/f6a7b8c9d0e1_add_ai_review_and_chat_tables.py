"""add_ai_review_and_chat_tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-16 10:00:00.000000

This migration creates the AI review session and chat message tables in the
calculations schema for persisting multi-persona AI analysis results and
follow-up chat conversations:

1. calculations.ai_review_sessions - Stores aggregated summaries, charge
   comparisons, persona prompts, raw Ollama responses, and parsed
   multi-persona results for each AI review session.

2. calculations.ai_chat_messages - Stores follow-up chat messages and AI
   responses linked to review sessions.

Requirements: 8.1, 8.4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create ai_review_sessions and ai_chat_messages tables in calculations schema.

    Tables:
    1. ai_review_sessions - Multi-persona AI review session data
    2. ai_chat_messages - Follow-up chat messages linked to sessions

    Requirements: 8.1, 8.4
    """
    # Create ai_review_sessions table
    op.create_table(
        'ai_review_sessions',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text('gen_random_uuid()'),
            comment='Internal primary key'
        ),
        sa.Column(
            'session_id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment='External session identifier'
        ),
        sa.Column(
            'calculation_id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment='Links to overflight_calculation_sessions.calculation_id'
        ),
        sa.Column(
            'flight_number',
            sa.String(20),
            nullable=True,
            comment='Flight number for efficient lookups'
        ),
        sa.Column(
            'flight_date',
            sa.Date(),
            nullable=True,
            comment='Flight date for efficient lookups'
        ),
        sa.Column(
            'aggregated_summary',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment='Complete Aggregated_Summary from all wizard steps'
        ),
        sa.Column(
            'charge_comparison',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment='Per-FIR charge comparison data'
        ),
        sa.Column(
            'persona_prompts',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment='Prompt text sent per persona to Ollama'
        ),
        sa.Column(
            'raw_responses',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment='Raw Ollama response per persona'
        ),
        sa.Column(
            'multi_persona_result',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment='Parsed Multi_Persona_Result'
        ),
        sa.Column(
            'created_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='Record creation timestamp'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_review_sessions')),
        schema='calculations'
    )

    # Create indexes for ai_review_sessions
    op.create_index(
        'idx_ai_review_sessions_session_id',
        'ai_review_sessions',
        ['session_id'],
        unique=True,
        schema='calculations'
    )
    op.create_index(
        'idx_ai_review_sessions_calculation_id',
        'ai_review_sessions',
        ['calculation_id'],
        unique=False,
        schema='calculations'
    )
    op.create_index(
        'idx_ai_review_sessions_flight_number_date',
        'ai_review_sessions',
        ['flight_number', 'flight_date'],
        unique=False,
        schema='calculations'
    )
    op.create_index(
        'idx_ai_review_sessions_created_at',
        'ai_review_sessions',
        ['created_at'],
        unique=False,
        schema='calculations'
    )

    # Create ai_chat_messages table
    op.create_table(
        'ai_chat_messages',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text('gen_random_uuid()'),
            comment='Internal primary key'
        ),
        sa.Column(
            'message_id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment='External message identifier'
        ),
        sa.Column(
            'session_id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment='Links to ai_review_sessions.session_id'
        ),
        sa.Column(
            'role',
            sa.String(10),
            nullable=False,
            comment='Message role: "user" or "assistant"'
        ),
        sa.Column(
            'message',
            sa.Text(),
            nullable=False,
            comment='Message content'
        ),
        sa.Column(
            'prompt',
            sa.Text(),
            nullable=True,
            comment='Ollama prompt for assistant messages only'
        ),
        sa.Column(
            'created_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='Message timestamp'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_chat_messages')),
        schema='calculations'
    )

    # Create indexes for ai_chat_messages
    op.create_index(
        'idx_ai_chat_messages_message_id',
        'ai_chat_messages',
        ['message_id'],
        unique=True,
        schema='calculations'
    )
    op.create_index(
        'idx_ai_chat_messages_session_id',
        'ai_chat_messages',
        ['session_id'],
        unique=False,
        schema='calculations'
    )


def downgrade() -> None:
    """
    Drop ai_chat_messages and ai_review_sessions tables.

    Tables are dropped in reverse order to respect any potential
    future foreign key constraints.
    """
    # Drop ai_chat_messages indexes and table
    op.drop_index(
        'idx_ai_chat_messages_session_id',
        table_name='ai_chat_messages',
        schema='calculations'
    )
    op.drop_index(
        'idx_ai_chat_messages_message_id',
        table_name='ai_chat_messages',
        schema='calculations'
    )
    op.drop_table('ai_chat_messages', schema='calculations')

    # Drop ai_review_sessions indexes and table
    op.drop_index(
        'idx_ai_review_sessions_created_at',
        table_name='ai_review_sessions',
        schema='calculations'
    )
    op.drop_index(
        'idx_ai_review_sessions_flight_number_date',
        table_name='ai_review_sessions',
        schema='calculations'
    )
    op.drop_index(
        'idx_ai_review_sessions_calculation_id',
        table_name='ai_review_sessions',
        schema='calculations'
    )
    op.drop_index(
        'idx_ai_review_sessions_session_id',
        table_name='ai_review_sessions',
        schema='calculations'
    )
    op.drop_table('ai_review_sessions', schema='calculations')
