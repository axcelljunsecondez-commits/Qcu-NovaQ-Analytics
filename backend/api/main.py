"""FastAPI application factory: middleware, auth router, and wiring."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.api import auth
from backend.api.account import router as account_router
from backend.api.analyses import router as analyses_router
from backend.api.analysis import router as analysis_router
from backend.api.auth_routes import router as auth_router
from backend.api.datasets import router as datasets_router
from backend.api.deps import get_current_user
from backend.api.email_delivery import build_email_sender
from backend.api.google_auth import OfficialGoogleTokenVerifier
from backend.api.onboarding import router as onboarding_router
from backend.api.optimization import router as optimization_router
from backend.api.proxy_assertion import NonceReplayCache, ProxyAssertionMiddleware
from backend.api.rate_limit import FixedWindowLimiter, ResourceLimitMiddleware
from backend.api.reports import router as reports_router
from backend.api.scenarios import router as scenarios_router
from backend.api.settings import Settings
from backend.api.shared_named import router as named_shared_router
from backend.api.simulation import router as simulation_router
from backend.api.templates import router as templates_router
from backend.api.users import router as users_router
from backend.api.workflow import router as workflow_router
from backend.db.session import create_engine_for
from backend.db.session import get_db as global_get_db
from backend.operations.migration_status import code_config, required_heads, schema_head_problem

logger = logging.getLogger("novaq.api")
EVENT_LOG_FORMAT = "%(asctime)sZ %(levelname)s %(name)s %(message)s"
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
REPO_ROOT = Path(__file__).resolve().parents[2]
# G7 (decision D4): the public readiness text for a schema that is not, or cannot be shown to be, at
# the code's migration heads. It names no revision.
SCHEMA_REVISION_DETAIL = "Database schema is not at the required migration revision."


class CsrfDoubleSubmitMiddleware:
    """Double-submit CSRF protection: mutations carrying a session cookie must
    echo the CSRF cookie in the X-CSRF-Token header.

    Stateless compute endpoints (analysis/simulation/optimization) are exempt:
    they never mutate server state, so cross-site requests cannot cause harm.
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    EXEMPT_FAMILIES = ("/analysis", "/simulation", "/optimize", "/onboarding")

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        settings: Settings = scope["app"].state.settings
        method = scope["method"]
        cookies = _cookies_from_scope(scope)
        session_cookie = cookies.get(settings.session_cookie_name)
        path = scope["path"]
        exempt = any(path == family or path.startswith(family + "/") for family in self.EXEMPT_FAMILIES)
        if method not in self.SAFE_METHODS and session_cookie and not exempt:
            header = _header_from_scope(scope, "x-csrf-token")
            cookie = cookies.get(settings.csrf_cookie_name)
            if not header or not cookie or header != cookie:
                response = JSONResponse({"detail": "CSRF token mismatch."}, status_code=403)
                return await response(scope, receive, send)
        return await self.app(scope, receive, send)


class RequestIdMiddleware:
    """Attach and echo an X-Request-ID header for correlation."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        supplied = _header_from_scope(scope, "x-request-id")
        request_id = supplied if supplied and SAFE_REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        scope["state"]["request_id"] = request_id

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        return await self.app(scope, receive, send_wrapper)


class _EventLogHandler(logging.StreamHandler):
    """The stream handler ``configure_event_logging`` adds; its type keeps the addition to one."""


def configure_event_logging() -> None:
    """Emit the ``novaq`` loggers' INFO and higher records, the ``event=`` lines.

    Uvicorn's default logging configuration covers only uvicorn's own loggers. Without this, the
    ``novaq`` loggers inherited the root WARNING level, so every INFO ``event=`` line was dropped.
    A UTC-timestamped stream handler is added only when the root logger has no handler, so an
    explicit logging configuration (or pytest's capture) still receives the records once, by
    propagation.
    """
    novaq = logging.getLogger("novaq")
    if novaq.level == logging.NOTSET:
        novaq.setLevel(logging.INFO)
    if logging.getLogger().handlers or any(isinstance(h, _EventLogHandler) for h in novaq.handlers):
        return
    formatter = logging.Formatter(EVENT_LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S")
    formatter.converter = time.gmtime
    handler = _EventLogHandler()
    handler.setFormatter(formatter)
    novaq.addHandler(handler)


class RequestLogMiddleware:
    """Structured access log: method, path, status, duration, request id."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        start = time.perf_counter()
        status_holder = {}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "event=http_request request_id=%s method=%s path=%s status=%s duration_ms=%.1f user_id=%s",
            scope["state"].get("request_id"),
            scope["method"],
            scope["path"],
            status_holder.get("status"),
            duration_ms,
            scope["state"].get("user_id", "anonymous"),
        )


