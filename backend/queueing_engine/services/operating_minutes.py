"""Clock formatting and arrival exposure in whole operating minutes."""

from __future__ import annotations


def format_clock(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def active_arrival_minutes(start: int, end: int, cutoff: int | None) -> int:
    """Exposure within the unchanged operating period, in whole minutes."""
    return max(0, (end if cutoff is None else min(end, cutoff)) - start)
