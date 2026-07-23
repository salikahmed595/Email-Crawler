"""
Structured JSON logging using structlog.
DEBUG in development, INFO in production.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.config import get_settings


def configure_logging() -> None:
    """
    Configure structlog for the application.
    Call this once at startup.
    """
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.DEBUG)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Suppress noisy third-party loggers (hpack/h2 log every single HTTP/2
    # header frame at DEBUG level — without this a single page crawl can
    # produce megabytes of log output).
    for noisy in (
        "httpx", "httpcore", "asyncio", "sqlalchemy.engine",
        "hpack", "h2", "playwright", "PIL",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_development:
        # Human-readable format in development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # JSON format in production
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named structured logger."""
    return structlog.get_logger(name)
