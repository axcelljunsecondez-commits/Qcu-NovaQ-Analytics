"""Separate-Queue Comparison backend: v2 selection validity and comparison data.

Comparison consumes persisted evidence only: the current dataset/setup plus
immutable schema-v2 schedules. It never reoptimizes, never reruns DES, and
never mutates saved scenarios. Stale or incomplete plans cannot be selected.
"""
from __future__ import annotations

from backend.api.scenarios import setup_fingerprint
from backend.db.models import AnalysisProject, Dataset, Scenario, User
from backend.queueing_engine.services.separate_optimization import (
    SEPARATE_DES_ENGINE_VERSION,
)
from tests.helpers import (
    clear_cookies,
    create_user,
    csrf_header,
    login,
    make_sessionmaker,
)

SAMPLES = [0.05, 0.08, 0.10, 0.12]


def _setup(queue_ids=("lane-a", "lane-b")):
    return {
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
        "queue_ids": list(queue_ids),
    }


def _dataset_rows():
    return [
        {"time": "08:00", "segment_id": "s1", "queue_id": "lane-a",
         "lambda": 4.0, "mu": 11.0, "c": 1, "variance": 0.0009,
         "service_samples_hours": list(SAMPLES)},
        {"time": "08:00", "segment_id": "s1", "queue_id": "lane-b",
         "lambda": 2.0, "mu": 11.0, "c": 1, "variance": 0.0009,
         "service_samples_hours": list(SAMPLES)},
    ]


def _schedule(overall="COMPLETE", optimal=1):
    period = {
        "time": "08:00",
        "overall": "OPTIMAL" if overall == "COMPLETE" else "UNSUPPORTED",
        "reason": None,
        "current_active_lanes": ["lane-a", "lane-b"],
        "optimal_active_lanes": optimal if overall == "COMPLETE" else None,
        "adjustment": -1 if overall == "COMPLETE" else None,
        "optimum": {
            "active_lane_count": optimal,
            "recommendation": "REDUCE",
            "total_cost": 180.0,
            "candidate_utilization": 0.55,
            "estimated_optimal": True,
        } if overall == "COMPLETE" else None,
        "candidates": [],
        "evaluation_method": "DES_REPLICATIONS",
        "replication_seeds": [42, 43, 44, 45, 46],
        "target_utilization": 0.70,
    }
    return {"overall": overall, "reason": None, "target_utilization": 0.70,
            "evaluation_method": "DES_REPLICATIONS", "periods": [period],
            "des": {"replications": 5, "base_seed": 42,
                    "duration_hours": 24.0, "max_events": 10000}}


def _calculation(dataset_id, target=0.70):
    options = {
        "target_utilization": target,
        "server_cost_per_hr": 87.0,
        "customer_waiting_cost": 100.0,
        "min_active_lanes": None,
        "max_active_lanes": None,
        "lambda_multiplier": 1.0,
        "des": {"replications": 5, "base_seed": 42,
                "duration_hours": 24.0, "max_events": 10000},
    }
    return {
        **options,
        "calculation": {
            "schema_version": 2,
            "engine_version": SEPARATE_DES_ENGINE_VERSION,
            "dataset_id": dataset_id,
            "dataset_row_count": 2,
            "options": options,
            "calculated_at": "2026-09-18T00:00:00+00:00",
            "setup_hash": setup_fingerprint(_setup()),
        },
    }


def _workspace(db_engine, email):
    user = create_user(db_engine, email, "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(
            user_id=user.id, name="Separate lanes",
            queue_setup_json=_setup(), setup_status="ready")
        db.add(analysis)
        db.flush()
        dataset = Dataset(
            user_id=user.id, analysis_id=analysis.id, name="Lanes",
            source_filename="lanes.csv", source_format="csv", row_count=2,
            normalized_json=_dataset_rows(),
            validation_report_json={"ok": True, "message": "ok"})
        db.add(dataset)
        db.flush()
        scenario = Scenario(
            user_id=user.id, analysis_id=analysis.id, dataset_id=dataset.id,
            name="Optimal @ 70%", settings_json=_calculation(dataset.id),
            results_json={"schedule": _schedule()})
        db.add(scenario)
        db.commit()
        return analysis.id, dataset.id, scenario.id


def test_select_valid_separate_plan_persists_selection(db_engine, client):
    analysis_id, _, scenario_id = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    response = client.post(
        f"/analyses/{analysis_id}/workflow/selection",
        headers=csrf_header(client),
        json={"scenario_id": scenario_id},
    )
    assert response.status_code == 200, response.text
    workflow = client.get(f"/analyses/{analysis_id}/workflow",
                          headers=csrf_header(client)).json()
    assert workflow["scenario"]["id"] == scenario_id


