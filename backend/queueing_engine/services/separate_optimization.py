"""Separate-queue optimization foundation: candidates built around verified math.

A separate queue is one physical queue plus one physical server; the
optimization variable is the number of ACTIVE single-server lanes per time
period — never servers inside a lane, never pooled demand.

Architecture (new orchestration, reused mathematics):

- candidate construction, demand-conservation checks, shortest-active-queue
  routing, feasibility orchestration, and ranking live here;
- queueing formulas, central model selection, stability/utilization/Wq math,
  and cost calculations are reused unchanged from existing services.

Step-8 representation finding (verified against repository mathematics):
only the full-active lane set is evaluable with existing per-queue analytical
models. A reduced active set under shortest-queue routing has no approved
analytical representation in NovaQ — not equal splitting (unjustified), not
pooled M/M/c (violates one-server-per-queue), not original per-queue rates
(ignores redistributed demand). Reduced candidates therefore resolve to
UNSUPPORTED on the analytical path with an exact reason instead of fabricated
numbers. The routing DES evaluator (``evaluate_candidate_with_des``) covers
reduced sets when every active lane carries empirical service samples: one
conserved Poisson arrival stream plus shortest-system-size routing with
seeded fair ties, served from each lane's own resampled measurements. The
Current-state parallel DES engine has no routing policy, so this evaluator
implements its own SimPy core reusing the engine's primitives (empirical
resampling, dedicated lifecycles, trace schema) and existing cost helpers.
Variance-only aggregate rows stay UNSUPPORTED on both paths.
"""

from __future__ import annotations

import math
import random
import statistics
from datetime import time as datetime_time
from numbers import Real
from typing import Any, TypeGuard

import simpy
from scipy.stats import t as student_t

from backend.queueing_engine.config import (
    DEFAULT_SERVER_COST_HR,
    DEFAULT_WAIT_COST_HR,
    PRE_BREAK_CUTOFF_MINUTES,
)
from backend.queueing_engine.services.model_selection import (
    UNSUPPORTED_SEPARATE_MODEL,
    select_model,
)
from backend.queueing_engine.services.optimization import (
    _compute_waiting_cost,
    _segment_server_cost,
)
from backend.queueing_engine.simulation.queue_lifecycle import (
    DedicatedQueueLifecycle,
    DedicatedQueueState,
    QueueReactivationPolicyError,
    dedicated_server_id,
    scheduled_active_queue_ids,
)

# Engine version stamped on verified Separate-Queue DES optimization snapshots.
# v2: representative-day candidates are read from one continuous-day DES
# (9b1f95a4); v1 snapshots hold 24 h per-period figures and are unsupported.
SEPARATE_DES_ENGINE_VERSION = "novaq-2026-09-separate-des-v2"

SEPARATE_MIN_UTILIZATION = 0.40
SEPARATE_MAX_UTILIZATION = 0.90
SEPARATE_DEFAULT_UTILIZATION = 0.70

# Default DES replication count: a configuration default for development, not
# an academic constant. No approved production replication count exists yet;
# expose for later product approval. (Downstream MC_DEFAULT_TRIALS = 2000
# counts cheap analytical perturbations, not full SimPy runs.)
DES_REPLICATIONS_DEFAULT_COUNT = 5

# Replication defaults mirror engine conventions without importing the heavy
# simulation package into services (cycle hygiene); parity is pinned by test:
# base seed mirrors RANDOM_SEED, horizon mirrors SIM_HOURS_PER_SEGMENT,
# event bound mirrors trace_simulate_segments max_events.
DES_DEFAULT_BASE_SEED = 42
DES_DEFAULT_DURATION_HOURS = 24.0
DES_DEFAULT_MAX_EVENTS = 10000

_DES_REPLICATION_CONFIG_KEYS = frozenset({
    "replications", "base_seed", "duration_hours", "max_events",
    "target", "server_cost", "waiting_cost",
})

_UTILIZATION_TOLERANCE = 1e-12


def _is_number(value: Any) -> TypeGuard[float]:
    if isinstance(value, bool):
        return False
    return isinstance(value, Real) and math.isfinite(float(value))


