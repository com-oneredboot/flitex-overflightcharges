"""Property-based tests for FormulaCache.

These tests verify universal properties across many generated inputs using Hypothesis.
Each property test runs with a minimum of 100 iterations.

Feature: python-formula-execution-system
"""

import hashlib
import json
import pickle
from typing import Any
from unittest.mock import MagicMock, Mock
from uuid import UUID, uuid4

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from redis import Redis

from src.formula_execution.formula_cache import FormulaCache


# Strategy for generating valid UUIDs
uuid_strategy = st.uuids()

# Strategy for generating version numbers
version_strategy = st.integers(min_value=1, max_value=100)

# Strategy for generating bytecode (simulated as bytes)
bytecode_strategy = st.binary(min_size=10, max_size=1000)

# Strategy for generating distance values
distance_strategy = st.floats(
    min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False
)

# Strategy for generating weight values
weight_strategy = st.floats(
    min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False
)

# Strategy for generating context dictionaries
context_strategy = st.fixed_dictionaries(
    {
        "firTag": st.text(min_size=4, max_size=4, alphabet=st.characters(min_codepoint=65, max_codepoint=90)),
        "arrival": st.text(min_size=4, max_size=4, alphabet=st.characters(min_codepoint=65, max_codepoint=90)),
        "departure": st.text(min_size=4, max_size=4, alphabet=st.characters(min_codepoint=65, max_codepoint=90)),
        "isFirstFir": st.booleans(),
        "isLastFir": st.booleans(),
        "firName": st.text(min_size=1, max_size=50),
        "originCountry": st.text(min_size=2, max_size=2, alphabet=st.characters(min_codepoint=65, max_codepoint=90)),
        "destinationCountry": st.text(min_size=2, max_size=2, alphabet=st.characters(min_codepoint=65, max_codepoint=90)),
    }
)

