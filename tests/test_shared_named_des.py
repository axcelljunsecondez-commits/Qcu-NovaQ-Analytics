"""Phase 5B-4.3 named-employee continuous shared-queue DES on prescribed arrivals.

ALL EMPLOYEES, AVAILABILITY, RULES, ROSTERS, DEMAND, ARRIVALS, AND SERVICE WORK IN THIS FILE ARE
SYNTHETIC TEST DATA. They are not NovaMart records, labor law, or recommended operating values.

Expected results are derived by hand in the comments. Every binary-exact run is also checked by
``check_named``, an independent checker of customer invariants 1-19 of the Phase 5B-4.3 request.
It works only from the inputs and the result, and it runs the Phase 5B-4.2 employee checker
(``check_invariants``) on the employee timeline.

The horizon is 08:00-12:00 (minutes 480-720), so hours run 0-4 and closing is at 4.0. One demand
period has service rate 4 per hour, so a service lasts work / 4 hours. Roster minutes are
multiples of 15, arrival times multiples of 1/8 hour, and work multiples of 1/2, so every time is
binary-exact and sums are compared exactly. The reduction tests use generated, non-binary-exact
arrivals and compare the two engines to each other only.
"""

from __future__ import annotations

import ast
import dataclasses
import random
from pathlib import Path
from typing import Any

import pytest

from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    SharedSegmentError,
    StaffingSegment,
)
from backend.queueing_engine.services.shared_workforce import (
    BreakRule,
    EmployeePay,
    ScheduledShift,
    WorkforceRules,
)
from backend.queueing_engine.simulation import shared_continuous_des, shared_named_des
from backend.queueing_engine.simulation.shared_employee_states import (
    AVAILABLE,
    COMPLETED,
    OFF,
    ON_BREAK,
    REGISTER_STATES,
    SERVING,
    SERVING_BREAK_DUE,
    SERVING_SHIFT_ENDED,
    SERVING_STATES,
    TRUNCATED_BY_CLOSING,
    UNFULFILLED,
    WAITING_FOR_REGISTER,
)
from backend.queueing_engine.simulation.shared_named_des import (
    APPROVED_EMPLOYEE_POLICY,
    DEPARTED,
    HARD_CUTOFF_REASON,
    NO_ELIGIBLE_EMPLOYEE,
    UNSERVED_AT_CLOSE,
    simulate_named_prescribed,
)
from tests.test_shared_employee_states import (
    HORIZON,
    break_rows,
    break_rule,
    check_invariants,
    rules,
    shift,
    shift_row,
    staff,
    timeline,
)

# ── SYNTHETIC TEST DATA ──────────────────────────────────────────────────────

MU = 4.0
PERIODS = [DemandPeriod("P", 480, 720, 10.0, MU)]
ONE_REQUIRED = [StaffingSegment("S", 480, 720, 1)]
CLOSE = 4.0
DRAIN, HARD_CUTOFF = shared_continuous_des.DRAIN, shared_continuous_des.HARD_CUTOFF
ACCEPTING = (AVAILABLE, SERVING)
LONG_SHIFT_BREAK = (BreakRule(15, 120, 0, ()), break_rule(121, 480, rest=30))  # a 30-minute break above 2 hours


def simulate(roster: list[ScheduledShift], workforce: WorkforceRules, arrivals: list[tuple[float, float]], *,
             policy: str = DRAIN, required: list[StaffingSegment] | None = None,
             periods: list[DemandPeriod] | None = None, exact: bool = True, **options: Any) -> dict:
    required = ONE_REQUIRED if required is None else required
    periods = PERIODS if periods is None else periods
    result = simulate_named_prescribed(HORIZON, periods, staff(roster), workforce, roster, arrivals,
                                       closing_policy=policy, employee_policy=APPROVED_EMPLOYEE_POLICY,
                                       required_staffing=required, **options)
    check_named(result, arrivals, workforce, roster, periods, required, policy, exact=exact)
    return result


def served(result: dict) -> list[tuple[int, float, float, str, int, float]]:
    """(customer, start, end, employee, register, wait) for every served customer."""
    return [(row["customer_id"], row["service_start_hours"], row["service_end_hours"], row["employee_id"],
             row["register_id"], row["wait_hours"]) for row in result["customers"] if row["status"] == DEPARTED]


def unserved(result: dict) -> list[tuple[int, str, float]]:
    return [(row["customer_id"], row["unserved_reason"], row["elapsed_wait_at_close_hours"])
            for row in result["customers"] if row["status"] == UNSERVED_AT_CLOSE]


def staffing_at(result: dict, t: float) -> dict[str, Any]:
    (row,) = [row for row in result["staffing"]["timeline"] if row["start"] <= t < row["end"]]
    return row


def window(result: dict, name: str) -> dict[str, Any]:
    (row,) = [row for row in result["staffing"]["windows"] if row["window"] == name]
    return row


# ── Independent invariant checker ───────────────────────────────────────────


def _state_at(intervals: list[dict], employee_id: str, t: float) -> str:
    """The employee's base state on [t, t + dt) from the intervals; OFF outside the run."""
    return next((row["state"] for row in intervals
                 if row["employee_id"] == employee_id and row["start"] <= t < row["end"]), OFF)


def _state_before(intervals: list[dict], employee_id: str, t: float) -> str:
    """The employee's base state on the interval that ends at t."""
    return next((row["state"] for row in intervals if row["employee_id"] == employee_id and row["end"] == t), OFF)


def _scheduled_active_spans(workforce: WorkforceRules, roster: list[ScheduledShift]) -> list[tuple[float, float]]:
    """Roster shifts minus their scheduled breaks, in hours (computed here, not by the roster report)."""
    spans = []
    for item in roster:
        length = item.end_minute - item.start_minute
        rule = next(rule for rule in workforce.break_rules if rule.min_shift_minutes <= length <= rule.max_shift_minutes)
        durations = {requirement.name: requirement.duration_minutes for requirement in rule.breaks}
        cuts = sorted((placed.start_minute, placed.start_minute + durations[placed.name]) for placed in item.breaks)
        cursor = item.start_minute
        for start, end in cuts:
            if start > cursor:
                spans.append((cursor, start))
            cursor = end
        if item.end_minute > cursor:
            spans.append((cursor, item.end_minute))
    return [((start - 480) / 60.0, (end - 480) / 60.0) for start, end in spans]


