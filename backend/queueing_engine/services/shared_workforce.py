"""Shared-queue workforce foundation (Phase 5B-1 of the shared-queue enhancement).

Validated inputs for pseudonymous employees, availability, shift and break rules, pay
parameters, physical registers, and a scheduled roster, plus the roster's scheduled hours,
active-server count, register check, and coverage of required staffing.

Everything here is **scheduled**, not simulated: active server time is when an employee is on
shift and not on break, never service or busy time (only the DES produces those). This
module builds no optimized roster and computes no cost; pay values are only validated and
checked for completeness.

Spec: docs/superpowers/specs/2026-09-26-shared-queue-workforce-foundation.md.
Nothing legacy imports this module. The separate-queue staff and break rules are not used.
"""

from __future__ import annotations

import bisect
import math
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from numbers import Integral, Real
from typing import Any

from backend.queueing_engine.services.shared_segments import (
    MINUTES_PER_DAY,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
    format_clock,
)

FOUNDATION_VERSION = "novaq-shared-workforce-foundation-v1"
INVALID, INCOMPLETE, COMPLETE = "INVALID", "INCOMPLETE", "COMPLETE"
_EMPLOYEE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

SCOPE_NOTE = (
    "Scheduled quantities derived from the roster. Active server time is scheduled staffing "
    "(on shift and not on break), not simulated service or busy time. This is not an optimized "
    "roster, and no cost is computed."
)
DEFINITIONS = {
    "scheduled_employee_minutes": "Sum of shift lengths.",
    "break_minutes": "Sum of scheduled break durations (paid + unpaid).",
    "paid_employee_minutes": "Scheduled employee minutes minus unpaid break minutes.",
    "scheduled_active_server_minutes": "Scheduled employee minutes minus all break minutes.",
    "regular_paid_minutes": "min(paid minutes, daily_regular_paid_minutes); unknown when the threshold is missing.",
    "overtime_paid_minutes": (
        "Paid minutes minus regular paid minutes: the paid time after the threshold is reached in clock "
        "order, so regular and overtime never overlap."
    ),
    "active_servers": "Employees on shift and not on break at an instant.",
    "shortfall_server_minutes": "Integral over the segment of max(0, required servers - active servers).",
    "surplus_server_minutes": "Integral over the segment of max(0, active servers - required servers).",
}
PSEUDONYMITY_NOTE = (
    "Employee ids are limited to letters, digits, '.', '_' and '-' (no spaces or '@'), but whether an id "
    "is pseudonymous cannot be verified; use ids that do not identify a person."
)


# ── Inputs ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AvailabilityWindow:
    start_minute: int
    end_minute: int


@dataclass(frozen=True)
class EmployeePay:
    """Pay parameters in the caller's currency; ``None`` means not supplied (never zero)."""

    regular_rate_per_hour: float | None
    overtime_rate_per_hour: float | None
    daily_regular_paid_minutes: int | None  # paid minutes per day before overtime begins


@dataclass(frozen=True)
class Employee:
    employee_id: str
    availability: tuple[AvailabilityWindow, ...]
    pay: EmployeePay


@dataclass(frozen=True)
class ShiftRules:
    earliest_start_minute: int
    latest_end_minute: int
    min_shift_minutes: int
    max_shift_minutes: int
    boundary_granularity_minutes: int  # shift starts and ends are multiples of this, from midnight
    max_shifts_per_employee: int
    min_minutes_between_shifts: int | None  # required when more than one shift is allowed


@dataclass(frozen=True)
class BreakRequirement:
    name: str
    duration_minutes: int
    paid: bool
    earliest_start_offset_minutes: int  # from the shift start
    latest_start_offset_minutes: int


@dataclass(frozen=True)
class BreakRule:
    """Breaks for shifts whose length lies in [min_shift_minutes, max_shift_minutes]."""

    min_shift_minutes: int
    max_shift_minutes: int
    min_gap_minutes: int
    breaks: tuple[BreakRequirement, ...]


