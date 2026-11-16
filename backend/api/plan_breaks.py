"""Suggested-only break composition; the Analysis Setup remains the Current baseline."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from backend.api.analysis_schemas import QueueSetup
from backend.queueing_engine.services.break_optimization import optimize_separate_breaks


class PlanBreakOptimization(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_shift_minutes: StrictInt = Field(ge=0, le=240, multiple_of=15)


def setup_digest(setup: dict[str, Any]) -> str:
    """Same canonical Setup identity used by scenario/evidence baseline bindings."""
    return hashlib.sha256(json.dumps(setup, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def setup_with_proposed_breaks(baseline: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """Overlay server-derived start moves, preserving all other baseline input fields."""
    draft = deepcopy(baseline)
    draft["breaks"] = [
        {**entry, "scheduled_start_time": proposed["scheduled_start_time"],
         "original_start_time": entry.get("original_start_time") or entry["scheduled_start_time"]}
        if proposed["shift_minutes"] else deepcopy(entry)
        for entry, proposed in zip(baseline.get("breaks") or [], proposal["proposed_breaks"], strict=True)
    ]
    return QueueSetup.model_validate(draft).model_dump(mode="json")


def build_optimized_break_setup(
    baseline: dict[str, Any], records: list[dict[str, Any]], *, target: float,
    max_shift_minutes: int, base_seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    descriptor = PlanBreakOptimization.model_validate({"max_shift_minutes": max_shift_minutes})
    proposal = optimize_separate_breaks(
        baseline, records, target=target, max_shift_minutes=descriptor.max_shift_minutes,
        replications=5, base_seed=base_seed,
    )
    return setup_with_proposed_breaks(baseline, proposal), proposal


BREAK_CHECK_BASIS = "plan_save_break_proposal_v1"


def break_check_record(proposal: dict[str, Any]) -> dict[str, Any]:
    """A compact copy of the break proposal the plan save already computed; nothing is recalculated.

    "current" is the analysis Setup's (uploaded) break schedule, "proposed" the plan's; both sides are
    the routing DES with the same seeds (``compare_break_schedules_des``).
    """
    des = proposal["des"]

    def side(name: str) -> dict[str, Any]:
        return {key: deepcopy(des[name][key]) for key in ("summary", "periods", "replications")}

    return {
        "basis": BREAK_CHECK_BASIS,
        "max_shift_minutes": proposal["max_shift_minutes"],
        "des": {"seeds": list(des["seeds"]), "current": side("current"), "proposed": side("proposed"),
                "comparison": deepcopy(des["comparison"])},
        **{key: deepcopy(proposal[key]) for key in
           ("peak_rho", "slots_above_target", "moves", "current_breaks", "proposed_breaks")},
    }


def break_plan_blockers(proposal: dict[str, Any], schedule: dict[str, Any]) -> list[str]:
    """Existing supervisor guards, shared by preview and independently verified plan save."""
    blockers = []
    if not proposal["moves"]:
        blockers.append("no_moves")
    if not proposal["all_below_target"]:
        blockers.append("break_limit")
    if not all(proposal["des"][side]["summary"]["customer_conservation"] for side in ("current", "proposed")):
        blockers.append("customer_accounting")
    paired = proposal["des"]["comparison"].get("paired_wait_change") or {}
    if paired.get("ci_lower") is None or paired.get("ci_upper") is None:
        blockers.append("wait_unavailable")
    elif paired.get("verdict") == "longer":
        blockers.append("wait_longer")
    if schedule["overall"] != "COMPLETE":
        blockers.append("staffing_check")
    return blockers


def resolve_scenario_plan_setup(baseline: dict[str, Any], calculation: dict[str, Any]) -> dict[str, Any]:
    """Read a server-verified, immutable plan schedule without changing Current's Setup."""
    if "break_optimization" not in calculation:
        if "plan_breaks" in calculation or "plan_setup_hash" in calculation:
            raise ValueError("Suggested break schedule has no verified optimization descriptor.")
        return baseline
    PlanBreakOptimization.model_validate(calculation["break_optimization"])
    breaks = calculation.get("plan_breaks")
    if not isinstance(breaks, list) or len(breaks) != len(baseline.get("breaks") or []):
        raise ValueError("Suggested break schedule is missing or invalid.")
    for original, entry in zip(baseline.get("breaks") or [], breaks, strict=True):
        if not isinstance(entry, dict) or any(
            entry.get(key) != original.get(key) for key in ("queue_id", "duration_minutes", "break_name")
        ):
            raise ValueError("Suggested breaks changed the baseline cashier, duration, name or order.")
    draft = QueueSetup.model_validate({**baseline, "breaks": deepcopy(breaks)}).model_dump(mode="json")
    if calculation.get("plan_setup_hash") != setup_digest(draft):
        raise ValueError("Suggested break schedule does not match its verified Setup identity.")
    return draft
