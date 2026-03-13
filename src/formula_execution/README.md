# Formula Execution Package

This package contains components for the Python Formula Execution System, which enables secure, high-performance execution of overflight charge calculation formulas.

## Structure

```
formula_execution/
├── __init__.py              # Package initialization
├── redis_config.py          # Redis connection configuration
├── README.md                # This file
└── (future components)
    ├── formula_cache.py     # Redis-based caching layer
    ├── formula_executor.py  # Core execution engine with sandbox
    ├── formula_validator.py # Pre-save validation pipeline
    ├── constants_provider.py # Constants and utilities loader
    └── eurocontrol_loader.py # EuroControl rates loader
```

## Components

### redis_config.py
Redis connection management for formula caching. Provides:
- Connection pool initialization
- Client instance management
- Graceful degradation when Redis is unavailable

## Requirements

This package implements requirements from the Python Formula Execution System spec:
- Requirements 1.1, 11.7, 11.10: Formula storage with hash and bytecode
- Requirements 5.1, 5.2, 5.3: Performance optimization with caching

## Database Schema

The migration `26c4d9aec284_add_formula_hash_and_bytecode_columns.py` adds:
- `formula_hash` (String(64)): SHA256 hash for duplicate detection
- `formula_bytecode` (LargeBinary): Compiled Python bytecode
- `idx_formulas_hash`: Index for efficient duplicate lookups

## Configuration

Required environment variables:
- `REDIS_URL`: Redis connection URL (e.g., `redis://localhost:6379/0`)

## Usage

```python
from src.formula_execution.redis_config import RedisConfig, get_redis_client

# Initialize Redis connection (typically in application startup)
RedisConfig.initialize()

# Get Redis client
redis_client = get_redis_client()

# Close connection (typically in application shutdown)
RedisConfig.close()
```
