"""
Structured logging configuration.

Provides JSON-formatted logging for agent state transitions and events.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs log records as JSON.

    Each log entry includes:
    - timestamp: ISO format datetime
    - level: Log level name
    - logger: Logger name
    - message: Log message
    - extra: Any additional fields passed to the log call
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add any extra attributes that were passed
        if hasattr(record, "extra"):
            log_entry["extra"] = record.extra

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    logger_name: str = "agents",
) -> logging.Logger:
    """
    Configure structured JSON logging.

    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file. If not provided, logs to stdout only.
        logger_name: Name for the logger instance.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers = []

    # Create formatter
    formatter = StructuredFormatter()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler if path provided
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def log_state_transition(
    event: str,
    state: Dict[str, Any],
    extra: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """
    Log an agent state transition event.

    Args:
        event: Name of the event (e.g., "clarification_start", "round_complete")
        state: Current state dictionary (will extract key fields)
        extra: Additional context to include in the log
        logger: Logger instance to use. If not provided, uses default.
    """
    if logger is None:
        logger = logging.getLogger("agents")

    # Extract key state information
    state_summary = {
        "current_round": state.get("current_round"),
        "completeness_score": state.get("completeness_score"),
        "clarification_complete": state.get("clarification_complete"),
    }

    log_data = {
        "event": event,
        "state_summary": state_summary,
    }

    if extra:
        log_data["extra"] = extra

    # Create a LogRecord with extra data
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        "",
        0,
        f"State transition: {event}",
        args=(),
        exc_info=None,
    )
    record.extra = log_data

    logger.handle(record)
