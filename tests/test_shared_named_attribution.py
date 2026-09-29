"""Phase 5B-4.6 attribution of one named-employee shared-queue DES result.

ALL EMPLOYEES, AVAILABILITY, RULES, ROSTERS, DEMAND, ARRIVALS, AND SERVICE WORK IN THIS FILE ARE SYNTHETIC TEST
DATA. They are not NovaMart records, labor law, or recommended operating values.

The hand cases use the Phase 5B-4.3 days: horizon 08:00-12:00 (hours 0-4), closing 4.0, service rate 4 per hour
(service time = work / 4), and binary-exact times. Each expected value below is derived by hand from the scenario's
definition and the approved rules (P1-P9, X1-X7, and the 5B-4.4 closing rules); the derivation is in the comments.
The engine runs through tests.test_shared_named_des.simulate, which also applies the independent 5B-4.3 checker.

Seeded tests assert identities only; no seeded value is compared with a stored golden value (numpy stream equality
across versions is UNKNOWN). Malformed inputs are deep-copy edits of an engine result; the engine is never changed.
"""

from __future__ import annotations

import ast
import copy
import math
import random
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from backend.queueing_engine.services.shared_workforce import AvailabilityWindow, BreakRule, Employee, EmployeePay
from backend.queueing_engine.simulation import shared_named_attribution, shared_named_playback
from backend.queueing_engine.simulation.shared_employee_states import (
    AVAILABLE,
    BASE_STATES,
    OFF,
    ON_BREAK,
    SERVING,
    SERVING_BREAK_DUE,
    SERVING_SHIFT_ENDED,
    STATE_MACHINE_VERSION,
    WAITING_FOR_REGISTER,
)
from backend.queueing_engine.simulation.shared_named_attribution import (
    ATTRIBUTION_VERSION,
    CHECKS,
    NamedAttributionError,
    build_named_attribution,
    derived_duration,
)
from backend.queueing_engine.simulation.shared_named_des import (
    APPROVED_EMPLOYEE_POLICY,
    NAMED_ENGINE_VERSION,
    simulate_named_prescribed,
)
from backend.queueing_engine.simulation.shared_named_replications import (
    named_replication_row,
    replication_seed_sequence,
)
from tests.test_shared_employee_states import HORIZON, break_rule, rules, shift, staff
from tests.test_shared_named_des import (
    CLOSING_ARRIVALS,
    CLOSING_ROSTER,
    CLOSING_RULES,
    LONG_SHIFT_BREAK,
    ONE_REQUIRED,
    PERIODS,
    REQUIRED_TWO,
    simulate,
)
from tests.test_shared_named_replications import SCENARIOS, regenerate, replicate

# ── SYNTHETIC TEST DATA ──────────────────────────────────────────────────────

DRAIN, HARD_CUTOFF = "DRAIN", "HARD_CUTOFF"
ON_DUTY = tuple(state for state in BASE_STATES if state != OFF)
SPLIT_RULES = rules(BreakRule(15, 60, 0, ()), break_rule(61, 480, rest=15), registers=1, max_shifts=2, rest=30)
SPLIT_ROSTER = [shift("A", 480, 540), shift("A", 570, 690, rest=600)]  # 08:00-09:00, 09:30-11:30 (break 10:00)
CELLS = ("after_closing_hours", "past_scheduled_end_hours", "after_closing_and_past_scheduled_end_hours",
         "after_closing_only_hours", "past_scheduled_end_only_hours", "neither_hours",
         "after_closing_or_past_scheduled_end_hours")


def attribute(roster: list, workforce: Any, arrivals: list, *, policy: str = DRAIN,
              required: list | None = None) -> tuple[dict, dict]:
    result = simulate(roster, workforce, arrivals, policy=policy, required=required)
    return result, build_named_attribution(result, staff(roster))


def shift_of(out: dict, employee_id: str, shift_index: int) -> dict:
    (row,) = [row for row in out["shifts"] if (row["employee_id"], row["shift_index"]) == (employee_id, shift_index)]
    return row


def employee_of(out: dict, employee_id: str) -> dict:
    (row,) = [row for row in out["employees"] if row["employee_id"] == employee_id]
    return row


def cells(ac: float, pe: float, both: float, ac_only: float, pe_only: float, neither: float) -> dict[str, float]:
    return {"after_closing_hours": ac, "past_scheduled_end_hours": pe,
            "after_closing_and_past_scheduled_end_hours": both, "after_closing_only_hours": ac_only,
            "past_scheduled_end_only_hours": pe_only, "neither_hours": neither,
            "after_closing_or_past_scheduled_end_hours": ac + pe - both}


def states(**hours: float) -> dict[str, float]:
    return {state: hours.get(state, 0.0) for state in ON_DUTY}


def fails(result: Any, employees: Any, check: str, match: str | None = None) -> dict:
    with pytest.raises(NamedAttributionError) as info:
        build_named_attribution(result, employees)
    assert info.value.failure["check"] == check, info.value.failure
    if match is not None:
        assert match in info.value.failure["message"], info.value.failure
    return info.value.failure


def closing_day(policy: str = DRAIN) -> tuple[dict, list[Employee]]:
    return simulate(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, policy=policy, required=REQUIRED_TWO), staff(
        CLOSING_ROSTER)


def interval(result: dict, employee_id: str, predicate: Any) -> dict:
    return next(row for row in result["employee_timeline"]["intervals"]
                if row["employee_id"] == employee_id and predicate(row))


def break_of(result: dict, employee_id: str) -> dict:
    return next(row for row in result["employee_timeline"]["breaks"] if row["employee_id"] == employee_id)


def shift_record(result: dict, employee_id: str, shift_index: int) -> dict:
    return next(row for row in result["employee_timeline"]["shifts"]
                if (row["employee_id"], row["shift_index"]) == (employee_id, shift_index))


# ── Hand cases H1-H8 (spec, section 6) ──────────────────────────────────────


