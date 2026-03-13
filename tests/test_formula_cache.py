"""
Unit Tests for FormulaCache

Tests the FormulaCache class that provides Redis-based caching for
compiled formula bytecode and execution results.

Requirements: 5.1, 5.2, 5.3
"""

import pickle
from uuid import uuid4, UUID

import pytest
from redis import Redis, RedisError
from unittest.mock import Mock, MagicMock, patch

from src.formula_execution.formula_cache import FormulaCache


class TestFormulaCacheInitialization:
    """Test suite for FormulaCache initialization."""

    def test_initialization_with_redis_client(self) -> None:
        """Test that FormulaCache initializes with Redis client."""
        mock_redis = Mock(spec=Redis)
        cache = FormulaCache(redis_client=mock_redis)

        assert cache._redis is mock_redis
        assert cache._enabled is True
        assert cache._bytecode_hits == 0
        assert cache._bytecode_misses == 0
        assert cache._result_hits == 0
        assert cache._result_misses == 0

    def test_initialization_without_redis_client(self) -> None:
        """Test that FormulaCache initializes without Redis client (disabled)."""
        cache = FormulaCache(redis_client=None)

        assert cache._redis is None
        assert cache._enabled is False

    def test_initialization_with_none_explicitly(self) -> None:
        """Test that FormulaCache handles None client gracefully."""
        cache = FormulaCache(None)

        assert cache._redis is None
        assert cache._enabled is False


class TestFormulaCacheBytecode:
    """Test suite for bytecode caching operations."""

    @pytest.fixture
    def mock_redis(self) -> Mock:
        """Create a mock Redis client."""
        return Mock(spec=Redis)

    @pytest.fixture
    def cache(self, mock_redis: Mock) -> FormulaCache:
        """Create a FormulaCache instance with mock Redis."""
        return FormulaCache(redis_client=mock_redis)

    @pytest.fixture
    def formula_id(self) -> UUID:
        """Create a test formula UUID."""
        return uuid4()

    @pytest.fixture
    def sample_bytecode(self) -> bytes:
        """Create sample bytecode."""
        return b"compiled_bytecode_data"

    def test_get_bytecode_cache_hit(
        self, cache: FormulaCache, mock_redis: Mock, formula_id: UUID
    ) -> None:
        """
        Test retrieving bytecode from cache when it exists.

        Requirements: 5.1
        """
        version = 1
        expected_bytecode = b"cached_bytecode"
        mock_redis.get.return_value = expected_bytecode

        result = cache.get_bytecode(formula_id, version)

        assert result == expected_bytecode
        mock_redis.get.assert_called_once_with(
            f"formula:bytecode:{formula_id}:{version}"
        )
        assert cache._bytecode_hits == 1
        assert cache._bytecode_misses == 0

    def test_get_bytecode_cache_miss(
        self, cache: FormulaCache, mock_redis: Mock, formula_id: UUID
    ) -> None:
        """
        Test retrieving bytecode when not in cache.

        Requirements: 5.1
        """
        version = 1
        mock_redis.get.return_value = None

        result = cache.get_bytecode(formula_id, version)

        assert result is None
        mock_redis.get.assert_called_once()
        assert cache._bytecode_hits == 0
        assert cache._bytecode_misses == 1

    def test_get_bytecode_when_disabled(self, formula_id: UUID) -> None:
        """Test that get_bytecode returns None when caching is disabled."""
        cache = FormulaCache(redis_client=None)

        result = cache.get_bytecode(formula_id, 1)

        assert result is None

    def test_get_bytecode_redis_error(
        self, cache: FormulaCache, mock_redis: Mock, formula_id: UUID
    ) -> None:
        """Test that get_bytecode handles Redis errors gracefully."""
        mock_redis.get.side_effect = RedisError("Connection failed")

        result = cache.get_bytecode(formula_id, 1)

        assert result is None

    def test_store_bytecode_success(
        self,
        cache: FormulaCache,
        mock_redis: Mock,
        formula_id: UUID,
        sample_bytecode: bytes,
    ) -> None:
        """
        Test storing bytecode in cache.

        Requirements: 5.1
        """
        version = 1

        cache.store_bytecode(formula_id, version, sample_bytecode)

        mock_redis.setex.assert_called_once_with(
            f"formula:bytecode:{formula_id}:{version}",
            FormulaCache.BYTECODE_TTL,
            sample_bytecode,
        )

    def test_store_bytecode_custom_ttl(
        self,
        cache: FormulaCache,
        mock_redis: Mock,
        formula_id: UUID,
        sample_bytecode: bytes,
    ) -> None:
        """Test storing bytecode with custom TTL."""
        version = 1
        custom_ttl = 7200

        cache.store_bytecode(formula_id, version, sample_bytecode, custom_ttl)

        mock_redis.setex.assert_called_once_with(
            f"formula:bytecode:{formula_id}:{version}",
            custom_ttl,
            sample_bytecode,
        )

    def test_store_bytecode_when_disabled(
        self, formula_id: UUID, sample_bytecode: bytes
    ) -> None:
        """Test that store_bytecode does nothing when caching is disabled."""
        cache = FormulaCache(redis_client=None)

        # Should not raise an error
        cache.store_bytecode(formula_id, 1, sample_bytecode)

    def test_store_bytecode_redis_error(
        self,
        cache: FormulaCache,
        mock_redis: Mock,
        formula_id: UUID,
        sample_bytecode: bytes,
    ) -> None:
        """Test that store_bytecode handles Redis errors gracefully."""
        mock_redis.setex.side_effect = RedisError("Connection failed")

        # Should not raise an error
        cache.store_bytecode(formula_id, 1, sample_bytecode)

    def test_bytecode_key_format(self, cache: FormulaCache, formula_id: UUID) -> None:
        """Test that bytecode keys are formatted correctly."""
        version = 5
        expected_key = f"formula:bytecode:{formula_id}:{version}"

        key = cache._bytecode_key(formula_id, version)

        assert key == expected_key


