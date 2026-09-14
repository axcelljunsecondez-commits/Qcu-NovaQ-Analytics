"""Persistent workflow evidence and deterministic Decision API coverage."""

from __future__ import annotations

from backend.api.workflow import _derive_decision
from backend.db.models import AnalysisProject, Dataset, Scenario
from tests.helpers import clear_cookies, create_user, csrf_header, login, make_sessionmaker


def _workspace(db_engine, email: str = "owner@example.com") -> tuple[int, int]:
    user = create_user(db_engine, email, "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(
            user_id=user.id,
            name="Branch queue",
            queue_setup_json={
                "queue_structure": "shared_queue",
                "fixed_server_count": 1,
                "staffing_varies_by_period": False,
                "capacity_mode": "unlimited",
                "total_system_capacity": None,
                "abandonment_mode": "not_modeled",
                "patience_rate_per_hour": None,
            },
            setup_status="ready",
        )
        db.add(analysis)
        db.flush()
        dataset = Dataset(
            user_id=user.id,
            analysis_id=analysis.id,
            name="Observed rates",
            source_filename="rates.csv",
            source_format="csv",
            row_count=1,
            normalized_json=[{"time": "08:00-09:00", "lambda": 1, "mu": 10, "c": 1}],
            validation_report_json={"ok": True, "message": "Input data is valid."},
        )
        db.add(dataset)
        db.flush()
        scenario = Scenario(
            user_id=user.id,
            analysis_id=analysis.id,
            dataset_id=dataset.id,
            name="Lean plan",
            settings_json={
                "calculation": {
                    "schema_version": 1,
                    "engine_version": "novaq-2026-09-system-v2",
                    "input_segments": [
                        {"time": "08:00-09:00", "lambda": 1, "mu": 10, "c": 1}
                    ],
                    "options": {},
                    "what_if_multiplier": 1,
                    "calculated_at": "2026-09-13T00:00:00+00:00",
                }
            },
            results_json={
                "results": [
                    {
                        "time": "08:00-09:00",
                        "lambda_": 1,
                        "mu": 10,
                        "c_current": 2,
                        "c_optimal": 1,
                        "rho_current": 0.05,
                        "rho_optimal": 0.1,
                        "Wq_current": 0.01,
                        "Wq_optimal": 0.02,
                        "Lq_current": 0.01,
                        "Lq_optimal": 0.02,
                        "cost_current": 100,
                        "cost_optimal": 50,
                        "current_stable": True,
                        "optimized_stable": True,
                    }
                ]
            },
        )
        db.add(scenario)
        db.commit()
        return analysis.id, scenario.id


def _decision_inputs(
    *, optimal_cost: float = 50, sim_status: str = "Normal"
) -> tuple[AnalysisProject, Scenario, dict]:
    analysis = AnalysisProject(
        id=1,
        user_id=1,
        name="Branch queue",
        setup_status="ready",
        queue_setup_json={},
    )
    scenario = Scenario(
        id=3,
        user_id=1,
        analysis_id=1,
        dataset_id=2,
        name="Plan A",
        settings_json={},
        results_json={
            "results": [{
                "time": "08:00-09:00",
                "c_current": 2,
                "c_optimal": 1,
                "cost_current": 100,
                "cost_optimal": optimal_cost,
            }]
        },
    )
    evidence = {
        "selection": {"id": 10},
        "des": {
            "id": 11,
            "result": {
                "results": [{
                    "time": "08:00-09:00",
                    "simulation_supported": True,
                    "error": None,
                }]
            },
        },
        "mc": None,
        "validation": {
            "id": 12,
            "params": {"mc_failure_rate_cap": 0.05},
            "result": {
                "results": [{
                    "time": "08:00-09:00",
                    "simulation_supported": True,
                    "validation_reason": None,
                    "sim_status": sim_status,
                    "mc_failure_rate": 0.01,
                    "mc_failure_rate_adequate": True,
                }]
            },
        },
    }
    return analysis, scenario, evidence


def test_decision_requires_revision_when_a_validation_interval_fails():
    analysis, scenario, evidence = _decision_inputs(sim_status="Critical")
    decision = _derive_decision(analysis, scenario, evidence)
    assert decision["status"] == "revise"
    assert decision["facts"]["failed_intervals"] == 1


def test_decision_is_conditional_when_validation_passes_but_cost_increases():
    analysis, scenario, evidence = _decision_inputs(optimal_cost=150)
    decision = _derive_decision(analysis, scenario, evidence)
    assert decision["status"] == "conditional"
    assert decision["facts"]["modeled_savings"] == -50


def test_decision_rejects_partial_interval_evidence():
    analysis, scenario, evidence = _decision_inputs()
    evidence["des"]["result"]["results"] = []
    decision = _derive_decision(analysis, scenario, evidence)
    assert decision["status"] == "insufficient_evidence"
    assert "supported, error-free DES evidence for every interval" in (
        decision["missing_evidence"]
    )


def test_workflow_requires_compare_selection_before_simulation(db_engine, client):
    analysis_id, _ = _workspace(db_engine)
    login(client, "owner@example.com", "pw")
    response = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des",
        headers=csrf_header(client),
        json={"sim_hours": 1, "max_events": 50},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Select a Scenario in Compare first."


