"""Phase 5B-2 sequential shared-queue rostering MILP.

ALL EMPLOYEES, AVAILABILITY, RULES, RATES, REQUIREMENTS, AND DEMAND IN THIS FILE ARE SYNTHETIC
TEST DATA. They are not NovaMart records, labor law, or recommended operating values.

Expected optima are computed by hand in the comments, and are also checked against an
independent brute force. The brute force enumerates every shift and break placement with plain
minute loops, accepts a plan only when the 5B-1 ``evaluate_roster`` finds no violation, and
computes cost, coverage, and register use itself, minute by minute.
"""

from __future__ import annotations

import itertools
import math
import random
from dataclasses import replace

import numpy as np
import pytest
from scipy.optimize import milp as real_milp

from backend.queueing_engine.services import shared_rostering
from backend.queueing_engine.services.shared_capacity import CapacityConfig, optimize_shared_capacity
from backend.queueing_engine.services.shared_rostering import (
    FEASIBLE,
    FEASIBLE_NOT_PROVEN_OPTIMAL,
    INCOMPLETE,
    INFEASIBLE,
    INTEGRALITY_TOLERANCE,
    NO_SOLUTION_FOUND,
    OPTIMAL,
    PATTERN_LIMIT_EXCEEDED,
    SOLVER_ERROR,
    UNKNOWN,
    VERIFICATION_FAILED,
    RosterOptimizationConfig,
    enumerate_patterns,
    max_paid_minutes,
    optimize_roster_for_capacity_plan,
    optimize_sequential_roster,
)
from backend.queueing_engine.services.shared_segments import (
    MINUTES_PER_DAY,
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
)
from backend.queueing_engine.services.shared_workforce import (
    AvailabilityWindow,
    BreakRequirement,
    BreakRule,
    Employee,
    EmployeePay,
    ScheduledBreak,
    ScheduledShift,
    ShiftRules,
    WorkforceRules,
    evaluate_roster,
)

# ── SYNTHETIC TEST DATA ──────────────────────────────────────────────────────

HORIZON = OperatingHorizon(480, 720)  # 08:00-12:00
REST = BreakRequirement("rest", 30, False, 60, 120)  # unpaid, starts 60-120 min into the shift
SHIFTS = ShiftRules(earliest_start_minute=480, latest_end_minute=720, min_shift_minutes=120, max_shift_minutes=240,
                    boundary_granularity_minutes=60, max_shifts_per_employee=1, min_minutes_between_shifts=None)
RULES = WorkforceRules(SHIFTS, (BreakRule(120, 180, 0, ()), BreakRule(181, 240, 0, (REST,))), register_count=2)
A = Employee("A", (AvailabilityWindow(480, 720),), EmployeePay(60.0, 90.0, 480))
B = Employee("B", (AvailabilityWindow(480, 720),), EmployeePay(40.0, 60.0, 480))
ALL_DAY = [StaffingSegment("day", 480, 720, 1)]
FIRST_TWO_HOURS = [StaffingSegment("early", 480, 600, 1), StaffingSegment("late", 600, 720, 0)]
BOTH_ENDS = [StaffingSegment("open", 480, 540, 1), StaffingSegment("lull", 540, 660, 0),
             StaffingSegment("close", 660, 720, 1)]
CONFIG = RosterOptimizationConfig(break_start_granularity_minutes=30, time_limit_seconds=60.0, mip_rel_gap=0.0,
                                  max_patterns=10_000)


def solve(employees, required, rules=RULES, config=CONFIG, horizon=HORIZON) -> dict:
    return optimize_sequential_roster(horizon, employees, rules, required, config=config)


def shifts_of(result: dict) -> set[tuple]:
    return {(item["employee_id"], item["start_minute"], item["end_minute"],
             tuple((b["name"], b["start_minute"]) for b in item["breaks"])) for item in result["roster"]}


def as_key(shift: ScheduledShift) -> tuple:
    return (shift.employee_id, shift.start_minute, shift.end_minute,
            tuple((b.name, b.start_minute) for b in shift.breaks))


# ── Independent brute force ─────────────────────────────────────────────────


def brute_single_shifts(employee, rules, break_grid, horizon=HORIZON) -> set[ScheduledShift]:
    """Every one-shift plan 5B-1 accepts with breaks on the grid, by plain minute loops."""
    grid = rules.shift_rules.boundary_granularity_minutes
    found = set()
    for start in range(0, MINUTES_PER_DAY + 1, 1):
        if start % grid:
            continue
        for end in range(start + 1, MINUTES_PER_DAY + 1):
            if end % grid:
                continue
            rule = next((r for r in rules.break_rules if r.min_shift_minutes <= end - start <= r.max_shift_minutes), None)
            if rule is None:
                continue
            options = [[u for u in range(start, end) if u % break_grid == 0] for _ in rule.breaks]
            for combo in itertools.product(*options):
                shift = ScheduledShift(employee.employee_id, start, end,
                                       tuple(ScheduledBreak(item.name, u) for item, u in zip(rule.breaks, combo)))
                if not evaluate_roster(horizon, [employee], rules, [shift])["violations"]:
                    found.add(shift)
    return found


def plan_minutes(plan, rules) -> tuple[np.ndarray, int]:
    """Active servers per clock minute and paid minutes, computed here, not by the module."""
    active = np.zeros(MINUTES_PER_DAY, dtype=np.int64)
    paid = 0
    for shift in plan:
        length = shift.end_minute - shift.start_minute
        rule = next(r for r in rules.break_rules if r.min_shift_minutes <= length <= r.max_shift_minutes)
        durations = {item.name: item for item in rule.breaks}
        active[shift.start_minute:shift.end_minute] += 1
        paid += length
        for item in shift.breaks:
            requirement = durations[item.name]
            active[item.start_minute:item.start_minute + requirement.duration_minutes] -= 1
            if not requirement.paid:
                paid -= requirement.duration_minutes
    return active, paid


