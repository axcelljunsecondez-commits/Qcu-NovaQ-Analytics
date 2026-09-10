from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
import yaml

from backend.api.settings import database_url_from_environment


def test_component_database_url_percent_encodes_reserved_characters(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_FILE", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "nova q")
    monkeypatch.setenv("POSTGRES_PASSWORD", "strong +/@: password")
    monkeypatch.setenv("POSTGRES_DB", "nova q")

    parsed = urlsplit(database_url_from_environment())

    assert unquote(parsed.username or "") == "nova q"
    assert unquote(parsed.password or "") == "strong +/@: password"
    assert unquote(parsed.path.lstrip("/")) == "nova q"


from backend.api.settings import Settings


@pytest.mark.parametrize(
    "raw",
    ['["https://app.example.com", "https://staff.example.com"]', "https://app.example.com,https://staff.example.com"],
)
def test_cors_origin_formats(raw, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", raw)
    assert Settings().allowed_origins == ["https://app.example.com", "https://staff.example.com"]


@pytest.mark.parametrize("raw", ["[broken", "*", "https://example.com/path", "[1]"])
def test_cors_rejects_invalid_origins(raw, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", raw)
    with pytest.raises(ValueError):
        Settings()


def test_production_has_private_services_and_mandatory_credentials():
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "docker-compose.production.yml").read_text())
    for service in ("db", "api"):
        assert "ports" not in config["services"][service]
    assert config["services"]["api"]["environment"]["SECURE_COOKIES"] == "1"
    assert config["services"]["db"]["environment"]["POSTGRES_PASSWORD_FILE"] == "/run/secrets/db_password"
    assert "ADMIN_PASSWORD" not in config["services"]["api"]["environment"]
    assert config["services"]["api"]["depends_on"]["bootstrap-admin"]["condition"] == "service_completed_successfully"
    assert (
        config["services"]["bootstrap-admin"]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    )
    assert config["services"]["web"]["ports"] == ["127.0.0.1:8080:8080"]
