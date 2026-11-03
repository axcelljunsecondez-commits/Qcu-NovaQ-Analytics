"""Separate-lines Current runs on a per-date file must use every date's records (AGENTS.md §6).

Defect (Kyoya review 2026-10-30): with ``event_period_basis = per_date`` ingestion stamps the
Setup segment id on every date's records, and ``_parallel_schedule`` took the first record per
(segment, lane), so a Current DES on a multi-date file simulated date 1 only, or a mix of dates
when date 1 lacked a lane record. The tests below are option-neutral: a Current run must either
simulate every date's records or refuse with a stated reason. A run that silently reports a
subset of the dates, or one "day" assembled from several dates, fails.

All data here is SYNTHETIC.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from backend.api.analysis_schemas import QueueSetup
from backend.data.analysis_ingestion import normalize_analysis_input
from backend.queueing_engine.simulation.simulation import (
    mc_simulate_segments,
    simulate_segments_with_trace,
)
from tests.helpers import create_user, csrf_header, login

SETUP = {
    "queue_structure": "separate_queues",
    "fixed_server_count": 2,
    "staffing_varies_by_period": False,
    "capacity_mode": "unlimited",
    "total_system_capacity": None,
    "abandonment_mode": "not_modeled",
    "patience_rate_per_hour": None,
    "event_period_basis": "per_date",
    "separate_queue_closure_policy": "drain_existing",
    "segments": [
        {"id": "s1", "start_time": "05:00:00", "end_time": "06:00:00", "active_queue_ids": None},
        {"id": "s2", "start_time": "06:00:00", "end_time": "07:00:00", "active_queue_ids": None},
    ],
    "queue_ids": ["a", "b"],
}

# (date, arrival HH:MM, service minutes, lane). Date 2 is much busier on lane a in s1.
DATE_1 = [
    ("2026-08-03", "05:10", 6, "a"), ("2026-08-03", "05:20", 6, "a"), ("2026-08-03", "05:30", 6, "b"),
    ("2026-08-03", "06:10", 6, "a"), ("2026-08-03", "06:20", 6, "b"),
]
DATE_2 = [("2026-08-04", f"05:{minute:02d}", 3, "a") for minute in range(0, 50, 5)] + [
    ("2026-08-04", "05:30", 6, "b"), ("2026-08-04", "06:10", 6, "a"), ("2026-08-04", "06:20", 6, "b"),
]
# The engine's refusal of one schedule built from several records of one (segment, lane) (C-PD guard).
DUPLICATE_REFUSAL = ("Parallel M/G/1 DES received 2 records for s1/a; "
                     "it simulates exactly one record per segment and queue.")


def _frame(events) -> pd.DataFrame:
    rows = []
    for date, arrive, minutes, lane in events:
        start = pd.Timestamp(f"{date}T{arrive}:00Z")
        rows.append({"arrival_time": start.isoformat(), "service_start": start.isoformat(),
                     "service_end": (start + pd.Timedelta(minutes=minutes)).isoformat(), "queue_id": lane})
    return pd.DataFrame(rows)


def _records(events) -> list[dict]:
    return _records_for(events, SETUP)


def _records_for(events, setup: dict) -> list[dict]:
    records, _ = normalize_analysis_input(_frame(events), QueueSetup.model_validate(setup))
    return records


def _csv(events) -> bytes:
    return _frame(events).to_csv(index=False).encode("utf-8")


def _labels(records) -> set[tuple[str, str]]:
    return {(str(row["time"]), str(row["queue_id"])) for row in records}


def _assert_all_dates_or_refused(rows, records, reason: str | None = None) -> None:
    """Every record's (period, lane) is simulated, or nothing is reported as simulated.

    With ``reason`` (K-CPD-5), a refusal must give exactly that engine reason on every row.
    """
    supported = [row for row in rows if row.get("simulation_supported") is True]
    if not supported:
        assert rows and all(row.get("error") for row in rows), "a refusal must state its reason"
        if reason is not None:
            assert {row.get("error") for row in rows} == {reason}
        return
    assert _labels(supported) == _labels(records), (
        "a Current run reported only some dates' records as simulated: "
        f"{sorted(_labels(records) - _labels(supported))} missing"
    )


def test_ingestion_repeats_the_setup_segment_id_on_every_date():
    """Precondition of the defect: a per-date file has one record per date x segment x lane."""
    records = _records(DATE_1 + DATE_2)
    assert len(records) == 8
    assert {row["segment_id"] for row in records} == {"s1", "s2"}
    assert len({row["time"] for row in records}) == 4


def test_current_des_uses_every_date_or_refuses():
    records = _records(DATE_1 + DATE_2)
    result = simulate_segments_with_trace(records, sim_hours=1.0, max_events=1000, seed=1, queue_setup=SETUP)
    _assert_all_dates_or_refused(result["results"], records, DUPLICATE_REFUSAL)


def test_current_des_never_builds_one_day_from_several_dates():
    """Date 1 has no lane-b customer in s2; date 2's s2/b record must not fill that gap."""
    events = [event for event in DATE_1 if not (event[1] == "06:20" and event[3] == "b")] + DATE_2
    records = _records(events)
    result = simulate_segments_with_trace(records, sim_hours=1.0, max_events=1000, seed=1, queue_setup=SETUP)
    supported = [row for row in result["results"] if row.get("simulation_supported") is True]
    dates_per_run = {str(row["time"]).split(" ", 1)[0] for row in supported}
    if not supported:  # K-CPD-5: a refusal must name the engine's exact reason
        assert {row.get("error") for row in result["results"]} == {DUPLICATE_REFUSAL}
    if supported and len(dates_per_run) > 1:
        # Several dates in one result are acceptable only when every record is reported.
        _assert_all_dates_or_refused(result["results"], records)


