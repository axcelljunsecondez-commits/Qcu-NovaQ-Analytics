"""Problem 7: separate-queue Monte Carlo and validation support.

Frozen semantics (Problem 6B): per-(time, queue_id) execution reusing all
existing MC mathematics, variance-aware dispatch to existing mg1, queue_id
threaded through results and validation matching, missing stays missing,
FAIL > insufficient > PASS with no pooled rates, Decision taxonomy unchanged.
"""
from __future__ import annotations

import pandas as pd

from backend.api.workflow import _derive_decision
from backend.db.models import AnalysisProject, Scenario
from backend.queueing_engine.simulation.simulation import mc_simulate_segment
from tests.helpers import create_user, csrf_header, login


def _separate_row(queue, lam=4.0, mu=6.0, variance=0.09, time="s1"):
    return {
        "segment_id": "s1", "time": time, "queue_id": queue,
        "queue_structure": "separate_queues", "model_id": "parallel_mg1",
        "lambda": lam, "mu": mu, "c": 1,
        "service_time_source": "aggregate_statistics",
        "variance": variance,
    }


def test_mc_dispatches_variance_rows_to_mg1():
    """Variance-bearing separate rows must run M/G/1, never M/M/1."""
    out = mc_simulate_segment(_separate_row("cashier-east"), num_trials=2000, seed=7)
    assert out["selected_model"] == "Parallel M/G/1"
    assert out["simulation_supported"] is True
    # Pollaczek-Khinchine for lam=4, mu=6, var=0.09 is ~0.707; M/M/1 says 0.333.
    assert out["Wq_mean"] is not None and 0.55 < out["Wq_mean"] < 0.90
    assert out["failure_rate"] is not None


def test_mc_result_preserves_queue_identity():
    out = mc_simulate_segment(_separate_row("lane_03"), num_trials=100, seed=7)
    assert out["queue_id"] == "lane_03"
    assert out["time"] == "s1"


def test_mc_unsupported_combinations_fail_closed():
    base = {"segment_id": "s1", "time": "s1", "queue_id": "express",
            "queue_structure": "separate_queues", "model_id": "parallel_mg1",
            "lambda": 4.0, "mu": 6.0, "service_time_source": "aggregate_statistics"}
    variants = [
        {**base, "c": 2, "variance": 0.01},
        {**base, "c": 1, "variance": 0.01, "K": 5},
        {**base, "c": 1, "variance": 0.01, "theta": 0.5},
        {**base, "c": 1},
    ]
    for row in variants:
        out = mc_simulate_segment(row, num_trials=50, seed=7)
        assert out["simulation_supported"] is False, row
        assert out["failure_rate"] is None, row
        assert out["error"], row


def test_mc_unstable_stays_null():
    out = mc_simulate_segment(_separate_row("Q1", lam=9.0, mu=6.0, variance=0.004),
                              num_trials=200, seed=7)
    assert out["Wq_mean"] is None
    assert out["failure_rate"] is not None


def _scenario(results):
    return Scenario(
        id=3, user_id=1, analysis_id=1, dataset_id=2, name="Separate plan",
        settings_json={}, results_json={"results": results},
    )


def _analysis():
    return AnalysisProject(id=1, user_id=1, name="Branch", setup_status="ready", queue_setup_json={})


def _scenario_row(time, queue, cost=100):
    return {"time": time, "queue_id": queue, "c_current": 1, "c_optimal": 1,
            "cost_current": cost, "cost_optimal": cost}


def _validation_row(time, queue, rate=0.01, adequate=True, status="Normal"):
    return {"time": time, "queue_id": queue, "simulation_supported": True,
            "validation_reason": None, "sim_status": status,
            "mc_failure_rate": rate, "mc_failure_rate_adequate": adequate}


def _evidence(validation_rows, times=("10:00", "10:00")):
    return {
        "selection": {"id": 10},
        "des": {"id": 11, "result": {"results": [
            {"time": time, "simulation_supported": True, "error": None} for time in times
        ]}},
        "mc": None,
        "validation": {"id": 12, "params": {"mc_failure_rate_cap": 0.05},
                       "result": {"results": validation_rows}},
    }


