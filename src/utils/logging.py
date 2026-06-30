"""
Structured JSON logging for the RCA pipeline.

Replaces scattered print() statements with proper logging.
Configurable via LOG_LEVEL env var (default: INFO).

Usage:
    from src.utils.logging import get_logger
    logger = get_logger(__name__)
    logger.info("event description", extra={"key": "value"})
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON for structured log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include extra fields if present
        if hasattr(record, "extra_data"):
            log_entry.update(record.extra_data)
        # Include exception info
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger with JSON formatting."""
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        handler.setLevel(getattr(logging, log_level, logging.INFO))
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, log_level, logging.INFO))

    return logger


def configure_root_logging():
    """Configure root logger for the application. Call once at startup."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level, logging.INFO))

    # Only add handler if root has none
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        root.addHandler(handler)
