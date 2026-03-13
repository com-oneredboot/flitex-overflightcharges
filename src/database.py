"""Database configuration and session management."""

import os
import time
import logging
from typing import Generator, Optional
from sqlalchemy import create_engine, exc, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Configure logging
logger = logging.getLogger(__name__)

# Create Base class for declarative models (always available)
Base = declarative_base()

# Read DATABASE_URL from environment (optional for migrations)
DATABASE_URL = os.getenv("DATABASE_URL")

# Only create engine and session if DATABASE_URL is provided
engine: Optional[object] = None
SessionLocal: Optional[sessionmaker] = None

if DATABASE_URL:
    # Create SQLAlchemy engine
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    
    # Create SessionLocal class for database sessions
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session with retry logic.
    
    Implements exponential backoff retry strategy:
    - Retry 1: 100ms delay
    - Retry 2: 200ms delay
    - Retry 3: 400ms delay
    
    Yields:
        Session: SQLAlchemy database session
    
    Raises:
        exc.OperationalError: If all connection retries fail
        ValueError: If DATABASE_URL is not configured
    """
    if not SessionLocal:
        raise ValueError("DATABASE_URL environment variable is required")
    
    max_retries = 3
    base_delay_ms = 100
    
    for attempt in range(max_retries):
        try:
            db = SessionLocal()
            # Test the connection
            db.execute(text("SELECT 1"))
            try:
                yield db
            finally:
                db.close()
            return
        except exc.OperationalError as e:
            if attempt < max_retries - 1:
                delay_ms = base_delay_ms * (2 ** attempt)
                logger.warning(
                    f"Database connection failed (attempt {attempt + 1}/{max_retries}). "
                    f"Retrying in {delay_ms}ms..."
                )
                time.sleep(delay_ms / 1000)
            else:
                logger.error(
                    f"Database connection failed after {max_retries} attempts. "
                    f"Error: {str(e)}"
                )
                raise
