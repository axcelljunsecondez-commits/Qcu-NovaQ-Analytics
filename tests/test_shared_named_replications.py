"""Phase 5B-4.4 seeded replications of the named-employee shared-queue DES.

ALL EMPLOYEES, AVAILABILITY, RULES, ROSTERS, AND DEMAND IN THIS FILE ARE SYNTHETIC TEST DATA. They are not
NovaMart records, labor law, or recommended operating values.

The numpy pins conflict across environments (requirements.txt below 2.3 for CI, the 2.4.6 local lock, the
2.2.6 production lock), and stream equality across numpy versions is UNKNOWN. So no test here compares a
seeded value with a stored golden value. Seeded tests assert only properties that hold within one runtime:
reproducibility, equality with an independent recomputation of the draws, common random numbers, equality with
the anonymous engine, invariants checked on every replication, and hand rules recomputed from each
replication's own customers. A few coverage assertions ("at least one replication shows a delayed break")
rely on overwhelming probabilities, stated where they appear; they are not golden values.

The horizon is 08:00-12:00 (hours 0-4, closing 4.0), as in the Phase 5B-4.2 and 5B-4.3 tests.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import math
import random
import statistics
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scipy.stats import t as student_t

from backend.queueing_engine.config import MC_MAX_TRIALS
from backend.queueing_engine.services.shared_segments import DemandPeriod, SharedSegmentError, StaffingSegment
from backend.queueing_engine.services.shared_workforce import BreakRule
from backend.queueing_engine.simulation import shared_continuous_des, shared_named_replications
from backend.queueing_engine.simulation.shared_employee_states import (
    COMPLETED,
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
from backend.queueing_engine.simulation.shared_named_replications import (
    customer_inputs_digest,
    named_replication_row,
    replication_seed_sequence,
    run_named_replications,
    simulate_named_replication,
)
from tests.test_shared_employee_states import HORIZON, break_rows, break_rule, rules, shift, shift_row, staff
from tests.test_shared_named_des import _COMPARED, LONG_SHIFT_BREAK, REDUCTIONS, TWO_PERIODS, check_named

# ── SYNTHETIC TEST DATA ──────────────────────────────────────────────────────

DRAIN, HARD_CUTOFF = shared_continuous_des.DRAIN, shared_continuous_des.HARD_CUTOFF
CLOSE = 4.0
MU = 4.0
ONE = [StaffingSegment("S", 480, 720, 1)]
TWO = [StaffingSegment("S", 480, 720, 2)]


def periods(rate: float) -> list[DemandPeriod]:
    return [DemandPeriod("P", 480, 720, rate, MU)]


SPLIT_RULES = rules(BreakRule(15, 60, 0, ()), break_rule(61, 480, rest=15), registers=2, max_shifts=2, rest=30)
# name -> (demand periods, roster, workforce rules, required staffing)
SCENARIOS: dict[str, tuple[list[DemandPeriod], list, Any, list[StaffingSegment]]] = {
    # λ 6 against two employees at μ 4 (offered load 1.5), breaks at 09:30 and 10:30.
    "stable": (periods(6.0), [shift("A", 480, 720, rest=570), shift("B", 480, 720, rest=630)],
               rules(*LONG_SHIFT_BREAK, registers=2), TWO),
    # λ 20 against two employees at μ 4 (offered load 5): a long line at closing. No breaks.
    "overloaded": (periods(20.0), [shift("A", 480, 720), shift("B", 480, 720)], rules(registers=2), TWO),
    # One overloaded employee with a 30-minute break at 10:00.
    "delayed_break": (periods(20.0), [shift("A", 480, 720, rest=600)], rules(*LONG_SHIFT_BREAK, registers=1), ONE),
    # A 08:00-10:00 and C 10:00-12:00 share register 1 with B (08:00-12:00, break 11:00) on register 2.
    "overrun_and_contention": (periods(20.0), [shift("A", 480, 600), shift("B", 480, 720, rest=660),
                                               shift("C", 600, 720)], rules(*LONG_SHIFT_BREAK, registers=2), TWO),
    # Nobody is on duty at closing: A works 08:00-11:00 only.
    "no_eligible_drain_employee": (periods(10.0), [shift("A", 480, 660)], rules(registers=1), ONE),
    # A's split shift (08:00-09:00, 09:30-11:30 with a break at 10:00; rest 30 minutes) and B all day.
    "split_shift": (periods(12.0), [shift("A", 480, 540), shift("A", 570, 690, rest=600),
                                    shift("B", 480, 720, rest=630)], SPLIT_RULES, TWO),
    # A starts 07:30 (before opening); B works 10:00-13:00 (past closing) with a break 11:30-12:00.
    "outside_the_horizon": (periods(8.0), [shift("A", 450, 690, rest=600), shift("B", 600, 780, rest=690)],
                            rules(*LONG_SHIFT_BREAK, registers=2), ONE),
    # A light day whose only break is scheduled 11:30-12:00, ending exactly at closing.
    "break_ending_at_closing": (periods(1.0), [shift("A", 480, 720, rest=690)],
                                rules(*LONG_SHIFT_BREAK, registers=1), ONE),
    # No demand at all.
    "zero_arrivals": (periods(0.0), [shift("A", 480, 720, rest=540)], rules(*LONG_SHIFT_BREAK, registers=1), ONE),
    # Nobody on duty in the horizon: A's only shift starts at closing (12:00-13:00) and is never activated.
    "nobody_on_duty": (periods(3.0), [shift("A", 720, 780)], rules(registers=1), ONE),
}


def replicate(name: str, *, replications: int, seed: int | None, policy: str) -> dict:
    demand, roster, workforce, required = SCENARIOS[name]
    return run_named_replications(HORIZON, demand, staff(roster), workforce, roster, replications=replications,
                                  seed=seed, closing_policy=policy, employee_policy=APPROVED_EMPLOYEE_POLICY,
                                  required_staffing=required)


def regenerate(name: str, root_entropy: int, index: int, policy: str, **options: Any) -> dict:
    demand, roster, workforce, required = SCENARIOS[name]
    return simulate_named_replication(HORIZON, demand, staff(roster), workforce, roster,
                                      seed_sequence=replication_seed_sequence(root_entropy, index),
                                      closing_policy=policy, employee_policy=APPROVED_EMPLOYEE_POLICY,
                                      required_staffing=required, **options)


def checked(name: str, root_entropy: int, index: int, policy: str) -> dict:
    """A regenerated replication, checked by the independent 5B-4.3 checker (float-tolerant mode)."""
    demand, roster, workforce, required = SCENARIOS[name]
    result = regenerate(name, root_entropy, index, policy)
    arrivals = shared_continuous_des.draw_arrivals(HORIZON, demand, required,
                                                   seed_sequence=replication_seed_sequence(root_entropy, index))
    check_named(result, arrivals, workforce, roster, demand, required, policy, exact=False)
    return result


def inputs_of(result: dict) -> list[tuple[float, float]]:
    return [(row["arrival_hours"], row["unit_work"]) for row in result["customers"]]


def _near(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is b
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def check_row(row: dict, result: dict, index: int) -> None:
    """Recompute a replication row from the full result's customers, intervals, shifts, and breaks."""
    customers, timeline = result["customers"], result["employee_timeline"]
    close, finish = result["closing_time"], result["finish"]
    text = "\n".join(f"{at.hex()} {work.hex()}" for at, work in inputs_of(result))
    assert (row["replication_index"], row["spawn_key"]) == (index, result["replication"]["spawn_key"])
    assert row["customer_inputs_sha256"] == hashlib.sha256(text.encode("ascii")).hexdigest()
    done = [item for item in customers if item["status"] == DEPARTED]
    missed = [item for item in customers if item["status"] == UNSERVED_AT_CLOSE]
    assert row["customer_conservation"] is True and len(done) + len(missed) == len(customers)
    assert row["customers"] == {
        "arrivals": len(customers), "served": len(done), "unserved": len(missed),
        "unserved_hard_cutoff": sum(1 for item in missed if item["unserved_reason"] == HARD_CUTOFF_REASON),
        "unserved_no_eligible_employee": sum(1 for item in missed if item["unserved_reason"] == NO_ELIGIBLE_EMPLOYEE),
        "served_after_closing": sum(1 for item in done if item["service_start_hours"] >= close),
    }
    waits = [item["service_start_hours"] - item["arrival_hours"] for item in done]
    waiting = row["waiting"]
    assert _near(waiting["wait_sum_hours"], sum(waits))
    assert _near(waiting["mean_wait_hours"], sum(waits) / len(waits) if waits else None)
    censored = sum(close - item["arrival_hours"] for item in missed)
    assert _near(waiting["customer_hours_total"], sum(waits) + censored)
    assert _near(waiting["customer_hours_in_horizon"] + waiting["customer_hours_after_closing"],
                 waiting["customer_hours_total"])
    assert waiting["max_queue_in_horizon"] == result["queue"]["max_length_in_horizon"]
    assert row["closing"] == {
        "waiting_at_close": sum(1 for item in customers if item["arrival_hours"] < close and (
            item["status"] == UNSERVED_AT_CLOSE or item["service_start_hours"] >= close)),
        "in_service_at_close": sum(1 for item in done if item["service_start_hours"] < close < item["service_end_hours"]),
        "drain_crew_size": len(result["at_close"]["drain_crew"]),
        "run_after_closing_hours": finish - close,
    }
    # Staffing: each window's values under its kind; gaps and the requirement only inside the horizon.
    staffing = row["staffing"]
    for window in result["staffing"]["windows"]:
        values = staffing["segments"][window["window"]] if window["kind"] == "staffing_segment" else staffing[window["kind"]]
        for key in ("duration_hours", "scheduled_active_hours", "accepting_capacity_hours", "busy_employee_hours",
                    "register_occupancy_hours", "waiting_for_register_hours"):
            assert values[key] == window[key]
        inside = window["kind"] in ("staffing_segment", "horizon")
        assert inside == (0.0 <= window["start"] and window["end"] <= close and window["kind"] != "after_closing")
        if inside:
            assert values["required_staffing_hours"] == window["required_staffing_hours"]
            for gap in ("schedule_realization_gap", "requirement_gap"):
                assert (values[f"{gap}_shortfall_hours"], values[f"{gap}_excess_hours"]) == (
                    window[gap]["shortfall_hours"], window[gap]["excess_hours"])
        else:
            assert len(values) == 6
    # Employees: from the intervals, shifts, and breaks.
    employees = row["employees"]
    states = {item["state"] for item in timeline["intervals"]} | set(employees["employee_hours_by_state"])
    for state in states:
        assert _near(employees["employee_hours_by_state"][state], sum(
            item["end"] - item["start"] for item in timeline["intervals"] if item["state"] == state))
        assert _near(employees["employee_hours_after_closing_by_state"][state], sum(
            item["end"] - item["start"] for item in timeline["intervals"] if item["state"] == state
            and item["start"] >= close))
    worked = [item for item in timeline["shifts"] if item["actual_start"] is not None]
    overruns = [max(0.0, item["release"] - item["scheduled_end"]) for item in worked]
    started = [item for item in timeline["breaks"] if item["actual_start"] is not None]
    delays = [item["actual_start"] - item["scheduled_start"] for item in started]
    unfulfilled = [item["unfulfilled_cause"] for item in timeline["breaks"] if item["actual_start"] is None]
    assert (employees["shifts_scheduled"], employees["shifts_activated"], employees["shifts_not_activated"]) == (
        len(timeline["shifts"]), len(worked), len(timeline["shifts"]) - len(worked))
    assert employees["shifts_with_overrun"] == sum(1 for value in overruns if value > 0)
    assert _near(employees["overrun_hours_total"], sum(overruns))
    assert employees["overrun_hours_max"] == (max(overruns) if overruns else None)
    assert _near(employees["activation_delay_hours_total"],
                 sum(item["actual_start"] - item["scheduled_start"] for item in worked))
    assert (employees["breaks_scheduled"], employees["breaks_started"]) == (len(timeline["breaks"]), len(started))
    assert (employees["breaks_completed"], employees["breaks_truncated_by_closing"], employees["breaks_unfulfilled"]) == (
        sum(1 for item in started if item["actual_end"] < close), sum(1 for item in started if item["actual_end"] == close),
        len(unfulfilled))
    assert employees["breaks_unfulfilled_by_cause"] == {
        cause: unfulfilled.count(cause) for cause in ("released", "shift_not_activated", "cancelled_at_closing")}
    assert _near(employees["break_delay_hours_total"], sum(delays))
    assert employees["break_delay_hours_max"] == (max(delays) if delays else None)
    assert employees["transitions"] == len(timeline["transitions"])


