"""Centralized structured logging configuration."""

from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a child logger for the given module name."""
    return logging.getLogger(name)
