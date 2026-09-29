"""Phase 5B-4.5 playback of one named-employee shared-queue DES replication.

ALL EMPLOYEES, AVAILABILITY, RULES, ROSTERS, DEMAND, ARRIVALS, AND SERVICE WORK IN THIS FILE ARE SYNTHETIC TEST
DATA. They are not NovaMart records, labor law, or recommended operating values.

The hand-computed cases reuse the Phase 5B-4.3 days (horizon 08:00-12:00, hours 0-4, closing 4.0, service rate 4
per hour, binary-exact times), whose customer results were derived by hand there; the expected playback event
sequences below are derived by hand from the named engine's recording order (spec, "Recording order"). Seeded tests
assert properties only; no seeded value is compared with a stored golden value (numpy stream equality across versions
is UNKNOWN). Corrupted traces are built by editing a deep copy of an engine result; the engine is never changed.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import inspect
import random
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from backend.queueing_engine.services.shared_segments import DemandPeriod, SharedSegmentError, StaffingSegment
from backend.queueing_engine.simulation import shared_named_playback
from backend.queueing_engine.simulation.shared_employee_states import (
    AVAILABLE,
    BASE_STATES,
    COMPLETED,
    OFF,
    ON_BREAK,
    SERVING,
    SERVING_BREAK_DUE,
    SERVING_SHIFT_ENDED,
    STAGES,
    TRUNCATED_BY_CLOSING,
    UNFULFILLED,
    WAITING_FOR_REGISTER,
)
from backend.queueing_engine.simulation.shared_named_des import (
    APPROVED_EMPLOYEE_POLICY,
    HARD_CUTOFF_REASON,
    NO_ELIGIBLE_EMPLOYEE,
    simulate_named_prescribed,
)
from backend.queueing_engine.simulation.shared_named_playback import (
    CUSTOMER_EVENT_TYPES,
    EMPLOYEE_TRANSITIONS,
    NOT_PRODUCED_BY_THE_NAMED_ENGINE,
    NamedPlaybackError,
    playback_from_named_replications,
    prepare_named_playback,
    rebuild_named_inputs,
    replay_named_trace,
)
from backend.queueing_engine.simulation.shared_named_replications import (
    named_inputs_digest,
    named_inputs_snapshot,
    named_replication_row,
    replication_seed_sequence,
    run_named_replications,
    simulate_named_replication,
)
from tests.test_shared_employee_states import HORIZON, break_rule, rules, shift, staff
from tests.test_shared_named_des import CLOSING_ARRIVALS, CLOSING_ROSTER, CLOSING_RULES, LONG_SHIFT_BREAK
from tests.test_shared_named_replications import SCENARIOS, replicate

# ── SYNTHETIC TEST DATA ──────────────────────────────────────────────────────

DRAIN, HARD_CUTOFF = "DRAIN", "HARD_CUTOFF"
CLOSE = 4.0
PERIODS = [DemandPeriod("P", 480, 720, 10.0, 4.0)]
ONE = [StaffingSegment("S", 480, 720, 1)]
TWO = [StaffingSegment("S", 480, 720, 2)]
THREE = [StaffingSegment("S", 480, 720, 3)]


def simulate(roster: list, workforce: Any, arrivals: list[tuple[float, float]], *, policy: str = DRAIN,
             required: list[StaffingSegment] | None = None) -> dict:
    return simulate_named_prescribed(HORIZON, PERIODS, staff(roster), workforce, roster, arrivals,
                                     closing_policy=policy, employee_policy=APPROVED_EMPLOYEE_POLICY,
                                     required_staffing=required or ONE)


def accepted(result: dict) -> dict:
    checked = replay_named_trace(result, HORIZON, PERIODS)
    assert checked["valid"], checked.get("failure")
    return checked


def rejected(result: dict, check: str) -> dict:
    checked = replay_named_trace(result, HORIZON, PERIODS)
    assert not checked["valid"], "a corrupted trace was accepted"
    assert checked["failure"]["check"] == check, checked["failure"]
    return checked["failure"]


def compact(checked: dict, t: float | None = None) -> list[tuple]:
    """(source, type, customer or employee, from, to) per playback event, optionally at one instant."""
    return [(event["source"], event["type"], event["customer_id"] if event["source"] == "customer_trace"
             else event["employee_id"], event["employee_state_before"], event["employee_state_after"])
            for event in checked["events"] if t is None or event["t"] == t]


def transitions(result: dict) -> list[dict]:
    rows: list[dict] = result["employee_timeline"]["transitions"]
    return rows


def drop_transition(result: dict, index: int) -> None:
    """Remove transition ``index`` and keep every customer event's interleaving count consistent."""
    del result["employee_timeline"]["transitions"][index]
    for event in result["trace"]:
        if event["employee_transitions_before"] > index:
            event["employee_transitions_before"] -= 1


# Prescribed days used below (all derived by hand in tests/test_shared_named_des.py unless stated).
NORMAL = ([shift("A", 480, 720)], rules(registers=1), [(0.5, 1.0), (0.625, 0.5), (2.0, 2.0)])
FCFS = ([shift(name, 480, 720) for name in "ABC"], rules(registers=3),
        [(1.0, 2.0), (1.0, 1.0), (1.0, 3.0), (1.0, 0.5), (1.125, 0.5)])
X1 = ([shift(name, 480, 720) for name in "ABC"], rules(registers=3),
      [(0.5, 1.0), (0.625, 1.0), (1.0, 4.0), (1.125, 3.5), (1.25, 3.0), (2.5, 1.0)])
HANDOVER = ([shift("A", 480, 600), shift("B", 600, 720)], rules(registers=1), [(1.75, 2.0), (2.125, 1.0)])
SURPLUS = ([shift(name, 480, 720) for name in "ABC"], rules(registers=3), [(0.5, 1.0)])

# Prescribed days that reach the transitions the seeded scenarios do not (probed in this phase; see the spec).
COVERAGE: dict[str, tuple[list, Any, list[tuple[float, float]], str]] = {
    # A 08:00-11:30 serves #1 3.25-4.25 past its shift end; B's 11:30 shift waits for the only register and is
    # released at closing while waiting (closing_input WAITING_FOR_REGISTER -> OFF).
    "waiting_released_at_closing": ([shift("A", 480, 690), shift("B", 690, 780)], rules(registers=1),
                                    [(3.25, 4.0)], DRAIN),
    # A 08:00-10:00 is idle at its shift end (shift_end AVAILABLE -> OFF).
    "idle_shift_end": ([shift("A", 480, 600), shift("B", 600, 720)], rules(registers=2), [(0.5, 1.0)], DRAIN),
    # B's 11:30-11:45 shift ends while B waits for A's register (shift_end WAITING_FOR_REGISTER -> OFF).
    "waiting_at_own_shift_end": ([shift("A", 480, 690), shift("B", 690, 705)], rules(registers=1),
                                 [(3.25, 4.0)], DRAIN),
    # A's break is due at 2.5 during #1 (2.25-3.25) and A's shift ends at 3.0 (shift_end SERVING_BREAK_DUE ->
    # SERVING_SHIFT_ENDED); the break is never taken.
    "break_due_then_shift_end": ([shift("A", 480, 660, rest=630)], rules(break_rule(15, 480, rest=15), registers=1),
                                 [(2.25, 4.0)], DRAIN),
    # A's 30-minute break is delayed by #1 (2.25-2.75) to 2.75-3.25, past the 3.0 shift end (break_end ON_BREAK ->
    # OFF).
    "break_past_shift_end": ([shift("A", 480, 660, rest=630)], rules(break_rule(15, 480, rest=30), registers=1),
                             [(2.25, 2.0)], DRAIN),
    # B waits for A's register from 3.5 and B's break falls due at 3.75 while waiting (break_due
    # WAITING_FOR_REGISTER -> ON_BREAK); it is truncated at closing.
    "break_due_while_waiting": ([shift("A", 480, 690, rest=540), shift("B", 690, 780, rest=705)],
                                rules(break_rule(15, 480, rest=15), registers=1), [(3.25, 4.0)], DRAIN),
    # A's break is scheduled at the shift start (shift_start OFF -> ON_BREAK).
    "break_at_shift_start": ([shift("A", 480, 720, rest=480)], rules(break_rule(15, 480, rest=15), registers=1),
                             [(1.0, 1.0)], DRAIN),
    # Approved rule 1: a break-due service completing exactly at closing (completion SERVING_BREAK_DUE -> AVAILABLE).
    "rule_1": ([shift("A", 480, 720, rest=690)], rules(*LONG_SHIFT_BREAK, registers=1),
               [(3.25, 3.0), (3.75, 1.0)], DRAIN),
    # The 5B-4.3 day test_break_due_service_across_closing_finishes_then_releases: #1 3.25-4.25 with the break due
    # at 3.5, so A is released at closing while SERVING_BREAK_DUE (closing_input -> SERVING_SHIFT_ENDED).
    "break_due_across_closing": ([shift("A", 480, 720, rest=690)], rules(*LONG_SHIFT_BREAK, registers=1),
                                 [(3.25, 4.0), (3.75, 1.0)], DRAIN),
}


def coverage(name: str) -> dict:
    roster, workforce, arrivals, policy = COVERAGE[name]
    return simulate(roster, workforce, arrivals, policy=policy)


# ── Event vocabulary ────────────────────────────────────────────────────────


def test_vocabulary_is_the_state_machines_named_engine_subset():
    states, stages = set(BASE_STATES), set(STAGES)
    for stage, event, before, after in EMPLOYEE_TRANSITIONS:
        assert stage in stages and before in states and after in states and event.startswith("employee_")
    assert not set(EMPLOYEE_TRANSITIONS) & set(NOT_PRODUCED_BY_THE_NAMED_ENGINE)
    assert set(CUSTOMER_EVENT_TYPES) == {"arrival", "service_start", "service_end", "closing", "unserved_at_close"}
    assert len(EMPLOYEE_TRANSITIONS) == 22


def test_every_vocabulary_entry_is_produced_by_the_engine_and_accepted():
    # The vocabulary is derived from the engine code; this shows each entry is actually produced, on prescribed days
    # only (no seeded coverage): the coverage days, the ordinary day, the handover day, and the closing day under
    # HARD_CUTOFF. Every replay passes.
    days = [coverage(name) for name in COVERAGE] + [
        simulate(*NORMAL), simulate(*HANDOVER),
        simulate(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, policy=HARD_CUTOFF, required=TWO)]
    seen_transitions: set[tuple] = set()
    seen_types: set[str] = set()
    for result in days:
        accepted(result)
        seen_transitions |= {(row["stage"], row["event"], row["from_state"], row["to_state"]) for row in transitions(result)}
        seen_types |= {row["type"] for row in result["trace"]}
    assert seen_transitions == set(EMPLOYEE_TRANSITIONS)
    assert seen_types == set(CUSTOMER_EVENT_TYPES)


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_seeded_replications_are_accepted(policy):
    # Every seeded scenario, 6 replications each; each replay uses that scenario's own demand periods.
    for name, (demand, roster, workforce, required) in SCENARIOS.items():
        for index in range(6):
            result = simulate_named_replication(
                HORIZON, demand, staff(roster), workforce, roster, seed_sequence=replication_seed_sequence(5, index),
                closing_policy=policy, employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=required)
            checked = replay_named_trace(result, HORIZON, demand)
            assert checked["valid"], (name, index, checked.get("failure"))
            assert set(checked["events"][0]) >= {"seq", "source", "source_index", "t", "type", "queue_len_after"}


