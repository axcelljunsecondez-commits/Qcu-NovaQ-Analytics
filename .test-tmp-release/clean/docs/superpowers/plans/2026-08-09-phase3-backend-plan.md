# Phase 3 — Backend Foundation Implementation Plan (2026-08-09)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI + PostgreSQL backend (auth, datasets, analysis, optimization, simulation, scenarios, reports, users) per the approved NovaMart architecture spec §6, with DB-backed sessions (roadmap correction: no JWT), Alembic migrations, Docker Compose, and full API integration tests.

**Architecture:** New `backend/api/`, `backend/db/` packages alongside the existing framework-free `backend/queueing_engine/`, `backend/data/`, `backend/reports/`. API routers are thin adapters over the domain layer — no business math in routes. Legacy root `api.py` and `legacy_streamlit/` untouched (156 tests + 15 E2E stay green).

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL (psycopg3) / SQLite for tests, argon2-cffi, httpx TestClient, Docker Compose.

## Global Constraints

- Existing 156 tests + 15 Streamlit E2E must stay green; queueing_engine stays framework-free.
- No business mathematics in API routes; no formula changes.
- No Phase 4 (React), no public signup, no billing, no multi-tenant authorization (tenant_id reserved, never in access-control paths).
- The `validate_with_simulation` theta/variance/K simplification stays as-is (explicitly deferred).
- V1 auth: email+password, argon2, DB-backed opaque sessions, HTTP-only cookie (Secure flag via env), logout revocation, inactive users rejected, admin/analyst roles, 401/403/404 semantics per spec §6.2 (404 for non-owned resources — no existence leaks).
- Per unit after implementation: relevant tests, full suite, E2E, ruff, mypy, commit.

---

### Unit A — Dependencies + DB layer + Alembic

**Files:**
- Modify: `requirements.txt` (+ sqlalchemy, alembic, psycopg[binary], argon2-cffi)
- Create: `backend/db/__init__.py`, `backend/db/base.py`, `backend/db/models.py`, `backend/db/session.py`, `backend/db/artifacts.py`, `backend/db/seed.py`
- Create: `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`, `migrations/versions/0001_create_initial_tables.py`
- Test: `tests/test_migrations.py`, `tests/test_artifacts.py`

Models (per spec §6.3): `users` (id, email unique, password_hash, role, active, tenant_id nullable, created_at), `sessions` (id, user_id FK, token_hash LargeBinary(32) unique, created_at, last_seen_at, expires_at, revoked_at nullable), `datasets` (id, user_id FK, name, source_filename, source_format, row_count, normalized_json, validation_report_json, tenant_id nullable, created_at), `scenarios` (id, user_id FK, dataset_id FK nullable, name, settings_json, results_json, tenant_id nullable, created_at), `jobs` (id, user_id FK, kind, status, params_json, result_json, error, created_at, finished_at). JSON columns use `JSON().with_variant(JSONB(), "postgresql")`.

`session.py`: `DATABASE_URL` env default `postgresql+psycopg://novamart:novamart@localhost:5432/novamart`; `create_engine_for(url)`; module engine; `SessionLocal`; `get_db()` dependency.

`artifacts.py`: `ArtifactStore` protocol + `LocalFileArtifactStore(root)` (put/get/delete by uuid4 hex name) — reserved for >512KB payloads (spec §6.3).

`seed.py`: `python -m backend.db.seed --email --password --role` idempotent admin bootstrap.

Tests: `test_migrations.py` runs `alembic upgrade head` on a tmp sqlite file then asserts all 5 tables exist; `test_artifacts.py` covers put/get/delete + missing-file error.

### Unit B — Auth + CSRF + middleware

**Files:**
- Create: `backend/api/__init__.py`, `backend/api/settings.py`, `backend/api/auth.py`, `backend/api/deps.py`, `backend/api/main.py`
- Test: `tests/test_auth_api.py`

`settings.py`: session_cookie_name, csrf_cookie_name, session_ttl_hours (24), secure_cookies (env, default off for dev/test), allowed_origins (env CSV), max_upload_bytes (5 MB), result_jsonb_max_bytes (512 KB), artifact_root (env, optional).

`auth.py`: argon2 hash/verify; `create_session(db,user_id)` → `secrets.token_urlsafe(32)` + SHA-256 hash stored; `get_session_user(db, token)` → session lookup by hash, `revoked_at is None`, `expires_at > now`, `user.active`; revoke on logout.

`deps.py`: `get_current_user` (401), `require_role("admin")` (403).

`main.py` `create_app()`: explicit-origins CORS; request-ID middleware (X-Request-ID, echoed + logged); structured request log middleware; CSRF double-submit middleware (non-safe methods with session cookie must send matching `X-CSRF-Token` header — 403 otherwise); `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `GET /health`. Login sets session + csrf cookies; logout revokes + clears. Invalid creds/inactive → 401 generic.

Tests: login success (cookies set, /auth/me works), wrong password 401, inactive user 401, logout revokes (session unusable), expired session 401 (insert expired row), CSRF missing header 403 on POST with session, X-Request-ID echoed, /health public.

### Unit C — Admin users router

**Files:** Create: `backend/api/users.py`; Test: `tests/test_users_api.py`
Endpoints (admin only): `POST /admin/users` (email, password, role) 201; `GET /admin/users`; `GET /admin/users/{id}`; `PATCH /admin/users/{id}` (role, active — deactivation revokes all user's sessions). Analyst → 403; nonexistent → 404.

### Unit D — Datasets + upload security

**Files:**
- Create: `backend/data/uploads.py`, `backend/api/datasets.py`
- Test: `tests/test_datasets_api.py`, `tests/test_uploads.py`

`uploads.py`: `parse_upload(filename, data: bytes)` → extension allowlist (.csv/.xlsx/.xls), size limit, magic-byte check (xlsx `PK\x03\x04`; CSV no NUL bytes), `pd.read_csv`/`read_excel` via `backend/data/ingestion.read_uploaded_table` semantics; `sanitize_workbook(df)` — prefix `'` to string cells starting with `= + @ - \t \r` (formula-injection protection); `safe_stem(filename)` — basename only, strip control chars.

