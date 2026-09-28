"""Named-employee state machine for the shared queue (Phase 5B-4.2 of the shared-queue enhancement).

The employee, break, shift, and register timeline of a validated Phase 5B-1 roster. There are
no customers, no queue, no service-time generation, and no random numbers: service starts and
completions are explicit caller inputs (``ServiceStart``, ``ServiceCompletion``), and nothing
here invents a service duration. Closing inputs (``Release``, ``EndBreakAtClosing``,
``CancelPendingBreaks``, and ``hold_past_shift_end``) represent the P5, P6, and P7 alternatives
without selecting one.

Specs: docs/superpowers/specs/2026-09-28-shared-queue-named-employee-des-policy.md (the approved
policy contract) and docs/superpowers/specs/2026-09-28-shared-queue-employee-state-machine.md.

Nothing legacy imports this module. It uses none of the separate-queue break code
(``PRE_BREAK_CUTOFF_MINUTES``, ``queue_lifecycle``, or the ``separate_optimization`` break
controller), and its event names carry an ``employee_`` prefix.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from numbers import Real
from typing import Any

from backend.queueing_engine.services.shared_segments import OperatingHorizon, SharedSegmentError
from backend.queueing_engine.services.shared_workforce import (
    INVALID,
    Employee,
    ScheduledShift,
    WorkforceRules,
    evaluate_roster,
)

STATE_MACHINE_VERSION = "novaq-shared-employee-states-v1"

# Base states. Exactly one holds for each employee at every instant.
OFF = "OFF"
WAITING_FOR_REGISTER = "WAITING_FOR_REGISTER"
AVAILABLE = "AVAILABLE"
SERVING = "SERVING"
SERVING_BREAK_DUE = "SERVING_BREAK_DUE"
SERVING_SHIFT_ENDED = "SERVING_SHIFT_ENDED"
ON_BREAK = "ON_BREAK"
BASE_STATES = (OFF, WAITING_FOR_REGISTER, AVAILABLE, SERVING, SERVING_BREAK_DUE, SERVING_SHIFT_ENDED, ON_BREAK)
REGISTER_STATES = frozenset({AVAILABLE, SERVING, SERVING_BREAK_DUE, SERVING_SHIFT_ENDED})
SERVING_STATES = frozenset({SERVING, SERVING_BREAK_DUE, SERVING_SHIFT_ENDED})

# Same-time stages, in processing order. X2 orders the employee-only events (completions, shift
# ends, break ends, breaks due, shift starts, register handovers, then the assignment pass). X2
# does not place closing; closing and the closing inputs come right after completions.
COMPLETION = "completion"
CLOSING = "closing"
CLOSING_INPUT = "closing_input"
SHIFT_END = "shift_end"
BREAK_END = "break_end"
BREAK_DUE = "break_due"
SHIFT_START = "shift_start"
REGISTER_HANDOVER = "register_handover"
SERVICE_START = "service_start"
STAGES = (COMPLETION, CLOSING, CLOSING_INPUT, SHIFT_END, BREAK_END, BREAK_DUE, SHIFT_START, REGISTER_HANDOVER,
          SERVICE_START)

# Terminal break outcomes.
COMPLETED, TRUNCATED_BY_CLOSING, UNFULFILLED = "completed", "truncated_by_closing", "unfulfilled"
BREAK_OUTCOMES = (COMPLETED, TRUNCATED_BY_CLOSING, UNFULFILLED)

# Why a release became due: the scheduled shift end, or a Release input after closing.
SCHEDULED_SHIFT_END, RELEASE_INPUT = "scheduled_shift_end", "release_input"

DEFINITIONS = {
    "time_unit": (
        "Hours from the horizon start: roster minute m becomes (m - horizon start minute) / 60, the "
        "anonymous engine's conversion. The timeline begins at the earlier of the horizon start and the "
        "earliest scheduled shift start; closing is the horizon end."
    ),
    "states": {
        OFF: "Not on duty: before a shift, between split shifts, or after release. No register.",
        WAITING_FOR_REGISTER: "On duty, not on a break, and waiting for a free register. No register.",
        AVAILABLE: "At a register and idle; may start a service.",
        SERVING: "At a register and serving; may take the next service after this one.",
        SERVING_BREAK_DUE: "At a register and serving; a break is due and starts at the completion.",
        SERVING_SHIFT_ENDED: (
            "At a register and serving the last service before release; released at the completion. "
            "The release is due because the scheduled shift end passed or because a Release input "
            "was applied after closing (see the shift's release_basis)."
        ),
        ON_BREAK: "On a break. No register.",
    },
    "same_time_order": (
        "At one instant: service completions, then closing, then closing inputs (in their given order), "
        "then shift ends, break ends, breaks due, shift starts, register handovers, and service starts. "
        "Within a stage, employees are taken in employee_id order."
    ),
    "registers": (
        "Registers are identified 1..K. Waiting employees take free registers in order of earliest wait "
        "start, then employee_id, and the lowest-numbered free register is assigned first. Occupancy never "
        "exceeds K."
    ),
    "breaks": (
        "A shift's first break falls due at its scheduled start; a later break at the later of its "
        "scheduled start and the previous break's actual end plus the rule's min_gap_minutes. A due break "
        "starts at once unless the employee is serving, in which case it starts at the completion (no "
        "pre-break cutoff). It lasts its full configured duration from the actual start. A break not "
        "started by release is unfulfilled."
    ),
    "shifts": (
        "No pre-shift-end cutoff: a service under way at the shift end finishes first. A later split shift "
        "activates at the later of its scheduled start and the actual release plus min_minutes_between_shifts. "
        "Its scheduled end does not move; if the delayed activation is at or after it, the shift is not "
        "activated."
    ),
    "attributes": (
        "after_closing (from closing on) and past_scheduled_end (on duty at or after the current shift's "
        "scheduled end) are descriptive flags on the state intervals. They split intervals but never add "
        "elapsed time: the intervals partition the timeline by base state."
    ),
    "closing_inputs": (
        "hold_past_shift_end: when True, scheduled shift ends at or after closing release nobody, and those "
        "employees stay on duty until a Release input. Release (at or after closing): the employee's duty "
        "ends for the rest of the run; an idle or waiting employee goes OFF at once, a serving employee at "
        "the completion, and one on a break at the break end; later shifts are not activated. "
        "EndBreakAtClosing (at closing): the break in progress ends now (truncated_by_closing). "
        "CancelPendingBreaks (at closing): breaks not yet started are not taken (unfulfilled)."
    ),
}
UNDETERMINED = [
    "A break that falls due before a delayed split-shift activation (the previous shift's actual release plus "
    "the required rest passes the break's scheduled start): taken at activation or unfulfilled is UNKNOWN, so "
    "the state machine raises UndeterminedPolicyError.",
    "Closing's place among same-time events is not set by X2. Closing is processed right after completions "
    "(Phase 3A order) so that P5 (a) stays representable; this is INFERRED.",
    "A delayed split shift keeps its scheduled end (no approved rule moves it); if the delayed activation is at or "
    "after that end, the shift is not activated and its breaks are unfulfilled. This reading is INFERRED.",
    "The P5, P6, and P7 selections are UNKNOWN; the closing inputs represent each alternative without "
    "choosing one.",
]


# ── Inputs ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ServiceStart:
    """At ``time`` (hours from the horizon start), the AVAILABLE employee starts a service."""

    time: float
    employee_id: str


@dataclass(frozen=True)
class ServiceCompletion:
    """At ``time``, the employee's service under way completes."""

    time: float
    employee_id: str


