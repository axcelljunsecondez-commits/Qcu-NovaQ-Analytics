"""B4b: recorded service times in the continuous shared-line run.

Spec: docs/superpowers/specs/2026-10-09-b4b-recorded-service-times.md (owner answers 2026-10-09: OD-B4b-1 = A
resample recorded durations, OD-B4b-2 = A nearest-period fallback listed, OD-UX-9 = the section 5 checks are the
acceptance set). Section 5 check 1 (exponential mode unchanged) is the engine's own pin and test suites, run
unchanged, plus the default-path checks below. Mutation testing of the sampling path runs from the session
scratchpad.

Deterministic cases use prescribed (arrival hour, service quantile) pairs and binary-exact durations, so every
expected value is computed by hand. Statistical cases use fixed seeds and state their tolerance.

Data: SYNTHETIC (rates, durations, setups and plans made for the test).
"""

from __future__ import annotations

import math
import statistics
from typing import Any

import numpy as np
import pytest
from sqlalchemy import func, select

from backend.api import shared_continuous
from backend.db.models import AnalysisProject, Dataset, Job, Scenario, User
from backend.queueing_engine.services.model_selection import select_model
from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
)
from backend.queueing_engine.simulation.shared_continuous_des import (
    DRAIN,
    ENGINE_VERSION,
    HARD_CUTOFF,
    RECORDED_ENGINE_VERSION,
    resolve_service_samples,
    simulate_prescribed,
    simulate_shared_replication,
)
from backend.queueing_engine.simulation.shared_playback import PlaybackConsistencyError, playback_from_replications
from backend.queueing_engine.simulation.shared_replications import run_shared_replications
from tests.helpers import create_user, csrf_header, login, make_sessionmaker


def timeline(*spec: tuple[str, float, float, float], servers: int = 1, mu: float = 4.0):
    """Demand periods (id, start hour, end hour, arrival rate) with one staffing segment each."""
    horizon = OperatingHorizon(int(spec[0][1] * 60), int(spec[-1][2] * 60))
    periods = [DemandPeriod(pid, int(a * 60), int(b * 60), lam, mu) for pid, a, b, lam in spec]
    segments = [StaffingSegment(pid, int(a * 60), int(b * 60), servers) for pid, a, b, _ in spec]
    return horizon, periods, segments


def durations(result: dict) -> list[float]:
    return [row["service_end_hours"] - row["service_start_hours"] for row in result["customers"]
            if row["service_start_hours"] is not None]


# ── Exact checks (section 5, checks 2-6) ────────────────────────────────────


def test_one_customer_on_one_counter_waits_zero_and_takes_the_recorded_quarter_hour():
    horizon, periods, segments = timeline(("d", 0, 1, 1.0))
    result = simulate_prescribed(horizon, periods, segments, [(0.0, 0.5)], closing_policy=DRAIN,
                                 service_samples={"d": [0.25]})
    row = result["customers"][0]
    assert row["wait_hours"] == 0.0
    assert row["service_end_hours"] - row["service_start_hours"] == 0.25
    provenance = result["provenance"]
    assert provenance["engine_version"] == RECORDED_ENGINE_VERSION
    assert provenance["service_model"] == "recorded"
    assert provenance["inputs"]["service_samples_hours"] == {"d": [0.25]}
    assert provenance["service_fallbacks"] == []


def test_equal_recorded_durations_give_deterministic_service():
    horizon, periods, segments = timeline(("d", 0, 2, 4.0), servers=2)
    arrivals = [(k * 0.125, quantile) for k, quantile in enumerate([0.0, 0.3, 0.6, 0.99, 0.5, 0.1, 0.75, 0.25])]
    result = simulate_prescribed(horizon, periods, segments, arrivals, closing_policy=DRAIN,
                                 service_samples={"d": [0.375] * 5})
    assert durations(result) == [0.375] * 8
    seeded = simulate_shared_replication(horizon, periods, segments, seed_sequence=np.random.SeedSequence(3),
                                         closing_policy=DRAIN, service_samples={"d": [0.375] * 5})
    assert seeded["customers"]
    assert all(value == pytest.approx(0.375, abs=1e-12) for value in durations(seeded))