def plan_cost(employee, paid: int) -> float:
    pay = employee.pay
    if paid == 0:
        return 0.0
    regular = min(paid, pay.daily_regular_paid_minutes)
    overtime = paid - regular
    return ((0.0 if regular == 0 else pay.regular_rate_per_hour * regular)
            + (0.0 if overtime == 0 else pay.overtime_rate_per_hour * overtime)) / 60.0


def brute_force(employees, rules, required, break_grid, horizon=HORIZON) -> tuple[float | None, set[frozenset]]:
    """The minimum labor cost and every roster that attains it (exhaustive)."""
    per_employee: list[list[tuple[tuple[ScheduledShift, ...], np.ndarray, float]]] = []
    for employee in employees:
        singles = sorted(brute_single_shifts(employee, rules, break_grid, horizon), key=as_key)
        plans: list[tuple[ScheduledShift, ...]] = [()]
        for size in range(1, rules.shift_rules.max_shifts_per_employee + 1):
            for combo in itertools.combinations(singles, size):
                if not evaluate_roster(horizon, [employee], rules, list(combo))["violations"]:
                    plans.append(combo)
        rows = []
        for plan in plans:
            active, paid = plan_minutes(plan, rules)
            rows.append((plan, active, plan_cost(employee, paid)))
        per_employee.append(rows)
    need = np.zeros(MINUTES_PER_DAY, dtype=np.int64)
    for segment in required:
        need[segment.start_minute:segment.end_minute] = segment.servers
    inside = np.zeros(MINUTES_PER_DAY, dtype=bool)
    inside[horizon.start_minute:horizon.end_minute] = True
    best: float | None = None
    rosters: set[frozenset] = set()
    for choice in itertools.product(*per_employee):
        total = sum((active for _, active, _ in choice), np.zeros(MINUTES_PER_DAY, dtype=np.int64))
        if total.max() > rules.register_count or np.any(total[inside] < need[inside]):
            continue
        cost = math.fsum(cost for _, _, cost in choice)
        key = frozenset(as_key(shift) for plan, _, _ in choice for shift in plan)
        if best is None or cost < best - 1e-9:
            best, rosters = cost, {key}
        elif abs(cost - best) <= 1e-9:
            rosters.add(key)
    return best, rosters


def assert_matches_brute_force(result, employees, rules, required, break_grid, horizon=HORIZON) -> set[frozenset]:
    best, rosters = brute_force(employees, rules, required, break_grid, horizon)
    if best is None:
        assert result["status"] == INFEASIBLE and result["feasibility"] == INFEASIBLE
        assert result["roster"] is None
        return rosters
    assert result["status"] == OPTIMAL and result["feasibility"] == FEASIBLE
    assert result["labor_cost"]["total"] == pytest.approx(best, abs=1e-9)
    assert frozenset(shifts_of(result)) in rosters
    return rosters


# ── Pattern generation ──────────────────────────────────────────────────────


@pytest.mark.parametrize("break_grid", [1, 30, 60])
def test_pattern_set_equals_brute_force(break_grid):
    generated = enumerate_patterns([A], RULES, break_grid, 10_000)
    assert generated["limit_exceeded"] is False and generated["missing_break_rules"] == []
    assert {as_key(pattern.as_shift()) for pattern in generated["patterns"]} == {
        as_key(shift) for shift in brute_single_shifts(A, RULES, break_grid)}


@pytest.mark.parametrize("break_grid, exactly_apart, too_close", [
    (15, [(("x", 510), ("y", 555)), (("x", 525), ("y", 480))], [(("x", 510), ("y", 540))]),
    (45, [(("x", 540), ("y", 585)), (("x", 540), ("y", 495))], [(("x", 540), ("y", 540))]),
])
def test_pattern_set_with_two_breaks_a_gap_and_windows_past_the_shift_end(break_grid, exactly_apart, too_close):
    # 120-180 minute shifts: a 30-minute break whose window (offset 60-170) runs past a 120-minute shift's
    # end, so only starts that finish inside the shift are admissible. 181-240 minutes: two 15-minute breaks
    # at least 30 minutes apart, in either order (y's window opens before x's). A 15-minute break at u and
    # the other at u + 45 are exactly 30 apart, which is admissible.
    late = BreakRequirement("late", 30, True, 60, 170)
    x, y = BreakRequirement("x", 15, True, 30, 90), BreakRequirement("y", 15, False, 0, 150)
    rules = replace(RULES, break_rules=(BreakRule(120, 180, 0, (late,)), BreakRule(181, 240, 30, (x, y))))
    generated = {as_key(p.as_shift()) for p in enumerate_patterns([A], rules, break_grid, 100_000)["patterns"]}
    assert generated == {as_key(shift) for shift in brute_single_shifts(A, rules, break_grid)}
    for breaks in exactly_apart:
        assert ("A", 480, 720, breaks) in generated
    for breaks in too_close:
        assert ("A", 480, 720, breaks) not in generated
    # A 120-minute shift from 08:00 ends at 10:00, so its 30-minute break must start by 09:30.
    lates = {dict(breaks)["late"] for _, start, end, breaks in generated if (start, end) == (480, 600)}
    assert lates and max(lates) <= 570


