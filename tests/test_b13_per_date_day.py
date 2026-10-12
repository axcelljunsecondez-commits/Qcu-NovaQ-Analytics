"""B13: per-date separate-lines plans are judged and checked one continuous day per date.

Spec: docs/superpowers/specs/2026-10-12-b13-per-date-continuous-day.md (owner-approved 2026-10-12: Option B
versioning, refuse a date that cannot be laid out, keep the period runs without operating segments).
Engine-level checks live in tests/test_separate_day_feasibility.py and tests/test_b5_break_events.py.

Data: SYNTHETIC (rates, setups and plans made for the test).
"""

from __future__ import annotations

from typing import Any

from backend.api.scenarios import setup_fingerprint
from backend.api.workflow import HISTORICAL_PER_DATE_SNAPSHOT
from backend.db.models import AnalysisProject, Dataset, Scenario
from backend.queueing_engine.services.separate_optimization import (
    SEPARATE_DES_ENGINE_VERSION,
    SEPARATE_DES_PER_DATE_DAY_ENGINE_VERSION,
)
from tests.helpers import create_user, csrf_header, login, make_sessionmaker

SAMPLES = [0.05, 0.08, 0.10, 0.12]
DES_OPTIONS = {"replications": 2, "base_seed": 101, "duration_hours": 4.0, "max_events": 2000}
DATES = ("2026-09-08", "2026-09-09")
SEGMENTS = [{"id": "s1", "start_time": "08:00:00", "end_time": "09:00:00", "active_queue_ids": None},
            {"id": "s2", "start_time": "09:00:00", "end_time": "10:00:00", "active_queue_ids": None}]


def _setup(basis: str) -> dict[str, Any]:
    return {
        "queue_structure": "separate_queues", "fixed_server_count": 2, "staffing_varies_by_period": False,
        "capacity_mode": "unlimited", "total_system_capacity": None, "abandonment_mode": "not_modeled",
        "patience_rate_per_hour": None, "segments": SEGMENTS, "separate_queue_closure_policy": "drain_existing",
        "queue_ids": ["lane-a", "lane-b"], "breaks": [], "event_period_basis": basis,
    }


def _rows(basis: str) -> list[dict[str, Any]]:
    labels = ([f"{date} {segment['id']} UTC" for date in DATES for segment in SEGMENTS] if basis == "per_date"
              else [str(segment["id"]) for segment in SEGMENTS])
    return [{"time": label, "segment_id": label.split(" ")[1] if basis == "per_date" else label,
             "queue_id": queue_id, "lambda": 3.0, "mu": 11.0, "c": 1, "service_samples_hours": list(SAMPLES)}
            for label in labels for queue_id in ("lane-a", "lane-b")]


