"""Optimization endpoints: single and batch, mirroring engine output."""

from __future__ import annotations

from backend.queueing_engine.config import DEFAULT_SERVER_COST_HR
from tests.helpers import create_user, login

SEGMENT = {"time": "08:00-09:00", "lambda": 30, "mu": 12, "c": 3}
OPTIMIZE_BODY = {"segment": SEGMENT}


def test_optimize_single(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post("/optimize", json=OPTIMIZE_BODY)
    assert response.status_code == 200
    body = response.json()
    assert body["c_current"] == 3
    assert body["c_optimal"] is not None
    assert body["current_stable"] is True
    assert body["recommendation"]
    assert body["time"] == "08:00-09:00"


def test_optimize_requires_auth(client):
    assert client.post("/optimize", json=OPTIMIZE_BODY).status_code == 401


def test_optimize_matches_engine_values(db_engine, client):
    from backend.queueing_engine.services.optimization import optimize_segment

    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    expected = optimize_segment(
        {"time": "08:00-09:00", "lambda": 30, "mu": 12, "c": 3},
        default_server_cost=DEFAULT_SERVER_COST_HR,
    )
    response = client.post("/optimize", json=OPTIMIZE_BODY)
    body = response.json()
    assert body["c_optimal"] == expected["c_optimal"]
    assert body["cost_current"] == expected["cost_current"]
    assert body["cost_optimal"] == expected["cost_optimal"]


def test_optimize_with_theta_uses_erlang_a(db_engine, client):
    from backend.queueing_engine.services.optimization import optimize_segment

    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    body = {"segment": {**SEGMENT, "theta": 1.0}}
    expected = optimize_segment({**SEGMENT, "theta": 1.0}, default_server_cost=DEFAULT_SERVER_COST_HR)
    response = client.post("/optimize", json=body)
    assert response.status_code == 200
    assert response.json()["c_optimal"] == expected["c_optimal"]


def test_optimize_batch(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/optimize/batch",
        json={
            "segments": [
                SEGMENT,
                {"time": "09:00-10:00", "lambda": 45, "mu": 12, "c": 4},
            ]
        },
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    assert results[0]["c_current"] == 3
    assert results[1]["c_current"] == 4


def test_optimize_batch_requires_auth(client):
    assert client.post("/optimize/batch", json={"segments": [SEGMENT]}).status_code == 401


def test_optimize_invalid_params_422(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/optimize", json={"segment": {"time": "x", "lambda": 30, "mu": 12, "c": 0}}
    )
    assert response.status_code == 422


def test_optimize_api_preserves_unstable_baseline_and_feasible_plan(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/optimize",
        json={
            "segment": {"time": "overload", "lambda": 20.214, "mu": 10, "c": 2},
            "target_utilization": 0.7,
            "max_servers": 5,
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["current_stable"] is False
    assert result["rho_current"] == 1.0107
    assert result["Wq_current"] is None
    assert result["cost_current"] is None
    assert result["c_optimal"] == 3
    assert result["optimized_stable"] is True
    assert result["Wq_optimal"] is not None