def _close(a: float, b: float, exact: bool) -> bool:
    return a == b if exact else abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def check_named(result: dict, arrivals: list[tuple[float, float]], workforce: WorkforceRules,
                roster: list[ScheduledShift], periods: list[DemandPeriod], required: list[StaffingSegment],
                policy: str, *, exact: bool = True) -> None:
    rows = result["customers"]
    employees = result["employee_timeline"]
    intervals = employees["intervals"]
    ids = sorted({item.employee_id for item in roster})
    close = result["closing_time"]
    assert close == CLOSE
    period_starts = [(period.start_minute - 480) / 60.0 for period in periods]

    def mu(t: float) -> float:
        return float(periods[max(index for index, start in enumerate(period_starts) if start <= t)].service_rate_per_hour)

    # 1, 2, 4, 13: conservation, one outcome, identity, no arrival at or after closing.
    assert len(rows) == len(arrivals)
    counts = result["counts"]
    assert counts["arrivals"] == len(arrivals) == counts["departed"] + counts["unserved_at_close"]
    for position, (row, (at, work)) in enumerate(zip(rows, arrivals), start=1):
        assert (row["customer_id"], row["arrival_hours"], row["unit_work"]) == (position, at, work)
        assert 0 <= at < close
        if row["status"] == DEPARTED:
            assert None not in (row["service_start_hours"], row["service_end_hours"], row["employee_id"],
                                row["register_id"])
            assert row["unserved_reason"] is None and row["elapsed_wait_at_close_hours"] is None
            assert row["wait_hours"] == row["service_start_hours"] - at >= 0
        else:
            assert row["status"] == UNSERVED_AT_CLOSE
            assert row["service_start_hours"] is None and row["employee_id"] is None and row["register_id"] is None
            assert row["unserved_reason"] in (HARD_CUTOFF_REASON, NO_ELIGIBLE_EMPLOYEE)
            assert row["elapsed_wait_at_close_hours"] == close - at
    done = [row for row in rows if row["status"] == DEPARTED]
    missed = [row for row in rows if row["status"] == UNSERVED_AT_CLOSE]

    # 3: one first-come, first-served line. Starts follow arrival order, and only a suffix is unserved.
    starts = [row["service_start_hours"] for row in done]
    assert starts == sorted(starts)
    assert all(a["customer_id"] < b["customer_id"] for a in done for b in missed)

    # 5, 6, 7, 11, 12: non-preemptive service by one employee, one customer at a time, starting from AVAILABLE.
    service_starts = [(row["t"], row["employee_id"]) for row in employees["transitions"]
                      if row["stage"] == "service_start"]
    assert all(row["from_state"] == AVAILABLE and row["to_state"] == SERVING
               for row in employees["transitions"] if row["stage"] == "service_start")
    assert sorted(service_starts) == sorted((row["service_start_hours"], row["employee_id"]) for row in done)
    for row in done:
        start, end, who = row["service_start_hours"], row["service_end_hours"], row["employee_id"]
        assert end == start + row["unit_work"] / mu(start)
        covering = [item for item in intervals if item["employee_id"] == who and item["start"] < end
                    and item["end"] > start]
        assert covering[0]["start"] <= start and covering[-1]["end"] >= end
        assert all(item["state"] in SERVING_STATES and item["register_id"] == row["register_id"] for item in covering)
        assert all(a["end"] == b["start"] for a, b in zip(covering, covering[1:]))
    for who in ids:
        own = sorted((row["service_start_hours"], row["service_end_hours"]) for row in done if row["employee_id"] == who)
        assert all(a[1] <= b[0] for a, b in zip(own, own[1:]))
        busy = sum(item["end"] - item["start"] for item in intervals
                   if item["employee_id"] == who and item["state"] in SERVING_STATES)
        assert _close(busy, sum(end - start for start, end in own), exact)  # busy time is service time

    # 8 and 9: the Phase 5B-4.2 employee invariants (including register occupancy <= K).
    check_invariants(employees, workforce, roster, exact=exact)

    # Approved Phase 5B-4.4 closing rules for breaks: no break starts at or after closing (so none has zero
    # length), a completed break ends before closing, and a break reaching closing is truncated there.
    for item in employees["breaks"]:
        if item["actual_start"] is not None:
            assert item["actual_start"] < close and item["actual_end"] > item["actual_start"]
            assert (item["outcome"] == TRUNCATED_BY_CLOSING) == (item["actual_end"] == close)
            assert item["outcome"] != COMPLETED or item["actual_end"] < close

    # 10: after the assignment pass, a non-empty line means nobody is AVAILABLE.
    def waiting_at(t: float) -> int:
        return sum(1 for row in rows if row["arrival_hours"] <= t < (
            row["service_start_hours"] if row["status"] == DEPARTED else close))

    points = sorted({item[key] for item in intervals for key in ("start", "end")}
                    | {row["arrival_hours"] for row in rows} | set(starts))
    for t in points[:-1]:
        if waiting_at(t):
            assert not any(_state_at(intervals, who, t) == AVAILABLE for who in ids), t

    # 14, 15, and X6: closing.
    waiting_at_close = [row["customer_id"] for row in rows if row["arrival_hours"] < close and (
        row["status"] == UNSERVED_AT_CLOSE or row["service_start_hours"] >= close)]
    assert result["at_close"]["waiting_customer_ids"] == waiting_at_close
    crew = [who for who in ids if _state_before(intervals, who, close) in ACCEPTING] if policy == DRAIN else []
    assert result["at_close"]["drain_crew"] == crew
    late = [row for row in done if row["service_start_hours"] >= close]
    if policy == HARD_CUTOFF:
        assert not late
        assert [row["customer_id"] for row in missed] == waiting_at_close
        assert all(row["unserved_reason"] == HARD_CUTOFF_REASON for row in missed)
    elif crew:
        assert not missed and all(row["employee_id"] in crew for row in late)
    else:
        assert not late and [row["customer_id"] for row in missed] == waiting_at_close
        assert all(row["unserved_reason"] == NO_ELIGIBLE_EMPLOYEE for row in missed)
    assert all(item["employee_id"] in crew for item in intervals
               if item["start"] >= close and item["state"] in ACCEPTING)

    # 16 and 17: staffing series from employee states, and the two gaps computed separately.
    schedule = _scheduled_active_spans(workforce, roster)
    steps = result["staffing"]["timeline"]
    assert steps[0]["start"] == employees["begin"] and all(a["end"] == b["start"] for a, b in zip(steps, steps[1:]))
    assert steps[-1]["end"] == max([employees["finish"], *(end for _, end in schedule)])
    for row in steps:
        t = row["start"]
        states = [_state_at(intervals, who, t) for who in ids]
        scheduled = sum(1 for start, end in schedule if start <= t < end)
        need = next((int(segment.servers) for segment in required
                     if (segment.start_minute - 480) / 60.0 <= t < (segment.end_minute - 480) / 60.0), None)
        accepting = sum(1 for state in states if state in ACCEPTING)
        assert row["accepting_capacity"] == accepting
        assert row["busy_employees"] == sum(1 for state in states if state in SERVING_STATES)
        assert row["register_occupancy"] == sum(1 for state in states if state in REGISTER_STATES)
        assert row["register_occupancy"] <= workforce.register_count
        assert row["waiting_for_register"] == states.count(WAITING_FOR_REGISTER)
        assert (row["scheduled_active"], row["required_staffing"]) == (scheduled, need)
        # Phase 5B-4.4 rule 5: both gaps exist only inside the operating horizon [0, closing).
        inside = 0.0 <= t < close
        assert (need is not None) == inside
        assert row["schedule_realization_gap"] == (accepting - scheduled if inside else None)
        assert row["requirement_gap"] == (accepting - need if need is not None else None)
    kinds = [item["kind"] for item in result["staffing"]["windows"]]
    assert kinds.count("horizon") == kinds.count("after_closing") == 1
    assert kinds.count("staffing_segment") == len(required)
    assert kinds.count("before_opening") == (1 if employees["begin"] < 0.0 else 0)
    for item in result["staffing"]["windows"]:
        low, high = item["start"], item["end"]
        overlap = [(min(high, row["end"]) - max(low, row["start"]), row) for row in steps
                   if row["start"] < high and row["end"] > low]
        accepting_hours = sum(min(high, row["end"]) - max(low, row["start"]) for row in intervals
                              if row["state"] in ACCEPTING and row["start"] < high and row["end"] > low)
        scheduled_hours = sum(min(high, end) - max(low, start) for start, end in schedule if start < high and end > low)
        assert _close(item["accepting_capacity_hours"], accepting_hours, exact)
        assert _close(item["scheduled_active_hours"], scheduled_hours, exact)
        if item["kind"] in ("staffing_segment", "horizon"):
            assert 0.0 <= low < high <= close
            for key in ("schedule_realization_gap", "requirement_gap"):
                assert _close(item[key]["shortfall_hours"],
                              sum(length * max(0, -row[key]) for length, row in overlap), exact)
                assert _close(item[key]["excess_hours"], sum(length * max(0, row[key]) for length, row in overlap),
                              exact)
        else:
            # Before opening and after closing: the series are reported, and no gap or requirement is calculated.
            assert high <= 0.0 if item["kind"] == "before_opening" else low == close
            assert item["schedule_realization_gap"] is None and item["requirement_gap"] is None
            assert item["required_staffing_hours"] is None

    # 18: the queue-length integral equals the waits, served and censored at closing.
    total = sum(row["wait_hours"] for row in done) + sum(row["elapsed_wait_at_close_hours"] for row in missed)
    assert _close(result["queue"]["customer_hours_total"], total, exact)
    assert result["queue"]["customer_hours_total"] == (result["queue"]["customer_hours_in_horizon"]
                                                       + result["queue"]["customer_hours_after_closing"])


