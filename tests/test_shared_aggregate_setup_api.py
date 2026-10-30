"""Additive shared upload ownership, atomicity, revision and retry behavior."""
from __future__ import annotations

import copy
import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from backend.api import shared_aggregate_upload
from backend.api.analysis_schemas import QueueSetup
from backend.db.models import AnalysisProject, Dataset, Job, Scenario
from tests.helpers import clear_cookies, create_user, csrf_header, login, make_sessionmaker

CSV = (Path(__file__).parent / "fixtures" / "shared_aggregate_owner.csv").read_bytes()
ANSWERS = {"capacity_mode": "unlimited", "abandonment_mode": "not_modeled"}


@pytest.fixture
def workspace(db_engine, client):
    create_user(db_engine, "shared-upload@example.com", "pw")
    assert login(client, "shared-upload@example.com", "pw") == 200
    response = client.post("/analyses", json={"name": "Shared fixture", "queue_setup": {"queue_structure": "shared_queue"}},
                           headers=csrf_header(client))
    assert response.status_code == 201, response.text
    return response.json()["analysis"]


def preview(client, analysis_id, data=CSV, filename="owner.csv", **params):
    return client.post(f"/analyses/{analysis_id}/datasets/shared-aggregate/preview", params=params,
                       files={"file": (filename, data, "application/octet-stream")}, headers=csrf_header(client))


def metadata(body, *, choices=None, confirm=False):
    return {"file_digest": body["file_digest"], "setup_revision": body["setup_revision"],
            "confirm_replace": confirm, "choices": ANSWERS if choices is None else choices}


def apply(client, analysis_id, submitted, data=CSV, filename="owner.csv", **params):
    return client.post(f"/analyses/{analysis_id}/datasets/shared-aggregate/apply", params=params,
                       files={"file": (filename, data, "application/octet-stream")},
                       data={"metadata": json.dumps(submitted)}, headers=csrf_header(client))


def stored(db_engine, analysis_id):
    with make_sessionmaker(db_engine)() as db:
        row = db.get(AnalysisProject, analysis_id)
        return {"setup": copy.deepcopy(row.queue_setup_json), "setup_status": row.setup_status,
                "datasets": db.query(Dataset).filter_by(analysis_id=analysis_id).count(),
                "jobs": db.query(Job).count(), "scenarios": db.query(Scenario).count()}