class TestFormulaCacheResults:
    """Test suite for result caching operations."""

    @pytest.fixture
    def mock_redis(self) -> Mock:
        """Create a mock Redis client."""
        return Mock(spec=Redis)

    @pytest.fixture
    def cache(self, mock_redis: Mock) -> FormulaCache:
        """Create a FormulaCache instance with mock Redis."""
        return FormulaCache(redis_client=mock_redis)

    @pytest.fixture
    def formula_id(self) -> UUID:
        """Create a test formula UUID."""
        return uuid4()

    @pytest.fixture
    def params_hash(self) -> str:
        """Create a test params hash."""
        return "abc123def456"

    @pytest.fixture
    def sample_result(self) -> dict:
        """Create a sample result dictionary."""
        return {
            "cost": 1250.50,
            "currency": "USD",
            "usd_cost": 1250.50,
        }

    def test_get_result_cache_hit(
        self,
        cache: FormulaCache,
        mock_redis: Mock,
        formula_id: UUID,
        params_hash: str,
        sample_result: dict,
    ) -> None:
        """
        Test retrieving result from cache when it exists.

        Requirements: 5.3
        """
        mock_redis.get.return_value = pickle.dumps(sample_result)

        result = cache.get_result(formula_id, params_hash)

        assert result == sample_result
        mock_redis.get.assert_called_once_with(
            f"formula:result:{formula_id}:{params_hash}"
        )
        assert cache._result_hits == 1
        assert cache._result_misses == 0

    def test_get_result_cache_miss(
        self,
        cache: FormulaCache,
        mock_redis: Mock,
        formula_id: UUID,
        params_hash: str,
    ) -> None:
        """
        Test retrieving result when not in cache.

        Requirements: 5.3
        """
        mock_redis.get.return_value = None

        result = cache.get_result(formula_id, params_hash)

        assert result is None
        mock_redis.get.assert_called_once()
        assert cache._result_hits == 0
        assert cache._result_misses == 1

    def test_get_result_when_disabled(
        self, formula_id: UUID, params_hash: str
    ) -> None:
        """Test that get_result returns None when caching is disabled."""
        cache = FormulaCache(redis_client=None)

        result = cache.get_result(formula_id, params_hash)

        assert result is None

    def test_get_result_redis_error(
        self,
        cache: FormulaCache,
        mock_redis: Mock,
        formula_id: UUID,
        params_hash: str,
    ) -> None:
        """Test that get_result handles Redis errors gracefully."""
        mock_redis.get.side_effect = RedisError("Connection failed")

        result = cache.get_result(formula_id, params_hash)

        assert result is None

    def test_get_result_pickle_error(
        self,
        cache: FormulaCache,
        mock_redis: Mock,
        formula_id: UUID,
        params_hash: str,
    ) -> None:
        """Test that get_result handles pickle errors gracefully."""
        mock_redis.get.return_value = b"invalid_pickle_data"

        result = cache.get_result(formula_id, params_hash)

        assert result is None

    def test_store_result_success(
        self,
        cache: FormulaCache,
        mock_redis: Mock,
        formula_id: UUID,
        params_hash: str,
        sample_result: dict,
    ) -> None:
        """
        Test storing result in cache.

        Requirements: 5.3
        """
        cache.store_result(formula_id, params_hash, sample_result)

        # Verify setex was called with correct key, TTL, and pickled data
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == f"formula:result:{formula_id}:{params_hash}"
        assert call_args[0][1] == FormulaCache.RESULT_TTL
        # Verify the pickled data can be unpickled to the original result
        assert pickle.loads(call_args[0][2]) == sample_result

    def test_store_result_custom_ttl(
        self,
        cache: FormulaCache,
        mock_redis: Mock,
        formula_id: UUID,
        params_hash: str,
        sample_result: dict,
    ) -> None:
        """Test storing result with custom TTL."""
        custom_ttl = 600

        cache.store_result(formula_id, params_hash, sample_result, custom_ttl)

        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == custom_ttl

    def test_store_result_when_disabled(
        self, formula_id: UUID, params_hash: str, sample_result: dict
    ) -> None:
        """Test that store_result does nothing when caching is disabled."""
        cache = FormulaCache(redis_client=None)

        # Should not raise an error
        cache.store_result(formula_id, params_hash, sample_result)

    def test_store_result_redis_error(
        self,
        cache: FormulaCache,
        mock_redis: Mock,
        formula_id: UUID,
        params_hash: str,
        sample_result: dict,
    ) -> None:
        """Test that store_result handles Redis errors gracefully."""
        mock_redis.setex.side_effect = RedisError("Connection failed")

        # Should not raise an error
        cache.store_result(formula_id, params_hash, sample_result)

    def test_result_key_format(
        self, cache: FormulaCache, formula_id: UUID, params_hash: str
    ) -> None:
        """Test that result keys are formatted correctly."""
        expected_key = f"formula:result:{formula_id}:{params_hash}"

        key = cache._result_key(formula_id, params_hash)

        assert key == expected_key