def test_pattern_counts_and_break_grid_by_hand():
    # Lengths 120 (starts 08, 09, 10), 180 (08, 09), and 240 (08) with the rest at offset 60-120.
    # Grid 30: rest at 09:00, 09:30, 10:00 -> 3 + 2 + 3 = 8. Grid 60: 09:00, 10:00 -> 7. Grid 1: 61 -> 66.
    counts = {grid: len(enumerate_patterns([A], RULES, grid, 10_000)["patterns"]) for grid in (1, 30, 60)}
    assert counts == {1: 66, 30: 8, 60: 7}
    rests = sorted(b.start_minute for p in enumerate_patterns([A], RULES, 60, 10_000)["patterns"] for b in p.breaks)
    assert rests == [540, 600]
    # The unpaid rest: a 240-minute pattern has 210 paid minutes and two active pieces.
    long = [p for p in enumerate_patterns([A], RULES, 30, 10_000)["patterns"] if p.end_minute - p.start_minute == 240]
    assert {p.paid_minutes for p in long} == {210}
    assert {p.active for p in long} == {((480, 540), (570, 720)), ((480, 570), (600, 720)), ((480, 600), (630, 720))}


def test_pattern_limit_stops_without_solving():
    result = solve([A, B], ALL_DAY, config=replace(CONFIG, max_patterns=15))  # 16 admissible
    assert result["status"] == PATTERN_LIMIT_EXCEEDED and result["feasibility"] == UNKNOWN
    assert result["solver"]["run"] is False and result["roster"] is None and result["labor_cost"] is None
    assert solve([A, B], ALL_DAY, config=replace(CONFIG, max_patterns=16))["status"] == OPTIMAL


def test_max_paid_minutes_matches_brute_force_with_split_shifts():
    rules = replace(RULES, shift_rules=replace(SHIFTS, min_shift_minutes=60, max_shifts_per_employee=2,
                                               min_minutes_between_shifts=60),
                    break_rules=(BreakRule(60, 180, 0, ()), BreakRule(181, 240, 0, (REST,))))
    patterns = enumerate_patterns([A], rules, 30, 10_000)["patterns"]
    singles = brute_single_shifts(A, rules, 30)
    best = 0
    for size in (1, 2):
        for combo in itertools.combinations(sorted(singles, key=as_key), size):
            if not evaluate_roster(HORIZON, [A], rules, list(combo))["violations"]:
                best = max(best, plan_minutes(combo, rules)[1])
    # Two shifts at least 60 minutes apart pay at most 180 (08:00-10:00 and 11:00-12:00), one 180-minute
    # shift pays 180, and the 240-minute shift pays 210 (its 30-minute rest is unpaid).
    assert max_paid_minutes(patterns, 2, 60) == best == 210
    assert max_paid_minutes(patterns, 1, 0) == 210


# ── 1. Exact small-instance optimum ─────────────────────────────────────────


def test_exact_optimum_by_hand():
    # One server 08:00-10:00: B works 08:00-10:00 (120 paid minutes x 40/h = 80). A would cost 120.
    result = solve([A, B], FIRST_TWO_HOURS)
    assert (result["status"], result["feasibility"]) == (OPTIMAL, FEASIBLE)
    assert shifts_of(result) == {("B", 480, 600, ())}
    assert result["labor_cost"]["total"] == 80.0
    assert result["optimality"]["proven"] is True
    assert result["optimality"]["dual_bound"] == pytest.approx(80.0, abs=1e-6)
    assert result["solver"]["status_code"] == 0 and result["solver"]["run"] is True
    assert result["verification"]["passed"] is True
    assert_matches_brute_force(result, [A, B], RULES, FIRST_TWO_HOURS, 30)


@pytest.mark.parametrize("required", [ALL_DAY, FIRST_TWO_HOURS, BOTH_ENDS,
                                      [StaffingSegment("a", 480, 600, 2), StaffingSegment("b", 600, 720, 1)]])
def test_optimum_matches_brute_force(required):
    c = Employee("C", (AvailabilityWindow(540, 720),), EmployeePay(30.0, 45.0, 120))
    employees = [A, B, c]
    assert_matches_brute_force(solve(employees, required), employees, RULES, required, 30)


# ── 2. Employee availability boundaries ─────────────────────────────────────


def test_availability_edges_are_inclusive_and_exact():
    required = [StaffingSegment("pre", 480, 540, 0), StaffingSegment("mid", 540, 660, 1),
                StaffingSegment("post", 660, 720, 0)]
    exact = Employee("C", (AvailabilityWindow(540, 660),), EmployeePay(30.0, 45.0, 480))
    # C's window is exactly 09:00-11:00, so C may work exactly 09:00-11:00 (120 x 30/h = 60).
    result = solve([A, B, exact], required)
    assert shifts_of(result) == {("C", 540, 660, ())} and result["labor_cost"]["total"] == 60.0
    # One minute less at either end and C has no admissible shift; B (80) is next cheapest.
    for window in (AvailabilityWindow(541, 660), AvailabilityWindow(540, 659)):
        narrow = replace(exact, availability=(window,))
        result = solve([A, B, narrow], required)
        assert shifts_of(result) == {("B", 540, 660, ())} and result["labor_cost"]["total"] == 80.0
        cases = {row["employee_id"]: row for row in result["model"]["labor_cases"]}
        assert cases["C"]["patterns"] == 0 and cases["C"]["labor_case"] == "NO_PATTERN"
    patterns = enumerate_patterns([exact], RULES, 30, 10_000)["patterns"]
    assert {(p.start_minute, p.end_minute) for p in patterns} == {(540, 660)}


# ── 3. Shift-length constraints ─────────────────────────────────────────────


def test_minimum_and_maximum_shift_lengths():
    one_hour = [StaffingSegment("open", 480, 540, 1), StaffingSegment("rest", 540, 720, 0)]
    # Minimum 120: one required hour still buys two (B 08:00-10:00, 80).
    result = solve([A, B], one_hour)
    assert shifts_of(result) == {("B", 480, 600, ())} and result["labor_cost"]["total"] == 80.0
    # Minimum 180: B 08:00-11:00 (120).
    longer = replace(RULES, shift_rules=replace(SHIFTS, min_shift_minutes=180))
    result = solve([A, B], one_hour, rules=longer)
    assert shifts_of(result) == {("B", 480, 660, ())} and result["labor_cost"]["total"] == 120.0
    # Maximum 180: no 240-minute pattern exists, and every rostered shift is 120-180 minutes.
    shorter = replace(RULES, shift_rules=replace(SHIFTS, max_shift_minutes=180))
    assert all(p.end_minute - p.start_minute <= 180 for p in enumerate_patterns([A], shorter, 30, 100)["patterns"])
    result = solve([A, B], ALL_DAY, rules=shorter)
    assert all(120 <= item["end_minute"] - item["start_minute"] <= 180 for item in result["roster"])
    assert_matches_brute_force(result, [A, B], shorter, ALL_DAY, 30)