def _add_scenario(db_engine, email, analysis_id, dataset_id, name, schedule, target=0.70):
    with make_sessionmaker(db_engine)() as db:
        user = db.query(User).filter_by(email=email).one()
        scenario = Scenario(
            user_id=user.id, analysis_id=analysis_id, dataset_id=dataset_id,
            name=name, settings_json=_calculation(dataset_id, target),
            results_json={"schedule": schedule})
        db.add(scenario)
        db.commit()
        return scenario.id


def _select(client, analysis_id, scenario_id):
    return client.post(
        f"/analyses/{analysis_id}/workflow/selection",
        headers=csrf_header(client),
        json={"scenario_id": scenario_id},
    )


def test_blocked_and_tampered_plans_are_not_selectable(db_engine, client):
    analysis_id, dataset_id, _ = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    blocked_id = _add_scenario(db_engine, "u@example.com", analysis_id, dataset_id,
                               "Blocked plan", _schedule(overall="BLOCKED"))
    assert _select(client, analysis_id, blocked_id).status_code == 422
    tampered = _schedule()
    tampered["periods"][0]["overall"] = "INFEASIBLE"
    tampered_id = _add_scenario(db_engine, "u@example.com", analysis_id, dataset_id,
                               "Tampered plan", tampered)
    assert _select(client, analysis_id, tampered_id).status_code == 422


def test_stale_plan_cannot_be_selected_after_dataset_change(db_engine, client):
    analysis_id, dataset_id, scenario_id = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    assert _select(client, analysis_id, scenario_id).status_code == 200
    with make_sessionmaker(db_engine)() as db:
        user = db.query(User).filter_by(email="u@example.com").one()
        newer = Dataset(
            user_id=user.id, analysis_id=analysis_id, name="Recut",
            source_filename="lanes2.csv", source_format="csv", row_count=2,
            normalized_json=_dataset_rows(),
            validation_report_json={"ok": True, "message": "ok"})
        db.add(newer)
        db.commit()
    assert _select(client, analysis_id, scenario_id).status_code == 422
    workflow = client.get(f"/analyses/{analysis_id}/workflow",
                          headers=csrf_header(client)).json()
    assert workflow["scenario"] is None


def _comparison(client, analysis_id):
    return client.get(
        f"/analyses/{analysis_id}/workflow/comparison/separate",
        headers=csrf_header(client),
    )