def test_current_monte_carlo_evaluates_every_date_record():
    """Step 3 check: Current Many variations is one analytical row per record, so no date is dropped."""
    records = _records(DATE_1 + DATE_2)
    rows = mc_simulate_segments(records, num_trials=50, seed=3)
    assert _labels(rows) == _labels(records)
    date_2_a = next(row for row in rows if row["time"] == "2026-08-04 s1 UTC" and row["queue_id"] == "a")
    assert date_2_a["lambda"] == 10.0


def _create_analysis(client, headers) -> int:
    response = client.post("/analyses", headers=headers, json={"name": "Per-date lanes", "queue_setup": SETUP})
    assert response.status_code in (200, 201), response.text
    return response.json()["analysis"]["id"]


def _upload(client, headers, analysis_id, events) -> None:
    uploaded = client.post(f"/analyses/{analysis_id}/datasets", headers=headers,
                           files={"file": ("events.csv", _csv(events), "text/csv")})
    assert uploaded.status_code == 201, uploaded.text


def test_current_des_route_uses_every_date_or_refuses(db_engine, client):
    create_user(db_engine, "perdate@example.com", "pw")
    login(client, "perdate@example.com", "pw")
    headers = csrf_header(client)
    analysis_id = _create_analysis(client, headers)
    _upload(client, headers, analysis_id, DATE_1 + DATE_2)
    run = client.post(f"/analyses/{analysis_id}/workflow/simulation/des/current", headers=headers,
                      json={"sim_hours": 1, "max_events": 1000, "seed": 7})
    if run.status_code == 200:
        _assert_all_dates_or_refused(run.json()["evidence"]["result"]["results"], _records(DATE_1 + DATE_2))
    else:
        assert run.status_code == 422, run.text
        assert run.json()["detail"]


def test_current_validation_route_covers_every_date(db_engine, client):
    """Step 3 check: Current validation requires and reads one row per date x segment x lane."""
    create_user(db_engine, "perdate-val@example.com", "pw")
    login(client, "perdate-val@example.com", "pw")
    headers = csrf_header(client)
    analysis_id = _create_analysis(client, headers)
    _upload(client, headers, analysis_id, DATE_1 + DATE_2)
    mc = client.post(f"/analyses/{analysis_id}/workflow/simulation/mc/current", headers=headers,
                     json={"num_trials": 50, "seed": 3})
    assert mc.status_code == 200, mc.text
    validation = client.post(f"/analyses/{analysis_id}/workflow/simulation/validation/current", headers=headers)
    assert validation.status_code == 200, validation.text
    rows = validation.json()["evidence"]["result"]["results"]
    assert _labels(rows) == _labels(_records(DATE_1 + DATE_2))


# ── A0 regression snapshot (SYNTHETIC; generated on unmodified 3ee8fe2c) ─────────────────────────────
#
# Two segments x two lanes; lane b is closed in s2. The fixture was written by running
#   NOVAQ_WRITE_CPD_SNAPSHOT=1 python -m pytest tests/test_current_separate_per_date.py -k snapshot
# on HEAD 3ee8fe2c before any C-PD source change. Without the variable the test only compares.

