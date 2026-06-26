"""Structured logging setup built on structlog.

``configure_logging`` is idempotent and safe to call from any entrypoint (API,
CLI, workers, tests). ``get_logger`` returns a bound structlog logger.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog

_configured = False


def configure_logging(*, level: str = "INFO", json: bool = False) -> None:
    """Configure structlog + stdlib logging once.

    Args:
        level: minimum log level name (e.g. ``"INFO"``, ``"DEBUG"``).
        json: emit JSON lines when True, human-readable console output otherwise.
    """
    global _configured

    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper(), logging.INFO))

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None, **initial_values: Any) -> structlog.BoundLogger:
    """Return a bound structlog logger, configuring defaults on first use."""
    if not _configured:
        configure_logging()
    logger: structlog.BoundLogger = structlog.get_logger(name)
    if initial_values:
        logger = logger.bind(**initial_values)
    return logger