# ── 4. Break constraints ────────────────────────────────────────────────────


def test_breaks_are_covered_placed_in_window_and_on_grid():
    # Only 240-minute shifts: each needs an unpaid 30-minute rest at 09:00, 09:30, or 10:00, so A and B
    # must both work and rest at different times. Cost 210 x 60/h + 210 x 40/h = 210 + 140 = 350.
    rules = replace(RULES, shift_rules=replace(SHIFTS, min_shift_minutes=240))
    result = solve([A, B], ALL_DAY, rules=rules)
    assert result["status"] == OPTIMAL and result["labor_cost"]["total"] == 350.0
    rests = [b["start_minute"] for item in result["roster"] for b in item["breaks"]]
    assert len(rests) == 2 and len(set(rests)) == 2 and set(rests) <= {540, 570, 600}
    assert result["roster_evaluation"]["coverage"]["segments"][0]["min_active_servers"] == 1
    rosters = assert_matches_brute_force(result, [A, B], rules, ALL_DAY, 30)
    assert len(rosters) == 6  # 3 x 2 ordered pairs of distinct rest starts
    # A 60-minute break grid leaves 09:00 and 10:00 only.
    coarse = solve([A, B], ALL_DAY, rules=rules, config=replace(CONFIG, break_start_granularity_minutes=60))
    assert {b["start_minute"] for item in coarse["roster"] for b in item["breaks"]} == {540, 600}


def test_one_employee_cannot_cover_their_own_break():
    # A alone: 120/180 shifts are too short and the 240 shift has a rest. Every interval can be covered by
    # some pattern, so no certificate fires; HiGHS proves the combination infeasible.
    result = solve([A], ALL_DAY)
    assert (result["status"], result["feasibility"]) == (INFEASIBLE, INFEASIBLE)
    assert [item["code"] for item in result["infeasibility_certificates"]] == ["SOLVER_PROVED_INFEASIBLE"]
    assert result["solver"]["status_code"] == 2 and result["roster"] is None and result["labor_cost"] is None
    assert_matches_brute_force(result, [A], RULES, ALL_DAY, 30)


# ── 5 and 6. Paid and unpaid time; regular and overtime cost ────────────────


def test_unpaid_and_paid_breaks():
    # A alone must work 08:00-12:00 to cover both ends; the rest falls at 09:00, 09:30, or 10:00.
    result = solve([A], BOTH_ENDS)
    assert result["labor_cost"]["employees"][0]["paid_minutes"] == 210
    assert result["labor_cost"]["total"] == 210.0  # 210 x 60/h
    assert {b["start_minute"] for item in result["roster"] for b in item["breaks"]} <= {540, 570, 600}
    assert len(assert_matches_brute_force(result, [A], RULES, BOTH_ENDS, 30)) == 3
    paid_rest = replace(RULES, break_rules=(RULES.break_rules[0], BreakRule(181, 240, 0, (replace(REST, paid=True),))))
    result = solve([A], BOTH_ENDS, rules=paid_rest)
    assert result["labor_cost"]["employees"][0]["paid_minutes"] == 240 and result["labor_cost"]["total"] == 240.0


@pytest.mark.parametrize("overtime_rate, expected", [(90.0, 255.0), (30.0, 165.0)])
def test_regular_and_overtime_cost_one_shift(overtime_rate, expected):
    # Threshold 120 on 210 paid minutes: 120 regular x 60/h = 120, plus 90 overtime x rate/h.
    # 90 x 90/h = 135 -> 255; 90 x 30/h = 45 -> 165 (an overtime rate below the regular rate).
    worker = replace(A, pay=EmployeePay(60.0, overtime_rate, 120))
    result = solve([worker], BOTH_ENDS)
    row = result["labor_cost"]["employees"][0]
    assert (row["regular_paid_minutes"], row["overtime_paid_minutes"]) == (120, 90)
    assert result["labor_cost"]["total"] == expected
    assert_matches_brute_force(result, [worker], RULES, BOTH_ENDS, 30)


SPLIT_RULES = WorkforceRules(replace(SHIFTS, min_shift_minutes=60, max_shifts_per_employee=2, min_minutes_between_shifts=60),
                             (BreakRule(60, 180, 0, ()), BreakRule(181, 240, 0, (REST,))), register_count=2)


@pytest.mark.parametrize("overtime_rate, expected", [(30.0, 105.0), (90.0, 135.0)])
def test_regular_and_overtime_with_split_shifts(overtime_rate, expected):
    # Two 60-minute shifts (08:00-09:00, 11:00-12:00; 120 min apart >= 60) pay 120 minutes. Threshold 90:
    # 90 regular x 60/h = 90, plus 30 overtime x rate/h (15 or 45). The 240 shift (210 paid) costs more.
    worker = replace(A, pay=EmployeePay(60.0, overtime_rate, 90))
    result = solve([worker], BOTH_ENDS, rules=SPLIT_RULES)
    assert shifts_of(result) == {("A", 480, 540, ()), ("A", 660, 720, ())}
    row = result["labor_cost"]["employees"][0]
    assert (row["regular_paid_minutes"], row["overtime_paid_minutes"], result["labor_cost"]["total"]) == (90, 30, expected)
    assert "model regular and overtime minutes equal the 5B-1 minutes" in result["verification"]["checks"]
    assert_matches_brute_force(result, [worker], SPLIT_RULES, BOTH_ENDS, 30)