SNAPSHOT = Path(__file__).parent / "fixtures" / "current_separate_des_snapshot_3ee8fe2c.json"
SNAP_SEGMENTS = [
    {"id": "s1", "start_time": "05:00:00", "end_time": "06:00:00", "active_queue_ids": ["a", "b"]},
    {"id": "s2", "start_time": "06:00:00", "end_time": "07:00:00", "active_queue_ids": ["a"]},
]
SNAP_EVENTS = [
    ("2026-08-03", "05:05", 6, "a"), ("2026-08-03", "05:15", 5, "a"), ("2026-08-03", "05:25", 7, "a"),
    ("2026-08-03", "05:45", 6, "a"), ("2026-08-03", "05:10", 4, "b"), ("2026-08-03", "05:30", 6, "b"),
    ("2026-08-03", "05:50", 5, "b"), ("2026-08-03", "06:05", 6, "a"), ("2026-08-03", "06:20", 5, "a"),
    ("2026-08-03", "06:40", 4, "a"),
]
SNAP_RUN = {"sim_hours": 1, "max_events": 1000, "seed": 7}
# Keys option (a) adds to a per-date result; nothing else may differ from the snapshot.
PER_DATE_ADDED_KEYS = ("execution", "days", "zero_arrival_lane_periods")


def _snap_setup(basis: str) -> dict:
    return {**SETUP, "staffing_varies_by_period": True, "event_period_basis": basis, "segments": SNAP_SEGMENTS}


def _route_result(client, headers, email: str, setup: dict, events, run: dict | None = None):
    response = client.post("/analyses", headers=headers, json={"name": email, "queue_setup": setup})
    assert response.status_code in (200, 201), response.text
    analysis_id = response.json()["analysis"]["id"]
    _upload(client, headers, analysis_id, events)
    return analysis_id, client.post(f"/analyses/{analysis_id}/workflow/simulation/des/current", headers=headers,
                                    json=run or SNAP_RUN)


def _without_added_keys(result: dict) -> dict:
    stripped = {key: value for key, value in result.items() if key not in PER_DATE_ADDED_KEYS}
    for field in ("results", "segments", "trace"):
        stripped[field] = [{k: v for k, v in item.items() if k != "date"} for item in result[field]]
    return stripped


def _encoded(value) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=False)


def test_snapshot_representative_day_and_single_date_results_are_unchanged(db_engine, client):
    records = _records_for(SNAP_EVENTS, _snap_setup("representative_day"))
    engine = simulate_segments_with_trace(records, sim_hours=1.0, max_events=1000, seed=7,
                                          queue_setup=_snap_setup("representative_day"))
    create_user(db_engine, "snapshot@example.com", "pw")
    login(client, "snapshot@example.com", "pw")
    headers = csrf_header(client)
    _, representative = _route_result(client, headers, "rep", _snap_setup("representative_day"), SNAP_EVENTS)
    _, per_date = _route_result(client, headers, "one-date", _snap_setup("per_date"), SNAP_EVENTS)
    assert representative.status_code == 200 and per_date.status_code == 200, (representative.text, per_date.text)
    actual = {
        "representative_day_engine": engine,
        "representative_day_route": representative.json()["evidence"]["result"],
        "single_date_per_date_route": per_date.json()["evidence"]["result"],
    }
    if os.environ.get("NOVAQ_WRITE_CPD_SNAPSHOT") == "1":
        SNAPSHOT.write_text(_encoded({"generated_at": "3ee8fe2c", "data": "SYNTHETIC", **actual}) + "\n",
                            encoding="utf-8")
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    # Representative day: the whole stored result is byte-identical (one date, unchanged path).
    assert _encoded(actual["representative_day_engine"]) == _encoded(expected["representative_day_engine"])
    assert _encoded(actual["representative_day_route"]) == _encoded(expected["representative_day_route"])
    # Single date on the per-date basis: identical once only the additive per-date keys are removed.
    single = actual["single_date_per_date_route"]
    assert _encoded(_without_added_keys(single)) == _encoded(_without_added_keys(expected["single_date_per_date_route"]))
    assert single["summary"] == expected["single_date_per_date_route"]["summary"]
    assert single["total_hours"] == expected["single_date_per_date_route"]["total_hours"]


# ── C-PD option (a) acceptance (owner decisions OD-C1 a, C2 i, C3 i, C4 i, C5 i; 2026-11-02) ─────────

SHARED_PER_DATE = {key: value for key, value in SETUP.items()
                   if key not in {"queue_ids", "separate_queue_closure_policy"}}
SHARED_PER_DATE["queue_structure"] = "shared_queue"


def _login(db_engine, client, email: str) -> dict:
    create_user(db_engine, email, "pw")
    login(client, email, "pw")
    return csrf_header(client)


def _run_current(client, headers, setup: dict, events, run: dict | None = None):
    return _route_result(client, headers, "C-PD", setup, events,
                         run or {"sim_hours": 1, "max_events": 1000, "seed": 7})


