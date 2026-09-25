"""D10: fixed-horizon accounting of the per-period routing DES.

Spec: docs/superpowers/specs/2026-09-25-d10-per-period-routing-des-accounting.md.

Utilization is calendar time: busy time up to the horizon H (service in progress
at H counts up to H, never beyond) over H. Wq is the mean complete queue wait of
the customers whose service started, measured from admission. Customers still
waiting at H are censored: counted with their partial waits, never given a
completed wait, and they leave the complete waiting cost undefined.

Independent references: a single-lane FIFO recursion over arrival times
regenerated from the run seed (the arrival stream is the first of the three
streams ``random.Random(seed)`` derives), and, for routed multi-lane runs, the
run's own event trace.
"""
from __future__ import annotations

import math
import random
import statistics

import pytest

from backend.queueing_engine.config import PRE_BREAK_CUTOFF_MINUTES
from backend.queueing_engine.services import separate_optimization as sep

SERVER, WAIT = 90.0, 100.0


# --- independent references ------------------------------------------------------------

def _arrival_gaps(seed):
    return random.Random(random.Random(seed).getrandbits(64))


def _admissions(seed, lam, horizon):
    """Admission times of one uninterrupted Poisson stream, strictly before the horizon."""
    gaps, out, t = _arrival_gaps(seed), [], 0.0
    while True:
        gap = gaps.expovariate(lam)
        if t + gap >= horizon:
            return out
        t = t + gap
        out.append(t)


def _fifo(admissions, service, horizon, *, free=0.0):
    """One lane, constant service: (admission, start, end) per customer; start >= H means
    the customer was still waiting at the horizon."""
    rows = []
    for a in admissions:
        s = max(a, free)
        free = s + service
        rows.append((a, s, free))
    return rows


def _measure(rows, horizon):
    """Everything the D10 spec defines for one lane, from (admission, start, end) rows."""
    started = [(a, s, e) for a, s, e in rows if s < horizon]
    waiting = [a for a, s, _ in rows if s >= horizon]
    waits = [s - a for a, s, _ in started]
    busy = math.fsum(min(e, horizon) - s for _, s, e in started)
    return {
        "arrivals": len(rows), "started": len(started),
        "served": sum(1 for _, _, e in started if e < horizon),
        "in_service": sum(1 for _, _, e in started if e >= horizon),
        "waiting": len(waiting), "busy": busy, "rho": min(1.0, busy / horizon),
        "Wq": statistics.fmean(waits) if waits else None, "exposure": math.fsum(waits),
        "completed_busy": math.fsum(e - s for _, s, e in started if e < horizon),
        "censored_hours": math.fsum(horizon - a for a in waiting),
    }


def _one_lane_reference(seed, lam, service, horizon):
    return _measure(_fifo(_admissions(seed, lam, horizon), service, horizon), horizon)


def _trace_reference(result, horizon):
    """Per-lane measures rebuilt from a run's event trace (no breaks: routing = admission)."""
    trace = result["trace_events"]
    arrived = {e["customer_id"]: e for e in trace if e["type"] == "arrival"}
    started = {e["customer_id"]: e["t"] for e in trace if e["type"] == "service_start"}
    ended = {e["customer_id"]: e["t"] for e in trace if e["type"] == "service_end"}
    lanes = {}
    for queue_id in {e["queue_id"] for e in arrived.values()}:
        rows = [(e["t"], started.get(cid, math.inf), ended.get(cid, math.inf))
                for cid, e in arrived.items() if e["queue_id"] == queue_id]
        lanes[queue_id] = _measure(rows, horizon)
    return lanes


# --- fixtures ----------------------------------------------------------------------------

def _lane(queue_id, lam, samples):
    return {"queue_id": queue_id, "lambda": lam, "mu": 1 / statistics.fmean(samples), "c": 1,
            "service_samples_hours": list(samples)}


def _candidate(active, available=None, **extra):
    available = list(available or active)
    return {"time": "08:00", "available_queue_ids": available, "active_queue_ids": list(active),
            "inactive_queue_ids": [q for q in available if q not in active], **extra}


def _single(seed, lam, service, horizon, target=0.90, **extra):
    return sep.evaluate_candidate_with_des(
        _candidate(["a"], **extra), {"a": _lane("a", lam, [service])}, duration_hours=horizon,
        seed=seed, target=target, server_cost=SERVER, waiting_cost=WAIT)


def _assert_lane_matches(lane, ref, *, abs_tol=1e-9):
    for key in ("arrivals", "served", "in_service", "waiting"):
        assert lane[key] == ref[key], key
    assert lane["rho"] == pytest.approx(ref["rho"], abs=abs_tol)
    if ref["Wq"] is None:
        assert lane["Wq"] is None
    else:
        assert lane["Wq"] == pytest.approx(ref["Wq"], abs=abs_tol)
    assert lane["started"] == ref["started"]
    assert lane["censored_customers"] == ref["waiting"]
    assert lane["censored_waiting_hours"] == pytest.approx(ref["censored_hours"], abs=abs_tol)
    assert lane["wait_population"] == sep.WAIT_POPULATION_STARTED


# --- 1-7: one run, one lane, constant service ----------------------------------------------

def test_1_services_completed_within_the_horizon():
    ref = _one_lane_reference(0, 2.0, 0.1, 4.0)
    assert ref["arrivals"] == ref["served"] > 0 and ref["in_service"] == ref["waiting"] == 0
    result = _single(0, 2.0, 0.1, 4.0)
    (lane,) = result["evaluations"]
    _assert_lane_matches(lane, ref)
    assert ref["busy"] == pytest.approx(0.1 * ref["served"])
    assert result["censored_customers"] == 0
    # Complete exposure, D1 formula: served / H * Wq * rate.
    assert result["waiting_cost"] == pytest.approx(ref["served"] / 4.0 * ref["Wq"] * WAIT)
    assert result["total_cost"] == pytest.approx(SERVER + result["waiting_cost"])


def test_2_and_7_service_continuing_beyond_the_horizon_is_credited_up_to_it():
    ref = _one_lane_reference(5, 2.0, 0.1, 4.0)
    assert ref["in_service"] == 1 and ref["waiting"] == 0
    assert ref["busy"] > ref["completed_busy"]  # the in-progress service adds H - s
    result = _single(5, 2.0, 0.1, 4.0)
    (lane,) = result["evaluations"]
    _assert_lane_matches(lane, ref)
    assert lane["started"] == lane["served"] + 1
    # The customer in service has a known, complete wait: it is in Wq and in the cost.
    assert result["censored_customers"] == 0
    assert result["waiting_cost"] == pytest.approx(ref["exposure"] / 4.0 * WAIT)
    assert result["started_cohort_waiting_cost"] == pytest.approx(result["waiting_cost"])


def test_3_server_continuously_busy_until_the_horizon():
    """The controlled case: 1 lane, 1 h, 30/h, 0.3 h services, target 0.90."""
    admissions = _admissions(0, 30.0, 1.0)
    rows = _fifo(admissions, 0.3, 1.0)
    ref = _measure(rows, 1.0)
    started = [r for r in rows if r[1] < 1.0]
    assert all(nxt[1] == prev[2] for prev, nxt in zip(started, started[1:]))  # never idle
    assert ref["busy"] == pytest.approx(1.0 - admissions[0])
    result = _single(0, 30.0, 0.3, 1.0, target=0.90)
    (lane,) = result["evaluations"]
    _assert_lane_matches(lane, ref)
    assert lane["rho"] == pytest.approx(0.996509, abs=1e-6)
    assert result["status"] == "INFEASIBLE"
    # The completed-services-only measure (the pre-D10 numerator) reads exactly 0.90 here
    # and would have passed the target.
    assert ref["completed_busy"] / 1.0 == pytest.approx(0.90)


def test_4_no_completed_service_but_positive_busy_time():
    admissions = _admissions(5, 6.0, 1.0)
    ref = _one_lane_reference(5, 6.0, 10.0, 1.0)
    assert ref["served"] == 0 and ref["started"] == 1 and ref["busy"] > 0
    result = _single(5, 6.0, 10.0, 1.0)
    (lane,) = result["evaluations"]
    _assert_lane_matches(lane, ref)
    assert lane["rho"] == pytest.approx(1.0 - admissions[0])
    assert lane["Wq"] == 0.0  # the first customer found the lane empty


def test_5_zero_arrivals():
    ref = _one_lane_reference(0, 0.01, 0.1, 1.0)
    assert ref["arrivals"] == 0
    result = _single(0, 0.01, 0.1, 1.0)
    (lane,) = result["evaluations"]
    _assert_lane_matches(lane, ref)
    assert lane["rho"] == 0.0 and lane["Wq"] is None
    assert result["status"] == "FEASIBLE"
    assert result["censored_customers"] == 0 and result["censored_waiting_hours"] == 0.0
    # Nobody waited: a known zero, not an unknown. No started cohort to estimate from.
    assert result["waiting_cost"] == 0.0
    assert result["total_cost"] == pytest.approx(SERVER)
    assert result["started_cohort_waiting_cost"] is None


def test_6_and_11_customers_waiting_at_the_horizon_are_censored_and_cost_is_undefined():
    ref = _one_lane_reference(0, 30.0, 0.3, 1.0)
    assert ref["waiting"] == 35
    result = _single(0, 30.0, 0.3, 1.0)
    (lane,) = result["evaluations"]
    _assert_lane_matches(lane, ref)
    assert result["censored_customers"] == 35 and result["unrouted_at_horizon"] == 0
    assert result["censored_waiting_hours"] == pytest.approx(ref["censored_hours"])
    # No service start is invented: only the 4 customers who started have one.
    starts = [e for e in result["trace_events"] if e["type"] == "service_start"]
    assert len(starts) == ref["started"] == 4
    # Wq covers the started cohort only; the partial waits are not in it.
    assert lane["Wq"] == pytest.approx(ref["exposure"] / 4)
    assert result["server_cost"] == pytest.approx(SERVER)
    assert result["waiting_cost"] is None and result["total_cost"] is None
    assert "still waiting at the horizon on a (35)" in result["cost_undefined_reason"]
    assert result["started_cohort_waiting_cost"] == pytest.approx(ref["exposure"] / 1.0 * WAIT)


# --- waiting measured from admission; unrouted customers at the horizon ---------------------

def _break_reference(seed, lam, service, horizon, start, duration):
    """One lane with one break: arrivals after the cutoff wait unrouted until it ends."""
    cutoff = max(0.0, start - PRE_BREAK_CUTOFF_MINUTES / 60.0)
    gaps, rows, t, free = _arrival_gaps(seed), [], 0.0, 0.0
    break_end = None
    unrouted = None
    while True:
        gap = gaps.expovariate(lam)
        if t + gap >= horizon:
            break
        a = t + gap
        if a < cutoff or (break_end is not None and a >= break_end):
            routed = a
        else:
            if break_end is None:
                drained = max(cutoff, free)
                break_end = drained + duration
            if break_end >= horizon:
                unrouted = a  # arrivals pause while no lane accepts them
                break
            routed = break_end
        s = max(routed, free)
        free = s + service
        rows.append((a, s, free, routed))
        t = routed
    return rows, unrouted


def test_waiting_is_measured_from_admission_including_the_wait_for_a_lane():
    rows, unrouted = _break_reference(3, 12.0, 0.05, 3.0, start=0.5, duration=0.5)
    assert unrouted is None
    delayed = [r for r in rows if r[3] > r[0]]
    assert delayed  # someone arrived while no lane accepted arrivals
    ref = _measure([r[:3] for r in rows], 3.0)
    result = _single(3, 12.0, 0.05, 3.0,
                     breaks=[{"queue_id": "a", "start_hours": 0.5, "duration_hours": 0.5}])
    (lane,) = result["evaluations"]
    _assert_lane_matches(lane, ref)
    # The routing time alone would understate the delayed customer's wait.
    routed_only = statistics.fmean(s - routed for _, s, _, routed in rows if s < 3.0)
    assert lane["Wq"] > routed_only


def test_a_customer_not_yet_routed_at_the_horizon_is_censored():
    rows, unrouted = _break_reference(3, 12.0, 0.05, 1.0, start=0.5, duration=5.0)
    assert unrouted is not None
    ref = _measure([r[:3] for r in rows], 1.0)
    result = _single(3, 12.0, 0.05, 1.0,
                     breaks=[{"queue_id": "a", "start_hours": 0.5, "duration_hours": 5.0}])
    (lane,) = result["evaluations"]
    _assert_lane_matches(lane, ref)
    assert result["admitted"] == len(rows) + 1
    assert result["unrouted_at_horizon"] == 1
    assert result["censored_customers"] == ref["waiting"] + 1
    assert result["censored_waiting_hours"] == pytest.approx(ref["censored_hours"] + 1.0 - unrouted)
    assert result["customer_conservation"] is True  # routed customers are all accounted for
    assert result["waiting_cost"] is None and result["total_cost"] is None
    assert "not yet routed (1)" in result["cost_undefined_reason"]


# --- routed lanes: the run's own trace as reference ----------------------------------------

@pytest.mark.parametrize("seed", [42, 43, 44])
def test_routed_lanes_match_their_own_event_trace(seed):
    samples = [0.2, 0.3, 0.4]
    by_id = {q: _lane(q, 2.5, samples) for q in ("a", "b", "c")}
    result = sep.evaluate_candidate_with_des(_candidate(["a", "b", "c"]), by_id, duration_hours=8.0,
                                             seed=seed, target=0.90, server_cost=SERVER,
                                             waiting_cost=WAIT, max_events=100000)
    assert result["trace_truncated"] is False
    refs = _trace_reference(result, 8.0)
    for lane in result["evaluations"]:
        ref = refs[lane["queue_id"]]
        # Trace times are rounded to 1e-6 h.
        _assert_lane_matches(lane, ref, abs_tol=1e-6 * max(1, ref["arrivals"]))
        assert lane["arrivals"] == lane["served"] + lane["in_service"] + lane["waiting"]
    assert result["censored_customers"] == sum(ref["waiting"] for ref in refs.values())


# --- 8-10: replications, aggregate feasibility, ranking eligibility -------------------------

CONTROLLED = {"lam": 30.0, "service": 0.3, "horizon": 1.0, "target": 0.90}


def test_8_and_9_replications_aggregate_the_corrected_utilization():
    seeds = [0, 1, 2, 3, 4]
    refs = [_one_lane_reference(s, 30.0, 0.3, 1.0) for s in seeds]
    aggregate = sep.evaluate_candidate_with_des_replications(
        _candidate(["a"]), {"a": _lane("a", 30.0, [0.3])},
        {"replications": 5, "base_seed": 0, "duration_hours": 1.0, "target": 0.90,
         "server_cost": SERVER, "waiting_cost": WAIT})
    assert aggregate["replication_seeds"] == seeds
    (lane,) = aggregate["per_lane"]
    assert lane["utilization"]["mean"] == pytest.approx(statistics.fmean(r["rho"] for r in refs))
    assert lane["Wq"]["mean"] == pytest.approx(statistics.fmean(r["Wq"] for r in refs))
    assert aggregate["censored_customers"]["mean"] == pytest.approx(
        statistics.fmean(r["waiting"] for r in refs))
    assert aggregate["censored_waiting_hours"]["mean"] == pytest.approx(
        statistics.fmean(r["censored_hours"] for r in refs))
    assert aggregate["replications_with_censoring"] == 5
    assert aggregate["started_cohort_waiting_cost"]["mean"] == pytest.approx(
        statistics.fmean(r["exposure"] / 1.0 * WAIT for r in refs))
    assert aggregate["wait_population"] == sep.WAIT_POPULATION_STARTED
    # 9: the unchanged rule (max mean active-lane utilization <= target) on corrected values.
    classified = sep.apply_des_aggregate_feasibility(aggregate)
    assert classified["status"] == "INFEASIBLE"
    assert classified["candidate_utilization"] == pytest.approx(statistics.fmean(r["rho"] for r in refs))
    # Completed services alone read at most 0.90 in every replication, which would pass.
    assert all(r["completed_busy"] <= 0.90 + 1e-9 for r in refs)


