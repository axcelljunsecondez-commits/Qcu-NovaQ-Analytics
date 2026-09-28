"""Named-employee continuous shared-queue DES (Phase 5B-4.3 of the shared-queue enhancement).

Customers from prescribed (arrival hour, unit work) pairs join one first-come, first-served line.
Named employees serve them. Each employee's duty, breaks, shifts, and register come from the
Phase 5B-4.2 state machine (``shared_employee_states.EmployeeTimeline``), which this module drives
with service starts, completions, and the closing inputs that apply the approved P5, P6, and P7
selections. Capacity comes from employee states; no staffing schedule is forced on the line.

Specs: docs/superpowers/specs/2026-09-28-shared-queue-named-des.md (this engine) and
docs/superpowers/specs/2026-09-28-shared-queue-named-employee-des-policy.md (the approved policy).

Prescribed arrivals only: this engine draws no random numbers and computes no monetary cost. Seeded
replications (``shared_named_replications.py``, Phase 5B-4.4) draw the arrivals first and pass them
here. Phase 5B-4.4 also applied the approved closing and staffing-gap rules (spec
docs/superpowers/specs/2026-09-28-shared-queue-named-replications.md). Nothing legacy imports this
module, and it uses none of the separate-queue break code (``PRE_BREAK_CUTOFF_MINUTES``,
``queue_lifecycle``, or the ``separate_optimization`` break controller). Only the anonymous engine's
(``shared_continuous_des``) closing policy names are imported.
"""

from __future__ import annotations

import bisect
import heapq
import math
from collections import deque
from collections.abc import Sequence
from dataclasses import asdict, dataclass, fields
from numbers import Integral, Real
from typing import Any

from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
    validate_timeline,
)
from backend.queueing_engine.services.shared_workforce import (
    Employee,
    ScheduledShift,
    WorkforceRules,
    evaluate_roster,
)
from backend.queueing_engine.simulation.shared_continuous_des import CLOSING_POLICIES, DRAIN, HARD_CUTOFF
from backend.queueing_engine.simulation.shared_employee_states import (
    AVAILABLE,
    ON_BREAK,
    REGISTER_STATES,
    SERVING,
    SERVING_BREAK_DUE,
    SERVING_STATES,
    STATE_MACHINE_VERSION,
    WAITING_FOR_REGISTER,
    CancelPendingBreaks,
    ClosingInput,
    EmployeeTimeline,
    EmployeeTimelineError,
    EndBreakAtClosing,
    Release,
)

NAMED_ENGINE_VERSION = "novaq-shared-named-des-v2"

DEPARTED, UNSERVED_AT_CLOSE = "departed", "unserved_at_close"
HARD_CUTOFF_REASON, NO_ELIGIBLE_EMPLOYEE = "hard_cutoff", "no_eligible_employee"  # X6 names the second
ACCEPTING_STATES = frozenset({AVAILABLE, SERVING})


# ── Approved policy selections ──────────────────────────────────────────────


@dataclass(frozen=True)
class EmployeeDesPolicy:
    """The approved P and X selections this engine applies. Every field is required, with no default.

    Each field has exactly one approved value (``APPROVED_EMPLOYEE_POLICY``); any other value is
    rejected rather than simulated.
    """

    drain_crew: str
    drain_duration: str
    hard_cutoff_release: str
    breaks_at_closing: str
    break_delay: str
    employee_choice: str


