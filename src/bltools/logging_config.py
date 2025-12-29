import structlog
import sys
import logging
from typing import Any


def configure_logging(verbose: bool = False) -> None:
    """
    Configure structlog and standard logging.
    """
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
    ]

    # If verbose, we might want debug logs from libraries too
    log_level = logging.DEBUG if verbose else logging.INFO

    if sys.stdout.isatty():
        # Pretty printing for terminal
        processors.extend([structlog.dev.ConsoleRenderer()])
    else:
        # JSON for production/docker
        processors.extend([structlog.processors.JSONRenderer()])

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )
