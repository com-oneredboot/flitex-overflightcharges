"""Unit tests for structured JSON logging configuration.

Tests verify that logging configuration produces JSON output with required fields
and correctly handles various log scenarios.
"""

import json
import logging
import os
from io import StringIO
from datetime import datetime

import pytest

from src.logging_config import JSONFormatter, configure_logging


class TestJSONFormatter:
    """Test suite for JSONFormatter class."""
    
    def test_basic_log_format(self):
        """Test that basic log entries contain required fields."""
        formatter = JSONFormatter(service_name="test-service")
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        log_entry = json.loads(output)
        
        # Verify required fields
        assert "timestamp" in log_entry
        assert "severity" in log_entry
        assert "service_name" in log_entry
        assert "message" in log_entry
        assert "logger_name" in log_entry
        
        # Verify field values
        assert log_entry["severity"] == "INFO"
        assert log_entry["service_name"] == "test-service"
        assert log_entry["message"] == "Test message"
        assert log_entry["logger_name"] == "test.logger"
    
    def test_timestamp_format(self):
        """Test that timestamp is in ISO 8601 format with timezone."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        log_entry = json.loads(output)
        
        # Verify timestamp can be parsed as ISO 8601
        timestamp = log_entry["timestamp"]
        parsed_time = datetime.fromisoformat(timestamp)
        assert parsed_time is not None
        
        # Verify timezone is present
        assert "+" in timestamp or "Z" in timestamp or timestamp.endswith("+00:00")
    
    def test_request_id_field(self):
        """Test that request_id is included when present."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.request_id = "test-request-123"
        
        output = formatter.format(record)
        log_entry = json.loads(output)
        
        assert "request_id" in log_entry
        assert log_entry["request_id"] == "test-request-123"
    
    def test_http_request_fields(self):
        """Test that HTTP request fields are included when present."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="API request processed",
            args=(),
            exc_info=None
        )
        record.method = "POST"
        record.path = "/api/route-costs"
        record.status_code = 200
        record.duration_ms = 125.5
        
        output = formatter.format(record)
        log_entry = json.loads(output)
        
        assert log_entry["method"] == "POST"
        assert log_entry["path"] == "/api/route-costs"
        assert log_entry["status_code"] == 200
        assert log_entry["duration_ms"] == 125.5
    
    def test_calculation_fields(self):
        """Test that calculation fields are included when present."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Calculation completed",
            args=(),
            exc_info=None
        )
        record.route_string = "KJFK DCT CYYZ"
        record.total_cost = 1250.50
        record.calculation_duration_ms = 85.3
        
        output = formatter.format(record)
        log_entry = json.loads(output)
        
        assert log_entry["route_string"] == "KJFK DCT CYYZ"
        assert log_entry["total_cost"] == 1250.50
        assert log_entry["calculation_duration_ms"] == 85.3
    
    def test_exception_handling(self):
        """Test that exceptions are formatted correctly."""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
            
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=exc_info
            )
            
            output = formatter.format(record)
            log_entry = json.loads(output)
            
            assert "exception" in log_entry
            assert "ValueError" in log_entry["exception"]
            assert "Test error" in log_entry["exception"]
    
    def test_stack_trace_field(self):
        """Test that stack_trace field is included when present."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error with stack trace",
            args=(),
            exc_info=None
        )
        record.stack_trace = "Traceback (most recent call last):\n  File test.py, line 10"
        
        output = formatter.format(record)
        log_entry = json.loads(output)
        
        assert "stack_trace" in log_entry
        assert log_entry["stack_trace"] == "Traceback (most recent call last):\n  File test.py, line 10"
    
    def test_log_levels(self):
        """Test that different log levels are formatted correctly."""
        formatter = JSONFormatter()
        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL")
        ]
        
        for level, level_name in levels:
            record = logging.LogRecord(
                name="test.logger",
                level=level,
                pathname="test.py",
                lineno=10,
                msg=f"Test {level_name} message",
                args=(),
                exc_info=None
            )
            
            output = formatter.format(record)
            log_entry = json.loads(output)
            
            assert log_entry["severity"] == level_name
            assert log_entry["message"] == f"Test {level_name} message"
    
    def test_default_service_name(self):
        """Test that default service name is used when not specified."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        log_entry = json.loads(output)
        
        assert log_entry["service_name"] == "flitex-overflightcharges"


