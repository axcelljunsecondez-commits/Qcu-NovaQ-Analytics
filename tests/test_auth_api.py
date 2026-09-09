"""API auth coverage: login, sessions, logout, CSRF, middleware."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.helpers import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    add_session_row,
    clear_cookies,
    create_user,
    csrf_header,
    login,
)


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_sets_cookies_and_me_works(db_engine, client):
    create_user(db_engine, "alice@example.com", "s3cret")
    assert login(client, "alice@example.com", "s3cret") == 200

    me = client.get("/auth/me")
    assert me.status_code == 200
    body = me.json()["user"]
    assert body["email"] == "alice@example.com"
    assert body["role"] == "analyst"
    assert body["active"] is True


def test_login_wrong_password_401(client):
    response = client.post("/auth/login", json={"email": "a@example.com", "password": "nope"})
    assert response.status_code == 401
    assert SESSION_COOKIE not in client.cookies


def test_login_unknown_email_401_same_message(client):
    missing = client.post("/auth/login", json={"email": "ghost@example.com", "password": "x"})
    wrong_pw = client.post("/auth/login", json={"email": "a@example.com", "password": "x"})
    assert missing.status_code == wrong_pw.status_code == 401
    assert missing.json()["detail"] == wrong_pw.json()["detail"]


def test_login_inactive_user_401(db_engine, client):
    create_user(db_engine, "off@example.com", "s3cret", active=False)
    assert login(client, "off@example.com", "s3cret") == 401
    assert SESSION_COOKIE not in client.cookies


def test_me_without_session_401(client):
    assert client.get("/auth/me").status_code == 401


def test_logout_revokes_session(db_engine, client):
    create_user(db_engine, "bob@example.com", "s3cret")
    login(client, "bob@example.com", "s3cret")
    assert client.get("/auth/me").status_code == 200

    response = client.post("/auth/logout", headers=csrf_header(client))
    assert response.status_code == 200
    assert client.get("/auth/me").status_code == 401


def test_expired_session_rejected(db_engine, client):
    user = create_user(db_engine, "carol@example.com", "s3cret")
    add_session_row(
        db_engine, user.id, "expired-token", expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    client.cookies.set(SESSION_COOKIE, "expired-token")
    assert client.get("/auth/me").status_code == 401


def test_revoked_session_rejected(db_engine, client):
    user = create_user(db_engine, "dave@example.com", "s3cret")
    add_session_row(
        db_engine,
        user.id,
        "revoked-token",
        revoked_at=datetime.now(timezone.utc),
    )
    client.cookies.set(SESSION_COOKIE, "revoked-token")
    assert client.get("/auth/me").status_code == 401


def test_csrf_missing_header_blocks_mutation(db_engine, client):
    create_user(db_engine, "erin@example.com", "s3cret")
    login(client, "erin@example.com", "s3cret")
    response = client.post("/auth/logout")
    assert response.status_code == 403


def test_csrf_mismatch_blocks_mutation(db_engine, client):
    create_user(db_engine, "frank@example.com", "s3cret")
    login(client, "frank@example.com", "s3cret")
    response = client.post("/auth/logout", headers={"X-CSRF-Token": "wrong-token"})
    assert response.status_code == 403


def test_csrf_not_required_without_session(client):
    response = client.post("/auth/login", json={"email": "x@example.com", "password": "y"})
    assert response.status_code == 401


def test_cookie_attributes(db_engine, client):
    create_user(db_engine, "grace@example.com", "s3cret")
    response = client.post(
        "/auth/login", json={"email": "grace@example.com", "password": "s3cret"}
    )
    set_cookies = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in set_cookies if c.startswith(f"{SESSION_COOKIE}="))
    assert "HttpOnly" in session_cookie
    assert "samesite=lax" in session_cookie.lower()
    assert "Secure" not in session_cookie


def test_secure_cookies_when_enabled(db_engine, client, app):
    from backend.api.settings import Settings

    create_user(db_engine, "grace@example.com", "s3cret")
    app.state.settings.secure_cookies = True
    response = client.post(
        "/auth/login", json={"email": "grace@example.com", "password": "s3cret"}
    )
    set_cookies = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in set_cookies if c.startswith(f"{SESSION_COOKIE}="))
    assert "Secure" in session_cookie


def test_request_id_echoed(client):
    response = client.get("/health", headers={"X-Request-ID": "req-123"})
    assert response.headers.get("X-Request-ID") == "req-123"


def test_request_id_generated_when_absent(client):
    response = client.get("/health")
    assert response.headers.get("X-Request-ID") is not None


def test_change_password_success(db_engine, client):
    create_user(db_engine, "pw@example.com", "oldpass")
    assert login(client, "pw@example.com", "oldpass") == 200

    response = client.post(
        "/account/password",
        headers=csrf_header(client),
        json={"current_password": "oldpass", "new_password": "newpass123"},
    )
    assert response.status_code == 200

    assert client.get("/auth/me").status_code == 200
    clear_cookies(client)
    assert login(client, "pw@example.com", "oldpass") == 401
    assert login(client, "pw@example.com", "newpass123") == 200


def test_change_password_wrong_current_401(db_engine, client):
    create_user(db_engine, "wrong@example.com", "realpass")
    assert login(client, "wrong@example.com", "realpass") == 200

    response = client.post(
        "/account/password",
        headers=csrf_header(client),
        json={"current_password": "nope", "new_password": "newpass123"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Current password is incorrect."

    clear_cookies(client)
    assert login(client, "wrong@example.com", "realpass") == 200


def test_change_password_revokes_other_sessions_but_not_current(db_engine, app, client):
    create_user(db_engine, "two@example.com", "pass1")
    assert login(client, "two@example.com", "pass1") == 200

    other = TestClient(app)
    assert login(other, "two@example.com", "pass1") == 200
    assert other.get("/auth/me").status_code == 200

    response = client.post(
        "/account/password",
        headers=csrf_header(client),
        json={"current_password": "pass1", "new_password": "password2"},
    )
    assert response.status_code == 200

    assert client.get("/auth/me").status_code == 200
    assert other.get("/auth/me").status_code == 401
