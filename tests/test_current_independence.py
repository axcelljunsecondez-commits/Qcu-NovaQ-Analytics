"""Problem 1: separate queues stay independent entities in Current Analysis.

Each (time, queue_id) row must be evaluated on its own inputs through the
central model-selection service. Nothing here may pool separate queues into
a shared lambda-total/c-total entity. Uses deliberately asymmetric inputs:
equal-split values could hide accidental aggregation.
"""
from __future__ import annotations

import pytest

from backend.queueing_engine.services.model_selection import select_model
from tests.helpers import create_user, csrf_header, login


def _setup(structure="separate_queues", queue_ids=None):
    return {
        "queue_structure": structure,
        "fixed_server_count": 2,
        "staffing_varies_by_period": False,
        "capacity_mode": "unlimited",
        "total_system_capacity": None,
        "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None,
        "segments": [],
        "queue_ids": queue_ids if queue_ids is not None else [],
    }


def _make_analysis(client, name, queue_ids):
    response = client.post(
        "/analyses",
        headers=csrf_header(client),
        json={"name": name, "queue_setup": _setup(queue_ids=queue_ids)},
    )
    assert response.status_code == 201, response.text
    return response.json()["analysis"]["id"]


def _upload(client, analysis_id, rows):
    lines = ["time,queue_id,lambda,mu,c,variance"]
    lines += [f"{time},{queue},{lam},{mu},{c},{var}" for time, queue, lam, mu, c, var in rows]
    response = client.post(
        f"/analyses/{analysis_id}/datasets",
        headers=csrf_header(client),
        files={"file": ("input.csv", ("\n".join(lines) + "\n").encode(), "text/csv")},
    )
    assert response.status_code == 201, response.text


def _current(client, analysis_id):
    response = client.get(f"/analyses/{analysis_id}/current")
    assert response.status_code == 200, response.text
    return response.json()


ASYMMETRIC = [
    ("08:00-09:00", "Q_A", 2, 10, 1, 0.001),
    ("08:00-09:00", "Q_B", 7, 12, 1, 0.004),
    ("08:00-09:00", "Q_C", 4, 9, 1, 0.008),
]


def test_asymmetric_queues_produce_independent_results(db_engine, client):
    """CASE A/B: three queues, one period -> three identifiable results."""
    create_user(db_engine, "p1@example.com", "pw")
    login(client, "p1@example.com", "pw")
    analysis_id = _make_analysis(client, "Asymmetric", ["Q_A", "Q_B", "Q_C"])
    _upload(client, analysis_id, ASYMMETRIC)
    body = _current(client, analysis_id)
    assert len(body["rows"]) == 3
    by_queue = {row["queue_id"]: row for row in body["rows"]}
    assert set(by_queue) == {"Q_A", "Q_B", "Q_C"}
    assert (by_queue["Q_A"]["lambda"], by_queue["Q_A"]["mu"]) == (2, 10)
    assert (by_queue["Q_B"]["lambda"], by_queue["Q_B"]["mu"]) == (7, 12)
    assert (by_queue["Q_C"]["lambda"], by_queue["Q_C"]["mu"]) == (4, 9)
    for row in body["rows"]:
        assert row["c"] == 1
        assert row["queue_structure"] == "separate_queues"
    # Per-queue outputs track per-queue inputs (rho = lambda/mu for M/G/1;
    # approximate: the engine reaches rho through its own float path).
    assert by_queue["Q_A"]["rho"] == pytest.approx(2 / 10)
    assert by_queue["Q_B"]["rho"] == pytest.approx(7 / 12)
    assert by_queue["Q_C"]["rho"] == pytest.approx(4 / 9)


def test_central_selector_used_per_queue_without_inline_dispatch(db_engine, client):
    """MODEL-SELECTION PROOF: each row matches the central selector's own answer."""
    create_user(db_engine, "p1@example.com", "pw")
    login(client, "p1@example.com", "pw")
    analysis_id = _make_analysis(client, "Selector", ["Q_A", "Q_B", "Q_C"])
    _upload(client, analysis_id, ASYMMETRIC)
    body = _current(client, analysis_id)
    for time, queue, lam, mu, c, var in ASYMMETRIC:
        expected = select_model(lam, mu, c, variance=var, queue_structure="separate_queues")
        row = next(r for r in body["rows"] if r["queue_id"] == queue)
        assert row["model"] == expected["name"]
        assert row["model_id"] == expected["model_id"] == "parallel_mg1"


def test_no_shared_lambda_or_server_total_is_analyzed(db_engine, client):
    """CASE C: no result row carries pooled lambda=13 or c=3."""
    create_user(db_engine, "p1@example.com", "pw")
    login(client, "p1@example.com", "pw")
    analysis_id = _make_analysis(client, "NoPool", ["Q_A", "Q_B", "Q_C"])
    _upload(client, analysis_id, ASYMMETRIC)
    body = _current(client, analysis_id)
    assert all(row["lambda"] != 2 + 7 + 4 for row in body["rows"])
    assert all(row["c"] != 3 for row in body["rows"])
    assert all(row["model_id"] == "parallel_mg1" for row in body["rows"])