def test_split_shift_rest_is_enforced():
    # With 150 minutes of rest required, 08:00-09:00 and 11:00-12:00 (120 apart) is not allowed, so A
    # must work the 240 shift: 90 x 60/h + 120 x 30/h = 90 + 60 = 150.
    worker = replace(A, pay=EmployeePay(60.0, 30.0, 90))
    rules = replace(SPLIT_RULES, shift_rules=replace(SPLIT_RULES.shift_rules, min_minutes_between_shifts=150))
    result = solve([worker], BOTH_ENDS, rules=rules)
    assert [(item["start_minute"], item["end_minute"]) for item in result["roster"]] == [(480, 720)]
    assert result["labor_cost"]["total"] == 150.0
    assert_matches_brute_force(result, [worker], rules, BOTH_ENDS, 30)


# ── 7. Surplus coverage ─────────────────────────────────────────────────────


def test_surplus_is_counted_and_costed_through_wages_only():
    one_hour = [StaffingSegment("open", 480, 540, 1), StaffingSegment("rest", 540, 720, 0)]
    result = solve([A, B], one_hour)
    # B works 08:00-10:00 for a 60-minute requirement: 60 surplus server-minutes, paid as wages (80).
    assert result["surplus"]["surplus_server_minutes"] == 60 and result["surplus"]["surplus_server_hours"] == 1.0
    assert result["surplus"]["active_server_minutes_in_horizon"] - result["coverage_target"]["required_server_minutes"] == 60
    assert result["labor_cost"]["total"] == 80.0
    assert "no separate surplus cost" in result["surplus"]["cost_note"]


def test_active_time_outside_the_horizon_is_not_surplus():
    # Shifts may run 07:00-13:00 and W is available then. W 07:00-09:00 (60 minutes outside the horizon)
    # and W 08:00-10:00 (60 surplus minutes) both cost 120 x 40/h = 80.
    wide = replace(RULES, shift_rules=replace(SHIFTS, earliest_start_minute=420, latest_end_minute=780))
    early = Employee("W", (AvailabilityWindow(420, 780),), EmployeePay(40.0, 60.0, 480))
    one_hour = [StaffingSegment("open", 480, 540, 1), StaffingSegment("rest", 540, 720, 0)]
    result = solve([A, early], one_hour, rules=wide)
    surplus = result["surplus"]
    assert result["labor_cost"]["total"] == 80.0
    assert surplus["surplus_server_minutes"] + surplus["active_server_minutes_outside_horizon"] == 60
    rosters = assert_matches_brute_force(result, [A, early], wide, one_hour, 30)
    assert rosters == {frozenset({("W", 420, 540, ())}), frozenset({("W", 480, 600, ())})}


def test_nothing_is_required_outside_the_horizon():
    # Shifts may run 07:00-13:00, but the requirement ends at 12:00 (closing): W 10:00-12:00 (120 x 40/h = 80)
    # is optimal and unique. Requiring cover after closing would force a longer, dearer shift.
    wide = replace(RULES, shift_rules=replace(SHIFTS, earliest_start_minute=420, latest_end_minute=780))
    early = Employee("W", (AvailabilityWindow(420, 780),), EmployeePay(40.0, 60.0, 480))
    required = [StaffingSegment("open", 480, 600, 0), StaffingSegment("close", 600, 720, 1)]
    result = solve([early], required, rules=wide)
    assert shifts_of(result) == {("W", 600, 720, ())} and result["labor_cost"]["total"] == 80.0
    assert assert_matches_brute_force(result, [early], wide, required, 30) == {frozenset({("W", 600, 720, ())})}


# ── 8. Insufficient workforce ───────────────────────────────────────────────


def test_insufficient_workforce_certificate():
    late = Employee("C", (AvailabilityWindow(600, 720),), EmployeePay(30.0, 45.0, 480))
    two = [StaffingSegment("day", 480, 720, 2)]
    result = solve([A, late], two)
    assert (result["status"], result["feasibility"]) == (INFEASIBLE, INFEASIBLE)
    assert result["solver"]["run"] is False
    certificate = result["infeasibility_certificates"]
    assert [item["code"] for item in certificate] == ["INSUFFICIENT_WORKFORCE"]
    # Before 10:00 only A can be active; the elementary intervals merge into one row.
    assert certificate[0]["intervals"] == [
        {"start_minute": 480, "end_minute": 600, "required_servers": 2, "max_possible_active": 1}]
    assert_matches_brute_force(result, [A, late], RULES, two, 30)


# ── 9. Physical register limits ─────────────────────────────────────────────


def test_requirement_above_registers_is_a_certificate():
    result = solve([A, B], [StaffingSegment("day", 480, 720, 3)])
    assert result["status"] == INFEASIBLE and result["solver"]["run"] is False
    certificate = result["infeasibility_certificates"][0]
    assert certificate["code"] == "REQUIREMENT_EXCEEDS_REGISTERS" and certificate["register_count"] == 2
    assert certificate["segments"] == [{"segment_id": "day", "start_minute": 480, "end_minute": 720, "required_servers": 3}]


def test_register_limit_binds():
    # Shifts of 180-240 minutes: covering 08:00-12:00 needs two employees who overlap while both active,
    # so one register makes it infeasible (proved by HiGHS) and two registers allow it.
    rules = replace(RULES, shift_rules=replace(SHIFTS, min_shift_minutes=180))
    one = solve([A, B], ALL_DAY, rules=replace(rules, register_count=1))
    assert one["status"] == INFEASIBLE and one["solver"]["status_code"] == 2
    assert_matches_brute_force(one, [A, B], replace(rules, register_count=1), ALL_DAY, 30)
    two = solve([A, B], ALL_DAY, rules=rules)
    assert two["status"] == OPTIMAL and two["roster_evaluation"]["register_check"]["max_active_servers"] == 2
    assert_matches_brute_force(two, [A, B], rules, ALL_DAY, 30)


