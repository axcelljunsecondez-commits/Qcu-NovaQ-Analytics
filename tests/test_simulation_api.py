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


def test_des_trace_endpoint(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/des/trace",
        json={"segments": SEGMENTS[:1], "trace_hours": 1, "max_events": 100, "seed": 7},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["event_count"] == len(body["trace"])
    assert body["trace"]
    assert body["trace"][0]["type"] == "arrival"
    assert isinstance(body["trace"][0]["customer_id"], int)
    assert body["segments"][0]["queue_structure"] == "shared"
    assert body["abandonment_supported"] is False


def test_des_trace_requires_auth(client):
    assert client.post("/simulation/des/trace", json={"segments": SEGMENTS}).status_code == 401


def test_des_trace_rejects_out_of_range_hours(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/des/trace",
        json={"segments": SEGMENTS, "trace_hours": 4.1},
    )
    assert response.status_code == 422


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


def test_mc_endpoint_exposes_failure_rate_ci_fields(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/mc",
        json={"segments": SEGMENTS, "num_trials": 200, "failure_threshold": 0.75, "seed": 7},
    )
    assert response.status_code == 200
    row = response.json()["results"][0]
    for key in [
        "failure_rate_ci_lower",
        "failure_rate_ci_upper",
        "failure_rate_ci_half_width",
        "failure_rate_precision",
        "failure_rate_adequate",
    ]:
        assert key in row


def test_validate_endpoint_exposes_mc_failure_rate_ci_fields(db_engine, client):
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
    row = response.json()["results"][0]
    for key in [
        "mc_failure_rate_ci_lower",
        "mc_failure_rate_ci_upper",
        "mc_failure_rate_ci_half_width",
        "mc_failure_rate_precision",
        "mc_failure_rate_adequate",
    ]:
        assert key in row


def test_mc_defaults_to_2000_trials(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/mc",
        json={"segments": SEGMENTS, "failure_threshold": 0.75, "seed": 7},
    )
    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


def test_validate_accepts_failure_rate_cap(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    comparison = [
        {"time": "08:00-09:00", "lambda": 30, "mu": 12, "c_optimal": 3},
    ]
    response = client.post(
        "/simulation/validate",
        json={"segments": comparison, "failure_rate_cap": 0.05, "seed": 7},
    )
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1


def test_validate_accepts_mc_failure_rate_cap_alias(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    comparison = [
        {"time": "08:00-09:00", "lambda": 30, "mu": 12, "c_optimal": 3},
    ]
    response = client.post(
        "/simulation/validate",
        json={"segments": comparison, "mc_failure_rate_cap": 0.05, "seed": 7},
    )
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1


def test_validate_accepts_des_sim_hours(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    comparison = [
        {"time": "08:00-09:00", "lambda": 30, "mu": 12, "c_optimal": 3},
    ]
    response = client.post(
        "/simulation/validate",
        json={"segments": comparison, "des_sim_hours": 12, "seed": 7},
    )
    assert response.status_code == 200
    row = response.json()["results"][0]
    assert row["sim_status"] in {"Lean", "Normal", "Peak", "Critical", "Unstable"}


def test_validate_rejects_out_of_range_failure_rate_cap(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    comparison = [
        {"time": "08:00-09:00", "lambda": 30, "mu": 12, "c_optimal": 3},
    ]
    response = client.post(
        "/simulation/validate",
        json={"segments": comparison, "failure_rate_cap": 1.5, "seed": 7},
    )
    assert response.status_code == 422


def test_validate_defaults_to_2000_trials(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    comparison = [
        {"time": "08:00-09:00", "lambda": 30, "mu": 12, "c_optimal": 3},
    ]
    response = client.post("/simulation/validate", json={"segments": comparison, "seed": 7})
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1


def test_mc_accepts_20000_trials(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/mc",
        json={"segments": SEGMENTS, "num_trials": 20000, "seed": 7},
    )
    assert response.status_code == 200


def test_mc_accepts_100000_trials(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/mc",
        json={"segments": SEGMENTS, "num_trials": 100000, "seed": 7},
    )
    assert response.status_code == 200


def test_mc_accepts_failure_rate_cap(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/mc",
        json={"segments": SEGMENTS, "failure_rate_cap": 0.99, "seed": 7},
    )
    assert response.status_code == 200
    assert all(r["status"] == "PASS" for r in response.json()["results"])


def test_mc_high_failure_rate_cap_marks_all_fail(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/mc",
        json={"segments": SEGMENTS, "failure_rate_cap": 0.001, "seed": 7},
    )
    assert response.status_code == 200
    assert all(r["status"] == "FAIL" for r in response.json()["results"])


def test_mc_rejects_out_of_range_failure_rate_cap(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/mc",
        json={"segments": SEGMENTS, "failure_rate_cap": 1.5, "seed": 7},
    )
    assert response.status_code == 422


def test_mc_rejects_100001_trials(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/mc",
        json={"segments": SEGMENTS, "num_trials": 100001, "seed": 7},
    )
    assert response.status_code == 422


def test_mc_rejects_extremely_large_trials(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/mc",
        json={"segments": SEGMENTS, "num_trials": 10**9, "seed": 7},
    )
    assert response.status_code == 422


def test_mc_rejects_zero_trials(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = client.post(
        "/simulation/mc",
        json={"segments": SEGMENTS, "num_trials": 0, "seed": 7},
    )
    assert response.status_code == 422


def test_validate_rejects_over_cap_trials(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    comparison = [
        {"time": "08:00-09:00", "lambda": 30, "mu": 12, "c_optimal": 3},
    ]
    response = client.post(
        "/simulation/validate",
        json={"segments": comparison, "mc_trials": 100001, "seed": 7},
    )
    assert response.status_code == 422
