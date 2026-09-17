"""Problem 9 audit probes: dataset replacement vs workflow evidence freshness.

Classification under test (see report, not code changes):
- Shared scenario-pinned evidence stays self-consistent for Dataset A
  (SAFE HISTORICAL): jobs reference scenario/dataset A explicitly.
- Current-kind jobs (des_current/mc_current/validation_current) keep returning
  the latest job even after a new upload (STALE-VISIBLE, P2): displayed but
  not consumable as fresh evidence (validation_current refuses stale MC).
- Decision never mixes datasets: it derives from explicitly referenced jobs.

Distinct lambdas (4 vs 14) fingerprint which dataset produced each result.
"""
from __future__ import annotations

from backend.db.models import AnalysisProject, Dataset, Scenario
from tests.helpers import create_user, csrf_header, login, make_sessionmaker


def _shared_setup():
    return {
        "queue_structure": "shared_queue", "fixed_server_count": 2,
        "staffing_varies_by_period": False, "capacity_mode": "unlimited",
        "total_system_capacity": None, "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None, "segments": [], "queue_ids": [],
    }


def _upload(client, analysis_id, headers, lam, name="data.csv"):
    payload = f"time,lambda,mu,c\n08:00-09:00,{lam},12,2\n".encode()
    response = client.post(
        f"/analyses/{analysis_id}/datasets", headers=headers,
        files={"file": (name, payload, "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()["dataset"]["id"]


def _seed_shared_scenario(db_engine, user_id, analysis_id, dataset_id):
    """Seed an operationally complete shared scenario pinned to a dataset.

    Mirrors the repository's own workflow fixtures: selection verifies
    ownership, dataset health, and row completeness, not recomputation.
    """
    with make_sessionmaker(db_engine)() as db:
        scenario = Scenario(
            user_id=user_id,
            analysis_id=analysis_id,
            dataset_id=dataset_id,
            name="Plan A",
            settings_json={"calculation": {
                "engine_version": "novaq-test",
                "input_segments": [{"time": "08:00-09:00", "lambda": 4, "mu": 12, "c": 2}],
            }},
            results_json={"results": [{
                "time": "08:00-09:00", "lambda_": 4.0, "mu": 12.0,
                "c_current": 2, "c_optimal": 2,
                "rho_current": 0.1667, "rho_optimal": 0.1667,
                "Wq_current": 0.01, "Wq_optimal": 0.01,
                "Lq_current": 0.04, "Lq_optimal": 0.04,
                "cost_current": 200, "cost_optimal": 200,
                "current_stable": True, "optimized_stable": True,
            }]},
        )
        db.add(scenario)
        db.commit()
        return scenario.id


def test_shared_scenario_evidence_stays_pinned_to_dataset_a(db_engine, client):
    user = create_user(db_engine, "stale@example.com", "pw")
    login(client, "stale@example.com", "pw")
    headers = csrf_header(client)
    analysis_id = client.post(
        "/analyses", headers=headers,
        json={"name": "Shop", "queue_setup": _shared_setup()},
    ).json()["analysis"]["id"]
    dataset_a = _upload(client, analysis_id, headers, 4, "a.csv")
    scenario_id = _seed_shared_scenario(db_engine, user.id, analysis_id, dataset_a)
    selected = client.post(
        f"/analyses/{analysis_id}/workflow/selection", headers=headers,
        json={"scenario_id": scenario_id},
    )
    assert selected.status_code == 200, selected.text
    des = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des", headers=headers,
        json={"sim_hours": 1, "max_events": 50},
    )
    assert des.status_code == 200, des.text
    dataset_b = _upload(client, analysis_id, headers, 14, "b.csv")
    assert dataset_b != dataset_a
    workflow = client.get(f"/analyses/{analysis_id}/workflow").json()
    # The scenario still references Dataset A explicitly: historical, consistent.
    assert workflow["scenario"]["id"] == scenario_id
    # The DES job still references the Dataset-A scenario run, not Dataset B.
    assert workflow["des"]["params"]["scenario_id"] == scenario_id
    assert workflow["des"]["params"]["dataset_id"] != dataset_b
    # Current dataset pointer moved to B.
    current = client.get(f"/analyses/{analysis_id}/current").json()
    assert current["dataset"]["id"] == dataset_b
    assert current["rows"][0]["lambda"] == 14


def _separate_setup(queue_ids):
    return {
        "queue_structure": "separate_queues", "fixed_server_count": 1,
        "staffing_varies_by_period": False, "capacity_mode": "unlimited",
        "total_system_capacity": None, "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None,
        "segments": [{"id": "s1", "start_time": "07:00:00", "end_time": "08:00:00", "active_queue_ids": None}],
        "separate_queue_closure_policy": "drain_existing",
        "queue_ids": queue_ids,
    }


def _events(north_count, south_count=1):
    lines = ["arrival_time,service_start,service_end,queue_id"]
    for index in range(north_count):
        minute = 5 + index
        lines.append(
            f"2026-09-08T07:{minute:02d}:00Z,2026-09-08T07:{minute:02d}:30Z,"
            f"2026-09-08T07:{minute + 5:02d}:00Z,north"
        )
    for index in range(south_count):
        minute = 10 + index
        lines.append(
            f"2026-09-08T07:{minute:02d}:00Z,2026-09-08T07:{minute:02d}:30Z,"
            f"2026-09-08T07:{minute + 5:02d}:00Z,south"
        )
    return ("\n".join(lines) + "\n").encode()


def _upload_events(client, analysis_id, headers, north_count, name="e.csv"):
    response = client.post(
        f"/analyses/{analysis_id}/datasets", headers=headers,
        files={"file": (name, _events(north_count), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()["dataset"]["id"]


def test_separate_current_jobs_stay_visible_after_replacement(db_engine, client):
    create_user(db_engine, "stale@example.com", "pw")
    login(client, "stale@example.com", "pw")
    headers = csrf_header(client)
    analysis_id = client.post(
        "/analyses", headers=headers,
        json={"name": "Lanes", "queue_setup": _separate_setup(["north", "south"])},
    ).json()["analysis"]["id"]
    dataset_a = _upload_events(client, analysis_id, headers, 2, "a.csv")
    for kind, payload in (
        ("des", {"sim_hours": 1, "max_events": 100}),
        ("mc", {"num_trials": 50, "failure_threshold": 0.8, "failure_rate_cap": 0.5, "seed": 7}),
    ):
        run = client.post(
            f"/analyses/{analysis_id}/workflow/simulation/{kind}/current", headers=headers, json=payload,
        )
        assert run.status_code == 200, run.text
    old_des = client.get(f"/analyses/{analysis_id}/workflow").json()["des_current"]["id"]
    dataset_b = _upload_events(client, analysis_id, headers, 6, "b.csv")
    assert dataset_b != dataset_a
    workflow = client.get(f"/analyses/{analysis_id}/workflow").json()
    # Old jobs are still returned (STALE-VISIBLE): they reference Dataset A.
    assert workflow["des_current"]["id"] == old_des
    assert workflow["des_current"]["params"]["dataset_id"] == dataset_a
    assert workflow["mc_current"]["params"]["dataset_id"] == dataset_a
    # Numerical fingerprint: old DES rows carry Dataset-A lambdas (2 north
    # arrivals/hour), while Current moved to Dataset B (6 north arrivals/hour).
    old_lambdas = {row["lambda"] for row in workflow["des_current"]["result"]["results"]}
    assert old_lambdas == {2.0, 1.0}
    # But Current itself moved to Dataset B.
    current = client.get(f"/analyses/{analysis_id}/current").json()
    assert current["dataset"]["id"] == dataset_b
    current_lambdas = {row["lambda"] for row in current["rows"]}
    assert current_lambdas == {6.0, 1.0}


def test_separate_decision_after_replacement_stays_insufficient(db_engine, client):
    create_user(db_engine, "stale@example.com", "pw")
    login(client, "stale@example.com", "pw")
    headers = csrf_header(client)
    analysis_id = client.post(
        "/analyses", headers=headers,
        json={"name": "Lanes", "queue_setup": _separate_setup(["north", "south"])},
    ).json()["analysis"]["id"]
    _upload_events(client, analysis_id, headers, 2, "a.csv")
    _upload_events(client, analysis_id, headers, 6, "b.csv")
    decision = client.post(f"/analyses/{analysis_id}/workflow/decision", headers=headers)
    assert decision.status_code == 200, decision.text
    assert decision.json()["decision"]["status"] == "insufficient_evidence"


def test_historical_dataset_report_stays_available_after_replacement(db_engine, client):
    """Explicitly ID-scoped historical export keeps working after replacement."""
    create_user(db_engine, "stale@example.com", "pw")
    login(client, "stale@example.com", "pw")
    headers = csrf_header(client)
    analysis_id = client.post(
        "/analyses", headers=headers,
        json={"name": "Shop", "queue_setup": _shared_setup()},
    ).json()["analysis"]["id"]
    dataset_a = _upload(client, analysis_id, headers, 4, "a.csv")
    _upload(client, analysis_id, headers, 14, "b.csv")
    report = client.get(f"/reports/datasets/{dataset_a}/pdf")
    assert report.status_code == 200
    assert report.content[:4] == b"%PDF"