@dataclass(frozen=True)
class Release:
    """At or after closing, the employee's duty ends for the rest of the run."""

    time: float
    employee_id: str


@dataclass(frozen=True)
class EndBreakAtClosing:
    """At closing, the employee's break in progress ends (outcome truncated_by_closing)."""

    time: float
    employee_id: str


@dataclass(frozen=True)
class CancelPendingBreaks:
    """At closing, the employee's breaks not yet started are not taken (outcome unfulfilled)."""

    time: float
    employee_id: str


ClosingInput = Release | EndBreakAtClosing | CancelPendingBreaks
TimelineInput = ServiceStart | ServiceCompletion | Release | EndBreakAtClosing | CancelPendingBreaks
_INPUT_TYPES = (ServiceStart, ServiceCompletion, Release, EndBreakAtClosing, CancelPendingBreaks)


class EmployeeTimelineError(ValueError):
    """An input the state machine cannot apply, such as a service start by an employee on a break."""


class UndeterminedPolicyError(EmployeeTimelineError):
    """A situation the approved policy contract does not determine (UNKNOWN); nothing is assumed."""


# ── Internal state ──────────────────────────────────────────────────────────


@dataclass
class _Break:
    name: str
    paid: bool
    duration_minutes: int
    scheduled_start: float
    duration: float
    due: float | None = None
    actual_start: float | None = None
    actual_end: float | None = None
    outcome: str | None = None
    unfulfilled_cause: str | None = None