def test_workflow_persists_selection_simulation_validation_and_decision(db_engine, client):
    analysis_id, scenario_id = _workspace(db_engine)
    login(client, "owner@example.com", "pw")
    headers = csrf_header(client)

    selection = client.post(
        f"/analyses/{analysis_id}/workflow/selection",
        headers=headers,
        json={"scenario_id": scenario_id},
    )
    assert selection.status_code == 200
    selection_id = selection.json()["selection"]["id"]

    insufficient = client.post(
        f"/analyses/{analysis_id}/workflow/decision", headers=headers
    )
    assert insufficient.status_code == 200
    assert insufficient.json()["decision"]["status"] == "insufficient_evidence"

    des = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des",
        headers=headers,
        json={"sim_hours": 2, "max_events": 100, "seed": 7},
    )
    assert des.status_code == 200
    des_evidence = des.json()["evidence"]
    des_result = des_evidence["result"]
    assert des_result["trace"]
    assert des_result["results"][0]["time"] == "08:00-09:00"

    validation = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/validation",
        headers=headers,
        json={
            "des_sim_hours": 2,
            "mc_trials": 200,
            "mc_failure_threshold": 1,
            "mc_failure_rate_cap": 1,
            "seed": 7,
        },
    )
    assert validation.status_code == 200
    validation_id = validation.json()["evidence"]["id"]

    decision = client.post(
        f"/analyses/{analysis_id}/workflow/decision", headers=headers
    )
    assert decision.status_code == 200
    decision_body = decision.json()
    assert decision_body["persisted"] is True
    assert decision_body["decision"]["status"] == "adopt"
    assert "Lean plan" in decision_body["decision"]["headline"]
    assert decision_body["decision"]["evidence_ids"] == {
        "selection": selection_id,
        "des": des_evidence["id"],
        "mc": None,
        "validation": validation_id,
    }

    evidence = client.get(f"/analyses/{analysis_id}/workflow")
    assert evidence.status_code == 200
    body = evidence.json()
    assert body["scenario"]["id"] == scenario_id
    assert body["des"]["result"]["results"] == des_result["results"]
    assert body["decision"]["result"]["status"] == "adopt"
    assert body["decision"]["result"]["evidence_ids"] == (
        decision_body["decision"]["evidence_ids"]
    )
    assert body["decision_stale"] is False


def test_workflow_selection_is_owner_scoped(db_engine, client):
    alice_analysis, alice_scenario = _workspace(db_engine, "alice@example.com")
    login(client, "alice@example.com", "pw")
    assert client.post(
        f"/analyses/{alice_analysis}/workflow/selection",
        headers=csrf_header(client),
        json={"scenario_id": alice_scenario},
    ).status_code == 200

    clear_cookies(client)
    bob_analysis, _ = _workspace(db_engine, "bob@example.com")
    login(client, "bob@example.com", "pw")
    response = client.post(
        f"/analyses/{bob_analysis}/workflow/selection",
        headers=csrf_header(client),
        json={"scenario_id": alice_scenario},
    )
    assert response.status_code == 422


def test_new_simulation_makes_saved_decision_stale(db_engine, client):
    analysis_id, scenario_id = _workspace(db_engine)
    login(client, "owner@example.com", "pw")
    headers = csrf_header(client)
    client.post(
        f"/analyses/{analysis_id}/workflow/selection",
        headers=headers,
        json={"scenario_id": scenario_id},
    )
    client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des",
        headers=headers,
        json={"sim_hours": 1, "max_events": 50},
    )
    client.post(
        f"/analyses/{analysis_id}/workflow/simulation/validation",
        headers=headers,
        json={
            "des_sim_hours": 1,
            "mc_trials": 200,
            "mc_failure_threshold": 1,
            "mc_failure_rate_cap": 1,
        },
    )
    assert client.post(
        f"/analyses/{analysis_id}/workflow/decision", headers=headers
    ).json()["persisted"] is True

    client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des",
        headers=headers,
        json={"sim_hours": 2, "max_events": 50},
    )
    evidence = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert evidence["decision"] is None
    assert evidence["decision_stale"] is True


def test_switching_scenario_hides_prior_scenario_evidence(db_engine, client):
    analysis_id, first_scenario_id = _workspace(db_engine)
    with make_sessionmaker(db_engine)() as db:
        first = db.get(Scenario, first_scenario_id)
        assert first is not None
        second = Scenario(
            user_id=first.user_id,
            analysis_id=first.analysis_id,
            dataset_id=first.dataset_id,
            name="Alternative plan",
            settings_json=first.settings_json,
            results_json=first.results_json,
            tenant_id=first.tenant_id,
        )
        db.add(second)
        db.commit()
        second_scenario_id = second.id

    login(client, "owner@example.com", "pw")
    headers = csrf_header(client)
    assert client.post(
        f"/analyses/{analysis_id}/workflow/selection",
        headers=headers,
        json={"scenario_id": first_scenario_id},
    ).status_code == 200
    assert client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des",
        headers=headers,
        json={"sim_hours": 1, "max_events": 50},
    ).status_code == 200
    assert client.post(
        f"/analyses/{analysis_id}/workflow/simulation/validation",
        headers=headers,
        json={
            "des_sim_hours": 1,
            "mc_trials": 20,
            "mc_failure_threshold": 1,
            "mc_failure_rate_cap": 1,
        },
    ).status_code == 200
    assert client.post(
        f"/analyses/{analysis_id}/workflow/decision", headers=headers
    ).json()["persisted"] is True

    selected = client.post(
        f"/analyses/{analysis_id}/workflow/selection",
        headers=headers,
        json={"scenario_id": second_scenario_id},
    )
    assert selected.status_code == 200
    evidence = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert evidence["scenario"]["id"] == second_scenario_id
    assert evidence["selection"]["params"]["scenario_id"] == second_scenario_id
    assert evidence["des"] is None
    assert evidence["mc"] is None
    assert evidence["validation"] is None
    assert evidence["decision"] is None
    assert evidence["decision_stale"] is False
