"""SaaS authentication routes layered onto NovaQ's existing session model."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.api import auth
from backend.api.auth_schemas import AuthConfigOut
from backend.api.deps import get_current_user
from backend.api.email_delivery import EmailDeliveryError, reset_email, verification_email
from backend.api.google_auth import InvalidGoogleCredential
from backend.db.models import AuthChallenge, AuthIdentity, User
from backend.db.session import get_db

router = APIRouter(tags=["authentication"])

GENERIC_VERIFICATION = "If this address is eligible, verification instructions have been sent."
GENERIC_RESET = "If this address is eligible, password reset instructions have been sent."
INVALID_CREDENTIALS = "Invalid email or password."


class EmailPassword(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=128)


class RegistrationRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class EmailRequest(BaseModel):
    email: EmailStr = Field(max_length=255)


class TokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class ResetRequest(TokenRequest):
    new_password: str = Field(min_length=8, max_length=128)


class GoogleCredential(BaseModel):
    credential: str = Field(min_length=20, max_length=16384)


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def _security_event(
    request: Request, event: str, *, outcome: str, user_id: int | None = None
) -> None:
    request.app.state.logger.info(
        "event=%s request_id=%s outcome=%s user_id=%s",
        event,
        _request_id(request),
        outcome,
        user_id if user_id is not None else "unknown",
    )


def _send_verification(request: Request, user: User, db: Session) -> bool:
    settings = request.app.state.settings
    raw = auth.issue_challenge(
        db,
        user_id=user.id,
        purpose="verify_email",
        ttl_minutes=settings.verification_ttl_minutes,
        cooldown_seconds=settings.auth_token_cooldown_seconds,
        hourly_limit=settings.auth_token_hourly_limit,
    )
    if raw is None:
        return False
    subject, text = verification_email(settings.public_app_url, raw)
    request.app.state.email_sender.send(to=user.email, subject=subject, text=text)
    return True


def _send_reset(request: Request, user: User, db: Session) -> bool:
    settings = request.app.state.settings
    raw = auth.issue_challenge(
        db,
        user_id=user.id,
        purpose="reset_password",
        ttl_minutes=settings.password_reset_ttl_minutes,
        cooldown_seconds=settings.auth_token_cooldown_seconds,
        hourly_limit=settings.auth_token_hourly_limit,
    )
    if raw is None:
        return False
    subject, text = reset_email(settings.public_app_url, raw)
    request.app.state.email_sender.send(to=user.email, subject=subject, text=text)
    return True


@router.get("/auth/config", response_model=AuthConfigOut)
def auth_config(request: Request) -> AuthConfigOut:
    settings = request.app.state.settings
    enabled = bool(settings.google_sign_in_enabled and settings.google_client_id)
    return AuthConfigOut(
        google_sign_in_enabled=enabled,
        google_client_id=settings.google_client_id if enabled else None,
    )


@router.post("/auth/register")
def register(payload: RegistrationRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    normalized = auth.normalize_email(str(payload.email))
    user = db.execute(select(User).where(User.email_normalized == normalized)).scalar_one_or_none()
    created = False
    if user is None:
        user = User(
            email=str(payload.email).strip(),
            email_normalized=normalized,
            email_verified_at=None,
            password_hash=auth.hash_password(payload.password),
            role="analyst",
            active=True,
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
            created = True
        except IntegrityError:
            db.rollback()
            user = db.execute(
                select(User).where(User.email_normalized == normalized)
            ).scalar_one_or_none()
    if user is not None and user.active and user.email_verified_at is None:
        try:
            _send_verification(request, user, db)
        except EmailDeliveryError as exc:
            request.app.state.logger.error(
                "Verification email delivery failed id=%s", _request_id(request)
            )
            if created:
                raise auth.AuthApiError(503, "email_delivery_unavailable", "Verification email is temporarily unavailable.") from exc
    _security_event(
        request,
        "registration",
        outcome="accepted",
        user_id=user.id if created and user is not None else None,
    )
    return {"detail": GENERIC_VERIFICATION}


@router.post("/auth/resend-verification")
def resend_verification(payload: EmailRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    user = db.execute(
        select(User).where(User.email_normalized == auth.normalize_email(str(payload.email)))
    ).scalar_one_or_none()
    if user is not None and user.active and user.email_verified_at is None:
        try:
            _send_verification(request, user, db)
        except EmailDeliveryError:
            request.app.state.logger.error(
                "Verification email delivery failed id=%s", _request_id(request)
            )
    return {"detail": GENERIC_VERIFICATION}


@router.post("/auth/verify-email")
def verify_email(payload: TokenRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    challenge = auth.consume_challenge(db, payload.token, "verify_email")
    if challenge is None or challenge.user_id is None:
        raise auth.AuthApiError(400, "invalid_or_expired_token", "This verification link is invalid, expired, or already used.")
    user = db.get(User, challenge.user_id)
    if user is None:
        db.rollback()
        raise auth.AuthApiError(400, "invalid_or_expired_token", "This verification link is invalid, expired, or already used.")
    now = datetime.now(timezone.utc)
    user.email_verified_at = user.email_verified_at or now
    db.execute(
        update(AuthChallenge)
        .where(
            AuthChallenge.user_id == user.id,
            AuthChallenge.purpose == "verify_email",
            AuthChallenge.consumed_at.is_(None),
        )
        .values(consumed_at=now)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    _security_event(request, "email_verification", outcome="success", user_id=user.id)
    return {"detail": "Email verified. You can now sign in."}


@router.post("/auth/forgot-password")
def forgot_password(payload: EmailRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    user = db.execute(
        select(User).where(User.email_normalized == auth.normalize_email(str(payload.email)))
    ).scalar_one_or_none()
    if user is not None and user.active and user.email_verified_at is not None:
        try:
            _send_reset(request, user, db)
        except EmailDeliveryError:
            request.app.state.logger.error("Password-reset email delivery failed id=%s", _request_id(request))
    _security_event(request, "password_reset_request", outcome="accepted")
    return {"detail": GENERIC_RESET}


@router.post("/auth/reset-password")
def reset_password(payload: ResetRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    challenge = auth.consume_challenge(db, payload.token, "reset_password")
    if challenge is None or challenge.user_id is None:
        raise auth.AuthApiError(400, "invalid_or_expired_token", "This reset link is invalid, expired, or already used.")
    user = db.get(User, challenge.user_id)
    if user is None:
        db.rollback()
        raise auth.AuthApiError(400, "invalid_or_expired_token", "This reset link is invalid, expired, or already used.")
    user.password_hash = auth.hash_password(payload.new_password)
    auth.revoke_all_sessions(db, user.id)
    _security_event(request, "password_reset", outcome="success", user_id=user.id)
    return {"detail": "Password reset. You can now sign in."}


@router.post("/auth/login")
def login(payload: EmailPassword, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    user = db.execute(
        select(User).where(User.email_normalized == auth.normalize_email(str(payload.email)))
    ).scalar_one_or_none()
    password_ok = user is not None and auth.verify_password(payload.password, user.password_hash)
    if not password_ok or user is None or not user.active:
        _security_event(request, "password_login", outcome="failure")
        raise auth.AuthApiError(401, "invalid_credentials", INVALID_CREDENTIALS)
    if user.email_verified_at is None:
        _security_event(request, "password_login", outcome="unverified", user_id=user.id)
        raise auth.AuthApiError(403, "email_not_verified", "Verify your email before signing in.")
    _security_event(request, "password_login", outcome="success", user_id=user.id)
    return auth.session_response(db, user, request.app.state.settings)


@router.post("/auth/logout")
def logout(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    settings = request.app.state.settings
    auth.revoke_session(db, request.cookies.get(settings.session_cookie_name))
    _security_event(request, "logout", outcome="success")
    response = JSONResponse({"detail": "Logged out."})
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.secure_cookies, httponly=True, samesite="lax")
    response.delete_cookie(settings.csrf_cookie_name, path="/", secure=settings.secure_cookies, httponly=False, samesite="lax")
    response.delete_cookie("novaq_google_nonce", path="/", secure=settings.secure_cookies, httponly=True, samesite="lax")
    return response


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return {"user": auth.user_payload(user)}


def _google_claims(request: Request, db: Session, credential: str) -> dict:
    settings = request.app.state.settings
    if not settings.google_sign_in_enabled or not settings.google_client_id:
        raise auth.AuthApiError(503, "google_sign_in_unavailable", "Google Sign-In is unavailable.")
    raw_nonce = request.cookies.get("novaq_google_nonce")
    if not raw_nonce:
        raise auth.AuthApiError(400, "invalid_google_credential", "Google Sign-In could not be verified.")
    try:
        claims = request.app.state.google_token_verifier.verify(credential, settings.google_client_id)
    except InvalidGoogleCredential as exc:
        raise auth.AuthApiError(401, "invalid_google_credential", "Google Sign-In could not be verified.") from exc
    if (
        not claims.get("sub")
        or not claims.get("email")
        or claims.get("email_verified") is not True
        or claims.get("nonce") != raw_nonce
    ):
        raise auth.AuthApiError(401, "invalid_google_credential", "Google Sign-In could not be verified.")
    challenge = auth.consume_challenge(db, raw_nonce, "google_nonce")
    if challenge is None:
        raise auth.AuthApiError(401, "invalid_google_credential", "Google Sign-In could not be verified.")
    db.commit()
    return claims


@router.post("/auth/google/nonce")
def google_nonce(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    settings = request.app.state.settings
    if not settings.google_sign_in_enabled or not settings.google_client_id:
        raise auth.AuthApiError(503, "google_sign_in_unavailable", "Google Sign-In is unavailable.")
    raw = auth.issue_challenge(
        db, user_id=None, purpose="google_nonce", ttl_minutes=settings.google_nonce_ttl_minutes
    )
    assert raw is not None
    response = JSONResponse({"nonce": raw})
    response.set_cookie(
        "novaq_google_nonce",
        raw,
        max_age=settings.google_nonce_ttl_minutes * 60,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )
    return response


def _google_response(response: JSONResponse, settings) -> JSONResponse:
    response.delete_cookie(
        "novaq_google_nonce", path="/", secure=settings.secure_cookies, httponly=True, samesite="lax"
    )
    return response


@router.post("/auth/google")
def google_login(payload: GoogleCredential, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    claims = _google_claims(request, db, payload.credential)
    subject = str(claims["sub"])
    identity = db.execute(
        select(AuthIdentity).where(
            AuthIdentity.provider == "google", AuthIdentity.provider_subject == subject
        )
    ).scalar_one_or_none()
    if identity is not None:
        user = db.get(User, identity.user_id)
        if user is None or not user.active:
            db.rollback()
            raise auth.AuthApiError(403, "account_inactive", "This account is inactive.")
        identity.last_login_at = datetime.now(timezone.utc)
        db.commit()
        _security_event(request, "google_login", outcome="success", user_id=user.id)
        return _google_response(auth.session_response(db, user, request.app.state.settings), request.app.state.settings)

    email = str(claims["email"])
    normalized = auth.normalize_email(email)
    authoritative = normalized.endswith("@gmail.com") or bool(claims.get("hd"))
    user = db.execute(select(User).where(User.email_normalized == normalized)).scalar_one_or_none()
    if user is not None:
        if not user.active:
            db.rollback()
            raise auth.AuthApiError(403, "account_inactive", "This account is inactive.")
        if not authoritative:
            db.rollback()
            raise auth.AuthApiError(
                409,
                "account_link_required",
                "Sign in with your NovaQ password, then link Google from Account settings.",
            )
        user.email_verified_at = user.email_verified_at or datetime.now(timezone.utc)
    try:
        if user is None:
            user = User(
                email=email.strip(),
                email_normalized=normalized,
                email_verified_at=datetime.now(timezone.utc),
                password_hash=None,
                role="analyst",
                active=True,
            )
            db.add(user)
            db.flush()
        db.add(
            AuthIdentity(
                user_id=user.id,
                provider="google",
                provider_subject=subject,
                email_at_link=email,
                last_login_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        identity = db.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == "google", AuthIdentity.provider_subject == subject
            )
        ).scalar_one_or_none()
        if identity is not None:
            user = db.get(User, identity.user_id)
        else:
            user = db.execute(
                select(User).where(User.email_normalized == normalized)
            ).scalar_one_or_none()
            if user is not None and authoritative:
                try:
                    db.add(
                        AuthIdentity(
                            user_id=user.id,
                            provider="google",
                            provider_subject=subject,
                            email_at_link=email,
                            last_login_at=datetime.now(timezone.utc),
                        )
                    )
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    identity = db.execute(
                        select(AuthIdentity).where(
                            AuthIdentity.provider == "google",
                            AuthIdentity.provider_subject == subject,
                        )
                    ).scalar_one_or_none()
                    user = db.get(User, identity.user_id) if identity is not None else None
            else:
                user = None
        if user is None:
            raise auth.AuthApiError(409, "identity_already_linked", "Google identity is already linked.")
        if user is None or not user.active:
            raise auth.AuthApiError(403, "account_inactive", "This account is inactive.")
    db.refresh(user)
    _security_event(request, "google_login", outcome="success", user_id=user.id)
    return _google_response(auth.session_response(db, user, request.app.state.settings), request.app.state.settings)


@router.post("/account/auth-identities/google")
def link_google(
    payload: GoogleCredential,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    claims = _google_claims(request, db, payload.credential)
    if auth.normalize_email(str(claims["email"])) != user.email_normalized:
        db.rollback()
        raise auth.AuthApiError(409, "account_link_required", "Google email must match your NovaQ email.")
    subject = str(claims["sub"])
    existing_subject = db.execute(
        select(AuthIdentity).where(
            AuthIdentity.provider == "google", AuthIdentity.provider_subject == subject
        )
    ).scalar_one_or_none()
    existing_user = db.execute(
        select(AuthIdentity).where(
            AuthIdentity.user_id == user.id, AuthIdentity.provider == "google"
        )
    ).scalar_one_or_none()
    if existing_subject is not None or existing_user is not None:
        db.rollback()
        raise auth.AuthApiError(409, "identity_already_linked", "Google identity is already linked.")
    db.add(
        AuthIdentity(
            user_id=user.id,
            provider="google",
            provider_subject=subject,
            email_at_link=str(claims["email"]),
            last_login_at=datetime.now(timezone.utc),
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise auth.AuthApiError(409, "identity_already_linked", "Google identity is already linked.") from exc
    _security_event(request, "google_link", outcome="success", user_id=user.id)
    return {"detail": "Google account linked.", "user": auth.user_payload(user)}