def validate_separate_target(value) -> float:
    """Validate the utilization ceiling for the separate pipeline.

    None selects the default. Anything outside [0.40, 0.90], non-numeric,
    or non-finite raises ValueError. The target is never silently relaxed.
    """
    if value is None:
        return SEPARATE_DEFAULT_UTILIZATION
    if isinstance(value, bool):
        raise ValueError("Utilization target must be a number between 0.40 and 0.90.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("Utilization target must be a number between 0.40 and 0.90.") from None
    if not math.isfinite(number) or not SEPARATE_MIN_UTILIZATION <= number <= SEPARATE_MAX_UTILIZATION:
        raise ValueError("Utilization target must be a number between 0.40 and 0.90.")
    return number


def full_coverage_min_lanes(queue_setup, requested) -> int:
    """Lower lane bound for Separate optimization under FULL COVERAGE.

    Every configured demand queue must stay active, so the only admissible
    ``min_active_lanes`` is the configured queue count (None selects it).
    Any other value would let the search close a lane; it raises ValueError.
    """
    setup = queue_setup if isinstance(queue_setup, dict) else {}
    count = len(setup.get("queue_ids") or [])
    if requested is None:
        return count
    if isinstance(requested, bool) or not isinstance(requested, int) or requested != count:
        raise ValueError(
            f"Separate optimization requires full coverage: min_active_lanes must equal "
            f"the configured queue count ({count}), got {requested!r}.")
    return count


def build_candidates(available_ids, min_lanes=None, max_lanes=None) -> list[dict]:
    """Build active-lane count candidates in configured order.

    Each candidate names its active set (first k configured IDs) and the
    complementary inactive set. Counts run 1..N filtered by lane bounds.
    """
    ids = list(available_ids or [])
    count = len(ids)
    if count == 0:
        raise ValueError("At least one configured queue is required.")
    low = 1 if min_lanes is None else min_lanes
    high = count if max_lanes is None else max_lanes
    for bound in (low, high):
        if isinstance(bound, bool) or not isinstance(bound, int):
            raise ValueError("Lane bounds must be integers.")
    if low < 1 or high < 1 or low > high or low > count:
        raise ValueError("Lane bounds must satisfy 1 <= min <= max within the configured queue count.")
    high = min(high, count)
    return [
        {"active_queue_ids": ids[:size], "inactive_queue_ids": ids[size:]}
        for size in range(low, high + 1)
    ]


def _validated_lambda(row: dict) -> float:
    value = row.get("lambda")
    if not _is_number(value) or value < 0:
        raise ValueError(f"Queue {row.get('queue_id')!r} has no valid arrival rate.")
    return value


def candidate_total_lambda(queue_inputs, active_ids) -> float:
    """Total modeled demand for a candidate, conserved by construction.

    The total always spans every supplied queue row regardless of the active
    set: closing lanes never deletes demand. Unknown IDs, duplicate IDs, or
    invalid rates raise ValueError instead of contributing zero.
    """
    by_id: dict[str, dict] = {}
    for row in queue_inputs:
        if not isinstance(row, dict):
            raise ValueError("Queue inputs must be dictionaries.")
        queue_id = row.get("queue_id")
        if not isinstance(queue_id, str) or not queue_id:
            raise ValueError("Queue inputs must carry non-empty string queue IDs.")
        if queue_id in by_id:
            raise ValueError(f"Duplicate queue ID in candidate inputs: {queue_id!r}.")
        by_id[queue_id] = row
    for queue_id in active_ids:
        if queue_id not in by_id:
            raise ValueError(f"Unknown queue ID in candidate: {queue_id!r}.")
    return sum(_validated_lambda(by_id[queue_id]) for queue_id in by_id)


def check_demand_conserved(original_total: float, candidate_total: float) -> bool:
    """True only when the candidate total exactly matches the original total."""
    if not _is_number(original_total) or not _is_number(candidate_total):
        return False
    return float(original_total) == float(candidate_total)


def route_arrival(active_ids, queue_lengths, tie_order, rng=None) -> str:
    """Shortest-active-queue routing with deterministic configured-order ties.

    Pure execution rule: no mathematics, no costs, no ranking. Inactive
    queues (including IDs absent from the lengths map values for active
    queues) never receive arrivals. Empty active sets raise ValueError.
    When ``rng`` (a ``random.Random``-compatible generator) is supplied,
    lanes tied for the shortest length share arrivals uniformly at random
    instead of collapsing to configured order; without it, ties resolve to
    configured order deterministically.
    """
    active = list(active_ids or [])
    if not active:
        raise ValueError("Routing requires at least one active queue.")
    order = list(tie_order or [])
    scored: list[tuple[float, int, str]] = []
    for queue_id in active:
        if queue_id not in queue_lengths:
            raise ValueError(f"No observed length for active queue {queue_id!r}.")
        length = queue_lengths[queue_id]
        if not _is_number(length) or float(length) < 0:
            raise ValueError(f"Invalid observed length for queue {queue_id!r}.")
        try:
            rank = order.index(queue_id)
        except ValueError:
            rank = len(order)
        scored.append((float(length), rank, queue_id))
    best = min(score for score, _, _ in scored)
    tied = sorted((rank, queue_id) for score, rank, queue_id in scored if score == best)
    if rng is not None:
        return rng.choice([queue_id for _, queue_id in tied])
    return tied[0][1]


def _validate_queue_row(row: dict) -> dict | None:
    """Return a normalized row dict, or None when the row is malformed.

    Malformed means: not a dict, missing/blank queue ID, non-finite lambda
    or mu, lambda < 0, mu <= 0, or c other than integer 1 (one queue is one
    server; anything else is invalid input, not a model question).
    """
    if not isinstance(row, dict):
        return None
    queue_id = row.get("queue_id")
    if not isinstance(queue_id, str) or not queue_id:
        return None
    lambda_ = row.get("lambda")
    mu = row.get("mu")
    servers = row.get("c", 1)
    if not _is_number(lambda_) or lambda_ < 0:
        return None
    if not _is_number(mu) or mu <= 0:
        return None
    if not _is_number(servers) or float(servers) != 1.0:
        return None
    clean = {
        "queue_id": queue_id,
        "lambda": lambda_,
        "mu": mu,
        "c": 1,
    }
    for key in ("variance", "K", "theta", "server_cost", "regular_hours", "ot_hours", "total_hours"):
        value = row.get(key)
        if value is None:
            continue
        if key in ("server_cost", "regular_hours", "ot_hours", "total_hours") and (
            not _is_number(value) or value < 0
        ):
            return None
        clean[key] = value
    return clean


def evaluate_candidate(candidate: dict, queues_by_id: dict, *, target: float,
                       server_cost: float = DEFAULT_SERVER_COST_HR,
                       waiting_cost: float = DEFAULT_WAIT_COST_HR) -> dict:
    """Evaluate one candidate through existing mathematics, or refuse honestly.

    Returns FEASIBLE with per-queue evidence and total cost, INFEASIBLE with a
    reason, UNSUPPORTED when no approved representation exists, or
    INVALID_INPUT for malformed data. Never fabricates numbers.
    """
    ceiling = validate_separate_target(target)
    available = candidate.get("available_queue_ids") or []
    active = candidate.get("active_queue_ids") or []
    inactive = candidate.get("inactive_queue_ids") or []
    time_label = candidate.get("time", "segment")
    base = {
        "time": time_label,
        "available_queue_ids": list(available),
        "active_queue_ids": list(active),
        "inactive_queue_ids": list(inactive),
        "target_utilization": ceiling,
    }
    if not active or set(active) | set(inactive) != set(available) or set(active) & set(inactive):
        return {**base, "status": "INVALID_INPUT",
                "reason": "Candidate active/inactive sets must partition the available queues with at least one active lane.",
                "evaluations": None, "total_cost": None}
    normalized: dict[str, dict] = {}
    for queue_id in available:
        row = queues_by_id.get(queue_id) if isinstance(queues_by_id, dict) else None
        clean = _validate_queue_row(row) if isinstance(row, dict) else None
        if clean is None:
            return {**base, "status": "INVALID_INPUT",
                    "reason": f"Queue {queue_id!r} has invalid analytical inputs.",
                    "evaluations": None, "total_cost": None}
        normalized[queue_id] = clean
    if inactive:
        return {**base, "status": "UNSUPPORTED",
                "reason": ("Reduced active-lane sets have no approved mathematical representation: "
                           "shortest-queue redistribution cannot be evaluated with existing per-queue models, "
                           "and no pooled or split approximation is justified."),
                "evaluations": None, "total_cost": None}
    evaluations = []
    for queue_id in active:
        row = normalized[queue_id]
        selection = select_model(
            row["lambda"], row["mu"], 1, variance=row.get("variance"),
            K=row.get("K"), theta=row.get("theta"), queue_structure="separate_queues",
        )
        if selection.get("model_id") == "separate_fifo_unsupported":
            return {**base, "status": "UNSUPPORTED",
                    "reason": f"Queue {queue_id!r} is not supported: "
                              f"{selection.get('name')}.",
                    "evaluations": None, "total_cost": None}
        metrics = selection.get("metrics") or {}
        evaluations.append({
            "queue_id": queue_id,
            "lambda": row["lambda"],
            "mu": row["mu"],
            "model": selection.get("name"),
            "model_id": selection.get("model_id"),
            "rho": metrics.get("rho"),
            "Wq": metrics.get("Wq"),
            "Lq": metrics.get("Lq"),
            "stable": bool(metrics.get("stable")),
        })
    unstable = sorted(item["queue_id"] for item in evaluations if not item["stable"])
    if unstable:
        return {**base, "status": "INFEASIBLE",
                "reason": f"Unstable queues under evaluated load: {', '.join(unstable)}.",
                "evaluations": evaluations, "total_cost": None}
    over_target = sorted(
        item["queue_id"] for item in evaluations
        if not _is_number(item["rho"]) or float(item["rho"]) > ceiling + _UTILIZATION_TOLERANCE
    )
    if over_target:
        return {**base, "status": "INFEASIBLE",
                "reason": f"Utilization exceeds the {ceiling:.0%} ceiling for: {', '.join(over_target)}.",
                "evaluations": evaluations, "total_cost": None}
    server_total = 0.0
    waiting_total = 0.0
    for item in evaluations:
        lane_cost = _segment_server_cost(normalized[item["queue_id"]], server_cost)
        lane_wait = _compute_waiting_cost(item["lambda"], item["Wq"], waiting_cost)
        server_total += lane_cost
        waiting_total += lane_wait
    return {**base, "status": "FEASIBLE", "reason": None,
            "evaluations": evaluations,
            "total_lambda": sum(item["lambda"] for item in evaluations),
            "total_cost": server_total + waiting_total,
            "server_cost": server_total, "waiting_cost": waiting_total}


def validate_des_replication_config(config: dict | None) -> dict:
    """Validate and normalize an optimizer DES replication configuration.

    None selects documented defaults. Unknown keys, non-integer or
    non-positive replication counts, non-integer base seeds, non-positive
    horizons, and non-positive event bounds raise ValueError. Bools are
    rejected wherever Python integer coercion could otherwise accept them.
    """
    raw = {} if config is None else config
    if not isinstance(raw, dict):
        raise ValueError("DES replication config must be a mapping.")
    unknown = set(raw) - _DES_REPLICATION_CONFIG_KEYS
    if unknown:
        raise ValueError(f"Unknown DES replication config keys: {sorted(unknown)}.")
    replications = raw.get("replications", DES_REPLICATIONS_DEFAULT_COUNT)
    if isinstance(replications, bool) or not isinstance(replications, int) or replications <= 0:
        raise ValueError("DES replication count must be a positive integer.")
    base_seed = raw.get("base_seed", DES_DEFAULT_BASE_SEED)
    if isinstance(base_seed, bool) or not isinstance(base_seed, int):
        raise ValueError("DES replication base seed must be an integer.")
    duration_hours = raw.get("duration_hours", DES_DEFAULT_DURATION_HOURS)
    if not _is_number(duration_hours) or float(duration_hours) <= 0:
        raise ValueError("DES replication horizon must be a finite positive duration_hours.")
    max_events = raw.get("max_events", DES_DEFAULT_MAX_EVENTS)
    if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events <= 0:
        raise ValueError("DES replication trace bound must be a positive integer max_events.")
    target = validate_separate_target(raw.get("target", None))
    server_cost = raw.get("server_cost", DEFAULT_SERVER_COST_HR)
    waiting_cost = raw.get("waiting_cost", DEFAULT_WAIT_COST_HR)
    for name, value in (("server_cost", server_cost), ("waiting_cost", waiting_cost)):
        if isinstance(value, bool) or not _is_number(value) or float(value) < 0:
            raise ValueError(f"DES replication {name} must be a finite non-negative number.")
    return {
        "replications": replications,
        "base_seed": base_seed,
        "duration_hours": float(duration_hours),
        "max_events": max_events,
        "target": target,
        "server_cost": float(server_cost),
        "waiting_cost": float(waiting_cost),
    }


def replication_seeds(base_seed: int, count: int) -> list[int]:
    """Deterministic replication seed schedule: base, base+1, ... .

    Mirrors the engine's per-segment seed-increment convention so matched
    candidates evaluated under the same config share equivalent stochastic
    inputs (matched replication seeds; full CRN coupling is not claimed).
    """
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValueError("Replication count must be a positive integer.")
    if isinstance(base_seed, bool) or not isinstance(base_seed, int):
        raise ValueError("Replication base seed must be an integer.")
    return [base_seed + index for index in range(count)]


def _validated_samples(row: dict) -> list[float] | None:
    """Return finite positive service samples, or None when absent/invalid."""
    samples = row.get("service_samples_hours")
    if not isinstance(samples, list) or not samples:
        return None
    clean: list[float] = []
    for sample in samples:
        if not _is_number(sample) or float(sample) <= 0:
            return None
        clean.append(float(sample))
    return clean


def evaluate_candidate_with_des(candidate: dict, queues_by_id: dict, *, duration_hours: float,
                                seed: int | None = None, target: float | None = None,
                                server_cost: float = DEFAULT_SERVER_COST_HR,
                                waiting_cost: float = DEFAULT_WAIT_COST_HR,
                                max_events: int = 10000) -> dict:
    """Evaluate one candidate with a conserved-arrival routing DES, or refuse honestly.

    Reduced active-lane sets have no approved analytical representation, so
    this evaluator simulates them: one Poisson stream carrying the conserved
    total demand, routed by shortest waiting count with configured-order ties,
    served from each active lane's own empirical service samples. Statuses
    mirror ``evaluate_candidate``: FEASIBLE/INFEASIBLE carry measured evidence,
    UNSUPPORTED marks missing empirical inputs, INVALID_INPUT marks malformed
    data. Never fabricates numbers. An optional ``breaks`` candidate entry
    carries pre-converted DES offset records for active lanes. Both measured
    verdicts return the run's ``trace_events``/``trace_truncated`` playback
    evidence; only the refusal statuses, which never reach the DES, omit it.
    """
    ceiling = validate_separate_target(target)
    available = candidate.get("available_queue_ids") or []
    active = candidate.get("active_queue_ids") or []
    inactive = candidate.get("inactive_queue_ids") or []
    time_label = candidate.get("time", "segment")
    base = {
        "time": time_label,
        "available_queue_ids": list(available),
        "active_queue_ids": list(active),
        "inactive_queue_ids": list(inactive),
        "target_utilization": ceiling,
    }
    if not active or set(active) | set(inactive) != set(available) or set(active) & set(inactive):
        return {**base, "status": "INVALID_INPUT",
                "reason": "Candidate active/inactive sets must partition the available queues with at least one active lane.",
                "evaluations": None, "total_cost": None}
    if not _is_number(duration_hours) or float(duration_hours) <= 0:
        return {**base, "status": "INVALID_INPUT",
                "reason": "DES evaluation requires a finite positive duration_hours horizon.",
                "evaluations": None, "total_cost": None}
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        return {**base, "status": "INVALID_INPUT",
                "reason": "DES evaluation requires an integer seed or None.",
                "evaluations": None, "total_cost": None}
    if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events <= 0:
        return {**base, "status": "INVALID_INPUT",
                "reason": "DES evaluation requires a positive integer max_events bound.",
                "evaluations": None, "total_cost": None}
    normalized: dict[str, dict] = {}
    for queue_id in available:
        row = queues_by_id.get(queue_id) if isinstance(queues_by_id, dict) else None
        clean = _validate_queue_row(row) if isinstance(row, dict) else None
        if clean is None:
            return {**base, "status": "INVALID_INPUT",
                    "reason": f"Queue {queue_id!r} has invalid analytical inputs.",
                    "evaluations": None, "total_cost": None}
        normalized[queue_id] = clean
    sample_lists: dict[str, list[float]] = {}
    for queue_id in active:
        raw = queues_by_id[queue_id]
        if "service_samples_hours" not in raw:
            return {**base, "status": "UNSUPPORTED",
                    "reason": (f"Queue {queue_id!r} carries no empirical service samples: routing DES "
                               "evaluation resamples each active lane's own measured service times, and "
                               "a variance-only aggregate row cannot supply them."),
                    "evaluations": None, "total_cost": None}
        samples = _validated_samples(raw)
        if samples is None:
            return {**base, "status": "INVALID_INPUT",
                    "reason": f"Queue {queue_id!r} carries malformed empirical service samples.",
                    "evaluations": None, "total_cost": None}
        sample_lists[queue_id] = samples
    horizon = float(duration_hours)
    total_lambda = sum(normalized[queue_id]["lambda"] for queue_id in available)
    raw_breaks = candidate.get("breaks")
    active_set = set(active)
    available_set = set(available)
    if raw_breaks is None:
        run_breaks = None
    else:
        if not isinstance(raw_breaks, list):
            return {**base, "status": "INVALID_INPUT",
                    "reason": "Candidate breaks must be a list of break records.",
                    "evaluations": None, "total_cost": None}
        run_breaks = []
        for entry in raw_breaks:
            if not isinstance(entry, dict):
                return {**base, "status": "INVALID_INPUT",
                        "reason": "Candidate break records must be dictionaries.",
                        "evaluations": None, "total_cost": None}
            queue_id = entry.get("queue_id")
            if queue_id not in available_set:
                return {**base, "status": "INVALID_INPUT",
                        "reason": f"Candidate break references unknown queue {queue_id!r}.",
                        "evaluations": None, "total_cost": None}
            if queue_id in active_set:
                run_breaks.append(entry)
    try:
        lanes, trace, trace_truncated, _ = _run_routing_des(
            active_ids=active, tie_order=available, samples_by_id=sample_lists,
            total_lambda=total_lambda, duration_hours=horizon, seed=seed,
            time_label=time_label, max_events=max_events, breaks=run_breaks,
        )
    except ValueError as exc:
        return {**base, "status": "INVALID_INPUT",
                "reason": f"Invalid break schedule: {exc}",
                "evaluations": None, "total_cost": None}
    evaluations = []
    for queue_id in available:
        if queue_id in lanes:
            stats = lanes[queue_id]
            mean_service = sum(sample_lists[queue_id]) / len(sample_lists[queue_id])
            served = stats["served"]
            waiting_left = len(stats["lifecycle"].waiting_customer_ids)
            in_service = 1 if stats["lifecycle"].in_service_customer_id is not None else 0
            wq = stats["wait_sum"] / served if served else None
            rho = min(1.0, stats["busy_time"] / horizon) if horizon > 0 else 0.0
            evaluations.append({
                "queue_id": queue_id,
                "active": True,
                "lambda": normalized[queue_id]["lambda"],
                "lambda_routed_sim": stats["arrivals"] / horizon,
                "mu": 1.0 / mean_service,
                "c": 1,
                "server_id": stats["lifecycle"].server_id,
                "arrivals": stats["arrivals"],
                "served": served,
                "waiting": waiting_left,
                "in_service": in_service,
                "Wq": wq,
                "rho": rho,
                "stable": bool(rho < 1.0),
                "max_queue": stats["max_queue"],
            })
        else:
            evaluations.append({
                "queue_id": queue_id,
                "active": False,
                "lambda": normalized[queue_id]["lambda"],
                "lambda_routed_sim": 0.0,
                "mu": normalized[queue_id]["mu"],
                "c": 1,
                "server_id": dedicated_server_id(queue_id),
                "arrivals": 0,
                "served": 0,
                "waiting": 0,
                "in_service": 0,
                "Wq": None,
                "rho": None,
                "stable": True,
                "max_queue": 0,
            })
    conserved = total_arrivals(lanes) == (
        sum(item["served"] for item in evaluations)
        + sum(item["waiting"] for item in evaluations)
        + sum(item["in_service"] for item in evaluations)
    )
    over_target = sorted(
        item["queue_id"] for item in evaluations if item["active"]
        and (item["rho"] is None or float(item["rho"]) > ceiling + _UTILIZATION_TOLERANCE)
    )
    # The run has already produced its trace by the time feasibility is decided, so
    # both verdicts carry it, as the continuous-day runner does. Dropping it on
    # INFEASIBLE left selected-plan playback with an empty floor for exactly the
    # busy periods the operator most needs to watch.
    trace_evidence = {"trace_events": trace, "trace_truncated": trace_truncated}
    if over_target:
        return {**base, "status": "INFEASIBLE",
                "reason": f"Simulated utilization exceeds the {ceiling:.0%} ceiling for: {', '.join(over_target)}.",
                "evaluations": evaluations, "total_cost": None, "total_lambda": total_lambda,
                "customer_conservation": conserved, "metric_provenance": "simulated",
                **trace_evidence}
    server_total = 0.0
    waiting_total = 0.0
    for item in evaluations:
        if not item["active"]:
            continue
        lane_cost = _segment_server_cost(normalized[item["queue_id"]], server_cost)
        server_total += lane_cost
        if item["served"] and item["Wq"] is not None:
            lane_wait = _compute_waiting_cost(
                item["served"] / horizon, item["Wq"], waiting_cost)
            waiting_total += lane_wait or 0.0
    return {**base, "status": "FEASIBLE", "reason": None,
            "evaluations": evaluations,
            "total_lambda": total_lambda,
            "total_cost": server_total + waiting_total,
            "server_cost": server_total, "waiting_cost": waiting_total,
            "customer_conservation": conserved,
            "metric_provenance": "simulated",
            "method": "conserved-arrival shortest-queue routing DES",
            "routing_rule": "shortest waiting count with configured-order ties",
            "seed": seed, "duration_hours": horizon,
            "demand_conserved": True,
            **trace_evidence}


def total_arrivals(lanes: dict) -> int:
    """Total routed arrivals across active lanes in a routing-DES run."""
    return sum(stats["arrivals"] for stats in lanes.values())


def _wall_minutes(value) -> float:
    """Wall-clock time to minutes since midnight (same precision as setup segments)."""
    parsed = datetime_time.fromisoformat(str(value))
    return parsed.hour * 60 + parsed.minute + parsed.second / 60


def des_day_start_minutes(queue_setup) -> float | None:
    """Earliest configured operating-segment start in minutes, if any.

    This persisted user-configured value is the authoritative simulation
    wall-clock origin for routing-DES runs: DES ``t = 0`` represents this
    operating-day start. Returns None when no segments are configured.
    """
    setup = queue_setup if isinstance(queue_setup, dict) else {}
    starts: list[float] = []
    for segment in setup.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        raw = segment.get("start_time")
        if raw is None:
            continue
        try:
            starts.append(_wall_minutes(raw))
        except ValueError:
            raise ValueError(
                f"Operating segment has an invalid start_time: {raw!r}.") from None
    return min(starts) if starts else None


def breaks_to_des_offsets(break_records, origin_minutes) -> list[dict]:
    """Convert persisted wall-clock breaks to routing-DES hour offsets.

    ``offset_hours = (break_start - origin) / 60`` on the same operating day;
    durations convert from minutes to hours. A break preceding the origin
    raises ValueError (no midnight wrap is defined); malformed records,
    unknown queues, and non-positive durations likewise raise.
    """
    if not isinstance(break_records, list):
        raise ValueError("Break schedule must be a list of break records.")
    if not _is_number(origin_minutes):
        raise ValueError("Break conversion requires a finite origin in minutes.")
    origin = float(origin_minutes)
    converted = []
    for entry in break_records:
        if not isinstance(entry, dict):
            raise ValueError("Break records must be dictionaries.")
        queue_id = entry.get("queue_id")
        if not isinstance(queue_id, str) or not queue_id:
            raise ValueError(f"Break records need a non-empty string queue ID, got {queue_id!r}.")
        raw_start = entry.get("scheduled_start_time")
        try:
            start_minutes = _wall_minutes(raw_start)
        except (ValueError, TypeError):
            raise ValueError(
                f"Break for {queue_id!r} has an invalid scheduled_start_time: {raw_start!r}.") from None
        duration = entry.get("duration_minutes")
        if not _is_number(duration) or float(duration) <= 0:
            raise ValueError(
                f"Break for {queue_id!r} needs a positive duration in minutes, got {duration!r}.")
        offset_minutes = start_minutes - origin
        if offset_minutes < 0:
            raise ValueError(
                f"Break for {queue_id!r} at {raw_start} precedes the operating-day start.")
        converted.append({"queue_id": queue_id, "start_hours": offset_minutes / 60.0,
                          "duration_hours": float(duration) / 60.0})
    return converted


def resolve_des_breaks(queue_setup) -> list[dict] | None:
    """Resolve persisted setup breaks to DES offsets, or None when none exist.

    Returns None without touching segments when no breaks are configured, so
    no-break behavior is unchanged. Raises ValueError with an exact reason
    when breaks exist but cannot be mapped (no origin segments, unknown
    queue, malformed record, or pre-origin break).
    """
    setup = queue_setup if isinstance(queue_setup, dict) else {}
    records = setup.get("breaks") or []
    if not records:
        return None
    configured = {str(queue_id) for queue_id in setup.get("queue_ids", [])}
    for entry in records:
        queue_id = entry.get("queue_id") if isinstance(entry, dict) else None
        if queue_id not in configured:
            raise ValueError(f"Break references unknown queue {queue_id!r}.")
    origin = des_day_start_minutes(setup)
    if origin is None:
        raise ValueError(
            "Separate-queue breaks require configured operating segments "
            "to anchor simulation time.")
    windows = [_segment_window(segment) for segment in setup.get("segments") or []
               if isinstance(segment, dict)]
    for entry in records:
        start = _break_start_minutes(entry)
        if start is not None and not any(low <= start < high for _, low, high in windows):
            raise ValueError(
                f"Break for {entry.get('queue_id')!r} at {entry.get('scheduled_start_time')} "
                "falls outside every configured operating segment.")
    return breaks_to_des_offsets(records, origin)


def _segment_window(segment: dict) -> tuple[str, float, float]:
    """(period key, start, end) of one configured segment in wall-clock minutes.

    The key matches the ``segment_id`` ingestion stamps on period rows: the
    configured id, else the ``HH:MM-HH:MM`` label of the interval.
    """
    low = _wall_minutes(segment.get("start_time"))
    high = _wall_minutes(segment.get("end_time"))
    key = segment.get("id") or (
        f"{int(low) // 60:02d}:{int(low) % 60:02d}-{int(high) // 60:02d}:{int(high) % 60:02d}")
    return str(key), low, high


def _break_start_minutes(entry) -> float | None:
    try:
        return _wall_minutes(entry.get("scheduled_start_time"))
    except (AttributeError, TypeError, ValueError):
        return None  # malformed records are rejected by breaks_to_des_offsets


def period_des_breaks(queue_setup, period_rows) -> list[dict] | None:
    """DES offsets for the breaks one period owns, or None when it owns none.

    A break belongs to exactly one period: the one whose operating segment
    contains its scheduled start. Other periods' runs never repeat it. Offsets
    use the same day origin as ``resolve_des_breaks``. Raises ValueError when
    breaks exist but the period cannot be mapped to a configured segment.
    """
    resolved = resolve_des_breaks(queue_setup)
    if resolved is None:
        return None
    setup = queue_setup if isinstance(queue_setup, dict) else {}
    segment_ids = {str(row.get("segment_id")) for row in period_rows or []
                   if isinstance(row, dict) and row.get("segment_id") is not None}
    windows = [_segment_window(segment) for segment in setup.get("segments") or []
               if isinstance(segment, dict)]
    matches = [(low, high) for key, low, high in windows if key in segment_ids]
    if len(matches) != 1:
        raise ValueError(
            "Cannot determine which operating segment owns this period's breaks "
            f"(segment ids: {sorted(segment_ids) or 'none'}).")
    low, high = matches[0]
    owned = []
    for entry in setup.get("breaks") or []:
        start = _break_start_minutes(entry)
        if start is not None and low <= start < high:
            owned.append(entry)
    if not owned:
        return None
    return breaks_to_des_offsets(owned, des_day_start_minutes(setup))


def _validate_breaks(breaks, active_ids) -> dict[str, list[tuple[float, float, float]]]:
    """Validate break records into per-queue sorted (cutoff, duration, scheduled start).

    Break times are absolute simulation-clock offsets in hours; durations are
    positive hour counts. The pre-break cutoff derives from the configured
    operational policy and is clamped at zero. Unknown queues, non-finite or
    negative starts, and non-positive durations raise ValueError.
    """
    if breaks is None:
        return {}
    if not isinstance(breaks, list):
        raise ValueError("Break schedule must be a list of break records.")
    known = set(active_ids or [])
    cutoff_delta = PRE_BREAK_CUTOFF_MINUTES / 60.0
    out: dict[str, list[tuple[float, float, float]]] = {}
    for entry in breaks:
        if not isinstance(entry, dict):
            raise ValueError("Break records must be dictionaries.")
        queue_id = entry.get("queue_id")
        start = entry.get("start_hours")
        duration = entry.get("duration_hours")
        if not isinstance(queue_id, str) or queue_id not in known:
            raise ValueError(f"Break references unknown queue {queue_id!r}.")
        if not _is_number(start) or float(start) < 0:
            raise ValueError(f"Break start must be a finite non-negative hour offset, got {start!r}.")
        if not _is_number(duration) or float(duration) <= 0:
            raise ValueError(f"Break duration must be a finite positive hour count, got {duration!r}.")
        cutoff = max(0.0, float(start) - cutoff_delta)
        out.setdefault(queue_id, []).append((cutoff, float(duration), float(start)))
    for queue_id in out:
        out[queue_id].sort()
    return out


def _paired_stream_seeds(seed: int | None) -> tuple[int | None, int | None, int | None]:
    """Derive the (arrivals, service, ties) stream seeds from one run seed.

    Common random numbers: ``random.Random(seed)`` yields three 64-bit seeds
    in that fixed order, so schedules run with the same seed share arrival
    gaps, per-customer service quantiles, and tie draws independently of one
    another. ``seed=None`` stays non-deterministic (each stream OS-seeded).
    """
    if seed is None:
        return None, None, None
    master = random.Random(seed)
    return master.getrandbits(64), master.getrandbits(64), master.getrandbits(64)


def _paired_streams(seed: int | None) -> tuple[random.Random, random.Random, random.Random]:
    arrivals, service, ties = _paired_stream_seeds(seed)
    return random.Random(arrivals), random.Random(service), random.Random(ties)


def _service_at_quantile(samples: list[float], quantile: float) -> float:
    """Empirical service time at a customer's uniform draw (uniform over samples)."""
    return samples[min(int(quantile * len(samples)), len(samples) - 1)]


def _run_routing_des(*, active_ids, tie_order, samples_by_id, total_lambda,
                     duration_hours, seed, time_label, max_events, breaks=None
                     ) -> tuple[dict, list[dict], bool, dict]:
    """Run one conserved-arrival routing DES over a static active-lane set.

    One Poisson stream carries the conserved total demand; each arrival is
    routed by ``route_arrival`` over live system sizes (waiting plus
    in-service, the standard join-the-shortest-queue observation: waiting
    counts alone cannot see a busy server, so ties would collapse to
    configured order and starve later lanes) and served from the chosen
    lane's own empirical samples (``rng.choice``, matching the Current-state
    parallel DES convention). Queues start empty; the run ends at the horizon
    with leftovers counted, never dropped. Event records reuse the engine
    trace schema so playback stays compatible.

    Optional ``breaks`` maps configured per-lane breaks (absolute
    simulation-clock hour offsets) onto the lifecycle: at scheduled start
    minus the configured pre-break cutoff a lane enters DRAINING and stops
    receiving new arrivals while its existing customers finish in place;
    once empty it takes its full configured break (ON_BREAK) measured from
    the actual start, then returns to ACTIVE. Only ACTIVE lanes receive new
    arrivals; arrivals admitted while no lane is eligible wait for the next
    eligibility change instead of being dropped or rerouted.
    """
    by_queue_breaks = _validate_breaks(breaks, active_ids)
    env = simpy.Environment()
    resources = {queue_id: simpy.Resource(env, capacity=1) for queue_id in active_ids}
    lifecycles = {
        queue_id: DedicatedQueueLifecycle(queue_id, dedicated_server_id(queue_id))
        for queue_id in active_ids
    }
    # Independent streams: arrival gaps, one service quantile per admitted
    # customer (by arrival order), and routing ties (common random numbers).
    arrival_rng, service_rng, tie_rng = _paired_streams(seed)
    stats = {
        queue_id: {"arrivals": 0, "served": 0, "wait_sum": 0.0,
                   "busy_time": 0.0, "max_queue": 0, "lifecycle": lifecycles[queue_id],
                   "breaks": []}
        for queue_id in active_ids
    }
    trace: list[dict] = []
    truncated = False
    topology_changed = env.event()
    pending_completion: dict[str, Any] = {queue_id: None for queue_id in active_ids}

    def record(at, event_type, customer_id, server_id, queue_len_after, queue_id,
               service_time_hours=None) -> None:
        nonlocal truncated
        if len(trace) >= max_events:
            truncated = True
            return
        event = {
            "t": round(at, 6),
            "type": event_type,
            "segment_id": time_label,
            "customer_id": customer_id,
            "server_id": server_id,
            "queue_len_after": queue_len_after,
            "queue_id": queue_id,
        }
        if service_time_hours is not None:
            event["service_time_hours"] = round(service_time_hours, 12)
        trace.append(event)

    customer_counter = 0
    admitted = 0

    def _signal_topology() -> None:
        nonlocal topology_changed
        if not topology_changed.triggered:
            topology_changed.succeed()
        topology_changed = env.event()

    def _eligible_ids() -> list[str]:
        return [queue_id for queue_id in active_ids
                if lifecycles[queue_id].accepts_arrivals]

    def customer_process(queue_id, customer_id, arrival, quantile):
        lifecycle = lifecycles[queue_id]
        row = stats[queue_id]
        row["arrivals"] += 1
        row["max_queue"] = max(row["max_queue"], len(lifecycle.waiting_customer_ids))
        record(env.now, "arrival", customer_id, None,
               len(lifecycle.waiting_customer_ids), queue_id)
        with resources[queue_id].request() as request:
            yield request
            lifecycle.begin_service()
            service_start = env.now
            row["wait_sum"] += service_start - arrival
            record(env.now, "service_start", customer_id, lifecycle.server_id,
                   len(lifecycle.waiting_customer_ids), queue_id)
            service_time = _service_at_quantile(samples_by_id[queue_id], quantile)
            yield env.timeout(service_time)
            row["busy_time"] += max(0.0, min(env.now, duration_hours) - service_start)
            lifecycle.complete_service()
            row["served"] += 1
            record(env.now, "service_end", customer_id, lifecycle.server_id,
                   len(lifecycle.waiting_customer_ids), queue_id, service_time)
            waiter = pending_completion.get(queue_id)
            if waiter is not None and not waiter.triggered:
                waiter.succeed()

    def break_controller(queue_id):
        lifecycle = lifecycles[queue_id]
        for cutoff, duration, scheduled in by_queue_breaks.get(queue_id, []):
            if env.now < cutoff:
                yield env.timeout(cutoff - env.now)
            if lifecycle.state == DedicatedQueueState.ACTIVE:
                lifecycle.begin_draining()
                record(env.now, "draining_start", None, lifecycle.server_id,
                       len(lifecycle.waiting_customer_ids), queue_id)
            _signal_topology()
            while lifecycle.waiting_customer_ids or lifecycle.in_service_customer_id is not None:
                waiter = env.event()
                pending_completion[queue_id] = waiter
                yield waiter
            actual_start = env.now
            stats[queue_id]["breaks"].append({
                "queue_id": queue_id,
                "scheduled_start": scheduled,
                "cutoff": cutoff,
                "actual_start": actual_start,
                "actual_end": None,
                "duration_hours": duration,
            })
            lifecycle.begin_break()
            record(env.now, "break_start", None, lifecycle.server_id,
                   len(lifecycle.waiting_customer_ids), queue_id)
            _signal_topology()
            yield env.timeout(duration)
            lifecycle.end_break()
            stats[queue_id]["breaks"][-1]["actual_end"] = env.now
            record(env.now, "break_end", None, lifecycle.server_id,
                   len(lifecycle.waiting_customer_ids), queue_id)
            _signal_topology()

    def arrival_process():
        nonlocal customer_counter, admitted
        while env.now < duration_hours:
            if total_lambda <= 0:
                break
            interval = arrival_rng.expovariate(total_lambda)
            if env.now + interval >= duration_hours:
                break
            yield env.timeout(interval)
            admitted += 1
            quantile = service_rng.random()
            eligible = _eligible_ids()
            while not eligible:
                yield topology_changed
                eligible = _eligible_ids()
            system_sizes = {
                queue_id: len(lifecycles[queue_id].waiting_customer_ids)
                + (1 if lifecycles[queue_id].in_service_customer_id is not None else 0)
                for queue_id in eligible
            }
            chosen = route_arrival(eligible, system_sizes, tie_order, tie_rng)
            customer_counter += 1
            lifecycles[chosen].enqueue(str(customer_counter))
            env.process(customer_process(chosen, customer_counter, env.now, quantile))

    for queue_id in active_ids:
        if queue_id in by_queue_breaks:
            env.process(break_controller(queue_id))
    env.process(arrival_process())
    env.run(until=duration_hours)
    routed = total_arrivals(stats)
    return stats, trace, truncated, {"admitted": admitted, "unrouted_at_horizon": admitted - routed}


def run_routing_day_des(periods: list[dict], *, tie_order: list[str], seed: int | None,
                        max_events: int, breaks: list[dict] | None = None) -> dict:
    """Run one continuous operating day of the Separate routing DES.

    ``periods`` are consecutive windows on the DES clock (``start_hours`` /
    ``end_hours`` from the operating-day origin), each with its scheduled
    ``active_queue_ids`` and per-lane rows (``lambda``, empirical
    ``service_samples_hours``). Within a window one Poisson stream at the
    window's total rate is routed by ``route_arrival`` over ACTIVE lanes
    (same live-system-size rule and seeded ties as ``_run_routing_des``);
    each customer is served by its own lane from that lane's samples for the
    customer's arrival window. At window boundaries lanes open or close per
    the schedule through ``DedicatedQueueLifecycle`` (a closing lane stops
    taking arrivals and finishes its own queue in place). Breaks (absolute
    DES offsets) use the same DRAINING -> ON_BREAK -> ACTIVE lifecycle and
    carry across boundaries. Arrivals stop at the day end; service continues
    until every admitted customer is served. Metrics are attributed to the
    customer's arrival window.
    """
    if not periods:
        raise ValueError("A day simulation needs at least one period.")
    windows = sorted(periods, key=lambda p: float(p["start_hours"]))
    lanes = list(tie_order)
    samples: dict[tuple[str, str], list[float]] = {}
    for window in windows:
        for queue_id in window["active_queue_ids"]:
            if queue_id not in lanes:
                raise ValueError(f"Period {window['time']} schedules unknown lane {queue_id!r}.")
            row = (window.get("queues_by_id") or {}).get(queue_id)
            clean = _validated_samples(row) if isinstance(row, dict) else None
            if clean is None:
                raise ValueError(
                    f"Lane {queue_id!r} has no empirical service samples for period {window['time']}.")
            samples[(window["time"], queue_id)] = clean
    by_queue_breaks = _validate_breaks(breaks, lanes)
    env = simpy.Environment()
    # Independent streams (common random numbers), as in ``_run_routing_des``.
    arrival_rng, service_rng, tie_rng = _paired_streams(seed)
    resources = {q: simpy.Resource(env, capacity=1) for q in lanes}
    lifecycles = {q: DedicatedQueueLifecycle(q, dedicated_server_id(q)) for q in lanes}
    first_active = set(windows[0]["active_queue_ids"])
    for queue_id, lifecycle in lifecycles.items():
        if queue_id not in first_active:
            lifecycle.state = DedicatedQueueState.INACTIVE
    scheduled = {"active": first_active}
    day_end = float(windows[-1]["end_hours"])
    stats = {(w["time"], q): {"arrivals": 0, "served": 0, "wait_sum": 0.0, "busy_time": 0.0,
                              "max_queue": 0}
             for w in windows for q in lanes}
    trace: list[dict] = []
    truncated = False
    topology_changed = env.event()
    pending_completion: dict[str, Any] = {q: None for q in lanes}
    counters = {"customer": 0, "admitted": 0, "served": 0}
    current_label = {"time": windows[0]["time"]}

    def record(event_type, customer_id, queue_id, label, service_time_hours=None) -> None:
        nonlocal truncated
        if len(trace) >= max_events:
            truncated = True
            return
        lifecycle = lifecycles[queue_id]
        event = {"t": round(env.now, 6), "type": event_type, "segment_id": label,
                 "customer_id": customer_id,
                 "server_id": lifecycle.server_id if event_type != "arrival" else None,
                 "queue_len_after": len(lifecycle.waiting_customer_ids), "queue_id": queue_id}
        if service_time_hours is not None:
            event["service_time_hours"] = round(service_time_hours, 12)
        trace.append(event)

    def signal() -> None:
        nonlocal topology_changed
        if not topology_changed.triggered:
            topology_changed.succeed()
        topology_changed = env.event()

    def add_busy(queue_id: str, start: float, end: float) -> None:
        # Busy time is credited to the window in which it occurs.
        for window in windows:
            lo, hi = float(window["start_hours"]), float(window["end_hours"])
            overlap = min(end, hi) - max(start, lo)
            if overlap > 0:
                stats[(window["time"], queue_id)]["busy_time"] += overlap

    def apply_schedule(queue_id: str) -> None:
        lifecycle = lifecycles[queue_id]
        if lifecycle.break_pending or lifecycle.state == DedicatedQueueState.ON_BREAK:
            return  # the break controller re-applies the schedule when the rest ends
        try:
            lifecycle.transition_for_segment(queue_id in scheduled["active"])
        except QueueReactivationPolicyError as exc:
            raise ValueError(str(exc)) from None

    def customer_process(queue_id, customer_id, arrival, label, quantile):
        lifecycle = lifecycles[queue_id]
        row = stats[(label, queue_id)]
        row["arrivals"] += 1
        row["max_queue"] = max(row["max_queue"], len(lifecycle.waiting_customer_ids))
        record("arrival", customer_id, queue_id, label)
        with resources[queue_id].request() as request:
            yield request
            lifecycle.begin_service()
            start = env.now
            row["wait_sum"] += start - arrival
            record("service_start", customer_id, queue_id, label)
            service_time = _service_at_quantile(samples[(label, queue_id)], quantile)
            yield env.timeout(service_time)
            add_busy(queue_id, start, env.now)
            lifecycle.complete_service()
            row["served"] += 1
            counters["served"] += 1
            record("service_end", customer_id, queue_id, label, service_time)
            if lifecycle.state == DedicatedQueueState.INACTIVE:
                signal()
            waiter = pending_completion.get(queue_id)
            if waiter is not None and not waiter.triggered:
                waiter.succeed()

    def schedule_controller():
        for window in windows[1:]:
            yield env.timeout(float(window["start_hours"]) - env.now)
            current_label["time"] = window["time"]
            scheduled["active"] = set(window["active_queue_ids"])
            for queue_id in lanes:
                apply_schedule(queue_id)
            signal()

    def break_controller(queue_id):
        lifecycle = lifecycles[queue_id]
        for cutoff, duration, _scheduled in by_queue_breaks.get(queue_id, []):
            if env.now < cutoff:
                yield env.timeout(cutoff - env.now)
            if lifecycle.state == DedicatedQueueState.INACTIVE:
                continue  # lane is off shift: nothing to take a break from
            if lifecycle.state == DedicatedQueueState.ACTIVE:
                lifecycle.begin_draining()
                record("draining_start", None, queue_id, current_label["time"])
            signal()
            while lifecycle.waiting_customer_ids or lifecycle.in_service_customer_id is not None:
                waiter = env.event()
                pending_completion[queue_id] = waiter
                yield waiter
            lifecycle.begin_break()
            record("break_start", None, queue_id, current_label["time"])
            signal()
            yield env.timeout(duration)
            lifecycle.end_break()
            record("break_end", None, queue_id, current_label["time"])
            apply_schedule(queue_id)
            signal()

    def arrival_process():
        for window in windows:
            label, end = window["time"], float(window["end_hours"])
            if env.now < float(window["start_hours"]):
                yield env.timeout(float(window["start_hours"]) - env.now)
            rate = sum(float((window["queues_by_id"].get(q) or {}).get("lambda") or 0.0)
                       for q in window["active_queue_ids"])
            # A customer may wait for an open lane past the window end; the
            # next window then starts from the current clock.
            while rate > 0 and env.now < end:
                interval = arrival_rng.expovariate(rate)
                if env.now + interval >= end:
                    yield env.timeout(end - env.now)
                    break
                yield env.timeout(interval)
                counters["admitted"] += 1
                quantile = service_rng.random()
                arrival = env.now
                eligible = [q for q in lanes if lifecycles[q].accepts_arrivals]
                while not eligible:
                    yield topology_changed
                    eligible = [q for q in lanes if lifecycles[q].accepts_arrivals]
                sizes = {q: len(lifecycles[q].waiting_customer_ids)
                         + (1 if lifecycles[q].in_service_customer_id is not None else 0)
                         for q in eligible}
                chosen = route_arrival(eligible, sizes, lanes, tie_rng)
                if (label, chosen) not in samples:
                    raise ValueError(
                        f"A customer arriving in period {label} waited for an open lane and "
                        f"reached lane {chosen!r}, which has no service samples for {label}.")
                counters["customer"] += 1
                lifecycles[chosen].enqueue(str(counters["customer"]))
                env.process(customer_process(chosen, counters["customer"], arrival, label, quantile))

    env.process(schedule_controller())
    for queue_id in lanes:
        if queue_id in by_queue_breaks:
            env.process(break_controller(queue_id))
    env.process(arrival_process())
    env.run(until=day_end + 24.0)
    conserved = counters["served"] == counters["admitted"]
    period_out = []
    for window in windows:
        duration = float(window["end_hours"]) - float(window["start_hours"])
        lane_rows = []
        for queue_id in lanes:
            row = stats[(window["time"], queue_id)]
            lane_rows.append({
                "queue_id": queue_id,
                "server_id": dedicated_server_id(queue_id),
                "active": queue_id in window["active_queue_ids"],
                "lambda": (window["queues_by_id"].get(queue_id) or {}).get("lambda"),
                "arrivals": row["arrivals"],
                "served": row["served"],
                "lambda_routed_sim": row["arrivals"] / duration if duration > 0 else None,
                "Wq": row["wait_sum"] / row["served"] if row["served"] else None,
                "rho": row["busy_time"] / duration if duration > 0 else None,
                "max_queue": row["max_queue"],
            })
        period_out.append({"time": window["time"], "start_hours": float(window["start_hours"]),
                           "duration_hours": duration, "lanes": lane_rows})
    return {"periods": period_out, "trace_events": trace, "trace_truncated": truncated,
            "admitted": counters["admitted"], "served": counters["served"],
            "customer_conservation": conserved, "day_hours": day_end - float(windows[0]["start_hours"])}


def index_period_queues(records: list, time_label: str) -> dict[str, dict]:
    """Index one period's queue rows by queue ID in persisted order.

    Mirrors the optimizer's per-period resolution rule (later rows overwrite
    earlier ones for the same queue) so selected-plan simulation models
    identical demand from identical evidence.
    """
    indexed: dict[str, dict] = {}
    for row in records or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("time", row.get("segment_id", "Unknown")))
        queue_id = row.get("queue_id")
        if label == time_label and isinstance(queue_id, str) and queue_id:
            indexed[queue_id] = row
    return indexed


