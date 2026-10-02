"""G8 client protocol fence at the API boundary."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.api import analysis as analysis_api
from backend.api import reports as reports_api
from backend.api import workflow as workflow_api
from backend.db.models import AuthChallenge, Job, SessionRecord
from tests.helpers import create_user, csrf_header

PROTOCOL = {"X-NovaQ-Client-Protocol": "2"}
REJECTION = {
    "code": "client_update_required",
    "detail": "NovaQ has been updated. Reload the application.",
    "request_id": "compat-test-1",
}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-NovaQ-Client-Protocol": "1"},
        {"X-NovaQ-Client-Protocol": "2, 2"},
        [
            ("X-NovaQ-Client-Protocol", "2"),
            ("x-novaq-client-protocol", "2"),
        ],
    ],
)
def test_missing_wrong_or_duplicate_protocol_is_rejected(app, headers):
    raw = TestClient(app)
    response = raw.get("/auth/config", headers=[*headers, ("X-Request-ID", "compat-test-1")] if isinstance(headers, list) else {**headers, "X-Request-ID": "compat-test-1"})

    assert response.status_code == 403
    assert response.json() == REJECTION
    assert response.headers["X-Request-ID"] == "compat-test-1"
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "x-novaq-client-protocol" in response.headers["Vary"].lower()


def test_exact_protocol_is_accepted_and_protected_responses_are_private(app):
    raw = TestClient(app)
    response = raw.get(
        "/auth/config",
        headers={"x-novaq-client-protocol": "2", "Origin": "http://localhost"},
    )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    vary = {part.strip().lower() for part in response.headers["Vary"].split(",")}
    assert {"origin", "x-novaq-client-protocol"} <= vary
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost"

    unknown = raw.get("/not-a-route", headers=PROTOCOL)
    assert unknown.status_code == 404
    assert unknown.headers["Cache-Control"] == "private, no-store"
    assert "x-novaq-client-protocol" in unknown.headers["Vary"].lower()


def test_only_exact_health_ready_options_and_logout_are_exempt(app):
    raw = TestClient(app)
    assert raw.get("/health").status_code == 200
    assert raw.get("/ready").status_code == 200
    assert raw.head("/health").status_code != 403
    assert raw.head("/ready").status_code != 403
    assert raw.options("/auth/login").status_code != 403
    assert raw.post("/auth/logout").status_code == 200

    for method, path in (
        ("POST", "/health"),
        ("GET", "/health/"),
        ("GET", "/auth/logout"),
        ("GET", "/docs"),
        ("GET", "/unknown"),
    ):
        response = raw.request(method, path)
        assert response.status_code == 403
        assert response.json()["code"] == "client_update_required"


def test_rejected_login_and_google_nonce_cannot_create_auth_records(app, db_engine, session_factory):
    create_user(db_engine, "compat@example.com", "password123")
    raw = TestClient(app)

    login = raw.post("/auth/login", json={"email": "compat@example.com", "password": "password123"})
    nonce = raw.post("/auth/google/nonce")
    assert login.status_code == nonce.status_code == 403
    assert "novaq_session" not in raw.cookies
    assert "novaq_google_nonce" not in raw.cookies
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(SessionRecord)) == 0
        assert db.scalar(select(func.count()).select_from(AuthChallenge)) == 0


def test_old_google_credential_submission_does_not_verify_or_consume_nonce(app, session_factory):
    app.state.settings.google_sign_in_enabled = True
    app.state.settings.google_client_id = "test-google-client"

    class ProbeVerifier:
        calls = 0

        def verify(self, credential, audience):
            self.calls += 1
            raise AssertionError("The rejected client must not reach Google verification.")

    verifier = ProbeVerifier()
    app.state.google_token_verifier = verifier
    raw = TestClient(app)
    assert raw.post("/auth/google/nonce", headers=PROTOCOL).status_code == 200

    response = raw.post("/auth/google", json={"credential": "credential-value-long"})
    assert response.status_code == 403
    assert response.json()["code"] == "client_update_required"
    assert verifier.calls == 0
    assert "novaq_session" not in raw.cookies
    with session_factory() as db:
        nonce = db.scalar(select(AuthChallenge).where(AuthChallenge.purpose == "google_nonce"))
        assert nonce is not None and nonce.consumed_at is None
        assert db.scalar(select(func.count()).select_from(SessionRecord)) == 0


def test_csrf_precedes_protocol_fence(app, db_engine):
    create_user(db_engine, "csrf-compat@example.com", "password123")
    raw = TestClient(app)
    assert raw.post(
        "/auth/login",
        headers=PROTOCOL,
        json={"email": "csrf-compat@example.com", "password": "password123"},
    ).status_code == 200

    csrf_failure = raw.post("/scenarios", json={})
    assert csrf_failure.status_code == 403
    assert csrf_failure.json() == {"detail": "CSRF token mismatch."}

    protocol_failure = raw.post("/scenarios", headers=csrf_header(raw), json={})
    assert protocol_failure.status_code == 403
    assert protocol_failure.json()["code"] == "client_update_required"


def test_rate_limit_precedes_protocol_fence(app):
    app.state.settings.rate_limit_auth = 1
    raw = TestClient(app)
    payload = {"email": "missing@example.com", "password": "wrong"}

    assert raw.post("/auth/login", json=payload).json()["code"] == "client_update_required"
    limited = raw.post("/auth/login", headers=PROTOCOL, json=payload)
    assert limited.status_code == 429
    assert limited.json()["code"] == "rate_limited"


def test_old_client_cannot_read_or_select_with_existing_session(app, db_engine, session_factory):
    create_user(db_engine, "old-client@example.com", "password123")
    raw = TestClient(app)
    assert raw.post(
        "/auth/login",
        headers=PROTOCOL,
        json={"email": "old-client@example.com", "password": "password123"},
    ).status_code == 200
    assert raw.get("/auth/me", headers=PROTOCOL).status_code == 200

    for path in (
        "/auth/me",
        "/analyses/1/current",
        "/scenarios?analysis_id=1",
        "/analyses/1/workflow",
        "/analyses/1/workflow/comparison/separate",
    ):
        response = raw.get(path)
        assert response.status_code == 403
        assert response.json()["code"] == "client_update_required"

    with session_factory() as db:
        jobs_before = db.scalar(select(func.count()).select_from(Job))
    selection = raw.post(
        "/analyses/1/workflow/selection",
        headers=csrf_header(raw),
        json={"scenario_id": 1},
    )
    assert selection.status_code == 403
    assert selection.json()["code"] == "client_update_required"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Job)) == jobs_before

    # A direct backend request has no Pages proxy to supply the required marker.
    direct = raw.get("/scenarios", headers={"Host": "api.example.test"})
    assert direct.status_code == 403
    assert direct.json()["code"] == "client_update_required"

    with session_factory() as db:
        sessions_before = db.scalar(select(func.count()).select_from(SessionRecord))
    relogin = raw.post(
        "/auth/login",
        headers=csrf_header(raw),
        json={"email": "old-client@example.com", "password": "password123"},
    )
    assert relogin.status_code == 403
    assert relogin.json()["code"] == "client_update_required"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(SessionRecord)) == sessions_before

    assert raw.post("/auth/logout", headers=csrf_header(raw)).status_code == 200
    assert raw.get("/auth/me", headers=PROTOCOL).status_code == 401


def test_old_workflow_read_and_write_never_reach_handler(app, db_engine, session_factory, monkeypatch):
    create_user(db_engine, "workflow-compat@example.com", "password123")
    raw = TestClient(app)
    assert raw.post(
        "/auth/login",
        headers=PROTOCOL,
        json={"email": "workflow-compat@example.com", "password": "password123"},
    ).status_code == 200

    reached_handler = []

    def unexpected_analysis(*args, **kwargs):
        reached_handler.append(True)
        raise AssertionError("The rejected client must not reach workflow handlers.")

    monkeypatch.setattr(workflow_api, "own_analysis", unexpected_analysis)
    with session_factory() as db:
        jobs_before = db.scalar(select(func.count()).select_from(Job))
    for method, path, body in (
        ("GET", "/analyses/1/workflow", None),
        ("POST", "/analyses/1/workflow/selection", {"scenario_id": 1}),
        ("POST", "/analyses/1/workflow/simulation/des/current", {}),
    ):
        response = raw.request(method, path, headers=csrf_header(raw), json=body)
        assert response.status_code == 403
        assert response.json()["code"] == "client_update_required"
    assert reached_handler == []
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Job)) == jobs_before


def test_stateless_compute_requires_protocol_even_without_session(app, monkeypatch):
    raw = TestClient(app)
    body = {"lambda": 1.0, "mu": 2.0}
    calls = []

    def unexpected_model(*args, **kwargs):
        calls.append(True)
        raise AssertionError("The rejected client must not reach the analytical model.")

    monkeypatch.setattr(analysis_api, "_run_model", unexpected_model)
    blocked = raw.post("/analysis/mm1", json=body)
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "client_update_required"
    assert raw.post("/analysis/mm1", headers=PROTOCOL, json=body).status_code == 401
    assert calls == []


def test_old_client_report_request_never_reaches_generator(app, db_engine, monkeypatch):
    create_user(db_engine, "report-compat@example.com", "password123")
    raw = TestClient(app)
    assert raw.post(
        "/auth/login",
        headers=PROTOCOL,
        json={"email": "report-compat@example.com", "password": "password123"},
    ).status_code == 200
    calls = []

    def unexpected(*args, **kwargs):
        calls.append(True)
        raise AssertionError("The rejected client must not reach report generation.")

    monkeypatch.setattr(reports_api, "_own_scenario", unexpected)
    monkeypatch.setattr(reports_api, "generate_pdf_report", unexpected)
    response = raw.get("/reports/scenarios/1/pdf")
    assert response.status_code == 403
    assert response.json()["code"] == "client_update_required"
    assert calls == []