# ── Hand-computed cases ─────────────────────────────────────────────────────


def test_normal_service():
    # A 08:00-12:00, one register. #1 (0.5, work 1) is served 0.5-0.75. #2 arrives 0.625 and waits for A:
    # 0.75-0.875 (wait 0.125). #3 is served 2.0-2.5. Under DRAIN, A is idle at closing and released then.
    roster = [shift("A", 480, 720)]
    result = simulate(roster, rules(registers=1), [(0.5, 1.0), (0.625, 0.5), (2.0, 2.0)])
    assert served(result) == [(1, 0.5, 0.75, "A", 1, 0.0), (2, 0.75, 0.875, "A", 1, 0.125), (3, 2.0, 2.5, "A", 1, 0.0)]
    assert result["queue"]["customer_hours_total"] == 0.125
    assert timeline(result["employee_timeline"], "A") == [
        (0.0, 0.5, AVAILABLE, 1), (0.5, 0.875, SERVING, 1), (0.875, 2.0, AVAILABLE, 1), (2.0, 2.5, SERVING, 1),
        (2.5, 4.0, AVAILABLE, 1)]
    assert result["at_close"]["drain_crew"] == ["A"] and result["finish"] == 4.0


def test_break_due_during_service():
    # A 08:00-12:00 with a 30-minute break at 09:00 (1.0). #1 (0.75, work 2) is served 0.75-1.25, so the break
    # falls due while serving (SERVING_BREAK_DUE 1.0-1.25) and starts at the completion with its full length:
    # 1.25-1.75, delay 0.25. #2 arrives 1.125 while the break is due: no pre-break cutoff, so A does not take
    # it; it is served when A returns, 1.75-1.875 (wait 0.625).
    roster = [shift("A", 480, 720, rest=540)]
    result = simulate(roster, rules(*LONG_SHIFT_BREAK, registers=1), [(0.75, 2.0), (1.125, 0.5)])
    assert served(result) == [(1, 0.75, 1.25, "A", 1, 0.0), (2, 1.75, 1.875, "A", 1, 0.625)]
    assert timeline(result["employee_timeline"], "A")[1:4] == [
        (0.75, 1.0, SERVING, 1), (1.0, 1.25, SERVING_BREAK_DUE, 1), (1.25, 1.75, ON_BREAK, None)]
    (item,) = break_rows(result["employee_timeline"], "A")
    assert (item["due"], item["actual_start"], item["actual_end"], item["delay"], item["outcome"]) == (
        1.0, 1.25, 1.75, 0.25, COMPLETED)


def test_shift_end_during_service():
    # A 08:00-10:00 and B 10:00-12:00, two registers. #1 (1.75, work 2) is served by A 1.75-2.25: A's shift
    # ends at 2.0 while serving, so A finishes (overrun 0.25) and takes no new customer. #2 (2.0, work 2) goes to
    # B, 2.0-2.5. #3 arrives 2.125: A is SERVING_SHIFT_ENDED and B is busy, and A is released at 2.25 without
    # taking #3, so #3 waits for B: 2.5-2.625 (wait 0.375).
    roster = [shift("A", 480, 600), shift("B", 600, 720)]
    result = simulate(roster, rules(registers=2), [(1.75, 2.0), (2.0, 2.0), (2.125, 0.5)])
    assert served(result) == [(1, 1.75, 2.25, "A", 1, 0.0), (2, 2.0, 2.5, "B", 2, 0.0), (3, 2.5, 2.625, "B", 2, 0.375)]
    row = shift_row(result["employee_timeline"], "A")
    assert (row["release"], row["overrun"], row["release_trigger"], row["release_basis"]) == (
        2.25, 0.25, "employee_service_completion", "scheduled_shift_end")
    assert timeline(result["employee_timeline"], "A")[-2:] == [(2.0, 2.25, SERVING_SHIFT_ENDED, 1), (2.25, 4.0, OFF, None)]


def test_register_handover():
    # One register. A 08:00-10:00 serves #1 (1.75, work 2) 1.75-2.25, past its shift end. B's shift starts at
    # 2.0 and waits for the register until A's release at 2.25 (P4). #2 arrives 2.125 and waits; at 2.25 A
    # completes and is released, B takes register 1, and the assignment pass gives #2 to B: 2.25-2.5.
    roster = [shift("A", 480, 600), shift("B", 600, 720)]
    result = simulate(roster, rules(registers=1), [(1.75, 2.0), (2.125, 1.0)])
    assert served(result) == [(1, 1.75, 2.25, "A", 1, 0.0), (2, 2.25, 2.5, "B", 1, 0.125)]
    assert timeline(result["employee_timeline"], "B") == [
        (0.0, 2.0, OFF, None), (2.0, 2.25, WAITING_FOR_REGISTER, None), (2.25, 2.5, SERVING, 1),
        (2.5, 4.0, AVAILABLE, 1)]
    assert staffing_at(result, 2.0)["waiting_for_register"] == 1 and staffing_at(result, 2.0)["register_occupancy"] == 1
    assert staffing_at(result, 2.0)["accepting_capacity"] == 0  # A is SERVING_SHIFT_ENDED, B has no register


def test_backlog_during_break():
    # A 08:00-12:00, 30-minute break at 09:00: A is idle, so it runs 1.0-1.5. #1 (1.125, work 1) and #2 (1.25,
    # work 0.5) wait: #1 1.5-1.75 (wait 0.375), #2 1.75-1.875 (wait 0.5). The line integral is 0.875.
    roster = [shift("A", 480, 720, rest=540)]
    result = simulate(roster, rules(*LONG_SHIFT_BREAK, registers=1), [(1.125, 1.0), (1.25, 0.5)])
    assert served(result) == [(1, 1.5, 1.75, "A", 1, 0.375), (2, 1.75, 1.875, "A", 1, 0.5)]
    assert result["queue"]["customer_hours_total"] == 0.875
    # During the break nobody accepts: 0.5 employee-hours below the one required server, and 0 against the
    # schedule (the break is scheduled there).
    segment = window(result, "S")
    assert segment["requirement_gap"] == {"shortfall_hours": 0.5, "excess_hours": 0.0}
    assert segment["schedule_realization_gap"] == {"shortfall_hours": 0.0, "excess_hours": 0.0}


