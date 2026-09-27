"""Integrated shared-queue planning MILP (Phase 5B-3 of the shared-queue enhancement).

Chooses employee shift-and-break patterns, and through them the active server count on every
elementary interval of the day, to minimise

    total planning cost = scheduled employee wages + analytical customer waiting cost.

The server count that prices waiting, and that is checked against stability, the utilization
target, and the maximum wait, is the roster's actual on-duty count on each interval (product-owner
decision, 2026-09-28): a break dip is costed at the lower count, and every employee on duty counts,
so surplus employees are never hidden. Each interval is evaluated with the Phase 1/Phase 2
stationary M/M/c evaluation over its own length, with its demand period's rates. Phase 2's server
cost per hour is never charged: wages are the only labor cost.

Pattern generation, pay-case logic, the labor rows, and the solver settings are reused from the
Phase 5B-2 sequential optimizer, which stays unchanged and available as the reference. Every solver
answer is re-checked exactly before it is called feasible.

The plan is analytical and scheduled, not simulated: "optimal" means optimal for this model, the
caller's break grid, and the reported solver tolerances, not for the real queue, and the
continuous-DES operating cost is a different quantity.

Spec: docs/superpowers/specs/2026-09-28-shared-queue-integrated-planning.md.
Nothing legacy imports this module.
"""

from __future__ import annotations

import bisect
import math
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from numbers import Integral, Real
from typing import Any

import numpy as np
import scipy
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array

from backend.queueing_engine.services.shared_capacity import (
    MAX_CANDIDATE_SERVERS,
    CapacityConfig,
    evaluate_candidate,
    optimize_shared_capacity,
)
from backend.queueing_engine.services.shared_rostering import (
    COST_CONSISTENCY_RELATIVE_TOLERANCE,
    FEASIBLE,
    FEASIBLE_NOT_PROVEN_OPTIMAL,
    INCOMPLETE,
    INFEASIBLE,
    INTEGRALITY_TOLERANCE,
    NO_SOLUTION_FOUND,
    OPTIMAL,
    PATTERN_LIMIT_EXCEEDED,
    SOLVER_ERROR,
    UNIQUENESS_NOTE,
    UNKNOWN,
    VERIFICATION_FAILED,
    RosterOptimizationConfig,
    RosterPattern,
    _build_model,
    _highs_details,
    _interval_cover,
    _labor_case,
    _labor_rows,
    enumerate_patterns,
    max_paid_minutes,
    optimize_roster_for_capacity_plan,
)
from backend.queueing_engine.services.shared_rostering import validate_config as validate_roster_config
from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
    validate_timeline,
)
from backend.queueing_engine.services.shared_workforce import (
    Employee,
    ScheduledBreak,
    ScheduledShift,
    WorkforceRules,
    _count_at,
    evaluate_roster,
    validate_workforce_inputs,
)

OPTIMIZER_VERSION = "novaq-shared-integrated-planning-v1"

SCOPE_NOTE = (
    "Integrated analytical planning: wages plus stationary M/M/c waiting cost, with the server count on "
    "every interval equal to the roster's on-duty count. The plan is scheduled, not simulated, and has not "
    "been validated by the DES; its waiting cost is an analytical estimate, not the continuous-DES operating "
    "cost. Optimal means optimal for this model, the break grid, and the reported solver tolerances, not "
    "for the real queue."
)
CAPACITY_NOTE = (
    "Each elementary interval (between consecutive shift, break, demand-period, and staffing-segment "
    "boundaries) is evaluated as a stationary M/M/c queue with its demand period's rates, over its own length, "
    "at the number of employees on duty. Short intervals, such as a break, are a stronger steady-state "
    "approximation than whole segments. Backlog carried between intervals is not represented."
)
LABOR_NOTE = (
    "Wages for scheduled paid minutes (regular and overtime, 5B-1 definitions) are the only labor cost. "
    "Phase 2's server cost per server-hour is not part of this objective and is never charged."
)
FORMULATION = {
    "decision_variables": "x_q in {0,1} per admissible pattern (5B-2 generation); z[i,c] in {0,1} per interval i "
                          "inside the horizon and admissible count c; with split shifts, R_e, O_e integer and "
                          "w_e in {0,1} as in 5B-2.",
    "objective": "minimise wages (5B-2 labor terms) + sum over i, c of waiting_cost[i,c] z[i,c], where "
                 "waiting_cost[i,c] = waiting cost per customer-hour x lambda x Wq(c) x length of i (hours)",
    "capacity_link": "sum_q a[q,i] x_q - sum_c c z[i,c] = 0 and sum_c z[i,c] = 1, every interval i inside the "
                     "horizon: the selected count is exactly the on-duty count",
    "admissible_counts": "c in [min_servers, min(max_servers, register_count)] that pass Phase 2's rule on i: "
                         "stable (or closed with no arrivals), rho <= target utilization and Wq <= maximum wait "
                         "(each + 1e-9)",
    "registers": "sum_q a[q,i] x_q <= register_count, every interval of the day (5B-2 rows)",
    "max_shifts_and_split_shifts": "the 5B-2 rows",
    "regular_overtime": "the 5B-2 terms: exact per-pattern cost with one shift a day, the R/O/w split otherwise",
    "time": "whole minutes since midnight; intervals are [start, end); rates are per hour",
}


# ── Inputs ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PlanningConfig:
    """Analytical planning settings supplied by the caller; none has a default."""

    waiting_cost_per_customer_hour: float | None  # None means not supplied, never 0
    target_utilization: float
    max_wait_minutes: float | None  # None means no wait limit, as in Phase 2
    min_servers: int  # bounds on the on-duty count inside the horizon
    max_servers: int


