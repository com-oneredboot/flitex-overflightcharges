"""Property-based tests for database migrations.

Tests migration behavior using property-based testing with Hypothesis to verify
correctness across a wide range of inputs.

Feature: regional-formula-support

NOTE: These tests require a PostgreSQL database. They will be skipped if
PostgreSQL is not available. To run these tests, ensure PostgreSQL is running
and DATABASE_URL environment variable is set.
"""

import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4
from hypothesis import given, settings, strategies as st
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config
from pathlib import Path
import os

from src.models.formula import Formula
from src.database import Base
from src.constants.countries import COUNTRY_CODE_TO_NAME


# Check if PostgreSQL is available
def is_postgres_available():
    """Check if PostgreSQL database is available for testing."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or "postgresql" not in database_url:
        return False
    
    try:
        engine = create_engine(database_url, echo=False)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


# Skip all tests in this module if PostgreSQL is not available
pytestmark = pytest.mark.skipif(
    not is_postgres_available(),
    reason="Requires PostgreSQL database. Set DATABASE_URL environment variable."
)


# Hypothesis strategies for generating test data
@st.composite
def formula_data(draw):
    """Generate valid formula data for testing."""
    country_codes = list(COUNTRY_CODE_TO_NAME.keys())
    
    return {
        "id": uuid4(),
        "country_code": draw(st.sampled_from(country_codes)),
        "formula_code": draw(st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Nd"), min_codepoint=65, max_codepoint=90),
            min_size=5,
            max_size=50
        )),
        "formula_logic": draw(st.text(
            alphabet=st.characters(blacklist_characters='\x00', min_codepoint=32, max_codepoint=126),
            min_size=20,
            max_size=500
        )),
        "effective_date": draw(st.dates(
            min_value=date(2020, 1, 1),
            max_value=date(2030, 12, 31)
        )),
        "currency": draw(st.sampled_from(["USD", "EUR", "GBP", "CAD", "AUD", "JPY"])),
        "version_number": draw(st.integers(min_value=1, max_value=10)),
        "is_active": draw(st.booleans()),
        "created_at": draw(st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2026, 12, 31),
            timezones=st.just(None)
        )),
        "created_by": draw(st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu"), min_codepoint=97, max_codepoint=122),
            min_size=3,
            max_size=50
        ))
    }


class TestMigrationProperties:
    """Property-based tests for migration correctness.
    
    **Validates: Requirements 1.4, 7.2, 9.1, 9.3**
    
    These tests use a PostgreSQL test database to verify migration behavior.
    Each test creates a fresh database to isolate test data.
    """
    
    def setup_method(self):
        """Set up test database for each test."""
        # Get database URL from environment
        base_db_url = os.getenv("DATABASE_URL")
        if not base_db_url:
            pytest.skip("DATABASE_URL not set")
        
        # Create a unique test database name
        import random
        import string
        db_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self.test_db_name = f"test_migration_{db_suffix}"
        
        # Parse base URL to get connection to postgres database
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(base_db_url)
        
        # Connect to postgres database to create test database
        postgres_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            '/postgres',
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        # Create test database
        postgres_engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT", echo=False)
        with postgres_engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE {self.test_db_name}"))
        postgres_engine.dispose()
        
        # Create URL for test database
        self.db_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            f'/{self.test_db_name}',
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        # Create engine and session for test database
        self.engine = create_engine(self.db_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Set up Alembic config
        self.alembic_cfg = Config()
        migrations_path = Path(__file__).parent.parent / "migrations"
        self.alembic_cfg.set_main_option("script_location", str(migrations_path))
        self.alembic_cfg.set_main_option("sqlalchemy.url", self.db_url)
        
        # Suppress Alembic output during tests
        self.alembic_cfg.attributes['configure_logger'] = False
    
    def teardown_method(self):
        """Clean up test database after each test."""
        # Close all connections
        self.engine.dispose()
        
        # Drop test database
        try:
            base_db_url = os.getenv("DATABASE_URL")
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(base_db_url)
            
            postgres_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                '/postgres',
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            
            postgres_engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT", echo=False)
            with postgres_engine.connect() as conn:
                # Terminate existing connections to test database
                conn.execute(text(f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = '{self.test_db_name}'
                    AND pid <> pg_backend_pid()
                """))
                conn.execute(text(f"DROP DATABASE IF EXISTS {self.test_db_name}"))
            postgres_engine.dispose()
        except Exception:
            pass
    
    def create_initial_schema(self):
        """Create the initial schema (before migration)."""
        # Run migration to the revision before regional formula support
        command.upgrade(self.alembic_cfg, "2a8de75b4840")
    
    def run_upgrade_migration(self):
        """Run the upgrade migration to add regional formula support."""
        command.upgrade(self.alembic_cfg, "cd9f343711ad")
    
    def insert_formula_old_schema(self, session, formula_data):
        """Insert formula using old schema (without description field)."""
        # Insert directly using SQL since the old schema doesn't have description
        insert_sql = text("""
            INSERT INTO formulas (
                id, country_code, formula_code, formula_logic,
                effective_date, currency, version_number, is_active,
                created_at, created_by
            ) VALUES (
                :id, :country_code, :formula_code, :formula_logic,
                :effective_date, :currency, :version_number, :is_active,
                :created_at, :created_by
            )
        """)
        
        # Convert UUID to string for PostgreSQL
        params = formula_data.copy()
        params['id'] = str(params['id'])
        
        session.execute(insert_sql, params)
        session.commit()
    
    def get_formula_by_id(self, session, formula_id):
        """Retrieve formula by ID after migration."""
        select_sql = text("""
            SELECT id, country_code, description, formula_code, formula_logic,
                   effective_date, currency, version_number, is_active,
                   created_at, created_by
            FROM formulas
            WHERE id = :id
        """)
        
        result = session.execute(select_sql, {"id": str(formula_id)})
        row = result.fetchone()
        
        if row:
            return {
                "id": str(row[0]),
                "country_code": row[1],
                "description": row[2],
                "formula_code": row[3],
                "formula_logic": row[4],
                "effective_date": row[5],
                "currency": row[6],
                "version_number": row[7],
                "is_active": row[8],
                "created_at": row[9],
                "created_by": row[10]
            }
        return None
    
    @pytest.mark.property
    @settings(max_examples=100, deadline=None)
    @given(formulas=st.lists(formula_data(), min_size=1, max_size=10, unique_by=lambda x: (x["country_code"], x["version_number"])))
    def test_property_4_migration_preserves_country_data(self, formulas):
        """
        Feature: regional-formula-support, Property 4: Migration Preserves Country Data
        
        **Validates: Requirements 1.4, 7.2, 9.1, 9.3**
        
        For all existing country formula records before migration, after running
        the upgrade migration, each record should have the same country_code value
        and all other fields (formula_logic, effective_date, currency, version_number,
        is_active, created_at, created_by) should remain unchanged.
        
        This property test uses Hypothesis to generate random formula data and verify
        that the migration preserves all data correctly across 100+ test cases.
        """
        # Arrange: Create initial schema and insert test data
        self.create_initial_schema()
        session = self.SessionLocal()
        
        try:
            # Insert formulas with old schema
            for formula in formulas:
                self.insert_formula_old_schema(session, formula)
            
            # Store original data for comparison
            original_formulas = {f["id"]: f for f in formulas}
            
            # Act: Run upgrade migration
            self.run_upgrade_migration()
            
            # Assert: Verify all data preserved
            for formula_id, original in original_formulas.items():
                migrated = self.get_formula_by_id(session, formula_id)
                
                # Verify formula exists after migration
                assert migrated is not None, \
                    f"Formula {formula_id} was lost during migration"
                
                # Verify country_code preserved (Requirement 1.4)
                assert migrated["country_code"] == original["country_code"], \
                    f"country_code changed from {original['country_code']} to {migrated['country_code']}"
                
                # Verify formula_code preserved
                assert migrated["formula_code"] == original["formula_code"], \
                    f"formula_code changed for formula {formula_id}"
                
                # Verify formula_logic preserved (Requirement 7.2)
                assert migrated["formula_logic"] == original["formula_logic"], \
                    f"formula_logic changed for formula {formula_id}"
                
                # Verify effective_date preserved
                original_date = original["effective_date"]
                migrated_date = migrated["effective_date"]
                assert migrated_date == original_date, \
                    f"effective_date changed from {original_date} to {migrated_date}"
                
                # Verify currency preserved
                assert migrated["currency"] == original["currency"], \
                    f"currency changed for formula {formula_id}"
                
                # Verify version_number preserved (Requirement 9.1)
                assert migrated["version_number"] == original["version_number"], \
                    f"version_number changed for formula {formula_id}"
                
                # Verify is_active preserved
                assert migrated["is_active"] == original["is_active"], \
                    f"is_active changed for formula {formula_id}"
                
                # Verify created_at preserved (Requirement 9.3)
                # PostgreSQL returns timezone-aware datetime, compare as timestamps
                original_created = original["created_at"]
                migrated_created = migrated["created_at"]
                
                # Handle timezone-aware vs naive datetime comparison
                if hasattr(migrated_created, 'replace') and migrated_created.tzinfo is not None:
                    # Convert to naive UTC for comparison
                    migrated_created = migrated_created.replace(tzinfo=None)
                
                assert migrated_created == original_created, \
                    f"created_at changed from {original_created} to {migrated_created}"
                
                # Verify created_by preserved
                assert migrated["created_by"] == original["created_by"], \
                    f"created_by changed for formula {formula_id}"
                
                # Verify description field was added and populated (Requirement 9.1)
                assert migrated["description"] is not None, \
                    f"description field not populated for formula {formula_id}"
                
                # Verify description matches country name from mapping
                expected_description = COUNTRY_CODE_TO_NAME.get(
                    original["country_code"],
                    f"Country: {original['country_code']}"
                )
                assert migrated["description"] == expected_description, \
                    f"description '{migrated['description']}' does not match expected '{expected_description}'"
        
        finally:
            session.close()
    
    @pytest.mark.property
    @settings(max_examples=50, deadline=None)
    @given(formulas=st.lists(formula_data(), min_size=1, max_size=5, unique_by=lambda x: (x["country_code"], x["version_number"])))
    def test_property_4_migration_count_unchanged(self, formulas):
        """
        Feature: regional-formula-support, Property 4: Migration Preserves Country Data (Count)
        
        **Validates: Requirements 9.1, 9.2**
        
        For any set of country formula records before migration, after running
        the upgrade migration, the count of records should be unchanged.
        
        This is a complementary test to verify no records are lost or duplicated.
        """
        # Arrange: Create initial schema and insert test data
        self.create_initial_schema()
        session = self.SessionLocal()
        
        try:
            # Insert formulas with old schema
            for formula in formulas:
                self.insert_formula_old_schema(session, formula)
            
            # Count records before migration
            count_before = session.execute(text("SELECT COUNT(*) FROM formulas")).scalar()
            
            # Act: Run upgrade migration
            self.run_upgrade_migration()
            
            # Assert: Verify count unchanged
            count_after = session.execute(text("SELECT COUNT(*) FROM formulas")).scalar()
            
            assert count_after == count_before, \
                f"Record count changed from {count_before} to {count_after} during migration"
            
            assert count_after == len(formulas), \
                f"Expected {len(formulas)} records, found {count_after}"
        
        finally:
            session.close()
    
    @pytest.mark.property
    @settings(max_examples=50, deadline=None)
    @given(formulas=st.lists(formula_data(), min_size=1, max_size=5, unique_by=lambda x: (x["country_code"], x["version_number"])))
    def test_property_4_migration_schema_changes(self, formulas):
        """
        Feature: regional-formula-support, Property 4: Migration Preserves Country Data (Schema)
        
        **Validates: Requirements 1.1, 2.1**
        
        After migration, verify that:
        1. country_code column is nullable
        2. description column exists and is NOT NULL
        3. All other columns remain unchanged
        """
        # Arrange: Create initial schema
        self.create_initial_schema()
        session = self.SessionLocal()
        
        try:
            # Insert at least one formula
            self.insert_formula_old_schema(session, formulas[0])
            
            # Act: Run upgrade migration
            self.run_upgrade_migration()
            
            # Assert: Verify schema changes
            inspector = inspect(self.engine)
            columns = {col['name']: col for col in inspector.get_columns('formulas')}
            
            # Verify country_code is nullable (Requirement 1.1)
            assert columns['country_code']['nullable'] is True, \
                "country_code should be nullable after migration"
            
            # Verify description column exists (Requirement 2.1)
            assert 'description' in columns, \
                "description column should exist after migration"
            
            # Verify description is NOT NULL (Requirement 2.2)
            assert columns['description']['nullable'] is False, \
                "description should be NOT NULL after migration"
            
            # Verify description is TEXT type
            desc_type_str = str(columns['description']['type']).upper()
            assert 'TEXT' in desc_type_str or 'VARCHAR' in desc_type_str, \
                f"description should be TEXT type, got {desc_type_str}"
            
            # Verify other columns still exist
            required_columns = [
                'id', 'country_code', 'description', 'formula_code',
                'formula_logic', 'effective_date', 'currency',
                'version_number', 'is_active', 'created_at', 'created_by'
            ]
            
            for col_name in required_columns:
                assert col_name in columns, \
                    f"Column {col_name} should exist after migration"
        
        finally:
            session.close()


    def run_downgrade_migration(self):
        """Run the downgrade migration to remove regional formula support."""
        command.downgrade(self.alembic_cfg, "2a8de75b4840")

    @pytest.mark.property
    @settings(max_examples=100, deadline=None)
    @given(formulas=st.lists(formula_data(), min_size=1, max_size=10, unique_by=lambda x: (x["country_code"], x["version_number"])))
    def test_property_6_migration_round_trip(self, formulas):
        """
        Feature: regional-formula-support, Property 6: Migration Round Trip

        **Validates: Requirements 3.3, 3.4**

        For any database state containing only country formulas (no regional formulas),
        running upgrade migration followed immediately by downgrade migration should
        restore the original schema with country_code as NOT NULL, description column
        removed, and all country formula data preserved.

        This property test verifies that the migration is fully reversible and that
        downgrading does not cause data loss for country formulas.
        """
        # Arrange: Create initial schema and insert test data
        self.create_initial_schema()
        session = self.SessionLocal()

        try:
            # Insert formulas with old schema (only country formulas, no regional)
            for formula in formulas:
                self.insert_formula_old_schema(session, formula)

            # Store original data for comparison
            original_formulas = {f["id"]: f for f in formulas}

            # Verify initial schema state (country_code NOT NULL, no description)
            inspector = inspect(self.engine)
            columns_before = {col['name']: col for col in inspector.get_columns('formulas')}

            assert columns_before['country_code']['nullable'] is False, \
                "country_code should be NOT NULL in initial schema"
            assert 'description' not in columns_before, \
                "description column should not exist in initial schema"

            # Act: Run upgrade migration
            self.run_upgrade_migration()

            # Verify upgrade worked (country_code nullable, description exists)
            inspector = inspect(self.engine)
            columns_after_upgrade = {col['name']: col for col in inspector.get_columns('formulas')}

            assert columns_after_upgrade['country_code']['nullable'] is True, \
                "country_code should be nullable after upgrade"
            assert 'description' in columns_after_upgrade, \
                "description column should exist after upgrade"

            # Act: Run downgrade migration
            self.run_downgrade_migration()

            # Assert: Verify schema restored to original state
            inspector = inspect(self.engine)
            columns_after_downgrade = {col['name']: col for col in inspector.get_columns('formulas')}

            # Verify country_code is NOT NULL again (Requirement 3.4)
            assert columns_after_downgrade['country_code']['nullable'] is False, \
                "country_code should be NOT NULL after downgrade (schema not restored)"

            # Verify description column removed (Requirement 3.3)
            assert 'description' not in columns_after_downgrade, \
                "description column should be removed after downgrade (schema not restored)"

            # Verify all original columns still exist
            required_columns = [
                'id', 'country_code', 'formula_code', 'formula_logic',
                'effective_date', 'currency', 'version_number', 'is_active',
                'created_at', 'created_by'
            ]

            for col_name in required_columns:
                assert col_name in columns_after_downgrade, \
                    f"Column {col_name} should exist after downgrade"

            # Verify all country formula data preserved (Requirement 3.4)
            for formula_id, original in original_formulas.items():
                # Query using raw SQL since we're back to old schema
                select_sql = text("""
                    SELECT id, country_code, formula_code, formula_logic,
                           effective_date, currency, version_number, is_active,
                           created_at, created_by
                    FROM formulas
                    WHERE id = :id
                """)

                result = session.execute(select_sql, {"id": str(formula_id)})
                row = result.fetchone()

                # Verify formula exists after round trip
                assert row is not None, \
                    f"Formula {formula_id} was lost during migration round trip"

                restored = {
                    "id": str(row[0]),
                    "country_code": row[1],
                    "formula_code": row[2],
                    "formula_logic": row[3],
                    "effective_date": row[4],
                    "currency": row[5],
                    "version_number": row[6],
                    "is_active": row[7],
                    "created_at": row[8],
                    "created_by": row[9]
                }

                # Verify all fields match original data
                assert restored["country_code"] == original["country_code"], \
                    f"country_code changed from {original['country_code']} to {restored['country_code']}"

                assert restored["formula_code"] == original["formula_code"], \
                    f"formula_code changed for formula {formula_id}"

                assert restored["formula_logic"] == original["formula_logic"], \
                    f"formula_logic changed for formula {formula_id}"

                original_date = original["effective_date"]
                restored_date = restored["effective_date"]
                assert restored_date == original_date, \
                    f"effective_date changed from {original_date} to {restored_date}"

                assert restored["currency"] == original["currency"], \
                    f"currency changed for formula {formula_id}"

                assert restored["version_number"] == original["version_number"], \
                    f"version_number changed for formula {formula_id}"

                assert restored["is_active"] == original["is_active"], \
                    f"is_active changed for formula {formula_id}"

                # Handle timezone-aware vs naive datetime comparison
                original_created = original["created_at"]
                restored_created = restored["created_at"]

                if hasattr(restored_created, 'replace') and restored_created.tzinfo is not None:
                    restored_created = restored_created.replace(tzinfo=None)

                assert restored_created == original_created, \
                    f"created_at changed from {original_created} to {restored_created}"

                assert restored["created_by"] == original["created_by"], \
                    f"created_by changed for formula {formula_id}"

            # Verify record count unchanged
            count_after = session.execute(text("SELECT COUNT(*) FROM formulas")).scalar()
            assert count_after == len(formulas), \
                f"Expected {len(formulas)} records after round trip, found {count_after}"

        finally:
            session.close()

    @pytest.mark.property
    @settings(max_examples=100, deadline=None)
    @given(formulas=st.lists(formula_data(), min_size=1, max_size=10, unique_by=lambda x: (x["country_code"], x["version_number"])))
    def test_property_16_migration_data_integrity(self, formulas):
        """
        Feature: regional-formula-support, Property 16: Migration Data Integrity

        **Validates: Requirements 9.1, 9.2**

        For any set of country formula records before migration, after running
        the upgrade migration, the count of records should be unchanged, and for
        each original record, there should exist a corresponding record with
        matching id, country_code, formula_logic, effective_date, currency,
        version_number, is_active, created_at, and created_by values.

        This property test verifies comprehensive data integrity during migration
        by checking both record count preservation and field-by-field matching
        for all records.
        """
        # Arrange: Create initial schema and insert test data
        self.create_initial_schema()
        session = self.SessionLocal()

        try:
            # Insert formulas with old schema
            for formula in formulas:
                self.insert_formula_old_schema(session, formula)

            # Store original data for comparison
            original_formulas = {f["id"]: f for f in formulas}
            original_count = len(formulas)

            # Act: Run upgrade migration
            self.run_upgrade_migration()

            # Assert Part 1: Verify record count unchanged (Requirement 9.1)
            count_after = session.execute(text("SELECT COUNT(*) FROM formulas")).scalar()

            assert count_after == original_count, \
                f"Record count changed during migration: expected {original_count}, got {count_after}"

            # Assert Part 2: Verify field-by-field matching for each record (Requirement 9.2)
            for formula_id, original in original_formulas.items():
                migrated = self.get_formula_by_id(session, formula_id)

                # Verify formula exists after migration
                assert migrated is not None, \
                    f"Formula {formula_id} was lost during migration (data integrity violation)"

                # Verify id preserved
                assert migrated["id"] == str(formula_id), \
                    f"Formula id changed from {formula_id} to {migrated['id']}"

                # Verify country_code preserved
                assert migrated["country_code"] == original["country_code"], \
                    f"country_code changed from {original['country_code']} to {migrated['country_code']} for formula {formula_id}"

                # Verify formula_logic preserved
                assert migrated["formula_logic"] == original["formula_logic"], \
                    f"formula_logic changed for formula {formula_id} (data integrity violation)"

                # Verify effective_date preserved
                original_date = original["effective_date"]
                migrated_date = migrated["effective_date"]
                assert migrated_date == original_date, \
                    f"effective_date changed from {original_date} to {migrated_date} for formula {formula_id}"

                # Verify currency preserved
                assert migrated["currency"] == original["currency"], \
                    f"currency changed from {original['currency']} to {migrated['currency']} for formula {formula_id}"

                # Verify version_number preserved
                assert migrated["version_number"] == original["version_number"], \
                    f"version_number changed from {original['version_number']} to {migrated['version_number']} for formula {formula_id}"

                # Verify is_active preserved
                assert migrated["is_active"] == original["is_active"], \
                    f"is_active changed from {original['is_active']} to {migrated['is_active']} for formula {formula_id}"

                # Verify created_at preserved
                original_created = original["created_at"]
                migrated_created = migrated["created_at"]

                # Handle timezone-aware vs naive datetime comparison
                if hasattr(migrated_created, 'replace') and migrated_created.tzinfo is not None:
                    migrated_created = migrated_created.replace(tzinfo=None)

                assert migrated_created == original_created, \
                    f"created_at changed from {original_created} to {migrated_created} for formula {formula_id}"

                # Verify created_by preserved
                assert migrated["created_by"] == original["created_by"], \
                    f"created_by changed from {original['created_by']} to {migrated['created_by']} for formula {formula_id}"

            # Assert Part 3: Verify no extra records were added
            all_ids_after = session.execute(text("SELECT id FROM formulas")).fetchall()
            all_ids_after_set = {str(row[0]) for row in all_ids_after}
            original_ids_set = {str(fid) for fid in original_formulas.keys()}

            assert all_ids_after_set == original_ids_set, \
                f"Record IDs changed during migration. Extra IDs: {all_ids_after_set - original_ids_set}, Missing IDs: {original_ids_set - all_ids_after_set}"

        finally:
            session.close()