def test_the_duration_comes_from_the_period_where_service_starts_and_is_kept_across_the_boundary():
    horizon, periods, segments = timeline(("p1", 0, 1, 2.0), ("p2", 1, 2, 2.0))
    samples = {"p1": [0.75], "p2": [0.125]}
    result = simulate_prescribed(horizon, periods, segments, [(0.5, 0.5), (0.75, 0.5)], closing_policy=DRAIN,
                                 service_samples=samples)
    first, second = result["customers"]
    # Customer 1 starts in p1 and ends in p2 with its p1 duration; customer 2 arrives in p1 but starts in p2.
    assert (first["service_start_hours"], first["service_end_hours"]) == (0.5, 1.25)
    assert (second["service_start_hours"], second["service_end_hours"]) == (1.25, 1.375)


def test_the_quantile_picks_from_the_sorted_recorded_durations():
    horizon, periods, segments = timeline(("d", 0, 1, 3.0), servers=3)
    result = simulate_prescribed(horizon, periods, segments, [(0.0, 0.0), (0.0625, 0.5), (0.125, 0.99)],
                                 closing_policy=DRAIN, service_samples={"d": [0.5, 0.125, 0.25]})
    assert durations(result) == [0.125, 0.25, 0.5]


@pytest.mark.parametrize("quantile", [1.0, -0.125, float("nan")])
def test_a_quantile_outside_zero_to_one_is_refused(quantile):
    horizon, periods, segments = timeline(("d", 0, 1, 1.0))
    with pytest.raises(SharedSegmentError):
        simulate_prescribed(horizon, periods, segments, [(0.0, quantile)], closing_policy=DRAIN,
                            service_samples={"d": [0.25]})


def test_after_closing_drain_services_use_the_final_periods_durations():
    horizon, periods, segments = timeline(("p1", 0, 1, 2.0), ("p2", 1, 2, 2.0))
    samples = {"p1": [0.75], "p2": [0.375]}
    arrivals = [(1.75, 0.5), (1.875, 0.5)]
    drain = simulate_prescribed(horizon, periods, segments, arrivals, closing_policy=DRAIN, service_samples=samples)
    assert [(row["service_start_hours"], row["service_end_hours"]) for row in drain["customers"]] == [
        (1.75, 2.125), (2.125, 2.5)]
    cutoff = simulate_prescribed(horizon, periods, segments, arrivals, closing_policy=HARD_CUTOFF,
                                 service_samples=samples)
    assert [row["status"] for row in cutoff["customers"]] == ["departed", "unserved_at_close"]


def test_a_period_without_recordings_borrows_the_nearest_earlier_then_later_period():
    _, periods, _ = timeline(("a", 0, 1, 1.0), ("b", 1, 2, 1.0), ("c", 2, 3, 1.0), ("d", 3, 4, 1.0))
    resolved, fallbacks = resolve_service_samples(periods, {"b": [0.25], "c": [], "d": [0.5]})
    assert resolved == [(0.25,), (0.25,), (0.25,), (0.5,)]
    assert fallbacks == [{"period_id": "a", "uses_period_id": "b"}, {"period_id": "c", "uses_period_id": "b"}]


def test_the_engine_uses_and_lists_the_fallback_period():
    horizon, periods, segments = timeline(("a", 0, 1, 1.0), ("b", 1, 2, 1.0), ("c", 2, 3, 1.0))
    result = simulate_prescribed(horizon, periods, segments, [(2.5, 0.5)], closing_policy=DRAIN,
                                 service_samples={"a": [0.125], "b": [0.25]})
    assert durations(result) == [0.25]
    assert result["provenance"]["service_fallbacks"] == [{"period_id": "c", "uses_period_id": "b"}]