@pytest.mark.parametrize("name", sorted(COVERAGE))
def test_coverage_days_reach_their_transition(name):
    target = {
        "waiting_released_at_closing": ("closing_input", "employee_release_input", WAITING_FOR_REGISTER, OFF),
        "idle_shift_end": ("shift_end", "employee_shift_end", AVAILABLE, OFF),
        "waiting_at_own_shift_end": ("shift_end", "employee_shift_end", WAITING_FOR_REGISTER, OFF),
        "break_due_then_shift_end": ("shift_end", "employee_shift_end", SERVING_BREAK_DUE, SERVING_SHIFT_ENDED),
        "break_past_shift_end": ("break_end", "employee_break_end", ON_BREAK, OFF),
        "break_due_while_waiting": ("break_due", "employee_break_start", WAITING_FOR_REGISTER, ON_BREAK),
        "break_at_shift_start": ("shift_start", "employee_break_start_at_shift_start", OFF, ON_BREAK),
        "rule_1": ("completion", "employee_service_completion", SERVING_BREAK_DUE, AVAILABLE),
        "break_due_across_closing": ("closing_input", "employee_release_input", SERVING_BREAK_DUE, SERVING_SHIFT_ENDED),
    }[name]
    result = coverage(name)
    accepted(result)
    assert target in {(row["stage"], row["event"], row["from_state"], row["to_state"]) for row in transitions(result)}


# ── Hand-computed traces ────────────────────────────────────────────────────


def test_ordinary_service_follows_the_engine_recording_order():
    # One employee, one register. At 0.0 A's shift starts and takes register 1. #1 arrives 0.5 and A starts it; #2
    # arrives 0.625 and waits. At 0.75 #1's service_end is recorded, then A's completion, then A takes #2. At 2.0
    # #3 arrives and is started. At closing (A idle, nobody waiting) the closing event comes first and A is
    # released (DRAIN crew member left idle).
    checked = accepted(simulate(*NORMAL))
    C, E = "customer_trace", "employee_transition"
    assert compact(checked) == [
        (E, "employee_shift_start", "A", OFF, WAITING_FOR_REGISTER),
        (E, "employee_register_assigned", "A", WAITING_FOR_REGISTER, AVAILABLE),
        (C, "arrival", 1, None, None),
        (E, "employee_service_start", "A", AVAILABLE, SERVING), (C, "service_start", 1, None, None),
        (C, "arrival", 2, None, None),
        (C, "service_end", 1, None, None), (E, "employee_service_completion", "A", SERVING, AVAILABLE),
        (E, "employee_service_start", "A", AVAILABLE, SERVING), (C, "service_start", 2, None, None),
        (C, "service_end", 2, None, None), (E, "employee_service_completion", "A", SERVING, AVAILABLE),
        (C, "arrival", 3, None, None),
        (E, "employee_service_start", "A", AVAILABLE, SERVING), (C, "service_start", 3, None, None),
        (C, "service_end", 3, None, None), (E, "employee_service_completion", "A", SERVING, AVAILABLE),
        (C, "closing", None, None, None), (E, "employee_release_input", "A", AVAILABLE, OFF)]
    events = checked["events"]
    assert [event["seq"] for event in events] == list(range(19))
    assert [(event["queue_len_before"], event["queue_len_after"]) for event in events[4:7]] == [(1, 0), (0, 1), (1, 1)]
    # Per-event counts follow the recording order: at #1's service_end A is still SERVING until its completion.
    assert (events[6]["busy_employees_after"], events[7]["busy_employees_after"]) == (1, 0)
    assert [(row["t"], row["queue_len"], row["accepting_capacity"], row["busy_employees"], row["register_occupancy"])
            for row in checked["instants"]] == [
        (0.0, 0, 1, 0, 1), (0.5, 0, 1, 1, 1), (0.625, 1, 1, 1, 1), (0.75, 0, 1, 1, 1), (0.875, 0, 1, 0, 1),
        (2.0, 0, 1, 1, 1), (2.5, 0, 1, 0, 1), (4.0, 0, 0, 0, 0)]
    assert [event["period"] for event in events][-2:] == ["closing", "closing"]
    assert events[-2]["drain_crew"] == ["A"] and events[-2]["closing_policy"] == DRAIN


def test_several_events_at_one_timestamp_merge_in_the_recorded_order():
    # FCFS day (A, B, C; three registers). At 0.0 three shift starts then three handovers (employee_id order; P4
    # gives registers 1, 2, 3). At 1.0 four arrivals are recorded after the instant's stages (none), then three
    # start pairs in X1 order (all AVAILABLE since 0.0; ties by id). At 1.5 two service_ends (customer_id order 1, 5)
    # precede two completions (employee_id order A, B). At closing all three are idle and released A, B, C.
    result = simulate(*FCFS, required=THREE)
    checked = accepted(result)
    C, E = "customer_trace", "employee_transition"
    assert compact(checked, 0.0) == [(E, "employee_shift_start", name, OFF, WAITING_FOR_REGISTER) for name in "ABC"] + [
        (E, "employee_register_assigned", name, WAITING_FOR_REGISTER, AVAILABLE) for name in "ABC"]
    assert compact(checked, 1.0) == [(C, "arrival", number, None, None) for number in (1, 2, 3, 4)] + [
        item for name, number in zip("ABC", (1, 2, 3))
        for item in ((E, "employee_service_start", name, AVAILABLE, SERVING), (C, "service_start", number, None, None))]
    assert compact(checked, 1.5) == [(C, "service_end", 1, None, None), (C, "service_end", 5, None, None),
                                     (E, "employee_service_completion", "A", SERVING, AVAILABLE),
                                     (E, "employee_service_completion", "B", SERVING, AVAILABLE)]
    assert [(event["type"], event["employee_transitions_before"]) for event in result["trace"] if event["t"] == 1.0] == [
        ("arrival", 6), ("arrival", 6), ("arrival", 6), ("arrival", 6), ("service_start", 7), ("service_start", 8),
        ("service_start", 9)]


def _all_results() -> list[tuple[dict, list[DemandPeriod]]]:
    runs = [(coverage(name), PERIODS) for name in COVERAGE] + [(simulate(*NORMAL), PERIODS),
                                                               (simulate(*FCFS, required=THREE), PERIODS)]
    for name, (demand, roster, workforce, required) in SCENARIOS.items():
        for policy in (DRAIN, HARD_CUTOFF):
            for index in range(3):
                runs.append((simulate_named_replication(
                    HORIZON, demand, staff(roster), workforce, roster, seed_sequence=replication_seed_sequence(8, index),
                    closing_policy=policy, employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=required), demand))
    return runs


def test_employee_transitions_before_is_monotone_bounded_and_consistent_with_time():
    for result, _ in _all_results():
        rows, counts = transitions(result), [event["employee_transitions_before"] for event in result["trace"]]
        assert counts == sorted(counts) and all(0 <= count <= len(rows) for count in counts)
        for event, count in zip(result["trace"], counts):
            assert count == 0 or rows[count - 1]["t"] <= event["t"]
            assert count == len(rows) or rows[count]["t"] >= event["t"]


def test_corrupted_interleaving_counts_are_rejected():
    result = simulate(*NORMAL)
    for position, value, check in (
        (9, len(transitions(result)) + 1, "trace_structure"),  # beyond the transition record
        (5, 2, "trace_structure"),                              # a count that decreases
        (1, 2, "same_time_order"),                              # #1's service_start before A's start transition
        (3, 4, "same_time_order"),                              # #1's service_end after A's completion transition
    ):
        corrupted = copy.deepcopy(result)
        corrupted["trace"][position]["employee_transitions_before"] = value
        rejected(corrupted, check)


def test_register_handover():
    # One register. A 08:00-10:00 serves #1 1.75-2.25 past its shift end; B's shift starts at 2.0 and waits. At 2.25
    # #1's service_end, A's release (register 1 freed), B takes register 1 (P4), and B starts #2 (wait 0.125).
    checked = accepted(simulate(*HANDOVER))
    E = "employee_transition"
    assert compact(checked, 2.0) == [(E, "employee_shift_end", "A", SERVING, SERVING_SHIFT_ENDED),
                                     (E, "employee_shift_start", "B", OFF, WAITING_FOR_REGISTER)]
    assert compact(checked, 2.25) == [
        ("customer_trace", "service_end", 1, None, None), (E, "employee_service_completion", "A", SERVING_SHIFT_ENDED, OFF),
        (E, "employee_register_assigned", "B", WAITING_FOR_REGISTER, AVAILABLE),
        (E, "employee_service_start", "B", AVAILABLE, SERVING), ("customer_trace", "service_start", 2, None, None)]
    handover = next(event for event in checked["events"] if event["type"] == "employee_register_assigned"
                    and event["employee_id"] == "B")
    assert (handover["register_before"], handover["register_after"]) == (None, 1)
    assert next(row for row in checked["instants"] if row["t"] == 2.0)["waiting_for_register"] == 1
    assert checked["shifts"] == [{"employee_id": "A", "activation": 0.0, "release": 2.25},
                                 {"employee_id": "B", "activation": 2.0, "release": 4.0}]


def test_multiple_employees_follow_x1_and_fcfs():
    # X1 day: A, B, C, A, B, A serve #1-#6 (C at #3 because C was AVAILABLE longest).
    checked = accepted(simulate(*X1, required=THREE))
    starts = [event["employee_id"] for event in checked["events"] if event["type"] == "service_start"]
    assert starts == ["A", "B", "C", "A", "B", "A"]
    # FCFS day: four arrive at 1.0 and one at 1.125; #4 and #5 wait and are served in arrival order by B.
    checked = accepted(simulate(*FCFS, required=THREE))
    assert [(event["customer_id"], event["employee_id"], event["register_id"]) for event in checked["events"]
            if event["type"] == "service_start"] == [(1, "A", 1), (2, "B", 2), (3, "C", 3), (4, "B", 2), (5, "B", 2)]


def test_break_due_during_service_and_delayed_break():
    # A's 30-minute break is due at 1.0 during #1 (0.75-1.25): SERVING_BREAK_DUE at 1.0, the break starts at the
    # completion 1.25 (delay 0.25) and ends 1.75; A rejoins through the register handover and takes #2.
    roster = [shift("A", 480, 720, rest=540)]
    checked = accepted(simulate(roster, rules(*LONG_SHIFT_BREAK, registers=1), [(0.75, 2.0), (1.125, 0.5)]))
    assert compact(checked, 1.0) == [("employee_transition", "employee_break_due_while_serving", "A", SERVING,
                                      SERVING_BREAK_DUE)]
    start = next(event for event in checked["events"] if event["employee_state_after"] == ON_BREAK)
    end = next(event for event in checked["events"] if event["employee_state_before"] == ON_BREAK)
    assert (start["t"], start["stage"], start["type"]) == (1.25, "completion", "employee_break_start")
    assert start["break"] == {"name": "rest", "scheduled_start": 1.0, "due": 1.0, "delay": 0.25, "outcome": COMPLETED}
    assert (end["t"], end["type"], end["employee_state_after"]) == (1.75, "employee_break_end", WAITING_FOR_REGISTER)
    assert checked["breaks"][0]["actual_start"] == 1.25 and checked["breaks"][0]["actual_end"] == 1.75


def test_split_shift():
    # The 5B-4.3 delayed split shift: shift 0 is released at 1.625 (after #1) and shift 1 activates at 2.125 (rest
    # 30 minutes); its break is due at 2.625 and runs 2.625-2.875.
    workforce = rules(break_rule(15, 60), break_rule(61, 480, rest=15), registers=1, max_shifts=2, rest=30)
    roster = [shift("A", 480, 540), shift("A", 570, 690, rest=600)]
    checked = accepted(simulate(roster, workforce, [(0.5, 4.5), (1.75, 1.0), (2.75, 0.5)]))
    assert checked["shifts"] == [{"employee_id": "A", "activation": 0.0, "release": 1.625},
                                 {"employee_id": "A", "activation": 2.125, "release": 3.5}]
    assert [(row["actual_start"], row["actual_end"], row["outcome"]) for row in checked["breaks"]] == [
        (2.625, 2.875, COMPLETED)]