def test_h1_drain_closing_both_attributes_truncated_break_and_unactivated_shift():
    # CLOSING_ROSTER: A 08:00-12:00 (shift 0, 30-minute break 08:30 = 0.5 h), B 08:00-12:00 (shift 1, break 11:30 =
    # 3.5 h), C 12:00-13:00 (shift 2, no break for 60 minutes); three registers. Service times: 0.5, 0.5, 0.5, 0.25,
    # 0.25. A is idle at 0.5, so its break runs 0.5-1.0 on time. #1 (3.25) goes to B (idle since 0.0, X1) 3.25-3.75;
    # #2 (3.375) to A 3.375-3.875. B's break falls due at 3.5 while serving and starts at the completion, 3.75. #3 and
    # #4 wait; A takes #3 at 3.875-4.375. At closing (4.0, also A's and B's scheduled end) A is serving: DRAIN crew.
    # B is on its break: truncated at 4.0 and released. C starts at closing: not activated. A serves #4 4.375-4.625
    # and #5 4.625-4.875, then is released at 4.875; the timeline finishes at 4.875.
    result, out = attribute(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, required=REQUIRED_TWO)
    a, b, c = shift_of(out, "A", 0), shift_of(out, "B", 1), shift_of(out, "C", 2)
    # A: on duty 0.0-4.875; on the break 0.5; serving 3.375-4.875 = 1.5; available 0-0.5 and 1.0-3.375 = 2.875.
    # After closing and past the 4.0 scheduled end: 4.0-4.875 = 0.875, both attributes at once.
    assert (a["actual_start_hours"], a["release_hours"], a["on_duty_hours"], a["overrun_hours"]) == (0.0, 4.875, 4.875,
                                                                                                    0.875)
    assert a["hours_by_state"] == states(AVAILABLE=2.875, SERVING=1.5, ON_BREAK=0.5)
    assert a["closing_attribution"] == cells(ac=0.875, pe=0.875, both=0.875, ac_only=0.0, pe_only=0.0, neither=4.0)
    (a_break,) = a["breaks"]
    assert (a_break["delay_from_scheduled_hours"], a_break["delay_from_due_hours"], a_break["actual_hours"],
            a_break["shortened_hours"], a_break["unfulfilled_hours"], a_break["outcome"]) == (
        0.0, 0.0, 0.5, 0.0, 0.0, "completed")
    # B: on duty 0.0-4.0: available 0-3.25, serving 3.25-3.5, serving with the break due 3.5-3.75, on the break
    # 3.75-4.0. Released exactly at its scheduled end: overrun 0, no after-closing time.
    assert (b["on_duty_hours"], b["overrun_hours"]) == (4.0, 0.0)
    assert b["hours_by_state"] == states(AVAILABLE=3.25, SERVING=0.25, SERVING_BREAK_DUE=0.25, ON_BREAK=0.25)
    assert b["closing_attribution"] == cells(ac=0.0, pe=0.0, both=0.0, ac_only=0.0, pe_only=0.0, neither=4.0)
    (b_break,) = b["breaks"]
    # Scheduled and due 3.5, started 3.75: both delays 0.25. Configured 30 minutes = 0.5 h, taken 0.25 h.
    assert (b_break["scheduled_start_hours"], b_break["due_hours"], b_break["actual_start_hours"],
            b_break["actual_end_hours"]) == (3.5, 3.5, 3.75, 4.0)
    assert (b_break["delay_from_scheduled_hours"], b_break["delay_from_due_hours"], b_break["configured_minutes"],
            b_break["configured_hours"], b_break["actual_hours"], b_break["shortened_hours"],
            b_break["unfulfilled_hours"], b_break["outcome"]) == (0.25, 0.25, 30, 0.5, 0.25, 0.25, 0.0,
                                                                  "truncated_by_closing")
    assert b["break_totals"] == {
        "breaks_scheduled": 1, "breaks_completed": 0, "breaks_truncated_by_closing": 1,
        "breaks_unfulfilled_by_cause": {"released": 0, "shift_not_activated": 0, "cancelled_at_closing": 0},
        "delay_from_scheduled_hours_total": 0.25, "delay_from_due_hours_total": 0.25, "actual_break_hours_total": 0.25,
        "shortened_hours_total": 0.25, "unfulfilled_hours_total": 0.0}
    assert a["break_totals"]["breaks_completed"] == 1 and a["break_totals"]["breaks_truncated_by_closing"] == 0
    # C: never activated; every duration None, not zero.
    assert (c["activated"], c["not_activated_reason"]) == (False, "released_after_closing")
    assert all(c[field] is None for field in ("actual_start_hours", "release_hours", "activation_delay_hours",
                                              "overrun_hours", "on_duty_hours", "hours_by_state",
                                              "register_wait_hours", "closing_attribution"))
    assert (c["scheduled_duration_hours"], c["breaks"]) == (1.0, [])
    # Employee summaries: OFF time is the rest of 0-4.875.
    assert (employee_of(out, "A")["off_hours"], employee_of(out, "B")["off_hours"],
            employee_of(out, "C")["off_hours"]) == (0.0, 0.875, 4.875)
    # Employee sums run over activated shifts only: C's unactivated 1.0-hour shift adds nothing.
    assert employee_of(out, "C")["activated_shift_count"] == 0 and employee_of(out, "C")["on_duty_hours"] == 0.0
    assert employee_of(out, "C")["scheduled_duration_hours"] == 0.0
    assert employee_of(out, "A")["scheduled_duration_hours"] == 4.0
    assert result["finish"] == 4.875


def test_h1b_hard_cutoff_closing():
    # As H1 under HARD_CUTOFF: #4 and #5 are unserved; A, serving #3 at closing, gets Release and becomes
    # SERVING_SHIFT_ENDED; it is released at #3's completion, 4.375. B as in H1.
    _, out = attribute(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, policy=HARD_CUTOFF, required=REQUIRED_TWO)
    a, b = shift_of(out, "A", 0), shift_of(out, "B", 1)
    assert (a["release_hours"], a["on_duty_hours"], a["overrun_hours"]) == (4.375, 4.375, 0.375)
    assert a["hours_by_state"] == states(AVAILABLE=2.875, SERVING=0.625, SERVING_SHIFT_ENDED=0.375, ON_BREAK=0.5)
    assert a["closing_attribution"] == cells(ac=0.375, pe=0.375, both=0.375, ac_only=0.0, pe_only=0.0, neither=4.0)
    assert b["breaks"][0]["shortened_hours"] == 0.25 and b["overrun_hours"] == 0.0


def test_h2_shift_end_during_service_is_past_end_only():
    # A 08:00-10:00 (0-2), B 10:00-12:00 (2-4), two registers, no breaks. #1 (1.75, work 2) is served by A 1.75-2.25:
    # A's shift ends at 2.0 during the service, so 2.0-2.25 is past its scheduled end but before closing.
    # B: #2 (2.0) 2.0-2.5, #3 (2.125, work 0.5) 2.5-2.625; idle at closing with nobody waiting, released at 4.0.
    _, out = attribute([shift("A", 480, 600), shift("B", 600, 720)], rules(registers=2),
                       [(1.75, 2.0), (2.0, 2.0), (2.125, 0.5)])
    a, b = shift_of(out, "A", 0), shift_of(out, "B", 1)
    assert (a["on_duty_hours"], a["overrun_hours"]) == (2.25, 0.25)
    assert a["hours_by_state"] == states(AVAILABLE=1.75, SERVING=0.25, SERVING_SHIFT_ENDED=0.25)
    assert a["closing_attribution"] == cells(ac=0.0, pe=0.25, both=0.0, ac_only=0.0, pe_only=0.25, neither=2.0)
    assert (b["actual_start_hours"], b["activation_delay_hours"], b["on_duty_hours"], b["overrun_hours"]) == (
        2.0, 0.0, 2.0, 0.0)
    assert b["register_wait_hours"] == 0.0
    assert b["closing_attribution"] == cells(ac=0.0, pe=0.0, both=0.0, ac_only=0.0, pe_only=0.0, neither=2.0)


def test_h3_register_wait_is_attributed_to_the_waiting_shift():
    # As H2 with one register: A holds register 1 until its release at 2.25, so B (shift 1) waits 2.0-2.25 for it
    # (P4). #2 (2.125, work 1) is served by B 2.25-2.5; B is idle until its release at closing.
    _, out = attribute([shift("A", 480, 600), shift("B", 600, 720)], rules(registers=1), [(1.75, 2.0), (2.125, 1.0)])
    a, b = shift_of(out, "A", 0), shift_of(out, "B", 1)
    assert b["register_wait_hours"] == 0.25
    assert b["hours_by_state"] == states(WAITING_FOR_REGISTER=0.25, SERVING=0.25, AVAILABLE=1.5)
    assert a["register_wait_hours"] == 0.0 and a["closing_attribution"]["past_scheduled_end_only_hours"] == 0.25
    assert employee_of(out, "B")["register_wait_hours"] == 0.25