def test_delayed_split_shift():
    # A: 08:00-09:00 and 09:30-11:30 (15-minute break at 10:00, offset 30 minutes), rest 30 minutes, one
    # register. #1 (0.5, work 4.5) is served 0.5-1.625, so shift 0 is released at 1.625 and shift 1 activates
    # at 1.625 + 0.5 = 2.125 (scheduled 1.5; the end 3.5 stays fixed). #2 arrives 1.75 and waits: 2.125-2.375.
    # P3: the break falls due at 2.125 + 0.5 = 2.625 and runs 2.625-2.875. #3 arrives 2.75 and waits: 2.875-3.0.
    workforce = rules(BreakRule(15, 60, 0, ()), break_rule(61, 480, rest=15), registers=1, max_shifts=2, rest=30)
    roster = [shift("A", 480, 540), shift("A", 570, 690, rest=600)]
    result = simulate(roster, workforce, [(0.5, 4.5), (1.75, 1.0), (2.75, 0.5)])
    assert served(result) == [(1, 0.5, 1.625, "A", 1, 0.0), (2, 2.125, 2.375, "A", 1, 0.375),
                              (3, 2.875, 3.0, "A", 1, 0.125)]
    second = shift_row(result["employee_timeline"], "A", 1)
    assert (second["actual_start"], second["activation_delay"], second["release"]) == (2.125, 0.625, 3.5)
    (item,) = break_rows(result["employee_timeline"], "A")
    assert (item["scheduled_start"], item["due"], item["actual_start"], item["actual_end"]) == (2.0, 2.625, 2.625, 2.875)
    # Scheduled active: 1 on 0-1, 1.5-2.0, and 2.25-3.5 (the planned break is 2.0-2.25). Accepting: 1 on 0-1,
    # 2.125-2.625, and 2.875-3.5. The schedule gap is -1 on 1.5-2.0 and 2.625-2.875 (shortfall 0.75) and +1 on
    # 2.125-2.25 (excess 0.125), where A works through the planned break time.
    assert window(result, "S")["schedule_realization_gap"] == {"shortfall_hours": 0.75, "excess_hours": 0.125}


def test_pushed_second_break():
    # A 08:00-12:00 with "first" (15 minutes) at 09:00 and "second" (15 minutes) at 09:45, minimum gap 30
    # minutes. #1 (0.875, work 1.5) is served 0.875-1.25, so "first" is delayed to 1.25-1.5. "second" is pushed
    # to max(1.75, 1.5 + 0.5) = 2.0 and runs 2.0-2.25. #2 arrives 2.125, during it, and waits: 2.25-2.375.
    workforce = rules(break_rule(15, 480, gap=30, first=15, second=15), registers=1)
    roster = [shift("A", 480, 720, first=540, second=585)]
    result = simulate(roster, workforce, [(0.875, 1.5), (2.125, 0.5)])
    assert [(item["name"], item["due"], item["actual_start"], item["actual_end"], item["delay"])
            for item in break_rows(result["employee_timeline"], "A")] == [
        ("first", 1.0, 1.25, 1.5, 0.25), ("second", 2.0, 2.0, 2.25, 0.25)]
    assert served(result)[1] == (2, 2.25, 2.375, "A", 1, 0.125)


def test_capacity_shortfall_caused_by_a_delayed_break():
    # A and B 08:00-12:00, two registers, two servers required throughout. A's 30-minute break is scheduled
    # 1.0-1.5. #1 (0.75, work 2) goes to A (both idle since 0.0; tie to A), 0.75-1.25, so the break runs
    # 1.25-1.75. #2 (1.5, work 1) goes to B, 1.5-1.75. #3 arrives 1.625: A is still on the delayed break and B is
    # busy, so #3 waits until 1.75 (A's handover and B's completion tie; A by employee_id): 1.75-1.875.
    required = [StaffingSegment("S", 480, 720, 2)]
    roster = [shift("A", 480, 720, rest=540), shift("B", 480, 720, rest=660)]
    result = simulate(roster, rules(*LONG_SHIFT_BREAK, registers=2), [(0.75, 2.0), (1.5, 1.0), (1.625, 0.5)],
                      required=required)
    assert served(result) == [(1, 0.75, 1.25, "A", 1, 0.0), (2, 1.5, 1.75, "B", 2, 0.0), (3, 1.75, 1.875, "A", 1, 0.125)]
    # On 1.5-1.75 two employees are scheduled but only B accepts: schedule shortfall 0.25 employee-hours. On
    # 1.0-1.75 one employee accepts against two required: requirement shortfall 0.75. The gaps differ.
    assert staffing_at(result, 1.5)["schedule_realization_gap"] == -1
    assert staffing_at(result, 1.0)["schedule_realization_gap"] == 0 and staffing_at(result, 1.0)["requirement_gap"] == -1
    segment = window(result, "S")
    assert segment["schedule_realization_gap"]["shortfall_hours"] == 0.25
    # B's break at 11:00 (3.0-3.5) is scheduled and taken on time: another 0.5 against the requirement.
    assert segment["requirement_gap"]["shortfall_hours"] == 0.75 + 0.5


# Closing roster: A 08:00-12:00 (break 08:30), B 08:00-12:00 (break 11:30), C 12:00-13:00; three registers.
CLOSING_ROSTER = [shift("A", 480, 720, rest=510), shift("B", 480, 720, rest=690), shift("C", 720, 780)]
CLOSING_RULES = rules(*LONG_SHIFT_BREAK, registers=3)
# A's break 0.5-1.0 makes A AVAILABLE since 1.0, B since 0.0. #1 (3.25) goes to B, idle longest (X1),
# 3.25-3.75 on register 2. #2 (3.375) goes to A, 3.375-3.875 on register 1. B's break falls due at 3.5 while
# serving and starts at its completion, 3.75 (due to end 4.25). #3 (3.5) and #4 (3.625) wait. At 3.875 A's
# completion comes before #5's arrival, and the pass gives #3 to A: 3.875-4.375. #4 and #5 are waiting at
# closing.
CLOSING_ARRIVALS = [(3.25, 2.0), (3.375, 2.0), (3.5, 2.0), (3.625, 1.0), (3.875, 1.0)]
REQUIRED_TWO = [StaffingSegment("S", 480, 720, 2)]


def test_drain_freezes_the_crew_and_serves_the_admitted_line():
    # At closing A is serving (crew, although its shift ends at closing), B is on its delayed break (excluded:
    # the break is truncated at 4.0 and B released), and C starts at closing (excluded, never activated).
    # A alone serves #4 4.375-4.625 and #5 4.625-4.875, then is released: overrun 0.875.
    result = simulate(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, required=REQUIRED_TWO)
    assert result["at_close"]["drain_crew"] == ["A"]
    assert result["at_close"]["waiting_customer_ids"] == [4, 5]
    assert served(result) == [(1, 3.25, 3.75, "B", 2, 0.0), (2, 3.375, 3.875, "A", 1, 0.0),
                              (3, 3.875, 4.375, "A", 1, 0.375), (4, 4.375, 4.625, "A", 1, 0.75),
                              (5, 4.625, 4.875, "A", 1, 0.75)]
    assert result["at_close"]["closing_inputs"] == [
        {"type": "CancelPendingBreaks", "employee_id": "A"},
        {"type": "CancelPendingBreaks", "employee_id": "B"}, {"type": "Release", "employee_id": "B"},
        {"type": "EndBreakAtClosing", "employee_id": "B"},
        {"type": "CancelPendingBreaks", "employee_id": "C"}, {"type": "Release", "employee_id": "C"}]
    employees = result["employee_timeline"]
    assert (shift_row(employees, "A")["release"], shift_row(employees, "A")["overrun"]) == (4.875, 0.875)
    b_break = break_rows(employees, "B")[0]
    assert (b_break["actual_start"], b_break["actual_end"], b_break["delay"], b_break["outcome"]) == (
        3.75, 4.0, 0.25, TRUNCATED_BY_CLOSING)
    assert shift_row(employees, "B")["release"] == 4.0
    assert (shift_row(employees, "C")["activated"], shift_row(employees, "C")["not_activated_reason"]) == (
        False, "released_after_closing")
    # Waits 0.375 + 0.75 + 0.75 = 1.875 customer-hours. Before closing: 1 waiting on 3.5-3.625 and 2 on
    # 3.625-4.0 (0.875); after: 2 on 4.0-4.375 and 1 on 4.375-4.625 (1.0).
    assert result["queue"] == {"customer_hours_in_horizon": 0.875, "customer_hours_after_closing": 1.0,
                               "customer_hours_total": 1.875, "max_length_in_horizon": 2}
    # After closing, C is scheduled 4.0-5.0 but released, and A serves 4.0-4.875. Phase 5B-4.4 rule 5: the
    # after-closing window reports the scheduled 1.0 employee-hour and A's 0.875 accepting (and busy) hours
    # separately, with no gap.
    after = window(result, "after_closing")
    assert (after["duration_hours"], after["scheduled_active_hours"], after["accepting_capacity_hours"],
            after["busy_employee_hours"]) == (1.0, 1.0, 0.875, 0.875)
    assert after["schedule_realization_gap"] is None and after["requirement_gap"] is None