def independent_draws(demand: list[DemandPeriod], root_entropy: int, index: int) -> list[tuple[float, float]]:
    """The documented draws recomputed without the engine: two PCG64 streams keyed (index, 0) and (index, 1)
    under the root entropy; exponential gaps at each period's rate, restarted at each period start; then one
    Exp(1) unit work per arrival."""
    gaps = np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy=root_entropy, spawn_key=(index, 0))))
    work = np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy=root_entropy, spawn_key=(index, 1))))
    times: list[float] = []
    for period in demand:
        rate = float(period.arrival_rate_per_hour)
        at, stop = (period.start_minute - 480) / 60.0, (period.end_minute - 480) / 60.0
        while rate > 0:
            at += float(gaps.exponential(1.0 / rate))
            if at >= stop:
                break
            times.append(at)
    return list(zip(times, [float(value) for value in work.exponential(1.0, size=len(times))]))


# ── Seeds, streams, and the X5 interface ────────────────────────────────────


@pytest.mark.parametrize("seed", [0, 7, None])
def test_replication_seed_is_the_phase_4_child(seed):
    root = np.random.SeedSequence(seed)
    children = root.spawn(5)
    for index, child in enumerate(children):
        mine = replication_seed_sequence(root.entropy, index)
        assert (mine.entropy, mine.spawn_key, mine.pool_size) == (child.entropy, child.spawn_key, child.pool_size)
        assert (mine.generate_state(8) == child.generate_state(8)).all()


