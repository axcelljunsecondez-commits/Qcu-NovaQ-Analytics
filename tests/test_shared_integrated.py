"""Phase 5B-3 integrated shared-queue planning MILP.

ALL EMPLOYEES, AVAILABILITY, RULES, RATES, AND DEMAND IN THIS FILE ARE SYNTHETIC TEST DATA. They
are not NovaMart records, labor law, or recommended operating values.

Expected optima are computed by hand in the comments, and are also checked against an independent
brute force. The brute force enumerates every shift and break placement with plain minute loops
(the 5B-2 test helpers), accepts a plan only when the 5B-1 ``evaluate_roster`` finds no violation,
counts the employees on duty minute by minute, prices waiting with the independent Erlang-B
recursion of the Phase 1 tests (not the module's Phase 1/2 path), and prices wages from the paid
minutes it computes itself.
"""

from __future__ import annotations

import copy
import itertools
import math
import random
from dataclasses import replace

import numpy as np
import pytest
from scipy.optimize import milp as real_milp

from backend.queueing_engine.services import shared_integrated
from backend.queueing_engine.services.shared_capacity import CapacityConfig
from backend.queueing_engine.services.shared_integrated import (
    PlanningConfig,
    compare_with_sequential,
    evaluate_planning_cost,
    optimize_integrated_plan,
    validate_planning_config,
)
from backend.queueing_engine.services.shared_rostering import (
    FEASIBLE,
    FEASIBLE_NOT_PROVEN_OPTIMAL,
    INCOMPLETE,
    INFEASIBLE,
    NO_SOLUTION_FOUND,
    OPTIMAL,
    PATTERN_LIMIT_EXCEEDED,
    SOLVER_ERROR,
    UNKNOWN,
    VERIFICATION_FAILED,
    RosterPattern,
)
from backend.queueing_engine.services.shared_segments import (
    MINUTES_PER_DAY,
    DemandPeriod,
    SharedSegmentError,
    StaffingSegment,
)
from backend.queueing_engine.services.shared_workforce import (
    AvailabilityWindow,
    BreakRule,
    Employee,
    EmployeePay,
    ScheduledBreak,
    ScheduledShift,
    WorkforceRules,
    evaluate_roster,
)
from tests.test_shared_rostering import (
    CONFIG,
    HORIZON,
    REST,
    RULES,
    SHIFTS,
    A,
    B,
    as_key,
    brute_single_shifts,
    plan_cost,
    plan_minutes,
)
from tests.test_shared_segments import erlang_reference

# ── SYNTHETIC TEST DATA ──────────────────────────────────────────────────────
# HORIZON 08:00-12:00; shifts of 120-240 minutes on the hour; a 30-minute unpaid rest 60-120 minutes
# into shifts over 180 minutes; 2 registers; A earns 60/h, B 40/h (from the 5B-2 tests).

STEADY = [DemandPeriod("steady", 480, 720, 2.0, 3.0)]  # lambda 2/h, mu 3/h
ONE_SEGMENT = [StaffingSegment("day", 480, 720, 1)]
PLANNING = PlanningConfig(waiting_cost_per_customer_hour=10.0, target_utilization=0.9, max_wait_minutes=None,
                          min_servers=0, max_servers=2)
C = Employee("C", (AvailabilityWindow(480, 720),), EmployeePay(50.0, 75.0, 480))

# Independent M/M/c values for lambda = 2, mu = 3 (hand check: M/M/1 Wq = lambda/(mu(mu - lambda)) = 2/3 h;
# M/M/2: a = 2/3, rho = 1/3, P(wait) = 1/6, Lq = 1/12, Wq = 1/24 h).
WQ1, WQ2 = 2 / 3, 1 / 24


def solve(employees, demand=STEADY, segments=ONE_SEGMENT, rules=RULES, planning=PLANNING, config=CONFIG,
          horizon=HORIZON) -> dict:
    return optimize_integrated_plan(horizon, demand, segments, employees, rules, planning=planning, config=config)


def roster_of(rows) -> list[ScheduledShift]:
    return [ScheduledShift(row["employee_id"], row["start_minute"], row["end_minute"],
                           tuple(ScheduledBreak(item["name"], item["start_minute"]) for item in row["breaks"]))
            for row in rows]


def key_of(result: dict) -> frozenset:
    return frozenset(as_key(shift) for shift in roster_of(result["roster"]))


# ── Independent brute force ─────────────────────────────────────────────────


def waiting_table(demand, planning, registers, horizon=HORIZON) -> np.ndarray:
    """Waiting cost per clock minute for each on-duty count; inf where the count is not admissible."""
    table = np.full((registers + 1, MINUTES_PER_DAY), np.inf)
    for period in demand:
        lam, mu = period.arrival_rate_per_hour, period.service_rate_per_hour
        start, end = max(period.start_minute, horizon.start_minute), min(period.end_minute, horizon.end_minute)
        if start >= end:
            continue
        for count in range(registers + 1):
            if not planning.min_servers <= count <= planning.max_servers:
                continue
            if lam == 0:
                per_minute = 0.0  # no arrivals: closed (count 0) or idle, nothing waits
            elif count == 0 or lam >= count * mu:
                continue  # no server, or unstable
            else:
                reference = erlang_reference(lam, mu, count)
                if reference["rho"] > planning.target_utilization + 1e-9:
                    continue
                if planning.max_wait_minutes is not None and reference["Wq"] * 60 > planning.max_wait_minutes + 1e-9:
                    continue
                per_minute = lam * reference["Wq"] / 60 * planning.waiting_cost_per_customer_hour
            table[count, start:end] = per_minute
    return table


