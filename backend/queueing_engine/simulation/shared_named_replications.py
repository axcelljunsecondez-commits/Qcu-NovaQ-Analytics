"""Seeded replications of the named-employee shared-queue DES (Phase 5B-4.4 of the shared-queue enhancement).

Each replication draws its customers with the anonymous engine's own arrival generation, through its
public interface ``shared_continuous_des.draw_arrivals`` (X5), and runs the Phase 5B-4.3 named engine
(``shared_named_des.simulate_named_prescribed``) on them. This module generates no random numbers of
its own, and neither the named engine nor the employee state machine draws any. The customers of a
replication therefore depend only on the horizon, the demand periods, the run's root entropy, and
the replication index: every roster, required staffing, closing policy, and employee policy sees the
same customers for the same seed (common random numbers).

Spec: docs/superpowers/specs/2026-09-28-shared-queue-named-replications.md.
No monetary cost, acceptance rule, playback, API, or frontend. Nothing legacy imports this module.

Phase 5B-4.5 (docs/superpowers/specs/2026-09-28-shared-queue-named-playback.md) added
``inputs_sha256`` to the run provenance: a digest of the recorded simulation-defining inputs, so a
playback can check that it regenerates a replication from the inputs the run recorded.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
from collections.abc import Sequence
from dataclasses import asdict
from numbers import Integral
from typing import Any

import numpy as np

from backend.queueing_engine.config import MC_CONFIDENCE_LEVEL, MC_MAX_TRIALS
from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
)
from backend.queueing_engine.services.shared_workforce import Employee, ScheduledShift, WorkforceRules
from backend.queueing_engine.simulation.shared_continuous_des import ENGINE_VERSION, draw_arrivals
from backend.queueing_engine.simulation.shared_employee_states import (
    BASE_STATES,
    COMPLETED,
    STATE_MACHINE_VERSION,
    TRUNCATED_BY_CLOSING,
    UNFULFILLED,
)
from backend.queueing_engine.simulation.shared_named_des import (
    DEPARTED,
    HARD_CUTOFF_REASON,
    NAMED_ENGINE_VERSION,
    NO_ELIGIBLE_EMPLOYEE,
    EmployeeDesPolicy,
    simulate_named_prescribed,
)
from backend.queueing_engine.simulation.shared_replications import (
    CONTINUOUS_INTERVAL_METHOD,
    PARAMETER_UNCERTAINTY,
    SEED_SCHEME,
    summarize_metric,
)

METHOD_VERSION = "novaq-shared-named-replications-v2"

# The causes the state machine gives an unfulfilled break (shared_employee_states).
UNFULFILLED_CAUSES = ("released", "shift_not_activated", "cancelled_at_closing")

RANDOM_STREAMS = (
    "Customers come from shared_continuous_des.draw_arrivals, the public interface to the anonymous engine's "
    "_draw_arrivals: the replication's SeedSequence spawns two numpy.random.default_rng streams, arrival gaps "
    "(exponential with the demand period's rate, restarted at each period start) and then unit work (Exp(1), "
    "one per customer in arrival order). The named engine and the employee state machine draw no random numbers."
)
COMMON_RANDOM_NUMBERS = (
    "The customers of replication i depend only on the horizon, the demand periods, the root entropy, and i. The "
    "roster, required staffing, closing policy, and employee policy consume no random numbers, so runs with the "
    "same seed give every roster the same customers in every replication (customer_inputs_sha256 is equal)."
)
REPRODUCIBILITY = (
    "A replication is regenerated exactly from its root entropy and replication index under the recorded numpy "
    "version and bit generator. Equality of the streams across numpy versions (the 2.2.6 production lock, the "
    "2.4.6 local lock, and the requirements.txt range below 2.3 installed by CI) is not established: UNKNOWN."
)
NO_VERDICT_REASON = (
    "No approved acceptance (PASS/FAIL) rule exists for the named-employee DES, so no verdict, failure rate, or "
    "acceptability label is produced. The legacy utilization > 0.75 rule is not applied, and no employee-level "
    "threshold is defined."
)
CUSTOMER_INPUTS_DEFINITION = (
    "SHA-256 of the replication's (arrival hour, unit work) pairs in arrival order, one line per pair, each value "
    "written exactly with float.hex()."
)
INPUTS_DIGEST_DEFINITION = (
    "SHA-256 of the recorded simulation-defining inputs: the horizon, demand periods, required staffing, employees, "
    "workforce rules, roster (as provenance.inputs records them), closing policy, and employee policy. They are "
    "written as JSON with sorted keys: a dataclass as an object of its fields, a list or tuple as an array, a whole "
    "number as an integer, a string, boolean, or None as itself, and a float as {\"float\": float.hex()}; any other "
    "value is rejected. Equal digests mean equal recorded values (an int and a float of equal value differ); the "
    "digest makes no claim of semantic equivalence. It detects a later change to the recorded inputs or digest "
    "within the result; it is not a tamper-proof signature."
)
METRIC_DEFINITIONS = {
    "customers": (
        "arrivals; served (departed, including after closing under DRAIN); unserved (unserved_at_close) and its "
        "split by reason (hard_cutoff, no_eligible_employee); served_after_closing (service started at or after "
        "closing)."
    ),
    "waiting": (
        "wait_sum_hours: sum of served customers' waits. mean_wait_hours: the named engine's mean over served "
        "customers, undefined (None) when nobody was served. customer_hours_*: the integral of the line before "
        "and after closing, which also counts unserved customers' censored waits. max_queue_in_horizon: the "
        "largest line before closing."
    ),
    "closing": (
        "waiting_at_close and in_service_at_close: customers waiting or in service at closing. drain_crew_size: "
        "the frozen DRAIN crew (0 under HARD_CUTOFF). run_after_closing_hours: the run's finish (every customer "
        "resolved and every employee released) minus closing."
    ),
    "staffing": (
        "The named engine's P8 windows, in employee-hours: horizon (opening to closing), segments (each "
        "required staffing segment), after_closing (always present, zero length when the timeline ends at "
        "closing), and before_opening when a shift starts before opening. Series: duration, scheduled_active, "
        "accepting_capacity, busy_employee, register_occupancy, waiting_for_register. Inside the horizon only: "
        "required_staffing_hours and the shortfall and excess of schedule_realization_gap and requirement_gap."
    ),
    "employees": (
        "From the employee timeline: employee-hours by base state over the whole timeline and after closing; "
        "shift counts, overrun (release after the scheduled end) and activation delay; break counts by outcome "
        "and unfulfilled cause, and break delay (actual start - scheduled start) over started breaks; the number "
        "of employee state transitions. A maximum over an empty set is undefined (None)."
    ),
}


def _is_whole(value: object) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def replication_seed_sequence(root_entropy: int, replication_index: int) -> np.random.SeedSequence:
    """Replication ``replication_index``'s seed: ``SeedSequence(entropy=root_entropy, spawn_key=(i,))``.

    This is the Phase 4 scheme (``shared_replications.SEED_SCHEME``): the i-th child of
    ``SeedSequence(root_entropy).spawn(n)``, so any replication can be regenerated alone.
    """
    problems = []
    if not _is_whole(root_entropy) or root_entropy < 0:
        problems.append("root_entropy must be a whole number, 0 or more.")
    if not _is_whole(replication_index) or replication_index < 0:
        problems.append("replication_index must be a whole number, 0 or more.")
    if problems:
        raise SharedSegmentError(problems)
    return np.random.SeedSequence(entropy=int(root_entropy), spawn_key=(int(replication_index),))


def runtime_provenance() -> dict[str, str]:
    """The runtime needed to reproduce a replication: numpy and Python versions and the default bit generator."""
    return {
        "numpy_version": np.__version__,
        "python_version": platform.python_version(),
        "bit_generator": type(np.random.default_rng(0).bit_generator).__name__,
        "bit_generator_source": "numpy.random.default_rng in this runtime, which draw_arrivals uses for both streams",
    }


def customer_inputs_digest(arrivals: Sequence[tuple[float, float]]) -> str:
    """SHA-256 of the (arrival hour, unit work) pairs, each value written exactly with ``float.hex()``."""
    text = "\n".join(f"{float(at).hex()} {float(work).hex()}" for at, work in arrivals)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def named_inputs_snapshot(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    employees: Sequence[Employee],
    rules: WorkforceRules,
    roster: Sequence[ScheduledShift],
    required_staffing: Sequence[StaffingSegment],
) -> dict[str, Any]:
    """The simulation-defining inputs as plain values (``dataclasses.asdict``), as ``provenance.inputs`` records them."""
    return {
        "horizon": asdict(horizon),
        "demand_periods": [asdict(period) for period in demand_periods],
        "required_staffing": [asdict(segment) for segment in required_staffing],
        "employees": [asdict(employee) for employee in employees],
        "rules": asdict(rules),
        "roster": [asdict(item) for item in roster],
    }


def _canonical(value: object) -> Any:
    """A JSON-ready copy that keeps every recorded value exactly (``INPUTS_DIGEST_DEFINITION``)."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, float):
        return {"float": value.hex()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {key: _canonical(item) for key, item in value.items()}
    raise SharedSegmentError([f"The input digest cannot represent a value of type {type(value).__name__}."])


def named_inputs_digest(inputs: dict[str, Any], closing_policy: object, employee_policy: dict[str, Any]) -> str:
    """SHA-256 of the recorded inputs, closing policy, and employee policy (``INPUTS_DIGEST_DEFINITION``)."""
    document = {"inputs": inputs, "closing_policy": closing_policy, "employee_policy": employee_policy}
    text = json.dumps(_canonical(document), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def simulate_named_replication(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    employees: Sequence[Employee],
    rules: WorkforceRules,
    roster: Sequence[ScheduledShift],
    *,
    seed_sequence: np.random.SeedSequence,
    closing_policy: str,
    employee_policy: EmployeeDesPolicy,
    required_staffing: Sequence[StaffingSegment],
    max_trace_events: int | None = None,
) -> dict[str, Any]:
    """One replication: the anonymous engine's customers for ``seed_sequence``, then the named engine.

    Returns the Phase 5B-4.3 result unchanged, plus a ``replication`` block with the seed identity
    (entropy, spawn key, pool size), the customer inputs (count and digest), and the runtime.
    Replication i of a run uses ``replication_seed_sequence(root_entropy, i)``. The sequence must be
    unused. ``closing_policy``, ``employee_policy``, and ``required_staffing`` (X7) have no defaults.
    """
    if not isinstance(required_staffing, (list, tuple)) or not required_staffing or not all(
            isinstance(segment, StaffingSegment) for segment in required_staffing):
        raise SharedSegmentError(["required_staffing is required (X7): a non-empty list of StaffingSegment "
                                  "items, with no default."])
    arrivals = draw_arrivals(horizon, demand_periods, required_staffing, seed_sequence=seed_sequence)
    result = simulate_named_prescribed(
        horizon, demand_periods, employees, rules, roster, arrivals, closing_policy=closing_policy,
        employee_policy=employee_policy, required_staffing=required_staffing, max_trace_events=max_trace_events,
    )
    result["replication"] = {
        "seed_entropy": seed_sequence.entropy,
        "spawn_key": list(seed_sequence.spawn_key),
        "pool_size": seed_sequence.pool_size,
        "customer_inputs": {
            "count": len(arrivals), "sha256": customer_inputs_digest(arrivals),
            "definition": CUSTOMER_INPUTS_DEFINITION,
        },
        "arrival_generation": {"function": "shared_continuous_des.draw_arrivals", "engine_version": ENGINE_VERSION},
        "random_streams": RANDOM_STREAMS,
        "runtime": runtime_provenance(),
        "reproducibility": REPRODUCIBILITY,
    }
    return result


# ── One scalar row per replication ──────────────────────────────────────────

_SERIES = ("duration_hours", "scheduled_active_hours", "accepting_capacity_hours", "busy_employee_hours",
           "register_occupancy_hours", "waiting_for_register_hours")
_GAPS = ("schedule_realization_gap", "requirement_gap")


def _window_values(window: dict[str, Any]) -> dict[str, float]:
    values = {key: window[key] for key in _SERIES}
    if window["kind"] in ("staffing_segment", "horizon"):  # gaps exist only inside the operating horizon
        values["required_staffing_hours"] = window["required_staffing_hours"]
        for gap in _GAPS:
            values[f"{gap}_shortfall_hours"] = window[gap]["shortfall_hours"]
            values[f"{gap}_excess_hours"] = window[gap]["excess_hours"]
    return values


def _staffing_values(windows: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, Any] = {"segments": {}}
    for window in windows:
        if window["kind"] == "staffing_segment":
            by_kind["segments"][window["window"]] = _window_values(window)
        else:
            by_kind[window["kind"]] = _window_values(window)
    return by_kind


def _employee_values(timeline: dict[str, Any]) -> dict[str, Any]:
    shifts, breaks = timeline["shifts"], timeline["breaks"]
    activated = [row for row in shifts if row["activated"]]
    started = [row for row in breaks if row["actual_start"] is not None]
    causes = [row["unfulfilled_cause"] for row in breaks if row["outcome"] == UNFULFILLED]
    unknown = sorted(set(causes) - set(UNFULFILLED_CAUSES))
    if unknown:
        raise SharedSegmentError([f"Unknown unfulfilled break cause(s): {', '.join(unknown)}."])
    return {
        "employee_hours_by_state": {state: math.fsum(totals[state] for totals in timeline["state_totals"].values())
                                    for state in BASE_STATES},
        "employee_hours_after_closing_by_state": {
            state: math.fsum(row["end"] - row["start"] for row in timeline["intervals"]
                             if row["after_closing"] and row["state"] == state)
            for state in BASE_STATES},
        "shifts_scheduled": len(shifts),
        "shifts_activated": len(activated),
        "shifts_not_activated": len(shifts) - len(activated),
        "shifts_with_overrun": sum(1 for row in activated if row["overrun"] > 0),
        "overrun_hours_total": math.fsum(row["overrun"] for row in activated),
        "overrun_hours_max": max((row["overrun"] for row in activated), default=None),
        "activation_delay_hours_total": math.fsum(row["activation_delay"] for row in activated),
        "breaks_scheduled": len(breaks),
        "breaks_started": len(started),
        "breaks_completed": sum(1 for row in breaks if row["outcome"] == COMPLETED),
        "breaks_truncated_by_closing": sum(1 for row in breaks if row["outcome"] == TRUNCATED_BY_CLOSING),
        "breaks_unfulfilled": len(causes),
        "breaks_unfulfilled_by_cause": {cause: causes.count(cause) for cause in UNFULFILLED_CAUSES},
        "break_delay_hours_total": math.fsum(row["delay"] for row in started),
        "break_delay_hours_max": max((row["delay"] for row in started), default=None),
        "transitions": len(timeline["transitions"]),
    }


def named_replication_row(result: dict[str, Any], replication_index: int) -> dict[str, Any]:
    """The scalar summary kept for one replication; every value is read from the Phase 5B-4.3 result."""
    rows, counts, queue, at_close = result["customers"], result["counts"], result["queue"], result["at_close"]
    served_waits = [row["wait_hours"] for row in rows if row["status"] == DEPARTED]
    conservation = len(rows) == counts["arrivals"] == counts["departed"] + counts["unserved_at_close"] and len(
        served_waits) == counts["departed"]
    if not conservation:
        raise SharedSegmentError([f"Replication {replication_index} does not conserve customers."])
    return {
        "replication_index": replication_index,
        "spawn_key": list(result["replication"]["spawn_key"]),
        "customer_inputs_sha256": result["replication"]["customer_inputs"]["sha256"],
        "customer_conservation": conservation,
        "customers": {
            "arrivals": counts["arrivals"],
            "served": counts["departed"],
            "unserved": counts["unserved_at_close"],
            "unserved_hard_cutoff": counts["unserved_by_reason"][HARD_CUTOFF_REASON],
            "unserved_no_eligible_employee": counts["unserved_by_reason"][NO_ELIGIBLE_EMPLOYEE],
            "served_after_closing": counts["served_after_closing"],
        },
        "waiting": {
            "wait_sum_hours": math.fsum(served_waits),
            "mean_wait_hours": result["mean_wait_hours"],
            "customer_hours_in_horizon": queue["customer_hours_in_horizon"],
            "customer_hours_after_closing": queue["customer_hours_after_closing"],
            "customer_hours_total": queue["customer_hours_total"],
            "max_queue_in_horizon": queue["max_length_in_horizon"],
        },
        "closing": {
            "waiting_at_close": len(at_close["waiting_customer_ids"]),
            "in_service_at_close": len(at_close["in_service_customer_ids"]),
            "drain_crew_size": len(at_close["drain_crew"]),
            "run_after_closing_hours": result["finish"] - result["closing_time"],
        },
        "staffing": _staffing_values(result["staffing"]["windows"]),
        "employees": _employee_values(result["employee_timeline"]),
    }


# ── Aggregation (descriptive only) ──────────────────────────────────────────


def _summaries(values: list[Any]) -> Any:
    """Across-replication statistics of every scalar in a nested block (``None`` = undefined, never 0)."""
    first = values[0]
    if isinstance(first, dict):
        if any(not isinstance(value, dict) or value.keys() != first.keys() for value in values):
            raise SharedSegmentError(["Replication rows do not share the same quantities."])
        return {key: _summaries([value[key] for value in values]) for key in first}
    return summarize_metric(values)


def aggregate_named_replications(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-replication rows; every replication is included in every count and denominator."""
    if not rows:
        raise SharedSegmentError(["At least one replication row is required."])
    total = len(rows)
    served = sum(row["customers"]["served"] for row in rows)
    wait_sum = math.fsum(row["waiting"]["wait_sum_hours"] for row in rows)

    def frequency(predicate: Any) -> dict[str, int]:
        return {"replications": sum(1 for row in rows if predicate(row)), "denominator_replications": total}

    return {
        "replications": total,
        "customers": {
            "totals": {key: sum(row["customers"][key] for row in rows) for key in rows[0]["customers"]},
            "conserved_in_every_replication": all(row["customer_conservation"] for row in rows),
            "per_replication": _summaries([row["customers"] for row in rows]),
        },
        "waiting_time": {
            "mean_of_replication_means_hours": {
                **summarize_metric([row["waiting"]["mean_wait_hours"] for row in rows]),
                "definition": (
                    "Mean over replications of each replication's mean wait of served customers; replications "
                    "with no served customer are undefined and counted in n_undefined."
                ),
            },
            "customer_weighted_mean_hours": {
                "value": wait_sum / served if served else None,
                "numerator_wait_hours": wait_sum,
                "denominator_served_customers": served,
                "definition": "Sum of all served customers' waits over all replications / all served customers.",
                "interval": "Not computed.",
            },
        },
        "metrics": {block: _summaries([row[block] for row in rows])
                    for block in ("waiting", "closing", "staffing", "employees")},
        "outcome_counts": {
            "definition": "Descriptive frequencies over all replications, not failure rates.",
            "with_unserved_customers": frequency(lambda row: row["customers"]["unserved"] > 0),
            "with_service_after_closing": frequency(lambda row: row["customers"]["served_after_closing"] > 0),
            "with_shift_overrun": frequency(lambda row: row["employees"]["shifts_with_overrun"] > 0),
            "with_unfulfilled_breaks": frequency(lambda row: row["employees"]["breaks_unfulfilled"] > 0),
        },
        "verdict": None,
        "verdict_reason": NO_VERDICT_REASON,
    }


def run_named_replications(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    employees: Sequence[Employee],
    rules: WorkforceRules,
    roster: Sequence[ScheduledShift],
    *,
    replications: int,
    seed: int | None,
    closing_policy: str,
    employee_policy: EmployeeDesPolicy,
    required_staffing: Sequence[StaffingSegment],
) -> dict[str, Any]:
    """Run ``replications`` independent named-employee replications and aggregate them.

    ``replications`` (1 to ``config.MC_MAX_TRIALS``), ``seed`` (``None`` draws fresh entropy, recorded as
    ``root_entropy``), ``closing_policy``, ``employee_policy``, and ``required_staffing`` are required.
    Each replication keeps one scalar row; ``simulate_named_replication`` with
    ``replication_seed_sequence(root_entropy, i)`` regenerates replication i in full.
    """
    problems = []
    if not _is_whole(replications) or not 1 <= replications <= MC_MAX_TRIALS:
        problems.append(f"replications must be a whole number from 1 to {MC_MAX_TRIALS} (config.MC_MAX_TRIALS).")
    if seed is not None and (not _is_whole(seed) or seed < 0):
        problems.append("seed must be a whole number, 0 or more, or None.")
    if problems:
        raise SharedSegmentError(problems)

    root_entropy = np.random.SeedSequence(seed).entropy
    assert isinstance(root_entropy, int)  # the seed itself, or fresh entropy when the seed is None
    rows = []
    for index in range(replications):
        result = simulate_named_replication(
            horizon, demand_periods, employees, rules, roster,
            seed_sequence=replication_seed_sequence(root_entropy, index), closing_policy=closing_policy,
            employee_policy=employee_policy, required_staffing=required_staffing, max_trace_events=0,
        )
        rows.append(named_replication_row(result, index))

    inputs = named_inputs_snapshot(horizon, demand_periods, employees, rules, roster, required_staffing)
    policy = asdict(employee_policy)
    return {
        "replications": rows,
        "summary": aggregate_named_replications(rows),
        "provenance": {
            "method_version": METHOD_VERSION,
            "named_engine_version": NAMED_ENGINE_VERSION,
            "state_machine_version": STATE_MACHINE_VERSION,
            "arrival_engine_version": ENGINE_VERSION,
            "metric_provenance": "des_named_replications",
            "method": "Independent replications of the named-employee continuous shared-queue DES over the whole horizon.",
            "parameter_uncertainty": PARAMETER_UNCERTAINTY,
            "replications": replications,
            "replication_limits": {"min": 1, "max": MC_MAX_TRIALS, "source": "config.MC_MAX_TRIALS"},
            "seed": seed,
            "root_entropy": root_entropy,
            "seed_scheme": SEED_SCHEME,
            "random_streams": RANDOM_STREAMS,
            "common_random_numbers": COMMON_RANDOM_NUMBERS,
            "reproducibility": REPRODUCIBILITY,
            "runtime": runtime_provenance(),
            "closing_policy": closing_policy,
            "employee_policy": policy,
            "confidence_level": MC_CONFIDENCE_LEVEL,
            "interval_method": CONTINUOUS_INTERVAL_METHOD,
            "metric_definitions": dict(METRIC_DEFINITIONS),
            "time_unit": "hours from the horizon start; staffing and employee quantities in employee-hours",
            "retained": (
                "One scalar row per replication; no events, customer rows, or employee timelines. "
                "simulate_named_replication with replication_seed_sequence(root_entropy, i) regenerates "
                "replication i in full."
            ),
            "monetary_cost": "None: no pay or cost is computed (workforce cost is Phase 5B-5).",
            "inputs": inputs,
            "inputs_sha256": named_inputs_digest(inputs, closing_policy, policy),
            "inputs_digest_definition": INPUTS_DIGEST_DEFINITION,
        },
    }