def _per_date_setup(start, end):
    return {
        "queue_structure": "separate_queues", "fixed_server_count": 1,
        "staffing_varies_by_period": False, "capacity_mode": "unlimited",
        "total_system_capacity": None, "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None, "separate_queue_closure_policy": "drain_existing",
        "queue_ids": ["a"], "event_period_basis": "per_date", "breaks": [],
        "segments": [{"id": "p", "start_time": start, "end_time": end, "active_queue_ids": None}],
    }


def _per_date_rows(lam, service):
    return [{"time": "p", "segment_id": "p", "queue_id": "a", "lambda": lam, "mu": 1 / service,
             "c": 1, "variance": 0.0, "queue_structure": "separate_queues",
             "model_id": "parallel_mg1", "service_time_source": "empirical",
             "service_samples_hours": [service]}]


def _per_date_schedule(start, end, lam, service, *, target, horizon, base_seed):
    return sep.optimize_separate_schedule(
        _per_date_setup(start, end), _per_date_rows(lam, service), target=target,
        server_cost=SERVER, waiting_cost=WAIT, full_coverage=True,
        des_settings={"replications": 5, "base_seed": base_seed, "duration_hours": horizon})


def test_10_a_candidate_over_target_on_corrected_utilization_is_not_ranked():
    schedule = _per_date_schedule("08:00:00", "09:00:00", 30.0, 0.3, target=0.90, horizon=1.0,
                                  base_seed=0)
    (period,) = schedule["periods"]
    (candidate,) = period["candidates"]
    refs = [_one_lane_reference(s, 30.0, 0.3, 1.0) for s in range(5)]
    assert candidate["candidate_utilization"] == pytest.approx(statistics.fmean(r["rho"] for r in refs))
    assert candidate["status"] == "INFEASIBLE"
    assert period["overall"] == "INFEASIBLE" and period["optimum"] is None


def test_10_a_feasible_candidate_with_censored_replications_is_not_ranked():
    refs = [_one_lane_reference(s, 1.0, 0.5, 8.0) for s in range(42, 47)]
    assert statistics.fmean(r["rho"] for r in refs) <= 0.90
    assert [r["waiting"] > 0 for r in refs] == [True, False, False, False, False]
    schedule = _per_date_schedule("08:00:00", "16:00:00", 1.0, 0.5, target=0.90, horizon=8.0,
                                  base_seed=42)
    (period,) = schedule["periods"]
    (candidate,) = period["candidates"]
    assert candidate["status"] == "FEASIBLE"
    assert candidate["replications_with_censoring"] == 1
    assert candidate["mean_total_cost"] is None
    assert [item["seed"] for item in candidate["cost_undefined_replications"]] == [42]
    assert period["overall"] == "UNSUPPORTED" and period["optimum"] is None
    assert "no defined replicated cost" in period["reason"]
    assert ("still waiting at the DES horizon for lane count(s) 1 (in 1 of 5 replications)"
            in period["reason"])


# --- stored selected-plan DES: who Wq covers, from recorded provenance only ------------------

def _stored(execution, *counts):
    periods = [{"time": f"p{i}", **({} if count == "missing" else {"censored_customers": count})}
               for i, count in enumerate(counts)]
    return {"execution": execution, "periods": periods}