def test_h4_delayed_split_shift_separates_the_two_delays():
    # A: shift 0 08:00-09:00 (0-1), shift 1 09:30-11:30 (1.5-3.5, 15-minute break at 10:00 = 2.0, offset 0.5), rest
    # 30 minutes, one register. #1 (0.5, work 4.5) is served 0.5-1.625, past shift 0's end at 1.0: overrun 0.625.
    # Shift 1 activates at max(1.5, 1.625 + 0.5) = 2.125 (activation delay 0.625); #2 (1.75) waits and is served
    # 2.125-2.375. The break falls due at 2.125 + 0.5 = 2.625 (P3) while A is idle, so it runs 2.625-2.875: 0.625 after
    # its scheduled 2.0, all from the late activation, and 0.0 after it fell due. #3 (2.75) is served 2.875-3.0;
    # released idle at the 3.5 scheduled end.
    _, out = attribute(SPLIT_ROSTER, SPLIT_RULES, [(0.5, 4.5), (1.75, 1.0), (2.75, 0.5)])
    first, second = shift_of(out, "A", 0), shift_of(out, "A", 1)
    assert (first["on_duty_hours"], first["overrun_hours"]) == (1.625, 0.625)
    assert first["closing_attribution"] == cells(ac=0.0, pe=0.625, both=0.0, ac_only=0.0, pe_only=0.625, neither=1.0)
    assert (second["actual_start_hours"], second["activation_delay_hours"], second["on_duty_hours"],
            second["overrun_hours"]) == (2.125, 0.625, 1.375, 0.0)
    assert second["hours_by_state"] == states(AVAILABLE=0.75, SERVING=0.375, ON_BREAK=0.25)
    (item,) = second["breaks"]
    assert (item["scheduled_start_hours"], item["due_hours"], item["actual_start_hours"], item["actual_end_hours"]) == (
        2.0, 2.625, 2.625, 2.875)
    assert (item["delay_from_scheduled_hours"], item["delay_from_due_hours"]) == (0.625, 0.0)
    employee = employee_of(out, "A")
    # Sums over the two activated shifts; OFF between the shifts (1.625-2.125) and after 3.5 until closing.
    assert (employee["on_duty_hours"], employee["overrun_hours"], employee["activation_delay_hours"],
            employee["off_hours"]) == (3.0, 0.625, 0.625, 1.0)
    assert (employee["break_totals"]["delay_from_scheduled_hours_total"],
            employee["break_totals"]["delay_from_due_hours_total"]) == (0.625, 0.0)


@pytest.mark.parametrize("policy", [HARD_CUTOFF, DRAIN])
def test_h5_after_closing_but_not_past_the_shift_end(policy):
    # A 08:00-13:00 (0-5), one register, no breaks. #1 (3.75, work 2) is served 3.75-4.25. Under HARD_CUTOFF A gets
    # Release at closing and is released at the completion; under DRAIN A is the crew and is released idle at 4.25.
    # Either way 4.0-4.25 is after closing but before A's 5.0 scheduled end.
    _, out = attribute([shift("A", 480, 780)], rules(registers=1), [(3.75, 2.0)], policy=policy)
    a = shift_of(out, "A", 0)
    assert (a["release_hours"], a["on_duty_hours"], a["overrun_hours"], a["scheduled_duration_hours"]) == (
        4.25, 4.25, 0.0, 5.0)
    assert a["closing_attribution"] == cells(ac=0.25, pe=0.0, both=0.0, ac_only=0.25, pe_only=0.0, neither=4.0)


def test_h6_break_carried_past_the_shift_end():
    # A 08:00-10:30 (0-2.5) with a 30-minute break at 10:00 (2.0), one register. #1 (1.75, work 2) is served
    # 1.75-2.25; the break falls due at 2.0 while serving and runs 2.25-2.75 at full length (P1). The shift ends at
    # 2.5 during the break; A is released at the break end, 2.75: overrun 0.25, spent ON_BREAK, before closing.
    _, out = attribute([shift("A", 480, 630, rest=600)], rules(*LONG_SHIFT_BREAK, registers=1), [(1.75, 2.0)])
    a = shift_of(out, "A", 0)
    assert (a["on_duty_hours"], a["overrun_hours"]) == (2.75, 0.25)
    assert a["hours_by_state"] == states(AVAILABLE=1.75, SERVING=0.25, SERVING_BREAK_DUE=0.25, ON_BREAK=0.5)
    assert a["closing_attribution"] == cells(ac=0.0, pe=0.25, both=0.0, ac_only=0.0, pe_only=0.25, neither=2.5)
    (item,) = a["breaks"]
    assert (item["due_hours"], item["delay_from_scheduled_hours"], item["delay_from_due_hours"], item["actual_hours"],
            item["shortened_hours"], item["outcome"]) == (2.0, 0.25, 0.25, 0.5, 0.0, "completed")


def test_h7_break_unfulfilled_at_release():
    # As H6 with #1 of work 4: served 1.75-2.75. The break falls due at 2.0 while serving; the shift ends at 2.5, so
    # A becomes SERVING_SHIFT_ENDED and is released at the completion, 2.75, without the break (unfulfilled,
    # released). The break's 30 minutes are reported as unfulfilled_hours 0.5; it has no delay.
    _, out = attribute([shift("A", 480, 630, rest=600)], rules(*LONG_SHIFT_BREAK, registers=1), [(1.75, 4.0)])
    a = shift_of(out, "A", 0)
    assert (a["overrun_hours"], a["closing_attribution"]["past_scheduled_end_only_hours"]) == (0.25, 0.25)
    assert a["hours_by_state"] == states(AVAILABLE=1.75, SERVING=0.25, SERVING_BREAK_DUE=0.5, SERVING_SHIFT_ENDED=0.25)
    (item,) = a["breaks"]
    assert (item["outcome"], item["unfulfilled_cause"], item["due_hours"], item["unfulfilled_hours"]) == (
        "unfulfilled", "released", 2.0, 0.5)
    assert all(item[field] is None for field in ("actual_start_hours", "actual_end_hours", "delay_from_scheduled_hours",
                                                 "delay_from_due_hours", "actual_hours", "shortened_hours"))
    assert a["break_totals"]["breaks_unfulfilled_by_cause"] == {"released": 1, "shift_not_activated": 0,
                                                               "cancelled_at_closing": 0}
    assert a["break_totals"]["unfulfilled_hours_total"] == 0.5


def test_h8_split_shift_not_activated():
    # The H4 roster with #1 (0.5, work 10): served 0.5-3.0, so shift 0 overruns its 1.0 end by 2.0. Shift 1 could
    # activate at max(1.5, 3.0 + 0.5) = 3.5, its fixed scheduled end: not activated. Its 15-minute break is
    # unfulfilled (shift_not_activated), never due.
    _, out = attribute(SPLIT_ROSTER, SPLIT_RULES, [(0.5, 10.0)])
    first, second = shift_of(out, "A", 0), shift_of(out, "A", 1)
    assert (first["release_hours"], first["overrun_hours"], first["closing_attribution"]["past_scheduled_end_hours"]) == (
        3.0, 2.0, 2.0)
    assert (second["activated"], second["not_activated_reason"], second["on_duty_hours"]) == (
        False, "rest_after_actual_release_reaches_scheduled_end", None)
    (item,) = second["breaks"]
    assert (item["outcome"], item["unfulfilled_cause"], item["due_hours"], item["unfulfilled_hours"]) == (
        "unfulfilled", "shift_not_activated", None, 0.25)
    assert second["break_totals"]["unfulfilled_hours_total"] == 0.25
    assert employee_of(out, "A")["activated_shift_count"] == 1


# ── Further situations (spec, section 7) ────────────────────────────────────


def test_quiet_single_shift_reports_zeros_not_none():
    # A 08:00-12:00, no break, no customer: available 0-4, released idle at closing (also its scheduled end). Every
    # closing cell is an established 0.0 except neither (4.0); nothing is None on an activated shift.
    _, out = attribute([shift("A", 480, 720)], rules(registers=1), [])
    a = shift_of(out, "A", 0)
    assert a["closing_attribution"] == cells(ac=0.0, pe=0.0, both=0.0, ac_only=0.0, pe_only=0.0, neither=4.0)
    assert (a["overrun_hours"], a["register_wait_hours"], a["activation_delay_hours"]) == (0.0, 0.0, 0.0)
    assert a["hours_by_state"] == states(AVAILABLE=4.0)
    assert a["breaks"] == [] and a["break_totals"]["breaks_scheduled"] == 0


