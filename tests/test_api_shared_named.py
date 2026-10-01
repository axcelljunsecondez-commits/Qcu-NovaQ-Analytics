"""Named Shared Queue API first slice (spec 2026-09-30-shared-queue-named-api-ui-first-slice.md, section 15).

The PostgreSQL cases (B1 persistence identity and the light, maximum-structure, busy, and stress round
trips) run only when NOVAQ_TEST_DATABASE_URL names a PostgreSQL test database; a skip is not a pass.
"""

from __future__ import annotations

import ast
import copy
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import event, func, select

from backend.api import shared_named
from backend.api.main import CsrfDoubleSubmitMiddleware
from backend.db.models import AnalysisProject, Dataset, Job
from backend.queueing_engine.services.shared_workforce import evaluate_roster
from backend.queueing_engine.simulation.shared_continuous_des import CLOSING_POLICIES
from backend.queueing_engine.simulation.shared_named_attribution import (
    NamedAttributionError,
    build_named_attribution,
)
from backend.queueing_engine.simulation.shared_named_des import (
    APPROVED_EMPLOYEE_POLICY,
    POLICY_MEANINGS,
    EmployeeDesPolicy,
)
from backend.queueing_engine.simulation.shared_named_playback import (
    NamedPlaybackError,
    playback_from_named_replications,
    rebuild_named_inputs,
)
from backend.queueing_engine.simulation.shared_named_replications import (
    NO_VERDICT_REASON,
    named_inputs_digest,
    replication_seed_sequence,
    run_named_replications,
    simulate_named_replication,
)
from tests.helpers import clear_cookies, create_user, csrf_header, login, make_sessionmaker
from tests.test_shared_segments import NOVAMART_AVERAGE_ROWS

REPO_ROOT = Path(__file__).resolve().parents[1]
ON_POSTGRES = bool(os.environ.get("NOVAQ_TEST_DATABASE_URL"))
postgres_only = pytest.mark.skipif(not ON_POSTGRES, reason="needs NOVAQ_TEST_DATABASE_URL (PostgreSQL)")

SHARED_SETUP = {
    "queue_structure": "shared_queue",
    "fixed_server_count": 1,
    "staffing_varies_by_period": False,
    "capacity_mode": "unlimited",
    "total_system_capacity": None,
    "abandonment_mode": "not_modeled",
    "patience_rate_per_hour": None,
}
LIGHT_ROWS = [
    {"time": "08:00-09:00", "lambda": 4.0, "mu": 4.0, "c": 1},
    {"time": "09:00-10:00", "lambda": 4.0, "mu": 4.0, "c": 1},
]
POLICY = asdict(APPROVED_EMPLOYEE_POLICY)


# ── Fixtures and builders ───────────────────────────────────────────────────


def _workspace(db_engine, *, email: str = "owner@example.com", setup: dict | None = None,
               rows: list[dict] | None = None, ok: bool = True) -> dict[str, int]:
    """A user with one analysis and one dataset; returns their ids. The user may already exist."""
    with make_sessionmaker(db_engine)() as db:
        from backend.db.models import User
        user = db.execute(select(User).where(User.email_normalized == email)).scalar_one_or_none()
    if user is None:
        user = create_user(db_engine, email, "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(user_id=user.id, name="Named queue", queue_setup_json=setup or SHARED_SETUP,
                                   setup_status="ready")
        db.add(analysis)
        db.flush()
        dataset = _add_dataset(db, user.id, analysis.id, rows if rows is not None else LIGHT_ROWS, ok=ok)
        db.commit()
        return {"user_id": user.id, "analysis_id": analysis.id, "dataset_id": dataset.id}


def _add_dataset(db, user_id: int, analysis_id: int, rows: list[dict], *, ok: bool = True) -> Dataset:
    dataset = Dataset(user_id=user_id, analysis_id=analysis_id, name="Rates", source_filename="rates.csv",
                      source_format="csv", row_count=len(rows), normalized_json=rows,
                      validation_report_json={"ok": ok, "message": "Input data is valid." if ok else "Invalid."})
    db.add(dataset)
    db.flush()
    return dataset


def _signed_in(client, db_engine, **options: Any) -> dict[str, int]:
    ids = _workspace(db_engine, **options)
    assert login(client, options.get("email", "owner@example.com"), "pw") == 200
    return ids


def _light(dataset_id: int, **changes: Any) -> dict[str, Any]:
    """Two employees, two hourly demand periods, and a roster that the domain accepts."""
    body: dict[str, Any] = {
        "dataset_id": dataset_id,
        "horizon": {"start_minute": 480, "end_minute": 600},
        "required_staffing": [
            {"segment_id": "A", "start_minute": 480, "end_minute": 540, "servers": 1},
            {"segment_id": "B", "start_minute": 540, "end_minute": 600, "servers": 2},
        ],
        "employees": [
            {"employee_id": "E1", "availability": [{"start_minute": 480, "end_minute": 600}],
             "pay": {"regular_rate_per_hour": 100.0, "overtime_rate_per_hour": 150.0, "daily_regular_paid_minutes": 480}},
            {"employee_id": "E2", "availability": [{"start_minute": 480, "end_minute": 600}],
             "pay": {"regular_rate_per_hour": 90.5, "overtime_rate_per_hour": None, "daily_regular_paid_minutes": None}},
        ],
        "rules": {
            "shift_rules": {"earliest_start_minute": 480, "latest_end_minute": 600, "min_shift_minutes": 60,
                            "max_shift_minutes": 120, "boundary_granularity_minutes": 30,
                            "max_shifts_per_employee": 1, "min_minutes_between_shifts": None},
            "break_rules": [{"min_shift_minutes": 60, "max_shift_minutes": 120, "min_gap_minutes": 0, "breaks": []}],
            "register_count": 2,
        },
        "roster": [
            {"employee_id": "E1", "start_minute": 480, "end_minute": 600, "breaks": []},
            {"employee_id": "E2", "start_minute": 540, "end_minute": 600, "breaks": []},
        ],
        "closing_policy": "DRAIN",
        "employee_policy": dict(POLICY),
    }
    body.update(changes)
    return body


def _run(dataset_id: int, *, replications: int = 2, seed: int = 7, **changes: Any) -> dict[str, Any]:
    return {**_light(dataset_id, **changes), "replications": replications, "seed": seed}