class TestFormulaCacheInvalidation:
    """Test suite for cache invalidation operations."""

    @pytest.fixture
    def mock_redis(self) -> Mock:
        """Create a mock Redis client."""
        redis_mock = Mock(spec=Redis)
        # Mock scan_iter to return some keys
        redis_mock.scan_iter = Mock()
        return redis_mock

    @pytest.fixture
    def cache(self, mock_redis: Mock) -> FormulaCache:
        """Create a FormulaCache instance with mock Redis."""
        return FormulaCache(redis_client=mock_redis)

    @pytest.fixture
    def formula_id(self) -> UUID:
        """Create a test formula UUID."""
        return uuid4()

    def test_invalidate_formula_success(
        self, cache: FormulaCache, mock_redis: Mock, formula_id: UUID
    ) -> None:
        """
        Test invalidating all caches for a formula.

        Requirements: 5.2
        """
        # Mock scan_iter to return some keys
        bytecode_keys = [
            f"formula:bytecode:{formula_id}:1",
            f"formula:bytecode:{formula_id}:2",
        ]
        result_keys = [
            f"formula:result:{formula_id}:hash1",
            f"formula:result:{formula_id}:hash2",
        ]

        def scan_iter_side_effect(match):
            if "bytecode" in match:
                return iter(bytecode_keys)
            elif "result" in match:
                return iter(result_keys)
            return iter([])

        mock_redis.scan_iter.side_effect = scan_iter_side_effect

        cache.invalidate_formula(formula_id)

        # Verify scan_iter was called for both patterns
        assert mock_redis.scan_iter.call_count == 2

        # Verify delete was called for all keys
        assert mock_redis.delete.call_count == 4

    def test_invalidate_formula_when_disabled(self, formula_id: UUID) -> None:
        """Test that invalidate_formula does nothing when caching is disabled."""
        cache = FormulaCache(redis_client=None)

        # Should not raise an error
        cache.invalidate_formula(formula_id)

    def test_invalidate_formula_redis_error(
        self, cache: FormulaCache, mock_redis: Mock, formula_id: UUID
    ) -> None:
        """Test that invalidate_formula handles Redis errors gracefully."""
        mock_redis.scan_iter.side_effect = RedisError("Connection failed")

        # Should not raise an error
        cache.invalidate_formula(formula_id)

    def test_invalidate_formula_no_keys(
        self, cache: FormulaCache, mock_redis: Mock, formula_id: UUID
    ) -> None:
        """Test invalidating formula when no keys exist."""
        mock_redis.scan_iter.return_value = iter([])

        cache.invalidate_formula(formula_id)

        # Verify scan_iter was called but delete was not
        assert mock_redis.scan_iter.call_count == 2
        mock_redis.delete.assert_not_called()


