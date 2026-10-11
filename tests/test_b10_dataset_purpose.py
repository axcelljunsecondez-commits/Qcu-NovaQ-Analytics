"""B10: planning file vs review-only file (spec docs/superpowers/specs/2026-10-09-b10-planning-vs-review-file.md).

The current dataset is the highest-id valid dataset uploaded FOR PLANNING. A review-only file is never
current, so it never changes evidence currentness. Every dataset that existed before B10 is planning.

Data: SYNTHETIC (users, analyses and uploads made for the test).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from backend.api import workflow
from backend.api.current_dataset import CurrentDatasetStatus, resolve_current_dataset
from backend.db.models import AnalysisProject, Dataset, User
from tests.helpers import create_user, csrf_header, login
from tests.test_current_dataset import NO_DATASET_DETAIL, SETUP, insert_dataset

AGGREGATE = b"time,lambda,mu,c\n08:00-09:00,4,6,2\n"
SEPARATE_SETUP = {**SETUP, "queue_structure": "separate_queues", "fixed_server_count": None, "queue_ids": ["A", "B"]}


def sign_in(db_engine, client, email: str = "owner@example.com") -> int:
    user = create_user(db_engine, email, "pw")
    assert login(client, email, "pw") == 200
    return user.id


def create_analysis(client, setup: dict = SETUP) -> int:
    response = client.post("/analyses", headers=csrf_header(client), json={"name": "Branch", "queue_setup": setup})
    assert response.status_code == 201, response.text
    return response.json()["analysis"]["id"]


def upload(client, analysis_id: int, purpose: str | None = None, **params):
    query = {} if purpose is None else {"purpose": purpose}
    query.update(params)
    return client.post(f"/analyses/{analysis_id}/datasets", headers=csrf_header(client), params=query,
                       files={"file": ("input.csv", AGGREGATE, "text/csv")})


def uploaded(client, analysis_id: int, purpose: str | None = None) -> int:
    response = upload(client, analysis_id, purpose)
    assert response.status_code == 201, response.text
    return response.json()["dataset"]["id"]


def current_id(session_factory, owner: int, analysis: int) -> int | None:
    with session_factory() as db:
        return resolve_current_dataset(db, owner_id=owner, analysis_id=analysis).dataset_id


def stored_purpose(session_factory, dataset_id: int) -> str:
    with session_factory() as db:
        return db.execute(select(Dataset.purpose).where(Dataset.id == dataset_id)).scalar_one()


# --- the rule ------------------------------------------------------------------------------------


def test_omitted_purpose_stores_planning_and_becomes_current(db_engine, client, session_factory):
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    first = uploaded(client, analysis)
    assert stored_purpose(session_factory, first) == "planning"
    assert current_id(session_factory, owner, analysis) == first


def test_a_newer_review_file_does_not_replace_the_planning_file(db_engine, client, session_factory):
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    planning = uploaded(client, analysis, "planning")
    review = uploaded(client, analysis, "review")
    assert review > planning
    assert stored_purpose(session_factory, review) == "review"
    assert current_id(session_factory, owner, analysis) == planning
    with session_factory() as db:
        user, project = db.get(User, owner), db.get(AnalysisProject, analysis)
        assert workflow._current_valid_dataset_id(db, user, project) == planning
        assert workflow._current_dataset(db, user, project).id == planning
    assert client.get(f"/analyses/{analysis}/current").json()["dataset"]["id"] == planning


def test_a_newer_planning_file_still_replaces_it(db_engine, client, session_factory):
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    uploaded(client, analysis, "planning")
    uploaded(client, analysis, "review")
    newest = uploaded(client, analysis, "planning")
    assert current_id(session_factory, owner, analysis) == newest


def test_only_review_files_means_no_planning_dataset(db_engine, client, session_factory):
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    uploaded(client, analysis, "review")
    with session_factory() as db:
        resolution = resolve_current_dataset(db, owner_id=owner, analysis_id=analysis)
    assert resolution.status == CurrentDatasetStatus.NO_PLANNING_DATASET
    assert resolution.dataset is None
    response = client.get(f"/analyses/{analysis}/current")
    assert response.status_code == 404
    assert response.json()["detail"] == NO_DATASET_DETAIL


def test_invalid_planning_rows_still_report_no_valid_dataset(db_engine, client, session_factory):
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    insert_dataset(session_factory, owner_id=owner, analysis_id=analysis, report={"ok": False})
    with session_factory() as db:
        resolution = resolve_current_dataset(db, owner_id=owner, analysis_id=analysis)
    assert resolution.status == CurrentDatasetStatus.NO_VALID_DATASET


def test_deleting_the_planning_file_falls_back_to_planning_never_to_review(db_engine, client, session_factory):
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    older = uploaded(client, analysis, "planning")
    newer = uploaded(client, analysis, "planning")
    uploaded(client, analysis, "review")
    assert client.delete(f"/datasets/{newer}", headers=csrf_header(client)).status_code in (200, 204)
    assert current_id(session_factory, owner, analysis) == older
    assert client.delete(f"/datasets/{older}", headers=csrf_header(client)).status_code in (200, 204)
    assert current_id(session_factory, owner, analysis) is None


# --- upload API ----------------------------------------------------------------------------------


def test_unknown_purpose_is_rejected_and_nothing_is_stored(db_engine, client, session_factory):
    sign_in(db_engine, client)
    analysis = create_analysis(client)
    response = upload(client, analysis, "later")
    assert response.status_code == 422
    with session_factory() as db:
        assert db.execute(select(Dataset)).scalars().all() == []


def test_a_review_file_can_never_change_the_setup(db_engine, client, session_factory):
    sign_in(db_engine, client)
    analysis = create_analysis(client)
    before = client.get(f"/analyses/{analysis}").json()["analysis"]["queue_setup"]
    response = upload(client, analysis, "review", apply_setup="true")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "review_cannot_change_setup"
    with session_factory() as db:
        assert db.execute(select(Dataset)).scalars().all() == []
    assert client.get(f"/analyses/{analysis}").json()["analysis"]["queue_setup"] == before


def test_dataset_responses_report_purpose_and_which_file_is_current(db_engine, client, session_factory):
    sign_in(db_engine, client)
    analysis = create_analysis(client)
    first = upload(client, analysis, "planning").json()["dataset"]
    assert (first["purpose"], first["is_current"]) == ("planning", True)
    review = upload(client, analysis, "review").json()["dataset"]
    assert (review["purpose"], review["is_current"]) == ("review", False)
    second = upload(client, analysis, "planning").json()["dataset"]
    assert second["is_current"] is True
    listed = {item["id"]: (item["purpose"], item["is_current"])
              for item in client.get(f"/analyses/{analysis}/datasets").json()["datasets"]}
    assert listed == {first["id"]: ("planning", False), review["id"]: ("review", False),
                      second["id"]: ("planning", True)}


# --- evidence currentness -----------------------------------------------------------------------


def test_a_review_upload_keeps_saved_plans_current_and_a_planning_upload_does_not(db_engine, client, session_factory):
    sign_in(db_engine, client)
    analysis = create_analysis(client)
    planning = uploaded(client, analysis, "planning")
    with session_factory() as db:
        dataset = db.get(Dataset, planning)
        assert dataset is not None
    context_before = _evidence_context(session_factory, analysis)
    uploaded(client, analysis, "review")
    assert _evidence_context(session_factory, analysis).current_dataset_id == context_before.current_dataset_id == planning
    newer = uploaded(client, analysis, "planning")
    assert _evidence_context(session_factory, analysis).current_dataset_id == newer


def _evidence_context(session_factory, analysis_id: int):
    with session_factory() as db:
        project = db.get(AnalysisProject, analysis_id)
        assert project is not None
        user = db.get(User, project.user_id)
        return workflow._evidence_context(db, user, project)


# --- planning screens refuse review files (OD-B10-3) ---------------------------------------------


@pytest.mark.parametrize("path", ["optimize/separate", "optimize/separate/breaks"])
def test_separate_optimizers_refuse_a_review_file(db_engine, client, path):
    sign_in(db_engine, client)
    analysis = create_analysis(client, SEPARATE_SETUP)
    review = _insert_review(client, analysis)
    response = client.post(f"/analyses/{analysis}/workflow/{path}", headers=csrf_header(client),
                           json={"dataset_id": review})
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "dataset_not_for_planning"


def test_the_named_shared_run_refuses_a_review_file(db_engine, client, session_factory):
    from fastapi import HTTPException

    from backend.api.shared_named import _selected_dataset

    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    review = uploaded(client, analysis, "review")
    with session_factory() as db:
        user, project = db.get(User, owner), db.get(AnalysisProject, analysis)
        with pytest.raises(HTTPException) as refused:
            _selected_dataset(db, user, project, review)
    assert refused.value.status_code == 422
    assert refused.value.detail == {"code": "dataset_not_for_planning"}


def _insert_review(client, analysis_id: int) -> int:
    # The separate endpoints read the stored rows; a review file is refused before any row is read.
    from backend.db.session import get_db  # noqa: F401  (kept: the app owns the session)
    response = client.post(f"/analyses/{analysis_id}/datasets", headers=csrf_header(client),
                           params={"purpose": "review"},
                           files={"file": ("lanes.csv", b"time,queue_id,lambda,mu,c,variance\n08:00-09:00,A,4,6,1,0.01\n08:00-09:00,B,4,6,1,0.01\n", "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()["dataset"]["id"]