def _structured(dataset_id: int, *, closing_policy: str = "HARD_CUTOFF") -> dict[str, Any]:
    """The maximum measured structure: 52 required-staffing segments, 24 employees, 48 split shifts with breaks."""
    staffing = []
    for hour in range(13):
        for quarter in range(4):
            start = 300 + hour * 60 + quarter * 15
            staffing.append({"segment_id": f"S{hour:02d}{quarter}", "start_minute": start, "end_minute": start + 15,
                             "servers": 2 + (hour + quarter) % 3})
    employees, roster = [], []
    for index in range(24):
        who = f"E{index:02d}"
        employees.append({"employee_id": who, "availability": [{"start_minute": 300, "end_minute": 1080}],
                          "pay": {"regular_rate_per_hour": 80.0 + index, "overtime_rate_per_hour": 120.0 + index,
                                  "daily_regular_paid_minutes": 480}})
        first = 300 + 15 * (index % 12)
        second = first + 240 + 60
        for start in (first, second):
            roster.append({"employee_id": who, "start_minute": start, "end_minute": start + 240, "breaks": [
                {"name": "rest", "start_minute": start + 60}, {"name": "meal", "start_minute": start + 120}]})
    return {
        "dataset_id": dataset_id,
        "horizon": {"start_minute": 300, "end_minute": 1080},
        "required_staffing": staffing,
        "employees": employees,
        "rules": {
            "shift_rules": {"earliest_start_minute": 300, "latest_end_minute": 1080, "min_shift_minutes": 60,
                            "max_shift_minutes": 480, "boundary_granularity_minutes": 15,
                            "max_shifts_per_employee": 2, "min_minutes_between_shifts": 30},
            "break_rules": [
                {"min_shift_minutes": 60, "max_shift_minutes": 180, "min_gap_minutes": 0, "breaks": []},
                {"min_shift_minutes": 181, "max_shift_minutes": 300, "min_gap_minutes": 15, "breaks": [
                    {"name": "rest", "duration_minutes": 15, "paid": True,
                     "earliest_start_offset_minutes": 60, "latest_start_offset_minutes": 90},
                    {"name": "meal", "duration_minutes": 30, "paid": False,
                     "earliest_start_offset_minutes": 120, "latest_start_offset_minutes": 180}]},
                {"min_shift_minutes": 301, "max_shift_minutes": 480, "min_gap_minutes": 15, "breaks": [
                    {"name": "meal", "duration_minutes": 30, "paid": False,
                     "earliest_start_offset_minutes": 120, "latest_start_offset_minutes": 300}]},
            ],
            "register_count": 24,
        },
        "roster": roster,
        "closing_policy": closing_policy,
        "employee_policy": dict(POLICY),
    }


def _scaled_rows(scale: float) -> list[dict]:
    return [{**row, "lambda": cast(float, row["lambda"]) * scale} for row in NOVAMART_AVERAGE_ROWS]


def _named_jobs(db_engine) -> list[Job]:
    with make_sessionmaker(db_engine)() as db:
        return list(db.execute(select(Job).where(Job.kind == shared_named.JOB_KIND)).scalars())


def _job_count(db_engine) -> int:
    with make_sessionmaker(db_engine)() as db:
        return db.execute(select(func.count()).select_from(Job)).scalar_one()


def _create(client, analysis_id: int, body: dict) -> Any:
    return client.post(f"/analyses/{analysis_id}/shared-named/runs", json=body, headers=csrf_header(client))


def _validate(client, analysis_id: int, body: dict) -> Any:
    return client.post(f"/analyses/{analysis_id}/shared-named/validate", json=body, headers=csrf_header(client))


def _created_run(client, ids: dict[str, int], **options: Any) -> dict[str, Any]:
    response = _create(client, ids["analysis_id"], _run(ids["dataset_id"], **options))
    assert response.status_code == 200, response.text
    return response.json()["evidence"]


def _tamper(db_engine, run_id: int, mutate) -> None:
    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, run_id)
        result = copy.deepcopy(job.result_json)
        mutate(result)
        job.result_json = result
        db.commit()


def _json(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def _stored_result(db_engine, run_id: int) -> dict:
    with make_sessionmaker(db_engine)() as db:
        return db.execute(select(Job.result_json).where(Job.id == run_id)).scalar_one()


@pytest.fixture
def engine_spy(monkeypatch):
    calls: list[str] = []

    def spy(name: str):
        def called(*args: Any, **kwargs: Any):
            calls.append(name)
            raise AssertionError(f"{name} must not be called")
        return called

    for name in ("run_named_replications", "simulate_named_prescribed", "evaluate_roster",
                 "timeline_from_aggregate_rows"):
        monkeypatch.setattr(shared_named, name, spy(name))
    return calls


# ── 1. Authentication and CSRF ──────────────────────────────────────────────


ROUTES = [
    ("get", "/analyses/{a}/shared-named/contract"),
    ("post", "/analyses/{a}/shared-named/validate"),
    ("post", "/analyses/{a}/shared-named/runs"),
    ("get", "/analyses/{a}/shared-named/runs"),
    ("get", "/analyses/{a}/shared-named/runs/1"),
    ("get", "/analyses/{a}/shared-named/runs/1/replications/0"),
]


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_every_route_requires_a_session(client, db_engine, method, path):
    ids = _workspace(db_engine)
    url = path.format(a=ids["analysis_id"])
    response = client.get(url) if method == "get" else client.post(url, json=_run(ids["dataset_id"]))
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated."}


@pytest.mark.parametrize("route", ["validate", "runs"])
def test_posts_need_the_csrf_header(client, db_engine, route):
    ids = _signed_in(client, db_engine)
    url = f"/analyses/{ids['analysis_id']}/shared-named/{route}"
    body = _run(ids["dataset_id"]) if route == "runs" else _light(ids["dataset_id"])
    for headers in ({}, {"X-CSRF-Token": "wrong"}):
        response = client.post(url, json=body, headers=headers)
        assert response.status_code == 403
        assert response.json() == {"detail": "CSRF token mismatch."}
    assert _named_jobs(db_engine) == []
    assert client.post(url, json=body, headers=csrf_header(client)).status_code == 200


def test_csrf_exemptions_are_unchanged():
    assert CsrfDoubleSubmitMiddleware.EXEMPT_FAMILIES == ("/analysis", "/simulation", "/optimize", "/onboarding")


# ── 2. Ownership ────────────────────────────────────────────────────────────


def test_another_users_analysis_is_not_found(client, db_engine):
    mine = _signed_in(client, db_engine)
    theirs = _workspace(db_engine, email="other@example.com")
    a = theirs["analysis_id"]
    assert client.get(f"/analyses/{a}/shared-named/contract").status_code == 404
    assert _validate(client, a, _light(theirs["dataset_id"])).status_code == 404
    assert _create(client, a, _run(theirs["dataset_id"])).status_code == 404
    assert client.get(f"/analyses/{a}/shared-named/runs").status_code == 404
    assert mine["analysis_id"] != a


def test_a_dataset_of_another_user_or_analysis_is_not_found(client, db_engine):
    mine = _signed_in(client, db_engine)
    other_analysis = _workspace(db_engine)  # same user, another analysis
    theirs = _workspace(db_engine, email="other@example.com")
    for dataset_id in (other_analysis["dataset_id"], theirs["dataset_id"], 999_999):
        for response in (_validate(client, mine["analysis_id"], _light(dataset_id)),
                         _create(client, mine["analysis_id"], _run(dataset_id))):
            assert response.status_code == 404
            assert response.json() == {"detail": {"code": "dataset_not_found"}}
    assert _named_jobs(db_engine) == []


def test_runs_of_another_analysis_user_or_kind_are_not_found(client, db_engine):
    ids = _signed_in(client, db_engine)
    run = _created_run(client, ids)
    other = _workspace(db_engine)  # same user, another analysis
    clear_cookies(client)
    theirs = _signed_in(client, db_engine, email="other@example.com")
    their_run = _created_run(client, theirs)
    clear_cookies(client)
    assert login(client, "owner@example.com", "pw") == 200
    with make_sessionmaker(db_engine)() as db:
        legacy = Job(user_id=ids["user_id"], kind="workflow_des", status="completed",
                     params_json={"analysis_id": ids["analysis_id"]}, result_json={})
        db.add(legacy)
        db.commit()
        legacy_id = legacy.id
    a = ids["analysis_id"]
    for url in (f"/analyses/{other['analysis_id']}/shared-named/runs/{run['id']}",
                f"/analyses/{a}/shared-named/runs/{their_run['id']}",
                f"/analyses/{a}/shared-named/runs/{legacy_id}",
                f"/analyses/{a}/shared-named/runs/999999",
                f"/analyses/{a}/shared-named/runs/{legacy_id}/replications/0"):
        response = client.get(url)
        assert response.status_code == 404, url
        assert response.json() == {"detail": {"code": "run_not_found"}}
    assert client.get(f"/analyses/{other['analysis_id']}/shared-named/runs").json() == {"runs": []}


@pytest.mark.parametrize("index", [2, 3, -1])
def test_a_replication_index_outside_the_run_is_not_found(client, db_engine, index):
    ids = _signed_in(client, db_engine)
    run = _created_run(client, ids, replications=2)
    response = client.get(f"/analyses/{ids['analysis_id']}/shared-named/runs/{run['id']}/replications/{index}")
    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "replication_not_found", "max_index": 1}}


