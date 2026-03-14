"""drop_country_name_update_fir_name

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-15 10:00:00.000000

This migration removes the redundant country_name column from iata_firs and
updates all fir_name values to the descriptive format
"{Country Name} FIR ({ICAO Code})" using pycountry lookup from country_code.

Steps (upgrade):
1. Drop vw_fir_formula_coverage view (depends on country_name column)
2. Update all fir_name values to descriptive format via pycountry
3. Drop country_name column from iata_firs
4. Recreate vw_fir_formula_coverage without country_name

Steps (downgrade):
1. Drop updated view
2. Add country_name VARCHAR(255) NOT NULL DEFAULT '' back
3. Recreate original view with country_name

Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 4.1, 4.2
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _resolve_country_name(country_code: str) -> str:
    """Resolve a country_code to a country name via pycountry.

    Falls back to the country_code itself if unresolvable.
    Imports pycountry lazily to avoid module-level dependency.
    """
    import pycountry
    country = pycountry.countries.get(alpha_2=country_code)
    if country:
        return country.name
    return country_code


def upgrade() -> None:
    """
    Drop country_name column, update fir_name to descriptive format,
    and recreate coverage view without country_name.

    Requirements: 1.1, 2.1, 2.2, 2.3, 4.1
    """
    # Step 1: Drop the vw_fir_formula_coverage view
    # Must drop before removing country_name column since the view references it
    op.execute("DROP VIEW IF EXISTS vw_fir_formula_coverage;")

    # Step 2: Update all fir_name values to descriptive format
    # Batch by country_code, using SQL concatenation for per-row icao_code
    conn = op.get_bind()
    codes = conn.execute(
        sa.text("SELECT DISTINCT country_code FROM iata_firs WHERE country_code IS NOT NULL")
    ).fetchall()

    for row in codes:
        code = row[0]
        country_name = _resolve_country_name(code)
        # Use SQL concatenation so each row gets its own icao_code in the name
        conn.execute(
            sa.text(
                "UPDATE iata_firs SET fir_name = :prefix || icao_code || ')' "
                "WHERE country_code = :code"
            ),
            {"prefix": f"{country_name} FIR (", "code": code},
        )

    # Step 3: Drop the country_name column from iata_firs
    op.drop_column('iata_firs', 'country_name')

    # Step 4: Recreate vw_fir_formula_coverage without country_name
    op.execute("""
        CREATE OR REPLACE VIEW vw_fir_formula_coverage AS
        SELECT
            f.icao_code,
            f.fir_name,
            f.country_code,
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
    Restore country_name column and original coverage view.

    Requirements: 1.2, 4.2
    """
    # Step 1: Drop the updated view
    op.execute("DROP VIEW IF EXISTS vw_fir_formula_coverage;")

    # Step 2: Add country_name column back
    op.add_column(
        'iata_firs',
        sa.Column('country_name', sa.VARCHAR(255), nullable=False, server_default='')
    )

    # Step 3: Recreate original view with country_name
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