@pytest.mark.parametrize(("entropy", "index"), [(-1, 0), (1, -1), (1.5, 0), (1, True), (None, 0)])
def test_replication_seed_rejects_invalid_identities(entropy, index):
    with pytest.raises(SharedSegmentError):
        replication_seed_sequence(entropy, index)


def test_customers_are_the_anonymous_draws_and_match_an_independent_recomputation():
    demand = TWO_PERIODS  # two periods with different rates: the gap stream restarts at 10:00
    roster, segments = REDUCTIONS["growing_crew"]
    for index in range(6):
        expected = independent_draws(demand, 424242, index)
        assert len(expected) > 20
        public = shared_continuous_des.draw_arrivals(HORIZON, demand, segments,
                                                     seed_sequence=replication_seed_sequence(424242, index))
        anonymous = shared_continuous_des.simulate_shared_replication(
            HORIZON, demand, segments, seed_sequence=replication_seed_sequence(424242, index), closing_policy=DRAIN)
        named = simulate_named_replication(
            HORIZON, demand, staff(roster), rules(registers=2), roster,
            seed_sequence=replication_seed_sequence(424242, index), closing_policy=DRAIN,
            employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=segments)
        assert public == expected == inputs_of(anonymous) == inputs_of(named)
        assert named["replication"]["customer_inputs"] == {
            "count": len(expected), "sha256": customer_inputs_digest(expected),
            "definition": shared_named_replications.CUSTOMER_INPUTS_DEFINITION}


def test_the_public_interface_reuses_the_private_generation_and_ignores_staffing():
    demand = TWO_PERIODS
    one = shared_continuous_des.draw_arrivals(HORIZON, demand, [StaffingSegment("a", 480, 600, 1),
                                                                StaffingSegment("b", 600, 720, 3)],
                                              seed_sequence=replication_seed_sequence(5, 2))
    other = shared_continuous_des.draw_arrivals(HORIZON, demand, [StaffingSegment("x", 480, 540, 0),
                                                                  StaffingSegment("y", 540, 600, 2),
                                                                  StaffingSegment("z", 600, 720, 9)],
                                                seed_sequence=replication_seed_sequence(5, 2))
    private = shared_continuous_des._draw_arrivals(HORIZON, demand, replication_seed_sequence(5, 2))
    assert one == other == private
    used = replication_seed_sequence(5, 2)
    used.spawn(1)
    with pytest.raises(SharedSegmentError, match="unused"):
        shared_continuous_des.draw_arrivals(HORIZON, demand, [StaffingSegment("a", 480, 600, 1),
                                                              StaffingSegment("b", 600, 720, 1)],
                                            seed_sequence=used)
    with pytest.raises(SharedSegmentError, match="horizon end"):
        shared_continuous_des.draw_arrivals(HORIZON, demand, [StaffingSegment("a", 480, 600, 1)],
                                            seed_sequence=replication_seed_sequence(5, 2))


