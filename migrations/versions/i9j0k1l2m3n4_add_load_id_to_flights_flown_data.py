"""add_load_id_to_flights_flown_data

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-03-17 10:00:00.000000

Adds a nullable load_id UUID column to flights_flown_data with a foreign key
referencing flights_flown_loaded.id and an index for efficient filtering.
This links each flight record to the file import that created it.

Requirements: 1.1, 1.2, 1.3, 1.4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'i9j0k1l2m3n4'
down_revision: Union[str, Sequence[str], None] = 'h8i9j0k1l2m3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add load_id column to flights_flown_data.

    Steps:
    1. Add nullable load_id UUID column
    2. Create foreign key constraint to flights_flown_loaded.id
    3. Create index for efficient load_id filtering
    """
    op.add_column(
        'flights_flown_data',
        sa.Column('load_id', UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_flights_flown_data_load_id',
        'flights_flown_data',
        'flights_flown_loaded',
        ['load_id'],
        ['id'],
    )
    op.create_index(
        'ix_flights_flown_data_load_id',
        'flights_flown_data',
        ['load_id'],
    )


def downgrade() -> None:
    """
    Remove load_id column from flights_flown_data.

    Steps:
    1. Drop index on load_id
    2. Drop foreign key constraint
    3. Drop load_id column
    """
    op.drop_index('ix_flights_flown_data_load_id', table_name='flights_flown_data')
    op.drop_constraint('fk_flights_flown_data_load_id', 'flights_flown_data', type_='foreignkey')
    op.drop_column('flights_flown_data', 'load_id')
