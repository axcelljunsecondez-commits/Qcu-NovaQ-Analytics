"""C-PD-C: compact stored result for per-date separate-lines Current DES (spec 2026-11-02, plan steps 1-4).

All data here is SYNTHETIC. Owner decisions 2026-11-02: OD-C8 (i), OD-C9 C-rows, OD-C10 (i), OD-C11 (i),
OD-C12 (i), OD-C13 (i), OD-C14 (i), OD-C15 (i); OD-C6 wording open (placeholder details only).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from backend.api.analysis_schemas import QueueSetup
from backend.data.analysis_ingestion import normalize_analysis_input
from backend.queueing_engine.simulation.simulation import simulate_segments_with_trace
from tests.helpers import create_user, csrf_header, login

# ── Step 1: scope snapshot, generated on the integrated step-0 state (claude/cpd-compact, base 4dd99465) ──
#
# Written by running
#   NOVAQ_WRITE_CPD_C_SNAPSHOT=1 python -m pytest tests/test_current_per_date_compact.py -k scope_snapshot
# before any C-PD-C engine or workflow edit. Without the variable the test only compares, byte for byte.

SNAPSHOT = Path(__file__).parent / "fixtures" / "current_per_date_compact_snapshot_4dd99465.json"
LANES = ["a", "b"]
SEGMENTS = [
    {"id": "s1", "start_time": "05:00:00", "end_time": "06:00:00", "active_queue_ids": ["a", "b"]},
    {"id": "s2", "start_time": "06:00:00", "end_time": "07:00:00", "active_queue_ids": ["a"]},
]
SEPARATE = {
    "queue_structure": "separate_queues", "fixed_server_count": 2, "staffing_varies_by_period": True,
    "capacity_mode": "unlimited", "total_system_capacity": None, "abandonment_mode": "not_modeled",
    "patience_rate_per_hour": None, "event_period_basis": "per_date",
    "separate_queue_closure_policy": "drain_existing", "segments": SEGMENTS, "queue_ids": LANES,
}
SHARED = {
    "queue_structure": "shared_queue", "fixed_server_count": 2, "staffing_varies_by_period": False,
    "capacity_mode": "unlimited", "total_system_capacity": None, "abandonment_mode": "not_modeled",
    "patience_rate_per_hour": None, "event_period_basis": "per_date",
    "segments": [{**segment, "active_queue_ids": None} for segment in SEGMENTS],
}
# (date, HH:MM, service minutes, lane)
ONE_DATE = [
    ("2026-08-03", "05:05", 6, "a"), ("2026-08-03", "05:15", 5, "a"), ("2026-08-03", "05:25", 7, "a"),
    ("2026-08-03", "05:45", 6, "a"), ("2026-08-03", "05:10", 4, "b"), ("2026-08-03", "05:30", 6, "b"),
    ("2026-08-03", "05:50", 5, "b"), ("2026-08-03", "06:05", 6, "a"), ("2026-08-03", "06:20", 5, "a"),
    ("2026-08-03", "06:40", 4, "a"),
]
RUN = {"sim_hours": 1, "max_events": 1000, "seed": 7}
AGGREGATE = (b"time,lambda,mu,c,variance,queue_id\n"
             b"s1,2,10,1,0.001,a\ns1,2,10,1,0.001,b\ns2,2,10,1,0.001,a\ns2,2,10,1,0.001,b\n")


def _frame(events, lanes: bool = True) -> pd.DataFrame:
    rows = []
    for date, arrive, minutes, lane in events:
        start = pd.Timestamp(f"{date}T{arrive}:00Z")
        row = {"arrival_time": start.isoformat(), "service_start": start.isoformat(),
               "service_end": (start + pd.Timedelta(minutes=minutes)).isoformat()}
        if lanes:
            row["queue_id"] = lane
        rows.append(row)
    return pd.DataFrame(rows)


def _records(events, setup: dict) -> list[dict]:
    records, _ = normalize_analysis_input(_frame(events), QueueSetup.model_validate(setup))
    return records


def _encoded(value) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=False)


def _login(db_engine, client, email: str) -> dict:
    create_user(db_engine, email, "pw")
    login(client, email, "pw")
    return csrf_header(client)


def _analysis(client, headers, setup: dict, body: bytes) -> int:
    response = client.post("/analyses", headers=headers, json={"name": "C-PD-C", "queue_setup": setup})
    assert response.status_code in (200, 201), response.text
    analysis_id = response.json()["analysis"]["id"]
    uploaded = client.post(f"/analyses/{analysis_id}/datasets", headers=headers,
                           files={"file": ("e.csv", body, "text/csv")})
    assert uploaded.status_code == 201, uploaded.text
    return analysis_id


def _run(client, headers, analysis_id: int, run: dict | None = None):
    return client.post(f"/analyses/{analysis_id}/workflow/simulation/des/current", headers=headers,
                       json=RUN if run is None else run)


def _csv(events, lanes: bool = True) -> bytes:
    return _frame(events, lanes).to_csv(index=False).encode("utf-8")


def _scope_results(db_engine, client) -> dict:
    headers = _login(db_engine, client, "scope@example.com")
    representative = {**SEPARATE, "event_period_basis": "representative_day"}
    out: dict = {}
    one = _run(client, headers, _analysis(client, headers, SEPARATE, _csv(ONE_DATE)))
    out["one_date_per_date_route"] = [one.status_code, one.json()["evidence"]["result"]]
    rep = _run(client, headers, _analysis(client, headers, representative, _csv(ONE_DATE)))
    out["representative_day_route"] = [rep.status_code, rep.json()["evidence"]["result"]]
    out["representative_day_engine"] = simulate_segments_with_trace(
        _records(ONE_DATE, representative), sim_hours=1.0, max_events=1000, seed=7, queue_setup=representative)
    shared = _run(client, headers, _analysis(client, headers, SHARED, _csv(ONE_DATE, lanes=False)))
    out["shared_per_date_route"] = [shared.status_code, shared.json()["evidence"]["result"]]
    aggregate = _run(client, headers, _analysis(client, headers, SEPARATE, AGGREGATE))
    out["aggregate_separate_route"] = [aggregate.status_code, aggregate.json()]
    legacy_records = _records(ONE_DATE, representative)
    legacy = client.post("/simulation/des", headers=headers, json={
        "segments": legacy_records, "sim_hours": 1, "seed": 7, "queue_setup": representative})
    out["legacy_des"] = [legacy.status_code, legacy.json()]
    trace = client.post("/simulation/des/trace", headers=headers, json={
        "segments": legacy_records, "trace_hours": 1, "max_events": 1000, "seed": 7, "queue_setup": representative})
    out["legacy_des_trace"] = [trace.status_code, trace.json()]
    two_dates = legacy_records + [{**row, "time": f"2026-08-04 {row['segment_id']} UTC"} for row in legacy_records]
    duplicate = client.post("/simulation/des/trace", headers=headers, json={
        "segments": two_dates, "trace_hours": 1, "max_events": 1000, "seed": 7, "queue_setup": representative})
    out["legacy_des_trace_duplicates"] = [duplicate.status_code, duplicate.json()]
    return out


def test_scope_snapshot_is_byte_identical(db_engine, client):
    """Spec §10 scope: one-date per-date, Representative day, shared lines, aggregate separate and the legacy
    endpoints give byte-identical results before and after C-PD-C (the marker lives in params, not here)."""
    actual = _scope_results(db_engine, client)
    if os.environ.get("NOVAQ_WRITE_CPD_C_SNAPSHOT") == "1":
        SNAPSHOT.write_text(_encoded({"generated_at": "claude/cpd-compact step 0 on 4dd99465", "data": "SYNTHETIC",
                                      **actual}) + "\n", encoding="utf-8")
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert actual["one_date_per_date_route"][0] == 200
    assert actual["aggregate_separate_route"][0] == 422
    for key, value in actual.items():
        assert _encoded(value) == _encoded(expected[key]), key


# ── Steps 2-4: compact run, day detail, fingerprints, seeds, evidence (spec §10) ─────────────────────────

GRID_LANES = ["l1", "l2", "l3"]


def _grid_setup(lanes=GRID_LANES, hours=range(8, 11)) -> dict:
    segments = [{"id": f"h{hour:02d}", "start_time": f"{hour:02d}:00:00", "end_time": f"{hour + 1:02d}:00:00",
                 "active_queue_ids": None} for hour in hours]
    return {**SEPARATE, "staffing_varies_by_period": False, "fixed_server_count": len(lanes),
            "segments": segments, "queue_ids": list(lanes)}


def _grid_events(dates: int, lanes=GRID_LANES, hours=range(8, 11)) -> list[tuple]:
    """SYNTHETIC: 2-4 customers per lane-hour, service 3-7 minutes, varying by date, hour and lane."""
    events = []
    for d in range(dates):
        date = (pd.Timestamp("2000-01-03") + pd.Timedelta(days=d)).date().isoformat()
        for hour in hours:
            for li, lane in enumerate(lanes):
                for k in range(2 + (d + hour + li) % 3):
                    events.append((date, f"{hour:02d}:{5 + 17 * k:02d}", 3 + (d + k + li) % 5, lane))
    return events


def _grid_days(dates: int, setup: dict | None = None):
    from backend.api.workflow import _current_per_date_groups

    setup = setup or _grid_setup()
    records = [{**row, "time": str(row["time"])} for row in _records(_grid_events(dates), setup)]
    return _current_per_date_groups(records, setup), setup


def _job(db_engine, job_id: int):
    from backend.db.models import Job
    from tests.helpers import make_sessionmaker

    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, job_id)
        return dict(job.params_json), dict(job.result_json)


def _update_job(db_engine, job_id: int, *, params=None, result=None) -> None:
    from backend.db.models import Job
    from tests.helpers import make_sessionmaker

    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, job_id)
        if params is not None:
            job.params_json = params
        if result is not None:
            job.result_json = result
        db.commit()


def _jobs(db_engine) -> int:
    from sqlalchemy import func, select

    from backend.db.models import Job
    from tests.helpers import make_sessionmaker

    with make_sessionmaker(db_engine)() as db:
        return int(db.scalar(select(func.count()).select_from(Job)) or 0)


def _day(client, analysis_id: int, date: str):
    return client.get(f"/analyses/{analysis_id}/workflow/simulation/des/current/days/{date}")


def _compact_run(db_engine, client, email: str, dates: int = 3, run: dict | None = None):
    headers = _login(db_engine, client, email)
    analysis_id = _analysis(client, headers, _grid_setup(), _csv(_grid_events(dates)))
    response = _run(client, headers, analysis_id, run)
    assert response.status_code == 200, response.text
    return headers, analysis_id, response.json()["evidence"]


def test_compact_run_keeps_every_record_once_with_full_run_totals(db_engine, client):
    from backend.api.workflow import _run_summary
    from backend.queueing_engine.services.separate_optimization import date_seed
    from backend.queueing_engine.simulation.simulation import COMPACT_ROW_FIELDS, simulate_parallel_days_with_trace

    _, _, evidence = _compact_run(db_engine, client, "compact@example.com")
    result = evidence["result"]
    assert result["execution"] == "current_per_date_days_compact"
    assert (result["trace"], result["segments"], result["event_count"], result["truncated"]) == ([], [], 0, False)
    assert not {"admitted", "in_system_at_close", "periods"} & set(result)
    keys = [(row["time"], row["queue_id"]) for row in result["results"]]
    records = _records(_grid_events(3), _grid_setup())
    assert sorted(keys) == sorted((row["time"], row["queue_id"]) for row in records) and len(set(keys)) == len(keys)
    assert all(list(row) == list(COMPACT_ROW_FIELDS) for row in result["results"])
    # The full per-date run (same seeds): every kept value is identical and the summary is equal.
    days, setup = _grid_days(3)
    full = simulate_parallel_days_with_trace(days, setup, 1.0, [date_seed(7, i) for i in range(3)], 10**9)
    assert result["results"] == [{field: row[field] for field in COMPACT_ROW_FIELDS} for row in full["results"]]
    assert result["summary"] == _run_summary(full)
    assert result["total_hours"] == full["total_hours"] == 9.0
    for day, full_day in zip(result["days"], full["days"]):
        rows = [row for row in result["results"] if row["date"] == day["date"]]
        assert {k: day[k] for k in full_day} == full_day
        assert day["arrivals"] == sum(r["arrivals"] for r in rows) == day["served"] + day["waiting_at_close"] + \
            day["in_service_at_close"]
        assert len(day["rows_digest"]) == len(day["trace_digest"]) == 64


def test_day_detail_equals_its_slice_of_an_uncapped_full_run_and_never_stores(db_engine, client):
    """Determinism (in process): each date's detail equals that date's slice of one uncapped full run;
    the trace is the slice's first max_events events (OD-C11 (i))."""
    from backend.queueing_engine.services.separate_optimization import date_seed
    from backend.queueing_engine.simulation.simulation import simulate_parallel_days_with_trace

    _, analysis_id, evidence = _compact_run(db_engine, client, "slice@example.com",
                                            run={"sim_hours": 1, "max_events": 40, "seed": 11})
    days, setup = _grid_days(3)
    full = simulate_parallel_days_with_trace(days, setup, 1.0, [date_seed(11, i) for i in range(3)], 10**9)
    jobs = _jobs(db_engine)
    for index, (date, _) in enumerate(days):
        response = _day(client, analysis_id, date)
        assert response.status_code == 200, response.text
        detail = response.json()
        assert detail["execution"] == "current_per_date_day_detail"
        assert (detail["date"], detail["job_id"]) == (date, evidence["id"])
        assert detail["days"] == [evidence["result"]["days"][index]]
        assert detail["results"] == [row for row in full["results"] if row["date"] == date]
        assert detail["segments"] == [entry for entry in full["segments"] if entry["date"] == date]
        whole = [event for event in full["trace"] if event["date"] == date]
        assert len(whole) > 40 and detail["trace"] == whole[:40]
        assert detail["truncated"] is True and detail["event_count"] == 40
    assert _jobs(db_engine) == jobs  # day detail never writes a job
    assert _day(client, analysis_id, "1999-12-31").status_code == 404


