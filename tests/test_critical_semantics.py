"""Regression gates for semantic values that UI refinement must preserve."""

from __future__ import annotations

from typing import Any

from backend.api.analysis_schemas import QueueSetup, setup_status
from backend.api.workflow import _derive_decision
from backend.db.models import AnalysisProject, Scenario
from tests.helpers import create_user, csrf_header, login

UNKNOWN_SETUP = {
    "queue_structure": "unknown",
    "fixed_server_count": None,
    "staffing_varies_by_period": False,
    "capacity_mode": "unknown",
    "total_system_capacity": None,
    "abandonment_mode": "unknown",
    "patience_rate_per_hour": None,
}


def test_unknown_setup_survives_schema_persistence_api_and_unrelated_patch(
    db_engine, client
) -> None:
    """An unanswered setup is incomplete, never a valid zero/default queue."""
    setup = QueueSetup()
    assert setup.model_dump(mode="json") == UNKNOWN_SETUP
    assert setup_status(setup) == "incomplete"

    create_user(db_engine, "unknown@example.com", "pw")
    login(client, "unknown@example.com", "pw")
    created = client.post(
        "/analyses",
        headers=csrf_header(client),
        json={"name": "Unknown setup"},
    )
    assert created.status_code == 201
    analysis = created.json()["analysis"]
    assert analysis["queue_setup"] == UNKNOWN_SETUP
    assert analysis["setup_status"] == "incomplete"

    patched = client.patch(
        f"/analyses/{analysis['id']}",
        headers=csrf_header(client),
        json={"location_label": "North"},
    )
    assert patched.status_code == 200
    assert patched.json()["analysis"]["queue_setup"] == UNKNOWN_SETUP
    fetched = client.get(f"/analyses/{analysis['id']}")
    assert fetched.json()["analysis"]["queue_setup"] == UNKNOWN_SETUP


def test_decision_uses_failure_cap_persisted_with_validation_evidence() -> None:
    """A duplicated/current UI threshold cannot change a saved run's verdict."""
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
            "results": [
                {
                    "time": "08:00-09:00",
                    "c_current": 2,
                    "c_optimal": 1,
                    "cost_current": 100,
                    "cost_optimal": 50,
                }
            ]
        },
    )
    evidence: dict[str, Any] = {
        "selection": {"id": 10},
        "des": {
            "id": 11,
            "result": {
                "results": [
                    {
                        "time": "08:00-09:00",
                        "simulation_supported": True,
                        "error": None,
                    }
                ]
            },
        },
        "mc": None,
        "validation": {
            "id": 12,
            "params": {"mc_failure_rate_cap": 0.05},
            "result": {
                "results": [
                    {
                        "time": "08:00-09:00",
                        "simulation_supported": True,
                        "validation_reason": None,
                        "sim_status": "Normal",
                        "mc_failure_rate": 0.10,
                        "mc_failure_rate_adequate": True,
                    }
                ]
            },
        },
    }

    strict_result = _derive_decision(analysis, scenario, evidence)
    assert strict_result["status"] == "revise"
    assert strict_result["facts"]["failure_rate_cap"] == 0.05

    evidence["validation"]["params"]["mc_failure_rate_cap"] = 0.20
    relaxed_result = _derive_decision(analysis, scenario, evidence)
    assert relaxed_result["status"] == "adopt"
    assert relaxed_result["facts"]["failure_rate_cap"] == 0.20
