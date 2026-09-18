"""Problem 7B: separate validation backed by persisted Current-MC evidence.

No optimized scenario exists or is fabricated on this path. Required rows are
Current analytical (time, queue_id) entities; verdicts aggregate per frozen
precedence (any FAIL -> fail; else any inadequate/missing -> insufficient;
else PASS) with no pooled rates.
"""
from __future__ import annotations

from backend.api.workflow import _separate_validation_verdict
from tests.helpers import create_user, csrf_header, login


def _setup(queue_ids):
    return {
        "queue_structure": "separate_queues",
        "fixed_server_count": 1,
        "staffing_varies_by_period": False,
        "capacity_mode": "unlimited",
        "total_system_capacity": None,
        "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None,
        "segments": [{"id": "s1", "start_time": "07:00:00", "end_time": "08:00:00", "active_queue_ids": None}],
        "separate_queue_closure_policy": "drain_existing",
        "queue_ids": queue_ids,
    }


def _mc_row(time, queue, rate=0.01, adequate=True, supported=True):
    return {"time": time, "queue_id": queue, "lambda": 4.0, "mu": 6.0, "c": 1,
            "selected_model": "Parallel M/G/1", "simulation_supported": supported,
            "failure_rate": rate, "mc_failure_rate_adequate": adequate}


def test_verdict_fail_overrides_passing_queues():
    verdict = _separate_validation_verdict(
        [("10:00", "cashier-east"), ("10:00", "express"), ("10:00", "lane_03")],
        {("10:00", "cashier-east"): _mc_row("10:00", "cashier-east"),
         ("10:00", "express"): _mc_row("10:00", "express", rate=0.40),
         ("10:00", "lane_03"): _mc_row("10:00", "lane_03")},
        0.05,
    )
    assert verdict["status"] == "fail"
    assert verdict["failed"] == [("10:00", "express")]


def test_verdict_insufficient_without_any_fail():
    verdict = _separate_validation_verdict(
        [("10:00", "cashier-east"), ("10:00", "express")],
        {("10:00", "cashier-east"): _mc_row("10:00", "cashier-east"),
         ("10:00", "express"): _mc_row("10:00", "express", rate=None, adequate=False)},
        0.05,
    )
    assert verdict["status"] == "insufficient"
    assert verdict["status"] != "pass"


def test_verdict_pass_requires_every_row():
    verdict = _separate_validation_verdict(
        [("10:00", "cashier-east"), ("10:00", "express")],
        {("10:00", "cashier-east"): _mc_row("10:00", "cashier-east"),
         ("10:00", "express"): _mc_row("10:00", "express", rate=0.02)},
        0.05,
    )
    assert verdict["status"] == "pass"


def test_verdict_missing_row_is_insufficient():
    verdict = _separate_validation_verdict(
        [("10:00", "cashier-east"), ("10:00", "express")],
        {("10:00", "cashier-east"): _mc_row("10:00", "cashier-east")},
        0.05,
    )
    assert verdict["status"] == "insufficient"


def _workspace_with_mc(client, headers, queue_ids=("cashier-east", "express")):
    analysis_id = client.post(
        "/analyses", headers=headers,
        json={"name": "Validate lanes", "queue_setup": _setup(list(queue_ids))},
    ).json()["analysis"]["id"]
    rows = []
    for queue in queue_ids:
        rows.append(f"2026-09-08T07:05:00Z,2026-09-08T07:06:00Z,2026-09-08T07:12:00Z,{queue}")
    events = ("arrival_time,service_start,service_end,queue_id\n" + "\n".join(rows) + "\n").encode()
    uploaded = client.post(
        f"/analyses/{analysis_id}/datasets", headers=headers,
        files={"file": ("events.csv", events, "text/csv")},
    )
    assert uploaded.status_code == 201, uploaded.text
    mc = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/mc/current",
        headers=headers,
        json={"num_trials": 200, "failure_threshold": 0.8, "failure_rate_cap": 0.05, "seed": 7},
    )
    assert mc.status_code == 200, mc.text
    return analysis_id


