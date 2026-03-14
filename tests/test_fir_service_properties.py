"""Property-based tests for FIR service operations.

These tests verify universal properties for FIR service CRUD operations using Hypothesis.
Each property test runs with a minimum of 100 iterations.

Feature: fir-versioning-and-data-import

NOTE: These tests require a PostgreSQL database. They will be skipped if
PostgreSQL is not available. To run these tests, ensure PostgreSQL is running
and DATABASE_URL environment variable is set.
"""

import uuid
import pytest
from datetime import datetime, timezone
from hypothesis import given, settings, strategies as st, HealthCheck
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

from src.models.iata_fir import IataFir
from src.schemas.fir import FIRCreate
from src.services.fir_service import FIRService
from src.database import Base


# PostgreSQL rejects NUL (0x00) in text — use printable + common unicode, no surrogates/NUL
pg_safe_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="\x00",
    ),
)


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


pytestmark = pytest.mark.skipif(
    not is_postgres_available(),
    reason="Requires PostgreSQL database. Set DATABASE_URL environment variable.",
)


@pytest.fixture(scope="function")
def test_db():
    """Create a test database session for each test."""
    database_url = os.getenv("DATABASE_URL")
    engine = create_engine(database_url, echo=False)

    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)
    session = TestSession()

    yield session

    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# --- Hypothesis strategies for FIR data ---

# ICAO code: 4 uppercase alphanumeric, must contain at least one letter
# (str.isupper() returns False for all-digit strings)
icao_code_strategy = st.tuples(
    st.text(
        alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        min_size=1,
        max_size=1,
    ),
    st.text(
        alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
        min_size=3,
        max_size=3,
    ),
).map(lambda t: t[0] + t[1])

country_code_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu",), min_codepoint=65, max_codepoint=90,
    ),
    min_size=2,
    max_size=2,
)

fir_name_strategy = pg_safe_text.filter(lambda s: len(s.strip()) > 0).map(
    lambda s: s[:100]
).filter(lambda s: len(s) >= 1)

country_name_strategy = pg_safe_text.filter(lambda s: len(s.strip()) > 0).map(
    lambda s: s[:100]
).filter(lambda s: len(s) >= 1)

created_by_strategy = pg_safe_text.filter(lambda s: len(s.strip()) > 0).map(
    lambda s: s[:100]
).filter(lambda s: len(s) >= 1)

geojson_polygon_strategy = st.just({
    "type": "Polygon",
    "coordinates": [
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]
    ],
})


@st.composite
def fir_create_strategy(draw):
    """Generate a valid FIRCreate schema instance with random data."""
    return FIRCreate(
        icao_code=draw(icao_code_strategy),
        fir_name=draw(fir_name_strategy),
        country_code=draw(country_code_strategy),
        country_name=draw(country_name_strategy),
        geojson_geometry=draw(geojson_polygon_strategy),
        avoid_status=draw(st.booleans()),
    )