def employee_plans(employee, rules, break_grid, horizon=HORIZON):
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
    return rows


def price(total: np.ndarray, labor: float, table: np.ndarray, registers: int, horizon=HORIZON) -> float | None:
    """Planning cost of on-duty counts per minute, or None when the plan is outside the feasible set."""
    if total.max(initial=0) > registers:
        return None
    minutes = np.arange(horizon.start_minute, horizon.end_minute)
    waiting = table[total[minutes], minutes]
    if np.isinf(waiting).any():
        return None
    return labor + math.fsum(waiting)


def brute_force(employees, rules, demand, planning, break_grid, horizon=HORIZON):
    """The minimum planning cost, the rosters within 1e-6 of it, and the rosters that tie it within 1e-9."""
    table = waiting_table(demand, planning, rules.register_count, horizon)
    per_employee = [employee_plans(employee, rules, break_grid, horizon) for employee in employees]
    priced = []
    for choice in itertools.product(*per_employee):
        total = sum((active for _, active, _ in choice), np.zeros(MINUTES_PER_DAY, dtype=np.int64))
        cost = price(total, math.fsum(cost for _, _, cost in choice), table, rules.register_count, horizon)
        if cost is not None:
            priced.append((cost, frozenset(as_key(shift) for plan, _, _ in choice for shift in plan)))
    if not priced:
        return None, set(), set()
    best = min(cost for cost, _ in priced)
    near = {key for cost, key in priced if cost <= best + 1e-6}
    tied = {key for cost, key in priced if cost - best <= 1e-9 * max(1.0, abs(best))}
    return best, near, tied


def independent_cost(result_roster, employees, rules, demand, planning, horizon=HORIZON):
    """Planning cost of a returned roster, recomputed minute by minute without the module."""
    table = waiting_table(demand, planning, rules.register_count, horizon)
    by_id = {employee.employee_id: employee for employee in employees}
    total = np.zeros(MINUTES_PER_DAY, dtype=np.int64)
    labor = []
    for who in by_id:
        plan = [shift for shift in result_roster if shift.employee_id == who]
        active, paid = plan_minutes(plan, rules)
        total += active
        labor.append(plan_cost(by_id[who], paid))
    return price(total, math.fsum(labor), table, rules.register_count, horizon), total, math.fsum(labor)


def assert_matches_brute_force(result, employees, rules, demand, planning, break_grid, horizon=HORIZON):
    best, near, tied = brute_force(employees, rules, demand, planning, break_grid, horizon)
    if best is None:
        assert (result["status"], result["feasibility"]) == (INFEASIBLE, INFEASIBLE)
        assert result["roster"] is None and result["planning_cost"] is None
        return best, tied
    assert (result["status"], result["feasibility"]) == (OPTIMAL, FEASIBLE)
    # HiGHS stops within its unchanged absolute gap (1e-6) of the optimum.
    assert result["planning_cost"]["total"] == pytest.approx(best, abs=1e-6)
    assert key_of(result) in near
    cost, total, labor = independent_cost(roster_of(result["roster"]), employees, rules, demand, planning, horizon)
    assert cost == pytest.approx(result["planning_cost"]["total"], rel=1e-9, abs=1e-12)
    assert labor == pytest.approx(result["planning_cost"]["labor_cost"], rel=1e-9, abs=1e-12)
    for row in result["capacity"]["capacity"]:  # the priced count is the on-duty count, minute by minute
        assert set(total[row["start_minute"]:row["end_minute"]]) == {row["active_servers"]}
    return best, tied


# ── Configuration ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("change, message", [
    ({"waiting_cost_per_customer_hour": -1.0}, "Waiting cost"),
    ({"waiting_cost_per_customer_hour": math.nan}, "Waiting cost"),
    ({"target_utilization": 0.0}, "Target utilization"),
    ({"target_utilization": 1.2}, "Target utilization"),
    ({"max_wait_minutes": -5.0}, "Maximum wait"),
    ({"min_servers": 3, "max_servers": 2}, "must not exceed"),
    ({"max_servers": 257}, "Maximum servers"),
    ({"min_servers": True}, "Minimum servers"),
])
def test_planning_config_rejects_bad_values(change, message):
    with pytest.raises(SharedSegmentError) as error:
        validate_planning_config(replace(PLANNING, **change))
    assert message in " | ".join(error.value.problems)


def test_planning_config_has_no_defaults_and_no_server_charge():
    with pytest.raises(TypeError):
        PlanningConfig()  # type: ignore[call-arg]
    assert not any("server_cost" in name for name in PlanningConfig.__dataclass_fields__)


# ── Hand-computed optimum, multiple optima, and the objective ───────────────


