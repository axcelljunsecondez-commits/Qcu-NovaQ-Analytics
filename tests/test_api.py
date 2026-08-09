"""Integration tests for the FastAPI REST wrapper."""

from __future__ import annotations

from starlette.testclient import TestClient

from api import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_metrics_mm1():
    resp = client.post("/metrics", json={"lambda": 5, "mu": 8, "c": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert "rho" in body
    assert body["stable"] is True
    assert body["model"] == "M/M/1"


def test_metrics_mmc():
    resp = client.post("/metrics", json={"lambda": 10, "mu": 4, "c": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert "Lq" in body
    assert body["stable"] is True


def test_metrics_invalid_lambda():
    resp = client.post("/metrics", json={"lambda": -5, "mu": 4, "c": 2})
    assert resp.status_code == 400


def test_optimize_valid():
    resp = client.post(
        "/optimize",
        json={
            "lambda": 10,
            "mu": 4,
            "c": 3,
            "server_cost_per_hr": 87,
            "wait_cost_per_min": 5,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("optimal_c"), int)
    assert body["optimal_c"] > 0


def test_batch_three_segments():
    segments = [
        {"lambda": 5, "mu": 8, "c": 1},
        {"lambda": 10, "mu": 4, "c": 3},
        {"lambda": 20, "mu": 6, "c": 4},
    ]
    resp = client.post("/metrics/batch", json={"segments": segments})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 3


def test_optimize_with_theta_uses_erlang_a():
    resp = client.post("/optimize", json={"lambda": 9, "mu": 10, "c": 1, "theta": 0.5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["Wq_current"] is not None

    resp_no_theta = client.post("/optimize", json={"lambda": 9, "mu": 10, "c": 1})
    assert resp_no_theta.status_code == 200
    assert body["Wq_current"] < resp_no_theta.json()["Wq_current"]