def test_drain():
    # The 5B-4.3 closing day under DRAIN: crew [A]; B's delayed break is truncated at closing and B released; C
    # never starts (no event; reported from the engine record). A alone serves #4 and #5 after closing.
    result = simulate(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, required=TWO)
    checked = accepted(result)
    closing = next(event for event in checked["events"] if event["type"] == "closing")
    assert closing["drain_crew"] == ["A"] and closing["queue_len_after"] == 2
    assert compact(checked, 4.0)[1:] == [("employee_transition", "employee_break_truncated_at_closing", "B", ON_BREAK, OFF)]
    truncated = next(event for event in checked["events"] if event["type"] == "employee_break_truncated_at_closing")
    assert truncated["break"]["outcome"] == TRUNCATED_BY_CLOSING
    after = [event for event in checked["events"] if event["t"] > CLOSE and event["type"] == "service_start"]
    assert [(event["customer_id"], event["employee_id"], event["t"]) for event in after] == [(4, "A", 4.375), (5, "A", 4.625)]
    assert {event["period"] for event in after} == {"after_closing"}
    assert "C" not in {event["employee_id"] for event in checked["events"]}


def test_idle_surplus_drain_employees_are_released_in_employee_id_order():
    # A, B, C idle at closing, nobody waiting: all three released at closing, recorded A, B, C (X1 would rank B, C, A).
    result = simulate(*SURPLUS, required=THREE)
    checked = accepted(result)
    assert compact(checked, 4.0) == [("customer_trace", "closing", None, None, None)] + [
        ("employee_transition", "employee_release_input", name, AVAILABLE, OFF) for name in "ABC"]
    # The fd67bbf2 engine's X1-ordered releases (B, C, A) are rejected.
    corrupted = copy.deepcopy(result)
    rows = transitions(corrupted)
    rows[-3:] = [rows[-2], rows[-1], rows[-3]]
    assert [row["employee_id"] for row in rows[-3:]] == ["B", "C", "A"]
    rejected(corrupted, "same_time_order")


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_hard_cutoff_and_unserved_customers(policy):
    # The closing day: under HARD_CUTOFF #4 and #5 leave unserved at closing (queue 2 -> 1 -> 0), A is released
    # at closing while serving and goes OFF at its completion 4.375; nothing starts at or after closing.
    result = simulate(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, policy=policy, required=TWO)
    checked = accepted(result)
    unserved = [event for event in checked["events"] if event["type"] == "unserved_at_close"]
    starts_after = [event for event in checked["events"] if event["type"] == "service_start" and event["t"] >= CLOSE]
    if policy == HARD_CUTOFF:
        assert [(event["customer_id"], event["unserved_reason"], event["queue_len_after"]) for event in unserved] == [
            (4, HARD_CUTOFF_REASON, 1), (5, HARD_CUTOFF_REASON, 0)]
        assert not starts_after
        assert ("employee_transition", "employee_release_input", "A", SERVING, SERVING_SHIFT_ENDED) in compact(checked, 4.0)
        assert compact(checked, 4.375)[-1] == ("employee_transition", "employee_service_completion", "A",
                                               SERVING_SHIFT_ENDED, OFF)
    else:
        assert not unserved and len(starts_after) == 2


def test_no_eligible_employee():
    # A's break 3.5-4.0 ends exactly at closing: A is on a break before closing, so the DRAIN crew is empty and #1
    # (3.75) leaves unserved, no_eligible_employee; the break is truncated at closing (rule 2).
    result = simulate([shift("A", 480, 720, rest=690)], rules(*LONG_SHIFT_BREAK, registers=1), [(3.75, 1.0)])
    checked = accepted(result)
    assert compact(checked, 4.0) == [
        ("customer_trace", "closing", None, None, None), ("customer_trace", "unserved_at_close", 1, None, None),
        ("employee_transition", "employee_break_truncated_at_closing", "A", ON_BREAK, OFF)]
    assert checked["events"][-2]["unserved_reason"] == NO_ELIGIBLE_EMPLOYEE
    assert checked["events"][-1]["break"]["outcome"] == TRUNCATED_BY_CLOSING


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_exact_closing_boundaries(policy):
    # Completion exactly at closing: #1 (3.5, work 2) ends at 4.0 and #2 (3.75) waits. The service_end precedes the
    # closing event; A was serving before closing, so under DRAIN A is the crew and starts #2 at 4.0; under
    # HARD_CUTOFF #2 is unserved and A is released at closing.
    checked = accepted(simulate([shift("A", 480, 720)], rules(registers=1), [(3.5, 2.0), (3.75, 1.0)], policy=policy))
    C, E = "customer_trace", "employee_transition"
    head = [(C, "service_end", 1, None, None), (C, "closing", None, None, None)]
    if policy == DRAIN:
        assert compact(checked, 4.0) == head + [(E, "employee_service_completion", "A", SERVING, AVAILABLE),
                                                (E, "employee_service_start", "A", AVAILABLE, SERVING),
                                                (C, "service_start", 2, None, None)]
    else:
        assert compact(checked, 4.0) == head + [(C, "unserved_at_close", 2, None, None),
                                                (E, "employee_service_completion", "A", SERVING, AVAILABLE),
                                                (E, "employee_release_input", "A", AVAILABLE, OFF)]
    # Rule 1: a break-due service completing exactly at closing completes first; no break starts.
    checked = accepted(coverage("rule_1"))
    assert compact(checked, 4.0) == [
        (C, "service_end", 1, None, None), (C, "closing", None, None, None), (C, "unserved_at_close", 2, None, None),
        (E, "employee_service_completion", "A", SERVING_BREAK_DUE, AVAILABLE),
        (E, "employee_release_input", "A", AVAILABLE, OFF)]
    assert not checked["breaks"]


# ── Selected-replication regeneration and provenance ───────────────────────


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_selected_replication_is_regenerated_and_matches_the_stored_row(policy):
    run = replicate("overrun_and_contention", replications=6, seed=2468, policy=policy)
    for index in (0, 4):
        playback = playback_from_named_replications(run, index)
        stored = run["replications"][index]
        assert playback["summary"] == stored
        assert playback["replication"]["customer_inputs_sha256"] == stored["customer_inputs_sha256"]
        assert playback["replication"]["spawn_key"] == [index] and playback["replication"]["root_entropy"] == 2468
        assert playback["provenance"]["recorded_inputs_sha256"] == run["provenance"]["inputs_sha256"]
        assert playback["provenance"]["inputs_sha256"] == run["provenance"]["inputs_sha256"]
        assert playback["provenance"]["runtime_matches_recorded"] is True
        assert {"quantity": "stored replication row", "method": "exact"} in playback["reconciliation"]
        # Every playback event is one engine record: each trace event and transition once, each stream in order.
        demand, roster, workforce, required = SCENARIOS["overrun_and_contention"]
        result = simulate_named_replication(HORIZON, demand, staff(roster), workforce, roster,
                                            seed_sequence=replication_seed_sequence(2468, index), closing_policy=policy,
                                            employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=required)
        for source, records in (("customer_trace", result["trace"]), ("employee_transition", transitions(result))):
            own = [event for event in playback["events"] if event["source"] == source]
            assert [event["source_index"] for event in own] == list(range(len(records)))
            assert all(event["t"] == record["t"] for event, record in zip(own, records))
        assert len(playback["events"]) == len(result["trace"]) + len(transitions(result))


def test_playback_regeneration_uses_the_5b_4_4_seed_path_and_draws_nothing_else(monkeypatch):
    run = replicate("delayed_break", replications=5, seed=31, policy=DRAIN)
    real = np.random.default_rng
    log: list[tuple] = []

    class Counting:
        def __init__(self, inner: np.random.Generator) -> None:
            self.inner = inner

        @property
        def bit_generator(self) -> Any:
            return self.inner.bit_generator

        def exponential(self, scale: float = 1.0, size: int | None = None) -> Any:
            log.append(("exponential", 1 if size is None else int(size)))
            return self.inner.exponential(scale, size)

    def counting(seed: Any = None) -> Counting:
        log.append(("stream", tuple(seed.spawn_key) if isinstance(seed, np.random.SeedSequence) else seed))
        return Counting(real(seed))

    monkeypatch.setattr(np.random, "default_rng", counting)
    playback = playback_from_named_replications(run, 3)
    count = playback["summary"]["customers"]["arrivals"]
    # Drop the runtime probe (default_rng(0) in the provenance), which draws nothing.
    assert [item for item in log if item != ("stream", 0)] == (
        [("stream", (3, 0)), ("stream", (3, 1))] + [("exponential", 1)] * (count + 1) + [("exponential", count)])


def test_replay_draws_no_random_numbers(monkeypatch):
    result = simulate(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, required=TWO)
    expected = replay_named_trace(result, HORIZON, PERIODS)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a random number source was used")

    for name in ("default_rng", "Generator", "SeedSequence", "RandomState", "PCG64", "random", "exponential"):
        monkeypatch.setattr(np.random, name, forbidden)
    for name in ("random", "Random", "uniform", "choice", "shuffle", "randint", "expovariate", "sample"):
        monkeypatch.setattr(random, name, forbidden)
    assert replay_named_trace(result, HORIZON, PERIODS) == expected


def test_the_trace_setting_does_not_change_the_customers():
    # The run keeps rows with max_trace_events=0; the playback regenerates with a full trace. The customer inputs
    # and every row field agree.
    run = replicate("split_shift", replications=3, seed=9, policy=HARD_CUTOFF)
    for index in range(3):
        playback = playback_from_named_replications(run, index)
        assert playback["replication"]["customer_inputs_sha256"] == run["replications"][index]["customer_inputs_sha256"]


def test_inputs_digest_definition():
    demand, roster, workforce, required = SCENARIOS["stable"]
    snapshot = named_inputs_snapshot(HORIZON, demand, staff(roster), workforce, roster, required)
    policy = dataclasses.asdict(APPROVED_EMPLOYEE_POLICY)
    digest = named_inputs_digest(snapshot, DRAIN, policy)
    assert digest == named_inputs_digest(copy.deepcopy(snapshot), DRAIN, policy)
    assert digest != named_inputs_digest(snapshot, HARD_CUTOFF, policy)
    # The rebuilt dataclasses reproduce the digest.
    rebuilt = rebuild_named_inputs(snapshot)
    assert named_inputs_digest(named_inputs_snapshot(rebuilt["horizon"], rebuilt["demand_periods"], rebuilt["employees"],
                                                     rebuilt["rules"], rebuilt["roster"], rebuilt["required_staffing"]),
                               DRAIN, policy) == digest
    # Recorded values, not semantics: an int and an equal float differ; a list and a tuple are both arrays.
    as_int = copy.deepcopy(snapshot)
    as_int["demand_periods"][0]["arrival_rate_per_hour"] = 6
    assert snapshot["demand_periods"][0]["arrival_rate_per_hour"] == 6.0
    assert named_inputs_digest(as_int, DRAIN, policy) != digest
    as_list = copy.deepcopy(snapshot)
    as_list["roster"][0]["breaks"] = list(as_list["roster"][0]["breaks"])
    assert named_inputs_digest(as_list, DRAIN, policy) == digest
    unsupported = copy.deepcopy(snapshot)
    unsupported["horizon"]["start_minute"] = object()
    with pytest.raises(SharedSegmentError, match="cannot represent"):
        named_inputs_digest(unsupported, DRAIN, policy)


