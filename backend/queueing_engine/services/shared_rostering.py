"""Sequential shared-queue rostering MILP (Phase 5B-2 of the shared-queue enhancement).

Chooses employee shift-and-break patterns that minimise labor cost while the scheduled active
servers meet the required servers at every instant (Phase 2's selected counts) and never exceed
the physical registers. It uses the 5B-1 workforce inputs, rules, and definitions, solves with
``scipy.optimize.milp`` (HiGHS), and checks every solver answer exactly with the 5B-1 roster
evaluation before calling it feasible.

The roster is **scheduled**, not simulated, and "optimal" means optimal for this model, the
caller's break grid, and the reported solver tolerances; it is not optimal for the real queue.

Spec: docs/superpowers/specs/2026-09-26-shared-queue-sequential-rostering.md.
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

from backend.queueing_engine.services.shared_segments import (
    MINUTES_PER_DAY,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
)
from backend.queueing_engine.services.shared_workforce import (
    BreakRequirement,
    BreakRule,
    Employee,
    ScheduledBreak,
    ScheduledShift,
    WorkforceRules,
    evaluate_roster,
    validate_workforce_inputs,
)
from backend.queueing_engine.simulation.shared_continuous_des import staffing_from_capacity_result

OPTIMIZER_VERSION = "novaq-shared-sequential-rostering-v1"

# Result statuses.
OPTIMAL = "OPTIMAL"
FEASIBLE_NOT_PROVEN_OPTIMAL = "FEASIBLE_NOT_PROVEN_OPTIMAL"
NO_SOLUTION_FOUND = "NO_SOLUTION_FOUND"
INFEASIBLE = "INFEASIBLE"
INCOMPLETE = "INCOMPLETE"
PATTERN_LIMIT_EXCEEDED = "PATTERN_LIMIT_EXCEEDED"
SOLVER_ERROR = "SOLVER_ERROR"
VERIFICATION_FAILED = "VERIFICATION_FAILED"
# Feasibility labels. FEASIBLE is given only after the exact verification passes.
FEASIBLE, UNKNOWN = "FEASIBLE", "UNKNOWN"

# HiGHS 1.12.0 default mip_feasibility_tolerance, which this module does not change. A solver
# vector further than this from an integer is not rounded.
INTEGRALITY_TOLERANCE = 1e-6
# Floating-point summation only: the labor cost from the 5B-1 minutes against the model objective.
COST_CONSISTENCY_RELATIVE_TOLERANCE = 1e-9

SCOPE_NOTE = (
    "Sequential rostering: Phase 2's selected server counts are the coverage target. The roster is "
    "scheduled, not simulated, and has not been validated by the DES. Optimal means optimal for this "
    "model, the break grid, and the reported solver tolerances, not for the real queue."
)
SURPLUS_NOTE = (
    "Surplus server-minutes are active servers above the requirement inside the operating horizon. "
    "Their cost is the wages already in the labor cost; no separate surplus cost is charged, and "
    "surplus is not attributed to individual employees. Active time outside the horizon has no "
    "requirement and is reported separately."
)
UNIQUENESS_NOTE = (
    "The solver returns one roster. Other rosters with the same objective may exist, and which one "
    "is returned can depend on the solver version."
)
FORMULATION = {
    "decision_variables": "x_q in {0,1} per admissible pattern; with split shifts allowed, also R_e, O_e "
                          "integer and w_e in {0,1} for employees whose paid time can split into regular and "
                          "overtime (with one shift a day each pattern's split is known and costed exactly).",
    "objective": "minimise sum over employees of (regular rate x regular minutes + overtime rate x "
                 "overtime minutes) / 60",
    "coverage": "sum_q a[q,i] x_q >= required servers, every elementary interval i inside the horizon",
    "registers": "sum_q a[q,i] x_q <= register_count, every elementary interval i of the day",
    "max_shifts": "sum over an employee's patterns of x_q <= max_shifts_per_employee",
    "split_shifts": "when more than one shift is allowed: for each shift start t of an employee, the "
                    "patterns with start <= t < end + min_minutes_between_shifts sum to at most 1",
    "regular_overtime": "one shift a day: pattern cost (r min(p, theta) + o max(0, p - theta)) / 60; split "
                        "shifts: P_e = R_e + O_e, R_e >= theta_e w_e, O_e <= (max paid - theta_e) w_e, "
                        "0 <= R_e <= theta_e, so R_e = min(P_e, theta_e) exactly",
    "time": "whole minutes since midnight; intervals are [start, end); rates are per hour",
}


# ── Inputs ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RosterOptimizationConfig:
    """Run settings supplied by the caller; none has a default."""

    break_start_granularity_minutes: int  # breaks start on clock multiples of this, from midnight
    time_limit_seconds: float | None  # None means no time limit
    mip_rel_gap: float  # HiGHS relative gap for proving optimality
    max_patterns: int  # the run stops (never truncates) when more patterns are admissible


@dataclass(frozen=True)
class RosterPattern:
    """One admissible shift of one employee, with every break of its rule placed."""

    employee_id: str
    start_minute: int
    end_minute: int
    breaks: tuple[ScheduledBreak, ...]
    active: tuple[tuple[int, int], ...]  # on shift and not on break, in clock order
    paid_minutes: int

    def as_shift(self) -> ScheduledShift:
        return ScheduledShift(self.employee_id, self.start_minute, self.end_minute, self.breaks)


def _whole(value: object) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def _finite(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_config(config: object) -> None:
    """Raise ``SharedSegmentError`` listing every configuration problem."""
    if not isinstance(config, RosterOptimizationConfig):
        raise SharedSegmentError(["config must be a RosterOptimizationConfig."])
    problems = []
    grid = config.break_start_granularity_minutes
    if not _whole(grid) or not 1 <= grid <= MINUTES_PER_DAY:
        problems.append(f"break_start_granularity_minutes must be a whole number from 1 to {MINUTES_PER_DAY}.")
    limit = config.time_limit_seconds
    if limit is not None and (not _finite(limit) or limit <= 0):
        problems.append("time_limit_seconds must be a finite number above 0, or None for no limit.")
    if not _finite(config.mip_rel_gap) or config.mip_rel_gap < 0:
        problems.append("mip_rel_gap must be a finite number, 0 or more.")
    if not _whole(config.max_patterns) or config.max_patterns < 1:
        problems.append("max_patterns must be a whole number, 1 or more.")
    if problems:
        raise SharedSegmentError(problems)


# ── Pattern generation ──────────────────────────────────────────────────────


class _PatternLimit(Exception):
    pass


def _apart(start: int, duration: int, other_start: int, other_duration: int, gap: int) -> bool:
    """The 5B-1 break rule for a pair: no overlap and at least ``gap`` minutes between them."""
    if start <= other_start:
        return other_start - (start + duration) >= gap
    return start - (other_start + other_duration) >= gap


def _break_placements(start: int, end: int, rule: BreakRule, grid: int,
                      budget: int) -> list[tuple[tuple[BreakRequirement, int], ...]]:
    """Every placement of the rule's breaks on the grid that 5B-1 accepts for this shift."""
    options = []
    for item in rule.breaks:
        low = start + item.earliest_start_offset_minutes
        high = min(start + item.latest_start_offset_minutes, end - item.duration_minutes)
        first = -(-low // grid) * grid
        options.append([(item, minute) for minute in range(first, high + 1, grid)])
    placements: list[tuple[tuple[BreakRequirement, int], ...]] = []
    placed: list[tuple[BreakRequirement, int]] = []

    def extend(depth: int) -> None:
        if depth == len(options):
            placements.append(tuple(placed))
            if len(placements) > budget:
                raise _PatternLimit
            return
        for item, minute in options[depth]:
            if all(_apart(minute, item.duration_minutes, other_minute, other.duration_minutes, rule.min_gap_minutes)
                   for other, other_minute in placed):
                placed.append((item, minute))
                extend(depth + 1)
                placed.pop()

    extend(0)
    return placements


def _active(start: int, end: int, cuts: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    pieces = []
    cursor = start
    for cut_start, cut_end in sorted(cuts):
        if cut_start > cursor:
            pieces.append((cursor, cut_start))
        cursor = max(cursor, cut_end)
    if cursor < end:
        pieces.append((cursor, end))
    return tuple(pieces)


def enumerate_patterns(employees: Sequence[Employee], rules: WorkforceRules,
                       break_start_granularity_minutes: int, max_patterns: int) -> dict[str, Any]:
    """Every admissible pattern, the admissible shifts that have no break rule, and the cap outcome."""
    shift_rules = rules.shift_rules
    grid = shift_rules.boundary_granularity_minutes
    first = -(-shift_rules.earliest_start_minute // grid) * grid
    points = range(first, shift_rules.latest_end_minute + 1, grid)
    patterns: list[RosterPattern] = []
    missing_rules: list[dict[str, Any]] = []
    shifts_without_placement = 0
    try:
        for employee in employees:
            for start in points:
                for end in points:
                    length = end - start
                    if not shift_rules.min_shift_minutes <= length <= shift_rules.max_shift_minutes:
                        continue
                    if not any(window.start_minute <= start and end <= window.end_minute
                               for window in employee.availability):
                        continue
                    rule = next((item for item in rules.break_rules
                                 if item.min_shift_minutes <= length <= item.max_shift_minutes), None)
                    if rule is None:
                        missing_rules.append({"employee_id": employee.employee_id, "start_minute": start,
                                              "end_minute": end, "length_minutes": length})
                        continue
                    placements = _break_placements(start, end, rule, break_start_granularity_minutes,
                                                   max_patterns - len(patterns))
                    if not placements:
                        shifts_without_placement += 1
                    unpaid = sum(item.duration_minutes for item in rule.breaks if not item.paid)
                    for placement in placements:
                        patterns.append(RosterPattern(
                            employee_id=employee.employee_id,
                            start_minute=start,
                            end_minute=end,
                            breaks=tuple(ScheduledBreak(item.name, minute) for item, minute in placement),
                            active=_active(start, end, [(minute, minute + item.duration_minutes)
                                                        for item, minute in placement]),
                            paid_minutes=length - unpaid,
                        ))
    except _PatternLimit:
        return {"patterns": None, "limit_exceeded": True, "missing_break_rules": missing_rules,
                "shifts_without_break_placement": shifts_without_placement}
    return {"patterns": patterns, "limit_exceeded": False, "missing_break_rules": missing_rules,
            "shifts_without_break_placement": shifts_without_placement}


def max_paid_minutes(patterns: Sequence[RosterPattern], max_shifts: int, rest_minutes: int) -> int:
    """Exact maximum paid minutes of one employee's day: at most ``max_shifts`` compatible shifts."""
    ordered = sorted({(item.start_minute, item.end_minute, item.paid_minutes) for item in patterns},
                     key=lambda item: (item[1], item[0]))
    ends = [end for _, end, _ in ordered]
    previous = [0] * (len(ordered) + 1)
    for _ in range(max_shifts):
        current = [0] * (len(ordered) + 1)
        for position, (start, _, paid) in enumerate(ordered, start=1):
            compatible = bisect.bisect_right(ends, start - rest_minutes)
            current[position] = max(current[position - 1], paid + previous[compatible])
        previous = current
    return previous[-1]


# ── Pay requirements ────────────────────────────────────────────────────────

NO_PATTERN, ZERO_PAID, OVERTIME_ONLY, REGULAR_ONLY, SPLIT, THRESHOLD_MISSING = (
    "NO_PATTERN", "ZERO_PAID", "OVERTIME_ONLY", "REGULAR_ONLY", "SPLIT", "THRESHOLD_MISSING")


def _labor_case(employee: Employee, has_pattern: bool, max_paid: int) -> tuple[str, list[dict[str, Any]]]:
    """How the employee's labor enters the objective, and the pay values it needs but lacks."""
    who, pay = employee.employee_id, employee.pay
    if not has_pattern:
        return NO_PATTERN, []
    if max_paid == 0:
        return ZERO_PAID, []
    threshold = pay.daily_regular_paid_minutes
    if threshold is None:
        missing = [{"employee_id": who, "field": "daily_regular_paid_minutes",
                    "reason": "Needed to split paid time into regular and overtime."}]
        missing += [{"employee_id": who, "field": field,
                     "reason": "Needed unless the missing threshold rules it out, which cannot be decided."}
                    for field in ("regular_rate_per_hour", "overtime_rate_per_hour") if getattr(pay, field) is None]
        return THRESHOLD_MISSING, missing
    case = OVERTIME_ONLY if threshold == 0 else REGULAR_ONLY if max_paid <= threshold else SPLIT
    needed = {OVERTIME_ONLY: ("overtime_rate_per_hour",), REGULAR_ONLY: ("regular_rate_per_hour",),
              SPLIT: ("regular_rate_per_hour", "overtime_rate_per_hour")}[case]
    reasons = {"regular_rate_per_hour": "Admissible plans include regular paid minutes.",
               "overtime_rate_per_hour": (f"Admissible plans reach {max_paid} paid minutes, above the "
                                          f"{threshold}-minute threshold.")}
    return case, [{"employee_id": who, "field": field, "reason": reasons[field]}
                  for field in needed if getattr(pay, field) is None]


# ── Model ───────────────────────────────────────────────────────────────────


def _required_at(segments: Sequence[StaffingSegment], minute: int) -> int:
    starts = [segment.start_minute for segment in segments]
    return int(segments[bisect.bisect_right(starts, minute) - 1].servers)


def _merge_certificate(rows: list[dict[str, int]]) -> list[dict[str, int]]:
    merged: list[dict[str, int]] = []
    for row in rows:
        last = merged[-1] if merged else None
        if (last is not None and last["end_minute"] == row["start_minute"]
                and last["required_servers"] == row["required_servers"]
                and last["max_possible_active"] == row["max_possible_active"]):
            last["end_minute"] = row["end_minute"]
        else:
            merged.append(dict(row))
    return merged


def _interval_cover(horizon: OperatingHorizon, segments: Sequence[StaffingSegment],
                    patterns: Sequence[RosterPattern]) -> tuple[list[int], list[list[int]]]:
    """Elementary intervals [points[i], points[i+1]) and the patterns active over each.

    The breakpoints include every pattern's active-interval ends, so each pattern is active over
    the whole of an elementary interval or not at all: interval constraints are exact in time.
    """
    points = sorted({horizon.start_minute, horizon.end_minute}
                    | {point for segment in segments for point in (segment.start_minute, segment.end_minute)}
                    | {point for pattern in patterns for piece in pattern.active for point in piece})
    position = {point: index for index, point in enumerate(points)}
    cover: list[list[int]] = [[] for _ in range(len(points) - 1)]
    for column, pattern in enumerate(patterns):
        for start, end in pattern.active:
            for index in range(position[start], position[end]):
                cover[index].append(column)
    return points, cover


def _build_model(horizon: OperatingHorizon, employees: Sequence[Employee], rules: WorkforceRules,
                 segments: Sequence[StaffingSegment], patterns: Sequence[RosterPattern],
                 cases: dict[str, tuple[str, int]]) -> dict[str, Any]:
    """The MILP arrays, with an integer copy of the constraint matrix for the exact check."""
    shift_rules = rules.shift_rules
    points, cover = _interval_cover(horizon, segments, patterns)
    interval_count = len(cover)

    rows: list[int] = []
    cols: list[int] = []
    values: list[int] = []
    row_lb: list[float] = []
    row_ub: list[float] = []

    def add_row(entries: list[tuple[int, int]], low: float, high: float) -> None:
        row = len(row_lb)
        for column, value in entries:
            rows.append(row)
            cols.append(column)
            values.append(value)
        row_lb.append(low)
        row_ub.append(high)

    coverage_rows = 0
    for index in range(interval_count):
        inside = horizon.start_minute <= points[index] < horizon.end_minute
        required = _required_at(segments, points[index]) if inside else 0
        if cover[index] or required > 0:
            add_row([(column, 1) for column in cover[index]], float(required), float(rules.register_count))
            coverage_rows += 1

    by_employee: dict[str, list[int]] = {}
    for column, pattern in enumerate(patterns):
        by_employee.setdefault(pattern.employee_id, []).append(column)
    objective = [0.0] * len(patterns)
    lower = [0.0] * len(patterns)
    upper = [1.0] * len(patterns)
    split_columns: dict[str, tuple[int, int, int]] = {}
    rest = int(shift_rules.min_minutes_between_shifts or 0)
    for employee in employees:
        who = employee.employee_id
        columns = by_employee.get(who, [])
        if not columns:
            continue
        add_row([(column, 1) for column in columns], -math.inf, float(shift_rules.max_shifts_per_employee))
        if shift_rules.max_shifts_per_employee > 1:
            for moment in sorted({patterns[column].start_minute for column in columns}):
                clique = [column for column in columns
                          if patterns[column].start_minute <= moment < patterns[column].end_minute + rest]
                add_row([(column, 1) for column in clique], -math.inf, 1.0)
        case, max_paid = cases[who]
        pay = employee.pay
        if case == REGULAR_ONLY or case == OVERTIME_ONLY:
            rate = pay.regular_rate_per_hour if case == REGULAR_ONLY else pay.overtime_rate_per_hour
            assert rate is not None  # guaranteed: missing pay stops the run before the model is built
            for column in columns:
                objective[column] = rate * patterns[column].paid_minutes / 60.0
        elif case == SPLIT and shift_rules.max_shifts_per_employee == 1:
            # One shift a day: each pattern's regular and overtime minutes are known exactly.
            threshold = pay.daily_regular_paid_minutes
            assert threshold is not None and pay.regular_rate_per_hour is not None
            assert pay.overtime_rate_per_hour is not None
            for column in columns:
                paid = patterns[column].paid_minutes
                objective[column] = (pay.regular_rate_per_hour * min(paid, threshold)
                                     + pay.overtime_rate_per_hour * max(0, paid - threshold)) / 60.0
        elif case == SPLIT:
            threshold = pay.daily_regular_paid_minutes
            assert threshold is not None and pay.regular_rate_per_hour is not None
            assert pay.overtime_rate_per_hour is not None
            regular, overtime, switch = len(objective), len(objective) + 1, len(objective) + 2
            split_columns[who] = (regular, overtime, switch)
            objective += [pay.regular_rate_per_hour / 60.0, pay.overtime_rate_per_hour / 60.0, 0.0]
            lower += [0.0, 0.0, 0.0]
            upper += [float(threshold), float(max_paid - threshold), 1.0]
            add_row([(column, patterns[column].paid_minutes) for column in columns]
                    + [(regular, -1), (overtime, -1)], 0.0, 0.0)
            add_row([(regular, 1), (switch, -threshold)], 0.0, math.inf)
            add_row([(overtime, 1), (switch, -(max_paid - threshold))], -math.inf, 0.0)
    matrix = coo_array((np.array(values, dtype=np.int64), (np.array(rows, dtype=np.int64),
                                                             np.array(cols, dtype=np.int64))),
                       shape=(len(row_lb), len(objective))).tocsr()
    return {
        "matrix": matrix,
        "row_lb": np.array(row_lb, dtype=float),
        "row_ub": np.array(row_ub, dtype=float),
        "objective": np.array(objective, dtype=float),
        "lower": np.array(lower, dtype=float),
        "upper": np.array(upper, dtype=float),
        "split_columns": split_columns,
        "size": {
            "patterns": len(patterns),
            "variables": len(objective),
            "integer_variables": len(objective),
            "constraints": len(row_lb),
            "coverage_and_register_rows": coverage_rows,
            "nonzeros": int(matrix.nnz),
            "elementary_intervals": interval_count,
        },
    }


def _certificates(horizon: OperatingHorizon, employees: Sequence[Employee], rules: WorkforceRules,
                  segments: Sequence[StaffingSegment], patterns: Sequence[RosterPattern] | None) -> list[dict[str, Any]]:
    """Exact proofs of infeasibility that need no solver."""
    found: list[dict[str, Any]] = []
    over = [{"segment_id": segment.segment_id, "start_minute": segment.start_minute, "end_minute": segment.end_minute,
             "required_servers": int(segment.servers)}
            for segment in segments if segment.servers > rules.register_count]
    if over:
        found.append({"code": "REQUIREMENT_EXCEEDS_REGISTERS", "register_count": rules.register_count, "segments": over,
                      "reason": "Required servers exceed the physical registers, which no roster can meet."})
    if patterns is None:
        return found
    points, cover = _interval_cover(horizon, segments, patterns)
    short = []
    for index, (start, end) in enumerate(zip(points, points[1:])):
        if not horizon.start_minute <= start < horizon.end_minute:
            continue
        required = _required_at(segments, start)
        possible = len({patterns[column].employee_id for column in cover[index]})
        if possible < required:
            short.append({"start_minute": start, "end_minute": end, "required_servers": required,
                          "max_possible_active": possible})
    if short:
        found.append({"code": "INSUFFICIENT_WORKFORCE", "intervals": _merge_certificate(short), "reason": (
            "Fewer employees have any admissible pattern active in these intervals than are required; each "
            "employee staffs at most one server at an instant.")})
    return found


# ── Solving and verification ────────────────────────────────────────────────


def _highs_details() -> dict[str, Any]:
    """HiGHS version and the defaults this module leaves unchanged; None when they cannot be read."""
    try:
        from scipy.optimize._highspy import _core  # private: read-only provenance

        options = _core.HighsOptions()
        return {"version": str(_core._Highs().version()),
                "unchanged_defaults": {"mip_abs_gap": float(options.mip_abs_gap),
                                       "mip_feasibility_tolerance": float(options.mip_feasibility_tolerance)}}
    except Exception:  # noqa: BLE001 - provenance only; the solve does not depend on it
        return {"version": None, "unchanged_defaults": None}


def _labor_rows(employees: Sequence[Employee], evaluation: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """Labor cost per rostered employee from the 5B-1 minutes; a reason when a needed rate is absent."""
    by_id = {employee.employee_id: employee for employee in employees}
    rows = []
    for row in evaluation["employees"]:
        if not row["shift_count"]:
            continue
        pay, minutes = by_id[row["employee_id"]].pay, row["minutes"]
        if minutes is None:
            return [], f"The 5B-1 evaluation withheld the hours of {row['employee_id']}."
        costs: dict[str, float] = {}
        for kind, rate in (("regular", pay.regular_rate_per_hour), ("overtime", pay.overtime_rate_per_hour)):
            amount = minutes[f"{kind}_paid_minutes"]
            if minutes["paid_employee_minutes"] == 0 or amount == 0:
                costs[f"{kind}_cost"] = 0.0  # zero minutes cost nothing whatever the rate
            elif amount is None or rate is None:
                return [], f"{row['employee_id']} has {kind} minutes without the pay values to cost them."
            else:
                costs[f"{kind}_cost"] = rate * amount / 60.0
        rows.append({
            "employee_id": row["employee_id"],
            "paid_minutes": minutes["paid_employee_minutes"],
            "regular_paid_minutes": minutes["regular_paid_minutes"],
            "overtime_paid_minutes": minutes["overtime_paid_minutes"],
            **costs,
            "labor_cost": costs["regular_cost"] + costs["overtime_cost"],
        })
    return rows, None


def _verify(model: dict[str, Any], x: np.ndarray, horizon: OperatingHorizon, employees: Sequence[Employee],
            rules: WorkforceRules, segments: Sequence[StaffingSegment],
            patterns: Sequence[RosterPattern]) -> dict[str, Any]:
    """Exact checks of a solver vector; the roster is FEASIBLE only when every check passes."""
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

    chosen = [patterns[column] for column in range(len(patterns)) if values[column] == 1]
    order = {employee.employee_id: index for index, employee in enumerate(employees)}
    chosen.sort(key=lambda item: (order[item.employee_id], item.start_minute))
    roster = [pattern.as_shift() for pattern in chosen]
    evaluation = evaluate_roster(horizon, employees, rules, roster, required_staffing=segments)
    extra = {"roster": roster, "evaluation": evaluation}
    if evaluation["violations"]:
        return failed("The 5B-1 evaluation found violations: "
                      + ", ".join(item["code"] for item in evaluation["violations"]) + ".", **extra)
    if not evaluation["coverage"]["fully_covered"]:
        return failed("The 5B-1 evaluation found a coverage shortfall.", **extra)
    if evaluation["register_check"]["exceeded"]:
        return failed("The 5B-1 evaluation found more active servers than registers.", **extra)
    checks.append("5B-1 evaluate_roster: no violation, no shortfall, no register excess")
    minutes_by_id = {row["employee_id"]: row["minutes"] for row in evaluation["employees"]}
    for who, (regular, overtime, _) in model["split_columns"].items():
        expected = minutes_by_id[who]
        if (values[regular], values[overtime]) != (expected["regular_paid_minutes"], expected["overtime_paid_minutes"]):
            return failed(f"The model's regular/overtime split for {who} differs from the 5B-1 minutes.", **extra)
    if model["split_columns"]:
        checks.append("model regular and overtime minutes equal the 5B-1 minutes")
    labor, reason = _labor_rows(employees, evaluation)
    if reason is not None:
        return failed(reason, **extra)
    exact = math.fsum(row["labor_cost"] for row in labor)
    model_value = math.fsum(float(coefficient) * int(value)
                            for coefficient, value in zip(model["objective"], values) if value)
    if abs(exact - model_value) > COST_CONSISTENCY_RELATIVE_TOLERANCE * max(1.0, abs(exact)):
        return failed(f"Labor cost from the 5B-1 minutes ({exact}) differs from the model objective ({model_value}).",
                      **extra)
    checks.append("labor cost from the 5B-1 minutes equals the model objective at the rounded vector")
    return {"passed": True, "failure": None, "checks": checks, "labor": labor, "verified_objective": exact,
            "model_objective_at_rounded": model_value, **extra}


# ── Entry points ────────────────────────────────────────────────────────────


def optimize_sequential_roster(
    horizon: OperatingHorizon,
    employees: Sequence[Employee],
    rules: WorkforceRules,
    required_staffing: Sequence[StaffingSegment],
    *,
    config: RosterOptimizationConfig,
) -> dict[str, Any]:
    """Minimise labor cost subject to coverage of ``required_staffing`` and the workforce rules."""
    return _optimize(horizon, employees, rules, required_staffing, config,
                     {"source": "required_staffing supplied by the caller"})


def optimize_roster_for_capacity_plan(
    horizon: OperatingHorizon,
    employees: Sequence[Employee],
    rules: WorkforceRules,
    capacity_plan: dict[str, Any],
    *,
    config: RosterOptimizationConfig,
) -> dict[str, Any]:
    """Use a complete Phase 2 plan's selected server counts as the coverage target."""
    plan_horizon = capacity_plan["provenance"]["inputs"]["horizon"]
    if not isinstance(horizon, OperatingHorizon) or plan_horizon != asdict(horizon):
        raise SharedSegmentError([f"The capacity plan covers {plan_horizon}, not the given horizon."])
    segments = staffing_from_capacity_result(capacity_plan)
    return _optimize(horizon, employees, rules, segments, config, {
        "source": "Phase 2 capacity plan (selected server counts via staffing_from_capacity_result)",
        "capacity_engine_version": capacity_plan["provenance"].get("engine_version"),
        "capacity_objective": capacity_plan["provenance"].get("objective"),
    })


def _optimize(horizon: OperatingHorizon, employees: Sequence[Employee], rules: WorkforceRules,
              required_staffing: Sequence[StaffingSegment], config: RosterOptimizationConfig,
              target_source: dict[str, Any]) -> dict[str, Any]:
    if required_staffing is None:
        raise SharedSegmentError(["required_staffing is required: it is the coverage target."])
    validate_workforce_inputs(horizon, employees, rules, [], required_staffing)
    validate_config(config)
    segments = list(required_staffing)
    shift_rules = rules.shift_rules
    highs = _highs_details()
    result: dict[str, Any] = {
        "status": None,
        "feasibility": UNKNOWN,
        "status_reason": None,
        "roster": None,
        "roster_evaluation": None,
        "labor_cost": None,
        "surplus": None,
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
        "coverage_target": {
            **target_source,
            "segments": [asdict(segment) for segment in segments],
            "required_server_minutes": sum(int(segment.servers) * (segment.end_minute - segment.start_minute)
                                           for segment in segments),
        },
        "formulation": dict(FORMULATION),
        "scope": SCOPE_NOTE,
        "provenance": {
            "optimizer_version": OPTIMIZER_VERSION,
            "config": asdict(config),
            "break_grid": (f"Breaks start only at clock minutes that are multiples of "
                           f"{config.break_start_granularity_minutes}; the result is optimal over rosters on this grid."),
            "surplus": SURPLUS_NOTE,
            "time_unit": "whole minutes since midnight; intervals are [start, end); rates are per hour",
        },
    }

    def finish(status: str, reason: str, feasibility: str = UNKNOWN) -> dict[str, Any]:
        result.update(status=status, status_reason=reason, feasibility=feasibility)
        return result

    generated = enumerate_patterns(employees, rules, config.break_start_granularity_minutes, config.max_patterns)
    patterns: list[RosterPattern] | None = generated["patterns"]
    complete_patterns = patterns is not None and not generated["missing_break_rules"]
    certificates = _certificates(horizon, employees, rules, segments, patterns if complete_patterns else None)
    result["infeasibility_certificates"] = certificates
    result["missing"] = [{"employee_id": item["employee_id"], "field": "break_rules", "reason": (
        f"An admissible {item['length_minutes']}-minute shift ({item['start_minute']}-{item['end_minute']}) has no "
        "break rule, so its breaks are unknown.")} for item in generated["missing_break_rules"]]
    if certificates:
        return finish(INFEASIBLE, "Proved infeasible without the solver: "
                      + ", ".join(item["code"] for item in certificates) + ".", INFEASIBLE)
    if patterns is None:
        return finish(PATTERN_LIMIT_EXCEEDED, f"More than {config.max_patterns} admissible patterns; nothing was solved.")
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
    result["model"] = {"labor_cases": labor_cases,
                       "shifts_without_break_placement": generated["shifts_without_break_placement"]}
    if result["missing"]:
        return finish(INCOMPLETE, "The objective needs pay values that were not supplied; nothing was solved "
                                  "and no cost was invented.")

    model = _build_model(horizon, employees, rules, segments, patterns, cases)
    result["model"].update(model["size"])
    if not model["objective"].size:
        # No admissible pattern exists and nothing is required (a certificate would have fired otherwise).
        values: np.ndarray | None = np.zeros(0)
        result["solver"]["not_run_reason"] = "No admissible pattern exists; the empty roster is the only roster."
        solver_status: int | None = 0
        response: Any = None
    else:
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
    if solver_status in (3, 4) or solver_status is None:
        return finish(SOLVER_ERROR, f"HiGHS stopped without a usable answer (status {solver_status}).")
    if values is None:
        if solver_status == 1:
            return finish(NO_SOLUTION_FOUND, "A solver limit was reached before any feasible roster was found; "
                                             "feasibility is unknown.")
        return finish(SOLVER_ERROR, "HiGHS reported success without a solution vector.")

    verification = _verify(model, values, horizon, employees, rules, segments, patterns)
    result["verification"] = {key: verification.get(key) for key in ("passed", "failure", "checks")}
    if "roster" in verification:
        result["roster"] = [asdict(shift) for shift in verification["roster"]]
        result["roster_evaluation"] = verification["evaluation"]
    if not verification["passed"]:
        return finish(VERIFICATION_FAILED, f"The solver's answer failed exact verification: {verification['failure']}")

    evaluation = verification["evaluation"]
    exact = verification["verified_objective"]
    result["labor_cost"] = {"employees": verification["labor"], "total": exact,
                            "note": "Caller's currency; wages for scheduled paid minutes (regular and overtime)."}
    totals = evaluation["totals"]["minutes"]
    result["surplus"] = {
        "surplus_server_minutes": evaluation["coverage"]["surplus_server_minutes"],
        "surplus_server_hours": evaluation["coverage"]["surplus_server_minutes"] / 60.0,
        "active_server_minutes_in_horizon": totals["active_server_minutes_in_horizon"],
        "active_server_minutes_outside_horizon": totals["active_server_minutes_outside_horizon"],
        "cost_note": SURPLUS_NOTE,
    }
    bound = result["solver"].get("dual_bound")
    distance = None if bound is None else exact - bound
    optimality = {
        "proven": solver_status == 0,
        "verified_objective": exact,
        "solver_objective": result["solver"].get("objective"),
        "model_objective_at_rounded_vector": verification["model_objective_at_rounded"],
        "dual_bound": bound,
        "gap_to_dual_bound": distance,
        "relative_gap_to_dual_bound": None if distance is None or exact == 0 else distance / abs(exact),
        "tolerances": {"mip_rel_gap": config.mip_rel_gap, "unchanged_highs_defaults": highs["unchanged_defaults"]},
    }
    if response is None:
        optimality["basis"] = "The empty roster is the only roster, so it is optimal by enumeration."
    elif solver_status == 0:
        optimality["basis"] = (f"HiGHS status 0: optimal within mip_rel_gap {config.mip_rel_gap} and the unchanged "
                               "HiGHS mip_abs_gap, for this model and break grid.")
    else:
        optimality["basis"] = "A solver limit stopped the search; this feasible roster is not proven optimal."
    result["optimality"] = optimality
    if solver_status == 0:
        return finish(OPTIMAL, "Optimal for this model within the reported tolerances; verified exactly.", FEASIBLE)
    return finish(FEASIBLE_NOT_PROVEN_OPTIMAL, "Feasible and verified exactly, but not proven optimal: "
                                               + str(response.message), FEASIBLE)
