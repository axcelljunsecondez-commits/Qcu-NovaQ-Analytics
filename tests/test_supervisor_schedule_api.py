"""Isolated supervisor orchestration tests; no live data or service mutations."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest
from sqlalchemy import event, update

from backend.api import supervisor_schedule as api
from backend.api.scenarios import setup_fingerprint
from backend.db.models import AnalysisProject, Dataset
from tests.helpers import csrf_header, login, make_sessionmaker
from tests.test_break_apply_api import _stored_setup
from tests.test_break_optimize_api import _workspace

BASE = "/analyses/{}/workflow/optimize/separate/supervisor/{}"


def _post(client, aid, action, body):
    return client.post(BASE.format(aid, action), json=body, headers=csrf_header(client))


def _body(db_engine, aid, **over):
    with make_sessionmaker(db_engine)() as db:
        did = db.query(Dataset.id).filter(Dataset.analysis_id == aid).first()[0]
    return {"dataset_id": did, "target_utilization": .9, "allow_break_changes": True,
            "des": {"replications": 2, "base_seed": 42}, **over}


def test_preview_and_confirmed_apply_use_same_checked_schedule(db_engine, client):
    aid, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    body = _body(db_engine, aid)
    response = _post(client, aid, "preview", body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert _stored_setup(db_engine, aid) == setup
    assert result["can_apply"] is True, result["blockers"]
    assert result["breaks"]["des"]["seeds"] == [42, 43, 44, 45, 46]
    applied = _post(client, aid, "apply", {**body, "preview_hash": result["preview_hash"]})
    assert applied.status_code == 200, applied.text
    out = applied.json()
    assert out["schedule"] == result["schedule"]
    stored = _stored_setup(db_engine, aid)
    assert {k: v for k, v in stored.items() if k != "breaks"} == {k: v for k, v in setup.items() if k != "breaks"}
    for old, new, proposed in zip(setup["breaks"], stored["breaks"], result["breaks"]["proposed_breaks"], strict=True):
        assert new["queue_id"] == old["queue_id"]
        assert new["duration_minutes"] == old["duration_minutes"]
        assert new["scheduled_start_time"] == proposed["scheduled_start_time"]
    options = {"target_utilization": .9, "server_cost_per_hr": 87., "customer_waiting_cost": 100.,
               "min_active_lanes": 2, "max_active_lanes": None, "lambda_multiplier": 1.,
               "des": out["schedule"]["des"]}
    saved = client.post("/scenarios", headers=csrf_header(client), json={
        "name": "Checked synthetic breaks", "analysis_id": aid, "dataset_id": body["dataset_id"],
        "settings": {**options, "calculation": {
            "schema_version": 2, "engine_version": out["engine_version"], "analysis_id": aid,
            "dataset_id": body["dataset_id"], "dataset_row_count": 10, "options": options,
            "calculated_at": "2026-10-23T00:00:00+00:00",
        }}, "results": {"schedule": out["schedule"]},
    })
    assert saved.status_code == 201, saved.text
    assert saved.json()["scenario"]["provenance"] == "verified_snapshot"
    # Applying changes invalidates the old token, including after replay.
    assert _post(client, aid, "apply", {**body, "preview_hash": result["preview_hash"]}).status_code == 409


def test_break_off_is_read_only_and_cannot_apply(db_engine, client):
    aid, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    body = _body(db_engine, aid, allow_break_changes=False, target_utilization=.725)
    result = _post(client, aid, "preview", body).json()
    assert result["schedule"]["target_utilization"] == .725
    assert result["breaks"] is None and not result["can_apply"]
    assert _post(client, aid, "apply", {**body, "preview_hash": result["preview_hash"]}).status_code == 409
    assert _stored_setup(db_engine, aid) == setup


@pytest.mark.parametrize("change", ["setup", "data", "new_planning", "settings"])
def test_stale_preview_never_writes(db_engine, client, change):
    aid, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    body = _body(db_engine, aid)
    result = _post(client, aid, "preview", body).json()
    with make_sessionmaker(db_engine)() as db:
        dataset = db.get(Dataset, body["dataset_id"])
        if change == "setup":
            db.get(AnalysisProject, aid).queue_setup_json = {**setup, "breaks": []}
        elif change == "data":
            dataset.normalized_json = list(dataset.normalized_json)[:-1]
        elif change == "new_planning":
            db.add(Dataset(user_id=dataset.user_id, analysis_id=aid, name="New", source_filename="new.csv", source_format="csv",
                           normalized_json=dataset.normalized_json, row_count=dataset.row_count,
                           validation_report_json={"ok": True}))
        db.commit()
    if change == "settings":
        body["target_utilization"] = .85
    before = _stored_setup(db_engine, aid)
    response = _post(client, aid, "apply", {**body, "preview_hash": result["preview_hash"]})
    assert response.status_code in (409, 422), response.text
    assert _stored_setup(db_engine, aid) == before


@pytest.mark.parametrize("blocker", ["staffing_check", "break_limit", "customer_accounting", "wait_unavailable", "wait_longer"])
def test_each_failed_check_blocks_apply(db_engine, client, monkeypatch, blocker):
    aid, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    original_breaks = api.optimize_separate_breaks
    original_schedule = api.optimize_separate_schedule

    def breaks(*args, **kwargs):
        result = original_breaks(*args, **kwargs)
        if blocker == "break_limit":
            result["all_below_target"] = False
        if blocker == "customer_accounting":
            result["des"]["proposed"]["summary"]["customer_conservation"] = False
        paired = result["des"]["comparison"]["paired_wait_change"]
        if blocker == "wait_unavailable":
            paired["ci_lower"] = None
        if blocker == "wait_longer":
            paired.update(ci_lower=1., ci_upper=2., verdict="longer")
        return result

    def schedule(*args, **kwargs):
        result = original_schedule(*args, **kwargs)
        if blocker == "staffing_check":
            result["overall"] = "INFEASIBLE"
        return result

    monkeypatch.setattr(api, "optimize_separate_breaks", breaks)
    monkeypatch.setattr(api, "optimize_separate_schedule", schedule)
    body = _body(db_engine, aid)
    result = _post(client, aid, "preview", body).json()
    assert blocker in result["blockers"] and not result["can_apply"]
    response = _post(client, aid, "apply", {**body, "preview_hash": result["preview_hash"]})
    assert response.status_code == 409
    assert _stored_setup(db_engine, aid) == setup


def test_guard_inputs_ownership_and_demand_basis(db_engine, client):
    aid, setup = _workspace(db_engine)
    body = _body(db_engine, aid)
    assert client.post(BASE.format(aid, "preview"), json=body).status_code in (401, 403)
    login(client, "brk@example.com", "pw")
    for over in ({"target_utilization": .91}, {"max_shift_minutes": 20},
                 {"lambda_multiplier": 2}, {"proposed_breaks": []}, {"dataset_id": 999999}):
        response = _post(client, aid, "preview", {**body, **over})
        assert response.status_code in (404, 422), response.text
    other, _ = _workspace(db_engine, email="other@example.com")
    assert _post(client, other, "preview", body).status_code == 404
    assert _stored_setup(db_engine, aid) == setup


def test_concurrent_setup_change_during_recheck_is_refused(db_engine, client, monkeypatch):
    aid, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    body = _body(db_engine, aid)
    result = _post(client, aid, "preview", body).json()
    original = api._check
    changed = deepcopy(setup)
    changed["breaks"] = []

    def check(*args, **kwargs):
        result = original(*args, **kwargs)
        with make_sessionmaker(db_engine)() as db:
            db.get(AnalysisProject, aid).queue_setup_json = changed
            db.commit()
        return result

    monkeypatch.setattr(api, "_check", check)
    response = _post(client, aid, "apply", {**body, "preview_hash": result["preview_hash"]})
    assert response.status_code == 409
    assert setup_fingerprint(_stored_setup(db_engine, aid)) == setup_fingerprint(changed)


def test_postgres_change_after_final_read_is_not_overwritten(db_engine, client):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("Requires native PostgreSQL concurrent transactions and JSONB")
    aid, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    body = _body(db_engine, aid)
    result = _post(client, aid, "preview", body).json()
    assert result["can_apply"] is True
    concurrent = {**setup, "breaks": []}
    intercepted = False

    def before_update(conn, cursor, statement, parameters, context, executemany):
        nonlocal intercepted
        if intercepted or not statement.lstrip().upper().startswith("UPDATE ANALYSIS_PROJECTS SET QUEUE_SETUP_JSON"):
            return
        intercepted = True
        # Another transaction commits after the endpoint's refresh, immediately before its UPDATE.
        with db_engine.begin() as other:
            other.execute(update(AnalysisProject).where(AnalysisProject.id == aid)
                          .values(queue_setup_json=concurrent))

    event.listen(db_engine, "before_cursor_execute", before_update)
    try:
        response = _post(client, aid, "apply", {**body, "preview_hash": result["preview_hash"]})
    finally:
        event.remove(db_engine, "before_cursor_execute", before_update)
    assert intercepted
    assert response.status_code == 409, response.text
    assert "concurrent update" in response.json()["detail"]
    assert _stored_setup(db_engine, aid) == concurrent


def test_postgres_simultaneous_applies_have_one_winner(db_engine, client):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("Requires native PostgreSQL row-lock rechecking and JSONB")
    aid, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    body = _body(db_engine, aid)
    result = _post(client, aid, "preview", body).json()
    assert result["can_apply"] is True
    headers = csrf_header(client)
    payload = {**body, "preview_hash": result["preview_hash"]}
    ready = Barrier(2, timeout=15)

    def before_update(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE ANALYSIS_PROJECTS SET QUEUE_SETUP_JSON"):
            ready.wait()

    event.listen(db_engine, "before_cursor_execute", before_update)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(client.post, BASE.format(aid, "apply"),
                                      headers=headers, json=payload) for _ in range(2)]
            responses = [future.result(timeout=30) for future in futures]
    finally:
        event.remove(db_engine, "before_cursor_execute", before_update)
    assert sorted(response.status_code for response in responses) == [200, 409], [r.text for r in responses]
    winner = next(response.json() for response in responses if response.status_code == 200)
    assert winner["schedule"] == result["schedule"]
    stored = _stored_setup(db_engine, aid)
    assert {k: v for k, v in stored.items() if k != "breaks"} == {k: v for k, v in setup.items() if k != "breaks"}
    assert [b["scheduled_start_time"] for b in stored["breaks"]] == [
        b["scheduled_start_time"] for b in result["breaks"]["proposed_breaks"]]


def test_apply_preserves_legacy_setup_fields_without_inserting_defaults(db_engine, client):
    aid, setup = _workspace(db_engine)
    for key in ("patience_rate_per_hour", "total_system_capacity"):
        setup.pop(key, None)
    with make_sessionmaker(db_engine)() as db:
        db.get(AnalysisProject, aid).queue_setup_json = setup
        db.commit()
    login(client, "brk@example.com", "pw")
    body = _body(db_engine, aid)
    result = _post(client, aid, "preview", body).json()
    response = _post(client, aid, "apply", {**body, "preview_hash": result["preview_hash"]})
    assert response.status_code == 200, response.text
    stored = _stored_setup(db_engine, aid)
    assert {k: v for k, v in stored.items() if k != "breaks"} == {k: v for k, v in setup.items() if k != "breaks"}


def test_confirmed_apply_invalidates_earlier_current_evidence(db_engine, client):
    from tests.test_break_apply_api import _add_job

    aid, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    body = _body(db_engine, aid)
    with make_sessionmaker(db_engine)() as db:
        user_id = db.get(AnalysisProject, aid).user_id
        _add_job(db, user_id, aid, "workflow_des_current", setup, dataset_id=body["dataset_id"])
        # A stored Decision/selection is needed for decision_stale to have work to do.
        # Match the established legacy break-apply fixture rather than inventing a new rule.
        _add_job(db, user_id, aid, "workflow_selection", setup, scenario_id=999)
        _add_job(db, user_id, aid, "workflow_decision", setup, scenario_id=999)
        db.commit()
    before = client.get(f"/analyses/{aid}/workflow").json()
    assert before["des_current"] is not None
    proposal = _post(client, aid, "preview", body).json()
    applied = _post(client, aid, "apply", {**body, "preview_hash": proposal["preview_hash"]})
    assert applied.status_code == 200, applied.text
    after = client.get(f"/analyses/{aid}/workflow").json()
    assert after["des_current"] is None
    assert after["decision_stale"] is True
