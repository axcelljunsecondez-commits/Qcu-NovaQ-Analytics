"""Phase 5B-1 shared-queue workforce foundation.

ALL EMPLOYEES, AVAILABILITY, RULES, RATES, AND ROSTERS IN THIS FILE ARE SYNTHETIC TEST DATA.
They are not NovaMart records, labor law, or recommended operating values.

Expected values are computed by hand in the comments. The active-server count and coverage
are also checked against an independent minute-by-minute brute force on generated rosters.
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from backend.queueing_engine.services.shared_segments import OperatingHorizon, SharedSegmentError, StaffingSegment
from backend.queueing_engine.services.shared_workforce import (
    COMPLETE,
    INCOMPLETE,
    INVALID,
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

HORIZON = OperatingHorizon(480, 1200)  # 08:00-20:00
REST = BreakRequirement("rest", 15, True, 60, 180)
MEAL = BreakRequirement("meal", 60, False, 180, 330)
RULES = WorkforceRules(
    shift_rules=ShiftRules(earliest_start_minute=420, latest_end_minute=1260, min_shift_minutes=240,
                           max_shift_minutes=600, boundary_granularity_minutes=15, max_shifts_per_employee=1,
                           min_minutes_between_shifts=None),
    break_rules=(BreakRule(240, 360, 0, (REST,)), BreakRule(361, 600, 60, (REST, MEAL))),
    register_count=3,
)
E1 = Employee("E1", (AvailabilityWindow(420, 1260),), EmployeePay(80.0, 120.0, 480))
E2 = Employee("E2", (AvailabilityWindow(480, 840),), EmployeePay(75.0, 110.0, 480))
E3 = Employee("E3", (AvailabilityWindow(720, 1260),), EmployeePay(None, None, None))
EMPLOYEES = [E1, E2, E3]
ROSTER = [
    # E1 08:00-18:00 (600 min): paid rest 10:00-10:15, unpaid meal 12:30-13:30.
    ScheduledShift("E1", 480, 1080, (ScheduledBreak("rest", 600), ScheduledBreak("meal", 750))),
    # E2 08:00-12:00 (240 min): paid rest 09:30-09:45.
    ScheduledShift("E2", 480, 720, (ScheduledBreak("rest", 570),)),
    # E3 14:00-20:30 (390 min): paid rest 15:30-15:45, unpaid meal 17:30-18:30; 30 min after closing.
    ScheduledShift("E3", 840, 1230, (ScheduledBreak("rest", 930), ScheduledBreak("meal", 1050))),
]
REQUIRED = [StaffingSegment("am", 480, 720, 2), StaffingSegment("mid", 720, 960, 2), StaffingSegment("pm", 960, 1200, 1)]


def evaluate(employees=None, rules=RULES, roster=None, **kwargs) -> dict:
    return evaluate_roster(HORIZON, EMPLOYEES if employees is None else employees, rules,
                           ROSTER if roster is None else roster, **kwargs)


def codes(result: dict) -> list[str]:
    return [item["code"] for item in result["violations"]]


def row(result: dict, employee_id: str) -> dict:
    return next(item for item in result["employees"] if item["employee_id"] == employee_id)


# ── Hand-computed hours ──────────────────────────────────────────────────────


def test_hours_by_hand():
    result = evaluate()
    # E1: S 600; breaks 15 paid + 60 unpaid; P = 540; A = 525; θ 480 -> R 480, O 60.
    assert row(result, "E1")["minutes"] == {
        "scheduled_employee_minutes": 600, "break_minutes": 75, "paid_break_minutes": 15,
        "unpaid_break_minutes": 60, "paid_employee_minutes": 540, "scheduled_active_server_minutes": 525,
        "active_server_minutes_in_horizon": 525, "active_server_minutes_outside_horizon": 0,
        "regular_paid_minutes": 480, "overtime_paid_minutes": 60,
    }
    # Paid time in clock order: 08:00-12:30 (270) then 13:30-18:00; 480 is reached at 13:30 + 210 = 17:00.
    assert row(result, "E1")["overtime_starts_at_minute"] == 1020
    assert row(result, "E1")["hours"]["overtime_paid_hours"] == 1.0
    # E2: S 240; paid rest 15; P 240; A 225; R 240; O 0; no overtime start.
    e2 = row(result, "E2")
    assert (e2["minutes"]["paid_employee_minutes"], e2["minutes"]["scheduled_active_server_minutes"],
            e2["minutes"]["regular_paid_minutes"], e2["minutes"]["overtime_paid_minutes"],
            e2["overtime_starts_at_minute"]) == (240, 225, 240, 0, None)
    # E3: S 390; P 330; A 315; active in horizon 90 + 105 + 90 = 285, outside 30 (20:00-20:30).
    e3 = row(result, "E3")["minutes"]
    assert (e3["paid_employee_minutes"], e3["scheduled_active_server_minutes"],
            e3["active_server_minutes_in_horizon"], e3["active_server_minutes_outside_horizon"]) == (330, 315, 285, 30)
    # θ is not supplied for E3: regular and overtime are unknown, never 0.
    assert e3["regular_paid_minutes"] is None and e3["overtime_paid_minutes"] is None
    totals = result["totals"]["minutes"]
    assert (totals["scheduled_employee_minutes"], totals["paid_employee_minutes"],
            totals["scheduled_active_server_minutes"], totals["regular_paid_minutes"]) == (1230, 1110, 1065, None)


def test_status_and_missing_values():
    result = evaluate()
    assert result["violations"] == []
    assert result["status"] == INCOMPLETE
    assert sorted(item["field"] for item in result["missing"]) == [
        "daily_regular_paid_minutes", "overtime_rate_per_hour", "regular_rate_per_hour"]
    assert all(item["employee_id"] == "E3" for item in result["missing"])
    assert row(result, "E3")["pay_complete"] is False and row(result, "E1")["pay_complete"] is True
    complete = evaluate(employees=[E1, E2, replace(E3, pay=EmployeePay(70.0, 105.0, 480))])
    assert complete["status"] == COMPLETE and complete["missing"] == []
    assert complete["totals"]["minutes"]["regular_paid_minutes"] == 480 + 240 + 330
    assert "cost" not in complete  # pay is validated only; no cost in this phase
    # Missing pay of an employee with no shift does not affect this roster.
    unrostered = replace(E3, employee_id="E4")
    assert evaluate(employees=[E1, E2, replace(E3, pay=EmployeePay(70.0, 105.0, 480)), unrostered])["status"] == COMPLETE


def test_active_server_steps_register_check_and_coverage_by_hand():
    result = evaluate(required_staffing=REQUIRED)
    assert [(s["start_minute"], s["end_minute"], s["active_servers"]) for s in result["active_server_steps"]] == [
        (480, 570, 2), (570, 585, 1), (585, 600, 2), (600, 615, 1), (615, 720, 2), (720, 750, 1), (750, 810, 0),
        (810, 840, 1), (840, 930, 2), (930, 945, 1), (945, 1050, 2), (1050, 1080, 1), (1080, 1110, 0),
        (1110, 1230, 1),
    ]
    integral = sum((s["end_minute"] - s["start_minute"]) * s["active_servers"] for s in result["active_server_steps"])
    assert integral == 1065 == result["totals"]["minutes"]["scheduled_active_server_minutes"]
    assert result["register_check"] == {"register_count": 3, "max_active_servers": 2, "exceeded": False}
    coverage = result["coverage"]
    # am needs 2: short 15 (09:30-09:45) + 15 (10:00-10:15) = 30.
    # mid needs 2: 30 + 60 x 2 + 30 + 15 = 195. pm needs 1: short 30 (18:00-18:30), surplus 90 (16:00-17:30).
    assert [(r["segment_id"], r["shortfall_server_minutes"], r["surplus_server_minutes"], r["min_active_servers"],
             r["max_active_servers"]) for r in coverage["segments"]] == [
        ("am", 30, 0, 1, 2), ("mid", 195, 0, 0, 2), ("pm", 30, 90, 0, 2)]
    assert (coverage["shortfall_server_minutes"], coverage["surplus_server_minutes"], coverage["fully_covered"]) == (
        255, 90, False)
    assert result["status"] == INCOMPLETE  # a coverage shortfall is reported, not a violation


def test_register_capacity_is_a_violation_with_its_intervals():
    result = evaluate(rules=replace(RULES, register_count=1))
    exceeded = [item for item in result["violations"] if item["code"] == "REGISTER_CAPACITY"]
    expected = ["08:00-09:30", "09:45-10:00", "10:15-12:00", "14:00-15:30", "15:45-17:30"]
    assert len(exceeded) == len(expected)
    for item, span in zip(exceeded, expected):
        assert item["message"] == (
            f"2 employees are scheduled to staff servers during {span}, above the 1 registers.")
    assert result["status"] == INVALID and result["register_check"]["exceeded"] is True
    assert result["totals"] is not None  # hours stay well defined; the roster is still invalid


def test_split_shifts_and_overtime_across_shifts():
    split_rules = replace(RULES, shift_rules=replace(RULES.shift_rules, max_shifts_per_employee=2,
                                                     min_minutes_between_shifts=60))
    worker = Employee("S1", (AvailabilityWindow(420, 1260),), EmployeePay(80.0, 120.0, 420))
    roster = [ScheduledShift("S1", 480, 720, (ScheduledBreak("rest", 540),)),
              ScheduledShift("S1", 780, 1020, (ScheduledBreak("rest", 870),))]
    result = evaluate_roster(HORIZON, [worker], split_rules, roster)
    # Paid 240 + 240 = 480 (rests are paid); θ 420 -> R 420, O 60, starting 13:00 + 180 = 16:00.
    minutes = row(result, "S1")["minutes"]
    assert (result["status"], minutes["paid_employee_minutes"], minutes["regular_paid_minutes"],
            minutes["overtime_paid_minutes"]) == (COMPLETE, 480, 420, 60)
    assert row(result, "S1")["overtime_starts_at_minute"] == 960
    short_rest = [roster[0], replace(roster[1], start_minute=750, end_minute=990,
                                     breaks=(ScheduledBreak("rest", 840),))]
    assert codes(evaluate_roster(HORIZON, [worker], split_rules, short_rest)) == ["INSUFFICIENT_REST"]
    overlapping = [roster[0], replace(roster[1], start_minute=660, end_minute=900,
                                      breaks=(ScheduledBreak("rest", 750),))]
    overlap = evaluate_roster(HORIZON, [worker], split_rules, overlapping)
    assert codes(overlap) == ["SHIFT_OVERLAP"]
    assert row(overlap, "S1")["minutes"] is None and overlap["totals"] is None  # withheld, not guessed


def test_overtime_threshold_edges():
    # θ 269 ends one minute before the 08:00-12:30 paid block does, so overtime starts at 12:29 (749);
    # θ 270 fills that block exactly, so overtime starts after the unpaid meal, at 13:30 (810).
    for threshold, regular, overtime, start in ((0, 0, 540, 480), (540, 540, 0, None), (270, 270, 270, 810),
                                                (269, 269, 271, 749)):
        employee = replace(E1, pay=EmployeePay(80.0, 120.0, threshold))
        result = evaluate(employees=[employee], roster=[ROSTER[0]])
        minutes = row(result, "E1")["minutes"]
        assert (minutes["regular_paid_minutes"], minutes["overtime_paid_minutes"]) == (regular, overtime)
        assert minutes["regular_paid_minutes"] + minutes["overtime_paid_minutes"] == minutes["paid_employee_minutes"]
        assert row(result, "E1")["overtime_starts_at_minute"] == start


# ── One test per violation code ──────────────────────────────────────────────


def with_shift(index: int, **changes) -> list[ScheduledShift]:
    roster = list(ROSTER)
    roster[index] = replace(roster[index], **changes)
    return roster


# An employee available all day isolates the boundary and shift-count checks from availability.
WIDE = Employee("W1", (AvailabilityWindow(0, 1440),), EmployeePay(80.0, 120.0, 480))


@pytest.mark.parametrize(("roster", "employees", "expected"), [
    (ROSTER + [ScheduledShift("E9", 480, 720, (ScheduledBreak("rest", 570),))], None, ["UNKNOWN_EMPLOYEE"]),
    (with_shift(1, start_minute=600, end_minute=900, breaks=(ScheduledBreak("rest", 690),)), None,
     ["OUTSIDE_AVAILABILITY"]),
    ([ScheduledShift("W1", 405, 1005, (ScheduledBreak("rest", 525), ScheduledBreak("meal", 675)))], [WIDE],
     ["OUTSIDE_SHIFT_BOUNDARIES"]),
    # A 180-minute shift is too short, and no break rule covers that length either.
    (with_shift(1, start_minute=480, end_minute=660, breaks=(ScheduledBreak("rest", 570),)), None,
     ["SHIFT_LENGTH", "NO_BREAK_RULE"]),
    (with_shift(1, start_minute=490, end_minute=730, breaks=(ScheduledBreak("rest", 580),)), None, ["OFF_GRID"]),
    ([ScheduledShift("W1", 480, 720, (ScheduledBreak("rest", 570),)),
      ScheduledShift("W1", 900, 1140, (ScheduledBreak("rest", 990),))], [WIDE], ["TOO_MANY_SHIFTS"]),
    (with_shift(0, breaks=(ScheduledBreak("rest", 600),)), None, ["BREAK_MISSING"]),
    (with_shift(1, breaks=(ScheduledBreak("rest", 570), ScheduledBreak("nap", 660))), None, ["BREAK_UNKNOWN"]),
    (with_shift(1, breaks=(ScheduledBreak("rest", 570), ScheduledBreak("rest", 630))), None, ["BREAK_DUPLICATE"]),
    (with_shift(1, breaks=(ScheduledBreak("rest", 510),)), None, ["BREAK_WINDOW"]),
    (with_shift(1, breaks=(ScheduledBreak("rest", 675),)), None, ["BREAK_WINDOW"]),  # offset 195 > 180
    (with_shift(0, end_minute=855, breaks=(ScheduledBreak("rest", 600), ScheduledBreak("meal", 810))), None,
     ["BREAK_OUTSIDE_SHIFT"]),
    (with_shift(0, breaks=(ScheduledBreak("rest", 660), ScheduledBreak("meal", 660))), None, ["BREAK_OVERLAP"]),
    (with_shift(0, breaks=(ScheduledBreak("rest", 650), ScheduledBreak("meal", 690))), None, ["BREAK_GAP"]),
], ids=["unknown_employee", "outside_availability", "outside_boundaries", "shift_length", "off_grid",
        "too_many_shifts", "break_missing", "break_unknown", "break_duplicate", "break_window_early",
        "break_window_late",
        "break_outside_shift", "break_overlap", "break_gap"])
def test_each_violation_is_reported_with_a_reason(roster, employees, expected):
    result = evaluate(employees=employees, roster=roster)
    assert codes(result) == expected
    assert result["status"] == INVALID
    assert all(item["message"] and item["employee_id"] is not None for item in result["violations"])


def test_no_break_rule_and_rule_gaps():
    gapped = replace(RULES, break_rules=(BreakRule(240, 300, 0, (REST,)), BreakRule(361, 600, 60, (REST, MEAL))))
    clean = evaluate(rules=gapped)
    assert clean["violations"] == []
    assert {"employee_id": None, "field": "break_rules", "consequence":
            "Shift lengths 301 to 360 minutes have no break rule; such shifts would be rejected."} in clean["missing"]
    shift_330 = with_shift(1, start_minute=480, end_minute=810, breaks=(ScheduledBreak("rest", 570),))
    result = evaluate(rules=gapped, roster=shift_330)
    assert codes(result) == ["NO_BREAK_RULE"]
    assert row(result, "E2")["minutes"] is None  # break lengths are unknown, so hours are withheld


def test_an_explicitly_break_free_rule_is_accepted():
    short = replace(RULES, break_rules=(BreakRule(240, 360, 0, ()), BreakRule(361, 600, 60, (REST, MEAL))))
    result = evaluate(rules=short, roster=with_shift(1, breaks=()))
    assert result["violations"] == [] and row(result, "E2")["minutes"]["break_minutes"] == 0


# ── Malformed inputs are rejected ────────────────────────────────────────────


@pytest.mark.parametrize(("employees", "message"), [
    ([E1, replace(E2, employee_id="E1")], "Duplicate employee ids: E1"),
    ([replace(E1, employee_id="Juan Dela Cruz")], "id must be 1 to 64"),
    ([replace(E1, employee_id="a@b.com")], "id must be 1 to 64"),
    ([replace(E1, availability=())], "needs at least one availability window"),
    ([replace(E1, availability=(AvailabilityWindow(420, 700), AvailabilityWindow(600, 900)))], "windows overlap"),
    ([replace(E1, availability=(AvailabilityWindow(420.0, 700),))], "whole minutes"),  # type: ignore[arg-type]
    ([replace(E1, availability=(AvailabilityWindow(700, 700),))], "must end after it starts"),
    ([replace(E1, pay=EmployeePay(-1.0, 120.0, 480))], "regular_rate_per_hour"),
    ([replace(E1, pay=EmployeePay(80.0, math.nan, 480))], "overtime_rate_per_hour"),
    ([replace(E1, pay=EmployeePay(80.0, 120.0, 480.5))], "daily_regular_paid_minutes"),  # type: ignore[arg-type]
    ([replace(E1, pay=None)], "pay must be an EmployeePay"),  # type: ignore[arg-type]
    ([], "At least one employee"),
])
def test_malformed_employees_are_rejected(employees, message):
    with pytest.raises(SharedSegmentError, match=message):
        evaluate_roster(HORIZON, employees, RULES, [])


def rules_with(**shift_changes) -> WorkforceRules:
    return replace(RULES, shift_rules=replace(RULES.shift_rules, **shift_changes))


@pytest.mark.parametrize(("rules", "message"), [
    (rules_with(min_shift_minutes=700), "min_shift_minutes <= max_shift_minutes"),
    (rules_with(boundary_granularity_minutes=0), "boundary_granularity_minutes"),
    (rules_with(max_shifts_per_employee=2), "min_minutes_between_shifts \\(required with split shifts\\)"),
    (rules_with(min_minutes_between_shifts=30), "applies only when more than one shift"),
    (rules_with(earliest_start_minute=1300), "permitted shift boundary"),
    (replace(RULES, register_count=0), "register_count"),
    (replace(RULES, break_rules=(BreakRule(240, 400, 0, (REST,)), BreakRule(361, 600, 60, (REST, MEAL)))),
     "ranges overlap"),
    (replace(RULES, break_rules=(BreakRule(240, 600, 0, (replace(REST, paid=None),)),)),  # type: ignore[arg-type]
     "paid must be True or False"),
    (replace(RULES, break_rules=(BreakRule(240, 600, 0, (replace(REST, earliest_start_offset_minutes=200),)),)),
     "earliest_start_offset <= latest_start_offset"),
    (replace(RULES, break_rules=(BreakRule(240, 600, 0, (REST, REST)),)), "names must be unique"),
    (replace(RULES, break_rules=(BreakRule(240, 600, 0, (replace(REST, duration_minutes=0),)),)), "duration_minutes"),
])
def test_malformed_rules_are_rejected(rules, message):
    with pytest.raises(SharedSegmentError, match=message):
        evaluate_roster(HORIZON, EMPLOYEES, rules, [])


@pytest.mark.parametrize(("roster", "staffing", "message"), [
    ([ScheduledShift("E1", 480, 480, ())], None, "must end after it starts"),
    ([ScheduledShift("E1", 480, 1500, ())], None, "whole minutes"),
    ([ScheduledShift("E1", 480, 720, (ScheduledBreak("rest", True),))], None, "break 'rest' start"),  # type: ignore[arg-type]
    (["E1 08:00-12:00"], None, "must be a ScheduledShift"),
    ([], [StaffingSegment("a", 480, 900, 1)], "tile the operating horizon"),
    ([], [StaffingSegment("a", 480, 900, 1), StaffingSegment("b", 900, 1200, -1)], "servers must be a whole number"),
])
def test_malformed_roster_and_staffing_are_rejected(roster, staffing, message):
    with pytest.raises(SharedSegmentError, match=message):
        evaluate_roster(HORIZON, EMPLOYEES, RULES, roster, required_staffing=staffing)


# ── Identities and an independent brute force on generated rosters ──────────


def brute_force_active(employees: list[Employee], rules: WorkforceRules, roster: list[ScheduledShift]) -> list[int]:
    """Active employees per minute 0..1439, checked minute by minute without interval arithmetic."""
    lengths = {item.name: item.duration_minutes for rule in rules.break_rules for item in rule.breaks}
    known = {employee.employee_id for employee in employees}
    counts = []
    for minute in range(1440):
        active = set()
        for shift in roster:
            if shift.employee_id not in known or not shift.start_minute <= minute < shift.end_minute:
                continue
            on_break = any(item.start_minute <= minute < item.start_minute + lengths[item.name] for item in shift.breaks)
            if not on_break:
                active.add(shift.employee_id)
        counts.append(len(active))
    return counts


def generated_roster(rng: np.random.Generator) -> list[ScheduledShift]:
    roster = []
    for employee_id in ("E1", "E2", "E3"):
        if rng.random() < 0.15:
            continue
        length = int(rng.choice([240, 300, 360, 420, 480, 540, 600]))
        start = int(rng.choice(range(420, 1260 - length + 1, 15)))
        breaks = [ScheduledBreak("rest", start + int(rng.integers(40, 200)))]
        if length > 360:
            breaks.append(ScheduledBreak("meal", start + int(rng.integers(160, 350))))
        roster.append(ScheduledShift(employee_id, start, start + length, tuple(breaks)))
    return roster


def test_identities_and_brute_force_on_generated_rosters():
    rng = np.random.default_rng(20260926)
    employees = [replace(employee, pay=EmployeePay(80.0, 120.0, 420)) for employee in EMPLOYEES]
    checked = 0
    for _ in range(200):
        roster = generated_roster(rng)
        result = evaluate_roster(HORIZON, employees, RULES, roster, required_staffing=REQUIRED)
        counts = brute_force_active(employees, RULES, roster)
        steps_by_minute = [0] * 1440
        for step in result["active_server_steps"]:
            for minute in range(step["start_minute"], step["end_minute"]):
                steps_by_minute[minute] = step["active_servers"]
        assert steps_by_minute == counts
        for segment, coverage in zip(REQUIRED, result["coverage"]["segments"]):
            window = counts[segment.start_minute:segment.end_minute]
            assert coverage["shortfall_server_minutes"] == sum(max(0, segment.servers - n) for n in window)
            assert coverage["surplus_server_minutes"] == sum(max(0, n - segment.servers) for n in window)
        assert result["register_check"]["exceeded"] == (max(counts) > 3)
        for item in result["employees"]:
            minutes = item["minutes"]
            if minutes is None:
                continue
            checked += 1
            assert minutes["scheduled_employee_minutes"] == minutes["paid_employee_minutes"] + minutes["unpaid_break_minutes"]
            assert minutes["scheduled_employee_minutes"] == minutes["scheduled_active_server_minutes"] + minutes["break_minutes"]
            assert minutes["paid_employee_minutes"] == minutes["scheduled_active_server_minutes"] + minutes["paid_break_minutes"]
            assert minutes["regular_paid_minutes"] + minutes["overtime_paid_minutes"] == minutes["paid_employee_minutes"]
            assert minutes["regular_paid_minutes"] == min(420, minutes["paid_employee_minutes"])
            employee_minutes = sum(1 for minute in range(1440) if any(
                shift.employee_id == item["employee_id"] and shift.start_minute <= minute < shift.end_minute
                and not any(b.start_minute <= minute < b.start_minute + (15 if b.name == "rest" else 60)
                            for b in shift.breaks) for shift in roster))
            assert minutes["scheduled_active_server_minutes"] == employee_minutes
            # Overtime start, minute by minute: the first paid minute after 420 paid minutes.
            paid_minutes = [minute for minute in range(1440) if any(
                shift.employee_id == item["employee_id"] and shift.start_minute <= minute < shift.end_minute
                and not any(b.name == "meal" and b.start_minute <= minute < b.start_minute + 60 for b in shift.breaks)
                for shift in roster)]
            assert item["overtime_starts_at_minute"] == (paid_minutes[420] if len(paid_minutes) > 420 else None)
    assert checked > 200  # most generated employees have well-defined hours


def test_scope_and_provenance_disclose_what_this_is_not():
    result = evaluate()
    assert "not simulated service or busy time" in result["scope"]
    assert "not an optimized roster" in result["scope"]
    assert "cannot be verified" in result["provenance"]["pseudonymity"]
    assert "counted, not identified" in result["provenance"]["registers"]
