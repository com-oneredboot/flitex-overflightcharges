"""Initial schema

Revision ID: 2a8de75b4840
Revises: 
Create Date: 2026-03-12 07:03:18.008345

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2a8de75b4840'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Create flitex-overflightcharges tables."""
    
    # Create iata_firs table (Requirements 1.6, 22.1, 22.2, 22.3)
    op.create_table(
        'iata_firs',
        sa.Column('icao_code', sa.String(length=4), nullable=False, comment='ICAO code (4 uppercase alphanumeric)'),
        sa.Column('fir_name', sa.String(length=255), nullable=False, comment='FIR name'),
        sa.Column('country_code', sa.String(length=2), nullable=False, comment='ISO 3166-1 alpha-2 country code'),
        sa.Column('country_name', sa.String(length=255), nullable=False, comment='Country name'),
        sa.Column('geojson_geometry', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='GeoJSON geometry for FIR boundary'),
        sa.Column('bbox_min_lon', sa.DECIMAL(precision=10, scale=6), nullable=True, comment='Minimum longitude of bounding box'),
        sa.Column('bbox_min_lat', sa.DECIMAL(precision=10, scale=6), nullable=True, comment='Minimum latitude of bounding box'),
        sa.Column('bbox_max_lon', sa.DECIMAL(precision=10, scale=6), nullable=True, comment='Maximum longitude of bounding box'),
        sa.Column('bbox_max_lat', sa.DECIMAL(precision=10, scale=6), nullable=True, comment='Maximum latitude of bounding box'),
        sa.Column('avoid_status', sa.Boolean(), nullable=True, server_default=sa.text('false'), comment='Whether this FIR should be avoided'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Record creation timestamp'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Record last update timestamp'),
        sa.PrimaryKeyConstraint('icao_code', name=op.f('pk_iata_firs'))
    )
    
    # Create indexes for iata_firs (Requirements 22.1, 22.2, 22.3)
    op.create_index('idx_iata_firs_country_code', 'iata_firs', ['country_code'], unique=False)
    op.create_index('idx_iata_firs_avoid_status', 'iata_firs', ['avoid_status'], unique=False)
    
    # Create formulas table (Requirements 3.6, 21.5, 22.4, 22.5, 22.6)
    op.create_table(
        'formulas',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()'), comment='Unique identifier for formula record'),
        sa.Column('country_code', sa.String(length=2), nullable=False, comment='ISO 3166-1 alpha-2 country code'),
        sa.Column('formula_code', sa.String(length=50), nullable=False, comment='Formula code identifier'),
        sa.Column('formula_logic', sa.Text(), nullable=False, comment='Python code for charge calculation'),
        sa.Column('effective_date', sa.Date(), nullable=False, comment='Date when formula becomes effective'),
        sa.Column('currency', sa.String(length=3), nullable=False, comment='ISO 4217 currency code'),
        sa.Column('version_number', sa.Integer(), nullable=False, comment='Version number for this formula (starts at 1)'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='Whether this version is currently active'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Record creation timestamp'),
        sa.Column('created_by', sa.String(length=255), nullable=False, comment='User who created this formula version'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_formulas')),
        sa.UniqueConstraint('country_code', 'version_number', name='unique_country_version')
    )
    
    # Create indexes for formulas (Requirements 22.4, 22.5, 22.6)
    op.create_index('idx_formulas_country_active', 'formulas', ['country_code', 'is_active'], unique=False)
    op.create_index('idx_formulas_version', 'formulas', ['version_number'], unique=False)
    op.create_index('idx_formulas_created_at', 'formulas', ['created_at'], unique=False)
    
    # Create unique partial index for active formulas (only one active per country)
    op.create_index(
        'unique_active_formula',
        'formulas',
        ['country_code', 'is_active'],
        unique=True,
        postgresql_where=sa.text('is_active = true')
    )
    
    # Create route_calculations table (Requirements 6.2, 22.7, 22.8, 22.9)
    op.create_table(
        'route_calculations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()'), comment='Unique identifier for calculation record'),
        sa.Column('route_string', sa.Text(), nullable=False, comment='ICAO-formatted flight route specification'),
        sa.Column('origin', sa.String(length=4), nullable=False, comment='Origin airport ICAO code'),
        sa.Column('destination', sa.String(length=4), nullable=False, comment='Destination airport ICAO code'),
        sa.Column('aircraft_type', sa.String(length=10), nullable=False, comment='Aircraft type code'),
        sa.Column('mtow_kg', sa.DECIMAL(precision=10, scale=2), nullable=False, comment='Maximum Takeoff Weight in kilograms'),
        sa.Column('total_cost', sa.DECIMAL(precision=12, scale=2), nullable=False, comment='Total calculated overflight charge'),
        sa.Column('currency', sa.String(length=3), nullable=False, comment='ISO 4217 currency code'),
        sa.Column('calculation_timestamp', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='When the calculation was performed'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_route_calculations'))
    )
    
    # Create indexes for route_calculations (Requirements 22.7, 22.8, 22.9)
    op.create_index('idx_route_calculations_timestamp', 'route_calculations', ['calculation_timestamp'], unique=False)
    op.create_index('idx_route_calculations_origin', 'route_calculations', ['origin'], unique=False)
    op.create_index('idx_route_calculations_destination', 'route_calculations', ['destination'], unique=False)
    
    # Create fir_charges table (Requirements 6.3, 6.4, 22.10, 22.11, 22.12, 22.13, 22.14)
    op.create_table(
        'fir_charges',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()'), comment='Unique identifier for FIR charge record'),
        sa.Column('calculation_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Reference to parent route calculation (Requirement 22.13)'),
        sa.Column('icao_code', sa.String(length=4), nullable=False, comment='Reference to FIR ICAO code (Requirement 22.14)'),
        sa.Column('fir_name', sa.String(length=255), nullable=False, comment='FIR name for display purposes'),
        sa.Column('country_code', sa.String(length=2), nullable=False, comment='ISO 3166-1 alpha-2 country code'),
        sa.Column('charge_amount', sa.DECIMAL(precision=12, scale=2), nullable=False, comment='Calculated charge for this FIR'),
        sa.Column('currency', sa.String(length=3), nullable=False, comment='ISO 4217 currency code'),
        sa.ForeignKeyConstraint(['calculation_id'], ['route_calculations.id'], name=op.f('fk_fir_charges_calculation_id'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['icao_code'], ['iata_firs.icao_code'], name=op.f('fk_fir_charges_icao_code')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_fir_charges'))
    )
    
    # Create indexes for fir_charges (Requirements 22.10, 22.11, 22.12)
    op.create_index('idx_fir_charges_calculation_id', 'fir_charges', ['calculation_id'], unique=False)
    op.create_index('idx_fir_charges_icao_code', 'fir_charges', ['icao_code'], unique=False)
    op.create_index('idx_fir_charges_country_code', 'fir_charges', ['country_code'], unique=False)


def downgrade() -> None:
    """Downgrade schema - Drop flitex-overflightcharges tables."""
    
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_index('idx_fir_charges_country_code', table_name='fir_charges')
    op.drop_index('idx_fir_charges_icao_code', table_name='fir_charges')
    op.drop_index('idx_fir_charges_calculation_id', table_name='fir_charges')
    op.drop_table('fir_charges')
    
    op.drop_index('idx_route_calculations_destination', table_name='route_calculations')
    op.drop_index('idx_route_calculations_origin', table_name='route_calculations')
    op.drop_index('idx_route_calculations_timestamp', table_name='route_calculations')
    op.drop_table('route_calculations')
    
    op.drop_index('unique_active_formula', table_name='formulas', postgresql_where=sa.text('is_active = true'))
    op.drop_index('idx_formulas_created_at', table_name='formulas')
    op.drop_index('idx_formulas_version', table_name='formulas')
    op.drop_index('idx_formulas_country_active', table_name='formulas')
    op.drop_table('formulas')
    
    op.drop_index('idx_iata_firs_avoid_status', table_name='iata_firs')
    op.drop_index('idx_iata_firs_country_code', table_name='iata_firs')
    op.drop_table('iata_firs')