def _day_detail(client, analysis_id: int, date: str) -> dict:
    """C-PD-C day detail of the current compact run (GET, regenerated and checked against its fingerprints)."""
    response = client.get(f"/analyses/{analysis_id}/workflow/simulation/des/current/days/{date}")
    assert response.status_code == 200, response.text
    return response.json()


def _rows_for(result: dict, date: str) -> list[dict]:
    return [row for row in result["results"] if row["date"] == date]


def _shared_csv(events) -> bytes:
    return _frame([event[:3] + ("",) for event in events]).drop(columns=["queue_id"]).to_csv(index=False).encode()


def _today_engine_result(db_engine, analysis_id: int, dataset_id: int) -> dict:
    """What run_des_current computed before C-PD for this stored analysis and dataset (the single call)."""
    from backend.api.workflow import _current_segments_for
    from backend.db.models import AnalysisProject, Dataset
    from tests.helpers import make_sessionmaker

    with make_sessionmaker(db_engine)() as db:
        analysis = db.get(AnalysisProject, analysis_id)
        dataset = db.get(Dataset, dataset_id)
        return simulate_segments_with_trace(_current_segments_for(analysis, dataset), sim_hours=1.0, max_events=1000,
                                            seed=7, carryover=True, queue_setup=analysis.queue_setup_json)


def test_route_simulates_every_date_as_its_own_day(db_engine, client):
    """Acceptance 1 (strict): every dated (period, lane) pair is simulated and each date is one conserved day."""
    headers = _login(db_engine, client, "strict@example.com")
    analysis_id, run = _run_current(client, headers, SETUP, DATE_1 + DATE_2)
    assert run.status_code == 200, run.text
    evidence = run.json()["evidence"]
    result = evidence["result"]
    assert len(result["results"]) == 8
    assert all(row["simulation_supported"] is True for row in result["results"])
    assert _labels(result["results"]) == _labels(_records(DATE_1 + DATE_2))
    # C-PD-C (OD-C10 (i)): two or more dates are stored compactly; each date's detail is served on request.
    assert result["execution"] == "current_per_date_days_compact"
    assert result["seed_used"] == 7
    assert result["provenance"] == "CURRENT"
    assert result["zero_arrival_lane_periods"] == []
    assert [day["date"] for day in result["days"]] == ["2026-08-03", "2026-08-04"]
    for day in result["days"]:
        rows = _rows_for(result, day["date"])
        assert len(rows) == 4
        assert {str(row["time"]).split(" ", 1)[0] for row in rows} == {day["date"]}
        assert day["arrivals"] == sum(row["arrivals"] for row in rows)
        assert day["served"] == sum(row["served"] for row in rows)
        assert day["waiting_at_close"] == sum(row["waiting"] for row in rows)
        assert day["in_service_at_close"] == sum(row["in_service"] for row in rows)
        assert day["arrivals"] == day["served"] + day["waiting_at_close"] + day["in_service_at_close"]
        assert day["customer_conservation"] is True
        assert day["day_hours"] == 2.0
    assert result["total_hours"] == 4.0
    assert (result["segments"], result["trace"], result["event_count"]) == ([], [], 0)
    for day in result["days"]:
        detail = _day_detail(client, analysis_id, day["date"])
        assert {entry["date"] for entry in detail["segments"]} == {day["date"]}
        assert detail["trace"] and {event["date"] for event in detail["trace"]} == {day["date"]}
    assert result["summary"]["basis"] == "per_period"
    assert evidence["params"]["current_des_basis"] == "per_date_days_v2"
    assert client.get(f"/analyses/{analysis_id}/workflow").json()["des_current"]["id"] == evidence["id"]


def test_engine_refuses_two_records_for_one_segment_and_lane():
    """Acceptance 2: the engine guard; restoring the first-match lookup fails this test."""
    from backend.queueing_engine.simulation.simulation import _parallel_schedule

    records = _records(DATE_1 + DATE_2)
    assert _parallel_schedule(records, SETUP, 1.0) == DUPLICATE_REFUSAL
    result = simulate_segments_with_trace(records, sim_hours=1.0, max_events=1000, seed=1, queue_setup=SETUP)
    assert {(row["simulation_supported"], row["error"]) for row in result["results"]} == {(False, DUPLICATE_REFUSAL)}
    assert result["trace"] == []


def test_engine_refuses_one_schedule_from_several_dates():
    """F10: no duplicate pair, but date 1's s1 and date 2's s2 would make one 'day' from two dates."""
    from backend.queueing_engine.simulation.simulation import _parallel_schedule

    records = [row for row in _records(DATE_1 + DATE_2)
               if row["time"] in {"2026-08-03 s1 UTC", "2026-08-04 s2 UTC"}]
    assert _parallel_schedule(records, SETUP, 1.0) == (
        "Parallel M/G/1 DES received records from 2 dates (2026-08-03, 2026-08-04); it simulates one date at a time.")


