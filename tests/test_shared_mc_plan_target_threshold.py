"""Shared-line Many variations counts failures at the plan's target, like separate lines.

Spec: docs/superpowers/specs/2026-10-29-shared-mc-plan-target-threshold.md (§4 rule, §9 R1-R8).
Data: SYNTHETIC two-period shared plan (tests.test_od_ux_13_full_day_decision); the separate parity
case reuses the small selected plan of tests.test_selected_mc_load (plan target 0.70).
"""

from __future__ import annotations

import math
from typing import Any, get_type_hints

import pytest
from scipy import integrate

from backend.api import workflow
from backend.db.models import AnalysisProject, Dataset, Scenario
from backend.queueing_engine.config import MC_ARRIVAL_NOISE, MC_DEFAULT_FAILURE_THRESHOLD, MC_SERVICE_NOISE
from backend.queueing_engine.simulation.simulation import mc_simulate_segments
from tests.helpers import create_user, csrf_header, login, make_sessionmaker
from tests.test_od_ux_13_full_day_decision import ROWS, SETUP, _day_run, _decide, _plan_rows

TRIALS = 2000
SEED = 3


def _shared_plan(db_engine, client, email: str, targets: tuple[float | None, float | None],
                 options: dict[str, Any] | None = None) -> int:
    """A selected shared plan (rows as in OD-UX-13) whose rows record ``targets``."""
    user = create_user(db_engine, email, "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(user_id=user.id, name="Line", queue_setup_json=SETUP, setup_status="ready")
        db.add(analysis)
        db.flush()
        dataset = Dataset(user_id=user.id, analysis_id=analysis.id, name="Rates", source_filename="rates.csv",
                          source_format="csv", row_count=2, normalized_json=ROWS,
                          validation_report_json={"ok": True, "message": "Input data is valid."})
        db.add(dataset)
        db.flush()
        scenario = Scenario(
            user_id=user.id, analysis_id=analysis.id, dataset_id=dataset.id, name="Plan",
            settings_json={**(options or {}), "calculation": {
                "schema_version": 1, "engine_version": "novaq-2026-09-system-v2", "input_segments": ROWS,
                "options": options or {}, "what_if_multiplier": 1, "calculated_at": "2026-10-29T00:00:00+00:00"}},
            results_json={"results": _plan_rows(targets)})
        db.add(scenario)
        db.commit()
        analysis_id, scenario_id = analysis.id, scenario.id
    assert login(client, email, "pw") == 200
    headers = csrf_header(client)
    assert client.put(f"/analyses/{analysis_id}/closing-policy", headers=headers,
                      json={"closing_policy": "DRAIN"}).status_code == 200
    assert client.post(f"/analyses/{analysis_id}/workflow/selection", headers=headers,
                       json={"scenario_id": scenario_id}).status_code == 200
    return analysis_id


def _shared_mc(client, analysis_id: int, **extra: Any) -> dict[str, Any]:
    response = client.post(f"/analyses/{analysis_id}/workflow/simulation/mc", headers=csrf_header(client),
                           json={"num_trials": TRIALS, "failure_rate_cap": 0.05, "seed": SEED, **extra})
    assert response.status_code == 200, response.text
    return response.json()["evidence"]


def _failure_probability(rho0: float, threshold: float) -> float:
    """P(rho0 (1 + a) / (1 + b) > T), a ~ U(-A, A), b ~ U(-S, S), by numerical integration (no MC code)."""
    a_half, s_half = MC_ARRIVAL_NOISE, MC_SERVICE_NOISE

    def given_b(b: float) -> float:
        a_star = threshold * (1 + b) / rho0 - 1  # failure iff a > a_star
        return min(1.0, max(0.0, (a_half - a_star) / (2 * a_half)))

    value, _ = integrate.quad(given_b, -s_half, s_half, limit=200, points=[])
    return value / (2 * s_half)


def _wilson(successes: int, n: int, z: float = 3.29) -> tuple[float, float]:
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


# R1 independent reference case
def test_r1_omitted_threshold_matches_the_integrated_probability_at_the_plan_target(db_engine, client):
    p70, p75 = _failure_probability(4 / 6, 0.70), _failure_probability(4 / 6, 0.75)
    assert p70 == pytest.approx(0.375, abs=0.01)  # hand check: mean a* = 0.05 -> (0.2 - 0.05) / 0.4
    assert p70 - p75 > 0.1  # the two thresholds are far apart for this period
    analysis_id = _shared_plan(db_engine, client, "r1@example.com", (0.70, 0.70))
    row = _shared_mc(client, analysis_id)["result"]["results"][0]
    assert (row["time"], row["c"]) == ("08:00-09:00", 1)
    low, high = _wilson(row["failure_count"], row["trials_completed"])
    assert low <= p70 <= high
    assert not low <= p75 <= high


# R2
def test_r2_shared_omitted_threshold_uses_the_plan_target_and_records_it(db_engine, client):
    analysis_id = _shared_plan(db_engine, client, "r2@example.com", (0.70, 0.70))
    evidence = _shared_mc(client, analysis_id)
    params, rows = evidence["params"], evidence["result"]["results"]
    assert params["failure_threshold"] == pytest.approx(0.70)
    assert params["failure_threshold_source"] == "plan_target"
    assert all(row["failure_threshold"] == pytest.approx(0.70) for row in rows)
    direct = mc_simulate_segments([{"time": r["time"], "lambda": r["lambda"], "mu": r["mu"], "c": r["c"]} for r in rows],
                                  num_trials=TRIALS, failure_threshold=0.70, seed=SEED, failure_rate_cap=0.05)
    assert [row["failure_count"] for row in rows] == [row["failure_count"] for row in direct]


# R3
def test_r3_shared_explicit_threshold_is_recorded_as_user(db_engine, client):
    analysis_id = _shared_plan(db_engine, client, "r3@example.com", (0.70, 0.70))
    params = _shared_mc(client, analysis_id, failure_threshold=0.75)["params"]
    assert params["failure_threshold"] == pytest.approx(0.75)
    assert params["failure_threshold_source"] == "user"


# R4
def test_r4_rows_without_targets_fall_back_to_the_saved_calculation_option(db_engine, client):
    analysis_id = _shared_plan(db_engine, client, "r4@example.com", (None, None), {"target_utilization": 0.65})
    params = _shared_mc(client, analysis_id)["params"]
    assert params["failure_threshold"] == pytest.approx(0.65)
    assert params["failure_threshold_source"] == "plan_target"


# R5
@pytest.mark.parametrize("targets", [(None, None), (0.70, 0.95), (0.70, None), (1.5, 1.5)])
def test_r5_no_single_valid_target_keeps_the_default(db_engine, client, targets):
    analysis_id = _shared_plan(db_engine, client, f"r5-{targets[0]}-{targets[1]}@example.com", targets)
    params = _shared_mc(client, analysis_id)["params"]
    assert params["failure_threshold"] == MC_DEFAULT_FAILURE_THRESHOLD
    assert params["failure_threshold_source"] == "default"


# R6 parity with separate lines
@pytest.mark.parametrize("body, expected", [({}, (0.70, "plan_target")), ({"failure_threshold": 0.75}, (0.75, "user"))])
def test_r6_shared_and_separate_resolve_the_threshold_the_same_way(db_engine, client, monkeypatch, body, expected):
    from tests.test_selected_mc_load import _small_selected

    calls: list[tuple[float | None, float | None]] = []
    real = workflow._resolve_mc_failure_threshold

    def spy(payload, target):
        calls.append((payload.failure_threshold, target))
        return real(payload, target)

    monkeypatch.setattr(workflow, "_resolve_mc_failure_threshold", spy)
    tag = "user" if body else "omit"
    separate_id, headers = _small_selected(db_engine, client, f"r6-sep-{tag}@example.com")
    separate = client.post(f"/analyses/{separate_id}/workflow/simulation/mc/selected", headers=headers, json=body)
    assert separate.status_code == 200, separate.text
    client.cookies.clear()  # sign the second user in on a fresh session
    shared_id = _shared_plan(db_engine, client, f"r6-shared-{tag}@example.com", (0.70, 0.70))
    shared = _shared_mc(client, shared_id, **body)
    recorded = []
    for params in (separate.json()["evidence"]["params"], shared["params"]):
        recorded.append((pytest.approx(params["failure_threshold"]), params["failure_threshold_source"]))
    assert recorded == [expected, expected]
    assert len(calls) == 2 and calls[0] == calls[1]


# R7 the Decision table's target and the counting threshold agree
def test_r7_full_day_decision_target_equals_the_counting_threshold(db_engine, client):
    analysis_id = _shared_plan(db_engine, client, "r7@example.com", (0.70, 0.70))
    _day_run(client, analysis_id)
    threshold = _shared_mc(client, analysis_id)["params"]["failure_threshold"]
    periods = _decide(client, analysis_id)["facts"]["periods"]
    assert len(periods) == 2
    assert all(period["target_utilization"] == pytest.approx(threshold) for period in periods)


# R8 today's staffing has no plan target
def test_r8_current_mc_still_defaults_to_075():
    assert workflow.WorkflowMcRequest().failure_threshold == MC_DEFAULT_FAILURE_THRESHOLD == 0.75
    assert get_type_hints(workflow.run_mc_current)["payload"] is workflow.WorkflowMcRequest
    assert get_type_hints(workflow.run_mc)["payload"] is workflow.SelectedMcRequest
