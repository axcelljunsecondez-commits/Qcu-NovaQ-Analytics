# Phase 4 Report: React Frontend (NovaMart)

**Date:** 2026-08-10
**Branch:** `feature/production-saas`
**Plan:** `docs/superpowers/plans/2026-08-10-phase4-react-frontend-plan.md` (11 tasks, all complete)

## Frontend Architecture

- **Stack:** React 19 + TypeScript, Vite 8 (dev/build), Vitest 4 + Testing Library (jsdom), TanStack Query v5, React Router 7 (`createBrowserRouter`), react-i18next (en/tl), Axios (`frontend/src/lib/http.ts` — `/api` base, `withCredentials`, CSRF header injection).
- **Auth:** `AuthProvider` (session cookie + `/auth/me` bootstrap), `RequireAuth` route guard, `RequireRole role="admin"` guard rendering `Forbidden`.
- **State:** Server state via TanStack Query (datasets, scenarios, users); local state for forms; mutations invalidate the relevant query keys.
- **i18n:** Flat-key JSON resources in `frontend/public/locales/{en,tl}/translation.json`, **188 keys each, symmetric** — every string added during Phase 4 was added to both locales.
- **Charts:** Plotly (`plotly.js/dist/plotly` alias, no type-dep bundle) for simulation heatmap/rho-Lq, comparison radar/waterfall; table + metric cards for tabular output.
- **Dev proxy:** Vite proxies `/api` → `http://localhost:8000` (strips `/api` prefix). Production web container (`nginx/`) proxies `/api/` → `api:8000/`; SPA static files are not yet served by the web container (noted in gaps).
- **Constraint adherence:** no queueing math implemented in React — only radar normalization (`computeRadarScores` clamp 0–100, 2-decimal rounding) and ×60/×100 unit conversions for display. No `queueing_engine/` or backend behavior changes.

## Pages Implemented (10)

| # | Route | Page | Unit |
|---|-------|------|------|
| 1 | `/login` | LoginPage | 1 |
| 2 | `/dashboard` | DashboardPage | 1 |
| 3 | `/datasets` | DatasetsPage (upload/validate/delete) | 2 |
| 4 | `/analysis` | AnalysisPage (M/M/1, M/M/c, M/G/c, M/M/K, M/G/K, Erlang-A) | 3 |
| 5 | `/optimize` | OptimizePage (segments from dataset, batch optimize, save scenario) | 4 |
| 6 | `/simulate` | SimulationPage (DES, MC, validate; plotly heatmap) | 7 |
| 7 | `/compare` | ComparisonPage (radar, utilization, servers, wait-time, cost waterfall) | 8 |
| 8 | `/reports` | ReportsPage (dataset/scenario PDF + Excel downloads) | 9 |
| 9 | `/account` | AccountPage (profile, logout) | 9 |
| 10 | `/admin` | AdminPage (users table, create, activate/deactivate) gated by `RequireRole` | 10 |

## API Endpoints Consumed

| Method | Path | Used by |
|--------|------|---------|
| POST | `/auth/login`, `/auth/logout`, GET `/auth/me` | auth |
| GET | `/datasets`, GET `/datasets/{id}`, POST `/datasets` (multipart), DELETE `/datasets/{id}` | datasets |
| POST | `/analysis/{model}` | analysis |
| POST | `/optimize`, `/optimize/batch` | optimize |
| POST | `/simulation/des`, `/simulation/mc`, `/simulation/validate` | simulate |
| GET | `/scenarios`, POST `/scenarios`, GET `/scenarios/{id}` | compare, reports |
| GET | `/reports/datasets/{id}/{pdf\|excel}`, `/reports/scenarios/{id}/{pdf\|excel}` | reports |
| GET | `/admin/users`, POST `/admin/users`, PATCH `/admin/users/{id}` | admin |

All paths verified against live backend mounts; one mismatch found in the parity pass and fixed (users API was mounted at `/admin/users`, not `/users` — see Defects).

## Feature Parity Status