def test_pending_break_at_closing_is_cancelled():
    # A 08:00-13:00 (0-5) with a 30-minute break at 12:30 (4.5), after closing; no customer. At closing A is idle:
    # the pending break is cancelled (P7, cancelled_at_closing) and A is released at 4.0, before its 5.0 end.
    for policy in (DRAIN, HARD_CUTOFF):
        _, out = attribute([shift("A", 480, 780, rest=750)], rules(*LONG_SHIFT_BREAK, registers=1), [], policy=policy)
        a = shift_of(out, "A", 0)
        (item,) = a["breaks"]
        assert (item["outcome"], item["unfulfilled_cause"], item["due_hours"], item["unfulfilled_hours"]) == (
            "unfulfilled", "cancelled_at_closing", None, 0.5)
        assert (a["release_hours"], a["overrun_hours"], a["closing_attribution"]["after_closing_hours"]) == (
            4.0, 0.0, 0.0)


def test_break_ending_exactly_at_closing_is_truncated_with_zero_shortening():
    # A 08:00-12:00 with a 30-minute break at 11:30 (3.5), no customer: the break runs 3.5-4.0 and is in progress at
    # closing, which comes before break ends (approved 5B-4.4 rule 2): truncated_by_closing, 0.5 of 0.5 taken.
    _, out = attribute([shift("A", 480, 720, rest=690)], rules(*LONG_SHIFT_BREAK, registers=1), [])
    (item,) = shift_of(out, "A", 0)["breaks"]
    assert (item["outcome"], item["actual_hours"], item["shortened_hours"], item["delay_from_scheduled_hours"]) == (
        "truncated_by_closing", 0.5, 0.0, 0.0)


def test_unrostered_employee_has_no_shift_and_a_zero_summary():
    roster = [shift("A", 480, 720)]
    employees = [*staff(roster), Employee("Z", (AvailabilityWindow(0, 1440),), EmployeePay(None, None, None))]
    result = simulate_named_prescribed(HORIZON, PERIODS, employees, rules(registers=1), roster, [],
                                       closing_policy=DRAIN, employee_policy=APPROVED_EMPLOYEE_POLICY,
                                       required_staffing=ONE_REQUIRED)
    out = build_named_attribution(result, employees)
    assert [row["employee_id"] for row in out["shifts"]] == ["A"]
    z = employee_of(out, "Z")
    assert (z["shift_count"], z["activated_shift_count"]) == (0, 0)
    assert all(z[field] == 0.0 for field in shared_named_attribution.SHIFT_SUM_FIELDS)
    assert z["closing_attribution"] == dict.fromkeys(CELLS, 0.0)
    assert z["off_hours"] == result["finish"] - result["begin"] == 4.0


def test_zero_attribution_day_seeded():
    # SCENARIOS["zero_arrivals"]: no demand; A 08:00-12:00 with a break at 09:00 taken on time; released at closing.
    for policy in (DRAIN, HARD_CUTOFF):
        for index in range(3):
            result = regenerate("zero_arrivals", 11, index, policy)
            out = build_named_attribution(result, staff(SCENARIOS["zero_arrivals"][1]))
            a = shift_of(out, "A", 0)
            assert (a["overrun_hours"], a["register_wait_hours"]) == (0.0, 0.0)
            assert a["closing_attribution"] == cells(ac=0.0, pe=0.0, both=0.0, ac_only=0.0, pe_only=0.0, neither=4.0)
            assert a["breaks"][0]["delay_from_scheduled_hours"] == 0.0


# ── Reconciliation on seeded runs (spec, section 5) ─────────────────────────


def _independent_cells(result: dict, employee_id: str, shift_index: int) -> dict[str, float]:
    rows = [row for row in result["employee_timeline"]["intervals"]
            if row["employee_id"] == employee_id and row["shift_index"] == shift_index]

    def total(keep: Any) -> float:
        return math.fsum(row["end"] - row["start"] for row in rows if keep(row["after_closing"], row["past_scheduled_end"]))

    return {"after_closing_hours": total(lambda ac, pe: ac), "past_scheduled_end_hours": total(lambda ac, pe: pe),
            "after_closing_and_past_scheduled_end_hours": total(lambda ac, pe: ac and pe),
            "after_closing_only_hours": total(lambda ac, pe: ac and not pe),
            "past_scheduled_end_only_hours": total(lambda ac, pe: pe and not ac),
            "neither_hours": total(lambda ac, pe: not ac and not pe),
            "after_closing_or_past_scheduled_end_hours": total(lambda ac, pe: ac or pe)}


