"""D1: replicated Separate-queue costs use every replication (policy A).

A replication whose own utilization exceeds the target is still a measured
run of the candidate, so its cost counts. Leaving it out (the defect) averaged
cost over the quieter replications only. A cost no replication can define is
undefined for the whole aggregate, with its reason, never zero-filled, and a
feasible candidate without a defined cost is never ranked.
"""
from __future__ import annotations

import math
import statistics

import pytest
from scipy.stats import t as student_t

from backend.queueing_engine.config import OT_RATE, REGULAR_RATE
from backend.queueing_engine.services import separate_optimization as sep

SEEDS = [42, 43, 44, 45, 46]


def _rep(rho, *, server_cost, waiting_cost, status=None, reason=None, target=0.70):
    """Canned single-run result for one active lane ``east-07``."""
    over = rho > target
    total = None if server_cost is None or waiting_cost is None else server_cost + waiting_cost
    return {
        "time": "08:00", "status": status or ("INFEASIBLE" if over else "FEASIBLE"),
        "reason": "over target" if over else None,
        "evaluations": [{"queue_id": "east-07", "active": True, "lambda": 6.0,
                         "arrivals": 48, "served": 48, "waiting": 0, "in_service": 0,
                         "Wq": 0.1, "rho": rho}],
        "total_lambda": 6.0, "server_cost": server_cost, "waiting_cost": waiting_cost,
        "total_cost": total, "cost_undefined_reason": reason,
        "customer_conservation": True, "metric_provenance": "simulated",
        "trace_events": [], "trace_truncated": False,
    }


def _runner(results_by_seed):
    def run(candidate, queues_by_id, *, duration_hours, seed, target, server_cost,
            waiting_cost, max_events):
        return results_by_seed[seed]
    return run


def _aggregate(results_by_seed):
    by_id = {"east-07": {"queue_id": "east-07", "lambda": 6.0, "mu": 10.0, "c": 1,
                         "service_samples_hours": [0.05, 0.10]}}
    candidate = {"time": "08:00", "available_queue_ids": ["east-07"],
                 "active_queue_ids": ["east-07"], "inactive_queue_ids": []}
    config = {"replications": 5, "base_seed": 42, "duration_hours": 8.0, "target": 0.70}
    return sep.evaluate_candidate_with_des_replications(
        candidate, by_id, config, run_fn=_runner(results_by_seed))


def _t_interval(values):
    mean = statistics.fmean(values)
    se = statistics.stdev(values) / len(values) ** 0.5
    half = float(student_t.ppf(0.975, len(values) - 1)) * se
    return mean, mean - half, mean + half


def test_all_feasible_replications_are_all_priced():
    waits = [10.0, 20.0, 30.0, 40.0, 50.0]
    outcome = _aggregate({seed: _rep(0.60, server_cost=100.0, waiting_cost=wait)
                          for seed, wait in zip(SEEDS, waits)})
    total = outcome["costs"]["total"]
    assert total["n"] == 5
    assert total["mean"] == pytest.approx(130.0)  # 100 + mean(10..50)
    assert outcome["replications_over_target"] == 0
    assert outcome["replications_over_target_seeds"] == []
    assert outcome["cost_undefined_replications"] == []


def test_one_over_target_replication_is_priced_not_dropped():
    rhos = [0.60, 0.62, 0.78, 0.61, 0.63]           # mean 0.648 <= 0.70
    totals = [180.0, 190.0, 260.0, 185.0, 195.0]     # the over-target run costs most
    results = {seed: _rep(rho, server_cost=100.0, waiting_cost=total - 100.0)
               for seed, rho, total in zip(SEEDS, rhos, totals)}
    outcome = _aggregate(results)
    assert results[44]["status"] == "INFEASIBLE"
    assert sep.apply_des_aggregate_feasibility(outcome)["status"] == "FEASIBLE"
    assert outcome["replications_over_target"] == 1
    assert outcome["replications_over_target_seeds"] == [44]
    total = outcome["costs"]["total"]
    mean, low, high = _t_interval(totals)
    assert total["n"] == 5
    assert mean == pytest.approx(202.0)
    assert total["mean"] == pytest.approx(mean)
    # The defect averaged only the four feasible runs (187.5).
    assert total["mean"] != pytest.approx(statistics.fmean([180.0, 190.0, 185.0, 195.0]))
    assert total["ci_lower"] == pytest.approx(low)
    assert total["ci_upper"] == pytest.approx(high)
    assert outcome["costs"]["waiting"]["n"] == outcome["costs"]["staffing"]["n"] == 5


