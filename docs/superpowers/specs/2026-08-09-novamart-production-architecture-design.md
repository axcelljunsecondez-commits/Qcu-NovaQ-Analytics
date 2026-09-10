# NovaMart Production Architecture — Design Spec

- **Date:** 2026-08-09
- **Status:** Approved (user review gate passed; Phase 0 verified 2026-08-09, Phase 1 executing)
- **Scope:** Evolve NovaMart from the current Streamlit prototype into a production-quality internal web application (SaaS-ready foundations)
- **Branch:** `feature/production-saas`

## 1. Context

NovaMart is a queueing-theory analysis and simulation system (M/M/1, M/M/c, M/G/c, M/M/c/K, M/G/c/K, Erlang-A) currently implemented as a 4-page Streamlit dashboard with a pure-Python math core (`queue_models.py`, `simulation.py`, `optimization.py`, `costing.py`, `pos_connector.py`, `report_export.py`), a minimal FastAPI wrapper (`api.py`), 122 passing tests, Docker + CI (ruff/mypy/pytest/pip-audit/coverage), and i18n (en/tl).

### Problems to solve
- No persistence: all state lives in `st.session_state`; no accounts, no saved datasets/scenarios
- No auth, wildcard CORS, no rate limits, CSV/Excel formula injection, an XSS vector in Page 3 queue bars and `toast()`
- Business modules coupled to Streamlit (`data_processing.py`, `i18n`) — untestable outside the UI runtime
- Model dispatch duplicated 3× with conflicting theta precedence; 3 divergent cost engines; 3 divergent MC failure thresholds; `summarize_simulation` empty-branch key mismatch
- Math core numerical-stability gaps (`mmc`/`mmck` raw power terms overflow; Erlang-A 200-state tail cap without warning)
- Known optimizer bugs: ternary search can discard the feasible region (false "no stable plan"); waste-hours removal has no savings>0 guard
- Coverage at 50% vs CI gate (65 in ci.yml, 75 in pyproject.toml — mismatch)
- Streamlit upgrade fragility (hardcoded emotion class hashes in dark-mode CSS)

## 2. Goals

1. Production-quality internal web application with user accounts and role-based access (admin/analyst)
2. Persistence via PostgreSQL: users, sessions, datasets, scenarios, jobs
3. The queueing mathematics becomes a clean, framework-free domain layer — **mathematical behavior unchanged**
4. Mathematical correctness proven against known analytical examples
5. Streamlit app keeps working until the React app reaches feature parity, then is retired
6. SaaS-ready foundations: tenant_id reserved, async job path reserved, containerized deployment

### Non-goals (explicitly deferred)
- Billing/payments/public signup
- LDAP/SSO
- Multi-organization tenancy (schema reserves the column only)
- Real-time collaborative editing

## 3. Key decisions (confirmed with product owner)

| Decision | Choice |
|---|---|
| User model | Internal/enterprise tool first: accounts + roles (admin/analyst), no billing |
| Frontend | FastAPI + React SPA (Vite + TypeScript) |
| Deployment/data | Docker Compose + PostgreSQL |
| Streamlit fate | Kept running in parallel until React parity, then retired |
| Domain layer | Package-per-domain under `queueing_engine/` |

## 4. Target architecture

```
novamart/
├── frontend/                  # React SPA (Vite + TypeScript)  [NEW]
│   └── src/
│       ├── pages/             # Dashboard, Upload, M/M/1, M/M/c, Simulation,
│       │                      #   Comparison, Reports, Account/Admin
│       ├── components/        # Charts, KPI cards, data tables
│       └── api/               # Typed API client
├── backend/
│   ├── api/                   # FastAPI: auth, datasets, analysis, jobs, reports
│   ├── queueing_engine/       # EXTRACTED domain layer (pure Python, no Streamlit)
│   │   ├── models/            # mm1, mmc, mgc, mmck, mgck, erlang_a
│   │   ├── simulation/        # DES + Monte Carlo + validation
│   │   ├── statistics/        # POS GoF tests, Poisson fit, MLE, KS
│   │   └── services/          # optimization, costing, data processing, kpis
│   ├── data/                  # ingestion: CSV/Excel normalization, validation
│   ├── db/                    # SQLAlchemy models + Alembic migrations
│   └── reports/               # PDF/Excel generators (already pure)
├── legacy_streamlit/          # Current app frozen; runs until React parity
├── tests/                     # unit + analytical benchmarks + API + e2e
└── docker-compose.yml         # api + frontend (nginx) + postgres
```

