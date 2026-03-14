"""Property-based tests for FIR database constraint enforcement.

These tests verify that PostgreSQL database constraints correctly enforce
data integrity for the iata_firs table using direct SQLAlchemy inserts
(not the service layer).

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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
import os

from src.models.iata_fir import IataFir
from src.database import Base


# --- Reuse strategies from test_fir_service_properties.py ---

pg_safe_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="\x00",
    ),
)

# ICAO code: 4 uppercase alphanumeric, must contain at least one letter
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

version_number_strategy = st.integers(min_value=1, max_value=1000)


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


def _make_fir(icao_code, version_number, is_active, created_by="test-user"):
    """Helper to create an IataFir instance with minimal required fields."""
    return IataFir(
        id=uuid.uuid4(),
        icao_code=icao_code,
        fir_name=f"Test FIR {icao_code}",
        country_code="GB",
        country_name="United Kingdom",
        geojson_geometry={
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
        },
        avoid_status=False,
        version_number=version_number,
        is_active=is_active,
        activation_date=datetime.now(timezone.utc) if is_active else None,
        created_at=datetime.now(timezone.utc),
        created_by=created_by,
    )


class TestUniqueVersionNumberPerICAOCodeProperty:
    """
    Feature: fir-versioning-and-data-import, Property 2: Unique version number per ICAO code

    **Validates: Requirements 1.10**

    For any ICAO code and any two FIR records sharing that ICAO code, their
    version_number values SHALL be distinct. Attempting to insert a duplicate
    (icao_code, version_number) pair SHALL raise an IntegrityError.
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        icao_code=icao_code_strategy,
        version_number=version_number_strategy,
        created_by=created_by_strategy,
    )
    def test_property_2_unique_version_number_per_icao_code(
        self, test_db, icao_code, version_number, created_by
    ):
        """
        **Validates: Requirements 1.10**

        Property 2: Unique version number per ICAO code

        Attempt duplicate (icao_code, version_number) inserts, verify IntegrityError.
        """
        test_db.rollback()

        # Clean up any existing FIR with same icao_code
        test_db.query(IataFir).filter(
            IataFir.icao_code == icao_code
        ).delete()
        test_db.commit()

        # Insert first FIR with given icao_code and version_number
        fir1 = _make_fir(icao_code, version_number, is_active=True, created_by=created_by)
        test_db.add(fir1)
        test_db.commit()

        # Attempt to insert second FIR with same (icao_code, version_number)
        # This must be is_active=False to avoid triggering the partial unique
        # index on active FIRs — we are testing the composite unique constraint only.
        fir2 = _make_fir(icao_code, version_number, is_active=False, created_by=created_by)
        test_db.add(fir2)

        with pytest.raises(IntegrityError):
            test_db.commit()

        # Rollback so the session is clean for the next iteration
        test_db.rollback()


class TestOneActiveFIRPerICAOCodeProperty:
    """
    Feature: fir-versioning-and-data-import, Property 3: One active FIR per ICAO code

    **Validates: Requirements 2.1, 2.2**

    For any ICAO code, at most one FIR record with is_active=True SHALL exist
    at any time. Attempting to insert a second active FIR for the same ICAO code
    SHALL raise an IntegrityError from the partial unique index.
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
    def test_property_3_one_active_fir_per_icao_code(
        self, test_db, icao_code, created_by
    ):
        """
        **Validates: Requirements 2.1, 2.2**

        Property 3: One active FIR per ICAO code

        Insert two active FIRs for same ICAO code, verify IntegrityError
        from partial unique index.
        """
        test_db.rollback()

        # Clean up any existing FIR with same icao_code
        test_db.query(IataFir).filter(
            IataFir.icao_code == icao_code
        ).delete()
        test_db.commit()

        # Insert first active FIR (version 1)
        fir1 = _make_fir(icao_code, version_number=1, is_active=True, created_by=created_by)
        test_db.add(fir1)
        test_db.commit()

        # Attempt to insert second active FIR (version 2) for same ICAO code
        fir2 = _make_fir(icao_code, version_number=2, is_active=True, created_by=created_by)
        test_db.add(fir2)

        with pytest.raises(IntegrityError):
            test_db.commit()

        # Rollback so the session is clean for the next iteration
        test_db.rollback()
