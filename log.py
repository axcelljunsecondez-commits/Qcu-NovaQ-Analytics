"""Centralized structured logging configuration."""

from __future__ import annotations

import logging
import os
import sys
from typing import TextIO


def _structured_formatter() -> logging.Formatter:
    fmt = os.environ.get("LOG_FORMAT", "text")

    if fmt == "json":
        return logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"module":"%(name)s","message":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    return logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def configure_logging(
    level: str | int | None = None,
    stream: TextIO | None = None,
) -> None:
    """Configure the root logger once at application startup.

    Parameters
    ----------
    level : str or int, optional
        Log level (default: INFO, overridable via LOG_LEVEL env var).
    stream : TextIO, optional
        Output stream (default: stderr).
    """
    effective_level = level or os.environ.get("LOG_LEVEL", "INFO")
    if isinstance(effective_level, str):
        effective_level = effective_level.upper()

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(_structured_formatter())

    root = logging.getLogger()
    root.setLevel(effective_level)
    # Avoid duplicate handlers if called more than once
    root.handlers.clear()
    root.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("streamlit").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger for the given module name."""
    return logging.getLogger(name)