def test_hand_computed_optimum_has_two_optimal_rosters():
    # One server all morning: two 2-hour shifts without breaks, wages 2 x 60 + 2 x 40 = 200 in either order.
    # Waiting at one server: lambda Wq T = 2 x 2/3 x 4 = 16/3 customer-hours, x 10 = 160/3.
    # Covering a 4-hour shift's break or overlapping costs more (hand check: B 4 h + A 2 h = 260 in wages alone).
    result = solve([A, B])
    best, tied = assert_matches_brute_force(result, [A, B], RULES, STEADY, PLANNING, 30)
    assert best == pytest.approx(200 + 160 / 3, rel=1e-12)
    assert result["planning_cost"]["labor_cost"] == 200.0
    assert result["planning_cost"]["waiting_cost"] == pytest.approx(160 / 3, rel=1e-12)
    assert tied == {
        frozenset({("A", 480, 600, ()), ("B", 600, 720, ())}),
        frozenset({("B", 480, 600, ()), ("A", 600, 720, ())}),
    }
    assert key_of(result) in tied
    assert result["uniqueness"] == "NOT_ESTABLISHED"


def test_objective_is_wages_plus_waiting_with_no_server_charge():
    result = solve([A, B])
    cost = result["planning_cost"]
    assert cost["total"] == pytest.approx(cost["labor_cost"] + cost["waiting_cost"], rel=1e-12)
    assert "server cost" in cost["excluded"]
    assert result["labor_cost"]["total"] == cost["labor_cost"]
    assert sum(row["labor_cost"] for row in result["labor_cost"]["employees"]) == cost["labor_cost"]
    assert result["optimality"]["verified_objective"] == cost["total"]
    assert result["optimality"]["model_objective_at_rounded_vector"] == pytest.approx(cost["total"], rel=1e-9)
    assert result["solver"]["objective"] == pytest.approx(cost["total"], rel=1e-9)


def test_staffing_segment_server_counts_are_ignored():
    # The segments only group the report: the priced count is the on-duty count.
    base = solve([A, B])
    for servers in (0, 2, 7):
        other = solve([A, B], segments=[StaffingSegment("day", 480, 720, servers)])
        assert other["planning_cost"]["total"] == base["planning_cost"]["total"]


# ── Waiting at the on-duty count, over each interval's own length ───────────


def test_break_dip_and_surplus_are_priced_at_the_on_duty_count():
    # A 08:00-12:00 with the rest 09:00-09:30, B 08:00-10:00. On duty: 2 (08:00-09:00), 1 (09:00-09:30, A on
    # break), 2 (09:30-10:00), 1 (10:00-12:00). Waiting customer-hours: two servers for 1.5 h -> 2 x 1/24 x 1.5
    # = 0.125; one server for 2.5 h -> 2 x 2/3 x 2.5 = 10/3. Wages: A 3.5 paid h x 60 = 210, B 2 h x 40 = 80.
    roster = [ScheduledShift("A", 480, 720, (ScheduledBreak("rest", 540),)), ScheduledShift("B", 480, 600, ())]
    result = evaluate_planning_cost(HORIZON, STEADY, ONE_SEGMENT, [A, B], RULES, roster, planning=PLANNING,
                                    break_start_granularity_minutes=30)
    hours = 2 * WQ2 * 1.5 + 2 * WQ1 * 2.5
    assert result["in_integrated_feasible_set"] is True
    assert [(row["start_minute"], row["end_minute"], row["active_servers"]) for row in result["capacity"]] == [
        (480, 540, 2), (540, 570, 1), (570, 600, 2), (600, 720, 1)]
    assert result["capacity"][1]["waiting_cost"] == pytest.approx(2 * WQ1 * 0.5 * 10, rel=1e-12)
    assert result["waiting_cost"]["expected_waiting_customer_hours"] == pytest.approx(hours, rel=1e-12)
    assert result["waiting_cost"]["total"] == pytest.approx(10 * hours, rel=1e-12)
    assert result["labor_cost"]["total"] == 290.0
    assert result["planning_cost"] == pytest.approx(290 + 10 * hours, rel=1e-12)
    assert result["server_minutes_above_smallest_admissible"] == 90  # the second server for 1.5 h
    assert result["capacity_by_staffing_segment"][0]["server_minutes"] == 60 * 2 + 30 + 30 * 2 + 120


def test_surplus_employee_lowers_waiting_and_is_paid():
    # Three on duty 08:00-10:00 where one would do: all three are paid and all three staff the queue.
    roster = [ScheduledShift("A", 480, 600, ()), ScheduledShift("B", 480, 600, ()),
              ScheduledShift("C", 480, 600, ()), ScheduledShift("B", 600, 720, ())]
    rules = replace(RULES, register_count=3, shift_rules=replace(SHIFTS, max_shifts_per_employee=2,
                                                                 min_minutes_between_shifts=0))
    planning = replace(PLANNING, max_servers=3)
    result = evaluate_planning_cost(HORIZON, STEADY, ONE_SEGMENT, [A, B, C], rules, roster, planning=planning,
                                    break_start_granularity_minutes=30)
    wq3 = erlang_reference(2.0, 3.0, 3)["Wq"]
    assert result["in_integrated_feasible_set"] is True
    assert result["capacity"][0]["active_servers"] == 3
    assert result["waiting_cost"]["total"] == pytest.approx(10 * (2 * wq3 * 2 + 2 * WQ1 * 2), rel=1e-12)
    assert result["labor_cost"]["total"] == 120 + 80 + 100 + 80
    assert result["server_minutes_above_smallest_admissible"] == 2 * 120


