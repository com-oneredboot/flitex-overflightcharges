"""Structured JSON logging configuration for the flitex-overflightcharges service.

This module configures structured JSON logging with fields required for
observability and log aggregation systems.
"""

import logging
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging.
    
    Formats log records as JSON with required fields:
    - timestamp: ISO 8601 format with timezone
    - severity: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - service_name: Service identifier
    - message: Log message
    - request_id: Optional request correlation ID
    - Additional context fields as provided
    """
    
    def __init__(self, service_name: str = "flitex-overflightcharges"):
        """Initialize the JSON formatter.
        
        Args:
            service_name: Name of the service for log identification
        """
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON.
        
        Args:
            record: The log record to format
        
        Returns:
            JSON-formatted log string
        """
        # Build base log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname,
            "service_name": self.service_name,
            "message": record.getMessage(),
            "logger_name": record.name,
        }
        
        # Add request_id if present
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        # Add HTTP request details if present
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        # Add calculation details if present
        if hasattr(record, "route_string"):
            log_entry["route_string"] = record.route_string
        if hasattr(record, "total_cost"):
            log_entry["total_cost"] = record.total_cost
        if hasattr(record, "calculation_duration_ms"):
            log_entry["calculation_duration_ms"] = record.calculation_duration_ms
        
        # Add exception details if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add stack trace for errors
        if hasattr(record, "stack_trace"):
            log_entry["stack_trace"] = record.stack_trace
        
        return json.dumps(log_entry)


def configure_logging() -> None:
    """Configure structured JSON logging for the service.
    
    Reads LOG_LEVEL from environment variable and configures the root logger
    with JSON formatting. Defaults to INFO level if not specified.
    
    Environment Variables:
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Get log level from environment variable
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Validate and convert log level
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    # Create JSON formatter
    json_formatter = JSONFormatter()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(json_formatter)
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    
    # Log configuration completion
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configured with level {log_level_str}",
        extra={"log_level": log_level_str}
    )