SUBPROCESS = """
import json, sys
from tests.test_current_per_date_compact import _grid_days
from backend.queueing_engine.services.separate_optimization import date_seed
from backend.queueing_engine.simulation.simulation import (canonical_digest, simulate_parallel_days_compact,
                                                           simulate_parallel_days_with_trace)
days, setup = _grid_days(4)
seeds = [date_seed(5, i) for i in range(4)]
compact = simulate_parallel_days_compact(days, setup, 1.0, seeds, 30)
full = simulate_parallel_days_with_trace(days, setup, 1.0, seeds, 10**9)
slices = [canonical_digest([r for r in full["results"] if r["date"] == d]) for d, _ in days]
details = [simulate_parallel_days_with_trace([day], setup, 1.0, [seeds[i]], 30) for i, day in enumerate(days)]
same = all(canonical_digest(d["results"]) == s for d, s in zip(details, slices))
prefix = all(d["trace"] == [e for e in full["trace"] if e["date"] == day[0]][:30] for d, day in zip(details, days))
print(json.dumps({"compact": canonical_digest(compact), "same": same, "prefix": prefix}))
"""


def test_regeneration_is_identical_across_hash_seeds():
    """Determinism across processes: PYTHONHASHSEED 0 and 12345 give the same compact result, and each date's
    detail equals its slice of an uncapped full run in both."""
    import subprocess
    import sys

    root = Path(__file__).resolve().parent.parent
    outputs = []
    for hash_seed in ("0", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONPATH": str(root)}
        done = subprocess.run([sys.executable, "-c", SUBPROCESS], cwd=root, env=env, capture_output=True,
                              text=True, check=True)
        outputs.append(json.loads(done.stdout.strip().splitlines()[-1]))
    assert outputs[0] == outputs[1]
    assert outputs[0]["same"] is True and outputs[0]["prefix"] is True


def test_fingerprint_mismatch_refuses_the_day_with_409(db_engine, client):
    """OD-C13 (i): a changed digest, seed_used or dataset value gives 409 and serves nothing."""
    from backend.api.workflow import CURRENT_DAY_DETAIL_MISMATCH_DETAIL
    from backend.db.models import Dataset
    from tests.helpers import make_sessionmaker

    _, analysis_id, evidence = _compact_run(db_engine, client, "fingerprint@example.com")
    job_id = evidence["id"]
    date = evidence["result"]["days"][1]["date"]
    assert _day(client, analysis_id, date).status_code == 200
    params, original = _job(db_engine, job_id)
    for change in ("rows_digest", "trace_digest", "seed_used"):
        result = json.loads(json.dumps(original))
        if change == "seed_used":
            result["seed_used"] = result["seed_used"] + 1
        else:
            result["days"][1][change] = "0" * 64
        _update_job(db_engine, job_id, result=result)
        refused = _day(client, analysis_id, date)
        assert refused.status_code == 409, change
        assert refused.json() == {"detail": CURRENT_DAY_DETAIL_MISMATCH_DETAIL}
    _update_job(db_engine, job_id, result=original)
    assert _day(client, analysis_id, date).status_code == 200
    with make_sessionmaker(db_engine)() as db:  # a stored observation changed in place, same dataset row
        dataset = db.get(Dataset, params["dataset_id"])
        rows = json.loads(json.dumps(dataset.normalized_json))
        target = next(row for row in rows if str(row["time"]).startswith(date))
        target["service_samples_hours"] = [value * 2 for value in target["service_samples_hours"]]
        dataset.normalized_json = rows
        db.commit()
    assert _day(client, analysis_id, date).json() == {"detail": CURRENT_DAY_DETAIL_MISMATCH_DETAIL}


def test_a_date_out_of_its_stored_position_is_refused(db_engine, client):
    """Spec §6.7: the date's index must equal its stored position (here the stored days are swapped)."""
    from backend.api.workflow import CURRENT_DAY_DETAIL_MISMATCH_DETAIL

    _, analysis_id, evidence = _compact_run(db_engine, client, "position@example.com")
    _, original = _job(db_engine, evidence["id"])
    swapped = json.loads(json.dumps(original))
    swapped["days"][0], swapped["days"][1] = swapped["days"][1], swapped["days"][0]
    _update_job(db_engine, evidence["id"], result=swapped)
    for day in swapped["days"][:2]:
        assert _day(client, analysis_id, day["date"]).json() == {"detail": CURRENT_DAY_DETAIL_MISMATCH_DETAIL}


def test_null_seed_is_drawn_by_the_server_and_recorded(db_engine, client):
    """OD-C12 (i): seed_used is an integer, params.seed stays null; the same seed_used gives the same digests."""
    headers, analysis_id, evidence = _compact_run(db_engine, client, "seedless@example.com",
                                                  run={"sim_hours": 1, "max_events": 300, "seed": None})
    seed_used = evidence["result"]["seed_used"]
    assert isinstance(seed_used, int) and not isinstance(seed_used, bool) and 0 <= seed_used < 2**31
    assert evidence["params"]["seed"] is None
    assert all(_day(client, analysis_id, day["date"]).status_code == 200 for day in evidence["result"]["days"])
    again = _run(client, headers, analysis_id, {"sim_hours": 1, "max_events": 300, "seed": seed_used})
    digests = [(d["rows_digest"], d["trace_digest"]) for d in again.json()["evidence"]["result"]["days"]]
    assert digests == [(d["rows_digest"], d["trace_digest"]) for d in evidence["result"]["days"]]
    assert again.json()["evidence"]["params"]["seed"] == seed_used


def test_one_date_per_date_run_keeps_the_full_shape(db_engine, client):
    """OD-C10 (i): one date is never compacted and has no seed_used or day detail."""
    headers = _login(db_engine, client, "one-date@example.com")
    analysis_id = _analysis(client, headers, _grid_setup(), _csv(_grid_events(1)))
    result = _run(client, headers, analysis_id).json()["evidence"]["result"]
    assert result["execution"] == "current_per_date_days" and "seed_used" not in result and result["trace"]
    assert _day(client, analysis_id, result["days"][0]["date"]).status_code == 404


def test_v1_and_unmarked_jobs_are_not_current_and_have_no_day_detail(db_engine, client):
    """OD-C15 (i): per_date_days_v2 is current, v1 historical; no marker is not Current either."""
    from backend.api.workflow import CURRENT_DAY_DETAIL_NOT_FOUND_DETAIL

    _, analysis_id, evidence = _compact_run(db_engine, client, "marker-v2@example.com")
    job_id, date = evidence["id"], evidence["result"]["days"][0]["date"]
    assert evidence["params"]["current_des_basis"] == "per_date_days_v2"
    assert client.get(f"/analyses/{analysis_id}/workflow").json()["des_current"]["id"] == job_id
    params, _ = _job(db_engine, job_id)
    for marker in ("per_date_days_v1", None):
        changed = {k: v for k, v in params.items() if k != "current_des_basis"}
        if marker is not None:
            changed["current_des_basis"] = marker
        _update_job(db_engine, job_id, params=changed)
        assert client.get(f"/analyses/{analysis_id}/workflow").json()["des_current"] is None, marker
        assert _day(client, analysis_id, date).json() == {"detail": CURRENT_DAY_DETAIL_NOT_FOUND_DETAIL}
    _update_job(db_engine, job_id, params=params)
    assert _day(client, analysis_id, date).status_code == 200


def test_day_detail_is_scoped_to_the_owner_analysis_and_generation(db_engine, client, monkeypatch):
    from backend.api import workflow as workflow_api

    headers, analysis_id, evidence = _compact_run(db_engine, client, "owner@example.com")
    date = evidence["result"]["days"][0]["date"]
    other = _analysis(client, headers, _grid_setup(), _csv(_grid_events(3)))  # same owner, no run yet
    assert _day(client, other, date).status_code == 404
    monkeypatch.setattr(workflow_api, "GENERATION_ENFORCEMENT_ENABLED", True)
    assert _day(client, analysis_id, date).status_code == 200
    params, _ = _job(db_engine, evidence["id"])
    _update_job(db_engine, evidence["id"], params={**params, "dataset_generation": "f" * 32})
    assert _day(client, analysis_id, date).status_code == 404
    _update_job(db_engine, evidence["id"], params=params)
    client.cookies.clear()
    _login(db_engine, client, "intruder@example.com")
    assert _day(client, analysis_id, date).status_code == 404


def test_day_detail_uses_the_compute_rate_limit(db_engine, client, app, monkeypatch):
    """OD-C14 (i): the existing per-user compute limit applies (the run consumed one request)."""
    _, analysis_id, evidence = _compact_run(db_engine, client, "limited@example.com")
    date = evidence["result"]["days"][0]["date"]
    monkeypatch.setattr(app.state.settings, "rate_limit_compute", 3)
    assert _day(client, analysis_id, date).status_code == 200
    assert _day(client, analysis_id, date).status_code == 200
    limited = _day(client, analysis_id, date)
    assert limited.status_code == 429


def test_owner_shaped_file_fits_the_default_cap_when_compact(db_engine, client):
    """SYNTHETIC 14 dates x 13 hourly segments x 5 lanes through the route with the default request."""
    from backend.api.workflow import _encoded_size

    lanes, hours = ["l1", "l2", "l3", "l4", "l5"], range(8, 21)
    headers = _login(db_engine, client, "fourteen@example.com")
    analysis_id = _analysis(client, headers, _grid_setup(lanes, hours), _csv(_grid_events(14, lanes, hours)))
    response = _run(client, headers, analysis_id, {})
    assert response.status_code == 200, response.text
    result = response.json()["evidence"]["result"]
    assert len(result["results"]) == 14 * 13 * 5 and len(result["days"]) == 14
    assert _encoded_size(result) <= 524_288
    assert all(day["event_count"] <= 3000 for day in result["days"])