def test_distinct_replication_identities_give_distinct_streams():
    digests, first_arrivals = set(), set()
    for index in range(60):
        pairs = shared_continuous_des.draw_arrivals(HORIZON, periods(10.0), ONE,
                                                    seed_sequence=replication_seed_sequence(99, index))
        digests.add(customer_inputs_digest(pairs))
        first_arrivals.add(pairs[0][0])
    assert len(digests) == len(first_arrivals) == 60
    # Different roots with the same index differ too.
    assert customer_inputs_digest(shared_continuous_des.draw_arrivals(
        HORIZON, periods(10.0), ONE, seed_sequence=replication_seed_sequence(100, 0))) not in digests


# ── Reproducibility and regeneration ────────────────────────────────────────


def test_same_identity_reproduces_the_same_result():
    for policy in (DRAIN, HARD_CUTOFF):
        first = regenerate("overrun_and_contention", 17, 3, policy)
        assert first == regenerate("overrun_and_contention", 17, 3, policy)
    run = replicate("split_shift", replications=6, seed=11, policy=DRAIN)
    assert run == replicate("split_shift", replications=6, seed=11, policy=DRAIN)
    assert run["replications"] != replicate("split_shift", replications=6, seed=12, policy=DRAIN)["replications"]
    assert run["provenance"]["root_entropy"] == 11
    # A longer run shares its first replications with a shorter run of the same seed.
    assert replicate("split_shift", replications=9, seed=11, policy=DRAIN)["replications"][:6] == run["replications"]


def test_seed_none_records_entropy_that_reproduces_the_run():
    free = replicate("stable", replications=4, seed=None, policy=HARD_CUTOFF)
    entropy = free["provenance"]["root_entropy"]
    assert free["provenance"]["seed"] is None and isinstance(entropy, int) and entropy >= 0
    assert replicate("stable", replications=4, seed=entropy, policy=HARD_CUTOFF)["replications"] == free["replications"]


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_a_selected_replication_is_regenerated_alone(policy):
    run = replicate("delayed_break", replications=10, seed=2024, policy=policy)
    entropy = run["provenance"]["root_entropy"]
    for index in (0, 7):
        full = regenerate("delayed_break", entropy, index, policy)
        assert named_replication_row(full, index) == run["replications"][index]
        assert (full["replication"]["seed_entropy"], full["replication"]["spawn_key"]) == (entropy, [index])
        # The Phase 5B-4.3 result is preserved unchanged: it equals the prescribed engine on the same draws.
        demand, roster, workforce, required = SCENARIOS["delayed_break"]
        prescribed = simulate_named_prescribed(
            HORIZON, demand, staff(roster), workforce, roster,
            independent_draws(demand, entropy, index), closing_policy=policy,
            employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=required)
        assert {key: value for key, value in full.items() if key != "replication"} == prescribed
        # The trace setting does not change the row.
        short = regenerate("delayed_break", entropy, index, policy, max_trace_events=0)
        assert named_replication_row(short, index) == run["replications"][index]


# ── Common random numbers ───────────────────────────────────────────────────


def test_common_random_numbers_across_rosters():
    # Two different workforces on the same demand and seed: two employees with no breaks and two required
    # servers, against one employee with a delayed break and one required server. Replication by replication
    # the customers are identical (and identical to the anonymous engine's), so any difference in outcome comes
    # from the workforce alone.
    first = replicate("overloaded", replications=8, seed=606, policy=DRAIN)
    second = replicate("delayed_break", replications=8, seed=606, policy=HARD_CUTOFF)
    assert [row["customer_inputs_sha256"] for row in first["replications"]] == [
        row["customer_inputs_sha256"] for row in second["replications"]]
    for index in (0, 5):
        one, two = regenerate("overloaded", 606, index, DRAIN), regenerate("delayed_break", 606, index, HARD_CUTOFF)
        anonymous = shared_continuous_des.simulate_shared_replication(
            HORIZON, periods(20.0), ONE, seed_sequence=replication_seed_sequence(606, index), closing_policy=DRAIN)
        assert inputs_of(one) == inputs_of(two) == inputs_of(anonymous)
    # Paired outcomes differ (offered load 5: the one-employee roster's line is far longer in practice).
    assert any(a["waiting"]["customer_hours_total"] != b["waiting"]["customer_hours_total"]
               for a, b in zip(first["replications"], second["replications"]))


class _CountingGenerator:
    """A generator that records every draw, wrapped around numpy's own."""

    def __init__(self, inner: np.random.Generator, log: list[tuple]) -> None:
        self.inner, self.log = inner, log

    @property
    def bit_generator(self) -> Any:
        return self.inner.bit_generator

    def exponential(self, scale: float = 1.0, size: int | None = None) -> Any:
        self.log.append(("exponential", 1 if size is None else int(size)))
        return self.inner.exponential(scale, size)


def test_employee_transitions_consume_no_random_numbers(monkeypatch):
    real = np.random.default_rng
    log: list[tuple] = []

    def counting(seed: Any = None) -> _CountingGenerator:
        log.append(("stream", tuple(seed.spawn_key) if isinstance(seed, np.random.SeedSequence) else seed))
        return _CountingGenerator(real(seed), log)

    monkeypatch.setattr(np.random, "default_rng", counting)
    draws: dict[str, list[tuple]] = {}
    # Three different workforces on the same demand (λ 20), under both closing policies.
    for name in ("overloaded", "delayed_break", "overrun_and_contention"):
        for policy in (DRAIN, HARD_CUTOFF):
            log.clear()
            result = regenerate(name, 8080, 3, policy)
            # Drop the runtime probe (default_rng(0) in the provenance), which draws nothing.
            draws[f"{name}/{policy}"] = [item for item in log if item != ("stream", 0)]
            count = result["counts"]["arrivals"]
            # Exactly two streams, and draws fixed by the demand alone: one gap per arrival plus the gap that
            # passes the period end, then one work value per arrival.
            assert draws[f"{name}/{policy}"] == (
                [("stream", (3, 0)), ("stream", (3, 1))] + [("exponential", 1)] * (count + 1) + [("exponential", count)])
    assert len({tuple(value) for value in draws.values()}) == 1