class TestFIRCreationInvariantsProperty:
    """
    Feature: fir-versioning-and-data-import, Property 1: FIR creation invariants

    **Validates: Requirements 1.1, 1.3, 1.4, 1.5, 5.1**

    For any valid FIR creation data and any created_by string, the resulting
    FIR record SHALL have a valid UUIDv4 id, version_number equal to 1,
    is_active equal to True, activation_date set to approximately the current
    timestamp, and created_by matching the input string.
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        fir_data=fir_create_strategy(),
        created_by=created_by_strategy,
    )
    def test_property_1_fir_creation_invariants(
        self, test_db, fir_data, created_by
    ):
        """
        **Validates: Requirements 1.1, 1.3, 1.4, 1.5, 5.1**

        Property 1: FIR creation invariants

        For any valid FIR creation data and any created_by string, the resulting
        FIR record SHALL have a valid UUIDv4 id, version_number equal to 1,
        is_active equal to True, activation_date set to approximately the current
        timestamp, and created_by matching the input string.
        """
        # Reset session state in case a previous iteration left it dirty
        test_db.rollback()

        # Clean up any existing FIR with same icao_code to avoid constraint violations
        test_db.query(IataFir).filter(
            IataFir.icao_code == fir_data.icao_code
        ).delete()
        test_db.commit()

        before = datetime.now(timezone.utc)

        service = FIRService(test_db)
        result = service.create_fir(fir_data, created_by)

        after = datetime.now(timezone.utc)

        # Requirement 1.1: id is a valid UUIDv4
        assert result.id is not None, "FIR id must not be None"
        assert isinstance(result.id, uuid.UUID), "FIR id must be a UUID"
        assert result.id.version == 4, "FIR id must be UUIDv4"

        # Requirement 1.3: version_number == 1
        assert result.version_number == 1, (
            f"version_number must be 1, got {result.version_number}"
        )

        # Requirement 1.4: is_active == True
        assert result.is_active is True, (
            f"is_active must be True, got {result.is_active}"
        )

        # Requirement 5.1: activation_date ≈ now()
        assert result.activation_date is not None, (
            "activation_date must not be None"
        )
        assert before <= result.activation_date <= after, (
            f"activation_date {result.activation_date} not between "
            f"{before} and {after}"
        )

        # Requirement 1.5: created_by matches input
        assert result.created_by == created_by, (
            f"created_by must be '{created_by}', got '{result.created_by}'"
        )


# --- Strategy for FIR update data ---

@st.composite
def fir_update_strategy(draw):
    """Generate a valid FIRUpdate schema instance with random partial update data."""
    from src.schemas.fir import FIRUpdate

    # Generate at least one field to ensure a meaningful update
    fir_name = draw(st.one_of(st.none(), fir_name_strategy))
    country_name = draw(st.one_of(st.none(), country_name_strategy))
    geojson_geometry = draw(st.one_of(st.none(), geojson_polygon_strategy))
    avoid_status = draw(st.one_of(st.none(), st.booleans()))

    # Ensure at least one field is set so the update is meaningful
    kwargs = {}
    if fir_name is not None:
        kwargs["fir_name"] = fir_name
    if country_name is not None:
        kwargs["country_name"] = country_name
    if geojson_geometry is not None:
        kwargs["geojson_geometry"] = geojson_geometry
    if avoid_status is not None:
        kwargs["avoid_status"] = avoid_status

    # If nothing was drawn, force at least fir_name
    if not kwargs:
        kwargs["fir_name"] = draw(fir_name_strategy)

    return FIRUpdate(**kwargs)


class TestFIRUpdateVersioningProperty:
    """
    Feature: fir-versioning-and-data-import, Property 4: FIR update creates new version and deactivates old

    **Validates: Requirements 5.2**

    For any active FIR and any valid update data, after an update operation:
    the previously active version SHALL have is_active=False and a non-null
    deactivation_date, and the new version SHALL have version_number equal to
    the old version's version_number + 1, is_active=True, and a non-null
    activation_date.
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        fir_data=fir_create_strategy(),
        update_data=fir_update_strategy(),
        created_by=created_by_strategy,
        updated_by=created_by_strategy,
    )
    def test_property_4_update_creates_new_version_and_deactivates_old(
        self, test_db, fir_data, update_data, created_by, updated_by
    ):
        """
        **Validates: Requirements 5.2**

        Property 4: FIR update creates new version and deactivates old

        Create a FIR, then update with random data; verify old version has
        is_active=False + deactivation_date, new version has version_number+1
        + is_active=True + activation_date.
        """
        # Reset session state in case a previous iteration left it dirty
        test_db.rollback()

        # Clean up any existing FIR with same icao_code to avoid constraint violations
        test_db.query(IataFir).filter(
            IataFir.icao_code == fir_data.icao_code
        ).delete()
        test_db.commit()

        service = FIRService(test_db)

        # Step 1: Create a FIR
        created_fir = service.create_fir(fir_data, created_by)
        old_version_number = created_fir.version_number
        old_fir_id = created_fir.id

        assert old_version_number == 1, (
            f"Initial version_number must be 1, got {old_version_number}"
        )

        # Step 2: Update the FIR with random update data
        new_fir = service.update_fir(fir_data.icao_code, update_data, updated_by)

        # Refresh the old version from the database to see deactivation changes
        test_db.refresh(created_fir)

        # Step 3: Verify old version is deactivated
        assert created_fir.is_active is False, (
            f"Old version is_active must be False, got {created_fir.is_active}"
        )
        assert created_fir.deactivation_date is not None, (
            "Old version deactivation_date must not be None"
        )

        # Step 4: Verify new version has correct versioning properties
        assert new_fir.version_number == old_version_number + 1, (
            f"New version_number must be {old_version_number + 1}, "
            f"got {new_fir.version_number}"
        )
        assert new_fir.is_active is True, (
            f"New version is_active must be True, got {new_fir.is_active}"
        )
        assert new_fir.activation_date is not None, (
            "New version activation_date must not be None"
        )

        # Verify the new version has a different id from the old version
        assert new_fir.id != old_fir_id, (
            "New version must have a different id from the old version"
        )

        # Verify the new version shares the same icao_code
        assert new_fir.icao_code == fir_data.icao_code, (
            f"New version icao_code must be '{fir_data.icao_code}', "
            f"got '{new_fir.icao_code}'"
        )