def test_comparison_endpoint_returns_current_and_plans_without_reoptimizing(db_engine, client):
    analysis_id, dataset_id, scenario_id = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    second_id = _add_scenario(db_engine, "u@example.com", analysis_id, dataset_id,
                              "Optimal @ 60%", _schedule(), target=0.60)
    response = _comparison(client, analysis_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["queue_structure"] == "separate_queues"
    assert body["current"]["dataset_id"] == dataset_id
    assert body["current"]["total_cost"] is None
    assert body["current"]["periods"][0]["active_lanes"] == ["lane-a", "lane-b"]
    assert body["current"]["periods"][0]["lambda_total"] == 6.0
    plans = {plan["scenario_id"]: plan for plan in body["plans"]}
    assert set(plans) == {scenario_id, second_id}
    for plan in plans.values():
        assert plan["stale"] is False
        assert plan["valid"] is True
        assert plan["evaluation_method"] == "DES_REPLICATIONS"
        assert plan["periods"][0]["optimal_active_lanes"] == 1
    assert plans[scenario_id]["target"] == 0.70
    assert plans[second_id]["target"] == 0.60
    assert body["selected_scenario_id"] is None
    assert "score" not in response.text
    assert "winner" not in response.text.lower()


def test_comparison_marks_stale_and_invalid_plans_unselectable(db_engine, client):
    analysis_id, dataset_id, scenario_id = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    blocked_id = _add_scenario(db_engine, "u@example.com", analysis_id, dataset_id,
                               "Blocked plan", _schedule(overall="BLOCKED"))
    body = _comparison(client, analysis_id).json()
    plans = {plan["scenario_id"]: plan for plan in body["plans"]}
    assert plans[blocked_id]["valid"] is False
    assert "COMPLETE" in plans[blocked_id]["valid_reason"]
    with make_sessionmaker(db_engine)() as db:
        user = db.query(User).filter_by(email="u@example.com").one()
        newer = Dataset(
            user_id=user.id, analysis_id=analysis_id, name="Recut",
            source_filename="lanes2.csv", source_format="csv", row_count=2,
            normalized_json=_dataset_rows(),
            validation_report_json={"ok": True, "message": "ok"})
        db.add(newer)
        db.commit()
        newer_id = newer.id
    body = _comparison(client, analysis_id).json()
    assert body["current"]["dataset_id"] == newer_id
    plans = {plan["scenario_id"]: plan for plan in body["plans"]}
    assert plans[scenario_id]["stale"] is True
    assert plans[scenario_id]["valid"] is False
    assert plans[blocked_id]["stale"] is True


def test_comparison_rejects_shared_structure_and_requires_auth(db_engine, client):
    user = create_user(db_engine, "shared@example.com", "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(
            user_id=user.id, name="Shared",
            queue_setup_json={"queue_structure": "shared_queue"},
            setup_status="ready")
        db.add(analysis)
        db.commit()
        shared_id = analysis.id
    login(client, "shared@example.com", "pw")
    assert _comparison(client, shared_id).status_code == 422
    clear_cookies(client)
    assert client.get("/analyses/1/workflow/comparison/separate").status_code == 401


def _scenario_results(db_engine, scenario_id):
    from backend.db.models import Scenario as _Scenario

    with make_sessionmaker(db_engine)() as db:
        return db.get(_Scenario, scenario_id).results_json


def test_selection_and_later_plans_leave_saved_snapshots_immutable(db_engine, client):
    analysis_id, dataset_id, first_id = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    before = _scenario_results(db_engine, first_id)
    assert _select(client, analysis_id, first_id).status_code == 200
    second_id = _add_scenario(db_engine, "u@example.com", analysis_id, dataset_id,
                              "Optimal @ 80%", _schedule(), target=0.80)
    assert _select(client, analysis_id, second_id).status_code == 200
    assert _scenario_results(db_engine, first_id) == before
    workflow = client.get(f"/analyses/{analysis_id}/workflow",
                          headers=csrf_header(client)).json()
    assert workflow["scenario"]["id"] == second_id


def test_comparison_current_metrics_come_from_authoritative_evidence(db_engine, client):
    from backend.queueing_engine.services.data_processing import compute_kpis
    from backend.queueing_engine.services.model_explanations import analyze_segments

    analysis_id, _, _ = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    body = _comparison(client, analysis_id).json()
    frame, _, _ = analyze_segments(_dataset_rows(), _setup(), {"ok": True})
    expected = compute_kpis(frame)
    assert body["current"]["wait_mean"] == expected["avg_waiting_time"]
    assert body["current"]["util_max"] == expected["max_utilization"]
    assert body["current"]["waiting_cost"] == expected["total_waiting_cost"]
    assert body["current"]["periods"][0]["lambda_total"] == 6.0


def test_comparison_marks_plan_stale_after_setup_edit(db_engine, client):
    analysis_id, _, scenario_id = _workspace(db_engine, "edit@example.com")
    login(client, "edit@example.com", "pw")
    plan = next(p for p in _comparison(client, analysis_id).json()["plans"]
                if p["scenario_id"] == scenario_id)
    assert plan["stale"] is False and plan["valid"] is True
    setup = {**_setup(), "breaks": [
        {"queue_id": "lane-a", "scheduled_start_time": "08:40:00", "duration_minutes": 10}]}
    patched = client.patch(f"/analyses/{analysis_id}", headers=csrf_header(client),
                           json={"queue_setup": setup})
    assert patched.status_code == 200, patched.text
    plan = next(p for p in _comparison(client, analysis_id).json()["plans"]
                if p["scenario_id"] == scenario_id)
    assert plan["stale"] is True
    assert plan["valid"] is False
    assert plan["valid_reason"] == "stale for the current Setup"
    assert _select(client, analysis_id, scenario_id).status_code == 422


def test_saved_separate_plan_without_setup_hash_is_stale(db_engine, client):
    analysis_id, dataset_id, _ = _workspace(db_engine, "nohash@example.com")
    settings = _calculation(dataset_id)
    settings["calculation"].pop("setup_hash")
    with make_sessionmaker(db_engine)() as db:
        user = db.query(User).filter_by(email="nohash@example.com").one()
        scenario = Scenario(
            user_id=user.id, analysis_id=analysis_id, dataset_id=dataset_id,
            name="Pre-hash plan", settings_json=settings,
            results_json={"schedule": _schedule()})
        db.add(scenario)
        db.commit()
        legacy_id = scenario.id
    login(client, "nohash@example.com", "pw")
    plan = next(p for p in _comparison(client, analysis_id).json()["plans"]
                if p["scenario_id"] == legacy_id)
    assert plan["stale"] is True and plan["valid"] is False
    assert _select(client, analysis_id, legacy_id).status_code == 422