# ── 10. Multiple optimal solutions ──────────────────────────────────────────


def test_multiple_optima_are_not_presented_as_unique():
    # One server all day: two 120-minute shifts, one by B (80) and one by A (120) = 200, in either order.
    result = solve([A, B], ALL_DAY)
    rosters = assert_matches_brute_force(result, [A, B], RULES, ALL_DAY, 30)
    assert rosters == {frozenset({("B", 480, 600, ()), ("A", 600, 720, ())}),
                       frozenset({("A", 480, 600, ()), ("B", 600, 720, ())})}
    assert result["labor_cost"]["total"] == 200.0
    assert result["uniqueness"] == "NOT_ESTABLISHED" and "Other rosters" in result["uniqueness_note"]


# ── 11. Missing required inputs ─────────────────────────────────────────────


def test_missing_rate_needed_by_the_objective_stops_the_run():
    unpriced = replace(B, pay=EmployeePay(None, 60.0, 480))
    result = solve([A, unpriced], ALL_DAY)
    assert (result["status"], result["feasibility"]) == (INCOMPLETE, UNKNOWN)
    assert [(m["employee_id"], m["field"]) for m in result["missing"]] == [("B", "regular_rate_per_hour")]
    assert result["solver"]["run"] is False and result["labor_cost"] is None and result["roster"] is None


def test_overtime_rate_is_required_only_when_overtime_is_possible():
    # A's longest plan pays 210 minutes. With a 210 threshold no overtime is possible: no overtime rate needed.
    no_overtime = replace(A, pay=EmployeePay(60.0, None, 210))
    result = solve([no_overtime], BOTH_ENDS)
    assert result["status"] == OPTIMAL and result["labor_cost"]["total"] == 210.0
    # With 209, one overtime minute is possible, so the missing overtime rate stops the run.
    result = solve([replace(A, pay=EmployeePay(60.0, None, 209))], BOTH_ENDS)
    assert result["status"] == INCOMPLETE
    assert [m["field"] for m in result["missing"]] == ["overtime_rate_per_hour"]
    assert "210 paid minutes, above the 209-minute threshold" in result["missing"][0]["reason"]


def test_missing_threshold_and_unschedulable_employees():
    result = solve([replace(A, pay=EmployeePay(None, None, None))], BOTH_ENDS)
    assert result["status"] == INCOMPLETE
    assert [m["field"] for m in result["missing"]] == [
        "daily_regular_paid_minutes", "regular_rate_per_hour", "overtime_rate_per_hour"]
    # A threshold of 0 makes every paid minute overtime: only the overtime rate is needed.
    result = solve([replace(A, pay=EmployeePay(None, 30.0, 0))], BOTH_ENDS)
    assert result["status"] == OPTIMAL and result["labor_cost"]["total"] == 105.0  # 210 x 30/h
    # An employee who can never be scheduled needs no pay values.
    absent = Employee("Z", (AvailabilityWindow(0, 60),), EmployeePay(None, None, None))
    assert solve([A, B, absent], ALL_DAY)["status"] == OPTIMAL


def test_missing_break_rule_for_an_admissible_length():
    gap = replace(RULES, break_rules=(BreakRule(120, 180, 0, ()),))  # 240-minute shifts have no rule
    result = solve([A, B], ALL_DAY, rules=gap)
    assert result["status"] == INCOMPLETE and result["solver"]["run"] is False
    assert {(m["employee_id"], m["field"]) for m in result["missing"]} == {("A", "break_rules"), ("B", "break_rules")}
    assert "240-minute shift" in result["missing"][0]["reason"]


def test_malformed_inputs_are_rejected():
    with pytest.raises(SharedSegmentError) as caught:
        solve([A], ALL_DAY, config=RosterOptimizationConfig(0, -1.0, -0.1, 0))  # type: ignore[arg-type]
    assert caught.value.problems == [
        "break_start_granularity_minutes must be a whole number from 1 to 1440.",
        "time_limit_seconds must be a finite number above 0, or None for no limit.",
        "mip_rel_gap must be a finite number, 0 or more.",
        "max_patterns must be a whole number, 1 or more.",
    ]
    with pytest.raises(SharedSegmentError, match="config must be a RosterOptimizationConfig"):
        solve([A], ALL_DAY, config=None)  # type: ignore[arg-type]
    with pytest.raises(SharedSegmentError, match="coverage target"):
        solve([A], None)  # type: ignore[arg-type]
    with pytest.raises(SharedSegmentError, match="tile the operating horizon"):
        solve([A], [StaffingSegment("day", 480, 700, 1)])
    with pytest.raises(SharedSegmentError, match="Duplicate employee ids"):
        solve([A, A], ALL_DAY)
    assert solve([A, B], ALL_DAY, config=replace(CONFIG, time_limit_seconds=None))["status"] == OPTIMAL


# ── 12. Solver infeasibility and non-optimal termination ────────────────────


def patched(monkeypatch, status: int, *, keep_x: bool = True, change=None) -> None:
    """Run the real solver, then report a different termination (a simulated limit or error)."""
    def run(*args, **kwargs):
        response = real_milp(*args, **kwargs)
        response.status, response.message = status, f"SIMULATED status {status}"
        if not keep_x:
            response.x = None
        elif change is not None:
            response.x = change(np.array(response.x))
        return response
    monkeypatch.setattr(shared_rostering, "milp", run)


