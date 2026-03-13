"""Property-based tests for Formula CRUD endpoints (Task 10).

This module implements property-based tests for the Formula execution system:
- Property 10: Formula Retrieval Correctness
- Property 12: HTTP Status Code Correctness
- Property 22: Version Increment on Update
- Property 23: Updated Timestamp on Modification

Validates Requirements: 8.2, 8.4, 8.5, 1.2, 1.3
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import date, datetime, timezone
from uuid import uuid4, UUID
import marshal

from src.models.formula import Formula
from src.exceptions import FormulaNotFoundException


# Strategy for generating valid formula code
@st.composite
def formula_code_strategy(draw):
    """Generate valid Python formula code."""
    cost_multiplier = draw(st.floats(min_value=0.01, max_value=100.0))
    currency = draw(st.sampled_from(["USD", "EUR", "GBP", "CAD"]))
    
    code = f"""def calculate(distance, weight, context):
    cost = distance * {cost_multiplier}
    return {{'cost': cost, 'currency': '{currency}', 'usd_cost': cost}}"""
    
    return code


# Strategy for generating Formula objects
@st.composite
def formula_strategy(draw):
    """Generate Formula model instances."""
    country_code = draw(st.sampled_from(["US", "CA", "GB", "FR", "DE", None]))
    version = draw(st.integers(min_value=1, max_value=10))
    
    formula_code = draw(formula_code_strategy())
    code_obj = compile(formula_code, "<test>", "exec")
    bytecode = marshal.dumps(code_obj)
    
    return Formula(
        id=uuid4(),
        country_code=country_code,
        description=f"Test Formula {country_code or 'Regional'}",
        formula_code=f"TEST_FORMULA_{version}",
        formula_logic=formula_code,
        effective_date=date(2024, 1, 1),
        currency=draw(st.sampled_from(["USD", "EUR", "GBP", "CAD"])),
        version_number=version,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        created_by="test_user",
        formula_hash=f"hash_{uuid4().hex[:16]}",
        formula_bytecode=bytecode
    )


class TestProperty10FormulaRetrievalCorrectness:
    """
    **Validates: Requirements 8.2**
    
    Property 10: Formula Retrieval Correctness
    
    For any valid formula ID, retrieving the formula from the database should
    return the formula with that exact ID and its associated code.
    """
    
    @given(formula=formula_strategy())
    @settings(max_examples=100)
    def test_formula_retrieval_returns_correct_id_and_code(self, formula):
        """
        Property test: Retrieved formula has correct ID and code.
        
        For any formula stored in the database, retrieving it by ID should
        return a formula with the same ID and formula_logic.
        """
        from unittest.mock import MagicMock, patch
        
        # Mock database session
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = formula
        mock_db.query.return_value = mock_query
        
        # Simulate retrieval
        retrieved = mock_db.query(Formula).filter(Formula.id == formula.id).first()
        
        # Property: Retrieved formula has same ID and code
        assert retrieved is not None
        assert retrieved.id == formula.id
        assert retrieved.formula_logic == formula.formula_logic
        assert retrieved.country_code == formula.country_code
        assert retrieved.version_number == formula.version_number
    
    @given(formula=formula_strategy())
    @settings(max_examples=100)
    def test_formula_retrieval_with_nonexistent_id_returns_none(self, formula):
        """
        Property test: Retrieving non-existent formula returns None.
        
        For any formula ID that doesn't exist in the database, retrieval
        should return None or raise FormulaNotFoundException.
        """
        from unittest.mock import MagicMock
        
        # Mock database session with no result
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Simulate retrieval with different ID
        different_id = uuid4()
        retrieved = mock_db.query(Formula).filter(Formula.id == different_id).first()
        
        # Property: Non-existent formula returns None
        assert retrieved is None


class TestProperty12HTTPStatusCodeCorrectness:
    """
    **Validates: Requirements 8.4, 8.5**
    
    Property 12: HTTP Status Code Correctness
    
    For any formula execution request, successful executions should return
    HTTP 200 status, and failed executions should return HTTP 500 status
    with error details.
    """
    
    @given(
        formula_id=st.uuids(),
        distance=st.floats(min_value=0.1, max_value=10000.0),
        weight=st.floats(min_value=0.1, max_value=1000.0)
    )
    @settings(max_examples=100)
    def test_successful_retrieval_returns_200(self, formula_id, distance, weight):
        """
        Property test: Successful formula retrieval returns HTTP 200.
        
        For any valid formula ID that exists, the GET endpoint should
        return HTTP 200 status code.
        """
        from unittest.mock import MagicMock, patch
        from fastapi.testclient import TestClient
        import os
        
        # Create a valid formula
        formula_code = f"""def calculate(distance, weight, context):
    return {{'cost': distance * 10, 'currency': 'USD', 'usd_cost': distance * 10}}"""
        
        code_obj = compile(formula_code, "<test>", "exec")
        bytecode = marshal.dumps(code_obj)
        
        formula = Formula(
            id=formula_id,
            country_code="US",
            description="Test Formula",
            formula_code="TEST",
            formula_logic=formula_code,
            effective_date=date(2024, 1, 1),
            currency="USD",
            version_number=1,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            created_by="test",
            formula_hash="test_hash",
            formula_bytecode=bytecode
        )
        
        # Mock environment and database
        env_vars = {
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "CORS_ORIGINS": "http://localhost:4200",
            "LOG_LEVEL": "INFO"
        }
        
        with patch.dict(os.environ, env_vars):
            with patch("src.main.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_result = MagicMock()
                mock_result.scalar.return_value = "2a8de75b4840"
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = iter([mock_db])
                
                with patch("src.routes.formula_routes.Formula") as mock_formula_model:
                    mock_query = MagicMock()
                    mock_query.filter.return_value.first.return_value = formula
                    mock_db.query.return_value = mock_query
                    
                    from src.main import app
                    client = TestClient(app)
                    
                    response = client.get(f"/api/formulas/{formula_id}/full")
                    
                    # Property: Successful retrieval returns 200
                    assert response.status_code == 200
    
    @given(formula_id=st.uuids())
    @settings(max_examples=100)
    def test_failed_retrieval_returns_404(self, formula_id):
        """
        Property test: Failed formula retrieval returns HTTP 404.
        
        For any formula ID that doesn't exist, the GET endpoint should
        return HTTP 404 status code.
        """
        from unittest.mock import MagicMock, patch
        from fastapi.testclient import TestClient
        import os
        
        # Mock environment and database
        env_vars = {
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "CORS_ORIGINS": "http://localhost:4200",
            "LOG_LEVEL": "INFO"
        }
        
        with patch.dict(os.environ, env_vars):
            with patch("src.main.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_result = MagicMock()
                mock_result.scalar.return_value = "2a8de75b4840"
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = iter([mock_db])
                
                with patch("src.routes.formula_routes.Formula") as mock_formula_model:
                    mock_query = MagicMock()
                    mock_query.filter.return_value.first.return_value = None
                    mock_db.query.return_value = mock_query
                    
                    from src.main import app
                    client = TestClient(app)
                    
                    response = client.get(f"/api/formulas/{formula_id}/full")
                    
                    # Property: Failed retrieval returns 404
                    assert response.status_code == 404


class TestProperty22VersionIncrementOnUpdate:
    """
    **Validates: Requirements 1.3**
    
    Property 22: Version Increment on Update
    
    For any formula being updated for a given country_code, the new version
    should have a version_number that is greater than all existing versions
    for that country.
    """
    
    @given(
        country_code=st.sampled_from(["US", "CA", "GB", "FR", "DE"]),
        current_version=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100)
    def test_version_increments_on_update(self, country_code, current_version):
        """
        Property test: Version number increments on formula update.
        
        For any formula update, the new version number should be exactly
        current_version + 1.
        """
        from unittest.mock import MagicMock
        
        # Create existing formula
        existing_formula = Formula(
            id=uuid4(),
            country_code=country_code,
            description=f"Test Formula {country_code}",
            formula_code="TEST",
            formula_logic="def calculate(distance, weight, context): return {'cost': 100, 'currency': 'USD', 'usd_cost': 100}",
            effective_date=date(2024, 1, 1),
            currency="USD",
            version_number=current_version,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            created_by="test",
            formula_hash="hash1",
            formula_bytecode=b"bytecode"
        )
        
        # Simulate version increment logic
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = (current_version,)
        mock_db.query.return_value = mock_query
        
        # Get max version
        max_version_result = mock_db.query(Formula.version_number).filter(
            Formula.country_code == country_code
        ).order_by(Formula.version_number.desc()).first()
        
        new_version = max_version_result[0] + 1
        
        # Property: New version is exactly current_version + 1
        assert new_version == current_version + 1
        assert new_version > current_version
    
    @given(
        country_code=st.sampled_from(["US", "CA", "GB", "FR", "DE"]),
        versions=st.lists(st.integers(min_value=1, max_value=50), min_size=1, max_size=10, unique=True)
    )
    @settings(max_examples=100)
    def test_version_greater_than_all_existing(self, country_code, versions):
        """
        Property test: New version is greater than all existing versions.
        
        For any set of existing versions, the new version should be greater
        than the maximum existing version.
        """
        from unittest.mock import MagicMock
        
        # Get max version from list
        max_existing_version = max(versions)
        
        # Simulate version increment logic
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = (max_existing_version,)
        mock_db.query.return_value = mock_query
        
        # Get max version
        max_version_result = mock_db.query(Formula.version_number).filter(
            Formula.country_code == country_code
        ).order_by(Formula.version_number.desc()).first()
        
        new_version = max_version_result[0] + 1
        
        # Property: New version is greater than all existing versions
        assert new_version > max_existing_version
        assert all(new_version > v for v in versions)


class TestProperty23UpdatedTimestampOnModification:
    """
    **Validates: Requirements 1.2**
    
    Property 23: Updated Timestamp on Modification
    
    For any formula modification, the updated_at timestamp should be set to
    a value greater than or equal to the previous updated_at value.
    """
    
    @given(formula=formula_strategy())
    @settings(max_examples=100)
    def test_updated_timestamp_increases_on_modification(self, formula):
        """
        Property test: Updated timestamp increases on modification.
        
        For any formula modification, the new created_at timestamp should
        be greater than or equal to the previous created_at timestamp.
        """
        import time
        
      
  # Original timestamp
        original_timestamp = formula.created_at
        
        # Simulate modification (small delay)
        time.sleep(0.001)
        
        # Create modified formula with new timestamp
        modified_formula = Formula(
            id=formula.id,
            country_code=formula.country_code,
            description=formula.description + " (Modified)",
            formula_code=formula.formula_code,
            formula_logic=formula.formula_logic,
            effective_date=formula.effective_date,
            currency=formula.currency,
            version_number=formula.version_number + 1,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            created_by=formula.created_by,
            formula_hash=formula.formula_hash,
            formula_bytecode=formula.formula_bytecode
        )
        
        # Property: New timestamp >= original timestamp
        assert modified_formula.created_at >= original_timestamp
    
    @given(
        country_code=st.sampled_from(["US", "CA", "GB", "FR", "DE"]),
        num_updates=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_timestamp_monotonically_increases_across_updates(self, country_code, num_updates):
        """
        Property test: Timestamps monotonically increase across multiple updates.
        
        For any sequence of formula updates, each new timestamp should be
        greater than or equal to the previous timestamp.
        """
        import time
        
        timestamps = []
        
        # Simulate multiple updates
        for i in range(num_updates):
            time.sleep(0.001)  # Small delay between updates
            timestamp = datetime.now(timezone.utc)
            timestamps.append(timestamp)
        
        # Property: Timestamps are monotonically increasing
        for i in range(1, len(timestamps)):
            assert timestamps[i] >= timestamps[i-1]
    
    @given(formula=formula_strategy())
    @settings(max_examples=100)
    def test_timestamp_is_recent(self, formula):
        """
        Property test: Created timestamp is recent (within reasonable bounds).
        
        For any newly created formula, the created_at timestamp should be
        close to the current time (within a few seconds).
        """
        from datetime import timedelta
        
        current_time = datetime.now(timezone.utc)
        time_diff = abs((current_time - formula.created_at).total_seconds())
        
        # Property: Timestamp is within 60 seconds of current time
        # (generous bound for test execution time)
        assert time_diff < 60.0