@pytest.mark.parametrize("samples", [
    {}, {"a": []}, {"zzz": [0.1]}, {"a": [0.0]}, {"a": [-0.25]}, {"a": [float("nan")]}, {"a": [float("inf")]},
    {"a": [True]}, {"a": "0.25"}, [("a", [0.25])],
])
def test_unusable_recorded_durations_are_refused(samples):
    _, periods, _ = timeline(("a", 0, 1, 1.0))
    with pytest.raises(SharedSegmentError):
        resolve_service_samples(periods, samples)


def test_recorded_mode_keeps_the_arrivals_and_draws_quantiles_from_its_own_stream():
    horizon, periods, segments = timeline(("d", 0, 4, 6.0), servers=2)
    exponential = simulate_shared_replication(horizon, periods, segments, seed_sequence=np.random.SeedSequence(9),
                                              closing_policy=DRAIN)
    recorded = simulate_shared_replication(horizon, periods, segments, seed_sequence=np.random.SeedSequence(9),
                                           closing_policy=DRAIN, service_samples={"d": [0.1, 0.2, 0.3]})
    assert [row["arrival_hours"] for row in recorded["customers"]] == [
        row["arrival_hours"] for row in exponential["customers"]]
    quantiles = np.random.default_rng(np.random.SeedSequence(9).spawn(3)[2]).random(len(recorded["customers"]))
    assert [row["unit_work"] for row in recorded["customers"]] == [float(value) for value in quantiles]
    assert exponential["provenance"]["engine_version"] == ENGINE_VERSION
    assert "service_model" not in exponential["provenance"]


def test_the_default_path_is_unchanged_when_no_durations_are_given():
    horizon, periods, segments = timeline(("p1", 0, 1, 3.0), ("p2", 1, 2, 5.0), servers=2)
    plain = run_shared_replications(horizon, periods, segments, replications=3, seed=5, closing_policy=DRAIN)
    explicit = run_shared_replications(horizon, periods, segments, replications=3, seed=5, closing_policy=DRAIN,
                                       service_samples=None)
    assert plain == explicit
    assert plain["provenance"]["engine_version"] == ENGINE_VERSION
    assert "service_samples_hours" not in plain["provenance"]["inputs"]


def test_same_seed_same_result_and_a_checked_replay():
    horizon, periods, segments = timeline(("p1", 0, 1, 3.0), ("p2", 1, 2, 5.0), servers=2)
    samples = {"p1": [0.25, 0.5, 0.125], "p2": [0.375, 0.25]}
    first = run_shared_replications(horizon, periods, segments, replications=3, seed=11, closing_policy=DRAIN,
                                    service_samples=samples)
    second = run_shared_replications(horizon, periods, segments, replications=3, seed=11, closing_policy=DRAIN,
                                     service_samples=samples)
    assert first == second
    assert first["provenance"]["engine_version"] == RECORDED_ENGINE_VERSION
    assert first["provenance"]["inputs"]["service_samples_hours"] == samples
    for index in range(3):
        playback = playback_from_replications(first, index)
        assert playback["summary"] == first["replications"][index]
        assert playback["replication"]["engine_version"] == RECORDED_ENGINE_VERSION
    assert first["replications"] != run_shared_replications(
        horizon, periods, segments, replications=3, seed=11, closing_policy=DRAIN)["replications"]


def test_a_replay_with_changed_durations_is_refused():
    horizon, periods, segments = timeline(("p1", 0, 2, 4.0), servers=1)
    result = run_shared_replications(horizon, periods, segments, replications=2, seed=4, closing_policy=DRAIN,
                                     service_samples={"p1": [0.25, 0.5]})
    tampered = {**result, "provenance": {**result["provenance"], "inputs": {
        **result["provenance"]["inputs"], "service_samples_hours": {"p1": [0.125, 0.5]}}}}
    with pytest.raises(PlaybackConsistencyError):
        playback_from_replications(tampered, 0)
    missing = {**result, "provenance": {**result["provenance"], "inputs": {
        key: value for key, value in result["provenance"]["inputs"].items() if key != "service_samples_hours"}}}
    with pytest.raises(PlaybackConsistencyError, match="do not match its engine version"):
        playback_from_replications(missing, 0)


