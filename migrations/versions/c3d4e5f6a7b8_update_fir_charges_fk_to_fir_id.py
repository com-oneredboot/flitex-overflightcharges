"""update_fir_charges_fk_to_fir_id

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-14 12:00:00.000000

This migration updates the fir_charges table to reference iata_firs via
a UUID fir_id column instead of the old icao_code FK:

1. Add fir_id UUID column (nullable initially)
2. Populate fir_id by joining fir_charges.icao_code with iata_firs.icao_code
   WHERE iata_firs.is_active = TRUE
3. Make fir_id NOT NULL after backfill
4. Add FK constraint on fir_id referencing iata_firs.id
5. Add idx_fir_charges_fir_id index
6. Retain icao_code as denormalized non-FK column
7. Keep existing idx_fir_charges_icao_code index

Note: The FK constraint fk_fir_charges_icao_code was already dropped in
Migration 1 (a1b2c3d4e5f6), so icao_code is already a plain column here.

Requirements: 4.1, 4.2, 4.3, 4.4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add fir_id UUID FK to fir_charges referencing iata_firs.id.

    Steps:
    1. Add fir_id UUID column (nullable initially for backfill)
    2. Populate fir_id from existing icao_code join against iata_firs
    3. Make fir_id NOT NULL
    4. Add FK constraint on fir_id -> iata_firs.id
    5. Add idx_fir_charges_fir_id index
    """
    # Step 1: Add fir_id UUID column (nullable for backfill)
    op.add_column(
        'fir_charges',
        sa.Column(
            'fir_id',
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment='Reference to FIR UUID in iata_firs (Requirement 4.1)'
        )
    )

    # Step 2: Populate fir_id by joining on icao_code where is_active = TRUE
    op.execute("""
        UPDATE fir_charges
        SET fir_id = iata_firs.id
        FROM iata_firs
        WHERE fir_charges.icao_code = iata_firs.icao_code
          AND iata_firs.is_active = TRUE
    """)

    # Step 3: Make fir_id NOT NULL after backfill
    op.alter_column('fir_charges', 'fir_id', nullable=False)

    # Step 4: Add FK constraint on fir_id -> iata_firs.id
    op.create_foreign_key(
        'fk_fir_charges_fir_id',
        'fir_charges',
        'iata_firs',
        ['fir_id'],
        ['id']
    )

    # Step 5: Add index on fir_id for efficient joins
    op.create_index(
        'idx_fir_charges_fir_id',
        'fir_charges',
        ['fir_id'],
        unique=False
    )


def downgrade() -> None:
    """
    Remove fir_id column and its FK/index from fir_charges.

    Steps:
    1. Drop idx_fir_charges_fir_id index
    2. Drop FK constraint fk_fir_charges_fir_id
    3. Drop fir_id column
    """
    # Step 1: Drop index
    op.drop_index('idx_fir_charges_fir_id', table_name='fir_charges')

    # Step 2: Drop FK constraint
    op.drop_constraint('fk_fir_charges_fir_id', 'fir_charges', type_='foreignkey')

    # Step 3: Drop fir_id column
    op.drop_column('fir_charges', 'fir_id')
