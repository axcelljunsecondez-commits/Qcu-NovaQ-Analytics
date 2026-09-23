"""Registration, verification, recovery, and Google identity security tests."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from backend.api import auth
from backend.api.google_auth import InvalidGoogleCredential, OfficialGoogleTokenVerifier
from backend.db.models import AuthChallenge, AuthIdentity, SessionRecord, User
from tests.helpers import SESSION_COOKIE, clear_cookies, create_user, csrf_header, login


def _token(message) -> str:
    match = re.search(r"#token=([^\s]+)", message.text)
    assert match
    return match.group(1)


class FakeGoogleVerifier:
    def __init__(self) -> None:
        self.claims: dict = {}
        self.failure = False
        self.audience: str | None = None

    def verify(self, credential: str, audience: str) -> dict:
        self.audience = audience
        if self.failure:
            raise InvalidGoogleCredential("no")
        return dict(self.claims)


def _enable_google(app) -> FakeGoogleVerifier:
    verifier = FakeGoogleVerifier()
    app.state.settings.google_sign_in_enabled = True
    app.state.settings.google_client_id = "client.apps.googleusercontent.com"
    app.state.google_token_verifier = verifier
    return verifier


def _nonce(client, *, authenticated: bool = False) -> str:
    headers = csrf_header(client) if authenticated else {}
    response = client.post("/auth/google/nonce", headers=headers)
    assert response.status_code == 200
    return response.json()["nonce"]


def test_registration_is_unverified_analyst_without_session(db_engine, client, email_sender):
    response = client.post(
        "/auth/register", json={"email": "  New@Example.com ", "password": "password123"}
    )
    assert response.status_code == 200
    assert SESSION_COOKIE not in client.cookies
    with auth_session(db_engine) as db:
        user = db.execute(select(User).where(User.email_normalized == "new@example.com")).scalar_one()
        assert user.role == "analyst"
        assert user.email_verified_at is None
        challenge = db.execute(select(AuthChallenge)).scalar_one()
        assert challenge.token_hash != _token(email_sender.messages[0]).encode()


def test_duplicate_normalized_registration_is_generic_and_cooldown_applies(db_engine, client, email_sender):
    first = client.post("/auth/register", json={"email": "same@example.com", "password": "password123"})
    second = client.post("/auth/register", json={"email": " SAME@example.com ", "password": "different123"})
    assert first.json() == second.json()
    assert len(email_sender.messages) == 1
    with auth_session(db_engine) as db:
        assert db.scalar(select(func.count(User.id))) == 1


def test_unverified_login_has_stable_code(db_engine, client):
    create_user(db_engine, "wait@example.com", "password123", verified=False)
    response = client.post("/auth/login", json={"email": "WAIT@example.com", "password": "password123"})
    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"


def test_verification_is_single_use_and_normalized_login_works(db_engine, client, email_sender):
    client.post("/auth/register", json={"email": "verify@example.com", "password": "password123"})
    raw = _token(email_sender.messages[-1])
    assert client.post("/auth/verify-email", json={"token": raw}).status_code == 200
    replay = client.post("/auth/verify-email", json={"token": raw})
    assert replay.status_code == 400
    assert replay.json()["code"] == "invalid_or_expired_token"
    assert login(client, " VERIFY@example.com ", "password123") == 200


def test_expired_and_wrong_purpose_verification_fail(db_engine, client):
    user = create_user(db_engine, "expired@example.com", "password123", verified=False)
    with auth_session(db_engine) as db:
        db.add(AuthChallenge(user_id=user.id, purpose="verify_email", token_hash=auth.hash_token("expired-token-value-123"), expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        db.add(AuthChallenge(user_id=user.id, purpose="reset_password", token_hash=auth.hash_token("wrong-purpose-token-123"), expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)))
        db.commit()
    for raw in ("expired-token-value-123", "wrong-purpose-token-123"):
        response = client.post("/auth/verify-email", json={"token": raw})
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_or_expired_token"


def test_forgot_is_generic_and_reset_revokes_sessions(db_engine, app, client, email_sender):
    create_user(db_engine, "recover@example.com", "oldpassword")
    assert login(client, "recover@example.com", "oldpassword") == 200
    from fastapi.testclient import TestClient

    other = TestClient(app)
    assert login(other, "recover@example.com", "oldpassword") == 200
    clear_cookies(client)
    known = client.post("/auth/forgot-password", json={"email": "recover@example.com"})
    missing = client.post("/auth/forgot-password", json={"email": "missing@example.com"})
    assert known.json() == missing.json()
    raw = _token(email_sender.messages[-1])
    reset = client.post("/auth/reset-password", json={"token": raw, "new_password": "newpassword"})
    assert reset.status_code == 200
    assert client.get("/auth/me").status_code == 401
    assert other.get("/auth/me").status_code == 401
    assert client.post("/auth/reset-password", json={"token": raw, "new_password": "anotherpass"}).status_code == 400
    clear_cookies(client)
    assert login(client, "recover@example.com", "oldpassword") == 401
    assert login(client, "recover@example.com", "newpassword") == 200


def test_google_only_user_can_establish_password(db_engine, client, email_sender):
    create_user(db_engine, "googleonly@example.com", None)
    assert login(client, "googleonly@example.com", "anything") == 401
    client.post("/auth/forgot-password", json={"email": "googleonly@example.com"})
    raw = _token(email_sender.messages[-1])
    assert client.post("/auth/reset-password", json={"token": raw, "new_password": "password123"}).status_code == 200
    assert login(client, "googleonly@example.com", "password123") == 200


def test_google_login_creates_verified_analyst_and_normal_session(db_engine, app, client):
    verifier = _enable_google(app)
    nonce = _nonce(client)
    verifier.claims = {"sub": "sub-1", "email": "person@gmail.com", "email_verified": True, "nonce": nonce}
    response = client.post("/auth/google", json={"credential": "credential-value-long"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "analyst"
    assert response.json()["user"]["has_password"] is False
    assert SESSION_COOKIE in client.cookies
    with auth_session(db_engine) as db:
        user = db.execute(select(User).where(User.email_normalized == "person@gmail.com")).scalar_one()
        identity = db.execute(select(AuthIdentity)).scalar_one()
        assert identity.user_id == user.id
        assert identity.provider_subject == "sub-1"


def test_google_existing_subject_ignores_changed_email(db_engine, app, client):
    verifier = _enable_google(app)
    user = create_user(db_engine, "original@gmail.com", None)
    with auth_session(db_engine) as db:
        db.add(AuthIdentity(user_id=user.id, provider="google", provider_subject="stable-sub", email_at_link=user.email))
        db.commit()
    nonce = _nonce(client)
    verifier.claims = {"sub": "stable-sub", "email": "changed@gmail.com", "email_verified": True, "nonce": nonce}
    response = client.post("/auth/google", json={"credential": "credential-value-long"})
    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.id
    assert response.json()["user"]["email"] == "original@gmail.com"


def test_google_links_gmail_but_requires_explicit_link_for_third_party(db_engine, app, client):
    verifier = _enable_google(app)
    gmail = create_user(db_engine, "match@gmail.com", "password123")
    nonce = _nonce(client)
    verifier.claims = {"sub": "gmail-sub", "email": "MATCH@gmail.com", "email_verified": True, "nonce": nonce}
    assert client.post("/auth/google", json={"credential": "credential-value-long"}).json()["user"]["id"] == gmail.id
    clear_cookies(client)
    create_user(db_engine, "work@example.org", "password123")
    nonce = _nonce(client)
    verifier.claims = {"sub": "work-sub", "email": "work@example.org", "email_verified": True, "nonce": nonce}
    response = client.post("/auth/google", json={"credential": "credential-value-long"})
    assert response.status_code == 409
    assert response.json()["code"] == "account_link_required"


def test_workspace_claim_auto_links_and_explicit_link_is_csrf_protected(db_engine, app, client):
    verifier = _enable_google(app)
    workspace = create_user(db_engine, "user@company.test", "password123")
    nonce = _nonce(client)
    verifier.claims = {"sub": "workspace-sub", "email": workspace.email, "email_verified": True, "hd": "company.test", "nonce": nonce}
    assert client.post("/auth/google", json={"credential": "credential-value-long"}).json()["user"]["id"] == workspace.id

    clear_cookies(client)
    linked = create_user(db_engine, "link@example.net", "password123")
    assert login(client, linked.email, "password123") == 200
    assert client.post("/auth/google/nonce").status_code == 403
    nonce = _nonce(client, authenticated=True)
    verifier.claims = {"sub": "explicit-sub", "email": linked.email, "email_verified": True, "nonce": nonce}
    response = client.post("/account/auth-identities/google", headers=csrf_header(client), json={"credential": "credential-value-long"})
    assert response.status_code == 200
    assert response.json()["user"]["id"] == linked.id


def test_google_nonce_missing_replay_and_invalid_credential_rejected(app, client):
    verifier = _enable_google(app)
    verifier.claims = {"sub": "sub", "email": "x@gmail.com", "email_verified": True, "nonce": "nope"}
    assert client.post("/auth/google", json={"credential": "credential-value-long"}).status_code == 400
    nonce = _nonce(client)
    verifier.failure = True
    assert client.post("/auth/google", json={"credential": "credential-value-long"}).status_code == 401
    verifier.failure = False
    verifier.claims = {"sub": "sub", "email": "x@gmail.com", "email_verified": True, "nonce": nonce}
    assert client.post("/auth/google", json={"credential": "credential-value-long"}).status_code == 200
    clear_cookies(client)
    client.cookies.set("novaq_google_nonce", nonce)
    assert client.post("/auth/google", json={"credential": "credential-value-long"}).status_code == 401


def test_google_disabled_is_hidden_and_fails_closed(client):
    config = client.get("/auth/config").json()
    assert config == {"google_sign_in_enabled": False, "google_client_id": None}
    response = client.post("/auth/google/nonce")
    assert response.status_code == 503
    assert response.json()["code"] == "google_sign_in_unavailable"


def test_password_and_google_login_keep_same_user_and_analysis(db_engine, app, client):
    verifier = _enable_google(app)
    user = create_user(db_engine, "owner@gmail.com", "password123")
    assert login(client, user.email, "password123") == 200
    created = client.post(
        "/analyses",
        headers=csrf_header(client),
        json={"name": "Owned queue", "service_type": "Checkout", "location_label": "Main"},
    )
    assert created.status_code == 201
    analysis_id = created.json()["analysis"]["id"]
    clear_cookies(client)
    nonce = _nonce(client)
    verifier.claims = {
        "sub": "same-user-sub",
        "email": "OWNER@gmail.com",
        "email_verified": True,
        "nonce": nonce,
    }
    google = client.post("/auth/google", json={"credential": "credential-value-long"})
    assert google.status_code == 200
    assert google.json()["user"]["id"] == user.id
    analyses = client.get("/analyses").json()
    assert [item["id"] for item in analyses["analyses"]] == [analysis_id]


def test_inactive_linked_google_user_and_invalid_claims_are_rejected(db_engine, app, client):
    verifier = _enable_google(app)
    user = create_user(db_engine, "inactive@gmail.com", None, active=False)
    with auth_session(db_engine) as db:
        db.add(AuthIdentity(user_id=user.id, provider="google", provider_subject="inactive-sub", email_at_link=user.email))
        db.commit()
    nonce = _nonce(client)
    verifier.claims = {"sub": "inactive-sub", "email": user.email, "email_verified": True, "nonce": nonce}
    response = client.post("/auth/google", json={"credential": "credential-value-long"})
    assert response.status_code == 403
    assert response.json()["code"] == "account_inactive"

    for claims in (
        {"email": "x@gmail.com", "email_verified": True},
        {"sub": "sub"},
        {"sub": "sub", "email": "x@gmail.com", "email_verified": False},
    ):
        clear_cookies(client)
        nonce = _nonce(client)
        verifier.claims = {**claims, "nonce": nonce}
        assert client.post("/auth/google", json={"credential": "credential-value-long"}).status_code == 401


def test_official_google_verifier_rejects_issuer_audience_and_expiry(monkeypatch):
    from google.oauth2 import id_token

    verifier = OfficialGoogleTokenVerifier()
    now = datetime.now(timezone.utc).timestamp()
    valid = {
        "iss": "https://accounts.google.com",
        "aud": "expected-client",
        "exp": now + 300,
        "sub": "sub",
        "email": "user@gmail.com",
        "email_verified": True,
    }
    monkeypatch.setattr(id_token, "verify_oauth2_token", lambda *_args, **_kwargs: valid)
    assert verifier.verify("credential", "expected-client")["sub"] == "sub"
    for changed in (
        {**valid, "iss": "https://issuer.invalid"},
        {**valid, "aud": "wrong-client"},
        {**valid, "exp": now - 1},
    ):
        monkeypatch.setattr(id_token, "verify_oauth2_token", lambda *_args, value=changed, **_kwargs: value)
        with pytest.raises(InvalidGoogleCredential):
            verifier.verify("credential", "expected-client")


def test_official_google_verifier_tolerates_small_clock_skew(monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from google.auth import crypt, jwt
    from google.oauth2 import id_token

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    signer = crypt.RSASigner.from_string(private_pem, key_id="test-key")
    monkeypatch.setattr(id_token, "_fetch_certs", lambda *_args, **_kwargs: {"test-key": public_pem})

    def token(issued_ahead: int) -> str:
        now = int(datetime.now(timezone.utc).timestamp())
        claims = {
            "iss": "https://accounts.google.com",
            "aud": "expected-client",
            "iat": now + issued_ahead,
            "exp": now + 3600,
            "sub": "sub",
            "email": "user@gmail.com",
            "email_verified": True,
        }
        return jwt.encode(signer, claims).decode()

    verifier = OfficialGoogleTokenVerifier()
    # Local clock a few seconds behind Google: the token looks issued in the future.
    assert verifier.verify(token(6), "expected-client")["sub"] == "sub"
    with pytest.raises(InvalidGoogleCredential):
        verifier.verify(token(300), "expected-client")


class auth_session:
    def __init__(self, engine) -> None:
        from tests.helpers import make_sessionmaker

        self.factory = make_sessionmaker(engine)

    def __enter__(self):
        self.db = self.factory()
        return self.db

    def __exit__(self, *_args):
        self.db.close()
