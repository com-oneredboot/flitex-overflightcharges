# Migration Property Tests

## Overview

The `test_migration_properties.py` file contains property-based tests for the regional formula support migration. These tests verify that the database migration preserves all existing country formula data correctly.

## Requirements

- **PostgreSQL database**: These tests require a running PostgreSQL instance
- **DATABASE_URL environment variable**: Must be set to a valid PostgreSQL connection string

## Running the Tests

### Setup PostgreSQL

If using Docker:

```bash
docker run --name postgres-test -e POSTGRES_PASSWORD=testpass -e POSTGRES_DB=testdb -p 5432:5432 -d postgres:14
```

### Set Environment Variable

```bash
export DATABASE_URL="postgresql://postgres:testpass@localhost:5432/testdb"
```

### Run the Tests

Run all migration property tests:

```bash
pytest tests/test_migration_properties.py -v
```

Run a specific property test:

```bash
pytest tests/test_migration_properties.py::TestMigrationProperties::test_property_4_migration_preserves_country_data -v
```

Run with property-based testing warning:

```bash
pytest tests/test_migration_properties.py -v --tb=short
```

## Test Coverage

### Property 4: Migration Preserves Country Data

**Validates: Requirements 1.4, 7.2, 9.1, 9.3**

This property test verifies that:

1. All existing country formula records are preserved during migration
2. The `country_code` value remains unchanged for each record
3. All other fields (`formula_logic`, `effective_date`, `currency`, `version_number`, `is_active`, `created_at`, `created_by`) remain unchanged
4. The new `description` field is populated correctly based on the country code mapping

The test uses Hypothesis to generate 100+ randomized test cases with different combinations of:
- Country codes (from the full ISO 3166-1 alpha-2 list)
- Formula codes
- Formula logic
- Effective dates
- Currencies
- Version numbers
- Active status
- Creation timestamps
- Created by users

### Additional Tests

- **test_property_4_migration_count_unchanged**: Verifies that the total number of records remains the same after migration
- **test_property_4_migration_schema_changes**: Verifies that schema changes are applied correctly (country_code nullable, description added)

## Test Isolation

Each test creates a unique PostgreSQL database to ensure complete isolation:

1. A new database is created with a random name (e.g., `test_migration_a1b2c3d4`)
2. Migrations are run against this database
3. Test assertions are performed
4. The database is dropped after the test completes

This approach ensures:
- No interference between test runs
- Clean state for each test
- Ability to run tests in parallel (if needed)

## Troubleshooting

### Tests are skipped

If you see:
```
SKIPPED [1] tests/test_migration_properties.py:XX: Requires PostgreSQL database. Set DATABASE_URL environment variable.
```

This means PostgreSQL is not available or DATABASE_URL is not set. Follow the setup instructions above.

### Connection errors

If you see connection errors, verify:
1. PostgreSQL is running: `docker ps` or `pg_isready`
2. DATABASE_URL is correct: `echo $DATABASE_URL`
3. You can connect manually: `psql $DATABASE_URL`

### Migration errors

If migrations fail during tests:
1. Check that migrations are up to date in the `migrations/versions/` directory
2. Verify the migration file `cd9f343711ad_add_regional_formula_support.py` exists
3. Check Alembic configuration in `alembic.ini`

## Performance

Property-based tests with 100 examples can take 1-3 minutes to run due to:
- Database creation/teardown for each test
- Running migrations multiple times
- Generating and validating 100+ test cases

This is expected and ensures thorough testing of the migration logic.