def test_preview_is_read_only_and_reads_the_real_fixture(db_engine, client, workspace):
    before = stored(db_engine, workspace["id"])
    response = preview(client, workspace["id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "shared_aggregate"
    assert body["file_digest"] == hashlib.sha256(CSV).hexdigest()
    assert len(body["setup_revision"]) == 64
    assert body["facts"]["row_count"] == 13
    assert body["facts"]["start_time"] == "05:00" and body["facts"]["end_time"] == "18:00"
    assert [row["c"] for row in body["facts"]["rows"]] == [3, 5, 5, 5, 5, 5, 2, 3, 5, 5, 5, 5, 2]
    assert body["needs_confirmation"] is False
    assert stored(db_engine, workspace["id"]) == before


def test_apply_saves_one_atomic_setup_and_dataset_and_retry_is_idempotent(db_engine, client, workspace):
    body = preview(client, workspace["id"]).json()
    request = metadata(body)
    response = apply(client, workspace["id"], request)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["duplicate"] is False
    assert result["analysis"]["setup_status"] == "ready_for_aggregate"
    assert result["analysis"]["queue_setup"]["capacity_mode"] == "unlimited"
    assert result["analysis"]["queue_setup"]["fixed_server_count"] is None
    assert result["dataset"]["row_count"] == 13
    assert result["dataset"]["is_current"] is True
    assert result["dataset"]["purpose"] == "planning"
    again = apply(client, workspace["id"], request)
    assert again.status_code == 201, again.text
    assert again.json()["duplicate"] is True
    assert again.json()["dataset"]["id"] == result["dataset"]["id"]
    assert stored(db_engine, workspace["id"])["datasets"] == 1


def test_replacing_saved_fixed_count_requires_confirmation_and_cancel_writes_nothing(db_engine, client, workspace):
    setup = {**workspace["queue_setup"], "fixed_server_count": 3}
    client.patch(f"/analyses/{workspace['id']}", json={"queue_setup": setup}, headers=csrf_header(client))
    before = stored(db_engine, workspace["id"])
    body = preview(client, workspace["id"]).json()
    assert body["needs_confirmation"] is True
    assert apply(client, workspace["id"], metadata(body)).status_code == 409
    assert stored(db_engine, workspace["id"]) == before
    assert apply(client, workspace["id"], metadata(body, confirm=True)).status_code == 201


def test_replacing_current_planning_data_requires_confirmation_even_with_same_setup(db_engine, client, workspace):
    first = preview(client, workspace["id"]).json()
    assert apply(client, workspace["id"], metadata(first)).status_code == 201
    next_preview = preview(client, workspace["id"]).json()
    assert next_preview["diff"] == []
    assert next_preview["needs_confirmation"] is True
    before = stored(db_engine, workspace["id"])
    response = apply(client, workspace["id"], metadata(next_preview, choices={}))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "confirmation_required"
    assert stored(db_engine, workspace["id"]) == before
    assert apply(client, workspace["id"], metadata(next_preview, choices={}, confirm=True)).status_code == 201
    assert stored(db_engine, workspace["id"])["datasets"] == 2


def test_explicit_finite_and_modeled_choices_are_validated_and_persisted(client, workspace):
    data = b"time,lambda,mu,c\n05:00-06:00,2,4,2\n06:00-07:00,3,4,2\n"
    body = preview(client, workspace["id"], data=data).json()
    chosen = {"capacity_mode": "finite", "total_system_capacity": 10,
              "abandonment_mode": "modeled", "patience_rate_per_hour": 0.4}
    response = apply(client, workspace["id"], metadata(body, choices=chosen), data=data)
    assert response.status_code == 201, response.text
    setup = response.json()["analysis"]["queue_setup"]
    assert setup["fixed_server_count"] == 2 and setup["staffing_varies_by_period"] is False
    assert all(setup[key] == value for key, value in chosen.items())
    assert all(row["K"] == 10 and row["theta"] == 0.4 for row in response.json()["dataset"]["normalized"])


def test_plain_aggregate_xlsx_uses_same_read_and_apply_validation(client, workspace):
    workbook = io.BytesIO()
    pd.read_csv(io.BytesIO(CSV)).to_excel(workbook, index=False)
    data = workbook.getvalue()
    body = preview(client, workspace["id"], data=data, filename="owner.xlsx").json()
    assert body["mode"] == "shared_aggregate" and body["facts"]["row_count"] == 13
    response = apply(client, workspace["id"], metadata(body), data=data, filename="owner.xlsx")
    assert response.status_code == 201, response.text
    assert response.json()["dataset"]["source_format"] == "xlsx"


def test_workbook_with_additional_sheets_declines_without_ignoring_staffing_evidence(db_engine, client, workspace):
    workbook = io.BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.read_csv(io.BytesIO(CSV)).to_excel(writer, sheet_name="data", index=False)
        pd.DataFrame([{"queue_id": "synthetic_lane", "shift_start": "06:00", "shift_end": "12:00"}]).to_excel(
            writer, sheet_name="staff", index=False,
        )
    data = workbook.getvalue()
    before = stored(db_engine, workspace["id"])
    response = preview(client, workspace["id"], data=data, filename="supplemental.xlsx")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "declined"
    assert body["reasons"][0]["code"] == "multiple_sheets"
    assert body["derived_setup"] is None and body["facts"] is None
    refused = apply(client, workspace["id"], metadata(body), data=data, filename="supplemental.xlsx")
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "not_supported"
    assert stored(db_engine, workspace["id"]) == before


@pytest.mark.parametrize("choices,missing", [
    ({}, ["capacity_mode", "abandonment_mode"]),
    ({"capacity_mode": "finite", "abandonment_mode": "not_modeled"}, ["total_system_capacity"]),
    ({"capacity_mode": "unlimited", "abandonment_mode": "modeled"}, ["patience_rate_per_hour"]),
])
def test_missing_explicit_choices_or_numbers_never_save(db_engine, client, workspace, choices, missing):
    body = preview(client, workspace["id"]).json()
    before = stored(db_engine, workspace["id"])
    response = apply(client, workspace["id"], metadata(body, choices=choices))
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == {"code": "missing_choices", "fields": missing}
    assert stored(db_engine, workspace["id"]) == before


def test_explicit_not_sure_preserves_unknown_without_inventing_an_assumption(client, workspace):
    body = preview(client, workspace["id"]).json()
    response = apply(client, workspace["id"], metadata(body, choices={"capacity_mode": "unknown", "abandonment_mode": "unknown"}))
    assert response.status_code == 201, response.text
    setup = response.json()["analysis"]["queue_setup"]
    assert setup["capacity_mode"] == setup["abandonment_mode"] == "unknown"
    compatibility_response = client.post(f"/analyses/{workspace['id']}/continuous/compatibility", headers=csrf_header(client))
    assert compatibility_response.status_code == 200, compatibility_response.text
    compatibility = compatibility_response.json()
    assert compatibility["plans"]["current"]["compatible"] is False


def test_known_finite_capacity_and_patience_are_preserved_in_setup_and_stored_records(client, workspace):
    setup = {**workspace["queue_setup"], "capacity_mode": "finite", "total_system_capacity": 20,
             "abandonment_mode": "modeled", "patience_rate_per_hour": 0.5}
    client.patch(f"/analyses/{workspace['id']}", json={"queue_setup": setup}, headers=csrf_header(client))
    body = preview(client, workspace["id"]).json()
    assert body["unresolved"] == [] and body["conflicts"] == []
    refused = apply(client, workspace["id"], metadata(body, choices=ANSWERS))
    assert refused.status_code == 422
    response = apply(client, workspace["id"], metadata(body, choices={}))
    assert response.status_code == 201, response.text
    assert response.json()["analysis"]["queue_setup"]["total_system_capacity"] == 20
    assert all(row["K"] == 20 and row["theta"] == 0.5 for row in response.json()["dataset"]["normalized"])


@pytest.mark.parametrize("kind", ["file", "setup", "dataset"])
def test_stale_or_changed_inputs_never_save(db_engine, client, workspace, kind):
    body = preview(client, workspace["id"]).json()
    data = CSV
    if kind == "file":
        data += b"\n"
    elif kind == "setup":
        setup = {**workspace["queue_setup"], "fixed_server_count": 5}
        client.patch(f"/analyses/{workspace['id']}", json={"queue_setup": setup}, headers=csrf_header(client))
    else:
        client.post(f"/analyses/{workspace['id']}/datasets", files={"file": ("other.csv", CSV, "text/csv")},
                    headers=csrf_header(client))
    before = stored(db_engine, workspace["id"])
    response = apply(client, workspace["id"], metadata(body), data=data)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == ("file_changed" if kind == "file" else "setup_changed")
    assert stored(db_engine, workspace["id"]) == before


@pytest.mark.parametrize("kind", ["setup", "dataset"])
def test_retry_after_a_later_change_does_not_reactivate_history(db_engine, client, workspace, kind):
    body = preview(client, workspace["id"]).json()
    request = metadata(body)
    first = apply(client, workspace["id"], request).json()
    if kind == "setup":
        setup = {**first["analysis"]["queue_setup"], "counter_breaks": [{"scheduled_start_time": "10:00", "duration_minutes": 15}]}
        client.patch(f"/analyses/{workspace['id']}", json={"queue_setup": setup}, headers=csrf_header(client))
    else:
        client.post(f"/analyses/{workspace['id']}/datasets", files={"file": ("new.csv", CSV, "text/csv")},
                    headers=csrf_header(client))
    before = stored(db_engine, workspace["id"])
    assert apply(client, workspace["id"], request).status_code == 409
    assert stored(db_engine, workspace["id"]) == before


def test_break_conflicts_are_refused_without_erasing_the_saved_break(db_engine, client, workspace):
    setup = {**workspace["queue_setup"], "counter_breaks": [{"scheduled_start_time": "04:00", "duration_minutes": 20}]}
    client.patch(f"/analyses/{workspace['id']}", json={"queue_setup": setup}, headers=csrf_header(client))
    before = stored(db_engine, workspace["id"])
    body = preview(client, workspace["id"]).json()
    assert body["conflicts"][0]["code"] == "breaks_outside_hours"
    response = apply(client, workspace["id"], metadata(body))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "setup_conflict"
    assert stored(db_engine, workspace["id"]) == before


def test_review_only_and_legacy_upload_paths_are_not_repurposed(db_engine, client, workspace):
    before = stored(db_engine, workspace["id"])
    assert preview(client, workspace["id"], purpose="review").status_code == 422
    assert stored(db_engine, workspace["id"]) == before
    legacy = client.post(f"/analyses/{workspace['id']}/datasets/preview", files={"file": ("owner.csv", CSV)},
                         headers=csrf_header(client))
    assert legacy.json() == {"mode": "legacy"}
    review = client.post(f"/analyses/{workspace['id']}/datasets?purpose=review", files={"file": ("owner.csv", CSV)},
                         headers=csrf_header(client))
    assert review.status_code == 201
    assert review.json()["dataset"]["purpose"] == "review"
    assert stored(db_engine, workspace["id"])["setup"] == before["setup"]


def test_declined_gap_keeps_legacy_behavior_and_stores_no_partial_data(db_engine, client, workspace):
    data = b"time,lambda,mu,c\n05:00-06:00,2,4,2\n07:00-08:00,2,4,2\n"
    before = stored(db_engine, workspace["id"])
    body = preview(client, workspace["id"], data=data).json()
    assert body["mode"] == "declined" and body["derived_setup"] is None
    response = apply(client, workspace["id"], metadata(body), data=data)
    assert response.status_code == 422
    assert stored(db_engine, workspace["id"]) == before


def test_authentication_ownership_archive_and_csrf(db_engine, client, workspace):
    path = f"/analyses/{workspace['id']}/datasets/shared-aggregate/preview"
    response = client.post(path, files={"file": ("owner.csv", CSV)})
    assert response.status_code == 403
    client.post(f"/analyses/{workspace['id']}/archive", headers=csrf_header(client))
    assert preview(client, workspace["id"]).status_code == 409
    clear_cookies(client)
    create_user(db_engine, "other-shared@example.com", "pw")
    login(client, "other-shared@example.com", "pw")
    assert preview(client, workspace["id"]).status_code == 404
    clear_cookies(client)
    assert client.post(path, files={"file": ("owner.csv", CSV)}).status_code == 401


def test_upload_limits_and_rate_limit_still_apply(app, client, workspace):
    app.state.settings.max_upload_bytes = 20
    assert preview(client, workspace["id"]).status_code == 413
    app.state.settings.max_upload_bytes = 1024 * 1024
    app.state.settings.rate_limit_upload = 2
    assert preview(client, workspace["id"]).status_code == 200
    assert preview(client, workspace["id"]).status_code == 429


def test_insert_failure_rolls_back_both_dataset_and_setup(db_engine, client, workspace):
    body = preview(client, workspace["id"]).json()
    before = stored(db_engine, workspace["id"])

    def fail_insert(*args):
        raise RuntimeError("Synthetic dataset insert failure")

    event.listen(Dataset, "before_insert", fail_insert)
    try:
        response = apply(client, workspace["id"], metadata(body))
        assert response.status_code == 500
    finally:
        event.remove(Dataset, "before_insert", fail_insert)
    assert stored(db_engine, workspace["id"]) == before


@pytest.mark.parametrize("initial_microseconds", [0, 123456])
def test_concurrent_sqlite_requests_cannot_both_insert(app, db_engine, client, workspace, monkeypatch, initial_microseconds):
    if db_engine.dialect.name != "sqlite":
        pytest.skip("This forced interleaving tests SQLite's timestamp CAS; PostgreSQL uses a row lock.")
    if initial_microseconds:
        with make_sessionmaker(db_engine)() as db:
            db.get(AnalysisProject, workspace["id"]).updated_at = datetime(2026, 10, 29, 17, 0, 0, initial_microseconds)
            db.commit()
    body = preview(client, workspace["id"]).json()
    barrier = Barrier(2)
    original = shared_aggregate_upload._revision

    def same_revision(db, analysis):
        result = original(db, analysis)
        barrier.wait(timeout=15)
        return result

    monkeypatch.setattr(shared_aggregate_upload, "_revision", same_revision)
    cookies = dict(client.cookies)
    header = csrf_header(client)
    path = f"/analyses/{workspace['id']}/datasets/shared-aggregate/apply"
    request = metadata(body)

    def send(_):
        with TestClient(app, cookies=cookies) as separate_client:
            return separate_client.post(path, files={"file": ("owner.csv", CSV, "text/csv")},
                                        data={"metadata": json.dumps(request)}, headers=header).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(send, range(2)))
    assert statuses == [201, 409]
    assert stored(db_engine, workspace["id"])["datasets"] == 1