def test_count_above_the_maximum_is_outside_the_feasible_set_but_still_priced():
    roster = [ScheduledShift("A", 480, 600, ()), ScheduledShift("B", 480, 720, (ScheduledBreak("rest", 570),))]
    result = evaluate_planning_cost(HORIZON, STEADY, ONE_SEGMENT, [A, B], RULES, roster,
                                    planning=replace(PLANNING, max_servers=1), break_start_granularity_minutes=30)
    assert result["in_integrated_feasible_set"] is False
    assert any("not admissible" in reason for reason in result["feasible_set_reasons"])
    assert result["capacity"][0]["violations"] == ["server_bounds"]
    assert result["planning_cost"] is not None  # priced, and flagged


def test_zero_on_duty_with_arrivals_leaves_waiting_undefined():
    roster = [ScheduledShift("A", 480, 600, ())]  # nobody after 10:00
    result = evaluate_planning_cost(HORIZON, STEADY, ONE_SEGMENT, [A], RULES, roster, planning=PLANNING,
                                    break_start_granularity_minutes=30)
    assert result["in_integrated_feasible_set"] is False
    assert result["capacity"][-1]["status"] == "NO_CAPACITY" and result["capacity"][-1]["waiting_cost"] is None
    assert result["waiting_cost"] is None and result["planning_cost"] is None
    assert result["labor_cost"]["total"] == 120.0


def test_count_above_the_registers_is_flagged_on_its_stretch():
    roster = [ScheduledShift("A", 480, 600, ()), ScheduledShift("B", 480, 600, ()), ScheduledShift("C", 480, 720, (
        ScheduledBreak("rest", 600),))]
    result = evaluate_planning_cost(HORIZON, STEADY, ONE_SEGMENT, [A, B, C], RULES, roster,
                                    planning=replace(PLANNING, max_servers=3), break_start_granularity_minutes=30)
    first = result["capacity"][0]
    assert (first["active_servers"], first["admissible"], first["violations"]) == (3, False, ["registers"])
    assert result["in_integrated_feasible_set"] is False


def test_staffing_segments_group_the_report_inside_one_demand_period():
    # One demand period, two staffing segments: stretches split at 10:00 and each segment reports its own rows.
    segments = [StaffingSegment("early", 480, 600, 0), StaffingSegment("late", 600, 720, 0)]
    roster = [ScheduledShift("A", 480, 720, (ScheduledBreak("rest", 540),)), ScheduledShift("B", 480, 660, ())]
    result = evaluate_planning_cost(HORIZON, STEADY, segments, [A, B], RULES, roster, planning=PLANNING,
                                    break_start_granularity_minutes=30)
    assert [(row["start_minute"], row["end_minute"], row["staffing_segment_id"]) for row in result["capacity"]] == [
        (480, 540, "early"), (540, 570, "early"), (570, 600, "early"), (600, 660, "late"), (660, 720, "late")]
    early, late = result["capacity_by_staffing_segment"]
    assert (early["min_active_servers"], early["max_active_servers"], early["server_minutes"]) == (1, 2, 60 * 2 + 30 + 30 * 2)
    assert (late["min_active_servers"], late["max_active_servers"], late["server_minutes"]) == (1, 2, 60 * 2 + 60)
    assert math.fsum([early["waiting_cost"], late["waiting_cost"]]) == pytest.approx(result["waiting_cost"]["total"])
    solved = solve([A, B], segments=segments)
    assert [row["segment_id"] for row in solved["capacity"]["capacity_by_staffing_segment"]] == ["early", "late"]


def test_off_grid_break_is_outside_the_feasible_set():
    roster = [ScheduledShift("A", 480, 720, (ScheduledBreak("rest", 555),)), ScheduledShift("B", 540, 660, ())]
    result = evaluate_planning_cost(HORIZON, STEADY, ONE_SEGMENT, [A, B], RULES, roster, planning=PLANNING,
                                    break_start_granularity_minutes=30)
    assert result["in_integrated_feasible_set"] is False
    assert any("break grid" in reason for reason in result["feasible_set_reasons"])


# ── Hard constraints ────────────────────────────────────────────────────────


def test_max_wait_forces_two_servers_where_it_binds():
    # Wq at one server is 40 minutes; a 30-minute limit leaves only two servers admissible 10:00-12:00.
    demand = [DemandPeriod("calm", 480, 600, 1.0, 3.0), DemandPeriod("busy", 600, 720, 2.0, 3.0)]
    segments = [StaffingSegment("calm", 480, 600, 0), StaffingSegment("busy", 600, 720, 0)]
    planning = replace(PLANNING, max_wait_minutes=30.0)
    rules = replace(RULES, register_count=3)
    result = solve([A, B, C], demand=demand, segments=segments, rules=rules, planning=planning)
    assert_matches_brute_force(result, [A, B, C], rules, demand, planning, 30)
    busy = [row for row in result["capacity"]["capacity"] if row["start_minute"] >= 600]
    assert busy and all(row["active_servers"] >= 2 and row["Wq_hours"] * 60 <= 30 for row in busy)


def test_target_utilization_and_min_servers_bind():
    # lambda 2, mu 3: one server has rho 2/3 > 0.6, so two servers everywhere; min_servers 2 says the same.
    rules = replace(RULES, register_count=3)
    for planning in (replace(PLANNING, target_utilization=0.6, max_servers=3),
                     replace(PLANNING, min_servers=2, max_servers=3)):
        result = solve([A, B, C], rules=rules, planning=planning)
        assert_matches_brute_force(result, [A, B, C], rules, STEADY, planning, 30)
        assert min(row["active_servers"] for row in result["capacity"]["capacity"]) >= 2


