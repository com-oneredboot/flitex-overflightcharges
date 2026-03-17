"""create_qa_schema_and_tables

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-01 10:00:00.000000

This migration creates the QA schema and all four tables for the route string
QA regression testing harness:

1. qa.flight_plans - Reference ICAO flight plan data imported from Excel files
2. qa.test_runs - Batch test execution records with git commit SHA and FIR hash
3. qa.test_run_results - Per-flight-plan parser output (waypoints, FIR crossings,
   unresolved tokens) stored as JSONB
4. qa.test_run_reviews - Manual expert review verdicts per result

Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3,
              12.1, 12.2, 12.3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create qa schema and all QA testing tables.

    Tables:
    1. qa.flight_plans - Reference flight plan data
    2. qa.test_runs - Batch test execution records
    3. qa.test_run_results - Per-flight-plan parser output
    4. qa.test_run_reviews - Manual review verdicts

    Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2,
                  4.3, 12.1, 12.2, 12.3
    """
    # Create qa schema
    op.execute("CREATE SCHEMA IF NOT EXISTS qa")

    # ── qa.flight_plans ──────────────────────────────────────────────────
    op.create_table(
        'flight_plans',
        sa.Column(
            'id',
            sa.Integer(),
            autoincrement=True,
            nullable=False,
            comment='Primary key'
        ),
        sa.Column(
            'scheduled_departure_dtmz',
            sa.TIMESTAMP(),
            nullable=True,
            comment='Scheduled departure timestamp'
        ),
        sa.Column(
            'departure_icao_aerodrome_code',
            sa.String(),
            nullable=True,
            comment='ICAO departure aerodrome code'
        ),
        sa.Column(
            'operational_icao_carrier_code',
            sa.String(),
            nullable=True,
            comment='ICAO carrier code'
        ),
        sa.Column(
            'flight_number',
            sa.String(),
            nullable=True,
            comment='Flight number'
        ),
        sa.Column(
            'release_number',
            sa.Integer(),
            nullable=True,
            comment='Release number'
        ),
        sa.Column(
            'aircraft_type',
            sa.String(),
            nullable=True,
            comment='Aircraft type designator'
        ),
        sa.Column(
            'icao_route',
            sa.Text(),
            nullable=True,
            comment='Full ICAO route string'
        ),
        sa.Column(
            'destination_aerodrome_code',
            sa.String(),
            nullable=True,
            comment='Destination aerodrome code'
        ),
        sa.Column(
            'total_estimated_elapsed_time',
            sa.String(),
            nullable=True,
            comment='Total estimated elapsed time'
        ),
        sa.Column(
            'alternate_aerodrome_list',
            sa.Text(),
            nullable=True,
            comment='Alternate aerodrome list'
        ),
        sa.Column(
            'hash_code',
            sa.String(),
            nullable=True,
            comment='Unique hash for deduplication'
        ),
        sa.Column(
            'created_at',
            sa.TIMESTAMP(),
            server_default=sa.text('now()'),
            nullable=False,
            comment='Record creation timestamp'
        ),
        sa.Column(
            'source_file',
            sa.String(),
            nullable=True,
            comment='Name of the source Excel file'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_qa_flight_plans')),
        sa.UniqueConstraint('hash_code', name='uq_qa_flight_plans_hash_code'),
        schema='qa'
    )

    # Indexes for qa.flight_plans
    op.create_index(
        'idx_qa_fp_departure',
        'flight_plans',
        ['departure_icao_aerodrome_code'],
        unique=False,
        schema='qa'
    )
    op.create_index(
        'idx_qa_fp_destination',
        'flight_plans',
        ['destination_aerodrome_code'],
        unique=False,
        schema='qa'
    )
    op.create_index(
        'idx_qa_fp_carrier',
        'flight_plans',
        ['operational_icao_carrier_code'],
        unique=False,
        schema='qa'
    )

    # ── qa.test_runs ─────────────────────────────────────────────────────
    op.create_table(
        'test_runs',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text('gen_random_uuid()'),
            comment='Primary key'
        ),
        sa.Column(
            'commit_sha',
            sa.String(),
            nullable=True,
            comment='Git commit SHA at time of run'
        ),
        sa.Column(
            'run_timestamp',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='When the test run was created'
        ),
        sa.Column(
            'notes',
            sa.Text(),
            nullable=True,
            comment='Optional notes for this run'
        ),
        sa.Column(
            'fir_boundary_hash',
            sa.String(),
            nullable=True,
            comment='MD5 hash of FIR boundary data version'
        ),
        sa.Column(
            'status',
            sa.String(),
            nullable=False,
            server_default='pending',
            comment='Run status: pending, running, completed, failed'
        ),
        sa.Column(
            'total_flight_plans',
            sa.Integer(),
            nullable=True,
            comment='Total flight plans in this run'
        ),
        sa.Column(
            'completed_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='Successfully processed flight plans'
        ),
        sa.Column(
            'failed_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='Flight plans that encountered errors'
        ),
        sa.Column(
            'created_by',
            sa.String(),
            nullable=True,
            comment='User who initiated the run'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_qa_test_runs')),
        schema='qa'
    )

    # Index for qa.test_runs
    op.create_index(
        'idx_qa_tr_timestamp',
        'test_runs',
        ['run_timestamp'],
        unique=False,
        schema='qa'
    )

    # ── qa.test_run_results ──────────────────────────────────────────────
    op.create_table(
        'test_run_results',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text('gen_random_uuid()'),
            comment='Primary key'
        ),
        sa.Column(
            'test_run_id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment='FK to qa.test_runs'
        ),
        sa.Column(
            'flight_plan_id',
            sa.Integer(),
            nullable=False,
            comment='FK to qa.flight_plans'
        ),
        sa.Column(
            'resolved_waypoints',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='Array of resolved waypoint objects'
        ),
        sa.Column(
            'fir_crossings',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='Array of FIR crossing objects'
        ),
        sa.Column(
            'unresolved_tokens',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='Array of unresolved token objects'
        ),
        sa.Column(
            'parse_duration_ms',
            sa.Integer(),
            nullable=True,
            comment='Time taken to parse this flight plan in milliseconds'
        ),
        sa.Column(
            'error_message',
            sa.Text(),
            nullable=True,
            comment='Error message if parsing failed'
        ),
        sa.Column(
            'created_at',
            sa.TIMESTAMP(),
            server_default=sa.text('now()'),
            nullable=False,
            comment='Record creation timestamp'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_qa_test_run_results')),
        sa.UniqueConstraint(
            'test_run_id', 'flight_plan_id',
            name='uq_qa_trr_run_plan'
        ),
        sa.ForeignKeyConstraint(
            ['test_run_id'],
            ['qa.test_runs.id'],
            name=op.f('fk_qa_trr_test_run_id')
        ),
        sa.ForeignKeyConstraint(
            ['flight_plan_id'],
            ['qa.flight_plans.id'],
            name=op.f('fk_qa_trr_flight_plan_id')
        ),
        schema='qa'
    )

    # Indexes for qa.test_run_results
    op.create_index(
        'idx_qa_trr_run',
        'test_run_results',
        ['test_run_id'],
        unique=False,
        schema='qa'
    )
    op.create_index(
        'idx_qa_trr_plan',
        'test_run_results',
        ['flight_plan_id'],
        unique=False,
        schema='qa'
    )

    # ── qa.test_run_reviews ──────────────────────────────────────────────
    op.create_table(
        'test_run_reviews',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text('gen_random_uuid()'),
            comment='Primary key'
        ),
        sa.Column(
            'test_run_result_id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment='FK to qa.test_run_results'
        ),
        sa.Column(
            'verdict',
            sa.String(),
            nullable=False,
            comment='Review verdict: correct, incorrect, needs_investigation'
        ),
        sa.Column(
            'reviewer_notes',
            sa.Text(),
            nullable=True,
            comment='Optional reviewer notes'
        ),
        sa.Column(
            'reviewed_by',
            sa.String(),
            nullable=False,
            comment='Reviewer identity'
        ),
        sa.Column(
            'reviewed_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='When the review was submitted'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_qa_test_run_reviews')),
        sa.ForeignKeyConstraint(
            ['test_run_result_id'],
            ['qa.test_run_results.id'],
            name=op.f('fk_qa_rev_test_run_result_id')
        ),
        schema='qa'
    )

    # Index for qa.test_run_reviews
    op.create_index(
        'idx_qa_rev_result',
        'test_run_reviews',
        ['test_run_result_id'],
        unique=False,
        schema='qa'
    )


