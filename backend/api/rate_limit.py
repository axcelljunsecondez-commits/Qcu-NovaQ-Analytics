"""Conservative single-worker application rate limiting."""

from __future__ import annotations

import hashlib
import math
import threading
import time
from collections import defaultdict, deque

from fastapi.responses import JSONResponse


class FixedWindowLimiter:
    """Small in-process limiter for the documented single API worker."""

    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def consume(self, bucket: str, key: str, limit: int, window_seconds: int) -> int | None:
        now = time.monotonic()
        cutoff = now - window_seconds
        storage_key = (bucket, key)
        with self._lock:
            events = self._events[storage_key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return max(1, math.ceil(events[0] + window_seconds - now))
            events.append(now)
            if len(self._events) > 10000:
                self._prune(cutoff)
        return None

    def _prune(self, cutoff: float) -> None:
        stale = [key for key, events in self._events.items() if not events or events[-1] <= cutoff]
        for key in stale:
            self._events.pop(key, None)


def _rule(method: str, path: str, settings) -> tuple[str, int] | None:
    if method == "POST" and path in {
        "/auth/login",
        "/auth/register",
        "/auth/resend-verification",
        "/auth/forgot-password",
        "/auth/reset-password",
        "/auth/google/nonce",
        "/auth/google",
    }:
        return "auth", settings.rate_limit_auth
    if method == "POST" and (path == "/datasets" or (path.startswith("/analyses/") and path.endswith("/datasets"))):
        return "upload", settings.rate_limit_upload
    if method == "GET" and path.startswith("/reports/"):
        return "report", settings.rate_limit_report
    if method == "POST" and (
        path == "/analysis"
        or path.startswith("/analysis/")
        or path == "/optimize"
        or path.startswith("/optimize/")
        or path == "/simulation"
        or path.startswith("/simulation/")
    ):
        return "compute", settings.rate_limit_compute
    if method in {"POST", "PATCH", "DELETE"} and path.startswith("/admin/"):
        return "admin", settings.rate_limit_admin
    return None


class ResourceLimitMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        settings = scope["app"].state.settings
        rule = _rule(scope["method"], scope["path"], settings)
        if rule is None:
            return await self.app(scope, receive, send)
        bucket, limit = rule
        cookies = _cookies(scope)
        session = cookies.get(settings.session_cookie_name)
        if session:
            key = "session:" + hashlib.sha256(session.encode()).hexdigest()[:24]
        else:
            client = scope.get("client")
            key = "client:" + (str(client[0]) if client else "unknown")
        retry = scope["app"].state.rate_limiter.consume(bucket, key, limit, settings.rate_limit_window_seconds)
        if retry is not None:
            request_id = scope.get("state", {}).get("request_id", "unknown")
            scope["app"].state.logger.warning("event=rate_limited request_id=%s category=%s", request_id, bucket)
            response = JSONResponse(
                {
                    "code": "rate_limited",
                    "detail": "Too many requests. Try again later.",
                    "request_id": request_id,
                },
                status_code=429,
                headers={"Retry-After": str(retry)},
            )
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)


def _cookies(scope: dict) -> dict[str, str]:
    for key, value in scope.get("headers", []):
        if key.lower() == b"cookie":
            result = {}
            for pair in value.decode(errors="ignore").split(";"):
                name, separator, item = pair.strip().partition("=")
                if separator:
                    result[name] = item
            return result
    return {}