def test_varying_active_queues_by_period_without_synthetic_rows(db_engine, client):
    """CASE D: P1 has 2 queues, P2 has 4; absence creates no lambda=0 rows."""
    create_user(db_engine, "p1@example.com", "pw")
    login(client, "p1@example.com", "pw")
    analysis_id = _make_analysis(client, "Periods", ["Q1", "Q2", "Q3", "Q4"])
    _upload(client, analysis_id, [
        ("05:00-06:00", "Q1", 4, 6, 1, 0.02),
        ("05:00-06:00", "Q2", 5, 6, 1, 0.02),
        ("06:00-07:00", "Q1", 4, 6, 1, 0.02),
        ("06:00-07:00", "Q2", 5, 6, 1, 0.02),
        ("06:00-07:00", "Q3", 6, 6, 1, 0.02),
        ("06:00-07:00", "Q4", 3, 6, 1, 0.02),
    ])
    body = _current(client, analysis_id)
    assert len(body["rows"]) == 6
    early = {row["queue_id"] for row in body["rows"] if row["time"] == "05:00-06:00"}
    late = {row["queue_id"] for row in body["rows"] if row["time"] == "06:00-07:00"}
    assert early == {"Q1", "Q2"}
    assert late == {"Q1", "Q2", "Q3", "Q4"}
    assert all(row["lambda"] > 0 for row in body["rows"])


def test_arbitrary_queue_ids_preserved_to_results(db_engine, client):
    """CASE E: non-pattern names survive to identifiable result rows."""
    create_user(db_engine, "p1@example.com", "pw")
    login(client, "p1@example.com", "pw")
    ids = ["cashier-east", "express", "lane_03"]
    analysis_id = _make_analysis(client, "Names", ids)
    _upload(client, analysis_id, [
        ("08:00-09:00", "cashier-east", 4, 6, 1, 0.02),
        ("08:00-09:00", "express", 5, 7, 1, 0.03),
        ("08:00-09:00", "lane_03", 6, 8, 1, 0.04),
    ])
    body = _current(client, analysis_id)
    assert {row["queue_id"] for row in body["rows"]} == set(ids)


def test_variance_consumed_per_queue_not_pooled(db_engine, client):
    """CASE G: same lambda/mu but different variance -> different waits."""
    create_user(db_engine, "p1@example.com", "pw")
    login(client, "p1@example.com", "pw")
    analysis_id = _make_analysis(client, "Variance", ["Q1", "Q2"])
    _upload(client, analysis_id, [
        ("08:00-09:00", "Q1", 4, 6, 1, 0.002),
        ("08:00-09:00", "Q2", 4, 6, 1, 0.020),
    ])
    body = _current(client, analysis_id)
    by_queue = {row["queue_id"]: row for row in body["rows"]}
    assert by_queue["Q1"]["Wq"] != by_queue["Q2"]["Wq"]
    assert by_queue["Q2"]["Wq"] > by_queue["Q1"]["Wq"]
    assert all(row["model_id"] == "parallel_mg1" for row in body["rows"])


def test_shared_queue_path_unchanged(db_engine, client):
    """CASE F: shared analysis still yields queue-less M/M/c rows."""
    create_user(db_engine, "p1@example.com", "pw")
    login(client, "p1@example.com", "pw")
    response = client.post(
        "/analyses",
        headers=csrf_header(client),
        json={"name": "Shared", "queue_setup": _setup(structure="shared_queue")},
    )
    assert response.status_code == 201, response.text
    analysis_id = response.json()["analysis"]["id"]
    upload = client.post(
        f"/analyses/{analysis_id}/datasets",
        headers=csrf_header(client),
        files={"file": ("input.csv", b"time,lambda,mu,c\n08:00-09:00,20,12,2\n", "text/csv")},
    )
    assert upload.status_code == 201, upload.text
    body = _current(client, analysis_id)
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["queue_id"] is None
    assert row["model"] == "M/M/c"
    assert row["lambda"] == 20


def test_unstable_queue_outputs_stay_null(db_engine, client):
    """CASE H: an overloaded queue reports rho without zero-filled waits."""
    create_user(db_engine, "p1@example.com", "pw")
    login(client, "p1@example.com", "pw")
    analysis_id = _make_analysis(client, "Unstable", ["Q1"])
    _upload(client, analysis_id, [("08:00-09:00", "Q1", 9, 6, 1, 0.004)])
    body = _current(client, analysis_id)
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["queue_id"] == "Q1"
    assert row["stable"] is False
    assert row["rho"] == pytest.approx(9 / 6)
    assert row["Wq"] is None
    assert row["Lq"] is None


def test_duplicate_period_pair_merges_into_one_observation(db_engine, client):
    """Duplicate (time, queue_id) contract: combined, never double-counted."""
    create_user(db_engine, "p1@example.com", "pw")
    login(client, "p1@example.com", "pw")
    analysis_id = _make_analysis(client, "Dupes", ["Q1"])
    _upload(client, analysis_id, [
        ("08:00-09:00", "Q1", 2, 6, 1, 0.02),
        ("08:00-09:00", "Q1", 3, 6, 1, 0.02),
    ])
    body = _current(client, analysis_id)
    assert len(body["rows"]) == 1
    assert body["rows"][0]["lambda"] == 5