def _shift(events, date: str):
    return [(date, arrive, minutes, lane) for _, arrive, minutes, lane in events]


def test_dates_with_equal_inputs_get_their_own_seed(db_engine, client):
    """Acceptance 3: date i runs with date_seed(seed, i), so equal dates are independent samples."""
    headers = _login(db_engine, client, "seeds@example.com")
    analysis_id, run = _run_current(client, headers, SETUP, DATE_1 + _shift(DATE_1, "2026-08-04"))
    assert run.status_code == 200, run.text
    details = [_day_detail(client, analysis_id, date) for date in ("2026-08-03", "2026-08-04")]
    first, second = (sorted((e["queue_id"], e["t"]) for e in detail["trace"] if e["type"] == "arrival")
                     for detail in details)
    assert first and second and first != second
    lambdas = {(row["date"], row["segment_id"], row["queue_id"]): row["lambda"]
               for detail in details for row in detail["results"]}
    assert len(lambdas) == 8
    assert all(lambdas[("2026-08-03", s, q)] == lambdas[("2026-08-04", s, q)] for _, s, q in lambdas)


def test_open_lane_without_a_record_on_a_date_is_zero_arrivals_and_listed(db_engine, client):
    """Acceptance 5 (OD-C2 (i)): listed openly; a representative day keeps today's refusal."""
    events = [event for event in DATE_1 if not (event[1] == "06:20" and event[3] == "b")] + DATE_2
    headers = _login(db_engine, client, "zero@example.com")
    analysis_id, run = _run_current(client, headers, SETUP, events)
    assert run.status_code == 200, run.text
    result = run.json()["evidence"]["result"]
    assert all(row["simulation_supported"] is True for row in result["results"])
    zero = next(row for row in result["results"] if row["time"] == "2026-08-03 s2 UTC" and row["queue_id"] == "b")
    assert (zero["arrivals"], zero["served"], zero["date"]) == (0, 0, "2026-08-03")
    detail = _day_detail(client, analysis_id, "2026-08-03")
    full = next(row for row in detail["results"] if row["time"] == "2026-08-03 s2 UTC" and row["queue_id"] == "b")
    assert (full["arrivals"], full["lambda"], full["mu"]) == (0, 0.0, None)
    assert detail["zero_arrival_lane_periods"] == [
        {"date": "2026-08-03", "time": "2026-08-03 s2 UTC", "segment_id": "s2", "queue_id": "b"}]
    assert result["zero_arrival_lane_periods"] == [
        {"date": "2026-08-03", "time": "2026-08-03 s2 UTC", "segment_id": "s2", "queue_id": "b"}]
    assert _labels(result["results"]) == _labels(_records(events)) | {("2026-08-03 s2 UTC", "b")}
    assert all(day["customer_conservation"] is True for day in result["days"])
    # The same gap on a representative day: refused exactly as before C-PD (no zero-arrival rule there).
    representative = {**SETUP, "event_period_basis": "representative_day"}
    one_day = [event for event in DATE_1 if not (event[1] == "06:20" and event[3] == "b")]
    engine = simulate_segments_with_trace(_records_for(one_day, representative), sim_hours=1.0, max_events=1000,
                                          seed=7, queue_setup=representative)
    assert {row["error"] for row in engine["results"]} == {"Missing empirical segment/queue record for s2/b."}
    _, route = _route_result(client, headers, "rep-gap", representative, one_day)
    assert route.status_code == 200, route.text
    assert {(row["simulation_supported"], row["error"]) for row in route.json()["evidence"]["result"]["results"]} == {
        (False, "Missing empirical segment/queue record for s2/b.")}


def test_date_without_a_whole_segment_refuses_the_run_and_stores_nothing(db_engine, client):
    """Acceptance 6 (OD-C5 (i)): HTTP 422 naming the date and segment; no job is saved."""
    from sqlalchemy import func, select

    from backend.db.models import Job
    from tests.helpers import make_sessionmaker

    events = DATE_1 + [event for event in DATE_2 if not event[1].startswith("06:")]
    headers = _login(db_engine, client, "gap@example.com")
    analysis_id, run = _run_current(client, headers, SETUP, events)
    assert run.status_code == 422, run.text
    assert run.json()["detail"] == (
        "Date 2026-08-04 has no records for operating segment(s) s2; NovaQ cannot tell whether the store was "
        "open, so the day cannot be simulated.")
    with make_sessionmaker(db_engine)() as db:
        assert db.scalar(select(func.count()).select_from(Job).where(Job.kind == "workflow_des_current")) == 0
    assert client.get(f"/analyses/{analysis_id}/workflow").json()["des_current"] is None


