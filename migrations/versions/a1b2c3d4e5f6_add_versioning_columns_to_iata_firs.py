"""add_versioning_columns_to_iata_firs

Revision ID: a1b2c3d4e5f6
Revises: 26c4d9aec284
Create Date: 2026-03-14 10:00:00.000000

This migration converts iata_firs from a simple ICAO-code-keyed schema to a
UUID-based versioned schema matching the formulas table pattern:

1. Add UUID `id` column as new primary key
2. Add versioning columns: version_number, is_active, effective_date,
   activation_date, deactivation_date, created_by
3. Drop `updated_at` column (versioned rows are immutable)
4. Convert PK from icao_code to id
5. Add partial unique index unique_active_fir on (icao_code, is_active)
   WHERE is_active = TRUE
6. Add unique constraint unique_icao_version on (icao_code, version_number)
7. Backfill existing rows with version_number=1, is_active=True,
   created_by='system-migration', activation_date=now()

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 2.1, 2.2, 2.3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '26c4d9aec284'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade iata_firs to versioned schema with UUID primary key.

    Steps:
    1. Drop FK from fir_charges.icao_code -> iata_firs.icao_code
    2. Drop existing PK on icao_code
    3. Add UUID id column with generated default
    4. Add versioning columns
    5. Backfill existing rows
    6. Set NOT NULL constraints after backfill
    7. Add new PK on id
    8. Re-create FK from fir_charges.icao_code -> iata_firs.icao_code (temporary)
    9. Drop updated_at column
    10. Add indexes and constraints
    """
    # Step 1: Drop FK constraint from fir_charges referencing iata_firs.icao_code
    # This must be done before we can change the PK on iata_firs
    op.drop_constraint('fk_fir_charges_icao_code', 'fir_charges', type_='foreignkey')

    # Step 2: Drop existing PK on icao_code
    op.drop_constraint('pk_iata_firs', 'iata_firs', type_='primary')

    # Step 3: Add UUID id column with server-side default
    op.add_column(
        'iata_firs',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            nullable=True,
            server_default=sa.text('gen_random_uuid()'),
            comment='Unique identifier for FIR record'
        )
    )

    # Backfill id for existing rows
    op.execute("UPDATE iata_firs SET id = gen_random_uuid() WHERE id IS NULL")

    # Make id NOT NULL
    op.alter_column('iata_firs', 'id', nullable=False)

    # Step 4: Add versioning columns (nullable initially for backfill)
    op.add_column(
        'iata_firs',
        sa.Column(
            'version_number',
            sa.Integer(),
            nullable=True,
            comment='Version number for this FIR (starts at 1 per ICAO code)'
        )
    )
    op.add_column(
        'iata_firs',
        sa.Column(
            'is_active',
            sa.Boolean(),
            nullable=True,
            server_default=sa.text('true'),
            comment='Whether this version is currently active'
        )
    )
    op.add_column(
        'iata_firs',
        sa.Column(
            'effective_date',
            sa.Date(),
            nullable=True,
            comment='Business date when this FIR version takes effect'
        )
    )
    op.add_column(
        'iata_firs',
        sa.Column(
            'activation_date',
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment='System timestamp when this version became active'
        )
    )
    op.add_column(
        'iata_firs',
        sa.Column(
            'deactivation_date',
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment='System timestamp when this version was deactivated'
        )
    )
    op.add_column(
        'iata_firs',
        sa.Column(
            'created_by',
            sa.String(255),
            nullable=True,
            comment='User who created this FIR version'
        )
    )

    # Step 5: Backfill existing rows with versioning defaults
    op.execute("""
        UPDATE iata_firs
        SET version_number = 1,
            is_active = TRUE,
            created_by = 'system-migration',
            activation_date = now()
        WHERE version_number IS NULL
    """)

    # Step 6: Set NOT NULL constraints after backfill
    op.alter_column('iata_firs', 'version_number', nullable=False)
    op.alter_column('iata_firs', 'is_active', nullable=False)
    op.alter_column('iata_firs', 'created_by', nullable=False)

    # Step 7: Add new PK on id
    op.create_primary_key('pk_iata_firs', 'iata_firs', ['id'])

    # Step 8: Re-create FK from fir_charges.icao_code -> iata_firs.icao_code
    # This is temporary — Migration 3 will replace this with fir_id UUID FK.
    # We need a unique constraint on icao_code for the FK to reference.
    # Since existing data has one row per icao_code (all version_number=1, is_active=True),
    # the partial unique index will serve this purpose once created.
    # However, a plain FK requires a unique constraint, so we use the
    # unique_icao_version constraint (icao_code, version_number) is not sufficient
    # for a single-column FK. Instead, we skip re-creating the FK here —
    # Migration 3 will handle the FK transition to fir_id.

    # Step 9: Drop updated_at column (versioned rows are immutable)
    op.drop_column('iata_firs', 'updated_at')

    # Step 10: Add indexes and constraints

    # Unique constraint on (icao_code, version_number)
    op.create_unique_constraint(
        'unique_icao_version',
        'iata_firs',
        ['icao_code', 'version_number']
    )

    # Partial unique index: only one active FIR per ICAO code
    op.create_index(
        'unique_active_fir',
        'iata_firs',
        ['icao_code', 'is_active'],
        unique=True,
        postgresql_where=sa.text('is_active = true')
    )

    # Note: idx_iata_firs_country_code and idx_iata_firs_avoid_status
    # already exist from the initial migration — no need to recreate them.


def downgrade() -> None:
    """
    Downgrade iata_firs back to simple ICAO-code-keyed schema.

    Steps:
    1. Drop indexes and constraints added in upgrade
    2. Add updated_at column back
    3. Drop PK on id
    4. Drop versioning columns
    5. Drop id column
    6. Re-create PK on icao_code
    7. Re-create FK from fir_charges.icao_code -> iata_firs.icao_code

    WARNING: This will DELETE all non-v1 FIR versions. Only the original
    version_number=1 rows are preserved. Ensure you have a backup.
    """
    # Delete any rows that are not the original version (version_number > 1)
    op.execute("DELETE FROM iata_firs WHERE version_number > 1")

    # Step 1: Drop indexes and constraints
    op.drop_index('unique_active_fir', table_name='iata_firs',
                   postgresql_where=sa.text('is_active = true'))
    op.drop_constraint('unique_icao_version', 'iata_firs', type_='unique')

    # Step 2: Add updated_at column back
    op.add_column(
        'iata_firs',
        sa.Column(
            'updated_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='Record last update timestamp'
        )
    )

    # Step 3: Drop PK on id
    op.drop_constraint('pk_iata_firs', 'iata_firs', type_='primary')

    # Step 4: Drop versioning columns
    op.drop_column('iata_firs', 'created_by')
    op.drop_column('iata_firs', 'deactivation_date')
    op.drop_column('iata_firs', 'activation_date')
    op.drop_column('iata_firs', 'effective_date')
    op.drop_column('iata_firs', 'is_active')
    op.drop_column('iata_firs', 'version_number')

    # Step 5: Drop id column
    op.drop_column('iata_firs', 'id')

    # Step 6: Re-create PK on icao_code
    op.create_primary_key('pk_iata_firs', 'iata_firs', ['icao_code'])

    # Step 7: Re-create FK from fir_charges.icao_code -> iata_firs.icao_code
    op.create_foreign_key(
        'fk_fir_charges_icao_code',
        'fir_charges',
        'iata_firs',
        ['icao_code'],
        ['icao_code']
    )