def test_the_named_engine_runs_with_every_random_source_disabled(monkeypatch):
    demand, roster, workforce, required = SCENARIOS["overrun_and_contention"]
    arrivals = independent_draws(demand, 31337, 1)
    expected = {policy: simulate_named_prescribed(HORIZON, demand, staff(roster), workforce, roster, arrivals,
                                                  closing_policy=policy, employee_policy=APPROVED_EMPLOYEE_POLICY,
                                                  required_staffing=required)
                for policy in (DRAIN, HARD_CUTOFF)}

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a random number source was used")

    for name in ("default_rng", "Generator", "SeedSequence", "RandomState", "PCG64", "random", "exponential"):
        monkeypatch.setattr(np.random, name, forbidden)
    for name in ("random", "Random", "uniform", "choice", "shuffle", "randint", "expovariate", "sample"):
        monkeypatch.setattr(random, name, forbidden)
    for policy in (DRAIN, HARD_CUTOFF):
        assert simulate_named_prescribed(HORIZON, demand, staff(roster), workforce, roster, arrivals,
                                         closing_policy=policy, employee_policy=APPROVED_EMPLOYEE_POLICY,
                                         required_staffing=required) == expected[policy]


def test_global_random_states_are_untouched():
    python_state, numpy_state = random.getstate(), np.random.get_state()
    replicate("split_shift", replications=3, seed=4, policy=DRAIN)
    assert random.getstate() == python_state
    after = np.random.get_state()
    assert after[0] == numpy_state[0] and (after[1] == numpy_state[1]).all() and after[2:] == numpy_state[2:]


# ── Reduction to the anonymous engine on seeded customers ───────────────────


@pytest.mark.parametrize("case", sorted(REDUCTIONS))
@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_seeded_reduction_to_the_anonymous_engine(case, policy):
    # The 5B-4.3 reduction, now on seeded customers: where the roster is equivalent to the anonymous schedule,
    # every customer's outcome is identical. Employee and server identities are not compared (X1 versus lowest
    # server id).
    roster, segments = REDUCTIONS[case]
    reason = {"no_eligible_server": NO_ELIGIBLE_EMPLOYEE}
    for index in range(8):
        named = simulate_named_replication(
            HORIZON, TWO_PERIODS, staff(roster), rules(registers=2), roster,
            seed_sequence=replication_seed_sequence(31, index), closing_policy=policy,
            employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=segments)
        anonymous = shared_continuous_des.simulate_shared_replication(
            HORIZON, TWO_PERIODS, segments, seed_sequence=replication_seed_sequence(31, index), closing_policy=policy)
        expected = [{key: reason.get(row[key], row[key]) if key == "unserved_reason" else row[key] for key in _COMPARED}
                    for row in anonymous["customers"]]
        assert [{key: row[key] for key in _COMPARED} for row in named["customers"]] == expected, index
        check_named(named, inputs_of(anonymous), rules(registers=2), roster, TWO_PERIODS, segments, policy, exact=False)


# ── Invariants on every replication ─────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(SCENARIOS))
@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_invariants_hold_in_every_replication(name, policy):
    # Every replication is regenerated in full and checked by check_named: conservation, one FCFS line,
    # non-preemptive service, one customer per employee, register occupancy <= K, the 5B-4.2 employee
    # invariants, work conservation, DRAIN and HARD_CUTOFF closing, X6, the approved closing-break rules, and
    # staffing gaps only inside the horizon. The regenerated rows equal the stored rows.
    run = replicate(name, replications=6, seed=1234, policy=policy)
    for index, row in enumerate(run["replications"]):
        assert row["customer_conservation"]
        result = checked(name, 1234, index, policy)
        assert named_replication_row(result, index) == row
        check_row(row, result, index)
        staffing = row["staffing"]
        assert set(staffing) >= {"horizon", "segments", "after_closing"}
        for key in ("before_opening", "after_closing"):
            assert key not in staffing or not any("gap" in field or "required" in field for field in staffing[key])
        assert all("requirement_gap_shortfall_hours" in values
                   for values in [staffing["horizon"], *staffing["segments"].values()])


# ── Seeded cases with independently recomputed rules ────────────────────────


def test_zero_arrivals():
    run = replicate("zero_arrivals", replications=5, seed=3, policy=DRAIN)
    empty = hashlib.sha256(b"").hexdigest()
    for row in run["replications"]:
        assert row["customers"]["arrivals"] == row["customers"]["served"] == 0
        assert row["waiting"]["mean_wait_hours"] is None and row["customer_inputs_sha256"] == empty
        # A takes its 09:00 break on time (idle) and accepts for 4.0 - 0.5 = 3.5 employee-hours, as scheduled.
        assert (row["employees"]["breaks_completed"], row["employees"]["break_delay_hours_total"]) == (1, 0.0)
        horizon = row["staffing"]["horizon"]
        assert (horizon["accepting_capacity_hours"], horizon["scheduled_active_hours"]) == (3.5, 3.5)
        assert horizon["requirement_gap_shortfall_hours"] == 0.5
    summary = run["summary"]
    means = summary["waiting_time"]["mean_of_replication_means_hours"]
    assert (means["mean"], means["n"], means["n_undefined"]) == (None, 0, 5)  # undefined, counted, never 0
    weighted = summary["waiting_time"]["customer_weighted_mean_hours"]
    assert (weighted["value"], weighted["denominator_served_customers"]) == (None, 0)
    assert summary["metrics"]["employees"]["overrun_hours_max"]["n"] == 5


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_nobody_on_duty_leaves_every_customer_unserved_and_maxima_undefined(policy):
    # A's only shift starts at closing and is released there without activating, so every arrival waits until
    # closing and is unserved (no_eligible_employee under DRAIN, hard_cutoff under HARD_CUTOFF). With no shift
    # activated and no break started, the overrun and break-delay maxima are undefined, counted, never 0.
    run = replicate("nobody_on_duty", replications=5, seed=13, policy=policy)
    reason = "unserved_no_eligible_employee" if policy == DRAIN else "unserved_hard_cutoff"
    for row in run["replications"]:
        customers, employees = row["customers"], row["employees"]
        assert customers["served"] == 0 and customers["unserved"] == customers[reason] == customers["arrivals"]
        assert (employees["shifts_activated"], employees["shifts_not_activated"]) == (0, 1)
        assert employees["overrun_hours_max"] is None and employees["break_delay_hours_max"] is None
        assert row["staffing"]["horizon"]["accepting_capacity_hours"] == 0.0
    metrics = run["summary"]["metrics"]["employees"]
    assert (metrics["overrun_hours_max"]["n"], metrics["overrun_hours_max"]["n_undefined"]) == (0, 5)
    assert run["summary"]["outcome_counts"]["with_unserved_customers"]["replications"] == sum(
        1 for row in run["replications"] if row["customers"]["arrivals"] > 0)