# ── Statistical checks (section 5, checks 7-10) ─────────────────────────────


def test_simulated_durations_have_the_recorded_mean_within_its_99_percent_interval():
    samples = [float(value) for value in np.random.default_rng(11).lognormal(math.log(0.2), 0.5, 300)]
    horizon, periods, segments = timeline(("d", 0, 24, 3.0))
    drawn: list[float] = []
    for child in np.random.SeedSequence(21).spawn(30):
        result = simulate_shared_replication(horizon, periods, segments, seed_sequence=child, closing_policy=DRAIN,
                                             service_samples={"d": samples})
        drawn += durations(result)
    mean, sd = statistics.fmean(samples), statistics.pstdev(samples)
    assert abs(statistics.fmean(drawn) - mean) <= 2.576 * sd / math.sqrt(len(drawn))


def test_a_large_exponential_recording_waits_like_the_exponential_mode():
    samples = [float(value) for value in np.random.default_rng(12).exponential(0.25, 20000)]
    mu = 1.0 / statistics.fmean(samples)
    horizon = OperatingHorizon(0, 480)
    periods = [DemandPeriod("d", 0, 480, 3.2, mu)]
    segments = [StaffingSegment("d", 0, 480, 1)]
    waits = {}
    for name, given in (("exponential", None), ("recorded", {"d": samples})):
        result = run_shared_replications(horizon, periods, segments, replications=400, seed=31,
                                         closing_policy=DRAIN, service_samples=given)
        waits[name] = result["summary"]["waiting_time"]["mean_of_replication_means_hours"]
    gap = abs(waits["recorded"]["mean"] - waits["exponential"]["mean"])
    assert gap <= 1.96 * math.hypot(waits["recorded"]["se"], waits["exponential"]["se"]), waits


def _gamma_day(replications: int, seed: int) -> tuple[dict, list[float]]:
    samples = [float(value) for value in np.random.default_rng(13).gamma(2.0, 0.125, 2000)]
    horizon = OperatingHorizon(0, 1440)
    periods = [DemandPeriod("d", 0, 1440, 12.0, 1.0 / statistics.fmean(samples))]
    segments = [StaffingSegment("d", 0, 1440, 4)]
    return run_shared_replications(horizon, periods, segments, replications=replications, seed=seed,
                                   closing_policy=DRAIN, service_samples={"d": samples}), samples


def test_littles_law_holds_on_a_long_recorded_day():
    result, _ = _gamma_day(20, 41)
    rows = result["replications"]
    for row in rows:  # sample-path identity: waiting customer-hours are the sum of the waits (DRAIN serves all)
        assert row["unserved"] == 0
        assert row["total_waiting_hours"] == pytest.approx(row["wait_sum_hours"], rel=1e-9)
    horizon_hours = 24.0 * len(rows)
    in_horizon = math.fsum(row["waiting_hours_before_close"] for row in rows) / horizon_hours
    rate_times_wait = math.fsum(row["wait_sum_hours"] for row in rows) / horizon_hours
    # The gap is only the waiting done after closing (the finite-horizon boundary term).
    assert abs(in_horizon - rate_times_wait) <= 0.02 * rate_times_wait


def test_the_analytical_mgc_estimate_is_of_the_same_order_as_the_recorded_run():
    result, samples = _gamma_day(30, 51)
    simulated = result["summary"]["waiting_time"]["customer_weighted_mean_hours"]["value"]
    mean = statistics.fmean(samples)
    analytical = select_model(12.0, 1.0 / mean, 4, variance=statistics.pvariance(samples))
    assert analytical["name"] == "M/G/c"
    estimate = float(analytical["metrics"]["Wq"])
    # Reported, not asserted equal: M/G/c is an approximation and the day starts empty.
    assert 0.1 <= simulated / estimate <= 10, (simulated, estimate)


