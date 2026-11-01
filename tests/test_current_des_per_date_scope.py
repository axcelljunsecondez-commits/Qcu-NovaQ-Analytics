"""Synthetic Current DES date-scope regressions; no operational observations."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

import pandas as pd
import pytest
from sqlalchemy import func, select

from backend.api import workflow
from backend.api.analysis_schemas import QueueSetup
from backend.data.analysis_ingestion import normalize_analysis_input
from backend.db.models import AnalysisProject, Dataset, Job
from backend.queueing_engine.simulation.simulation import simulate_segments_with_trace
from tests.helpers import create_user, csrf_header, login, make_sessionmaker

DATES = ("2026-08-03", "2026-08-04")
QUEUES = ("synthetic_lane_a", "synthetic_lane_b")
SETUP = {
    "queue_structure": "separate_queues",
    "event_period_basis": "per_date",
    "queue_ids": list(QUEUES),
    "fixed_server_count": 2,
    "staffing_varies_by_period": False,
    "capacity_mode": "unlimited",
    "total_system_capacity": None,
    "abandonment_mode": "not_modeled",
    "patience_rate_per_hour": None,
    "separate_queue_closure_policy": "drain_existing",
    "segments": [
        {"id": "s1", "start_time": "08:00:00", "end_time": "09:00:00"},
        {"id": "s2", "start_time": "09:00:00", "end_time": "10:00:00"},
    ],
}
DES_REQUEST = {"sim_hours": 2.0, "max_events": 300, "seed": 42}


@pytest.fixture
def synthetic_rows():
    # Forty-four explicitly synthetic observations: 1 then 10 arrivals per
    # lane/hour/date, each served for 72 seconds (= .02 hours), without overlap.
    events = []
    for day, count in zip(DATES, (1, 10)):
        for hour in (8, 9):
            for queue in QUEUES:
                for index in range(count):
                    at = datetime.fromisoformat(day).replace(hour=hour, minute=5) + timedelta(minutes=5 * index)
                    events.append({
                        "arrival_time": at.isoformat(),
                        "service_start": at.isoformat(),
                        "service_end": (at + timedelta(seconds=72)).isoformat(),
                        "queue_id": queue,
                    })
    assert len(events) == 44
    records, provenance = normalize_analysis_input(pd.DataFrame(events), QueueSetup.model_validate(SETUP))
    assert provenance["schema"] == "customer_events"
    assert len(records) == 8
    assert [row["lambda"] for row in records] == [1.0] * 4 + [10.0] * 4
    assert all(row["service_samples_hours"] == [0.02] * int(row["lambda"]) for row in records)
    return records


@pytest.fixture
def save_current(db_engine, client):
    email = "synthetic-date-scope@example.com"
    user = create_user(db_engine, email, "pw")
    assert login(client, email, "pw") == 200

    def save(rows, setup=None):
        with make_sessionmaker(db_engine)() as db:
            analysis = AnalysisProject(
                user_id=user.id,
                name="SYNTHETIC date scope",
                queue_setup_json=deepcopy(SETUP if setup is None else setup),
                setup_status="ready",
            )
            db.add(analysis)
            db.flush()
            dataset = Dataset(
                user_id=user.id,
                analysis_id=analysis.id,
                name="SYNTHETIC events",
                source_filename="synthetic-events.csv",
                source_format="csv",
                row_count=len(rows),
                normalized_json=deepcopy(rows),
                validation_report_json={"ok": True, "schema": "customer_events"},
            )
            db.add(dataset)
            db.commit()
            return analysis.id, dataset.id

    return save


def _post_des(client, analysis_id):
    return client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des/current",
        headers=csrf_header(client),
        json=DES_REQUEST,
    )


def _assert_engine_unchanged(client, analysis_id, rows, setup):
    # Independent direct call to the unchanged engine, rather than a hardcoded
    # response copied from the adapter or an altered expected result fixture.
    expected = simulate_segments_with_trace(deepcopy(rows), queue_setup=deepcopy(setup), **DES_REQUEST)
    response = _post_des(client, analysis_id)
    assert response.status_code == 200, response.text
    result = response.json()["evidence"]["result"]
    assert result.pop("provenance") == "CURRENT"
    result.pop("summary")
    assert result == expected  # Includes exact result values, trace, time and event metadata.
    return result


@pytest.mark.parametrize("case", [
    "two_dates", "two_dates_reversed", "missing_lane_cross_date", "complementary_dates",
    "malformed_label", "invalid_calendar_date", "unknown_segment", "missing_segment",
    "duplicate_identity", "duplicate_identity_different_label", "conflicting_period_segments",
])
def test_ambiguous_or_invalid_per_date_current_refused_before_engine_or_job(
    case, synthetic_rows, save_current, client, db_engine, monkeypatch,
):
    rows = deepcopy(synthetic_rows)
    if case == "two_dates_reversed":
        rows.reverse()
    elif case == "missing_lane_cross_date":
        rows = [row for row in rows if not (
            row["time"].startswith(DATES[0]) and row["segment_id"] == "s2" and row["queue_id"] == QUEUES[0]
        )]
    elif case == "complementary_dates":
        rows = [row for row in rows if (
            row["time"].startswith(DATES[0]) and row["segment_id"] == "s1"
        ) or (row["time"].startswith(DATES[1]) and row["segment_id"] == "s2")]
        rows.reverse()
    elif case != "two_dates":
        rows = rows[:4]
        if case == "malformed_label":
            rows[0]["time"] = "not-a-calendar-period"
        elif case == "invalid_calendar_date":
            for row in rows:
                row["time"] = row["time"].replace(DATES[0], "2026-02-30")
        elif case == "unknown_segment":
            extra = deepcopy(rows[0])
            extra.update(time=f"{DATES[0]} unknown UTC", segment_id="unknown")
            rows.append(extra)
        elif case == "missing_segment":
            rows = [row for row in rows if row["segment_id"] == "s1"]
        elif case in {"duplicate_identity", "duplicate_identity_different_label"}:
            extra = deepcopy(rows[0])
            if case == "duplicate_identity_different_label":
                extra["time"] = f"{DATES[0]} s1 alternate-label UTC"
            rows.append(extra)
        elif case == "conflicting_period_segments":
            rows[0]["segment_id"] = "s2"
    analysis_id, dataset_id = save_current(rows)
    with make_sessionmaker(db_engine)() as db:
        before_jobs = db.scalar(select(func.count()).select_from(Job))
        saved_rows = deepcopy(db.get(Dataset, dataset_id).normalized_json)

    def forbidden_engine(*args, **kwargs):
        pytest.fail("Invalid Current date scope reached the DES engine")

    monkeypatch.setattr(workflow, "simulate_segments_with_trace", forbidden_engine)
    response = _post_des(client, analysis_id)
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "Current dataset records are invalid."}
    with make_sessionmaker(db_engine)() as db:
        assert db.scalar(select(func.count()).select_from(Job)) == before_jobs
        assert db.get(Dataset, dataset_id).normalized_json == saved_rows
        assert db.get(AnalysisProject, analysis_id).queue_setup_json == SETUP


@pytest.mark.parametrize("basis", ["per_date", "representative_day", None])
def test_coherent_day_preserves_exact_engine_results_and_trace(
    basis, synthetic_rows, save_current, client,
):
    rows = deepcopy(synthetic_rows[:4])
    setup = deepcopy(SETUP)
    if basis is None:
        setup.pop("event_period_basis")
    else:
        setup["event_period_basis"] = basis
    if basis != "per_date":
        for row in rows:
            row["time"] = row["segment_id"]
    analysis_id, _ = save_current(rows, setup)
    result = _assert_engine_unchanged(client, analysis_id, rows, setup)
    assert len(result["results"]) == 4
    assert result["trace"]
    assert all(row["simulation_supported"] for row in result["results"])


def test_missing_active_lane_in_single_date_keeps_existing_unsupported_result(
    synthetic_rows, save_current, client,
):
    rows = [row for row in synthetic_rows[:4] if not (
        row["segment_id"] == "s2" and row["queue_id"] == QUEUES[0]
    )]
    analysis_id, _ = save_current(rows)
    result = _assert_engine_unchanged(client, analysis_id, rows, SETUP)
    assert not any(row["simulation_supported"] for row in result["results"])
    assert {row["error"] for row in result["results"]} == {
        "Missing empirical segment/queue record for s2/synthetic_lane_a."
    }


@pytest.mark.parametrize("outside_scope", ["no_segments", "basis_absent", "representative_day", "shared"])
def test_other_current_des_scopes_remain_exactly_unchanged(
    outside_scope, synthetic_rows, save_current, client,
):
    rows = deepcopy(synthetic_rows)
    setup = deepcopy(SETUP)
    if outside_scope == "no_segments":
        setup["segments"] = []
    elif outside_scope == "basis_absent":
        setup.pop("event_period_basis")
    elif outside_scope == "representative_day":
        setup["event_period_basis"] = "representative_day"
    else:
        setup["queue_structure"] = "shared_queue"
        for row in rows:
            row["queue_structure"] = "shared_queue"
            row["model_id"] = "mmc"
            row["c"] = 2
    analysis_id, _ = save_current(rows, setup)
    _assert_engine_unchanged(client, analysis_id, rows, setup)


def test_current_mc_still_receives_all_dates_without_des_scope_validation(
    synthetic_rows, save_current, client, monkeypatch,
):
    analysis_id, _ = save_current(synthetic_rows)
    calls = []

    def mc_spy(rows, **kwargs):
        calls.append((deepcopy(rows), kwargs))
        return [{"synthetic_probe": "all dates forwarded"}]

    monkeypatch.setattr(workflow, "mc_simulate_segments", mc_spy)
    response = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/mc/current",
        headers=csrf_header(client),
        json={"num_trials": 2, "seed": 42},
    )
    assert response.status_code == 200, response.text
    assert len(calls) == 1
    assert calls[0][0] == synthetic_rows
    assert calls[0][1] == {
        "num_trials": 2, "failure_threshold": 0.75, "failure_rate_cap": 0.05, "seed": 42,
    }
    assert response.json()["evidence"]["result"] == {
        "results": [{"synthetic_probe": "all dates forwarded"}], "provenance": "CURRENT",
    }