**Invariants**
- `queueing_engine/` imports nothing from Streamlit, FastAPI, or the DB layer
- Math behavior is unchanged by extraction (verified by the existing 122-test suite)
- Formula changes happen ONLY when an analytical benchmark test proves an error
- The legacy Streamlit app's tests (incl. AppTest e2e) stay green through Phase 2

## 5. Domain layer (package-per-domain)

Extracted mechanically in Phase 2 from the existing modules:

| New package | Source | Contents |
|---|---|---|
| `queueing_engine/models` | `queue_models.py` | `mm1`, `mmc`, `mgc`, `mmck`, `mgck`, `erlang_a`, `mmc_priority`, `_result`, validators |
| `queueing_engine/simulation` | `simulation.py` | DES (`simulate_segment(s)`), Monte Carlo (`mc_simulate_segment(s)`), summarizers, status classifier, `validate_with_simulation` (moved from data_processing) |
| `queueing_engine/statistics` | `pos_connector.py` | `load_transactions`, `compute_lambda_mu`, `test_poisson_arrivals`, `fit_service_distribution`, `to_novamart_csv` |
| `queueing_engine/services` | `optimization.py`, `costing.py`, `data_processing.py` | `optimize_segment(s)`, `summarize_optimization`, `build_recommendations`, `compute_segment_costs`, `compute_all_costs`, `compute_cost_summary`, `process_segments`, `compute_kpis`, `get_unstable_messages`, `_classify_utilization_status` |
| `data/` | `app_page_utils.py` | `validate_and_normalize`, `to_segment_records`, `read_uploaded_table`, `sample_segments`, `pretty_metric` (pure parts only) |
| `reports/` | `report_export.py` | `generate_pdf_report`, `generate_excel_report` (drop dead `segment_df` params) |

Rules:
- Replace `@st.cache_data` on business functions with explicit, injectable caching (or `functools.lru_cache` where inputs are hashable); the API layer owns caching policy
- `i18n` translation files (en/tl JSON) migrate to the frontend as `react-i18next` resources; backend error messages stay English (UI-level only)
- `config.py` constants move to `queueing_engine/config.py`; legacy Streamlit re-imports from there

## 6. Backend design (FastAPI + PostgreSQL)

### 6.1 API modules (`backend/api/`)
- `main.py` — app factory, routers, locked-down CORS (explicit origins, no credentials wildcard), middleware (logging, request ID)
- `deps.py` — current-user dependency, role checks (`require_role("admin")`)
- `auth.py` — `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`; argon2-hashed passwords; opaque-token sessions backed by the `sessions` table (SHA-256 token hashes)
- `datasets.py` — `POST /datasets` (upload CSV/Excel, run validation), `GET /datasets`, `GET /datasets/{id}`, `DELETE /datasets/{id}`; upload size limits
- `analysis.py` — `POST /analysis/mm1`, `/analysis/mmc`, `/analysis/mgc`, `/analysis/mmck`, `/analysis/mgck`, `/analysis/erlang_a` (stateless engine calls, Pydantic contracts)
- `optimization.py` — `POST /optimize` (exists), `POST /optimize/batch` (existing surface preserved)
- `simulation.py` — `POST /simulation/des`, `POST /simulation/mc`, `POST /simulation/validate`
- `scenarios.py` — CRUD for saved scenario chains (dataset → settings → results cache)
- `reports.py` — `GET /reports/{id}/pdf`, `GET /reports/{id}/excel` (reuse existing generators, return bytes)
- `users.py` — admin-only user management (create, list, roles, deactivate)

