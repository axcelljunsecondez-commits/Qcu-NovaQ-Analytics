from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from backend.api.email_delivery import FakeEmailSender
from backend.api.main import CsrfDoubleSubmitMiddleware, create_app
from backend.api.settings import Settings, env_value


def production_environment(monkeypatch) -> None:
    values = {
        "NOVAQ_ENV": "production",
        "DATABASE_URL": "postgresql+psycopg://novaq:strong-fixture@db:5432/novaq",
        "SECURE_COOKIES": "1",
        "ALLOWED_ORIGINS": "https://novaq.example",
        "PUBLIC_APP_URL": "https://novaq.example",
        "EMAIL_DELIVERY_MODE": "smtp",
        "SMTP_HOST": "smtp.example",
        "SMTP_FROM_EMAIL": "no-reply@novaq.example",
        "FORWARDED_ALLOW_IPS": "172.30.0.10",
        "API_WORKERS": "1",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_production_preflight_accepts_secure_fixture(monkeypatch):
    production_environment(monkeypatch)
    settings = Settings()
    assert settings.secure_cookies is True
    assert settings.cors_methods == ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
    assert settings.cors_headers == ["Content-Type", "X-CSRF-Token", "X-Request-ID"]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SECURE_COOKIES", "0"),
        ("ALLOWED_ORIGINS", "http://novaq.example"),
        ("PUBLIC_APP_URL", "http://novaq.example"),
        ("EMAIL_DELIVERY_MODE", "console"),
        ("FORWARDED_ALLOW_IPS", "*"),
        ("API_WORKERS", "2"),
        ("SESSION_TTL_HOURS", "nan"),
        ("MAX_UPLOAD_BYTES", "0"),
    ],
)
def test_production_preflight_rejects_insecure_values(monkeypatch, name, value):
    production_environment(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        Settings()


def test_google_enabled_requires_client_id(monkeypatch):
    monkeypatch.setenv("GOOGLE_SIGN_IN_ENABLED", "1")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID"):
        Settings()


def test_secret_file_is_supported_and_conflicts_fail(tmp_path, monkeypatch):
    secret = tmp_path / "secret"
    secret.write_text("not-logged-value\n", encoding="utf-8")
    monkeypatch.setenv("SMTP_PASSWORD_FILE", str(secret))
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    assert env_value("SMTP_PASSWORD") == "not-logged-value"
    monkeypatch.setenv("SMTP_PASSWORD", "duplicate")
    with pytest.raises(ValueError, match="only one"):
        env_value("SMTP_PASSWORD")


def test_cors_allows_only_configured_origin(db_engine):
    settings = Settings()
    settings.allowed_origins = ["https://novaq.example"]
    app = create_app(engine=db_engine, settings=settings, email_sender=FakeEmailSender())
    client = TestClient(app)
    allowed = client.get("/health", headers={"Origin": "https://novaq.example"})
    denied = client.get("/health", headers={"Origin": "https://attacker.example"})
    assert allowed.headers["access-control-allow-origin"] == "https://novaq.example"
    assert denied.headers.get("access-control-allow-origin") is None
    preflight = client.options(
        "/auth/logout",
        headers={
            "Origin": "https://novaq.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-token,x-request-id",
        },
    )
    assert preflight.status_code == 200
    assert "POST" in preflight.headers["access-control-allow-methods"]
    assert "authorization" not in preflight.headers["access-control-allow-headers"].lower()


def test_invalid_request_id_is_replaced(client):
    supplied = "bad id\r\nmalicious" + "x" * 100
    response = client.get("/health", headers={"X-Request-ID": supplied})
    request_id = response.headers["X-Request-ID"]
    assert request_id != supplied
    assert len(request_id) <= 64


def test_unexpected_error_is_sanitized(db_engine):
    app = create_app(engine=db_engine, settings=Settings(), email_sender=FakeEmailSender())

    @app.get("/test-unexpected")
    def unexpected() -> None:
        raise RuntimeError("database password and C:/secret/path")

    response = TestClient(app, raise_server_exceptions=False).get("/test-unexpected")
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "password" not in response.text
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_rate_limit_returns_429_and_retry_after(db_engine):
    settings = Settings()
    settings.rate_limit_auth = 1
    app = create_app(engine=db_engine, settings=settings, email_sender=FakeEmailSender())
    client = TestClient(app)
    payload = {"email": "missing@example.com", "password": "wrong"}
    assert client.post("/auth/login", json=payload).status_code == 401
    limited = client.post("/auth/login", json=payload)
    assert limited.status_code == 429
    assert limited.json()["code"] == "rate_limited"
    assert int(limited.headers["Retry-After"]) >= 1


def test_malformed_json_is_actionable_but_sanitized(client):
    response = client.post(
        "/auth/login", content=b'{"email":', headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert "traceback" not in response.text.lower()
    assert "filesystem" not in response.text.lower()


def test_secure_cookie_deletion_matches_issuance(client, app):
    app.state.settings.secure_cookies = True
    response = client.post(
        "/auth/logout",
        headers={
            "Cookie": "novaq_session=fake; novaq_csrf=csrf",
            "X-CSRF-Token": "csrf",
        },
    )
    assert response.status_code == 200
    deleted = response.headers.get_list("set-cookie")
    assert len(deleted) == 3
    assert all("Secure" in cookie and "Path=/" in cookie and "SameSite=lax" in cookie for cookie in deleted)


def test_csrf_exemptions_are_exact_and_cookie_is_not_authorization(client):
    assert CsrfDoubleSubmitMiddleware.EXEMPT_FAMILIES == (
        "/analysis",
        "/simulation",
        "/optimize",
        "/onboarding",
    )
    client.cookies.set("novaq_csrf", "csrf-only")
    assert client.post("/scenarios", json={}).status_code == 401


def test_production_artifacts_encode_required_isolation_and_sequence():
    root = Path(__file__).resolve().parents[1]
    compose = yaml.safe_load((root / "docker-compose.production.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert "ports" not in services["db"] and "ports" not in services["api"]
    assert services["web"]["ports"] == ["127.0.0.1:8080:8080"]
    assert services["bootstrap-admin"]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    assert services["api"]["depends_on"]["bootstrap-admin"]["condition"] == "service_completed_successfully"
    assert "ADMIN_PASSWORD" not in services["api"]["environment"]
    assert services["api"]["read_only"] is True
    assert services["api"]["cap_drop"] == ["ALL"]

    dockerfile = (root / "Dockerfile.api").read_text(encoding="utf-8")
    for required in (
        "FROM python:3.11.16-alpine3.24@sha256:"
        "0d55920083f1ce1e38ac292e2772f924b4f8bb4188d336c79bf66963039e6146",
        "apk upgrade --no-cache",
        "addgroup -S -g 10001 novaq",
        "adduser -S -D -H -u 10001 -G novaq -s /sbin/nologin novaq",
        "requirements-production.lock",
        "pip install --no-cache-dir --no-deps -r requirements-production.lock",
        "python -m pip check",
        "pip uninstall --yes pip setuptools wheel",
        "USER 10001:10001",
    ):
        assert required in dockerfile
    assert "apt-get" not in dockerfile
    assert "alembic upgrade" not in (root / "backend/api/entrypoint.sh").read_text(encoding="utf-8")

    nginx = (root / "nginx/production.conf").read_text(encoding="utf-8")
    for directive in (
        "server_tokens off",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Content-Security-Policy",
        "frame-ancestors 'none'",
        "proxy_set_header X-Forwarded-For $remote_addr",
    ):
        assert directive in nginx
    assert "unsafe-eval" not in nginx