def test_registers_bound_the_on_duty_count_all_day():
    rules = replace(RULES, register_count=1)
    result = solve([A, B], rules=rules, planning=replace(PLANNING, waiting_cost_per_customer_hour=1000.0))
    assert_matches_brute_force(result, [A, B], rules, STEADY, replace(PLANNING, waiting_cost_per_customer_hour=1000.0),
                               30)
    assert result["roster_evaluation"]["register_check"]["max_active_servers"] == 1


def test_expensive_waiting_buys_a_second_server_despite_break_dips():
    # Waiting at 100 per customer-hour: two 4-hour shifts (wages 3.5 x 60 + 3.5 x 40 = 350) keep two servers
    # except in the two rests, and beat one server all morning (200 + 2 x 2/3 x 4 x 100 = 733.3).
    planning = replace(PLANNING, waiting_cost_per_customer_hour=100.0)
    result = solve([A, B], planning=planning)
    best, _ = assert_matches_brute_force(result, [A, B], RULES, STEADY, planning, 30)
    assert best == pytest.approx(350 + 100 * (2 * WQ2 * 3 + 2 * WQ1 * 1), rel=1e-12)


def test_availability_is_respected():
    late = Employee("L", (AvailabilityWindow(600, 720),), EmployeePay(10.0, 15.0, 480))
    result = solve([A, late])
    assert_matches_brute_force(result, [A, late], RULES, STEADY, PLANNING, 30)
    assert all(row["start_minute"] >= 600 for row in result["roster"] if row["employee_id"] == "L")


# ── Infeasible, incomplete, and not solved ──────────────────────────────────


def test_no_admissible_capacity_certificate():
    # rho at one server is 2/3 > 0.5, and one register allows no second server.
    result = solve([A, B], rules=replace(RULES, register_count=1), planning=replace(PLANNING, target_utilization=0.5))
    assert (result["status"], result["feasibility"]) == (INFEASIBLE, INFEASIBLE)
    assert [item["code"] for item in result["infeasibility_certificates"]] == ["NO_ADMISSIBLE_CAPACITY"]
    interval = result["infeasibility_certificates"][0]["intervals"][0]
    assert interval["candidate_counts"] == [0, 1]  # min_servers 0 up to min(max_servers 2, registers 1)
    assert interval["violations"] == {"0": ["no_capacity"], "1": ["target_utilization"]}
    assert result["solver"]["run"] is False


def test_insufficient_workforce_certificate():
    # lambda 4 > mu 3: one server is unstable, and only A can work.
    demand = [DemandPeriod("rush", 480, 720, 4.0, 3.0)]
    result = solve([A], demand=demand)
    assert (result["status"], result["feasibility"]) == (INFEASIBLE, INFEASIBLE)
    assert [item["code"] for item in result["infeasibility_certificates"]] == ["INSUFFICIENT_WORKFORCE"]
    assert result["infeasibility_certificates"][0]["intervals"][0]["smallest_admissible_servers"] == 2
    assert result["solver"]["run"] is False


def test_solver_proves_infeasible_when_every_shift_has_a_break():
    # Only 4-hour shifts, each with a rest: one employee leaves the queue unstaffed during it.
    rules = replace(RULES, shift_rules=replace(SHIFTS, min_shift_minutes=240))
    result = solve([A], rules=rules)
    assert result["infeasibility_certificates"][0]["code"] == "SOLVER_PROVED_INFEASIBLE"
    assert_matches_brute_force(result, [A], rules, STEADY, PLANNING, 30)


def test_missing_waiting_rate_is_incomplete_when_customers_arrive():
    result = solve([A, B], planning=replace(PLANNING, waiting_cost_per_customer_hour=None))
    assert (result["status"], result["feasibility"]) == (INCOMPLETE, UNKNOWN)
    assert [item["field"] for item in result["missing"]] == ["waiting_cost_per_customer_hour"]
    assert result["solver"]["run"] is False and result["planning_cost"] is None


def test_missing_waiting_rate_is_not_needed_without_arrivals():
    demand = [DemandPeriod("closed", 480, 720, 0.0, 3.0)]
    planning = replace(PLANNING, waiting_cost_per_customer_hour=None, min_servers=1)
    result = solve([A, B], demand=demand, planning=planning)
    assert result["status"] == OPTIMAL
    assert result["planning_cost"]["waiting_cost"] == 0.0
    # Someone on duty all morning at the lowest wages: A 2 h + B 2 h = 200 (B 4 h with A covering the rest
    # costs 140 + 120; B 3 h + A 2 h costs 120 + 120).
    assert result["planning_cost"]["total"] == result["planning_cost"]["labor_cost"] == 200.0


def test_missing_waiting_rate_leaves_the_evaluation_undefined():
    roster = [ScheduledShift("A", 480, 600, ()), ScheduledShift("B", 600, 720, ())]
    result = evaluate_planning_cost(HORIZON, STEADY, ONE_SEGMENT, [A, B], RULES, roster,
                                    planning=replace(PLANNING, waiting_cost_per_customer_hour=None),
                                    break_start_granularity_minutes=30)
    assert result["labor_cost"]["total"] == 200.0
    assert result["waiting_cost"] is None and result["planning_cost"] is None
    assert result["capacity"][0]["expected_waiting_customer_hours"] == pytest.approx(2 * WQ1 * 4, rel=1e-12)