### 6.2 Auth (internal-tool grade)
- Email + password, argon2 (`passlib`/`argon2-cffi`)
- **Sessions (DB-backed):** login issues an opaque random token (`secrets.token_urlsafe(32)`) stored in an HTTP-only `Secure` `SameSite=Lax` cookie; the server persists only `SHA-256(token)` in the `sessions` table (raw token never stored, lookups by hash); logout, password change, and admin deactivation set `revoked_at`; inactive users cannot authenticate (rejected at login, existing sessions invalidated)
- **CSRF:** double-submit token on state-changing endpoints (required because auth is cookie-based)
- No JWT in v1 (documented alternative only if server-to-server claims are ever needed)
- Roles: `admin` (user management) vs `analyst` (tool use)
- **Authorization model:**
  - Row-level ownership: `datasets`, `scenarios`, `jobs` each scoped by `user_id`; every access filters `WHERE user_id = <current user>` at the data-access layer (owner-scoped repository), not only in route handlers
  - User A cannot read or modify User B's datasets/scenarios/jobs; non-owned resources return **404** (not 403 — no existence leaks)
  - Analysts cannot access admin endpoints (`require_role("admin")` → **403**); unauthenticated requests to protected endpoints → **401** (only `POST /auth/login` and `POST /auth/register` are public)
  - All `tenant_id` columns are nullable and unused in v1 with **no authorization semantics** (see §6.3)
- Password reset: admin-initiated reset code (no email infra in v1)

### 6.3 PostgreSQL schema (v1)
- `users` (id, email unique, password_hash, role, active, created_at)
- `sessions` (id, user_id FK, token_hash BYTEA UNIQUE indexed, created_at, last_seen_at, expires_at, revoked_at NULL)
- `datasets` (id, user_id FK, name, source_filename, source_format, row_count, normalized_jsonb, validation_report_jsonb, created_at)
- `scenarios` (id, user_id FK, dataset_id FK, name, settings_jsonb, results_jsonb, created_at)
- `jobs` (id, user_id FK, kind, status, params_jsonb, result_jsonb, error, created_at, finished_at) — v1 runs synchronously; the table reserves the async path
- **`tenant_id` semantics (v1):** columns reserved now on `users`/`datasets`/`scenarios` (nullable, unused in v1) to avoid migration churn later — but they carry **no authorization semantics**. All v1 authorization is `user_id`-scoped. No endpoint, service, or query may infer tenant access from `tenant_id`; it must never appear in access-control paths or filters. Any future use requires a spec update defining its semantics before the column is read anywhere.
- **Result-size boundary:** `normalized_jsonb`/`results_jsonb` are used for payloads ≤ `RESULT_JSONB_MAX_BYTES` (default 512 KB serialized JSON, configurable). Larger simulation outputs (DES/MC traces) are written to an artifact store through a storage abstraction (`ArtifactStore`: `put`/`get`/`delete` — local filesystem outside the repo in v1, S3-compatible object storage is a later config-only swap); the row stores `{"artifact": "<uri>", "summary": {...}}` with summary metrics always inline in JSONB. No code path may write unbounded payloads into a single PostgreSQL row.
- Alembic migrations from day 1

### 6.4 Jobs
- v1: DES/MC endpoints execute synchronously with a generous timeout; heavy runs use `BackgroundTasks` where safe
- v2: worker consuming `jobs` rows (reserved by schema)

## 7. Frontend design (React SPA)

### 7.1 Stack
- Vite + TypeScript + React Router
- Charts: Plotly.js (chart parity with the current app)
- Styling: Tailwind with the existing design tokens (`#1B2A4A` primary, `#E8A838` accent, `#F1F5F9`/`#0F172A` page/sidebar, Poppins/Inter)
- Data: React Query (server cache + invalidation); no business logic client-side — every number comes from the API
- i18n: `react-i18next`, en/tl resources migrated from `i18n/*.json`

### 7.2 Routes
- `/` — dashboard: overview of datasets, saved scenarios, quick links
- `/upload` — CSV/Excel dropzone, inline validation errors, normalized preview table
- `/analyze/mm1`, `/analyze/mmc` — parameter inputs → live metric cards (ρ, P0, Lq, Wq, L, W) + charts
- `/simulate` — DES + MC run controls, progress, results tables/charts
- `/compare` — current vs optimized comparison, cost breakdown, ROI
- `/reports` — PDF/Excel generation + downloads
- `/account` — profile/password; `/admin/users` (admin only)

