"""Operational attribution of one named-employee shared-queue DES result (Phase 5B-4.6 of the shared-queue enhancement).

Per employee and shift (P9), the attribution reports quantities only:

- shift timing;
- time waiting for a register;
- break delay, shortening, and non-fulfilment;
- on-shift time after closing and past the scheduled shift end.

The after-closing and past-end time is split into four disjoint cells, so no elapsed time is counted twice.

It is a pure read of the named engine's employee timeline and the run's input employees. It runs no simulation, draws
no random numbers, changes no record, and attaches no pay, cost, or overtime meaning (Phase 5B-5).

Every duration is in hours (D1). A failed check raises ``NamedAttributionError`` with the check, a message, and the
evidence; nothing is repaired. Times compare exactly. The house tolerance (``shared_named_playback.TOLERANCE``) is used
only for reconciliation checks and for the D7 rule on derived durations.

Spec: docs/superpowers/specs/2026-09-29-shared-queue-named-attribution.md.
Nothing legacy imports this module. No API, database, or frontend uses it.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from numbers import Integral, Real
from typing import Any

from backend.queueing_engine.services.shared_workforce import Employee
from backend.queueing_engine.simulation.shared_continuous_des import CLOSING_POLICIES
from backend.queueing_engine.simulation.shared_employee_states import (
    BASE_STATES,
    BREAK_OUTCOMES,
    COMPLETED,
    OFF,
    ON_BREAK,
    STATE_MACHINE_VERSION,
    TRUNCATED_BY_CLOSING,
    UNFULFILLED,
    WAITING_FOR_REGISTER,
)
from backend.queueing_engine.simulation.shared_named_des import NAMED_ENGINE_VERSION
from backend.queueing_engine.simulation.shared_named_playback import TOLERANCE
from backend.queueing_engine.simulation.shared_named_replications import UNFULFILLED_CAUSES

ATTRIBUTION_VERSION = "novaq-shared-named-attribution-v1"

ON_DUTY_STATES = tuple(state for state in BASE_STATES if state != OFF)
CLOSING_CELLS = (
    "after_closing_hours", "past_scheduled_end_hours", "after_closing_and_past_scheduled_end_hours",
    "after_closing_only_hours", "past_scheduled_end_only_hours", "neither_hours",
    "after_closing_or_past_scheduled_end_hours",
)
SHIFT_SUM_FIELDS = ("scheduled_duration_hours", "activation_delay_hours", "overrun_hours", "on_duty_hours",
                    "register_wait_hours")
BREAK_HOURS_TOTALS = ("delay_from_scheduled_hours_total", "delay_from_due_hours_total", "actual_break_hours_total",
                      "shortened_hours_total", "unfulfilled_hours_total")
BREAK_DURATION_FIELDS = ("configured_hours", "delay_from_scheduled_hours", "delay_from_due_hours", "actual_hours",
                         "shortened_hours", "unfulfilled_hours")

CHECKS = {
    "record_structure": (
        "The result has provenance, closing_policy (exactly DRAIN or HARD_CUTOFF), and an employee_timeline with "
        "begin, finish, closing_time, intervals, shifts, breaks, and state_totals under the engine's field names. "
        "Times are finite reals (not bool), shift_index is a whole number (or None on an interval), flags are bool, "
        "and duration_minutes is a whole number of at least 1."),
    "source_versions": (
        "The result's engine and state-machine versions equal NAMED_ENGINE_VERSION and STATE_MACHINE_VERSION; a result "
        "from another version is refused."),
    "employee_identity": (
        "The input employees are a list or tuple of Employee with distinct ids; the state_totals keys are strings "
        "equal to the input ids (exact, case-sensitive, never normalized); every interval, shift, and break names "
        "one of them."),
    "shift_identity": (
        "(employee_id, shift_index) is unique across shifts; every interval with a shift_index and every break names "
        "a shift of the same employee; break names are unique within a shift."),
    "interval_geometry": (
        "Per employee, intervals are contiguous from begin to finish with end > start (exact); shift_index is None if "
        "and only if the state is OFF; after_closing if and only if start >= closing_time, and no interval crosses "
        "closing; on a shift, past_scheduled_end if and only if start >= the shift's scheduled end, and no interval "
        "crosses it; an OFF interval is never past a scheduled end."),
    "shift_reconciliation": (
        "An activated shift has actual_start >= scheduled_start (exact), intervals that tile exactly "
        "[actual_start, release), activation_delay and overrun equal to the engine's formulas exactly, on_duty_hours "
        "within tolerance of release - actual_start, and past_scheduled_end_hours within tolerance of overrun. A shift "
        "that was not activated has no interval, and its actual_start, release, activation_delay, and overrun are None."),
    "closing_partition": (
        "The four disjoint cells sum to on_duty_hours; after_closing = after_closing_only + both, past_scheduled_end = "
        "past_scheduled_end_only + both, and union = after_closing + past_scheduled_end - both, within tolerance; "
        "both <= after_closing and both <= past_scheduled_end exactly."),
    "base_state_partition": "The shift's hours by base state sum to on_duty_hours within tolerance.",
    "break_reconciliation": (
        "Outcome and cause come from the engine's vocabularies; a break is started if and only if its outcome is not "
        "unfulfilled; a started break has a due time, delay equal to actual_start - scheduled_start exactly, "
        "actual_start >= due and actual_start < actual_end (exact); a completed break lasts its configured duration "
        "within tolerance; a truncated break ends exactly at closing; an unfulfilled break has no actual end or delay; "
        "the shift's ON_BREAK hours are within tolerance of its started breaks' actual hours."),
    "employee_reconciliation": (
        "For each on-duty state, the sum over the employee's shifts is within tolerance of state_totals; the "
        "employee's state_totals sum to finish - begin within tolerance."),
    "finite_nonnegative": (
        "Every derived duration passes the D7 rule (a tiny negative within tolerance is reported as 0.0; beyond it "
        "the check fails with evidence), and every output duration is a finite number of hours, 0 or more, or None "
        "where the spec says None."),
}

DEFINITIONS = {
    "time_unit": (
        "Hours from the horizon start, as in the named engine (D1). Every duration ends in _hours; configured_minutes "
        "is the break's configured length copied in its source unit. Minutes are a display conversion only."),
    "record": (
        "The primary record is one employee x one shift x one run, in the engine's shift order. An interval belongs "
        "to shift (employee_id, shift_index) if and only if it carries both; allocation is exact, never proportional. "
        "OFF time belongs to no shift."),
    "on_duty_hours": "The sum of the lengths of the shift's intervals: release - actual_start.",
    "hours_by_state": (
        "The shift's hours in each of the six on-duty base states; the states never overlap. register_wait_hours is "
        "its WAITING_FOR_REGISTER entry."),
    "closing_attribution": (
        "after_closing and past_scheduled_end are independent flags on the engine's intervals. Each on-shift interval "
        "lies in exactly one of four disjoint cells: neither, after_closing_only, past_scheduled_end_only, or "
        "after_closing_and_past_scheduled_end. Every field, including the overlapping totals after_closing, "
        "past_scheduled_end, and their union, is summed directly over its intervals, never by subtraction (D3). "
        "No field is overtime, paid, or unpaid."),
    "delay_from_scheduled_hours": (
        "Per break: the actual start minus the roster's scheduled break start; the engine's delay (P2). It includes a "
        "delayed split-shift activation (P3), the minimum-gap push of a later break (P1), and waiting for a service "
        "to finish."),
    "delay_from_due_hours": (
        "Per break: the actual start minus the instant the break fell due. A due break starts at once unless the "
        "employee is serving, and then at that service's completion, so this is the part caused by the service under "
        "way."),
    "shortened_hours": (
        "Per break: 0.0 for a completed break (P1: it lasts its configured duration; not computed by subtraction); "
        "configured_hours - actual_hours for a break truncated by closing; None for an unfulfilled break."),
    "unfulfilled_hours": "Per break: configured_hours when unfulfilled (its cause is kept beside it), else 0.0.",
    "_total": (
        "A sum across several breaks, at shift or employee level. No per-break field is a total. No delay threshold "
        "exists (P2)."),
    "employee_summary": (
        "One per input employee, in employee_id order. Shift duration fields, hours_by_state, and closing_attribution "
        "are sums over the employee's activated shifts; break counts and _total fields are sums over all its shifts; "
        "off_hours is the employee's OFF time from state_totals."),
    "derived_durations": (
        "D7: a duration computed as x = a - b whose true value is nonnegative (scheduled_duration_hours, "
        "delay_from_scheduled_hours, delay_from_due_hours, actual_hours, and a truncated break's shortened_hours) is "
        "reported as x when x >= 0 and as 0.0 when x < 0 but a and b are within the house tolerance; otherwise the "
        "check finite_nonnegative fails. The tolerance never decides event order or any timing comparison, which "
        "stay exact, and no source value changes."),
    "not_reported": (
        "The engine break record's paid flag, and any wage, overtime pay, penalty, waiting cost, break compensation, "
        "or after-closing cost (Phase 5B-5)."),
}

UNDETERMINED = [
    "Whether a derived duration can ever come out float-negative, and so take the D7 zero or failure branch, is NOT "
    "TESTED on engine output; the rule decides the handling either way.",
    "Before-opening attribution is out of scope: time before opening is ordinary on-duty time in hours_by_state, and "
    "the P8 before-opening window shape stays INFERRED.",
]

RECONCILIATION = [
    {"identity": "per employee, intervals are contiguous from begin to finish, end > start", "method": "exact"},
    {"identity": "after_closing and past_scheduled_end flags against closing_time and the scheduled end",
     "method": "exact"},
    {"identity": "activated shift: actual_start >= scheduled_start; intervals tile [actual_start, release)",
     "method": "exact"},
    {"identity": "activation_delay = actual_start - scheduled_start; overrun = max(0, release - scheduled_end)",
     "method": "exact"},
    {"identity": "on_duty_hours = release - actual_start", "method": "tolerance"},
    {"identity": "past_scheduled_end_hours = overrun", "method": "tolerance"},
    {"identity": "neither + after_closing_only + past_scheduled_end_only + both = on_duty_hours", "method": "tolerance"},
    {"identity": "after_closing = after_closing_only + both; past_scheduled_end = past_scheduled_end_only + both",
     "method": "tolerance"},
    {"identity": "union = after_closing + past_scheduled_end - both", "method": "tolerance"},
    {"identity": "both <= after_closing and both <= past_scheduled_end", "method": "exact"},
    {"identity": "sum of hours_by_state = on_duty_hours", "method": "tolerance"},
    {"identity": "break: delay = actual_start - scheduled_start; actual_start >= due; actual_start < actual_end; "
                 "truncated actual_end = closing_time", "method": "exact"},
    {"identity": "completed break: actual_hours = configured_hours", "method": "tolerance"},
    {"identity": "shift ON_BREAK hours = actual_break_hours_total", "method": "tolerance"},
    {"identity": "per employee and on-duty state: sum over shifts = state_totals", "method": "tolerance"},
    {"identity": "per employee: sum of state_totals = finish - begin", "method": "tolerance"},
]

_TIMELINE_LISTS = ("intervals", "shifts", "breaks")
_INTERVAL_FIELDS = ("employee_id", "start", "end", "state", "shift_index", "after_closing", "past_scheduled_end")
_SHIFT_FIELDS = ("employee_id", "shift_index", "scheduled_start", "scheduled_end", "activated", "actual_start",
                 "activation_delay", "release", "release_trigger", "release_basis", "overrun", "not_activated_reason")
_BREAK_FIELDS = ("employee_id", "shift_index", "name", "duration_minutes", "scheduled_start", "due", "actual_start",
                 "actual_end", "delay", "outcome", "unfulfilled_cause")


class NamedAttributionError(Exception):
    """A check failed, so no attribution is produced. ``failure`` holds the check, message, and evidence."""

    def __init__(self, failure: dict[str, Any]) -> None:
        super().__init__(f"{failure['check']}: {failure['message']}")
        self.failure = failure


class _Violation(Exception):
    def __init__(self, failure: dict[str, Any]) -> None:
        super().__init__(failure["message"])
        self.failure = failure


def _fail(check: str, message: str, evidence: dict[str, Any] | None = None) -> _Violation:
    return _Violation({"check": check, "message": message, "evidence": evidence or {}})


def _close_enough(a: float, b: float) -> bool:
    try:
        return math.isclose(a, b, rel_tol=TOLERANCE["rel"], abs_tol=TOLERANCE["abs"])
    except OverflowError:  # an exact (for example Fraction) value beyond the float range is not close to anything
        return False


def _time(value: object) -> bool:
    if not isinstance(value, Real) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:  # a whole number or fraction beyond the float range
        return False


def _whole(value: object) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def _fsum(values: Iterable[float], field: str, record: dict[str, Any]) -> float:
    try:
        return math.fsum(values)
    except (OverflowError, ValueError):
        raise _fail("finite_nonnegative", f"{field} is not a finite number of hours.",
                    {"field": field, "record": record}) from None


# ── D7: derived durations ───────────────────────────────────────────────────


def _derived(field: str, a: float, b: float, record: dict[str, Any]) -> float:
    """``a - b`` for a duration whose true value is nonnegative, under the approved D7 rule."""
    a, b = float(a), float(b)  # the operands passed record_structure, so each converts to a finite float
    x = a - b
    if not math.isfinite(x):
        raise _fail("finite_nonnegative", f"{field} is not a finite number of hours.",
                    {"field": field, "record": record, "a": a, "b": b, "x": x})
    if x >= 0:
        return x if x > 0 else 0.0
    if _close_enough(a, b):
        return 0.0
    raise _fail("finite_nonnegative", f"{field} is below zero beyond the house tolerance (D7).",
                {"field": field, "record": record, "a": a, "b": b, "x": x,
                 "tolerance": max(TOLERANCE["rel"] * max(abs(a), abs(b)), TOLERANCE["abs"])})


def derived_duration(a: float, b: float, *, field: str) -> float:
    """The D7 rule on its own: ``a - b``, 0.0 for a tiny negative within the house tolerance, else a failure."""
    try:
        if not (_time(a) and _time(b)):
            raise _fail("finite_nonnegative", f"{field} needs two finite real operands.", {"a": a, "b": b})
        return _derived(field, a, b, {})
    except _Violation as violation:
        raise NamedAttributionError(violation.failure) from None


# ── Structure, versions, and identity ───────────────────────────────────────


def _check_fields(kind: str, index: int, record: object, names: Sequence[str]) -> dict[str, Any]:
    if not isinstance(record, dict) or any(name not in record for name in names):
        raise _fail("record_structure", f"A {kind} record lacks the engine's fields.",
                    {"record_type": kind, "index": index, "required": list(names),
                     "record": dict(record) if isinstance(record, dict) else record})
    return record


def _type_error(kind: str, index: int, field: str, value: object, expected: str) -> _Violation:
    return _fail("record_structure", f"{kind}[{index}].{field} must be {expected}.",
                 {"record_type": kind, "index": index, "field": field, "value": value})


def _check_structure(result: object) -> dict[str, Any]:
    if not isinstance(result, dict) or not isinstance(result.get("provenance"), dict) or not isinstance(
            result.get("employee_timeline"), dict) or "closing_policy" not in result:
        raise _fail("record_structure", "The result must be a named-engine result with provenance, closing_policy, "
                    "and employee_timeline.", {"keys": sorted(map(str, result)) if isinstance(result, dict) else None})
    return result


def _check_versions(result: dict[str, Any]) -> None:
    provenance = result["provenance"]
    found = {"engine_version": provenance.get("engine_version"),
             "state_machine_version": provenance.get("state_machine_version")}
    expected = {"engine_version": NAMED_ENGINE_VERSION, "state_machine_version": STATE_MACHINE_VERSION}
    if any(not isinstance(found[key], str) or found[key] != expected[key] for key in expected):
        raise _fail("source_versions", "The result comes from another engine or state-machine version.",
                    {"found": found, "expected": expected})


def _check_timeline(result: dict[str, Any]) -> dict[str, Any]:
    policy = result["closing_policy"]
    if not isinstance(policy, str) or policy not in CLOSING_POLICIES:
        raise _fail("record_structure", "The closing policy must be exactly DRAIN or HARD_CUTOFF.",
                    {"closing_policy": policy, "approved": list(CLOSING_POLICIES)})
    replication = result.get("replication")
    if replication is not None and not (
            isinstance(replication, dict) and _whole(replication.get("seed_entropy"))
            and isinstance(replication.get("spawn_key"), (list, tuple))
            and isinstance(replication.get("customer_inputs"), dict)
            and isinstance(replication["customer_inputs"].get("sha256"), str)):
        raise _fail("record_structure", "The replication block lacks the seed identity or the customer-inputs digest.",
                    {"replication": replication})
    timeline = result["employee_timeline"]
    for key in ("begin", "finish", "closing_time"):
        if not _time(timeline.get(key)):
            raise _fail("record_structure", f"employee_timeline.{key} must be a finite number of hours.",
                        {"field": key, "value": timeline.get(key)})
    for key in _TIMELINE_LISTS:
        if not isinstance(timeline.get(key), (list, tuple)):
            raise _fail("record_structure", f"employee_timeline.{key} must be a list.", {"field": key})
    if not isinstance(timeline.get("state_totals"), dict):
        raise _fail("record_structure", "employee_timeline.state_totals must be a mapping.", {})
    for index, item in enumerate(timeline["intervals"]):
        row = _check_fields("intervals", index, item, _INTERVAL_FIELDS)
        for field in ("start", "end"):
            if not _time(row[field]):
                raise _type_error("intervals", index, field, row[field], "a finite number of hours")
        if not isinstance(row["state"], str) or row["state"] not in BASE_STATES:
            raise _type_error("intervals", index, "state", row["state"], "one of the engine's base states")
        if row["shift_index"] is not None and not _whole(row["shift_index"]):
            raise _type_error("intervals", index, "shift_index", row["shift_index"], "a whole number or None")
        for field in ("after_closing", "past_scheduled_end"):
            if not isinstance(row[field], bool):
                raise _type_error("intervals", index, field, row[field], "True or False")
    for index, item in enumerate(timeline["shifts"]):
        row = _check_fields("shifts", index, item, _SHIFT_FIELDS)
        if not _whole(row["shift_index"]):
            raise _type_error("shifts", index, "shift_index", row["shift_index"], "a whole number")
        for field in ("scheduled_start", "scheduled_end"):
            if not _time(row[field]):
                raise _type_error("shifts", index, field, row[field], "a finite number of hours")
        if not isinstance(row["activated"], bool):
            raise _type_error("shifts", index, "activated", row["activated"], "True or False")
        for field in ("actual_start", "activation_delay", "release", "overrun"):
            if row[field] is not None and not _time(row[field]):
                raise _type_error("shifts", index, field, row[field], "a finite number of hours or None")
        for field in ("release_trigger", "release_basis", "not_activated_reason"):
            if row[field] is not None and not isinstance(row[field], str):
                raise _type_error("shifts", index, field, row[field], "text or None")
    for index, item in enumerate(timeline["breaks"]):
        row = _check_fields("breaks", index, item, _BREAK_FIELDS)
        if not _whole(row["shift_index"]):
            raise _type_error("breaks", index, "shift_index", row["shift_index"], "a whole number")
        if not isinstance(row["name"], str):
            raise _type_error("breaks", index, "name", row["name"], "text")
        if not _whole(row["duration_minutes"]) or row["duration_minutes"] < 1 or not _time(row["duration_minutes"]):
            raise _type_error("breaks", index, "duration_minutes", row["duration_minutes"], "a whole number, 1 or more")
        if not _time(row["scheduled_start"]):
            raise _type_error("breaks", index, "scheduled_start", row["scheduled_start"], "a finite number of hours")
        for field in ("due", "actual_start", "actual_end", "delay"):
            if row[field] is not None and not _time(row[field]):
                raise _type_error("breaks", index, field, row[field], "a finite number of hours or None")
        if not isinstance(row["outcome"], str):
            raise _type_error("breaks", index, "outcome", row["outcome"], "text")
        if row["unfulfilled_cause"] is not None and not isinstance(row["unfulfilled_cause"], str):
            raise _type_error("breaks", index, "unfulfilled_cause", row["unfulfilled_cause"], "text or None")
    for employee_id, totals in timeline["state_totals"].items():
        if not isinstance(totals, dict) or not all(isinstance(key, str) for key in totals) or set(totals) != set(
                BASE_STATES) or not all(_time(value) for value in totals.values()):
            raise _fail("record_structure", "Each state_totals entry must give finite hours for every base state.",
                        {"employee_id": employee_id, "state_totals": totals})
    return timeline


def _check_employees(timeline: dict[str, Any], employees: object) -> list[str]:
    if not isinstance(employees, (list, tuple)) or not all(isinstance(item, Employee) for item in employees):
        raise _fail("employee_identity", "employees must be the run's input list of Employee.",
                    {"employees_type": type(employees).__name__})
    input_ids = [item.employee_id for item in employees]
    if not all(isinstance(employee_id, str) for employee_id in input_ids) or len(set(input_ids)) != len(input_ids):
        raise _fail("employee_identity", "The input employee ids must be distinct strings.", {"input_ids": input_ids})
    keys = list(timeline["state_totals"])
    if not all(isinstance(key, str) for key in keys) or set(keys) != set(input_ids):
        raise _fail("employee_identity", "The employee timeline's employees (state_totals keys) differ from the "
                    "run's input employees.", {"timeline_employees": keys, "input_employees": input_ids})
    known = frozenset(input_ids)
    for block in _TIMELINE_LISTS:
        for index, row in enumerate(timeline[block]):
            employee_id = row["employee_id"]
            if not isinstance(employee_id, str) or employee_id not in known:
                raise _fail("employee_identity", f"A {block} record names an employee who is not an input employee.",
                            {"record_type": block, "index": index, "employee_id": employee_id,
                             "input_employees": sorted(known)})
    return sorted(known)


def _check_shift_identity(
    timeline: dict[str, Any],
) -> tuple[dict[tuple[str, int], dict[str, Any]], dict[tuple[str, int], list[dict[str, Any]]]]:
    shifts: dict[tuple[str, int], dict[str, Any]] = {}
    for index, row in enumerate(timeline["shifts"]):
        key = (row["employee_id"], int(row["shift_index"]))
        if key in shifts:
            raise _fail("shift_identity", "Two shift records share (employee_id, shift_index).",
                        {"index": index, "employee_id": key[0], "shift_index": key[1]})
        shifts[key] = row
    for index, row in enumerate(timeline["intervals"]):
        if row["shift_index"] is not None and (row["employee_id"], int(row["shift_index"])) not in shifts:
            raise _fail("shift_identity", "An interval names a shift the employee does not have.",
                        {"index": index, "interval": dict(row)})
    breaks: dict[tuple[str, int], list[dict[str, Any]]] = {key: [] for key in shifts}
    for index, row in enumerate(timeline["breaks"]):
        key = (row["employee_id"], int(row["shift_index"]))
        if key not in shifts:
            raise _fail("shift_identity", "A break names a shift the employee does not have.",
                        {"index": index, "break": dict(row)})
        if any(item["name"] == row["name"] for item in breaks[key]):
            raise _fail("shift_identity", "Two breaks of one shift share a name.",
                        {"index": index, "employee_id": key[0], "shift_index": key[1], "name": row["name"]})
        breaks[key].append(row)
    return shifts, breaks


def _check_geometry(
    timeline: dict[str, Any], employee_ids: list[str], shifts: dict[tuple[str, int], dict[str, Any]],
) -> dict[tuple[str, int], list[dict[str, Any]]]:
    begin, finish, closing = timeline["begin"], timeline["finish"], timeline["closing_time"]
    by_employee: dict[str, list[dict[str, Any]]] = {employee_id: [] for employee_id in employee_ids}
    for row in timeline["intervals"]:
        by_employee[row["employee_id"]].append(row)
    by_shift: dict[tuple[str, int], list[dict[str, Any]]] = {key: [] for key in shifts}
    for employee_id in employee_ids:
        expected = begin
        for row in by_employee[employee_id]:
            evidence = {"employee_id": employee_id, "interval": dict(row)}
            if row["start"] != expected or not row["end"] > row["start"]:
                raise _fail("interval_geometry", "The employee's intervals are not contiguous with positive length.",
                            {**evidence, "expected_start": expected})
            expected = row["end"]
            on_shift = row["shift_index"] is not None
            if on_shift != (row["state"] != OFF):
                raise _fail("interval_geometry", "An interval has a shift if and only if its state is not OFF.", evidence)
            if row["after_closing"] != (row["start"] >= closing) or (not row["after_closing"] and row["end"] > closing):
                raise _fail("interval_geometry", "after_closing disagrees with the interval's position against closing.",
                            {**evidence, "closing_time": closing})
            if on_shift:
                key = (employee_id, int(row["shift_index"]))
                scheduled_end = shifts[key]["scheduled_end"]
                if row["past_scheduled_end"] != (row["start"] >= scheduled_end) or (
                        not row["past_scheduled_end"] and row["end"] > scheduled_end):
                    raise _fail("interval_geometry", "past_scheduled_end disagrees with the interval's position against "
                                "the shift's scheduled end.", {**evidence, "scheduled_end": scheduled_end})
                by_shift[key].append(row)
            elif row["past_scheduled_end"]:
                raise _fail("interval_geometry", "An OFF interval is flagged past a scheduled end.", evidence)
        if expected != finish:
            raise _fail("interval_geometry", "The employee's intervals do not reach the timeline finish.",
                        {"employee_id": employee_id, "last_end": expected, "finish": finish})
    return by_shift


# ── Per-shift attribution ───────────────────────────────────────────────────


def _lengths(rows: Sequence[dict[str, Any]], keep: Any) -> list[float]:
    return [row["end"] - row["start"] for row in rows if keep(row)]


def _shift_quantities(row: dict[str, Any], rows: list[dict[str, Any]], record: dict[str, Any]) -> dict[str, Any]:
    """shift_reconciliation, closing_partition, and base_state_partition for one activated shift."""
    actual_start, release = row["actual_start"], row["release"]
    evidence = {**record, "shift": dict(row)}
    if release is None or row["activation_delay"] is None or row["overrun"] is None:
        raise _fail("shift_reconciliation", "An activated shift lacks its release, activation delay, or overrun.",
                    evidence)
    if not actual_start >= row["scheduled_start"]:
        raise _fail("shift_reconciliation", "The shift starts before its scheduled start.", evidence)
    if not rows or rows[0]["start"] != actual_start or rows[-1]["end"] != release or any(
            first["end"] != second["start"] for first, second in zip(rows, rows[1:])):
        raise _fail("shift_reconciliation", "The shift's intervals do not tile [actual_start, release) exactly.",
                    {**evidence, "intervals": [dict(item) for item in rows]})
    if row["activation_delay"] != actual_start - row["scheduled_start"] or row["overrun"] != max(
            0.0, release - row["scheduled_end"]):
        raise _fail("shift_reconciliation", "activation_delay or overrun differs from the engine's formula.", evidence)
    on_duty = _fsum(_lengths(rows, lambda item: True), "on_duty_hours", record)
    if not _close_enough(on_duty, release - actual_start):
        raise _fail("shift_reconciliation", "on_duty_hours differs from release - actual_start beyond the tolerance.",
                    {**evidence, "on_duty_hours": on_duty})
    cells = {
        "neither_hours": _lengths(rows, lambda item: not item["after_closing"] and not item["past_scheduled_end"]),
        "after_closing_only_hours": _lengths(rows, lambda item: item["after_closing"] and not item["past_scheduled_end"]),
        "past_scheduled_end_only_hours": _lengths(
            rows, lambda item: item["past_scheduled_end"] and not item["after_closing"]),
        "after_closing_and_past_scheduled_end_hours": _lengths(
            rows, lambda item: item["after_closing"] and item["past_scheduled_end"]),
        "after_closing_hours": _lengths(rows, lambda item: item["after_closing"]),
        "past_scheduled_end_hours": _lengths(rows, lambda item: item["past_scheduled_end"]),
        "after_closing_or_past_scheduled_end_hours": _lengths(
            rows, lambda item: item["after_closing"] or item["past_scheduled_end"]),
    }
    closing = {name: _fsum(cells[name], name, record) for name in CLOSING_CELLS}
    if not _close_enough(closing["past_scheduled_end_hours"], row["overrun"]):
        raise _fail("shift_reconciliation", "past_scheduled_end_hours differs from overrun beyond the tolerance.",
                    {**evidence, "past_scheduled_end_hours": closing["past_scheduled_end_hours"]})
    after, past, both = (closing["after_closing_hours"], closing["past_scheduled_end_hours"],
                         closing["after_closing_and_past_scheduled_end_hours"])
    partition = _fsum([closing["neither_hours"], closing["after_closing_only_hours"],
                       closing["past_scheduled_end_only_hours"], both], "closing cells", record)
    if not (_close_enough(partition, on_duty) and _close_enough(after, closing["after_closing_only_hours"] + both)
            and _close_enough(past, closing["past_scheduled_end_only_hours"] + both)
            and _close_enough(closing["after_closing_or_past_scheduled_end_hours"], after + past - both)
            and both <= after and both <= past):
        raise _fail("closing_partition", "The closing and shift-end cells do not reconcile.",
                    {**evidence, "closing_attribution": closing, "on_duty_hours": on_duty})
    by_state = {state: _fsum(_lengths(rows, lambda item, state=state: item["state"] == state), state, record)
                for state in ON_DUTY_STATES}
    if not _close_enough(_fsum(by_state.values(), "hours_by_state", record), on_duty):
        raise _fail("base_state_partition", "The shift's hours by base state do not sum to on_duty_hours.",
                    {**evidence, "hours_by_state": by_state, "on_duty_hours": on_duty})
    return {"on_duty_hours": on_duty, "hours_by_state": by_state, "closing_attribution": closing}


def _break_record(row: dict[str, Any], closing_time: float, record: dict[str, Any]) -> dict[str, Any]:
    """break_reconciliation and the D7 durations for one break."""
    evidence = {**record, "break": dict(row)}
    outcome, cause = row["outcome"], row["unfulfilled_cause"]
    if outcome not in BREAK_OUTCOMES or (cause not in UNFULFILLED_CAUSES if outcome == UNFULFILLED else cause is not None):
        raise _fail("break_reconciliation", "The break's outcome or cause is not in the engine's vocabulary.", evidence)
    started = row["actual_start"] is not None
    if started != (outcome != UNFULFILLED):
        raise _fail("break_reconciliation", "A break is started if and only if its outcome is not unfulfilled.",
                    evidence)
    configured = row["duration_minutes"] / 60.0
    output = {
        "name": row["name"], "configured_minutes": row["duration_minutes"], "configured_hours": configured,
        "scheduled_start_hours": row["scheduled_start"], "due_hours": row["due"],
        "actual_start_hours": row["actual_start"], "actual_end_hours": row["actual_end"],
        "outcome": outcome, "unfulfilled_cause": cause,
        "delay_from_scheduled_hours": None, "delay_from_due_hours": None, "actual_hours": None,
        "shortened_hours": None, "unfulfilled_hours": configured,
    }
    if not started:
        if row["actual_end"] is not None or row["delay"] is not None:
            raise _fail("break_reconciliation", "An unfulfilled break has an actual end or a delay.", evidence)
        return output
    start, end, due = row["actual_start"], row["actual_end"], row["due"]
    if end is None or due is None or row["delay"] is None:
        raise _fail("break_reconciliation", "A started break lacks its due time, actual end, or delay.", evidence)
    if row["delay"] != start - row["scheduled_start"]:
        raise _fail("break_reconciliation", "delay differs from actual_start - scheduled_start.", evidence)
    if not start >= due or not start < end:
        raise _fail("break_reconciliation", "A started break must satisfy due <= actual_start < actual_end (exact).",
                    evidence)
    actual = _derived("actual_hours", end, start, record)
    if outcome == COMPLETED:
        if not _close_enough(actual, configured):
            raise _fail("break_reconciliation", "A completed break does not last its configured duration.",
                        {**evidence, "actual_hours": actual, "configured_hours": configured})
        shortened = 0.0  # P1: a completed break lasts its configured duration; not computed by subtraction
    else:
        if end != closing_time:
            raise _fail("break_reconciliation", "A break truncated by closing does not end exactly at closing.",
                        {**evidence, "closing_time": closing_time})
        shortened = _derived("shortened_hours", configured, actual, record)
    output.update({
        "delay_from_scheduled_hours": _derived("delay_from_scheduled_hours", start, row["scheduled_start"], record),
        "delay_from_due_hours": _derived("delay_from_due_hours", start, due, record),
        "actual_hours": actual, "shortened_hours": shortened, "unfulfilled_hours": 0.0,
    })
    return output


def _break_totals(breaks: Sequence[dict[str, Any]], record: dict[str, Any]) -> dict[str, Any]:
    started = [item for item in breaks if item["outcome"] != UNFULFILLED]
    unfulfilled = [item for item in breaks if item["outcome"] == UNFULFILLED]

    def total(field: str, rows: Sequence[dict[str, Any]]) -> float:
        return _fsum([item[field] for item in rows], f"{field}_total", record)

    return {
        "breaks_scheduled": len(breaks),
        "breaks_completed": sum(1 for item in breaks if item["outcome"] == COMPLETED),
        "breaks_truncated_by_closing": sum(1 for item in breaks if item["outcome"] == TRUNCATED_BY_CLOSING),
        "breaks_unfulfilled_by_cause": {cause: sum(1 for item in unfulfilled if item["unfulfilled_cause"] == cause)
                                        for cause in UNFULFILLED_CAUSES},
        "delay_from_scheduled_hours_total": total("delay_from_scheduled_hours", started),
        "delay_from_due_hours_total": total("delay_from_due_hours", started),
        "actual_break_hours_total": total("actual_hours", started),
        "shortened_hours_total": total("shortened_hours", started),
        "unfulfilled_hours_total": total("unfulfilled_hours", unfulfilled),
    }


def _shift_record(row: dict[str, Any], rows: list[dict[str, Any]], breaks: list[dict[str, Any]],
                  closing_time: float) -> dict[str, Any]:
    record = {"employee_id": row["employee_id"], "shift_index": int(row["shift_index"])}
    scheduled_duration = _derived("scheduled_duration_hours", row["scheduled_end"], row["scheduled_start"], record)
    activated = row["activated"]
    if activated != (row["actual_start"] is not None):
        raise _fail("shift_reconciliation", "activated disagrees with actual_start.", {**record, "shift": dict(row)})
    quantities: dict[str, Any] = {"on_duty_hours": None, "hours_by_state": None, "closing_attribution": None}
    if activated:
        quantities = _shift_quantities(row, rows, record)
    elif rows or any(row[field] is not None for field in ("release", "activation_delay", "overrun")):
        raise _fail("shift_reconciliation", "A shift that was not activated has intervals, a release, an activation "
                    "delay, or an overrun.", {**record, "shift": dict(row), "intervals": [dict(item) for item in rows]})
    break_rows = [_break_record(item, closing_time, {**record, "name": item["name"]}) for item in breaks]
    totals = _break_totals(break_rows, record)
    on_break = 0.0 if quantities["hours_by_state"] is None else quantities["hours_by_state"][ON_BREAK]
    if not _close_enough(on_break, totals["actual_break_hours_total"]):
        raise _fail("break_reconciliation", "The shift's ON_BREAK hours differ from its started breaks' actual hours.",
                    {**record, "on_break_hours": on_break, "actual_break_hours_total": totals["actual_break_hours_total"]})
    by_state = quantities["hours_by_state"]
    return {
        "employee_id": row["employee_id"], "shift_index": int(row["shift_index"]), "activated": activated,
        "not_activated_reason": row["not_activated_reason"], "release_trigger": row["release_trigger"],
        "release_basis": row["release_basis"],
        "scheduled_start_hours": row["scheduled_start"], "scheduled_end_hours": row["scheduled_end"],
        "scheduled_duration_hours": scheduled_duration,
        "actual_start_hours": row["actual_start"] if activated else None,
        "release_hours": row["release"] if activated else None,
        "activation_delay_hours": row["activation_delay"] if activated else None,
        "overrun_hours": row["overrun"] if activated else None,
        "on_duty_hours": quantities["on_duty_hours"],
        "hours_by_state": by_state,
        "register_wait_hours": None if by_state is None else by_state[WAITING_FOR_REGISTER],
        "closing_attribution": quantities["closing_attribution"],
        "breaks": break_rows,
        "break_totals": totals,
    }


# ── Per-employee summary and output checks ──────────────────────────────────


def _employee_record(employee_id: str, shifts: list[dict[str, Any]], totals: dict[str, float],
                     span: float) -> dict[str, Any]:
    record = {"employee_id": employee_id}
    activated = [item for item in shifts if item["activated"]]
    for state in ON_DUTY_STATES:
        summed = _fsum([item["hours_by_state"][state] for item in activated], state, record)
        if not _close_enough(summed, totals[state]):
            raise _fail("employee_reconciliation", "The employee's shift hours differ from state_totals.",
                        {**record, "state": state, "shift_sum": summed, "state_totals": totals[state]})
    total = _fsum(totals.values(), "state_totals", record)
    if not _close_enough(total, span):
        raise _fail("employee_reconciliation", "The employee's state_totals do not sum to finish - begin.",
                    {**record, "state_totals_sum": total, "finish_minus_begin": span})
    counts = ("breaks_scheduled", "breaks_completed", "breaks_truncated_by_closing")
    return {
        "employee_id": employee_id,
        "shift_count": len(shifts),
        "activated_shift_count": len(activated),
        "off_hours": totals[OFF],
        **{field: _fsum([item[field] for item in activated], field, record) for field in SHIFT_SUM_FIELDS},
        "hours_by_state": {state: _fsum([item["hours_by_state"][state] for item in activated], state, record)
                           for state in ON_DUTY_STATES},
        "closing_attribution": {name: _fsum([item["closing_attribution"][name] for item in activated], name, record)
                                for name in CLOSING_CELLS},
        "break_totals": {
            **{field: sum(item["break_totals"][field] for item in shifts) for field in counts},
            "breaks_unfulfilled_by_cause": {
                cause: sum(item["break_totals"]["breaks_unfulfilled_by_cause"][cause] for item in shifts)
                for cause in UNFULFILLED_CAUSES},
            **{field: _fsum([item["break_totals"][field] for item in shifts], field, record)
               for field in BREAK_HOURS_TOTALS},
        },
    }


def _durations(item: dict[str, Any]) -> list[tuple[str, Any]]:
    """Every duration of a shift or employee record (never an instant), with its name."""
    values = [(field, item[field]) for field in SHIFT_SUM_FIELDS if field in item]
    values += [(field, item[field]) for field in ("off_hours",) if field in item]
    for block in ("hours_by_state", "closing_attribution"):
        if item[block] is not None:
            values += [(f"{block}.{key}", value) for key, value in item[block].items()]
    values += [(f"break_totals.{field}", item["break_totals"][field]) for field in BREAK_HOURS_TOTALS]
    for row in item.get("breaks", []):
        values += [(f"breaks[{row['name']}].{field}", row[field]) for field in BREAK_DURATION_FIELDS]
    return values


def _check_outputs(shifts: list[dict[str, Any]], employees: list[dict[str, Any]]) -> None:
    for item in [*shifts, *employees]:
        for field, value in _durations(item):
            if value is not None and not (math.isfinite(value) and value >= 0):
                raise _fail("finite_nonnegative", f"{field} is not a finite number of hours, 0 or more.",
                            {"employee_id": item["employee_id"], "shift_index": item.get("shift_index"),
                             "field": field, "value": value})


# ── Entry point ─────────────────────────────────────────────────────────────


def _build(result: object, employees: object) -> dict[str, Any]:
    checked = _check_structure(result)
    _check_versions(checked)
    timeline = _check_timeline(checked)
    employee_ids = _check_employees(timeline, employees)
    shifts, breaks = _check_shift_identity(timeline)
    by_shift = _check_geometry(timeline, employee_ids, shifts)
    closing_time = timeline["closing_time"]
    shift_records = []
    for row in timeline["shifts"]:
        key = (row["employee_id"], int(row["shift_index"]))
        shift_records.append(_shift_record(row, by_shift[key], breaks[key], closing_time))
    span = timeline["finish"] - timeline["begin"]
    employee_records = [
        _employee_record(employee_id, [item for item in shift_records if item["employee_id"] == employee_id],
                         timeline["state_totals"][employee_id], span)
        for employee_id in employee_ids
    ]
    _check_outputs(shift_records, employee_records)
    provenance = checked["provenance"]
    replication = checked.get("replication")
    return {
        "shifts": shift_records,
        "employees": employee_records,
        "reconciliation": [dict(item) for item in RECONCILIATION],
        "definitions": dict(DEFINITIONS),
        "checks": dict(CHECKS),
        "undetermined": list(UNDETERMINED),
        "provenance": {
            "attribution_version": ATTRIBUTION_VERSION,
            "named_engine_version": provenance["engine_version"],
            "state_machine_version": provenance["state_machine_version"],
            "closing_policy": checked["closing_policy"],
            "begin_hours": timeline["begin"],
            "closing_hours": closing_time,
            "finish_hours": timeline["finish"],
            "replication": None if replication is None else {
                "seed_entropy": replication["seed_entropy"],
                "spawn_key": list(replication["spawn_key"]),
                "customer_inputs_sha256": replication["customer_inputs"]["sha256"],
            },
            "source": "result['employee_timeline'] only; no customer trace; nothing synthesized",
            "time_unit": "hours from the horizon start",
            "tolerance": dict(TOLERANCE, applies_to=(
                "reconciliation checks and the D7 derived-duration rule only; times and event order compare exactly")),
            "monetary_cost": "None: quantities only; pay and cost are Phase 5B-5",
            "inputs_sha256": None,
            "inputs_sha256_reason": (
                "full run inputs unavailable: build_named_attribution receives only the result and the input "
                "employees, and no partial digest is computed (D4)"),
        },
    }


def build_named_attribution(result: dict[str, Any], employees: Sequence[Employee]) -> dict[str, Any]:
    """Per employee x shift attribution of one named-engine result; raises ``NamedAttributionError`` on any failure.

    ``result`` is a ``simulate_named_prescribed`` or ``simulate_named_replication`` result, and ``employees`` the run's
    input employees (the authoritative employee set). Neither has a default. A replication of a stored run is first
    regenerated through the 5B-4.4 path (``simulate_named_replication`` with ``replication_seed_sequence``).
    """
    try:
        return _build(result, employees)
    except _Violation as violation:
        raise NamedAttributionError(violation.failure) from None
