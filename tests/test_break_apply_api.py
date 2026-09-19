"""Apply the break optimizer's proposal to the Analysis Setup (separate queues only).

The server re-runs placement on the current Setup and dataset; break times are
never accepted from the client.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.api.scenarios import setup_fingerprint
from backend.db.models import AnalysisProject, Dataset, Job
from tests.helpers import create_user, csrf_header, login, make_sessionmaker
from tests.test_break_optimize_api import SHARED_NOTE, _run, _setup, _workspace
from tests.test_setup_derivation import novamart_workbook
from tests.test_upload_setup_api import _analysis, _upload

STALE = "Setup changed since this proposal was made. Run the break optimizer again."
NOTHING = "Nothing to apply: no break moves."
DATA_STALE = "The data changed since this proposal was made. Run the break optimizer again."


def _apply(client, analysis_id, body):
    return client.post(f"/analyses/{analysis_id}/workflow/optimize/separate/breaks/apply",
                       headers=csrf_header(client), json=body)


def _from(proposal) -> dict:
    return {"target_rho": proposal["target_rho"], "max_shift_minutes": proposal["max_shift_minutes"],
            "setup_hash": proposal["setup_hash"], "dataset_id": proposal["dataset_id"]}


def _dataset_id(db_engine, analysis_id) -> int:
    with make_sessionmaker(db_engine)() as db:
        return db.query(Dataset.id).filter(Dataset.analysis_id == analysis_id).order_by(Dataset.id.desc()).first()[0]


def _stored_setup(db_engine, analysis_id) -> dict:
    with make_sessionmaker(db_engine)() as db:
        return db.get(AnalysisProject, analysis_id).queue_setup_json


def _named_setup() -> dict:
    # Out-of-queue-order list with names on some entries; a third, short break for "a".
    return _setup(breaks=[
        {"queue_id": "b", "scheduled_start_time": "10:00:00", "duration_minutes": 30, "break_name": "Coffee"},
        {"queue_id": "a", "scheduled_start_time": "11:30:00", "duration_minutes": 15},
        {"queue_id": "a", "scheduled_start_time": "10:00:00", "duration_minutes": 30, "break_name": "Rest"},
    ])


def test_break_optimize_returns_setup_hash(db_engine, client):
    analysis_id, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    body = _run(client, analysis_id, {"des": {"replications": 1}}).json()
    assert body["setup_hash"] == setup_fingerprint(setup)
    assert body["dataset_id"] == _dataset_id(db_engine, analysis_id)


def test_apply_writes_exactly_the_proposed_start_times(db_engine, client):
    analysis_id, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    proposal = _run(client, analysis_id, {"des": {"replications": 1}}).json()
    assert proposal["moves"]
    response = _apply(client, analysis_id, _from(proposal))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["moves_applied"] == len(proposal["moves"])
    stored = _stored_setup(db_engine, analysis_id)
    assert [b["scheduled_start_time"] for b in stored["breaks"]] == [
        b["scheduled_start_time"] for b in proposal["proposed_breaks"]]
    assert body["analysis"]["queue_setup"] == stored
    assert body["analysis"]["setup_status"] == "ready"


def test_apply_keeps_names_durations_and_order(db_engine, client):
    analysis_id, setup = _workspace(db_engine, setup=_named_setup())
    login(client, "brk@example.com", "pw")
    proposal = _run(client, analysis_id, {"des": {"replications": 1}}).json()
    assert proposal["moves"]
    assert _apply(client, analysis_id, _from(proposal)).status_code == 200
    stored = _stored_setup(db_engine, analysis_id)["breaks"]
    strip = [{k: v for k, v in b.items() if k != "scheduled_start_time"} for b in stored]
    assert strip == [{k: v for k, v in b.items() if k != "scheduled_start_time"} for b in setup["breaks"]]
    assert stored[0]["break_name"] == "Coffee" and "break_name" not in stored[1]
    assert [b["scheduled_start_time"] for b in stored] == [
        b["scheduled_start_time"] for b in proposal["proposed_breaks"]]


def test_apply_changes_nothing_else_in_setup(db_engine, client):
    analysis_id, setup = _workspace(db_engine, setup=_named_setup())
    login(client, "brk@example.com", "pw")
    proposal = _run(client, analysis_id, {"des": {"replications": 1}}).json()
    assert _apply(client, analysis_id, _from(proposal)).status_code == 200
    stored = _stored_setup(db_engine, analysis_id)
    assert {k: v for k, v in stored.items() if k != "breaks"} == {
        k: v for k, v in setup.items() if k != "breaks"}


def test_apply_rejects_stale_setup_hash_and_keeps_setup(db_engine, client):
    analysis_id, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    response = _apply(client, analysis_id, {"target_rho": 0.85, "max_shift_minutes": 120,
                                            "setup_hash": "0" * 64,
                                            "dataset_id": _dataset_id(db_engine, analysis_id)})
    assert response.status_code == 409
    assert response.json()["detail"] == STALE
    assert _stored_setup(db_engine, analysis_id) == setup


def test_apply_without_moves_is_409(db_engine, client):
    analysis_id, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    response = _apply(client, analysis_id, {"target_rho": 0.85, "max_shift_minutes": 0,
                                            "setup_hash": setup_fingerprint(setup),
                                            "dataset_id": _dataset_id(db_engine, analysis_id)})
    assert response.status_code == 409
    assert response.json()["detail"] == NOTHING
    assert _stored_setup(db_engine, analysis_id) == setup


def test_apply_rejects_shared_queue(db_engine, client):
    user = create_user(db_engine, "shared@example.com", "pw")
    setup = {"queue_structure": "shared_queue", "fixed_server_count": 2}
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(user_id=user.id, name="Shared", setup_status="ready", queue_setup_json=setup)
        db.add(analysis)
        db.commit()
        analysis_id = analysis.id
    login(client, "shared@example.com", "pw")
    response = _apply(client, analysis_id, {"target_rho": 0.85, "max_shift_minutes": 120,
                                            "setup_hash": setup_fingerprint(setup), "dataset_id": 1})
    assert response.status_code == 422
    assert response.json()["detail"] == SHARED_NOTE


def test_apply_reports_placement_failure_as_422(db_engine, client):
    analysis_id, setup = _workspace(db_engine)
    per_date = {**setup, "event_period_basis": "per_date"}
    with make_sessionmaker(db_engine)() as db:
        db.get(AnalysisProject, analysis_id).queue_setup_json = per_date
        db.commit()
    login(client, "brk@example.com", "pw")
    response = _apply(client, analysis_id, {"target_rho": 0.85, "max_shift_minutes": 120,
                                            "setup_hash": setup_fingerprint(per_date),
                                            "dataset_id": _dataset_id(db_engine, analysis_id)})
    assert response.status_code == 422
    assert response.json()["detail"] == "Break optimization requires the representative day basis."


def test_apply_request_bounds_and_auth(db_engine, client):
    assert client.post("/analyses/1/workflow/optimize/separate/breaks/apply",
                       json={}).status_code in (401, 403)
    analysis_id, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    good = {"target_rho": 0.85, "max_shift_minutes": 120, "setup_hash": setup_fingerprint(setup),
            "dataset_id": _dataset_id(db_engine, analysis_id)}
    for bad in ({"target_rho": 0}, {"max_shift_minutes": 20}, {"setup_hash": None},
                {"dataset_id": None}, {"proposed_breaks": []}):
        assert _apply(client, analysis_id, {**good, **bad}).status_code == 422, bad
    assert _stored_setup(db_engine, analysis_id) == setup


def _add_job(db, user_id, analysis_id, kind, setup, scenario_id=None):
    db.add(Job(user_id=user_id, kind=kind, status="completed", tenant_id=None,
               params_json={"analysis_id": analysis_id, "scenario_id": scenario_id,
                            "setup_hash": setup_fingerprint(setup)},
               result_json={}, finished_at=datetime.now(timezone.utc)))


def test_apply_makes_earlier_evidence_stale(db_engine, client):
    analysis_id, setup = _workspace(db_engine)
    with make_sessionmaker(db_engine)() as db:
        analysis = db.get(AnalysisProject, analysis_id)
        for kind in ("workflow_des_current", "workflow_mc_current", "workflow_validation_current"):
            _add_job(db, analysis.user_id, analysis_id, kind, setup)
        _add_job(db, analysis.user_id, analysis_id, "workflow_selection", setup, scenario_id=999)
        _add_job(db, analysis.user_id, analysis_id, "workflow_decision", setup, scenario_id=999)
        db.commit()
    login(client, "brk@example.com", "pw")
    before = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert before["des_current"] is not None and before["decision_stale"] is False
    proposal = _run(client, analysis_id, {"des": {"replications": 1}}).json()
    assert _apply(client, analysis_id, _from(proposal)).status_code == 200
    after = client.get(f"/analyses/{analysis_id}/workflow").json()
    for key in ("des_current", "mc_current", "validation_current", "decision"):
        assert after[key] is None, key
    assert after["decision_stale"] is True


def _novamart_apply_and_rerun(db_engine, client) -> tuple[dict, dict, dict]:
    create_user(db_engine, "nm@example.com", "pw")
    login(client, "nm@example.com", "pw")
    analysis_id = _analysis(client)["id"]
    assert _upload(client, analysis_id, novamart_workbook(), apply=True).status_code == 201
    body = {"des": {"replications": 1}}
    first = _run(client, analysis_id, body).json()
    assert first["status"] == "improved" and first["moves"], first.get("detail")
    applied = _apply(client, analysis_id, _from(first))
    assert applied.status_code == 200, applied.text
    return first, applied.json(), _run(client, analysis_id, body).json()


def test_novamart_apply_then_rerun_starts_from_the_earlier_after_peak(db_engine, client):
    first, applied, second = _novamart_apply_and_rerun(db_engine, client)
    assert applied["moves_applied"] == len(first["moves"])
    assert second["peak_rho"]["before"] == first["peak_rho"]["after"]
    assert second["peak_rho"]["after"] <= second["peak_rho"]["before"]


@pytest.mark.xfail(strict=True, reason=(
    "R12: placement is not idempotent — each run's ±max_shift window is measured from the current "
    "Setup, so repeated apply can move breaks beyond the original ±120 min (NovaMart: 2 applies, "
    "peak 0.6253→0.5507, cashier_5 lunch 12:00→15:00); fixed-point placement anchored to "
    "original times is a separate fix."))
def test_novamart_apply_then_rerun_reports_no_moves(db_engine, client):
    first, _, second = _novamart_apply_and_rerun(db_engine, client)
    assert second["moves"] == []
    assert second["peak_rho"]["after"] == first["peak_rho"]["after"]


def test_new_upload_between_optimize_and_apply_is_409(db_engine, client):
    create_user(db_engine, "nm2@example.com", "pw")
    login(client, "nm2@example.com", "pw")
    analysis_id = _analysis(client)["id"]
    assert _upload(client, analysis_id, novamart_workbook(), apply=True).status_code == 201
    proposal = _run(client, analysis_id, {"des": {"replications": 1}}).json()
    assert proposal["moves"]
    setup = _stored_setup(db_engine, analysis_id)
    assert _upload(client, analysis_id, novamart_workbook()).status_code == 201
    assert setup_fingerprint(_stored_setup(db_engine, analysis_id)) == proposal["setup_hash"]
    response = _apply(client, analysis_id, _from(proposal))
    assert response.status_code == 409
    assert response.json()["detail"] == DATA_STALE
    assert _stored_setup(db_engine, analysis_id) == setup
