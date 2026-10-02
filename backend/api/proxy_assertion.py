"""Verify the Pages-to-Render caller assertion before application traffic."""

from __future__ import annotations

import base64
import hashlib
import heapq
import hmac
import ipaddress
import re
import threading
import time

from fastapi.responses import JSONResponse

VERSION = b"1"
MAX_AGE_SECONDS = 60
MAX_FUTURE_SECONDS = 5
MAX_NONCES = 10_000
NONCE_PATTERN = re.compile(rb"[0-9a-f]{32}\Z")
TIMESTAMP_PATTERN = re.compile(rb"[1-9][0-9]{0,11}\Z")
SIGNATURE_PATTERN = re.compile(rb"[A-Za-z0-9_-]{43}\Z")
ASSERTION_HEADERS = (
    b"x-novaq-proxy-version",
    b"x-novaq-proxy-timestamp",
    b"x-novaq-proxy-nonce",
    b"x-novaq-proxy-client-ip",
    b"x-novaq-proxy-signature",
)


def canonical_payload(
    version: bytes, timestamp: bytes, nonce: bytes, client_ip: bytes, method: bytes, path_query: bytes
) -> bytes:
    """Version 1: six UTF-8/ASCII fields separated by LF, without a final LF."""
    fields = (b"v" + version, timestamp, nonce, client_ip, method, path_query)
    return b"\n".join(fields)


class NonceReplayCache:
    """Bounded, lock-protected replay memory for exactly one process/instance."""

    def __init__(self) -> None:
        self._expiry: dict[bytes, int] = {}
        self._deadlines: list[tuple[int, bytes]] = []
        self._lock = threading.Lock()

    def consume(self, nonce: bytes, expiry: int, now: int) -> bool:
        with self._lock:
            while self._deadlines and self._deadlines[0][0] < now:
                deadline, seen = heapq.heappop(self._deadlines)
                if self._expiry.get(seen) == deadline:
                    del self._expiry[seen]
            if nonce in self._expiry or len(self._expiry) >= MAX_NONCES:
                return False
            self._expiry[nonce] = expiry
            heapq.heappush(self._deadlines, (expiry, nonce))
            return True


class ProxyAssertionMiddleware:
    """Fail closed on ordinary API traffic when Pages is the signed ingress."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        settings = scope["app"].state.settings
        if settings.proxy_mode != "pages_signed":
            return await self.app(scope, receive, send)
        method = scope["method"]
        path = scope["path"]
        if method == "OPTIONS" or (method in {"GET", "HEAD"} and path in {"/health", "/ready"}):
            return await self.app(scope, receive, send)

        def denied():
            return JSONResponse(
                {"code": "proxy_assertion_required", "detail": "Trusted API ingress required."},
                status_code=403,
                headers={"Cache-Control": "private, no-store"},
            )

        values = {
            name: [value for key, value in scope.get("headers", []) if key.lower() == name]
            for name in ASSERTION_HEADERS
        }
        if any(len(items) != 1 for items in values.values()):
            return await denied()(scope, receive, send)
        version, timestamp, nonce, claimed_ip, signature = (values[name][0] for name in ASSERTION_HEADERS)
        if (
            version != VERSION
            or not TIMESTAMP_PATTERN.fullmatch(timestamp)
            or not NONCE_PATTERN.fullmatch(nonce)
            or not SIGNATURE_PATTERN.fullmatch(signature)
        ):
            return await denied()(scope, receive, send)
        now = int(time.time())
        issued = int(timestamp)
        if not now - MAX_AGE_SECONDS <= issued <= now + MAX_FUTURE_SECONDS:
            return await denied()(scope, receive, send)
        try:
            ip_text = claimed_ip.decode("ascii")
            if "%" in ip_text:
                raise ValueError("Scoped IPv6 addresses are not valid client identities")
            ip = str(ipaddress.ip_address(ip_text))
            raw_path = scope["raw_path"]
            query = scope["query_string"]
            path_query = raw_path + (b"?" + query if query else b"")
            path_query.decode("ascii")
            method_bytes = method.encode("ascii")
        except (UnicodeError, ValueError, KeyError):
            return await denied()(scope, receive, send)
        if ip.encode("ascii") != claimed_ip or b"\n" in path_query or b"\n" in method_bytes:
            return await denied()(scope, receive, send)

        payload = canonical_payload(version, timestamp, nonce, claimed_ip, method_bytes, path_query)
        secrets = (settings.proxy_assertion_secret, settings.proxy_assertion_previous_secret)
        valid = False
        for secret in secrets:
            if secret:
                key = base64.urlsafe_b64decode(secret + "=")
                mac = hmac.new(key, payload, hashlib.sha256).digest()
                encoded = base64.urlsafe_b64encode(mac).rstrip(b"=")
                valid |= hmac.compare_digest(signature, encoded)
        if not valid:
            return await denied()(scope, receive, send)
        if not scope["app"].state.proxy_replay_cache.consume(nonce, issued + MAX_AGE_SECONDS, now):
            return await denied()(scope, receive, send)
        scope.setdefault("state", {})["verified_client_ip"] = ip
        return await self.app(scope, receive, send)
