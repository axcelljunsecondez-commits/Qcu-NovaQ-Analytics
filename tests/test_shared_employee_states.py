"""Phase 5B-4.2 named-employee state machine for the shared queue.

ALL EMPLOYEES, AVAILABILITY, RULES, ROSTERS, AND SERVICE TIMES IN THIS FILE ARE SYNTHETIC TEST DATA.
They are not NovaMart records, labor law, or recommended operating values. Service starts and
completions are prescribed inputs chosen to reach each transition; they are not generated
customers or service-time estimates.

Expected timelines are derived by hand in the comments. Every run is also checked by
``check_invariants``, an independent checker of the sixteen Phase 5B-4.2 invariants that works
only from the result, the rules, and the roster.

The horizon is 08:00-12:00 (minutes 480-720), so hours run 0-4 and closing is at 4.0. Every roster
minute is a multiple of 15 and every input time a multiple of 1/8 hour, so all times are
binary-exact and the partition sums are compared exactly. The exception is the section "Whole-minute
arithmetic" (Phase 5B-4.3), whose 5-minute rosters are deliberately not binary-exact; those runs
are checked by their own exact assertions, because ``check_invariants`` compares float sums
exactly and so applies to binary-exact inputs only.

Phase 5B-4.3 replaced the 5B-4.2 test that expected ``UndeterminedPolicyError`` for a break of a
delayed split shift: the approved P3 rule now determines that case (the break keeps its planned
offset from the actual shift start).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from backend.queueing_engine.services.shared_segments import OperatingHorizon, SharedSegmentError
from backend.queueing_engine.services.shared_workforce import (
    INCOMPLETE,
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
from backend.queueing_engine.simulation import shared_continuous_des, shared_employee_states
from backend.queueing_engine.simulation.shared_employee_states import (
    AVAILABLE,
    BASE_STATES,
    BREAK_OUTCOMES,
    COMPLETED,
    OFF,
    ON_BREAK,
    REGISTER_STATES,
    SERVING,
    SERVING_BREAK_DUE,
    SERVING_SHIFT_ENDED,
    STAGES,
    TRUNCATED_BY_CLOSING,
    UNFULFILLED,
    WAITING_FOR_REGISTER,
    CancelPendingBreaks,
    EmployeeTimeline,
    EmployeeTimelineError,
    EndBreakAtClosing,
    Release,
    ServiceCompletion,
    ServiceStart,
    run_timeline,
)

# ── SYNTHETIC TEST DATA ──────────────────────────────────────────────────────

HORIZON = OperatingHorizon(480, 720)  # 08:00-12:00; closing at 4.0 h
NO_BREAKS = BreakRule(15, 480, 0, ())


def break_rule(low: int, high: int, gap: int = 0, **durations: int) -> BreakRule:
    """A rule whose breaks may start anywhere in the shift (offsets 0-480)."""
    return BreakRule(low, high, gap, tuple(BreakRequirement(name, minutes, True, 0, 480)
                                           for name, minutes in durations.items()))


def rules(*break_rules: BreakRule, registers: int, max_shifts: int = 1, rest: int | None = None) -> WorkforceRules:
    return WorkforceRules(ShiftRules(0, 1440, 15, 480, 15, max_shifts, rest), break_rules or (NO_BREAKS,), registers)


def shift(employee_id: str, start: int, end: int, **breaks: int) -> ScheduledShift:
    return ScheduledShift(employee_id, start, end, tuple(ScheduledBreak(name, minute) for name, minute in breaks.items()))


def staff(roster: list[ScheduledShift]) -> list[Employee]:
    ids = sorted({item.employee_id for item in roster})
    return [Employee(employee_id, (AvailabilityWindow(0, 1440),), EmployeePay(None, None, None)) for employee_id in ids]


def run(roster: list[ScheduledShift], workforce: WorkforceRules, inputs: list[Any] | None = None, *,
        hold: bool = False, finish: float = 4.5) -> dict:
    result = run_timeline(HORIZON, staff(roster), workforce, roster, inputs or [], hold_past_shift_end=hold,
                          finish=finish)
    check_invariants(result, workforce, roster)
    return result


def timeline(result: dict, employee_id: str) -> list[tuple[float, float, str, int | None]]:
    """(start, end, state, register) with attribute-only splits merged."""
    merged: list[list[Any]] = []
    for row in result["intervals"]:
        if row["employee_id"] != employee_id:
            continue
        key = (row["state"], row["register_id"], row["shift_index"])
        if merged and merged[-1][4] == key and merged[-1][1] == row["start"]:
            merged[-1][1] = row["end"]
        else:
            merged.append([row["start"], row["end"], row["state"], row["register_id"], key])
    return [(start, end, state, register) for start, end, state, register, _ in merged]


def shift_row(result: dict, employee_id: str, index: int = 0) -> dict:
    rows = [row for row in result["shifts"] if row["employee_id"] == employee_id]
    return sorted(rows, key=lambda row: row["scheduled_start"])[index]


def break_rows(result: dict, employee_id: str) -> list[dict]:
    return [row for row in result["breaks"] if row["employee_id"] == employee_id]


def at(result: dict, t: float) -> list[tuple[str, str, str, str]]:
    return [(row["stage"], row["employee_id"], row["from_state"], row["to_state"])
            for row in result["transitions"] if row["t"] == t]


def accepting_after_closing(result: dict) -> set[str]:
    return {row["employee_id"] for row in result["intervals"]
            if row["after_closing"] and row["state"] in (AVAILABLE, SERVING)}


# ── Independent invariant checker ───────────────────────────────────────────


def _merge(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(spans):
        if merged and merged[-1][1] == start:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def _near(a: float, b: float, exact: bool) -> bool:
    """Exact equality, or within float rounding for seeded runs (``exact=False``), whose instants are not
    binary-exact, so a duration recomputed as a difference can differ in the last place."""
    return a == b if exact else abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def check_invariants(result: dict, workforce: WorkforceRules, roster: list[ScheduledShift], *,
                     exact: bool = True) -> None:
    begin, finish, close, registers = result["begin"], result["finish"], result["closing_time"], result["register_count"]
    assert registers == workforce.register_count
    ids = sorted({item.employee_id for item in roster})
    rows = {employee_id: [row for row in result["intervals"] if row["employee_id"] == employee_id] for employee_id in ids}
    shifts = {employee_id: sorted((row for row in result["shifts"] if row["employee_id"] == employee_id),
                                  key=lambda row: row["scheduled_start"]) for employee_id in ids}

    for employee_id, own in rows.items():
        # 1 and 14: the intervals tile [begin, finish) with one base state at a time, no gap, no overlap.
        assert own[0]["start"] == begin and own[-1]["end"] == finish
        assert all(a["end"] == b["start"] for a, b in zip(own, own[1:]))
        for row in own:
            assert row["start"] < row["end"] and row["state"] in BASE_STATES
            # 2, 5, 6: a register exactly in the register states, one per interval, numbered 1..K.
            assert (row["register_id"] is not None) == (row["state"] in REGISTER_STATES), row
            assert row["register_id"] is None or 1 <= row["register_id"] <= registers
            assert (row["shift_index"] is None) == (row["state"] == OFF), row
            # Attributes describe the interval; they never add time (the tiling above).
            assert row["after_closing"] == (row["start"] >= close), row
            if row["shift_index"] is not None:
                scheduled_end = next(item["scheduled_end"] for item in shifts[employee_id]
                                     if item["shift_index"] == row["shift_index"])
                assert row["past_scheduled_end"] == (row["start"] >= scheduled_end), row
            else:
                assert row["past_scheduled_end"] is False
        # 14: the totals are the interval lengths by state and sum to the elapsed time exactly.
        expected = dict.fromkeys(BASE_STATES, 0.0)
        for row in own:
            expected[row["state"]] += row["end"] - row["start"]
        assert result["state_totals"][employee_id] == expected
        assert _near(sum(expected.values()), finish - begin, exact)

    # 3 and 4: at every instant, a register has at most one holder and occupancy is at most K.
    points = sorted({row[key] for own in rows.values() for row in own for key in ("start", "end")})
    for point in points[:-1]:
        held = [row["register_id"] for own in rows.values() for row in own
                if row["start"] <= point < row["end"] and row["register_id"] is not None]
        assert len(held) == len(set(held)) and len(held) <= registers

    # 7-10 and 13: breaks.
    assert len(result["breaks"]) == sum(len(item.breaks) for item in roster)
    by_shift: dict[tuple[str, int], list[dict]] = {}
    for row in result["breaks"]:
        assert row["outcome"] in BREAK_OUTCOMES  # 13
        duration = row["duration_minutes"] / 60.0
        if row["outcome"] == UNFULFILLED:
            assert row["actual_start"] is None and row["actual_end"] is None and row["unfulfilled_cause"]
            continue
        assert row["unfulfilled_cause"] is None
        assert row["scheduled_start"] <= row["due"] <= row["actual_start"]  # 7
        assert row["delay"] == row["actual_start"] - row["scheduled_start"]
        if row["outcome"] == COMPLETED:
            assert _near(row["actual_end"] - row["actual_start"], duration, exact)  # 8
        else:
            # Truncated at closing. A break reaching exactly closing may be truncated too (Phase 5B-4.4 rule 2).
            assert row["actual_end"] == close and row["actual_start"] < close
            assert close <= row["actual_start"] + duration or _near(close, row["actual_start"] + duration, exact)
        by_shift.setdefault((row["employee_id"], row["shift_index"]), []).append(row)
    for employee_id in ids:
        taken = sorted((row["actual_start"], row["actual_end"]) for row in result["breaks"]
                       if row["employee_id"] == employee_id and row["actual_start"] is not None)
        assert all(a[1] <= b[0] for a, b in zip(taken, taken[1:]))  # 9
        # ON_BREAK time is exactly the actual break time.
        on_break = [(row["start"], row["end"]) for row in rows[employee_id] if row["state"] == ON_BREAK]
        assert _merge(on_break) == _merge(taken)
    for (employee_id, index), taken_rows in by_shift.items():
        item = roster[index]
        length = item.end_minute - item.start_minute
        gap = next(rule.min_gap_minutes for rule in workforce.break_rules
                   if rule.min_shift_minutes <= length <= rule.max_shift_minutes) / 60.0
        taken_rows.sort(key=lambda row: row["actual_start"])
        for earlier, later in zip(taken_rows, taken_rows[1:]):
            minimum = earlier["actual_end"] + gap
            assert later["actual_start"] >= minimum or _near(later["actual_start"], minimum, exact)  # 10

    # 11 and 12: shifts.
    rest = workforce.shift_rules.min_minutes_between_shifts
    for employee_id in ids:
        previous_release = None
        for row in shifts[employee_id]:
            if not row["activated"]:
                assert row["not_activated_reason"] and row["release"] is None
                assert all(item["outcome"] == UNFULFILLED for item in break_rows(result, employee_id)
                           if item["shift_index"] == row["shift_index"])
                continue
            if previous_release is None:
                expected_start = row["scheduled_start"]
            else:
                assert rest is not None  # 5B-1 requires the rest whenever split shifts are allowed
                expected_start = max(row["scheduled_start"], previous_release + rest / 60.0)
            assert _near(row["actual_start"], expected_start, exact)  # 12: rest from the actual release
            assert row["activation_delay"] == row["actual_start"] - row["scheduled_start"]
            on_shift = [(item["start"], item["end"]) for item in rows[employee_id]
                        if item["shift_index"] == row["shift_index"]]
            assert _merge(on_shift) == [(row["actual_start"], row["release"])]  # 11: one shift at a time
            assert row["overrun"] == max(0.0, row["release"] - row["scheduled_end"])  # 11
            previous_release = row["release"]

    # 15 and 16: replay the transitions.
    state = dict.fromkeys(ids, OFF)
    register: dict[str, int | None] = dict.fromkeys(ids)
    wait_start: dict[str, float] = {}
    order = {stage: position for position, stage in enumerate(STAGES)}
    transitions = result["transitions"]
    position = 0
    while position < len(transitions):
        t = transitions[position]["t"]
        group = []
        while position < len(transitions) and transitions[position]["t"] == t:
            group.append(transitions[position])
            position += 1
        stages = [order[row["stage"]] for row in group]
        assert stages == sorted(stages)  # 16
        for stage in (0, 3, 4, 5, 6):  # completion, shift end, break end, break due, shift start
            members = [row["employee_id"] for row in group if order[row["stage"]] == stage]
            assert members == sorted(members)  # 16: employee_id order within a stage
        handover = [row for row in group if row["stage"] == "register_handover"]
        for row in group:
            assert row["event"].startswith("employee_")
            assert row["from_state"] == state[row["employee_id"]] and row["register_before"] == register[row["employee_id"]]
            if handover and row is handover[0]:
                # 15: earliest wait start, then employee_id; lowest-numbered free register first.
                waiting = sorted((wait_start[who], who) for who in ids if state[who] == WAITING_FOR_REGISTER)
                free = sorted(set(range(1, registers + 1)) - {value for value in register.values() if value})
                assert [(item["employee_id"], item["register_after"]) for item in handover] == [
                    (who, number) for (_, who), number in zip(waiting, free)]
            state[row["employee_id"]], register[row["employee_id"]] = row["to_state"], row["register_after"]
            if row["to_state"] == WAITING_FOR_REGISTER:
                wait_start[row["employee_id"]] = t
        # After the handover, nobody waits while a register is free.
        waiting_now = [who for who in ids if state[who] == WAITING_FOR_REGISTER]
        assert not waiting_now or sum(1 for value in register.values() if value) == registers

    # The transitions and the intervals describe the same timeline.
    for employee_id in ids:
        replayed: list[tuple[float, float, str, int | None]] = []
        current, since, holding = OFF, begin, None
        own_transitions: list[dict | None] = [row for row in transitions if row["employee_id"] == employee_id]
        for change in own_transitions + [None]:
            t = finish if change is None else change["t"]
            if t > since:
                if replayed and replayed[-1][2:] == (current, holding) and replayed[-1][1] == since:
                    replayed[-1] = (replayed[-1][0], t, current, holding)
                else:
                    replayed.append((since, t, current, holding))
                since = t
            if change is not None:
                current, holding = change["to_state"], change["register_after"]
        own = [(row["start"], row["end"], row["state"], row["register_id"]) for row in rows[employee_id]]
        merged: list[tuple[float, float, str, int | None]] = []
        for item in own:
            if merged and merged[-1][2:] == item[2:] and merged[-1][1] == item[0]:
                merged[-1] = (merged[-1][0], item[1], item[2], item[3])
            else:
                merged.append(item)
        assert merged == replayed


# ── Units, inputs, and isolation ────────────────────────────────────────────


def test_time_conversion_is_the_anonymous_engines():
    for minute in (0, 1, 7, 420, 479, 480, 481, 599, 720, 721, 1440):
        assert shared_employee_states._hours(minute, HORIZON) == shared_continuous_des._hours(minute, HORIZON)


def test_roster_precondition_x4():
    workforce = rules(registers=1)
    roster = [shift("A", 540, 660)]
    # Pay fields only are missing: INCOMPLETE and accepted.
    assert evaluate_roster(HORIZON, staff(roster), workforce, roster)["status"] == INCOMPLETE
    run(roster, workforce)
    # INVALID: two employees scheduled on one register.
    with pytest.raises(SharedSegmentError, match="INVALID"):
        run([shift("A", 540, 660), shift("B", 600, 690)], workforce)
    # INCOMPLETE because shift lengths 241-480 have no break rule: rejected.
    gap_rules = rules(BreakRule(15, 240, 0, ()), registers=1)
    with pytest.raises(SharedSegmentError, match="break_rules"):
        run(roster, gap_rules)


def test_hold_past_shift_end_has_no_default():
    roster = [shift("A", 540, 660)]
    with pytest.raises(TypeError):
        EmployeeTimeline(HORIZON, staff(roster), rules(registers=1), roster)  # type: ignore[call-arg]
    with pytest.raises(EmployeeTimelineError, match="no default"):
        EmployeeTimeline(HORIZON, staff(roster), rules(registers=1), roster, hold_past_shift_end=None)  # type: ignore[arg-type]


def test_rejected_inputs():
    workforce = rules(registers=1)
    roster = [shift("A", 540, 660)]
    with pytest.raises(EmployeeTimelineError, match="cannot start a service"):
        run(roster, workforce, [ServiceStart(0.5, "A")])  # still OFF
    with pytest.raises(EmployeeTimelineError, match="no service to complete"):
        run(roster, workforce, [ServiceCompletion(1.5, "A")])
    with pytest.raises(EmployeeTimelineError, match="only at or after closing"):
        run(roster, workforce, [Release(3.5, "A")])
    with pytest.raises(EmployeeTimelineError, match="only at closing"):
        run(roster, workforce, [CancelPendingBreaks(4.25, "A")])
    with pytest.raises(EmployeeTimelineError, match="only at closing"):
        run(roster, workforce, [EndBreakAtClosing(4.25, "A")])
    with pytest.raises(EmployeeTimelineError, match="already released"):
        run(roster, workforce, [Release(4.0, "A"), Release(4.25, "A")])
    with pytest.raises(EmployeeTimelineError, match="not on a break"):
        run(roster, workforce, [EndBreakAtClosing(4.0, "A")])
    with pytest.raises(EmployeeTimelineError, match="Unknown employee"):
        run(roster, workforce, [ServiceStart(1.5, "Z")])
    with pytest.raises(EmployeeTimelineError, match="after finish"):
        run(roster, workforce, [Release(5.0, "A")])
    # The service has no completion, so A is still on duty at finish.
    with pytest.raises(EmployeeTimelineError, match="still on duty"):
        run(roster, workforce, [ServiceStart(2.5, "A")])
    machine = EmployeeTimeline(HORIZON, staff(roster), workforce, roster, hold_past_shift_end=False)
    with pytest.raises(EmployeeTimelineError, match="process it first"):
        machine.process(1.5)  # skips the shift start at 1.0
    machine.process(1.0)
    with pytest.raises(EmployeeTimelineError, match="not after"):
        machine.process(1.0)
    with pytest.raises(EmployeeTimelineError, match="must follow process"):
        machine.start_service(1.25, "A")
    with pytest.raises(EmployeeTimelineError, match="3.0 h has not been processed"):
        machine.result(4.5)  # the shift end at 3.0 and closing are still pending


def test_no_customer_randomness_or_separate_queue_code():
    tree = ast.parse(Path(shared_employee_states.__file__).read_text(encoding="utf-8"))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imported |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    assert imported == {
        "__future__", "math", "collections.abc", "dataclasses", "numbers", "typing",
        "backend.queueing_engine.services.shared_segments", "backend.queueing_engine.services.shared_workforce",
    }


# ── Shifts ──────────────────────────────────────────────────────────────────


def test_normal_shift_start_and_end():
    # A 09:00-11:00 = 1.0-3.0 h, one register, no service.
    result = run([shift("A", 540, 660)], rules(registers=1))
    assert timeline(result, "A") == [(0.0, 1.0, OFF, None), (1.0, 3.0, AVAILABLE, 1), (3.0, 4.5, OFF, None)]
    row = shift_row(result, "A")
    assert (row["actual_start"], row["release"], row["overrun"], row["release_trigger"], row["release_basis"]) == (
        1.0, 3.0, 0.0, "employee_shift_end", "scheduled_shift_end")
    # The closing splits the final OFF time without adding to it.
    assert [(row["start"], row["end"], row["after_closing"]) for row in result["intervals"] if row["start"] >= 3.0] == [
        (3.0, 4.0, False), (4.0, 4.5, True)]
    assert result["state_totals"]["A"][OFF] == 2.5


def test_shift_end_while_serving():
    # Service 2.5-3.25 runs 0.25 h past the 3.0 shift end: no pre-shift-end cutoff.
    result = run([shift("A", 540, 660)], rules(registers=1), [ServiceStart(2.5, "A"), ServiceCompletion(3.25, "A")])
    assert timeline(result, "A") == [
        (0.0, 1.0, OFF, None), (1.0, 2.5, AVAILABLE, 1), (2.5, 3.0, SERVING, 1),
        (3.0, 3.25, SERVING_SHIFT_ENDED, 1), (3.25, 4.5, OFF, None)]
    row = shift_row(result, "A")
    assert (row["release"], row["overrun"], row["release_trigger"]) == (3.25, 0.25, "employee_service_completion")
    overrun = [item for item in result["intervals"] if item["past_scheduled_end"]]
    assert [(item["start"], item["end"], item["state"]) for item in overrun] == [(3.0, 3.25, SERVING_SHIFT_ENDED)]


def test_completion_at_the_shift_end_instant():
    # X2: the completion at 3.0 comes before the shift end, so A ends AVAILABLE -> OFF with no overrun.
    result = run([shift("A", 540, 660)], rules(registers=1), [ServiceStart(2.5, "A"), ServiceCompletion(3.0, "A")])
    assert at(result, 3.0) == [("completion", "A", SERVING, AVAILABLE), ("shift_end", "A", AVAILABLE, OFF)]
    assert timeline(result, "A")[2:] == [(2.5, 3.0, SERVING, 1), (3.0, 4.5, OFF, None)]
    assert shift_row(result, "A")["overrun"] == 0.0


def test_split_shift_overrun_delays_the_next_shift():
    # A: shift 0 is 08:00-09:00 (0-1 h), shift 1 is 09:30-11:30 (1.5-3.5 h) with a 15-minute break at
    # 10:30 (2.5 h); required rest 30 minutes. A serves 0.5-1.625, so shift 0 is released at 1.625,
    # and shift 1 activates at max(1.5, 1.625 + 0.5) = 2.125, not at 1.5 (scheduled end + rest).
    # P3 (approved for 5B-4.3): the break keeps its planned 60-minute offset from the shift start, so it
    # falls due at 2.125 + 1.0 = 3.125, not at its scheduled 2.5 (the 5B-4.2 expectation), and runs to 3.375.
    workforce = rules(BreakRule(15, 60, 0, ()), break_rule(61, 480, rest=15), registers=1, max_shifts=2, rest=30)
    roster = [shift("A", 480, 540), shift("A", 570, 690, rest=630)]
    result = run(roster, workforce, [ServiceStart(0.5, "A"), ServiceCompletion(1.625, "A")])
    assert timeline(result, "A") == [
        (0.0, 0.5, AVAILABLE, 1), (0.5, 1.0, SERVING, 1), (1.0, 1.625, SERVING_SHIFT_ENDED, 1),
        (1.625, 2.125, OFF, None), (2.125, 3.125, AVAILABLE, 1), (3.125, 3.375, ON_BREAK, None),
        (3.375, 3.5, AVAILABLE, 1), (3.5, 4.5, OFF, None)]
    (item,) = break_rows(result, "A")
    assert (item["scheduled_start"], item["due"], item["actual_start"], item["delay"]) == (2.5, 3.125, 3.125, 0.625)
    first, second = shift_row(result, "A", 0), shift_row(result, "A", 1)
    assert (first["release"], first["overrun"]) == (1.625, 0.625)
    assert (second["actual_start"], second["activation_delay"], second["release"]) == (2.125, 0.625, 3.5)
    # The time 1.5-1.625 belongs to shift 0 only: no second, simultaneous shift.
    assert [(row["start"], row["end"], row["shift_index"]) for row in result["intervals"]
            if row["start"] < 1.625 <= row["end"]] == [(1.0, 1.625, 0)]


def test_delayed_split_shift_break_keeps_its_planned_offset():
    # P3 (approved for 5B-4.3), the case 5B-4.2 left undetermined: as above, but the break is planned at
    # 10:00 (2.0 h), 30 minutes after the planned shift start 09:30, and before the delayed activation at
    # 2.125. actual_due = 2.125 + (2.0 - 1.5) = 2.625; A is AVAILABLE, so the full 15 minutes run 2.625-2.875.
    workforce = rules(BreakRule(15, 60, 0, ()), break_rule(61, 480, rest=15), registers=1, max_shifts=2, rest=30)
    roster = [shift("A", 480, 540), shift("A", 570, 690, rest=600)]
    result = run(roster, workforce, [ServiceStart(0.5, "A"), ServiceCompletion(1.625, "A")])
    assert timeline(result, "A")[3:] == [
        (1.625, 2.125, OFF, None), (2.125, 2.625, AVAILABLE, 1), (2.625, 2.875, ON_BREAK, None),
        (2.875, 3.5, AVAILABLE, 1), (3.5, 4.5, OFF, None)]
    (item,) = break_rows(result, "A")
    assert (item["scheduled_start"], item["due"], item["actual_start"], item["actual_end"], item["delay"],
            item["outcome"]) == (2.0, 2.625, 2.625, 2.875, 0.625, COMPLETED)
    assert shift_row(result, "A", 1)["scheduled_end"] == 3.5  # the scheduled end stays fixed


def test_delayed_split_shift_breaks_follow_ordinary_delay_and_gap_rules():
    # P3 then P1: shift 1 (09:30-11:30) has "first" at 09:45 and "second" at 10:15, 15 minutes each, with a
    # 15-minute minimum gap. Activation 2.125 moves the planned due times to 2.125 + 0.25 = 2.375 and
    # 2.125 + 0.75 = 2.875. A serves 2.25-2.5, so "first" falls due while serving and starts at the completion,
    # 2.5-2.75 (full length). "second" is pushed by the gap to max(2.875, 2.75 + 0.25) = 3.0 and runs 3.0-3.25.
    workforce = rules(BreakRule(15, 60, 0, ()), break_rule(61, 480, gap=15, first=15, second=15),
                      registers=1, max_shifts=2, rest=30)
    roster = [shift("A", 480, 540), shift("A", 570, 690, first=585, second=615)]
    inputs = [ServiceStart(0.5, "A"), ServiceCompletion(1.625, "A"), ServiceStart(2.25, "A"),
              ServiceCompletion(2.5, "A")]
    result = run(roster, workforce, inputs)
    assert timeline(result, "A")[4:] == [
        (2.125, 2.25, AVAILABLE, 1), (2.25, 2.375, SERVING, 1), (2.375, 2.5, SERVING_BREAK_DUE, 1),
        (2.5, 2.75, ON_BREAK, None), (2.75, 3.0, AVAILABLE, 1), (3.0, 3.25, ON_BREAK, None),
        (3.25, 3.5, AVAILABLE, 1), (3.5, 4.5, OFF, None)]
    assert [(item["name"], item["due"], item["actual_start"], item["actual_end"], item["delay"])
            for item in break_rows(result, "A")] == [
        ("first", 2.375, 2.5, 2.75, 0.75), ("second", 3.0, 3.0, 3.25, 0.75)]


def test_delayed_split_shift_break_due_at_its_fixed_end_is_unfulfilled():
    # P3: the break is planned at 11:00 (3.0 h), 90 minutes into shift 1. Activation 2.125 moves it to
    # 2.125 + 1.5 = 3.625, after the fixed shift end 3.5, so it cannot occur: A is released at 3.5 and the
    # break is unfulfilled (pending at release).
    workforce = rules(BreakRule(15, 60, 0, ()), break_rule(61, 480, rest=15), registers=1, max_shifts=2, rest=30)
    roster = [shift("A", 480, 540), shift("A", 570, 690, rest=660)]
    result = run(roster, workforce, [ServiceStart(0.5, "A"), ServiceCompletion(1.625, "A")])
    assert timeline(result, "A")[-2:] == [(2.125, 3.5, AVAILABLE, 1), (3.5, 4.5, OFF, None)]
    (item,) = break_rows(result, "A")
    assert (item["due"], item["outcome"], item["unfulfilled_cause"]) == (None, UNFULFILLED, "released")


def test_split_shift_that_cannot_start_before_its_end_is_not_activated():
    # Shift 1 is 09:30-10:00 (1.5-2.0 h); release 1.625 + rest 0.5 = 2.125 >= 2.0, so it is never worked.
    workforce = rules(registers=1, max_shifts=2, rest=30)
    roster = [shift("A", 480, 540), shift("A", 570, 600)]
    result = run(roster, workforce, [ServiceStart(0.5, "A"), ServiceCompletion(1.625, "A")])
    second = shift_row(result, "A", 1)
    assert (second["activated"], second["not_activated_reason"]) == (
        False, "rest_after_actual_release_reaches_scheduled_end")
    assert timeline(result, "A")[-1] == (1.625, 4.5, OFF, None)


def test_split_shift_not_activated_leaves_its_breaks_unfulfilled():
    # Shift 1 is 09:30-11:30 (1.5-3.5 h) with a break at 10:00. A serves 0.5-3.0, so the earliest activation
    # is 3.0 + 0.5 = 3.5, the scheduled end: the shift is never worked, and its break is unfulfilled rather
    # than undetermined (INFERRED reading: no rule moves the scheduled end).
    workforce = rules(BreakRule(15, 60, 0, ()), break_rule(61, 480, rest=15), registers=1, max_shifts=2, rest=30)
    roster = [shift("A", 480, 540), shift("A", 570, 690, rest=600)]
    result = run(roster, workforce, [ServiceStart(0.5, "A"), ServiceCompletion(3.0, "A")])
    assert shift_row(result, "A", 1)["not_activated_reason"] == "rest_after_actual_release_reaches_scheduled_end"
    (row,) = break_rows(result, "A")
    assert (row["outcome"], row["unfulfilled_cause"]) == (UNFULFILLED, "shift_not_activated")


def test_hold_applies_only_from_closing():
    # hold_past_shift_end affects shift ends at or after closing only; a 3.0 shift end still releases A.
    result = run([shift("A", 540, 660)], rules(registers=1), hold=True)
    assert shift_row(result, "A")["release"] == 3.0
    assert result["hold_past_shift_end"] is True


def test_pre_opening_shift_and_exact_partition():
    # A 07:00-09:00 (-1.0 to 1.0 h) starts before opening, so the timeline begins at -1.0 (X3).
    # B 08:00-10:00 (0-2 h) takes a 15-minute break at 09:00 (1.0 h). Two registers.
    workforce = rules(break_rule(15, 480, rest=15), registers=2)
    roster = [shift("A", 420, 540, rest=450), shift("B", 480, 600, rest=540)]
    result = run(roster, workforce)
    assert result["begin"] == -1.0
    assert timeline(result, "A") == [
        (-1.0, -0.5, AVAILABLE, 1), (-0.5, -0.25, ON_BREAK, None), (-0.25, 1.0, AVAILABLE, 1), (1.0, 4.5, OFF, None)]
    assert timeline(result, "B") == [
        (-1.0, 0.0, OFF, None), (0.0, 1.0, AVAILABLE, 2), (1.0, 1.25, ON_BREAK, None), (1.25, 2.0, AVAILABLE, 1),
        (2.0, 4.5, OFF, None)]
    # By hand: A is AVAILABLE 0.5 + 1.25, on break 0.25, OFF 3.5; B is OFF 1.0 + 2.5, AVAILABLE 1.0 + 0.75,
    # on break 0.25. Each sums to 5.5 = 4.5 - (-1.0).
    assert result["state_totals"]["A"] == {**dict.fromkeys(BASE_STATES, 0.0), AVAILABLE: 1.75, ON_BREAK: 0.25, OFF: 3.5}
    assert result["state_totals"]["B"] == {**dict.fromkeys(BASE_STATES, 0.0), AVAILABLE: 1.75, ON_BREAK: 0.25, OFF: 3.5}


# ── Registers ───────────────────────────────────────────────────────────────


def test_delayed_break_no_register_wait_and_handover():
    # One register. A 08:00-12:00 with a 15-minute break at 09:00 (1.0 h); B 09:00-09:15 (1.0-1.25 h).
    # A serves 0.5-1.125, so A's break falls due at 1.0 while serving and starts at 1.125 with its full
    # 0.25 h. B starts at 1.0, finds the register occupied, and waits until A releases it at 1.125.
    workforce = rules(BreakRule(15, 60, 0, ()), break_rule(61, 480, rest=15), registers=1)
    roster = [shift("A", 480, 720, rest=540), shift("B", 540, 555)]
    result = run(roster, workforce, [ServiceStart(0.5, "A"), ServiceCompletion(1.125, "A")])
    assert timeline(result, "A") == [
        (0.0, 0.5, AVAILABLE, 1), (0.5, 1.0, SERVING, 1), (1.0, 1.125, SERVING_BREAK_DUE, 1),
        (1.125, 1.375, ON_BREAK, None), (1.375, 4.0, AVAILABLE, 1), (4.0, 4.5, OFF, None)]
    assert timeline(result, "B") == [
        (0.0, 1.0, OFF, None), (1.0, 1.125, WAITING_FOR_REGISTER, None), (1.125, 1.25, AVAILABLE, 1),
        (1.25, 4.5, OFF, None)]
    (row,) = break_rows(result, "A")
    assert (row["due"], row["actual_start"], row["actual_end"], row["delay"], row["outcome"]) == (
        1.0, 1.125, 1.375, 0.125, COMPLETED)
    # By hand: A is AVAILABLE 0.5 + 2.625 = 3.125, SERVING 0.5, SERVING_BREAK_DUE 0.125, ON_BREAK 0.25, OFF 0.5.
    assert result["state_totals"]["A"] == {
        OFF: 0.5, WAITING_FOR_REGISTER: 0.0, AVAILABLE: 3.125, SERVING: 0.5, SERVING_BREAK_DUE: 0.125,
        SERVING_SHIFT_ENDED: 0.0, ON_BREAK: 0.25}
    assert result["state_totals"]["B"][WAITING_FOR_REGISTER] == 0.125


def test_register_handover_order():
    # Two registers. P and Q 08:00-09:00 serve past their end (until 1.5 and 1.25 h). Z and Y start at
    # 09:00 (1.0 h) and wait; X starts at 09:30 (1.5 h).
    # 1.25: Q leaves register 2. Y and Z both waited from 1.0, so employee_id decides: Y takes register 2.
    # 1.5: P leaves register 1 and Y's shift ends (register 2). Z (waiting since 1.0) comes before X (since
    #      1.5) although "X" < "Z", and takes the lowest-numbered register, 1. X takes register 2.
    roster = [shift("P", 480, 540), shift("Q", 480, 540), shift("Z", 540, 600), shift("Y", 540, 570),
              shift("X", 570, 600)]
    inputs = [ServiceStart(0.5, "P"), ServiceStart(0.5, "Q"), ServiceCompletion(1.25, "Q"), ServiceCompletion(1.5, "P")]
    result = run(roster, rules(registers=2), inputs)
    assert timeline(result, "Y") == [
        (0.0, 1.0, OFF, None), (1.0, 1.25, WAITING_FOR_REGISTER, None), (1.25, 1.5, AVAILABLE, 2), (1.5, 4.5, OFF, None)]
    assert timeline(result, "Z") == [
        (0.0, 1.0, OFF, None), (1.0, 1.5, WAITING_FOR_REGISTER, None), (1.5, 2.0, AVAILABLE, 1), (2.0, 4.5, OFF, None)]
    assert timeline(result, "X") == [(0.0, 1.5, OFF, None), (1.5, 2.0, AVAILABLE, 2), (2.0, 4.5, OFF, None)]
    handovers = [(row["t"], row["employee_id"], row["register_after"]) for row in result["transitions"]
                 if row["stage"] == "register_handover"]
    assert handovers == [(0.0, "P", 1), (0.0, "Q", 2), (1.25, "Y", 2), (1.5, "Z", 1), (1.5, "X", 2)]
    assert (shift_row(result, "P")["overrun"], shift_row(result, "Q")["overrun"]) == (0.5, 0.25)


# ── Breaks ──────────────────────────────────────────────────────────────────


def test_immediate_break():
    # A is AVAILABLE when the 15-minute break falls due at 1.0, so it starts at once (delay 0).
    workforce = rules(break_rule(15, 480, rest=15), registers=1)
    result = run([shift("A", 480, 720, rest=540)], workforce)
    assert timeline(result, "A") == [
        (0.0, 1.0, AVAILABLE, 1), (1.0, 1.25, ON_BREAK, None), (1.25, 4.0, AVAILABLE, 1), (4.0, 4.5, OFF, None)]
    (row,) = break_rows(result, "A")
    assert (row["due"], row["actual_start"], row["delay"], row["outcome"]) == (1.0, 1.0, 0.0, COMPLETED)
    assert at(result, 1.0) == [("break_due", "A", AVAILABLE, ON_BREAK)]


def test_first_break_delay_pushes_the_second():
    # A 08:00-12:00, gap 30 minutes: "first" 30 minutes at 09:00 (1.0 h), "second" 15 minutes at 10:30 (2.5 h).
    # A serves 0.75-1.75: the first break runs 1.75-2.25 (full 0.5 h), and the second falls due at
    # max(2.5, 2.25 + 0.5) = 2.75, not at its scheduled 2.5, and runs 2.75-3.0.
    workforce = rules(break_rule(15, 480, 30, first=30, second=15), registers=1)
    result = run([shift("A", 480, 720, first=540, second=630)], workforce,
                 [ServiceStart(0.75, "A"), ServiceCompletion(1.75, "A")])
    assert timeline(result, "A") == [
        (0.0, 0.75, AVAILABLE, 1), (0.75, 1.0, SERVING, 1), (1.0, 1.75, SERVING_BREAK_DUE, 1),
        (1.75, 2.25, ON_BREAK, None), (2.25, 2.75, AVAILABLE, 1), (2.75, 3.0, ON_BREAK, None),
        (3.0, 4.0, AVAILABLE, 1), (4.0, 4.5, OFF, None)]
    first, second = break_rows(result, "A")
    assert (first["due"], first["actual_start"], first["actual_end"], first["delay"]) == (1.0, 1.75, 2.25, 0.75)
    assert (second["due"], second["actual_start"], second["actual_end"], second["delay"]) == (2.75, 2.75, 3.0, 0.25)
    assert at(result, 2.5) == []  # nothing happens at the second break's scheduled start


def test_gap_push_puts_the_employee_on_duty_in_scheduled_break_time():
    # The same run: 5B-1 schedules the second break for 2.5-2.75, but A is AVAILABLE then. So before
    # closing, accepting employees can exceed the 5B-1 scheduled active count (0 here during 2.5-2.75).
    # The policy spec's INFERRED bound does not hold once delays push later breaks.
    workforce = rules(break_rule(15, 480, 30, first=30, second=15), registers=1)
    roster = [shift("A", 480, 720, first=540, second=630)]
    result = run(roster, workforce, [ServiceStart(0.75, "A"), ServiceCompletion(1.75, "A")])
    steps = evaluate_roster(HORIZON, staff(roster), workforce, roster)["active_server_steps"]
    assert {"start_minute": 630, "end_minute": 645, "active_servers": 0} in steps
    assert [(row["start"], row["end"]) for row in result["intervals"]
            if row["state"] == AVAILABLE and row["start"] <= 2.5 < row["end"]] == [(2.25, 2.75)]


def test_break_due_while_serving_is_unfulfilled_at_release():
    # A 08:00-10:00 (0-2 h) with a 30-minute break at 09:30 (1.5 h). A serves 1.25-2.25: the break falls
    # due at 1.5 while serving, the shift ends at 2.0 during the same service, and A is released at 2.25.
    # The break never started, so it is unfulfilled.
    workforce = rules(break_rule(15, 480, rest=30), registers=1)
    result = run([shift("A", 480, 600, rest=570)], workforce, [ServiceStart(1.25, "A"), ServiceCompletion(2.25, "A")])
    assert timeline(result, "A") == [
        (0.0, 1.25, AVAILABLE, 1), (1.25, 1.5, SERVING, 1), (1.5, 2.0, SERVING_BREAK_DUE, 1),
        (2.0, 2.25, SERVING_SHIFT_ENDED, 1), (2.25, 4.5, OFF, None)]
    (row,) = break_rows(result, "A")
    assert (row["due"], row["actual_start"], row["outcome"], row["unfulfilled_cause"]) == (
        1.5, None, UNFULFILLED, "released")
    assert shift_row(result, "A")["overrun"] == 0.25


def test_break_in_progress_at_shift_end_keeps_its_full_duration():
    # A 08:00-10:00 with a 30-minute break at 09:30 (1.5 h). A serves 1.25-1.75, so the break runs 1.75-2.25:
    # past the 2.0 shift end, for its full 0.5 h. A goes OFF at the break end.
    workforce = rules(break_rule(15, 480, rest=30), registers=1)
    result = run([shift("A", 480, 600, rest=570)], workforce, [ServiceStart(1.25, "A"), ServiceCompletion(1.75, "A")])
    assert timeline(result, "A")[-2:] == [(1.75, 2.25, ON_BREAK, None), (2.25, 4.5, OFF, None)]
    row = shift_row(result, "A")
    assert (row["release"], row["overrun"], row["release_trigger"]) == (2.25, 0.25, "employee_break_end")
    assert break_rows(result, "A")[0]["outcome"] == COMPLETED


# ── Closing ─────────────────────────────────────────────────────────────────

CLOSING_BREAK_RULES = rules(break_rule(15, 480, rest=30), registers=1)
CLOSING_BREAK_ROSTER = [shift("A", 600, 780, rest=705)]  # 10:00-13:00, break 11:45-12:15 (3.75-4.25 h)


def test_break_at_closing_default_finishes_and_rejoins():
    result = run(CLOSING_BREAK_ROSTER, CLOSING_BREAK_RULES, finish=5.0)
    assert timeline(result, "A") == [
        (0.0, 2.0, OFF, None), (2.0, 3.75, AVAILABLE, 1), (3.75, 4.25, ON_BREAK, None), (4.25, 5.0, AVAILABLE, 1)]
    # The break is split at closing by the attribute only.
    assert [(row["start"], row["end"], row["after_closing"]) for row in result["intervals"] if row["state"] == ON_BREAK] == [
        (3.75, 4.0, False), (4.0, 4.25, True)]
    assert break_rows(result, "A")[0]["outcome"] == COMPLETED


def test_break_at_closing_ended_at_closing():
    result = run(CLOSING_BREAK_ROSTER, CLOSING_BREAK_RULES, [EndBreakAtClosing(4.0, "A")], finish=5.0)
    assert timeline(result, "A")[2:] == [(3.75, 4.0, ON_BREAK, None), (4.0, 5.0, AVAILABLE, 1)]
    (row,) = break_rows(result, "A")
    assert (row["actual_start"], row["actual_end"], row["outcome"]) == (3.75, 4.0, TRUNCATED_BY_CLOSING)


def test_break_at_closing_then_ineligible():
    # Release while on the break: the break keeps its full duration and A goes OFF at its end.
    result = run(CLOSING_BREAK_ROSTER, CLOSING_BREAK_RULES, [Release(4.0, "A")], finish=5.0)
    assert timeline(result, "A")[2:] == [(3.75, 4.25, ON_BREAK, None), (4.25, 5.0, OFF, None)]
    row = shift_row(result, "A")
    assert (row["release"], row["release_trigger"], row["release_basis"], row["overrun"]) == (
        4.25, "employee_break_end", "release_input", 0.0)
    # Ending the break at closing and releasing: OFF at 4.0. The inputs apply in their given order.
    result = run(CLOSING_BREAK_ROSTER, CLOSING_BREAK_RULES, [EndBreakAtClosing(4.0, "A"), Release(4.0, "A")])
    assert timeline(result, "A")[2:] == [(3.75, 4.0, ON_BREAK, None), (4.0, 4.5, OFF, None)]
    assert at(result, 4.0) == [("closing_input", "A", ON_BREAK, WAITING_FOR_REGISTER),
                               ("closing_input", "A", WAITING_FOR_REGISTER, OFF)]
    result = run(CLOSING_BREAK_ROSTER, CLOSING_BREAK_RULES, [Release(4.0, "A"), EndBreakAtClosing(4.0, "A")])
    assert at(result, 4.0) == [("closing_input", "A", ON_BREAK, OFF)]
    assert shift_row(result, "A")["release_trigger"] == "employee_break_truncated_at_closing"


# HARD_CUTOFF: A and B 11:30-13:00 (3.5-5.0 h); C 10:00-13:00 (2.0-5.0 h) with a 30-minute break at 11:45
# (3.75 h). Three registers. B serves 3.5-4.25 and C serves 3.5-4.5 (C's break falls due at 3.75 while
# serving). No service starts after closing; the state machine only represents who is released when.
HARD_RULES = rules(BreakRule(15, 120, 0, ()), break_rule(121, 480, rest=30), registers=3)
HARD_ROSTER = [shift("A", 690, 780), shift("B", 690, 780), shift("C", 600, 780, rest=705)]
HARD_SERVICE = [ServiceStart(3.5, "B"), ServiceStart(3.5, "C"), ServiceCompletion(4.25, "B"),
                ServiceCompletion(4.5, "C")]


def test_hard_cutoff_released_at_last_completion():
    inputs = HARD_SERVICE + [Release(4.0, "A"), Release(4.0, "B"), Release(4.0, "C")]
    result = run(HARD_ROSTER, HARD_RULES, inputs)
    assert at(result, 4.0) == [("closing_input", "A", AVAILABLE, OFF),
                               ("closing_input", "B", SERVING, SERVING_SHIFT_ENDED),
                               ("closing_input", "C", SERVING_BREAK_DUE, SERVING_SHIFT_ENDED)]
    assert [shift_row(result, who)["release"] for who in "ABC"] == [4.0, 4.25, 4.5]
    assert {shift_row(result, who)["release_basis"] for who in "ABC"} == {"release_input"}
    (row,) = break_rows(result, "C")
    assert (row["outcome"], row["unfulfilled_cause"]) == (UNFULFILLED, "released")
    assert accepting_after_closing(result) == set()


def test_hard_cutoff_released_at_scheduled_end_with_pending_break():
    result = run(HARD_ROSTER, HARD_RULES, HARD_SERVICE, finish=5.0)
    # C took register 1 at 2.0 (alone); A and B took 2 and 3 at 3.5.
    assert timeline(result, "C") == [
        (0.0, 2.0, OFF, None), (2.0, 3.5, AVAILABLE, 1), (3.5, 3.75, SERVING, 1), (3.75, 4.5, SERVING_BREAK_DUE, 1),
        (4.5, 5.0, ON_BREAK, None)]
    (row,) = break_rows(result, "C")
    assert (row["due"], row["actual_start"], row["actual_end"], row["outcome"]) == (3.75, 4.5, 5.0, COMPLETED)
    # At 5.0 the shift end comes before the break end; the break end releases C.
    assert at(result, 5.0) == [("shift_end", "A", AVAILABLE, OFF), ("shift_end", "B", AVAILABLE, OFF),
                               ("break_end", "C", ON_BREAK, OFF)]
    assert [shift_row(result, who)["release"] for who in "ABC"] == [5.0, 5.0, 5.0]


def test_hard_cutoff_pending_break_cancelled_at_closing():
    result = run(HARD_ROSTER, HARD_RULES, HARD_SERVICE + [CancelPendingBreaks(4.0, "C")], finish=5.0)
    assert at(result, 4.0) == [("closing_input", "C", SERVING_BREAK_DUE, SERVING)]
    assert timeline(result, "C")[-2:] == [(4.0, 4.5, SERVING, 1), (4.5, 5.0, AVAILABLE, 1)]
    (row,) = break_rows(result, "C")
    assert (row["due"], row["outcome"], row["unfulfilled_cause"]) == (3.75, UNFULFILLED, "cancelled_at_closing")


def test_hard_cutoff_break_taken_then_released():
    # A Release applied at C's completion instant comes after the completion (X2 then closing inputs),
    # so C takes the full break and goes OFF at its end.
    result = run(HARD_ROSTER, HARD_RULES, HARD_SERVICE + [Release(4.5, "C")], finish=5.0)
    assert at(result, 4.5) == [("completion", "C", SERVING_BREAK_DUE, ON_BREAK)]
    row = shift_row(result, "C")
    assert (row["release"], row["release_trigger"], row["release_basis"]) == (5.0, "employee_break_end", "release_input")


def test_break_due_completion_at_closing_with_cancel_starts_no_break():
    # Phase 5B-4.4 rule 1. C serves 3.5-4.0 with its break due at 3.75, so the completion falls exactly at
    # closing. With C's CancelPendingBreaks at closing, the completion comes first and leaves C AVAILABLE (no
    # break starts), the cancel makes the break unfulfilled (cancelled_at_closing), and the Release sends C OFF
    # at 4.0: no zero-length break exists.
    service = [ServiceStart(3.5, "C"), ServiceCompletion(4.0, "C")]
    result = run(HARD_ROSTER, HARD_RULES, service + [CancelPendingBreaks(4.0, "C"), Release(4.0, "C")], finish=5.0)
    assert at(result, 4.0) == [("completion", "C", SERVING_BREAK_DUE, AVAILABLE), ("closing_input", "C", AVAILABLE, OFF)]
    (row,) = break_rows(result, "C")
    assert (row["due"], row["actual_start"], row["actual_end"], row["outcome"], row["unfulfilled_cause"]) == (
        3.75, None, None, UNFULFILLED, "cancelled_at_closing")
    shift_c = shift_row(result, "C")
    assert (shift_c["release"], shift_c["release_basis"], shift_c["release_trigger"]) == (
        4.0, "release_input", "employee_release_input")
    assert not [item for item in result["intervals"] if item["employee_id"] == "C" and item["state"] == ON_BREAK]
    # Without a cancel at closing the machine keeps its policy-free behavior: the break starts at the
    # completion and, with a Release, C goes OFF at the break end.
    result = run(HARD_ROSTER, HARD_RULES, service + [Release(4.0, "C")], finish=5.0)
    assert at(result, 4.0) == [("completion", "C", SERVING_BREAK_DUE, ON_BREAK)]
    assert break_rows(result, "C")[0]["actual_start"] == 4.0 and shift_row(result, "C")["release"] == 4.5


# DRAIN crew: A 11:30-13:00 (3.5-5.0 h); B 10:00-12:00 (2.0-4.0 h) serving 3.75-4.125; C 10:00-13:00 with a
# 30-minute break at 11:45 (3.75-4.25 h); D 12:15-13:00 (4.25-5.0 h). Three registers.
# At closing (4.0): A is AVAILABLE, B is SERVING and its shift ends at closing, C is on a break, and D has
# not started.
DRAIN_RULES = rules(BreakRule(15, 150, 0, ()), break_rule(151, 480, rest=30), registers=3)
DRAIN_ROSTER = [shift("A", 690, 780), shift("B", 600, 720), shift("C", 600, 780, rest=705), shift("D", 735, 780)]


def test_drain_crew_a_accepting_before_closing():
    # (a) with no cap: hold shift ends from closing on; C and D are made ineligible at closing; A and B
    # serve until released at 4.5.
    inputs = [ServiceStart(3.75, "B"), Release(4.0, "C"), Release(4.0, "D"), ServiceCompletion(4.125, "B"),
              Release(4.5, "A"), Release(4.5, "B")]
    result = run(DRAIN_ROSTER, DRAIN_RULES, inputs, hold=True, finish=5.0)
    assert accepting_after_closing(result) == {"A", "B"}
    assert timeline(result, "B")[-3:] == [(3.75, 4.125, SERVING, 1), (4.125, 4.5, AVAILABLE, 1), (4.5, 5.0, OFF, None)]
    b = shift_row(result, "B")
    assert (b["release"], b["overrun"], b["release_basis"], b["release_trigger"]) == (
        4.5, 0.5, "release_input", "employee_release_input")
    assert [(row["start"], row["end"], row["state"]) for row in result["intervals"]
            if row["employee_id"] == "B" and row["past_scheduled_end"]] == [(4.0, 4.125, SERVING), (4.125, 4.5, AVAILABLE)]
    c = shift_row(result, "C")
    assert (c["release"], c["release_trigger"]) == (4.25, "employee_break_end")
    d = shift_row(result, "D")
    assert (d["activated"], d["not_activated_reason"]) == (False, "released_after_closing")


def test_drain_crew_b_shift_runs_past_closing():
    # (b): no hold, so B leaves at its closing-time shift end after the service; A, C, and D work to 5.0.
    # At 4.25 C (back from break) and D (starting) both wait from 4.25; by employee_id C takes register 1
    # (freed by B at 4.125) and D takes register 2 (freed by C at 3.75).
    inputs = [ServiceStart(3.75, "B"), ServiceCompletion(4.125, "B")]
    result = run(DRAIN_ROSTER, DRAIN_RULES, inputs, finish=5.0)
    assert accepting_after_closing(result) == {"A", "C", "D"}
    b = shift_row(result, "B")
    assert (b["release"], b["overrun"], b["release_basis"]) == (4.125, 0.125, "scheduled_shift_end")
    assert timeline(result, "C")[-1] == (4.25, 5.0, AVAILABLE, 1)
    assert timeline(result, "D")[-1] == (4.25, 5.0, AVAILABLE, 2)


def test_drain_crew_c_includes_returning_and_late_starters():
    # (c): hold, and nobody is made ineligible at closing. B holds register 1 past its shift end, so at 4.25
    # C takes the only free register (2) and D waits until B is released at 4.5.
    inputs = [ServiceStart(3.75, "B"), ServiceCompletion(4.125, "B"), Release(4.5, "B"), Release(4.75, "A"),
              Release(4.75, "C"), Release(4.75, "D")]
    result = run(DRAIN_ROSTER, DRAIN_RULES, inputs, hold=True, finish=5.0)
    assert accepting_after_closing(result) == {"A", "B", "C", "D"}
    assert timeline(result, "D") == [
        (0.0, 4.25, OFF, None), (4.25, 4.5, WAITING_FOR_REGISTER, None), (4.5, 4.75, AVAILABLE, 1), (4.75, 5.0, OFF, None)]
    assert timeline(result, "C")[-2:] == [(4.25, 4.75, AVAILABLE, 2), (4.75, 5.0, OFF, None)]


# ── Whole-minute arithmetic (Phase 5B-4.3) ──────────────────────────────────
# A 5-minute grid: (m - 480) / 60 is not binary-exact, and adding minutes in hours can miss the
# exact conversion of the summed minute by one unit in the last place. The guards below show that
# each case is one of those.


def _five_minute_rules(max_shifts: int = 1, between: int | None = None, **durations: int) -> WorkforceRules:
    rule = BreakRule(5, 480, 0, tuple(BreakRequirement(name, minutes, True, 0, 480)
                                      for name, minutes in durations.items()))
    return WorkforceRules(ShiftRules(0, 1440, 5, 480, 5, max_shifts, between), (rule,), 2)


def _hours(minute: int) -> float:
    return (minute - HORIZON.start_minute) / 60.0


def test_break_ending_at_the_shift_end_in_minutes_ends_there_exactly():
    # A 08:00-08:50 with a 10-minute break at 08:40; B 08:00-09:20 with a 10-minute break at 09:10. Each
    # break ends at its shift end in minutes. In hours, the naive sums fall one unit below (A) and above (B)
    # the shift end; the machine now adds the minutes first, so each break ends at the shift end, completes,
    # and releases with no overrun and no sliver of AVAILABLE time.
    assert _hours(520) + 10 / 60 < _hours(530) and _hours(550) + 10 / 60 > _hours(560)
    workforce = _five_minute_rules(rest=10)
    roster = [shift("A", 480, 530, rest=520), shift("B", 480, 560, rest=550)]
    result = run_timeline(HORIZON, staff(roster), workforce, roster, [], hold_past_shift_end=False, finish=4.5)
    for employee_id, start, end in (("A", 520, 530), ("B", 550, 560)):
        assert timeline(result, employee_id) == [
            (0.0, _hours(start), AVAILABLE, 1 if employee_id == "A" else 2),
            (_hours(start), _hours(end), ON_BREAK, None), (_hours(end), 4.5, OFF, None)]
        row = shift_row(result, employee_id)
        assert (row["release"], row["overrun"]) == (_hours(end), 0.0)
        (item,) = break_rows(result, employee_id)
        assert (item["actual_end"], item["outcome"]) == (_hours(end), COMPLETED)


def test_split_shift_rest_ending_at_the_next_start_in_minutes_is_on_time():
    # A works 08:00-08:35 and 08:55-10:00 with a required rest of 20 minutes. Released at 08:35, A may
    # start again at 08:55 exactly; the naive hour sum is one unit later, which would record a delay.
    assert _hours(515) + 20 / 60 > _hours(535)
    workforce = _five_minute_rules(max_shifts=2, between=20)
    roster = [shift("A", 480, 515), shift("A", 535, 600)]
    result = run_timeline(HORIZON, staff(roster), workforce, roster, [], hold_past_shift_end=False, finish=4.5)
    second = shift_row(result, "A", 1)
    assert (second["actual_start"], second["activation_delay"]) == (_hours(535), 0.0)


def test_snapshot_reports_state_register_and_break_end():
    # A 08:00-12:00 with a 30-minute break at 09:00 (1.0 h); one register.
    machine = EmployeeTimeline(HORIZON, staff([shift("A", 480, 720, rest=540)]),
                               rules(break_rule(15, 480, rest=30), registers=1),
                               [shift("A", 480, 720, rest=540)], hold_past_shift_end=False)
    assert machine.snapshot() == {"A": {"state": OFF, "register_id": None, "current_break_end": None}}
    machine.process(0.0)
    assert machine.snapshot() == {"A": {"state": AVAILABLE, "register_id": 1, "current_break_end": None}}
    machine.process(1.0)
    assert machine.snapshot() == {"A": {"state": ON_BREAK, "register_id": None, "current_break_end": 1.5}}


# ── Same-time order ─────────────────────────────────────────────────────────


def test_same_time_order_x2():
    # Two registers; every employee-only stage happens at 2.0 h (10:00):
    #   A 09:00-10:00 completes a service at 2.0 (completion) and its shift ends (shift end);
    #   B 09:30-11:30 took an offset-0, 30-minute break 1.5-2.0 (break end);
    #   E 08:00-12:00 has a 30-minute break at 10:00 (break due);
    #   D 10:00-10:30 starts (shift start).
    # Then B and D, both waiting from 2.0, take registers 1 and 2 by employee_id.
    workforce = rules(BreakRule(15, 60, 0, ()), break_rule(61, 480, rest=30), registers=2)
    roster = [shift("E", 480, 720, rest=600), shift("A", 540, 600), shift("B", 570, 690, rest=570),
              shift("D", 600, 630)]
    result = run(roster, workforce, [ServiceStart(1.5, "A"), ServiceCompletion(2.0, "A")])
    assert at(result, 2.0) == [
        ("completion", "A", SERVING, AVAILABLE),
        ("shift_end", "A", AVAILABLE, OFF),
        ("break_end", "B", ON_BREAK, WAITING_FOR_REGISTER),
        ("break_due", "E", AVAILABLE, ON_BREAK),
        ("shift_start", "D", OFF, WAITING_FOR_REGISTER),
        ("register_handover", "B", WAITING_FOR_REGISTER, AVAILABLE),
        ("register_handover", "D", WAITING_FOR_REGISTER, AVAILABLE),
    ]
    assert at(result, 1.5) == [("shift_start", "B", OFF, ON_BREAK), ("service_start", "A", AVAILABLE, SERVING)]
    # 2.5: D's shift end frees register 2 before E's break end, so E returns to register 2.
    assert timeline(result, "E")[-2:] == [(2.5, 4.0, AVAILABLE, 2), (4.0, 4.5, OFF, None)]
    # The assignment pass comes last: E is on its break at 2.0 and cannot start a service.
    with pytest.raises(EmployeeTimelineError, match="cannot start a service"):
        run(roster, workforce, [ServiceStart(1.5, "A"), ServiceCompletion(2.0, "A"), ServiceStart(2.0, "E")])


def test_same_stage_events_follow_employee_id():
    # A and B (08:00-10:00, two registers) complete at the same instant; the inputs name B first.
    roster = [shift("B", 480, 600), shift("A", 480, 600)]
    inputs = [ServiceStart(0.5, "B"), ServiceStart(0.5, "A"), ServiceCompletion(1.0, "B"), ServiceCompletion(1.0, "A")]
    result = run(roster, rules(registers=2), inputs)
    assert at(result, 1.0) == [("completion", "A", SERVING, AVAILABLE), ("completion", "B", SERVING, AVAILABLE)]
    # Service starts keep their input order (the caller's assignment pass).
    assert at(result, 0.5) == [("service_start", "B", AVAILABLE, SERVING), ("service_start", "A", AVAILABLE, SERVING)]
    assert at(result, 2.0) == [("shift_end", "A", AVAILABLE, OFF), ("shift_end", "B", AVAILABLE, OFF)]