def test_several_over_target_replications_keep_costs_and_the_aggregate_verdict():
    rhos = [0.72, 0.75, 0.66, 0.74, 0.71]           # mean 0.716 > 0.70
    results = {seed: _rep(rho, server_cost=100.0, waiting_cost=50.0 + index)
               for index, (seed, rho) in enumerate(zip(SEEDS, rhos))}
    outcome = _aggregate(results)
    classified = sep.apply_des_aggregate_feasibility(outcome)
    assert classified["status"] == "INFEASIBLE"
    assert classified["candidate_utilization"] == pytest.approx(statistics.fmean(rhos))
    assert outcome["replications_over_target"] == 4
    assert outcome["replications_over_target_seeds"] == [42, 43, 45, 46]
    assert outcome["costs"]["total"]["n"] == 5
    assert outcome["costs"]["total"]["mean"] == pytest.approx(152.0)


def test_an_undefined_replication_cost_leaves_the_aggregate_cost_undefined():
    results = {seed: _rep(0.60, server_cost=100.0, waiting_cost=20.0) for seed in SEEDS}
    results[45] = _rep(0.60, server_cost=100.0, waiting_cost=None,
                       reason="Waiting cost undefined: no measured wait for east-07.")
    outcome = _aggregate(results)
    assert outcome["costs"]["waiting"] is None
    assert outcome["costs"]["total"] is None
    assert outcome["costs"]["staffing"]["n"] == 5
    assert outcome["cost_undefined_replications"] == [
        {"replication": 3, "seed": 45,
         "reason": "Waiting cost undefined: no measured wait for east-07."}]


def _live_rows():
    samples = [0.05, 0.08, 0.10, 0.12]
    return [{"queue_id": "a", "lambda": 5.0, "mu": 11.0, "c": 1, "service_samples_hours": samples},
            {"queue_id": "b", "lambda": 4.0, "mu": 11.0, "c": 1, "service_samples_hours": samples}]


def _stub_optimize(priced_by_count):
    """Single-run stub: lane count -> total cost (None = undefined), always feasible."""
    def run(candidate, queues_by_id, *, duration_hours, seed, target, server_cost,
            waiting_cost, max_events):
        count = len(candidate["active_queue_ids"])
        cost = priced_by_count[count]
        result = _rep(0.50, server_cost=100.0 * count,
                      waiting_cost=None if cost is None else cost - 100.0 * count,
                      reason=None if cost is not None else "Waiting cost undefined: test.")
        evaluations = [{**result["evaluations"][0], "queue_id": queue_id}
                       for queue_id in candidate["active_queue_ids"]]
        return {**result, "evaluations": evaluations}
    return run


def test_a_feasible_candidate_without_a_defined_cost_blocks_the_optimum():
    result = sep.optimize_separate(
        "08:00", _live_rows(), target=0.70, run_fn=_stub_optimize({1: 150.0, 2: None}),
        des_replications={"replications": 2, "base_seed": 42, "duration_hours": 8.0})
    assert result["overall"] == "UNSUPPORTED"
    assert result["optimum"] is None
    assert "2 have no defined replicated cost" in result["reason"]
    unpriced = next(c for c in result["candidates"] if c["active_lane_count"] == 2)
    assert unpriced["status"] == "FEASIBLE"
    assert unpriced["mean_total_cost"] is None
    assert unpriced["cost_undefined_replications"][0]["reason"] == "Waiting cost undefined: test."


def test_ranking_is_unchanged_when_every_candidate_is_priced():
    result = sep.optimize_separate(
        "08:00", _live_rows(), target=0.70, run_fn=_stub_optimize({1: 210.0, 2: 205.0}),
        des_replications={"replications": 2, "base_seed": 42, "duration_hours": 8.0})
    assert result["overall"] == "OPTIMAL"
    assert result["optimum"]["active_lane_count"] == 2
    assert result["optimum"]["mean_total_cost"] == pytest.approx(205.0)