def test_an_unknown_unfulfilled_cause_is_rejected_not_dropped():
    result = regenerate("stable", 3, 0, DRAIN)
    doctored = dict(result, employee_timeline=dict(result["employee_timeline"], breaks=[
        dict(item, outcome=UNFULFILLED, unfulfilled_cause="mystery", actual_start=None, actual_end=None, delay=None)
        for item in result["employee_timeline"]["breaks"]]))
    with pytest.raises(SharedSegmentError, match="mystery"):
        named_replication_row(doctored, 0)


def test_ordinary_stable_day():
    # Under DRAIN a non-empty crew serves everyone still waiting at closing, so nobody is unserved and every
    # customer waiting at closing starts service after closing.
    run = replicate("stable", replications=10, seed=77, policy=DRAIN)
    for row in run["replications"]:
        customers, closing = row["customers"], row["closing"]
        assert row["customer_conservation"] and customers["arrivals"] == customers["served"] + customers["unserved"]
        if closing["drain_crew_size"] > 0:
            assert customers["unserved"] == 0 and customers["served_after_closing"] == closing["waiting_at_close"]
    summary = run["summary"]
    assert summary["customers"]["conserved_in_every_replication"]
    assert summary["customers"]["totals"]["arrivals"] == sum(row["customers"]["arrivals"] for row in run["replications"])
    assert summary["waiting_time"]["mean_of_replication_means_hours"]["n"] == 10


def _in_service_at(result: dict, who: str, t: float) -> dict | None:
    rows = [row for row in result["customers"] if row["status"] == DEPARTED and row["employee_id"] == who
            and row["service_start_hours"] < t < row["service_end_hours"]]
    assert len(rows) <= 1
    return rows[0] if rows else None


def test_delayed_break_matches_the_service_under_way():
    # A's break is scheduled at 2.0 (10:00). If A is serving then, the break starts at that service's end (P1,
    # P2: full duration from the actual start); otherwise at 2.0. Recomputed from each replication's customers.
    # A service still running at closing leaves the break pending, cancelled at closing; one starting within
    # 30 minutes of closing is truncated there.
    delayed = 0
    for index in range(8):
        result = checked("delayed_break", 555, index, DRAIN)
        (item,) = break_rows(result["employee_timeline"], "A")
        serving = _in_service_at(result, "A", 2.0)
        start = serving["service_end_hours"] if serving else 2.0
        assert item["due"] == 2.0
        if start >= CLOSE:
            assert (item["outcome"], item["unfulfilled_cause"]) == (UNFULFILLED, "cancelled_at_closing")
            continue
        assert (item["actual_start"], item["delay"]) == (start, start - 2.0)
        if start + 0.5 < CLOSE:
            assert (item["outcome"], item["actual_end"]) == (COMPLETED, start + 0.5)
        else:
            assert (item["outcome"], item["actual_end"]) == (TRUNCATED_BY_CLOSING, CLOSE)
        delayed += item["delay"] > 0
    # Offered load 5 on one employee: an idle A at 2.0 needs every one of about 40 arrivals served by about 8
    # services, so at least one of eight replications shows a delay with overwhelming probability.
    assert delayed >= 1


def test_shift_overrun_and_register_contention():
    # A's shift ends at 2.0; if A is serving then, A finishes (overrun) and holds register 1 until release. C
    # starts at 2.0 and B holds register 2 all day (except its break), so C waits for a register exactly until
    # a register frees: A's release or B's break start, whichever is first.
    contended = 0
    for index in range(8):
        result = checked("overrun_and_contention", 808, index, HARD_CUTOFF)
        employees = result["employee_timeline"]
        serving = _in_service_at(result, "A", 2.0)
        release = serving["service_end_hours"] if serving else 2.0
        a = shift_row(employees, "A")
        assert (a["release"], a["overrun"]) == (release, release - 2.0)
        b_break = break_rows(employees, "B")[0]
        freed = min(release, b_break["actual_start"]) if b_break["actual_start"] is not None else release
        waiting = [(row["start"], row["end"]) for row in employees["intervals"]
                   if row["employee_id"] == "C" and row["state"] == WAITING_FOR_REGISTER]
        assert waiting == ([(2.0, freed)] if freed > 2.0 else [])
        contended += freed > 2.0
    assert contended >= 1  # offered load 5 on two employees: A is serving at 2.0 in practice


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_closing_policies_on_an_overloaded_day(policy):
    # DRAIN: the two employees (both accepting before closing) serve everyone; the run ends at the last
    # completion. HARD_CUTOFF: the line at closing is unserved, nothing starts at or after closing, and each
    # employee is released at closing or at the end of the service under way.
    served_late = 0
    for index in range(6):
        result = checked("overloaded", 99, index, policy)
        row = named_replication_row(result, index)
        ends = [item["service_end_hours"] for item in result["customers"] if item["status"] == DEPARTED]
        waiting = len(result["at_close"]["waiting_customer_ids"])
        if policy == DRAIN:
            assert row["customers"]["unserved"] == 0 and row["closing"]["drain_crew_size"] == 2
            assert row["customers"]["served_after_closing"] == waiting
            assert row["closing"]["run_after_closing_hours"] == max(0.0, max(ends, default=CLOSE) - CLOSE)
            served_late += waiting > 0
        else:
            assert row["customers"]["unserved"] == row["customers"]["unserved_hard_cutoff"] == waiting
            assert row["customers"]["served_after_closing"] == 0
            for who in ("A", "B"):
                serving = _in_service_at(result, who, CLOSE)
                assert shift_row(result["employee_timeline"], who)["release"] == (
                    serving["service_end_hours"] if serving else CLOSE)
    assert policy == HARD_CUTOFF or served_late >= 1


