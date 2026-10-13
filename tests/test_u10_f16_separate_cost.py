"""U10 F16: the separate-lanes cost estimate counts every replication and never goes below 0.

Spec: docs/superpowers/specs/2026-10-13-u10-f16-separate-cost-interval.md.
"""

from __future__ import annotations

import math
import statistics

import pytest
from scipy.stats import t as student_t

from backend.queueing_engine.services import separate_optimization as sep


def _sampled(queue_id, lam, mu, samples):
    return {"queue_id": queue_id, "lambda": lam, "mu": mu, "c": 1, "service_samples_hours": list(samples)}


def _candidate(active, available):
    return {"time": "08:00", "available_queue_ids": list(available), "active_queue_ids": list(active),
            "inactive_queue_ids": [qid for qid in available if qid not in active]}


def test_an_over_target_run_still_reports_its_cost():
    by_id = {"east": _sampled("east", 8.0, 13.0, [0.05, 0.08, 0.10]),
             "express": _sampled("express", 4.0, 13.0, [0.05, 0.08, 0.10])}
    result = sep.evaluate_candidate_with_des(_candidate(["east"], ["east", "express"]), by_id,
                                             duration_hours=24.0, seed=5)
    assert result["status"] == "INFEASIBLE" and "70%" in result["reason"]
    assert result["server_cost"] > 0 and result["waiting_cost"] > 0
    assert result["total_cost"] == pytest.approx(result["server_cost"] + result["waiting_cost"])


def test_an_over_target_period_of_the_continuous_day_still_reports_its_cost():
    from tests.test_b13_per_date_day import SAMPLES, _setup

    setup = _setup("representative_day")
    rows = {label: [{"time": label, "segment_id": label, "queue_id": queue_id, "lambda": 6.0, "mu": 1 / 0.0875, "c": 1,
                     "service_samples_hours": list(SAMPLES)} for queue_id in ("lane-a", "lane-b")]
            for label in ("s1", "s2")}
    lanes = ["lane-a", "lane-b"]
    runner = sep._day_candidate_runner(setup, ["s1", "s2"], rows, {"s1": lanes, "s2": lanes})
    result = runner(_candidate(lanes, lanes) | {"time": "s1"}, {row["queue_id"]: row for row in rows["s1"]},
                    duration_hours=1.0, seed=3, target=0.40, server_cost=87.0, waiting_cost=100.0, max_events=4000)
    assert result["status"] == "INFEASIBLE" and "40%" in result["reason"]
    assert result["server_cost"] > 0
    assert result["total_cost"] == pytest.approx(result["server_cost"] + result["waiting_cost"])


def test_an_old_representative_day_plan_is_reported_as_historical(db_engine, client):
    from backend.api.workflow import HISTORICAL_COST_SNAPSHOT
    from tests.helpers import login
    from tests.test_b13_per_date_day import _insert_plan, _optimize, _workspace

    analysis_id, dataset_id, rows = _workspace(db_engine, "representative_day")
    login(client, "owner@example.com", "pw")
    schedule = _optimize(client, analysis_id)["schedule"]
    old_id = _insert_plan(db_engine, analysis_id, dataset_id, rows, sep.SEPARATE_DES_V2_ENGINE_VERSION, schedule)
    scenario = next(s for s in client.get(f"/analyses/{analysis_id}/scenarios").json()["scenarios"] if s["id"] == old_id)
    assert scenario["evidence_status"] == "HISTORICAL_REQUIRES_RECALCULATION"
    assert any(HISTORICAL_COST_SNAPSHOT in (reason.get("detail") or "") for reason in scenario["evidence_reasons"])


def _run(status, cost, rho):
    lane = {"queue_id": "a", "active": True, "rho": rho, "arrivals": 10, "served": 10, "waiting": 0, "Wq": 0.1}
    return {"status": status, "customer_conservation": True, "evaluations": [lane], "total_lambda": 5.0,
            "server_cost": 50.0, "waiting_cost": cost - 50.0, "total_cost": cost,
            "trace_events": [], "trace_truncated": False}


def test_the_mean_cost_uses_every_replication_and_the_interval_stops_at_zero():
    runs = iter([_run("FEASIBLE", 60.0, 0.60), _run("INFEASIBLE", 400.0, 0.80), _run("FEASIBLE", 55.0, 0.62)])
    aggregate = sep.evaluate_candidate_with_des_replications(
        _candidate(["a"], ["a"]), {"a": {}}, {"replications": 3, "base_seed": 1, "target": 0.7},
        run_fn=lambda *args, **kwargs: next(runs))
    total = aggregate["costs"]["total"]
    costs = [60.0, 400.0, 55.0]
    mean = math.fsum(costs) / 3
    half = float(student_t.ppf(0.975, 2)) * statistics.stdev(costs) / math.sqrt(3)
    assert total["n"] == 3 and total["mean"] == pytest.approx(mean)
    assert mean - half < 0  # the plain t interval would go negative here
    assert total["ci_lower"] == 0.0 and total["ci_upper"] == pytest.approx(mean + half)
    assert aggregate["costs"]["waiting"]["ci_lower"] >= 0.0 and aggregate["costs"]["staffing"]["ci_lower"] == 50.0


def test_the_floor_only_raises_a_negative_lower_bound():
    assert sep._summarize_metric([1.0, 100.0])["ci_lower"] < 0
    assert sep._summarize_metric([1.0, 100.0], floor=0.0)["ci_lower"] == 0.0
    tight = sep._summarize_metric([10.0, 11.0, 12.0], floor=0.0)
    assert tight == sep._summarize_metric([10.0, 11.0, 12.0])  # a positive bound is left as it is
    assert sep._summarize_metric([5.0], floor=0.0)["ci_lower"] is None


def test_plans_saved_before_the_change_are_historical():
    from backend.api.workflow import (
        HISTORICAL_COST_SNAPSHOT,
        HISTORICAL_PER_DATE_SNAPSHOT,
        UNSUPPORTED_SEPARATE_SNAPSHOT,
        _separate_schedule_problem,
    )
    from backend.db.models import Scenario

    rep_day = {"queue_structure": "separate_queues", "event_period_basis": "representative_day"}
    per_date_day = {"queue_structure": "separate_queues", "event_period_basis": "per_date",
                    "segments": [{"id": "s1", "start_time": "08:00", "end_time": "09:00"}]}
    assert sep.separate_engine_version(rep_day) == "novaq-2026-10-separate-des-v4"
    assert sep.separate_engine_version(per_date_day) == "novaq-2026-10-separate-des-v5"

    def problem(version, setup):
        scenario = Scenario(settings_json={"calculation": {"schema_version": 2, "engine_version": version}},
                            results_json={})
        return _separate_schedule_problem(scenario, setup)

    assert problem("novaq-2026-09-separate-des-v2", rep_day) == HISTORICAL_COST_SNAPSHOT
    assert problem("novaq-2026-10-separate-des-v3", per_date_day) == HISTORICAL_COST_SNAPSHOT
    assert problem("novaq-2026-09-separate-des-v2", per_date_day) == HISTORICAL_PER_DATE_SNAPSHOT
    assert problem("novaq-2026-01-separate-des-v1", rep_day) == UNSUPPORTED_SEPARATE_SNAPSHOT
    assert problem("novaq-2026-10-separate-des-v4", rep_day) == "schedule is not COMPLETE"  # current version passes the version check