def test_inputs_digest_is_sha256_of_canonical_sorted_json():
    # Independent recomputation on a hand-written document: floats as {"float": hex}, whole numbers as integers,
    # tuples as arrays, sorted keys, compact separators, ASCII.
    inputs = {"horizon": {"start_minute": 480, "end_minute": 720}, "rate": 6.0, "window": (1, 2.5), "flag": True,
              "name": "P", "missing": None}
    policy = {"employee_choice": "longest_available_then_employee_id"}
    text = ('{"closing_policy":"DRAIN","employee_policy":{"employee_choice":"longest_available_then_employee_id"},'
            '"inputs":{"flag":true,"horizon":{"end_minute":720,"start_minute":480},"missing":null,"name":"P",'
            '"rate":{"float":"0x1.8000000000000p+2"},"window":[1,{"float":"0x1.4000000000000p+1"}]}}')
    assert named_inputs_digest(inputs, DRAIN, policy) == hashlib.sha256(text.encode("ascii")).hexdigest()


def _reversed_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _reversed_keys(value[key]) for key in reversed(list(value))}
    if isinstance(value, (list, tuple)):
        return type(value)(_reversed_keys(item) for item in value)
    return value


def test_inputs_digest_ignores_dictionary_order():
    demand, roster, workforce, required = SCENARIOS["split_shift"]
    snapshot = named_inputs_snapshot(HORIZON, demand, staff(roster), workforce, roster, required)
    policy = dataclasses.asdict(APPROVED_EMPLOYEE_POLICY)
    reordered = _reversed_keys(snapshot)
    assert list(reordered) == list(reversed(list(snapshot)))
    assert named_inputs_digest(reordered, DRAIN, _reversed_keys(policy)) == named_inputs_digest(snapshot, DRAIN, policy)


@pytest.mark.parametrize("change", [
    "horizon_end", "arrival_rate", "service_rate", "required_servers", "roster_shift_start", "roster_break_minute",
    "break_duration", "break_gap", "rest_between_shifts", "register_count", "availability", "closing_policy",
    "employee_policy",
])
def test_a_simulation_defining_change_changes_the_digest(change):
    demand, roster, workforce, required = SCENARIOS["split_shift"]
    snapshot = named_inputs_snapshot(HORIZON, demand, staff(roster), workforce, roster, required)
    policy = dataclasses.asdict(APPROVED_EMPLOYEE_POLICY)
    base = named_inputs_digest(snapshot, DRAIN, policy)
    changed, closing = copy.deepcopy(snapshot), DRAIN
    changed_policy = copy.deepcopy(policy)
    rules_ = changed["rules"]
    if change == "horizon_end":
        changed["horizon"]["end_minute"] += 60
    elif change == "arrival_rate":
        changed["demand_periods"][0]["arrival_rate_per_hour"] += 1.0
    elif change == "service_rate":
        changed["demand_periods"][0]["service_rate_per_hour"] += 1.0
    elif change == "required_servers":
        changed["required_staffing"][0]["servers"] += 1
    elif change == "roster_shift_start":
        changed["roster"][0]["start_minute"] += 15
    elif change == "roster_break_minute":
        changed["roster"][1]["breaks"][0]["start_minute"] += 15
    elif change == "break_duration":
        rules_["break_rules"][1]["breaks"][0]["duration_minutes"] += 5
    elif change == "break_gap":
        rules_["break_rules"][1]["min_gap_minutes"] += 5
    elif change == "rest_between_shifts":
        rules_["shift_rules"]["min_minutes_between_shifts"] += 15
    elif change == "register_count":
        rules_["register_count"] += 1
    elif change == "availability":
        changed["employees"][0]["availability"][0]["end_minute"] -= 60
    elif change == "closing_policy":
        closing = HARD_CUTOFF
    else:
        changed_policy["employee_choice"] = "other"
    assert named_inputs_digest(changed, closing, changed_policy) != base


def test_the_digest_covers_every_simulation_input_of_a_replication():
    # Repository mapping: simulate_named_replication's inputs are the six recorded blocks, the two policies (both
    # digested), the seed (recorded separately as root_entropy and the spawn key), and max_trace_events, which does
    # not change the row (5B-4.4). A new simulation parameter fails this test until its provenance is decided.
    parameters = set(inspect.signature(simulate_named_replication).parameters)
    snapshot = named_inputs_snapshot(HORIZON, PERIODS, staff(NORMAL[0]), NORMAL[1], NORMAL[0], ONE)
    assert parameters == set(snapshot) | {"closing_policy", "employee_policy", "seed_sequence", "max_trace_events"}
    assert set(snapshot) == {"horizon", "demand_periods", "required_staffing", "employees", "rules", "roster"}
    assert snapshot["rules"]["register_count"] == 1  # the physical register count is part of the rules block
    run = replicate("stable", replications=2, seed=3, policy=DRAIN)
    provenance = run["provenance"]
    demand, roster, workforce, required = SCENARIOS["stable"]
    assert provenance["method_version"] == "novaq-shared-named-replications-v2"
    assert provenance["inputs"] == named_inputs_snapshot(HORIZON, demand, staff(roster), workforce, roster, required)
    assert provenance["inputs_sha256"] == named_inputs_digest(provenance["inputs"], DRAIN, provenance["employee_policy"])
    assert "not a tamper-proof" in provenance["inputs_digest_definition"]


def _refused(run: dict, index: int, check: str) -> dict:
    with pytest.raises(NamedPlaybackError) as caught:
        playback_from_named_replications(run, index)
    failure: dict = caught.value.failure
    assert failure["check"] == check, failure
    return failure


def test_regeneration_refuses_changed_inputs_digest_versions_and_rows():
    run = replicate("stable", replications=3, seed=12, policy=DRAIN)
    # A changed recorded input (a break moved by 15 minutes) no longer matches the digest.
    changed = copy.deepcopy(run)
    changed["provenance"]["inputs"]["roster"][0]["breaks"][0]["start_minute"] += 15
    _refused(changed, 1, "regeneration_identity")
    # A changed digest, a missing digest, and another engine version are refused.
    for key, value in (("inputs_sha256", "0" * 64), ("inputs_sha256", None),
                       ("named_engine_version", "novaq-shared-named-des-v2"),
                       ("method_version", "novaq-shared-named-replications-v1")):
        altered = copy.deepcopy(run)
        altered["provenance"][key] = value
        _refused(altered, 0, "regeneration_identity")
    # A stored row that does not match the regeneration is refused, naming the field.
    tampered = copy.deepcopy(run)
    tampered["replications"][2]["customers"]["served"] += 1
    assert _refused(tampered, 2, "stored_row")["evidence"]["fields"] == ["customers"]
    misplaced = copy.deepcopy(run)
    misplaced["replications"][1]["spawn_key"] = [2]
    _refused(misplaced, 1, "regeneration_identity")
    # Another root entropy regenerates other customers, so the stored row no longer matches.
    reseeded = copy.deepcopy(run)
    reseeded["provenance"]["root_entropy"] = 13
    assert "customer_inputs_sha256" in _refused(reseeded, 0, "stored_row")["evidence"]["fields"]
    for index in (-1, 3, 1.0, True):
        with pytest.raises(SharedSegmentError):
            playback_from_named_replications(run, index)


def test_pre_opening_and_post_closing_activity_is_reported_without_a_requirement():
    # A starts at 07:30 (-0.5 h): its shift starts and takes register 1 at -0.5, so before opening A is AVAILABLE
    # 0.5 h and B is OFF 0.5 h, whatever the seed. After closing only series are reported (reconciled with the row).
    demand, roster, workforce, required = SCENARIOS["outside_the_horizon"]
    playback = prepare_named_playback(HORIZON, demand, staff(roster), workforce, roster, root_entropy=21,
                                      replication_index=0, closing_policy=DRAIN,
                                      employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=required)
    outside = playback["outside_horizon"]
    assert outside["before_opening_hours_by_state"] == {**dict.fromkeys(BASE_STATES, 0.0), AVAILABLE: 0.5, OFF: 0.5}
    assert not any("gap" in key or "required" in key for key in outside)
    assert {event["period"] for event in playback["events"] if event["t"] < 0} == {"before_opening"}
    # Float sums over differently split intervals: compared with the playback tolerance (TOLERANCE), not exactly.
    stored = playback["summary"]["employees"]["employee_hours_after_closing_by_state"]
    assert outside["after_closing_hours_by_state"] == {
        state: pytest.approx(hours, rel=shared_named_playback.TOLERANCE["rel"], abs=shared_named_playback.TOLERANCE["abs"])
        for state, hours in stored.items()}


# ── Corrupted traces (fault injection on copies of engine results) ─────────


def test_valid_days_are_accepted():
    for arguments, required in ((NORMAL, ONE), (FCFS, THREE), (X1, THREE), (HANDOVER, ONE), (SURPLUS, THREE)):
        accepted(simulate(*arguments, required=required))


def test_malformed_event_order_is_rejected():
    result = simulate(*NORMAL)
    backwards = copy.deepcopy(result)
    backwards["trace"][2]["t"] = 0.25  # arrival #2 (0.625) placed before the previous event at 0.5
    rejected(backwards, "time_order")
    same_time = copy.deepcopy(simulate(*FCFS, required=THREE))
    rows = transitions(same_time)
    rows[0], rows[1] = rows[1], rows[0]  # B's shift start before A's at 0.0
    rejected(same_time, "same_time_order")
    # At 2.0, #4's arrival is recorded after A's completion and shift end; placing it before them is rejected.
    early = simulate([shift("A", 480, 600), shift("B", 480, 720)], rules(registers=2),
                     [(1.5, 2.0), (1.625, 2.0), (1.875, 1.0), (2.0, 0.5)], required=TWO)
    accepted(early)
    arrival = next(event for event in early["trace"] if event["type"] == "arrival" and event["customer_id"] == 4)
    arrival["employee_transitions_before"] -= 2
    rejected(early, "same_time_order")


def test_same_time_order_violations_are_rejected_at_the_first_offending_event():
    # Each corruption reorders records of one instant; the replay names the first event out of the X2 order.
    # 1. Handover day at 2.0: A's shift end (stage shift_end) is recorded before B's shift start (shift_start).
    stages = copy.deepcopy(simulate(*HANDOVER))
    rows = transitions(stages)
    first = next(position for position, row in enumerate(rows) if row["t"] == 2.0)
    assert [rows[first]["stage"], rows[first + 1]["stage"]] == ["shift_end", "shift_start"]
    rows[first], rows[first + 1] = rows[first + 1], rows[first]
    failure = rejected(stages, "same_time_order")
    assert (failure["t"], failure["event"]["stage"]) == (2.0, "shift_end")
    # 2. A and B idle all day, B on a break 3.5-4.0: at closing B (not crew) is truncated before crew member A is
    # released. The crew release recorded first is rejected, although the employee ids stay in order.
    day = simulate([shift("A", 480, 720, rest=540), shift("B", 480, 720, rest=690)], rules(*LONG_SHIFT_BREAK, registers=2),
                   [], required=TWO)
    groups = copy.deepcopy(day)
    rows = transitions(groups)
    assert [(row["employee_id"], row["event"]) for row in rows[-2:]] == [
        ("B", "employee_break_truncated_at_closing"), ("A", "employee_release_input")]
    rows[-2], rows[-1] = rows[-1], rows[-2]
    failure = rejected(groups, "same_time_order")
    assert failure["event"]["employee_id"] == "B" and "before DRAIN releases" in failure["message"]
    # 3. FCFS day at 1.5: #5's service_end recorded before #1's (the engine's completion heap gives 1, 5).
    ends = copy.deepcopy(simulate(*FCFS, required=THREE))
    trace = ends["trace"]
    one, five = (next(position for position, event in enumerate(trace) if event["type"] == "service_end"
                      and event["customer_id"] == number) for number in (1, 5))
    assert five == one + 1
    trace[one], trace[five] = trace[five], trace[one]
    failure = rejected(ends, "same_time_order")
    assert (failure["event"]["customer_id"], failure["evidence"]["previous_customer_id"]) == (1, 5)
    # 4. FCFS day at 1.0: #1's service_start displaced after B's start transition. The first offending record is B's
    # transition, recorded while A's start still waits for its customer event.
    displaced = copy.deepcopy(simulate(*FCFS, required=THREE))
    start_one = next(event for event in displaced["trace"] if event["type"] == "service_start" and event["customer_id"] == 1)
    start_one["employee_transitions_before"] += 1
    failure = rejected(displaced, "same_time_order")
    assert (failure["source"], failure["event"]["employee_id"], failure["evidence"]["employee_id"]) == (
        "employee", "B", "A")
    # 5. Ordinary day: A's completion at 0.875 removed. The instant ends with #2's service_end unmatched.
    unmatched = copy.deepcopy(simulate(*NORMAL))
    completion = next(position for position, row in enumerate(transitions(unmatched)) if row["t"] == 0.875)
    drop_transition(unmatched, completion)
    failure = rejected(unmatched, "same_time_order")
    assert (failure["t"], failure["evidence"]["employee_ids"]) == (0.875, ["A"])


