"""Datasets API coverage: upload, retrieval, deletion, isolation, size limits."""

from __future__ import annotations

import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.api.main import create_app
from backend.api.settings import Settings
from backend.db.models import Scenario
from tests.helpers import clear_cookies, create_user, csrf_header, login

CSV_GOOD = b"time,lambda,mu,c\n08:00-09:00,30,12,3\n09:00-10:00,45,12,4\n"
CSV_INJECTION = b"time,lambda,mu,c\n=HYPERLINK(\"http://x\"),30,12,3\n09:00-10:00,45,12,4\n"
CSV_MISSING_COLUMN = b"time,lambda\n08:00-09:00,30\n"
CSV_INVALID_NUMERIC = b"time,lambda,mu,c\n08:00-09:00,abc,12,3\n"


def make_xlsx_bytes() -> bytes:
    buffer = io.BytesIO()
    pd.DataFrame(
        {"time": ["08:00-09:00"], "lambda": [30.0], "mu": [12.0], "c": [3]}
    ).to_excel(buffer, index=False)
    return buffer.getvalue()


@pytest.fixture
def small_limit_app(db_engine, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1024")
    return create_app(engine=db_engine, settings=Settings())


@pytest.fixture
def small_limit_client(small_limit_app):
    return TestClient(small_limit_app)


def upload(client: TestClient, filename: str, data: bytes, headers: dict | None = None):
    return client.post(
        "/datasets",
        headers=headers,
        files={"file": (filename, data, "application/octet-stream")},
    )


def test_upload_csv_succeeds(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = upload(client, "segments.csv", CSV_GOOD, csrf_header(client))
    assert response.status_code == 201
    dataset = response.json()["dataset"]
    assert dataset["row_count"] == 2
    assert dataset["source_format"] == "csv"
    assert dataset["validation"]["ok"] is True


def test_upload_xlsx_succeeds(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = upload(client, "segments.xlsx", make_xlsx_bytes(), csrf_header(client))
    assert response.status_code == 201
    assert response.json()["dataset"]["source_format"] == "xlsx"


def test_upload_requires_auth(client):
    assert upload(client, "segments.csv", CSV_GOOD).status_code == 401


def test_upload_rejects_bad_extension(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = upload(client, "segments.txt", b"hello", csrf_header(client))
    assert response.status_code == 422


def test_upload_rejects_oversize(db_engine, small_limit_client, monkeypatch):
    create_user(db_engine, "u@example.com", "pw")
    login(small_limit_client, "u@example.com", "pw")
    big = b"x" * 2048
    response = upload(small_limit_client, "segments.csv", big, csrf_header(small_limit_client))
    assert response.status_code == 413


def test_upload_rejects_missing_columns(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = upload(client, "segments.csv", CSV_MISSING_COLUMN, csrf_header(client))
    assert response.status_code == 422


def test_upload_rejects_invalid_numeric(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = upload(client, "segments.csv", CSV_INVALID_NUMERIC, csrf_header(client))
    assert response.status_code == 422


def test_upload_sanitizes_formula_injection(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = upload(client, "segments.csv", CSV_INJECTION, csrf_header(client))
    assert response.status_code == 201
    dataset_id = response.json()["dataset"]["id"]
    detail = client.get(f"/datasets/{dataset_id}")
    stored = detail.json()["dataset"]["normalized"]
    assert stored[0]["time"] == "'=HYPERLINK(\"http://x\")"


def test_upload_sanitizes_filename(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = upload(client, "..\\..\\evil.csv", CSV_GOOD, csrf_header(client))
    assert response.status_code == 201
    assert response.json()["dataset"]["source_filename"] == "evil.csv"


def test_upload_sanitizes_filename_control_chars(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    response = upload(client, "..\\..\\evil\n\t\x00.csv", CSV_GOOD, csrf_header(client))
    assert response.status_code == 201
    assert response.json()["dataset"]["source_filename"] == "evil .csv"


def test_list_datasets_own_only(db_engine, client):
    create_user(db_engine, "alice@example.com", "pw")
    login(client, "alice@example.com", "pw")
    upload(client, "segments.csv", CSV_GOOD, csrf_header(client))

    clear_cookies(client)
    create_user(db_engine, "bob@example.com", "pw")
    login(client, "bob@example.com", "pw")
    listing = client.get("/datasets")
    assert listing.status_code == 200
    assert listing.json()["datasets"] == []


def test_get_dataset_returns_normalized_rows(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    dataset_id = upload(client, "segments.csv", CSV_GOOD, csrf_header(client)).json()["dataset"]["id"]
    detail = client.get(f"/datasets/{dataset_id}")
    assert detail.status_code == 200
    assert len(detail.json()["dataset"]["normalized"]) == 2


def test_cross_user_get_is_404(db_engine, client):
    create_user(db_engine, "alice@example.com", "pw")
    login(client, "alice@example.com", "pw")
    dataset_id = upload(client, "segments.csv", CSV_GOOD, csrf_header(client)).json()["dataset"]["id"]

    clear_cookies(client)
    create_user(db_engine, "bob@example.com", "pw")
    login(client, "bob@example.com", "pw")
    assert client.get(f"/datasets/{dataset_id}").status_code == 404


def test_get_missing_dataset_404(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    assert client.get("/datasets/99999").status_code == 404


def test_delete_dataset_own(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    dataset_id = upload(client, "segments.csv", CSV_GOOD, csrf_header(client)).json()["dataset"]["id"]
    response = client.delete(f"/datasets/{dataset_id}", headers=csrf_header(client))
    assert response.status_code == 200
    assert client.get(f"/datasets/{dataset_id}").status_code == 404


def test_delete_dataset_cascades_scenarios(db_engine, client, session_factory):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    dataset_id = upload(client, "segments.csv", CSV_GOOD, csrf_header(client)).json()["dataset"]["id"]
    with session_factory() as db:
        db.add(
            Scenario(
                user_id=1,
                dataset_id=dataset_id,
                name="linked",
                settings_json={},
                results_json={},
            )
        )
        db.commit()
    client.delete(f"/datasets/{dataset_id}", headers=csrf_header(client))
    with session_factory() as db:
        remaining = db.execute(select(Scenario)).scalars().all()
    assert remaining == []


def test_cross_user_delete_is_404(db_engine, client):
    create_user(db_engine, "alice@example.com", "pw")
    login(client, "alice@example.com", "pw")
    dataset_id = upload(client, "segments.csv", CSV_GOOD, csrf_header(client)).json()["dataset"]["id"]
    clear_cookies(client)
    create_user(db_engine, "bob@example.com", "pw")
    login(client, "bob@example.com", "pw")
    response = client.delete(f"/datasets/{dataset_id}", headers=csrf_header(client))
    assert response.status_code == 404
    clear_cookies(client)
    login(client, "alice@example.com", "pw")
    assert client.get(f"/datasets/{dataset_id}").status_code == 200


def test_upload_requires_csrf(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    assert upload(client, "segments.csv", CSV_GOOD).status_code == 403