APPROVED_EMPLOYEE_POLICY = EmployeeDesPolicy(
    drain_crew="accepting_immediately_before_closing",
    drain_duration="until_admitted_queue_empty",
    hard_cutoff_release="idle_at_closing_busy_at_completion",
    breaks_at_closing="truncate_in_progress_cancel_pending",
    break_delay="record_actual_delay_only",
    employee_choice="longest_available_then_employee_id",
)
POLICY_MEANINGS = {
    "drain_crew": (
        "P5 (DRAIN): the crew is frozen at closing from the employees accepting (AVAILABLE or SERVING) "
        "immediately before closing, including one whose shift ends exactly at closing. Employees on a "
        "break, with a break or a shift release pending, starting later, or returning after closing are "
        "excluded."
    ),
    "drain_duration": (
        "P5 (DRAIN): crew members keep serving the admitted line, regardless of their scheduled shift end, "
        "and each is released once idle with nobody waiting."
    ),
    "hard_cutoff_release": (
        "P6 (HARD_CUTOFF): customers still waiting at closing are unserved; services under way finish; idle "
        "employees are released at closing and busy ones at their completion; no service starts at or "
        "after closing."
    ),
    "breaks_at_closing": (
        "P7: a break in progress at closing ends at closing (truncated_by_closing); a break not yet started "
        "is unfulfilled with cause cancelled_at_closing; nobody returns from a break after closing. Approved "
        "Phase 5B-4.4 rules: a break ending exactly at closing is truncated_by_closing, because closing is "
        "processed before break ends; a service with a break due that completes exactly at closing completes "
        "first, and its break is cancelled_at_closing (no zero-length break is created)."
    ),
    "break_delay": "P2: the actual break delay is recorded; there is no delay threshold and no pre-break cutoff.",
    "employee_choice": (
        "X1: among AVAILABLE employees, the one AVAILABLE longest (earliest time of becoming AVAILABLE) takes "
        "the next customer; ties go to the lower employee_id. No random choice."
    ),
}

SAME_TIME_ORDER = (
    "X2: at one instant, service completions, then the closing boundary (closing inputs and unserved "
    "customers), shift ends, break ends, breaks becoming due, shift starts, register handovers, arrivals, "
    "and one first-come, first-served assignment pass."
)
DEFINITIONS = {
    "time_unit": (
        "Hours from the horizon start, as in the anonymous engine: roster minute m is (m - horizon start "
        "minute) / 60. Arrivals lie in [0, closing). Instants are compared exactly, as in the anonymous "
        "engine, with no event-time tolerance; roster-derived instants are computed in whole minutes by the "
        "state machine, and service times are never rounded or snapped to roster boundaries (approved "
        "Phase 5B-4.4 rule)."
    ),
    "same_time_order": SAME_TIME_ORDER,
    "service": (
        "Non-preemptive. A service starting at t lasts unit_work / mu(t), where mu(t) is the service rate of "
        "the demand period containing t (the final period's rate at or after closing), as in the anonymous "
        "engine."
    ),
    "customer_status": (
        "departed: served to completion. unserved_at_close: still waiting at closing and never served, with "
        "reason hard_cutoff (HARD_CUTOFF) or no_eligible_employee (DRAIN with an empty crew, X6). "
        "elapsed_wait_at_close_hours is closing minus arrival for an unserved customer."
    ),
    "scheduled_active": (
        "Employees scheduled on shift and not on a scheduled break (the roster report's active_server_steps): "
        "planned times, not simulated ones."
    ),
    "required_staffing": (
        "The server count of the required_staffing segment containing the instant (X7). None before opening "
        "and after closing, where no segment applies; None is not zero."
    ),
    "accepting_capacity": (
        "Employees AVAILABLE or SERVING in the simulation: at a register and able to take a customer now or "
        "at their completion. SERVING_BREAK_DUE and SERVING_SHIFT_ENDED are excluded (their next step is a "
        "break or a release), as are WAITING_FOR_REGISTER, ON_BREAK, and OFF (approved Phase 5B-4.4 rule)."
    ),
    "busy_employees": "Employees SERVING, SERVING_BREAK_DUE, or SERVING_SHIFT_ENDED.",
    "register_occupancy": "Employees holding a register (AVAILABLE or a serving state). Never above register_count.",
    "waiting_for_register": "Employees on duty, not on a break, and waiting for a free register.",
    "schedule_realization_gap": (
        "accepting_capacity - scheduled_active, at each instant inside the operating horizon [opening, closing); "
        "None before opening and after closing, where no gap is calculated."
    ),
    "requirement_gap": (
        "accepting_capacity - required_staffing inside the operating horizon; None before opening and after "
        "closing, where no requirement exists."
    ),
    "gap_integrals": (
        "Gaps are integrated only over the operating horizon: per staffing segment and over the whole horizon. "
        "shortfall_hours is the integral of max(0, -gap) and excess_hours the integral of max(0, gap), in "
        "employee-hours. The two gaps are reported separately and never combined. The before_opening and "
        "after_closing windows report the series (capacity and time) without any gap (approved Phase 5B-4.4 "
        "rule); after_closing is always reported, with zero duration when the timeline ends at closing."
    ),
    "queue_customer_hours": (
        "The integral of the number of customers waiting (not in service). It equals the served customers' "
        "waits plus the unserved customers' elapsed waits at closing."
    ),
}
UNDETERMINED = [
    "DRAIN release order: when fewer customers wait than crew members are idle, the crew members X1 ranks "
    "first serve and the rest are released (INFERRED from X1 and P5).",
    "Staffing windows beyond the approved Phase 5B-4.4 rule: the before_opening window (series only, when a "
    "shift starts before opening) and the timeline's extension to the last scheduled shift end are INFERRED "
    "choices of shape.",
]