def test_missing_pay_is_incomplete_not_zero():
    unpaid = Employee("U", (AvailabilityWindow(480, 720),), EmployeePay(None, 90.0, 480))
    result = solve([unpaid, B])
    assert (result["status"], result["feasibility"]) == (INCOMPLETE, UNKNOWN)
    assert {(item["employee_id"], item["field"]) for item in result["missing"]} == {("U", "regular_rate_per_hour")}
    assert result["solver"]["run"] is False


def test_missing_break_rule_is_incomplete():
    rules = replace(RULES, break_rules=(BreakRule(120, 180, 0, ()),))  # 181-240-minute shifts have no rule
    result = solve([A, B], rules=rules)
    assert (result["status"], result["feasibility"]) == (INCOMPLETE, UNKNOWN)
    assert result["missing"] and all(item["field"] == "break_rules" for item in result["missing"])


def test_incomplete_pattern_set_gives_no_workforce_certificate():
    # A can only work 10:00-12:00, a 2-hour shift whose break rule is missing, so whether A can help is
    # unknown: the run is incomplete, not proved infeasible for lack of a second server.
    rules = replace(RULES, break_rules=(BreakRule(181, 240, 0, (REST,)),))
    late = Employee("L", (AvailabilityWindow(600, 720),), EmployeePay(10.0, 15.0, 480))
    result = solve([late, B], demand=[DemandPeriod("rush", 480, 720, 4.0, 3.0)], rules=rules)
    assert (result["status"], result["feasibility"]) == (INCOMPLETE, UNKNOWN)
    assert result["infeasibility_certificates"] == []


def test_pattern_limit_is_reported_not_truncated():
    result = solve([A, B], config=replace(CONFIG, max_patterns=5))
    assert (result["status"], result["feasibility"]) == (PATTERN_LIMIT_EXCEEDED, UNKNOWN)
    assert result["model"]["patterns"] is None and result["model"]["pattern_limit"] == 5
    assert result["solver"]["run"] is False


# ── Solver outcomes are reported truthfully ─────────────────────────────────


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
    monkeypatch.setattr(shared_integrated, "milp", run)


def test_limit_with_incumbent_is_feasible_but_not_proven_optimal(monkeypatch):
    patched(monkeypatch, 1)
    result = solve([A, B])
    assert (result["status"], result["feasibility"]) == (FEASIBLE_NOT_PROVEN_OPTIMAL, FEASIBLE)
    assert result["optimality"]["proven"] is False and "not proven optimal" in result["optimality"]["basis"]
    assert result["verification"]["passed"] is True


def test_limit_without_incumbent_leaves_feasibility_unknown(monkeypatch):
    patched(monkeypatch, 1, keep_x=False)
    result = solve([A, B])
    assert (result["status"], result["feasibility"]) == (NO_SOLUTION_FOUND, UNKNOWN)
    assert result["roster"] is None and result["planning_cost"] is None and result["optimality"] is None
    assert "not disproved" in result["status_reason"]


def test_solver_infeasible_status_is_infeasible(monkeypatch):
    patched(monkeypatch, 2, keep_x=False)
    result = solve([A, B])
    assert (result["status"], result["feasibility"]) == (INFEASIBLE, INFEASIBLE)


@pytest.mark.parametrize("status", [3, 4])
def test_solver_error(monkeypatch, status):
    patched(monkeypatch, status)
    result = solve([A, B])
    assert (result["status"], result["feasibility"]) == (SOLVER_ERROR, UNKNOWN)
    assert result["roster"] is None and result["planning_cost"] is None


def _flip_capacity(x: np.ndarray) -> np.ndarray:
    # Flip the last capacity column: its interval then selects no count or two, which breaks a model row.
    y = x.copy()
    y[-1] = 1.0 - y[-1]
    return y


@pytest.mark.parametrize("change, failure", [
    (lambda x: x + 0.3, "from an integer"),
    (lambda x: np.where(np.arange(x.size) == 0, 1.0 - x, x), "constraint"),
    (_flip_capacity, "constraint"),
])
def test_corrupted_solver_vector_fails_verification(monkeypatch, change, failure):
    patched(monkeypatch, 0, change=change)
    result = solve([A, B])
    assert (result["status"], result["feasibility"]) == (VERIFICATION_FAILED, UNKNOWN)
    assert failure in result["verification"]["failure"]
    assert result["planning_cost"] is None


def test_verification_detects_a_wrong_capacity_price(monkeypatch):
    # A model whose waiting coefficient disagrees with the independent evaluation is caught.
    original = shared_integrated._build_integrated_model

    def skewed(*args, **kwargs):
        model = original(*args, **kwargs)
        model["objective"][model["labor_columns"]:] *= 1.5
        return model
    monkeypatch.setattr(shared_integrated, "_build_integrated_model", skewed)
    result = solve([A, B])
    assert result["status"] == VERIFICATION_FAILED
    assert "Waiting cost" in result["verification"]["failure"]


def test_verification_detects_a_miscounted_server(monkeypatch):
    original = shared_integrated._build_integrated_model

    def miscounted(*args, **kwargs):
        model = original(*args, **kwargs)
        for interval in model["intervals"]:  # relabel the options: each column now claims one more server
            interval["options"] = [(servers + 1, column, row) for servers, column, row in interval["options"]]
        return model
    monkeypatch.setattr(shared_integrated, "_build_integrated_model", miscounted)
    result = solve([A, B])
    assert result["status"] == VERIFICATION_FAILED
    assert "employees on duty" in result["verification"]["failure"]