def test_illegal_employee_transition_is_rejected():
    result = simulate(*NORMAL)
    illegal = copy.deepcopy(result)
    transitions(illegal)[3]["to_state"] = ON_BREAK  # a service completion that ends on a break is not a legal tuple
    rejected(illegal, "employee_transition_legal")
    wrong_start = copy.deepcopy(result)
    first = transitions(wrong_start)[0]
    first.update(event="employee_break_start_at_shift_start", to_state=ON_BREAK)  # legal tuple, wrong history
    rejected(wrong_start, "employee_transition_legal")
    # A second service for an employee already serving (a duplicated start pair) is rejected at the transition.
    doubled = copy.deepcopy(result)
    rows, trace = transitions(doubled), doubled["trace"]
    rows.insert(3, dict(rows[2]))
    for event in trace[2:]:
        event["employee_transitions_before"] += 1
    rejected(doubled, "employee_transition_legal")


def test_one_employee_serving_two_customers_is_rejected():
    # FCFS day: #2 recorded as served by A (already serving #1) instead of B. The replay rejects A's second start,
    # because a service starts only from AVAILABLE and A is SERVING (the transition check enforces one customer at
    # a time; no separate check is reachable).
    result = copy.deepcopy(simulate(*FCFS, required=THREE))
    start_b = next(row for row in transitions(result) if row["t"] == 1.0 and row["employee_id"] == "B")
    start_b.update(employee_id="A", from_state=SERVING, register_before=1, register_after=1)
    assert (start_b["from_state"], start_b["to_state"]) == (SERVING, SERVING)
    rejected(result, "employee_transition_legal")  # (service_start, SERVING -> SERVING) is not a legal tuple
    same_tuple = copy.deepcopy(simulate(*FCFS, required=THREE))
    start_b = next(row for row in transitions(same_tuple) if row["t"] == 1.0 and row["employee_id"] == "B")
    start_b.update(employee_id="A", register_before=1, register_after=1)  # AVAILABLE -> SERVING, but A is SERVING
    failure = rejected(same_tuple, "employee_transition_legal")
    assert failure["evidence"]["replayed_state"] == SERVING


def test_double_register_occupancy_is_rejected():
    result = copy.deepcopy(simulate(*FCFS, required=THREE))
    handover = next(row for row in transitions(result) if row["event"] == "employee_register_assigned"
                    and row["employee_id"] == "C")
    handover["register_after"] = 1  # register 1 is A's
    rejected(result, "register_single_holder")
    beyond = copy.deepcopy(simulate(*FCFS, required=THREE))
    next(row for row in transitions(beyond) if row["event"] == "employee_register_assigned"
         and row["employee_id"] == "C")["register_after"] = 4
    rejected(beyond, "register_capacity")
    holding = copy.deepcopy(simulate(*NORMAL))
    holding["employee_timeline"]["transitions"][-1]["register_after"] = 1  # OFF with a register
    rejected(holding, "no_register_off_break_waiting")


def test_register_handover_order_is_enforced():
    # FCFS day: at 0.0 A, B, C wait from 0.0 and take registers 1, 2, 3. B recorded taking register 3 (register 2 is
    # the lowest free one) is rejected (P4).
    result = copy.deepcopy(simulate(*FCFS, required=THREE))
    handover = next(row for row in transitions(result) if row["event"] == "employee_register_assigned"
                    and row["employee_id"] == "B")
    handover["register_after"] = 3
    assert rejected(result, "register_handover_order")["evidence"]["expected"] == ("B", 2)


def test_a_trace_ending_with_a_customer_in_service_is_rejected():
    # DRAIN closing day: A serves #5 4.625-4.875 and is released at 4.875. Without #5's service_end and A's last two
    # transitions, the trace ends with #5 in service.
    result = copy.deepcopy(simulate(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, required=TWO))
    assert [(row["t"], row["event"]) for row in transitions(result)[-2:]] == [
        (4.875, "employee_service_completion"), (4.875, "employee_release_input")]
    assert (result["trace"][-1]["type"], result["trace"][-1]["t"]) == ("service_end", 4.875)
    del result["trace"][-1]
    for _ in range(2):
        drop_transition(result, len(transitions(result)) - 1)
    assert rejected(result, "end_state")["evidence"]["unresolved"] == [5]


def test_customer_duplication_is_rejected():
    result = copy.deepcopy(simulate(*FCFS, required=THREE))
    index = next(position for position, event in enumerate(result["trace"]) if event["type"] == "arrival"
                 and event["customer_id"] == 2)
    result["trace"].insert(index + 1, dict(result["trace"][index]))
    rejected(result, "customer_identity")
    again = copy.deepcopy(simulate(*NORMAL))
    second = next(event for event in again["trace"] if event["type"] == "service_start" and event["customer_id"] == 2)
    second["customer_id"] = 1  # a second service for the departed #1
    rejected(again, "customer_single_service")


def test_unknown_event_types_are_rejected():
    for corrupt in ("customer", "employee", "state_machine_only"):
        result = copy.deepcopy(simulate(*NORMAL))
        if corrupt == "customer":
            result["trace"][0]["type"] = "queue_entry"
        elif corrupt == "employee":
            transitions(result)[0]["event"] = "employee_teleport"
        else:
            transitions(result)[3].update(stage="closing_input", event="employee_breaks_cancelled_at_closing")
        failure = rejected(result, "event_vocabulary")
        assert failure["source_index"] in (0, 3)


def test_corrupted_traces_with_plausible_final_counts_are_rejected():
    # Each corruption keeps every final count (arrivals, service starts and ends, unserved) and the engine's own
    # summary untouched, yet the replay rejects it with evidence.
    def counts(result: dict) -> dict[str, int]:
        return {kind: sum(1 for event in result["trace"] if event["type"] == kind) for kind in CUSTOMER_EVENT_TYPES}

    # 1. X1: #6 (2.5) recorded as served by B instead of A (A, B, C all AVAILABLE since 2.0; tie to A).
    original = simulate(*X1, required=THREE)
    relabeled = copy.deepcopy(original)
    for row in transitions(relabeled):
        if row["t"] in (2.5, 2.75) and row["employee_id"] == "A":
            row.update(employee_id="B", register_before=2, register_after=2)
    for event in relabeled["trace"]:
        if event["customer_id"] == 6 and event["type"] in ("service_start", "service_end"):
            event.update(employee_id="B", register_id=2)
    assert counts(relabeled) == counts(original) and relabeled["counts"] == original["counts"]
    failure = rejected(relabeled, "x1_employee_choice")
    assert failure["evidence"]["expected"] == "A" and failure["t"] == 2.5
    # 2. FCFS: #4 and #5 swapped (B serves #5 first).
    original = simulate(*FCFS, required=THREE)
    swapped = copy.deepcopy(original)
    for event in swapped["trace"]:
        if event["type"] in ("service_start", "service_end") and event["customer_id"] in (4, 5):
            event["customer_id"] = 9 - event["customer_id"]
    assert counts(swapped) == counts(original)
    assert rejected(swapped, "fcfs")["evidence"]["queue_head"] == 4
    # 3. DRAIN release set: one surplus release dropped, so C is never released at closing.
    original = simulate(*SURPLUS, required=THREE)
    dropped = copy.deepcopy(original)
    drop_transition(dropped, len(transitions(dropped)) - 1)
    assert counts(dropped) == counts(original)
    assert rejected(dropped, "drain_frozen_crew")["evidence"]["expected"] == ["A", "B", "C"]
    # 4. A service start removed while the customer waits and A is AVAILABLE (work conservation).
    original = simulate(*NORMAL)
    missing = copy.deepcopy(original)
    drop_transition(missing, 4)  # A's start of #2 at 0.75
    del missing["trace"][4]      # #2's service_start
    rejected(missing, "work_conservation")


def test_policy_and_reason_corruptions_are_rejected():
    # HARD_CUTOFF: the DRAIN day relabelled HARD_CUTOFF starts #2 at closing.
    drain = simulate([shift("A", 480, 720)], rules(registers=1), [(3.5, 2.0), (3.75, 1.0)])
    relabeled = dict(copy.deepcopy(drain), closing_policy=HARD_CUTOFF)
    rejected(relabeled, "hard_cutoff_no_start_after_closing")
    # Unserved under DRAIN with a crew: the HARD_CUTOFF day relabelled DRAIN.
    cutoff = simulate([shift("A", 480, 720)], rules(registers=1), [(3.5, 2.0), (3.75, 1.0)], policy=HARD_CUTOFF)
    rejected(dict(copy.deepcopy(cutoff), closing_policy=DRAIN), "unserved_reason")
    # A wrong reason code in the engine's customer row.
    wrong = copy.deepcopy(cutoff)
    wrong["customers"][1]["unserved_reason"] = NO_ELIGIBLE_EMPLOYEE
    rejected(wrong, "unserved_reason")
    # The engine's claimed DRAIN crew differs from the crew rebuilt from the states before closing.
    crew = copy.deepcopy(drain)
    crew["at_close"]["drain_crew"] = []
    rejected(crew, "drain_frozen_crew")


def test_queue_service_and_summary_corruptions_are_rejected():
    result = simulate(*NORMAL)
    queue = copy.deepcopy(result)
    queue["trace"][0]["queue_len_after"] = 0
    rejected(queue, "queue_reconciliation")
    work = copy.deepcopy(result)
    work["customers"][0]["unit_work"] = 1.5
    rejected(work, "service_duration")
    counts = copy.deepcopy(result)
    counts["counts"]["departed"] += 1
    rejected(counts, "customer_reconciliation")
    shifts = copy.deepcopy(result)
    shifts["employee_timeline"]["shifts"][0]["release"] = 4.5
    rejected(shifts, "employee_reconciliation")
    totals = copy.deepcopy(result)
    totals["employee_timeline"]["state_totals"]["A"][AVAILABLE] += 1e-6
    rejected(totals, "employee_reconciliation")
    steps = copy.deepcopy(result)
    steps["staffing"]["timeline"][1]["busy_employees"] += 1
    rejected(steps, "employee_reconciliation")


def _record(records: list[dict], **fields: Any) -> int:
    """The position of the only record with these field values."""
    (position,) = [index for index, record in enumerate(records) if all(record[key] == value
                                                                          for key, value in fields.items())]
    return position