# ── 3. Eligibility (OD-3, OD-7) ─────────────────────────────────────────────


@pytest.mark.parametrize(("change", "reason"), [
    ({"queue_structure": "separate_queues"}, "queue_structure_not_shared_queue"),
    ({"queue_structure": "single_server"}, "queue_structure_not_shared_queue"),
    ({"queue_structure": "unknown"}, "queue_structure_not_shared_queue"),
    ({"capacity_mode": "finite", "total_system_capacity": 10}, "capacity_not_unlimited"),
    ({"capacity_mode": "unknown"}, "capacity_not_unlimited"),
    ({"abandonment_mode": "modeled", "patience_rate_per_hour": 2.0}, "abandonment_not_not_modeled"),
    ({"abandonment_mode": "unknown"}, "abandonment_not_not_modeled"),
])
def test_ineligible_setups_are_refused(client, db_engine, engine_spy, change, reason):
    ids = _signed_in(client, db_engine, setup={**SHARED_SETUP, **change})
    contract = client.get(f"/analyses/{ids['analysis_id']}/shared-named/contract").json()
    assert contract["eligible"] is False
    assert contract["ineligible_reasons"] == [reason]
    for response in (_validate(client, ids["analysis_id"], _light(ids["dataset_id"])),
                     _create(client, ids["analysis_id"], _run(ids["dataset_id"]))):
        assert response.status_code == 422
        assert response.json() == {"detail": {"code": "ineligible_setup", "reasons": [reason]}}
    assert engine_spy == []
    assert _named_jobs(db_engine) == []


def test_a_dataset_that_was_not_processed_is_refused(client, db_engine):
    ids = _signed_in(client, db_engine, ok=False)
    for response in (_validate(client, ids["analysis_id"], _light(ids["dataset_id"])),
                     _create(client, ids["analysis_id"], _run(ids["dataset_id"]))):
        assert response.status_code == 422
        assert response.json() == {"detail": {"code": "dataset_not_processed"}}


def test_an_archived_analysis_cannot_create_a_run_but_its_runs_stay_readable(client, db_engine, monkeypatch):
    ids = _signed_in(client, db_engine)
    run = _created_run(client, ids)
    with make_sessionmaker(db_engine)() as db:
        db.get(AnalysisProject, ids["analysis_id"]).archived_at = datetime.now(timezone.utc)
        db.commit()
    calls: list[int] = []
    monkeypatch.setattr(shared_named, "run_named_replications", lambda *a, **k: calls.append(1))
    before = _job_count(db_engine)
    a = ids["analysis_id"]
    response = _create(client, a, _run(ids["dataset_id"]))
    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "analysis_archived"}}
    assert calls == []
    assert _job_count(db_engine) == before
    assert _validate(client, a, _light(ids["dataset_id"])).json()["runnable"] is True
    assert [item["id"] for item in client.get(f"/analyses/{a}/shared-named/runs").json()["runs"]] == [run["id"]]
    assert client.get(f"/analyses/{a}/shared-named/runs/{run['id']}").status_code == 200
    assert client.get(f"/analyses/{a}/shared-named/runs/{run['id']}/replications/0").status_code == 200


# ── 4. Model scope: never reduced to M/M/c ──────────────────────────────────


@pytest.mark.parametrize("rows", [
    [{**LIGHT_ROWS[0], "variance": 0.01}, LIGHT_ROWS[1]],
    [{**LIGHT_ROWS[0], "K": 10}, LIGHT_ROWS[1]],
    [{**LIGHT_ROWS[0], "theta": 2.0}, LIGHT_ROWS[1]],
    [{**LIGHT_ROWS[0], "queue_structure": "separate_queues"}, LIGHT_ROWS[1]],
    [{"time": "2026-09-01 08:00-09:00 UTC", "lambda": 4.0, "mu": 4.0, "c": 1, "variance": 0.02},
     {"time": "2026-09-01 09:00-10:00 UTC", "lambda": 4.0, "mu": 4.0, "c": 1, "variance": 0.02}],
    [{"time": "8:00 AM", "lambda": 4.0, "mu": 4.0, "c": 1}],
])
def test_unsupported_dataset_rows_fail_at_the_demand_stage(client, db_engine, rows):
    ids = _signed_in(client, db_engine, rows=rows)
    validated = _validate(client, ids["analysis_id"], _light(ids["dataset_id"]))
    assert validated.status_code == 200
    body = validated.json()
    assert (body["runnable"], body["stage_failed"], body["demand"], body["roster_report"]) == (False, "demand", None, None)
    assert body["problems"]
    created = _create(client, ids["analysis_id"], _run(ids["dataset_id"]))
    assert created.status_code == 422
    assert created.json()["detail"]["code"] == "named_input_invalid"
    assert created.json()["detail"]["stage"] == "demand"
    assert _named_jobs(db_engine) == []


# ── 5. Schema ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", [
    ("closing_policy",), ("employee_policy",), ("required_staffing",), ("replications",), ("seed",),
    ("dataset_id",), ("roster",), ("employees", 0, "pay", "regular_rate_per_hour"),
    ("employees", 0, "pay", "overtime_rate_per_hour"), ("employees", 0, "pay", "daily_regular_paid_minutes"),
    ("rules", "shift_rules", "min_minutes_between_shifts"), ("employee_policy", "drain_crew"),
])
def test_a_missing_required_key_is_refused_without_a_default(client, db_engine, engine_spy, path):
    ids = _signed_in(client, db_engine)
    body = _run(ids["dataset_id"])
    target = body
    for key in path[:-1]:
        target = target[key]
    del target[path[-1]]
    assert _create(client, ids["analysis_id"], body).status_code == 422
    assert engine_spy == []
    assert _named_jobs(db_engine) == []


