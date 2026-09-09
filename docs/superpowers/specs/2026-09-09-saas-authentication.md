# NovaQ SaaS authentication design

## Goal and invariants

Extend the existing opaque-session authentication system with public registration, mandatory email verification, password recovery, and Google Identity Services. Every successful login resolves to the existing `users.id` and calls the same session-creation and cookie code. Roles, ownership, analytical routes, and queueing behavior remain unchanged.

## Existing architecture

- FastAPI currently performs password login in `backend/api/main.py` using Argon2 helpers from `backend/api/auth.py`.
- A random opaque token is stored only as a SHA-256 digest in `sessions`; `novaq_session` is HttpOnly and `novaq_csrf` is readable by the SPA.
- Mutations carrying a session cookie require the double-submit CSRF header except the three stateless calculation route families.
- `get_current_user` rejects missing, expired, revoked, or inactive sessions; role guards operate on the resolved `User`.
- React's `AuthProvider` owns the `/auth/me`, login, and logout state. `RequireAuth` retains the protected return destination. The post-login landing page is `/analyses`.
- Analysis workspaces, datasets, scenarios, and jobs are owned by `users.id`; no authentication-provider identifier is referenced by analytical data.

## Data model

Revision `0003` extends `users` with required unique `email_normalized`, nullable `email_verified_at`, and nullable `password_hash`. The normalization policy is Unicode-aware `strip().casefold()` and is shared by login, registration, admin creation, seeding, recovery, and Google matching. Existing rows are backfilled as verified without changing hashes, IDs, roles, activity, tenants, or ownership. The migration aborts before uniqueness is added when multiple legacy user IDs normalize to one address and reports only normalized addresses and affected IDs.

`auth_identities` stores the permanent `(provider, provider_subject)` key, currently Google `sub`, plus the linked user, email-at-link, creation time, and last login. A user may have at most one identity per provider.

`auth_challenges` stores only SHA-256 digests for `verify_email`, `reset_password`, and `google_nonce`. Challenges have expiry and consumption timestamps. Replacement email/reset challenges consume outstanding challenges of the same purpose. Conditional updates consume a challenge exactly once. Google nonce rows may have no user; other purposes require a user at the service boundary.

## Email and token flows

Registration always returns a generic eligibility response and never creates a session. A new active analyst receives an unverified account and verification challenge. Existing verified accounts are not disclosed; active unverified accounts may receive a replacement subject to cooldown and hourly limits. A real email-delivery failure returns a temporary-service error because confirmation is mandatory.

Email links place raw tokens in URL fragments. The SPA copies the fragment into memory, calls `history.replaceState` immediately, and submits it only by POST. Verification marks the user verified and consumes all outstanding verification challenges without creating a session.

Forgot-password responses are always generic. Eligible active, verified users—including Google-only users—receive reset challenges. A valid reset sets an Argon2 hash and revokes every session. Tokens are single-use and never logged in production.

Email delivery is behind an `EmailSender` protocol. SMTP is the production implementation; tests inject an in-memory fake. A local console sender is permitted only outside production. Production startup requires an HTTPS public URL, SMTP mode, and complete SMTP settings.

## Google sign-in and linking

The SPA requests a five-minute server nonce. NovaQ stores its digest and sets the raw nonce in a short-lived HttpOnly SameSite=Lax cookie. Google Identity Services receives that nonce. The backend verifies the full credential with the official `google-auth` library and independently requires configured availability, exact audience, approved issuer, expiry, `sub`, verified email, and nonce equality. The nonce cookie and database challenge must both match and the challenge is atomically consumed before a NovaQ session is created. No Google access or refresh token is requested or stored.

Resolution order is identity `(google, sub)`, then normalized verified Google email. Gmail addresses and verified Workspace addresses with `hd` may auto-link. An existing third-party-domain collision returns `account_link_required`; the signed-in Account flow may link it only after a fresh nonce and an exact normalized email match. Google claims never reactivate a user, assign admin, replace the NovaQ email, or move ownership.

## API and errors

Public endpoints are `/auth/register`, `/auth/verify-email`, `/auth/resend-verification`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/config`, `/auth/google/nonce`, and `/auth/google`. Explicit linking is `POST /account/auth-identities/google`. Existing `/auth/login`, `/auth/logout`, `/auth/me`, and `/account/password` remain compatible.

Stable error bodies use `{code, detail}` for `invalid_credentials`, `email_not_verified`, `invalid_or_expired_token`, `google_sign_in_unavailable`, `invalid_google_credential`, `account_link_required`, `identity_already_linked`, `account_inactive`, and `rate_limited`. Enumeration-sensitive endpoints retain generic success bodies.

## Frontend

The approved login layout adds Google, registration, recovery, and resend links without changing the post-login destination. `/register`, `/verify-email`, `/forgot-password`, and `/reset-password` are public routes. Google success writes the same `['me']` query state as password login. Account shows verified state and authentication methods, keeps current-password change for password users, offers reset-based Set Password for Google-only users, and supports explicit Google linking.

## Security and operations

Password creation/replacement accepts 8–128 characters; legacy shorter passwords remain valid at login. Request schemas cap field sizes. Raw passwords, credentials, tokens, nonces, JWT claims, and SMTP secrets are never logged. Google remains hidden and fails closed when disabled. Required environment variables and Google Console Authorized JavaScript Origins are documented; no client secret is used.
