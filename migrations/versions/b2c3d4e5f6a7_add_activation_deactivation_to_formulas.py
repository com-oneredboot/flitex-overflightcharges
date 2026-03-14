"""add_activation_deactivation_to_formulas

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-14 11:00:00.000000

This migration adds activation_date and deactivation_date columns to the
formulas table, aligning it with the standard versioned column set shared
by both iata_firs and formulas:

1. Add nullable activation_date TIMESTAMP(timezone=True) column
2. Add nullable deactivation_date TIMESTAMP(timezone=True) column

Both columns are nullable for backward compatibility — no data loss, no backfill needed.

Requirements: 6.1, 6.2, 6.3, 6.6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add activation_date and deactivation_date to formulas table.

    Both columns are nullable TIMESTAMP(timezone=True) for backward
    compatibility with existing formula rows.

    Requirements: 6.1, 6.2, 6.6
    """
    op.add_column(
        'formulas',
        sa.Column(
            'activation_date',
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment='System timestamp when this version became active'
        )
    )

    op.add_column(
        'formulas',
        sa.Column(
            'deactivation_date',
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment='System timestamp when this version was deactivated'
        )
    )


def downgrade() -> None:
    """
    Remove activation_date and deactivation_date from formulas table.
    """
    op.drop_column('formulas', 'deactivation_date')
    op.drop_column('formulas', 'activation_date')