def test_each_date_has_its_own_event_cap(db_engine, client):
    """Acceptance 7, now OD-C11 (i) (replaces OD-C3 (i) for compact runs): every date's detail has its own
    max_events cap; the stored compact result holds no events; only the trace is capped, not the metrics."""
    headers = _login(db_engine, client, "cap@example.com")
    analysis_id, run = _run_current(client, headers, SETUP, DATE_1 + DATE_2,
                                    {"sim_hours": 1, "max_events": 5, "seed": 7})
    assert run.status_code == 200, run.text
    result = run.json()["evidence"]["result"]
    assert (result["event_count"], result["truncated"], result["trace"]) == (0, False, [])
    for day in result["days"]:
        assert (day["event_count"], day["truncated"]) == (5, True)
        detail = _day_detail(client, analysis_id, day["date"])
        assert detail["event_count"] == len(detail["trace"]) == 5 and detail["truncated"] is True
        assert {event["date"] for event in detail["trace"]} == {day["date"]}
        assert day["arrivals"] > 5


def test_shared_lines_and_aggregate_separate_current_runs_are_unchanged(db_engine, client):
    """Acceptance 8: shared lines keep the base's single run; separate aggregate data keeps the base's refusal
    (on the integrated main base that is the bounded guard's 422, not the 200 of 3ee8fe2c)."""
    headers = _login(db_engine, client, "unchanged@example.com")
    response = client.post("/analyses", headers=headers, json={"name": "shared", "queue_setup": SHARED_PER_DATE})
    analysis_id = response.json()["analysis"]["id"]
    uploaded = client.post(f"/analyses/{analysis_id}/datasets", headers=headers,
                           files={"file": ("e.csv", _shared_csv(DATE_1 + DATE_2), "text/csv")})
    assert uploaded.status_code == 201, uploaded.text
    run = client.post(f"/analyses/{analysis_id}/workflow/simulation/des/current", headers=headers,
                      json={**SNAP_RUN, "current_des_basis": "forged"})
    assert run.status_code == 200, run.text
    evidence = run.json()["evidence"]
    stored = {key: value for key, value in evidence["result"].items() if key not in {"provenance", "summary"}}
    assert stored["results"] and all(row.get("queue_structure") != "separate" for row in stored["results"])
    assert _encoded(stored) == _encoded(_today_engine_result(db_engine, analysis_id, evidence["params"]["dataset_id"]))
    assert "current_des_basis" not in evidence["params"]

    aggregate = (b"time,lambda,mu,c,variance,queue_id\n"
                 b"s1,2,10,1,0.001,a\ns1,2,10,1,0.001,b\ns2,2,10,1,0.001,a\ns2,2,10,1,0.001,b\n")
    response = client.post("/analyses", headers=headers, json={"name": "aggregate", "queue_setup": SETUP})
    analysis_id = response.json()["analysis"]["id"]
    uploaded = client.post(f"/analyses/{analysis_id}/datasets", headers=headers,
                           files={"file": ("a.csv", aggregate, "text/csv")})
    assert uploaded.status_code == 201, uploaded.text
    run = client.post(f"/analyses/{analysis_id}/workflow/simulation/des/current", headers=headers, json=SNAP_RUN)
    # Integrated base (origin/main 4dd99465): aggregate separate data is outside the C-PD gate, so main's bounded
    # guard (d8f89da6) refuses it unchanged, as on main, and nothing is stored (OD-C8 (i), C-PD-C §6.1).
    assert run.status_code == 422, run.text
    assert run.json() == {"detail": "Current dataset records are invalid."}
    assert client.get(f"/analyses/{analysis_id}/workflow").json()["des_current"] is None


