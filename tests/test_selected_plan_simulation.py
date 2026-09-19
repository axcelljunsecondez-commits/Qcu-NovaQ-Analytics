"""Selected Separate-plan Simulation: gate, DES, playback trace, Monte Carlo.

The selected immutable schema-v2 scenario is the sole optimized-plan
authority. Simulation executes its persisted per-period optima with the
proven routing DES core (period-independent, explicitly labeled), persists
scenario-scoped evidence jobs, and never reoptimizes or mutates scenarios.
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


def _setup(queue_ids=("east-07", "lane-A")):
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


def _row(time, queue_id, lam):
    return {"time": time, "segment_id": "s1", "queue_id": queue_id,
            "lambda": lam, "mu": 11.0, "c": 1, "variance": 0.0009,
            "service_samples_hours": list(SAMPLES)}


def _dataset_rows():
    return [_row("08:00", "east-07", 4.0), _row("08:00", "lane-A", 2.0)]


def _optimum(active_ids, count):
    return {
        "active_lane_count": count,
        "recommendation": "REDUCE",
        "total_cost": 180.0,
        "candidate_utilization": 0.55,
        "estimated_optimal": True,
    }


def _period(time, active_ids, overall="OPTIMAL"):
    count = len(active_ids)
    return {
        "time": time,
        "overall": overall,
        "reason": None,
        "current_active_lanes": ["east-07", "lane-A"],
        "optimal_active_lanes": count if overall == "OPTIMAL" else None,
        "adjustment": count - 2 if overall == "OPTIMAL" else None,
        "optimum": ({
            **_optimum(active_ids, count),
            "active_queue_ids": list(active_ids),
            "inactive_queue_ids": [q for q in ("east-07", "lane-A") if q not in active_ids],
        } if overall == "OPTIMAL" else None),
        "candidates": [],
        "evaluation_method": "DES_REPLICATIONS",
        "replication_seeds": [42, 43, 44, 45, 46],
        "target_utilization": 0.70,
    }


def _schedule(periods):
    return {"overall": "COMPLETE", "reason": None, "target_utilization": 0.70,
            "evaluation_method": "DES_REPLICATIONS", "periods": periods,
            "des": {"replications": 5, "base_seed": 42,
                    "duration_hours": 8.0, "max_events": 5000}}


def _calculation(dataset_id, target=0.70):
    options = {
        "target_utilization": target,
        "server_cost_per_hr": 87.0,
        "customer_waiting_cost": 100.0,
        "min_active_lanes": None,
        "max_active_lanes": None,
        "lambda_multiplier": 1.0,
        "des": {"replications": 5, "base_seed": 42,
                "duration_hours": 8.0, "max_events": 5000},
    }
    return {**options, "calculation": {
        "schema_version": 2, "engine_version": SEPARATE_DES_ENGINE_VERSION,
        "dataset_id": dataset_id, "dataset_row_count": 2,
        "options": options, "calculated_at": "2026-09-18T00:00:00+00:00",
        "setup_hash": setup_fingerprint(_setup())}}


def _workspace(db_engine, email, periods=None):
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
            results_json={"schedule": _schedule(
                periods if periods is not None else [_period("08:00", ["east-07"])]
            )})
        db.add(scenario)
        db.commit()
        return analysis.id, dataset.id, scenario.id


def _select(client, analysis_id, scenario_id):
    return client.post(
        f"/analyses/{analysis_id}/workflow/selection",
        headers=csrf_header(client),
        json={"scenario_id": scenario_id},
    )


def _run_des(client, analysis_id, body=None):
    return client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des/selected",
        headers=csrf_header(client),
        json={} if body is None else body,
    )


def _run_mc(client, analysis_id, body=None):
    return client.post(
        f"/analyses/{analysis_id}/workflow/simulation/mc/selected",
        headers=csrf_header(client),
        json={} if body is None else body,
    )


def test_selected_des_without_selection_is_blocked(db_engine, client):
    analysis_id, _, _ = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    response = _run_des(client, analysis_id)
    assert response.status_code == 409, response.text
    assert "Comparison" in response.json()["detail"]


def test_selected_des_executes_persisted_active_ids_with_conservation(db_engine, client):
    analysis_id, _, scenario_id = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    assert _select(client, analysis_id, scenario_id).status_code == 200
    response = _run_des(client, analysis_id, {"seed": 7})
    assert response.status_code == 200, response.text
    result = response.json()["evidence"]["result"]
    assert result["scenario_id"] == scenario_id
    assert result["provenance"] == "SELECTED"
    assert result["overall_conservation"] is True
    assert result["overall_status"] == "COMPLETED"
    (period,) = result["periods"]
    assert period["active_queue_ids"] == ["east-07"]
    assert period["conservation"] is True
    by_lane = {row["queue_id"]: row for row in period["results"]}
    assert set(by_lane) == {"east-07", "lane-A"}
    assert by_lane["lane-A"]["arrivals"] == 0
    assert by_lane["lane-A"]["served"] == 0
    assert by_lane["east-07"]["arrivals"] > 0
    assert by_lane["east-07"]["arrivals"] == (
        by_lane["east-07"]["served"] + by_lane["east-07"]["waiting"]
        + by_lane["east-07"]["in_service"])
    trace = period["trace"]
    assert trace["abandonment_supported"] is False
    assert trace["truncated"] is False
    assert trace["event_count"] == len(trace["trace"]) > 0
    assert {event["queue_id"] for event in trace["trace"]} == {"east-07"}
    assert trace["segments"][0]["queue_structure"] == "separate"


def _add_scenario(db_engine, email, analysis_id, dataset_id, name, schedule):
    with make_sessionmaker(db_engine)() as db:
        user = db.query(User).filter_by(email=email).one()
        scenario = Scenario(
            user_id=user.id, analysis_id=analysis_id, dataset_id=dataset_id,
            name=name, settings_json=_calculation(dataset_id),
            results_json={"schedule": schedule})
        db.add(scenario)
        db.commit()
        return scenario.id


def test_selected_gate_blocks_cross_analysis_stale_and_tampered(db_engine, client):
    analysis_id, dataset_id, scenario_id = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    other_id = _workspace(db_engine, "other@example.com")[0]
    clear_cookies(client)
    login(client, "other@example.com", "pw")
    assert _run_des(client, other_id).status_code == 409
    clear_cookies(client)
    login(client, "u@example.com", "pw")
    assert _select(client, analysis_id, scenario_id).status_code == 200
    blocked_id = _add_scenario(db_engine, "u@example.com", analysis_id, dataset_id,
                               "Blocked", _schedule([_period("08:00", ["east-07"])]))
    blocked = _schedule([_period("08:00", ["east-07"])])
    blocked["overall"] = "BLOCKED"
    with make_sessionmaker(db_engine)() as db:
        db.get(Scenario, blocked_id).results_json = {"schedule": blocked}
        db.commit()
    assert _select(client, analysis_id, blocked_id).status_code == 422
    response = _run_des(client, analysis_id)
    assert response.status_code == 200
    with make_sessionmaker(db_engine)() as db:
        user = db.query(User).filter_by(email="u@example.com").one()
        newer = Dataset(
            user_id=user.id, analysis_id=analysis_id, name="Recut",
            source_filename="r.csv", source_format="csv", row_count=2,
            normalized_json=_dataset_rows(),
            validation_report_json={"ok": True, "message": "ok"})
        db.add(newer)
        db.commit()
    stale = _run_des(client, analysis_id)
    assert stale.status_code == 422
    assert "runnable" in stale.json()["detail"]


def test_selected_mc_uses_same_scenario_and_measured_loads(db_engine, client):
    analysis_id, _, scenario_id = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    assert _select(client, analysis_id, scenario_id).status_code == 200
    assert _run_mc(client, analysis_id).status_code == 404
    des = _run_des(client, analysis_id, {"seed": 7})
    assert des.status_code == 200, des.text
    des_body = des.json()["evidence"]
    mc = _run_mc(client, analysis_id)
    assert mc.status_code == 200, mc.text
    mc_result = mc.json()["evidence"]["result"]
    assert mc_result["scenario_id"] == scenario_id
    assert mc_result["des_job_id"] == des_body["id"]
    assert mc_result["provenance"] == "SELECTED"
    rows = mc_result["results"]
    assert {row["queue_id"] for row in rows} == {"east-07"}
    assert rows[0]["num_trials"] == 2000
    assert rows[0]["failure_threshold"] == 0.70  # R9: omitted threshold = plan target
    assert rows[0]["failure_rate_ci_lower"] is not None
    des_lane = des_body["result"]["periods"][0]["results"][0]
    assert rows[0]["lambda"] == des_lane["lambda_routed_mean"]


def test_scenario_change_stales_old_simulation_evidence(db_engine, client):
    analysis_id, dataset_id, first_id = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    assert _select(client, analysis_id, first_id).status_code == 200
    assert _run_des(client, analysis_id, {"seed": 7}).status_code == 200
    second_id = _add_scenario(
        db_engine, "u@example.com", analysis_id, dataset_id,
        "Optimal @ 60%", _schedule([_period("08:00", ["east-07", "lane-A"])]))
    assert _select(client, analysis_id, second_id).status_code == 200
    workflow = client.get(f"/analyses/{analysis_id}/workflow",
                          headers=csrf_header(client)).json()
    assert workflow["scenario"]["id"] == second_id
    assert workflow["des"] is None
    assert workflow["mc"] is None


def test_workflow_exposes_selected_plan_schema_for_page_routing(db_engine, client):
    # The Simulation page shows the Separate-plan view only when it can see
    # settings.calculation.schema_version == 2 on the selected scenario.
    analysis_id, _, scenario_id = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    assert _select(client, analysis_id, scenario_id).status_code == 200
    workflow = client.get(f"/analyses/{analysis_id}/workflow",
                          headers=csrf_header(client)).json()
    assert workflow["scenario"]["settings"]["calculation"]["schema_version"] == 2


def test_simulation_runs_leave_scenario_immutable_and_reproducible(db_engine, client):
    from backend.db.models import Scenario as _Scenario

    analysis_id, _, scenario_id = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    with make_sessionmaker(db_engine)() as db:
        before = dict(db.get(_Scenario, scenario_id).results_json)
    assert _select(client, analysis_id, scenario_id).status_code == 200
    first = _run_des(client, analysis_id, {"seed": 7})
    second = _run_des(client, analysis_id, {"seed": 7})
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["evidence"]["result"] == second.json()["evidence"]["result"]
    assert _run_mc(client, analysis_id).status_code == 200
    with make_sessionmaker(db_engine)() as db:
        assert db.get(_Scenario, scenario_id).results_json == before


def test_selected_simulation_makes_no_optimizer_calls():
    import inspect

    import backend.api.workflow as workflow_api

    for name in ("run_selected_des", "run_selected_mc",
                 "_run_selected_plan_des", "_require_selected_separate_plan"):
        source = inspect.getsource(getattr(workflow_api, name))
        assert "optimize_separate" not in source
        assert "_optimize_separate_des" not in source
        assert "rank_des_candidates" not in source


def test_conservation_failure_invalidates_selected_run(db_engine, client):
    import backend.api.workflow as workflow_api

    analysis_id, _, scenario_id = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    assert _select(client, analysis_id, scenario_id).status_code == 200

    def _leaky(candidate, queues_by_id, **kwargs):
        good = workflow_api.evaluate_candidate_with_des(
            candidate, queues_by_id, **kwargs)
        good["customer_conservation"] = False
        return good

    with make_sessionmaker(db_engine)() as db:
        user = db.query(User).filter_by(email="u@example.com").one()
        analysis = db.get(AnalysisProject, analysis_id)
        plan = workflow_api._require_selected_separate_plan(db, user, analysis)
    result = workflow_api._run_selected_plan_des(plan, seed=7, execute=_leaky)
    assert result["overall_status"] == "ERROR"
    assert result["overall_conservation"] is False
