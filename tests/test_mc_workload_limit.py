"""Monte Carlo workload limit: trials x total counters <= MC_MAX_COUNTER_TRIALS (OD-N4, approved 2026-10-13).

Spec: docs/superpowers/specs/2026-10-12-large-server-count-erlang-numerics.md section 9. The limit is checked
before any trial (and, for validation, before DES) and every route refuses with 422 and a string detail.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.queueing_engine.config import MC_MAX_COUNTER_TRIALS
from backend.queueing_engine.simulation import simulation
from backend.queueing_engine.simulation.simulation import (
    McWorkloadError,
    mc_simulate_segments,
    require_mc_workload_within_limit,
    validate_with_simulation,
)
from tests.helpers import create_user, csrf_header, login

LARGE = {"time": "09:00", "lambda": 1.0, "mu": 1.0, "c": 100_000}
OVER_TRIALS = MC_MAX_COUNTER_TRIALS // 100_000 + 1  # 241 trials x 100,000 counters = 24,100,000


def _no_trial(*args, **kwargs):
    raise AssertionError("a trial ran")


def test_limit_value_is_the_approved_one():
    assert MC_MAX_COUNTER_TRIALS == 24_000_000


def test_over_the_limit_is_refused_before_any_trial(monkeypatch):
    monkeypatch.setattr(simulation, "mc_simulate_segment", _no_trial)
    with pytest.raises(McWorkloadError) as refused:
        mc_simulate_segments([LARGE], num_trials=OVER_TRIALS)
    assert str(refused.value) == (
        "Monte Carlo run too large: 241 trials x 100,000 counters = 24,100,000 counter-trials; "
        "the limit is 24,000,000. Use at most 240 trials for these counters."
    )


def test_exactly_the_limit_runs(monkeypatch):
    calls = []
    monkeypatch.setattr(simulation, "mc_simulate_segment", lambda *args: calls.append(args) or {})
    mc_simulate_segments([LARGE], num_trials=OVER_TRIALS - 1)
    assert len(calls) == 1


def test_counters_sum_over_segments_and_default_to_one():
    require_mc_workload_within_limit([{"lambda": 1.0, "mu": 1.0}] * 240, 100_000)  # 24,000,000: allowed
    with pytest.raises(McWorkloadError, match="241 counters"):
        require_mc_workload_within_limit([{"lambda": 1.0, "mu": 1.0}] * 241, 100_000)


def test_segments_that_run_no_trial_count_zero():
    huge = MC_MAX_COUNTER_TRIALS + 1
    require_mc_workload_within_limit([{"lambda": 1.0, "c": huge}], 1)  # no mu: refused per segment, no trial
    require_mc_workload_within_limit([{"lambda": 1.0, "mu": 1.0, "c": -huge}], 1)
    require_mc_workload_within_limit([{"lambda": -1.0, "mu": 1.0, "c": huge}], 1)  # refused segment keeps its c
    require_mc_workload_within_limit(["not a segment"], 1)
    with pytest.raises(McWorkloadError, match="The counters alone exceed the limit."):
        require_mc_workload_within_limit([{"lambda": 1.0, "mu": 1.0, "c": huge}], 1)


def test_validation_is_refused_before_des(monkeypatch):
    monkeypatch.setattr(simulation, "simulate_segments", _no_trial)
    comparison = pd.DataFrame([{"time": "09:00", "lambda": 1.0, "mu": 1.0, "c_optimal": 100_000}])
    with pytest.raises(McWorkloadError):
        validate_with_simulation(comparison, mc_trials=OVER_TRIALS)


def test_simulation_mc_route_refuses_with_422(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post("/simulation/mc", json={"segments": [LARGE], "num_trials": OVER_TRIALS})
    assert response.status_code == 422
    assert response.json()["detail"].endswith("Use at most 240 trials for these counters.")


def test_simulation_validate_route_refuses_with_422(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    comparison = [{"time": "09:00", "lambda": 1.0, "mu": 1.0, "c_optimal": 100_000}]
    response = client.post("/simulation/validate", json={"segments": comparison, "mc_trials": OVER_TRIALS})
    assert response.status_code == 422
    assert "the limit is 24,000,000" in response.json()["detail"]


def test_workflow_current_mc_route_refuses_with_422(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    headers = csrf_header(client)
    setup = {
        "queue_structure": "shared_queue", "fixed_server_count": 100_000, "staffing_varies_by_period": False,
        "capacity_mode": "unlimited", "total_system_capacity": None, "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None, "segments": [], "queue_ids": [],
    }
    created = client.post("/analyses", headers=headers, json={"name": "Large", "service_type": "checkout",
                                                               "queue_setup": setup})
    assert created.status_code == 201, created.text
    analysis_id = created.json()["analysis"]["id"]
    uploaded = client.post(f"/analyses/{analysis_id}/datasets", headers=headers,
                           files={"file": ("input.csv", b"time,lambda,mu,c\n08:00-09:00,1,1,100000\n", "text/csv")})
    assert uploaded.status_code == 201, uploaded.text
    response = client.post(f"/analyses/{analysis_id}/workflow/simulation/mc/current", headers=headers,
                           json={"num_trials": OVER_TRIALS, "seed": 7})
    assert response.status_code == 422, response.text
    assert "the limit is 24,000,000" in response.json()["detail"]