# ── Internal state ──────────────────────────────────────────────────────────


@dataclass
class _Customer:
    customer_id: int
    arrival: float
    work: float
    service_start: float | None = None
    service_end: float | None = None
    employee_id: str | None = None
    register_id: int | None = None
    departed: bool = False
    unserved_reason: str | None = None


def _hours(minute: int, horizon: OperatingHorizon) -> float:
    """The anonymous engine's conversion (``shared_continuous_des._hours``)."""
    return (minute - horizon.start_minute) / 60.0


def _is_finite_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def _validate(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    arrivals: Sequence[tuple[float, float]],
    closing_policy: str,
    employee_policy: EmployeeDesPolicy,
    required_staffing: Sequence[StaffingSegment],
    max_trace_events: int | None,
) -> None:
    if not isinstance(required_staffing, (list, tuple)) or not required_staffing or not all(
            isinstance(segment, StaffingSegment) for segment in required_staffing):
        raise SharedSegmentError(["required_staffing is required (X7): a non-empty list of StaffingSegment "
                                  "items, with no default."])
    validate_timeline(horizon, demand_periods, required_staffing)
    end = _hours(horizon.end_minute, horizon)
    period_starts = [_hours(period.start_minute, horizon) for period in demand_periods]
    problems = []
    if closing_policy not in CLOSING_POLICIES:
        problems.append("closing_policy must be DRAIN or HARD_CUTOFF; there is no default.")
    if not isinstance(employee_policy, EmployeeDesPolicy):
        problems.append("employee_policy must be an EmployeeDesPolicy; there is no default.")
    else:
        for item in fields(EmployeeDesPolicy):
            given, approved = getattr(employee_policy, item.name), getattr(APPROVED_EMPLOYEE_POLICY, item.name)
            if given != approved:
                problems.append(f"employee_policy.{item.name} {given!r} is not an approved selection; the only "
                                f"approved selection is {approved!r}.")
    if max_trace_events is not None and (
        not isinstance(max_trace_events, Integral) or isinstance(max_trace_events, bool) or max_trace_events < 0
    ):
        problems.append("max_trace_events must be a whole number, 0 or more, or omitted.")
    if not isinstance(arrivals, (list, tuple)):
        problems.append("arrivals must be a list of (hour, work) pairs.")
        arrivals = []
    previous = -math.inf
    for position, pair in enumerate(arrivals, start=1):
        # The anonymous engine's prescribed-arrival checks (shared_continuous_des.simulate_prescribed).
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            problems.append(f"Arrival {position} must be an (hour, work) pair.")
            continue
        at, work = pair
        if not _is_finite_real(at) or not 0 <= float(at) < end:
            problems.append(f"Arrival {position} time must lie in the horizon [0, {end:g}) hours.")
            continue
        if float(at) < previous:
            problems.append(f"Arrival {position} is earlier than the arrival before it.")
        previous = float(at)
        if not _is_finite_real(work) or float(work) <= 0:
            problems.append(f"Arrival {position} work must be a finite number above 0.")
        period = demand_periods[bisect.bisect_right(period_starts, float(at)) - 1]
        if float(period.arrival_rate_per_hour) == 0:
            problems.append(f"Arrival {position} falls in demand period {period.period_id}, whose arrival rate is 0.")
    if problems:
        raise SharedSegmentError(problems)