def test_hard_cutoff():
    # Same day under HARD_CUTOFF: #4 and #5 are unserved at closing (elapsed waits 0.375 and 0.125). A finishes
    # #3 (released at 4.375, overrun 0.375); nothing starts at or after closing.
    result = simulate(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, policy=HARD_CUTOFF, required=REQUIRED_TWO)
    assert unserved(result) == [(4, HARD_CUTOFF_REASON, 0.375), (5, HARD_CUTOFF_REASON, 0.125)]
    assert served(result)[-1] == (3, 3.875, 4.375, "A", 1, 0.375)
    assert result["at_close"]["drain_crew"] == []
    a = shift_row(result["employee_timeline"], "A")
    assert (a["release"], a["overrun"], a["release_basis"]) == (4.375, 0.375, "release_input")
    assert timeline(result["employee_timeline"], "A")[-1] == (4.0, 4.375, SERVING_SHIFT_ENDED, 1)
    assert result["queue"]["customer_hours_total"] == 0.375 + 0.375 + 0.125


def test_hard_cutoff_releases_an_idle_employee_at_closing():
    # A 08:00-13:00 (break 09:00) is idle at closing: released at 4.0, although its shift runs to 5.0.
    result = simulate([shift("A", 480, 780, rest=540)], rules(*LONG_SHIFT_BREAK, registers=1), [(0.5, 1.0)],
                      policy=HARD_CUTOFF)
    row = shift_row(result["employee_timeline"], "A")
    assert (row["release"], row["release_trigger"]) == (4.0, "employee_release_input")


def test_empty_frozen_crew_marks_the_line_no_eligible_employee():
    # A 08:00-12:00 takes its 30-minute break at 11:30 (3.5-4.0) while idle, so A, on a break immediately before
    # closing, is not in the crew. #1 arrives 3.75 and waits. The crew is empty, so #1 is unserved:
    # no_eligible_employee, elapsed wait 0.25 (X6). The break ends exactly at closing; Phase 5B-4.4 rule 2
    # records it truncated_by_closing (this expectation was COMPLETED in 5B-4.3, where the case was INFERRED).
    result = simulate([shift("A", 480, 720, rest=690)], rules(*LONG_SHIFT_BREAK, registers=1), [(3.75, 1.0)])
    assert result["at_close"]["drain_crew"] == []
    assert unserved(result) == [(1, NO_ELIGIBLE_EMPLOYEE, 0.25)]
    (item,) = break_rows(result["employee_timeline"], "A")
    assert (item["actual_start"], item["actual_end"], item["outcome"]) == (3.5, 4.0, TRUNCATED_BY_CLOSING)
    assert result["counts"]["unserved_by_reason"] == {HARD_CUTOFF_REASON: 0, NO_ELIGIBLE_EMPLOYEE: 1}


# ── Same-time cases ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_completion_at_closing(policy):
    # A 08:00-12:00 serves #1 (3.5, work 2) 3.5-4.0; #2 (3.75) waits. At 4.0 the completion comes first (X2).
    # DRAIN: A was serving just before closing, so it is in the crew and serves #2 at 4.0-4.25.
    # HARD_CUTOFF: #2 is unserved and A is released at 4.0.
    result = simulate([shift("A", 480, 720)], rules(registers=1), [(3.5, 2.0), (3.75, 1.0)], policy=policy)
    if policy == DRAIN:
        assert served(result)[1] == (2, 4.0, 4.25, "A", 1, 0.25)
        assert shift_row(result["employee_timeline"], "A")["release"] == 4.25
    else:
        assert unserved(result) == [(2, HARD_CUTOFF_REASON, 0.25)]
        assert shift_row(result["employee_timeline"], "A")["release"] == 4.0


def test_drain_crew_left_idle_is_released_in_x1_order():
    # A and B 08:00-12:00, two registers. #1 (3.5, work 2) -> A (tie since 0.0), 3.5-4.0; #2 (3.625, work 1.5) ->
    # B, 3.625-4.0; #3 (3.75) waits. Both complete at closing and are in the crew. One customer waits for two
    # idle crew members: X1 ranks A first (both AVAILABLE since 4.0; tie by id), so A serves #3 4.0-4.25 and B,
    # left with nobody to serve, is released at closing.
    roster = [shift("A", 480, 720), shift("B", 480, 720)]
    result = simulate(roster, rules(registers=2), [(3.5, 2.0), (3.625, 1.5), (3.75, 1.0)])
    assert result["at_close"]["drain_crew"] == ["A", "B"]
    assert served(result)[2] == (3, 4.0, 4.25, "A", 1, 0.25)
    employees = result["employee_timeline"]
    assert (shift_row(employees, "A")["release"], shift_row(employees, "B")["release"]) == (4.25, 4.0)
    assert result["at_close"]["closing_inputs"][-1] == {"type": "Release", "employee_id": "B"}


def test_drain_releases_idle_crew_in_employee_id_order():
    # Phase 5B-4.5 trace-order rule. A, B, C 08:00-12:00, three registers. #1 (0.5, work 1) -> A (all AVAILABLE
    # since 0.0; tie by id), 0.5-0.75, so A is AVAILABLE since 0.75 and B, C since 0.0. At closing all three are
    # idle crew members and nobody waits, so all three are released at the same instant. X1 would rank them B, C, A
    # (the fd67bbf2 engine recorded that order); the releases are recorded in employee_id order A, B, C, and no
    # customer result depends on it.
    roster = [shift(name, 480, 720) for name in "ABC"]
    result = simulate(roster, rules(registers=3), [(0.5, 1.0)], required=[StaffingSegment("S", 480, 720, 3)])
    assert served(result) == [(1, 0.5, 0.75, "A", 1, 0.0)]
    assert result["at_close"]["drain_crew"] == ["A", "B", "C"]
    assert [(row["stage"], row["employee_id"], row["from_state"], row["to_state"])
            for row in result["employee_timeline"]["transitions"] if row["t"] == CLOSE] == [
        ("closing_input", "A", AVAILABLE, OFF), ("closing_input", "B", AVAILABLE, OFF),
        ("closing_input", "C", AVAILABLE, OFF)]
    assert result["at_close"]["closing_inputs"][3:] == [{"type": "Release", "employee_id": name} for name in "ABC"]


def test_trace_records_employee_transitions_before():
    # Phase 5B-4.5: each customer event records how many employee transitions precede it. Same day as
    # test_normal_service. Transitions: 0 A shift start (0.0), 1 A register 1 (0.0), 2 A starts #1 (0.5), 3 A
    # completes #1 (0.75), 4 A starts #2 (0.75), 5 A completes #2 (0.875), 6 A starts #3 (2.0), 7 A completes #3
    # (2.5), 8 A released at closing. Arrivals follow the instant's state-machine stages, each service_start
    # follows its employee's start transition, and service_end and closing precede the instant's transitions.
    result = simulate([shift("A", 480, 720)], rules(registers=1), [(0.5, 1.0), (0.625, 0.5), (2.0, 2.0)])
    assert [row["event"] for row in result["employee_timeline"]["transitions"]] == [
        "employee_shift_start", "employee_register_assigned", "employee_service_start", "employee_service_completion",
        "employee_service_start", "employee_service_completion", "employee_service_start",
        "employee_service_completion", "employee_release_input"]
    assert [(row["type"], row["employee_transitions_before"]) for row in result["trace"]] == [
        ("arrival", 2), ("service_start", 3), ("arrival", 3), ("service_end", 3), ("service_start", 5),
        ("service_end", 5), ("arrival", 6), ("service_start", 7), ("service_end", 7), ("closing", 8)]


