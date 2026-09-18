"""Separate-queue optimal-plan persistence: verified save, reload, immutability."""

from __future__ import annotations

from backend.db.models import AnalysisProject, Dataset
from backend.queueing_engine.services.separate_optimization import (
    SEPARATE_DES_ENGINE_VERSION,
)
from tests.helpers import create_user, csrf_header, login, make_sessionmaker

SAMPLES = [0.05, 0.08, 0.10, 0.12]
CALCULATED_AT = "2026-09-18T00:00:00+00:00"
DES_OPTIONS = {"replications": 2, "base_seed": 101, "duration_hours": 4.0, "max_events": 500}


def _row(time, queue_id, lam):
    return {"time": time, "segment_id": "s1", "queue_id": queue_id,
            "lambda": lam, "mu": 11.0, "c": 1, "service_samples_hours": list(SAMPLES)}


def _workspace(db_engine, email):
    rows = [_row("08:00", "lane-a", 4.0), _row("08:00", "lane-b", 2.0),
            _row("09:00", "lane-a", 1.0), _row("09:00", "lane-b", 1.0)]
    user = create_user(db_engine, email, "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(
            user_id=user.id,
            name="Separate lanes",
            queue_setup_json={
                "queue_structure": "separate_queues",
                "fixed_server_count": 1,
                "staffing_varies_by_period": False,
                "capacity_mode": "unlimited",
                "total_system_capacity": None,
                "abandonment_mode": "not_modeled",
                "patience_rate_per_hour": None,
                "segments": [{"id": "s1", "start_time": "08:00:00",
                              "end_time": "09:00:00", "active_queue_ids": None}],
                "separate_queue_closure_policy": "drain_existing",
                "queue_ids": ["lane-a", "lane-b"],
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
            row_count=len(rows),
            normalized_json=rows,
            validation_report_json={"ok": True, "message": "Input data is valid."},
        )
        db.add(dataset)
        db.commit()
        return analysis.id, dataset.id, len(rows)


def _run(client, analysis_id, target, request_des=True):
    body = {"target_utilization": target}
    if request_des:
        body["des"] = dict(DES_OPTIONS)
    return client.post(
        f"/analyses/{analysis_id}/workflow/optimize/separate",
        headers=csrf_header(client),
        json=body,
    )


def _snapshot(analysis_id, dataset_id, row_count, target, schedule):
    options = {
        "target_utilization": target,
        "server_cost_per_hr": 87.0,
        "customer_waiting_cost": 100.0,
        "min_active_lanes": 2,  # full coverage: both configured lanes
        "max_active_lanes": None,
        "lambda_multiplier": 1.0,
        "des": dict(DES_OPTIONS),
    }
    return {
        **options,
        "calculation": {
            "schema_version": 2,
            "engine_version": SEPARATE_DES_ENGINE_VERSION,
            "analysis_id": analysis_id,
            "dataset_id": dataset_id,
            "dataset_row_count": row_count,
            "options": options,
            "calculated_at": CALCULATED_AT,
        },
    }, {"schedule": schedule}


def _save(client, name, analysis_id, dataset_id, settings, results):
    return client.post(
        "/scenarios",
        headers=csrf_header(client),
        json={"name": name, "analysis_id": analysis_id, "dataset_id": dataset_id,
              "settings": settings, "results": results},
    )


def test_save_valid_separate_plan_and_reload_unchanged(db_engine, client):
    analysis_id, dataset_id, row_count = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    run = _run(client, analysis_id, 0.70)
    assert run.status_code == 200, run.text
    assert run.json()["schedule"]["overall"] == "COMPLETE"
    settings, results = _snapshot(analysis_id, dataset_id, row_count, 0.70,
                                  run.json()["schedule"])
    saved = _save(client, "Optimal @ 70%", analysis_id, dataset_id, settings, results)
    assert saved.status_code == 201, saved.text
    scenario = saved.json()["scenario"]
    assert scenario["provenance"] == "verified_snapshot"
    reloaded = client.get(f"/scenarios/{scenario['id']}",
                          headers=csrf_header(client)).json()["scenario"]
    assert reloaded["name"] == "Optimal @ 70%"
    assert reloaded["settings"]["target_utilization"] == 0.70
    assert reloaded["results"]["schedule"]["overall"] == "COMPLETE"
    assert reloaded["results"]["schedule"]["evaluation_method"] == "DES_REPLICATIONS"
    assert reloaded["results"]["schedule"]["des"]["replications"] == 2
    assert reloaded["dataset_id"] == dataset_id


def test_save_rejects_tampered_results_and_stale_dataset(db_engine, client):
    analysis_id, dataset_id, row_count = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    schedule = _run(client, analysis_id, 0.70).json()["schedule"]
    settings, results = _snapshot(analysis_id, dataset_id, row_count, 0.70, schedule)
    tampered = {"schedule": {**schedule, "overall": "COMPLETE",
                             "periods": [{**schedule["periods"][0],
                                          "optimal_active_lanes": 99}]}}
    assert _save(client, "Tampered", analysis_id, dataset_id,
                 settings, tampered).status_code == 422
    stale_settings, _ = _snapshot(analysis_id, dataset_id, row_count + 5, 0.70, schedule)
    assert _save(client, "Stale", analysis_id, dataset_id,
                 stale_settings, results).status_code == 422


def test_runs_at_different_targets_coexist_unchanged(db_engine, client):
    analysis_id, dataset_id, row_count = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    settings70, results70 = _snapshot(analysis_id, dataset_id, row_count, 0.70,
                                      _run(client, analysis_id, 0.70).json()["schedule"])
    assert _save(client, "Optimal @ 70%", analysis_id, dataset_id,
                 settings70, results70).status_code == 201
    settings80, results80 = _snapshot(analysis_id, dataset_id, row_count, 0.80,
                                      _run(client, analysis_id, 0.80).json()["schedule"])
    assert _save(client, "Optimal @ 80%", analysis_id, dataset_id,
                 settings80, results80).status_code == 201
    listed = client.get(f"/scenarios?analysis_id={analysis_id}",
                        headers=csrf_header(client)).json()["scenarios"]
    assert len(listed) == 2
    kept = next(item for item in listed if item["name"] == "Optimal @ 70%")
    assert kept["settings"]["target_utilization"] == 0.70
    assert kept["results"]["schedule"]["target_utilization"] == 0.70