@dataclass
class _Shift:
    index: int  # position in the roster
    scheduled_start: float
    scheduled_end: float
    gap: float  # min_gap_minutes of the shift's break rule, in hours
    breaks: list[_Break]
    actual_start: float | None = None
    release: float | None = None
    release_trigger: str | None = None
    release_basis: str | None = None
    not_activated_reason: str | None = None
    end_reached: bool = False  # the scheduled end has passed while on this shift


@dataclass
class _Employee:
    employee_id: str
    shifts: list[_Shift]
    state: str = OFF
    register: int | None = None
    recorded_register: int | None = None  # the register as of the last recorded transition
    wait_start: float | None = None
    current: _Shift | None = None
    next_index: int = 0
    last_release: float | None = None
    release_basis: str | None = None  # set while a release is due at the next completion or break end
    released_for_run: bool = False
    open_start: float = 0.0
    intervals: list[dict[str, Any]] = field(default_factory=list)


def _hours(minute: int, horizon: OperatingHorizon) -> float:
    """The anonymous engine's conversion (``shared_continuous_des._hours``)."""
    return (minute - horizon.start_minute) / 60.0


def _wait_order(employee: _Employee) -> tuple[float, str]:
    """P4: earliest wait start, then employee_id."""
    if employee.wait_start is None:
        raise EmployeeTimelineError(f"{employee.employee_id} is waiting without a wait start.")
    return employee.wait_start, employee.employee_id


