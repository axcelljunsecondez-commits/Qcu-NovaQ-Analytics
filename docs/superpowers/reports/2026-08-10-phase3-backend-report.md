# Phase 3 Report: Production Backend Foundation

**Date:** 2026-08-10
**Branch:** `feature/production-saas`
**Plan:** `docs/superpowers/plans/2026-08-09-phase3-backend-plan.md`
**Spec:** `docs/superpowers/specs/2026-08-09-novamart-production-architecture-design.md`

## Summary

Phase 3 delivered the FastAPI + PostgreSQL backend foundation for NovaMart: database schema with Alembic migrations, session-based authentication with CSRF protection, role-based admin user management, datasets with upload security, compute APIs over the unchanged queueing engine, scenarios, PDF/Excel reports, and a Docker Compose stack. All nine plan units (A–I) are complete.

## Database Schema

Tables created by migration `0001_create_initial_tables` (`migrations/versions/`):

- **users** — id, email (unique), password_hash (argon2), role (admin/analyst), active, created_at, updated_at
- **sessions** — id, user_id FK, token_hash (SHA-256 of session token), expires_at, revoked_at, created_at
- **datasets** — id, user_id FK, name, source_filename, source_format, row_count, validation_json, normalized_json (JSON/JSONB), created_at; cascade-deletes scenarios
- **scenarios** — id, user_id FK, dataset_id FK nullable, name, settings_json, results_json (JSON/JSONB), created_at, updated_at
- **job_queue** — id, user_id FK, kind, payload_json, status, error, created_at, updated_at

`tenant_id` is reserved on all resource tables per spec §6.3. JSON columns use a JSONB variant on PostgreSQL, plain JSON on SQLite (tests). `backend/db/models.py`, `backend/db/session.py` (default URL `postgresql+psycopg://novamart:novamart@localhost:5432/novamart`), `backend/db/artifacts.py` (local filesystem ArtifactStore with path-guard against `/`, `\`, `..`), `backend/db/seed.py` (admin bootstrap CLI).

## Migrations

- Alembic configured (`alembic.ini` with `path_separator = os`), env.py wired to `Settings().database_url`.
- Verified locally: upgrade head, downgrade base, re-upgrade (idempotent) on fresh SQLite; upgrade on real PostgreSQL 16 inside the Docker stack (`tests/test_migrations.py`).

## API Routes

Base prefix: none (mounted at root; nginx proxies `/api/`).

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | /health | none | Liveness |
| POST | /auth/login | none | Session + CSRF cookie issue |
| POST | /auth/logout | session | Session revocation |
| GET | /auth/me | session | Current user |
| POST | /admin/users | admin | Create user (201/409/422) |
| GET | /admin/users | admin | List users |
| GET/PATCH | /admin/users/{id} | admin | Get/update (role, active; deactivation revokes sessions) |
| POST | /datasets | session | Multipart upload (413/422) |
| GET | /datasets | session | Own datasets |
| GET/DELETE | /datasets/{id} | session | Own-only (404), cascade delete |
| POST | /analysis/{model} | session | mm1, mmc, mgc, mmck, mgck, erlang_a |
| POST | /optimize | session | Single-segment optimization |
| POST | /optimize/batch | session | Batch optimization (27-key rows) |
| POST | /simulation/des | session | DES simulation |
| POST | /simulation/mc | session | Monte Carlo simulation |
| POST | /simulation/validate | session | Simulate-vs-theoretical validation |
| POST | /scenarios | session | Create scenario (dataset_id FK validated) |
| GET | /scenarios, /scenarios/{id} | session | Own-only (404) |
| PATCH/DELETE | /scenarios/{id} | session | Update/delete |
| GET | /reports/datasets/{id}/{format} | session | pdf, excel from dataset (own-only) |
| GET | /reports/scenarios/{id}/{format} | session | pdf, excel from scenario results (own-only) |

## Authentication & Security

- **Sessions:** opaque random token (HttpOnly cookie `novamart_session`, 24h TTL); DB stores only SHA-256 hash; logout and admin deactivation revoke immediately (`sessions.revoked_at`).
- **CSRF:** double-submit pattern — plaintext token cookie `novamart_csrf` echoed via `X-CSRF-Token` header on all non-safe requests holding a session cookie. Stateless compute prefixes `/analysis`, `/simulation`, `/optimize` are exempt (they mutate nothing).
- **Cookies:** SameSite=Lax always; `Secure` gated by `SECURE_COOKIES` env (off in local compose over http, on for TLS deployments).
- **Passwords:** argon2id via argon2-cffi; no plaintext anywhere.
- **Ownership isolation:** all resource reads/writes scoped to the authenticated user; non-owned resources return 404 (never leak existence).

## Isolation Tests

`tests/test_{auth,users,datasets,uploads,analysis,optimization,simulation,scenarios,reports,migrations,artifacts}_api.py` cover cross-user dataset and scenario 404s, duplicate email 409s, role-guarded admin endpoints, deactivation session revocation, oversize upload 413s, and report ownership 404s.

## Upload Security

- Extension allowlist (.csv, .xlsx, .xls) **plus** content validation: ZIP magic bytes `PK\x03\x04` for xlsx, NUL-byte heuristic for csv.
- Size cap enforced at read time (5 MB default; `MAX_UPLOAD_BYTES` overridable) → 413.
- Formula-injection sanitization: cells starting with `= + @ - \t \r` are prefixed with `'`; filenames sanitized (spaces→underscores, no path separators).

## Docker Status

`docker-compose.yml`: db (postgres:16-alpine, healthcheck, named volume), api (`Dockerfile.api`, alembic upgrade + admin seed on start, port 8000), web (nginx placeholder proxying `/api` → api:8000, port 80), legacy (root `Dockerfile`, CMD fixed to `legacy_streamlit/streamlit_app.py`, port 8501).

Live-verified on this machine: `docker compose config` valid; db+api+web up; login → `/auth/me`, `/admin/users`, `/optimize`, multipart `/datasets`, `/reports/datasets/{id}/pdf` (3.9 KB PDF) all succeeded over the running stack. Legacy streamlit image not built locally (unchanged behavior; CMD path fix only).

## Test Counts

| Stage | Tests |
|---|---|
| Phase 2.5 baseline | 156 |
| + Unit A (migrations, artifacts) | 167 |
| + Unit B (auth, middleware) | 183 |
| + Unit C (admin users) | 200 |
| + Unit D (datasets, uploads) | 227 |
| + Unit E (analysis/optimization/simulation) | 252 |
| + Unit F (scenarios) | 265 |
| + Unit G (reports) | **276** |

Final battery (Unit I): 276 passed; ruff clean; mypy clean (72 files); `test_imports.py` clean; `pip-audit -r requirements.txt --strict` — no known vulnerabilities.

## Limitations / Notes

- `job_queue` table exists but no async job runner (not in Phase 3 scope); unused.
- Scenario reports require stored comparison rows (`results.comparison` or `results.results` list); scenarios without them return 422.
- ArtifactStore is local-filesystem only; S3/GCS adapter left for a later phase.
- Local dev uses SQLite (tests) and PostgreSQL (compose); `Settings()` reads env at construction.
- Legacy Streamlit service is unchanged apart from the Docker CMD path fix.

## Exit Assessment

Phase 3 exit criteria met: schema+migrations committed and re-runnable; all routers covered by tests; 276 tests + 15 E2E green; lint/type/import/security checks clean; full stack verified live via Docker Compose against PostgreSQL. No open blockers. Stop per phase instructions — subsequent work requires a new plan.