def _summarize_metric(values: list) -> dict | None:
    """Aggregate one continuous metric across replications.

    Returns mean, sample standard deviation, standard error, Student-t 95 %
    interval, and contributing count — or None when no replication produced
    a value. Missing stays missing: never zero-filled. Single-replication
    summaries carry a mean but no dispersion or interval.
    """
    present = [float(value) for value in values if _is_number(value)]
    count = len(present)
    if count == 0:
        return None
    mean = math.fsum(present) / count
    if count < 2:
        return {"mean": mean, "sd": None, "se": None,
                "ci_lower": None, "ci_upper": None, "n": 1}
    sd = statistics.stdev(present)
    se = sd / math.sqrt(count)
    half_width = float(student_t.ppf(0.975, count - 1)) * se
    return {"mean": mean, "sd": sd, "se": se,
            "ci_lower": mean - half_width, "ci_upper": mean + half_width,
            "n": count}


def _aggregate_shell(candidate: dict, config: dict, status: str, reason) -> dict:
    """Minimal aggregate result for non-evidence outcomes."""
    return {
        "time": candidate.get("time", "segment"),
        "available_queue_ids": list(candidate.get("available_queue_ids") or []),
        "active_queue_ids": list(candidate.get("active_queue_ids") or []),
        "inactive_queue_ids": list(candidate.get("inactive_queue_ids") or []),
        "status": status,
        "reason": reason,
        "rankable": False,
        "evaluation_method": "DES_REPLICATIONS",
        "replication_count": config["replications"],
        "base_seed": config["base_seed"],
        "replication_seeds": replication_seeds(config["base_seed"], config["replications"]),
        "duration_hours": config["duration_hours"],
        "target_utilization": config["target"],
        "metric_source": "SIMULATED",
        "all_replications_conserved": None,
    }