def test_limit_with_incumbent_is_feasible_but_not_proven_optimal(monkeypatch):
    patched(monkeypatch, 1)
    result = solve([A, B], FIRST_TWO_HOURS)
    assert (result["status"], result["feasibility"]) == (FEASIBLE_NOT_PROVEN_OPTIMAL, FEASIBLE)
    assert result["optimality"]["proven"] is False and "not proven optimal" in result["optimality"]["basis"]
    assert result["verification"]["passed"] is True and result["labor_cost"]["total"] == 80.0


def test_limit_without_incumbent_leaves_feasibility_unknown(monkeypatch):
    patched(monkeypatch, 1, keep_x=False)
    result = solve([A, B], FIRST_TWO_HOURS)
    assert (result["status"], result["feasibility"]) == (NO_SOLUTION_FOUND, UNKNOWN)
    assert result["roster"] is None and result["labor_cost"] is None and result["optimality"] is None


@pytest.mark.parametrize("status", [3, 4])
def test_solver_error(monkeypatch, status):
    patched(monkeypatch, status)
    result = solve([A, B], FIRST_TWO_HOURS)
    assert (result["status"], result["feasibility"]) == (SOLVER_ERROR, UNKNOWN)
    assert result["solver"]["message"] == f"SIMULATED status {status}" and result["roster"] is None


def test_verification_rejects_a_fractional_vector(monkeypatch):
    def nudge(x):
        x[0] += 0.3
        return x
    patched(monkeypatch, 0, change=nudge)
    result = solve([A, B], FIRST_TWO_HOURS)
    assert (result["status"], result["feasibility"]) == (VERIFICATION_FAILED, UNKNOWN)
    assert "from an integer" in result["verification"]["failure"] and result["labor_cost"] is None


def test_verification_rejects_a_vector_with_a_shortfall(monkeypatch):
    patched(monkeypatch, 0, change=np.zeros_like)
    result = solve([A, B], FIRST_TWO_HOURS)
    assert result["status"] == VERIFICATION_FAILED and result["feasibility"] == UNKNOWN
    assert result["verification"]["failure"] == "The rounded vector breaks a model constraint."


def test_verification_rejects_a_model_cost_that_disagrees_with_5b1(monkeypatch):
    # Scaling every cost by 1.5 keeps B 08:00-10:00 optimal, but the model says 120 where 5B-1 minutes give 80.
    real_build = shared_rostering._build_model

    def build(*args, **kwargs):
        model = real_build(*args, **kwargs)
        model["objective"] = model["objective"] * 1.5
        return model
    monkeypatch.setattr(shared_rostering, "_build_model", build)
    result = solve([A, B], FIRST_TWO_HOURS)
    assert (result["status"], result["feasibility"]) == (VERIFICATION_FAILED, UNKNOWN)
    assert result["verification"]["failure"] == (
        "Labor cost from the 5B-1 minutes (80.0) differs from the model objective (120.0).")


def test_verification_rejects_a_shortfall_the_model_missed(monkeypatch):
    # With the coverage rows relaxed, the empty roster is "optimal" for the broken model; 5B-1 finds the gap.
    real_build = shared_rostering._build_model

    def build(*args, **kwargs):
        model = real_build(*args, **kwargs)
        model["row_lb"] = np.minimum(model["row_lb"], 0.0)
        return model
    monkeypatch.setattr(shared_rostering, "_build_model", build)
    result = solve([A, B], FIRST_TWO_HOURS)
    assert result["status"] == VERIFICATION_FAILED and result["feasibility"] == UNKNOWN
    assert result["verification"]["failure"] == "The 5B-1 evaluation found a coverage shortfall."
    assert result["roster"] == []


def test_verification_rejects_a_roster_that_5b1_finds_invalid(monkeypatch):
    # A pattern outside C's availability is slipped into the model; the solver picks it (60 < 80), and the
    # independent 5B-1 evaluation rejects the roster.
    late = Employee("C", (AvailabilityWindow(600, 720),), EmployeePay(30.0, 45.0, 480))
    real_enumerate = shared_rostering.enumerate_patterns

    def enumerate_with_intruder(*args, **kwargs):
        generated = real_enumerate(*args, **kwargs)
        intruder = shared_rostering.RosterPattern("C", 480, 600, (), ((480, 600),), 120)
        return {**generated, "patterns": [*generated["patterns"], intruder]}
    monkeypatch.setattr(shared_rostering, "enumerate_patterns", enumerate_with_intruder)
    result = solve([A, B, late], FIRST_TWO_HOURS)
    assert result["status"] == VERIFICATION_FAILED
    assert result["verification"]["failure"] == "The 5B-1 evaluation found violations: OUTSIDE_AVAILABILITY."
    assert shifts_of(result) == {("C", 480, 600, ())} and result["labor_cost"] is None


# ── Phase 2 coverage target ─────────────────────────────────────────────────


def test_phase2_selection_is_the_coverage_target():
    periods = [DemandPeriod("am", 480, 600, 6.0, 4.0), DemandPeriod("pm", 600, 720, 3.0, 4.0)]
    current = [StaffingSegment("am", 480, 600, 1), StaffingSegment("pm", 600, 720, 1)]
    plan = optimize_shared_capacity(HORIZON, periods, current, CapacityConfig(
        server_cost_per_hour=50.0, waiting_cost_per_customer_hour=20.0, target_utilization=0.9,
        min_servers=0, max_servers=2))
    selected = [(row["segment_id"], row["selected"]["servers"]) for row in plan["segments"]]
    # am: λ 6, μ 4 -> ρ ≤ 0.9 needs 2 servers (the maximum); pm: λ 3 -> 1 or 2, chosen by cost.
    assert selected[0] == ("am", 2)
    c = Employee("C", (AvailabilityWindow(480, 720),), EmployeePay(50.0, 75.0, 480))
    employees = [A, B, c]
    result = optimize_roster_for_capacity_plan(HORIZON, employees, RULES, plan, config=CONFIG)
    target = [(item["segment_id"], item["servers"]) for item in result["coverage_target"]["segments"]]
    assert target == selected and result["coverage_target"]["source"].startswith("Phase 2 capacity plan")
    required = [StaffingSegment(item["segment_id"], item["start_minute"], item["end_minute"], item["servers"])
                for item in result["coverage_target"]["segments"]]
    assert_matches_brute_force(result, employees, RULES, required, 30)
    with pytest.raises(SharedSegmentError, match="not the given horizon"):
        optimize_roster_for_capacity_plan(OperatingHorizon(480, 700), employees, RULES, plan, config=CONFIG)


