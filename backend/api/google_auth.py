"""Backend-only Google Identity Services ID-token verification."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


class InvalidGoogleCredential(ValueError):
    pass


class GoogleTokenVerifier(Protocol):
    def verify(self, credential: str, audience: str) -> dict: ...


class OfficialGoogleTokenVerifier:
    def verify(self, credential: str, audience: str) -> dict:
        try:
            from google.auth.transport import requests
            from google.oauth2 import id_token

            claims = id_token.verify_oauth2_token(credential, requests.Request(), audience)
        except Exception as exc:
            raise InvalidGoogleCredential("Google credential validation failed.") from exc
        issuer = claims.get("iss")
        expires = claims.get("exp")
        if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
            raise InvalidGoogleCredential("Invalid Google issuer.")
        if not isinstance(expires, (int, float)) or expires <= datetime.now(timezone.utc).timestamp():
            raise InvalidGoogleCredential("Expired Google credential.")
        if claims.get("aud") != audience:
            raise InvalidGoogleCredential("Invalid Google audience.")
        return dict(claims)