def test_verification_rejects_an_inadmissible_count_the_model_allowed(monkeypatch):
    # The model is built with the target relaxed to 1.0, so it may keep one server (rho 2/3) where the
    # caller's 0.6 target needs two: only the independent evaluation stands between that and FEASIBLE.
    original = shared_integrated._build_integrated_model

    def relaxed(horizon, employees, rules, pieces, patterns, cases, capacity):
        loose = shared_integrated._Capacity(replace(capacity.planning, target_utilization=1.0), capacity.register_count)
        return original(horizon, employees, rules, pieces, patterns, cases, loose)
    monkeypatch.setattr(shared_integrated, "_build_integrated_model", relaxed)
    result = solve([A, B], planning=replace(PLANNING, target_utilization=0.6))
    assert result["status"] == VERIFICATION_FAILED
    assert "independent evaluation rejects" in result["verification"]["failure"]


def test_verification_rejects_a_roster_that_breaks_5b1(monkeypatch):
    # A generated pattern outside the employee's availability (and without its break) must never be FEASIBLE.
    late = Employee("L", (AvailabilityWindow(600, 720),), EmployeePay(10.0, 15.0, 480))
    original = shared_integrated.enumerate_patterns

    def with_invalid(*args, **kwargs):
        generated = original(*args, **kwargs)
        generated["patterns"].append(RosterPattern("L", 480, 720, (), ((480, 720),), 240))
        return generated
    monkeypatch.setattr(shared_integrated, "enumerate_patterns", with_invalid)
    result = solve([A, late])
    assert result["status"] == VERIFICATION_FAILED
    assert "5B-1 evaluation found violations" in result["verification"]["failure"]


# ── Integrated versus sequential ────────────────────────────────────────────


def capacity_config(planning: PlanningConfig, server_cost: float) -> CapacityConfig:
    assert planning.waiting_cost_per_customer_hour is not None  # Phase 2 has no "not supplied" rate
    return CapacityConfig(server_cost_per_hour=server_cost,
                          waiting_cost_per_customer_hour=planning.waiting_cost_per_customer_hour,
                          target_utilization=planning.target_utilization, min_servers=planning.min_servers,
                          max_servers=planning.max_servers, max_wait_minutes=planning.max_wait_minutes)


def test_integrated_beats_sequential_when_wages_differ_from_the_server_charge():
    # Phase 2 charges 200 per server-hour, so it picks one server (800 + 533.3 < 1600 + 33.3); 5B-2 then
    # rosters A 2 h + B 2 h (wages 200). On the planning objective that costs 200 + 533.3 = 733.3, while the
    # integrated plan keeps two servers except in the rests (350 + 158.3 = 508.3).
    planning = replace(PLANNING, waiting_cost_per_customer_hour=100.0)
    outcome = compare_with_sequential(HORIZON, STEADY, ONE_SEGMENT, [A, B], RULES,
                                      capacity_config=capacity_config(planning, 200.0), planning=planning,
                                      config=CONFIG)
    comparison = outcome["comparison"]
    assert outcome["sequential"]["phase2_selected_servers"] == [1]
    assert comparison["comparable"] is True and comparison["integrated_no_worse"] is True
    assert comparison["sequential_planning_cost"] == pytest.approx(200 + 100 * 2 * WQ1 * 4, rel=1e-12)
    assert comparison["integrated_planning_cost"] == pytest.approx(350 + 100 * (2 * WQ2 * 3 + 2 * WQ1), rel=1e-12)
    assert comparison["difference"] < -200
    sequential = roster_of(outcome["sequential"]["roster_result"]["roster"])
    cost, _, _ = independent_cost(sequential, [A, B], RULES, STEADY, planning)
    assert cost == pytest.approx(comparison["sequential_planning_cost"], rel=1e-12)


def test_equal_costs_are_no_worse():
    outcome = compare_with_sequential(HORIZON, STEADY, ONE_SEGMENT, [A, B], RULES,
                                      capacity_config=capacity_config(PLANNING, 94.375), planning=PLANNING,
                                      config=CONFIG)
    comparison = outcome["comparison"]
    assert comparison["integrated_no_worse"] is True
    assert comparison["difference"] == pytest.approx(0.0, abs=1e-9)


def test_mismatched_settings_are_not_compared():
    outcome = compare_with_sequential(HORIZON, STEADY, ONE_SEGMENT, [A, B], RULES,
                                      capacity_config=replace(capacity_config(PLANNING, 94.375), target_utilization=0.8),
                                      planning=PLANNING, config=CONFIG)
    assert outcome["comparison"]["comparable"] is False
    assert outcome["comparison"]["mismatched_settings"] == ["target_utilization"]
    assert outcome["comparison"]["integrated_no_worse"] is None and outcome["sequential"] is None


def test_sequential_roster_outside_the_integrated_set_is_not_claimed():
    # Only 4-hour shifts with a rest and at most one server: covering each rest puts two on duty, which the
    # integrated model forbids, so it has no plan; the sequential roster exceeds the maximum.
    rules = replace(RULES, shift_rules=replace(SHIFTS, min_shift_minutes=240))
    planning = replace(PLANNING, max_servers=1)
    outcome = compare_with_sequential(HORIZON, STEADY, ONE_SEGMENT, [A, B], rules,
                                      capacity_config=capacity_config(planning, 94.375), planning=planning,
                                      config=CONFIG)
    assert outcome["sequential"]["roster_result"]["status"] == OPTIMAL
    assert outcome["sequential"]["evaluation"]["in_integrated_feasible_set"] is False
    assert outcome["integrated"]["status"] == INFEASIBLE
    assert outcome["comparison"]["integrated_no_worse"] is None
    assert "outside the integrated feasible set" in outcome["comparison"]["basis"]


