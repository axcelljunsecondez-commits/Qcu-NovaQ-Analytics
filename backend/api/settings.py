"""Fail-closed runtime settings for the NovaQ API."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit


def env_value(name: str, default: str | None = None) -> str | None:
    """Read NAME or NAME_FILE without ever logging the resolved secret value."""
    direct = os.environ.get(name)
    file_name = os.environ.get(f"{name}_FILE")
    if direct is not None and file_name:
        raise ValueError(f"Set only one of {name} and {name}_FILE")
    if file_name:
        path = Path(file_name)
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(f"Could not read {name}_FILE") from exc
        if not value:
            raise ValueError(f"{name}_FILE must not be empty")
        return value
    return direct if direct is not None else default


def database_url_from_environment() -> str:
    """Resolve a full URL or construct one from PostgreSQL component settings."""
    configured = env_value("DATABASE_URL")
    if configured:
        return configured
    production = os.environ.get("NOVAQ_ENV", "development").strip().lower() == "production"
    user = os.environ.get("POSTGRES_USER")
    password = env_value("POSTGRES_PASSWORD")
    database = os.environ.get("POSTGRES_DB")
    host = os.environ.get("DATABASE_HOST", "db" if production else "localhost")
    port = os.environ.get("DATABASE_PORT", "5432")
    if user and password and database:
        return (
            f"postgresql+psycopg://{quote(user, safe='')}:{quote(password, safe='')}"
            f"@{host}:{port}/{quote(database, safe='')}"
        )
    if production:
        raise ValueError(
            "Production requires DATABASE_URL(_FILE) or POSTGRES_USER, "
            "POSTGRES_PASSWORD(_FILE), and POSTGRES_DB"
        )
    return "postgresql+psycopg://novaq:novaq@localhost:5432/novaq"


def _int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be finite and between {minimum} and {maximum}")
    return value


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "1" if default else "0").strip().lower()
    if raw not in {"0", "1", "true", "false"}:
        raise ValueError(f"{name} must be 0/1 or true/false")
    return raw in {"1", "true"}


def _origins(raw: str) -> list[str]:
    values = json.loads(raw) if raw.startswith("[") else [item.strip() for item in raw.split(",") if item.strip()]
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise ValueError("ALLOWED_ORIGINS must contain origin strings")
    for origin in values:
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
            or origin == "*"
        ):
            raise ValueError(
                "ALLOWED_ORIGINS requires exact HTTP(S) origins without paths, wildcards, or credentials"
            )
    return values


def _https_origin(name: str, value: str) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError(f"Production requires {name} to be an exact HTTPS origin")


class Settings:
    """Readable settings whose constructor is the production preflight."""

    def __init__(self) -> None:
        self.environment = os.environ.get("NOVAQ_ENV", "development").strip().lower()
        if self.environment not in {"development", "test", "integration", "production"}:
            raise ValueError("NOVAQ_ENV must be development, test, integration, or production")

        self.session_cookie_name = os.environ.get("SESSION_COOKIE_NAME", "novaq_session")
        self.csrf_cookie_name = os.environ.get("CSRF_COOKIE_NAME", "novaq_csrf")
        for name, value in (
            ("SESSION_COOKIE_NAME", self.session_cookie_name),
            ("CSRF_COOKIE_NAME", self.csrf_cookie_name),
        ):
            if not value or not all(character.isalnum() or character in "_-" for character in value):
                raise ValueError(f"{name} contains unsafe characters")
        self.session_ttl_hours = _float("SESSION_TTL_HOURS", 24, 0.25, 720)
        self.verification_ttl_minutes = _int("VERIFICATION_TTL_MINUTES", 60, 5, 1440)
        self.password_reset_ttl_minutes = _int("PASSWORD_RESET_TTL_MINUTES", 30, 5, 1440)
        self.google_nonce_ttl_minutes = _int("GOOGLE_NONCE_TTL_MINUTES", 5, 1, 30)
        self.auth_token_cooldown_seconds = _int("AUTH_TOKEN_COOLDOWN_SECONDS", 60, 1, 3600)
        self.auth_token_hourly_limit = _int("AUTH_TOKEN_HOURLY_LIMIT", 5, 1, 100)
        self.secure_cookies = _bool("SECURE_COOKIES", False)
        self.public_app_url = os.environ.get("PUBLIC_APP_URL", "http://localhost").rstrip("/")

        raw_origins = os.environ.get("ALLOWED_ORIGINS", "").strip()
        self.allowed_origins = _origins(raw_origins) if raw_origins else []
        self.cors_methods = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
        self.cors_headers = ["Content-Type", "X-CSRF-Token", "X-Request-ID"]

        self.email_delivery_mode = os.environ.get("EMAIL_DELIVERY_MODE", "console").strip().lower()
        if self.email_delivery_mode not in {"console", "smtp"}:
            raise ValueError("EMAIL_DELIVERY_MODE must be console or smtp")
        self.smtp_host = os.environ.get("SMTP_HOST", "").strip()
        self.smtp_port = _int("SMTP_PORT", 587, 1, 65535)
        self.smtp_username = os.environ.get("SMTP_USERNAME", "").strip()
        self.smtp_password = env_value("SMTP_PASSWORD")
        self.smtp_from_email = os.environ.get("SMTP_FROM_EMAIL", "").strip()
        self.smtp_use_tls = _bool("SMTP_USE_TLS", True)
        self.google_sign_in_enabled = _bool("GOOGLE_SIGN_IN_ENABLED", False)
        self.google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip() or None

        self.max_upload_bytes = _int("MAX_UPLOAD_BYTES", 5 * 1024 * 1024, 1024, 50 * 1024 * 1024)
        self.xlsx_max_uncompressed_bytes = _int(
            "XLSX_MAX_UNCOMPRESSED_BYTES", 50 * 1024 * 1024, 1024, 500 * 1024 * 1024
        )
        self.xlsx_max_zip_members = _int("XLSX_MAX_ZIP_MEMBERS", 1000, 10, 10000)
        self.xlsx_max_compression_ratio = _float("XLSX_MAX_COMPRESSION_RATIO", 100, 1, 1000)
        self.xlsx_max_worksheets = _int("XLSX_MAX_WORKSHEETS", 20, 1, 100)
        self.upload_max_rows = _int("UPLOAD_MAX_ROWS", 100000, 1, 1000000)
        self.upload_max_columns = _int("UPLOAD_MAX_COLUMNS", 100, 1, 1000)
        self.upload_max_cell_chars = _int("UPLOAD_MAX_CELL_CHARS", 32768, 1, 1048576)
        self.upload_max_dataframe_bytes = _int(
            "UPLOAD_MAX_DATAFRAME_BYTES", 100 * 1024 * 1024, 1024, 1024 * 1024 * 1024
        )
        self.result_jsonb_max_bytes = _int("RESULT_JSONB_MAX_BYTES", 512 * 1024, 1024, 10 * 1024 * 1024)
        self.artifact_root = os.environ.get("ARTIFACT_ROOT")

        self.db_pool_size = _int("DB_POOL_SIZE", 5, 1, 50)
        self.db_max_overflow = _int("DB_MAX_OVERFLOW", 5, 0, 50)
        self.db_pool_timeout_seconds = _int("DB_POOL_TIMEOUT_SECONDS", 10, 1, 120)
        self.db_pool_recycle_seconds = _int("DB_POOL_RECYCLE_SECONDS", 1800, 30, 86400)
        self.db_connect_timeout_seconds = _int("DB_CONNECT_TIMEOUT_SECONDS", 5, 1, 60)
        self.api_workers = _int("API_WORKERS", 1, 1, 2)
        self.api_limit_concurrency = _int("API_LIMIT_CONCURRENCY", 32, 1, 256)
        self.api_graceful_shutdown_seconds = _int("API_GRACEFUL_SHUTDOWN_SECONDS", 30, 1, 120)
        self.rate_limit_window_seconds = _int("RATE_LIMIT_WINDOW_SECONDS", 60, 1, 3600)
        self.rate_limit_auth = _int("RATE_LIMIT_AUTH", 10, 1, 1000)
        self.rate_limit_upload = _int("RATE_LIMIT_UPLOAD", 10, 1, 1000)
        self.rate_limit_report = _int("RATE_LIMIT_REPORT", 10, 1, 1000)
        self.rate_limit_compute = _int("RATE_LIMIT_COMPUTE", 30, 1, 1000)
        self.rate_limit_admin = _int("RATE_LIMIT_ADMIN", 30, 1, 1000)

        self.database_url = database_url_from_environment()
        self.forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1").strip()

        if self.google_sign_in_enabled and not self.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID is required when Google Sign-In is enabled")
        if self.environment == "production":
            self._validate_production()

    def _validate_production(self) -> None:
        if not self.secure_cookies:
            raise ValueError("Production requires SECURE_COOKIES=1")
        if not self.allowed_origins:
            raise ValueError("Production requires explicit ALLOWED_ORIGINS")
        for origin in self.allowed_origins:
            _https_origin("ALLOWED_ORIGINS", origin)
        _https_origin("PUBLIC_APP_URL", self.public_app_url)
        if self.email_delivery_mode != "smtp" or not self.smtp_host or not self.smtp_from_email:
            raise ValueError("Production requires SMTP email delivery settings")
        if not self.smtp_use_tls:
            raise ValueError("Production requires SMTP_USE_TLS=1")
        parsed_db = urlsplit(self.database_url)
        if (
            not parsed_db.scheme.startswith("postgresql")
            or not parsed_db.hostname
            or not parsed_db.username
            or not parsed_db.path.strip("/")
        ):
            raise ValueError("Production requires a complete PostgreSQL database configuration")
        if parsed_db.password in {"novaq", "postgres", "password", "admin123"}:
            raise ValueError("Production database credentials must not use demo defaults")
        try:
            database_port = parsed_db.port
        except ValueError as exc:
            raise ValueError("Production database port is invalid") from exc
        if database_port is not None and not 1 <= database_port <= 65535:
            raise ValueError("Production database port is invalid")
        configured_user = os.environ.get("POSTGRES_USER")
        configured_database = os.environ.get("POSTGRES_DB")
        if configured_user and unquote(parsed_db.username or "") != configured_user:
            raise ValueError("DATABASE_URL does not agree with POSTGRES_USER")
        if configured_database and unquote(parsed_db.path.strip("/")) != configured_database:
            raise ValueError("DATABASE_URL does not agree with POSTGRES_DB")
        if self.public_app_url not in self.allowed_origins:
            raise ValueError("PUBLIC_APP_URL must be included in ALLOWED_ORIGINS")
        if self.forwarded_allow_ips in {"", "*", "0.0.0.0/0"}:
            raise ValueError("Production requires an explicit trusted FORWARDED_ALLOW_IPS value")
        if self.api_workers != 1:
            raise ValueError("The initial production topology requires API_WORKERS=1")