def evaluate_candidate_with_des_replications(candidate: dict, queues_by_id: dict,
                                             config: dict | None = None,
                                             *, run_fn=None) -> dict:
    """Aggregate N controlled routing-DES replications into candidate evidence.

    Each replication calls the single-run evaluator (``run_fn``, defaulting
    to ``evaluate_candidate_with_des``) with the next seed of the deterministic
    schedule; DES internals are never duplicated here. INVALID_INPUT or
    UNSUPPORTED in any replication propagates to the aggregate instead of
    being averaged away, as does any demand-conservation violation. Verdict
    strings are not voted on: continuous metrics are aggregated first, and
    the final optimizer feasibility rule stays deferred (``feasibility``
    carries FEASIBILITY_POLICY_REQUIRED) until an aggregate utilization
    statistic is approved.
    """
    try:
        settings = validate_des_replication_config(config)
    except ValueError as exc:
        fallback = {"replications": 0, "base_seed": None, "duration_hours": None, "target": None}
        shell = _aggregate_shell(candidate if isinstance(candidate, dict) else {},
                                 {**fallback, "replications": 0}, "INVALID_INPUT", str(exc))
        shell["replication_seeds"] = []
        return shell
    runner = evaluate_candidate_with_des if run_fn is None else run_fn
    seeds = replication_seeds(settings["base_seed"], settings["replications"])
    runs: list[dict] = []
    for index, seed in enumerate(seeds):
        try:
            runs.append(runner(
                candidate, queues_by_id, duration_hours=settings["duration_hours"],
                seed=seed, target=settings["target"],
                server_cost=settings["server_cost"], waiting_cost=settings["waiting_cost"],
                max_events=settings["max_events"]))
        except Exception as exc:
            shell = _aggregate_shell(candidate, settings, "AGGREGATION_ERROR",
                                     f"Replication {index} (seed {seed}) raised {type(exc).__name__}: {exc}")
            shell["replication_seeds"] = seeds
            return shell
    for index, run in enumerate(runs):
        if run.get("status") == "INVALID_INPUT":
            shell = _aggregate_shell(candidate, settings, "INVALID_INPUT",
                                     f"Replication {index} (seed {seeds[index]}) returned INVALID_INPUT: "
                                     f"{run.get('reason')}")
            shell["replication_seeds"] = seeds
            return shell
    for index, run in enumerate(runs):
        if run.get("status") == "UNSUPPORTED":
            shell = _aggregate_shell(candidate, settings, "UNSUPPORTED",
                                     f"Replication {index} (seed {seeds[index]}) returned UNSUPPORTED: "
                                     f"{run.get('reason')}")
            shell["replication_seeds"] = seeds
            return shell
    for index, run in enumerate(runs):
        if run.get("status") not in ("FEASIBLE", "INFEASIBLE"):
            shell = _aggregate_shell(candidate, settings, "AGGREGATION_ERROR",
                                     f"Replication {index} (seed {seeds[index]}) returned "
                                     f"unexpected status {run.get('status')!r}.")
            shell["replication_seeds"] = seeds
            return shell
    bad = [index for index, run in enumerate(runs)
           if run.get("customer_conservation") is not True]
    if bad:
        shell = _aggregate_shell(candidate, settings, "AGGREGATION_ERROR",
                                 "Demand conservation violated in replication(s) "
                                 + ", ".join(f"{index} (seed {seeds[index]})" for index in bad)
                                 + "; candidate evidence is not rankable.")
        shell["replication_seeds"] = seeds
        shell["all_replications_conserved"] = False
        return shell
    active = list(candidate.get("active_queue_ids") or [])
    by_rep_lane = []
    for run in runs:
        lanes = {item["queue_id"]: item for item in (run.get("evaluations") or [])
                 if isinstance(item, dict) and item.get("active")}
        by_rep_lane.append(lanes)
    per_lane = []
    for queue_id in active:
        per_lane.append({
            "queue_id": queue_id,
            "active": True,
            "utilization": _summarize_metric([lanes.get(queue_id, {}).get("rho") for lanes in by_rep_lane]),
            "arrivals": _summarize_metric([lanes.get(queue_id, {}).get("arrivals") for lanes in by_rep_lane]),
            "served": _summarize_metric([lanes.get(queue_id, {}).get("served") for lanes in by_rep_lane]),
            "waiting_end": _summarize_metric([lanes.get(queue_id, {}).get("waiting") for lanes in by_rep_lane]),
            "Wq": _summarize_metric([lanes.get(queue_id, {}).get("Wq") for lanes in by_rep_lane]),
        })
    for queue_id in (candidate.get("inactive_queue_ids") or []):
        per_lane.append({"queue_id": queue_id, "active": False, "utilization": None,
                         "arrivals": None, "served": None, "waiting_end": None, "Wq": None})
    rep_waits = []
    for lanes in by_rep_lane:
        weighted = [(lanes[qid]["served"], lanes[qid]["Wq"]) for qid in active
                    if qid in lanes and _is_number(lanes[qid].get("served"))
                    and lanes[qid]["served"] > 0 and _is_number(lanes[qid].get("Wq"))]
        served_total = math.fsum(served for served, _ in weighted)
        rep_waits.append(math.fsum(served * wq for served, wq in weighted) / served_total
                         if served_total > 0 else None)
    rep_arrivals = [math.fsum(lanes[qid]["arrivals"] for qid in active if qid in lanes
                              and _is_number(lanes[qid].get("arrivals")))
                    for lanes in by_rep_lane]
    rep_served = [math.fsum(lanes[qid]["served"] for qid in active if qid in lanes
                            and _is_number(lanes[qid].get("served")))
                  for lanes in by_rep_lane]
    lane_means = [lane["utilization"]["mean"] for lane in per_lane
                  if lane["active"] and lane["utilization"] is not None]
    first_trace = runs[0]
    return {
        "time": candidate.get("time", "segment"),
        "available_queue_ids": list(candidate.get("available_queue_ids") or []),
        "active_queue_ids": list(active),
        "inactive_queue_ids": list(candidate.get("inactive_queue_ids") or []),
        "status": "VALID_AGGREGATE_EVIDENCE",
        "reason": None,
        "rankable": True,
        "evaluation_method": "DES_REPLICATIONS",
        "replication_count": len(runs),
        "base_seed": settings["base_seed"],
        "replication_seeds": seeds,
        "duration_hours": settings["duration_hours"],
        "target_utilization": settings["target"],
        "metric_source": "SIMULATED",
        "routing_policy": "shortest system size with seeded fair ties",
        "service_sampling_method": "empirical per-lane resampling",
        "arrival_method": "single conserved Poisson stream at total lambda",
        "all_replications_conserved": True,
        "demand_conserved": True,
        "total_lambda": runs[0].get("total_lambda"),
        "per_lane": per_lane,
        "waiting_time": _summarize_metric(rep_waits),
        "max_mean_lane_utilization": max(lane_means) if lane_means else None,
        "costs": {
            "staffing": _summarize_metric([run.get("server_cost") for run in runs]),
            "waiting": _summarize_metric([run.get("waiting_cost") for run in runs]),
            "abandonment": None,
            "total": _summarize_metric([run.get("total_cost") for run in runs]),
        },
        "arrivals": _summarize_metric(rep_arrivals),
        "served": _summarize_metric(rep_served),
        "abandoned": None,
        "feasibility": {
            "policy": "FEASIBILITY_POLICY_REQUIRED",
            "reason": ("No aggregate utilization statistic is approved yet for the "
                       "utilization <= target rule; metrics are reported without an "
                       "optimizer feasibility verdict."),
            "target_utilization": settings["target"],
        },
        "representative_trace": {
            "replication": 0,
            "seed": seeds[0],
            "events": first_trace.get("trace_events"),
            "truncated": first_trace.get("trace_truncated"),
        },
    }