@pytest.mark.parametrize("status, expected", [(OPTIMAL, "CONFLICTING"), (FEASIBLE_NOT_PROVEN_OPTIMAL, "not proven")])
def test_a_cheaper_sequential_roster_is_flagged(status, expected):
    integrated = solve([A, B])
    doctored = copy.deepcopy(integrated)
    doctored["status"] = status
    doctored["planning_cost"]["total"] += 50.0
    outcome = compare_with_sequential(HORIZON, STEADY, ONE_SEGMENT, [A, B], RULES,
                                      capacity_config=capacity_config(PLANNING, 94.375), planning=PLANNING,
                                      config=CONFIG, integrated=doctored)
    assert outcome["comparison"]["integrated_no_worse"] is False
    assert expected in outcome["comparison"]["basis"]


# ── Random synthetic instances against the brute force ──────────────────────

RANDOM_SEEDS = 40


def random_instance(seed: int):
    rng = random.Random(seed)
    rest = replace(REST, paid=rng.random() < 0.5)
    shifts = replace(SHIFTS, min_shift_minutes=rng.choice([60, 120]), max_shift_minutes=rng.choice([180, 240]))
    if rng.random() < 0.3:
        shifts = replace(shifts, max_shifts_per_employee=2, min_minutes_between_shifts=rng.choice([0, 60]))
    rules = WorkforceRules(shifts, (BreakRule(shifts.min_shift_minutes, 180, 0, ()), BreakRule(181, 240, 0, (rest,))),
                           register_count=rng.randint(1, 3))
    cut = rng.choice([540, 600, 660])
    demand = [DemandPeriod("a", 480, cut, rng.choice([0.0, 1.0, 2.0, 3.0]), rng.choice([2.0, 3.0, 4.0])),
              DemandPeriod("b", cut, 720, rng.choice([0.0, 1.0, 2.0, 4.0, 5.0]), rng.choice([2.0, 3.0, 4.0]))]
    segments = [StaffingSegment("a", 480, cut, 0), StaffingSegment("b", cut, 720, 0)]
    planning = PlanningConfig(waiting_cost_per_customer_hour=rng.choice([0.0, 5.0, 40.0, 150.0]),
                              target_utilization=rng.choice([0.6, 0.8, 1.0]),
                              max_wait_minutes=rng.choice([None, None, 15.0, 45.0]),
                              min_servers=rng.choice([0, 0, 1]), max_servers=rng.choice([2, 3]))
    employees = []
    for index in range(2 if shifts.max_shifts_per_employee == 2 else rng.randint(2, 3)):
        start, end = rng.choice([480, 480, 540]), rng.choice([660, 720, 720])
        employees.append(Employee(f"E{index}", (AvailabilityWindow(start, end),), EmployeePay(
            float(rng.randint(20, 80)), float(rng.randint(10, 120)), rng.choice([60, 90, 120, 150, 480]))))
    return employees, rules, demand, segments, planning, rng.choice([30, 60])


@pytest.mark.parametrize("seed", range(RANDOM_SEEDS))
def test_random_instances_match_brute_force(seed):
    employees, rules, demand, segments, planning, grid = random_instance(seed)
    result = solve(employees, demand=demand, segments=segments, rules=rules, planning=planning,
                   config=replace(CONFIG, break_start_granularity_minutes=grid))
    assert_matches_brute_force(result, employees, rules, demand, planning, grid)
    if result["status"] == OPTIMAL:
        evaluation = evaluate_roster(HORIZON, employees, rules, roster_of(result["roster"]))
        assert evaluation["violations"] == [] and not evaluation["register_check"]["exceeded"]


def test_random_instances_cover_every_outcome():
    # Guards the generator: the comparison above must see optima, certificates, solver-proved infeasibility,
    # break dips, more than one server, overtime, and split shifts.
    seen = set()
    for seed in range(RANDOM_SEEDS):
        employees, rules, demand, segments, planning, grid = random_instance(seed)
        result = solve(employees, demand=demand, segments=segments, rules=rules, planning=planning,
                       config=replace(CONFIG, break_start_granularity_minutes=grid))
        seen.add(result["status"])
        seen.update(item["code"] for item in result["infeasibility_certificates"])
        if result["status"] == OPTIMAL:
            rows = result["capacity"]["capacity"]
            if any(shift["breaks"] for shift in result["roster"]):
                seen.add("break")
            if max(row["active_servers"] for row in rows) >= 2:
                seen.add("two servers")
            if any(row["overtime_paid_minutes"] for row in result["labor_cost"]["employees"]):
                seen.add("overtime")
            if rules.shift_rules.max_shifts_per_employee == 2:
                seen.add("split")
    assert {OPTIMAL, INFEASIBLE, "NO_ADMISSIBLE_CAPACITY", "INSUFFICIENT_WORKFORCE", "SOLVER_PROVED_INFEASIBLE",
            "break", "two servers", "overtime", "split"} <= seen