# ── API: customer-record uploads in the full-day run ────────────────────────

EVENT_SETUP = {
    "queue_structure": "shared_queue", "fixed_server_count": 2, "staffing_varies_by_period": False,
    "capacity_mode": "unlimited", "total_system_capacity": None, "abandonment_mode": "not_modeled",
    "patience_rate_per_hour": None, "event_period_basis": "representative_day",
    "segments": [{"id": "s1", "start_time": "08:00:00", "end_time": "09:00:00"},
                 {"id": "s2", "start_time": "09:00:00", "end_time": "10:00:00"},
                 {"id": "s3", "start_time": "10:00:00", "end_time": "11:00:00"}],
}
SAMPLES = {"s1": [0.25, 0.125, 0.5], "s2": [0.125, 0.25], "s3": [0.375]}


def _event_row(segment_id: str, rate: float) -> dict[str, Any]:
    samples = SAMPLES[segment_id]
    mean = statistics.fmean(samples)
    return {"time": segment_id, "segment_id": segment_id, "lambda": rate, "mu": 1.0 / mean, "c": 2,
            "variance": statistics.pvariance(samples), "observation_days": 3, "service_time_source": "empirical",
            "service_samples_hours": list(samples)}


def _plan_result(row: dict[str, Any], servers: int) -> dict[str, Any]:
    return {"time": row["time"], "lambda_": row["lambda"], "mu": row["mu"], "c_current": 2, "c_optimal": servers,
            "rho_current": 0.5, "rho_optimal": 0.5, "Wq_current": 0.1, "Wq_optimal": 0.1, "Lq_current": 0.1,
            "Lq_optimal": 0.1, "cost_current": 100, "cost_optimal": 100, "current_stable": True,
            "optimized_stable": True}


def _plan_input(row: dict[str, Any]) -> dict[str, Any]:
    """What Suggested plans saves for a row (frontend segmentsOf): no recorded durations."""
    return {key: row[key] for key in ("time", "lambda", "mu", "c", "variance")}


def _workspace(db_engine, rows: list[dict[str, Any]], *, setup: dict | None = None, servers: list[int] | None = None,
               email: str = "owner@example.com") -> dict[str, int]:
    with make_sessionmaker(db_engine)() as db:
        existing = db.execute(select(User).where(User.email_normalized == email)).scalar_one_or_none()
    user = existing or create_user(db_engine, email, "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(user_id=user.id, name="Shared line", queue_setup_json=setup or EVENT_SETUP,
                                   setup_status="ready")
        db.add(analysis)
        db.flush()
        dataset = Dataset(user_id=user.id, analysis_id=analysis.id, name="Records", source_filename="records.csv",
                          source_format="csv", row_count=len(rows), normalized_json=rows,
                          validation_report_json={"ok": True, "message": "Input data is valid."})
        db.add(dataset)
        db.flush()
        scenario = Scenario(
            user_id=user.id, analysis_id=analysis.id, dataset_id=dataset.id, name="Plan",
            settings_json={"calculation": {
                "schema_version": 1, "engine_version": "novaq-2026-09-system-v2",
                "input_segments": [_plan_input(row) for row in rows], "options": {}, "what_if_multiplier": 1,
                "calculated_at": "2026-10-12T00:00:00+00:00"}},
            results_json={"results": [_plan_result(row, count) for row, count in zip(rows, servers or [3] * len(rows))]},
        )
        db.add(scenario)
        db.commit()
        return {"analysis_id": analysis.id, "dataset_id": dataset.id, "scenario_id": scenario.id}