def apply_des_aggregate_feasibility(aggregate: dict, target: float | None = None) -> dict:
    """Classify aggregated DES candidate evidence without rerunning DES.

    The utilization ceiling applies to the most heavily utilized ACTIVE
    lane: FEASIBLE iff max mean active-lane utilization <= target (existing
    1e-12 tolerance). Uncertainty bands stay informational and never
    redefine the constraint. Non-evidence states (INVALID_INPUT,
    UNSUPPORTED, AGGREGATION_ERROR) pass through unchanged, never converted
    into INFEASIBLE.

    ``near_target_noise`` only annotates a FEASIBLE result: True when a peak
    lane's utilization interval reaches past the target, False when every
    peak lane's interval stays within it, None when any peak lane has no
    interval (never guessed) and for every non-FEASIBLE result.
    """
    status = aggregate.get("status") if isinstance(aggregate, dict) else None
    if status in ("INVALID_INPUT", "UNSUPPORTED", "AGGREGATION_ERROR"):
        return dict(aggregate)
    if status != "VALID_AGGREGATE_EVIDENCE":
        return {"status": "AGGREGATION_ERROR",
                "reason": f"Cannot classify aggregate with status {status!r}.",
                "candidate_utilization": None, "max_lane_ids": []}
    raw_target = aggregate.get("target_utilization") if target is None else target
    try:
        ceiling = validate_separate_target(raw_target)
    except ValueError as exc:
        return {"status": "AGGREGATION_ERROR", "reason": str(exc),
                "candidate_utilization": None, "max_lane_ids": []}
    means: dict[str, float] = {}
    uppers: dict[str, Any] = {}
    for lane in aggregate.get("per_lane") or []:
        if not isinstance(lane, dict) or not lane.get("active"):
            continue
        utilization = lane.get("utilization") or {}
        mean = utilization.get("mean")
        queue_id = lane.get("queue_id")
        if _is_number(mean) and isinstance(queue_id, str):
            means[queue_id] = float(mean)
            uppers[queue_id] = utilization.get("ci_upper")
    if not means:
        return {"status": "UNSUPPORTED",
                "reason": "No mean active-lane utilization evidence to classify.",
                "candidate_utilization": None, "max_lane_ids": []}
    peak = max(means.values())
    peak_lanes = sorted(qid for qid, mean in means.items() if mean == peak)
    classified = {"candidate_utilization": peak, "max_lane_ids": peak_lanes,
                  "target_utilization": ceiling, "near_target_noise": None}
    if peak <= ceiling + _UTILIZATION_TOLERANCE:
        known = [float(upper) for qid in peak_lanes
                 if _is_number(upper := uppers.get(qid))]
        if len(known) == len(peak_lanes):
            classified["near_target_noise"] = any(
                upper > ceiling + _UTILIZATION_TOLERANCE for upper in known)
        return {**classified, "status": "FEASIBLE", "reason": None}
    violators = sorted(qid for qid, mean in means.items()
                       if mean > ceiling + _UTILIZATION_TOLERANCE)
    return {**classified, "status": "INFEASIBLE",
            "reason": (f"Max mean active-lane utilization {peak:.2%} exceeds the "
                       f"{ceiling:.0%} target for: {', '.join(violators)}.")}


