"""Shared Queue cutoff reference cases using the supplied hourly planning fixture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.api import workflow
from backend.db.models import Job
from backend.queueing_engine.services.shared_segments import DemandPeriod, OperatingHorizon
from backend.queueing_engine.simulation.shared_continuous_des import _arrival_times
from tests.helpers import create_user, csrf_header, login
from tests.test_shared_aggregate_setup_api import CSV, apply, metadata, preview

STAMP = "2026-11-27T00:00:00+00:00"
PLANNING_DEFAULTS = Path(__file__).resolve().parents[1] / "frontend/src/api/planning-defaults.json"


def _read(response, expected=200):
    assert response.status_code == expected, (response.status_code, response.text[:1000])
    return response.json()


@pytest.fixture
def shared_scope(client, db_engine):
    create_user(db_engine, "arrival-allowance@example.com", "pw")
    assert login(client, "arrival-allowance@example.com", "pw") == 200
    headers = csrf_header(client)
    analysis = _read(client.post("/analyses", headers=headers, json={
        "name": "Arrival allowance", "queue_setup": {"queue_structure": "shared_queue"},
    }), 201)["analysis"]
    analysis_id = analysis["id"]
    base = f"/analyses/{analysis_id}"

    def save_file(csv=CSV):
        prepared = _read(preview(client, analysis_id, data=csv))
        return _read(apply(client, analysis_id, metadata(prepared, confirm=True), data=csv), 201)["dataset"]

    def put_allowance(minutes):
        return client.put(base + "/arrival-cutoff", headers=headers, json={"allowance_minutes": minutes})

    def post(path, body=None):
        return client.post(base + path, headers=headers, json=body)

    def set_closing(rule="DRAIN"):
        return _read(client.put(base + "/closing-policy", headers=headers, json={"closing_policy": rule}))

    return base, headers, save_file, put_allowance, post, set_closing


def _select_plan(client, base, headers, dataset):
    options = json.loads(PLANNING_DEFAULTS.read_text(encoding="utf-8"))
    inputs = [{key: row[key] for key in ("time", "lambda", "mu", "c")} for row in dataset["normalized"]]
    plan = _read(client.post("/optimize/batch", headers=headers, json={"segments": inputs, **options}))
    scenario = _read(client.post("/scenarios", headers=headers, json={
        "name": "Suggested staffing", "analysis_id": int(base.rsplit("/", 1)[1]), "dataset_id": dataset["id"],
        "results": plan, "settings": {**options, "calculation": {
            "schema_version": 1, "engine_version": "novaq-2026-09-system-v2", "input_segments": inputs,
            "options": options, "what_if_multiplier": 1, "calculated_at": STAMP,
        }},
    }), 201)["scenario"]
    _read(client.post(base + "/workflow/selection", headers=headers, json={"scenario_id": scenario["id"]}))


def _run(post, plan="suggested"):
    return _read(post("/continuous/runs", {"plan": plan, "replications": 1, "seed": 42}))["evidence"]


def test_arrivals_exclude_the_exact_cutoff_without_shortening_the_horizon():
    class FixedGaps:
        def __init__(self):
            self.gaps = iter([0.25, 0.25, 0.25, 0.25])

        def exponential(self, scale):
            return next(self.gaps)

    horizon = OperatingHorizon(1020, 1080)
    periods = [DemandPeriod("17:00-18:00", 1020, 1080, 5, 4)]
    assert _arrival_times(horizon, periods, FixedGaps(), 1050) == [0.25]
    assert _arrival_times(horizon, periods, FixedGaps()) == [0.25, 0.5, 0.75]


@pytest.mark.parametrize(("allowance", "cutoff", "final_count"), [
    (0, 1080, 5), (15, 1065, 3.75), (30, 1050, 2.5), (45, 1035, 1.25), (60, 1020, 0),
])
def test_hourly_file_keeps_18_00_closing_and_adjusts_expected_arrivals(
    client, shared_scope, allowance, cutoff, final_count,
):
    base, _, save_file, put_allowance, post, set_closing = shared_scope
    dataset = save_file()
    assert _read(client.get(base + "/arrival-cutoff")) == {"allowance_minutes": 0}
    assert _read(put_allowance(allowance)) == {"allowance_minutes": allowance}
    set_closing()
    view = _read(post("/continuous/compatibility"))
    current = view["plans"]["current"]
    assert current["compatible"]
    assert current["horizon"] == {"start_minute": 300, "end_minute": 1080}
    assert view.get("arrival_allowance_minutes", 0) == allowance
    assert current.get("arrival_cutoff_minute", 1080) == cutoff
    expected = sum(row["lambda"] for row in dataset["normalized"][:-1]) + final_count
    assert current["expected_customers_per_day"] == pytest.approx(expected)
    run = _run(post, "current")
    inputs = run["result"]["provenance"]["inputs"]
    assert inputs["horizon"] == current["horizon"]
    assert inputs["staffing_segments"][-1]["servers"] == 2
    assert inputs["demand_periods"][-1]["arrival_rate_per_hour"] == 5
    assert inputs.get("arrival_cutoff_minute", 1080) == cutoff
    assert ("arrival_allowance_minutes" in run["params"]) is bool(allowance)


def test_cutoff_put_requires_hourly_data_and_cutoff_after_opening(shared_scope):
    _, _, save_file, put_allowance, _, _ = shared_scope
    missing = _read(put_allowance(30), 422)
    assert missing["detail"]["code"] == "arrival_cutoff_requires_hourly_aggregate"
    save_file(b"time,lambda,mu,c\n17:00-18:00,5,4,2\n")
    too_long = _read(put_allowance(60), 422)
    assert too_long["detail"]["code"] == "arrival_cutoff_before_opening"
    _read(put_allowance(30))
    for invalid in (False, 30.0, 20, "30"):
        _read(put_allowance(invalid), 422)


@pytest.mark.parametrize("rule", ["DRAIN", "HARD_CUTOFF"])
def test_earlier_cutoff_replays_seeded_prefix_and_requires_matching_checks(client, shared_scope, rule):
    base, headers, save_file, put_allowance, post, set_closing = shared_scope
    _select_plan(client, base, headers, save_file())
    set_closing(rule)
    full = _run(post)
    assert full["result"] == _run(post)["result"]
    _read(put_allowance(30))
    status = _read(client.get(base + "/workflow"))
    assert status["arrival_allowance_minutes"] == 30
    assert status["decision_basis"] == "full_day_run"
    assert status["full_day_run_id"] is None
    assert _read(post("/workflow/decision"), 422)["detail"]["code"] == "arrival_cutoff_run_required"

    early = _run(post)
    assert early["params"]["arrival_cutoff_minute"] == 1050
    assert _read(post("/workflow/decision"), 422)["detail"]["code"] == "arrival_cutoff_check_required"

    def playback(run):
        return _read(client.get(base + f"/continuous/runs/{run['id']}/replications/0/playback"))["playback"]

    def arrival_times(run):
        return [customer["arrival_hours"] for customer in playback(run)["customers"]]

    cut_hours = 12.5  # 05:00 to 17:30, independently of the closing-time run code.
    assert arrival_times(early) == [time for time in arrival_times(full) if time < cut_hours]
    assert playback(early)["closing"]["closing_hours"] == 13

    mc = _read(post("/workflow/simulation/mc", {"num_trials": 2000, "seed": 42}))["evidence"]
    assert mc["params"]["arrival_continuous_run_id"] == early["id"]
    assert mc["params"]["arrival_run_token"] == early["params"]["arrival_run_token"]
    assert mc["result"]["results"][-1]["lambda"] == 2.5
    assert mc["result"]["results"][-2]["lambda"] == pytest.approx(6.2857)
    decided = _read(post("/workflow/decision"))
    assert decided["persisted"] is True
    decision = decided["decision"]
    assert decision["arrival_cutoff_minute"] == 1050
    assert decision["evidence_ids"]["mc"] == mc["id"]
    assert decision["evidence_ids"]["continuous"] == early["id"]
    report = _read(client.get(base + "/reports/full/preview"))["model"]
    assert "17:30" in report["checks"][0]["settings"]
    assert "saved plan’s arrival rates" in " ".join(report["not_included"])
    for ext, prefix in (("pdf", b"%PDF"), ("xlsx", b"PK")):
        response = client.get(base + "/reports/full." + ext)
        assert response.status_code == 200
        assert response.content.startswith(prefix)

    set_closing("HARD_CUTOFF" if rule == "DRAIN" else "DRAIN")
    assert not _read(client.get(base + f"/continuous/runs/{early['id']}"))["arrival_settings_match"]
    assert _read(post("/workflow/decision"), 422)["detail"]["code"] == "arrival_cutoff_run_required"
    _read(client.get(base + "/reports/full/preview"), 422)


def test_new_run_between_evidence_reads_cannot_reuse_the_old_mc(client, shared_scope, monkeypatch):
    base, headers, save_file, put_allowance, post, set_closing = shared_scope
    _select_plan(client, base, headers, save_file())
    set_closing()
    _read(put_allowance(60))
    first = _run(post)
    mc = _read(post("/workflow/simulation/mc", {"num_trials": 2000, "seed": 42}))["evidence"]
    assert mc["result"]["results"][-1]["lambda"] == 0
    second = _run(post)
    run_ids = iter([first["id"], second["id"]])

    def eligible(db, *_args: Any):
        return db.get(Job, next(run_ids))

    with monkeypatch.context() as patch:
        patch.setattr(workflow, "_eligible_full_day_run", eligible)
        assert _read(post("/workflow/decision"), 422)["detail"]["code"] == "arrival_cutoff_check_required"
    _read(client.get(base + "/reports/full/preview"), 422)