# Strategy for generating result dictionaries
result_strategy = st.fixed_dictionaries(
    {
        "cost": st.floats(min_value=0.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        "currency": st.sampled_from(["USD", "EUR", "GBP", "CAD", "JPY"]),
        "usd_cost": st.floats(min_value=0.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    }
)


def compute_params_hash(distance: float, weight: float, context: dict) -> str:
    """Compute SHA256 hash of execution parameters.
    
    This matches the hash computation that would be used in the actual system.
    """
    params_str = f"{distance}:{weight}:{json.dumps(context, sort_keys=True)}"
    return hashlib.sha256(params_str.encode()).hexdigest()[:16]


def create_mock_redis() -> Mock:
    """Create a mock Redis client that simulates real Redis behavior.
    
    This is a factory function to ensure each call gets a fresh Redis mock
    with empty storage for test isolation.
    """
    redis_mock = Mock(spec=Redis)
    # Use a dictionary to simulate Redis storage (fresh for each call)
    storage = {}
    
    def mock_get(key):
        return storage.get(key)
    
    def mock_setex(key, ttl, value):
        storage[key] = value
    
    def mock_delete(key):
        if key in storage:
            del storage[key]
    
    def mock_scan_iter(match):
        # Simple pattern matching for keys
        pattern = match.replace("*", "")
        return [k for k in storage.keys() if k.startswith(pattern)]
    
    redis_mock.get = mock_get
    redis_mock.setex = mock_setex
    redis_mock.delete = mock_delete
    redis_mock.scan_iter = mock_scan_iter
    redis_mock._storage = storage  # Expose storage for test inspection
    
    return redis_mock


class TestFormulaCacheProperties:
    """Property-based tests for FormulaCache caching behavior."""

    @settings(
        max_examples=100,
        deadline=None,
    )
    @given(
        formula_id=uuid_strategy,
        version=version_strategy,
        bytecode=bytecode_strategy,
    )
    def test_property_7_bytecode_cache_round_trip(
        self,
        formula_id: UUID,
        version: int,
        bytecode: bytes,
    ) -> None:
        """
        **Validates: Requirements 5.1, 5.2**

        Property 7: Bytecode Cache Round Trip

        For any formula, after first compilation, subsequent executions should
        use cached bytecode until the formula is updated, at which point the
        cache should be invalidated.

        This test verifies:
        1. First compilation stores bytecode in cache
        2. Subsequent retrievals get the same bytecode from cache (cache hit)
        3. Cache invalidation removes the bytecode
        4. After invalidation, cache retrieval returns None (cache miss)
        """
        # Create fresh mock Redis and cache instance for this test
        mock_redis = create_mock_redis()
        cache = FormulaCache(redis_client=mock_redis)

        # Initial state: bytecode should not be in cache
        initial_bytecode = cache.get_bytecode(formula_id, version)
        assert initial_bytecode is None, "Bytecode should not be cached initially"
        assert cache._bytecode_misses == 1, "Should record cache miss"
        assert cache._bytecode_hits == 0, "Should have no cache hits yet"

        # Store bytecode (simulating first compilation)
        cache.store_bytecode(formula_id, version, bytecode)

        # Verify bytecode is now in cache
        cached_bytecode = cache.get_bytecode(formula_id, version)
        assert cached_bytecode is not None, "Bytecode should be cached after storage"
        assert cached_bytecode == bytecode, "Cached bytecode should match original"
        assert cache._bytecode_hits == 1, "Should record cache hit"

        # Subsequent retrieval should also hit cache
        cached_bytecode_2 = cache.get_bytecode(formula_id, version)
        assert cached_bytecode_2 == bytecode, "Subsequent retrieval should return same bytecode"
        assert cache._bytecode_hits == 2, "Should record second cache hit"

        # Simulate formula update by invalidating cache
        cache.invalidate_formula(formula_id)

        # After invalidation, bytecode should not be in cache
        invalidated_bytecode = cache.get_bytecode(formula_id, version)
        assert invalidated_bytecode is None, "Bytecode should not be cached after invalidation"
        assert cache._bytecode_misses == 2, "Should record cache miss after invalidation"

        # Verify cache key was actually removed from Redis
        expected_key = f"formula:bytecode:{formula_id}:{version}"
        assert expected_key not in mock_redis._storage, "Cache key should be removed from Redis"

    @settings(
        max_examples=100,
        deadline=None,
    )
    @given(
        formula_id=uuid_strategy,
        version=version_strategy,
        bytecode1=bytecode_strategy,
        bytecode2=bytecode_strategy,
    )
    def test_property_7_bytecode_cache_invalidation_on_update(
        self,
        formula_id: UUID,
        version: int,
        bytecode1: bytes,
        bytecode2: bytes,
    ) -> None:
        """
        **Validates: Requirements 5.1, 5.2**

        Property 7: Bytecode Cache Round Trip (Update Scenario)

        For any formula that is updated, the cache should be invalidated,
        and the new bytecode should be cached separately.

        This test verifies:
        1. Original bytecode is cached
        2. After update (invalidation + new version), old cache is cleared
        3. New bytecode can be cached independently
        """
        # Ensure bytecodes are different for this test
        if bytecode1 == bytecode2:
            bytecode2 = bytecode1 + b"_updated"

        # Create fresh mock Redis and cache instance for this test
        mock_redis = create_mock_redis()
        cache = FormulaCache(redis_client=mock_redis)

        # Store original bytecode
        cache.store_bytecode(formula_id, version, bytecode1)
        
        # Verify original is cached
        cached = cache.get_bytecode(formula_id, version)
        assert cached == bytecode1, "Original bytecode should be cached"

        # Simulate formula update: invalidate cache
        cache.invalidate_formula(formula_id)

        # Verify original is no longer cached
        cached_after_invalidation = cache.get_bytecode(formula_id, version)
        assert cached_after_invalidation is None, "Original bytecode should be invalidated"

        # Store new bytecode (could be same version or new version)
        new_version = version + 1
        cache.store_bytecode(formula_id, new_version, bytecode2)

        # Verify new bytecode is cached
        cached_new = cache.get_bytecode(formula_id, new_version)
        assert cached_new == bytecode2, "New bytecode should be cached"

        # Verify old version is still not cached
        cached_old = cache.get_bytecode(formula_id, version)
        assert cached_old is None, "Old version should remain invalidated"

    @settings(
        max_examples=100,
        deadline=None,
    )
    @given(
        formula_id=uuid_strategy,
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
        result=result_strategy,
    )
    def test_property_8_result_cache_consistency(
        self,
        formula_id: UUID,
        distance: float,
        weight: float,
        context: dict,
        result: dict,
    ) -> None:
        """
        **Validates: Requirements 5.3**

        Property 8: Result Cache Consistency

        For any formula execution with specific parameters (distance, weight,
        context), executing twice with identical parameters should return the
        same result, with the second execution being a cache hit.

        This test verifies:
        1. First execution stores result in cache
        2. Second execution with identical parameters returns cached result
        3. Cache hit is recorded for second execution
        4. Cached result matches original result exactly
        """
        # Create fresh mock Redis and cache instance for this test
        mock_redis = create_mock_redis()
        cache = FormulaCache(redis_client=mock_redis)

        # Compute params hash (as would be done in actual execution)
        params_hash = compute_params_hash(distance, weight, context)

        # Initial state: result should not be in cache
        initial_result = cache.get_result(formula_id, params_hash)
        assert initial_result is None, "Result should not be cached initially"
        assert cache._result_misses == 1, "Should record cache miss"
        assert cache._result_hits == 0, "Should have no cache hits yet"

        # Store result (simulating first execution)
        cache.store_result(formula_id, params_hash, result)

        # Second execution with identical parameters should hit cache
        cached_result = cache.get_result(formula_id, params_hash)
        assert cached_result is not None, "Result should be cached after storage"
        assert cached_result == result, "Cached result should match original exactly"
        assert cache._result_hits == 1, "Should record cache hit"

        # Third execution should also hit cache
        cached_result_2 = cache.get_result(formula_id, params_hash)
        assert cached_result_2 == result, "Subsequent retrieval should return same result"
        assert cache._result_hits == 2, "Should record second cache hit"

        # Verify all fields in cached result match original
        for key, value in result.items():
            assert key in cached_result_2, f"Cached result missing key '{key}'"
            assert cached_result_2[key] == value, f"Cached result value for '{key}' doesn't match"

    @settings(
        max_examples=100,
        deadline=None,
    )
    @given(
        formula_id=uuid_strategy,
        distance1=distance_strategy,
        weight1=weight_strategy,
        context1=context_strategy,
        distance2=distance_strategy,
        weight2=weight_strategy,
        context2=context_strategy,
        result1=result_strategy,
        result2=result_strategy,
    )
    def test_property_8_result_cache_different_parameters(
        self,
        formula_id: UUID,
        distance1: float,
        weight1: float,
        context1: dict,
        distance2: float,
        weight2: float,
        context2: dict,
        result1: dict,
        result2: dict,
    ) -> None:
        """
        **Validates: Requirements 5.3**

        Property 8: Result Cache Consistency (Different Parameters)

        For any formula execution with different parameters, each unique
        parameter combination should have its own cache entry.

        This test verifies:
        1. Different parameters produce different cache keys
        2. Each parameter combination caches independently
        3. Retrieving with specific parameters returns the correct cached result
        """
        # Ensure parameters are different
        if (distance1 == distance2 and weight1 == weight2 and 
            json.dumps(context1, sort_keys=True) == json.dumps(context2, sort_keys=True)):
            # Make distance2 different
            distance2 = distance1 + 100.0

        # Create fresh mock Redis and cache instance for this test
        mock_redis = create_mock_redis()
        cache = FormulaCache(redis_client=mock_redis)

        # Compute params hashes
        params_hash1 = compute_params_hash(distance1, weight1, context1)
        params_hash2 = compute_params_hash(distance2, weight2, context2)

        # Verify hashes are different for different parameters
        assert params_hash1 != params_hash2, "Different parameters should produce different hashes"

        # Store first result
        cache.store_result(formula_id, params_hash1, result1)

        # Store second result
        cache.store_result(formula_id, params_hash2, result2)

        # Retrieve first result - should get result1
        cached_result1 = cache.get_result(formula_id, params_hash1)
        assert cached_result1 == result1, "Should retrieve correct result for first parameters"

        # Retrieve second result - should get result2
        cached_result2 = cache.get_result(formula_id, params_hash2)
        assert cached_result2 == result2, "Should retrieve correct result for second parameters"

        # Verify both results are still cached independently
        cached_result1_again = cache.get_result(formula_id, params_hash1)
        assert cached_result1_again == result1, "First result should still be cached"

        cached_result2_again = cache.get_result(formula_id, params_hash2)
        assert cached_result2_again == result2, "Second result should still be cached"

    @settings(
        max_examples=100,
        deadline=None,
    )
    @given(
        formula_id=uuid_strategy,
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
        result=result_strategy,
    )
    def test_property_8_result_cache_invalidation(
        self,
        formula_id: UUID,
        distance: float,
        weight: float,
        context: dict,
        result: dict,
    ) -> None:
        """
        **Validates: Requirements 5.3**

        Property 8: Result Cache Consistency (Invalidation)

        For any formula, when the formula is updated (cache invalidated),
        all result caches for that formula should be cleared.

        This test verifies:
        1. Result is cached after first execution
        2. Cache invalidation removes all result caches for the formula
        3. After invalidation, cache retrieval returns None
        """
        # Create fresh mock Redis and cache instance for this test
        mock_redis = create_mock_redis()
        cache = FormulaCache(redis_client=mock_redis)

        # Compute params hash
        params_hash = compute_params_hash(distance, weight, context)

        # Store result
        cache.store_result(formula_id, params_hash, result)

        # Verify result is cached
        cached_result = cache.get_result(formula_id, params_hash)
        assert cached_result == result, "Result should be cached"

        # Invalidate formula cache
        cache.invalidate_formula(formula_id)

        # Verify result is no longer cached
        cached_after_invalidation = cache.get_result(formula_id, params_hash)
        assert cached_after_invalidation is None, "Result should not be cached after invalidation"

        # Verify cache key was actually removed from Redis
        expected_key = f"formula:result:{formula_id}:{params_hash}"
        assert expected_key not in mock_redis._storage, "Cache key should be removed from Redis"

    @settings(
        max_examples=100,
        deadline=None,
    )
    @given(
        formula_id=uuid_strategy,
        version=version_strategy,
        bytecode=bytecode_strategy,
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
        result=result_strategy,
    )
    def test_property_7_and_8_combined_cache_behavior(
        self,
        formula_id: UUID,
        version: int,
        bytecode: bytes,
        distance: float,
        weight: float,
        context: dict,
        result: dict,
    ) -> None:
        """
        **Validates: Requirements 5.1, 5.2, 5.3**

        Properties 7 & 8: Combined Bytecode and Result Cache Behavior

        For any formula execution, both bytecode and result caches should work
        together correctly, and invalidation should clear both cache types.

        This test verifies:
        1. Bytecode cache works independently
        2. Result cache works independently
        3. Invalidation clears both bytecode and result caches
        4. After invalidation, both caches return None
        """
        # Create fresh mock Redis and cache instance for this test
        mock_redis = create_mock_redis()
        cache = FormulaCache(redis_client=mock_redis)

        # Compute params hash
        params_hash = compute_params_hash(distance, weight, context)

        # Store bytecode
        cache.store_bytecode(formula_id, version, bytecode)

        # Store result
        cache.store_result(formula_id, params_hash, result)

        # Verify both are cached
        cached_bytecode = cache.get_bytecode(formula_id, version)
        assert cached_bytecode == bytecode, "Bytecode should be cached"

        cached_result = cache.get_result(formula_id, params_hash)
        assert cached_result == result, "Result should be cached"

        # Invalidate formula cache (should clear both)
        cache.invalidate_formula(formula_id)

        # Verify both are invalidated
        cached_bytecode_after = cache.get_bytecode(formula_id, version)
        assert cached_bytecode_after is None, "Bytecode should be invalidated"

        cached_result_after = cache.get_result(formula_id, params_hash)
        assert cached_result_after is None, "Result should be invalidated"

        # Verify both cache keys were removed from Redis
        bytecode_key = f"formula:bytecode:{formula_id}:{version}"
        result_key = f"formula:result:{formula_id}:{params_hash}"
        
        assert bytecode_key not in mock_redis._storage, "Bytecode cache key should be removed"
        assert result_key not in mock_redis._storage, "Result cache key should be removed"