`datasets.py`: `POST /datasets` (multipart) → validation via `validate_and_normalize`, store normalized records + validation report; `GET /datasets`; `GET /datasets/{id}` (own only, 404 otherwise); `DELETE /datasets/{id}` (own only, cascade scenarios). Never write uploads to disk; safe source_filename only.

Tests: valid CSV upload → 201 + validation ok; bad extension → 422; oversize → 413; binary garbage as .csv → 422; formula-injection cells sanitized (verify stored JSON has `'=` prefix); retrieval returns normalized rows; delete; cross-user 404.

### Unit E — Analysis / Optimization / Simulation routers

**Files:** Create: `backend/api/analysis.py`, `backend/api/optimization.py`, `backend/api/simulation.py`; Tests: `tests/test_analysis_api.py`, `tests/test_optimization_api.py`, `tests/test_simulation_api.py`

- `POST /analysis/{model}` for mm1, mmc, mgc, mmck, mgck, erlang_a — Pydantic input (lambda, mu, c, variance?, K?, theta?) → direct `backend.queueing_engine.models` calls, full metrics dict returned.
- `POST /optimize` + `POST /optimize/batch` — thin wrapper over `services.optimization.optimize_segment(s)` with the existing surface (server_cost_per_hr, max_servers, target_rho); Pydantic response model mirroring engine output.
- `POST /simulation/des`, `/simulation/mc`, `/simulation/validate` — wrappers over `simulation.simulate_segments`, `mc_simulate_segments`, `validate_with_simulation` (records in, records out; no theta/variance/K changes per deferral).

Tests: each analysis model 200 + known metric shape; optimize matches engine output; batch N segments; des/mc/validate return expected columns; invalid params 422.

### Unit F — Scenarios router

**Files:** Create: `backend/api/scenarios.py`; Test: `tests/test_scenarios_api.py`
CRUD: `POST /scenarios` (name, dataset_id?, settings, results — result payload ≤ result_jsonb_max_bytes else 413), `GET /scenarios`, `GET /scenarios/{id}`, `PATCH /scenarios/{id}`, `DELETE /scenarios/{id}`; own-only (404). Tests: create/retrieve/update/delete, size boundary, cross-user isolation.

### Unit G — Reports router

**Files:** Create: `backend/api/reports.py`; Test: `tests/test_reports_api.py`
Reuse `backend/reports/report_export.generate_pdf_report` / `generate_excel_report` unchanged. `GET /reports/datasets/{id}/pdf|excel` (from stored normalized data via `process_segments`+`compute_kpis`), `GET /reports/scenarios/{id}/pdf|excel` (from `results_json` comparison records via `summarize_optimization`+`build_recommendations`). Own-only; bytes with correct media_type (application/pdf, xlsx). Tests: 200 + non-empty bytes + content-type + cross-user 404.

### Unit H — Docker Compose

**Files:** Modify: `Dockerfile` (CMD → `legacy_streamlit/streamlit_app.py`), `docker-compose.yml`; Create: `Dockerfile.api`, `nginx/nginx.conf`, `nginx/Dockerfile` (placeholder), `backend/api/entrypoint.sh` (seed admin from env, run uvicorn)

Compose services: `db` (postgres:16-alpine, healthcheck, volume), `api` (build Dockerfile.api, depends_on db healthy, env DATABASE_URL/ADMIN_*/SECURE_COOKIES=1, port 8000), `web` (nginx placeholder proxying /api → api:8000, port 80), `legacy` (existing Streamlit service with corrected CMD). Verify `docker compose config` validates; attempt `docker compose up -d db api` (daemon availability permitting) + `GET /health`.

### Unit I — Final verification + report

- Full battery: `python -m pytest tests/ -x --tb=short`, E2E, `python -m ruff check .`, `python -m mypy .`, `python test_imports.py`, `pip-audit -r requirements.txt --strict`
- Report: schema, migrations, routes, auth, authorization tests, isolation tests, upload security, docker status, test counts, known limitations, exit assessment.

## Risk register

| Risk | Mitigation |
|---|---|
| Docker daemon unavailable locally | Write + `docker compose config` validate; attempt daemon start; document if unverifiable |
| Secure cookies break TestClient (http) | `settings.secure_cookies` env-gated (off in tests/dev, on in compose) |
| SQLite vs Postgres type drift | JSON variant/JSONB; LargeBinary for hashes; run tests on sqlite, migration test runs alembic head |
| Existing `api.py` root module vs new `backend/api` package | Distinct names; legacy app untouched, its tests stay green |
| 512KB result boundary rejected in tests | Size limit configurable via settings; tests use tiny override |
