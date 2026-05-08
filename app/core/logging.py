"""
Auralis Logging Configuration
Structured logging with console output and optional file logging.
"""

import logging
import sys
from app.core.config import settings


def setup_logging() -> logging.Logger:
    """Configure and return the application logger."""

    logger = logging.getLogger("auralis")
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Console handler with rich formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    # Force UTF-8 on Windows to avoid cp1252 UnicodeEncodeError
    if hasattr(console_handler.stream, "reconfigure"):
        try:
            console_handler.stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    logger.addHandler(console_handler)

    return logger


# Application logger instance
logger = setup_logging()