def _workspace(db_engine, basis: str, email: str = "owner@example.com") -> tuple[int, int, int]:
    user = create_user(db_engine, email, "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(user_id=user.id, name="Lanes", queue_setup_json=_setup(basis), setup_status="ready")
        db.add(analysis)
        db.flush()
        rows = _rows(basis)
        dataset = Dataset(user_id=user.id, analysis_id=analysis.id, name="Lanes", source_filename="lanes.csv",
                          source_format="csv", row_count=len(rows), normalized_json=rows,
                          validation_report_json={"ok": True, "message": "Input data is valid."})
        db.add(dataset)
        db.commit()
        return analysis.id, dataset.id, len(rows)


def _optimize(client, analysis_id: int):
    response = client.post(f"/analyses/{analysis_id}/workflow/optimize/separate", headers=csrf_header(client),
                           json={"target_utilization": 0.85, "des": dict(DES_OPTIONS)})
    assert response.status_code == 200, response.text
    return response.json()


def _settings(analysis_id: int, dataset_id: int, row_count: int, engine_version: str) -> dict[str, Any]:
    options = {"target_utilization": 0.85, "server_cost_per_hr": 87.0, "customer_waiting_cost": 100.0,
               "min_active_lanes": 2, "max_active_lanes": None, "lambda_multiplier": 1.0, "des": dict(DES_OPTIONS)}
    return {**options, "calculation": {
        "schema_version": 2, "engine_version": engine_version, "analysis_id": analysis_id, "dataset_id": dataset_id,
        "dataset_row_count": row_count, "options": options, "calculated_at": "2026-10-12T00:00:00+00:00"}}


def _save(client, analysis_id: int, dataset_id: int, settings: dict, schedule: dict):
    return client.post("/scenarios", headers=csrf_header(client), json={
        "name": "Plan", "analysis_id": analysis_id, "dataset_id": dataset_id, "settings": settings,
        "results": {"schedule": schedule}})


def test_per_date_optimization_reports_the_continuous_day_version_and_saves_with_it(db_engine, client):
    analysis_id, dataset_id, rows = _workspace(db_engine, "per_date")
    login(client, "owner@example.com", "pw")
    out = _optimize(client, analysis_id)
    assert out["engine_version"] == SEPARATE_DES_PER_DATE_DAY_ENGINE_VERSION
    assert out["schedule"]["utilization_basis"] == "continuous-day DES"
    assert [p["time"] for p in out["schedule"]["periods"]] == [f"{d} {s['id']} UTC" for d in DATES for s in SEGMENTS]
    old = _save(client, analysis_id, dataset_id, _settings(analysis_id, dataset_id, rows, SEPARATE_DES_ENGINE_VERSION),
                out["schedule"])
    assert old.status_code == 422
    saved = _save(client, analysis_id, dataset_id, _settings(analysis_id, dataset_id, rows, out["engine_version"]),
                  out["schedule"])
    assert saved.status_code == 201, saved.text


def test_representative_day_plans_keep_version_two(db_engine, client):
    analysis_id, dataset_id, rows = _workspace(db_engine, "representative_day")
    login(client, "owner@example.com", "pw")
    out = _optimize(client, analysis_id)
    assert out["engine_version"] == SEPARATE_DES_ENGINE_VERSION
    saved = _save(client, analysis_id, dataset_id, _settings(analysis_id, dataset_id, rows, SEPARATE_DES_ENGINE_VERSION),
                  out["schedule"])
    assert saved.status_code == 201, saved.text
    scenario = client.get(f"/analyses/{analysis_id}/scenarios").json()["scenarios"][0]
    assert scenario["evidence_status"] == "CURRENT"


def _insert_plan(db_engine, analysis_id: int, dataset_id: int, rows: int, engine_version: str, schedule: dict) -> int:
    with make_sessionmaker(db_engine)() as db:
        analysis = db.get(AnalysisProject, analysis_id)
        settings = _settings(analysis_id, dataset_id, rows, engine_version)
        settings["calculation"]["setup_hash"] = setup_fingerprint(analysis.queue_setup_json)
        scenario = Scenario(user_id=analysis.user_id, analysis_id=analysis_id, dataset_id=dataset_id, name="Before B13",
                            settings_json=settings, results_json={"schedule": schedule})
        db.add(scenario)
        db.commit()
        return scenario.id


def test_a_per_date_plan_saved_before_b13_must_be_recalculated(db_engine, client):
    analysis_id, dataset_id, rows = _workspace(db_engine, "per_date")
    login(client, "owner@example.com", "pw")
    schedule = _optimize(client, analysis_id)["schedule"]
    old_id = _insert_plan(db_engine, analysis_id, dataset_id, rows, SEPARATE_DES_ENGINE_VERSION, schedule)
    scenario = next(s for s in client.get(f"/analyses/{analysis_id}/scenarios").json()["scenarios"] if s["id"] == old_id)
    assert scenario["evidence_status"] == "HISTORICAL_REQUIRES_RECALCULATION"
    assert any(HISTORICAL_PER_DATE_SNAPSHOT in (reason.get("detail") or "") for reason in scenario["evidence_reasons"])
    selection = client.post(f"/analyses/{analysis_id}/workflow/selection", headers=csrf_header(client),
                            json={"scenario_id": old_id})
    assert selection.status_code != 200


def test_the_selected_per_date_plan_runs_one_day_per_date(db_engine, client):
    analysis_id, dataset_id, rows = _workspace(db_engine, "per_date")
    login(client, "owner@example.com", "pw")
    out = _optimize(client, analysis_id)
    saved = _save(client, analysis_id, dataset_id, _settings(analysis_id, dataset_id, rows, out["engine_version"]),
                  out["schedule"]).json()["scenario"]
    assert client.post(f"/analyses/{analysis_id}/workflow/selection", headers=csrf_header(client),
                       json={"scenario_id": saved["id"]}).status_code == 200
    run = client.post(f"/analyses/{analysis_id}/workflow/simulation/des/selected", headers=csrf_header(client),
                      json={"seed": 7})
    assert run.status_code == 200, run.text
    result = run.json()["evidence"]["result"]
    assert result["execution"].startswith("selected-plan continuous-day")
    assert [day["date"] for day in result["days"]] == list(DATES)
    assert result["admitted"] == sum(day["admitted"] for day in result["days"])
    assert result["served"] == sum(day["served"] for day in result["days"])
    assert result["summary"]["basis"] == "continuous_day"
    assert [p["start_hours"] for p in result["periods"]] == [0.0, 1.0, 0.0, 1.0]
    # Equal inputs on both dates, yet each date is its own random sample (date_seed).
    arrivals = [[row["arrivals"] for row in p["results"]] for p in result["periods"]]
    assert arrivals[:2] != arrivals[2:]
