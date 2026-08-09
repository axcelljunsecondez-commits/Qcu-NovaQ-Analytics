"""Admin user management coverage: role enforcement, lifecycle, session revocation."""

from __future__ import annotations

from sqlalchemy import select

from backend.db.models import SessionRecord
from tests.helpers import (
    SESSION_COOKIE,
    clear_cookies,
    create_user,
    csrf_header,
    login,
)


def admin_client(db_engine, client):
    """Login as admin and return the client."""
    create_user(db_engine, "root@example.com", "rootpw", role="admin")
    login(client, "root@example.com", "rootpw")
    return client


def test_analyst_cannot_create_users(db_engine, client):
    create_user(db_engine, "analyst@example.com", "apw")
    login(client, "analyst@example.com", "apw")
    response = client.post(
        "/admin/users",
        headers=csrf_header(client),
        json={"email": "new@example.com", "password": "pw", "role": "analyst"},
    )
    assert response.status_code == 403


def test_analyst_cannot_list_users(db_engine, client):
    create_user(db_engine, "analyst@example.com", "apw")
    login(client, "analyst@example.com", "apw")
    assert client.get("/admin/users").status_code == 403


def test_unauthenticated_create_user_401(client):
    response = client.post(
        "/admin/users",
        json={"email": "new@example.com", "password": "pw", "role": "analyst"},
    )
    assert response.status_code == 401


def test_admin_creates_user(db_engine, client):
    admin_client(db_engine, client)
    response = client.post(
        "/admin/users",
        headers=csrf_header(client),
        json={"email": "new@example.com", "password": "s3cret", "role": "analyst"},
    )
    assert response.status_code == 201
    body = response.json()["user"]
    assert body["email"] == "new@example.com"
    assert body["role"] == "analyst"
    assert body["active"] is True
    assert "password" not in response.text
    assert "password_hash" not in response.text


def test_created_user_can_login(db_engine, client):
    admin_client(db_engine, client)
    client.post(
        "/admin/users",
        headers=csrf_header(client),
        json={"email": "new@example.com", "password": "s3cret", "role": "analyst"},
    )
    clear_cookies(client)
    assert login(client, "new@example.com", "s3cret") == 200


def test_admin_can_create_admin(db_engine, client):
    admin_client(db_engine, client)
    response = client.post(
        "/admin/users",
        headers=csrf_header(client),
        json={"email": "second@example.com", "password": "s3cret", "role": "admin"},
    )
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "admin"


def test_duplicate_email_409(db_engine, client):
    admin_client(db_engine, client)
    create_user(db_engine, "taken@example.com", "pw")
    response = client.post(
        "/admin/users",
        headers=csrf_header(client),
        json={"email": "taken@example.com", "password": "pw2", "role": "analyst"},
    )
    assert response.status_code == 409


def test_invalid_role_422(db_engine, client):
    admin_client(db_engine, client)
    response = client.post(
        "/admin/users",
        headers=csrf_header(client),
        json={"email": "x@example.com", "password": "pw", "role": "superuser"},
    )
    assert response.status_code == 422


def test_admin_lists_users(db_engine, client):
    admin_client(db_engine, client)
    create_user(db_engine, "a@example.com", "pw")
    create_user(db_engine, "b@example.com", "pw")
    response = client.get("/admin/users")
    assert response.status_code == 200
    emails = {u["email"] for u in response.json()["users"]}
    assert {"root@example.com", "a@example.com", "b@example.com"} <= emails


def test_admin_gets_user(db_engine, client):
    admin_client(db_engine, client)
    target = create_user(db_engine, "target@example.com", "pw")
    response = client.get(f"/admin/users/{target.id}")
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "target@example.com"


def test_admin_gets_missing_user_404(db_engine, client):
    admin_client(db_engine, client)
    assert client.get("/admin/users/99999").status_code == 404


def test_admin_deactivates_user_revoking_sessions(db_engine, client, session_factory):
    admin_client(db_engine, client)
    target = create_user(db_engine, "victim@example.com", "vpw")

    clear_cookies(client)
    assert login(client, "victim@example.com", "vpw") == 200
    assert client.get("/auth/me").status_code == 200

    clear_cookies(client)
    assert login(client, "root@example.com", "rootpw") == 200
    response = client.patch(
        f"/admin/users/{target.id}",
        headers=csrf_header(client),
        json={"active": False},
    )
    assert response.status_code == 200
    assert response.json()["user"]["active"] is False

    with session_factory() as db:
        sessions = db.execute(
            select(SessionRecord).where(SessionRecord.user_id == target.id)
        ).scalars().all()
    assert all(s.revoked_at is not None for s in sessions)

    clear_cookies(client)
    assert login(client, "victim@example.com", "vpw") == 401


def test_admin_changes_role(db_engine, client):
    admin_client(db_engine, client)
    target = create_user(db_engine, "promo@example.com", "pw")
    response = client.patch(
        f"/admin/users/{target.id}",
        headers=csrf_header(client),
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"


def test_admin_patch_missing_user_404(db_engine, client):
    admin_client(db_engine, client)
    response = client.patch(
        "/admin/users/99999",
        headers=csrf_header(client),
        json={"active": False},
    )
    assert response.status_code == 404


def test_deactivated_user_cannot_login(db_engine, client):
    admin_client(db_engine, client)
    target = create_user(db_engine, "off@example.com", "pw")
    client.patch(
        f"/admin/users/{target.id}",
        headers=csrf_header(client),
        json={"active": False},
    )
    clear_cookies(client)
    assert login(client, "off@example.com", "pw") == 401


def test_csrf_required_for_admin_mutations(db_engine, client):
    admin_client(db_engine, client)
    response = client.post(
        "/admin/users",
        json={"email": "x@example.com", "password": "pw", "role": "analyst"},
    )
    assert response.status_code == 403


def test_session_cookie_still_present_after_helpers(db_engine, client):
    admin_client(db_engine, client)
    assert SESSION_COOKIE in client.cookies
