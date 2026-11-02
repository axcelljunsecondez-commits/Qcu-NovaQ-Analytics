"""Separate lines: the simulated wait intervals stop at 0 (Part B of the 2026-10-29 wait-range fix).

Spec: docs/superpowers/specs/2026-10-29-separate-wait-interval-floor.md. Reference values (R1-R5) are
hand-computed with the Student-t table values t(0.975, 2) = 4.302653 and t(0.975, 4) = 2.776445.
"""

from __future__ import annotations

import math

import pytest

from backend.queueing_engine.services import separate_optimization as sep

T_975_DF4 = 2.776445


def test_r1_a_wait_interval_that_dips_below_zero_is_cut_at_zero():
    plain = sep._summarize_metric([0.0, 0.0, 0.0, 0.0, 0.1])
    floored = sep._summarize_metric([0.0, 0.0, 0.0, 0.0, 0.1], floor=0.0)
    assert plain["ci_lower"] == pytest.approx(-0.0355289, abs=1e-6)
    assert floored["ci_lower"] == 0.0
    assert floored["ci_upper"] == pytest.approx(0.0755289, abs=1e-6)
    assert floored["mean"] == pytest.approx(0.02)
    assert floored["sd"] == pytest.approx(math.sqrt(0.002))
    assert floored["se"] == pytest.approx(0.02)
    assert floored["n"] == 5
    assert {k: v for k, v in floored.items() if k != "ci_lower"} == {k: v for k, v in plain.items() if k != "ci_lower"}


def test_r2_a_wait_interval_above_zero_is_left_as_it_is():
    floored = sep._summarize_metric([0.10, 0.12, 0.14], floor=0.0)
    assert floored["ci_lower"] == pytest.approx(0.0703172, abs=1e-6)
    assert floored["ci_upper"] == pytest.approx(0.1696828, abs=1e-6)
    assert floored == sep._summarize_metric([0.10, 0.12, 0.14])


def test_r3_r4_r5_counts_no_spread_and_one_replication():
    waiting_end = sep._summarize_metric([0, 0, 0, 0, 2], floor=0.0)
    assert waiting_end["ci_lower"] == 0.0
    assert waiting_end["ci_upper"] == pytest.approx(1.510578, abs=1e-6)
    assert waiting_end["mean"] == pytest.approx(0.4)
    no_spread = sep._summarize_metric([0.0, 0.0, 0.0], floor=0.0)
    assert (no_spread["ci_lower"], no_spread["ci_upper"]) == (0.0, 0.0)
    single = sep._summarize_metric([0.3], floor=0.0)
    assert single["ci_lower"] is None and single["ci_upper"] is None and single["n"] == 1


def _run(wq, waiting, rho):
    lane = {"queue_id": "a", "active": True, "rho": rho, "arrivals": 10, "served": 10, "waiting": waiting, "Wq": wq}
    return {"status": "FEASIBLE", "customer_conservation": True, "evaluations": [lane], "total_lambda": 5.0,
            "server_cost": 50.0, "waiting_cost": 5.0, "total_cost": 55.0, "trace_events": [], "trace_truncated": False}


def _aggregate(runs):
    stream = iter(runs)
    return sep.evaluate_candidate_with_des_replications(
        {"time": "08:00", "available_queue_ids": ["a"], "active_queue_ids": ["a"], "inactive_queue_ids": []},
        {"a": {}}, {"replications": len(runs), "base_seed": 1, "target": 0.85},
        run_fn=lambda *args, **kwargs: next(stream))


def test_the_plan_wait_and_each_lanes_wait_and_queue_left_stop_at_zero():
    wq, waiting, rho = [0.0, 0.0, 0.0, 0.0, 0.1], [0, 0, 0, 0, 2], [0.0, 0.0, 0.0, 0.0, 0.5]
    aggregate = _aggregate([_run(*values) for values in zip(wq, waiting, rho)])
    (lane,) = aggregate["per_lane"]
    for summary, values in ((aggregate["waiting_time"], wq), (lane["Wq"], wq), (lane["waiting_end"], waiting)):
        plain = sep._summarize_metric(values)
        assert plain["ci_lower"] < 0  # the plain t interval would dip below 0 here
        assert summary["ci_lower"] == 0.0
        assert {k: v for k, v in summary.items() if k != "ci_lower"} == {k: v for k, v in plain.items() if k != "ci_lower"}
    assert aggregate["waiting_time"]["ci_upper"] == pytest.approx(0.02 + T_975_DF4 * 0.02, abs=1e-6)
    # Outside this change: utilization keeps the plain interval (spec §3, OD-W2).
    assert lane["utilization"] == sep._summarize_metric(rho) and lane["utilization"]["ci_lower"] < 0


def test_waits_whose_interval_stays_above_zero_are_unchanged():
    wq = [0.10, 0.12, 0.14]
    aggregate = _aggregate([_run(value, 1, 0.6) for value in wq])
    assert aggregate["waiting_time"] == sep._summarize_metric(wq)
    assert aggregate["per_lane"][0]["Wq"] == sep._summarize_metric(wq)


def test_a_computed_plans_wait_range_never_starts_below_zero(db_engine, client):
    from scipy.stats import t as student_t

    from tests.helpers import login
    from tests.test_b13_per_date_day import _insert_plan, _optimize, _workspace

    analysis_id, dataset_id, rows = _workspace(db_engine, "representative_day")
    login(client, "owner@example.com", "pw")
    schedule = _optimize(client, analysis_id)["schedule"]
    plan_id = _insert_plan(db_engine, analysis_id, dataset_id, rows, sep.SEPARATE_DES_ENGINE_VERSION, schedule)
    waits = [period["optimum"]["evidence"]["waiting_time"] for period in schedule["periods"]]
    plain_lowers = [w["mean"] - float(student_t.ppf(0.975, w["n"] - 1)) * w["se"] for w in waits]
    assert any(lower < 0 for lower in plain_lowers)  # the floor binds in this run
    comparison = client.get(f"/analyses/{analysis_id}/workflow/comparison/separate")
    assert comparison.status_code == 200, comparison.text
    plan = next(item for item in comparison.json()["plans"] if item["scenario_id"] == plan_id)
    assert len(plan["periods"]) == len(waits)
    for period, wait, plain_lower in zip(plan["periods"], waits, plain_lowers):
        lower, upper = period["wait_ci"]
        assert lower == pytest.approx(max(0.0, plain_lower))
        assert lower >= 0.0 and upper == pytest.approx(wait["ci_upper"])