# --- live evaluators --------------------------------------------------------------

def _hand_cost(evaluations, horizon, server_rate, wait_rate):
    """Independent restatement of the per-replication cost formula."""
    active = [item for item in evaluations if item["active"]]
    staffing = server_rate * len(active)
    waiting = math.fsum(item["served"] / horizon * item["Wq"] * wait_rate
                        for item in active if item["served"])
    return staffing, waiting


def test_live_replications_average_every_run_including_over_target_runs():
    by_id = {row["queue_id"]: row for row in _live_rows()}
    candidate = {"time": "08:00", "available_queue_ids": ["a", "b"],
                 "active_queue_ids": ["a"], "inactive_queue_ids": ["b"]}
    config = {"replications": 5, "base_seed": 42, "duration_hours": 8.0, "target": 0.70}
    singles = [sep.evaluate_candidate_with_des(candidate, by_id, duration_hours=8.0, seed=seed,
                                               target=0.70)
               for seed in SEEDS]
    assert all(single["status"] == "INFEASIBLE" for single in singles)  # 9/h on one lane
    hand = [sum(_hand_cost(single["evaluations"], 8.0, sep.DEFAULT_SERVER_COST_HR,
                           sep.DEFAULT_WAIT_COST_HR)) for single in singles]
    assert [single["total_cost"] for single in singles] == pytest.approx(hand)
    outcome = sep.evaluate_candidate_with_des_replications(candidate, by_id, config)
    assert outcome["replications_over_target"] == 5
    assert outcome["costs"]["total"]["n"] == 5
    assert outcome["costs"]["total"]["mean"] == pytest.approx(statistics.fmean(hand))


def test_arrivals_that_are_never_served_leave_waiting_cost_undefined_not_zero():
    by_id = {"a": {"queue_id": "a", "lambda": 6.0, "mu": 0.1, "c": 1,
                   "service_samples_hours": [10.0]}}
    candidate = {"time": "08:00", "available_queue_ids": ["a"],
                 "active_queue_ids": ["a"], "inactive_queue_ids": []}
    result = sep.evaluate_candidate_with_des(candidate, by_id, duration_hours=1.0, seed=5)
    (lane,) = result["evaluations"]
    assert lane["arrivals"] > 0 and lane["served"] == 0 and lane["Wq"] is None
    assert result["server_cost"] == pytest.approx(sep.DEFAULT_SERVER_COST_HR)
    assert result["waiting_cost"] is None
    assert result["total_cost"] is None
    assert "no measured wait for a" in result["cost_undefined_reason"]


def test_a_lane_without_arrivals_waited_zero_customer_hours():
    costs = sep._replication_costs(
        [{"queue_id": "a", "active": True, "arrivals": 0, "served": 0, "Wq": None},
         {"queue_id": "b", "active": True, "arrivals": 4, "served": 4, "Wq": 0.25},
         {"queue_id": "c", "active": False, "arrivals": 0, "served": 0, "Wq": None}],
        {"a": {}, "b": {}}, horizon=2.0, server_cost=90.0, waiting_cost=100.0)
    assert costs == {"server_cost": 180.0, "waiting_cost": pytest.approx(4 / 2.0 * 0.25 * 100.0),
                     "total_cost": pytest.approx(230.0), "cost_undefined_reason": None}


def _day_setup_and_records():
    """Representative day, one hour, two lanes near 0.7 utilization."""
    import pandas as pd

    from backend.api.analysis_schemas import QueueSetup
    from backend.data.analysis_ingestion import normalize_analysis_input

    setup = {"queue_structure": "separate_queues", "fixed_server_count": 2,
             "staffing_varies_by_period": False, "capacity_mode": "unlimited",
             "total_system_capacity": None, "abandonment_mode": "not_modeled",
             "patience_rate_per_hour": None, "separate_queue_closure_policy": "drain_existing",
             "queue_ids": ["a", "b"], "event_period_basis": "representative_day", "breaks": [],
             "segments": [{"id": "08:00-09:00", "start_time": "08:00:00", "end_time": "09:00:00",
                           "active_queue_ids": None}]}
    rows = []
    for day in (1, 2):
        for lane in ("a", "b"):
            for index in range(7):
                minute = 2 + index * 8
                rows.append({"arrival_time": f"2026-09-0{day}T08:{minute:02d}:00Z",
                             "service_start": f"2026-09-0{day}T08:{minute:02d}:30Z",
                             "service_end": f"2026-09-0{day}T08:{minute + 6:02d}:30Z",
                             "queue_id": lane})
    parsed = QueueSetup.model_validate(setup)
    records, _ = normalize_analysis_input(pd.DataFrame(rows), parsed)
    return parsed.model_dump(mode="json"), records


