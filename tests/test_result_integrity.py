"""Regressions for invalid states identified in the result-integrity review."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from backend.data.ingestion import validate_and_normalize
from backend.queueing_engine.models import queue_models
from backend.queueing_engine.services.optimization import optimize_segment, summarize_optimization
from backend.queueing_engine.simulation.simulation import mc_simulate_segment, simulate_segment


def test_utilization_target_is_a_constraint():
    result = optimize_segment({"lambda": 18, "mu": 10, "c": 2}, target_utilization=.5,
                              default_server_cost=100, customer_waiting_cost=0)
    assert result["c_optimal"] == 4
    assert result["rho_optimal"] <= .5


def test_low_load_cannot_override_server_bound_or_cost_minimum():
    result = optimize_segment({"lambda": 5, "mu": 10, "c": 10}, max_servers=4,
                              default_server_cost=100, customer_waiting_cost=0)
    assert result["c_optimal"] == 1
    assert result["cost_optimal"] == 100


def test_finite_capacity_candidates_are_searchable():
    result = optimize_segment({"lambda": 10, "mu": 10, "c": 2, "K": 5}, max_servers=24)
    assert 1 <= result["c_optimal"] <= 5


@pytest.mark.parametrize("rows", [[], [optimize_segment({"lambda": 100, "mu": 1, "c": 1}, max_servers=1)]])
def test_missing_plan_never_generates_savings(rows):
    summary = summarize_optimization(rows)
    assert summary["total_savings"] is None
    assert summary["total_optimized_cost"] is None
    assert summary["comparison_complete"] is False


@pytest.mark.parametrize("lam,mu,c,theta", [(100, 1, 1, .01), (10, 4, 3, .5), (100, 1, 2, 1e12)])
def test_erlang_a_flow_and_capacity(lam, mu, c, theta):
    result = queue_models.erlang_a(lam, mu, c, theta)
    assert result["stable"], result["error"]
    assert 0 <= result["lambda_eff"] <= c * mu
    assert result["lambda_eff"] + theta * result["Lq"] == pytest.approx(lam, rel=1e-9)
    assert all(math.isfinite(result[k]) and result[k] >= 0 for k in ["L", "Lq", "W", "Wq"])


def test_erlang_a_reports_nonconvergence(monkeypatch):
    monkeypatch.setattr(queue_models, "ERLANG_A_MAX_STATES", 5, raising=False)
    result = queue_models.erlang_a(100, 1, 1, .01)
    assert not result["stable"]
    assert "converg" in result["error"].lower()


@pytest.mark.parametrize("key,value", [("c", 2.9), ("K", 2.5), ("theta", "abc"), ("variance", -1),
                                        ("lambda", math.inf), ("mu", math.nan), ("c", True)])
def test_upload_rejects_invalid_supplied_values(key, value):
    ok, message, _ = validate_and_normalize(pd.DataFrame([{"time": "t", "lambda": 10, "mu": 10, "c": 2, key: value}]))
    assert not ok
    assert key in message and "row" in message.lower()


@pytest.mark.parametrize("extra", [{"K": 2}, {"variance": .1}, {"theta": .5}])
def test_simulation_explicitly_declines_unsupported_models(extra):
    segment = {"time": "t", "lambda": 5, "mu": 10, "c": 2, **extra}
    des = simulate_segment(segment, sim_hours=.1).to_dict()
    mc = mc_simulate_segment(segment, num_trials=2)
    for result in [des, mc]:
        assert result["simulation_supported"] is False
        assert "unsupported" in result["error"].lower()


def test_finite_capacity_approximation_cannot_claim_impossible_queue():
    result = queue_models.mgck(10, 10, 2, 10, 5)
    assert not result["stable"]
    assert "capacity" in result["error"]
    assert result["L"] is None


@pytest.mark.parametrize("servers", [2.9, math.inf, math.nan, True])
def test_simulation_rejects_malformed_server_counts(servers):
    row = {"time": "t", "lambda": 5, "mu": 10, "c": servers}
    assert simulate_segment(row, sim_hours=.1).error
    assert mc_simulate_segment(row, num_trials=2)["error"]


@pytest.mark.parametrize("optional", [{}, {"theta": None}, {"variance": ""}, {"theta": 0, "variance": 0}])
def test_upload_preserves_absent_and_valid_optional_fields(optional):
    ok, message, _ = validate_and_normalize(pd.DataFrame([{"time": "t", "lambda": 0, "mu": 10, "c": 1, **optional}]))
    assert ok, message


@pytest.mark.parametrize("servers", [2.9, math.inf])
def test_validation_does_not_truncate_recommended_staffing(servers):
    from backend.queueing_engine.simulation.simulation import validate_with_simulation
    frame = pd.DataFrame([{"time": "t", "lambda": 5, "mu": 10, "c_optimal": servers}])
    result = validate_with_simulation(frame, mc_trials=2, des_sim_hours=.01)
    assert not result.iloc[0]["simulation_supported"]
    assert result.iloc[0]["validation_reason"]