# --- Additional imports for Properties 5-9 ---
from src.schemas.fir import FIRUpdate
from src.exceptions import FIRNotFoundException


class TestFIRSoftDeletePreservesRowsProperty:
    """
    Feature: fir-versioning-and-data-import, Property 5: FIR soft-delete preserves rows

    **Validates: Requirements 5.3**

    For any active FIR, after a soft-delete operation: the FIR record SHALL have
    is_active=False and a non-null deactivation_date, and the total number of rows
    for that ICAO code SHALL remain unchanged (no physical deletion).
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        fir_data=fir_create_strategy(),
        created_by=created_by_strategy,
    )
    def test_property_5_soft_delete_preserves_rows(
        self, test_db, fir_data, created_by
    ):
        """
        **Validates: Requirements 5.3**

        Property 5: FIR soft-delete preserves rows

        Create FIR, soft-delete, verify is_active=False + deactivation_date set,
        total row count unchanged.
        """
        test_db.rollback()

        # Clean up any existing FIR with same icao_code
        test_db.query(IataFir).filter(
            IataFir.icao_code == fir_data.icao_code
        ).delete()
        test_db.commit()

        service = FIRService(test_db)

        # Create a FIR
        created_fir = service.create_fir(fir_data, created_by)

        # Count rows before soft-delete
        row_count_before = (
            test_db.query(IataFir)
            .filter(IataFir.icao_code == fir_data.icao_code)
            .count()
        )

        # Soft-delete the FIR
        result = service.soft_delete_fir(fir_data.icao_code)
        assert result is True, "soft_delete_fir must return True"

        # Refresh to see changes
        test_db.refresh(created_fir)

        # Verify is_active=False
        assert created_fir.is_active is False, (
            f"After soft-delete, is_active must be False, got {created_fir.is_active}"
        )

        # Verify deactivation_date is set
        assert created_fir.deactivation_date is not None, (
            "After soft-delete, deactivation_date must not be None"
        )

        # Verify row count unchanged (no physical deletion)
        row_count_after = (
            test_db.query(IataFir)
            .filter(IataFir.icao_code == fir_data.icao_code)
            .count()
        )
        assert row_count_after == row_count_before, (
            f"Row count must be unchanged after soft-delete: "
            f"before={row_count_before}, after={row_count_after}"
        )


class TestFIRRollbackRoundTripProperty:
    """
    Feature: fir-versioning-and-data-import, Property 6: FIR rollback round-trip

    **Validates: Requirements 5.4**

    For any ICAO code with at least two versions where one is active and one is
    inactive, rolling back to the inactive version SHALL result in: the previously
    active version having is_active=False and a non-null deactivation_date, and the
    target version having is_active=True and a non-null activation_date.
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        fir_data=fir_create_strategy(),
        update_data=fir_update_strategy(),
        created_by=created_by_strategy,
        updated_by=created_by_strategy,
    )
    def test_property_6_rollback_round_trip(
        self, test_db, fir_data, update_data, created_by, updated_by
    ):
        """
        **Validates: Requirements 5.4**

        Property 6: FIR rollback round-trip

        Create FIR, update to v2, rollback to v1; verify v2 deactivated,
        v1 reactivated with activation_date.
        """
        test_db.rollback()

        # Clean up any existing FIR with same icao_code
        test_db.query(IataFir).filter(
            IataFir.icao_code == fir_data.icao_code
        ).delete()
        test_db.commit()

        service = FIRService(test_db)

        # Step 1: Create v1
        v1_fir = service.create_fir(fir_data, created_by)
        v1_id = v1_fir.id
        assert v1_fir.version_number == 1

        # Step 2: Update to v2
        v2_fir = service.update_fir(fir_data.icao_code, update_data, updated_by)
        v2_id = v2_fir.id
        assert v2_fir.version_number == 2

        # Step 3: Rollback to v1
        rolled_back = service.rollback_fir(fir_data.icao_code, 1)

        # Refresh v2 to see deactivation
        test_db.refresh(v2_fir)

        # Verify v2 is deactivated
        assert v2_fir.is_active is False, (
            f"After rollback, v2 is_active must be False, got {v2_fir.is_active}"
        )
        assert v2_fir.deactivation_date is not None, (
            "After rollback, v2 deactivation_date must not be None"
        )

        # Verify v1 is reactivated
        assert rolled_back.id == v1_id, (
            "Rolled-back FIR must be the original v1"
        )
        assert rolled_back.is_active is True, (
            f"After rollback, v1 is_active must be True, got {rolled_back.is_active}"
        )
        assert rolled_back.activation_date is not None, (
            "After rollback, v1 activation_date must not be None"
        )