def test_stored_des_disclosure_distinguishes_zero_positive_unknown_and_not_applicable():
    per_period = sep.SELECTED_DES_PER_PERIOD_EXECUTION
    recorded = sep.selected_des_wait_disclosure(_stored(per_period, 0, 5))
    assert recorded["basis"] == "per_period"
    assert recorded["wait_definition"] == sep.WAIT_DEFINITION_STARTED
    assert recorded["periods"] == {
        "p0": {"censoring_status": "recorded", "censored_customers": 0},   # verified zero
        "p1": {"censoring_status": "recorded", "censored_customers": 5}}   # verified positive
    older = sep.selected_des_wait_disclosure(_stored(per_period, "missing", None))
    assert older["basis"] == "per_period"
    assert older["wait_definition"] is None  # its Wq predates the started-cohort definition
    assert {p["censoring_status"] for p in older["periods"].values()} == {"unknown"}
    assert all(p["censored_customers"] is None for p in older["periods"].values())
    day = sep.selected_des_wait_disclosure(_stored(sep.SELECTED_DES_CONTINUOUS_DAY_EXECUTION, "missing"))
    assert day["basis"] == "continuous_day"
    assert day["wait_definition"] == sep.WAIT_DEFINITION_CONTINUOUS_DAY
    assert day["periods"]["p0"] == {"censoring_status": "not_applicable", "censored_customers": None}


def test_stored_des_basis_is_never_inferred_from_metric_values():
    # No recorded execution: the basis is unknown even when counts or waits look complete.
    for execution in (None, "something else"):
        unknown = sep.selected_des_wait_disclosure(_stored(execution, 0, 3))
        assert unknown["basis"] == "unknown" and unknown["wait_definition"] is None
        assert {p["censoring_status"] for p in unknown["periods"].values()} == {"unknown"}
    # A malformed count is unknown, never zero.
    bad = sep.selected_des_wait_disclosure(_stored(sep.SELECTED_DES_PER_PERIOD_EXECUTION, True, -1, 2.5))
    assert {p["censoring_status"] for p in bad["periods"].values()} == {"unknown"}


# --- 12-13: D1 and D5 preserved on complete observations -------------------------------------

D1_SEEDS = [27, 28, 29, 30, 31]  # uncensored; 27, 28, 29, 31 over a 0.45 target, 30 under


def test_12_d1_every_replication_is_priced_including_over_target_runs():
    refs = [_one_lane_reference(s, 3.0, 0.15, 8.0) for s in D1_SEEDS]
    assert all(r["waiting"] == 0 for r in refs)
    over = [r["rho"] > 0.45 for r in refs]
    assert any(over) and not all(over)
    hand = [SERVER + r["exposure"] / 8.0 * WAIT for r in refs]
    aggregate = sep.evaluate_candidate_with_des_replications(
        _candidate(["a"]), {"a": _lane("a", 3.0, [0.15])},
        {"replications": 5, "base_seed": 27, "duration_hours": 8.0, "target": 0.45,
         "server_cost": SERVER, "waiting_cost": WAIT})
    assert aggregate["replications_over_target"] == sum(over)
    assert aggregate["replications_with_censoring"] == 0
    assert aggregate["cost_undefined_replications"] == []
    assert aggregate["costs"]["total"]["n"] == 5
    assert aggregate["costs"]["total"]["mean"] == pytest.approx(statistics.fmean(hand))
    # Where nobody is in service at H the exposure is exactly the D1 served / H * Wq form.
    for seed, ref in zip(D1_SEEDS, refs):
        if ref["in_service"] == 0:
            single = _single(seed, 3.0, 0.15, 8.0, target=0.45)
            assert single["waiting_cost"] == pytest.approx(ref["served"] / 8.0 * ref["Wq"] * WAIT)


def test_13_d5_period_costs_are_the_hourly_rates_times_the_period_length():
    refs = [_one_lane_reference(s, 3.0, 0.15, 8.0) for s in D1_SEEDS]
    hand = statistics.fmean(SERVER + r["exposure"] / 8.0 * WAIT for r in refs)
    schedule = _per_date_schedule("08:00:00", "08:30:00", 3.0, 0.15, target=0.90, horizon=8.0,
                                  base_seed=27)
    (period,) = schedule["periods"]
    assert period["overall"] == "OPTIMAL"
    assert period["duration_hours"] == pytest.approx(0.5)
    optimum = period["optimum"]
    assert optimum["mean_total_cost"] == pytest.approx(hand)
    assert optimum["period_costs"]["total"]["mean"] == pytest.approx(hand * 0.5)
    assert optimum["period_costs"]["staffing"]["mean"] == pytest.approx(SERVER * 0.5)