class TestFormulaCacheStatistics:
    """Test suite for cache statistics."""

    @pytest.fixture
    def mock_redis(self) -> Mock:
        """Create a mock Redis client."""
        return Mock(spec=Redis)

    @pytest.fixture
    def cache(self, mock_redis: Mock) -> FormulaCache:
        """Create a FormulaCache instance with mock Redis."""
        return FormulaCache(redis_client=mock_redis)

    def test_get_stats_initial_state(self, cache: FormulaCache) -> None:
        """Test that get_stats returns correct initial statistics."""
        stats = cache.get_stats()

        assert stats["bytecode_hits"] == 0
        assert stats["bytecode_misses"] == 0
        assert stats["bytecode_hit_rate"] == 0.0
        assert stats["result_hits"] == 0
        assert stats["result_misses"] == 0
        assert stats["result_hit_rate"] == 0.0
        assert stats["enabled"] is True

    def test_get_stats_after_operations(
        self, cache: FormulaCache, mock_redis: Mock
    ) -> None:
        """Test that get_stats tracks hits and misses correctly."""
        formula_id = uuid4()

        # Simulate some cache operations
        mock_redis.get.return_value = b"cached_data"
        cache.get_bytecode(formula_id, 1)  # Hit
        cache.get_bytecode(formula_id, 1)  # Hit

        mock_redis.get.return_value = None
        cache.get_bytecode(formula_id, 2)  # Miss

        mock_redis.get.return_value = pickle.dumps({"cost": 100})
        cache.get_result(formula_id, "hash1")  # Hit

        mock_redis.get.return_value = None
        cache.get_result(formula_id, "hash2")  # Miss
        cache.get_result(formula_id, "hash3")  # Miss

        stats = cache.get_stats()

        assert stats["bytecode_hits"] == 2
        assert stats["bytecode_misses"] == 1
        assert stats["bytecode_hit_rate"] == pytest.approx(2 / 3)
        assert stats["result_hits"] == 1
        assert stats["result_misses"] == 2
        assert stats["result_hit_rate"] == pytest.approx(1 / 3)

    def test_get_stats_when_disabled(self) -> None:
        """Test that get_stats shows caching as disabled."""
        cache = FormulaCache(redis_client=None)

        stats = cache.get_stats()

        assert stats["enabled"] is False
        assert stats["bytecode_hit_rate"] == 0.0
        assert stats["result_hit_rate"] == 0.0

    def test_get_stats_hit_rate_calculation(self, cache: FormulaCache) -> None:
        """Test that hit rate is calculated correctly."""
        # Manually set statistics
        cache._bytecode_hits = 7
        cache._bytecode_misses = 3
        cache._result_hits = 5
        cache._result_misses = 5

        stats = cache.get_stats()

        assert stats["bytecode_hit_rate"] == pytest.approx(0.7)
        assert stats["result_hit_rate"] == pytest.approx(0.5)


class TestFormulaCacheTTL:
    """Test suite for TTL configuration."""

    def test_default_bytecode_ttl(self) -> None:
        """Test that default bytecode TTL is 1 hour (3600 seconds)."""
        assert FormulaCache.BYTECODE_TTL == 3600

    def test_default_result_ttl(self) -> None:
        """Test that default result TTL is 5 minutes (300 seconds)."""
        assert FormulaCache.RESULT_TTL == 300

    def test_bytecode_ttl_used_in_store(self) -> None:
        """Test that bytecode TTL is used when storing."""
        mock_redis = Mock(spec=Redis)
        cache = FormulaCache(redis_client=mock_redis)
        formula_id = uuid4()

        cache.store_bytecode(formula_id, 1, b"bytecode")

        # Verify TTL was passed to setex
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == FormulaCache.BYTECODE_TTL

    def test_result_ttl_used_in_store(self) -> None:
        """Test that result TTL is used when storing."""
        mock_redis = Mock(spec=Redis)
        cache = FormulaCache(redis_client=mock_redis)
        formula_id = uuid4()

        cache.store_result(formula_id, "hash", {"cost": 100})

        # Verify TTL was passed to setex
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == FormulaCache.RESULT_TTL


class TestFormulaCacheGracefulDegradation:
    """Test suite for graceful degradation when Redis is unavailable."""

    def test_all_operations_work_without_redis(self) -> None:
        """
        Test that all cache operations work without Redis (graceful degradation).

        Requirements: 5.1, 5.2, 5.3
        """
        cache = FormulaCache(redis_client=None)
        formula_id = uuid4()

        # All operations should work without raising errors
        result = cache.get_bytecode(formula_id, 1)
        assert result is None

        cache.store_bytecode(formula_id, 1, b"bytecode")

        result = cache.get_result(formula_id, "hash")
        assert result is None

        cache.store_result(formula_id, "hash", {"cost": 100})

        cache.invalidate_formula(formula_id)

        stats = cache.get_stats()
        assert stats["enabled"] is False
