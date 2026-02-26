"""Observability layer: centralized logger setup for API and ETL/runtime tracing."""

from __future__ import annotations

import logging


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger once for structured single-line console output."""
    normalized = level.upper()
    logging.basicConfig(
        level=normalized,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.setLevel(normalized)
        logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger instance."""
    return logging.getLogger(name)