def _ready(client, db_engine, rows: list[dict[str, Any]], **options: Any) -> dict[str, int]:
    ids = _workspace(db_engine, rows, **options)
    assert login(client, "owner@example.com", "pw") == 200
    assert client.put(f"/analyses/{ids['analysis_id']}/closing-policy", headers=csrf_header(client),
                      json={"closing_policy": "DRAIN"}).status_code == 200
    assert client.post(f"/analyses/{ids['analysis_id']}/workflow/selection", headers=csrf_header(client),
                       json={"scenario_id": ids["scenario_id"]}).status_code == 200
    return ids


def _compat(client, analysis_id: int) -> dict[str, Any]:
    response = client.post(f"/analyses/{analysis_id}/continuous/compatibility", headers=csrf_header(client), json={})
    assert response.status_code == 200, response.text
    return response.json()


def _run(client, analysis_id: int, plan: str = "current"):
    return client.post(f"/analyses/{analysis_id}/continuous/runs", headers=csrf_header(client),
                       json={"plan": plan, "replications": 2, "seed": 7})


def _job_count(db_engine) -> int:
    with make_sessionmaker(db_engine)() as db:
        return db.execute(select(func.count()).select_from(Job).where(Job.kind == shared_continuous.JOB_KIND)).scalar_one()


ALL_ROWS = [_event_row("s1", 4.0), _event_row("s2", 6.0), _event_row("s3", 2.0)]


def test_customer_records_run_with_their_recorded_durations(db_engine, client):
    ids = _ready(client, db_engine, ALL_ROWS)
    compat = _compat(client, ids["analysis_id"])
    for plan in ("current", "suggested"):
        view = compat["plans"][plan]
        assert view["compatible"] is True, view
        assert view["service_model"] == "recorded"
        assert view["service_fallbacks"] == []
        assert view["horizon"] == {"start_minute": 480, "end_minute": 660}
    assert compat["plans"]["current"]["expected_customers_per_day"] == pytest.approx(12.0)
    current, suggested = _run(client, ids["analysis_id"]), _run(client, ids["analysis_id"], "suggested")
    assert current.status_code == 200, current.text
    assert suggested.status_code == 200, suggested.text
    for response, servers in ((current, [2, 2, 2]), (suggested, [3, 3, 3])):
        evidence = response.json()["evidence"]
        provenance = evidence["result"]["provenance"]
        assert provenance["engine_version"] == RECORDED_ENGINE_VERSION
        assert provenance["inputs"]["service_samples_hours"] == SAMPLES
        assert [item["servers"] for item in provenance["inputs"]["staffing_segments"]] == servers
        assert [item["period_id"] for item in provenance["inputs"]["demand_periods"]] == ["s1", "s2", "s3"]
        assert evidence["params"]["service_model"] == "recorded"
        assert evidence["params"]["engine_version"] == RECORDED_ENGINE_VERSION
    run_id = current.json()["evidence"]["id"]
    replay = client.get(f"/analyses/{ids['analysis_id']}/continuous/runs/{run_id}/replications/1/playback")
    assert replay.status_code == 200, replay.text
    assert [item["period_id"] for item in replay.json()["by_period"]] == ["s1", "s2", "s3"]
    runs = client.get(f"/analyses/{ids['analysis_id']}/continuous/runs").json()["runs"]
    assert {run["service_model"] for run in runs} == {"recorded"}


