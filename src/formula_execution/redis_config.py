"""Redis connection configuration for formula execution caching.

This module provides Redis client initialization and connection management
for the formula execution system's caching layer.

Requirements: 5.1, 5.2, 5.3
"""

import os
import logging
from typing import Optional
from redis import Redis, ConnectionPool, RedisError

logger = logging.getLogger(__name__)


class RedisConfig:
    """Redis connection configuration and client management."""
    
    _pool: Optional[ConnectionPool] = None
    _client: Optional[Redis] = None
    
    @classmethod
    def initialize(cls, redis_url: Optional[str] = None) -> None:
        """Initialize Redis connection pool.
        
        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL env var)
        
        Raises:
            ValueError: If redis_url is not provided and REDIS_URL env var is not set
        """
        url = redis_url or os.getenv("REDIS_URL")
        
        if not url:
            raise ValueError(
                "Redis URL must be provided via redis_url parameter or REDIS_URL environment variable"
            )
        
        try:
            # Create connection pool with sensible defaults
            cls._pool = ConnectionPool.from_url(
                url,
                max_connections=10,
                socket_timeout=5,
                socket_connect_timeout=5,
                decode_responses=False,  # We need bytes for bytecode storage
            )
            
            # Create client from pool
            cls._client = Redis(connection_pool=cls._pool)
            
            # Test connection
            cls._client.ping()
            
            logger.info(
                "Redis connection initialized successfully",
                extra={"redis_url": url.split("@")[-1]}  # Log without credentials
            )
            
        except RedisError as e:
            logger.error(
                f"Failed to initialize Redis connection: {str(e)}",
                extra={"error": str(e)}
            )
            raise
    
    @classmethod
    def get_client(cls) -> Redis:
        """Get Redis client instance.
        
        Returns:
            Redis client instance
        
        Raises:
            RuntimeError: If Redis has not been initialized
        """
        if cls._client is None:
            raise RuntimeError(
                "Redis client not initialized. Call RedisConfig.initialize() first."
            )
        
        return cls._client
    
    @classmethod
    def close(cls) -> None:
        """Close Redis connection pool.
        
        Should be called during application shutdown.
        """
        if cls._client:
            cls._client.close()
            cls._client = None
        
        if cls._pool:
            cls._pool.disconnect()
            cls._pool = None
        
        logger.info("Redis connection closed")
    
    @classmethod
    def is_available(cls) -> bool:
        """Check if Redis is available and responding.
        
        Returns:
            True if Redis is available, False otherwise
        """
        if cls._client is None:
            return False
        
        try:
            cls._client.ping()
            return True
        except RedisError:
            return False


def get_redis_client() -> Optional[Redis]:
    """Dependency function to get Redis client.
    
    Returns:
        Redis client instance or None if Redis is not available
    
    Note:
        This function returns None instead of raising an error to support
        graceful degradation when Redis is unavailable.
    """
    try:
        return RedisConfig.get_client()
    except RuntimeError:
        logger.warning("Redis client not available, caching will be disabled")
        return None
