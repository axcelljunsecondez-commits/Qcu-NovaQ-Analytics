"""Current selected-load and legacy interpretation notices and read-only projections."""

import json
from collections.abc import Mapping
from typing import Any

from backend.queueing_engine.statistics.selected_load_uncertainty import SELECTED_LOAD_METHOD

SELECTED_LOAD_ASSESSMENT_NOTICE = (
    "Validation checks uncertainty in the average customer load estimated by simulation. "
    "Unsupported or inconclusive checks remain Insufficient evidence. "
    "This does not establish seed stability or future operational safety."
)

SELECTED_SCOPE_NOTICE = (
    "Load estimate uncertainty: Not checked. "
    "The variation test changes the load around a simulation average. "
    "It does not measure how much that average may change. "
    "Repeating the simulation with another seed can change its mean load and the configured-run result. "
    "This does not establish seed stability or future operational safety."
)


def selected_scope_notice(decision: Mapping[str, Any]) -> str | None:
    """Avoid repeating an identical note already contained in saved wording."""
    notice = (SELECTED_LOAD_ASSESSMENT_NOTICE if decision.get("selected_load_method") == SELECTED_LOAD_METHOD
              else SELECTED_SCOPE_NOTICE)
    return None if notice in str(decision.get("recommendation") or "") else notice


def selected_load_fields(result: Mapping[str, Any]) -> dict[str, Any]:
    """Carry optional persisted metadata without changing legacy/shared models."""
    return {key: result[key] for key in ("selected_load_method", "load_uncertainty") if key in result}


def selected_load_provenance(validation: Mapping[str, Any]) -> dict[str, str]:
    """Existing provenance rows carry canonical technical data, not new labels."""
    if validation.get("selected_load_method") != SELECTED_LOAD_METHOD:
        return {}
    encode = lambda value: json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(", ", ": "))
    result = {"selected_load_method": SELECTED_LOAD_METHOD,
              "selected_load_family": encode(validation.get("load_uncertainty"))}
    for period in validation.get("periods") or []:
        for row in period.get("queues") or []:
            assessment = row.get("load_assessment")
            if isinstance(assessment, Mapping):
                result[f"selected_load_assessment:{period.get('time')}/{row.get('queue_id')}"] = encode({
                    **assessment, "raw_mc_verdict": row.get("raw_mc_verdict")})
    return result