def test_a_segment_without_customers_uses_the_nearest_recorded_period(db_engine, client):
    ids = _ready(client, db_engine, ALL_ROWS[:2], servers=[3, 3])
    compat = _compat(client, ids["analysis_id"])
    current = compat["plans"]["current"]
    assert current["compatible"] is True, current
    assert current["service_fallbacks"] == [{"period_id": "s3", "uses_period_id": "s2"}]
    # The plan has no server count for s3, and NovaQ does not invent one.
    suggested = compat["plans"]["suggested"]
    assert suggested["compatible"] is False
    reason = next(item for item in suggested["reasons"] if item["code"] == "plan_missing_periods")
    assert reason["periods"] == ["s3"]
    response = _run(client, ids["analysis_id"])
    assert response.status_code == 200, response.text
    inputs = response.json()["evidence"]["result"]["provenance"]["inputs"]
    empty = inputs["demand_periods"][2]
    assert (empty["period_id"], empty["arrival_rate_per_hour"]) == ("s3", 0.0)
    assert empty["service_rate_per_hour"] == pytest.approx(1.0 / statistics.fmean(SAMPLES["s2"]))
    assert inputs["staffing_segments"][2]["servers"] == 2  # the Setup's fixed server count
    assert inputs["service_samples_hours"] == {"s1": SAMPLES["s1"], "s2": SAMPLES["s2"]}
    assert response.json()["evidence"]["result"]["provenance"]["service_fallbacks"] == [
        {"period_id": "s3", "uses_period_id": "s2"}]
    assert _run(client, ids["analysis_id"], "suggested").status_code == 422


def test_date_by_date_customer_records_are_refused(db_engine, client):
    rows = [{**row, "time": f"2026-09-08 {row['segment_id']} UTC"} for row in ALL_ROWS]
    ids = _ready(client, db_engine, rows, setup={**EVENT_SETUP, "event_period_basis": "per_date"})
    current = _compat(client, ids["analysis_id"])["plans"]["current"]
    assert current["compatible"] is False
    assert "per_date_data" in [reason["code"] for reason in current["reasons"]]
    assert _run(client, ids["analysis_id"]).status_code == 422
    assert _job_count(db_engine) == 0


def test_a_row_outside_the_setup_segments_is_refused(db_engine, client):
    rows = [*ALL_ROWS, {**_event_row("s3", 1.0), "time": "s9", "segment_id": "s9"}]
    ids = _ready(client, db_engine, rows)
    current = _compat(client, ids["analysis_id"])["plans"]["current"]
    reason = next(item for item in current["reasons"] if item["code"] == "timeline_invalid")
    assert any("s9" in problem for problem in reason["problems"])


def test_records_without_durations_still_need_counts_per_period(db_engine, client):
    rows = [{**row, "service_samples_hours": []} if row["segment_id"] == "s2" else row for row in ALL_ROWS]
    ids = _ready(client, db_engine, rows)
    current = _compat(client, ids["analysis_id"])["plans"]["current"]
    assert "service_time_variation" in [reason["code"] for reason in current["reasons"]]


def test_durations_too_large_to_store_are_refused_before_simulating(db_engine, client, app, monkeypatch):
    ids = _ready(client, db_engine, ALL_ROWS)
    monkeypatch.setattr(app.state.settings, "result_jsonb_max_bytes", 32)
    called: list[bool] = []
    monkeypatch.setattr(shared_continuous, "run_shared_replications", lambda *a, **k: called.append(True))
    response = _run(client, ids["analysis_id"])
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "evidence_too_large"
    assert called == []
    assert _job_count(db_engine) == 0


# ── The real path: Setup, upload and run through the public routes only ─────


def _records_csv() -> bytes:
    """SYNTHETIC customer records on two dates, 08:00-10:00, no customer after 09:30 on either date."""
    lines = ["arrival_time,service_start,service_end"]
    for date in ("2026-09-08", "2026-09-09"):
        for minute, wait, service in ((5, 0, 6), (14, 0, 9), (20, 3, 4), (47, 0, 12), (65, 0, 7), (80, 2, 5)):
            arrival = 8 * 60 + minute
            start, end = arrival + wait, arrival + wait + service
            stamp = lambda m: f"{date}T{m // 60:02d}:{m % 60:02d}:00Z"  # noqa: E731
            lines.append(f"{stamp(arrival)},{stamp(start)},{stamp(end)}")
    return "\n".join(lines).encode()