def test_separate_current_des_jobs_without_the_basis_marker_are_not_current(db_engine, client):
    """Acceptance 9 (OD-C4 (i)): a pre-fix separate Current DES job stops being Current; shared jobs do not."""
    from backend.db.models import Job
    from tests.helpers import make_sessionmaker

    headers = _login(db_engine, client, "marker@example.com")
    analysis_id, run = _route_result(client, headers, "marker", _snap_setup("representative_day"), SNAP_EVENTS,
                                     {**SNAP_RUN, "current_des_basis": "forged"})
    assert run.status_code == 200, run.text
    job_id = run.json()["evidence"]["id"]
    assert run.json()["evidence"]["params"]["current_des_basis"] == "per_date_days_v2"  # the payload value is ignored
    assert client.get(f"/analyses/{analysis_id}/workflow").json()["des_current"]["id"] == job_id
    with make_sessionmaker(db_engine)() as db:  # the same job as stored before C-PD: no marker
        job = db.get(Job, job_id)
        job.params_json = {key: value for key, value in job.params_json.items() if key != "current_des_basis"}
        db.commit()
    assert client.get(f"/analyses/{analysis_id}/workflow").json()["des_current"] is None
    rerun = client.post(f"/analyses/{analysis_id}/workflow/simulation/des/current", headers=headers, json=SNAP_RUN)
    assert rerun.status_code == 200, rerun.text
    assert client.get(f"/analyses/{analysis_id}/workflow").json()["des_current"]["id"] == rerun.json()["evidence"]["id"]

    response = client.post("/analyses", headers=headers, json={"name": "shared", "queue_setup": SHARED_PER_DATE})
    shared_id = response.json()["analysis"]["id"]
    assert client.post(f"/analyses/{shared_id}/datasets", headers=headers,
                       files={"file": ("e.csv", _shared_csv(DATE_1), "text/csv")}).status_code == 201
    shared = client.post(f"/analyses/{shared_id}/workflow/simulation/des/current", headers=headers, json=SNAP_RUN)
    assert shared.status_code == 200, shared.text
    assert "current_des_basis" not in shared.json()["evidence"]["params"]
    assert client.get(f"/analyses/{shared_id}/workflow").json()["des_current"]["id"] == shared.json()["evidence"]["id"]


def test_scenario_des_with_duplicate_separate_inputs_is_refused(db_engine, client):
    """Acceptance 10 / F2 (behaviour change): a plan run with two inputs for one (segment, lane) is refused,
    where before C-PD the engine silently simulated the first one."""
    from backend.db.models import AnalysisProject, Dataset, Scenario
    from tests.helpers import make_sessionmaker

    user = create_user(db_engine, "dup-plan@example.com", "pw")
    setup = {**SETUP, "queue_ids": ["a"], "fixed_server_count": 1, "segments": SETUP["segments"][:1]}
    rows = [{"time": label, "segment_id": "s1", "queue_id": "a", "queue_structure": "separate_queues",
             "model_id": "parallel_mg1", "server_id": "server:a", "lambda": 4.0, "mu": 4.0, "c": 1,
             "variance": 0.0025, "service_time_source": "empirical", "service_samples_hours": [0.05, 0.1]}
            for label in ("2026-08-03 s1 UTC", "2026-08-04 s1 UTC")]
    inputs = [{key: row[key] for key in ("time", "segment_id", "queue_id", "queue_structure", "model_id",
                                         "lambda", "mu", "c", "variance")} for row in rows]
    plan_rows = [{"time": row["time"], "lambda_": 4.0, "mu": 4.0, "c_current": 1, "c_optimal": 1,
                  "rho_current": 0.5, "rho_optimal": 0.5, "Wq_current": 0.1, "Wq_optimal": 0.1, "Lq_current": 0.4,
                  "Lq_optimal": 0.4, "cost_current": 1, "cost_optimal": 1, "current_stable": True,
                  "optimized_stable": True} for row in rows]
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(user_id=user.id, name="dup", queue_setup_json=setup, setup_status="ready")
        db.add(analysis)
        db.flush()
        dataset = Dataset(user_id=user.id, analysis_id=analysis.id, name="dup", source_filename="e.csv",
                          source_format="csv", row_count=2, normalized_json=rows,
                          validation_report_json={"ok": True, "message": "Input data is valid."})
        db.add(dataset)
        db.flush()
        scenario = Scenario(
            user_id=user.id, analysis_id=analysis.id, dataset_id=dataset.id, name="dup plan",
            settings_json={"calculation": {
                "schema_version": 1, "engine_version": "novaq-2026-09-system-v2", "input_segments": inputs,
                "options": {}, "what_if_multiplier": 1, "calculated_at": "2026-11-02T00:00:00+00:00"}},
            results_json={"results": plan_rows},
        )
        db.add(scenario)
        db.commit()
        analysis_id, scenario_id = analysis.id, scenario.id
    login(client, "dup-plan@example.com", "pw")
    headers = csrf_header(client)
    selected = client.post(f"/analyses/{analysis_id}/workflow/selection", headers=headers,
                           json={"scenario_id": scenario_id})
    assert selected.status_code == 200, selected.text
    run = client.post(f"/analyses/{analysis_id}/workflow/simulation/des", headers=headers,
                      json={"sim_hours": 1, "max_events": 100, "seed": 7})
    assert run.status_code == 200, run.text
    rows_out = run.json()["evidence"]["result"]["results"]
    assert len(rows_out) == 2
    assert {(row["simulation_supported"], row["error"]) for row in rows_out} == {(False, DUPLICATE_REFUSAL)}