# ── Engine ──────────────────────────────────────────────────────────────────


def simulate_named_prescribed(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    employees: Sequence[Employee],
    rules: WorkforceRules,
    roster: Sequence[ScheduledShift],
    arrivals: Sequence[tuple[float, float]],
    *,
    closing_policy: str,
    employee_policy: EmployeeDesPolicy,
    required_staffing: Sequence[StaffingSegment],
    max_trace_events: int | None = None,
) -> dict[str, Any]:
    """Run the named-employee engine on prescribed (arrival hour, unit work) pairs.

    ``closing_policy`` (``DRAIN`` or ``HARD_CUTOFF``), ``employee_policy``, and
    ``required_staffing`` (X7) have no defaults. The roster must pass the X4 precondition. The run
    is deterministic and draws no random numbers.
    """
    _validate(horizon, demand_periods, arrivals, closing_policy, employee_policy, required_staffing,
              max_trace_events)
    # Every release at or after closing is a Release input chosen below under P5 or P6, so shift ends
    # at or after closing release nobody by themselves.
    machine = EmployeeTimeline(horizon, employees, rules, roster, hold_past_shift_end=True)
    report = evaluate_roster(horizon, employees, rules, roster, required_staffing=required_staffing)
    closing = machine.closing_time
    period_starts = [_hours(period.start_minute, horizon) for period in demand_periods]
    segment_starts = [_hours(segment.start_minute, horizon) for segment in required_staffing]

    def mu_at(hour: float) -> float:
        # At or after closing this is the final demand period's rate (the anonymous engine's rule).
        return float(demand_periods[bisect.bisect_right(period_starts, hour) - 1].service_rate_per_hour)

    customers = [_Customer(customer_id, float(at), float(work))
                 for customer_id, (at, work) in enumerate(arrivals, start=1)]
    queue: deque[int] = deque()
    completions: list[tuple[float, int]] = []  # (service end, customer id)
    available_since: dict[str, float] = {}
    consumed = 0  # machine transitions already read
    next_arrival = 0
    crew: list[str] | None = None
    at_close: dict[str, Any] = {}
    trace: list[dict[str, Any]] = []
    truncated = False
    area = {"in_horizon": 0.0, "after_closing": 0.0}
    clock = {"last": machine.begin}
    max_queue = 0

    def record(at: float, kind: str, customer: _Customer | None) -> None:
        nonlocal truncated
        if max_trace_events is not None and len(trace) >= max_trace_events:
            truncated = True
            return
        trace.append({
            "t": at, "type": kind, "customer_id": None if customer is None else customer.customer_id,
            "employee_id": None if customer is None else customer.employee_id,
            "register_id": None if customer is None else customer.register_id, "queue_len_after": len(queue),
        })

    def advance(now: float) -> None:
        elapsed = now - clock["last"]
        if elapsed > 0 and queue:
            area["after_closing" if clock["last"] >= closing else "in_horizon"] += len(queue) * elapsed
        clock["last"] = now

    def read_transitions() -> None:
        nonlocal consumed
        for row in machine.transitions[consumed:]:
            if row["to_state"] == AVAILABLE:
                available_since[row["employee_id"]] = row["t"]
        consumed = len(machine.transitions)

    def x1_order(view: dict[str, dict[str, Any]]) -> list[str]:
        return [employee_id for _, employee_id in sorted(
            (available_since[employee_id], employee_id) for employee_id, row in view.items()
            if row["state"] == AVAILABLE)]

    def unserve(t: float, reason: str) -> None:
        while queue:
            customer = customers[queue.popleft() - 1]
            customer.unserved_reason = reason
            record(t, "unserved_at_close", customer)

    while True:
        candidates = [time for time in (
            machine.next_time(),
            customers[next_arrival].arrival if next_arrival < len(customers) else None,
            completions[0][0] if completions else None,
        ) if time is not None]
        if not candidates:
            break
        t = min(candidates)
        advance(t)
        view = machine.snapshot()  # the state on the interval ending at t
        at_closing = not machine.closed and t == closing

        # 1. Service completions.
        finishing: dict[str, int] = {}
        while completions and completions[0][0] == t:
            _, customer_id = heapq.heappop(completions)
            customer = customers[customer_id - 1]
            customer.departed = True
            assert customer.employee_id is not None
            finishing[customer.employee_id] = customer_id
            record(t, "service_end", customer)

        # 2. The closing boundary.
        closing_inputs: list[ClosingInput] = []
        if at_closing:
            crew, closing_inputs = _closing_inputs(t, closing_policy, view, finishing)
            at_close = {
                "waiting_customer_ids": list(queue),
                "in_service_customer_ids": sorted(
                    customer.customer_id for customer in customers
                    if customer.service_start is not None and not customer.departed),
                "drain_crew": list(crew),
                "closing_inputs": [{"type": type(item).__name__, "employee_id": item.employee_id}
                                   for item in closing_inputs],
            }
            record(t, "closing", None)
            if closing_policy == HARD_CUTOFF:
                unserve(t, HARD_CUTOFF_REASON)
            elif not crew:
                unserve(t, NO_ELIGIBLE_EMPLOYEE)  # X6
        if closing_policy == DRAIN and crew is not None:
            # P5: a crew member idle after this instant's completions, with nobody left for them, is
            # released now. Only crew members accept after closing, and nobody arrives.
            idle = [employee_id for employee_id in x1_order(view) if employee_id in crew] + sorted(
                employee_id for employee_id in finishing if employee_id in crew and view[employee_id]["state"] == SERVING)
            released = idle[len(queue):]
            closing_inputs += [Release(t, employee_id) for employee_id in released]
            if at_closing:
                at_close["closing_inputs"] += [{"type": "Release", "employee_id": employee_id} for employee_id in released]

        # 1-7 in the state machine: completions, closing inputs, shift ends, break ends, breaks due,
        # shift starts, and register handovers.
        machine.process(t, completions=sorted(finishing), closing_inputs=closing_inputs)
        read_transitions()

        # 8. Arrivals (none at or after closing).
        while next_arrival < len(customers) and customers[next_arrival].arrival == t:
            customer = customers[next_arrival]
            queue.append(customer.customer_id)
            record(t, "arrival", customer)
            next_arrival += 1

        # 9. One first-come, first-served assignment pass (X1 chooses the employee).
        view = machine.snapshot()
        if closing_policy == HARD_CUTOFF and t >= closing:
            assert not queue and not any(row["state"] == AVAILABLE for row in view.values())
        for employee_id in x1_order(view):
            if not queue:
                break
            customer = customers[queue.popleft() - 1]
            end = t + customer.work / mu_at(t)
            if not end > t:
                raise EmployeeTimelineError(
                    f"Customer {customer.customer_id}'s service at {t} h is shorter than the time scale resolves.")
            machine.start_service(t, employee_id)
            customer.service_start, customer.service_end = t, end
            customer.employee_id, customer.register_id = employee_id, view[employee_id]["register_id"]
            heapq.heappush(completions, (end, customer.customer_id))
            record(t, "service_start", customer)
        read_transitions()
        if t < closing:
            max_queue = max(max_queue, len(queue))
        view = machine.snapshot()
        # Invariant: a non-empty line after the pass means nobody is AVAILABLE.
        assert not queue or not any(row["state"] == AVAILABLE for row in view.values())
        if machine.closed:
            # After closing only the frozen crew accepts customers (P5), and nobody under HARD_CUTOFF (P6);
            # a crew member left idle has been released.
            assert all(row["state"] not in ACCEPTING_STATES or employee_id in (crew or [])
                       for employee_id, row in view.items())
            assert not any(row["state"] == AVAILABLE for row in view.values())

    # The run ends with every customer resolved and every employee released.
    assert not queue and not completions and next_arrival == len(customers)
    assert all(customer.departed or customer.unserved_reason for customer in customers)
    assert machine.now is not None
    timeline = machine.result(machine.now)
    return _summarize(horizon, required_staffing, customers, segment_starts, timeline, report, closing_policy,
                      employee_policy, at_close, trace, truncated, max_trace_events, area, max_queue)


