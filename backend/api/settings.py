"""Runtime settings for the API, driven by environment variables."""

from __future__ import annotations

import os


class Settings:
    """Readable, testable settings. Values are read from the environment at
    instantiation time so tests can build their own instance."""

    def __init__(self) -> None:
        self.session_cookie_name = os.environ.get("SESSION_COOKIE_NAME", "novamart_session")
        self.csrf_cookie_name = os.environ.get("CSRF_COOKIE_NAME", "novamart_csrf")
        self.session_ttl_hours = float(os.environ.get("SESSION_TTL_HOURS", "24"))
        self.secure_cookies = os.environ.get("SECURE_COOKIES", "0") == "1"
        self.allowed_origins = [
            origin.strip()
            for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        ]
        self.max_upload_bytes = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
        self.result_jsonb_max_bytes = int(
            os.environ.get("RESULT_JSONB_MAX_BYTES", str(512 * 1024))
        )
        self.artifact_root = os.environ.get("ARTIFACT_ROOT")
