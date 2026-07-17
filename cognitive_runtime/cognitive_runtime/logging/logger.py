"""
Logging initialization for Cognitive Runtime.

This module sets up structured logging using `structlog` without creating
global mutable state. It provides a function to configure the logger
based on the provided settings.
"""

import logging
import sys
from typing import Any

import structlog

from cognitive_runtime.config.settings import LoggingSettings


def configure_logging(settings: LoggingSettings) -> None:
    """
    Configure standard logging and structlog.

    Args:
        settings: The logging configuration settings.
    """
    # Convert string level to logging integer
    level = getattr(logging, settings.level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    # Define common processors
    processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Select renderer based on format setting
    if settings.format.lower() == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: The name of the logger, typically `__name__`.

    Returns:
        A structlog bound logger.
    """
    return structlog.get_logger(name)
