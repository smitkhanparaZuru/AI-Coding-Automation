from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(log_level: str, debug: bool) -> None:
    """Configure structlog with stdlib integration.

    Args:
        log_level: One of DEBUG / INFO / WARNING / ERROR / CRITICAL.
        debug: When True, use human-friendly ConsoleRenderer; otherwise JSON.
    """
    level = logging.DEBUG if debug else getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
    )

    processors: list = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
    ]

    if debug:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named structlog logger.

    Args:
        name: Logger name (e.g. ``"cli"``, ``"repo.analyzer"``).
            Surfaces as the ``logger=`` field in every log event.

    Returns:
        A bound structlog logger.
    """
    return structlog.get_logger().bind(logger=name)