class ErrorBoundaryMiddleware:
    """Return a correlation-safe envelope for otherwise unhandled failures."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        try:
            return await self.app(scope, receive, send)
        except Exception as exc:
            request_id = str(scope.get("state", {}).get("request_id", "unknown"))
            logger.error(
                "event=unexpected_error request_id=%s exception_type=%s",
                request_id,
                type(exc).__name__,
            )
            response = JSONResponse(
                {
                    "code": "internal_error",
                    "detail": "An unexpected server error occurred.",
                    "request_id": request_id,
                },
                status_code=500,
            )
            return await response(scope, receive, send)


def _cookies_from_scope(scope: dict) -> dict[str, str]:
    """Parse the Cookie header out of an ASGI scope."""
    cookie_header = _header_from_scope(scope, "cookie")
    if not cookie_header:
        return {}
    result: dict[str, str] = {}
    for pair in cookie_header.split(";"):
        if "=" in pair:
            key, _, value = pair.strip().partition("=")
            result[key] = value
    return result


def _header_from_scope(scope: dict, name: str) -> str | None:
    target = name.encode()
    for key, value in scope.get("headers", []):
        if key.lower() == target:
            return value.decode()
    return None


def _schema_revision_guard(engine: Engine):
    """G7 (spec 2026-09-26 §11.1, gate G-T16): a production app serves only a database exactly at the
    code's Alembic heads.

    The lifespan runs whenever this app is served, however uvicorn is launched. It fails closed
    (decision D3): heads that cannot be determined, a revision that cannot be read, and any other
    revision all refuse startup, so nothing is served. The heads are resolved from the package, not the
    working directory, and are kept for ``/ready``.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            expected = required_heads(code_config(REPO_ROOT / "alembic.ini", REPO_ROOT / "migrations"))
        except Exception as exc:
            raise RuntimeError(
                f"Database migration heads cannot be determined ({type(exc).__name__}: {exc})."
            ) from exc
        problem = schema_head_problem(engine, expected)
        if problem is not None:
            raise RuntimeError(problem)
        app.state.required_heads = frozenset(expected)
        yield

    return lifespan


def create_app(
    engine=None,
    settings: Settings | None = None,
    email_sender=None,
    google_token_verifier=None,
) -> FastAPI:
    """Build the API application.

    Pass an engine for tests (sqlite); otherwise the configured database is used.
    """
    configure_event_logging()
    settings = settings or Settings()
    engine = engine or create_engine_for(settings.database_url, settings)
    from sqlalchemy.orm import sessionmaker

    SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def get_db():
        db: Session = SessionFactory()
        try:
            yield db
        finally:
            db.close()

    # G7 (decision D2): only production checks the database revision. Every other environment builds
    # the app exactly as before, with no lifespan.
    guard_schema = settings.environment == "production"
    app = FastAPI(
        title="NovaQ — Queueing Analytics",
        version="1.0.0",
        lifespan=_schema_revision_guard(engine) if guard_schema else None,
    )
    app.state.settings = settings
    app.state.email_sender = email_sender or build_email_sender(settings)
    app.state.google_token_verifier = google_token_verifier or OfficialGoogleTokenVerifier()
    app.state.logger = logger
    app.state.rate_limiter = FixedWindowLimiter()
    app.state.proxy_replay_cache = NonceReplayCache()
    app.dependency_overrides[global_get_db] = get_db

    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(ResourceLimitMiddleware)
    app.add_middleware(CsrfDoubleSubmitMiddleware)
    app.add_middleware(ErrorBoundaryMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins or ["http://localhost", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
    )
    app.add_middleware(ProxyAssertionMiddleware)

    @app.exception_handler(auth.AuthApiError)
    async def auth_api_error_handler(request: Request, exc: auth.AuthApiError) -> JSONResponse:
        return JSONResponse(
            {
                "code": exc.code,
                "detail": exc.detail,
                "request_id": str(getattr(request.state, "request_id", "unknown")),
            },
            status_code=exc.status_code,
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready(db: Session = Depends(get_db)) -> dict[str, str]:
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="Database not ready.") from exc
        if guard_schema:
            # G7: the revision is read again on every call, in case the schema changes under the running
            # process. Heads the lifespan did not establish are unverified, never a match.
            required = getattr(app.state, "required_heads", None)
            if required is None or schema_head_problem(engine, set(required)) is not None:
                raise HTTPException(status_code=503, detail=SCHEMA_REVISION_DETAIL)
        return {"status": "ready"}

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(account_router)
    app.include_router(onboarding_router)
    app.include_router(datasets_router)
    app.include_router(analysis_router)
    app.include_router(analyses_router)
    app.include_router(optimization_router)
    app.include_router(simulation_router)
    app.include_router(scenarios_router)
    app.include_router(reports_router)
    app.include_router(templates_router)
    app.include_router(workflow_router)
    app.include_router(named_shared_router)

    return app


app = create_app()