def test_decision_rejects_cross_queue_time_only_match():
    """Same times but wrong queues must read as missing evidence, not a match."""
    scenario = _scenario([_scenario_row("10:00", "cashier-east"), _scenario_row("10:00", "express")])
    evidence = _evidence([_validation_row("10:00", "cashier-east"), _validation_row("10:00", "cashier-east")])
    decision = _derive_decision(_analysis(), scenario, evidence)
    assert decision["status"] == "insufficient_evidence"
    assert any("validation evidence" in item for item in decision["missing_evidence"])


def test_decision_per_queue_fail_revises_with_counts():
    scenario = _scenario([_scenario_row("10:00", "cashier-east"), _scenario_row("10:00", "express")])
    evidence = _evidence([_validation_row("10:00", "cashier-east", rate=0.01),
                          _validation_row("10:00", "express", rate=0.40, status="Critical")])
    decision = _derive_decision(_analysis(), scenario, evidence)
    assert decision["status"] == "revise"
    assert decision["facts"]["failed_intervals"] == 1
    assert decision["facts"]["validation_intervals"] == 2


def test_decision_inadequate_row_does_not_become_pass():
    scenario = _scenario([_scenario_row("10:00", "cashier-east"), _scenario_row("10:00", "express")])
    evidence = _evidence([_validation_row("10:00", "cashier-east", rate=0.01),
                          _validation_row("10:00", "express", rate=None, adequate=False)])
    decision = _derive_decision(_analysis(), scenario, evidence)
    assert decision["status"] != "adopt"


def test_mc_current_end_to_end_with_arbitrary_ids(db_engine, client):
    """Setup -> event upload -> Current-MC keeps per-queue evidence, persisted."""
    create_user(db_engine, "mc-east@example.com", "pw")
    login(client, "mc-east@example.com", "pw")
    headers = csrf_header(client)
    analysis_id = client.post(
        "/analyses", headers=headers,
        json={"name": "MC lanes", "queue_setup": {
            "queue_structure": "separate_queues", "fixed_server_count": 1,
            "staffing_varies_by_period": False, "capacity_mode": "unlimited",
            "total_system_capacity": None, "abandonment_mode": "not_modeled",
            "patience_rate_per_hour": None,
            "segments": [{"id": "s1", "start_time": "07:00:00", "end_time": "08:00:00", "active_queue_ids": None}],
            "separate_queue_closure_policy": "drain_existing",
            "queue_ids": ["cashier-east", "express"],
        }},
    ).json()["analysis"]["id"]
    events = (
        b"arrival_time,service_start,service_end,queue_id\n"
        b"2026-09-08T07:05:00Z,2026-09-08T07:06:00Z,2026-09-08T07:12:00Z,cashier-east\n"
        b"2026-09-08T07:20:00Z,2026-09-08T07:21:00Z,2026-09-08T07:26:00Z,cashier-east\n"
        b"2026-09-08T07:10:00Z,2026-09-08T07:11:00Z,2026-09-08T07:15:00Z,express\n"
    )
    uploaded = client.post(
        f"/analyses/{analysis_id}/datasets", headers=headers,
        files={"file": ("events.csv", events, "text/csv")},
    )
    assert uploaded.status_code == 201, uploaded.text
    run = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/mc/current",
        headers=headers,
        json={"num_trials": 200, "failure_threshold": 0.8, "failure_rate_cap": 0.05, "seed": 7},
    )
    assert run.status_code == 200, run.text
    result = run.json()["evidence"]["result"]
    by_queue = {row["queue_id"]: row for row in result["results"]}
    assert set(by_queue) == {"cashier-east", "express"}
    for row in by_queue.values():
        assert row["failure_rate"] is not None
        assert row["selected_model"] == "Parallel M/G/1"
    workflow = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert workflow["mc_current"]["result"]["results"][0]["queue_id"] in {"cashier-east", "express"}