### 7.3 Performance & responsiveness
- Route-level code splitting; virtualized tables for large datasets; skeleton loaders (reuse shimmer pattern)
- Mobile-first, breakpoints 640/1024/1200; WCAG AA contrast, `prefers-reduced-motion` honored; aria labels on charts

## 8. Legacy Streamlit preservation

- Moved to `legacy_streamlit/` (Phase 2), imports repointed at `queueing_engine`
- Its 122 tests (incl. AppTest e2e) must stay green through Phase 2
- Frozen: no new features; only the two contained security fixes (P3 queue-bar XSS escaping, `toast()` escaping) land while legacy is live
- Deleted in Phase 6 after React parity + e2e coverage of the new UI

## 9. Phased roadmap (each phase: spec → plan → TDD implementation)

| Phase | Deliverable | Exit criteria |
|---|---|---|
| 0 | Baseline commit + feature branch + recorded verification | See Phase 0 verification record (§9.1) |
| 1 | Analytical benchmark tests: λ, μ, ρ, P0, Lq, Wq for M/M/1 and M/M/c against known values; edge cases (ρ→1, λ=0, c=1≡M/M/1) | New benchmark suite green; no formula changes unless a test proves an error (documented if so); all 122 tests still green |
| 2 | Extract `queueing_engine/` packages + `data/` + `reports/`; de-Streamlit `data_processing`/`i18n`; repoint legacy imports; land the 2 XSS fixes | All 122 tests green; `queueing_engine` imports no Streamlit/FastAPI/DB; ruff+mypy clean |
| 2.5 | Correctness workstream (separate sign-off per item): ternary-search feasible-region fix; waste-hours savings>0 guard; unify cost engines; unify dispatch precedence; unify MC thresholds; `summarize_simulation` key consistency | Each fix has a failing test first; behavior changes documented; **no item left unclassified** — every item resolved in the sign-off register (§9.2) as `Fixed` or `Deferred` with rationale |
| 3 | Backend: auth, datasets, scenarios, reports routers; Postgres schema + Alembic; Docker Compose; Pydantic contracts | **Blocked until every Phase 2.5 item is `Fixed` or explicitly `Deferred` in §9.2**; API integration tests green; `docker compose up` serves api+db |
| 4 | React SPA: scaffold → dashboard → upload → M/M/1 → M/M/c → simulate → compare → reports → account/admin; chart parity; i18n | SPA e2e tests green; feature parity checklist vs legacy |
| 5 | Hardening: CORS lockdown, rate limits, upload limits, CSV/Excel injection sanitization, coverage ≥ gate (reconcile 75 vs 65), async DES jobs, logging/observability | Security tests green; coverage threshold met; `pip-audit` clean |
| 6 | Streamlit retirement: delete `legacy_streamlit/` + its e2e tests | No Streamlit references remain; full suite green |

### 9.1 Phase 0 verification record (2026-08-09)

- **git status:** clean — no uncommitted changes (verified before Phase 1 began)
- **Baseline commit:** `bdff4374db05088077e29fcd93fa0efc45280d37` ("Harden cross-page consistency and CI gates"); current HEAD `13806bc9` (design spec commit)
- **Branch:** `feature/production-saas`
- **Test command:** `python -m pytest tests/ -x --tb=short` (identical to ci.yml invocation)
- **Test result:** 122 passed, 0 failed, 1 warning (StarletteDeprecationWarning re: httpx2) in 17.72s — re-run and recorded at Phase 1 start
- **Lint:** `ruff check .` → "All checks passed"
- **Type check:** `mypy . --config-file=pyproject.toml` → "Success: no issues found in 26 source files"
- **Runtime:** Python 3.13.13 (local dev — NOT in CI matrix 3.10/3.11/3.12, lint job 3.11; pyproject mypy `python_version = 3.11`, ruff target py311) — local-vs-CI parity watch item
- **Key dependencies** (pip freeze, 2026-08-09): streamlit 1.58.0, plotly 6.7.0, pandas 3.0.3, numpy 2.4.6, openpyxl 3.1.5, simpy 4.1.2, reportlab 4.5.1, fastapi 0.136.3, uvicorn 0.48.0, scipy 1.17.1, pytest 9.0.3, pytest-cov 7.1.0, httpx 0.28.1, hypothesis 6.155.1, ruff 0.15.15, mypy 2.1.0, itsdangerous 2.2.0
- **Known watch item:** one flaky AppTest timeout observed once under `coverage run` instrumentation; not reproducible on re-run

