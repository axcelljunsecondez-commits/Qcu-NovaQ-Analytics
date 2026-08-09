"""Simulation endpoints: DES, Monte Carlo, and plan validation."""

from __future__ import annotations

from tests.helpers import create_user, login

SEGMENTS = [
    {"time": "08:00-09:00", "lambda": 30, "mu": 12, "c": 3},
    {"time": "09:00-10:00", "lambda": 45, "mu": 12, "c": 4},
]


def test_des_endpoint(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/des", json={"segments": SEGMENTS, "sim_hours": 8, "seed": 7}
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    assert "status" in results[0]
    assert "rho_sim" in results[0]


def test_des_requires_auth(client):
    assert client.post("/simulation/des", json={"segments": SEGMENTS}).status_code == 401


def test_mc_endpoint(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/mc",
        json={"segments": SEGMENTS, "num_trials": 200, "failure_threshold": 0.75, "seed": 7},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    assert "failure_rate" in results[0]
    assert "adequate_samples" in results[0]


def test_validate_endpoint(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    comparison = [
        {"time": "08:00-09:00", "lambda": 30, "mu": 12, "c_optimal": 3},
        {"time": "09:00-10:00", "lambda": 45, "mu": 12, "c_optimal": 4},
    ]
    response = client.post(
        "/simulation/validate",
        json={"segments": comparison, "mc_trials": 200, "seed": 7},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    assert "sim_status" in results[0]
    assert "mc_failure_rate" in results[0]
    assert "mc_adequate" in results[0]


def test_validate_empty_segments_422(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post("/simulation/validate", json={"segments": []})
    assert response.status_code == 422


def test_validate_requires_auth(client):
    response = client.post("/simulation/validate", json={"segments": []})
    assert response.status_code == 401
