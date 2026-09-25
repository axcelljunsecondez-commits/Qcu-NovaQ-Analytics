"""Continuous shared-queue DES replications (Phase 4 of the shared-queue enhancement).

Repeated stochastic simulation, not repeated analytical formulas: every replication runs the
Phase 3A continuous DES over the whole horizon with the scenario's own rates, one explicit
closing policy, and its own seeded streams. No parameter perturbation is applied; the legacy
±20% / ±10% noise of ``simulation.mc_simulate_segment`` is not used.

Spec: docs/superpowers/specs/2026-09-25-shared-queue-des-replications-playback.md.
Nothing legacy imports this module.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from numbers import Integral, Real
from typing import Any

import numpy as np
from scipy.stats import norm
from scipy.stats import t as student_t

from backend.queueing_engine.config import MC_CONFIDENCE_LEVEL, MC_MAX_TRIALS
from backend.queueing_engine.services.shared_day_cost import (
    COSTED,
    SERVER_HOURS_NOTE,
    DayCostRates,
    cost_shared_day,
    validate_rates,
)
from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
    validate_timeline,
)
from backend.queueing_engine.simulation.shared_continuous_des import (
    CLOSING_POLICIES,
    ENGINE_VERSION,
    SERVER_HOURS_MEANING,
    simulate_shared_replication,
)
from backend.queueing_engine.statistics.proportions import wilson_ci
from backend.queueing_engine.utilization import THRESHOLD_TOLERANCE

METHOD_VERSION = "novaq-shared-des-replications-v1"

# Two-sided quantiles for the configured confidence level (0.95 in config).
_UPPER = 1.0 - (1.0 - MC_CONFIDENCE_LEVEL) / 2.0
_Z = float(norm.ppf(_UPPER))

VIOLATED, SATISFIED, NOT_EVALUABLE = "VIOLATED", "SATISFIED", "NOT_EVALUABLE"
FAILED, PASSED = "FAILED", "PASSED"

SEED_SCHEME = (
    "Root numpy SeedSequence(seed); seed None draws fresh entropy, recorded as root_entropy. Replication i "
    "(0-based) uses child SeedSequence(entropy=root_entropy, spawn_key=(i,)), the i-th child of "
    "root.spawn(replications); numpy documents spawned children as seeds for independent bit generators. "
    "Each child spawns two PCG64 streams: arrival gaps, then unit work."
)
PARAMETER_UNCERTAINTY = (
    "None. Every replication uses the scenario's own arrival and service rates; the variation is the "
    "DES's own randomness. The legacy analytical perturbation (arrival ±20%, service ±10%) is not "
    "applied. Parameter uncertainty is a separate experiment, not implemented here."
)
CONTINUOUS_INTERVAL_METHOD = (
    "Mean, sample SD (n - 1), SE = SD / sqrt(n), and a two-sided Student-t interval at the configured "
    "confidence level over replications where the value is defined (the NovaQ DES-replication "
    "convention). n < 2 gives a mean only. Undefined values are counted in n_undefined, never zero-filled."
)
PROPORTION_INTERVAL_METHOD = "Wilson score interval (statistics.proportions.wilson_ci)."

METRIC_DEFINITIONS = {
    "arrivals": "Customers who arrived during the horizon.",
    "served": "Customers who completed service (departed), including after closing under DRAIN.",
    "unserved": "Customers recorded as unserved_at_close.",
    "wait_sum_hours": "Sum of waits (service start - arrival) over served customers.",
    "mean_wait_hours": (
        "Replication mean wait: wait_sum_hours / served. Population: customers who started service; "
        "undefined when none did. Unserved customers' elapsed waits are censored and excluded here but "
        "counted in the waiting-hours values."
    ),
    "waiting_hours_before_close": "Customer-hours spent waiting inside the horizon (integral of the line).",
    "waiting_hours_after_close": "Customer-hours spent waiting after closing.",
    "total_waiting_hours": "Waiting customer-hours before plus after closing.",
    "time_average_queue_in_horizon": "Waiting customer-hours inside the horizon / horizon hours.",
    "max_queue_in_horizon": "Largest number waiting inside the horizon.",
    "busy_server_hours_in_horizon": "Server-hours spent serving inside the horizon.",
    "busy_server_hours_after_close": "Server-hours spent serving after closing.",
    "available_server_hours_in_horizon": (
        "Server-hours with a server open (accepting or draining) inside the horizon; the regular hours."
    ),
    "overtime_server_hours": "Server-hours with a server open after closing.",
    "scheduled_server_hours": "Scheduled servers x segment hours.",
    "server_hours_above_schedule_in_horizon": "Available minus scheduled server-hours inside the horizon.",
    "utilization_in_horizon": (
        "busy_server_hours_in_horizon / available_server_hours_in_horizon; undefined when no server was open."
    ),
    "utilization_whole_run": (
        "(busy in horizon + busy after closing) / (available in horizon + overtime server-hours)."
    ),
    "overrun_hours": "Last server release after closing - closing time (0 when none).",
}
CONTINUOUS_METRICS = tuple(key for key in METRIC_DEFINITIONS if key not in ("arrivals", "served", "unserved"))

CRITERION_DEFINITIONS = {
    "max_mean_wait_minutes": (
        "Violated when the replication mean wait (served customers, minutes) exceeds the limit plus "
        "THRESHOLD_TOLERANCE; not evaluable when no customer was served."
    ),
    "max_utilization": (
        "Violated when utilization_in_horizon exceeds the limit plus THRESHOLD_TOLERANCE; not evaluable when "
        "no server was open. Independent of any Phase 2 target utilization."
    ),
    "max_unserved_customers": "Violated when the unserved count exceeds the limit.",
    "max_overrun_minutes": "Violated when the closing overrun (minutes) exceeds the limit plus THRESHOLD_TOLERANCE.",
}
NO_VERDICT_REASON = (
    "No approved pass/fail rule exists for the continuous shared DES, so no PASS/FAIL or acceptability "
    "label is produced; the proportions are descriptive. The legacy utilization > 0.75 criterion and 0.05 "
    "failure cap are not applied."
)


@dataclass(frozen=True)
class FailureCriteria:
    """Caller-supplied limits. ``None`` means not evaluated; there are no default thresholds."""

    max_mean_wait_minutes: float | None = None
    max_utilization: float | None = None
    max_unserved_customers: int | None = None
    max_overrun_minutes: float | None = None


def _is_finite_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def _is_whole(value: object) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def criteria_problems(criteria: object) -> list[str]:
    """Every problem with a ``FailureCriteria``; an empty list when valid."""
    if not isinstance(criteria, FailureCriteria):
        return ["failure_criteria must be a FailureCriteria or omitted."]
    problems = []
    values = asdict(criteria)
    if all(value is None for value in values.values()):
        problems.append("failure_criteria must set at least one criterion.")
    for name in ("max_mean_wait_minutes", "max_overrun_minutes"):
        value = values[name]
        if value is not None and (not _is_finite_real(value) or value < 0):
            problems.append(f"{name} must be a finite number, 0 or more, or None.")
    utilization = values["max_utilization"]
    if utilization is not None and (not _is_finite_real(utilization) or not 0 < utilization <= 1):
        problems.append("max_utilization must be a finite number above 0 and at most 1, or None.")
    unserved = values["max_unserved_customers"]
    if unserved is not None and (not _is_whole(unserved) or unserved < 0):
        problems.append("max_unserved_customers must be a whole number, 0 or more, or None.")
    return problems


def _above(value: float, limit: float) -> bool:
    return value > float(limit) + THRESHOLD_TOLERANCE


def criterion_outcomes(row: dict[str, Any], criteria: FailureCriteria) -> dict[str, str]:
    """Outcome of each set criterion for one replication row."""
    outcomes = {}
    if criteria.max_mean_wait_minutes is not None:
        wait = row["mean_wait_hours"]
        outcomes["max_mean_wait_minutes"] = (
            NOT_EVALUABLE if wait is None else VIOLATED if _above(wait * 60.0, criteria.max_mean_wait_minutes)
            else SATISFIED
        )
    if criteria.max_utilization is not None:
        utilization = row["utilization_in_horizon"]
        outcomes["max_utilization"] = (
            NOT_EVALUABLE if utilization is None else VIOLATED if _above(utilization, criteria.max_utilization)
            else SATISFIED
        )
    if criteria.max_unserved_customers is not None:
        outcomes["max_unserved_customers"] = (
            VIOLATED if row["unserved"] > int(criteria.max_unserved_customers) else SATISFIED
        )
    if criteria.max_overrun_minutes is not None:
        outcomes["max_overrun_minutes"] = (
            VIOLATED if _above(row["overrun_hours"] * 60.0, criteria.max_overrun_minutes) else SATISFIED
        )
    return outcomes


def replication_outcome(outcomes: dict[str, str]) -> str:
    """FAILED if any set criterion is violated, PASSED if all are evaluable and satisfied."""
    if any(outcome == VIOLATED for outcome in outcomes.values()):
        return FAILED
    if all(outcome == SATISFIED for outcome in outcomes.values()):
        return PASSED
    return NOT_EVALUABLE


def replication_row(
    result: dict[str, Any],
    replication_index: int,
    cost_rates: DayCostRates | None = None,
    failure_criteria: FailureCriteria | None = None,
) -> dict[str, Any]:
    """The scalar summary kept for one replication (no events and no customer rows)."""
    totals, closing = result["totals"], result["closing"]
    served_waits = [row["wait_hours"] for row in result["customers"] if row["status"] == "departed"]
    served = len(served_waits)
    wait_sum = math.fsum(served_waits)
    available_in, overtime = totals["present_server_hours"], closing["after_close_server_hours"]
    busy_in, busy_after = totals["busy_server_hours"], closing["after_close_busy_server_hours"]
    available_all = available_in + overtime
    row: dict[str, Any] = {
        "replication_index": replication_index,
        "spawn_key": list(result["provenance"]["spawn_key"]),
        "arrivals": totals["arrivals"],
        "served": served,
        "unserved": totals["unserved_at_close"],
        "customer_conservation": totals["customer_conservation"]
        and totals["arrivals"] == served + totals["unserved_at_close"],
        "wait_sum_hours": wait_sum,
        "mean_wait_hours": wait_sum / served if served else None,
        "waiting_hours_before_close": totals["queue_customer_hours"],
        "waiting_hours_after_close": closing["after_close_waiting_customer_hours"],
        "total_waiting_hours": result["cost_quantities"]["total_waiting_customer_hours"],
        "time_average_queue_in_horizon": totals["time_average_queue"],
        "max_queue_in_horizon": totals["max_queue"],
        "busy_server_hours_in_horizon": busy_in,
        "busy_server_hours_after_close": busy_after,
        "available_server_hours_in_horizon": available_in,
        "overtime_server_hours": overtime,
        "scheduled_server_hours": totals["scheduled_server_hours"],
        "server_hours_above_schedule_in_horizon": totals["server_hours_above_schedule"],
        "utilization_in_horizon": busy_in / available_in if available_in > 0 else None,
        "utilization_whole_run": (busy_in + busy_after) / available_all if available_all > 0 else None,
        "overrun_hours": closing["overrun_hours"],
    }
    if not row["customer_conservation"]:
        raise SharedSegmentError([f"Replication {replication_index} does not conserve customers."])
    if cost_rates is not None:
        summary = cost_shared_day(result, cost_rates)
        row["cost"] = {
            "total_cost": summary["total_cost"],
            "components": {item["component"]: item["cost"] for item in summary["components"]},
        }
    if failure_criteria is not None:
        outcomes = criterion_outcomes(row, failure_criteria)
        row["criteria"] = {"outcomes": outcomes, "replication_outcome": replication_outcome(outcomes)}
    return row


def summarize_metric(values: Sequence[float | None]) -> dict[str, Any]:
    """Across-replication statistics of one continuous metric (``None`` = undefined, never 0)."""
    defined = [float(value) for value in values if value is not None]
    count = len(defined)
    base: dict[str, Any] = {
        "mean": None, "sd": None, "se": None, "ci_lower": None, "ci_upper": None, "ci_half_width": None,
        "min": None, "max": None, "n": count, "n_undefined": len(values) - count,
    }
    if count == 0:
        return base
    mean = math.fsum(defined) / count
    base.update({"mean": mean, "min": min(defined), "max": max(defined)})
    if count < 2:
        return base
    sd = statistics.stdev(defined)
    se = sd / math.sqrt(count)
    half_width = float(student_t.ppf(_UPPER, count - 1)) * se
    base.update({
        "sd": sd, "se": se, "ci_lower": mean - half_width, "ci_upper": mean + half_width, "ci_half_width": half_width,
    })
    return base


def summarize_proportion(numerator: int, denominator: int) -> dict[str, Any]:
    """A proportion with its Wilson interval, numerator, and denominator."""
    lower, upper, half_width = wilson_ci(numerator, denominator, z=_Z)
    return {
        "numerator": numerator, "denominator": denominator,
        "proportion": numerator / denominator if denominator else None,
        "ci_lower": lower, "ci_upper": upper, "ci_half_width": half_width,
        "confidence_level": MC_CONFIDENCE_LEVEL, "method": PROPORTION_INTERVAL_METHOD,
    }


def _criteria_summary(rows: list[dict[str, Any]], criteria: FailureCriteria | None) -> dict[str, Any]:
    if criteria is None:
        return {"evaluated": False, "reason": "No failure criterion was supplied; no failure proportion is computed."}
    per_criterion = {}
    for name, limit in asdict(criteria).items():
        if limit is None:
            continue
        outcomes = [row["criteria"]["outcomes"][name] for row in rows]
        violations = outcomes.count(VIOLATED)
        not_evaluable = outcomes.count(NOT_EVALUABLE)
        per_criterion[name] = {
            "threshold": limit, "definition": CRITERION_DEFINITIONS[name], "violations": violations,
            "not_evaluable": not_evaluable, **summarize_proportion(violations, len(rows) - not_evaluable),
        }
    overall = [row["criteria"]["replication_outcome"] for row in rows]
    failed, passed = overall.count(FAILED), overall.count(PASSED)
    return {
        "evaluated": True,
        "thresholds": asdict(criteria),
        "threshold_tolerance": THRESHOLD_TOLERANCE,
        "per_criterion": per_criterion,
        "combined": {
            "rule": (
                "A replication fails when any set criterion is violated and passes when every set criterion "
                "is evaluable and satisfied; otherwise it is not evaluable and is excluded from the "
                "denominator, with its count reported."
            ),
            "failed": failed, "passed": passed, "not_evaluable": overall.count(NOT_EVALUABLE),
            **summarize_proportion(failed, failed + passed),
        },
        "verdict": None,
        "verdict_reason": NO_VERDICT_REASON,
    }


def _cost_summary(rows: list[dict[str, Any]], rates: DayCostRates | None, reference: dict[str, Any]) -> dict[str, Any]:
    # ``reference`` is the Phase 3A cost summary of one replication: component statuses and the
    # withheld reason depend only on the configuration, so they are the same for every replication.
    if rates is None:
        return {"evaluated": False, "reason": "No cost rates were supplied; no monetary output is produced."}
    totals = [row["cost"]["total_cost"] for row in rows]
    complete = [total is not None for total in totals]
    assert all(complete) or not any(complete)  # applicability depends only on the configuration
    components = {}
    for item in reference["components"]:
        name = item["component"]
        costs = [row["cost"]["components"][name] for row in rows]
        components[name] = {
            **{key: item[key] for key in ("status", "rate_field", "rate", "applies", "unit", "note")},
            "per_replication": summarize_metric(costs) if item["status"] == COSTED else None,
        }
    return {
        "evaluated": True,
        "rates": asdict(rates),
        "method": "Each replication is costed with services.shared_day_cost first; the costs are then aggregated.",
        "components": components,
        "total_cost": summarize_metric(totals) if all(complete) else None,
        "total_withheld_reason": reference["total_withheld_reason"],
        "server_hours_note": SERVER_HOURS_NOTE,
        "currency": "The caller's currency; no currency is assumed.",
    }


def aggregate_replications(
    rows: list[dict[str, Any]],
    *,
    cost_rates: DayCostRates | None = None,
    cost_reference: dict[str, Any] | None = None,
    failure_criteria: FailureCriteria | None = None,
) -> dict[str, Any]:
    """Aggregate per-replication rows; every replication is included in every count."""
    served = sum(row["served"] for row in rows)
    wait_sum = math.fsum(row["wait_sum_hours"] for row in rows)
    return {
        "replications": len(rows),
        "customers": {
            "arrivals": sum(row["arrivals"] for row in rows),
            "served": served,
            "unserved": sum(row["unserved"] for row in rows),
            "conserved_in_every_replication": all(row["customer_conservation"] for row in rows),
            "per_replication": {key: summarize_metric([row[key] for row in rows]) for key in ("arrivals", "served", "unserved")},
        },
        "waiting_time": {
            "mean_of_replication_means_hours": {
                **summarize_metric([row["mean_wait_hours"] for row in rows]),
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
        "metrics": {key: summarize_metric([row[key] for row in rows]) for key in CONTINUOUS_METRICS},
        "outcome_counts": {
            "definition": "Descriptive frequencies, not failure rates.",
            "replications_with_unserved_customers": sum(1 for row in rows if row["unserved"] > 0),
            "replications_with_overrun": sum(1 for row in rows if row["overrun_hours"] > 0),
            "replications_with_hours_above_schedule": sum(
                1 for row in rows if row["server_hours_above_schedule_in_horizon"] > 0
            ),
        },
        "cost": _cost_summary(rows, cost_rates, cost_reference or {}),
        "criteria": _criteria_summary(rows, failure_criteria),
    }


def run_shared_replications(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    staffing_segments: Sequence[StaffingSegment],
    *,
    replications: int,
    seed: int | None,
    closing_policy: str,
    cost_rates: DayCostRates | None = None,
    failure_criteria: FailureCriteria | None = None,
) -> dict[str, Any]:
    """Run ``replications`` independent continuous-DES replications and aggregate them.

    ``replications`` (1 to ``config.MC_MAX_TRIALS``), ``seed``, and ``closing_policy`` are
    required. Each replication keeps one scalar row; no events are retained. A single
    replication can be regenerated with its trace by ``shared_playback``.
    """
    validate_timeline(horizon, demand_periods, staffing_segments)
    problems = []
    if not _is_whole(replications) or not 1 <= replications <= MC_MAX_TRIALS:
        problems.append(f"replications must be a whole number from 1 to {MC_MAX_TRIALS} (config.MC_MAX_TRIALS).")
    if seed is not None and (not _is_whole(seed) or seed < 0):
        problems.append("seed must be a whole number, 0 or more, or None.")
    if closing_policy not in CLOSING_POLICIES:
        problems.append("closing_policy must be DRAIN or HARD_CUTOFF; there is no default.")
    if cost_rates is not None and not isinstance(cost_rates, DayCostRates):
        problems.append("cost_rates must be a DayCostRates or omitted.")
    if failure_criteria is not None:
        problems += criteria_problems(failure_criteria)
    if problems:
        raise SharedSegmentError(problems)
    if cost_rates is not None:
        validate_rates(cost_rates)

    root = np.random.SeedSequence(seed)
    rows: list[dict[str, Any]] = []
    cost_reference: dict[str, Any] = {}
    for index, child in enumerate(root.spawn(replications)):
        result = simulate_shared_replication(
            horizon, demand_periods, staffing_segments,
            seed_sequence=child, closing_policy=closing_policy, max_trace_events=0,
        )
        if cost_rates is not None and not cost_reference:
            cost_reference = cost_shared_day(result, cost_rates)
        rows.append(replication_row(result, index, cost_rates, failure_criteria))

    return {
        "replications": rows,
        "summary": aggregate_replications(
            rows, cost_rates=cost_rates, cost_reference=cost_reference, failure_criteria=failure_criteria,
        ),
        "provenance": {
            "method_version": METHOD_VERSION,
            "engine_version": ENGINE_VERSION,
            "metric_provenance": "des_continuous_replications",
            "method": "Independent replications of the continuous shared-queue DES over the whole horizon.",
            "parameter_uncertainty": PARAMETER_UNCERTAINTY,
            "replications": replications,
            "replication_limits": {"min": 1, "max": MC_MAX_TRIALS, "source": "config.MC_MAX_TRIALS"},
            "seed": seed,
            "root_entropy": root.entropy,
            "seed_scheme": SEED_SCHEME,
            "closing_policy": closing_policy,
            "confidence_level": MC_CONFIDENCE_LEVEL,
            "interval_methods": {"continuous": CONTINUOUS_INTERVAL_METHOD, "proportions": PROPORTION_INTERVAL_METHOD},
            "metric_definitions": dict(METRIC_DEFINITIONS),
            "time_unit": "hours (criteria thresholds in minutes)",
            "server_hours_meaning": SERVER_HOURS_MEANING,
            "retained": "One scalar row per replication; no events or customer rows.",
            "inputs": {
                "horizon": asdict(horizon),
                "demand_periods": [asdict(period) for period in demand_periods],
                "staffing_segments": [asdict(segment) for segment in staffing_segments],
                "cost_rates": None if cost_rates is None else asdict(cost_rates),
                "failure_criteria": None if failure_criteria is None else asdict(failure_criteria),
            },
        },
    }
