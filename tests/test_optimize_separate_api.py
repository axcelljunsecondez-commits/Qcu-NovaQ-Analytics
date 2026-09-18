"""Separate-queue optimization workflow endpoint: dispatch, evidence, nulls."""

from __future__ import annotations

from backend.db.models import AnalysisProject, Dataset
from tests.helpers import create_user, csrf_header, login, make_sessionmaker

SAMPLES = [0.05, 0.08, 0.10, 0.12]


def _row(time, queue_id, lam, segment_id="s1", samples=SAMPLES):
    row = {"time": time, "segment_id": segment_id, "queue_id": queue_id,
           "lambda": lam, "mu": 11.0, "c": 1}
    if samples is not None:
        row["service_samples_hours"] = list(samples)
    else:
        row["variance"] = 0.001
    return row


def _workspace(db_engine, email="sep@example.com", structure="separate_queues", rows=None):
    user = create_user(db_engine, email, "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(
            user_id=user.id,
            name="Separate lanes",
            queue_setup_json={
                "queue_structure": structure,
                "fixed_server_count": 1,
                "staffing_varies_by_period": False,
                "capacity_mode": "unlimited",
                "total_system_capacity": None,
                "abandonment_mode": "not_modeled",
                "patience_rate_per_hour": None,
                "segments": [{"id": "s1", "start_time": "08:00:00",
                              "end_time": "09:00:00", "active_queue_ids": None}],
                "separate_queue_closure_policy": "drain_existing",
                "queue_ids": ["lane-a", "lane-b"] if structure == "separate_queues" else [],
            },
            setup_status="ready",
        )
        db.add(analysis)
        db.flush()
        dataset = Dataset(
            user_id=user.id,
            analysis_id=analysis.id,
            name="Lane observations",
            source_filename="lanes.csv",
            source_format="csv",
            row_count=len(rows or []),
            normalized_json=rows or [],
            validation_report_json={"ok": True, "message": "Input data is valid."},
        )
        db.add(dataset)
        db.commit()
        return analysis.id, dataset.id


def _light_rows():
    return [
        _row("08:00", "lane-a", 4.0),
        _row("08:00", "lane-b", 2.0),
        _row("09:00", "lane-a", 1.0),
        _row("09:00", "lane-b", 1.0),
    ]


def _run(client, analysis_id, body):
    return client.post(
        f"/analyses/{analysis_id}/workflow/optimize/separate",
        headers=csrf_header(client),
        json=body,
    )


def test_separate_optimize_returns_complete_schedule_with_provenance(db_engine, client):
    analysis_id, _ = _workspace(db_engine, "u@example.com", rows=_light_rows())
    login(client, "u@example.com", "pw")
    response = _run(client, analysis_id, {"target_utilization": 0.70})
    assert response.status_code == 200, response.text
    schedule = response.json()["schedule"]
    assert schedule["overall"] == "COMPLETE"
    assert schedule["evaluation_method"] == "DES_REPLICATIONS"
    assert schedule["target_utilization"] == 0.70
    assert [period["time"] for period in schedule["periods"]] == ["08:00", "09:00"]
    for period in schedule["periods"]:
        assert period["overall"] == "OPTIMAL"
        assert period["optimal_active_lanes"] is not None
        assert period["current_active_lanes"] == ["lane-a", "lane-b"]
        assert period["replication_seeds"] == [42, 43, 44, 45, 46]
        for candidate in period["candidates"]:
            trace = candidate["evidence"]["representative_trace"]
            assert trace["events"] is None
            assert trace["events_omitted"] is True
    assert schedule["des"]["replications"] == 5


def test_separate_optimize_rejects_shared_structure(db_engine, client):
    analysis_id, _ = _workspace(
        db_engine, "u@example.com", structure="shared_queue",
        rows=[{"time": "08:00", "lambda": 30, "mu": 12, "c": 3}])
    login(client, "u@example.com", "pw")
    response = _run(client, analysis_id, {"target_utilization": 0.70})
    assert response.status_code == 422


def test_separate_optimize_target_bounds(db_engine, client):
    analysis_id, _ = _workspace(db_engine, "u@example.com", rows=_light_rows())
    login(client, "u@example.com", "pw")
    for good in (0.40, 0.70, 0.90):
        assert _run(client, analysis_id, {"target_utilization": good}).status_code == 200
    for bad in (0.39, 0.91):
        assert _run(client, analysis_id, {"target_utilization": bad}).status_code == 422


def test_separate_optimize_blocked_keeps_nulls_not_zeros(db_engine, client):
    rows = [_row("08:00", "lane-a", 4.0), _row("08:00", "lane-b", 2.0, samples=None)]
    analysis_id, _ = _workspace(db_engine, "u@example.com", rows=rows)
    login(client, "u@example.com", "pw")
    response = _run(client, analysis_id, {"target_utilization": 0.70})
    assert response.status_code == 200, response.text
    schedule = response.json()["schedule"]
    assert schedule["overall"] == "BLOCKED"
    (period,) = schedule["periods"]
    assert period["optimal_active_lanes"] is None
    assert period["adjustment"] is None


def test_separate_optimize_requires_auth(client):
    assert client.post("/analyses/1/workflow/optimize/separate",
                       json={"target_utilization": 0.70}).status_code in (401, 403)