### 9.2 Phase 2.5 sign-off register

**Rule:** Phase 3 may not begin until every item below is `Fixed` (test-first) or explicitly `Deferred` (product-owner sign-off + rationale recorded here). No item may be left unclassified.

| # | Item | Evidence | Status | Sign-off |
|---|---|---|---|---|
| 1 | Ternary-search feasible-region fix | `optimization.py` search can discard the feasible region → false "no stable plan" at peak load | *pending* | — |
| 2 | Waste-hours removal savings>0 guard | can recommend cost-increasing removals ("save ₱-X") | *pending* | — |
| 3 | Unify cost engines | `compute_kpis` used `λ×10×cost`, others `UNSTABLE_FIXED_COST`; unstable-Wq rows treated inconsistently — **largely fixed in `bdff4374`** (both now use `UNSTABLE_FIXED_COST`, Wq optional); verify + lock with tests | *pending* | — |
| 4 | Unify model-dispatch precedence | theta ignored by some dispatch paths — **fixed in `bdff4374`** (theta → `erlang_a()` threaded through `optimize_segment` + `api._segment_to_record`); verify + lock with tests | *pending* | — |
| 5 | Unify MC failure thresholds | three divergent constants (0.75/0.85/0.05) + PASS 0.10 | *pending* | — |
| 6 | `summarize_simulation` empty-branch key consistency | empty branch returns keys consumers crash/NaN on | *pending* | — |

## 10. Risks & mitigations

1. **Phase 1 discovers a formula error** → change only with a failing analytical test; document; cascade-check optimization/costing expectations (some tests encode current behavior, e.g., `UNSTABLE_FIXED_COST` parity)
2. **Divergence bugs** (ternary-search false negative, negative-savings recommendation) → fast-tracked in Phase 2.5 with test-first fixes
3. **Blended-rate fallback ₱1.0/server** biases optimization toward hiring → keep default, document; revisit in Phase 5
4. **Coverage 50% vs gate** → lift during Phase 2 (extracted services are easily unit-tested); reconcile pyproject 75 vs ci.yml 65
5. **Greenfield DB** → no legacy data migration risk
6. **Streamlit version fragility** → frozen legacy; new frontend independent

## 11. Preservation list

- `queue_models.py` math — especially Erlang-A log-domain implementation
- Simulation warm-up logic (adaptive warm-up, area-under-curve split)
- POS goodness-of-fit statistics (chi-squared, KS, MLE)
- PDF/Excel generators (already return `BytesIO`)
- `config.py` constants (relocated, not redefined)
- The 122-test suite + Phase 1 analytical benchmarks

## 12. Testing strategy

- Unit: `queueing_engine` packages (no framework imports) — expanded in Phase 2
- Analytical benchmarks: `tests/analytical_benchmarks.py` (Phase 1) — fixed known-value assertions with tight tolerances
- API: httpx against the FastAPI app (existing pattern in `test_api.py`)
- Frontend: Vitest + React Testing Library for components; Playwright e2e for workflows (Phase 4)
- CI: existing workflows extended with backend/frontend jobs; `pip-audit` kept

## 13. Acceptance criteria (overall)

1. Users can log in, upload datasets, run M/M/1 and M/M/c analysis, simulation, comparison, and reports in the React app
2. Analytical benchmarks prove the math against textbook values
3. The domain layer is framework-free and unit-tested; math behavior unchanged from the verified baseline
4. All security findings from the analysis are remediated (XSS, CSV/Excel injection, CORS, rate limits, upload limits)
5. Docker Compose deploys the full stack; CI green end-to-end
6. Streamlit legacy retired with no feature regression