def _raw_post(client, url: str, body: dict, marker_path: tuple, token: str):
    target = body
    for key in marker_path[:-1]:
        target = target[key]
    target[marker_path[-1]] = "__MARKER__"
    raw = json.dumps(body).replace('"__MARKER__"', token)
    return client.post(url, content=raw, headers={**csrf_header(client), "Content-Type": "application/json"})


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("marker_path", [
    ("horizon", "start_minute"),
    ("required_staffing", 0, "servers"),
    ("employees", 0, "pay", "regular_rate_per_hour"),
    ("employees", 0, "pay", "overtime_rate_per_hour"),
    ("seed",),
    ("replications",),
])
def test_non_finite_numbers_are_refused_in_every_field_class(client, db_engine, engine_spy, token, marker_path):
    ids = _signed_in(client, db_engine)
    url = f"/analyses/{ids['analysis_id']}/shared-named/runs"
    response = _raw_post(client, url, _run(ids["dataset_id"]), marker_path, token)
    assert response.status_code == 422
    errors = response.json()["detail"]  # FastAPI's validation list; the non-finite input shown as its token
    assert isinstance(errors, list) and errors
    assert [error["input"] for error in errors if tuple(error["loc"][1:]) == marker_path] == [token]
    assert engine_spy == []
    if marker_path not in (("seed",), ("replications",)):
        validate_url = f"/analyses/{ids['analysis_id']}/shared-named/validate"
        assert _raw_post(client, validate_url, _light(ids["dataset_id"]), marker_path, token).status_code == 422
    assert _named_jobs(db_engine) == []


@pytest.mark.parametrize(("path", "value"), [
    (("horizon", "start_minute"), 480.0),
    (("required_staffing", 0, "servers"), 1.0),
    (("seed",), 7.0),
    (("replications",), 2.0),
    (("employees", 0, "pay", "daily_regular_paid_minutes"), 480.0),
    (("horizon", "end_minute"), True),
    (("rules", "register_count"), "2"),
    (("employees", 0, "pay", "regular_rate_per_hour"), "100"),
    (("employees", 0, "pay", "regular_rate_per_hour"), True),
    (("closing_policy",), 1),
    (("seed",), -1),
    (("seed",), shared_named.SEED_MAX + 1),
    (("replications",), 0),
    (("employees", 0, "employee_id"), ""),
    (("employees", 0, "employee_id"), "x" * 65),
])
def test_wrong_types_and_bounds_are_refused(client, db_engine, engine_spy, path, value):
    ids = _signed_in(client, db_engine)
    body = _run(ids["dataset_id"])
    target = body
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert _create(client, ids["analysis_id"], body).status_code == 422
    assert engine_spy == []


@pytest.mark.parametrize("where", [(), ("horizon",), ("employees", 0), ("employees", 0, "pay"), ("employee_policy",)])
def test_extra_keys_are_refused(client, db_engine, engine_spy, where):
    ids = _signed_in(client, db_engine)
    body = _run(ids["dataset_id"])
    target = body
    for key in where:
        target = target[key]
    target["name"] = "Alice"
    assert _create(client, ids["analysis_id"], body).status_code == 422
    assert engine_spy == []


@pytest.mark.parametrize("field", list(POLICY))
def test_a_non_approved_employee_policy_fails_at_the_engine_stage(client, db_engine, field):
    ids = _signed_in(client, db_engine)
    policy = {**POLICY, field: "something_else"}
    validated = _validate(client, ids["analysis_id"], _light(ids["dataset_id"], employee_policy=policy)).json()
    assert (validated["runnable"], validated["stage_failed"]) == (False, "engine")
    assert any(field in problem for problem in validated["problems"])
    created = _create(client, ids["analysis_id"], _run(ids["dataset_id"], employee_policy=policy))
    assert created.status_code == 422
    assert created.json()["detail"]["stage"] == "engine"
    assert _named_jobs(db_engine) == []


def test_an_unapproved_closing_policy_fails_at_the_engine_stage(client, db_engine):
    ids = _signed_in(client, db_engine)
    validated = _validate(client, ids["analysis_id"], _light(ids["dataset_id"], closing_policy="drain")).json()
    assert (validated["runnable"], validated["stage_failed"]) == (False, "engine")
    assert _create(client, ids["analysis_id"], _run(ids["dataset_id"], closing_policy="drain")).status_code == 422


# ── 5 (B1). Persistence identity, SQLite unit level ─────────────────────────


def test_b1_rereads_the_database_not_the_identity_map(client, db_engine, session_factory):
    """A change made in the database after the flush must be seen by the re-read, so the run is refused."""
    ids = _signed_in(client, db_engine)
    before = _job_count(db_engine)
    jobs_table = Job.__table__

    def tamper_after_flush(session, _context):
        for item in session.new | session.dirty:
            if isinstance(item, Job) and item.kind == shared_named.JOB_KIND and item.id is not None:
                changed = copy.deepcopy(item.result_json)
                changed["replications"][0]["customers"]["arrivals"] += 1
                session.connection().execute(
                    jobs_table.update().where(jobs_table.c.id == item.id).values(result_json=changed))

    from sqlalchemy.orm import Session as OrmSession
    event.listen(OrmSession, "after_flush", tamper_after_flush)
    try:
        response = _create(client, ids["analysis_id"], _run(ids["dataset_id"]))
    finally:
        event.remove(OrmSession, "after_flush", tamper_after_flush)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "persistence_identity_mismatch"
    assert [(item["check"], item.get("replication_index"), item.get("fields")) for item in detail["checks"]] == [
        ("stored_row", 0, ["customers"])]
    assert "evidence" not in response.json() and "id" not in json.dumps(detail["checks"])
    assert _job_count(db_engine) == before
    assert client.get(f"/analyses/{ids['analysis_id']}/shared-named/runs").json() == {"runs": []}


@pytest.mark.parametrize("mutate", [
    lambda result: result["provenance"]["inputs"]["employees"][0]["pay"].update(regular_rate_per_hour=100),
    lambda result: result["provenance"].update(root_entropy=float(result["provenance"]["root_entropy"])),
    lambda result: result["provenance"].update(inputs_sha256="0" * 64),
    lambda result: result["replications"][1]["waiting"].update(max_queue_in_horizon=float(
        result["replications"][1]["waiting"]["max_queue_in_horizon"] or 0)),
    lambda result: result.update(replications=result["replications"][:1]),
])
def test_b1_a_differing_read_back_rolls_back_and_exposes_no_run(client, db_engine, monkeypatch, mutate):
    """A read-back that differs only by representation (int for float, float for int) is still refused."""
    ids = _signed_in(client, db_engine)
    real = shared_named._reread_result_json

    def differing(db, job_id):
        value = copy.deepcopy(real(db, job_id))
        mutate(value)
        return value

    monkeypatch.setattr(shared_named, "_reread_result_json", differing)
    before = _job_count(db_engine)
    response = _create(client, ids["analysis_id"], _run(ids["dataset_id"]))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "persistence_identity_mismatch"
    assert response.json()["detail"]["checks"]
    assert "evidence" not in response.json()
    assert _job_count(db_engine) == before
    assert client.get(f"/analyses/{ids['analysis_id']}/shared-named/runs").json() == {"runs": []}