@dataclass(frozen=True)
class WorkforceRules:
    shift_rules: ShiftRules
    break_rules: tuple[BreakRule, ...]
    register_count: int  # physical service points


@dataclass(frozen=True)
class ScheduledBreak:
    name: str
    start_minute: int


@dataclass(frozen=True)
class ScheduledShift:
    """The employee staffs one server whenever on this shift and not on a break."""

    employee_id: str
    start_minute: int
    end_minute: int
    breaks: tuple[ScheduledBreak, ...]


# ── Malformed-input validation (raises) ─────────────────────────────────────


def _whole(value: object) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def _finite(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def _minute(value: object) -> bool:
    return _whole(value) and 0 <= int(value) <= MINUTES_PER_DAY  # type: ignore[call-overload]


def _interval_problems(label: str, start: object, end: object) -> list[str]:
    if not _minute(start) or not _minute(end):
        return [f"{label} must use whole minutes between 0 and {MINUTES_PER_DAY}."]
    if int(end) <= int(start):  # type: ignore[call-overload]
        return [f"{label} must end after it starts."]
    return []


def _count_problems(label: str, value: object, minimum: int) -> list[str]:
    return [] if _whole(value) and int(value) >= minimum else [  # type: ignore[call-overload]
        f"{label} must be a whole number, {minimum} or more."]


def _employee_problems(employees: object) -> list[str]:
    if not isinstance(employees, (list, tuple)) or not employees:
        return ["At least one employee is required."]
    problems = []
    ids = []
    for position, employee in enumerate(employees, start=1):
        if not isinstance(employee, Employee):
            problems.append(f"Employee {position} must be an Employee.")
            continue
        label = f"Employee {employee.employee_id!r}"
        if not isinstance(employee.employee_id, str) or not _EMPLOYEE_ID.match(employee.employee_id):
            problems.append(
                f"Employee {position} id must be 1 to 64 letters, digits, '.', '_' or '-', starting with a letter "
                "or digit.")
        else:
            ids.append(employee.employee_id)
        windows = employee.availability
        if not isinstance(windows, (list, tuple)) or not windows:
            problems.append(f"{label} needs at least one availability window.")
        elif not all(isinstance(window, AvailabilityWindow) for window in windows):
            problems.append(f"{label} availability must be AvailabilityWindow items.")
        else:
            window_problems = [p for window in windows for p in _interval_problems(
                f"{label} availability window", window.start_minute, window.end_minute)]
            problems += window_problems
            if not window_problems:
                ordered = sorted(windows, key=lambda window: window.start_minute)
                if any(later.start_minute < earlier.end_minute for earlier, later in zip(ordered, ordered[1:])):
                    problems.append(f"{label} availability windows overlap.")
        pay = employee.pay
        if not isinstance(pay, EmployeePay):
            problems.append(f"{label} pay must be an EmployeePay (use None fields for values not supplied).")
            continue
        for name in ("regular_rate_per_hour", "overtime_rate_per_hour"):
            value = getattr(pay, name)
            if value is not None and (not _finite(value) or value < 0):
                problems.append(f"{label} {name} must be a finite number, 0 or more, or None.")
        threshold = pay.daily_regular_paid_minutes
        if threshold is not None and (not _whole(threshold) or threshold < 0):
            problems.append(f"{label} daily_regular_paid_minutes must be a whole number, 0 or more, or None.")
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        problems.append(f"Duplicate employee ids: {', '.join(duplicates)}.")
    return problems


def _rule_problems(rules: object) -> list[str]:
    if not isinstance(rules, WorkforceRules):
        return ["rules must be a WorkforceRules."]
    problems = _count_problems("register_count", rules.register_count, 1)
    shift = rules.shift_rules
    if not isinstance(shift, ShiftRules):
        return problems + ["shift_rules must be a ShiftRules."]
    problems += _interval_problems("The permitted shift boundary", shift.earliest_start_minute, shift.latest_end_minute)
    problems += _count_problems("min_shift_minutes", shift.min_shift_minutes, 1)
    problems += _count_problems("max_shift_minutes", shift.max_shift_minutes, 1)
    problems += _count_problems("boundary_granularity_minutes", shift.boundary_granularity_minutes, 1)
    problems += _count_problems("max_shifts_per_employee", shift.max_shifts_per_employee, 1)
    if not problems:
        span = shift.latest_end_minute - shift.earliest_start_minute
        if not shift.min_shift_minutes <= shift.max_shift_minutes <= span:
            problems.append("Shift lengths need min_shift_minutes <= max_shift_minutes <= the permitted boundary span.")
        if shift.max_shifts_per_employee > 1:
            problems += _count_problems("min_minutes_between_shifts (required with split shifts)",
                                        shift.min_minutes_between_shifts, 0)
        elif shift.min_minutes_between_shifts is not None:
            problems.append("min_minutes_between_shifts applies only when more than one shift is allowed; use None.")
    break_rules = rules.break_rules
    if not isinstance(break_rules, (list, tuple)) or not all(isinstance(rule, BreakRule) for rule in break_rules):
        return problems + ["break_rules must be BreakRule items."]
    for number, rule in enumerate(break_rules, start=1):
        label = f"Break rule {number}"
        rule_problems = (_count_problems(f"{label} min_shift_minutes", rule.min_shift_minutes, 1)
                         + _count_problems(f"{label} max_shift_minutes", rule.max_shift_minutes, 1)
                         + _count_problems(f"{label} min_gap_minutes", rule.min_gap_minutes, 0))
        if not rule_problems and rule.min_shift_minutes > rule.max_shift_minutes:
            rule_problems.append(f"{label} needs min_shift_minutes <= max_shift_minutes.")
        if not isinstance(rule.breaks, (list, tuple)) or not all(isinstance(item, BreakRequirement) for item in rule.breaks):
            rule_problems.append(f"{label} breaks must be BreakRequirement items (an empty tuple declares no break).")
        else:
            names = [item.name for item in rule.breaks]
            if any(not isinstance(name, str) or not name.strip() for name in names):
                rule_problems.append(f"{label} break names must be non-empty text.")
            elif len(set(names)) != len(names):
                rule_problems.append(f"{label} break names must be unique.")
            for item in rule.breaks:
                item_label = f"{label} break {item.name!r}"
                rule_problems += _count_problems(f"{item_label} duration_minutes", item.duration_minutes, 1)
                if not isinstance(item.paid, bool):
                    rule_problems.append(f"{item_label} paid must be True or False.")
                offsets = (item.earliest_start_offset_minutes, item.latest_start_offset_minutes)
                if not all(_whole(value) and value >= 0 for value in offsets):  # type: ignore[operator]
                    rule_problems.append(f"{item_label} start offsets must be whole numbers, 0 or more.")
                elif offsets[0] > offsets[1]:
                    rule_problems.append(f"{item_label} needs earliest_start_offset <= latest_start_offset.")
        problems += rule_problems
    if not problems:
        ordered = sorted(break_rules, key=lambda rule: rule.min_shift_minutes)
        if any(later.min_shift_minutes <= earlier.max_shift_minutes for earlier, later in zip(ordered, ordered[1:])):
            problems.append("Break rule shift-length ranges overlap; each length needs at most one rule.")
    return problems


def _roster_problems(roster: object) -> list[str]:
    if not isinstance(roster, (list, tuple)):
        return ["roster must be a list of ScheduledShift items."]
    problems = []
    for position, shift in enumerate(roster, start=1):
        if not isinstance(shift, ScheduledShift):
            problems.append(f"Roster item {position} must be a ScheduledShift.")
            continue
        if not isinstance(shift.employee_id, str):
            problems.append(f"Roster item {position} employee_id must be text.")
        problems += _interval_problems(f"Roster item {position}", shift.start_minute, shift.end_minute)
        if not isinstance(shift.breaks, (list, tuple)) or not all(isinstance(b, ScheduledBreak) for b in shift.breaks):
            problems.append(f"Roster item {position} breaks must be ScheduledBreak items.")
            continue
        for item in shift.breaks:
            if not isinstance(item.name, str) or not item.name.strip():
                problems.append(f"Roster item {position} has a break without a name.")
            if not _minute(item.start_minute):
                problems.append(f"Roster item {position} break {item.name!r} start must be a whole minute "
                                f"between 0 and {MINUTES_PER_DAY}.")
    return problems


def _staffing_problems(horizon: OperatingHorizon, segments: object) -> list[str]:
    if not isinstance(segments, (list, tuple)) or not segments or not all(
            isinstance(segment, StaffingSegment) for segment in segments):
        return ["required_staffing must be a non-empty list of StaffingSegment items or omitted."]
    problems: list[str] = []
    for segment in segments:
        problems += _interval_problems(f"Required staffing segment {segment.segment_id}",
                                       segment.start_minute, segment.end_minute)
        problems += _count_problems(f"Required staffing segment {segment.segment_id} servers", segment.servers, 0)
    ids = [segment.segment_id for segment in segments]
    if len(set(ids)) != len(ids):
        problems.append("Required staffing segment ids must be unique.")
    if problems:
        return problems
    if segments[0].start_minute != horizon.start_minute or segments[-1].end_minute != horizon.end_minute or any(
            later.start_minute != earlier.end_minute for earlier, later in zip(segments, segments[1:])):
        problems.append("Required staffing segments must tile the operating horizon in order, without gaps or overlaps.")
    return problems


def validate_workforce_inputs(
    horizon: OperatingHorizon,
    employees: Sequence[Employee],
    rules: WorkforceRules,
    roster: Sequence[ScheduledShift],
    required_staffing: Sequence[StaffingSegment] | None = None,
) -> None:
    """Raise ``SharedSegmentError`` listing every malformed input; return when well formed."""
    problems: list[str] = [] if isinstance(horizon, OperatingHorizon) else ["horizon must be an OperatingHorizon."]
    if not problems:
        problems += _interval_problems("The operating horizon", horizon.start_minute, horizon.end_minute)
    problems += _employee_problems(employees)
    problems += _rule_problems(rules)
    problems += _roster_problems(roster)
    if required_staffing is not None and not problems:
        problems += _staffing_problems(horizon, required_staffing)
    if problems:
        raise SharedSegmentError(problems)


# ── Interval helpers (half-open [start, end) in whole minutes) ──────────────


def _union(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(item for item in intervals if item[1] > item[0]):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _subtract(base: list[tuple[int, int]], cuts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result = []
    cuts = _union(cuts)
    for start, end in _union(base):
        cursor = start
        for cut_start, cut_end in cuts:
            if cut_end <= cursor or cut_start >= end:
                continue
            if cut_start > cursor:
                result.append((cursor, cut_start))
            cursor = max(cursor, cut_end)
        if cursor < end:
            result.append((cursor, end))
    return result


def _length(intervals: list[tuple[int, int]]) -> int:
    return sum(end - start for start, end in intervals)


def _clip(intervals: list[tuple[int, int]], low: int, high: int) -> list[tuple[int, int]]:
    return [(max(start, low), min(end, high)) for start, end in intervals if min(end, high) > max(start, low)]


def _span(start: int, end: int) -> str:
    return f"{format_clock(start)}-{format_clock(end)}"


# ── Roster evaluation ───────────────────────────────────────────────────────


def _violation(code: str, employee_id: str | None, shift_index: int | None, message: str) -> dict[str, Any]:
    return {"code": code, "employee_id": employee_id, "shift_index": shift_index, "message": message}


def _rule_gaps(rules: WorkforceRules) -> list[tuple[int, int]]:
    """Shift lengths in the permitted range that no break rule covers (closed ranges)."""
    low, high = rules.shift_rules.min_shift_minutes, rules.shift_rules.max_shift_minutes
    gaps = []
    cursor = low
    for rule in sorted(rules.break_rules, key=lambda item: item.min_shift_minutes):
        if rule.max_shift_minutes < cursor:
            continue
        if rule.min_shift_minutes > high:
            break
        if rule.min_shift_minutes > cursor:
            gaps.append((cursor, rule.min_shift_minutes - 1))
        cursor = max(cursor, rule.max_shift_minutes + 1)
    if cursor <= high:
        gaps.append((cursor, high))
    return gaps


def _check_shift(index: int, shift: ScheduledShift, employee: Employee, rules: WorkforceRules,
                 violations: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate one shift of a known employee; return its breaks with rule lengths where known."""
    who, shift_rules = employee.employee_id, rules.shift_rules
    start, end = shift.start_minute, shift.end_minute
    length = end - start
    where = f"Shift {index} of {who} ({_span(start, end)})"
    if start < shift_rules.earliest_start_minute or end > shift_rules.latest_end_minute:
        violations.append(_violation("OUTSIDE_SHIFT_BOUNDARIES", who, index, (
            f"{where} is outside the permitted {_span(shift_rules.earliest_start_minute, shift_rules.latest_end_minute)}.")))
    if not shift_rules.min_shift_minutes <= length <= shift_rules.max_shift_minutes:
        violations.append(_violation("SHIFT_LENGTH", who, index, (
            f"{where} lasts {length} minutes; permitted {shift_rules.min_shift_minutes} to "
            f"{shift_rules.max_shift_minutes}.")))
    granularity = shift_rules.boundary_granularity_minutes
    if start % granularity or end % granularity:
        violations.append(_violation("OFF_GRID", who, index,
                                     f"{where} must start and end on multiples of {granularity} minutes."))
    if not any(window.start_minute <= start and end <= window.end_minute for window in employee.availability):
        violations.append(_violation("OUTSIDE_AVAILABILITY", who, index,
                                     f"{where} is not inside one of the employee's availability windows."))

    rule = next((item for item in rules.break_rules if item.min_shift_minutes <= length <= item.max_shift_minutes), None)
    checked: dict[str, Any] = {"rule": rule, "breaks": [], "hours_defined": True}
    if rule is None:
        violations.append(_violation("NO_BREAK_RULE", who, index, (
            f"{where}: no break rule covers a {length}-minute shift, so its breaks are unknown.")))
        checked["hours_defined"] = False
        return checked
    required = {item.name: item for item in rule.breaks}
    names = [item.name for item in shift.breaks]
    for name in sorted({name for name in names if names.count(name) > 1}):
        violations.append(_violation("BREAK_DUPLICATE", who, index, f"{where} schedules break {name!r} more than once."))
    for name in [name for name in required if name not in names]:
        violations.append(_violation("BREAK_MISSING", who, index, f"{where} is missing the required break {name!r}."))
    placed: list[dict[str, Any]] = []
    for item in shift.breaks:
        requirement = required.get(item.name)
        if requirement is None:
            violations.append(_violation("BREAK_UNKNOWN", who, index, (
                f"{where}: break {item.name!r} is not in the rule for {rule.min_shift_minutes}-"
                f"{rule.max_shift_minutes}-minute shifts.")))
            checked["hours_defined"] = False
            continue
        break_end = item.start_minute + requirement.duration_minutes
        offset = item.start_minute - start
        if not requirement.earliest_start_offset_minutes <= offset <= requirement.latest_start_offset_minutes:
            violations.append(_violation("BREAK_WINDOW", who, index, (
                f"{where}: break {item.name!r} starts {offset} minutes after the shift start; permitted "
                f"{requirement.earliest_start_offset_minutes} to {requirement.latest_start_offset_minutes}.")))
        if item.start_minute < start or break_end > end:
            violations.append(_violation("BREAK_OUTSIDE_SHIFT", who, index, (
                f"{where}: break {item.name!r} ({_span(item.start_minute, break_end)}) does not lie inside the shift.")))
            checked["hours_defined"] = False
        placed.append({"name": item.name, "start_minute": item.start_minute, "end_minute": break_end,
                       "duration_minutes": requirement.duration_minutes, "paid": requirement.paid})
    placed.sort(key=lambda item: item["start_minute"])
    for earlier, later in zip(placed, placed[1:]):
        if later["start_minute"] < earlier["end_minute"]:
            violations.append(_violation("BREAK_OVERLAP", who, index,
                                         f"{where}: breaks {earlier['name']!r} and {later['name']!r} overlap."))
            checked["hours_defined"] = False
        elif later["start_minute"] - earlier["end_minute"] < rule.min_gap_minutes:
            violations.append(_violation("BREAK_GAP", who, index, (
                f"{where}: breaks {earlier['name']!r} and {later['name']!r} are "
                f"{later['start_minute'] - earlier['end_minute']} minutes apart; at least {rule.min_gap_minutes} "
                "required.")))
    checked["breaks"] = placed
    return checked


def _overtime_start(paid_intervals: list[tuple[int, int]], threshold: int) -> int | None:
    """The clock minute at which paid time, in clock order, first exceeds the threshold."""
    elapsed = 0
    for start, end in paid_intervals:
        if elapsed + (end - start) > threshold:
            return start + (threshold - elapsed)
        elapsed += end - start
    return None


def _as_hours(minutes: dict[str, int | None]) -> dict[str, float | None]:
    return {key.replace("_minutes", "_hours"): None if value is None else value / 60.0 for key, value in minutes.items()}


def _active_steps(active_by_employee: dict[str, list[tuple[int, int]]]) -> list[dict[str, int]]:
    changes: dict[int, int] = {}
    for intervals in active_by_employee.values():
        for start, end in intervals:
            changes[start] = changes.get(start, 0) + 1
            changes[end] = changes.get(end, 0) - 1
    steps: list[dict[str, int]] = []
    count = 0
    points = sorted(changes)
    for here, following in zip(points, points[1:]):
        count += changes[here]
        if steps and steps[-1]["active_servers"] == count and steps[-1]["end_minute"] == here:
            steps[-1]["end_minute"] = following
        else:
            steps.append({"start_minute": here, "end_minute": following, "active_servers": count})
    return steps


def _count_at(steps: list[dict[str, int]], starts: list[int], minute: int) -> int:
    position = bisect.bisect_right(starts, minute) - 1
    if position < 0 or minute >= steps[position]["end_minute"]:
        return 0
    return steps[position]["active_servers"]


def _coverage(steps: list[dict[str, int]], segments: Sequence[StaffingSegment]) -> dict[str, Any]:
    starts = [step["start_minute"] for step in steps]
    boundaries = sorted({point for step in steps for point in (step["start_minute"], step["end_minute"])})
    rows = []
    for segment in segments:
        points = sorted({segment.start_minute, segment.end_minute}
                        | {point for point in boundaries if segment.start_minute < point < segment.end_minute})
        required = int(segment.servers)
        pieces = [(end - start, _count_at(steps, starts, start)) for start, end in zip(points, points[1:])]
        rows.append({
            "segment_id": segment.segment_id,
            "start_minute": segment.start_minute,
            "end_minute": segment.end_minute,
            "required_servers": required,
            "min_active_servers": min(count for _, count in pieces),
            "max_active_servers": max(count for _, count in pieces),
            "shortfall_server_minutes": sum(minutes * max(0, required - count) for minutes, count in pieces),
            "surplus_server_minutes": sum(minutes * max(0, count - required) for minutes, count in pieces),
        })
    return {
        "segments": rows,
        "shortfall_server_minutes": sum(row["shortfall_server_minutes"] for row in rows),
        "surplus_server_minutes": sum(row["surplus_server_minutes"] for row in rows),
        "fully_covered": all(row["shortfall_server_minutes"] == 0 for row in rows),
        "note": "Scheduled coverage only; whether it meets demand is established by the DES, not here.",
    }


def evaluate_roster(
    horizon: OperatingHorizon,
    employees: Sequence[Employee],
    rules: WorkforceRules,
    roster: Sequence[ScheduledShift],
    *,
    required_staffing: Sequence[StaffingSegment] | None = None,
) -> dict[str, Any]:
    """Validate a roster against the workforce rules and report its scheduled quantities."""
    validate_workforce_inputs(horizon, employees, rules, roster, required_staffing)
    by_id = {employee.employee_id: employee for employee in employees}
    violations: list[dict[str, Any]] = []
    shifts_by_employee: dict[str, list[tuple[int, ScheduledShift, dict[str, Any]]]] = {}
    for index, shift in enumerate(roster):
        employee = by_id.get(shift.employee_id)
        if employee is None:
            violations.append(_violation("UNKNOWN_EMPLOYEE", shift.employee_id, index, (
                f"Shift {index} names employee {shift.employee_id!r}, who is not in the employee list.")))
            continue
        checked = _check_shift(index, shift, employee, rules, violations)
        shifts_by_employee.setdefault(employee.employee_id, []).append((index, shift, checked))

    shift_rules = rules.shift_rules
    employee_rows: list[dict[str, Any]] = []
    active_by_employee: dict[str, list[tuple[int, int]]] = {}
    missing: list[dict[str, Any]] = []
    for employee in employees:
        who = employee.employee_id
        items = sorted(shifts_by_employee.get(who, []), key=lambda item: item[1].start_minute)
        hours_defined = all(item[2]["hours_defined"] for item in items)
        if len(items) > shift_rules.max_shifts_per_employee:
            violations.append(_violation("TOO_MANY_SHIFTS", who, None, (
                f"{who} has {len(items)} shifts; at most {shift_rules.max_shifts_per_employee} permitted.")))
        for (first_index, first, _), (second_index, second, _) in zip(items, items[1:]):
            if second.start_minute < first.end_minute:
                violations.append(_violation("SHIFT_OVERLAP", who, second_index, (
                    f"{who}'s shifts {first_index} and {second_index} overlap: the employee cannot staff two servers.")))
                hours_defined = False
            elif shift_rules.max_shifts_per_employee > 1 and (
                    second.start_minute - first.end_minute < int(shift_rules.min_minutes_between_shifts or 0)):
                violations.append(_violation("INSUFFICIENT_REST", who, second_index, (
                    f"{who} rests {second.start_minute - first.end_minute} minutes between shifts {first_index} and "
                    f"{second_index}; at least {shift_rules.min_minutes_between_shifts} required.")))
        shifts = [(shift.start_minute, shift.end_minute) for _, shift, _ in items]
        breaks = [item for _, _, checked in items for item in checked["breaks"]]
        break_intervals = [(item["start_minute"], item["end_minute"]) for item in breaks]
        unpaid = [(item["start_minute"], item["end_minute"]) for item in breaks if not item["paid"]]
        active = _subtract(shifts, break_intervals)
        active_by_employee[who] = active
        paid_intervals = _subtract(shifts, unpaid)
        threshold = employee.pay.daily_regular_paid_minutes

        minutes: dict[str, int | None] | None = None
        overtime_start = None
        if hours_defined:
            scheduled = sum(end - start for start, end in shifts)
            paid_breaks = sum(item["duration_minutes"] for item in breaks if item["paid"])
            unpaid_breaks = sum(item["duration_minutes"] for item in breaks if not item["paid"])
            paid = scheduled - unpaid_breaks
            in_horizon = _length(_clip(active, horizon.start_minute, horizon.end_minute))
            minutes = {
                "scheduled_employee_minutes": scheduled,
                "break_minutes": paid_breaks + unpaid_breaks,
                "paid_break_minutes": paid_breaks,
                "unpaid_break_minutes": unpaid_breaks,
                "paid_employee_minutes": paid,
                "scheduled_active_server_minutes": scheduled - paid_breaks - unpaid_breaks,
                "active_server_minutes_in_horizon": in_horizon,
                "active_server_minutes_outside_horizon": _length(active) - in_horizon,
                "regular_paid_minutes": None if threshold is None else min(paid, threshold),
                "overtime_paid_minutes": None if threshold is None else paid - min(paid, threshold),
            }
            # Identities of a well-defined roster: the shift time splits into active and break time.
            assert minutes["scheduled_active_server_minutes"] == _length(active)
            assert paid == _length(paid_intervals)
            if threshold is not None:
                overtime_start = _overtime_start(paid_intervals, threshold)
        if items:
            for field in ("regular_rate_per_hour", "overtime_rate_per_hour", "daily_regular_paid_minutes"):
                if getattr(employee.pay, field) is None:
                    missing.append({"employee_id": who, "field": field, "consequence": (
                        "Regular and overtime minutes cannot be classified." if field == "daily_regular_paid_minutes"
                        else "Labor cost cannot be computed for this employee in a later phase.")})
        employee_rows.append({
            "employee_id": who,
            "shift_count": len(items),
            "shifts": [{"shift_index": index, "start_minute": shift.start_minute, "end_minute": shift.end_minute,
                        "break_rule": None if checked["rule"] is None else
                        [checked["rule"].min_shift_minutes, checked["rule"].max_shift_minutes],
                        "breaks": checked["breaks"]} for index, shift, checked in items],
            "hours_defined": hours_defined,
            "hours_withheld_reason": None if hours_defined else (
                "A shift or break conflict or an unknown break length leaves this employee's time without a "
                "well-defined split into active and break time; see the violations."),
            "minutes": minutes,
            "hours": None if minutes is None else _as_hours(minutes),
            "overtime_starts_at_minute": overtime_start,
            "pay_complete": all(value is not None for value in asdict(employee.pay).values()),
        })

    steps = _active_steps(active_by_employee)
    for step in steps:
        if step["active_servers"] > rules.register_count:
            violations.append(_violation("REGISTER_CAPACITY", None, None, (
                f"{step['active_servers']} employees are scheduled to staff servers during "
                f"{_span(step['start_minute'], step['end_minute'])}, above the {rules.register_count} registers.")))
    for low, high in _rule_gaps(rules):
        missing.append({"employee_id": None, "field": "break_rules", "consequence": (
            f"Shift lengths {low} to {high} minutes have no break rule; such shifts would be rejected.")})

    totals: dict[str, Any] | None = None
    if all(row["minutes"] is not None for row in employee_rows):
        keys = list(employee_rows[0]["minutes"]) if employee_rows else []
        summed = {key: None if any(row["minutes"][key] is None for row in employee_rows)
                  else sum(row["minutes"][key] for row in employee_rows) for key in keys}
        totals = {"minutes": summed, "hours": _as_hours(summed)}
    status = INVALID if violations else INCOMPLETE if missing else COMPLETE
    return {
        "status": status,
        "violations": violations,
        "missing": missing,
        "employees": employee_rows,
        "totals": totals,
        "totals_withheld_reason": None if totals is not None else "Hours are withheld for at least one employee.",
        "active_server_steps": steps,
        "register_check": {
            "register_count": rules.register_count,
            "max_active_servers": max((step["active_servers"] for step in steps), default=0),
            "exceeded": any(step["active_servers"] > rules.register_count for step in steps),
        },
        "coverage": None if required_staffing is None else _coverage(steps, required_staffing),
        "scope": SCOPE_NOTE,
        "definitions": dict(DEFINITIONS),
        "provenance": {
            "foundation_version": FOUNDATION_VERSION,
            "time_unit": "whole minutes since midnight; intervals are [start, end); hours = minutes / 60",
            "pseudonymity": PSEUDONYMITY_NOTE,
            "registers": "Registers are counted, not identified; which register an employee uses is not modeled.",
        },
    }