def near(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_identities_hold_on_seeded_runs(name, policy):
    roster = SCENARIOS[name][1]
    for index in range(25):
        result = regenerate(name, 20260929, index, policy)
        out = build_named_attribution(result, staff(roster))
        timeline = result["employee_timeline"]
        activated = [row for row in out["shifts"] if row["activated"]]
        for row in activated:
            closing = row["closing_attribution"]
            assert closing == _independent_cells(result, row["employee_id"], row["shift_index"])
            assert near(math.fsum(closing[key] for key in ("neither_hours", "after_closing_only_hours",
                                                           "past_scheduled_end_only_hours",
                                                           "after_closing_and_past_scheduled_end_hours")),
                        row["on_duty_hours"])
            assert near(closing["after_closing_or_past_scheduled_end_hours"],
                        closing["after_closing_hours"] + closing["past_scheduled_end_hours"]
                        - closing["after_closing_and_past_scheduled_end_hours"])
            assert near(row["on_duty_hours"], row["release_hours"] - row["actual_start_hours"])
            assert near(closing["past_scheduled_end_hours"], row["overrun_hours"])
            assert near(math.fsum(row["hours_by_state"].values()), row["on_duty_hours"])
            assert near(row["hours_by_state"][ON_BREAK], row["break_totals"]["actual_break_hours_total"])
        for row in out["shifts"]:
            for item in row["breaks"]:
                # P1: a completed break reports exactly 0.0 shortening, even where configured - actual is +-2.2e-16.
                if item["outcome"] == "completed":
                    assert item["shortened_hours"] == 0.0 and near(item["actual_hours"], item["configured_hours"])
                elif item["outcome"] == "truncated_by_closing":
                    assert item["shortened_hours"] >= 0.0
        for employee_id in timeline["state_totals"]:
            mine = [row for row in activated if row["employee_id"] == employee_id]
            for state in ON_DUTY:
                assert near(math.fsum(row["hours_by_state"][state] for row in mine),
                            timeline["state_totals"][employee_id][state])
        # The unchanged 5B-4.4 replication row reconciles with the attribution.
        values = named_replication_row(result, index)["employees"]
        assert near(values["overrun_hours_total"], math.fsum(row["overrun_hours"] for row in activated))
        assert near(values["break_delay_hours_total"],
                    math.fsum(item["delay_from_scheduled_hours"] for row in out["shifts"] for item in row["breaks"]
                              if item["delay_from_scheduled_hours"] is not None))
        for state in ON_DUTY:
            assert near(values["employee_hours_by_state"][state],
                        math.fsum(row["hours_by_state"][state] for row in out["employees"]))
        assert near(math.fsum(values["employee_hours_after_closing_by_state"][state] for state in ON_DUTY),
                    math.fsum(row["closing_attribution"]["after_closing_hours"] for row in out["employees"]))
        # Per-employee sums are the fsum of the activated shift values.
        for employee in out["employees"]:
            mine = [row for row in activated if row["employee_id"] == employee["employee_id"]]
            assert employee["on_duty_hours"] == math.fsum(row["on_duty_hours"] for row in mine)
            assert employee["closing_attribution"] == {
                key: math.fsum(row["closing_attribution"][key] for row in mine) for key in CELLS}


# ── D7: derived durations ───────────────────────────────────────────────────


def test_d7_positive_and_tiny_positive_values_are_kept():
    assert derived_duration(0.75, 0.5, field="x") == 0.25
    tiny = derived_duration(math.nextafter(0.5, 1.0), 0.5, field="x")
    assert tiny > 0 and tiny == math.nextafter(0.5, 1.0) - 0.5  # reported as computed, not snapped to 0.0


def test_d7_exact_zero_is_positive_zero():
    for a, b in ((0.5, 0.5), (-0.0, 0.0)):
        value = derived_duration(a, b, field="x")
        assert value == 0.0 and math.copysign(1.0, value) == 1.0


def test_d7_tiny_negative_within_the_house_tolerance_is_zero():
    assert derived_duration(0.5, math.nextafter(0.5, 1.0), field="x") == 0.0
    assert derived_duration(4.0 - 2.220446049250313e-16 * 2, 4.0, field="x") == 0.0


def test_d7_boundary_follows_math_isclose():
    # The house tolerance is applied as math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12): |a - b| equal to the
    # absolute tolerance is still close (<=), so the value is 0.0; the next float beyond it fails.
    assert derived_duration(0.0, 1e-12, field="x") == 0.0
    with pytest.raises(NamedAttributionError) as info:
        derived_duration(0.0, math.nextafter(1e-12, 1.0), field="x")
    assert info.value.failure["check"] == "finite_nonnegative"


def test_d7_meaningful_negative_fails_with_evidence():
    with pytest.raises(NamedAttributionError) as info:
        derived_duration(0.5, 0.75, field="shortened_hours")
    failure = info.value.failure
    assert failure["check"] == "finite_nonnegative"
    # The spec's tolerance for the operands: max(1e-9 * max(|a|, |b|), 1e-12) = 1e-9 * 0.75.
    assert {key: failure["evidence"][key] for key in ("field", "a", "b", "x", "tolerance")} == {
        "field": "shortened_hours", "a": 0.5, "b": 0.75, "x": -0.25, "tolerance": 1e-9 * 0.75}


def test_d7_rejects_non_finite_results_and_operands():
    for a, b in ((1e308, -1e308), (math.inf, 0.0), (math.nan, 0.0), (True, 0.0)):
        with pytest.raises(NamedAttributionError) as info:
            derived_duration(a, b, field="x")
        assert info.value.failure["check"] == "finite_nonnegative"


def test_d7_tiny_negative_shortening_of_a_truncated_break_is_zero():
    # B's truncated break (H1) is made to start one float earlier than 3.75, so its actual length exceeds the
    # configured 15 minutes by about 4.4e-16 (duration_minutes set to 15 = 0.25 h). The delay stays consistent with
    # the source formula. The shortening is reported as 0.0; the source record is unchanged.
    result, employees = closing_day()
    item = break_of(result, "B")
    item["duration_minutes"] = 15
    item["actual_start"] = math.nextafter(3.75, 0.0)
    item["delay"] = item["actual_start"] - item["scheduled_start"]
    before = copy.deepcopy(result)
    out = build_named_attribution(result, employees)
    (row,) = shift_of(out, "B", 1)["breaks"]
    assert row["actual_hours"] > 0.25 and row["shortened_hours"] == 0.0
    assert result == before


def test_d7_negative_shortening_beyond_the_tolerance_fails():
    result, employees = closing_day()
    break_of(result, "B")["duration_minutes"] = 10  # configured 1/6 h, but 0.25 h was taken before closing
    failure = fails(result, employees, "finite_nonnegative")
    assert failure["evidence"]["field"] == "shortened_hours"


def test_d7_tiny_negative_delay_from_scheduled_is_zero_and_the_source_keeps_its_value():
    result, employees = closing_day()
    item = break_of(result, "B")
    item["scheduled_start"] = math.nextafter(3.75, 4.0)  # one float after the actual start 3.75
    item["delay"] = item["actual_start"] - item["scheduled_start"]
    source_delay = item["delay"]
    out = build_named_attribution(result, employees)
    assert source_delay < 0 and shift_of(out, "B", 1)["breaks"][0]["delay_from_scheduled_hours"] == 0.0
    assert break_of(result, "B")["delay"] == source_delay


def test_d7_negative_delay_from_scheduled_beyond_the_tolerance_fails():
    result, employees = closing_day()
    item = break_of(result, "B")
    item["scheduled_start"] = 3.875
    item["delay"] = item["actual_start"] - item["scheduled_start"]
    assert fails(result, employees, "finite_nonnegative")["evidence"]["field"] == "delay_from_scheduled_hours"


def test_d7_tiny_negative_scheduled_duration_is_zero():
    result, employees = closing_day()
    shift_record(result, "C", 2)["scheduled_end"] = math.nextafter(4.0, 0.0)  # one float before C's 4.0 start
    assert shift_of(build_named_attribution(result, employees), "C", 2)["scheduled_duration_hours"] == 0.0


def test_d7_negative_scheduled_duration_fails():
    result, employees = closing_day()
    shift_record(result, "C", 2)["scheduled_end"] = 3.0  # C never activated; start 4.0
    assert fails(result, employees, "finite_nonnegative")["evidence"]["field"] == "scheduled_duration_hours"


@pytest.mark.parametrize("edit, match", [
    # Each is an order violation of 1e-15 h or less, far inside the house tolerance; D7 forgives none of them.
    ("shift_starts_before_its_schedule", "starts before its scheduled start"),
    ("break_starts_before_it_is_due", "due <= actual_start < actual_end"),
    ("break_ends_at_its_start", "due <= actual_start < actual_end"),
])
def test_exact_order_violations_are_not_forgiven(edit, match):
    result, employees = closing_day()
    if edit == "shift_starts_before_its_schedule":
        row = shift_record(result, "B", 1)
        row["scheduled_start"] = 1e-15
        row["activation_delay"] = row["actual_start"] - row["scheduled_start"]
        check = "shift_reconciliation"
    elif edit == "break_starts_before_it_is_due":
        break_of(result, "B")["due"] = math.nextafter(3.75, 4.0)
        check = "break_reconciliation"
    else:
        item = break_of(result, "A")
        item["actual_end"] = item["actual_start"]
        check = "break_reconciliation"
    fails(result, employees, check, match)


# ── Malformed inputs ────────────────────────────────────────────────────────


class _EqualsAnything:
    """A version value that claims equality with anything: only the string test rejects it."""

    def __eq__(self, other: object) -> bool:
        return True

    __hash__ = None  # type: ignore[assignment]


def _edit(result: dict, change: str) -> None:
    timeline = result["employee_timeline"]
    if change == "orphan_interval":
        timeline["intervals"].append({**timeline["intervals"][-1], "employee_id": "Z"})
    elif change == "orphan_shift":
        timeline["shifts"].append({**shift_record(result, "C", 2), "employee_id": "Z"})
    elif change == "orphan_break":
        timeline["breaks"].append({**break_of(result, "A"), "employee_id": "Z"})
    elif change == "int_employee_id":
        timeline["intervals"][0]["employee_id"] = 7
    elif change == "unhashable_employee_id":
        timeline["intervals"][0]["employee_id"] = ["A"]
    elif change == "case_changed_employee_id":
        timeline["breaks"][0]["employee_id"] = "a"
    elif change == "duplicate_shift":
        timeline["shifts"].append(dict(shift_record(result, "A", 0)))
    elif change == "interval_unknown_shift":
        interval(result, "B", lambda row: row["shift_index"] == 1)["shift_index"] = 99
    elif change == "break_unknown_shift":
        break_of(result, "A")["shift_index"] = 99
    elif change == "duplicate_break_name":
        timeline["breaks"].append(dict(break_of(result, "A")))
    elif change == "off_interval_with_shift":
        interval(result, "C", lambda row: True)["shift_index"] = 2
    elif change == "on_duty_interval_without_shift":
        interval(result, "A", lambda row: row["state"] == ON_BREAK)["shift_index"] = None
    elif change == "gap":
        interval(result, "A", lambda row: True)["end"] += 0.125
    elif change == "flipped_after_closing":
        row = interval(result, "A", lambda row: row["after_closing"])
        row["after_closing"] = False
    elif change == "flipped_past_scheduled_end":
        row = interval(result, "A", lambda row: row["past_scheduled_end"])
        row["past_scheduled_end"] = False
    elif change == "interval_straddles_closing":
        # Merge A's last pre-closing interval with the first after-closing one (both SERVING).
        rows = [row for row in timeline["intervals"] if row["employee_id"] == "A"]
        position = next(i for i, row in enumerate(rows) if row["after_closing"])
        rows[position - 1]["end"] = rows[position]["end"]
        timeline["intervals"].remove(rows[position])
    elif change == "tampered_overrun":
        shift_record(result, "A", 0)["overrun"] = 0.75
    elif change == "tampered_activation_delay":
        shift_record(result, "B", 1)["activation_delay"] = 0.125
    elif change == "tampered_delay":
        break_of(result, "B")["delay"] = 0.5
    elif change == "activated_without_start":
        shift_record(result, "C", 2)["activated"] = True
    elif change == "unactivated_with_start":
        shift_record(result, "C", 2)["actual_start"] = 4.0
    elif change == "after_closing_flag_before_closing":
        interval(result, "A", lambda row: row["start"] == 3.875)["after_closing"] = True
    elif change == "past_end_flag_before_the_end":
        interval(result, "A", lambda row: row["start"] == 3.875)["past_scheduled_end"] = True
    elif change == "unactivated_with_release":
        shift_record(result, "C", 2)["release"] = 4.0
    elif change == "completed_break_wrong_length":
        item = break_of(result, "A")
        item["actual_end"] = 0.875
    elif change == "truncated_break_not_at_closing":
        break_of(result, "B")["actual_end"] = 3.875
    elif change == "unknown_outcome":
        break_of(result, "A")["outcome"] = "done"
    elif change == "unknown_cause":
        item = break_of(result, "B")
        item.update(outcome="unfulfilled", unfulfilled_cause="lost", actual_start=None, actual_end=None, delay=None)
    elif change == "started_unfulfilled":
        item = break_of(result, "A")
        item.update(outcome="unfulfilled", unfulfilled_cause="released")
    elif change == "unfulfilled_with_delay":
        item = break_of(result, "B")
        item.update(outcome="unfulfilled", unfulfilled_cause="released", actual_start=None, actual_end=None)
    elif change == "started_without_due":
        break_of(result, "A")["due"] = None
    elif change == "on_break_hours_mismatch":
        interval(result, "A", lambda row: row["state"] == AVAILABLE)["state"] = ON_BREAK
    elif change == "state_totals_moved":
        totals = timeline["state_totals"]["A"]
        totals[AVAILABLE] -= 0.125
        totals[OFF] += 0.125
    elif change == "state_totals_sum":
        timeline["state_totals"]["B"][OFF] += 0.125
    elif change == "negative_off_hours":
        timeline["state_totals"]["A"][OFF] = -1e-13  # A is on duty the whole timeline; its OFF time is 0
    elif change == "nan_time":
        timeline["intervals"][0]["start"] = math.nan
    elif change == "inf_schedule":
        shift_record(result, "A", 0)["scheduled_start"] = math.inf
    elif change == "bool_shift_index":
        timeline["intervals"][0]["shift_index"] = True
    elif change == "string_shift_index":
        timeline["shifts"][0]["shift_index"] = "0"
    elif change == "bool_break_shift_index":
        break_of(result, "A")["shift_index"] = False
    elif change == "string_state":
        timeline["intervals"][0]["state"] = "available"
    elif change == "flag_not_bool":
        timeline["intervals"][0]["after_closing"] = 0
    elif change == "missing_field":
        del timeline["intervals"][0]["past_scheduled_end"]
    elif change == "zero_minute_break":
        break_of(result, "A")["duration_minutes"] = 0
    elif change == "state_totals_missing_state":
        del timeline["state_totals"]["A"][SERVING_BREAK_DUE]
    elif change == "timeline_not_list":
        timeline["breaks"] = None
    elif change == "no_closing_policy":
        del result["closing_policy"]
    elif change == "version_equals_anything":
        result["provenance"]["engine_version"] = _EqualsAnything()
    elif change == "begin_not_finite":
        timeline["begin"] = math.nan
    elif change == "closing_time_text":
        timeline["closing_time"] = "4.0"
    elif change == "state_totals_list":
        timeline["state_totals"] = []
    elif change == "activated_not_bool":
        shift_record(result, "A", 0)["activated"] = 1
    elif change == "release_text":
        shift_record(result, "A", 0)["release"] = "4.875"
    elif change == "trigger_not_text":
        shift_record(result, "A", 0)["release_trigger"] = 5
    elif change == "break_name_not_text":
        break_of(result, "A")["name"] = 7
    elif change == "break_scheduled_nan":
        break_of(result, "A")["scheduled_start"] = math.nan
    elif change == "break_due_text":
        break_of(result, "A")["due"] = "0.5"
    elif change == "outcome_not_text":
        break_of(result, "A")["outcome"] = 3
    elif change == "cause_not_text":
        break_of(result, "B")["unfulfilled_cause"] = 3
    elif change == "zero_length_interval":
        first = interval(result, "A", lambda row: True)
        timeline["intervals"].insert(timeline["intervals"].index(first) + 1,
                                     {**first, "start": first["end"], "end": first["end"]})
    elif change == "off_interval_past_end":
        interval(result, "C", lambda row: True)["past_scheduled_end"] = True
    elif change == "intervals_stop_short":
        timeline["intervals"].remove([row for row in timeline["intervals"] if row["employee_id"] == "A"][-1])
    elif change == "activated_without_release":
        shift_record(result, "A", 0)["release"] = None
    elif change == "shift_starts_after_its_intervals":
        row = shift_record(result, "B", 1)
        row.update(actual_start=0.125, activation_delay=0.125)
    elif change == "shift_released_after_its_intervals":
        shift_record(result, "A", 0).update(release=5.0, overrun=1.0)
    elif change == "lowercase_policy":
        result["closing_policy"] = "drain"
    elif change == "old_engine":
        result["provenance"]["engine_version"] = "novaq-shared-named-des-v2"
    elif change == "old_state_machine":
        result["provenance"]["state_machine_version"] = "novaq-shared-employee-states-v2"
    elif change == "version_not_text":
        result["provenance"]["engine_version"] = ["novaq-shared-named-des-v3"]
    elif change == "no_provenance":
        del result["provenance"]
    else:
        raise AssertionError(change)


@pytest.mark.parametrize("change, check", [
    ("orphan_interval", "employee_identity"), ("orphan_shift", "employee_identity"),
    ("orphan_break", "employee_identity"), ("int_employee_id", "employee_identity"),
    ("unhashable_employee_id", "employee_identity"), ("case_changed_employee_id", "employee_identity"),
    ("duplicate_shift", "shift_identity"), ("interval_unknown_shift", "shift_identity"),
    ("break_unknown_shift", "shift_identity"), ("duplicate_break_name", "shift_identity"),
    ("off_interval_with_shift", "interval_geometry"), ("on_duty_interval_without_shift", "interval_geometry"),
    ("gap", "interval_geometry"), ("flipped_after_closing", "interval_geometry"),
    ("flipped_past_scheduled_end", "interval_geometry"), ("interval_straddles_closing", "interval_geometry"),
    ("after_closing_flag_before_closing", "interval_geometry"), ("past_end_flag_before_the_end", "interval_geometry"),
    ("tampered_overrun", "shift_reconciliation"), ("tampered_activation_delay", "shift_reconciliation"),
    ("activated_without_start", "shift_reconciliation"), ("unactivated_with_start", "shift_reconciliation"),
    ("unactivated_with_release", "shift_reconciliation"),
    ("tampered_delay", "break_reconciliation"), ("completed_break_wrong_length", "break_reconciliation"),
    ("truncated_break_not_at_closing", "break_reconciliation"), ("unknown_outcome", "break_reconciliation"),
    ("unknown_cause", "break_reconciliation"), ("started_unfulfilled", "break_reconciliation"),
    ("unfulfilled_with_delay", "break_reconciliation"), ("started_without_due", "break_reconciliation"),
    ("on_break_hours_mismatch", "break_reconciliation"),
    ("state_totals_moved", "employee_reconciliation"), ("state_totals_sum", "employee_reconciliation"),
    ("negative_off_hours", "finite_nonnegative"),
    ("nan_time", "record_structure"), ("inf_schedule", "record_structure"), ("bool_shift_index", "record_structure"),
    ("string_shift_index", "record_structure"), ("bool_break_shift_index", "record_structure"),
    ("string_state", "record_structure"), ("flag_not_bool", "record_structure"), ("missing_field", "record_structure"),
    ("zero_minute_break", "record_structure"), ("state_totals_missing_state", "record_structure"),
    ("timeline_not_list", "record_structure"), ("lowercase_policy", "record_structure"),
    ("no_provenance", "record_structure"), ("no_closing_policy", "record_structure"),
    ("begin_not_finite", "record_structure"), ("closing_time_text", "record_structure"),
    ("state_totals_list", "record_structure"), ("activated_not_bool", "record_structure"),
    ("release_text", "record_structure"), ("trigger_not_text", "record_structure"),
    ("break_name_not_text", "record_structure"), ("break_scheduled_nan", "record_structure"),
    ("break_due_text", "record_structure"), ("outcome_not_text", "record_structure"),
    ("cause_not_text", "record_structure"),
    ("zero_length_interval", "interval_geometry"), ("off_interval_past_end", "interval_geometry"),
    ("intervals_stop_short", "interval_geometry"),
    ("old_engine", "source_versions"), ("old_state_machine", "source_versions"), ("version_not_text", "source_versions"),
    ("version_equals_anything", "source_versions"),
])
def test_malformed_input_fails_its_check_and_is_never_repaired(change, check):
    result, employees = closing_day()
    _edit(result, change)
    before = copy.deepcopy(result)
    # Where a later check with the same code would also catch the record, the message pins the intended condition.
    fails(result, employees, check, _MESSAGES.get(change))
    assert result == before  # container equality compares the same NaN object by identity


_MESSAGES = {
    "after_closing_flag_before_closing": "after_closing disagrees",
    "past_end_flag_before_the_end": "past_scheduled_end disagrees",
    "tampered_overrun": "differs from the engine's formula",
    "tampered_activation_delay": "differs from the engine's formula",
    "activated_without_start": "activated disagrees",
    "unactivated_with_start": "activated disagrees",
    "unactivated_with_release": "was not activated",
    "tampered_delay": "delay differs",
    "completed_break_wrong_length": "configured duration",
    "truncated_break_not_at_closing": "exactly at closing",
    "unknown_outcome": "vocabulary",
    "unknown_cause": "vocabulary",
    "started_unfulfilled": "started if and only if",
    "unfulfilled_with_delay": "has an actual end or a delay",
    "started_without_due": "lacks its due time",
    "on_break_hours_mismatch": "ON_BREAK hours",
    "state_totals_moved": "differ from state_totals",
    "state_totals_sum": "do not sum to finish - begin",
    "zero_length_interval": "positive length",
    "off_interval_past_end": "OFF interval is flagged",
    "intervals_stop_short": "do not reach the timeline finish",
    "gap": "not contiguous",
    "on_duty_interval_without_shift": "if and only if its state is not OFF",
    "off_interval_with_shift": "if and only if its state is not OFF",
}


@pytest.mark.parametrize("change, match", [
    ("activated_without_release", "lacks its release"),
    ("shift_starts_after_its_intervals", "do not tile"),
    ("shift_released_after_its_intervals", "do not tile"),
])
def test_shift_span_is_checked_exactly(change, match):
    result, employees = closing_day()
    _edit(result, change)
    fails(result, employees, "shift_reconciliation", match)


def _merge_at(result: dict, employee_id: str, instant: float) -> None:
    """Merge the employee's interval ending at ``instant`` with the next one, keeping the first one's fields."""
    intervals = result["employee_timeline"]["intervals"]
    first = interval(result, employee_id, lambda row: row["end"] == instant)
    second = interval(result, employee_id, lambda row: row["start"] == instant)
    first["end"] = second["end"]
    intervals.remove(second)


def test_an_interval_crossing_closing_alone_is_rejected():
    # H5 under DRAIN: A serves 3.75-4.25 in one state; the engine splits the service at closing (4.0). Merged, the
    # interval crosses closing but not A's 5.0 scheduled end.
    result = simulate([shift("A", 480, 780)], rules(registers=1), [(3.75, 2.0)], policy=DRAIN)
    _merge_at(result, "A", 4.0)
    fails(result, staff([shift("A", 480, 780)]), "interval_geometry", "after_closing")


def test_an_interval_crossing_the_shift_end_alone_is_rejected():
    # H2: A serves 1.75-2.25 and its shift ends at 2.0, before closing. Merged, the interval crosses the shift end only.
    roster = [shift("A", 480, 600), shift("B", 600, 720)]
    result = simulate(roster, rules(registers=2), [(1.75, 2.0), (2.0, 2.0), (2.125, 0.5)])
    _merge_at(result, "A", 2.0)
    fails(result, staff(roster), "interval_geometry", "past_scheduled_end")


def test_a_shift_whose_intervals_are_not_adjacent_is_rejected():
    # H4: A's shift 0 intervals are 0-0.5 (available), 0.5-1.0 (serving), 1.0-1.625 (serving past the end). The middle
    # one is relabelled to shift 1, whose flags it also satisfies; shift 0 then starts and ends correctly but has a gap.
    result = simulate(SPLIT_ROSTER, SPLIT_RULES, [(0.5, 4.5), (1.75, 1.0), (2.75, 0.5)])
    interval(result, "A", lambda row: row["start"] == 0.5)["shift_index"] = 1
    fails(result, staff(SPLIT_ROSTER), "shift_reconciliation", "do not tile")


def test_past_end_hours_must_match_the_overrun():
    # H2's B shift (actual 2.0-4.0) is given a scheduled end of 1.0, before its actual start, with every other field
    # kept consistent: every interval is past the end (2.0 h) but the overrun formula gives 4.0 - 1.0 = 3.0.
    result = simulate([shift("A", 480, 600), shift("B", 600, 720)], rules(registers=2),
                      [(1.75, 2.0), (2.0, 2.0), (2.125, 0.5)])
    row = shift_record(result, "B", 1)
    row.update(scheduled_start=0.5, scheduled_end=1.0, activation_delay=1.5, overrun=3.0)
    for item in result["employee_timeline"]["intervals"]:
        if item["employee_id"] == "B" and item["shift_index"] == 1:
            item["past_scheduled_end"] = True
    fails(result, staff([shift("A", 480, 600), shift("B", 600, 720)]), "shift_reconciliation",
          "past_scheduled_end_hours differs from overrun")


@pytest.mark.parametrize("employees, match", [
    ("not a list", "input list of Employee"),
    ("missing C", "differ from the run's input employees"),
    ("extra Z", "differ from the run's input employees"),
    ("duplicate A", "distinct strings"),
])
def test_input_employees_are_authoritative(employees, match):
    result, staffed = closing_day()
    extra = Employee("Z", (AvailabilityWindow(0, 1440),), EmployeePay(None, None, None))
    given = {"not a list": staffed[0], "missing C": staffed[:2], "extra Z": [*staffed, extra],
             "duplicate A": [*staffed, staffed[0]]}[employees]
    fails(result, given, "employee_identity", match)


def test_result_must_be_a_named_result():
    fails("not a result", staff(CLOSING_ROSTER), "record_structure")
    result, employees = closing_day()
    result["replication"] = {"seed_entropy": 1}
    fails(result, employees, "record_structure", "replication block")


def test_overflowing_sums_fail_as_non_finite():
    with pytest.raises(shared_named_attribution._Violation) as info:
        shared_named_attribution._fsum([1e308, 1e308], "on_duty_hours", {})
    assert info.value.failure["check"] == "finite_nonnegative"


@pytest.mark.parametrize("edit, check", [
    # Values beyond the float range fail a check instead of raising OverflowError (a defect found and fixed in 5B-4.6).
    (lambda result: result["employee_timeline"]["intervals"][0].__setitem__("start", 10**400), "record_structure"),
    (lambda result: break_of(result, "A").__setitem__("duration_minutes", 10**400), "record_structure"),
    (lambda result: shift_record(result, "C", 2).update(scheduled_start=Fraction(-17 * 10**307),
                                                        scheduled_end=Fraction(17 * 10**307)), "finite_nonnegative"),
], ids=["huge_int_time", "huge_break_minutes", "fraction_span_beyond_float_range"])
def test_values_beyond_the_float_range_fail_a_check_not_raise(edit, check):
    result, employees = closing_day()
    edit(result)
    fails(result, employees, check)


def test_a_value_beyond_the_float_range_is_not_close_to_anything():
    assert shared_named_attribution._close_enough(1.0, Fraction(2 * 10**308)) is False


# ── Contract: units, names, provenance, purity ──────────────────────────────


def _numeric_fields(record: Any, path: str = "") -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    if isinstance(record, dict):
        for key, value in record.items():
            found += _numeric_fields(value, f"{path}.{key}")
    elif isinstance(record, list):
        for value in record:
            found += _numeric_fields(value, path + "[]")
    elif isinstance(record, (int, float)) and not isinstance(record, bool):
        found.append((path, record))
    return found


def test_units_and_names():
    _, out = attribute(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, required=REQUIRED_TWO)
    records = {"shifts": out["shifts"], "employees": out["employees"]}
    for path, _value in _numeric_fields(records):
        leaf = path.rsplit(".", 1)[-1]
        in_state_map = ".hours_by_state." in path
        is_count = leaf in ("shift_index", "shift_count", "activated_shift_count", "breaks_scheduled",
                            "breaks_completed", "breaks_truncated_by_closing", "released", "shift_not_activated",
                            "cancelled_at_closing")
        assert leaf.endswith("_hours") or leaf.endswith("_hours_total") or in_state_map or is_count or (
            leaf == "configured_minutes"), path
    for row in out["shifts"]:
        for item in row["breaks"]:
            assert isinstance(item["configured_minutes"], int)
            assert item["configured_hours"] == item["configured_minutes"] / 60.0
    # No bare "delay", no per-break total, and no pay field anywhere in the records.
    keys = {path.rsplit(".", 1)[-1] for path, _ in _numeric_fields(records)} | {
        key for row in out["shifts"] for item in row["breaks"] for key in item}
    assert "delay" not in keys and "paid" not in keys
    assert not any(key.endswith("_total") for row in out["shifts"] for item in row["breaks"] for key in item)
    text = repr(records).lower()
    assert not any(word in text for word in ("paid", "wage", "cost", "overtime", "penalty", "pay_"))


def test_provenance_and_contract_texts():
    result, out = attribute(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, required=REQUIRED_TWO)
    provenance = out["provenance"]
    assert provenance["attribution_version"] == ATTRIBUTION_VERSION == "novaq-shared-named-attribution-v1"
    assert (provenance["named_engine_version"], provenance["state_machine_version"]) == (
        NAMED_ENGINE_VERSION, STATE_MACHINE_VERSION)
    assert (provenance["closing_policy"], provenance["begin_hours"], provenance["closing_hours"],
            provenance["finish_hours"]) == (DRAIN, 0.0, 4.0, 4.875)
    assert provenance["replication"] is None
    assert provenance["inputs_sha256"] is None and "full run inputs unavailable" in provenance["inputs_sha256_reason"]
    assert provenance["tolerance"]["rel"] == 1e-9 and provenance["tolerance"]["abs"] == 1e-12
    assert provenance["monetary_cost"].startswith("None")
    assert list(out["checks"]) == list(CHECKS) == [
        "record_structure", "source_versions", "employee_identity", "shift_identity", "interval_geometry",
        "shift_reconciliation", "closing_partition", "base_state_partition", "break_reconciliation",
        "employee_reconciliation", "finite_nonnegative"]
    assert {item["method"] for item in out["reconciliation"]} == {"exact", "tolerance"}
    assert [row["employee_id"] for row in out["employees"]] == ["A", "B", "C"]
    assert [(row["employee_id"], row["shift_index"]) for row in out["shifts"]] == [
        (row["employee_id"], row["shift_index"]) for row in result["employee_timeline"]["shifts"]]


def test_a_replication_carries_its_identity_and_regenerates_identically():
    # D6: regenerate replication i through the unchanged 5B-4.4 path, then attribute it. The stored row keeps its
    # shape (no attribution inside it).
    run = replicate("split_shift", replications=2, seed=5, policy=DRAIN)
    roster = SCENARIOS["split_shift"][1]
    for index in range(2):
        result = regenerate("split_shift", run["provenance"]["root_entropy"], index, DRAIN)
        out = build_named_attribution(result, staff(roster))
        identity = out["provenance"]["replication"]
        assert identity == {"seed_entropy": result["replication"]["seed_entropy"],
                            "spawn_key": list(replication_seed_sequence(run["provenance"]["root_entropy"],
                                                                        index).spawn_key),
                            "customer_inputs_sha256": run["replications"][index]["customer_inputs_sha256"]}
        again = regenerate("split_shift", run["provenance"]["root_entropy"], index, DRAIN)
        assert build_named_attribution(again, staff(roster)) == out
        assert not any("attribution" in key for key in run["replications"][index])


def test_attribution_is_observational_deterministic_and_draws_nothing(monkeypatch):
    result, employees = closing_day()
    before, staff_before = copy.deepcopy(result), copy.deepcopy(employees)
    expected = build_named_attribution(result, employees)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a random number source was used")

    for name in ("default_rng", "Generator", "SeedSequence", "RandomState", "PCG64", "random", "exponential"):
        monkeypatch.setattr(np.random, name, forbidden)
    for name in ("random", "Random", "uniform", "choice", "shuffle", "randint", "expovariate", "sample"):
        monkeypatch.setattr(random, name, forbidden)
    assert build_named_attribution(result, employees) == expected
    assert result == before and employees == staff_before
    # The output shares no mutable object with the source: editing every output container leaves the source intact.
    for row in expected["shifts"]:
        row["breaks"].clear()
        if row["hours_by_state"] is not None:
            row["hours_by_state"].clear()
            row["closing_attribution"].clear()
    expected["provenance"]["tolerance"]["rel"] = 0.5
    assert result == before and shared_named_playback.TOLERANCE == {"rel": 1e-9, "abs": 1e-12}


def test_a_replication_identity_is_copied_not_shared():
    replication = regenerate("split_shift", 5, 0, DRAIN)
    out = build_named_attribution(replication, staff(SCENARIOS["split_shift"][1]))
    out["provenance"]["replication"]["spawn_key"].append(99)
    assert replication["replication"]["spawn_key"] == [0]


# ── Isolation ───────────────────────────────────────────────────────────────


def test_module_runs_no_simulation_and_uses_no_separate_queue_or_cost_code():
    tree = ast.parse(Path(shared_named_attribution.__file__).read_text(encoding="utf-8"))
    modules: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    assert not any(name == "random" or "numpy" in name or "separate" in name or "queue_lifecycle" in name
                   or "break_optimization" in name or "cost" in name or "api" in name or "db" in name
                   for name in modules)
    assert not names & {"simulate_named_prescribed", "simulate_named_replication", "EmployeeTimeline",
                        "run_named_replications", "draw_arrivals", "exponential", "default_rng", "SeedSequence"}
    assert shared_named_attribution.TOLERANCE is shared_named_playback.TOLERANCE


def test_module_is_registered_with_the_isolation_test():
    from tests.test_shared_segments import SHARED_QUEUE_ENHANCEMENT_MODULES

    assert "shared_named_attribution.py" in SHARED_QUEUE_ENHANCEMENT_MODULES