@pytest.mark.skipif(ON_POSTGRES, reason="documents the SQLite JSON path; PostgreSQL is covered below")
def test_b1_on_sqlite_keeps_a_large_float_so_the_run_commits(client, db_engine):
    """B1 is a representation check, not a numeric-domain rule: where storage keeps 1e16 the run is accepted."""
    ids = _signed_in(client, db_engine)
    body = _run(ids["dataset_id"])
    body["employees"][0]["pay"]["regular_rate_per_hour"] = 1e16
    assert _create(client, ids["analysis_id"], body).status_code == 200


# ── 6. Limits (provisional, NOT PRODUCTION-APPROVED) ────────────────────────


def _segments(count: int) -> list[dict]:
    return [{"segment_id": f"S{i}", "start_minute": 480, "end_minute": 481, "servers": 1} for i in range(count)]


@pytest.mark.parametrize(("limit", "change"), [
    ("replications", lambda b: b.update(replications=shared_named.N_MAX + 1)),
    ("required_staffing", lambda b: b.update(required_staffing=_segments(shared_named.S_MAX + 1))),
    ("employees", lambda b: b.update(employees=[{**b["employees"][0], "employee_id": f"E{i}"}
                                                for i in range(shared_named.E_MAX + 1)])),
    ("roster", lambda b: b.update(roster=[b["roster"][0]] * (shared_named.R_MAX + 1))),
    ("break_rules", lambda b: b["rules"].update(break_rules=b["rules"]["break_rules"] * (shared_named.BR_MAX + 1))),
    ("availability", lambda b: b["employees"][0].update(
        availability=b["employees"][0]["availability"] * (shared_named.AV_MAX + 1))),
    ("break_rules.breaks", lambda b: b["rules"]["break_rules"][0].update(breaks=[
        {"name": "rest", "duration_minutes": 15, "paid": True, "earliest_start_offset_minutes": 0,
         "latest_start_offset_minutes": 30}] * (shared_named.BQ_MAX + 1))),
    ("roster.breaks", lambda b: b["roster"][0].update(
        breaks=[{"name": "rest", "start_minute": 500}] * (shared_named.BS_MAX + 1))),
])
def test_limits_are_refused_before_any_computation(client, db_engine, engine_spy, limit, change):
    ids = _signed_in(client, db_engine)
    body = _run(ids["dataset_id"])
    change(body)
    response = _create(client, ids["analysis_id"], body)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert (detail["code"], detail["limit"]) == ("limit_exceeded", limit)
    assert detail["value"] == detail["max"] + 1
    if limit != "replications":
        workforce = {key: value for key, value in body.items() if key not in ("replications", "seed")}
        assert _validate(client, ids["analysis_id"], workforce).json()["detail"]["code"] == "limit_exceeded"
    assert engine_spy == []
    assert _named_jobs(db_engine) == []


def test_the_replication_limit_itself_is_accepted(client, db_engine):
    ids = _signed_in(client, db_engine)
    run = _created_run(client, ids, replications=shared_named.N_MAX)
    assert run["result"]["provenance"]["replications"] == shared_named.N_MAX == 9


def test_the_limits_are_the_provisional_measured_values():
    assert (shared_named.N_MAX, shared_named.S_MAX, shared_named.E_MAX, shared_named.R_MAX) == (9, 52, 24, 48)
    assert (shared_named.AV_MAX, shared_named.BR_MAX, shared_named.BQ_MAX, shared_named.BS_MAX) == (3, 3, 2, 2)
    assert shared_named.LIMITS_STATUS == "provisional_not_production_approved"


# ── 7. Faithfulness to the domain ───────────────────────────────────────────


def test_contract_values_are_the_imported_constants(client, db_engine, app):
    ids = _signed_in(client, db_engine)
    contract = client.get(f"/analyses/{ids['analysis_id']}/shared-named/contract").json()
    assert contract["eligible"] is True and contract["ineligible_reasons"] == []
    assert contract["closing_policies"] == list(CLOSING_POLICIES)
    assert contract["employee_policy"] == {
        name: {"approved": value, "meaning": POLICY_MEANINGS[name]} for name, value in POLICY.items()}
    assert contract["seed"] == {"min": 0, "max": 2**53 - 1}
    assert (contract["verdict"], contract["verdict_reason"]) == (None, NO_VERDICT_REASON)
    assert contract["limits"]["result_max_bytes"] == app.state.settings.result_jsonb_max_bytes
    assert contract["limits"]["status"] == "provisional_not_production_approved"
    assert contract["model_scope"] == shared_named.MODEL_SCOPE


def _domain(body: dict, rows: list[dict]) -> dict:
    from backend.queueing_engine.services.shared_segments import timeline_from_aggregate_rows
    periods, _ = timeline_from_aggregate_rows(rows)
    return rebuild_named_inputs({
        "horizon": body["horizon"], "demand_periods": [asdict(period) for period in periods],
        "required_staffing": body["required_staffing"], "employees": body["employees"], "rules": body["rules"],
        "roster": body["roster"]})


def test_the_run_result_is_the_domain_result_unchanged(client, db_engine):
    ids = _signed_in(client, db_engine)
    body = _run(ids["dataset_id"], replications=3, seed=12345)
    response = _create(client, ids["analysis_id"], body)
    inputs = _domain(body, LIGHT_ROWS)
    direct = run_named_replications(
        inputs["horizon"], inputs["demand_periods"], inputs["employees"], inputs["rules"], inputs["roster"],
        replications=3, seed=12345, closing_policy="DRAIN", employee_policy=APPROVED_EMPLOYEE_POLICY,
        required_staffing=inputs["required_staffing"])
    assert response.json()["evidence"]["result"] == _json(direct)


def test_validate_returns_the_domain_roster_report_unchanged(client, db_engine):
    ids = _signed_in(client, db_engine)
    body = _light(ids["dataset_id"])
    validated = _validate(client, ids["analysis_id"], body).json()
    inputs = _domain(body, LIGHT_ROWS)
    direct = evaluate_roster(inputs["horizon"], inputs["employees"], inputs["rules"], inputs["roster"],
                             required_staffing=inputs["required_staffing"])
    assert validated["runnable"] is True and validated["stage_failed"] is None and validated["problems"] == []
    assert validated["roster_report"] == _json(direct)
    assert validated["demand"] == {"dataset_id": ids["dataset_id"], "demand_periods": [
        asdict(period) for period in inputs["demand_periods"]]}