def _is_time(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


_PAY_FIELDS = frozenset({"regular_rate_per_hour", "overtime_rate_per_hour", "daily_regular_paid_minutes"})


def _roster_precondition(report: dict[str, Any]) -> None:
    """X4: reject an INVALID roster, and an INCOMPLETE one unless only pay fields are missing."""
    if report["status"] == INVALID:
        raise SharedSegmentError([f"The roster is INVALID (X4): {item['message']}" for item in report["violations"]])
    other = [item for item in report["missing"] if item["field"] not in _PAY_FIELDS]
    if other:
        raise SharedSegmentError([
            f"The roster is INCOMPLETE beyond pay fields (X4): {item['field']}: {item['consequence']}"
            for item in other])


# ── State machine ───────────────────────────────────────────────────────────


class EmployeeTimeline:
    """The employee timeline of one roster, advanced one instant at a time.

    Call ``process(t, ...)`` for every instant in increasing order: each time from
    ``next_time()``, and each time at which an input applies. After ``process(t)``,
    ``start_service(t, employee_id)`` applies the assignment pass for that instant. ``result``
    closes the timeline once every employee is OFF.
    """

    def __init__(
        self,
        horizon: OperatingHorizon,
        employees: Sequence[Employee],
        rules: WorkforceRules,
        roster: Sequence[ScheduledShift],
        *,
        hold_past_shift_end: bool,
    ) -> None:
        if not isinstance(hold_past_shift_end, bool):
            raise EmployeeTimelineError("hold_past_shift_end must be True or False; there is no default.")
        report = evaluate_roster(horizon, employees, rules, roster)
        _roster_precondition(report)
        self.horizon = horizon
        self.hold_past_shift_end = hold_past_shift_end
        self.register_count = rules.register_count
        self.closing_time = _hours(horizon.end_minute, horizon)
        rest = rules.shift_rules.min_minutes_between_shifts
        self.rest: float | None = None if rest is None else rest / 60.0
        self.employees: dict[str, _Employee] = {}
        for row in report["employees"]:
            shifts = []
            for item in row["shifts"]:
                length = item["end_minute"] - item["start_minute"]
                rule = next(rule for rule in rules.break_rules
                            if rule.min_shift_minutes <= length <= rule.max_shift_minutes)
                breaks = [_Break(name=placed["name"], paid=placed["paid"], duration_minutes=placed["duration_minutes"],
                                 scheduled_start=_hours(placed["start_minute"], horizon),
                                 duration=placed["duration_minutes"] / 60.0)
                          for placed in sorted(item["breaks"], key=lambda placed: placed["start_minute"])]
                shifts.append(_Shift(index=item["shift_index"], scheduled_start=_hours(item["start_minute"], horizon),
                                     scheduled_end=_hours(item["end_minute"], horizon),
                                     gap=rule.min_gap_minutes / 60.0, breaks=breaks))
            self.employees[row["employee_id"]] = _Employee(row["employee_id"], shifts)
        self.order = sorted(self.employees)
        starts = [shift.scheduled_start for employee in self.employees.values() for shift in employee.shifts]
        self.begin = min([0.0, *starts])
        for employee in self.employees.values():
            employee.open_start = self.begin
        self.now: float | None = None
        self.closed = False
        self.holder: dict[int, str] = {}
        self.transitions: list[dict[str, Any]] = []

    # ── Scheduled times ────────────────────────────────────────────────────

    def _pending_break(self, shift: _Shift) -> _Break | None:
        return next((item for item in shift.breaks if item.actual_start is None and item.outcome is None), None)

    def _current_break(self, employee: _Employee) -> _Break:
        shift = self._shift(employee)
        return next(item for item in shift.breaks if item.actual_start is not None and item.actual_end is None)

    def _due_time(self, employee: _Employee) -> float | None:
        """When the next break falls due; None when none can fall due yet."""
        shift = employee.current
        if shift is None or employee.release_basis is not None:
            return None
        item = self._pending_break(shift)
        if item is None or item.due is not None:
            return None
        position = shift.breaks.index(item)
        if position == 0:
            return item.scheduled_start
        previous_end = shift.breaks[position - 1].actual_end
        return None if previous_end is None else max(item.scheduled_start, previous_end + shift.gap)

    def _activation_time(self, employee: _Employee) -> float | None:
        if employee.current is not None or employee.released_for_run or employee.next_index >= len(employee.shifts):
            return None
        shift = employee.shifts[employee.next_index]
        if employee.last_release is None:
            return shift.scheduled_start
        return max(shift.scheduled_start, employee.last_release + self._rest())

    def _employee_times(self, employee: _Employee) -> list[float]:
        times = [self._activation_time(employee), self._due_time(employee)]
        shift = employee.current
        if shift is not None and not shift.end_reached:
            times.append(shift.scheduled_end)
        if employee.state == ON_BREAK:
            item = self._current_break(employee)
            times.append(self._break_end(item))
        return [time for time in times if time is not None]

    def next_time(self) -> float | None:
        """The earliest scheduled instant not yet processed (closing included), or None."""
        times = [time for employee in self.employees.values() for time in self._employee_times(employee)]
        if not self.closed:
            times.append(self.closing_time)
        return min(times, default=None)

    @staticmethod
    def _break_end(item: _Break) -> float:
        assert item.actual_start is not None
        return item.actual_start + item.duration

    def _rest(self) -> float:
        if self.rest is None:  # validation allows a second shift only when the rest is supplied
            raise EmployeeTimelineError("min_minutes_between_shifts is required for a later split shift.")
        return self.rest

    # ── Recording ──────────────────────────────────────────────────────────

    @staticmethod
    def _shift(employee: _Employee) -> _Shift:
        if employee.current is None:
            raise EmployeeTimelineError(f"{employee.employee_id} is not on a shift.")
        return employee.current

    def _flush(self, employee: _Employee, t: float) -> None:
        """Record the interval [open start, t) before anything about the employee changes at t."""
        if t > employee.open_start:
            shift = employee.current
            employee.intervals.append({
                "employee_id": employee.employee_id,
                "start": employee.open_start,
                "end": t,
                "state": employee.state,
                "register_id": employee.register,
                "shift_index": None if shift is None else shift.index,
                "after_closing": self.closed,
                "past_scheduled_end": shift is not None and shift.end_reached,
            })
            employee.open_start = t

    def _set(self, employee: _Employee, t: float, stage: str, state: str, event: str) -> None:
        """Record a state change; any register change at this transition has already been made."""
        self.transitions.append({"t": t, "stage": stage, "employee_id": employee.employee_id,
                                 "from_state": employee.state, "to_state": state,
                                 "register_before": employee.recorded_register, "register_after": employee.register,
                                 "event": event})
        employee.state = state
        employee.recorded_register = employee.register

    def _free_register(self, employee: _Employee) -> None:
        if employee.register is not None:
            del self.holder[employee.register]
            employee.register = None

    # ── Transitions ────────────────────────────────────────────────────────

    def _join_wait(self, employee: _Employee, t: float, stage: str, event: str) -> None:
        self._flush(employee, t)
        employee.wait_start = t
        self._set(employee, t, stage, WAITING_FOR_REGISTER, event)

    def _start_break(self, employee: _Employee, item: _Break, t: float, stage: str, event: str) -> None:
        self._flush(employee, t)
        if item.due is None:
            item.due = t
        item.actual_start = t
        self._free_register(employee)
        employee.wait_start = None
        self._set(employee, t, stage, ON_BREAK, event)

    def _release(self, employee: _Employee, t: float, stage: str, event: str) -> None:
        """The employee leaves the current shift and goes OFF."""
        self._flush(employee, t)
        shift = self._shift(employee)
        shift.release, shift.release_trigger, shift.release_basis = t, event, employee.release_basis
        for item in shift.breaks:
            if item.actual_start is None and item.outcome is None:
                item.outcome, item.unfulfilled_cause = UNFULFILLED, "released"
        self._free_register(employee)
        employee.wait_start = None
        employee.current = None
        employee.release_basis = None
        employee.last_release = t
        self._set(employee, t, stage, OFF, event)
        self._after_release(employee, t)

    def _not_activated(self, employee: _Employee, reason: str) -> None:
        shift = employee.shifts[employee.next_index]
        shift.not_activated_reason = reason
        for item in shift.breaks:
            if item.outcome is None:
                item.outcome, item.unfulfilled_cause = UNFULFILLED, "shift_not_activated"
        employee.next_index += 1

    def _after_release(self, employee: _Employee, t: float) -> None:
        """Settle the later shifts: none after a Release input; otherwise wait for rest from release."""
        while employee.next_index < len(employee.shifts):
            if employee.released_for_run:
                self._not_activated(employee, "released_after_closing")
                continue
            shift = employee.shifts[employee.next_index]
            activation = max(shift.scheduled_start, t + self._rest())
            if activation >= shift.scheduled_end:
                self._not_activated(employee, "rest_after_actual_release_reaches_scheduled_end")
                continue
            if activation > shift.scheduled_start and any(item.scheduled_start < activation for item in shift.breaks):
                raise UndeterminedPolicyError(
                    f"{employee.employee_id}'s shift {shift.index} activates at {activation} h, after its scheduled "
                    f"start {shift.scheduled_start} h, and a break falls due before then. Whether that break is "
                    "taken at activation or is unfulfilled is UNKNOWN in the approved policy.")
            break

    def _complete(self, employee: _Employee, t: float) -> None:
        if employee.state not in SERVING_STATES:
            raise EmployeeTimelineError(
                f"{employee.employee_id} has no service to complete at {t} h (state {employee.state}).")
        self._flush(employee, t)
        if employee.state == SERVING:
            self._set(employee, t, COMPLETION, AVAILABLE, "employee_service_completion")
        elif employee.state == SERVING_BREAK_DUE:
            item = self._pending_break(self._shift(employee))
            assert item is not None and item.due is not None
            self._start_break(employee, item, t, COMPLETION, "employee_break_start")
        else:
            self._release(employee, t, COMPLETION, "employee_service_completion")

    def _shift_end(self, employee: _Employee, t: float) -> None:
        self._flush(employee, t)
        self._shift(employee).end_reached = True
        if self.closed and self.hold_past_shift_end:
            return  # held on duty past the shift end until a Release input
        if employee.release_basis is not None:
            return  # already released at the next completion or break end
        employee.release_basis = SCHEDULED_SHIFT_END
        if employee.state in (AVAILABLE, WAITING_FOR_REGISTER):
            self._release(employee, t, SHIFT_END, "employee_shift_end")
        elif employee.state in (SERVING, SERVING_BREAK_DUE):
            self._set(employee, t, SHIFT_END, SERVING_SHIFT_ENDED, "employee_shift_end")
        # ON_BREAK: the break keeps its full duration, and the employee goes OFF at its end.

    def _end_break(self, employee: _Employee, t: float, stage: str, outcome: str, event: str) -> None:
        self._flush(employee, t)
        item = self._current_break(employee)
        item.actual_end, item.outcome = t, outcome
        if employee.release_basis is not None:
            self._release(employee, t, stage, event)
        else:
            self._join_wait(employee, t, stage, event)

    def _break_due(self, employee: _Employee, t: float) -> None:
        self._flush(employee, t)
        item = self._pending_break(self._shift(employee))
        assert item is not None
        item.due = t
        if employee.state in (AVAILABLE, WAITING_FOR_REGISTER):
            self._start_break(employee, item, t, BREAK_DUE, "employee_break_start")
        elif employee.state == SERVING:
            self._set(employee, t, BREAK_DUE, SERVING_BREAK_DUE, "employee_break_due_while_serving")
        else:
            raise EmployeeTimelineError(f"{employee.employee_id} cannot have a break fall due in {employee.state}.")

    def _activate(self, employee: _Employee, t: float) -> None:
        self._flush(employee, t)
        shift = employee.shifts[employee.next_index]
        employee.next_index += 1
        shift.actual_start = t
        employee.current = shift
        item = self._pending_break(shift)
        if item is not None and self._due_time(employee) == t:
            item.due = t  # a break scheduled at this instant falls due as the shift starts
            self._start_break(employee, item, t, SHIFT_START, "employee_break_start_at_shift_start")
        else:
            self._join_wait(employee, t, SHIFT_START, "employee_shift_start")

    def _handover(self, t: float) -> None:
        free = sorted(set(range(1, self.register_count + 1)) - set(self.holder))
        waiting = sorted((employee for employee in self.employees.values() if employee.state == WAITING_FOR_REGISTER),
                         key=_wait_order)
        for register, employee in zip(free, waiting):
            self._flush(employee, t)
            employee.register = register
            self.holder[register] = employee.employee_id
            employee.wait_start = None
            self._set(employee, t, REGISTER_HANDOVER, AVAILABLE, "employee_register_assigned")

    # ── Closing inputs ─────────────────────────────────────────────────────

    def _apply_release(self, employee: _Employee, t: float) -> None:
        if employee.released_for_run:
            raise EmployeeTimelineError(f"{employee.employee_id} was already released.")
        self._flush(employee, t)
        employee.released_for_run = True
        if employee.current is None:
            while employee.next_index < len(employee.shifts):
                self._not_activated(employee, "released_after_closing")
            return
        if employee.release_basis is None:
            employee.release_basis = RELEASE_INPUT
        if employee.state in (AVAILABLE, WAITING_FOR_REGISTER):
            self._release(employee, t, CLOSING_INPUT, "employee_release_input")
        elif employee.state in (SERVING, SERVING_BREAK_DUE):
            self._set(employee, t, CLOSING_INPUT, SERVING_SHIFT_ENDED, "employee_release_input")
        # SERVING_SHIFT_ENDED and ON_BREAK: OFF at the completion or at the break end.

    def _apply_cancel(self, employee: _Employee, t: float) -> None:
        self._flush(employee, t)
        shifts = ([] if employee.current is None else [employee.current]) + employee.shifts[employee.next_index:]
        for shift in shifts:
            for item in shift.breaks:
                if item.actual_start is None and item.outcome is None:
                    item.outcome, item.unfulfilled_cause = UNFULFILLED, "cancelled_at_closing"
        if employee.state == SERVING_BREAK_DUE:
            self._set(employee, t, CLOSING_INPUT, SERVING, "employee_breaks_cancelled_at_closing")

    def _apply_closing_input(self, item: ClosingInput, t: float) -> None:
        employee = self._employee(item.employee_id)
        if isinstance(item, Release):
            self._apply_release(employee, t)
            return
        if t != self.closing_time:
            raise EmployeeTimelineError(f"{type(item).__name__} applies only at closing ({self.closing_time} h).")
        if isinstance(item, EndBreakAtClosing):
            if employee.state != ON_BREAK:
                raise EmployeeTimelineError(f"{employee.employee_id} is not on a break at closing.")
            self._end_break(employee, t, CLOSING_INPUT, TRUNCATED_BY_CLOSING, "employee_break_truncated_at_closing")
        else:
            self._apply_cancel(employee, t)

    # ── Public stepping ────────────────────────────────────────────────────

    def _employee(self, employee_id: str) -> _Employee:
        employee = self.employees.get(employee_id)
        if employee is None:
            raise EmployeeTimelineError(f"Unknown employee {employee_id!r}.")
        return employee

    def process(
        self,
        t: float,
        *,
        completions: Sequence[str] = (),
        closing_inputs: Sequence[ClosingInput] = (),
    ) -> None:
        """Process every event at instant ``t`` in the same-time order, up to the register handover."""
        if not _is_time(t) or t < self.begin:
            raise EmployeeTimelineError(f"Instant {t!r} must be a finite number of hours, {self.begin} or later.")
        t = float(t)
        if self.now is not None and t <= self.now:
            raise EmployeeTimelineError(f"Instant {t} h is not after the last processed instant {self.now} h.")
        pending = self.next_time()
        if pending is not None and pending < t:
            raise EmployeeTimelineError(f"The scheduled instant {pending} h precedes {t} h; process it first.")
        closing_items = list(closing_inputs)
        if closing_items and t < self.closing_time:
            raise EmployeeTimelineError(f"Closing inputs apply only at or after closing ({self.closing_time} h).")
        self.now = t
        for employee_id in sorted(completions):
            self._complete(self._employee(employee_id), t)
        if not self.closed and t == self.closing_time:
            for employee in self.employees.values():
                self._flush(employee, t)
            self.closed = True
        for item in closing_items:
            self._apply_closing_input(item, t)
        employees = [self.employees[employee_id] for employee_id in self.order]
        for employee in employees:
            shift = employee.current
            if shift is not None and not shift.end_reached and shift.scheduled_end == t:
                self._shift_end(employee, t)
        for employee in employees:
            if employee.state == ON_BREAK and self._break_end(self._current_break(employee)) == t:
                self._end_break(employee, t, BREAK_END, COMPLETED, "employee_break_end")
        for employee in employees:
            if self._due_time(employee) == t:
                self._break_due(employee, t)
        for employee in employees:
            if self._activation_time(employee) == t:
                self._activate(employee, t)
        self._handover(t)

    def start_service(self, t: float, employee_id: str) -> None:
        """The assignment pass at the instant last processed: an AVAILABLE employee starts a service."""
        if self.now is None or t != self.now:
            raise EmployeeTimelineError(f"A service start at {t} h must follow process() at that instant.")
        employee = self._employee(employee_id)
        if employee.state != AVAILABLE:
            raise EmployeeTimelineError(
                f"{employee_id} cannot start a service at {t} h (state {employee.state}).")
        self._flush(employee, t)
        self._set(employee, t, SERVICE_START, SERVING, "employee_service_start")

    def result(self, finish: float) -> dict[str, Any]:
        """Close the timeline at ``finish`` and return its record; every employee must be OFF."""
        if not _is_time(finish) or finish < max(self.closing_time, self.now if self.now is not None else self.begin):
            raise EmployeeTimelineError("finish must be a finite number of hours, at or after closing and the last "
                                        "processed instant.")
        finish = float(finish)
        problems = []
        pending = self.next_time()
        if pending is not None:
            problems.append(f"The scheduled instant {pending} h has not been processed.")
        for employee_id in self.order:
            employee = self.employees[employee_id]
            if employee.state != OFF or employee.current is not None:
                problems.append(f"{employee_id} is still on duty ({employee.state}); issue the missing completion "
                                "or Release input.")
        if problems:
            raise EmployeeTimelineError(" ".join(problems))
        for employee in self.employees.values():
            self._flush(employee, finish)
        return self._record(finish)

    def _record(self, finish: float) -> dict[str, Any]:
        intervals = [row for employee_id in self.order for row in self.employees[employee_id].intervals]
        shifts, breaks = [], []
        for employee_id in self.order:
            for shift in self.employees[employee_id].shifts:
                activated = shift.actual_start is not None
                shifts.append({
                    "employee_id": employee_id,
                    "shift_index": shift.index,
                    "scheduled_start": shift.scheduled_start,
                    "scheduled_end": shift.scheduled_end,
                    "activated": activated,
                    "actual_start": shift.actual_start,
                    "activation_delay": None if shift.actual_start is None else shift.actual_start - shift.scheduled_start,
                    "release": shift.release,
                    "release_trigger": shift.release_trigger,
                    "release_basis": shift.release_basis,
                    "overrun": None if shift.release is None else max(0.0, shift.release - shift.scheduled_end),
                    "not_activated_reason": shift.not_activated_reason,
                })
                for item in shift.breaks:
                    assert item.outcome in BREAK_OUTCOMES
                    breaks.append({
                        "employee_id": employee_id,
                        "shift_index": shift.index,
                        "name": item.name,
                        "paid": item.paid,
                        "duration_minutes": item.duration_minutes,
                        "scheduled_start": item.scheduled_start,
                        "due": item.due,
                        "actual_start": item.actual_start,
                        "actual_end": item.actual_end,
                        "delay": None if item.actual_start is None else item.actual_start - item.scheduled_start,
                        "outcome": item.outcome,
                        "unfulfilled_cause": item.unfulfilled_cause,
                    })
        totals: dict[str, dict[str, float]] = {}
        for row in intervals:
            by_state = totals.setdefault(row["employee_id"], dict.fromkeys(BASE_STATES, 0.0))
            by_state[row["state"]] += row["end"] - row["start"]
        return {
            "begin": self.begin,
            "finish": finish,
            "closing_time": self.closing_time,
            "hold_past_shift_end": self.hold_past_shift_end,
            "register_count": self.register_count,
            "intervals": intervals,
            "transitions": list(self.transitions),
            "shifts": shifts,
            "breaks": breaks,
            "state_totals": totals,
            "definitions": dict(DEFINITIONS),
            "undetermined": list(UNDETERMINED),
            "provenance": {
                "state_machine_version": STATE_MACHINE_VERSION,
                "scope": ("Employee, break, shift, and register timeline only. No customers, queue, service-time "
                          "generation, random numbers, or monetary cost; service starts and completions are "
                          "caller inputs."),
            },
        }


def run_timeline(
    horizon: OperatingHorizon,
    employees: Sequence[Employee],
    rules: WorkforceRules,
    roster: Sequence[ScheduledShift],
    inputs: Sequence[TimelineInput],
    *,
    hold_past_shift_end: bool,
    finish: float,
) -> dict[str, Any]:
    """Run the roster's timeline with prescribed inputs, from the timeline start to ``finish``.

    Inputs at one instant are applied in the same-time order; closing inputs at one instant keep
    their given order.
    """
    machine = EmployeeTimeline(horizon, employees, rules, roster, hold_past_shift_end=hold_past_shift_end)
    if not isinstance(inputs, (list, tuple)):
        raise EmployeeTimelineError("inputs must be a list of timeline inputs.")
    for position, item in enumerate(inputs, start=1):
        if not isinstance(item, _INPUT_TYPES):
            raise EmployeeTimelineError(f"Input {position} must be a ServiceStart, ServiceCompletion, Release, "
                                        "EndBreakAtClosing, or CancelPendingBreaks.")
        if not _is_time(item.time):
            raise EmployeeTimelineError(f"Input {position} time must be a finite number of hours.")
    ordered = sorted(inputs, key=lambda item: float(item.time))
    position = 0
    while True:
        times = [time for time in (machine.next_time(), float(ordered[position].time) if position < len(ordered)
                                   else None) if time is not None]
        if not times or min(times) > finish:
            break
        t = min(times)
        batch = []
        while position < len(ordered) and float(ordered[position].time) == t:
            batch.append(ordered[position])
            position += 1
        machine.process(t, completions=[item.employee_id for item in batch if isinstance(item, ServiceCompletion)],
                        closing_inputs=[item for item in batch
                                        if isinstance(item, (Release, EndBreakAtClosing, CancelPendingBreaks))])
        for item in batch:
            if isinstance(item, ServiceStart):
                machine.start_service(t, item.employee_id)
    if position < len(ordered):
        raise EmployeeTimelineError(f"Input at {ordered[position].time} h is after finish {finish} h.")
    return machine.result(finish)