def downgrade() -> None:
    """
    Drop all QA tables and the qa schema.

    Tables are dropped in reverse order to respect foreign key constraints.
    """
    # Drop qa.test_run_reviews indexes and table
    op.drop_index(
        'idx_qa_rev_result',
        table_name='test_run_reviews',
        schema='qa'
    )
    op.drop_table('test_run_reviews', schema='qa')

    # Drop qa.test_run_results indexes and table
    op.drop_index(
        'idx_qa_trr_plan',
        table_name='test_run_results',
        schema='qa'
    )
    op.drop_index(
        'idx_qa_trr_run',
        table_name='test_run_results',
        schema='qa'
    )
    op.drop_table('test_run_results', schema='qa')

    # Drop qa.test_runs indexes and table
    op.drop_index(
        'idx_qa_tr_timestamp',
        table_name='test_runs',
        schema='qa'
    )
    op.drop_table('test_runs', schema='qa')

    # Drop qa.flight_plans indexes and table
    op.drop_index(
        'idx_qa_fp_carrier',
        table_name='flight_plans',
        schema='qa'
    )
    op.drop_index(
        'idx_qa_fp_destination',
        table_name='flight_plans',
        schema='qa'
    )
    op.drop_index(
        'idx_qa_fp_departure',
        table_name='flight_plans',
        schema='qa'
    )
    op.drop_table('flight_plans', schema='qa')

    # Drop qa schema
    op.execute("DROP SCHEMA IF EXISTS qa")
