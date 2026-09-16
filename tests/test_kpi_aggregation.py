"""Problem 2: separate-queue Current KPI aggregation semantics.

Semantic specification under test:

- Average waiting time (separate) = arrival-rate-weighted mean wait across
  analyzed queue-periods: sum(lambda_i * Wq_i) / sum(lambda_i). The weight is
  throughput-exact because the supported separate contract (stable M/G/1,
  unlimited capacity, no abandonment) makes throughput equal lambda.
- Missing/unstable component -> aggregate unavailable (None), never zero.
- Shared-queue semantics are unchanged (plain mean across periods).
- Utilization, costs, and extremes keep their existing defined meanings.

Period durations are not reliably derivable from aggregate time labels, so
no time weighting is invented; that limitation is documented, not coded.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.queueing_engine.services.data_processing import compute_kpis
from tests.helpers import create_user, csrf_header, login


def _separate_frame(rows):
    return pd.DataFrame(rows)


def test_weighted_wait_differs_from_plain_mean():
    """CASE A (unit): hand-calculable proof that weighting is applied."""
    frame = _separate_frame([
        {"time": "08:00", "queue_id": "Q1", "queue_structure": "separate_queues",
         "lambda": 10.0, "mu": 12.0, "c": 1, "rho": 0.5, "Wq": 0.05, "Lq": 0.5, "stable": True},
        {"time": "08:00", "queue_id": "Q2", "queue_structure": "separate_queues",
         "lambda": 2.0, "mu": 9.0, "c": 1, "rho": 0.4, "Wq": 0.50, "Lq": 1.0, "stable": True},
    ])
    kpis = compute_kpis(frame)
    plain_mean = (0.05 + 0.50) / 2
    weighted = (10.0 * 0.05 + 2.0 * 0.50) / (10.0 + 2.0)
    assert weighted == pytest.approx(0.125)
    assert plain_mean == pytest.approx(0.275)
    assert kpis["avg_waiting_time"] == pytest.approx(weighted)
    assert kpis["avg_waiting_time"] != pytest.approx(plain_mean)


def test_equal_demand_reduces_to_plain_mean():
    """CASE B (unit): equal weights collapse to the ordinary mean."""
    frame = _separate_frame([
        {"time": "08:00", "queue_id": "Q1", "queue_structure": "separate_queues",
         "lambda": 5.0, "mu": 12.0, "c": 1, "rho": 0.5, "Wq": 0.10, "Lq": 0.5, "stable": True},
        {"time": "08:00", "queue_id": "Q2", "queue_structure": "separate_queues",
         "lambda": 5.0, "mu": 9.0, "c": 1, "rho": 0.4, "Wq": 0.30, "Lq": 1.5, "stable": True},
    ])
    assert compute_kpis(frame)["avg_waiting_time"] == pytest.approx(0.20)


def test_single_queue_reduces_to_its_wait():
    """CASE C (unit): one active queue aggregates to its own KPI."""
    frame = _separate_frame([
        {"time": "08:00", "queue_id": "Q1", "queue_structure": "separate_queues",
         "lambda": 4.0, "mu": 6.0, "c": 1, "rho": 0.5, "Wq": 0.25, "Lq": 1.0, "stable": True},
    ])
    assert compute_kpis(frame)["avg_waiting_time"] == pytest.approx(0.25)


def test_missing_wait_makes_aggregate_unavailable():
    """CASE E (unit): one unstable queue -> None, never zero-filled."""
    frame = _separate_frame([
        {"time": "08:00", "queue_id": "Q1", "queue_structure": "separate_queues",
         "lambda": 4.0, "mu": 6.0, "c": 1, "rho": 0.5, "Wq": 0.25, "Lq": 1.0, "stable": True},
        {"time": "08:00", "queue_id": "Q2", "queue_structure": "separate_queues",
         "lambda": 9.0, "mu": 6.0, "c": 1, "Wq": None, "Lq": None, "stable": False,
         "rho": 1.5},
    ])
    assert compute_kpis(frame)["avg_waiting_time"] is None


def test_shared_frames_keep_plain_mean():
    """CASE H (unit): non-separate frames are untouched by weighting."""
    frame = pd.DataFrame([
        {"time": "08:00", "lambda": 30.0, "mu": 12.0, "c": 3, "rho": 0.8, "Wq": 0.10, "Lq": 3.0, "stable": True},
        {"time": "09:00", "lambda": 45.0, "mu": 12.0, "c": 4, "rho": 0.9, "Wq": 0.30, "Lq": 13.5, "stable": True},
    ])
    assert compute_kpis(frame)["avg_waiting_time"] == pytest.approx(0.20)


def _setup(queue_ids):
    return {
        "queue_structure": "separate_queues",
        "fixed_server_count": 1,
        "staffing_varies_by_period": False,
        "capacity_mode": "unlimited",
        "total_system_capacity": None,
        "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None,
        "segments": [],
        "queue_ids": queue_ids,
    }


def _upload(client, analysis_id, rows):
    lines = ["time,queue_id,lambda,mu,c,variance"]
    lines += [f"{time},{queue},{lam},{mu},{c},{var}" for time, queue, lam, mu, c, var in rows]
    response = client.post(
        f"/analyses/{analysis_id}/datasets",
        headers=csrf_header(client),
        files={"file": ("input.csv", ("\n".join(lines) + "\n").encode(), "text/csv")},
    )
    assert response.status_code == 201, response.text


def test_api_weighted_wait_matches_independent_derivation(db_engine, client):
    """CASE A (API): end-to-end weighted wait through the real selector."""
    create_user(db_engine, "kpi@example.com", "pw")
    login(client, "kpi@example.com", "pw")
    analysis_id = client.post(
        "/analyses", headers=csrf_header(client),
        json={"name": "KPI", "queue_setup": _setup(["Q1", "Q2"])},
    ).json()["analysis"]["id"]
    _upload(client, analysis_id, [
        ("08:00-09:00", "Q1", 10, 12, 1, 0.001),
        ("08:00-09:00", "Q2", 2, 9, 1, 0.020),
    ])
    body = client.get(f"/analyses/{analysis_id}/current").json()
    rows = {row["queue_id"]: row for row in body["rows"]}
    expected = (
        rows["Q1"]["lambda"] * rows["Q1"]["Wq"] + rows["Q2"]["lambda"] * rows["Q2"]["Wq"]
    ) / (rows["Q1"]["lambda"] + rows["Q2"]["lambda"])
    plain = (rows["Q1"]["Wq"] + rows["Q2"]["Wq"]) / 2
    assert expected != pytest.approx(plain)
    assert body["kpis"]["avg_waiting_time"] == pytest.approx(expected)


def test_api_unstable_queue_makes_wait_unavailable(db_engine, client):
    """CASE E (API): overload anywhere -> wait KPI unavailable, costs kept."""
    create_user(db_engine, "kpi@example.com", "pw")
    login(client, "kpi@example.com", "pw")
    analysis_id = client.post(
        "/analyses", headers=csrf_header(client),
        json={"name": "KPI unstable", "queue_setup": _setup(["Q1", "Q2"])},
    ).json()["analysis"]["id"]
    _upload(client, analysis_id, [
        ("08:00-09:00", "Q1", 4, 6, 1, 0.004),
        ("08:00-09:00", "Q2", 9, 6, 1, 0.004),
    ])
    body = client.get(f"/analyses/{analysis_id}/current").json()
    assert body["kpis"]["avg_waiting_time"] is None
    assert body["kpis"]["total_waiting_cost"] > 0


def test_api_varying_periods_without_synthetic_queues(db_engine, client):
    """CASE D (API): partial activity aggregates only uploaded queues."""
    create_user(db_engine, "kpi@example.com", "pw")
    login(client, "kpi@example.com", "pw")
    analysis_id = client.post(
        "/analyses", headers=csrf_header(client),
        json={"name": "KPI periods", "queue_setup": _setup(["Q1", "Q2", "Q3", "Q4"])},
    ).json()["analysis"]["id"]
    _upload(client, analysis_id, [
        ("05:00-06:00", "Q1", 4, 6, 1, 0.004),
        ("05:00-06:00", "Q2", 4, 6, 1, 0.004),
        ("06:00-07:00", "Q1", 4, 6, 1, 0.004),
        ("06:00-07:00", "Q2", 4, 6, 1, 0.004),
        ("06:00-07:00", "Q3", 4, 6, 1, 0.004),
        ("06:00-07:00", "Q4", 4, 6, 1, 0.004),
    ])
    body = client.get(f"/analyses/{analysis_id}/current").json()
    assert body["kpis"]["avg_waiting_time"] is not None
    assert all(row["lambda"] > 0 for row in body["rows"])


def test_api_shared_wait_semantics_unchanged(db_engine, client):
    """CASE H (API): shared multi-period wait stays a plain mean."""
    create_user(db_engine, "kpi@example.com", "pw")
    login(client, "kpi@example.com", "pw")
    analysis_id = client.post(
        "/analyses", headers=csrf_header(client),
        json={"name": "KPI shared", "queue_setup": {
            "queue_structure": "shared_queue", "fixed_server_count": 2,
            "staffing_varies_by_period": False, "capacity_mode": "unlimited",
            "total_system_capacity": None, "abandonment_mode": "not_modeled",
            "patience_rate_per_hour": None, "segments": [], "queue_ids": [],
        }},
    ).json()["analysis"]["id"]
    response = client.post(
        f"/analyses/{analysis_id}/datasets",
        headers=csrf_header(client),
        files={"file": ("input.csv", b"time,lambda,mu,c\n08:00-09:00,20,12,2\n09:00-10:00,15,12,2\n", "text/csv")},
    )
    assert response.status_code == 201, response.text
    body = client.get(f"/analyses/{analysis_id}/current").json()
    waits = [row["Wq"] for row in body["rows"]]
    assert body["kpis"]["avg_waiting_time"] == pytest.approx(sum(waits) / len(waits))
