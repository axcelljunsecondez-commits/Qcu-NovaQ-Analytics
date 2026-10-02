"""Signed Pages ingress and rate-limit identity regressions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.api.email_delivery import FakeEmailSender
from backend.api.main import create_app
from backend.api.proxy_assertion import MAX_NONCES, NonceReplayCache
from backend.api.settings import Settings
from tests.helpers import create_user

SECRET = base64.urlsafe_b64encode(bytes(range(32))).decode().rstrip("=")
OTHER_SECRET = base64.urlsafe_b64encode(bytes(range(32, 64))).decode().rstrip("=")


def assertion(
    method: str = "GET",
    path_query: str = "/auth/config",
    ip: str = "198.51.100.8",
    *,
    timestamp: int | None = None,
    nonce: str | None = None,
    secret: str = SECRET,
) -> dict[str, str]:
    issued = str(int(time.time()) if timestamp is None else timestamp)
    token = nonce or uuid.uuid4().hex
    payload = f"v1\n{issued}\n{token}\n{ip}\n{method}\n{path_query}".encode()
    key = base64.urlsafe_b64decode(secret + "=")
    mac = hmac.new(key, payload, hashlib.sha256).digest()
    return {
        "X-NovaQ-Proxy-Version": "1",
        "X-NovaQ-Proxy-Timestamp": issued,
        "X-NovaQ-Proxy-Nonce": token,
        "X-NovaQ-Proxy-Client-IP": ip,
        "X-NovaQ-Proxy-Signature": base64.urlsafe_b64encode(mac).decode().rstrip("="),
        "X-NovaQ-Client-Protocol": "2",
    }


@pytest.fixture
def signed_client(monkeypatch, db_engine):
    monkeypatch.setenv("NOVAQ_PROXY_MODE", "pages_signed")
    monkeypatch.setenv("NOVAQ_PROXY_ASSERTION_SECRET", SECRET)
    app = create_app(engine=db_engine, settings=Settings(), email_sender=FakeEmailSender())
    return TestClient(app), app


def test_signed_request_and_narrow_exemptions(signed_client):
    client, _ = signed_client
    assert client.get("/auth/config", headers=assertion()).status_code == 200
    assert client.get("/auth/config").json()["code"] == "proxy_assertion_required"
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    assert client.options("/auth/config").status_code != 403
    assert client.post("/auth/logout").json()["code"] == "proxy_assertion_required"
    assert client.post("/auth/logout", headers=assertion("POST", "/auth/logout")).status_code == 200
    assert client.get("/auth/config", headers={"X-NovaQ-Client-Protocol": "2"}).status_code == 403


@pytest.mark.parametrize(
    ("mutation", "path"),
    [
        ("missing", "/auth/config"),
        ("version", "/auth/config"),
        ("timestamp", "/auth/config"),
        ("nonce", "/auth/config"),
        ("ip", "/auth/config"),
        ("signature", "/auth/config"),
        ("method", "/auth/config"),
        ("path", "/auth/config"),
        ("query", "/auth/config?x=2"),
        ("xff", "/auth/config"),
        ("xfp", "/auth/config"),
    ],
)
def test_assertion_integrity(signed_client, mutation, path):
    client, _ = signed_client
    headers = assertion(path_query="/auth/config?x=1" if mutation == "query" else "/auth/config")
    if mutation == "missing":
        headers.pop("X-NovaQ-Proxy-Nonce")
    elif mutation == "version":
        headers["X-NovaQ-Proxy-Version"] = "2"
    elif mutation == "timestamp":
        headers["X-NovaQ-Proxy-Timestamp"] = "not-a-time"
    elif mutation == "nonce":
        headers["X-NovaQ-Proxy-Nonce"] = "not-a-nonce"
    elif mutation == "ip":
        headers["X-NovaQ-Proxy-Client-IP"] = "198.51.100.9"
    elif mutation == "signature":
        headers["X-NovaQ-Proxy-Signature"] = "A" * 43
    elif mutation == "method":
        headers = assertion("POST")
    elif mutation == "path":
        headers = assertion(path_query="/auth/me")
    elif mutation == "xff":
        headers["X-Forwarded-For"] = "203.0.113.10"
    elif mutation == "xfp":
        headers["X-Forwarded-Proto"] = "http"
    response = client.get(path, headers=headers)
    if mutation in {"xff", "xfp"}:
        assert response.status_code == 200
    else:
        assert response.status_code == 403
        assert response.json()["code"] == "proxy_assertion_required"


@pytest.mark.parametrize("offset", [-70, 15])
def test_stale_and_future_assertions_fail(signed_client, offset):
    client, _ = signed_client
    assert client.get("/auth/config", headers=assertion(timestamp=int(time.time()) + offset)).status_code == 403


def test_replay_wrong_secret_and_duplicate_headers_fail(signed_client):
    client, _ = signed_client
    headers = assertion()
    assert client.get("/auth/config", headers=headers).status_code == 200
    assert client.get("/auth/config", headers=headers).status_code == 403
    assert client.get("/auth/config", headers=assertion(secret=OTHER_SECRET)).status_code == 403
    duplicate = list(assertion().items())
    duplicate.append(("X-NovaQ-Proxy-Client-IP", "198.51.100.8"))
    assert client.get("/auth/config", headers=duplicate).status_code == 403


@pytest.mark.parametrize("bad_ip", ["198.51.100.999", "001.2.3.4", "bad", "fe80::1%eth0"])
def test_signed_but_malformed_ip_fails(signed_client, bad_ip):
    client, _ = signed_client
    assert client.get("/auth/config", headers=assertion(ip=bad_ip)).status_code == 403


def test_previous_key_is_verification_only(signed_client):
    client, app = signed_client
    app.state.settings.proxy_assertion_previous_secret = OTHER_SECRET
    assert client.get("/auth/config", headers=assertion(secret=OTHER_SECRET)).status_code == 200


def test_nonce_cache_is_thread_safe_bounded_and_expires():
    cache = NonceReplayCache()
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: cache.consume(b"a" * 32, 160, 100), range(20)))
    assert results.count(True) == 1
    for i in range(MAX_NONCES - 1):
        assert cache.consume(f"{i:032x}".encode(), 160, 100)
    assert not cache.consume(b"b" * 32, 160, 100)
    assert cache.consume(b"b" * 32, 221, 161)


def test_signed_ip_is_the_bucket_despite_fake_cookies_and_spoofed_forwarding(signed_client):
    client, app = signed_client
    app.state.settings.rate_limit_auth = 1
    body = {"email": "missing@example.com", "password": "wrong"}
    first = client.post("/auth/login", json=body, headers=assertion("POST", "/auth/login"))
    assert first.status_code == 401
    rotated = assertion("POST", "/auth/login")
    rotated.update({
        "Cookie": "novaq_session=forged-one; novaq_csrf=token",
        "X-CSRF-Token": "token",
        "X-Forwarded-For": "203.0.113.25",
    })
    assert client.post("/auth/login", json=body, headers=rotated).status_code == 429
    rotated["Cookie"] = "novaq_session=forged-two; novaq_csrf=token"
    rotated.update(assertion("POST", "/auth/login"))
    assert client.post("/auth/login", json=body, headers=rotated).status_code == 429
    assert client.post(
        "/auth/login", json=body, headers=assertion("POST", "/auth/login", "198.51.100.9")
    ).status_code == 401
    assert client.post("/auth/login", json=body, headers={"X-NovaQ-Client-Protocol": "2"}).status_code == 403


def test_valid_authenticated_session_remains_usable(signed_client, db_engine):
    client, _ = signed_client
    create_user(db_engine, "signed@example.com", "s3cret")
    login = client.post(
        "/auth/login", json={"email": "signed@example.com", "password": "s3cret"},
        headers=assertion("POST", "/auth/login"),
    )
    assert login.status_code == 200
    me = client.get("/auth/me", headers=assertion("GET", "/auth/me"))
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "signed@example.com"
    csrf = client.cookies.get("novaq_csrf")
    assert csrf
    logout_headers = assertion("POST", "/auth/logout")
    logout_headers["X-CSRF-Token"] = csrf
    assert client.post("/auth/logout", headers=logout_headers).status_code == 200


@pytest.mark.parametrize(
    ("method", "path", "limit"),
    [
        ("POST", "/datasets", "rate_limit_upload"),
        ("GET", "/reports/missing", "rate_limit_report"),
        ("POST", "/analysis", "rate_limit_compute"),
        ("POST", "/admin/missing", "rate_limit_admin"),
    ],
)
def test_other_resource_buckets_use_signed_ip(signed_client, method, path, limit):
    client, app = signed_client
    setattr(app.state.settings, limit, 1)
    client.request(method, path, headers=assertion(method, path))
    second = client.request(method, path, headers=assertion(method, path))
    assert second.status_code == 429


def test_direct_mode_cookie_rotation_does_not_change_rate_bucket(db_engine):
    settings = Settings()
    settings.rate_limit_auth = 1
    app = create_app(engine=db_engine, settings=settings, email_sender=FakeEmailSender())
    client = TestClient(app)
    body = {"email": "missing@example.com", "password": "wrong"}
    assert client.post("/auth/login", json=body, headers={"X-NovaQ-Client-Protocol": "2"}).status_code == 401
    assert client.post(
        "/auth/login", json=body,
        headers={
            "X-NovaQ-Client-Protocol": "2", "Cookie": "novaq_session=forged; novaq_csrf=t",
            "X-CSRF-Token": "t",
        },
    ).status_code == 429