def _closing_inputs(
    t: float,
    closing_policy: str,
    view: dict[str, dict[str, Any]],
    finishing: dict[str, int],
) -> tuple[list[str], list[ClosingInput]]:
    """P5, P6, and P7 at closing: the frozen crew and the state machine's closing inputs.

    ``view`` is each employee's state immediately before closing. Every break not yet started is
    cancelled (P7). Non-crew employees are released: at once when idle or waiting, at their
    completion when serving, and at closing when on a break, which a truncation ends (P7).
    """
    crew = [employee_id for employee_id, row in view.items()
            if closing_policy == DRAIN and row["state"] in ACCEPTING_STATES]
    inputs: list[ClosingInput] = []
    for employee_id, row in view.items():
        state = row["state"]
        cancel, release = CancelPendingBreaks(t, employee_id), Release(t, employee_id)
        if employee_id in crew:
            inputs.append(cancel)
        elif state == SERVING_BREAK_DUE and employee_id not in finishing:
            # Release first, so the employee finishes this customer as SERVING_SHIFT_ENDED; the pending
            # break is then cancelled.
            inputs += [release, cancel]
        elif state == ON_BREAK:
            # Closing comes before break ends (X2), so a break ending exactly at closing is still in progress
            # there and is truncated like a later one (approved Phase 5B-4.4 rule).
            inputs += [cancel, release, EndBreakAtClosing(t, employee_id)]
        else:
            # OFF, WAITING_FOR_REGISTER, AVAILABLE, SERVING, SERVING_SHIFT_ENDED, and a SERVING_BREAK_DUE
            # service completing exactly at closing: it completes first, and the cancel keeps its due break
            # from starting, so the break is cancelled_at_closing, never a zero-length break (Phase 5B-4.4).
            inputs += [cancel, release]
    return crew, inputs