# ── A7b (OD-C7 (iii), owner 2026-11-02) and A7c (K-CPD-2) ───────────────────────────────────────────────

OLD_TOO_LARGE = "Workflow evidence is too large. Reduce the playback event cap."


def _des_current_jobs(db_engine) -> int:
    from sqlalchemy import func, select

    from backend.db.models import Job
    from tests.helpers import make_sessionmaker

    with make_sessionmaker(db_engine)() as db:
        return int(db.scalar(select(func.count()).select_from(Job).where(Job.kind == "workflow_des_current")) or 0)


def _analysis_with(client, headers, setup: dict, events) -> int:
    response = client.post("/analyses", headers=headers, json={"name": "size", "queue_setup": setup})
    assert response.status_code in (200, 201), response.text
    analysis_id = response.json()["analysis"]["id"]
    _upload(client, headers, analysis_id, events)
    return analysis_id


def test_per_date_result_over_the_cap_is_refused_with_its_own_reason(db_engine, client, app, monkeypatch):
    """(1) over a small cap: 413 with the per-date detail (real numbers), nothing stored; (2) same file, large cap: 200."""
    from backend.api.workflow import CURRENT_PER_DATE_TOO_LARGE_DETAIL, _encoded_size

    headers = _login(db_engine, client, "too-large@example.com")
    analysis_id = _analysis_with(client, headers, SETUP, DATE_1 + DATE_2)
    url = f"/analyses/{analysis_id}/workflow/simulation/des/current"
    monkeypatch.setattr(app.state.settings, "result_jsonb_max_bytes", 2048)
    refused = client.post(url, headers=headers, json=SNAP_RUN)
    assert refused.status_code == 413, refused.text
    assert _des_current_jobs(db_engine) == 0
    assert client.get(f"/analyses/{analysis_id}/workflow").json()["des_current"] is None
    monkeypatch.setattr(app.state.settings, "result_jsonb_max_bytes", 524288)
    stored = client.post(url, headers=headers, json=SNAP_RUN)
    assert stored.status_code == 200, stored.text
    assert _des_current_jobs(db_engine) == 1
    result = stored.json()["evidence"]["result"]
    assert result["execution"] == "current_per_date_days_compact"
    # Same seed, same result: the refused size is the stored result's size, measured by _save_job's rule.
    size = _encoded_size(result)
    assert size > 2048
    assert refused.json()["detail"] == CURRENT_PER_DATE_TOO_LARGE_DETAIL.format(
        dates=2, size_bytes=size, limit_bytes=2048)
    # Final EN text of W1 (spec §9.1, owner delegation 2026-11-03); sizes are no longer named in it.
    assert refused.json()["detail"] == (
        "This Current run is too large to save: it covers 2 dates. Upload a file with fewer dates.")


def test_other_oversized_current_results_keep_the_existing_413(db_engine, client, app, monkeypatch):
    """(3) a representative-day (single-call) separate result over the cap keeps _save_job's message."""
    headers = _login(db_engine, client, "old-413@example.com")
    analysis_id = _analysis_with(client, headers, _snap_setup("representative_day"), SNAP_EVENTS)
    monkeypatch.setattr(app.state.settings, "result_jsonb_max_bytes", 1024)
    run = client.post(f"/analyses/{analysis_id}/workflow/simulation/des/current", headers=headers, json=SNAP_RUN)
    assert run.status_code == 413, run.text
    assert run.json()["detail"] == OLD_TOO_LARGE
    assert _des_current_jobs(db_engine) == 0


def test_open_lane_at_lambda_zero_without_samples_is_refused_outside_the_per_date_runner():
    """K-CPD-2: only the per-date runner's own zero-arrival records may be open with no samples.

    A representative-day (or any other caller's) record for an open lane with lambda 0 or no lambda and no
    samples keeps HEAD's exact refusal, and a marker key with a JSON value is not accepted.
    """
    setup = _snap_setup("representative_day")
    base = _records_for(SNAP_EVENTS, setup)
    for change in ({"lambda": 0.0}, {"lambda": None}, {"lambda": 0.0, "_cpd_zero_arrival": True}):
        records = [dict(row) for row in base]
        target = next(row for row in records if row["segment_id"] == "s1" and row["queue_id"] == "b")
        target.update({"service_samples_hours": [], **change})
        if change.get("lambda") is None:
            target.pop("lambda")
        result = simulate_segments_with_trace(records, sim_hours=1.0, max_events=1000, seed=7, queue_setup=setup)
        assert {(row["simulation_supported"], row["error"]) for row in result["results"]} == {
            (False, "Missing empirical service samples for s1/b.")}, change