def test_customer_event_corruptions_are_rejected_where_they_occur():
    normal = simulate(*NORMAL)
    # A service_start transition whose customer event is missing: A's start at 0.5 is left unpaired.
    unpaired = copy.deepcopy(normal)
    del unpaired["trace"][_record(unpaired["trace"], type="service_start", customer_id=1)]
    failure = rejected(unpaired, "same_time_order")
    assert failure["t"] == 0.5 and "no customer service_start after it" in failure["message"]
    # An arrival recorded after closing.
    late = copy.deepcopy(normal)
    late["trace"].append({"t": 4.0, "type": "arrival", "customer_id": 4, "employee_id": None, "register_id": None,
                          "queue_len_after": 1, "employee_transitions_before": len(transitions(late))})
    assert "No arrival at or after closing" in rejected(late, "closing_rules")["message"]
    # A service start on a register the employee does not hold.
    register = copy.deepcopy(normal)
    register["trace"][_record(register["trace"], type="service_start", customer_id=1)]["register_id"] = 2
    assert "register differs" in rejected(register, "register_single_holder")["message"]
    # A service_end for a customer who already departed (#2's end relabelled #1).
    departed = copy.deepcopy(normal)
    departed["trace"][_record(departed["trace"], type="service_end", customer_id=2)]["customer_id"] = 1
    assert "Only a customer in service" in rejected(departed, "customer_single_service")["message"]
    # A service_end with another employee and register (FCFS day: #2 served by B on register 2).
    other = copy.deepcopy(simulate(*FCFS, required=THREE))
    other["trace"][_record(other["trace"], type="service_end", customer_id=2)].update(employee_id="C", register_id=3)
    assert "different employee or register" in rejected(other, "customer_single_service")["message"]
    # A service start while nobody waits: an extra start pair for A at 2.5, after #3's completion.
    idle = copy.deepcopy(normal)
    rows = transitions(idle)
    completion = _record(rows, t=2.5)
    rows.insert(completion + 1, {"t": 2.5, "stage": "service_start", "employee_id": "A", "from_state": AVAILABLE,
                                 "to_state": SERVING, "register_before": 1, "register_after": 1,
                                 "event": "employee_service_start"})
    end_three = _record(idle["trace"], type="service_end", customer_id=3)
    idle["trace"][end_three + 1]["employee_transitions_before"] += 1  # the closing event
    idle["trace"].insert(end_three + 1, {"t": 2.5, "type": "service_start", "customer_id": 3, "employee_id": "A",
                                         "register_id": 1, "queue_len_after": 0,
                                         "employee_transitions_before": completion + 2})
    failure = rejected(idle, "fcfs")
    assert failure["source"] == "employee" and "while nobody waits" in failure["message"]


def test_closing_corruptions_are_rejected():
    cutoff = simulate(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, policy=HARD_CUTOFF, required=TWO)
    trace = cutoff["trace"]
    closing, four, five = (_record(trace, type="closing"), _record(trace, type="unserved_at_close", customer_id=4),
                           _record(trace, type="unserved_at_close", customer_id=5))
    assert (four, five) == (closing + 1, closing + 2)
    # An unserved customer recorded before the closing event.
    early = copy.deepcopy(cutoff)
    early["trace"][closing], early["trace"][four] = early["trace"][four], early["trace"][closing]
    assert "only at closing" in rejected(early, "unserved_reason")["message"]
    # Unserved customers out of line order (#5 before #4).
    order = copy.deepcopy(cutoff)
    order["trace"][four], order["trace"][five] = order["trace"][five], order["trace"][four]
    assert rejected(order, "fcfs")["evidence"]["queue_head"] == 4
    # A customer left waiting after a hard cutoff (#5's unserved event missing).
    waiting = copy.deepcopy(cutoff)
    del waiting["trace"][five]
    assert "still wait after closing" in rejected(waiting, "unserved_reason")["message"]
    # A second closing event.
    normal = simulate(*NORMAL)
    twice = copy.deepcopy(normal)
    twice["trace"].append(dict(twice["trace"][-1]))
    assert "Exactly one closing event" in rejected(twice, "closing_rules")["message"]
    # No closing event at all, on a day whose last event is A's release at 2.0.
    early_day = simulate([shift("A", 480, 600)], rules(registers=1), [(0.5, 1.0)])
    assert early_day["trace"][-1]["type"] == "closing" and transitions(early_day)[-1]["t"] == 2.0
    missing = copy.deepcopy(early_day)
    del missing["trace"][-1]
    assert "has no closing event" in rejected(missing, "closing_rules")["message"]
    # P7: A's break in progress at closing not truncated (the truncation transition missing).
    on_break = simulate([shift("A", 480, 720, rest=690)], rules(*LONG_SHIFT_BREAK, registers=1), [(3.75, 1.0)])
    untruncated = copy.deepcopy(on_break)
    assert transitions(untruncated)[-1]["event"] == "employee_break_truncated_at_closing"
    drop_transition(untruncated, len(transitions(untruncated)) - 1)
    assert "P7" in rejected(untruncated, "closing_rules")["message"]
    # HARD_CUTOFF: an idle employee not released at closing stays AVAILABLE after closing.
    idle = simulate([shift("A", 480, 780, rest=540)], rules(*LONG_SHIFT_BREAK, registers=1), [(0.5, 1.0)],
                    policy=HARD_CUTOFF)
    kept = copy.deepcopy(idle)
    assert transitions(kept)[-1]["event"] == "employee_release_input"
    drop_transition(kept, len(transitions(kept)) - 1)
    failure = rejected(kept, "closing_rules")
    assert failure["evidence"]["state"] == AVAILABLE and "After closing only" in failure["message"]
    # DRAIN: a non-crew employee starts service after closing. On the rule 1 day A (break due before closing, not
    # crew) completes #1 at closing; the corrupted trace has A start #2 instead of #2 leaving unserved.
    rule_1 = copy.deepcopy(coverage("rule_1"))
    del rule_1["trace"][_record(rule_1["trace"], type="unserved_at_close")]
    rows = transitions(rule_1)
    assert rows[-1]["event"] == "employee_release_input"
    rows[-1] = {"t": 4.0, "stage": "service_start", "employee_id": "A", "from_state": AVAILABLE, "to_state": SERVING,
                "register_before": 1, "register_after": 1, "event": "employee_service_start"}
    rule_1["trace"].append({"t": 4.0, "type": "service_start", "customer_id": 2, "employee_id": "A", "register_id": 1,
                            "queue_len_after": 0, "employee_transitions_before": len(rows)})
    assert "Only the frozen crew" in rejected(rule_1, "drain_frozen_crew")["message"]


def test_employee_transition_corruptions_are_rejected_where_they_occur():
    # Rule 1 applies only at closing: a break-due completion recorded as AVAILABLE at 1.25.
    breaks = simulate([shift("A", 480, 720, rest=540)], rules(*LONG_SHIFT_BREAK, registers=1), [(0.75, 2.0), (1.125, 0.5)])
    early = copy.deepcopy(breaks)
    row = transitions(early)[_record(transitions(early), t=1.25, stage="completion")]
    row.update(event="employee_service_completion", to_state=AVAILABLE, register_after=1)
    failure = rejected(early, "employee_transition_legal")
    assert failure["t"] == 1.25 and "rule 1" in failure["message"]
    # A closing input before closing: A's idle shift end at 2.0 recorded as a release input.
    idle = copy.deepcopy(coverage("idle_shift_end"))
    row = transitions(idle)[_record(transitions(idle), t=2.0, employee_id="A")]
    row.update(stage="closing_input", event="employee_release_input")
    assert "only at or after closing" in rejected(idle, "closing_rules")["message"]
    # A shift end at closing (the release at closing recorded as a shift_end).
    normal = copy.deepcopy(simulate(*NORMAL))
    transitions(normal)[-1].update(stage="shift_end", event="employee_shift_end")
    assert "No shift_end transition at or after closing" in rejected(normal, "closing_rules")["message"]
    # A break starting at closing: the rule 1 completion recorded as a break start.
    late_break = copy.deepcopy(coverage("rule_1"))
    row = transitions(late_break)[_record(transitions(late_break), t=4.0, stage="completion")]
    row.update(event="employee_break_start", to_state=ON_BREAK, register_after=None)
    assert "No break starts" in rejected(late_break, "closing_rules")["message"]
    # A completion that moves the employee to another register.
    moved = copy.deepcopy(coverage("idle_shift_end"))
    transitions(moved)[_record(transitions(moved), t=0.75)]["register_after"] = 2
    assert "keeps its register" in rejected(moved, "register_single_holder")["message"]
    # A waiting employee while a register is free: A's handover at 0.0 missing.
    unassigned = copy.deepcopy(simulate(*NORMAL))
    drop_transition(unassigned, _record(transitions(unassigned), event="employee_register_assigned"))
    failure = rejected(unassigned, "register_handover_order")
    assert failure["t"] == 0.0 and "while one is free" in failure["message"]


def test_engine_claims_that_differ_from_the_events_are_rejected():
    # The events are valid; one claim of the engine result is changed at a time.
    base = simulate(*NORMAL)
    claims = [
        (lambda result: result["customers"][1].update(service_start_hours=0.8), "customer_reconciliation", "customers"),
        (lambda result: result["at_close"].update(waiting_customer_ids=[1]), "customer_reconciliation", "at_close"),
        (lambda result: result.update(mean_wait_hours=0.5), "customer_reconciliation", "mean_wait_hours"),
        (lambda result: result["queue"].update(max_length_in_horizon=2), "customer_reconciliation", "max_length"),
        (lambda result: result["queue"].update(customer_hours_in_horizon=0.2), "customer_reconciliation",
         "customer_hours_in_horizon"),
        (lambda result: result.update(finish=4.5), "employee_reconciliation", "finish"),
        (lambda result: result["employee_timeline"]["intervals"][2].update(register_id=2), "employee_reconciliation",
         "intervals"),
        (lambda result: result["staffing"]["windows"][0].update(accepting_capacity_hours=1.0), "employee_reconciliation",
         "window"),
    ]
    for change, check, quantity in claims:
        result = copy.deepcopy(base)
        change(result)
        assert quantity in rejected(result, check)["message"]
    breaks = copy.deepcopy(simulate([shift("A", 480, 720, rest=540)], rules(*LONG_SHIFT_BREAK, registers=1),
                                    [(0.75, 2.0), (1.125, 0.5)]))
    breaks["employee_timeline"]["breaks"][0]["actual_end"] = 1.8
    assert "started breaks" in rejected(breaks, "employee_reconciliation")["message"]


def test_the_rows_after_closing_hours_are_recomputed_from_the_events():
    # An interval's after_closing flag is the one row input the result reconciliation does not compare.
    demand, roster, workforce, required = SCENARIOS["overloaded"]
    result = simulate_named_replication(HORIZON, demand, staff(roster), workforce, roster,
                                        seed_sequence=replication_seed_sequence(2, 0), closing_policy=DRAIN,
                                        employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=required)
    shared_named_playback.build_named_playback(result, HORIZON, demand, replication_index=0, root_entropy=2)
    flagged = copy.deepcopy(result)
    next(row for row in flagged["employee_timeline"]["intervals"] if not row["after_closing"])["after_closing"] = True
    with pytest.raises(NamedPlaybackError) as caught:
        shared_named_playback.build_named_playback(flagged, HORIZON, demand, replication_index=0, root_entropy=2)
    assert caught.value.failure["check"] == "employee_reconciliation"
    assert "employee_hours_after_closing_by_state" in caught.value.failure["message"]


def test_recorded_inputs_that_cannot_be_trusted_or_rebuilt_are_refused():
    run = replicate("stable", replications=2, seed=12, policy=DRAIN)
    # An extra recorded field without a matching digest.
    extra = copy.deepcopy(run)
    extra["provenance"]["inputs"]["horizon"]["note"] = "x"
    assert "do not match the recorded inputs_sha256" in _refused(extra, 0, "regeneration_identity")["message"]
    # An extra employee field with a digest recomputed to match: the rebuilt inputs lack it.
    dropped = copy.deepcopy(run)
    provenance = dropped["provenance"]
    provenance["inputs"]["employees"][0]["note"] = "x"
    provenance["inputs_sha256"] = named_inputs_digest(provenance["inputs"], provenance["closing_policy"],
                                                      provenance["employee_policy"])
    assert "do not reproduce" in _refused(dropped, 0, "regeneration_identity")["message"]
    # An extra horizon field with a matching digest cannot be rebuilt into OperatingHorizon: refused, not a crash.
    unknown = copy.deepcopy(run)
    provenance = unknown["provenance"]
    provenance["inputs"]["horizon"]["note"] = "x"
    provenance["inputs_sha256"] = named_inputs_digest(provenance["inputs"], provenance["closing_policy"],
                                                      provenance["employee_policy"])
    assert "cannot be rebuilt" in _refused(unknown, 0, "regeneration_identity")["message"]
    # A recorded value the digest cannot represent.
    unrepresentable = copy.deepcopy(run)
    unrepresentable["provenance"]["inputs"]["horizon"]["start_minute"] = object()
    assert "cannot be digested" in _refused(unrepresentable, 0, "regeneration_identity")["message"]


