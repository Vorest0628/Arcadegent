"""Observability layer: centralized logger setup for API and ETL/runtime tracing."""

from __future__ import annotations

import logging


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger once for structured single-line console output."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger instance."""
    return logging.getLogger(name)

