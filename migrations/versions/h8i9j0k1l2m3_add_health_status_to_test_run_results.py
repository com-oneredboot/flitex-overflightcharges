"""add_health_status_to_test_run_results

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-03-16 23:30:00.000000

Adds a health_status column to qa.test_run_results for efficient filtering.
Values: 'pass', 'warning', 'fail'. Backfills existing rows based on the
same logic used in the frontend:
  - fail: error_message IS NOT NULL OR resolved == 0 OR unresolved ratio > 0.2
  - pass: no error, resolved > 0, unresolved == 0
  - warning: everything else (no error, resolved > 0, 0 < ratio <= 0.2)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h8i9j0k1l2m3'
down_revision: Union[str, Sequence[str], None] = 'g7h8i9j0k1l2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the column
    op.add_column(
        'test_run_results',
        sa.Column('health_status', sa.String(), nullable=True),
        schema='qa',
    )

    # Add index for filtering
    op.create_index(
        'idx_qa_trr_health_status',
        'test_run_results',
        ['health_status'],
        schema='qa',
    )

    # Backfill existing rows
    op.execute("""
        UPDATE qa.test_run_results
        SET health_status = CASE
            WHEN error_message IS NOT NULL THEN 'fail'
            WHEN COALESCE(jsonb_array_length(resolved_waypoints), 0) = 0 THEN 'fail'
            WHEN COALESCE(jsonb_array_length(unresolved_tokens), 0) = 0 THEN 'pass'
            WHEN COALESCE(jsonb_array_length(unresolved_tokens), 0)::float
                 / NULLIF(
                     COALESCE(jsonb_array_length(resolved_waypoints), 0)
                     + COALESCE(jsonb_array_length(unresolved_tokens), 0),
                     0
                 ) > 0.2 THEN 'fail'
            ELSE 'warning'
        END
    """)


def downgrade() -> None:
    op.drop_index('idx_qa_trr_health_status', table_name='test_run_results', schema='qa')
    op.drop_column('test_run_results', 'health_status', schema='qa')