def test_trace_schema_v3_adds_only_employee_transitions_before():
    # Engine v3 (Phase 5B-4.5): the customer trace gained exactly one key over v2; the employee transition record
    # (state machine, unchanged) keeps its eight keys.
    result = _run(arrivals=[(1.0, 1.0), (2.0, 1.0)])
    assert result["provenance"]["engine_version"] == "novaq-shared-named-des-v3"
    v2_keys = {"t", "type", "customer_id", "employee_id", "register_id", "queue_len_after"}
    assert all(set(event) == v2_keys | {"employee_transitions_before"} for event in result["trace"])
    assert all(set(row) == {"t", "stage", "employee_id", "from_state", "to_state", "register_before", "register_after",
                            "event"} for row in result["employee_timeline"]["transitions"])


def test_break_due_service_across_closing_finishes_then_releases():
    # A 08:00-12:00 with a 30-minute break at 11:30 (3.5). #1 (3.25, work 4) is served 3.25-4.25, so the break is
    # due at 3.5 while serving. At closing A is not in the crew (a break is pending): Release comes first, so A
    # goes straight from SERVING_BREAK_DUE to SERVING_SHIFT_ENDED without passing through SERVING, finishes #1,
    # and is released at 4.25. The break never starts: unfulfilled, cancelled_at_closing. #2 (3.75) is unserved.
    result = simulate([shift("A", 480, 720, rest=690)], rules(*LONG_SHIFT_BREAK, registers=1),
                      [(3.25, 4.0), (3.75, 1.0)])
    employees = result["employee_timeline"]
    assert [(row["stage"], row["from_state"], row["to_state"]) for row in employees["transitions"]
            if row["t"] == 4.0] == [("closing_input", SERVING_BREAK_DUE, SERVING_SHIFT_ENDED)]
    assert result["at_close"]["drain_crew"] == [] and unserved(result) == [(2, NO_ELIGIBLE_EMPLOYEE, 0.25)]
    (item,) = break_rows(employees, "A")
    assert (item["due"], item["outcome"], item["unfulfilled_cause"]) == (3.5, UNFULFILLED, "cancelled_at_closing")
    assert (shift_row(employees, "A")["release"], shift_row(employees, "A")["overrun"]) == (4.25, 0.25)


def test_shift_end_at_closing_keeps_an_idle_employee_in_the_crew():
    # A 08:00-12:00 is idle immediately before closing: in the DRAIN crew, then released at closing because
    # nobody waits.
    result = simulate([shift("A", 480, 720)], rules(registers=1), [(1.0, 1.0)])
    assert result["at_close"]["drain_crew"] == ["A"]
    assert result["at_close"]["closing_inputs"][-1] == {"type": "Release", "employee_id": "A"}


def test_completion_and_shift_end_at_one_instant():
    # A 08:00-10:00 and B 08:00-12:00, two registers. #1 (1.5, work 2) goes to A (tie), 1.5-2.0; #2 (1.625,
    # work 2) to B, 1.625-2.125. #3 (1.875) waits. At 2.0 A's completion comes before its shift end (X2), so A is
    # released with no overrun and does not take #3; #4 arrives at 2.0, behind #3. B serves #3 2.125-2.375 and
    # #4 2.375-2.5.
    roster = [shift("A", 480, 600), shift("B", 480, 720)]
    result = simulate(roster, rules(registers=2), [(1.5, 2.0), (1.625, 2.0), (1.875, 1.0), (2.0, 0.5)])
    assert served(result)[2:] == [(3, 2.125, 2.375, "B", 2, 0.25), (4, 2.375, 2.5, "B", 2, 0.375)]
    row = shift_row(result["employee_timeline"], "A")
    assert (row["release"], row["overrun"]) == (2.0, 0.0)


def test_break_due_at_closing_is_cancelled_for_a_crew_member():
    # A 08:00-12:30 (270 minutes) has a 30-minute break at 12:00 (4.0). A is idle just before closing, so it is
    # in the DRAIN crew; the closing boundary comes before breaks due (X2), and the break is cancelled.
    result = simulate([shift("A", 480, 750, rest=720)], rules(*LONG_SHIFT_BREAK, registers=1), [(1.0, 1.0)])
    assert result["at_close"]["drain_crew"] == ["A"]
    (item,) = break_rows(result["employee_timeline"], "A")
    assert (item["outcome"], item["unfulfilled_cause"]) == (UNFULFILLED, "cancelled_at_closing")


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_break_due_service_completing_exactly_at_closing_cancels_the_break(policy):
    # Phase 5B-4.4 rule 1 (5B-4.3 raised UndeterminedPolicyError here). A 08:00-12:00, break at 11:30 (3.5).
    # #1 (3.25, work 3) is served 3.25-4.0, so the break is due from 3.5 and the completion falls exactly at
    # closing. The service completes first: #1 departs at 4.0 and is not in service at closing. A was pending a
    # break immediately before closing, so it is not in the DRAIN crew. The break never starts (no zero-length
    # break): it is unfulfilled, cancelled_at_closing, and A is released at 4.0. #2 (3.75) is unserved:
    # no_eligible_employee under DRAIN (empty crew), hard_cutoff under HARD_CUTOFF.
    result = simulate([shift("A", 480, 720, rest=690)], rules(*LONG_SHIFT_BREAK, registers=1),
                      [(3.25, 3.0), (3.75, 1.0)], policy=policy)
    assert served(result) == [(1, 3.25, 4.0, "A", 1, 0.0)]
    assert unserved(result) == [(2, NO_ELIGIBLE_EMPLOYEE if policy == DRAIN else HARD_CUTOFF_REASON, 0.25)]
    assert result["at_close"]["drain_crew"] == [] and result["at_close"]["in_service_customer_ids"] == []
    assert result["at_close"]["closing_inputs"] == [{"type": "CancelPendingBreaks", "employee_id": "A"},
                                                    {"type": "Release", "employee_id": "A"}]
    employees = result["employee_timeline"]
    (item,) = break_rows(employees, "A")
    assert (item["due"], item["actual_start"], item["actual_end"], item["outcome"], item["unfulfilled_cause"]) == (
        3.5, None, None, UNFULFILLED, "cancelled_at_closing")
    assert [(row["stage"], row["from_state"], row["to_state"]) for row in employees["transitions"]
            if row["t"] == 4.0] == [("completion", SERVING_BREAK_DUE, AVAILABLE), ("closing_input", AVAILABLE, OFF)]
    assert ON_BREAK not in [state for _, _, state, _ in timeline(employees, "A")]
    assert (shift_row(employees, "A")["release"], shift_row(employees, "A")["overrun"]) == (4.0, 0.0)
    # The run ends at closing, and the after-closing window is still reported, with zero duration.
    assert result["finish"] == 4.0 and window(result, "after_closing")["duration_hours"] == 0.0


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_break_ending_exactly_at_closing_is_truncated_by_closing(policy):
    # Phase 5B-4.4 rule 2. A and B 08:00-12:00, two registers, no customers. A's 30-minute break at 11:30 runs
    # 3.5-4.0, ending exactly at closing; B's runs 1.0-1.5. Closing is processed before break ends (X2), so A's
    # break is truncated at closing (after its full 30 minutes) and A is released there; A never returns to add
    # DRAIN capacity. B, idle immediately before closing, is the DRAIN crew (nobody under HARD_CUTOFF) and, with
    # nobody waiting, is released at closing too.
    roster = [shift("A", 480, 720, rest=690), shift("B", 480, 720, rest=540)]
    result = simulate(roster, rules(*LONG_SHIFT_BREAK, registers=2), [], policy=policy)
    employees = result["employee_timeline"]
    (item,) = break_rows(employees, "A")
    assert (item["actual_start"], item["actual_end"], item["delay"], item["outcome"]) == (
        3.5, 4.0, 0.0, TRUNCATED_BY_CLOSING)
    assert [(row["stage"], row["from_state"], row["to_state"], row["event"]) for row in employees["transitions"]
            if row["t"] == 4.0 and row["employee_id"] == "A"] == [
        ("closing_input", ON_BREAK, OFF, "employee_break_truncated_at_closing")]
    assert shift_row(employees, "A")["release"] == 4.0 and break_rows(employees, "B")[0]["outcome"] == COMPLETED
    assert result["at_close"]["drain_crew"] == (["B"] if policy == DRAIN else [])


