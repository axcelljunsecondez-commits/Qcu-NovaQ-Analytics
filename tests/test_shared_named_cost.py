"""Phase 5B-5 named workforce cost of one named-employee shared-queue DES result.

ALL EMPLOYEES, AVAILABILITY, PAY, RATES, THRESHOLDS, RULES, ROSTERS, DEMAND, ARRIVALS, AND SERVICE WORK IN THIS FILE ARE
SYNTHETIC TEST DATA. They are not NovaMart records, labor law, payroll rules, or recommended rates.

The hand cases (spec section 12) use the Phase 5B-4.3 days: horizon 08:00-12:00 (hours 0-4), closing 4.0, service rate
4 per hour (service time = work / 4), and binary-exact times. Default pay: regular 20, overtime 30, daily threshold 480
minutes; waiting rate 10 per customer-hour, unserved rate 50 per customer. Each expected value is derived by hand in the
comments from the scenario's timeline (the attribution tests' H1-H7 derivations) and the approved rules C1-C16; none is
copied from probe output. Every run goes through the independent 5B-4.3 checker.

Seeded tests assert identities and an independent exact-arithmetic (Fraction) recomputation of the pay walk; no seeded
value is compared with a stored golden value. Malformed inputs are deep-copy edits of an engine result; the engine is
never changed. Tests marked "rule level" call the pay walk on synthetic intervals, for branches no engine lifecycle is
known to reach (spec section 15).
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

from backend.queueing_engine.services import shared_day_cost, shared_named_cost
from backend.queueing_engine.services.shared_named_cost import (
    CHECKS,
    COSTED,
    HOURS_UNDETERMINED,
    NAMED_COST_VERSION,
    NOT_APPLICABLE,
    PAID_STATES,
    RATE_MISSING,
    ZERO_QUANTITY,
    NamedCostError,
    NamedCostRates,
    cost_named_workforce,
)
from backend.queueing_engine.services.shared_workforce import (
    AvailabilityWindow,
    BreakRequirement,
    BreakRule,
    Employee,
    EmployeePay,
)
from backend.queueing_engine.simulation import shared_named_playback
from backend.queueing_engine.simulation.shared_employee_states import BASE_STATES, OFF, ON_BREAK, STATE_MACHINE_VERSION
from backend.queueing_engine.simulation.shared_named_attribution import (
    ATTRIBUTION_VERSION,
    NamedAttributionError,
    build_named_attribution,
)
from backend.queueing_engine.simulation.shared_named_des import (
    APPROVED_EMPLOYEE_POLICY,
    NAMED_ENGINE_VERSION,
    simulate_named_prescribed,
)
from backend.queueing_engine.simulation.shared_named_replications import simulate_named_replication
from tests.test_shared_employee_states import HORIZON, rules, shift, staff
from tests.test_shared_named_attribution import SPLIT_ROSTER, SPLIT_RULES
from tests.test_shared_named_des import (
    CLOSING_ARRIVALS,
    CLOSING_ROSTER,
    CLOSING_RULES,
    LONG_SHIFT_BREAK,
    ONE_REQUIRED,
    PERIODS,
    REQUIRED_TWO,
    check_named,
    simulate,
)
from tests.test_shared_named_replications import SCENARIOS, regenerate, replicate, replication_seed_sequence

# ── SYNTHETIC TEST DATA ──────────────────────────────────────────────────────

DRAIN, HARD_CUTOFF = "DRAIN", "HARD_CUTOFF"
PAY = EmployeePay(20, 30, 480)
RATES = NamedCostRates(10, 50)
UNPAID_REST = BreakRequirement("rest", 30, False, 0, 480)  # the same timing as the helpers' paid "rest" break
UNPAID_LONG_SHIFT_BREAK = (BreakRule(15, 120, 0, ()), BreakRule(121, 480, 0, (UNPAID_REST,)))
UNPAID_CLOSING_RULES = rules(*UNPAID_LONG_SHIFT_BREAK, registers=3)
H6_ROSTER = [shift("A", 480, 630, rest=600)]  # 08:00-10:30, 30-minute break at 10:00 (2.0)
H4_ARRIVALS = [(0.5, 4.5), (1.75, 1.0), (2.75, 0.5)]


def people(roster: list, **pay: EmployeePay) -> list[Employee]:
    """The roster's employees (helpers' ids and availability), each with its pay (default PAY)."""
    return [Employee(item.employee_id, item.availability, pay.get(item.employee_id, PAY)) for item in staff(roster)]


def run(roster: list, workforce: Any, arrivals: list, *, policy: str = DRAIN, required: list | None = None,
        **pay: EmployeePay) -> tuple[dict, list[Employee]]:
    """One named-engine run with pay-bearing employees, checked by the independent 5B-4.3 checker."""
    employees = people(roster, **pay)
    required = ONE_REQUIRED if required is None else required
    result = simulate_named_prescribed(HORIZON, PERIODS, employees, workforce, roster, arrivals, closing_policy=policy,
                                       employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=required)
    check_named(result, arrivals, workforce, roster, PERIODS, required, policy)
    # Pay never changes the engine: the run equals the pay-free helper run.
    assert result == simulate(roster, workforce, arrivals, policy=policy, required=required)
    return result, employees


def cost(roster: list, workforce: Any, arrivals: list, *, policy: str = DRAIN, required: list | None = None,
         rates: NamedCostRates = RATES, **pay: EmployeePay) -> dict:
    result, employees = run(roster, workforce, arrivals, policy=policy, required=required, **pay)
    return cost_named_workforce(result, employees, rates)


def emp(out: dict, employee_id: str) -> dict:
    (row,) = [row for row in out["employees"] if row["employee_id"] == employee_id]
    return row


def shift_of(out: dict, employee_id: str, shift_index: int) -> dict:
    (row,) = [row for row in emp(out, employee_id)["shifts"] if row["shift_index"] == shift_index]
    return row


def component(record: dict, name: str) -> dict:
    (row,) = [row for row in record["components"] if row["component"] == name]
    return row


def split(record: dict) -> tuple[Any, ...]:
    """(paid, regular, past-end-or-after-closing F, threshold-only T, overtime, labor cost)."""
    breakdown = record["overtime_breakdown"]
    return (record["paid_hours"], record["regular_paid_hours"], breakdown["past_end_or_after_closing_hours"],
            breakdown["daily_threshold_only_hours"], record["overtime_paid_hours"], record.get("labor_cost"))


def statuses(record: dict) -> tuple[str, str]:
    return component(record, "regular_labor")["status"], component(record, "overtime_labor")["status"]


def fails(result: Any, employees: Any, rates: Any, check: str, match: str | None = None) -> dict:
    with pytest.raises(NamedCostError) as info:
        cost_named_workforce(result, employees, rates)
    assert info.value.failure["check"] == check, info.value.failure
    if match is not None:
        assert match in info.value.failure["message"], info.value.failure
    return info.value.failure


# ── Hand cases (spec, section 12) ───────────────────────────────────────────


def test_hc_a_ordinary_regular_day():
    # A 08:00-12:00, no break, no customer, DRAIN: AVAILABLE 0-4 (4.0 paid, unflagged); at closing A is idle, so the
    # crew is [A] and A is released at 4.0. theta 8 h: R_1 = 8 > 4, one G piece of 4.0. Labor 4 x 20 = 80. The queue
    # integral is 0.0 (ZERO_QUANTITY). DRAIN with nobody unserved: the unserved term is NOT_APPLICABLE (C10b).
    out = cost([shift("A", 480, 720)], rules(registers=1), [])
    a = emp(out, "A")
    assert split(a) == (4.0, 4.0, 0.0, 0.0, 0.0, 80.0)
    assert (a["threshold_required"], a["hours_status"], a["threshold_reached_at_hours"]) == (True, "DETERMINED", None)
    assert statuses(a) == (COSTED, ZERO_QUANTITY)
    assert (out["waiting"]["quantity"], out["waiting"]["cost"], out["waiting"]["status"]) == (0.0, 0.0, ZERO_QUANTITY)
    assert (out["unserved"]["applies"], out["unserved"]["status"], out["unserved"]["cost"]) == (False, NOT_APPLICABLE,
                                                                                              None)
    assert out["unserved"]["applicability_basis"]["drain_crew"] == ["A"]
    assert (out["labor"]["total_cost"], out["total_cost"], out["missing"], out["total_withheld_reason"]) == (
        80.0, 80.0, [], None)


def test_hc_b_threshold_crossed_inside_one_interval():
    # HC-A with theta 180 minutes (3 h): R_1 = 3 < 4, so AVAILABLE 0-4 splits into G 3.0 and T 1.0; the threshold is
    # reached at 0 + 3 = 3.0. Labor 3 x 20 + 1 x 30 = 90.
    out = cost([shift("A", 480, 720)], rules(registers=1), [], A=EmployeePay(20, 30, 180))
    a = emp(out, "A")
    assert split(a) == (4.0, 3.0, 0.0, 1.0, 1.0, 90.0)
    assert (a["threshold_reached_at_hours"], a["daily_threshold_hours"]) == (3.0, 3.0)
    assert out["total_cost"] == 90.0


def test_hc_b0_zero_threshold_makes_every_unflagged_hour_overtime():
    # theta 0: C_1 = 0 >= 0, so the threshold is reached at the first paid instant, 0.0, and all 4.0 paid hours are T.
    # Regular is 0.0 (ZERO_QUANTITY), so the missing regular rate is not required. Overtime 4 x 30 = 120.
    out = cost([shift("A", 480, 720)], rules(registers=1), [], A=EmployeePay(None, 30, 0))
    a = emp(out, "A")
    assert split(a) == (4.0, 0.0, 0.0, 4.0, 4.0, 120.0)
    assert a["threshold_reached_at_hours"] == 0.0
    assert statuses(a) == (ZERO_QUANTITY, COSTED)
    assert component(a, "regular_labor")["rate_required"] is False
    assert (out["total_cost"], out["missing"]) == (120.0, [])


def test_hc_c_threshold_across_split_shifts_with_activation_delay_and_delayed_paid_break():
    # H4 (attribution test h4): shift 0 08:00-09:00 (0-1), shift 1 09:30-11:30 (1.5-3.5, paid 15-minute break at 10:00),
    # rest 30 minutes, one register, theta 120 minutes (2 h). Paid intervals in time order:
    #   [0, 0.5) AVAILABLE, [0.5, 1.0) SERVING #1, [1.0, 1.625) SERVING_SHIFT_ENDED (past shift 0's end: F 0.625),
    #   OFF 1.625-2.125 (unpaid: rest, and shift 1's activation delay from its 1.5 scheduled start),
    #   [2.125, 2.375) SERVING #2, [2.375, 2.625) AVAILABLE, [2.625, 2.875) ON_BREAK (paid; delayed 0.625 by the late
    #   activation), [2.875, 3.0) SERVING #3, [3.0, 3.5) AVAILABLE.
    # Walk: G 0.5, G 0.5; F 0.625 (C = 1.0 < 2, but flagged: no threshold split); C_4 = 1.625 counts the flagged time
    # (C5 condition 3), R_4 = 0.375 >= 0.25: G 0.25; C_5 = 1.875, R_5 = 0.125 < 0.25: G 0.125 + T 0.125, crossing at
    # 2.375 + 0.125 = 2.5; then T 0.25 (the paid break), 0.125, 0.5.
    # Regular 1.375; F 0.625; T 1.0; overtime 1.625; paid 3.0. Labor 27.5 + 48.75 = 76.25. Waits: #2 1.75 -> 2.125
    # (0.375), #3 2.75 -> 2.875 (0.125): 0.5 customer-hours, 5.0. DRAIN: A is OFF at closing (empty crew), nobody
    # waiting, nobody unserved: NOT_APPLICABLE. Total 81.25.
    out = cost(SPLIT_ROSTER, SPLIT_RULES, H4_ARRIVALS, A=EmployeePay(20, 30, 120))
    a = emp(out, "A")
    assert split(a) == (3.0, 1.375, 0.625, 1.0, 1.625, 76.25)
    assert (a["paid_break_hours"], a["unpaid_break_hours"], a["threshold_reached_at_hours"]) == (0.25, 0.0, 2.5)
    assert split(shift_of(out, "A", 0))[:5] == (1.625, 1.0, 0.625, 0.0, 0.625)
    assert split(shift_of(out, "A", 1))[:5] == (1.375, 0.375, 0.0, 1.0, 1.0)
    assert (out["waiting"]["quantity"], out["waiting"]["cost"]) == (0.5, 5.0)
    assert (out["unserved"]["status"], out["unserved"]["applicability_basis"]["drain_crew"]) == (NOT_APPLICABLE, [])
    assert out["total_cost"] == 81.25


def test_earlier_flagged_overtime_consumes_the_threshold_before_later_unflagged_split_shift_time():
    # Explicit regression (C5 condition 3 counts ALL earlier paid time). HC-C with theta 105 minutes (1.75 h): after
    # G 0.5 + 0.5 and the flagged F 0.625, C_4 = 1.625, so R_4 = 0.125 < 0.25: shift 1's first interval splits into
    # G 0.125 and T 0.125 (reached at 2.125 + 0.125 = 2.25), and everything after is T: 0.25 + 0.25 + 0.125 + 0.5.
    # Regular 1.125, T 1.25, F 0.625. Had the flagged time not counted, C_4 would be 1.0 and regular 1.75 (wrong).
    # The threshold is not reset between split shifts.
    a = emp(cost(SPLIT_ROSTER, SPLIT_RULES, H4_ARRIVALS, A=EmployeePay(20, 30, 105)), "A")
    assert split(a)[:5] == (3.0, 1.125, 0.625, 1.25, 1.875)
    assert a["threshold_reached_at_hours"] == 2.25
    assert a["regular_paid_hours"] != 1.75


def test_hc_d_register_waiting_is_paid_and_hc_i_overrun_before_closing():
    # H3: A 08:00-10:00 (0-2), B 10:00-12:00 (2-4), one register. A: AVAILABLE 0-1.75, serves #1 1.75-2.25, past its
    # 2.0 end from 2.0 (HC-I: F 0.25, before closing): regular 2.0, labor 40 + 7.5 = 47.5. B waits for the register
    # 2.0-2.25 (paid), serves #2 2.25-2.5, AVAILABLE 2.5-4.0: paid 2.0, all regular, labor 40.0 (overtime
    # ZERO_QUANTITY). #2 waits 2.125-2.25: 0.125 customer-hours, 1.25. Crew [B], nobody unserved: NOT_APPLICABLE.
    # Total 88.75.
    out = cost([shift("A", 480, 600), shift("B", 600, 720)], rules(registers=1), [(1.75, 2.0), (2.125, 1.0)])
    a, b = emp(out, "A"), emp(out, "B")
    assert split(a) == (2.25, 2.0, 0.25, 0.0, 0.25, 47.5)
    assert split(b) == (2.0, 2.0, 0.0, 0.0, 0.0, 40.0)
    assert statuses(b) == (COSTED, ZERO_QUANTITY)
    assert (out["waiting"]["quantity"], out["waiting"]["cost"], out["unserved"]["status"]) == (0.125, 1.25,
                                                                                             NOT_APPLICABLE)
    assert out["total_cost"] == 88.75


def test_hc_e_delayed_paid_break_carried_past_the_shift_end():
    # H6: A 08:00-10:30 (0-2.5), paid 30-minute break at 10:00 (2.0). #1 (1.75, work 2) 1.75-2.25; the break is due at
    # 2.0 while serving and runs 2.25-2.75 (delayed 0.25), split at the 2.5 shift end: [2.25, 2.5) regular, [2.5, 2.75)
    # past the end (F 0.25). Paid 2.75, regular 2.5, labor 50 + 7.5 = 57.5. A is OFF at closing: empty DRAIN crew,
    # nobody unserved, so the term is NOT_APPLICABLE (C10b: an empty crew alone does not make it apply).
    out = cost(H6_ROSTER, rules(*LONG_SHIFT_BREAK, registers=1), [(1.75, 2.0)])
    a = emp(out, "A")
    assert split(a) == (2.75, 2.5, 0.25, 0.0, 0.25, 57.5)
    assert (a["paid_break_hours"], a["unpaid_break_hours"]) == (0.5, 0.0)
    assert (out["unserved"]["status"], out["unserved"]["applicability_basis"]["drain_crew"]) == (NOT_APPLICABLE, [])
    assert out["total_cost"] == 57.5
    no_rate = cost(H6_ROSTER, rules(*LONG_SHIFT_BREAK, registers=1), [(1.75, 2.0)], rates=NamedCostRates(10, None))
    assert no_rate["total_cost"] == 57.5 and no_rate["unserved"]["status"] == NOT_APPLICABLE


def test_hc_f_delayed_unpaid_break_is_neither_paid_nor_counted():
    # H6 with the unpaid rule: the same timeline; the break 2.25-2.75 is unpaid, so paid 2.75 - 0.5 = 2.25, all before
    # the 2.5 end: regular 2.25, overtime ZERO_QUANTITY, labor 45.0. The unpaid ON_BREAK time past the end (0.25) is the
    # attribution's flagged union with F = 0.
    out = cost(H6_ROSTER, rules(*UNPAID_LONG_SHIFT_BREAK, registers=1), [(1.75, 2.0)])
    a = emp(out, "A")
    assert split(a) == (2.25, 2.25, 0.0, 0.0, 0.0, 45.0)
    assert (a["paid_break_hours"], a["unpaid_break_hours"]) == (0.0, 0.5)
    assert statuses(a) == (COSTED, ZERO_QUANTITY)
    assert out["total_cost"] == 45.0


def test_hc_g_unfulfilled_unpaid_break_with_work_instead():
    # H7 with the unpaid rule: #1 (1.75, work 4) 1.75-2.75; the break falls due at 2.0 while serving, the shift ends at
    # 2.5, and A is released at the completion without the break (unfulfilled, released). No break time exists; the
    # work is paid: AVAILABLE 1.75 + SERVING 0.25 + SERVING_BREAK_DUE 0.5 + SERVING_SHIFT_ENDED 0.25 (F) = 2.75.
    # Regular 2.5, labor 57.5. No phantom deduction. Nobody unserved: NOT_APPLICABLE; total 57.5.
    result, employees = run(H6_ROSTER, rules(*UNPAID_LONG_SHIFT_BREAK, registers=1), [(1.75, 4.0)])
    (item,) = result["employee_timeline"]["breaks"]
    assert (item["outcome"], item["unfulfilled_cause"], item["paid"]) == ("unfulfilled", "released", False)
    out = cost_named_workforce(result, employees, RATES)
    a = emp(out, "A")
    assert split(a) == (2.75, 2.5, 0.25, 0.0, 0.25, 57.5)
    assert (a["paid_break_hours"], a["unpaid_break_hours"]) == (0.0, 0.0)
    assert out["total_cost"] == 57.5


def test_hc_h_ordinary_and_truncated_unpaid_breaks_under_drain():
    # H1 (DRAIN) with the unpaid rule, which applies to A's and B's 4-hour shifts alike.
    # A: AVAILABLE 0-0.5, unpaid break 0.5-1.0, AVAILABLE 1.0-3.375, serving 3.375-4.875 (crew after closing); 4.0-4.875
    # is after closing and past the 4.0 end at once (F 0.875, counted once). Paid 4.875 - 0.5 = 4.375, regular 3.5,
    # labor 70 + 26.25 = 96.25.
    # B: AVAILABLE 0-3.25, SERVING 3.25-3.5, SERVING_BREAK_DUE 3.5-3.75, unpaid break 3.75-4.0 (delayed 0.25, truncated
    # by closing, then released; no work follows). Paid 3.75, regular, labor 75.0; overtime ZERO_QUANTITY.
    # C: 12:00-13:00, never activated: no paid time, labor 0.0.
    # Waits: #3 3.5 -> 3.875 (0.375), #4 3.625 -> 4.375 (0.75), #5 3.875 -> 4.625 (0.75): 1.875, so 18.75. Crew [A]
    # served the line: nobody unserved, NOT_APPLICABLE. Total 96.25 + 75 + 0 + 18.75 = 190.0.
    out = cost(CLOSING_ROSTER, UNPAID_CLOSING_RULES, CLOSING_ARRIVALS, required=REQUIRED_TWO)
    a, b, c = emp(out, "A"), emp(out, "B"), emp(out, "C")
    assert split(a) == (4.375, 3.5, 0.875, 0.0, 0.875, 96.25)
    assert (a["paid_break_hours"], a["unpaid_break_hours"]) == (0.0, 0.5)
    assert split(b) == (3.75, 3.75, 0.0, 0.0, 0.0, 75.0)
    assert (b["paid_break_hours"], b["unpaid_break_hours"]) == (0.0, 0.25)
    assert split(c) == (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert shift_of(out, "C", 2) == {"shift_index": 2, "activated": False, "paid_hours": None,
                                     "paid_break_hours": None, "unpaid_break_hours": None,
                                     "regular_paid_hours": None, "overtime_paid_hours": None,
                                     "overtime_breakdown": None}
    assert (out["waiting"]["quantity"], out["waiting"]["cost"], out["unserved"]["status"]) == (1.875, 18.75,
                                                                                             NOT_APPLICABLE)
    assert out["total_cost"] == 190.0


def test_hc_j_after_closing_before_the_scheduled_end_under_hard_cutoff():
    # H5: A 08:00-13:00 (0-5), #1 (3.75, work 2) 3.75-4.25. Under HARD_CUTOFF A gets Release at closing and finishes as
    # SERVING_SHIFT_ENDED: 4.0-4.25 is after closing but before the 5.0 end (F 0.25, after closing only). Paid 4.25,
    # regular 4.0, labor 80 + 7.5 = 87.5. The unserved term APPLIES (HARD_CUTOFF) with quantity 0: ZERO_QUANTITY, 0.0,
    # no rate required. Total 87.5, also with the unserved rate None.
    for rates in (RATES, NamedCostRates(10, None)):
        out = cost([shift("A", 480, 780)], rules(registers=1), [(3.75, 2.0)], policy=HARD_CUTOFF, rates=rates)
        assert split(emp(out, "A")) == (4.25, 4.0, 0.25, 0.0, 0.25, 87.5)
        unserved = out["unserved"]
        assert (unserved["applies"], unserved["quantity"], unserved["rate_required"], unserved["cost"],
                unserved["status"]) == (True, 0, False, 0.0, ZERO_QUANTITY)
        assert unserved["applicability_basis"]["rule"] == "X6 HARD_CUTOFF (inherited)"
        assert (out["total_cost"], out["missing"]) == (87.5, [])


def test_hc_k_cancelled_pending_unpaid_break_with_work_after_closing():
    # A 08:00-13:00 with an unpaid 30-minute break at 12:30 (4.5); #1 (3.75, work 2) 3.75-4.25; DRAIN. At closing A is
    # serving: crew [A]; the pending break is cancelled_at_closing. A serves on to 4.25 (after closing: F 0.25) and is
    # released idle. Paid 4.25, regular 4.0, labor 87.5. Nobody unserved: NOT_APPLICABLE. Total 87.5.
    result, employees = run([shift("A", 480, 780, rest=750)], rules(*UNPAID_LONG_SHIFT_BREAK, registers=1),
                            [(3.75, 2.0)])
    (item,) = result["employee_timeline"]["breaks"]
    assert (item["outcome"], item["unfulfilled_cause"]) == ("unfulfilled", "cancelled_at_closing")
    out = cost_named_workforce(result, employees, RATES)
    assert split(emp(out, "A")) == (4.25, 4.0, 0.25, 0.0, 0.25, 87.5)
    assert (out["unserved"]["status"], out["total_cost"]) == (NOT_APPLICABLE, 87.5)


def test_hc_l_p_past_end_and_after_closing_at_once_and_drain_crew_serves():
    # H1 (DRAIN, paid breaks). HC-L: A's 4.0-4.875 is both after closing and past the end, counted once: F 0.875;
    # paid 4.875 (paid break), regular 4.0, labor 80 + 26.25 = 106.25. HC-P: B paid 4.0 (paid break, truncated), 80.0;
    # C 0.0; labor 186.25; waiting 1.875, 18.75; two customers waited at closing and crew [A] served them, so nobody was
    # unserved: NOT_APPLICABLE. Total 205.0.
    out = cost(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, required=REQUIRED_TWO)
    assert split(emp(out, "A")) == (4.875, 4.0, 0.875, 0.0, 0.875, 106.25)
    assert split(emp(out, "B")) == (4.0, 4.0, 0.0, 0.0, 0.0, 80.0)
    assert emp(out, "B")["paid_break_hours"] == 0.25
    basis = out["unserved"]["applicability_basis"]
    assert (basis["drain_crew"], basis["waiting_customer_count"], basis["unserved_at_close"]) == (["A"], 2, 0)
    assert (out["labor"]["total_cost"], out["unserved"]["status"], out["total_cost"]) == (186.25, NOT_APPLICABLE,
                                                                                         205.0)


def test_hc_m_threshold_past_end_and_after_closing_at_once_get_one_premium():
    # H1 with A's theta 210 minutes (3.5 h); B keeps 480. A's paid intervals: [0, 0.5), paid break [0.5, 1.0),
    # [1.0, 3.375), [3.375, 3.875), [3.875, 4.0), then [4.0, 4.375), [4.375, 4.625), [4.625, 4.875) flagged. Walk:
    # G 0.5, 0.5, 2.375; C_4 = 3.375, R_4 = 0.125 < 0.5: G 0.125 + T 0.375 (reached 3.5); T 0.125; F 0.875 (the
    # after-closing, past-end, past-threshold instants get the one premium). Regular 3.5, T 0.5, overtime 1.375, labor
    # 70 + 41.25 = 111.25; run total 111.25 + 80 + 18.75 = 210.0.
    out = cost(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, required=REQUIRED_TWO, A=EmployeePay(20, 30, 210))
    a = emp(out, "A")
    assert split(a) == (4.875, 3.5, 0.875, 0.5, 1.375, 111.25)
    assert a["threshold_reached_at_hours"] == 3.5
    assert out["total_cost"] == 210.0
    # theta 240 (4 h): C_5 = 3.875 and R_5 = 0.125 equals [3.875, 4.0)'s length: G, reached exactly at its end, 4.0 (the
    # boundary case R_k == l_k). Hours as HC-L; run total 205.0.
    out = cost(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, required=REQUIRED_TWO, A=EmployeePay(20, 30, 240))
    a = emp(out, "A")
    assert split(a) == (4.875, 4.0, 0.875, 0.0, 0.875, 106.25)
    assert (a["threshold_reached_at_hours"], out["total_cost"]) == (4.0, 205.0)


def test_hc_n_activation_delay_is_unpaid():
    # HC-C shift 1: scheduled 1.5, activated 2.125; A is OFF 1.625-2.125 (the rest after the 1.625 release covers the
    # 0.625 activation delay). Shift 1's paid time is exactly its on-duty span 2.125-3.5 = 1.375, and the employee's
    # paid time 3.0 equals its on-duty hours: no OFF time is paid.
    result, employees = run(SPLIT_ROSTER, SPLIT_RULES, H4_ARRIVALS, A=EmployeePay(20, 30, 120))
    attribution = build_named_attribution(result, employees)
    out = cost_named_workforce(result, employees, RATES)
    second = [row for row in attribution["shifts"] if row["shift_index"] == 1][0]
    assert (second["activation_delay_hours"], second["on_duty_hours"]) == (0.625, 1.375)
    assert shift_of(out, "A", 1)["paid_hours"] == 1.375
    assert emp(out, "A")["paid_hours"] == attribution["employees"][0]["on_duty_hours"] == 3.0


def test_hc_o_hard_cutoff_with_unserved_customers():
    # H1b (HARD_CUTOFF): A serves #2 3.375-3.875 and #3 3.875-4.375; at closing A gets Release and finishes #3 as
    # SERVING_SHIFT_ENDED (4.0-4.375, both flags: F 0.375). Paid 4.375 (paid break), regular 4.0, labor 91.25. B: paid
    # 4.0 (paid break truncated at closing), 80.0. C 0.0. Labor 171.25. #4 (3.625) and #5 (3.875) are unserved
    # (hard_cutoff), waiting 0.375 and 0.125 until closing; #3 waited 0.375: 0.875 customer-hours, 8.75. Unserved
    # 2 x 50 = 100. Total 280.0.
    out = cost(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, policy=HARD_CUTOFF, required=REQUIRED_TWO)
    assert split(emp(out, "A")) == (4.375, 4.0, 0.375, 0.0, 0.375, 91.25)
    assert emp(out, "B")["labor_cost"] == 80.0 and out["labor"]["total_cost"] == 171.25
    assert (out["waiting"]["quantity"], out["waiting"]["cost"]) == (0.875, 8.75)
    unserved = out["unserved"]
    assert (unserved["applies"], unserved["quantity"], unserved["cost"], unserved["status"]) == (True, 2, 100.0, COSTED)
    assert unserved["applicability_basis"]["unserved_by_reason"] == {"hard_cutoff": 2, "no_eligible_employee": 0}
    assert out["total_cost"] == 280.0


def test_hc_q_drain_no_eligible_employee_applies_the_term():
    # A 08:00-11:00, released idle at 3.0. #1 arrives at 3.5 with nobody on duty and waits to closing; the DRAIN crew is
    # empty, so #1 is unserved (no_eligible_employee, elapsed 0.5). A paid 3.0 regular, 60.0; waiting 0.5, 5.0; the term
    # applies (C10b realized): 1 x 50 = 50.0. Total 115.0.
    out = cost([shift("A", 480, 660)], rules(registers=1), [(3.5, 1.0)])
    unserved = out["unserved"]
    assert (unserved["applies"], unserved["quantity"], unserved["rate_required"], unserved["cost"],
            unserved["status"]) == (True, 1, True, 50.0, COSTED)
    assert unserved["applicability_basis"] == {
        "closing_policy": DRAIN, "rule": "C10b DRAIN (realized)", "unserved_at_close": 1,
        "unserved_by_reason": {"hard_cutoff": 0, "no_eligible_employee": 1}, "drain_crew": [],
        "waiting_customer_count": 1}
    assert (emp(out, "A")["labor_cost"], out["waiting"]["cost"], out["total_cost"]) == (60.0, 5.0, 115.0)


def test_hc_r_s_t_missing_rates():
    day = ([shift("A", 480, 720)], rules(registers=1), [])
    # HC-R: regular 4.0 > 0 needs its rate.
    out = cost(*day, A=EmployeePay(None, 30, 480))
    a = emp(out, "A")
    assert statuses(a) == (RATE_MISSING, ZERO_QUANTITY)
    assert (a["labor_cost"], out["labor"]["total_cost"], out["total_cost"]) == (None, None, None)
    assert a["labor_cost_withheld"] == [{"field": "regular_rate_per_hour", "status": RATE_MISSING}]
    assert out["missing"] == [{"scope": "employee", "employee_id": "A", "field": "regular_rate_per_hour",
                               "status": RATE_MISSING, "requirement": "required"}]
    assert out["total_withheld_reason"] == "Withheld: A.regular_rate_per_hour (RATE_MISSING)."
    # HC-S: overtime 1.0 > 0 needs its rate; with overtime 0.0 it does not.
    out = cost(*day, A=EmployeePay(20, None, 180))
    assert statuses(emp(out, "A")) == (COSTED, RATE_MISSING) and out["total_cost"] is None
    out = cost(*day, A=EmployeePay(20, None, 480))
    assert statuses(emp(out, "A")) == (COSTED, ZERO_QUANTITY) and out["total_cost"] == 80.0
    # HC-T: waiting 0.125 > 0 (HC-D) needs its rate; waiting 0.0 (HC-A) does not.
    out = cost([shift("A", 480, 600), shift("B", 600, 720)], rules(registers=1), [(1.75, 2.0), (2.125, 1.0)],
               rates=NamedCostRates(None, 50))
    assert (out["waiting"]["status"], out["waiting"]["cost"], out["total_cost"]) == (RATE_MISSING, None, None)
    assert out["missing"] == [{"scope": "run", "employee_id": None, "field": "waiting_rate", "status": RATE_MISSING,
                               "requirement": "required"}]
    out = cost(*day, rates=NamedCostRates(None, 50))
    assert (out["waiting"]["status"], out["total_cost"]) == (ZERO_QUANTITY, 80.0)


def test_hc_u_v_unserved_rate_required_only_when_the_term_applies_with_a_positive_count():
    # HC-U: HC-O (2 unserved) and HC-Q (1 unserved) need the rate; HC-J (HARD_CUTOFF, 0) and HC-E (DRAIN, 0) do not.
    no_rate = NamedCostRates(10, None)
    for out in (cost(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, policy=HARD_CUTOFF, required=REQUIRED_TWO,
                     rates=no_rate),
                cost([shift("A", 480, 660)], rules(registers=1), [(3.5, 1.0)], rates=no_rate)):
        assert (out["unserved"]["status"], out["unserved"]["rate_required"], out["total_cost"]) == (RATE_MISSING, True,
                                                                                                    None)
        assert out["missing"][-1]["field"] == "unserved_customer_rate"
    assert cost([shift("A", 480, 780)], rules(registers=1), [(3.75, 2.0)], policy=HARD_CUTOFF,
                rates=no_rate)["total_cost"] == 87.5
    assert cost(H6_ROSTER, rules(*LONG_SHIFT_BREAK, registers=1), [(1.75, 2.0)], rates=no_rate)["total_cost"] == 57.5
    # HC-V: HC-P under DRAIN with nobody unserved: NOT_APPLICABLE whether or not a rate is supplied; a supplied rate is
    # recorded but not used.
    for rates in (no_rate, RATES):
        out = cost(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, required=REQUIRED_TWO, rates=rates)
        unserved = out["unserved"]
        assert (unserved["status"], unserved["applies"], unserved["rate_required"], unserved["cost"]) == (
            NOT_APPLICABLE, False, False, None)
        assert unserved["rate"] == rates.unserved_customer_rate
        assert out["total_cost"] == 205.0


def test_hc_w_missing_required_threshold_is_hours_undetermined_not_rate_missing():
    # HC-A with theta None: all 4.0 paid hours are unflagged, so theta is required (C14). Regular and overtime are None,
    # labor and total None, naming A.daily_regular_paid_minutes. Equal rates (20 and 20) change nothing.
    for pay in (EmployeePay(20, 30, None), EmployeePay(20, 20, None)):
        out = cost([shift("A", 480, 720)], rules(registers=1), [], A=pay)
        a = emp(out, "A")
        assert (a["threshold_required"], a["hours_status"], a["paid_hours"]) == (True, HOURS_UNDETERMINED, 4.0)
        assert (a["regular_paid_hours"], a["overtime_paid_hours"], a["labor_cost"]) == (None, None, None)
        assert a["overtime_breakdown"] == {"past_end_or_after_closing_hours": 0.0, "daily_threshold_only_hours": None}
        for name in ("regular_labor", "overtime_labor"):
            row = component(a, name)
            assert (row["status"], row["quantity"], row["rate_required"], row["cost"]) == (HOURS_UNDETERMINED, None,
                                                                                         None, None)
        assert out["missing"] == [{"scope": "employee", "employee_id": "A", "field": "daily_regular_paid_minutes",
                                   "status": HOURS_UNDETERMINED, "requirement": "required"}]
        assert (out["total_cost"], out["labor"]["total_cost"]) == (None, None)
        assert out["labor"]["withheld"] == [{"employee_id": "A", "field": "daily_regular_paid_minutes",
                                             "status": HOURS_UNDETERMINED}]
    # A None rate beside a missing required threshold is listed as undetermined (5B-2 precedent), never RATE_MISSING.
    out = cost([shift("A", 480, 720)], rules(registers=1), [], A=EmployeePay(None, None, None))
    assert [(item["field"], item["status"], item["requirement"]) for item in out["missing"]] == [
        ("daily_regular_paid_minutes", HOURS_UNDETERMINED, "required"),
        ("regular_rate_per_hour", HOURS_UNDETERMINED, "undetermined"),
        ("overtime_rate_per_hour", HOURS_UNDETERMINED, "undetermined")]
    # Only the required threshold withholds the labor cost; the undetermined rates are listed, not blamed.
    assert emp(out, "A")["labor_cost_withheld"] == [{"field": "daily_regular_paid_minutes",
                                                    "status": HOURS_UNDETERMINED}]
    assert out["total_withheld_reason"] == "Withheld: A.daily_regular_paid_minutes (HOURS_UNDETERMINED)."


def test_hc_w2_missing_threshold_keeps_the_flagged_part():
    # H1b with A's theta None: A has unflagged paid time, so HOURS_UNDETERMINED; its flagged F 0.375 is still reported.
    out = cost(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, policy=HARD_CUTOFF, required=REQUIRED_TWO,
               A=EmployeePay(20, 30, None))
    a = emp(out, "A")
    assert a["hours_status"] == HOURS_UNDETERMINED
    assert split(a) == (4.375, None, 0.375, None, None, None)
    assert out["total_cost"] is None and emp(out, "B")["labor_cost"] == 80.0


def test_hc_w3_threshold_not_required_without_paid_time():
    # H1 with C's pay all None: C has no paid time, so theta is not required; regular and overtime 0.0 are
    # ZERO_QUANTITY and need no rate. Labor 0.0; the run total is HC-P's 205.0.
    out = cost(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, required=REQUIRED_TWO, C=EmployeePay(None, None, None))
    c = emp(out, "C")
    assert (c["threshold_required"], c["hours_status"], c["daily_threshold_hours"]) == (False, "DETERMINED", None)
    assert split(c) == (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert statuses(c) == (ZERO_QUANTITY, ZERO_QUANTITY)
    assert (out["missing"], out["total_cost"]) == ([], 205.0)


# ── Status rules (C10b, C13) ────────────────────────────────────────────────


def test_c10b_asymmetry_hard_cutoff_zero_applies_drain_zero_does_not():
    hard = cost([shift("A", 480, 780)], rules(registers=1), [(3.75, 2.0)], policy=HARD_CUTOFF)["unserved"]
    drain = cost([shift("A", 480, 780)], rules(registers=1), [(3.75, 2.0)], policy=DRAIN)["unserved"]
    assert (hard["applies"], hard["quantity"], hard["rate_required"], hard["cost"], hard["status"]) == (
        True, 0, False, 0.0, ZERO_QUANTITY)
    assert (drain["applies"], drain["quantity"], drain["rate_required"], drain["cost"], drain["status"]) == (
        False, 0, False, None, NOT_APPLICABLE)


def test_status_vocabulary_keeps_zero_none_and_every_status_apart():
    assert len({COSTED, ZERO_QUANTITY, RATE_MISSING, NOT_APPLICABLE, HOURS_UNDETERMINED}) == 5
    assert (COSTED, RATE_MISSING, NOT_APPLICABLE) == (shared_day_cost.COSTED, shared_day_cost.RATE_MISSING,
                                                      shared_day_cost.NOT_APPLICABLE)
    seen = {}
    for out in (cost([shift("A", 480, 720)], rules(registers=1), []),
                cost([shift("A", 480, 720)], rules(registers=1), [], A=EmployeePay(None, 30, None)),
                cost([shift("A", 480, 720)], rules(registers=1), [], A=EmployeePay(None, 30, 480)),
                cost([shift("A", 480, 660)], rules(registers=1), [(3.5, 1.0)])):
        for row in [*(item for record in out["employees"] for item in record["components"]), out["waiting"],
                    out["unserved"]]:
            seen.setdefault(row["status"], set()).add(repr(row["cost"]))
    assert seen == {COSTED: {"80.0", "5.0", "50.0", "60.0"}, ZERO_QUANTITY: {"0.0"}, RATE_MISSING: {"None"},
                    NOT_APPLICABLE: {"None"}, HOURS_UNDETERMINED: {"None"}}


def test_a_supplied_zero_rate_is_costed_zero():
    out = cost([shift("A", 480, 720)], rules(registers=1), [], A=EmployeePay(0, 30, 480))
    row = component(emp(out, "A"), "regular_labor")
    assert (row["status"], row["quantity"], row["rate"], row["rate_required"], row["cost"]) == (COSTED, 4.0, 0, True,
                                                                                              0.0)
    assert out["total_cost"] == 0.0


def test_a_tiny_positive_quantity_still_requires_its_rate():
    # #1 arrives one ulp before closing with nobody on duty: it waits 4.0 - nextafter(4.0, 0) = 2**-51 hours and is
    # unserved (empty DRAIN crew). The waiting quantity is positive, however small, so its rate is required (exact zero
    # test, C13); the tolerance never turns it into zero.
    arrival = math.nextafter(4.0, 0.0)
    out = cost([shift("A", 480, 660)], rules(registers=1), [(arrival, 1.0)], rates=NamedCostRates(None, 50))
    assert out["waiting"]["quantity"] == 4.0 - arrival == 2.0 ** -51
    assert (out["waiting"]["status"], out["waiting"]["rate_required"], out["total_cost"]) == (RATE_MISSING, True, None)
    out = cost([shift("A", 480, 660)], rules(registers=1), [(arrival, 1.0)])
    assert (out["waiting"]["status"], out["waiting"]["cost"]) == (COSTED, 2.0 ** -51 * 10.0)


def test_a_tiny_float_slice_is_reported_as_computed_not_snapped():
    # A 08:15-10:45 (0.25-2.75), paid 20-minute break at 08:20 (20/60 h), no customer, theta 5 minutes. In exact
    # arithmetic the threshold falls exactly at the break start (08:20), but the float times are l_1 = 20/60 - 0.25 and
    # theta_h = 5/60, so R_2 = theta_h - l_1 is a positive sliver: the break's first 2**-56 hours are a G piece and the
    # rest T. The sliver is reported as computed; nothing is snapped to the boundary (C15).
    workforce = rules(BreakRule(15, 120, 0, ()), BreakRule(121, 480, 0, (BreakRequirement("rest", 20, True, 0, 480),)),
                      registers=1)
    result, employees = run([shift("A", 495, 645, rest=500)], workforce, [], A=EmployeePay(20, 30, 5))
    out = cost_named_workforce(result, employees, RATES)
    a = emp(out, "A")
    first = 20 / 60 - 0.25
    sliver = 5 / 60 - first
    assert 0.0 < sliver < 1e-15
    # The pieces themselves: G first, then the G sliver and the T remainder of the paid break, then T.
    rows = [row for row in shared_named_cost._paid_rows(result["employee_timeline"])["A"] if row["paid"]]
    walk = shared_named_cost._pay_walk(rows, 5 / 60, {})
    assert walk["pieces"] == [(0, "G", first), (0, "G", sliver), (0, "T", (40 / 60 - 20 / 60) - sliver),
                              (0, "T", 2.75 - 40 / 60)]
    # Kept, not snapped: regular is first + sliver (= 5/60), not the boundary value `first` alone. The derived instant
    # 20/60 + sliver rounds to 20/60 in float; it is reported as that computation gives it.
    assert a["regular_paid_hours"] == math.fsum([first, sliver]) == 5 / 60 != first
    assert a["threshold_reached_at_hours"] == 20 / 60 + sliver
    assert a["overtime_breakdown"]["daily_threshold_only_hours"] == math.fsum(
        [(40 / 60 - 20 / 60) - sliver, 2.75 - 40 / 60])


# ── Paid and unpaid breaks (C3, C7) ─────────────────────────────────────────


def _with_unpaid_breaks(workforce: Any) -> Any:
    return type(workforce)(workforce.shift_rules, tuple(
        BreakRule(rule.min_shift_minutes, rule.max_shift_minutes, rule.min_gap_minutes,
                  tuple(BreakRequirement(item.name, item.duration_minutes, False, item.earliest_start_offset_minutes,
                                         item.latest_start_offset_minutes) for item in rule.breaks))
        for rule in workforce.break_rules), workforce.register_count)


def _without_paid_flags(result: dict) -> dict:
    timeline = copy.deepcopy(result["employee_timeline"])
    for row in timeline["breaks"]:
        row.pop("paid")
    return timeline


@pytest.mark.parametrize("name", ["stable", "delayed_break", "split_shift", "outside_the_horizon",
                                  "break_ending_at_closing"])
def test_paid_and_unpaid_breaks_leave_the_timeline_unchanged_and_move_only_break_time(name):
    demand, roster, workforce, required = SCENARIOS[name]
    for index in range(3):
        runs = [simulate_named_replication(HORIZON, demand, staff(roster), rule_set, roster,
                                           seed_sequence=replication_seed_sequence(7, index), closing_policy=DRAIN,
                                           employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=required)
                for rule_set in (workforce, _with_unpaid_breaks(workforce))]
        assert _without_paid_flags(runs[0]) == _without_paid_flags(runs[1])
        assert {row["paid"] for row in runs[0]["employee_timeline"]["breaks"]} <= {True}
        assert {row["paid"] for row in runs[1]["employee_timeline"]["breaks"]} <= {False}
        paid, unpaid = (cost_named_workforce(item, people(roster), RATES) for item in runs)
        for left, right in zip(paid["employees"], unpaid["employees"]):
            assert left["unpaid_break_hours"] == 0.0 and right["paid_break_hours"] == 0.0
            assert left["paid_break_hours"] == right["unpaid_break_hours"]
            assert near(left["paid_hours"] - left["paid_break_hours"], right["paid_hours"])


# ── Seeded identities (10 scenarios x 2 policies x 25 replications) ─────────


def near(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def _exact_walk(result: dict, employee_id: str, minutes: int) -> tuple[Fraction, Fraction, Fraction, Any, bool]:
    """An independent exact-arithmetic walk: (G, T, F, reached, required) with Fraction lengths and theta = minutes/60."""
    timeline = result["employee_timeline"]
    started = [row for row in timeline["breaks"] if row["employee_id"] == employee_id and row["actual_start"] is not None]
    theta = Fraction(minutes, 60)
    regular = threshold = flagged = cumulative = Fraction(0)
    reached = None
    required = False
    for row in timeline["intervals"]:
        if row["employee_id"] != employee_id or row["state"] == OFF:
            continue
        if row["state"] == ON_BREAK:
            (item,) = [b for b in started if b["shift_index"] == row["shift_index"]
                       and b["actual_start"] <= row["start"] and row["end"] <= b["actual_end"]]
            if not item["paid"]:
                continue
        length = Fraction(row["end"]) - Fraction(row["start"])
        if reached is None and cumulative + length >= theta:
            reached = Fraction(row["start"]) + max(Fraction(0), theta - cumulative)
        if row["after_closing"] or row["past_scheduled_end"]:
            flagged += length
        else:
            required = True
            before = max(Fraction(0), min(length, theta - cumulative))
            regular += before
            threshold += length - before
        cumulative += length
    return regular, threshold, flagged, reached, required


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_identities_hold_on_seeded_runs(name, policy):
    roster = SCENARIOS[name][1]
    for index in range(25):
        result = regenerate(name, 20260930, index, policy)
        minutes = (0, 45, 180, 480)[index % 4]
        employees = people(roster, **{item.employee_id: EmployeePay(20, 30, minutes) for item in staff(roster)})
        out = cost_named_workforce(result, employees, RATES)
        attribution = build_named_attribution(result, employees)
        for record, summary in zip(out["employees"], attribution["employees"]):
            assert record["employee_id"] == summary["employee_id"]
            regular, threshold, flagged, reached, required = _exact_walk(result, record["employee_id"], minutes)
            assert record["threshold_required"] == required
            f = record["overtime_breakdown"]["past_end_or_after_closing_hours"]
            t = record["overtime_breakdown"]["daily_threshold_only_hours"]
            assert near(record["regular_paid_hours"], float(regular)) and near(t, float(threshold))
            assert near(f, float(flagged))
            assert (record["threshold_reached_at_hours"] is None) == (reached is None)
            if reached is not None:
                assert near(record["threshold_reached_at_hours"], float(reached))
            assert near(record["regular_paid_hours"] + record["overtime_paid_hours"], record["paid_hours"])
            assert record["regular_paid_hours"] <= minutes / 60 or near(record["regular_paid_hours"], minutes / 60)
            assert near(record["paid_hours"] + record["unpaid_break_hours"], summary["on_duty_hours"])
            assert near(record["paid_break_hours"] + record["unpaid_break_hours"], summary["hours_by_state"][ON_BREAK])
            assert record["unpaid_break_hours"] == 0.0  # every SCENARIOS break is paid
            assert record["labor_cost"] == math.fsum([record["regular_paid_hours"] * 20.0,
                                                      record["overtime_paid_hours"] * 30.0])
            activated = [row for row in record["shifts"] if row["activated"]]
            assert near(math.fsum(row["paid_hours"] for row in activated), record["paid_hours"])
            assert near(math.fsum(row["regular_paid_hours"] for row in activated), record["regular_paid_hours"])
        assert out["waiting"]["quantity"] == result["queue"]["customer_hours_total"]
        unserved = result["counts"]["unserved_at_close"]
        assert out["unserved"]["quantity"] == unserved
        assert out["unserved"]["applies"] == (policy == HARD_CUTOFF or unserved > 0)
        costs = [row["cost"] for record in out["employees"] for row in record["components"]] + [out["waiting"]["cost"]]
        if out["unserved"]["applies"]:
            costs.append(out["unserved"]["cost"])
        assert out["total_cost"] == math.fsum(costs)
        assert out["labor"]["total_cost"] == math.fsum(record["labor_cost"] for record in out["employees"])


# ── Rule level: the pay walk on synthetic intervals ─────────────────────────


def _rows(*spans: tuple[float, float, bool], shift_index: int = 0) -> list[dict[str, Any]]:
    return [{"start": start, "end": end, "length": end - start, "shift_index": shift_index, "on_break": False,
             "paid": True, "flagged": flagged} for start, end, flagged in spans]


def test_rule_level_threshold_not_required_when_every_paid_instant_is_flagged():
    # Rule level (spec section 15, item 4): no engine lifecycle is known to give paid time above 0 that is entirely
    # flagged (every activated shift starts before its scheduled end and before closing). C14 decides it anyway: the
    # threshold is not required, every piece is F, regular is 0.0, and the split is determined even without theta.
    paid = _rows((4.0, 4.5, True), (4.5, 5.0, True))
    walk = shared_named_cost._pay_walk(paid, None, {})
    assert (walk["required"], walk["determined"], walk["reached"]) == (False, True, None)
    assert walk["pieces"] == [(0, "F", 0.5), (0, "F", 0.5)]
    # With theta 0.75 h the instant is still found (4.75), inside a flagged interval, with no pay effect: no T piece.
    walk = shared_named_cost._pay_walk(paid, 0.75, {})
    assert (walk["reached"], walk["pieces"]) == (4.75, [(0, "F", 0.5), (0, "F", 0.5)])
    # Missing theta with some unflagged time: undetermined, and only the F pieces are formed.
    walk = shared_named_cost._pay_walk(_rows((3.0, 4.0, False), (4.0, 4.5, True)), None, {})
    assert (walk["required"], walk["determined"], walk["pieces"]) == (True, False, [(0, "F", 0.5)])


def test_rule_level_threshold_reached_at_the_previous_end_through_float_sums():
    # Rule level (spec 5.2 step 7a, "otherwise x_{k-1}.end"): with boundaries 1/3, +0.2, +0.7 and theta_h = fsum(l_1,
    # l_2) = 0.9000000000000001, R_2 = theta_h - l_1 = 0.7000000000000002 exceeds l_2 = 0.7000000000000001 by rounding,
    # so the second interval is wholly G; then C_3 = theta_h, the threshold is reached at the second interval's end,
    # and the third interval is T. Every comparison is exact.
    s0 = 1 / 3
    s1 = s0 + 0.2
    s2 = s1 + 0.7
    # An unpaid gap (OFF, or an unpaid break) separates the second and third paid intervals: the instant is the second
    # interval's end, not the third's start.
    paid = _rows((s0, s1, False), (s1, s2, False), (s2 + 0.25, s2 + 0.75, False))
    theta = math.fsum([s1 - s0, s2 - s1])
    assert theta - (s1 - s0) > s2 - s1
    walk = shared_named_cost._pay_walk(paid, theta, {})
    assert [kind for _, kind, _ in walk["pieces"]] == ["G", "G", "T"]
    assert walk["reached"] == s2


def test_rule_level_threshold_reached_exactly_at_the_end_of_the_last_paid_interval():
    # R_k == l_k on the last paid interval: the whole interval is G (no zero-length T piece), and the instant is its
    # end even though no later interval exists to observe C_k >= theta_h.
    walk = shared_named_cost._pay_walk(_rows((0.0, 0.5, False), (0.5, 1.0, False)), 1.0, {})
    assert (walk["pieces"], walk["reached"]) == ([(0, "G", 0.5), (0, "G", 0.5)], 1.0)
    walk = shared_named_cost._pay_walk(_rows((0.0, 0.5, False), (0.5, 1.0, True)), 1.0, {})
    assert (walk["pieces"], walk["reached"]) == ([(0, "G", 0.5), (0, "F", 0.5)], 1.0)


def test_d7_failure_inside_the_walk_raises_finite_nonnegative_with_the_d7_evidence():
    # Rule level: both D7 differences in the walk are INFERRED unreachable (spec 5.3). The wrapper still reports a D7
    # failure as finite_nonnegative carrying the attribution D7 failure.
    with pytest.raises(shared_named_cost._Violation) as info:
        shared_named_cost._d7(1.0, 2.0, "R_k", {"employee_id": "A", "k": 3})
    failure = info.value.failure
    assert failure["check"] == "finite_nonnegative"
    assert failure["evidence"]["d7_failure"]["check"] == "finite_nonnegative"
    assert (failure["evidence"]["employee_id"], failure["evidence"]["k"]) == ("A", 3)
    assert shared_named_cost._d7(1.0, math.nextafter(1.0, 2.0), "R_k", {}) == 0.0


# ── Malformed inputs (spec, section 11) ─────────────────────────────────────


def closing_day(policy: str = DRAIN) -> tuple[dict, list[Employee]]:
    return run(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, policy=policy, required=REQUIRED_TWO)


def h6_day() -> tuple[dict, list[Employee]]:
    return run(H6_ROSTER, rules(*LONG_SHIFT_BREAK, registers=1), [(1.75, 2.0)])


@pytest.mark.parametrize("rates", [
    None, (10, 50), NamedCostRates(-1, 50), NamedCostRates(10, -0.5), NamedCostRates(math.nan, 50),
    NamedCostRates(10, math.inf), NamedCostRates(True, 50), NamedCostRates("10", 50),  # type: ignore[arg-type]
    NamedCostRates(10, 10**400),
], ids=["none", "tuple", "negative_waiting", "negative_unserved", "nan", "inf", "bool", "text", "beyond_float"])
def test_malformed_rates_fail_rate_structure(rates):
    result, employees = closing_day()
    fails(result, employees, rates, "rate_structure")


@pytest.mark.parametrize("pay", [
    None, (20, 30, 480), EmployeePay(-1, 30, 480), EmployeePay(20, math.nan, 480), EmployeePay(True, 30, 480),
    EmployeePay(20, "30", 480), EmployeePay(10**400, 30, 480), EmployeePay(20, 30, -5),  # type: ignore[arg-type]
    EmployeePay(20, 30, 4.5),  # type: ignore[arg-type]
    EmployeePay(20, 30, True), EmployeePay(20, 30, 10**400),
], ids=["none", "tuple", "negative_rate", "nan_rate", "bool_rate", "text_rate", "rate_beyond_float",
        "negative_threshold", "float_threshold", "bool_threshold", "threshold_beyond_float"])
def test_malformed_pay_fails_pay_structure(pay):
    result, employees = closing_day()
    employees = [Employee(item.employee_id, item.availability, pay if item.employee_id == "B" else item.pay)
                 for item in employees]
    failure = fails(result, employees, RATES, "pay_structure")
    assert failure["evidence"]["employee_id"] == "B"


def _customer(result: dict, customer_id: int) -> dict:
    return next(row for row in result["customers"] if row["customer_id"] == customer_id)


@pytest.mark.parametrize("edit", [
    lambda r: r.pop("counts"),
    lambda r: r["counts"].pop("unserved_at_close"),
    lambda r: r["counts"].__setitem__("unserved_by_reason", [0, 0]),
    lambda r: r.__setitem__("customers", {"1": {}}),
    lambda r: _customer(r, 1).pop("status"),
    lambda r: _customer(r, 1).__setitem__("status", "left"),
    lambda r: _customer(r, 1).__setitem__("status", ["departed"]),
    lambda r: _customer(r, 1).__setitem__("unserved_reason", 5),
    lambda r: _customer(r, 1).__setitem__("customer_id", "1"),
    lambda r: _customer(r, 1).__setitem__("customer_id", True),
    lambda r: r["customers"].append("row"),
    lambda r: r["queue"].pop("customer_hours_total"),
    lambda r: r["queue"].__setitem__("customer_hours_total", "1.875"),
    lambda r: r["queue"].__setitem__("customer_hours_in_horizon", True),
    lambda r: r.__setitem__("queue", None),
    lambda r: r.__setitem__("at_close", None),
    lambda r: r["employee_timeline"]["breaks"][0].pop("paid"),
    lambda r: r["employee_timeline"]["breaks"][0].__setitem__("paid", "yes"),
    lambda r: r["employee_timeline"]["breaks"][0].__setitem__("paid", 1),
    lambda r: r["employee_timeline"]["breaks"][1].__setitem__("paid", None),
], ids=["no_counts", "no_unserved_count", "reasons_not_mapping", "customers_not_list", "no_status",
        "unknown_status", "unhashable_status", "reason_not_text", "id_text", "id_bool", "row_not_mapping",
        "no_queue_total", "queue_text", "queue_bool", "queue_none", "at_close_none", "paid_missing", "paid_text",
        "paid_int", "paid_none"])
def test_malformed_result_fields_fail_result_structure(edit):
    result, employees = closing_day()
    edit(result)
    fails(result, employees, RATES, "result_structure")


def test_attribution_failures_propagate_unchanged():
    result, employees = closing_day()
    result["employee_timeline"]["intervals"][0]["state"] = "IDLE"
    with pytest.raises(NamedAttributionError) as info:
        cost_named_workforce(result, employees, RATES)
    assert info.value.failure["check"] == "record_structure"
    with pytest.raises(NamedAttributionError):
        cost_named_workforce("not a result", employees, RATES)
    # Attribution runs first (C16): a malformed result is reported before malformed rates.
    with pytest.raises(NamedAttributionError):
        cost_named_workforce(result, employees, None)  # type: ignore[arg-type]


def test_break_mapping_requires_containment_and_exact_tiling():
    # H6: the break 2.25-2.75 is two ON_BREAK intervals split at the 2.5 shift end. Each edit keeps the attribution
    # valid (delay, due, and lengths within its tolerance) and fails only the exact mapping.
    result, employees = h6_day()
    item = result["employee_timeline"]["breaks"][0]
    assert (item["actual_start"], item["actual_end"]) == (2.25, 2.75)
    late = copy.deepcopy(result)
    moved = late["employee_timeline"]["breaks"][0]
    moved["actual_start"] = math.nextafter(2.25, 3.0)  # the first ON_BREAK interval now starts before the break
    moved["delay"] = moved["actual_start"] - moved["scheduled_start"]
    build_named_attribution(late, employees)
    fails(late, employees, RATES, "break_mapping", "inside exactly one")
    short = copy.deepcopy(result)
    short["employee_timeline"]["breaks"][0]["actual_end"] = math.nextafter(2.75, 3.0)  # the intervals stop 1 ulp early
    build_named_attribution(short, employees)
    fails(short, employees, RATES, "break_mapping", "tile")
    early = copy.deepcopy(result)
    moved = early["employee_timeline"]["breaks"][0]
    moved["actual_start"] = math.nextafter(2.25, 0.0)  # the intervals start 1 ulp after the break
    moved["delay"] = moved["actual_start"] - moved["scheduled_start"]
    build_named_attribution(early, employees)
    fails(early, employees, RATES, "break_mapping", "tile")


def test_two_paid_breaks_in_one_shift_map_to_their_own_intervals():
    # A 08:00-12:00 with two paid 15-minute breaks, a at 09:00 (1.0) and b at 10:00 (2.0), no customer: AVAILABLE 0-1,
    # ON_BREAK 1.0-1.25 (a), AVAILABLE 1.25-2.0, ON_BREAK 2.0-2.25 (b), AVAILABLE 2.25-4.0. Each ON_BREAK interval lies
    # in exactly its own break. Paid 4.0 including 0.5 of paid breaks, all regular: 80.0. With both breaks unpaid: paid
    # 3.5, 70.0.
    for paid, expected in ((True, (4.0, 0.5, 0.0, 80.0)), (False, (3.5, 0.0, 0.5, 70.0))):
        workforce = rules(BreakRule(15, 120, 0, ()), BreakRule(121, 480, 0, (
            BreakRequirement("a", 15, paid, 0, 480), BreakRequirement("b", 15, paid, 0, 480))), registers=1)
        a = emp(cost([shift("A", 480, 720, a=540, b=600)], workforce, []), "A")
        assert (a["paid_hours"], a["paid_break_hours"], a["unpaid_break_hours"], a["labor_cost"]) == expected
        assert a["regular_paid_hours"] == a["paid_hours"]


def test_break_mapping_rejects_an_on_break_interval_inside_two_breaks():
    # A 08:00-12:00 with two paid 15-minute breaks, a at 09:00 (1.0) and b at 10:00 (2.0), no customer: ON_BREAK 1.0-1.25
    # and 2.0-2.25. Copying a's timing into b keeps the attribution valid (b is a completed 0.25-hour break, and the
    # shift's ON_BREAK hours 0.5 still equal the started breaks' 0.25 + 0.25), but the interval 1.0-1.25 now lies inside
    # two started breaks: not exactly one.
    workforce = rules(BreakRule(15, 120, 0, ()), BreakRule(121, 480, 0, (BreakRequirement("a", 15, True, 0, 480),
                                                                         BreakRequirement("b", 15, True, 0, 480))),
                      registers=1)
    result, employees = run([shift("A", 480, 720, a=540, b=600)], workforce, [])
    a, b = result["employee_timeline"]["breaks"]
    assert (a["actual_start"], b["actual_start"]) == (1.0, 2.0)
    b.update({key: a[key] for key in ("scheduled_start", "due", "actual_start", "actual_end", "delay")})
    build_named_attribution(result, employees)
    failure = fails(result, employees, RATES, "break_mapping", "inside exactly one")
    assert failure["evidence"]["matches"] == 2


@pytest.mark.parametrize("edit, match", [
    (lambda r: r.__setitem__("at_close", {}), "never processed closing"),
    (lambda r: r["at_close"].__setitem__("drain_crew", "A"), "as lists"),
    (lambda r: r["at_close"].__setitem__("waiting_customer_ids", ["4"]), "as lists"),
    (lambda r: r["at_close"].__setitem__("drain_crew", [1]), "as lists"),
    (lambda r: r["counts"]["unserved_by_reason"].__setitem__("other", 0), "exactly hard_cutoff"),
    (lambda r: r["counts"]["unserved_by_reason"].pop("no_eligible_employee"), "exactly hard_cutoff"),
    (lambda r: r["counts"]["unserved_by_reason"].__setitem__("hard_cutoff", 2.0), "exactly hard_cutoff"),
    (lambda r: r["counts"]["unserved_by_reason"].__setitem__("hard_cutoff", True), "exactly hard_cutoff"),
    (lambda r: r["counts"].__setitem__("unserved_at_close", 3), "exactly hard_cutoff"),
    (lambda r: r["counts"].__setitem__("unserved_at_close", 2.0), "exactly hard_cutoff"),
    (lambda r: (r["counts"].update(unserved_at_close=1), r["counts"]["unserved_by_reason"].update(hard_cutoff=1)),
     "rows do not match"),
    (lambda r: _customer(r, 4).__setitem__("unserved_reason", "no_eligible_employee"), "rows do not match"),
    (lambda r: _customer(r, 4).__setitem__("unserved_reason", "other"), "rows do not match"),
    (lambda r: _customer(r, 1).__setitem__("unserved_reason", "hard_cutoff"), "rows do not match"),
    # An extra unserved row with an unknown or no reason leaves the per-reason counts intact; only the row count shows it.
    (lambda r: _customer(r, 1).update(status="unserved_at_close", unserved_reason="other"), "rows do not match"),
    (lambda r: _customer(r, 1).update(status="unserved_at_close", unserved_reason=None), "rows do not match"),
    (lambda r: (_customer(r, 4).update(unserved_reason="no_eligible_employee"),
                r["counts"]["unserved_by_reason"].update(hard_cutoff=1, no_eligible_employee=1)), "closing policy"),
    (lambda r: r["at_close"].__setitem__("waiting_customer_ids", [4, 6]), "closing policy"),
    (lambda r: r["at_close"].__setitem__("waiting_customer_ids", [4, 5, 5]), "closing policy"),
], ids=["no_closing_record", "crew_not_list", "waiting_ids_text", "crew_ids_not_text", "extra_reason",
        "missing_reason", "reason_float", "reason_bool", "total_mismatch", "total_float", "rows_short",
        "reason_mismatch", "unknown_reason", "departed_with_reason", "extra_row_unknown_reason",
        "extra_row_no_reason", "hard_cutoff_with_no_eligible",
        "waiting_ids_differ", "waiting_ids_duplicated"])
def test_hard_cutoff_unserved_record_must_agree(edit, match):
    result, employees = closing_day(HARD_CUTOFF)  # #4 and #5 unserved (hard_cutoff); at_close waiting [4, 5]
    assert result["at_close"]["waiting_customer_ids"] == [4, 5]
    edit(result)
    fails(result, employees, RATES, "unserved_consistency", match)


def test_drain_unserved_record_must_agree():
    # DRAIN with a crew (H1): nobody is unserved; DRAIN with an empty crew (HC-Q): the waiting line is unserved.
    crewed, employees = closing_day(DRAIN)
    edited = copy.deepcopy(crewed)
    _customer(edited, 5).update(status="unserved_at_close", unserved_reason="no_eligible_employee")
    edited["counts"].update(unserved_at_close=1, unserved_by_reason={"hard_cutoff": 0, "no_eligible_employee": 1})
    fails(edited, employees, RATES, "unserved_consistency", "DRAIN crew")
    empty, staff_q = run([shift("A", 480, 660)], rules(registers=1), [(3.5, 1.0)])
    for edit in (
        lambda r: r["at_close"].__setitem__("drain_crew", ["A"]),  # a crew, yet a customer was unserved
        lambda r: (_customer(r, 1).__setitem__("unserved_reason", "hard_cutoff"),
                   r["counts"]["unserved_by_reason"].update(hard_cutoff=1, no_eligible_employee=0)),
        lambda r: r["at_close"].__setitem__("waiting_customer_ids", []),
        # Empty crew and a waiting customer, yet nobody unserved (X6 says everyone waiting is unserved).
        lambda r: (_customer(r, 1).update(status="departed", unserved_reason=None),
                   r["counts"].update(unserved_at_close=0, unserved_by_reason={"hard_cutoff": 0,
                                                                               "no_eligible_employee": 0})),
    ):
        edited = copy.deepcopy(empty)
        edit(edited)
        fails(edited, staff_q, RATES, "unserved_consistency", "closing policy")


@pytest.mark.parametrize("edit, check", [
    (lambda q: q.__setitem__("customer_hours_total", 2.0), "waiting_consistency"),
    (lambda q: q.__setitem__("customer_hours_after_closing", -0.25), "waiting_consistency"),
    (lambda q: q.update(customer_hours_in_horizon=-0.5, customer_hours_after_closing=0.0, customer_hours_total=-0.5),
     "waiting_consistency"),
    (lambda q: q.__setitem__("customer_hours_total", math.nan), "waiting_consistency"),
    (lambda q: q.__setitem__("customer_hours_in_horizon", math.inf), "waiting_consistency"),
    (lambda q: q.update(customer_hours_in_horizon=1.7e308, customer_hours_after_closing=1.7e308,
                        customer_hours_total=1.7e308), "waiting_consistency"),
    (lambda q: q.update(customer_hours_in_horizon=Fraction(2 * 10**308), customer_hours_total=Fraction(2 * 10**308)),
     "waiting_consistency"),
], ids=["total_differs", "negative", "negative_but_summing", "nan", "inf", "sum_overflows", "fraction_beyond_float"])
def test_queue_integrals_must_reconcile(edit, check):
    result, employees = closing_day()
    edit(result["queue"])
    fails(result, employees, RATES, check)


def test_costs_beyond_the_float_range_fail_finite_nonnegative():
    result, employees = closing_day()
    fails(result, employees, NamedCostRates(1.7e308, 50), "finite_nonnegative")  # 1.875 customer-hours x 1.7e308
    big = [Employee(item.employee_id, item.availability, EmployeePay(1e308, 30, 480)) for item in employees]
    failure = fails(result, big, RATES, "finite_nonnegative")  # A's 4.0 regular hours x 1e308 = inf
    assert (failure["evidence"]["field"], failure["evidence"]["employee_id"]) == ("labor_cost", "A")
    # A withheld total still checks every computed cost: with A's regular rate missing (total withheld), the overflowing
    # waiting cost (1.875 x 1.7e308) is caught by the output check.
    partial = [Employee(item.employee_id, item.availability, EmployeePay(None, 30, 480) if item.employee_id == "A"
                        else item.pay) for item in employees]
    failure = fails(result, partial, NamedCostRates(1.7e308, 50), "finite_nonnegative")
    assert failure["evidence"]["field"] == "component waiting.cost"


def test_partition_self_checks_reject_inconsistent_hours():
    # paid_partition and overtime_partition reconcile the pay walk with the attribution. On valid input they hold by
    # construction: both sum the same validated intervals, partitioned into paid and unpaid (and G, T, F) pieces, so
    # no input reaches their failures. Fed an inconsistent record, each fails.
    result, employees = closing_day()
    out = cost_named_workforce(result, employees, RATES)
    a = emp(out, "A")
    attribution = build_named_attribution(result, employees)["employees"][0]
    hours = {key: a[key] for key in ("paid_hours", "paid_break_hours", "unpaid_break_hours", "regular_paid_hours",
                                     "overtime_paid_hours")}
    hours.update(overtime_breakdown=dict(a["overtime_breakdown"]), unpaid_flagged_break_hours=0.0, _g=4.0, _t=0.0)
    shared_named_cost._check_partitions(hours, attribution, 8.0, {})  # the consistent record passes
    edits = [
        ("paid_partition", {"paid_hours": 4.5}),
        ("paid_partition", {"paid_break_hours": 0.25}),
        ("overtime_partition", {"_g": -0.5}),
        ("overtime_partition", {"_t": -0.5}),
        ("overtime_partition", {"unpaid_flagged_break_hours": 0.5}),
        ("overtime_partition", {"regular_paid_hours": 3.0}),
        ("overtime_partition", {"overtime_breakdown": {"past_end_or_after_closing_hours": -0.875,
                                                       "daily_threshold_only_hours": 0.0}}),
    ]
    for check, edit in edits:
        with pytest.raises(shared_named_cost._Violation) as info:
            shared_named_cost._check_partitions({**hours, **edit}, attribution, 8.0, {})
        assert info.value.failure["check"] == check, (check, edit)
    with pytest.raises(shared_named_cost._Violation) as info:
        shared_named_cost._check_partitions(hours, attribution, 3.5, {})  # regular 4.0 above a 3.5 h threshold
    assert "exceeds the daily threshold" in info.value.failure["message"]


def test_output_self_check_rejects_an_inconsistent_component():
    # cost_arithmetic guards the module's own arithmetic; no valid input reaches its failure. Fed an inconsistent
    # record, it fails.
    out = cost([shift("A", 480, 720)], rules(registers=1), [])
    components = [*out["employees"][0]["components"], out["waiting"], out["unserved"]]
    for field, value in (("cost", 81.0), ("status", ZERO_QUANTITY), ("rate", None)):
        edited = copy.deepcopy(components)
        edited[0][field] = value
        with pytest.raises(shared_named_cost._Violation) as info:
            shared_named_cost._check_output(out, edited)
        assert info.value.failure["check"] == "cost_arithmetic"
    edited_out = {**out, "total_cost": 79.0}
    with pytest.raises(shared_named_cost._Violation) as info:
        shared_named_cost._check_output(edited_out, components)
    assert info.value.failure["check"] == "cost_arithmetic"


# ── Contract: schema, units, provenance, purity ─────────────────────────────


def test_output_schema_and_provenance():
    result, employees = closing_day()
    out = cost_named_workforce(result, employees, RATES)
    assert list(out) == ["employees", "labor", "waiting", "unserved", "total_cost", "missing", "total_withheld_reason",
                         "formula", "currency", "reconciliation", "definitions", "checks", "undetermined",
                         "provenance"]
    assert list(out["employees"][0]) == [
        "employee_id", "pay", "paid_hours", "paid_break_hours", "unpaid_break_hours", "threshold_required",
        "daily_threshold_hours", "threshold_reached_at_hours", "hours_status", "regular_paid_hours",
        "overtime_paid_hours", "overtime_breakdown", "shifts", "components", "labor_cost", "labor_cost_withheld"]
    assert list(out["employees"][0]["shifts"][0]) == [
        "shift_index", "activated", "paid_hours", "paid_break_hours", "unpaid_break_hours", "regular_paid_hours",
        "overtime_paid_hours", "overtime_breakdown"]
    assert list(out["waiting"]) == ["component", "quantity", "unit", "source", "rate_field", "rate", "applies",
                                    "rate_required", "cost", "status", "note"]
    assert list(out["unserved"])[-1] == "applicability_basis"
    assert [row["employee_id"] for row in out["employees"]] == ["A", "B", "C"]
    assert emp(out, "A")["pay"] == {"regular_rate_per_hour": 20, "overtime_rate_per_hour": 30,
                                    "daily_regular_paid_minutes": 480}
    assert (out["waiting"]["unit"], out["unserved"]["unit"], component(emp(out, "A"), "regular_labor")["unit"]) == (
        "customer-hours", "customers", "paid hours")
    provenance = out["provenance"]
    assert provenance["cost_version"] == NAMED_COST_VERSION == "novaq-shared-named-cost-v1"
    assert (provenance["attribution_version"], provenance["named_engine_version"],
            provenance["state_machine_version"], provenance["closing_policy"]) == (
        ATTRIBUTION_VERSION, NAMED_ENGINE_VERSION, STATE_MACHINE_VERSION, DRAIN)
    assert provenance["replication"] is None and provenance["inputs_sha256"] is None
    assert provenance["tolerance"]["rel"] == 1e-9 and provenance["tolerance"]["abs"] == 1e-12
    assert "not an employment-law" in provenance["scope_note"]
    assert list(out["checks"]) == list(CHECKS) == [
        "rate_structure", "pay_structure", "result_structure", "break_mapping", "paid_partition", "overtime_partition",
        "unserved_consistency", "waiting_consistency", "finite_nonnegative", "cost_arithmetic"]
    assert out["currency"] == "The caller's currency; this module assumes none."
    # No verdict, acceptance, or capacity-labor field anywhere (C2, C11).
    text = repr({key: value for key, value in out.items() if key not in ("definitions", "checks", "undetermined",
                                                                         "provenance", "formula")}).lower()
    assert not any(word in text for word in ("verdict", "pass", "fail", "accept", "server_hours", "server-hours"))


def test_paid_states_are_every_base_state_but_off_and_on_break():
    assert set(PAID_STATES) | {OFF, ON_BREAK} == set(BASE_STATES) and not set(PAID_STATES) & {OFF, ON_BREAK}


def test_capacity_integrals_and_the_trace_are_never_read():
    # C2: the named result's staffing integrals and trace are not charged or used.
    result, employees = closing_day()
    expected = cost_named_workforce(result, employees, RATES)
    result["staffing"] = None
    result["trace"] = None
    assert cost_named_workforce(result, employees, RATES) == expected


def test_a_replication_carries_its_identity_and_regenerates_identically():
    run_ = replicate("split_shift", replications=2, seed=5, policy=DRAIN)
    roster = SCENARIOS["split_shift"][1]
    for index in range(2):
        result = regenerate("split_shift", run_["provenance"]["root_entropy"], index, DRAIN)
        out = cost_named_workforce(result, people(roster), RATES)
        assert out["provenance"]["replication"] == build_named_attribution(result, people(roster))["provenance"][
            "replication"]
        again = regenerate("split_shift", run_["provenance"]["root_entropy"], index, DRAIN)
        assert cost_named_workforce(again, people(roster), RATES) == out
        out["provenance"]["replication"]["spawn_key"].append(99)
        assert result["replication"]["spawn_key"] == [index]


def test_cost_is_observational_deterministic_and_draws_nothing(monkeypatch):
    result, employees = closing_day()
    rates = NamedCostRates(10, 50)
    before, staff_before, rates_before = copy.deepcopy(result), copy.deepcopy(employees), copy.deepcopy(rates)
    attribution_before = build_named_attribution(result, employees)
    expected = cost_named_workforce(result, employees, rates)
    np_state, py_state = np.random.get_state(), random.getstate()

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a random number source was used")

    for name in ("default_rng", "Generator", "SeedSequence", "RandomState", "PCG64", "random", "exponential"):
        monkeypatch.setattr(np.random, name, forbidden)
    for name in ("random", "Random", "uniform", "choice", "shuffle", "randint", "expovariate", "sample"):
        monkeypatch.setattr(random, name, forbidden)
    assert cost_named_workforce(result, employees, rates) == expected
    monkeypatch.undo()
    assert result == before and employees == staff_before and rates == rates_before
    assert build_named_attribution(result, employees) == attribution_before
    assert np.array_equal(np.random.get_state()[1], np_state[1]) and random.getstate() == py_state
    # The output shares no mutable object with the source: editing its containers leaves the source intact.
    for record in expected["employees"]:
        record["pay"]["regular_rate_per_hour"] = -1
        record["shifts"].clear()
    expected["unserved"]["applicability_basis"]["drain_crew"].append("Z")
    expected["unserved"]["applicability_basis"]["unserved_by_reason"]["hard_cutoff"] = 9
    expected["provenance"]["tolerance"]["rel"] = 0.5
    assert result == before and employees == staff_before
    assert shared_named_playback.TOLERANCE == {"rel": 1e-9, "abs": 1e-12}


# ── Isolation ───────────────────────────────────────────────────────────────


def test_module_runs_no_simulation_and_uses_no_separate_queue_api_or_db_code():
    tree = ast.parse(Path(shared_named_cost.__file__).read_text(encoding="utf-8"))
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
                   or "break_optimization" in name or ".api" in name or ".db" in name or "costing" in name
                   or "optimization" in name for name in modules)
    assert not names & {"simulate_named_prescribed", "simulate_named_replication", "EmployeeTimeline",
                        "run_named_replications", "draw_arrivals", "exponential", "default_rng", "SeedSequence",
                        "cost_shared_day", "DayCostRates"}
    assert shared_named_cost.TOLERANCE is shared_named_playback.TOLERANCE


def test_module_is_registered_with_the_isolation_test():
    from tests.test_shared_segments import SHARED_QUEUE_ENHANCEMENT_MODULES

    assert "shared_named_cost.py" in SHARED_QUEUE_ENHANCEMENT_MODULES