def test_both_runners_price_lane_rows_identically():
    """Per-date runs pass validated rows; the continuous day passes
    ``_validate_queue_row(row) or {}``. Rate overrides and blended labor hours
    must price the same way through either."""
    rows = {"a": {"queue_id": "a", "lambda": 3.0, "mu": 9.0, "c": 1, "server_cost": 120.0,
                  "service_samples_hours": [0.1]},
            "b": {"queue_id": "b", "lambda": 2.0, "mu": 9.0, "c": 1, "regular_hours": 6.0,
                  "ot_hours": 2.0, "total_hours": 8.0, "service_samples_hours": [0.1]}}
    evaluations = [{"queue_id": "a", "active": True, "arrivals": 5, "served": 5, "Wq": 0.2},
                   {"queue_id": "b", "active": True, "arrivals": 3, "served": 3, "Wq": 0.1}]
    per_date = sep._replication_costs(
        evaluations, {qid: sep._validate_queue_row(row) for qid, row in rows.items()},
        horizon=1.0, server_cost=90.0, waiting_cost=100.0)
    day = sep._replication_costs(
        evaluations, {qid: sep._validate_queue_row(row) or {} for qid, row in rows.items()},
        horizon=1.0, server_cost=90.0, waiting_cost=100.0)
    blended = (6.0 * REGULAR_RATE + 2.0 * OT_RATE) / 8.0
    assert per_date == day
    assert per_date["server_cost"] == pytest.approx(120.0 + blended)
    assert per_date["waiting_cost"] == pytest.approx(5 * 0.2 * 100.0 + 3 * 0.1 * 100.0)


def test_continuous_day_replication_costs_match_the_day_simulation_by_hand():
    setup, records = _day_setup_and_records()
    schedule = sep.optimize_separate_schedule(
        setup, records, target=0.70, full_coverage=True,
        des_settings={"replications": 5, "base_seed": 42})
    (period,) = schedule["periods"]
    (candidate,) = period["candidates"]
    window = {"time": "08:00-09:00", "start_hours": 0.0, "end_hours": 1.0,
              "active_queue_ids": ["a", "b"],
              "queues_by_id": {str(r["queue_id"]): r for r in records}}
    hand = []
    for seed in SEEDS:
        day = sep.run_routing_day_des([window], tie_order=["a", "b"], seed=seed, max_events=10000)
        (per,) = day["periods"]
        staffing = 2 * sep.DEFAULT_SERVER_COST_HR
        waiting = math.fsum(lane["served"] / per["duration_hours"] * lane["Wq"] * sep.DEFAULT_WAIT_COST_HR
                            for lane in per["lanes"] if lane["active"] and lane["served"])
        hand.append(staffing + waiting)
    total = candidate["evidence"]["costs"]["total"]
    assert total["n"] == 5
    assert total["mean"] == pytest.approx(statistics.fmean(hand))


def test_continuous_day_prices_over_target_replications():
    setup, records = _day_setup_and_records()
    schedule = sep.optimize_separate_schedule(
        setup, records, target=0.40, full_coverage=True,
        des_settings={"replications": 5, "base_seed": 42})
    assert schedule["utilization_basis"] == sep.DAY_UTILIZATION_BASIS
    (period,) = schedule["periods"]
    (candidate,) = period["candidates"]
    assert candidate["status"] == "INFEASIBLE"
    assert candidate["replications_over_target"] == 5
    assert candidate["cost_uncertainty"]["n"] == 5
    assert candidate["evidence"]["costs"]["staffing"]["mean"] == pytest.approx(
        2 * sep.DEFAULT_SERVER_COST_HR)