# ── 8. X4 and X7 ────────────────────────────────────────────────────────────


def test_a_register_excess_roster_is_not_runnable(client, db_engine):
    ids = _signed_in(client, db_engine)
    body = _light(ids["dataset_id"])
    body["rules"]["register_count"] = 1
    validated = _validate(client, ids["analysis_id"], body).json()
    assert (validated["runnable"], validated["stage_failed"]) == (False, "engine")
    assert validated["roster_report"]["status"] == "INVALID"
    assert validated["roster_report"]["violations"]
    assert all("X4" in problem for problem in validated["problems"])
    created = _create(client, ids["analysis_id"], {**body, "replications": 2, "seed": 1})
    assert created.status_code == 422 and created.json()["detail"]["stage"] == "engine"


def test_a_roster_missing_only_pay_is_runnable(client, db_engine):
    ids = _signed_in(client, db_engine)
    body = _light(ids["dataset_id"])
    for employee in body["employees"]:
        employee["pay"] = {"regular_rate_per_hour": None, "overtime_rate_per_hour": None,
                           "daily_regular_paid_minutes": None}
    validated = _validate(client, ids["analysis_id"], body).json()
    assert validated["runnable"] is True
    assert validated["roster_report"]["status"] == "INCOMPLETE"
    assert _create(client, ids["analysis_id"], {**body, "replications": 1, "seed": 3}).status_code == 200


def test_a_staffing_segment_crossing_a_demand_boundary_is_not_runnable(client, db_engine):
    ids = _signed_in(client, db_engine)
    body = _light(ids["dataset_id"], required_staffing=[
        {"segment_id": "ALL", "start_minute": 480, "end_minute": 600, "servers": 1}])
    validated = _validate(client, ids["analysis_id"], body).json()
    assert (validated["runnable"], validated["stage_failed"]) == (False, "workforce")
    assert any("crosses a demand-period boundary" in problem for problem in validated["problems"])


def test_an_empty_roster_is_runnable_and_serves_nobody(client, db_engine):
    ids = _signed_in(client, db_engine)
    validated = _validate(client, ids["analysis_id"], _light(ids["dataset_id"], roster=[])).json()
    assert validated["runnable"] is True
    run = _created_run(client, ids, roster=[], replications=3)
    for row in run["result"]["replications"]:
        assert row["customers"]["served"] == 0
        assert row["customers"]["unserved"] == row["customers"]["arrivals"]


# ── 9. Persistence ──────────────────────────────────────────────────────────


def test_the_job_records_exact_params_and_the_unmodified_result(client, db_engine):
    ids = _signed_in(client, db_engine)
    run = _created_run(client, ids, replications=2, seed=99)
    (job,) = _named_jobs(db_engine)
    assert (job.id, job.kind, job.status, job.user_id) == (run["id"], "shared_named_replications", "completed",
                                                           ids["user_id"])
    expected_keys = [
        "analysis_id", "scenario_id", "dataset_id", "replications", "seed", "closing_policy",
        "named_api_version", "engine_version", "method_version", "named_engine_version", "state_machine_version",
        "arrival_engine_version", "inputs_sha256", "root_entropy", "dataset_generation", "setup_hash"]
    assert sorted(job.params_json) == sorted(expected_keys)
    if db_engine.dialect.name == "sqlite":
        # The write order (server keys after request keys) survives only where storage keeps key order:
        # PostgreSQL jsonb stores object keys in its own order, so there the key set is what is checked.
        assert list(job.params_json) == expected_keys
    provenance = job.result_json["provenance"]
    assert job.params_json["scenario_id"] is None
    assert (job.params_json["replications"], job.params_json["seed"], job.params_json["root_entropy"]) == (2, 99, 99)
    assert job.params_json["engine_version"] == provenance["method_version"]
    assert job.params_json["inputs_sha256"] == provenance["inputs_sha256"]
    assert job.params_json["named_api_version"] == "novaq-shared-named-api-v1"
    assert set(job.result_json) == {"replications", "summary", "provenance"}
    assert run["result"] == job.result_json
    text = json.dumps(job.result_json)
    for forbidden in ('"events"', '"customers": [', '"employee_timeline"', '"trace"'):
        assert forbidden not in text


@pytest.mark.parametrize("server_key", ["dataset_generation", "setup_hash", "inputs_sha256", "root_entropy",
                                        "engine_version", "named_api_version", "analysis_id", "scenario_id"])
def test_a_request_cannot_supply_a_server_key(client, db_engine, engine_spy, server_key):
    ids = _signed_in(client, db_engine)
    response = _create(client, ids["analysis_id"], {**_run(ids["dataset_id"]), server_key: "forged"})
    assert response.status_code == 422
    assert engine_spy == []
    assert _named_jobs(db_engine) == []


def _failing_requests(client, ids, monkeypatch, app):
    a, d = ids["analysis_id"], ids["dataset_id"]
    yield "schema", _create(client, a, {**_run(d), "seed": "x"})
    yield "limit", _create(client, a, _run(d, replications=shared_named.N_MAX + 1))
    yield "dataset", _create(client, a, _run(999_999))
    yield "domain", _create(client, a, _run(d, closing_policy="drain"))
    monkeypatch.setattr(app.state.settings, "result_jsonb_max_bytes", 1024)
    yield "size", _create(client, a, _run(d))
    monkeypatch.undo()
    monkeypatch.setattr(shared_named, "run_named_replications", lambda *args, **kwargs: {"bad": float("nan")})
    yield "serialize", _create(client, a, _run(d))


def test_no_job_is_left_after_any_refusal(client, db_engine, monkeypatch, app):
    ids = _signed_in(client, db_engine)
    statuses = {}
    for name, response in _failing_requests(client, ids, monkeypatch, app):
        statuses[name] = (response.status_code, response.json()["detail"])
        assert _named_jobs(db_engine) == [], name
    assert statuses["size"][0] == 413
    assert statuses["size"][1]["code"] == "evidence_too_large" and statuses["size"][1]["max_bytes"] == 1024
    assert statuses["serialize"] == (500, {"code": "result_not_serializable"})
    assert {name: status for name, (status, _) in statuses.items()} == {
        "schema": 422, "limit": 422, "dataset": 404, "domain": 422, "size": 413, "serialize": 500}


# ── 10. Evidence isolation ──────────────────────────────────────────────────


def test_named_runs_are_invisible_to_the_workflow_evidence_and_report(client, db_engine):
    ids = _signed_in(client, db_engine)
    a = ids["analysis_id"]
    urls = (f"/analyses/{a}/workflow", f"/reports/analyses/{a}/selected/preview")
    before = [(client.get(url).status_code, client.get(url).content) for url in urls]
    _created_run(client, ids)
    _created_run(client, ids, seed=8)
    after = [(client.get(url).status_code, client.get(url).content) for url in urls]
    assert after == before


# ── 11-12. Regeneration and the D6 guard ────────────────────────────────────