def test_staffing_gaps_are_calculated_only_inside_the_operating_horizon():
    # Phase 5B-4.4 rule 5. A 07:30-11:30 starts 0.5 h before opening; B 10:00-13:00 runs 1 h past closing; two
    # registers, one server required, no customers. Under DRAIN, B (idle) is the crew and is released at closing.
    # Before opening (-0.5-0): A accepts 0.5 employee-hours, scheduled 0.5. Horizon (0-4): accepting and scheduled
    # are both A 0-3.5 plus B 2-4 = 5.5, so the schedule gap is 0; against one required server the excess is 1.5
    # (2.0-3.5). After closing (4-5): B is scheduled 1.0 employee-hour but released, so accepting is 0. Gaps are
    # reported only for the segment and the horizon; outside it the series stand alone.
    roster = [shift("A", 450, 690), shift("B", 600, 780)]
    result = simulate(roster, rules(registers=2), [])
    before, horizon, after = (window(result, name) for name in ("before_opening", "horizon", "after_closing"))
    assert (before["start"], before["end"], before["accepting_capacity_hours"], before["scheduled_active_hours"]) == (
        -0.5, 0.0, 0.5, 0.5)
    assert (horizon["accepting_capacity_hours"], horizon["scheduled_active_hours"], horizon["required_staffing_hours"]) == (
        5.5, 5.5, 4.0)
    assert horizon["schedule_realization_gap"] == {"shortfall_hours": 0.0, "excess_hours": 0.0}
    assert horizon["requirement_gap"] == {"shortfall_hours": 0.0, "excess_hours": 1.5}
    assert window(result, "S")["requirement_gap"] == horizon["requirement_gap"]
    assert (after["start"], after["end"], after["scheduled_active_hours"], after["accepting_capacity_hours"]) == (
        4.0, 5.0, 1.0, 0.0)
    for outside in (before, after):
        assert outside["schedule_realization_gap"] is None and outside["requirement_gap"] is None
        assert outside["required_staffing_hours"] is None
    for t, gaps in ((-0.25, (None, None)), (3.0, (0, 1)), (4.5, (None, None))):
        row = staffing_at(result, t)
        assert (row["schedule_realization_gap"], row["requirement_gap"]) == gaps, t


# ── First come, first served, and X1 ────────────────────────────────────────


def test_fcfs_with_several_employees():
    # A, B, C 08:00-12:00, three registers. Four customers arrive at 1.0 and one at 1.125. X1 (all idle since
    # 0.0, ties by id): #1 -> A 1.0-1.5, #2 -> B 1.0-1.25, #3 -> C 1.0-1.75. #4 and #5 wait in arrival order;
    # B frees first: #4 1.25-1.375, then #5 1.375-1.5.
    roster = [shift(name, 480, 720) for name in "ABC"]
    arrivals = [(1.0, 2.0), (1.0, 1.0), (1.0, 3.0), (1.0, 0.5), (1.125, 0.5)]
    result = simulate(roster, rules(registers=3), arrivals)
    assert served(result) == [(1, 1.0, 1.5, "A", 1, 0.0), (2, 1.0, 1.25, "B", 2, 0.0), (3, 1.0, 1.75, "C", 3, 0.0),
                              (4, 1.25, 1.375, "B", 2, 0.25), (5, 1.375, 1.5, "B", 2, 0.25)]


def test_x1_longest_available_employee():
    # A, B, C 08:00-12:00, three registers. #1 (0.5) -> A (all idle since 0.0; tie to A), 0.5-0.75. #2 (0.625)
    # -> B (B and C since 0.0), 0.625-0.875. Now A is AVAILABLE since 0.75, B since 0.875, C since 0.0.
    # #3 (1.0, work 4) -> C, idle longest (lowest id would give A), 1.0-2.0. #4 (1.125, work 3.5) -> A (since
    # 0.75), 1.125-2.0. #5 (1.25, work 3) -> B, 1.25-2.0. All three complete at 2.0, so at #6 (2.5) they are
    # AVAILABLE since 2.0 alike and the tie goes to A.
    roster = [shift(name, 480, 720) for name in "ABC"]
    arrivals = [(0.5, 1.0), (0.625, 1.0), (1.0, 4.0), (1.125, 3.5), (1.25, 3.0), (2.5, 1.0)]
    result = simulate(roster, rules(registers=3), arrivals)
    assert [row[3] for row in served(result)] == ["A", "B", "C", "A", "B", "A"]


# ── Invariant 19 and the reduction to the anonymous engine ──────────────────


def test_common_prescribed_arrivals_give_identical_demand_across_rosters():
    arrivals = [(0.5, 1.0), (0.625, 2.0), (1.5, 0.5), (3.875, 1.0)]
    one = simulate([shift("A", 480, 720)], rules(registers=1), arrivals)
    two = simulate([shift("A", 480, 720, rest=540), shift("B", 600, 720)], rules(*LONG_SHIFT_BREAK, registers=2),
                   arrivals, required=[StaffingSegment("S1", 480, 600, 1), StaffingSegment("S2", 600, 720, 2)])
    demand = [[(row["customer_id"], row["arrival_hours"], row["unit_work"]) for row in result["customers"]]
              for result in (one, two)]
    assert demand[0] == demand[1] == [(position, at, work) for position, (at, work) in enumerate(arrivals, start=1)]


def _generated_arrivals(seed: int, periods: list[DemandPeriod], grid: bool) -> list[tuple[float, float]]:
    """Prescribed pairs generated for a comparison of the two engines (no golden values)."""
    generator = random.Random(seed)
    arrivals: list[tuple[float, float]] = []
    t = 0.0
    while True:
        rate = next(float(period.arrival_rate_per_hour) for period in periods
                    if (period.start_minute - 480) / 60.0 <= t < (period.end_minute - 480) / 60.0)
        t += generator.expovariate(rate)
        if grid:
            t = round(t * 64) / 64
        if t >= CLOSE:
            return arrivals
        work = generator.expovariate(1.0)
        arrivals.append((t, max(1 / 16, round(work * 16) / 16) if grid else work))


TWO_PERIODS = [DemandPeriod("P1", 480, 600, 9.0, 4.0), DemandPeriod("P2", 600, 720, 12.0, 6.0)]
REDUCTIONS = {
    # A fixed crew with no breaks: two employees on the whole horizon, two anonymous servers throughout (the
    # segments are split at the demand-period boundary, as validate_timeline requires).
    "fixed_crew": ([shift("A", 480, 720), shift("B", 480, 720)],
                   [StaffingSegment("S1", 480, 600, 2), StaffingSegment("S2", 600, 720, 2)]),
    # A crew that only grows: B joins at 10:00, where the anonymous schedule goes from 1 to 2 servers.
    "growing_crew": ([shift("A", 480, 720), shift("B", 600, 720)],
                     [StaffingSegment("S1", 480, 600, 1), StaffingSegment("S2", 600, 720, 2)]),
}
_COMPARED = ("customer_id", "arrival_hours", "unit_work", "arrival_segment_id", "service_start_hours",
             "service_end_hours", "wait_hours", "elapsed_wait_at_close_hours", "status", "unserved_reason")


