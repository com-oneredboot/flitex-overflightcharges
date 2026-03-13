"""Redis-based caching for compiled formula bytecode and execution results.

This module provides the FormulaCache class which handles caching of:
1. Compiled formula bytecode (TTL: 1 hour)
2. Formula execution results (TTL: 5 minutes)

The cache supports graceful degradation when Redis is unavailable.

Requirements: 5.1, 5.2, 5.3
"""

import logging
import pickle
from typing import Optional, Any
from uuid import UUID
from redis import Redis, RedisError

logger = logging.getLogger(__name__)


class FormulaCache:
    """Redis-based cache for formula bytecode and execution results.
    
    This class provides caching functionality with two cache types:
    - Bytecode cache: Stores compiled Python bytecode (1 hour TTL)
    - Result cache: Stores execution results (5 minutes TTL)
    
    The cache handles graceful degradation when Redis is unavailable.
    """
    
    # Cache key prefixes
    BYTECODE_PREFIX = "formula:bytecode"
    RESULT_PREFIX = "formula:result"
    STATS_PREFIX = "formula:stats"
    
    # TTL values in seconds
    BYTECODE_TTL = 3600  # 1 hour
    RESULT_TTL = 300     # 5 minutes
    
    def __init__(self, redis_client: Optional[Redis] = None):
        """Initialize cache with Redis client.
        
        Args:
            redis_client: Redis client instance. If None, caching is disabled.
        """
        self._redis = redis_client
        self._enabled = redis_client is not None
        
        # Initialize statistics counters
        self._bytecode_hits = 0
        self._bytecode_misses = 0
        self._result_hits = 0
        self._result_misses = 0
        
        if not self._enabled:
            logger.warning(
                "FormulaCache initialized without Redis client - caching disabled"
            )
    
    def get_bytecode(self, formula_id: UUID, version: int) -> Optional[bytes]:
        """Retrieve compiled bytecode from cache.
        
        Args:
            formula_id: UUID of the formula
            version: Version number of the formula
        
        Returns:
            Compiled bytecode as bytes, or None if not cached or Redis unavailable
        """
        if not self._enabled:
            return None
        
        key = self._bytecode_key(formula_id, version)
        
        try:
            bytecode = self._redis.get(key)
            
            if bytecode:
                self._bytecode_hits += 1
                logger.debug(
                    "Bytecode cache hit",
                    extra={
                        "formula_id": str(formula_id),
                        "version": version,
                        "key": key
                    }
                )
                return bytecode
            else:
                self._bytecode_misses += 1
                logger.debug(
                    "Bytecode cache miss",
                    extra={
                        "formula_id": str(formula_id),
                        "version": version,
                        "key": key
                    }
                )
                return None
                
        except RedisError as e:
            logger.warning(
                f"Redis error retrieving bytecode: {str(e)}",
                extra={
                    "formula_id": str(formula_id),
                    "version": version,
                    "error": str(e)
                }
            )
            return None
    
    def store_bytecode(
        self,
        formula_id: UUID,
        version: int,
        bytecode: bytes,
        ttl_seconds: int = BYTECODE_TTL
    ) -> None:
        """Store compiled bytecode in cache.
        
        Args:
            formula_id: UUID of the formula
            version: Version number of the formula
            bytecode: Compiled bytecode as bytes
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
        """
        if not self._enabled:
            return
        
        key = self._bytecode_key(formula_id, version)
        
        try:
            self._redis.setex(key, ttl_seconds, bytecode)
            
            logger.debug(
                "Bytecode stored in cache",
                extra={
                    "formula_id": str(formula_id),
                    "version": version,
                    "key": key,
                    "ttl_seconds": ttl_seconds,
                    "size_bytes": len(bytecode) if isinstance(bytecode, (bytes, bytearray)) else 0
                }
            )
            
        except RedisError as e:
            logger.warning(
                f"Redis error storing bytecode: {str(e)}",
                extra={
                    "formula_id": str(formula_id),
                    "version": version,
                    "error": str(e)
                }
            )
    
    def get_result(
        self,
        formula_id: UUID,
        params_hash: str
    ) -> Optional[dict]:
        """Retrieve cached execution result.
        
        Args:
            formula_id: UUID of the formula
            params_hash: Hash of execution parameters (distance, weight, context)
        
        Returns:
            Cached result dictionary, or None if not cached or Redis unavailable
        """
        if not self._enabled:
            return None
        
        key = self._result_key(formula_id, params_hash)
        
        try:
            cached_data = self._redis.get(key)
            
            if cached_data:
                self._result_hits += 1
                result = pickle.loads(cached_data)
                
                logger.debug(
                    "Result cache hit",
                    extra={
                        "formula_id": str(formula_id),
                        "params_hash": params_hash,
                        "key": key
                    }
                )
                return result
            else:
                self._result_misses += 1
                logger.debug(
                    "Result cache miss",
                    extra={
                        "formula_id": str(formula_id),
                        "params_hash": params_hash,
                        "key": key
                    }
                )
                return None
                
        except (RedisError, pickle.PickleError) as e:
            logger.warning(
                f"Error retrieving cached result: {str(e)}",
                extra={
                    "formula_id": str(formula_id),
                    "params_hash": params_hash,
                    "error": str(e)
                }
            )
            return None
    
    def store_result(
        self,
        formula_id: UUID,
        params_hash: str,
        result: dict,
        ttl_seconds: int = RESULT_TTL
    ) -> None:
        """Store execution result in cache.
        
        Args:
            formula_id: UUID of the formula
            params_hash: Hash of execution parameters
            result: Result dictionary to cache
            ttl_seconds: Time-to-live in seconds (default: 5 minutes)
        """
        if not self._enabled:
            return
        
        key = self._result_key(formula_id, params_hash)
        
        try:
            # Serialize result using pickle
            serialized = pickle.dumps(result)
            self._redis.setex(key, ttl_seconds, serialized)
            
            logger.debug(
                "Result stored in cache",
                extra={
                    "formula_id": str(formula_id),
                    "params_hash": params_hash,
                    "key": key,
                    "ttl_seconds": ttl_seconds,
                    "size_bytes": len(serialized)
                }
            )
            
        except (RedisError, pickle.PickleError) as e:
            logger.warning(
                f"Error storing result in cache: {str(e)}",
                extra={
                    "formula_id": str(formula_id),
                    "params_hash": params_hash,
                    "error": str(e)
                }
            )
    
    def invalidate_formula(self, formula_id: UUID) -> None:
        """Invalidate all caches for a formula.
        
        This method removes all bytecode and result caches associated with
        the given formula ID. It uses pattern matching to find all keys.
        
        Args:
            formula_id: UUID of the formula to invalidate
        """
        if not self._enabled:
            return
        
        try:
            # Pattern to match all keys for this formula
            bytecode_pattern = f"{self.BYTECODE_PREFIX}:{formula_id}:*"
            result_pattern = f"{self.RESULT_PREFIX}:{formula_id}:*"
            
            deleted_count = 0
            
            # Delete bytecode caches
            for key in self._redis.scan_iter(match=bytecode_pattern):
                self._redis.delete(key)
                deleted_count += 1
            
            # Delete result caches
            for key in self._redis.scan_iter(match=result_pattern):
                self._redis.delete(key)
                deleted_count += 1
            
            logger.info(
                "Formula caches invalidated",
                extra={
                    "formula_id": str(formula_id),
                    "deleted_keys": deleted_count
                }
            )
            
        except RedisError as e:
            logger.warning(
                f"Error invalidating formula caches: {str(e)}",
                extra={
                    "formula_id": str(formula_id),
                    "error": str(e)
                }
            )
    
    def get_stats(self) -> dict:
        """Return cache hit/miss statistics.
        
        Returns:
            Dictionary containing cache statistics:
            - bytecode_hits: Number of bytecode cache hits
            - bytecode_misses: Number of bytecode cache misses
            - bytecode_hit_rate: Bytecode cache hit rate (0.0-1.0)
            - result_hits: Number of result cache hits
            - result_misses: Number of result cache misses
            - result_hit_rate: Result cache hit rate (0.0-1.0)
            - enabled: Whether caching is enabled
        """
        bytecode_total = self._bytecode_hits + self._bytecode_misses
        result_total = self._result_hits + self._result_misses
        
        bytecode_hit_rate = (
            self._bytecode_hits / bytecode_total if bytecode_total > 0 else 0.0
        )
        result_hit_rate = (
            self._result_hits / result_total if result_total > 0 else 0.0
        )
        
        return {
            "bytecode_hits": self._bytecode_hits,
            "bytecode_misses": self._bytecode_misses,
            "bytecode_hit_rate": bytecode_hit_rate,
            "result_hits": self._result_hits,
            "result_misses": self._result_misses,
            "result_hit_rate": result_hit_rate,
            "enabled": self._enabled
        }
    
    def _bytecode_key(self, formula_id: UUID, version: int) -> str:
        """Generate cache key for bytecode.
        
        Args:
            formula_id: UUID of the formula
            version: Version number of the formula
        
        Returns:
            Cache key string
        """
        return f"{self.BYTECODE_PREFIX}:{formula_id}:{version}"
    
    def _result_key(self, formula_id: UUID, params_hash: str) -> str:
        """Generate cache key for execution result.
        
        Args:
            formula_id: UUID of the formula
            params_hash: Hash of execution parameters
        
        Returns:
            Cache key string
        """
        return f"{self.RESULT_PREFIX}:{formula_id}:{params_hash}"