def rank_des_candidates(entries: list) -> list:
    """Order classified DES candidates best-first without rerunning DES.

    Only FEASIBLE candidates with a numeric mean total cost participate,
    ordered by lowest mean cost with ties resolving to fewer lanes (the
    existing foundation tie rule, exact tuple ordering, no indifference
    bands). Mixed evaluation methods raise ValueError: one ranking must
    never compare analytical and simulated objectives as identical evidence.
    """
    methods = {entry.get("evaluation_method") for entry in entries
               if isinstance(entry, dict)}
    if methods - {"DES_REPLICATIONS"}:
        raise ValueError("DES ranking requires every candidate to use DES_REPLICATIONS evidence.")
    eligible = [entry for entry in entries
                if entry.get("status") == "FEASIBLE"
                and _is_number(entry.get("mean_total_cost"))]
    return sorted(eligible, key=lambda entry: (entry["mean_total_cost"],
                                               entry["active_lane_count"]))


def check_des_search_complete(entries: list) -> dict:
    """A search is complete only when every candidate evaluated to FEASIBLE
    or INFEASIBLE. Anything else (UNSUPPORTED, INVALID_INPUT,
    AGGREGATION_ERROR) leaves the required search space incomplete, and no
    global optimum may be claimed."""
    offenders = sorted(str(entry.get("active_lane_count")) for entry in entries
                       if entry.get("status") not in ("FEASIBLE", "INFEASIBLE"))
    if offenders:
        return {"complete": False,
                "reason": ("Incomplete candidate search: lane count(s) "
                           + ", ".join(offenders) + " lack valid evaluation.")}
    return {"complete": True, "reason": None}


