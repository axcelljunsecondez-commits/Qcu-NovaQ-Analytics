"""Current interpretation note for selected Separate reports; no statistical assessment."""

from collections.abc import Mapping
from typing import Any

SELECTED_SCOPE_NOTICE = (
    "Load estimate uncertainty: Not checked. "
    "The variation test changes the load around a simulation average. "
    "It does not measure how much that average may change. "
    "Repeating the simulation with another seed can change its mean load and the configured-run result. "
    "This does not establish seed stability or future operational safety."
)


def selected_scope_notice(decision: Mapping[str, Any]) -> str | None:
    """Avoid repeating an identical note already contained in saved wording."""
    return None if SELECTED_SCOPE_NOTICE in str(decision.get("recommendation") or "") else SELECTED_SCOPE_NOTICE
