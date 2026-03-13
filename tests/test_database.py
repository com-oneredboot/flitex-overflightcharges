"""Tests for database connection and retry logic."""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import exc
from src.database import get_db


@pytest.mark.skip(reason="Requires running PostgreSQL database")
def test_get_db_successful_connection():
    """Test that get_db yields a session on successful connection."""
    db_gen = get_db()
    db = next(db_gen)
    
    assert db is not None
    
    # Clean up
    try:
        next(db_gen)
    except StopIteration:
        pass


def test_get_db_retry_logic_with_eventual_success():
    """Test that get_db retries on OperationalError and succeeds on retry."""
    with patch('src.database.SessionLocal') as mock_session_local:
        # First call fails, second call succeeds
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        call_count = 0
        def side_effect(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise exc.OperationalError("Connection failed", None, None)
            return None
        
        mock_session.execute.side_effect = side_effect
        
        # Should succeed on second attempt
        db_gen = get_db()
        db = next(db_gen)
        
        assert db is not None
        assert call_count == 2
        
        # Clean up
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_get_db_retry_exhaustion():
    """Test that get_db raises OperationalError after max retries."""
    with patch('src.database.SessionLocal') as mock_session_local:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        # Always fail
        mock_session.execute.side_effect = exc.OperationalError(
            "Connection failed", None, None
        )
        
        # Should raise after 3 attempts
        with pytest.raises(exc.OperationalError):
            db_gen = get_db()
            next(db_gen)
        
        # Verify it tried 3 times
        assert mock_session.execute.call_count == 3


def test_get_db_exponential_backoff_timing():
    """Test that retry delays follow exponential backoff pattern."""
    with patch('src.database.SessionLocal') as mock_session_local:
        with patch('src.database.time.sleep') as mock_sleep:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            
            # Always fail
            mock_session.execute.side_effect = exc.OperationalError(
                "Connection failed", None, None
            )
            
            # Should raise after 3 attempts
            with pytest.raises(exc.OperationalError):
                db_gen = get_db()
                next(db_gen)
            
            # Verify exponential backoff: 100ms, 200ms (no third sleep before final raise)
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(0.1)  # 100ms
            mock_sleep.assert_any_call(0.2)  # 200ms