def _optimize_separate_des(time_label, available, by_id, counts, *, ceiling,
                           current_active, server_cost, waiting_cost,
                           des_settings, run_fn, breaks=None) -> dict:
    """Routing-capable optimization over a complete DES-evaluated search.

    Every candidate (including full-active) uses DES_REPLICATIONS evidence so
    one ranking never mixes analytical and simulated objectives. OPTIMAL here
    means the lowest estimated (mean replicated) total cost among FEASIBLE
    candidates over a complete search — a simulation estimate, not an exact
    quantity. Any unevaluated candidate blocks the optimum claim.
    """
    candidates = []
    for spec in counts:
        candidate = {"time": time_label, "available_queue_ids": available,
                     "active_queue_ids": spec["active_queue_ids"],
                     "inactive_queue_ids": spec["inactive_queue_ids"]}
        if breaks is not None:
            candidate["breaks"] = breaks
        aggregate = evaluate_candidate_with_des_replications(
            candidate, by_id, des_settings, run_fn=run_fn)
        classified = apply_des_aggregate_feasibility(aggregate)
        costs = aggregate.get("costs") or {}
        total = costs.get("total") or {}
        candidates.append({
            "time": time_label,
            "available_queue_ids": list(available),
            "active_queue_ids": list(spec["active_queue_ids"]),
            "inactive_queue_ids": list(spec["inactive_queue_ids"]),
            "target_utilization": ceiling,
            "active_lane_count": len(spec["active_queue_ids"]),
            "evaluation_method": "DES_REPLICATIONS",
            "status": classified.get("status"),
            "reason": classified.get("reason"),
            "candidate_utilization": classified.get("candidate_utilization"),
            "max_lane_ids": classified.get("max_lane_ids"),
            "near_target_noise": classified.get("near_target_noise"),
            "total_cost": total.get("mean"),
            "mean_total_cost": total.get("mean"),
            "server_cost": (costs.get("staffing") or {}).get("mean"),
            "waiting_cost": (costs.get("waiting") or {}).get("mean"),
            "cost_uncertainty": {key: total.get(key)
                                 for key in ("sd", "se", "ci_lower", "ci_upper", "n")},
            "evidence": aggregate,
        })
    provenance = {
        "evaluation_method": "DES_REPLICATIONS",
        "replication_count": des_settings["replications"],
        "base_seed": des_settings["base_seed"],
        "replication_seeds": replication_seeds(des_settings["base_seed"],
                                               des_settings["replications"]),
    }
    completeness = check_des_search_complete(candidates)
    if not completeness["complete"]:
        if any(candidate["status"] == "INVALID_INPUT" for candidate in candidates):
            overall, reason = "INVALID_INPUT", "Candidate inputs failed validation."
        else:
            overall, reason = ("UNSUPPORTED",
                               "Complete candidate search cannot be evaluated with available "
                               "evidence. " + (completeness["reason"] or ""))
        return {"time": time_label, "target_utilization": ceiling, "overall": overall,
                "reason": reason, "candidates": candidates, "optimum": None, **provenance}
    ranking = rank_des_candidates(candidates)
    if not ranking:
        return {"time": time_label, "target_utilization": ceiling, "overall": "INFEASIBLE",
                "reason": "No candidate satisfies stability and utilization constraints.",
                "candidates": candidates, "optimum": None, **provenance}
    best = ranking[0]
    if current_active is None:
        recommendation = None
    elif best["active_lane_count"] > current_active:
        recommendation = "INCREASE"
    elif best["active_lane_count"] < current_active:
        recommendation = "REDUCE"
    else:
        recommendation = "KEEP"
    return {"time": time_label, "target_utilization": ceiling, "overall": "OPTIMAL",
            "reason": None, "candidates": candidates,
            "optimum": {**best, "recommendation": recommendation,
                        "estimated_optimal": True},
            **provenance}


def _period_current_active(queue_setup: dict, period_rows: list) -> list[str] | None:
    """Current active lanes for one period from authoritative setup metadata.

    Non-varying setups always run every configured lane. Varying setups
    resolve through the scheduled segment matching the rows' segment_id;
    unmappable periods yield None (unknown, never fabricated).
    """
    setup = queue_setup if isinstance(queue_setup, dict) else {}
    configured = [str(queue_id) for queue_id in (setup.get("queue_ids") or [])]
    segments = [s for s in (setup.get("segments") or []) if isinstance(s, dict)]
    seg_ids = {str(row.get("segment_id")) for row in period_rows
               if isinstance(row, dict) and row.get("segment_id") is not None}
    match = next((s for s in segments if str(s.get("id")) in seg_ids), None)
    if match is not None:
        try:
            active = scheduled_active_queue_ids(setup, match)
        except ValueError:
            return None
        return [queue_id for queue_id in configured if queue_id in active]
    if setup.get("staffing_varies_by_period"):
        return None
    return configured


DAY_UTILIZATION_BASIS = "continuous-day DES"


def _day_candidate_runner(queue_setup: dict, order: list[str], period_rows: dict[str, list],
                          scheduled: dict[str, list[str]]):
    """A ``run_fn`` that reads each period's replication from one continuous-day DES.

    Finding K: a period run alone for ``duration_hours`` (24 h) dilutes a
    break that fills that period. Here replication ``i`` of every period
    comes from the same day run (``run_routing_day_des`` with that
    replication's seed and the setup's breaks), as in selected-plan
    Validation. A lane's utilization is its busy time in the period over the
    period length (clamped at 1 as in ``evaluate_candidate_with_des``);
    waiting cost keeps the ``served / horizon * Wq * rate`` formula with the
    period as the horizon. Each seed's day runs once and is cached. Raises
    ValueError when the day cannot be laid out; the caller rejects the
    schedule rather than falling back to 24 h per-period runs (finding K2).
    """
    origin = des_day_start_minutes(queue_setup)
    if origin is None:
        raise ValueError("Representative-day optimization needs configured operating segments "
                         "to lay out the operating day.")
    try:
        segment_windows = {key: (low, high) for key, low, high in
                           (_segment_window(seg) for seg in queue_setup.get("segments") or []
                            if isinstance(seg, dict))}
    except (TypeError, ValueError):
        raise ValueError("Representative-day optimization cannot lay out the operating day: "
                         "an operating segment has an invalid start or end time.") from None
    unmatched = [label for label in order if label not in segment_windows]
    if unmatched:
        raise ValueError("Representative-day optimization cannot lay out the operating day: "
                         f"period(s) {', '.join(unmatched)} match no configured operating segment.")
    windows = []
    for label in order:
        low, high = segment_windows[label]
        windows.append({"time": label, "start_hours": (low - origin) / 60.0,
                        "end_hours": (high - origin) / 60.0,
                        "active_queue_ids": list(scheduled[label]),
                        "queues_by_id": {str(row.get("queue_id")): row for row in period_rows[label]}})
    tie_order = [str(queue_id) for queue_id in queue_setup.get("queue_ids") or []]
    day_breaks = resolve_des_breaks(queue_setup)
    days: dict[Any, dict] = {}

    def run(candidate, queues_by_id, *, duration_hours, seed, target, server_cost, waiting_cost,
            max_events):
        label = candidate.get("time")
        active = list(candidate.get("active_queue_ids") or [])
        available = list(candidate.get("available_queue_ids") or [])
        base = {"time": label, "available_queue_ids": available, "active_queue_ids": active,
                "inactive_queue_ids": list(candidate.get("inactive_queue_ids") or []),
                "target_utilization": target}
        if label not in scheduled or set(active) != set(scheduled[label]):
            return {**base, "status": "INVALID_INPUT",
                    "reason": "Continuous-day evaluation needs the scheduled lanes of every period.",
                    "evaluations": None, "total_cost": None}
        if seed not in days:
            try:
                days[seed] = run_routing_day_des(windows, tie_order=tie_order, seed=seed,
                                                 max_events=max_events, breaks=day_breaks)
            except ValueError as exc:
                days[seed] = {"error": str(exc)}
        day = days[seed]
        if "error" in day:
            return {**base, "status": "INVALID_INPUT", "reason": day["error"],
                    "evaluations": None, "total_cost": None}
        period = next(item for item in day["periods"] if item["time"] == label)
        horizon = period["duration_hours"]
        evaluations = []
        for lane in period["lanes"]:
            queue_id = lane["queue_id"]
            if queue_id not in available:
                continue
            row = queues_by_id.get(queue_id) or {}
            if queue_id in active:
                samples = _validated_samples(row) or []
                evaluations.append({
                    "queue_id": queue_id, "active": True, "lambda": row.get("lambda"),
                    "lambda_routed_sim": lane["lambda_routed_sim"],
                    "mu": len(samples) / sum(samples) if samples else row.get("mu"), "c": 1,
                    "server_id": lane["server_id"], "arrivals": lane["arrivals"],
                    "served": lane["served"], "waiting": max(0, lane["arrivals"] - lane["served"]),
                    "in_service": 0, "Wq": lane["Wq"], "rho": min(1.0, lane["rho"]),
                    "stable": bool(lane["rho"] < 1.0), "max_queue": lane["max_queue"]})
            else:
                evaluations.append({
                    "queue_id": queue_id, "active": False, "lambda": row.get("lambda"),
                    "lambda_routed_sim": 0.0, "mu": row.get("mu"), "c": 1,
                    "server_id": lane["server_id"], "arrivals": 0, "served": 0, "waiting": 0,
                    "in_service": 0, "Wq": None, "rho": None, "stable": True, "max_queue": 0})
        shared = {"evaluations": evaluations,
                  "total_lambda": sum(float(queues_by_id[q].get("lambda") or 0.0) for q in active),
                  "customer_conservation": day["customer_conservation"] is True,
                  "metric_provenance": "simulated", "utilization_basis": DAY_UTILIZATION_BASIS,
                  "seed": seed, "duration_hours": horizon,
                  "trace_events": [e for e in day["trace_events"] if e.get("segment_id") == label],
                  "trace_truncated": day["trace_truncated"]}
        over_target = sorted(item["queue_id"] for item in evaluations if item["active"]
                             and float(item["rho"]) > target + _UTILIZATION_TOLERANCE)
        if over_target:
            return {**base, **shared, "status": "INFEASIBLE", "total_cost": None,
                    "reason": (f"Simulated utilization exceeds the {target:.0%} ceiling for: "
                               + ", ".join(over_target) + ".")}
        server_total = 0.0
        waiting_total = 0.0
        for item in evaluations:
            if not item["active"]:
                continue
            server_total += _segment_server_cost(
                _validate_queue_row(queues_by_id[item["queue_id"]]) or {}, server_cost)
            if item["served"] and item["Wq"] is not None:
                waiting_total += _compute_waiting_cost(
                    item["served"] / horizon, item["Wq"], waiting_cost) or 0.0
        return {**base, **shared, "status": "FEASIBLE", "reason": None,
                "total_cost": server_total + waiting_total,
                "server_cost": server_total, "waiting_cost": waiting_total, "demand_conserved": True}

    return run


