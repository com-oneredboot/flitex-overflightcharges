"""create_vw_fir_formula_coverage_view

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-14 13:00:00.000000

This migration creates the vw_fir_formula_coverage PostgreSQL view that
joins active FIRs with active formulas on country_code to identify
FIRs missing formula coverage:

1. LEFT JOIN ensures uncovered FIRs appear with has_formula=FALSE
2. Only active FIRs (is_active=TRUE) and active formulas (is_active=TRUE)
3. Columns: icao_code, fir_name, country_code, country_name, has_formula,
   formula_description

Requirements: 9.1, 9.2, 9.3, 9.4
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create vw_fir_formula_coverage view.

    The view LEFT JOINs active FIRs with active formulas on country_code
    so that uncovered FIRs appear with has_formula=FALSE and
    formula_description=NULL.
    """
    op.execute("""
        CREATE OR REPLACE VIEW vw_fir_formula_coverage AS
        SELECT
            f.icao_code,
            f.fir_name,
            f.country_code,
            f.country_name,
            CASE WHEN fm.id IS NOT NULL THEN TRUE ELSE FALSE END AS has_formula,
            fm.description AS formula_description
        FROM iata_firs f
        LEFT JOIN formulas fm
            ON f.country_code = fm.country_code
            AND fm.is_active = TRUE
        WHERE f.is_active = TRUE;
    """)


def downgrade() -> None:
    """
    Drop vw_fir_formula_coverage view.
    """
    op.execute("DROP VIEW IF EXISTS vw_fir_formula_coverage;")
