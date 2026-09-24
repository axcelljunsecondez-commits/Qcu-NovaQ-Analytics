"""Shared-queue dynamic capacity optimization (Phase 2 of the shared-queue enhancement).

For every staffing segment of a validated Phase 1 timeline, evaluate each configured
server count with the stationary M/M/c equations (M/M/1 when c = 1), enforce the
configured constraints, cost the segment over its duration, and keep the cheapest
feasible server count.

Spec: docs/superpowers/specs/2026-09-24-shared-queue-capacity-optimization.md.

Nothing existing imports this module. The legacy optimizer (``optimization.optimize_segment``
behind ``/optimize`` and ``/optimize/batch``), scenario schema versions, model selection,
Decision, reports, the legacy shared DES, and all separate-queue code are unchanged.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from numbers import Integral, Real
from typing import Any

from backend.queueing_engine.services.shared_segments import (
    ASSUMPTIONS as SEGMENT_ASSUMPTIONS,
)
from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
    containing_period,
    evaluate_segment,
    validate_timeline,
)
from backend.queueing_engine.utilization import THRESHOLD_TOLERANCE

ENGINE_VERSION = "novaq-shared-capacity-v1"
MAX_CANDIDATE_SERVERS = 256  # the legacy optimizer API's ceiling
COST_TIE_RELATIVE_TOLERANCE = 1e-9

OBJECTIVE = (
    "For each staffing segment, minimize server cost (c x server cost per hour x T) plus waiting "
    "cost (arrival rate x Wq x T x waiting cost per customer-hour) over the configured candidate "
    "server counts, subject to the enabled constraints. Segments are independent in the "
    "stationary model, so this is the horizon minimum for this objective; it is not a workforce "
    "or payroll optimum."
)
TOLERANCE_POLICY = (
    f"The shared-queue pipeline uses one float-noise tolerance, utilization.THRESHOLD_TOLERANCE "
    f"({THRESHOLD_TOLERANCE:g}): the same tolerance is_saturated applies to the stability test inside "
    "the M/M/c equations, so stability and the utilization and wait limits share one boundary rule. "
    "It is far above the rounding error of lambda/(c mu) and far below the smallest displayed "
    "utilization step (1e-6). The legacy optimizer's 1e-12 margin is unchanged and applies only "
    "to the legacy path."
)
TIE_RULE = (
    f"Candidates within a relative {COST_TIE_RELATIVE_TOLERANCE:g} of the lowest total cost are "
    "tied; the tie goes to fewer servers."
)
CAPACITY_ASSUMPTIONS = [
    "Costs use the configured server cost per server-hour and waiting cost per customer-hour; "
    "no rate is assumed by the optimizer.",
    "Wait limits and costs are steady-state estimates for customers arriving in each segment. "
    "They are not exact outcomes of a continuous day; the continuous DES is the tool for that.",
    "Closing a segment (0 servers) can only be chosen when no customer arrives in it, and "
    "customers left waiting from earlier segments cannot be checked by this analysis.",
]

_INFEASIBLE_STATUS = {"UNSTABLE": "stability", "NO_CAPACITY": "no_capacity", "CALCULATION_FAILED": "calculation_failed"}


@dataclass(frozen=True)
class CapacityConfig:
    """Operating parameters supplied by the caller; the optimizer holds no defaults."""

    server_cost_per_hour: float
    waiting_cost_per_customer_hour: float
    target_utilization: float
    min_servers: int
    max_servers: int
    max_wait_minutes: float | None = None


def _is_finite_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def _is_whole_number(value: object) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def validate_config(config: CapacityConfig) -> None:
    """Raise ``SharedSegmentError`` listing every configuration problem."""
    problems = []
    if not _is_finite_real(config.server_cost_per_hour) or float(config.server_cost_per_hour) <= 0:
        problems.append("Server cost per server-hour must be a finite number above 0.")
    if not _is_finite_real(config.waiting_cost_per_customer_hour) or float(config.waiting_cost_per_customer_hour) < 0:
        problems.append("Waiting cost per customer-hour must be a finite number, 0 or more.")
    if not _is_finite_real(config.target_utilization) or not 0 < float(config.target_utilization) <= 1:
        problems.append("Target utilization must be a finite number above 0 and at most 1.")
    bounds_ok = True
    for name, value in (("Minimum servers", config.min_servers), ("Maximum servers", config.max_servers)):
        if not _is_whole_number(value) or not 0 <= int(value) <= MAX_CANDIDATE_SERVERS:  # type: ignore[call-overload]
            problems.append(f"{name} must be a whole number between 0 and {MAX_CANDIDATE_SERVERS}.")
            bounds_ok = False
    if bounds_ok and int(config.min_servers) > int(config.max_servers):
        problems.append("Minimum servers must not exceed maximum servers.")
    if config.max_wait_minutes is not None and (
        not _is_finite_real(config.max_wait_minutes) or float(config.max_wait_minutes) < 0
    ):
        problems.append("Maximum wait must be a finite number of minutes, 0 or more, or omitted.")
    if problems:
        raise SharedSegmentError(problems)


def evaluate_candidate(
    segment: StaffingSegment, period: DemandPeriod, servers: int, config: CapacityConfig
) -> dict[str, Any]:
    """Cost and check one server count for one staffing segment."""
    row = evaluate_segment(replace(segment, servers=servers), period)
    duration = row["duration_hours"]
    server_cost = servers * float(config.server_cost_per_hour) * duration
    waiting_hours = row["expected_waiting_customer_hours"]
    waiting_cost = None if waiting_hours is None else waiting_hours * float(config.waiting_cost_per_customer_hour)
    status = row["status"]

    violations: list[str] = []
    if status in _INFEASIBLE_STATUS:
        violations.append(_INFEASIBLE_STATUS[status])
    elif status in ("STABLE", "ZERO_DEMAND"):
        if row["rho"] > float(config.target_utilization) + THRESHOLD_TOLERANCE:
            violations.append("target_utilization")
        if config.max_wait_minutes is not None and (
            row["Wq_hours"] * 60.0 > float(config.max_wait_minutes) + THRESHOLD_TOLERANCE
        ):
            violations.append("max_wait_minutes")
    # CLOSED: no customer arrives, so the utilization and wait limits have nothing to limit.

    return {
        "servers": servers,
        "status": status,
        "selected_model": row["selected_model"],
        "rho": row["rho"],
        "Lq": row["Lq"],
        "Wq_hours": row["Wq_hours"],
        "server_hours": row["server_hours"],
        "expected_waiting_customer_hours": waiting_hours,
        "server_cost": server_cost,
        "waiting_cost": waiting_cost,
        "total_cost": None if waiting_cost is None else server_cost + waiting_cost,
        "feasible": not violations and waiting_cost is not None,
        "violations": violations,
        "note": row["note"],
    }


def _select(candidates: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    feasible = [candidate for candidate in candidates if candidate["feasible"]]
    if not feasible:
        return None
    lowest = min(candidate["total_cost"] for candidate in feasible)
    tied = [
        candidate for candidate in feasible
        if math.isclose(candidate["total_cost"], lowest, rel_tol=COST_TIE_RELATIVE_TOLERANCE, abs_tol=0.0)
    ]
    return min(tied, key=lambda candidate: candidate["servers"])


def _optimize_segment(segment: StaffingSegment, period: DemandPeriod, config: CapacityConfig) -> dict[str, Any]:
    candidates = [
        evaluate_candidate(segment, period, servers, config)
        for servers in range(int(config.min_servers), int(config.max_servers) + 1)
    ]
    current = evaluate_candidate(segment, period, int(segment.servers), config)
    current["within_candidate_range"] = int(config.min_servers) <= int(segment.servers) <= int(config.max_servers)
    selected = _select(candidates)
    base = evaluate_segment(segment, period)
    violations_seen = sorted({violation for candidate in candidates for violation in candidate["violations"]})
    return {
        "segment_id": segment.segment_id,
        "start": base["start"],
        "end": base["end"],
        "duration_minutes": base["duration_minutes"],
        "duration_hours": base["duration_hours"],
        "arrival_rate_per_hour": base["arrival_rate_per_hour"],
        "service_rate_per_hour": base["service_rate_per_hour"],
        "demand_period_id": base["demand_period_id"],
        "demand_source": base["demand_source"],
        "outcome": "OPTIMIZED" if selected is not None else "NO_FEASIBLE_CANDIDATE",
        "current": current,
        "selected": selected,
        "violations_seen": violations_seen,
        "server_change": None if selected is None else selected["servers"] - current["servers"],
        "cost_change": (
            None if selected is None or current["total_cost"] is None
            else selected["total_cost"] - current["total_cost"]
        ),
        "candidates": candidates,
    }


def _totals(rows: Sequence[dict[str, Any] | None], segment_ids: Sequence[str]) -> dict[str, Any]:
    """Sum each cost field only when every segment defines it."""
    missing = [segment_id for segment_id, row in zip(segment_ids, rows) if row is None]
    totals: dict[str, Any] = {}
    for field in ("server_hours", "server_cost", "expected_waiting_customer_hours", "waiting_cost", "total_cost"):
        values = [None if row is None else row[field] for row in rows]
        totals[field] = None if any(value is None for value in values) else math.fsum(values)  # type: ignore[arg-type]
    undefined = [
        segment_id for segment_id, row in zip(segment_ids, rows)
        if row is not None and row["total_cost"] is None
    ]
    totals["segments_without_selection"] = missing
    totals["segments_with_undefined_cost"] = undefined
    return totals


def optimize_shared_capacity(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    staffing_segments: Sequence[StaffingSegment],
    config: CapacityConfig,
) -> dict[str, Any]:
    """Validate the timeline and configuration, then optimize every staffing segment."""
    validate_timeline(horizon, demand_periods, staffing_segments)
    validate_config(config)

    segments = []
    for segment in staffing_segments:
        period = containing_period(segment, demand_periods)
        assert period is not None  # guaranteed by validate_timeline
        segments.append(_optimize_segment(segment, period, config))

    segment_ids = [row["segment_id"] for row in segments]
    current_totals = _totals([row["current"] for row in segments], segment_ids)
    selected_totals = _totals([row["selected"] for row in segments], segment_ids)
    plan_complete = not selected_totals["segments_without_selection"]
    if current_totals["total_cost"] is None:
        change_reason: str | None = (
            "The current staffing has no finite cost in: "
            + ", ".join(current_totals["segments_with_undefined_cost"]) + "."
        )
    elif selected_totals["total_cost"] is None:
        change_reason = (
            "No feasible server count exists in: "
            + ", ".join(selected_totals["segments_without_selection"]) + "."
        )
    else:
        change_reason = None

    return {
        "segments": segments,
        "totals": {
            "current": current_totals,
            "selected": selected_totals,
            "plan_complete": plan_complete,
            "cost_change": (
                None if change_reason is not None
                else selected_totals["total_cost"] - current_totals["total_cost"]
            ),
            "cost_change_unavailable_reason": change_reason,
        },
        "provenance": {
            "engine_version": ENGINE_VERSION,
            "metric_provenance": "analytical_steady_state",
            "objective": OBJECTIVE,
            "tie_rule": TIE_RULE,
            "tolerances": {
                "utilization_and_wait_limits": THRESHOLD_TOLERANCE,
                "cost_tie_relative": COST_TIE_RELATIVE_TOLERANCE,
            },
            "tolerance_policy": TOLERANCE_POLICY,
            "units": {
                "rates": "customers per hour; service rate per server",
                "duration": "hours (whole minutes / 60)",
                "Wq": "hours",
                "max_wait": "minutes",
                "server_cost_per_hour": "currency per server-hour",
                "waiting_cost_per_customer_hour": "currency per customer-hour",
                "costs": "currency over each segment's duration",
            },
            "config": asdict(config),
            "inputs": {
                "horizon": asdict(horizon),
                "demand_periods": [asdict(period) for period in demand_periods],
                "staffing_segments": [asdict(segment) for segment in staffing_segments],
            },
            "assumptions": [*SEGMENT_ASSUMPTIONS, *CAPACITY_ASSUMPTIONS],
        },
    }