def test_structural_corruptions_are_rejected():
    result = simulate(*NORMAL)
    truncated = copy.deepcopy(result)
    truncated["trace_truncated"] = True
    rejected(truncated, "trace_complete")
    no_count = copy.deepcopy(result)
    del no_count["trace"][0]["employee_transitions_before"]
    rejected(no_count, "trace_structure")
    no_closing = copy.deepcopy(result)
    del no_closing["trace"][-1]
    rejected(no_closing, "closing_rules")
    stranger = copy.deepcopy(result)
    transitions(stranger)[0]["employee_id"] = "Z"
    rejected(stranger, "trace_structure")


def test_a_failed_playback_raises_with_evidence_and_is_never_repaired():
    demand, roster, workforce, required = SCENARIOS["stable"]
    result = simulate_named_replication(HORIZON, demand, staff(roster), workforce, roster,
                                        seed_sequence=replication_seed_sequence(1, 0), closing_policy=DRAIN,
                                        employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=required)
    corrupted = copy.deepcopy(result)
    corrupted["trace"][0]["type"] = "teleport"
    before = copy.deepcopy(corrupted)
    with pytest.raises(NamedPlaybackError) as caught:
        shared_named_playback.build_named_playback(corrupted, HORIZON, demand, replication_index=0, root_entropy=1)
    assert caught.value.failure["check"] == "event_vocabulary" and caught.value.failure["event"]["type"] == "teleport"
    assert corrupted == before  # the trace is not repaired or changed


# ── Validation hardening (5B-4.5 follow-up) ─────────────────────────────────
#
# Two defects reproduced on 028917fe: (1) replay_named_trace and build_named_playback accepted any closing-policy
# label ("FOO", None, "drain", ...) on a day whose events are the same under both policies; (2) an unhashable value
# in a field the replay tests by set or dict membership raised TypeError instead of failing a check.

UNAPPROVED_POLICIES = ["FOO", None, "drain", "Drain", "hard_cutoff", "", 1, True, ["DRAIN"], ("DRAIN",), {"DRAIN": 1}]
CUSTOMER_FIELDS = ("t", "type", "customer_id", "employee_id", "register_id", "queue_len_after",
                   "employee_transitions_before")
TRANSITION_FIELDS = ("t", "stage", "employee_id", "from_state", "to_state", "register_before", "register_after", "event")


def _replication(name: str, policy: str) -> tuple[dict, list[DemandPeriod]]:
    demand, roster, workforce, required = SCENARIOS[name]
    return simulate_named_replication(HORIZON, demand, staff(roster), workforce, roster,
                                      seed_sequence=replication_seed_sequence(0, 0), closing_policy=policy,
                                      employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=required), demand


def _build(result: dict, demand: list[DemandPeriod]) -> dict:
    playback: dict = shared_named_playback.build_named_playback(result, HORIZON, demand, replication_index=0,
                                                                root_entropy=0)
    return playback


def test_approved_closing_policies_are_accepted_by_every_entry_point():
    for policy in (DRAIN, HARD_CUTOFF):
        accepted(simulate(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, policy=policy, required=TWO))
        result, demand = _replication("overrun_and_contention", policy)
        playback = _build(result, demand)
        assert (playback["closing"]["policy"], playback["validation"]["valid"]) == (policy, True)
        assert "closing_policy" in playback["validation"]["checks"]
        assert playback["provenance"]["playback_version"] == "novaq-shared-named-playback-v3"  # v3: employee_identity
        run = replicate("overrun_and_contention", replications=2, seed=7, policy=policy)
        assert playback_from_named_replications(run, 1)["summary"] == run["replications"][1]


@pytest.mark.parametrize("label", UNAPPROVED_POLICIES, ids=repr)
def test_an_unapproved_closing_policy_is_rejected_by_replay_and_build(label):
    # Nobody can serve after closing on these days, so the events are the same under both policies and only the label
    # differs. Exact values only: no case folding, no inference from the events, and the input is left as it was.
    for name in ("nobody_on_duty", "no_eligible_drain_employee"):
        result, demand = _replication(name, DRAIN)
        assert replay_named_trace(result, HORIZON, demand)["valid"]
        relabeled = dict(copy.deepcopy(result), closing_policy=label)
        before = copy.deepcopy(relabeled)
        checked = replay_named_trace(relabeled, HORIZON, demand)
        assert not checked["valid"] and checked["failure"]["check"] == "closing_policy"
        assert checked["failure"]["evidence"] == {"closing_policy": label, "approved": [DRAIN, HARD_CUTOFF]}
        with pytest.raises(NamedPlaybackError) as caught:
            _build(relabeled, demand)
        assert caught.value.failure == checked["failure"]
        assert relabeled == before


def test_a_closing_policy_whose_equality_is_not_a_bool_is_rejected():
    # A numpy array compares elementwise, so testing it against the approved strings would raise ValueError; the string
    # test rejects it first.
    result, demand = _replication("nobody_on_duty", DRAIN)
    label = np.array([DRAIN, DRAIN])
    checked = replay_named_trace(dict(result, closing_policy=label), HORIZON, demand)
    assert not checked["valid"] and checked["failure"]["check"] == "closing_policy"
    assert checked["failure"]["evidence"]["closing_policy"] is label


def test_the_stored_run_path_applies_the_same_closing_policy_check():
    run = replicate("nobody_on_duty", replications=2, seed=4, policy=DRAIN)
    # A relabeled policy with the old digest is a digest mismatch, as before.
    stale = copy.deepcopy(run)
    stale["provenance"]["closing_policy"] = "drain"
    _refused(stale, 0, "regeneration_identity")
    # With a digest recomputed over the unapproved value, the replay's closing-policy check refuses it before any
    # regeneration (on 028917fe the engine raised SharedSegmentError here).
    for label in ("FOO", None, "drain", ["DRAIN"]):
        relabeled = copy.deepcopy(run)
        provenance = relabeled["provenance"]
        provenance["closing_policy"] = label
        provenance["inputs_sha256"] = named_inputs_digest(provenance["inputs"], label, provenance["employee_policy"])
        assert _refused(relabeled, 0, "closing_policy")["evidence"]["closing_policy"] == label
    # prepare_named_playback takes the policy as an argument, and the engine refuses it as it refuses any invalid input.
    demand, roster, workforce, required = SCENARIOS["nobody_on_duty"]
    with pytest.raises(SharedSegmentError, match="closing_policy must be DRAIN or HARD_CUTOFF"):
        prepare_named_playback(HORIZON, demand, staff(roster), workforce, roster, root_entropy=4, replication_index=0,
                               closing_policy="drain", employee_policy=APPROVED_EMPLOYEE_POLICY,
                               required_staffing=required)


@pytest.mark.parametrize("source, field, check", [
    ("customer", "type", "event_vocabulary"),
    ("employee", "event", "event_vocabulary"),
    ("employee", "stage", "employee_transition_legal"),
    ("employee", "from_state", "employee_transition_legal"),
    ("employee", "to_state", "employee_transition_legal"),
    ("employee", "employee_id", "trace_structure"),
])
def test_an_unhashable_value_in_a_membership_field_fails_its_check(source, field, check):
    # The replay tests these fields by set or dict membership; on 028917fe each case raised TypeError. The value is
    # the field's own value wrapped in a list or a dict, so it is unhashable and is not converted back.
    result, demand = _replication("stable", DRAIN)
    for wrap in (lambda value: [value], lambda value: {"value": value}):
        corrupted = copy.deepcopy(result)
        record = (corrupted["trace"] if source == "customer" else transitions(corrupted))[0]
        record[field] = wrap(record[field])
        before = copy.deepcopy(corrupted)
        checked = replay_named_trace(corrupted, HORIZON, demand)
        assert not checked["valid"], "an unhashable value was accepted"
        failure = checked["failure"]
        assert (failure["check"], failure["source"], failure["source_index"]) == (check, source, 0), failure
        assert failure["event"][field] == record[field]
        with pytest.raises(NamedPlaybackError) as caught:
            _build(corrupted, demand)
        assert caught.value.failure == failure
        assert corrupted == before


def test_an_unhashable_started_break_key_fails_reconciliation():
    # Started engine breaks are keyed by (employee_id, actual_start); on 028917fe an unhashable key raised TypeError
    # (an extra row escaped the comparison, and a second row for A broke its sort).
    day = simulate([shift("A", 480, 720, rest=540)], rules(*LONG_SHIFT_BREAK, registers=1), [(0.75, 2.0), (1.125, 0.5)])
    accepted(day)
    for field, value in (("employee_id", ["A"]), ("actual_start", [1.25]), ("actual_start", {"t": 1.25})):
        corrupted = copy.deepcopy(day)
        corrupted["employee_timeline"]["breaks"].append(dict(corrupted["employee_timeline"]["breaks"][0], **{field: value}))
        before = copy.deepcopy(corrupted)
        failure = rejected(corrupted, "employee_reconciliation")
        assert "non-string employee_id or a non-numeric actual_start" in failure["message"]
        assert failure["evidence"]["breaks"][0][field] == value
        assert corrupted == before


def test_no_unhashable_trace_value_raises_or_is_accepted():
    # Every field of every customer event and employee transition on six days, replaced in turn by its own value
    # wrapped in a list and in a dict: each replay returns a structured failure with a known check.
    days = [simulate(*NORMAL), simulate(*HANDOVER), simulate(*FCFS, required=THREE),
            simulate(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, required=TWO),
            simulate(CLOSING_ROSTER, CLOSING_RULES, CLOSING_ARRIVALS, policy=HARD_CUTOFF, required=TWO),
            simulate([shift("A", 480, 720, rest=540)], rules(*LONG_SHIFT_BREAK, registers=1), [(0.75, 2.0), (1.125, 0.5)])]
    replays = 0
    for day in days:
        pristine = copy.deepcopy(day)
        for records, fields in ((day["trace"], CUSTOMER_FIELDS), (transitions(day), TRANSITION_FIELDS)):
            assert all(set(record) == set(fields) for record in records)
            for record in records:
                for field in fields:
                    original = record[field]
                    for wrapped in ([original], {"value": original}):
                        record[field] = wrapped
                        checked = replay_named_trace(day, HORIZON, PERIODS)
                        assert not checked["valid"], (field, record)
                        assert checked["failure"]["check"] in shared_named_playback.CHECKS
                        replays += 1
                    record[field] = original
        assert day == pristine  # the replay changed nothing
    assert replays == 2 * sum(len(day["trace"]) * len(CUSTOMER_FIELDS) + len(transitions(day)) * len(TRANSITION_FIELDS)
                              for day in days)


# ── Employee referential integrity (5B-4.5 follow-up) ───────────────────────
#
# Reproduced on 086075f7: an extra interval, shift, break, or closing-input record naming an employee outside the
# employee timeline was accepted, because the reconciliation compared only the timeline's employees (closing inputs
# were not compared at all). The timeline's employees are the input employees (evaluate_roster reports every one,
# rostered or not); ids are case-sensitive strings (shared_workforce._EMPLOYEE_ID) and are never normalized.