def test_validation_current_pass_end_to_end(db_engine, client):
    create_user(db_engine, "val@example.com", "pw")
    login(client, "val@example.com", "pw")
    headers = csrf_header(client)
    analysis_id = _workspace_with_mc(client, headers)
    run = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/validation/current", headers=headers, json={},
    )
    assert run.status_code == 200, run.text
    result = run.json()["evidence"]["result"]
    assert result["provenance"] == "CURRENT"
    # Light loads never fail; adequacy of a 200-trial run is engine-determined.
    assert result["verdict"]["status"] in ("pass", "insufficient")
    assert result["verdict"]["failed"] == []
    assert {row["queue_id"] for row in result["results"]} == {"cashier-east", "express"}
    assert "scenario_id" not in result
    # Persisted and reloadable without rerunning.
    workflow = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert workflow["validation_current"]["result"]["verdict"]["status"] in ("pass", "insufficient")


def test_validation_current_creates_no_scenario(db_engine, client):
    create_user(db_engine, "val@example.com", "pw")
    login(client, "val@example.com", "pw")
    headers = csrf_header(client)
    analysis_id = _workspace_with_mc(client, headers)
    client.post(
        f"/analyses/{analysis_id}/workflow/simulation/validation/current", headers=headers, json={},
    )
    scenarios = client.get(f"/analyses/{analysis_id}/scenarios").json()["scenarios"]
    assert scenarios == []


def test_validation_current_requires_mc_evidence(db_engine, client):
    create_user(db_engine, "val@example.com", "pw")
    login(client, "val@example.com", "pw")
    headers = csrf_header(client)
    analysis_id = client.post(
        "/analyses", headers=headers,
        json={"name": "No MC", "queue_setup": _setup(["cashier-east"])},
    ).json()["analysis"]["id"]
    run = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/validation/current", headers=headers, json={},
    )
    assert run.status_code == 404, run.text


def test_validation_current_rejects_shared_analyses(db_engine, client):
    create_user(db_engine, "val@example.com", "pw")
    login(client, "val@example.com", "pw")
    headers = csrf_header(client)
    analysis_id = client.post(
        "/analyses", headers=headers,
        json={"name": "Shared", "queue_setup": {
            "queue_structure": "shared_queue", "fixed_server_count": 2,
            "staffing_varies_by_period": False, "capacity_mode": "unlimited",
            "total_system_capacity": None, "abandonment_mode": "not_modeled",
            "patience_rate_per_hour": None, "segments": [],
            "separate_queue_closure_policy": "drain_existing", "queue_ids": [],
        }},
    ).json()["analysis"]["id"]
    run = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/validation/current", headers=headers, json={},
    )
    assert run.status_code == 422, run.text


def test_stale_mc_evidence_cannot_validate(db_engine, client):
    create_user(db_engine, "val@example.com", "pw")
    login(client, "val@example.com", "pw")
    headers = csrf_header(client)
    analysis_id = _workspace_with_mc(client, headers, queue_ids=("cashier-east",))
    events = (b"arrival_time,service_start,service_end,queue_id\n"
              b"2026-09-08T07:05:00Z,2026-09-08T07:06:00Z,2026-09-08T07:12:00Z,cashier-east\n")
    replaced = client.post(
        f"/analyses/{analysis_id}/datasets", headers=headers,
        files={"file": ("events2.csv", events, "text/csv")},
    )
    assert replaced.status_code == 201, replaced.text
    run = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/validation/current", headers=headers, json={},
    )
    assert run.status_code == 409, run.text
    assert "stale" in run.json()["detail"].lower()


def test_current_validation_rejects_mc_without_current_setup_hash(db_engine, client):
    from backend.db.models import Job
    from tests.helpers import make_sessionmaker

    create_user(db_engine, "hash@example.com", "pw")
    login(client, "hash@example.com", "pw")
    headers = csrf_header(client)
    analysis_id = _workspace_with_mc(client, headers)
    with make_sessionmaker(db_engine)() as db:
        job = db.query(Job).filter_by(kind="workflow_mc_current").one()
        job.params_json = {**job.params_json, "setup_hash": "0" * 64}
        db.commit()
    run = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/validation/current", headers=headers, json={},
    )
    assert run.status_code == 409, run.text
    assert run.json()["detail"] == "Setup changed since this evidence was produced. Rerun Simulation."
    workflow = client.get(f"/analyses/{analysis_id}/workflow", headers=headers).json()
    assert workflow["mc_current"] is None