def test_a_shared_customer_record_upload_runs_the_full_day_through_the_public_routes(db_engine, client):
    create_user(db_engine, "owner@example.com", "pw")
    assert login(client, "owner@example.com", "pw") == 200
    setup = {**EVENT_SETUP, "segments": [
        {"id": "s1", "start_time": "08:00:00", "end_time": "09:00:00", "active_queue_ids": None},
        {"id": "s2", "start_time": "09:00:00", "end_time": "10:00:00", "active_queue_ids": None}]}
    created = client.post("/analyses", headers=csrf_header(client), json={"name": "Shared records", "queue_setup": setup})
    assert created.status_code == 201, created.text
    analysis_id = created.json()["analysis"]["id"]
    upload = client.post(f"/analyses/{analysis_id}/datasets", headers=csrf_header(client),
                         files={"file": ("records.csv", _records_csv(), "text/csv")})
    assert upload.status_code == 201, upload.text
    assert client.put(f"/analyses/{analysis_id}/closing-policy", headers=csrf_header(client),
                      json={"closing_policy": "DRAIN"}).status_code == 200
    current = _compat(client, analysis_id)["plans"]["current"]
    assert current["compatible"] is True, current
    assert current["service_model"] == "recorded"
    response = _run(client, analysis_id)
    assert response.status_code == 200, response.text
    provenance = response.json()["evidence"]["result"]["provenance"]
    assert provenance["engine_version"] == RECORDED_ENGINE_VERSION
    assert [item["period_id"] for item in provenance["inputs"]["demand_periods"]] == ["s1", "s2"]


def test_the_older_shared_paths_accept_a_representative_day_upload(db_engine, client):
    """B4b addendum section 5: Suggested plans, the period-by-period run, Monte Carlo, data dates, observed waits."""
    create_user(db_engine, "owner@example.com", "pw")
    assert login(client, "owner@example.com", "pw") == 200
    setup = {**EVENT_SETUP, "segments": [
        {"id": "s1", "start_time": "08:00:00", "end_time": "09:00:00", "active_queue_ids": None},
        {"id": "s2", "start_time": "09:00:00", "end_time": "10:00:00", "active_queue_ids": None}]}
    analysis_id = client.post("/analyses", headers=csrf_header(client),
                              json={"name": "Shared records", "queue_setup": setup}).json()["analysis"]["id"]
    dataset = client.post(f"/analyses/{analysis_id}/datasets", headers=csrf_header(client),
                          files={"file": ("records.csv", _records_csv(), "text/csv")}).json()["dataset"]
    rows = dataset["normalized"]
    assert [(row["time"], row["lambda"], row["observation_days"]) for row in rows] == [("s1", 4.0, 2), ("s2", 2.0, 2)]
    # The upload's own date range is stored at upload (B11), whatever the basis.
    listed = client.get(f"/analyses/{analysis_id}/datasets").json()["datasets"]
    assert listed[0]["data_dates"] == {"first": "2026-09-08", "last": "2026-09-09", "source": "stored_at_upload"}
    plans = client.post("/optimize/batch", headers=csrf_header(client), json={"segments": [
        {key: row[key] for key in ("time", "lambda", "mu", "c", "variance")} for row in rows]})
    assert plans.status_code == 200, plans.text
    assert [item["time"] for item in plans.json()["results"]] == ["s1", "s2"]
    older = client.post(f"/analyses/{analysis_id}/workflow/simulation/des/current", headers=csrf_header(client),
                        json={"sim_hours": 8, "queue_overload_threshold": 10, "max_events": 3000, "seed": 7,
                              "carryover": False})
    assert older.status_code == 200, older.text
    monte_carlo = client.post(f"/analyses/{analysis_id}/workflow/simulation/mc/current", headers=csrf_header(client),
                              json={"num_trials": 50, "failure_threshold": 0.75, "failure_rate_cap": 0.05, "seed": 7})
    assert monte_carlo.status_code == 200, monte_carlo.text
    observed = client.get(f"/analyses/{analysis_id}/workflow/observed-wait")
    assert observed.status_code == 200, observed.text
    assert {period["time"] for period in observed.json()["periods"]} == {"s1", "s2"}