ORPHAN_VARIANTS = ["interval_zero_length", "interval_whole_timeline_off", "shift_activated", "shift_not_activated",
                   "break_started", "break_unfulfilled", "closing_input"]


def _identity_result() -> tuple[dict, list[DemandPeriod]]:
    # Employees A, B, C with at least one activated shift, one started break, and closing inputs (checked below).
    demand, roster, workforce, required = SCENARIOS["overrun_and_contention"]
    result = simulate_named_replication(HORIZON, demand, staff(roster), workforce, roster,
                                        seed_sequence=replication_seed_sequence(3, 0), closing_policy=DRAIN,
                                        employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=required)
    timeline = result["employee_timeline"]
    assert sorted(timeline["state_totals"]) == ["A", "B", "C"] and result["at_close"]["closing_inputs"]
    assert any(row["activated"] for row in timeline["shifts"])
    assert any(row["actual_start"] is not None for row in timeline["breaks"])
    return result, demand


def _extra_record(result: dict, variant: str, employee_id: Any) -> tuple[dict, list]:
    """A copy of ``result`` with one extra record for ``employee_id``; every legitimate record is left as it is."""
    corrupted = copy.deepcopy(result)
    timeline = corrupted["employee_timeline"]
    shift_row = next(row for row in timeline["shifts"] if row["activated"])
    started = next(row for row in timeline["breaks"] if row["actual_start"] is not None)
    block, name, row = {
        "interval_zero_length": ("employee_timeline", "intervals",
                                 dict(timeline["intervals"][0], start=corrupted["finish"], end=corrupted["finish"])),
        "interval_whole_timeline_off": ("employee_timeline", "intervals",
                                        dict(timeline["intervals"][0], start=corrupted["begin"], end=corrupted["finish"],
                                             state=OFF, register_id=None)),
        "shift_activated": ("employee_timeline", "shifts", dict(shift_row)),
        "shift_not_activated": ("employee_timeline", "shifts",
                                dict(shift_row, activated=False, actual_start=None, activation_delay=None, release=None,
                                     overrun=None)),
        "break_started": ("employee_timeline", "breaks", dict(started)),
        "break_unfulfilled": ("employee_timeline", "breaks",
                              dict(started, actual_start=None, actual_end=None, delay=None, outcome=UNFULFILLED,
                                   unfulfilled_cause="released")),
        "closing_input": ("at_close", "closing_inputs", {"type": "Release"}),
    }[variant]
    records = corrupted[block][name]
    records.append(dict(row, employee_id=employee_id))
    return corrupted, records


def _rejected_with(result: dict, demand: list[DemandPeriod], check: str) -> dict:
    checked = replay_named_trace(result, HORIZON, demand)
    assert not checked["valid"] and checked["failure"]["check"] == check, checked
    failure: dict = checked["failure"]
    return failure


@pytest.mark.parametrize("variant", ORPHAN_VARIANTS)
def test_an_extra_record_for_an_unknown_employee_is_rejected(variant):
    result, demand = _identity_result()
    corrupted, records = _extra_record(result, variant, "Z")
    before = copy.deepcopy(corrupted)
    checked = replay_named_trace(corrupted, HORIZON, demand)
    assert not checked["valid"], "an orphan employee record was accepted"
    failure = checked["failure"]
    assert failure["check"] == "employee_identity"
    record_type = ("at_close." if variant == "closing_input" else "employee_timeline.") + (
        "closing_inputs" if variant == "closing_input" else variant.split("_")[0] + "s")
    assert failure["evidence"] == {"record_type": record_type, "index": len(records) - 1, "record": records[-1],
                                   "timeline_employees": ["A", "B", "C"]}
    with pytest.raises(NamedPlaybackError) as caught:
        _build(corrupted, demand)
    assert caught.value.failure == failure
    assert corrupted == before  # not dropped, not repaired, no employee created


@pytest.mark.parametrize("variant", ["interval_zero_length", "interval_whole_timeline_off", "closing_input"])
def test_an_orphan_record_is_rejected_when_every_aggregate_is_unchanged(variant):
    # The extra record changes no count, total, or row value (the replication row, the state totals, the counts, and
    # the staffing series are the engine's own); only the orphan record is inconsistent.
    result, demand = _identity_result()
    corrupted, _ = _extra_record(result, variant, "Z")
    assert named_replication_row(corrupted, 0) == named_replication_row(result, 0)
    assert all(corrupted[key] == result[key] for key in ("counts", "customers", "queue", "staffing"))
    assert corrupted["employee_timeline"]["state_totals"] == result["employee_timeline"]["state_totals"]
    assert replay_named_trace(corrupted, HORIZON, demand)["failure"]["check"] == "employee_identity"


@pytest.mark.parametrize("employee_id", ["a", "A ", " A", "", "D", "Z" * 64], ids=repr)
def test_an_id_that_only_resembles_a_timeline_employee_is_rejected(employee_id):
    # Ids are exact, case-sensitive strings: "a" is not "A", and whitespace is not stripped. "D" and a 64-character id
    # are well-formed ids of employees who are not in this run.
    result, demand = _identity_result()
    for variant in ORPHAN_VARIANTS:
        corrupted, _ = _extra_record(result, variant, employee_id)
        checked = replay_named_trace(corrupted, HORIZON, demand)
        assert not checked["valid"] and checked["failure"]["check"] == "employee_identity", (variant, checked)


def test_a_non_string_employee_id_in_an_employee_record_fails_without_raising():
    # The 086075f7 contract holds: a malformed id fails a check. A started break keeps its earlier check
    # (employee_reconciliation, its key guard); every other record fails employee_identity.
    result, demand = _identity_result()
    for variant in ORPHAN_VARIANTS:
        for value in (["A"], {"id": "A"}, None, 5):
            corrupted, _ = _extra_record(result, variant, value)
            checked = replay_named_trace(corrupted, HORIZON, demand)
            expected = "employee_reconciliation" if variant == "break_started" else "employee_identity"
            assert not checked["valid"] and checked["failure"]["check"] == expected, (variant, value, checked)
    # A closing input without an employee_id, or one that is not a record, fails the same check.
    for record in ({"type": "Release"}, "Release Z"):
        corrupted = copy.deepcopy(result)
        corrupted["at_close"]["closing_inputs"].append(record)
        failure = _rejected_with(corrupted, demand, "employee_identity")
        assert failure["evidence"]["record"] == record


def test_the_timeline_employee_set_itself_is_checked():
    result, demand = _identity_result()
    # A non-string timeline employee fails the check (on 086075f7 sorting the ids raised TypeError).
    mixed = copy.deepcopy(result)
    mixed["employee_timeline"]["state_totals"][5] = dict.fromkeys(BASE_STATES, 0.0)
    assert _rejected_with(mixed, demand, "employee_identity")["evidence"]["timeline_employees"] == ["A", "B", "C", 5]
    # A timeline employee without intervals still fails the interval comparison, as on 086075f7.
    unknown = copy.deepcopy(result)
    unknown["employee_timeline"]["state_totals"]["Z"] = dict.fromkeys(BASE_STATES, 0.0)
    _rejected_with(unknown, demand, "employee_reconciliation")


def test_an_unrostered_input_employee_is_on_the_timeline_and_accepted():
    # The approved rule, not equality of every record: every input employee is on the timeline, rostered or not; only
    # rostered employees have shifts and breaks. D is an input employee with no roster shift.
    demand, roster, workforce, required = SCENARIOS["overrun_and_contention"]
    employees = staff(roster + [shift("D", 480, 720)])
    playback = prepare_named_playback(HORIZON, demand, employees, workforce, roster, root_entropy=3, replication_index=0,
                                      closing_policy=DRAIN, employee_policy=APPROVED_EMPLOYEE_POLICY,
                                      required_staffing=required)
    assert sorted(playback["employees"]) == ["A", "B", "C", "D"]
    assert {row["state"] for row in playback["employees"]["D"]} == {OFF}
    assert "D" not in {row["employee_id"] for row in playback["shifts"] + playback["breaks"]}
    assert "D" not in {event["employee_id"] for event in playback["events"]}
    assert playback["provenance"]["playback_version"] == "novaq-shared-named-playback-v3"
    assert "employee_identity" in playback["validation"]["checks"]


def test_the_input_employees_decide_what_the_result_alone_cannot(monkeypatch):
    # An employee who is OFF all day with no other record looks like an unrostered employee, so only the inputs can
    # tell. The engine never produces such a result; the two doctored engines below stand for a defective one.
    real = shared_named_playback.simulate_named_replication
    demand, roster, workforce, required = SCENARIOS["overrun_and_contention"]
    employees = staff(roster + [shift("D", 480, 720)])

    def with_extra(*args: Any, **kwargs: Any) -> dict:
        # Z copies exactly what the engine records for the unrostered D: its intervals and state totals.
        result: dict = real(*args, **kwargs)
        timeline = result["employee_timeline"]
        timeline["state_totals"]["Z"] = dict(timeline["state_totals"]["D"])
        timeline["intervals"] += [dict(row, employee_id="Z") for row in timeline["intervals"] if row["employee_id"] == "D"]
        return result

    def without_d(*args: Any, **kwargs: Any) -> dict:
        result: dict = real(*args, **kwargs)
        timeline = result["employee_timeline"]
        del timeline["state_totals"]["D"]
        timeline["intervals"] = [row for row in timeline["intervals"] if row["employee_id"] != "D"]
        return result

    for doctored, difference in ((with_extra, ({"Z"}, set())), (without_d, (set(), {"D"}))):
        monkeypatch.setattr(shared_named_playback, "simulate_named_replication", doctored)
        with pytest.raises(NamedPlaybackError) as caught:
            prepare_named_playback(HORIZON, demand, employees, workforce, roster, root_entropy=3, replication_index=0,
                                   closing_policy=DRAIN, employee_policy=APPROVED_EMPLOYEE_POLICY,
                                   required_staffing=required)
        failure = caught.value.failure
        timeline_ids, input_ids = set(failure["evidence"]["timeline_employees"]), set(failure["evidence"]["input_employees"])
        assert failure["check"] == "employee_identity" and (timeline_ids - input_ids, input_ids - timeline_ids) == difference
    # The stored-run path regenerates through prepare_named_playback, so it refuses in the same way (the run itself was
    # recorded by the real engine).
    run = run_named_replications(HORIZON, demand, employees, workforce, roster, replications=1, seed=3,
                                 closing_policy=DRAIN, employee_policy=APPROVED_EMPLOYEE_POLICY,
                                 required_staffing=required)
    monkeypatch.setattr(shared_named_playback, "simulate_named_replication", with_extra)
    assert _refused(run, 0, "employee_identity")["evidence"]["input_employees"] == ["A", "B", "C", "D"]
    monkeypatch.setattr(shared_named_playback, "simulate_named_replication", real)
    assert playback_from_named_replications(run, 0)["summary"] == run["replications"][0]


# ── Isolation ───────────────────────────────────────────────────────────────


def test_module_draws_nothing_and_uses_no_separate_queue_code():
    tree = ast.parse(Path(shared_named_playback.__file__).read_text(encoding="utf-8"))
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
                   or "break_optimization" in name for name in modules)
    # No draw, no private engine helper, and no engine run of its own: regeneration goes through the 5B-4.4 entry point.
    assert not names & {"exponential", "default_rng", "SeedSequence", "_draw_arrivals", "_closing_inputs",
                        "simulate_named_prescribed", "EmployeeTimeline"}
    assert "simulate_named_replication" in names and "replication_seed_sequence" in names


def test_module_is_registered_with_the_isolation_test():
    from tests.test_shared_segments import SHARED_QUEUE_ENHANCEMENT_MODULES

    assert "shared_named_playback.py" in SHARED_QUEUE_ENHANCEMENT_MODULES