class TestConfigureLogging:
    """Test suite for configure_logging function."""
    
    def test_default_log_level(self, monkeypatch):
        """Test that default log level is INFO when not specified."""
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        
        configure_logging()
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
    
    def test_custom_log_level(self, monkeypatch):
        """Test that custom log level is applied from environment variable."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        
        configure_logging()
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
    
    def test_log_level_case_insensitive(self, monkeypatch):
        """Test that log level is case-insensitive."""
        monkeypatch.setenv("LOG_LEVEL", "warning")
        
        configure_logging()
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING
    
    def test_invalid_log_level_defaults_to_info(self, monkeypatch):
        """Test that invalid log level defaults to INFO."""
        monkeypatch.setenv("LOG_LEVEL", "INVALID")
        
        configure_logging()
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
    
    def test_json_formatter_applied(self, monkeypatch, capsys):
        """Test that JSON formatter is applied to handlers."""
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        
        configure_logging()
        
        # Log a test message
        logger = logging.getLogger("test.logger")
        logger.info("Test message")
        
        # Capture output
        captured = capsys.readouterr()
        
        # Verify output is valid JSON
        lines = captured.out.strip().split("\n")
        for line in lines:
            if line:
                log_entry = json.loads(line)
                assert "timestamp" in log_entry
                assert "severity" in log_entry
                assert "service_name" in log_entry
                assert "message" in log_entry
    
    def test_removes_existing_handlers(self, monkeypatch):
        """Test that existing handlers are removed before configuration."""
        # Add a dummy handler
        root_logger = logging.getLogger()
        dummy_handler = logging.StreamHandler()
        root_logger.addHandler(dummy_handler)
        initial_handler_count = len(root_logger.handlers)
        
        configure_logging()
        
        # Should have exactly one handler (the new JSON handler)
        assert len(root_logger.handlers) == 1
        assert dummy_handler not in root_logger.handlers
    
    def test_all_log_levels_work(self, monkeypatch, capsys):
        """Test that all log levels produce valid JSON output."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        for level in levels:
            monkeypatch.setenv("LOG_LEVEL", level)
            configure_logging()
            
            logger = logging.getLogger(f"test.{level.lower()}")
            logger.log(getattr(logging, level), f"Test {level} message")
            
            captured = capsys.readouterr()
            lines = captured.out.strip().split("\n")
            
            # Find the test message line
            for line in lines:
                if line and f"Test {level} message" in line:
                    log_entry = json.loads(line)
                    assert log_entry["severity"] == level
                    assert log_entry["message"] == f"Test {level} message"
                    break


class TestLoggingIntegration:
    """Integration tests for logging configuration."""
    
    def test_end_to_end_logging(self, monkeypatch, capsys):
        """Test complete logging flow from configuration to output."""
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        
        configure_logging()
        
        logger = logging.getLogger("integration.test")
        
        # Log with extra fields
        logger.info(
            "API request processed",
            extra={
                "request_id": "req-123",
                "method": "POST",
                "path": "/api/route-costs",
                "status_code": 200,
                "duration_ms": 150.5
            }
        )
        
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        
        # Find the API request line
        for line in lines:
            if line and "API request processed" in line:
                log_entry = json.loads(line)
                
                assert log_entry["message"] == "API request processed"
                assert log_entry["request_id"] == "req-123"
                assert log_entry["method"] == "POST"
                assert log_entry["path"] == "/api/route-costs"
                assert log_entry["status_code"] == 200
                assert log_entry["duration_ms"] == 150.5
                break
    
    def test_calculation_logging(self, monkeypatch, capsys):
        """Test logging of calculation details."""
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        
        configure_logging()
        
        logger = logging.getLogger("calculation.test")
        
        logger.info(
            "Route calculation completed",
            extra={
                "route_string": "KJFK DCT CYYZ",
                "total_cost": 1250.50,
                "calculation_duration_ms": 85.3
            }
        )
        
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        
        # Find the calculation line
        for line in lines:
            if line and "Route calculation completed" in line:
                log_entry = json.loads(line)
                
                assert log_entry["route_string"] == "KJFK DCT CYYZ"
                assert log_entry["total_cost"] == 1250.50
                assert log_entry["calculation_duration_ms"] == 85.3
                break