# ── Output ──────────────────────────────────────────────────────────────────


def _mean(values: Sequence[float]) -> float | None:
    return math.fsum(values) / len(values) if values else None


def _staffing(
    horizon: OperatingHorizon,
    required_staffing: Sequence[StaffingSegment],
    timeline: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    """P8: the six staffing series and the two gaps, as a step timeline and per-window integrals.

    The timeline runs from the run's begin to the later of its finish and the last scheduled shift end;
    every employee is OFF after the finish.
    """
    begin, finish, closing = timeline["begin"], timeline["finish"], timeline["closing_time"]
    changes: dict[float, dict[str, int]] = {}

    def add(at: float, key: str, amount: int) -> None:
        row = changes.setdefault(at, {})
        row[key] = row.get(key, 0) + amount

    for row in timeline["intervals"]:
        state = row["state"]
        keys = [key for key, members in (
            ("accepting_capacity", ACCEPTING_STATES), ("busy_employees", SERVING_STATES),
            ("register_occupancy", REGISTER_STATES), ("waiting_for_register", {WAITING_FOR_REGISTER}),
        ) if state in members]
        for key in keys:
            add(row["start"], key, 1)
            add(row["end"], key, -1)
    for step in report["active_server_steps"]:
        add(_hours(step["start_minute"], horizon), "scheduled_active", step["active_servers"])
        add(_hours(step["end_minute"], horizon), "scheduled_active", -step["active_servers"])
    required = [(_hours(segment.start_minute, horizon), _hours(segment.end_minute, horizon), int(segment.servers))
                for segment in required_staffing]
    last = max([finish, *(_hours(step["end_minute"], horizon) for step in report["active_server_steps"])])
    points = sorted({begin, last, 0.0, closing, *changes, *(point for start, end, _ in required
                                                              for point in (start, end))})
    counts = dict.fromkeys(("scheduled_active", "accepting_capacity", "busy_employees", "register_occupancy",
                            "waiting_for_register"), 0)
    steps: list[dict[str, Any]] = []
    for here, following in zip(points, points[1:]):
        for key, amount in changes.get(here, {}).items():
            counts[key] += amount
        if here < begin or following > last:
            continue
        need = next((servers for start, end, servers in required if start <= here < end), None)
        inside = 0.0 <= here < closing  # gaps exist only inside the operating horizon (Phase 5B-4.4 rule)
        row = {
            "start": here, "end": following,
            "scheduled_active": counts["scheduled_active"],
            "required_staffing": need,
            "accepting_capacity": counts["accepting_capacity"],
            "busy_employees": counts["busy_employees"],
            "register_occupancy": counts["register_occupancy"],
            "waiting_for_register": counts["waiting_for_register"],
            "schedule_realization_gap": counts["accepting_capacity"] - counts["scheduled_active"] if inside else None,
            "requirement_gap": None if need is None else counts["accepting_capacity"] - need,
        }
        values = {key: value for key, value in row.items() if key not in ("start", "end")}
        if steps and steps[-1]["end"] == here and all(steps[-1][key] == value for key, value in values.items()):
            steps[-1]["end"] = following
        else:
            steps.append(row)

    def window(name: str, kind: str, start: float, end: float, need: int | None) -> dict[str, Any]:
        pieces = [(min(end, row["end"]) - max(start, row["start"]), row) for row in steps
                  if row["start"] < end and row["end"] > start]

        def integral(key: str) -> float:
            return math.fsum(length * row[key] for length, row in pieces)

        def split(key: str) -> dict[str, float]:
            return {"shortfall_hours": math.fsum(length * max(0, -row[key]) for length, row in pieces),
                    "excess_hours": math.fsum(length * max(0, row[key]) for length, row in pieces)}

        # Gaps and the requirement are integrated over the operating horizon only: per staffing segment and
        # over the whole horizon. Before opening and after closing only the series are reported.
        inside = kind in ("staffing_segment", "horizon")
        return {
            "window": name, "kind": kind, "start": start, "end": end, "duration_hours": end - start,
            "required_servers": need,
            "scheduled_active_hours": integral("scheduled_active"),
            "required_staffing_hours": integral("required_staffing") if inside else None,
            "accepting_capacity_hours": integral("accepting_capacity"),
            "busy_employee_hours": integral("busy_employees"),
            "register_occupancy_hours": integral("register_occupancy"),
            "waiting_for_register_hours": integral("waiting_for_register"),
            "schedule_realization_gap": split("schedule_realization_gap") if inside else None,
            "requirement_gap": split("requirement_gap") if inside else None,
        }

    windows = []
    if begin < 0.0:
        windows.append(window("before_opening", "before_opening", begin, 0.0, None))
    windows += [window(segment.segment_id, "staffing_segment", start, end, servers)
                for segment, (start, end, servers) in zip(required_staffing, required)]
    windows.append(window("horizon", "horizon", 0.0, closing, None))
    # Post-close capacity and time are always reported separately; the window is empty when the timeline
    # ends at closing.
    windows.append(window("after_closing", "after_closing", closing, last, None))
    return {"timeline": steps, "windows": windows}


def _summarize(
    horizon: OperatingHorizon,
    required_staffing: Sequence[StaffingSegment],
    customers: list[_Customer],
    segment_starts: list[float],
    timeline: dict[str, Any],
    report: dict[str, Any],
    closing_policy: str,
    employee_policy: EmployeeDesPolicy,
    at_close: dict[str, Any],
    trace: list[dict[str, Any]],
    truncated: bool,
    max_trace_events: int | None,
    area: dict[str, float],
    max_queue: int,
) -> dict[str, Any]:
    closing = timeline["closing_time"]
    rows = []
    for customer in customers:
        status = DEPARTED if customer.departed else UNSERVED_AT_CLOSE
        rows.append({
            "customer_id": customer.customer_id,
            "arrival_hours": customer.arrival,
            "unit_work": customer.work,
            "arrival_segment_id": required_staffing[bisect.bisect_right(segment_starts, customer.arrival) - 1].segment_id,
            "service_start_hours": customer.service_start,
            "service_end_hours": customer.service_end,
            "employee_id": customer.employee_id,
            "register_id": customer.register_id,
            "wait_hours": None if customer.service_start is None else customer.service_start - customer.arrival,
            "elapsed_wait_at_close_hours": closing - customer.arrival if status == UNSERVED_AT_CLOSE else None,
            "status": status,
            "unserved_reason": customer.unserved_reason,
        })
    assert all((row["status"] == UNSERVED_AT_CLOSE) == (row["service_start_hours"] is None) for row in rows)
    waits = [customer.service_start - customer.arrival for customer in customers if customer.service_start is not None]
    reasons = [row["unserved_reason"] for row in rows if row["unserved_reason"] is not None]
    return {
        "customers": rows,
        "counts": {
            "arrivals": len(rows),
            "departed": sum(1 for row in rows if row["status"] == DEPARTED),
            "unserved_at_close": sum(1 for row in rows if row["status"] == UNSERVED_AT_CLOSE),
            "unserved_by_reason": {reason: reasons.count(reason) for reason in (HARD_CUTOFF_REASON, NO_ELIGIBLE_EMPLOYEE)},
            "served_after_closing": sum(1 for row in rows if row["service_start_hours"] is not None
                                        and row["service_start_hours"] >= closing),
        },
        "mean_wait_hours": _mean(waits),
        "queue": {
            "customer_hours_in_horizon": area["in_horizon"],
            "customer_hours_after_closing": area["after_closing"],
            "customer_hours_total": area["in_horizon"] + area["after_closing"],
            "max_length_in_horizon": max_queue,
        },
        "closing_time": closing,
        "begin": timeline["begin"],
        "finish": timeline["finish"],
        "closing_policy": closing_policy,
        "at_close": at_close,
        "staffing": _staffing(horizon, required_staffing, timeline, report),
        "employee_timeline": timeline,
        "trace": trace,
        "trace_truncated": truncated,
        "definitions": dict(DEFINITIONS),
        "policy": {"selections": asdict(employee_policy), "meanings": dict(POLICY_MEANINGS)},
        "undetermined": list(UNDETERMINED),
        "provenance": {
            "engine_version": NAMED_ENGINE_VERSION,
            "state_machine_version": STATE_MACHINE_VERSION,
            "arrivals": "prescribed (arrival hour, unit work) pairs; no random numbers",
            "max_trace_events": max_trace_events,
            "scope": ("Customers, the shared line, and named employees on prescribed arrivals; this engine "
                      "draws no random numbers. No playback or monetary cost."),
        },
    }