class TestActiveFIRQueryFilterProperty:
    """
    Feature: fir-versioning-and-data-import, Property 7: Active FIR query filter

    **Validates: Requirements 5.5, 7.1**

    For any database state containing a mix of active and inactive FIR records,
    get_all_active_firs() SHALL return only records where is_active=True, and
    every record in the result set SHALL have is_active=True.
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        fir_datas=st.lists(
            fir_create_strategy(),
            min_size=2,
            max_size=5,
        ),
        created_by=created_by_strategy,
        delete_flags=st.lists(st.booleans(), min_size=2, max_size=5),
    )
    def test_property_7_active_fir_query_filter(
        self, test_db, fir_datas, created_by, delete_flags
    ):
        """
        **Validates: Requirements 5.5, 7.1**

        Property 7: Active FIR query filter

        Generate mix of active/inactive FIRs, verify get_all_active_firs()
        returns only is_active=True records.
        """
        test_db.rollback()

        # Deduplicate by icao_code to avoid constraint violations
        seen_codes = set()
        unique_firs = []
        for fir_data in fir_datas:
            if fir_data.icao_code not in seen_codes:
                seen_codes.add(fir_data.icao_code)
                unique_firs.append(fir_data)

        if len(unique_firs) < 2:
            return  # Need at least 2 unique FIRs for a meaningful test

        # Clean up existing FIRs for these icao_codes
        for fir_data in unique_firs:
            test_db.query(IataFir).filter(
                IataFir.icao_code == fir_data.icao_code
            ).delete()
        test_db.commit()

        service = FIRService(test_db)

        # Create all FIRs
        created_firs = []
        for fir_data in unique_firs:
            fir = service.create_fir(fir_data, created_by)
            created_firs.append(fir)

        # Soft-delete some based on delete_flags
        expected_active_codes = set()
        for i, fir in enumerate(created_firs):
            flag = delete_flags[i] if i < len(delete_flags) else False
            if flag:
                service.soft_delete_fir(fir.icao_code)
            else:
                expected_active_codes.add(fir.icao_code)

        # Query active FIRs
        active_firs = service.get_all_active_firs()

        # Every returned record must have is_active=True
        for fir in active_firs:
            assert fir.is_active is True, (
                f"get_all_active_firs returned FIR with is_active={fir.is_active}"
            )

        # All our expected active codes must be in the result
        active_codes_in_result = {fir.icao_code for fir in active_firs}
        for code in expected_active_codes:
            assert code in active_codes_in_result, (
                f"Expected active FIR {code} not found in get_all_active_firs result"
            )


class TestFIRHistoryOrderingProperty:
    """
    Feature: fir-versioning-and-data-import, Property 8: FIR history ordering

    **Validates: Requirements 5.6, 7.2**

    For any ICAO code with multiple versions, get_fir_history(icao_code) SHALL
    return all versions for that ICAO code, and the returned list SHALL be ordered
    by version_number descending.
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        fir_data=fir_create_strategy(),
        n_updates=st.integers(min_value=1, max_value=5),
        created_by=created_by_strategy,
        updated_by=created_by_strategy,
    )
    def test_property_8_fir_history_ordering(
        self, test_db, fir_data, n_updates, created_by, updated_by
    ):
        """
        **Validates: Requirements 5.6, 7.2**

        Property 8: FIR history ordering

        Create FIR with N updates, verify get_fir_history() returns all versions
        ordered by version_number DESC.
        """
        test_db.rollback()

        # Clean up any existing FIR with same icao_code
        test_db.query(IataFir).filter(
            IataFir.icao_code == fir_data.icao_code
        ).delete()
        test_db.commit()

        service = FIRService(test_db)

        # Create initial FIR (v1)
        service.create_fir(fir_data, created_by)

        # Perform N updates
        for _ in range(n_updates):
            update_data = FIRUpdate(fir_name=f"Updated FIR {_}")
            service.update_fir(fir_data.icao_code, update_data, updated_by)

        # Get history
        history = service.get_fir_history(fir_data.icao_code)

        # Total versions should be 1 (initial) + n_updates
        expected_total = 1 + n_updates
        assert len(history) == expected_total, (
            f"History should have {expected_total} versions, got {len(history)}"
        )

        # Verify ordering: version_number descending
        version_numbers = [fir.version_number for fir in history]
        for i in range(len(version_numbers) - 1):
            assert version_numbers[i] > version_numbers[i + 1], (
                f"History not ordered by version_number DESC: {version_numbers}"
            )

        # Verify all version numbers are present
        expected_versions = set(range(1, expected_total + 1))
        actual_versions = set(version_numbers)
        assert actual_versions == expected_versions, (
            f"Expected versions {expected_versions}, got {actual_versions}"
        )


