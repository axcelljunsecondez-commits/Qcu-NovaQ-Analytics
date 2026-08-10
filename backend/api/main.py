"""FastAPI application factory: middleware, auth router, and wiring."""

from __future__ import annotations

import logging
import secrets
import time
import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api import auth
from backend.api.account import router as account_router
from backend.api.analysis import router as analysis_router
from backend.api.datasets import router as datasets_router
from backend.api.deps import get_current_user
from backend.api.optimization import router as optimization_router
from backend.api.reports import router as reports_router
from backend.api.scenarios import router as scenarios_router
from backend.api.settings import Settings
from backend.api.simulation import router as simulation_router
from backend.api.users import router as users_router
from backend.db.models import User
from backend.db.session import DATABASE_URL, create_engine_for
from backend.db.session import get_db as global_get_db

logger = logging.getLogger("novamart.api")


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CsrfDoubleSubmitMiddleware:
    """Double-submit CSRF protection: mutations carrying a session cookie must
    echo the CSRF cookie in the X-CSRF-Token header.

    Stateless compute endpoints (analysis/simulation/optimization) are exempt:
    they never mutate server state, so cross-site requests cannot cause harm.
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    EXEMPT_PREFIXES = ("/analysis", "/simulation", "/optimize")

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        settings: Settings = scope["app"].state.settings
        method = scope["method"]
        cookies = _cookies_from_scope(scope)
        session_cookie = cookies.get(settings.session_cookie_name)
        exempt = scope["path"].startswith(self.EXEMPT_PREFIXES)
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

        request_id = _header_from_scope(scope, "x-request-id") or uuid.uuid4().hex
        scope["state"]["request_id"] = request_id

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        return await self.app(scope, receive, send_wrapper)


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
            "%s %s -> %s (%.1fms) id=%s",
            scope["method"],
            scope["path"],
            status_holder.get("status"),
            duration_ms,
            scope["state"].get("request_id"),
        )


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


def create_app(
    engine=None,
    settings: Settings | None = None,
) -> FastAPI:
    """Build the API application.

    Pass an engine for tests (sqlite); otherwise the configured database is used.
    """
    settings = settings or Settings()
    engine = engine or create_engine_for(DATABASE_URL)
    from sqlalchemy.orm import sessionmaker

    SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def get_db():
        db: Session = SessionFactory()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI(title="NovaMart API", version="1.0.0")
    app.state.settings = settings
    app.dependency_overrides[global_get_db] = get_db

    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(CsrfDoubleSubmitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins or ["http://localhost", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/auth/login")
    def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
        settings_local: Settings = request.app.state.settings
        user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
        if user is None or not auth.verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        if not user.active:
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        token = auth.create_session(db, user.id, settings_local.session_ttl_hours)
        csrf_token = secrets.token_urlsafe(32)
        max_age = int(settings_local.session_ttl_hours * 3600)
        response = JSONResponse({"user": UserOut.model_validate(user).model_dump(mode="json")})
        for name, value, httponly in (
            (settings_local.session_cookie_name, token, True),
            (settings_local.csrf_cookie_name, csrf_token, False),
        ):
            response.set_cookie(
                key=name,
                value=value,
                max_age=max_age,
                httponly=httponly,
                secure=settings_local.secure_cookies,
                samesite="lax",
                path="/",
            )
        return response

    @app.post("/auth/logout")
    def logout(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
        settings_local: Settings = request.app.state.settings
        token = request.cookies.get(settings_local.session_cookie_name)
        auth.revoke_session(db, token)
        response = JSONResponse({"detail": "Logged out."})
        response.delete_cookie(
            key=settings_local.session_cookie_name, path="/", samesite="lax"
        )
        response.delete_cookie(key=settings_local.csrf_cookie_name, path="/", samesite="lax")
        return response

    @app.get("/auth/me")
    def me(user: User = Depends(get_current_user)) -> dict[str, UserOut]:
        return {"user": UserOut.model_validate(user)}

    app.include_router(users_router)
    app.include_router(account_router)
    app.include_router(datasets_router)
    app.include_router(analysis_router)
    app.include_router(optimization_router)
    app.include_router(simulation_router)
    app.include_router(scenarios_router)
    app.include_router(reports_router)

    return app


app = create_app()