@pytest.mark.parametrize("case", sorted(REDUCTIONS))
@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
@pytest.mark.parametrize("grid", [False, True])
def test_reduction_to_the_anonymous_engine(case, policy, grid):
    # Where the roster is equivalent to the anonymous schedule (no breaks; the crew never shrinks before
    # closing), every customer's outcome is identical: the same starts, ends, waits, and closing results. Which
    # employee or server serves may differ (X1 versus lowest server id), so identities are not compared. The
    # grid variant makes ties between arrivals and completions frequent.
    roster, segments = REDUCTIONS[case]
    for seed in range(12):
        arrivals = _generated_arrivals(seed, TWO_PERIODS, grid)
        named = simulate(roster, rules(registers=2), arrivals, policy=policy, required=segments, periods=TWO_PERIODS,
                         exact=False)
        anonymous = shared_continuous_des.simulate_prescribed(HORIZON, TWO_PERIODS, segments, arrivals,
                                                              closing_policy=policy)
        reason = {"no_eligible_server": NO_ELIGIBLE_EMPLOYEE}
        expected = [{key: reason.get(row[key], row[key]) if key == "unserved_reason" else row[key] for key in _COMPARED}
                    for row in anonymous["customers"]]
        assert [{key: row[key] for key in _COMPARED} for row in named["customers"]] == expected, seed
        assert len(arrivals) > 20


# ── Inputs, policy, and isolation ───────────────────────────────────────────


def _run(**overrides: Any) -> dict:
    arguments: dict[str, Any] = {
        "horizon": HORIZON, "demand_periods": PERIODS, "employees": staff([shift("A", 480, 720)]),
        "rules": rules(registers=1), "roster": [shift("A", 480, 720)], "arrivals": [(1.0, 1.0)],
        "closing_policy": DRAIN, "employee_policy": APPROVED_EMPLOYEE_POLICY, "required_staffing": ONE_REQUIRED,
    }
    arguments.update(overrides)
    return simulate_named_prescribed(**arguments)


@pytest.mark.parametrize("value", [[], None, (), ["S"]])
def test_required_staffing_is_mandatory(value):
    with pytest.raises(SharedSegmentError, match="X7"):
        _run(required_staffing=value)


def test_required_staffing_has_no_default():
    with pytest.raises(TypeError):
        simulate_named_prescribed(HORIZON, PERIODS, staff([shift("A", 480, 720)]), rules(registers=1),  # type: ignore[call-arg]
                                  [shift("A", 480, 720)], [], closing_policy=DRAIN,
                                  employee_policy=APPROVED_EMPLOYEE_POLICY)


def test_required_staffing_is_validated_against_the_horizon():
    with pytest.raises(SharedSegmentError, match="horizon end"):
        _run(required_staffing=[StaffingSegment("S", 480, 600, 1)])


@pytest.mark.parametrize("field", [item.name for item in dataclasses.fields(APPROVED_EMPLOYEE_POLICY)])
def test_only_the_approved_policy_selections_run(field):
    with pytest.raises(SharedSegmentError, match=f"employee_policy.{field}"):
        _run(employee_policy=dataclasses.replace(APPROVED_EMPLOYEE_POLICY, **{field: "other"}))


@pytest.mark.parametrize("policy", [None, "drain", "NONE"])
def test_closing_policy_is_required(policy):
    with pytest.raises(SharedSegmentError, match="closing_policy"):
        _run(closing_policy=policy)


@pytest.mark.parametrize(("arrivals", "message"), [
    ([(4.0, 1.0)], "horizon"),
    ([(2.0, 1.0), (1.0, 1.0)], "earlier"),
    ([(1.0, 0.0)], "work"),
    ([(1.0,)], "pair"),
])
def test_arrivals_are_validated_like_the_anonymous_engine(arrivals, message):
    with pytest.raises(SharedSegmentError, match=message):
        _run(arrivals=arrivals)


def test_arrival_in_a_zero_rate_period_is_rejected():
    periods = [DemandPeriod("P1", 480, 600, 10.0, 4.0), DemandPeriod("P2", 600, 720, 0.0, 4.0)]
    with pytest.raises(SharedSegmentError, match="arrival rate is 0"):
        _run(demand_periods=periods, arrivals=[(2.5, 1.0)],
             required_staffing=[StaffingSegment("S1", 480, 600, 1), StaffingSegment("S2", 600, 720, 1)])


def test_x4_rejects_an_invalid_roster():
    roster = [shift("A", 480, 600), shift("A", 540, 720)]  # overlapping shifts
    with pytest.raises(SharedSegmentError, match="INVALID"):
        _run(roster=roster, employees=staff(roster))


def test_x4_rejects_operational_incompleteness_and_accepts_missing_pay():
    # A break_rules gap (shift lengths 121-480 have no rule) is not a pay field: rejected.
    with pytest.raises(SharedSegmentError, match="INCOMPLETE beyond pay"):
        _run(rules=rules(BreakRule(15, 120, 0, ()), registers=1), roster=[shift("A", 480, 540)],
             employees=staff([shift("A", 480, 540)]), arrivals=[(0.5, 1.0)])
    # Missing pay only (every employee here has EmployeePay(None, None, None)): the run proceeds.
    assert staff([shift("A", 480, 720)])[0].pay == EmployeePay(None, None, None)
    assert _run()["counts"]["departed"] == 1


def test_trace_is_truncated_at_max_trace_events():
    full = _run(arrivals=[(1.0, 1.0), (2.0, 1.0)])
    assert [row["type"] for row in full["trace"]] == [
        "arrival", "service_start", "service_end", "arrival", "service_start", "service_end", "closing"]
    assert full["trace_truncated"] is False
    short = _run(arrivals=[(1.0, 1.0), (2.0, 1.0)], max_trace_events=3)
    assert short["trace"] == full["trace"][:3] and short["trace_truncated"] is True


def test_time_conversion_is_the_anonymous_engines():
    for minute in (480, 495, 505, 600, 719, 720, 780):
        assert shared_named_des._hours(minute, HORIZON) == shared_continuous_des._hours(minute, HORIZON)


def test_no_random_numbers_and_no_separate_queue_code():
    tree = ast.parse(Path(shared_named_des.__file__).read_text(encoding="utf-8"))
    imported, names, texts = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            texts.add(node.value)
    assert not any(name == "random" or "numpy" in name or "separate" in name or "queue_lifecycle" in name
                   or "break_optimization" in name for name in imported)
    assert not names & {"PRE_BREAK_CUTOFF_MINUTES", "begin_draining", "begin_break", "end_break", "random"}
    # No separate-queue event name is used as a value (the docstring may name them).
    assert not texts & {"draining_start", "break_start", "break_end"}


def test_module_is_registered_with_the_isolation_test():
    from tests.test_shared_segments import SHARED_QUEUE_ENHANCEMENT_MODULES

    assert "shared_named_des.py" in SHARED_QUEUE_ENHANCEMENT_MODULES


def test_scope_and_provenance():
    result = _run()
    assert result["provenance"]["engine_version"] == shared_named_des.NAMED_ENGINE_VERSION
    assert result["policy"]["selections"] == dataclasses.asdict(APPROVED_EMPLOYEE_POLICY)
    assert "no random numbers" in result["provenance"]["arrivals"]
    assert not any("cost" in key for key in result)