# ── Seeded random instances against the brute force ────────────────────────


RANDOM_SEEDS = 40


def random_instance(seed: int):
    rng = random.Random(seed)
    rest = replace(REST, paid=rng.random() < 0.5)
    shifts = replace(SHIFTS, min_shift_minutes=rng.choice([60, 120]), max_shift_minutes=rng.choice([180, 240]))
    if rng.random() < 0.4:
        shifts = replace(shifts, max_shifts_per_employee=2, min_minutes_between_shifts=rng.choice([0, 60]))
    required = [StaffingSegment("a", 480, 600, rng.randint(1, 2)), StaffingSegment("b", 600, 720, rng.randint(0, 2))]
    # Registers never below the requirement here (that certificate has its own test), but often binding.
    registers = rng.randint(max(segment.servers for segment in required), 3)
    rules = WorkforceRules(shifts, (BreakRule(shifts.min_shift_minutes, 180, 0, ()), BreakRule(181, 240, 0, (rest,))),
                           register_count=registers)
    employees = []
    # Split shifts multiply the plans per employee, so those instances keep two employees for the brute force.
    for index in range(2 if shifts.max_shifts_per_employee == 2 else rng.randint(2, 3)):
        start, end = rng.choice([480, 480, 540]), rng.choice([660, 720, 720])
        employees.append(Employee(f"E{index}", (AvailabilityWindow(start, end),), EmployeePay(
            float(rng.randint(20, 80)), float(rng.randint(10, 120)), rng.choice([60, 90, 120, 150, 480]))))
    return employees, rules, required, rng.choice([30, 60])


@pytest.mark.parametrize("seed", range(RANDOM_SEEDS))
def test_random_instances_match_brute_force(seed):
    employees, rules, required, grid = random_instance(seed)
    config = replace(CONFIG, break_start_granularity_minutes=grid)
    result = solve(employees, required, rules=rules, config=config)
    assert_matches_brute_force(result, employees, rules, required, grid)
    if result["status"] == OPTIMAL:
        evaluation = evaluate_roster(HORIZON, employees, rules,
                                     [ScheduledShift(i["employee_id"], i["start_minute"], i["end_minute"],
                                                     tuple(ScheduledBreak(b["name"], b["start_minute"]) for b in i["breaks"]))
                                      for i in result["roster"]], required_staffing=required)
        assert evaluation["violations"] == [] and evaluation["coverage"]["fully_covered"]


def test_random_instances_cover_every_outcome():
    # Guards the generator: the brute-force comparison above must see optima, both kinds of infeasibility,
    # overtime (also at a rate below the regular rate), binding registers, and split shifts.
    seen = set()
    for seed in range(RANDOM_SEEDS):
        employees, rules, required, grid = random_instance(seed)
        result = solve(employees, required, rules=rules, config=replace(CONFIG, break_start_granularity_minutes=grid))
        seen |= {result["status"]} | {item["code"] for item in result["infeasibility_certificates"]}
        rows = (result["labor_cost"] or {}).get("employees", [])
        pay = {employee.employee_id: employee.pay for employee in employees}
        if any(row["overtime_paid_minutes"] for row in rows):
            seen.add("overtime")
        if any(row["overtime_paid_minutes"] and pay[row["employee_id"]].overtime_rate_per_hour
               < pay[row["employee_id"]].regular_rate_per_hour for row in rows):
            seen.add("overtime_below_regular")
        if result["status"] == OPTIMAL and (result["roster_evaluation"]["register_check"]["max_active_servers"]
                                            == rules.register_count):
            seen.add("registers_binding")
        if rules.shift_rules.max_shifts_per_employee == 2 and result["status"] == OPTIMAL:
            seen.add("split_shift_rules")
    assert seen >= {OPTIMAL, INFEASIBLE, "INSUFFICIENT_WORKFORCE", "SOLVER_PROVED_INFEASIBLE", "overtime",
                    "overtime_below_regular", "registers_binding", "split_shift_rules"}


# ── Output and provenance ───────────────────────────────────────────────────


def test_solver_provenance_and_tolerances():
    result = solve([A, B], FIRST_TWO_HOURS)
    solver = result["solver"]
    assert solver["name"] == "HiGHS via scipy.optimize.milp"
    assert solver["options"] == {"presolve": True, "mip_rel_gap": 0.0, "time_limit_seconds": 60.0}
    for key in ("status_code", "message", "objective", "dual_bound", "mip_gap", "node_count", "wall_seconds"):
        assert key in solver
    defaults = solver["unchanged_highs_defaults"]
    if defaults is not None:  # read from HiGHS at run time; None only when its options cannot be read
        assert defaults["mip_feasibility_tolerance"] == INTEGRALITY_TOLERANCE
    assert result["provenance"]["optimizer_version"] == "novaq-shared-sequential-rostering-v1"
    assert result["model"]["patterns"] == 16 and result["model"]["variables"] == 16
    assert "not simulated" in result["scope"] and "break grid" in result["scope"]


def test_same_inputs_give_the_same_answer():
    first, second = solve([A, B], ALL_DAY), solve([A, B], ALL_DAY)
    assert first["roster"] == second["roster"] and first["labor_cost"] == second["labor_cost"]