def optimize_separate_schedule(queue_setup: dict, records: list, *, target: float | None,
                               server_cost: float = DEFAULT_SERVER_COST_HR,
                               waiting_cost: float = DEFAULT_WAIT_COST_HR,
                               min_lanes=None, max_lanes=None,
                               lambda_multiplier: float = 1.0,
                               des_settings: dict | None = None,
                               run_fn=None, full_coverage: bool = False) -> dict:
    """Optimize every time period in persisted order, then roll up one status.

    With ``full_coverage`` each period's lower lane bound is the set of lanes
    scheduled for it (every configured lane unless staffing varies), and the
    period's records must name exactly those lanes; otherwise ValueError.

    Records group by time label; each period runs the routing-capable
    optimizer (or the legacy path when samples don't cover its search).
    Overall is COMPLETE only when every period is OPTIMAL; any INVALID_INPUT
    dominates, then incomplete (BLOCKED), then INFEASIBLE. Nulls stay null:
    unknown current lanes or no optimum render as missing, never zero.
    """
    ceiling = validate_separate_target(target)
    settings = validate_des_replication_config(des_settings)
    # Validation fills default costs; the caller's rates win unless the DES
    # config itself pinned them (as a saved scenario's snapshot does).
    pinned = des_settings if isinstance(des_settings, dict) else {}
    if "server_cost" not in pinned:
        settings["server_cost"] = float(server_cost)
    if "waiting_cost" not in pinned:
        settings["waiting_cost"] = float(waiting_cost)
    if not _is_number(lambda_multiplier) or float(lambda_multiplier) <= 0:
        raise ValueError("lambda_multiplier must be a finite positive number.")
    factor = float(lambda_multiplier)
    rows = list(records or [])
    if any(not isinstance(row, dict) for row in rows):
        return {"overall": "INVALID_INPUT", "reason": "Persisted queue records are invalid.",
                "target_utilization": ceiling, "evaluation_method": None,
                "periods": [], "des": settings}
    try:
        des_breaks = resolve_des_breaks(queue_setup)
    except ValueError as exc:
        return {"overall": "INVALID_INPUT", "reason": str(exc),
                "target_utilization": ceiling, "evaluation_method": None,
                "periods": [], "des": settings}
    order: list[str] = []
    grouped: dict[str, list] = {}
    for row in rows:
        label = str(row.get("time", row.get("segment_id", "Unknown")))
        if label not in grouped:
            grouped[label] = []
            order.append(label)
        grouped[label].append(row)
    # Finding K: representative-day full coverage reads every period from one
    # continuous day per replication (see _day_candidate_runner).
    day_run_fn = None
    if run_fn is None and full_coverage and queue_setup.get("event_period_basis") == "representative_day":
        scheduled = {label: _period_current_active(queue_setup, grouped[label]) for label in order}
        if all(scheduled.values()):
            scaled_rows = {label: [{**row, "lambda": float(row["lambda"]) * factor
                                    if _is_number(row.get("lambda")) else row.get("lambda")}
                                   for row in grouped[label]] for label in order}
            try:
                day_run_fn = _day_candidate_runner(
                    queue_setup, order, scaled_rows,
                    {label: list(lanes or []) for label, lanes in scheduled.items()})
            except ValueError as exc:
                return {"overall": "INVALID_INPUT", "reason": str(exc),
                        "target_utilization": ceiling, "evaluation_method": None,
                        "periods": [], "des": settings}
    periods: list[dict] = []
    for label in order:
        period_rows = []
        for row in grouped[label]:
            scaled = dict(row)
            lam = row.get("lambda")
            scaled["lambda"] = float(lam) * factor if _is_number(lam) else lam
            period_rows.append(scaled)
        current = _period_current_active(queue_setup, grouped[label])
        period_min = min_lanes
        if full_coverage:
            present = {str(row.get("queue_id")) for row in grouped[label]}
            if current is None or present != set(current):
                raise ValueError(
                    f"Full coverage: period {label} has records for lanes {sorted(present)} "
                    f"but the lanes scheduled for it are {current}.")
            period_min = len(current)
        try:
            period_breaks = (period_des_breaks(queue_setup, grouped[label])
                             if des_breaks is not None else None)
        except ValueError as exc:
            return {"overall": "INVALID_INPUT", "reason": str(exc),
                    "target_utilization": ceiling, "evaluation_method": None,
                    "periods": [], "des": settings}
        result = optimize_separate(
            label, period_rows, target=ceiling, min_lanes=period_min, max_lanes=max_lanes,
            current_active=len(current) if current else None,
            server_cost=server_cost, waiting_cost=waiting_cost,
            des_replications=settings, run_fn=day_run_fn or run_fn, breaks=period_breaks)
        optimum = result.get("optimum")
        optimal_count = optimum.get("active_lane_count") if optimum else None
        periods.append({
            "time": label,
            "overall": result.get("overall"),
            "reason": result.get("reason"),
            "current_active_lanes": current,
            "optimal_active_lanes": optimal_count,
            "adjustment": (optimal_count - len(current)
                           if optimal_count is not None and current else None),
            "optimum": optimum,
            "candidates": result.get("candidates"),
            "evaluation_method": result.get("evaluation_method"),
            "replication_count": result.get("replication_count"),
            "base_seed": result.get("base_seed"),
            "replication_seeds": result.get("replication_seeds"),
            "target_utilization": ceiling,
            **({"utilization_basis": DAY_UTILIZATION_BASIS} if day_run_fn else {}),
        })
    methods = {period.get("evaluation_method") for period in periods}
    method = "DES_REPLICATIONS" if methods == {"DES_REPLICATIONS"} else None
    shell = {"target_utilization": ceiling, "evaluation_method": method,
             "periods": periods, "des": settings,
             **({"utilization_basis": DAY_UTILIZATION_BASIS} if day_run_fn else {})}
    bad_input = [str(p["time"]) for p in periods if p["overall"] == "INVALID_INPUT"]
    if bad_input:
        return {**shell, "overall": "INVALID_INPUT",
                "reason": f"Invalid inputs for period(s): {', '.join(bad_input)}."}
    blocked = [str(p["time"]) for p in periods
               if p["overall"] != "OPTIMAL" and p["overall"] != "INFEASIBLE"]
    if blocked:
        first = next(p for p in periods if p["time"] in blocked)
        return {**shell, "overall": "BLOCKED",
                "reason": f"Period(s) {', '.join(blocked)} cannot claim an optimum: "
                          f"{first.get('reason')}"}
    infeasible = [str(p["time"]) for p in periods if p["overall"] == "INFEASIBLE"]
    if infeasible:
        return {**shell, "overall": "INFEASIBLE",
                "reason": "No feasible staffing plan satisfies the selected utilization target "
                          f"for period(s): {', '.join(infeasible)}."}
    return {**shell, "overall": "COMPLETE", "reason": None}


def prune_separate_schedule(schedule: dict) -> dict:
    """Drop trace event payloads for API/persistence transfer.

    Metrics, statuses, costs, uncertainty, and provenance are preserved;
    representative traces keep their identity, truncation flag, and event
    count with the payload replaced by an explicit omission marker.
    """
    import copy

    pruned = copy.deepcopy(schedule)
    for period in pruned.get("periods") or []:
        seen = set()

        def _records():
            yield from period.get("candidates") or []
            if period.get("optimum") is not None:
                yield period["optimum"]

        for record in _records():
            if id(record) in seen:
                continue
            seen.add(id(record))
            evidence = (record or {}).get("evidence") or {}
            trace = evidence.get("representative_trace") or {}
            events = trace.get("events")
            if isinstance(events, list):
                trace["event_count"] = len(events)
                trace["events"] = None
                trace["events_omitted"] = True
    return pruned


def optimize_separate(time_label, queue_rows, *, target=None, min_lanes=None, max_lanes=None,
                      current_active=None, server_cost=DEFAULT_SERVER_COST_HR,
                      waiting_cost=DEFAULT_WAIT_COST_HR,
                      des_replications=None, run_fn=None, breaks=None) -> dict:
    """Produce one optimum over active-lane counts, or an honest non-result.

    Exactly one optimum (lowest modeled total cost among feasible candidates;
    ties resolve to fewer lanes deterministically) or None with an overall
    status of INVALID_INPUT, UNSUPPORTED, or INFEASIBLE. The recommendation
    compares the optimum lane count to current staffing when provided.

    When every lane the search can activate carries empirical service
    samples, candidates are evaluated with routing-capable DES_REPLICATIONS
    (one consistent method across the whole ranking) instead of the
    analytical path; otherwise the legacy analytical behavior is preserved
    exactly, including reduced-lane UNSUPPORTED.

    Optional ``breaks`` carries pre-converted DES offset records applied to
    every candidate evaluation that activates the corresponding lanes.
    """
    ceiling = validate_separate_target(target)
    if not isinstance(queue_rows, list) or not queue_rows:
        return {"time": time_label, "target_utilization": ceiling, "overall": "INVALID_INPUT",
                "reason": "At least one queue row is required.",
                "candidates": [], "optimum": None}
    available = []
    for row in queue_rows:
        queue_id = row.get("queue_id") if isinstance(row, dict) else None
        if not isinstance(queue_id, str) or not queue_id:
            return {"time": time_label, "target_utilization": ceiling, "overall": "INVALID_INPUT",
                    "reason": "Queue rows must carry non-empty string queue IDs.",
                    "candidates": [], "optimum": None}
        available.append(queue_id)
    if len(set(available)) != len(available):
        return {"time": time_label, "target_utilization": ceiling, "overall": "INVALID_INPUT",
                "reason": "Queue IDs must be unique within a time period.",
                "candidates": [], "optimum": None}
    counts = build_candidates(available, min_lanes=min_lanes, max_lanes=max_lanes)
    by_id = {row["queue_id"]: row for row in queue_rows if isinstance(row, dict)}
    raw_des = {} if des_replications is None else des_replications
    try:
        des_settings = validate_des_replication_config(des_replications)
    except ValueError as exc:
        return {"time": time_label, "target_utilization": ceiling, "overall": "INVALID_INPUT",
                "reason": str(exc), "candidates": [], "optimum": None}
    if not isinstance(raw_des, dict):
        raw_des = {}
    if "server_cost" not in raw_des:
        des_settings["server_cost"] = float(server_cost)
    if "waiting_cost" not in raw_des:
        des_settings["waiting_cost"] = float(waiting_cost)
    des_settings["target"] = ceiling
    needed_lanes = {queue_id for spec in counts for queue_id in spec["active_queue_ids"]}
    des_capable = True
    for queue_id in needed_lanes:
        row = by_id.get(queue_id)
        if not isinstance(row, dict) or _validate_queue_row(row) is None:
            des_capable = False
            break
        if _validated_samples(row) is None:
            des_capable = False
            break
    if des_capable:
        return _optimize_separate_des(
            time_label, available, by_id, counts, ceiling=ceiling,
            current_active=current_active, server_cost=server_cost,
            waiting_cost=waiting_cost, des_settings=des_settings, run_fn=run_fn,
            breaks=breaks)
    candidates = []
    for spec in counts:
        result = evaluate_candidate(
            {"time": time_label, "available_queue_ids": available,
             "active_queue_ids": spec["active_queue_ids"],
             "inactive_queue_ids": spec["inactive_queue_ids"]},
            by_id, target=ceiling, server_cost=server_cost, waiting_cost=waiting_cost,
        )
        result["active_lane_count"] = len(spec["active_queue_ids"])
        candidates.append(result)
    if any(candidate["status"] == "INVALID_INPUT" for candidate in candidates):
        return {"time": time_label, "target_utilization": ceiling, "overall": "INVALID_INPUT",
                "reason": "Candidate inputs failed validation.",
                "candidates": candidates, "optimum": None}
    feasible = [candidate for candidate in candidates if candidate["status"] == "FEASIBLE"]
    if not feasible:
        if any(candidate["status"] == "UNSUPPORTED" for candidate in candidates):
            overall, reason = "UNSUPPORTED", "No candidate has an approved mathematical representation."
        else:
            overall, reason = "INFEASIBLE", "No candidate satisfies stability and utilization constraints."
        return {"time": time_label, "target_utilization": ceiling, "overall": overall,
                "reason": reason, "candidates": candidates, "optimum": None}
    optimum = min(feasible, key=lambda candidate: (candidate["total_cost"], candidate["active_lane_count"]))
    if current_active is None:
        recommendation = None
    elif optimum["active_lane_count"] > current_active:
        recommendation = "INCREASE"
    elif optimum["active_lane_count"] < current_active:
        recommendation = "REDUCE"
    else:
        recommendation = "KEEP"
    return {"time": time_label, "target_utilization": ceiling, "overall": "OPTIMAL",
            "reason": None, "candidates": candidates,
            "optimum": {**optimum, "recommendation": recommendation}}
