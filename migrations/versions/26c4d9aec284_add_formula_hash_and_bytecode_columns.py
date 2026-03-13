"""add_formula_hash_and_bytecode_columns

Revision ID: 26c4d9aec284
Revises: cd9f343711ad
Create Date: 2026-03-13 03:54:22.140022

This migration adds support for Python formula execution system by:
1. Adding formula_hash column for duplicate detection (SHA256 hash)
2. Adding formula_bytecode column for compiled Python bytecode storage
3. Creating index on formula_hash for efficient duplicate lookups

Requirements: 1.1, 11.7, 11.10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '26c4d9aec284'
down_revision: Union[str, Sequence[str], None] = 'cd9f343711ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema to support Python formula execution.
    
    Steps:
    1. Add formula_hash column (String(64)) for SHA256 hash storage
    2. Add formula_bytecode column (LargeBinary) for compiled bytecode
    3. Create index on formula_hash for duplicate detection
    
    Requirements: 1.1, 11.7, 11.10
    """
    # Step 1: Add formula_hash column
    # Nullable for backward compatibility with existing formulas
    op.add_column(
        'formulas',
        sa.Column(
            'formula_hash',
            sa.String(64),
            nullable=True,
            comment='SHA256 hash of formatted formula code for duplicate detection'
        )
    )
    
    # Step 2: Add formula_bytecode column
    # Nullable for backward compatibility with existing formulas
    op.add_column(
        'formulas',
        sa.Column(
            'formula_bytecode',
            sa.LargeBinary,
            nullable=True,
            comment='Compiled Python bytecode for formula execution'
        )
    )
    
    # Step 3: Create index on formula_hash for efficient duplicate detection
    op.create_index(
        'idx_formulas_hash',
        'formulas',
        ['formula_hash'],
        unique=False
    )


def downgrade() -> None:
    """
    Downgrade schema to remove Python formula execution support.
    
    Steps:
    1. Drop index on formula_hash
    2. Drop formula_bytecode column
    3. Drop formula_hash column
    """
    # Step 1: Drop index
    op.drop_index('idx_formulas_hash', table_name='formulas')
    
    # Step 2: Drop formula_bytecode column
    op.drop_column('formulas', 'formula_bytecode')
    
    # Step 3: Drop formula_hash column
    op.drop_column('formulas', 'formula_hash')
