"""
Console logging configuration helpers.
"""

import logging
import sys


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_HANDLER_MARKER = "_trippi_console_handler"


def configure_terminal_logging(level: int = logging.INFO) -> None:
    """
    Ensure application logs are emitted to the terminal.

    This is used by CLI and test entry points that do not pass through
    ``agents.main``, which is where the API app configures logging.

    Args:
        level: Minimum log level to emit
    """
    root_logger = logging.getLogger()

    if root_logger.level > level:
        root_logger.setLevel(level)

    has_console_handler = any(
        getattr(handler, _HANDLER_MARKER, False) for handler in root_logger.handlers
    )
    if not has_console_handler:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        handler.setLevel(level)
        setattr(handler, _HANDLER_MARKER, True)
        root_logger.addHandler(handler)

    logging.getLogger("agents").setLevel(level)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