def test_no_eligible_drain_employee():
    # A leaves at 11:00 (or at the end of the service under way) and nobody else works, so under DRAIN the crew
    # is empty and everyone still waiting at closing is unserved, reason no_eligible_employee (X6).
    unserved = 0
    for index in range(8):
        result = checked("no_eligible_drain_employee", 4242, index, DRAIN)
        assert result["at_close"]["drain_crew"] == []
        missed = [row for row in result["customers"] if row["status"] == UNSERVED_AT_CLOSE]
        assert [row["customer_id"] for row in missed] == result["at_close"]["waiting_customer_ids"]
        assert all(row["unserved_reason"] == NO_ELIGIBLE_EMPLOYEE for row in missed)
        unserved += len(missed)
    # λ 10 for the hour after A leaves: at least one waiting customer in eight replications in practice.
    assert unserved >= 1


@pytest.mark.parametrize("policy", [DRAIN, HARD_CUTOFF])
def test_break_scheduled_to_end_at_closing(policy):
    # A's 30-minute break is scheduled 3.5-4.0. Taken on time, it ends exactly at closing and is truncated there
    # (rule 2). Delayed by a service, it starts later and is truncated at closing, or it is still pending at
    # closing and cancelled (rule 1 when the service ends exactly at closing). It is never completed.
    on_time = 0
    for index in range(20):
        result = checked("break_ending_at_closing", 7, index, policy)
        (item,) = break_rows(result["employee_timeline"], "A")
        serving = _in_service_at(result, "A", 3.5)
        if serving is None:
            assert (item["actual_start"], item["actual_end"], item["outcome"]) == (3.5, CLOSE, TRUNCATED_BY_CLOSING)
            on_time += 1
        elif serving["service_end_hours"] < CLOSE:
            assert (item["actual_start"], item["outcome"]) == (serving["service_end_hours"], TRUNCATED_BY_CLOSING)
        else:
            assert (item["outcome"], item["unfulfilled_cause"]) == (UNFULFILLED, "cancelled_at_closing")
    # λ 1 against μ 4: A is idle at 3.5 with probability about 0.75, so some replication takes it on time.
    assert on_time >= 1


def test_staffing_gaps_stay_inside_the_operating_horizon():
    # A starts before opening and B works past closing: those windows report series only, never a gap or a
    # requirement; the horizon and the segment carry both gaps.
    run = replicate("outside_the_horizon", replications=4, seed=21, policy=DRAIN)
    for row in run["replications"]:
        staffing = row["staffing"]
        assert set(staffing) == {"before_opening", "segments", "horizon", "after_closing"}
        for key in ("before_opening", "after_closing"):
            assert set(staffing[key]) == {"duration_hours", "scheduled_active_hours", "accepting_capacity_hours",
                                          "busy_employee_hours", "register_occupancy_hours",
                                          "waiting_for_register_hours"}
        assert staffing["before_opening"]["scheduled_active_hours"] == 0.5
        assert staffing["after_closing"]["scheduled_active_hours"] == 1.0  # B's 12:00-13:00, scheduled not worked
        assert staffing["horizon"]["required_staffing_hours"] == 4.0
    metrics = run["summary"]["metrics"]["staffing"]
    assert "requirement_gap_shortfall_hours" not in metrics["after_closing"]
    assert metrics["horizon"]["requirement_gap_shortfall_hours"]["n"] == 4


# ── Aggregation ─────────────────────────────────────────────────────────────


def test_aggregation_counts_every_replication_and_matches_independent_statistics():
    run = replicate("stable", replications=12, seed=5, policy=DRAIN)
    rows, summary = run["replications"], run["summary"]
    assert summary["replications"] == 12
    for key in ("arrivals", "served", "unserved", "served_after_closing"):
        assert summary["customers"]["totals"][key] == sum(row["customers"][key] for row in rows)
    values = [row["waiting"]["customer_hours_total"] for row in rows]
    stats = summary["metrics"]["waiting"]["customer_hours_total"]
    mean, sd = statistics.fmean(values), statistics.stdev(values)
    low, high = student_t.interval(0.95, len(values) - 1, loc=mean, scale=sd / math.sqrt(len(values)))
    assert (stats["n"], stats["n_undefined"]) == (12, 0)
    assert stats["mean"] == pytest.approx(mean, rel=1e-12) and stats["sd"] == pytest.approx(sd, rel=1e-12)
    assert (stats["ci_lower"], stats["ci_upper"]) == (pytest.approx(low, rel=1e-9), pytest.approx(high, rel=1e-9))
    served = sum(row["customers"]["served"] for row in rows)
    weighted = summary["waiting_time"]["customer_weighted_mean_hours"]
    assert weighted["denominator_served_customers"] == served
    assert weighted["numerator_wait_hours"] == math.fsum(row["waiting"]["wait_sum_hours"] for row in rows)
    for key, value in summary["outcome_counts"].items():
        if key != "definition":
            assert value["denominator_replications"] == 12 and 0 <= value["replications"] <= 12
    assert summary["verdict"] is None and "0.75" in summary["verdict_reason"]
    assert set(summary["metrics"]["staffing"]["segments"]) == {"S"}
    assert summary["metrics"]["employees"]["breaks_unfulfilled_by_cause"].keys() == {
        "released", "shift_not_activated", "cancelled_at_closing"}


