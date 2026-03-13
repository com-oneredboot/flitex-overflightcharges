"""add_regional_formula_support

Revision ID: cd9f343711ad
Revises: 2a8de75b4840
Create Date: 2026-03-12 18:08:49.539101

This migration adds support for regional formulas (EuroControl, Oceanic) by:
1. Adding a required 'description' field to identify all formulas
2. Making 'country_code' nullable to support regional formulas
3. Preserving all existing country formula data

Recovery: If this migration fails, run 'alembic downgrade -1' to restore
the previous schema state.

Requirements: 1.1, 1.2, 1.4, 2.1, 2.2, 3.5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Import country code mapping for data migration
import sys
from pathlib import Path

# Add src directory to path to import constants
# __file__ is migrations/versions/filename.py
# .parent.parent.parent gets us to repo root
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))

from constants.countries import COUNTRY_CODE_TO_NAME


# revision identifiers, used by Alembic.
revision: str = 'cd9f343711ad'
down_revision: Union[str, Sequence[str], None] = '2a8de75b4840'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema to support regional formulas.
    
    Steps:
    1. Add description column with temporary default
    2. Populate description for existing records using country code mapping
    3. Remove temporary default from description column
    4. Alter country_code column to nullable
    
    Requirements: 1.1, 1.2, 1.4, 2.1, 2.2, 3.5
    """
    # Step 1: Add description column as TEXT NOT NULL with temporary default
    # Using a temporary default allows us to add the NOT NULL column to a table with existing data
    op.add_column(
        'formulas',
        sa.Column('description', sa.Text(), nullable=False, server_default='TEMPORARY')
    )
    
    # Step 2: Populate description for existing records using country code mapping
    # Build CASE statement for all country codes in the mapping
    case_conditions = []
    for code, name in COUNTRY_CODE_TO_NAME.items():
        # Escape single quotes in country names for SQL
        escaped_name = name.replace("'", "''")
        case_conditions.append(f"WHEN country_code = '{code}' THEN '{escaped_name}'")
    
    # Add fallback for any unmapped country codes
    case_statement = f"""
        CASE 
            {' '.join(case_conditions)}
            ELSE 'Country: ' || country_code
        END
    """
    
    # Update all existing records with appropriate descriptions
    op.execute(f"""
        UPDATE formulas
        SET description = {case_statement}
        WHERE country_code IS NOT NULL
    """)
    
    # Step 3: Remove temporary default from description column
    # Now that all existing records have proper descriptions, remove the default
    op.alter_column('formulas', 'description', server_default=None)
    
    # Step 4: Alter country_code column to nullable
    # This allows regional formulas to have country_code = NULL
    op.alter_column('formulas', 'country_code', nullable=True)


def downgrade() -> None:
    """
    Downgrade schema to remove regional formula support.
    
    WARNING: This will DELETE all regional formulas (country_code=NULL).
    Ensure you have a backup before proceeding.
    
    Steps:
    1. Delete all records with country_code = NULL (regional formulas)
    2. Alter country_code back to NOT NULL
    3. Drop description column
    
    Requirements: 3.3, 3.4
    """
    # Step 1: Delete regional formulas (country_code = NULL)
    # We must do this before making country_code NOT NULL again
    result = op.execute("DELETE FROM formulas WHERE country_code IS NULL")
    
    # Step 2: Alter country_code back to NOT NULL
    op.alter_column('formulas', 'country_code', nullable=False)
    
    # Step 3: Drop description column
    op.drop_column('formulas', 'description')