| Capability | Status | Notes |
|------------|--------|-------|
| Upload (CSV/XLSX) | ✅ verified | live upload of a 13-row real-world file, "Input data is valid." |
| Validation (schema + stability) | ✅ verified | missing columns, K<c, non-numeric, unstable-flag paths covered by tests |
| M/M/1 | ✅ verified | stable result + unstable flag (λ>μ) |
| M/M/c | ✅ verified | |
| M/G/c | ✅ verified | |
| M/M/K | ✅ verified | |
| M/G/K | ✅ verified | |
| Erlang-A (M/M/c+M) | ✅ verified | |
| Optimization (staffing, costs) | ✅ verified | live: c 3→4, total cost 612→401 |
| DES simulation | ✅ verified | live run, 609 served / 0 dropped, critical-flag present |
| MC simulation | ✅ verified | live run, failure rate + CI present |
| DES↔analytic validation | ✅ verified | |
| Scenario comparison | ✅ verified | two scenarios saved, list consumed; radar/waterfall computed from results |
| Scenario saving | ✅ verified | |
| PDF report (dataset + scenario) | ✅ verified | valid `%PDF` bytes, correct content-type |
| Excel report (dataset + scenario) | ✅ verified | valid `PK` bytes, correct content-type |
| en/tl localization | ✅ verified | 188 keys symmetric |
| Account page | ✅ verified | email/role/created_at from session, logout |
| Admin (user mgmt, role gate) | ✅ verified | create, deactivate, 409 duplicate, list; analyst sees Forbidden |
| Sidebar / route protection | ✅ verified | `/admin` admin-only; sidebar hides admin link for analysts |

## Test / Gate Results (final battery)

- **Frontend tests:** 56 passed (14 files), jsdom
- **typecheck:** `tsc -b` clean · **lint:** oxlint clean · **build:** Vite `built in 11.3s`
- **Python:** `python -m pytest tests/ -q` → **276 passed** (1 warning: known flaky AppTest timeout — passes on re-run per AGENTS.md)
- **ruff check .** clean · **mypy .** clean (72 files) · **test_imports.py** clean
- **pip-audit -r requirements.txt --strict:** no known vulnerabilities
- **Streamlit E2E:** `tests/test_dashboard_e2e.py` → **15 passed**; `legacy_streamlit/` untouched (git tree clean before final commit)

## Visual / Manual Verification Notes

- Browser manual walk partially performed by the user during the parity pass (login + page navigation confirmed live via API logs).
- Full API-driven flow verified live against the running stack (login → upload → analysis M/M/1 + M/M/c + M/G/c + M/M/K + Erlang-A → optimize → DES → MC → validate → scenario save/list → dataset+scenario PDF/Excel → admin user lifecycle).
- **Defect found during parity pass (fixed):** `frontend/src/api/users.ts` used `/users`; backend mounts the router at `/admin/users`. Fixed (commit `2a420438`). Unit tests had mocked the API module, so they could not catch the path mismatch — caught only by the live walk.
- **User-reported issue during walk (no code defect):** browser carried a stale `novamart_session` cookie from before the API container restart → every mutation (upload/delete/login) returned 403 CSRF mismatch while reads worked. Resolution is client-side (clear cookies / incognito); upload + consumption verified working with a real 13-row CSV through the Vite proxy.

## Known Parity Gaps

1. **POS ingestion is legacy-only** — the CSV/XLSX upload path is the only React ingestion; POS log import remains in `legacy_streamlit/`.
2. **Account password change absent** — Account page shows profile info + logout only.
3. **Scenario comparison requires API-saved scenarios** — the compare page consumes `GET /scenarios`; ad-hoc in-memory comparisons are not offered.
4. **Production web container serves only the API proxy** — the built SPA is served by Vite (dev/preview); `nginx/` needs a static-root config + build artifact copy for a one-container deploy (out of scope for Phase 4).
5. **Analysis page is manual-entry only** — uploaded datasets feed Optimize/Simulate/Reports, not the Analysis page (by design, matches plan Task 3).

## Phase 4 Exit Assessment

All 11 plan tasks complete. Frontend replaces the Streamlit dashboard for all core capabilities with feature parity verified at the API level and in 56 component/unit tests. Python and Streamlit suites remain green (276 + 15). No backend behavior changes were made; one frontend contract fix landed from the parity pass. No Phase 5 work was performed (per plan Step 6).

## Commits

| Commit | Unit |
|--------|------|
| `d9eedab1` | Phase 4 Unit 7: simulation page with DES/MC/validate and plotly chart parity |
| `c598820e` | Phase 4 Unit 8: comparison page with radar, bars, wait-time, waterfall charts |
| `ec0db94a` | Phase 4 Unit 9: reports download page and account profile page |
| `ed04b1b0` | Phase 4 Unit 10: admin user management with role-gated route |
| `2a420438` | Phase 4: fix users API base path to /admin/users (parity pass) |