def test_one_replication_has_no_dispersion():
    summary = replicate("stable", replications=1, seed=8, policy=HARD_CUTOFF)["summary"]
    stats = summary["metrics"]["waiting"]["customer_hours_total"]
    assert stats["n"] == 1 and stats["sd"] is None and stats["ci_lower"] is None


# ── Inputs, provenance, and isolation ───────────────────────────────────────


@pytest.mark.parametrize(("options", "message"), [
    ({"replications": 0}, "replications"),
    ({"replications": MC_MAX_TRIALS + 1}, "replications"),
    ({"replications": 2.0}, "replications"),
    ({"replications": True}, "replications"),
    ({"seed": -1}, "seed"),
    ({"seed": 1.5}, "seed"),
    ({"seed": True}, "seed"),
])
def test_invalid_run_settings_are_rejected(options, message):
    settings = {"replications": 2, "seed": 1, **options}
    demand, roster, workforce, required = SCENARIOS["stable"]
    with pytest.raises(SharedSegmentError, match=message):
        run_named_replications(HORIZON, demand, staff(roster), workforce, roster, closing_policy=DRAIN,
                               employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=required, **settings)


@pytest.mark.parametrize("value", [None, [], ["S"]])
def test_required_staffing_is_mandatory(value):
    demand, roster, workforce, _ = SCENARIOS["stable"]
    with pytest.raises(SharedSegmentError, match="X7"):
        simulate_named_replication(HORIZON, demand, staff(roster), workforce, roster,
                                   seed_sequence=replication_seed_sequence(1, 0), closing_policy=DRAIN,
                                   employee_policy=APPROVED_EMPLOYEE_POLICY, required_staffing=value)


def test_policies_are_validated_by_the_named_engine():
    demand, roster, workforce, required = SCENARIOS["stable"]
    with pytest.raises(SharedSegmentError, match="closing_policy"):
        run_named_replications(HORIZON, demand, staff(roster), workforce, roster, replications=2, seed=1,
                               closing_policy="drain", employee_policy=APPROVED_EMPLOYEE_POLICY,
                               required_staffing=required)
    with pytest.raises(SharedSegmentError, match="employee_policy.employee_choice"):
        run_named_replications(HORIZON, demand, staff(roster), workforce, roster, replications=2, seed=1,
                               closing_policy=DRAIN, required_staffing=required,
                               employee_policy=dataclasses.replace(APPROVED_EMPLOYEE_POLICY, employee_choice="x"))


def test_required_arguments_have_no_defaults():
    demand, roster, workforce, required = SCENARIOS["stable"]
    base = {"replications": 2, "seed": 1, "closing_policy": DRAIN, "employee_policy": APPROVED_EMPLOYEE_POLICY,
            "required_staffing": required}
    for missing in base:
        with pytest.raises(TypeError):
            run_named_replications(HORIZON, demand, staff(roster), workforce, roster,
                                   **{key: value for key, value in base.items() if key != missing})


def test_provenance_records_seed_runtime_and_limits():
    run = replicate("stable", replications=3, seed=41, policy=DRAIN)
    provenance = run["provenance"]
    assert provenance["runtime"]["numpy_version"] == np.__version__
    assert provenance["runtime"]["bit_generator"] == type(np.random.default_rng(1).bit_generator).__name__
    assert (provenance["seed"], provenance["root_entropy"]) == (41, 41)
    assert "spawn_key=(i,)" in provenance["seed_scheme"]
    assert "UNKNOWN" in provenance["reproducibility"] and "2.2.6" in provenance["reproducibility"]
    assert provenance["named_engine_version"] == "novaq-shared-named-des-v2"
    assert provenance["state_machine_version"] == "novaq-shared-employee-states-v3"
    assert provenance["arrival_engine_version"] == shared_continuous_des.ENGINE_VERSION
    assert provenance["employee_policy"] == dataclasses.asdict(APPROVED_EMPLOYEE_POLICY)
    assert [row["spawn_key"] for row in run["replications"]] == [[0], [1], [2]]
    full = regenerate("stable", 41, 2, DRAIN)["replication"]
    assert full["runtime"] == provenance["runtime"] and full["pool_size"] == 4
    assert not any("cost" in key for key in run["summary"]) and "5B-5" in provenance["monetary_cost"]


def test_module_uses_only_the_public_arrival_interface():
    tree = ast.parse(Path(shared_named_replications.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    modules: set[str] = set()
    attributes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.Attribute):
            attributes.add(node.attr)
    assert "draw_arrivals" in imported and not any(name.startswith("_") for name in imported)
    assert "_draw_arrivals" not in attributes and "random" not in modules
    # numpy is used for seed sequences and the runtime probe only; no variate is drawn here.
    assert not attributes & {"exponential", "integers", "uniform", "normal", "choice", "shuffle", "permutation"}
    assert not any("separate" in name or "queue_lifecycle" in name or "break_optimization" in name for name in modules)


def test_module_is_registered_with_the_isolation_test():
    from tests.test_shared_segments import SHARED_QUEUE_ENHANCEMENT_MODULES

    assert "shared_named_replications.py" in SHARED_QUEUE_ENHANCEMENT_MODULES