@pytest.mark.parametrize("policy", ["DRAIN", "HARD_CUTOFF"])
def test_selected_replication_matches_the_direct_domain_calls(client, db_engine, policy):
    ids = _signed_in(client, db_engine)
    run = _created_run(client, ids, replications=3, closing_policy=policy)
    stored = _stored_result(db_engine, run["id"])
    for index in (0, 2):
        response = client.get(f"/analyses/{ids['analysis_id']}/shared-named/runs/{run['id']}/replications/{index}")
        assert response.status_code == 200
        body = response.json()
        assert body["replication_index"] == index
        assert body["playback"] == _json(playback_from_named_replications(stored, index))
        provenance = stored["provenance"]
        inputs = rebuild_named_inputs(provenance["inputs"])
        regenerated = simulate_named_replication(
            inputs["horizon"], inputs["demand_periods"], inputs["employees"], inputs["rules"], inputs["roster"],
            seed_sequence=replication_seed_sequence(provenance["root_entropy"], index),
            closing_policy=provenance["closing_policy"], employee_policy=EmployeeDesPolicy(**provenance["employee_policy"]),
            required_staffing=inputs["required_staffing"], max_trace_events=0)
        assert body["attribution"] == _json(build_named_attribution(regenerated, inputs["employees"]))
        assert body["regeneration"]["runtime_matches_recorded"] is True
        assert body["regeneration"]["runtime_recorded"] == provenance["runtime"]
        assert body["regeneration"]["basis"] == body["playback"]["provenance"]["regeneration_basis"]
    assert _named_jobs(db_engine)[0].result_json == stored  # regeneration persisted nothing


def _drain_lowercase_with_matching_digest(result: dict) -> None:
    """Tamper the closing policy and recompute the digest, so the closing-policy check itself refuses."""
    provenance = result["provenance"]
    provenance["closing_policy"] = "drain"
    provenance["inputs_sha256"] = named_inputs_digest(
        provenance["inputs"], provenance["closing_policy"], provenance["employee_policy"])


@pytest.mark.parametrize(("check", "mutate"), [
    ("stored_row", lambda r: r["replications"][0]["customers"].update(arrivals=r["replications"][0]["customers"]["arrivals"] + 1)),
    ("regeneration_identity", lambda r: r["provenance"]["inputs"]["employees"][0]["pay"].update(regular_rate_per_hour=1.0)),
    ("regeneration_identity", lambda r: r["provenance"].update(inputs_sha256="0" * 64)),
    ("regeneration_identity", lambda r: r["provenance"].update(method_version="novaq-shared-named-replications-v1")),
    ("regeneration_identity", lambda r: r["provenance"].update(closing_policy="drain")),
    ("closing_policy", _drain_lowercase_with_matching_digest),
])
def test_a_tampered_run_is_refused_with_409(client, db_engine, check, mutate):
    ids = _signed_in(client, db_engine)
    run = _created_run(client, ids)
    _tamper(db_engine, run["id"], mutate)
    response = client.get(f"/analyses/{ids['analysis_id']}/shared-named/runs/{run['id']}/replications/0")
    assert response.status_code == 409
    body = response.json()
    assert "playback" not in body and "attribution" not in body
    assert body["detail"]["code"] == "regeneration_identity"
    assert body["detail"]["check"] == check
    assert body["detail"]["message"]


def test_the_attribution_row_guard_refuses_with_409(client, db_engine, monkeypatch):
    ids = _signed_in(client, db_engine)
    run = _created_run(client, ids)
    real = shared_named.named_replication_row
    monkeypatch.setattr(shared_named, "named_replication_row",
                        lambda result, index: {**real(result, index), "customer_conservation": False})
    response = client.get(f"/analyses/{ids['analysis_id']}/shared-named/runs/{run['id']}/replications/1")
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert (detail["code"], detail["check"], detail["fields"]) == (
        "regeneration_identity", "attribution_stored_row", ["customer_conservation"])
    assert "playback" not in response.json()


def test_other_playback_and_attribution_failures_are_server_errors(client, db_engine, monkeypatch):
    ids = _signed_in(client, db_engine)
    run = _created_run(client, ids)
    url = f"/analyses/{ids['analysis_id']}/shared-named/runs/{run['id']}/replications/0"

    def playback_fails(*args, **kwargs):
        raise NamedPlaybackError({"check": "fcfs", "message": "replay defect", "evidence": {"at": 1.5}})

    monkeypatch.setattr(shared_named, "playback_from_named_replications", playback_fails)
    response = client.get(url)
    assert response.status_code == 500
    assert response.json()["detail"] == {"code": "playback_check_failed", "check": "fcfs",
                                         "message": "replay defect", "evidence": {"at": 1.5}}
    monkeypatch.undo()

    def attribution_fails(*args, **kwargs):
        raise NamedAttributionError({"check": "reconciliation", "message": "defect", "evidence": {}})

    monkeypatch.setattr(shared_named, "build_named_attribution", attribution_fails)
    response = client.get(url)
    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "attribution_check_failed"
    assert "playback" not in response.json()


# ── 13-14. Cost stays backend-only; adapter imports ─────────────────────────


def _cost_keys(value: Any, found: list[tuple[str, Any]]) -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            if "cost" in key.lower():
                found.append((key, item))
            _cost_keys(item, found)
    elif isinstance(value, list):
        for item in value:
            _cost_keys(item, found)
    return found


def test_no_response_carries_a_cost(client, db_engine):
    """Only the domain's own monetary_cost disclaimer text may name cost; no cost value is exposed."""
    ids = _signed_in(client, db_engine)
    a = ids["analysis_id"]
    run = _created_run(client, ids)
    responses = [
        client.get(f"/analyses/{a}/shared-named/contract").json(),
        _validate(client, a, _light(ids["dataset_id"])).json(),
        {"evidence": run},
        client.get(f"/analyses/{a}/shared-named/runs").json(),
        client.get(f"/analyses/{a}/shared-named/runs/{run['id']}").json(),
        client.get(f"/analyses/{a}/shared-named/runs/{run['id']}/replications/0").json(),
    ]
    for response in responses:
        for key, value in _cost_keys(response, []):
            assert key == "monetary_cost" and isinstance(value, str), (key, value)


ALLOWED_DOMAIN_MODULES = {
    "backend.queueing_engine.services.shared_segments",
    "backend.queueing_engine.services.shared_workforce",
    "backend.queueing_engine.simulation.shared_continuous_des",
    "backend.queueing_engine.simulation.shared_named_des",
    "backend.queueing_engine.simulation.shared_named_replications",
    "backend.queueing_engine.simulation.shared_named_playback",
    "backend.queueing_engine.simulation.shared_named_attribution",
}
FORBIDDEN_MODULES = {"shared_named_cost", "shared_day_cost", "shared_rostering", "shared_integrated",
                     "shared_capacity", "shared_replications", "shared_playback"}