class TestNonExistentFIRErrorsProperty:
    """
    Feature: fir-versioning-and-data-import, Property 9: Operations on non-existent FIRs raise errors

    **Validates: Requirements 5.7, 5.8, 7.7**

    For any ICAO code that has no active FIR record, calling update_fir,
    soft_delete_fir, or rollback_fir SHALL raise a FIRNotFoundException.
    Additionally, for any ICAO code and version number that does not exist,
    calling rollback_fir SHALL raise a FIRNotFoundException.
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        icao_code=icao_code_strategy,
        created_by=created_by_strategy,
    )
    def test_property_9_operations_on_non_existent_firs_raise_errors(
        self, test_db, icao_code, created_by
    ):
        """
        **Validates: Requirements 5.7, 5.8, 7.7**

        Property 9: Operations on non-existent FIRs raise errors

        Generate random non-existent ICAO codes, verify update_fir,
        soft_delete_fir, rollback_fir raise FIRNotFoundException.
        """
        test_db.rollback()

        # Ensure no FIR exists for this icao_code
        test_db.query(IataFir).filter(
            IataFir.icao_code == icao_code
        ).delete()
        test_db.commit()

        service = FIRService(test_db)

        # update_fir should raise FIRNotFoundException
        update_data = FIRUpdate(fir_name="Should Fail")
        with pytest.raises(FIRNotFoundException):
            service.update_fir(icao_code, update_data, created_by)

        # soft_delete_fir should raise FIRNotFoundException
        with pytest.raises(FIRNotFoundException):
            service.soft_delete_fir(icao_code)

        # rollback_fir should raise FIRNotFoundException
        with pytest.raises(FIRNotFoundException):
            service.rollback_fir(icao_code, 1)
