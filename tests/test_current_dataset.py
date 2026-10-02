"""Step 2 tests for backend/api/current_dataset.py, the one current-dataset rule.

Every test checks four read paths against a literal expectation fixed when the test data was
built (for example "the second upload"). The expectation is never recomputed from the rule.

- resolve_current_dataset;
- workflow._current_valid_dataset_id;
- workflow._current_dataset;
- GET /analyses/{id}/current.

Data is labelled on every test:

- SYNTHETIC: users, analyses and datasets made for the test. Valid datasets come through the
  real upload endpoints. No upload path stores an invalid validation report, so invalid rows are
  inserted directly.
- RECORDED: ids, owners, analysis links, creation times and validity copied from
  tests/fixtures/evidence_status_local_reference_2026-09-25.json, a read-only local export.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.api import workflow
from backend.api.current_dataset import CurrentDatasetStatus, resolve_current_dataset
from backend.db.models import AnalysisProject, Dataset, User
from tests.helpers import create_user, csrf_header, login

NO_DATASET_DETAIL = "This Analysis has no successfully processed dataset."
AGGREGATE = b"time,lambda,mu,c\n08:00-09:00,4,6,2\n"
SETUP = {
    "queue_structure": "shared_queue",
    "fixed_server_count": 2,
    "staffing_varies_by_period": False,
    "capacity_mode": "unlimited",
    "total_system_capacity": None,
    "abandonment_mode": "not_modeled",
    "patience_rate_per_hour": None,
    "segments": [],
    "queue_ids": [],
}


def sign_in(db_engine, client, email: str = "owner@example.com") -> int:
    user = create_user(db_engine, email, "pw")
    assert login(client, email, "pw") == 200
    return user.id


def create_analysis(client, name: str = "Branch A") -> int:
    response = client.post("/analyses", headers=csrf_header(client),
                           json={"name": name, "service_type": "checkout", "queue_setup": SETUP})
    assert response.status_code == 201, response.text
    return response.json()["analysis"]["id"]


def upload(client, analysis_id: int) -> int:
    response = client.post(f"/analyses/{analysis_id}/datasets", headers=csrf_header(client),
                           files={"file": ("input.csv", AGGREGATE, "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()["dataset"]["id"]


def insert_dataset(session_factory, *, owner_id: int, analysis_id: int | None, report: dict | None,
                   created_at: datetime | None = None, dataset_id: int | None = None) -> int:
    with session_factory() as db:
        dataset = Dataset(id=dataset_id, user_id=owner_id, analysis_id=analysis_id, name="synthetic",
                          source_filename="synthetic.csv", source_format="csv", row_count=0,
                          normalized_json=[], validation_report_json=report)
        if created_at is not None:
            dataset.created_at = created_at
        db.add(dataset)
        db.commit()
        return dataset.id


def read_paths(client, session_factory, owner_id: int, analysis_id: int) -> dict:
    """What every current-dataset path reports for this owner and Analysis."""
    with session_factory() as db:
        resolution = resolve_current_dataset(db, owner_id=owner_id, analysis_id=analysis_id)
        assert not (db.new or db.dirty or db.deleted)  # read-only
        user = db.get(User, owner_id)
        analysis = db.get(AnalysisProject, analysis_id)
        assert user is not None and analysis is not None
        workflow_id = workflow._current_valid_dataset_id(db, user, analysis)
        try:
            workflow_dataset: int | str = workflow._current_dataset(db, user, analysis).id
        except HTTPException as exc:
            assert exc.status_code == 404
            workflow_dataset = exc.detail
    response = client.get(f"/analyses/{analysis_id}/current")
    endpoint = response.json()["dataset"]["id"] if response.status_code == 200 else response.json()["detail"]
    if response.status_code != 200:
        assert response.status_code == 404
    return {"status": resolution.status, "resolver": resolution.dataset_id, "workflow_id": workflow_id,
            "workflow_dataset": workflow_dataset, "endpoint": endpoint}


def current(dataset_id: int) -> dict:
    return {"status": CurrentDatasetStatus.CURRENT, "resolver": dataset_id, "workflow_id": dataset_id,
            "workflow_dataset": dataset_id, "endpoint": dataset_id}


def none_current(status: CurrentDatasetStatus) -> dict:
    # Both "no dataset" and "no valid dataset" keep the existing single 404 message.
    return {"status": status, "resolver": None, "workflow_id": None,
            "workflow_dataset": NO_DATASET_DETAIL, "endpoint": NO_DATASET_DETAIL}


def test_1_one_valid_dataset(db_engine, client, session_factory):
    # SYNTHETIC
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    only = upload(client, analysis)
    assert read_paths(client, session_factory, owner, analysis) == current(only)


def test_2_multiple_valid_datasets_the_last_upload_is_current(db_engine, client, session_factory):
    # SYNTHETIC
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    first, second, third = upload(client, analysis), upload(client, analysis), upload(client, analysis)
    assert first < second < third
    assert read_paths(client, session_factory, owner, analysis) == current(third)


@pytest.mark.parametrize("report", [{"ok": False, "message": "rejected"}, {}, {"message": "no ok key"}])
def test_3_latest_invalid_dataset_is_skipped(db_engine, client, session_factory, report):
    # SYNTHETIC: the newest row's report is not ok, so the previous valid upload stays current.
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    valid = upload(client, analysis)
    newer = insert_dataset(session_factory, owner_id=owner, analysis_id=analysis, report=report)
    assert newer > valid
    assert read_paths(client, session_factory, owner, analysis) == current(valid)


def test_3_invalid_dataset_between_valid_ones_changes_nothing(db_engine, client, session_factory):
    # SYNTHETIC
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    upload(client, analysis)
    insert_dataset(session_factory, owner_id=owner, analysis_id=analysis, report={"ok": False})
    latest_valid = upload(client, analysis)
    assert read_paths(client, session_factory, owner, analysis) == current(latest_valid)


def test_4_no_datasets(db_engine, client, session_factory):
    # SYNTHETIC
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    assert read_paths(client, session_factory, owner, analysis) == none_current(CurrentDatasetStatus.NO_DATASET)


def test_4_only_invalid_datasets_is_distinguished_from_none(db_engine, client, session_factory):
    # SYNTHETIC: the resolver tells the two apart; existing responses stay identical.
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    insert_dataset(session_factory, owner_id=owner, analysis_id=analysis, report={"ok": False})
    insert_dataset(session_factory, owner_id=owner, analysis_id=analysis, report={})
    assert read_paths(client, session_factory, owner, analysis) == none_current(
        CurrentDatasetStatus.NO_VALID_DATASET)


def test_5_dataset_of_another_analysis_is_never_selected(db_engine, client, session_factory):
    # SYNTHETIC: the owner's other Analysis has the newest upload.
    owner = sign_in(db_engine, client)
    first, second = create_analysis(client, "A"), create_analysis(client, "B")
    own = upload(client, first)
    other = upload(client, second)
    assert other > own
    assert read_paths(client, session_factory, owner, first) == current(own)
    assert read_paths(client, session_factory, owner, second) == current(other)


def test_5_another_owners_row_on_the_same_analysis_is_never_selected(db_engine, client, session_factory):
    # SYNTHETIC: no endpoint writes such a row; inserted directly to show the owner filter.
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    own = upload(client, analysis)
    stranger = create_user(db_engine, "stranger@example.com", "pw").id
    foreign = insert_dataset(session_factory, owner_id=stranger, analysis_id=analysis, report={"ok": True})
    assert foreign > own
    assert read_paths(client, session_factory, owner, analysis) == current(own)


def test_6_deleted_dataset_is_never_selected(db_engine, client, session_factory):
    # SYNTHETIC: deletion through the real endpoint (a hard delete; there is no restore).
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    older, newer = upload(client, analysis), upload(client, analysis)
    assert client.delete(f"/datasets/{newer}", headers=csrf_header(client)).status_code == 200
    assert read_paths(client, session_factory, owner, analysis) == current(older)
    assert client.delete(f"/datasets/{older}", headers=csrf_header(client)).status_code == 200
    assert read_paths(client, session_factory, owner, analysis) == none_current(CurrentDatasetStatus.NO_DATASET)


def test_7_archived_analysis_keeps_its_current_dataset(db_engine, client, session_factory):
    # SYNTHETIC. Verified existing behavior: archiving blocks uploads (409) but no current-dataset
    # path checks archived_at, so the current dataset is unchanged.
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    dataset = upload(client, analysis)
    assert client.post(f"/analyses/{analysis}/archive", headers=csrf_header(client)).status_code == 200
    rejected = client.post(f"/analyses/{analysis}/datasets", headers=csrf_header(client),
                           files={"file": ("input.csv", AGGREGATE, "text/csv")})
    assert rejected.status_code == 409
    assert read_paths(client, session_factory, owner, analysis) == current(dataset)


def test_8_unassociated_legacy_dataset_belongs_to_no_analysis_until_associated(db_engine, client, session_factory):
    # SYNTHETIC legacy row (analysis_id NULL, as before Analysis workspaces).
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    legacy = insert_dataset(session_factory, owner_id=owner, analysis_id=None, report={"ok": True})
    assert read_paths(client, session_factory, owner, analysis) == none_current(CurrentDatasetStatus.NO_DATASET)
    # The existing association path: saving a Scenario on it creates a legacy Analysis for it.
    response = client.post("/scenarios", headers=csrf_header(client),
                           json={"name": "legacy", "dataset_id": legacy, "settings": {}, "results": {}})
    assert response.status_code == 201, response.text
    with session_factory() as db:
        associated = db.get(Dataset, legacy)
        assert associated is not None and associated.analysis_id is not None
        legacy_analysis = associated.analysis_id
    assert legacy_analysis != analysis
    assert read_paths(client, session_factory, owner, legacy_analysis) == current(legacy)
    assert read_paths(client, session_factory, owner, analysis) == none_current(CurrentDatasetStatus.NO_DATASET)


def test_8_legacy_upload_without_analysis_gets_its_own_analysis(db_engine, client, session_factory):
    # SYNTHETIC: POST /datasets without analysis_id creates a legacy Analysis for the upload.
    owner = sign_in(db_engine, client)
    response = client.post("/datasets", headers=csrf_header(client),
                           files={"file": ("segments.csv", b"time,lambda,mu,c\n08:00-09:00,30,12,3\n", "text/csv")})
    assert response.status_code == 201, response.text
    dataset = response.json()["dataset"]
    with session_factory() as db:
        created = db.get(AnalysisProject, dataset["analysis_id"])
        assert created is not None and created.setup_status == "legacy"
    assert read_paths(client, session_factory, owner, dataset["analysis_id"]) == current(dataset["id"])


def test_9_order_is_by_id_not_creation_time_and_is_repeatable(db_engine, client, session_factory):
    # SYNTHETIC: the higher id wins even when its created_at is earlier.
    owner = sign_in(db_engine, client)
    analysis = create_analysis(client)
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    lower = insert_dataset(session_factory, owner_id=owner, analysis_id=analysis, report={"ok": True},
                           created_at=base + timedelta(days=2))
    higher = insert_dataset(session_factory, owner_id=owner, analysis_id=analysis, report={"ok": True},
                            created_at=base)
    assert higher > lower
    first = read_paths(client, session_factory, owner, analysis)
    assert first == current(higher)
    assert all(read_paths(client, session_factory, owner, analysis) == first for _ in range(3))


def test_10_duplicated_rules_now_delegate_to_the_resolver():
    # The former duplicates call the one resolver; no other module repeats the query.
    import inspect

    from backend.api import analyses

    assert "resolve_current_dataset(" in inspect.getsource(analyses.current_analysis)
    assert "resolve_current_dataset(" in inspect.getsource(workflow._current_valid_dataset_id)
    assert "_current_valid_dataset_id(" in inspect.getsource(workflow._current_dataset)
    backend = Path(__file__).resolve().parents[1] / "backend"
    repeats = [path.relative_to(backend).as_posix() for path in backend.rglob("*.py")
               if path.name != "current_dataset.py"
               and 'get("ok")' in (text := path.read_text(encoding="utf-8")) and "Dataset.id.desc()" in text]
    assert repeats == []


FIXTURE = Path(__file__).parent / "fixtures" / "evidence_status_local_reference_2026-09-25.json"


def parse_time(text: str) -> datetime:
    # PostgreSQL trims trailing zeros in fractions; Python 3.10 needs 3 or 6 digits. Padding only.
    return datetime.fromisoformat(re.sub(r"\.(\d{1,6})", lambda m: "." + m.group(1).ljust(6, "0"), text))


def test_recorded_local_datasets_resolve_as_recorded(db_engine, client, session_factory):
    # RECORDED: dataset ids, owners, Analysis links, creation times and validity (all ok) of
    # the local export. Analyses 7 and 13 have no dataset left (17 and 23 were deleted).
    # Not recorded: user emails, names and normalized rows, which are placeholders here.
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for owner in sorted({item["user_id"] for item in data["analyses"]}):
        assert create_user(db_engine, f"recorded-owner-{owner}@example.com", "pw").id == owner
    with session_factory() as db:
        for item in data["analyses"]:
            db.add(AnalysisProject(id=item["id"], user_id=item["user_id"], name=f"recorded {item['id']}",
                                   queue_setup_json=item["queue_setup_json"]))
        db.commit()
    for item in data["datasets"]:
        assert item["validation_ok"] is True
        insert_dataset(session_factory, dataset_id=item["id"], owner_id=item["user_id"],
                       analysis_id=item["analysis_id"], report={"ok": True},
                       created_at=parse_time(item["created_at"].replace("Z", "+00:00")))
    owners = {item["id"]: item["user_id"] for item in data["analyses"]}
    expected = {2: 8, 21: 35, 7: None, 13: None}
    with session_factory() as db:
        resolved = {analysis_id: resolve_current_dataset(db, owner_id=owners[analysis_id],
                                                         analysis_id=analysis_id).dataset_id
                    for analysis_id in expected}
    assert resolved == expected
    assert not ({17, 23} & {item["id"] for item in data["datasets"]})