def _whole(value: object) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def _finite(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_planning_config(config: object) -> None:
    """Raise ``SharedSegmentError`` listing every configuration problem."""
    if not isinstance(config, PlanningConfig):
        raise SharedSegmentError(["planning must be a PlanningConfig."])
    problems = []
    rate = config.waiting_cost_per_customer_hour
    if rate is not None and (not _finite(rate) or float(rate) < 0):
        problems.append("Waiting cost per customer-hour must be a finite number, 0 or more, or None when not supplied.")
    if not _finite(config.target_utilization) or not 0 < float(config.target_utilization) <= 1:
        problems.append("Target utilization must be a finite number above 0 and at most 1.")
    if config.max_wait_minutes is not None and (not _finite(config.max_wait_minutes) or config.max_wait_minutes < 0):
        problems.append("Maximum wait must be a finite number of minutes, 0 or more, or None for no limit.")
    bounds_ok = True
    for name, value in (("Minimum servers", config.min_servers), ("Maximum servers", config.max_servers)):
        if not _whole(value) or not 0 <= int(value) <= MAX_CANDIDATE_SERVERS:  # type: ignore[call-overload]
            problems.append(f"{name} must be a whole number between 0 and {MAX_CANDIDATE_SERVERS}.")
            bounds_ok = False
    if bounds_ok and config.min_servers > config.max_servers:
        problems.append("Minimum servers must not exceed maximum servers.")
    if problems:
        raise SharedSegmentError(problems)


# ── Capacity evaluation (Phase 1/2 formulas) ────────────────────────────────


@dataclass(frozen=True)
class _Piece:
    """A stretch of the horizon inside one demand period and one staffing segment."""

    start_minute: int
    end_minute: int
    period: DemandPeriod
    segment_id: str


def _refinement(horizon: OperatingHorizon, demand_periods: Sequence[DemandPeriod],
                staffing_segments: Sequence[StaffingSegment]) -> list[_Piece]:
    points = sorted({horizon.start_minute, horizon.end_minute}
                    | {p for period in demand_periods for p in (period.start_minute, period.end_minute)}
                    | {p for segment in staffing_segments for p in (segment.start_minute, segment.end_minute)})
    pieces = []
    for start, end in zip(points, points[1:]):
        period = next(item for item in demand_periods if item.start_minute <= start < item.end_minute)
        segment = next(item for item in staffing_segments if item.start_minute <= start < item.end_minute)
        pieces.append(_Piece(start, end, period, segment.segment_id))
    return pieces


def _piece_at(pieces: Sequence[_Piece], starts: Sequence[int], minute: int) -> _Piece:
    return pieces[bisect.bisect_right(starts, minute) - 1]


class _Capacity:
    """Phase 2's admissibility rule and waiting customer-hours for one count over one stretch of time.

    ``evaluate_candidate`` is called only for its rule (stability, utilization target, maximum wait, with
    Phase 2's 1e-9 tolerance) and its expected waiting customer-hours (lambda x Wq x hours). Its cost
    fields are never read: its server charge must not enter this objective, and waiting is priced
    here with the caller's rate, so the rates passed to it are placeholders.
    """

    def __init__(self, planning: PlanningConfig, register_count: int):
        self.planning = planning
        self.register_count = register_count
        self.rule = CapacityConfig(server_cost_per_hour=0.0, waiting_cost_per_customer_hour=0.0,
                                   target_utilization=planning.target_utilization, min_servers=planning.min_servers,
                                   max_servers=planning.max_servers, max_wait_minutes=planning.max_wait_minutes)

    def candidates(self) -> range:
        return range(int(self.planning.min_servers), min(int(self.planning.max_servers), self.register_count) + 1)

    def evaluate(self, start: int, end: int, period: DemandPeriod, servers: int) -> dict[str, Any]:
        row = evaluate_candidate(StaffingSegment("interval", start, end, servers), period, servers, self.rule)
        hours = row["expected_waiting_customer_hours"]
        rate = self.planning.waiting_cost_per_customer_hour
        within = int(self.planning.min_servers) <= servers <= int(self.planning.max_servers)
        registers_ok = servers <= self.register_count
        violations = list(row["violations"])
        if not within:
            violations.append("server_bounds")
        if not registers_ok:
            violations.append("registers")
        if hours is None:
            cost = None
        elif hours == 0:
            cost = 0.0  # no expected waiting costs nothing whatever the rate
        else:
            cost = None if rate is None else hours * float(rate)
        return {
            "servers": servers,
            "status": row["status"],
            "selected_model": row["selected_model"],
            "rho": row["rho"],
            "Wq_hours": row["Wq_hours"],
            "expected_waiting_customer_hours": hours,
            "waiting_cost": cost,
            "admissible": bool(row["feasible"]) and within and registers_ok,
            "violations": violations,
        }


def _waiting_needed(horizon: OperatingHorizon, demand_periods: Sequence[DemandPeriod]) -> bool:
    return any(float(period.arrival_rate_per_hour) > 0 and period.start_minute < horizon.end_minute
               and period.end_minute > horizon.start_minute for period in demand_periods)


# ── Independent evaluation of any roster ────────────────────────────────────


def evaluate_planning_cost(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    staffing_segments: Sequence[StaffingSegment],
    employees: Sequence[Employee],
    rules: WorkforceRules,
    roster: Sequence[ScheduledShift],
    *,
    planning: PlanningConfig,
    break_start_granularity_minutes: int,
) -> dict[str, Any]:
    """Total planning cost of a roster on the integrated objective, and whether the roster is in its feasible set.

    Independent of the MILP: the on-duty counts come from the 5B-1 active-server steps, the wages from the
    5B-1 minutes, and waiting from Phase 2's evaluation of each stretch of constant count.
    """
    validate_timeline(horizon, demand_periods, staffing_segments)
    validate_planning_config(planning)
    grid = break_start_granularity_minutes
    if not _whole(grid) or not 1 <= grid <= 1440:
        raise SharedSegmentError(["break_start_granularity_minutes must be a whole number from 1 to 1440."])
    evaluation = evaluate_roster(horizon, employees, rules, roster)
    capacity = _Capacity(planning, rules.register_count)
    pieces = _refinement(horizon, demand_periods, staffing_segments)
    piece_starts = [piece.start_minute for piece in pieces]
    steps = evaluation["active_server_steps"]
    step_starts = [step["start_minute"] for step in steps]
    points = sorted({piece.start_minute for piece in pieces} | {horizon.end_minute}
                    | {p for step in steps for p in (step["start_minute"], step["end_minute"])
                       if horizon.start_minute < p < horizon.end_minute})

    stretches: list[dict[str, Any]] = []
    for start, end in zip(points, points[1:]):
        piece = _piece_at(pieces, piece_starts, start)
        count = _count_at(steps, step_starts, start)
        last = stretches[-1] if stretches else None
        if (last is not None and last["end_minute"] == start and last["active_servers"] == count
                and last["demand_period_id"] == piece.period.period_id and last["staffing_segment_id"] == piece.segment_id):
            last["end_minute"] = end
        else:
            stretches.append({"start_minute": start, "end_minute": end, "active_servers": count,
                              "demand_period_id": piece.period.period_id, "staffing_segment_id": piece.segment_id,
                              "_period": piece.period})
    rows = []
    for stretch in stretches:
        period = stretch.pop("_period")
        evaluated = capacity.evaluate(stretch["start_minute"], stretch["end_minute"], period, stretch["active_servers"])
        smallest = next((c for c in capacity.candidates()
                         if capacity.evaluate(stretch["start_minute"], stretch["end_minute"], period, c)["admissible"]),
                        None)
        rows.append({**stretch, "minutes": stretch["end_minute"] - stretch["start_minute"],
                     "arrival_rate_per_hour": float(period.arrival_rate_per_hour),
                     "service_rate_per_hour": float(period.service_rate_per_hour),
                     **{key: evaluated[key] for key in ("status", "selected_model", "rho", "Wq_hours",
                                                        "expected_waiting_customer_hours", "waiting_cost",
                                                        "admissible", "violations")},
                     "smallest_admissible_servers": smallest})

    reasons: list[str] = []
    if evaluation["violations"]:
        reasons.append("5B-1 violations: " + ", ".join(sorted({item["code"] for item in evaluation["violations"]})) + ".")
    off_grid = [shift for shift in roster for item in shift.breaks if item.start_minute % grid]
    if off_grid:
        reasons.append(f"A break does not start on the {grid}-minute break grid.")
    inadmissible = [row for row in rows if not row["admissible"]]
    if inadmissible:
        reasons.append("The on-duty count is not admissible in "
                       f"{len(inadmissible)} stretch(es) of the horizon (see capacity rows).")

    labor, labor_reason = _labor_rows(employees, evaluation) if not evaluation["violations"] else ([], None)
    labor_total = math.fsum(row["labor_cost"] for row in labor) if labor_reason is None and not evaluation["violations"] \
        else None
    waiting_values = [row["waiting_cost"] for row in rows]
    waiting_total = None if any(value is None for value in waiting_values) else math.fsum(waiting_values)  # type: ignore[arg-type]
    withheld = []
    if evaluation["violations"]:
        withheld.append("The roster is invalid under 5B-1, so its hours and wages are withheld.")
    elif labor_reason is not None:
        withheld.append(labor_reason)
    if waiting_total is None:
        withheld.append("Waiting cost is undefined in some stretch: an inadmissible (unstable or closed with "
                        "arrivals) count, or a missing waiting cost per customer-hour.")
    totals_minutes = (evaluation["totals"] or {}).get("minutes") or {}
    by_segment = []
    for segment in staffing_segments:
        own = [row for row in rows if row["staffing_segment_id"] == segment.segment_id]
        costs = [row["waiting_cost"] for row in own]
        by_segment.append({
            "segment_id": segment.segment_id, "start_minute": segment.start_minute, "end_minute": segment.end_minute,
            "min_active_servers": min(row["active_servers"] for row in own),
            "max_active_servers": max(row["active_servers"] for row in own),
            "server_minutes": sum(row["active_servers"] * row["minutes"] for row in own),
            "waiting_cost": None if any(cost is None for cost in costs) else math.fsum(costs),  # type: ignore[arg-type]
        })
    above = [row for row in rows if row["smallest_admissible_servers"] is not None]
    return {
        "in_integrated_feasible_set": not reasons,
        "feasible_set_reasons": reasons,
        "roster_evaluation": evaluation,
        "capacity": rows,
        "capacity_by_staffing_segment": by_segment,
        "active_server_minutes_in_horizon": sum(row["active_servers"] * row["minutes"] for row in rows),
        "active_server_minutes_outside_horizon": totals_minutes.get("active_server_minutes_outside_horizon"),
        "server_minutes_above_smallest_admissible": sum(
            (row["active_servers"] - row["smallest_admissible_servers"]) * row["minutes"] for row in above
            if row["active_servers"] > row["smallest_admissible_servers"]),
        "labor_cost": None if labor_total is None else {"employees": labor, "total": labor_total, "note": LABOR_NOTE},
        "waiting_cost": None if waiting_total is None else {
            "total": waiting_total,
            "expected_waiting_customer_hours": math.fsum(row["expected_waiting_customer_hours"] for row in rows),
            "note": CAPACITY_NOTE},
        "planning_cost": None if labor_total is None or waiting_total is None else labor_total + waiting_total,
        "withheld_reasons": withheld,
    }


# ── Model ───────────────────────────────────────────────────────────────────


def _build_integrated_model(horizon: OperatingHorizon, employees: Sequence[Employee], rules: WorkforceRules,
                            pieces: Sequence[_Piece], patterns: Sequence[RosterPattern],
                            cases: dict[str, tuple[str, int]], capacity: _Capacity) -> dict[str, Any]:
    """The 5B-2 labor, shift, and register model, extended with the capacity columns and link rows."""
    # Zero-requirement segments on the refinement: 5B-2 then adds only register rows for coverage, and its
    # breakpoints include every demand-period and staffing-segment boundary.
    tiling = [StaffingSegment(f"piece-{index}", piece.start_minute, piece.end_minute, 0)
              for index, piece in enumerate(pieces)]
    base = _build_model(horizon, employees, rules, tiling, patterns, cases)
    points, cover = _interval_cover(horizon, tiling, patterns)
    matrix = base["matrix"].tocoo()
    rows, cols, values = list(matrix.row), list(matrix.col), list(matrix.data)
    row_lb, row_ub = list(base["row_lb"]), list(base["row_ub"])
    objective, lower, upper = list(base["objective"]), list(base["lower"]), list(base["upper"])
    labor_columns = len(objective)
    starts = [piece.start_minute for piece in pieces]
    intervals: list[dict[str, Any]] = []
    for index, (start, end) in enumerate(zip(points, points[1:])):
        if not horizon.start_minute <= start < horizon.end_minute:
            continue
        piece = _piece_at(pieces, starts, start)
        options = []
        for servers in capacity.candidates():
            evaluated = capacity.evaluate(start, end, piece.period, servers)
            if evaluated["admissible"]:
                column = len(objective)
                objective.append(float(evaluated["waiting_cost"]))
                lower.append(0.0)
                upper.append(1.0)
                options.append((servers, column, evaluated))
        link = len(row_lb)
        for column in cover[index]:
            rows.append(link)
            cols.append(column)
            values.append(1)
        for servers, column, _ in options:
            if servers:
                rows.append(link)
                cols.append(column)
                values.append(-servers)
        row_lb.append(0.0)
        row_ub.append(0.0)
        choose = len(row_lb)
        for _, column, _ in options:
            rows.append(choose)
            cols.append(column)
            values.append(1)
        row_lb.append(1.0)
        row_ub.append(1.0)
        intervals.append({"index": index, "start_minute": start, "end_minute": end, "piece": piece,
                          "options": options, "possible_employees": len({patterns[q].employee_id for q in cover[index]})})
    full = coo_array((np.array(values, dtype=np.int64), (np.array(rows, dtype=np.int64), np.array(cols, dtype=np.int64))),
                     shape=(len(row_lb), len(objective))).tocsr()
    size = dict(base["size"])
    size.update(variables=len(objective), integer_variables=len(objective), constraints=len(row_lb),
                nonzeros=int(full.nnz), capacity_variables=len(objective) - labor_columns,
                intervals_inside_horizon=len(intervals))
    return {
        "matrix": full,
        "row_lb": np.array(row_lb, dtype=float),
        "row_ub": np.array(row_ub, dtype=float),
        "objective": np.array(objective, dtype=float),
        "lower": np.array(lower, dtype=float),
        "upper": np.array(upper, dtype=float),
        "split_columns": base["split_columns"],
        "labor_columns": labor_columns,
        "intervals": intervals,
        "size": size,
    }


def _merge_rows(rows: list[dict[str, Any]], keys: Sequence[str]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for row in rows:
        last = merged[-1] if merged else None
        if last is not None and last["end_minute"] == row["start_minute"] and all(last[k] == row[k] for k in keys):
            last["end_minute"] = row["end_minute"]
        else:
            merged.append(dict(row))
    return merged


def _certificates(horizon: OperatingHorizon, pieces: Sequence[_Piece], capacity: _Capacity,
                  patterns: Sequence[RosterPattern] | None) -> list[dict[str, Any]]:
    """Exact proofs of infeasibility that need no solver."""
    found: list[dict[str, Any]] = []
    empty = []
    for piece in pieces:
        evaluated = [capacity.evaluate(piece.start_minute, piece.end_minute, piece.period, c) for c in capacity.candidates()]
        if not any(item["admissible"] for item in evaluated):
            empty.append({"start_minute": piece.start_minute, "end_minute": piece.end_minute,
                          "demand_period_id": piece.period.period_id,
                          "candidate_counts": [item["servers"] for item in evaluated],
                          "violations": {str(item["servers"]): item["violations"] for item in evaluated}})
    if empty:
        found.append({"code": "NO_ADMISSIBLE_CAPACITY", "register_count": capacity.register_count,
                      "min_servers": capacity.planning.min_servers, "max_servers": capacity.planning.max_servers,
                      "intervals": empty, "reason": (
                          "No server count within the bounds and the registers passes stability, the utilization "
                          "target, and the maximum wait here, so no roster can be admissible.")})
    if patterns is None:
        return found
    tiling = [StaffingSegment(f"piece-{index}", piece.start_minute, piece.end_minute, 0)
              for index, piece in enumerate(pieces)]
    points, cover = _interval_cover(horizon, tiling, patterns)
    starts = [piece.start_minute for piece in pieces]
    short = []
    for index, (start, end) in enumerate(zip(points, points[1:])):
        if not horizon.start_minute <= start < horizon.end_minute:
            continue
        piece = _piece_at(pieces, starts, start)
        smallest = next((c for c in capacity.candidates()
                         if capacity.evaluate(start, end, piece.period, c)["admissible"]), None)
        possible = len({patterns[column].employee_id for column in cover[index]})
        if smallest is not None and possible < smallest:
            short.append({"start_minute": start, "end_minute": end, "smallest_admissible_servers": smallest,
                          "max_possible_active": possible})
    if short:
        found.append({"code": "INSUFFICIENT_WORKFORCE",
                      "intervals": _merge_rows(short, ("smallest_admissible_servers", "max_possible_active")),
                      "reason": ("Fewer employees have any admissible pattern active in these intervals than the "
                                 "smallest admissible server count; each employee staffs at most one server at an "
                                 "instant.")})
    return found


# ── Verification ────────────────────────────────────────────────────────────


def _verify(model: dict[str, Any], x: np.ndarray, horizon: OperatingHorizon, demand_periods: Sequence[DemandPeriod],
            staffing_segments: Sequence[StaffingSegment], employees: Sequence[Employee], rules: WorkforceRules,
            patterns: Sequence[RosterPattern], planning: PlanningConfig, grid: int) -> dict[str, Any]:
    """Exact checks of a solver vector; the plan is FEASIBLE only when every check passes."""
    checks: list[str] = []

    def failed(reason: str, **extra: Any) -> dict[str, Any]:
        return {"passed": False, "failure": reason, "checks": checks, **extra}

    deviation = float(np.max(np.abs(x - np.rint(x)))) if x.size else 0.0
    if deviation > INTEGRALITY_TOLERANCE:
        return failed(f"A variable is {deviation:.3g} from an integer, above {INTEGRALITY_TOLERANCE}.")
    checks.append(f"integrality: largest deviation {deviation:.3g} <= {INTEGRALITY_TOLERANCE}")
    values = np.rint(x).astype(np.int64)
    if np.any(values < model["lower"]) or np.any(values > model["upper"]):
        return failed("The rounded vector breaks a variable bound.")
    activity = model["matrix"] @ values
    if np.any(activity < model["row_lb"]) or np.any(activity > model["row_ub"]):
        return failed("The rounded vector breaks a model constraint.")
    checks.append("every bound and constraint holds exactly in integer arithmetic")

    chosen = [patterns[q] for q in range(len(patterns)) if values[q] == 1]
    order = {employee.employee_id: index for index, employee in enumerate(employees)}
    chosen.sort(key=lambda item: (order[item.employee_id], item.start_minute))
    roster = [pattern.as_shift() for pattern in chosen]
    independent = evaluate_planning_cost(horizon, demand_periods, staffing_segments, employees, rules, roster,
                                         planning=planning, break_start_granularity_minutes=grid)
    extra = {"roster": roster, "independent": independent}
    evaluation = independent["roster_evaluation"]
    if evaluation["violations"]:
        return failed("The 5B-1 evaluation found violations: "
                      + ", ".join(item["code"] for item in evaluation["violations"]) + ".", **extra)
    if evaluation["register_check"]["exceeded"]:
        return failed("The 5B-1 evaluation found more active servers than registers.", **extra)
    checks.append("5B-1 evaluate_roster: no violation, no register excess")

    steps = evaluation["active_server_steps"]
    step_starts = [step["start_minute"] for step in steps]
    selected = []
    for interval in model["intervals"]:
        picked = [(servers, row) for servers, column, row in interval["options"] if values[column] == 1]
        if len(picked) != 1:
            return failed(f"Interval {interval['start_minute']}-{interval['end_minute']} does not select exactly one "
                          "server count.", **extra)
        servers, row = picked[0]
        on_duty = _count_at(steps, step_starts, interval["start_minute"])
        if on_duty != servers:
            return failed(f"The model selects {servers} servers in {interval['start_minute']}-{interval['end_minute']}, "
                          f"but 5B-1 counts {on_duty} employees on duty.", **extra)
        selected.append({"start_minute": interval["start_minute"], "end_minute": interval["end_minute"],
                         "servers": servers, "waiting_cost": row["waiting_cost"]})
    checks.append("the selected server count equals the 5B-1 on-duty count on every interval inside the horizon")
    if not independent["in_integrated_feasible_set"]:
        return failed("The independent evaluation rejects the plan: " + " ".join(independent["feasible_set_reasons"]),
                      **extra)
    checks.append("every stretch of the horizon has an admissible on-duty count (independent evaluation)")

    minutes_by_id = {row["employee_id"]: row["minutes"] for row in evaluation["employees"]}
    for who, (regular, overtime, _) in model["split_columns"].items():
        expected = minutes_by_id[who]
        if (values[regular], values[overtime]) != (expected["regular_paid_minutes"], expected["overtime_paid_minutes"]):
            return failed(f"The model's regular/overtime split for {who} differs from the 5B-1 minutes.", **extra)
    if model["split_columns"]:
        checks.append("model regular and overtime minutes equal the 5B-1 minutes")

    if independent["labor_cost"] is None or independent["waiting_cost"] is None:
        return failed("The independent evaluation withheld a cost: " + " ".join(independent["withheld_reasons"]), **extra)
    split = model["labor_columns"]
    model_labor = math.fsum(float(model["objective"][q]) * int(values[q]) for q in range(split) if values[q])
    model_waiting = math.fsum(float(model["objective"][q]) * int(values[q])
                              for q in range(split, values.size) if values[q])
    for label, exact, modeled in (("Wages", independent["labor_cost"]["total"], model_labor),
                                  ("Waiting cost", independent["waiting_cost"]["total"], model_waiting)):
        if abs(exact - modeled) > COST_CONSISTENCY_RELATIVE_TOLERANCE * max(1.0, abs(exact)):
            return failed(f"{label} from the independent evaluation ({exact}) differs from the model ({modeled}).",
                          **extra)
    checks.append("wages from the 5B-1 minutes equal the model's labor terms, charged once")
    checks.append("waiting cost from the independent evaluation equals the model's capacity terms")
    return {"passed": True, "failure": None, "checks": checks, "selected": selected,
            "model_labor": model_labor, "model_waiting": model_waiting, **extra}


# ── Entry point ─────────────────────────────────────────────────────────────


def optimize_integrated_plan(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    staffing_segments: Sequence[StaffingSegment],
    employees: Sequence[Employee],
    rules: WorkforceRules,
    *,
    planning: PlanningConfig,
    config: RosterOptimizationConfig,
) -> dict[str, Any]:
    """Minimise wages plus analytical waiting cost over rosters and the server counts they put on duty.

    The staffing segments' server counts are not used: the segments only group the report and add
    breakpoints. Their bounds must tile the horizon inside the demand periods, as in Phase 1.
    """
    validate_timeline(horizon, demand_periods, staffing_segments)
    validate_workforce_inputs(horizon, employees, rules, [])
    validate_planning_config(planning)
    validate_roster_config(config)
    shift_rules = rules.shift_rules
    capacity = _Capacity(planning, rules.register_count)
    pieces = _refinement(horizon, demand_periods, staffing_segments)
    highs = _highs_details()
    result: dict[str, Any] = {
        "status": None,
        "feasibility": UNKNOWN,
        "status_reason": None,
        "roster": None,
        "roster_evaluation": None,
        "planning_cost": None,
        "labor_cost": None,
        "waiting_cost": None,
        "capacity": None,
        "optimality": None,
        "uniqueness": "NOT_ESTABLISHED",
        "uniqueness_note": UNIQUENESS_NOTE,
        "missing": [],
        "infeasibility_certificates": [],
        "verification": None,
        "solver": {
            "name": "HiGHS via scipy.optimize.milp",
            "scipy_version": scipy.__version__,
            "highs_version": highs["version"],
            "run": False,
            "options": {"presolve": True, "mip_rel_gap": config.mip_rel_gap,
                        "time_limit_seconds": config.time_limit_seconds},
            "unchanged_highs_defaults": highs["unchanged_defaults"],
            "integrality_tolerance": INTEGRALITY_TOLERANCE,
        },
        "model": None,
        "formulation": dict(FORMULATION),
        "scope": SCOPE_NOTE,
        "provenance": {
            "optimizer_version": OPTIMIZER_VERSION,
            "planning": asdict(planning),
            "config": asdict(config),
            "inputs": {"horizon": asdict(horizon), "demand_periods": [asdict(p) for p in demand_periods],
                       "staffing_segments": [asdict(s) for s in staffing_segments]},
            "capacity": CAPACITY_NOTE,
            "labor": LABOR_NOTE,
            "break_grid": (f"Breaks start only at clock minutes that are multiples of "
                           f"{config.break_start_granularity_minutes}; the result is optimal over rosters on this grid."),
            "time_unit": "whole minutes since midnight; intervals are [start, end); rates are per hour",
        },
    }

    def finish(status: str, reason: str, feasibility: str = UNKNOWN) -> dict[str, Any]:
        result.update(status=status, status_reason=reason, feasibility=feasibility)
        return result

    started = time.perf_counter()
    generated = enumerate_patterns(employees, rules, config.break_start_granularity_minutes, config.max_patterns)
    patterns: list[RosterPattern] | None = generated["patterns"]
    generation_seconds = time.perf_counter() - started
    complete_patterns = patterns is not None and not generated["missing_break_rules"]
    certificates = _certificates(horizon, pieces, capacity, patterns if complete_patterns else None)
    result["infeasibility_certificates"] = certificates
    result["missing"] = [{"employee_id": item["employee_id"], "field": "break_rules", "reason": (
        f"An admissible {item['length_minutes']}-minute shift ({item['start_minute']}-{item['end_minute']}) has no "
        "break rule, so its breaks are unknown.")} for item in generated["missing_break_rules"]]
    result["model"] = {"patterns": None if patterns is None else len(patterns),
                       "pattern_generation_seconds": generation_seconds,
                       "pattern_limit": config.max_patterns,
                       "shifts_without_break_placement": generated["shifts_without_break_placement"]}
    if certificates:
        return finish(INFEASIBLE, "Proved infeasible without the solver: "
                      + ", ".join(item["code"] for item in certificates) + ".", INFEASIBLE)
    if patterns is None:
        return finish(PATTERN_LIMIT_EXCEEDED, f"More than {config.max_patterns} admissible patterns; nothing was "
                                              "solved and no pattern was dropped.")
    if result["missing"]:
        return finish(INCOMPLETE, "Some admissible shift lengths have no break rule; nothing was solved.")

    cases: dict[str, tuple[str, int]] = {}
    labor_cases = []
    for employee in employees:
        own = [pattern for pattern in patterns if pattern.employee_id == employee.employee_id]
        maximum = max_paid_minutes(own, shift_rules.max_shifts_per_employee,
                                   int(shift_rules.min_minutes_between_shifts or 0)) if own else 0
        case, lacking = _labor_case(employee, bool(own), maximum)
        cases[employee.employee_id] = (case, maximum)
        result["missing"] += lacking
        labor_cases.append({"employee_id": employee.employee_id, "patterns": len(own), "max_paid_minutes": maximum,
                            "labor_case": case})
    if planning.waiting_cost_per_customer_hour is None and _waiting_needed(horizon, demand_periods):
        result["missing"].append({"employee_id": None, "field": "waiting_cost_per_customer_hour", "reason": (
            "Customers arrive during the horizon, so every admissible plan has a positive expected waiting time "
            "to price.")})
    result["model"]["labor_cases"] = labor_cases
    if result["missing"]:
        return finish(INCOMPLETE, "The objective needs values that were not supplied; nothing was solved and no "
                                  "cost was invented.")

    started = time.perf_counter()
    model = _build_integrated_model(horizon, employees, rules, pieces, patterns, cases, capacity)
    result["model"].update(model["size"], build_seconds=time.perf_counter() - started)
    options: dict[str, Any] = {"presolve": True, "mip_rel_gap": float(config.mip_rel_gap)}
    if config.time_limit_seconds is not None:
        options["time_limit"] = float(config.time_limit_seconds)
    started = time.perf_counter()
    response = milp(model["objective"], integrality=np.ones(model["objective"].size),
                    bounds=Bounds(model["lower"], model["upper"]),
                    constraints=LinearConstraint(model["matrix"].astype(float), model["row_lb"], model["row_ub"]),
                    options=options)
    solver_status = int(response.status)
    result["solver"].update(
        run=True,
        status_code=solver_status,
        message=str(response.message),
        objective=None if response.fun is None else float(response.fun),
        dual_bound=None if response.mip_dual_bound is None else float(response.mip_dual_bound),
        mip_gap=None if response.mip_gap is None else float(response.mip_gap),
        node_count=None if response.mip_node_count is None else int(response.mip_node_count),
        wall_seconds=time.perf_counter() - started,
    )
    values = None if response.x is None else np.asarray(response.x, dtype=float)

    if solver_status == 2:
        certificates.append({"code": "SOLVER_PROVED_INFEASIBLE", "reason": str(response.message)})
        return finish(INFEASIBLE, "HiGHS proved the model infeasible.", INFEASIBLE)
    if solver_status in (3, 4):
        return finish(SOLVER_ERROR, f"HiGHS stopped without a usable answer (status {solver_status}).")
    if values is None:
        if solver_status == 1:
            return finish(NO_SOLUTION_FOUND, "A solver limit was reached before any feasible plan was found; "
                                             "feasibility is unknown, not disproved.")
        return finish(SOLVER_ERROR, "HiGHS reported success without a solution vector.")

    verification = _verify(model, values, horizon, demand_periods, staffing_segments, employees, rules, patterns,
                           planning, config.break_start_granularity_minutes)
    result["verification"] = {key: verification.get(key) for key in ("passed", "failure", "checks")}
    if "roster" in verification:
        result["roster"] = [asdict(shift) for shift in verification["roster"]]
        result["roster_evaluation"] = verification["independent"]["roster_evaluation"]
    if not verification["passed"]:
        return finish(VERIFICATION_FAILED, f"The solver's answer failed exact verification: {verification['failure']}")

    independent = verification["independent"]
    labor, waiting = independent["labor_cost"], independent["waiting_cost"]
    total = independent["planning_cost"]
    result["labor_cost"] = labor
    result["waiting_cost"] = waiting
    result["planning_cost"] = {
        "total": total, "labor_cost": labor["total"], "waiting_cost": waiting["total"],
        "excluded": "Phase 2's server cost per server-hour (server capacity is paid only through wages).",
        "note": "Caller's currency. Analytical planning cost, not the continuous-DES operating cost.",
    }
    result["capacity"] = {key: independent[key] for key in (
        "capacity", "capacity_by_staffing_segment", "active_server_minutes_in_horizon",
        "active_server_minutes_outside_horizon", "server_minutes_above_smallest_admissible")}
    result["capacity"]["note"] = CAPACITY_NOTE
    bound = result["solver"]["dual_bound"]
    distance = None if bound is None else total - bound
    optimality = {
        "proven": solver_status == 0,
        "verified_objective": total,
        "solver_objective": result["solver"]["objective"],
        "model_objective_at_rounded_vector": verification["model_labor"] + verification["model_waiting"],
        "dual_bound": bound,
        "gap_to_dual_bound": distance,
        "relative_gap_to_dual_bound": None if distance is None or total == 0 else distance / abs(total),
        "tolerances": {"mip_rel_gap": config.mip_rel_gap, "unchanged_highs_defaults": highs["unchanged_defaults"]},
    }
    if solver_status == 0:
        optimality["basis"] = (f"HiGHS status 0: optimal within mip_rel_gap {config.mip_rel_gap} and the unchanged "
                               "HiGHS mip_abs_gap, for this model and break grid.")
    else:
        optimality["basis"] = "A solver limit stopped the search; this feasible plan is not proven optimal."
    result["optimality"] = optimality
    if solver_status == 0:
        return finish(OPTIMAL, "Optimal for this model within the reported tolerances; verified exactly.", FEASIBLE)
    return finish(FEASIBLE_NOT_PROVEN_OPTIMAL, "Feasible and verified exactly, but not proven optimal: "
                                               + str(response.message), FEASIBLE)


# ── Integrated versus sequential ────────────────────────────────────────────


def _roster_from_rows(rows: Sequence[dict[str, Any]]) -> list[ScheduledShift]:
    return [ScheduledShift(row["employee_id"], row["start_minute"], row["end_minute"],
                           tuple(ScheduledBreak(item["name"], item["start_minute"]) for item in row["breaks"]))
            for row in rows]


def compare_with_sequential(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    staffing_segments: Sequence[StaffingSegment],
    employees: Sequence[Employee],
    rules: WorkforceRules,
    *,
    capacity_config: CapacityConfig,
    planning: PlanningConfig,
    config: RosterOptimizationConfig,
    integrated: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the sequential pipeline (Phase 2, then 5B-2) and compare it with the integrated plan on one objective.

    Both rosters are priced by ``evaluate_planning_cost``. "No worse" is claimed only when the sequential
    roster is in the integrated model's feasible set and the verified integrated cost is at most the
    sequential cost.
    """
    validate_planning_config(planning)
    mismatched = [name for name in ("waiting_cost_per_customer_hour", "target_utilization", "max_wait_minutes",
                                    "min_servers", "max_servers")
                  if getattr(capacity_config, name) != getattr(planning, name)]
    comparison: dict[str, Any] = {"comparable": not mismatched, "mismatched_settings": mismatched,
                                  "integrated_no_worse": None, "basis": None}
    if mismatched:
        comparison["basis"] = ("The Phase 2 settings differ from the planning settings, so the two methods do not "
                               "share constraints: " + ", ".join(mismatched) + ".")
        return {"comparison": comparison, "sequential": None, "integrated": integrated}

    plan = optimize_shared_capacity(horizon, demand_periods, staffing_segments, capacity_config)
    sequential: dict[str, Any] = {
        "phase2_selected_servers": [None if row["selected"] is None else row["selected"]["servers"]
                                    for row in plan["segments"]],
        "phase2_objective_note": ("Phase 2's own totals (server charge plus waiting at the selected counts) are a "
                                  "different objective and are not compared."),
        "phase2_totals": plan["totals"]["selected"],
        "roster_result": None,
        "evaluation": None,
    }
    if plan["totals"]["plan_complete"]:
        roster_result = optimize_roster_for_capacity_plan(horizon, employees, rules, plan, config=config)
        sequential["roster_result"] = roster_result
        if roster_result["feasibility"] == FEASIBLE:
            sequential["evaluation"] = evaluate_planning_cost(
                horizon, demand_periods, staffing_segments, employees, rules,
                _roster_from_rows(roster_result["roster"]), planning=planning,
                break_start_granularity_minutes=config.break_start_granularity_minutes)
    if integrated is None:
        integrated = optimize_integrated_plan(horizon, demand_periods, staffing_segments, employees, rules,
                                              planning=planning, config=config)

    evaluation = sequential["evaluation"]
    if evaluation is None:
        comparison["basis"] = "The sequential pipeline produced no verified roster."
    elif not evaluation["in_integrated_feasible_set"]:
        comparison["basis"] = ("The sequential roster is outside the integrated feasible set: "
                               + " ".join(evaluation["feasible_set_reasons"]))
    elif evaluation["planning_cost"] is None:
        comparison["basis"] = "The sequential roster's planning cost is withheld: " + " ".join(evaluation["withheld_reasons"])
    elif integrated["feasibility"] != FEASIBLE:
        comparison["basis"] = f"The integrated run has no verified plan (status {integrated['status']})."
    else:
        mine, theirs = integrated["planning_cost"]["total"], evaluation["planning_cost"]
        difference = mine - theirs
        tolerance = COST_CONSISTENCY_RELATIVE_TOLERANCE * max(1.0, abs(theirs))
        comparison.update(integrated_planning_cost=mine, sequential_planning_cost=theirs, difference=difference)
        bound = integrated["optimality"]["dual_bound"]
        if bound is not None:
            comparison["sequential_at_or_above_dual_bound"] = theirs >= bound - tolerance
        if difference <= tolerance:
            comparison["integrated_no_worse"] = True
            comparison["basis"] = ("The sequential roster is in the integrated feasible set, and both rosters were "
                                   "priced exactly on the same objective; the integrated cost is not higher.")
        else:
            comparison["integrated_no_worse"] = False
            gap = integrated["solver"]["options"]["mip_rel_gap"]
            defaults = integrated["solver"]["unchanged_highs_defaults"] or {}
            allowed = max(gap * abs(mine), float(defaults.get("mip_abs_gap") or 0.0)) + tolerance
            if integrated["status"] == OPTIMAL and difference > allowed:
                comparison["basis"] = ("CONFLICTING: a feasible sequential roster costs less than a plan proven optimal, "
                                       "beyond the solver's optimality tolerance.")
            elif integrated["status"] == OPTIMAL:
                comparison["basis"] = ("The sequential roster costs less by an amount within the solver's optimality "
                                       "tolerance (mip_rel_gap and mip_abs_gap).")
            else:
                comparison["basis"] = "The integrated plan is not proven optimal, and the sequential roster costs less."
    return {"comparison": comparison, "sequential": sequential, "integrated": integrated}