def test_the_adapter_imports_only_the_pinned_domain_modules():
    source = (REPO_ROOT / "backend" / "api" / "shared_named.py").read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    domain = {name for name in imported if name.startswith("backend.queueing_engine")}
    assert domain == ALLOWED_DOMAIN_MODULES
    assert not {name.rsplit(".", 1)[-1] for name in imported} & FORBIDDEN_MODULES
    for name in FORBIDDEN_MODULES:
        assert name not in source


# ── 15. Round trips ─────────────────────────────────────────────────────────


def test_round_trip_persist_reload_regenerate(client, db_engine):
    ids = _signed_in(client, db_engine)
    run = _created_run(client, ids, replications=3)
    a = ids["analysis_id"]
    listed = client.get(f"/analyses/{a}/shared-named/runs").json()["runs"]
    assert [item["id"] for item in listed] == [run["id"]]
    assert listed[0]["setup_matches_current"] is True and listed[0]["inputs_sha256"] == run["params"]["inputs_sha256"]
    detail = client.get(f"/analyses/{a}/shared-named/runs/{run['id']}").json()
    assert detail == {"evidence": {**run, "created_at": detail["evidence"]["created_at"],
                                   "finished_at": detail["evidence"]["finished_at"]}, "setup_matches_current": True}
    for index in range(3):
        assert client.get(f"/analyses/{a}/shared-named/runs/{run['id']}/replications/{index}").status_code == 200


def test_runs_are_listed_newest_first_and_marked_when_the_setup_changed(client, db_engine):
    ids = _signed_in(client, db_engine)
    first = _created_run(client, ids, seed=1)
    second = _created_run(client, ids, seed=2)
    a = ids["analysis_id"]
    assert [item["id"] for item in client.get(f"/analyses/{a}/shared-named/runs").json()["runs"]] == [
        second["id"], first["id"]]
    with make_sessionmaker(db_engine)() as db:
        analysis = db.get(AnalysisProject, a)
        analysis.queue_setup_json = {**SHARED_SETUP, "fixed_server_count": 2}
        db.commit()
    listed = client.get(f"/analyses/{a}/shared-named/runs").json()["runs"]
    assert [item["setup_matches_current"] for item in listed] == [False, False]
    assert client.get(f"/analyses/{a}/shared-named/runs/{first['id']}").json()["setup_matches_current"] is False
    assert client.get(f"/analyses/{a}/shared-named/runs/{first['id']}/replications/0").status_code == 200


# ── 16. Dataset generation (OD-2) ───────────────────────────────────────────


def test_the_run_records_the_selected_datasets_generation(client, db_engine):
    ids = _signed_in(client, db_engine)
    with make_sessionmaker(db_engine)() as db:
        newer = _add_dataset(db, ids["user_id"], ids["analysis_id"], LIGHT_ROWS)
        db.commit()
        older_generation = db.get(Dataset, ids["dataset_id"]).generation
        newer_id, newer_generation = newer.id, newer.generation
    assert older_generation and newer_generation and older_generation != newer_generation
    older_run = _created_run(client, ids)  # explicitly the older dataset, not the current one
    newer_run = _create(client, ids["analysis_id"], _run(newer_id)).json()["evidence"]
    assert (older_run["params"]["dataset_id"], older_run["params"]["dataset_generation"]) == (
        ids["dataset_id"], older_generation)
    assert (newer_run["params"]["dataset_id"], newer_run["params"]["dataset_generation"]) == (
        newer_id, newer_generation)


# ── PostgreSQL: B1 (all five points) and the four payload round trips ───────


def _require_postgres(db_engine) -> None:
    assert db_engine.dialect.name == "postgresql", "NOVAQ_TEST_DATABASE_URL must select PostgreSQL"


@postgres_only
def test_postgres_b1_normal_run_commits_and_a_representation_change_rolls_back(client, db_engine):
    _require_postgres(db_engine)
    ids = _signed_in(client, db_engine)
    a = ids["analysis_id"]
    # 1. A normal run survives write, re-read, and verification, and commits.
    good = _created_run(client, ids, replications=3)
    assert [item["id"] for item in client.get(f"/analyses/{a}/shared-named/runs").json()["runs"]] == [good["id"]]
    before = _job_count(db_engine)
    # 2. A recorded float that PostgreSQL JSONB returns as an integer (1e16) is refused and rolled back.
    body = _run(ids["dataset_id"])
    body["employees"][0]["pay"]["regular_rate_per_hour"] = 1e16
    response = _create(client, a, body)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "persistence_identity_mismatch"
    assert "inputs_fingerprint" in [item["check"] for item in detail["checks"]]
    # 3. No successful Job remains.
    assert _job_count(db_engine) == before
    # 4. No run id is exposed: the body has no evidence, and R4 lists only the good run.
    assert set(response.json()) == {"detail"}
    assert [item["id"] for item in client.get(f"/analyses/{a}/shared-named/runs").json()["runs"]] == [good["id"]]
    # 5. Regeneration still fails closed independently on a run tampered after commit.
    _tamper(db_engine, good["id"], lambda r: r["replications"][1]["closing"].update(drain_crew_size=99))
    refused = client.get(f"/analyses/{a}/shared-named/runs/{good['id']}/replications/1")
    assert refused.status_code == 409
    assert (refused.json()["detail"]["code"], refused.json()["detail"]["check"]) == ("regeneration_identity",
                                                                                     "stored_row")
    assert client.get(f"/analyses/{a}/shared-named/runs/{good['id']}/replications/0").status_code == 200


@postgres_only
@pytest.mark.parametrize(("name", "scale", "structured", "policy"), [
    ("light", None, False, "DRAIN"),
    ("maximum_structure", 1.0, True, "HARD_CUTOFF"),
    ("busy", 5.0, True, "DRAIN"),
    ("stress", 10.0, True, "HARD_CUTOFF"),
])
def test_postgres_round_trip(client, db_engine, name, scale, structured, policy):
    _require_postgres(db_engine)
    rows = LIGHT_ROWS if scale is None else _scaled_rows(scale)
    ids = _signed_in(client, db_engine, rows=rows)
    a = ids["analysis_id"]
    body = _structured(ids["dataset_id"], closing_policy=policy) if structured else _light(
        ids["dataset_id"], closing_policy=policy)
    validated = _validate(client, a, body).json()
    assert validated["runnable"] is True, validated["problems"]
    replications = 3
    response = _create(client, a, {**body, "replications": replications, "seed": 20260930})
    assert response.status_code == 200, response.text
    run = response.json()["evidence"]
    stored = _stored_result(db_engine, run["id"])
    assert stored["provenance"]["inputs_sha256"] == named_inputs_digest(
        stored["provenance"]["inputs"], stored["provenance"]["closing_policy"], stored["provenance"]["employee_policy"])
    for index in (0, replications - 1):
        regenerated = client.get(f"/analyses/{a}/shared-named/runs/{run['id']}/replications/{index}")
        assert regenerated.status_code == 200, (name, index, regenerated.text[:500])
        assert regenerated.json()["playback"]["validation"]["valid"] is True
        assert regenerated.json()["regeneration"]["runtime_matches_recorded"] is True
