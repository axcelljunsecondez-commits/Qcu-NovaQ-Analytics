# AGENTS.md — Agent Instructions

Guidance for AI agents and developers working in this repository: the **NovaMart Queueing Theory Dashboard** (production SaaS + legacy Streamlit + React frontend).

## Repository Layout

- `backend/` — Production FastAPI service (`backend/api/main.py`). Queueing engine under `backend/queueing_engine/` (models, services, simulation, statistics), DB layer under `backend/db/` (SQLAlchemy + Postgres), report generation under `backend/reports/`.
- `frontend/` — React 19 + Vite SPA (React Router, TanStack Query, i18next, Plotly). Builds into `dist/`; production serving via nginx.
- `nginx/` — `nginx.conf` serves the built SPA at `/` and proxies `/api/` → `api:8000` (strips the `/api` prefix).
- `legacy_streamlit/` — Frozen Streamlit dashboard (4 pages). DO NOT change its logic; minimal dead-code cleanup only, and only when explicitly requested. It shares the frontend locale files via `frontend/public/locales/`.
- `tests/` — pytest suite for backend + API + queueing engine.
- `docs/superpowers/` — plans (`plans/`) and design specs (`specs/`) written before implementation.

## Running the Stack

- `docker compose up -d --build` — Postgres (`db`), API (`api`, :8000), web (`web`, :80 — built SPA + API proxy), legacy Streamlit (`legacy`, :8501).
- Frontend dev: `npm run dev` in `frontend/` (Vite :5173, proxies `/api` → `localhost:8000` stripping the prefix).
- Default admin seed: `admin@example.com` / `admin123` (compose default; override via `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `.env`). Seeding is **create-only**: an existing user is never modified. To change an existing admin's password/role, run `docker compose exec api python -m backend.db.seed --email <email> --password <newpass> --force-reset`.

## Gates (run before claiming work complete)

- Backend: `python -m pytest tests/ -x --tb=short` (CI invocation; bare `pytest` resolves to a stale system install — always use `python -m pytest`)
- Lint/type: `ruff check .`, `mypy .`
- Frontend: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build` (in `frontend/`)

## Constraints

- **Queueing-engine contract is frozen**: request/response shapes of `backend/api/` (especially `/simulation/*` and `/optimize/*`) are production contracts — do not change them without a plan. New features must be additive.
- **Single source of truth for model selection**: `backend/queueing_engine/services/model_selection.py` (dispatch: theta → Erlang-A, K+variance → M/G/c/K, K → M/M/c/K, variance → M/G/c, c==1 → M/M/1, else M/M/c). Never re-implement dispatch inline.
- **CSRF flow**: session cookie `novamart_session` is HttpOnly; `novamart_csrf` is JS-readable (httponly=False). The SPA attaches `X-CSRF-Token` on non-GET requests whenever the csrf cookie is present (`frontend/src/lib/http.ts`). The API exempts only `/analysis`, `/simulation`, `/optimize` prefixes.
- **i18n**: any new label/string must be added to BOTH `frontend/public/locales/en/translation.json` and `frontend/public/locales/tl/translation.json` (keys must stay symmetric).
- **Reports use minutes** for wait times (multiply hour-valued Wq by 60 at display time); thresholds and alerts are minutes.
- Never commit secrets or `.env`. No changes to `docker-compose.yml` ports without checking both `web` (nginx) and `api` exposure.
- Work follows the superpowers flow: brainstorm → spec (`docs/superpowers/specs/`) → plan (`docs/superpowers/plans/`) → implement → verify → report.

---

# Session History (context, not instructions)

## Session Summary — CI Debugging & Hardening (2026-05-31)

### Problem
CI workflow was failing with exit code 2 on all Python versions (3.10, 3.11, 3.12).

### Root Cause
Bare `pytest` command in CI resolved to system-installed `pytest` 4.6 (from `apt` on ubuntu-22.04) instead of the pip-installed one. pytest 4.x uses a different test discovery entry point, so all tests were reported as "no tests ran" → exit code 2.

### Fix
- Switched from bare `pytest` to `python -m pytest` — avoids PATH ambiguity, always uses the pip-installed version.
- Also use `python -m pytest` for coverage measurement.

### CI Runs Summary

| Run | Change | Result |
|-----|--------|--------|
| #1-6 | Initial CI attempts | ❌ exit code 2 (system pytest) |
| #7 | Removed hypothesis from install by accident | ❌ exit code 2 (missing hypothesis import) |
| #8 | Added hypothesis back | ✅ **First green** |
| #9 | Switched to `python -m pytest` | ✅ Green |
| #10 | Raised coverage to 75%, pinned deps with `~=`, updated pre-commit | ❌ `scipy~=1.17` lacks wheel for Py3.10 on ubuntu-22.04 |
| #11 | Loosened `scipy~=1.17` → `scipy>=1.14.0` | ✅ **All jobs green** |

### Key Configuration Decisions

#### CI (.github/workflows/ci.yml)
- Use `python -m pytest` instead of bare `pytest` to avoid system PATH conflicts
- Coverage threshold: `--cov-fail-under=75`
- Test dependency constraints: `>=` for scipy (cross-Python compatibility), `~=` for pytest/httpx/hypothesis/pytest-cov
- Pin policy: avoid `~=` for packages that need different versions per Python runtime

#### Pre-commit (.pre-commit-config.yaml)
- ruff: v0.15.12
- pre-commit-hooks: v5.0.1
- Added `ci` section with `autofix_prs: false` and `autoupdate_schedule: monthly`

### Files Changed
- `.github/workflows/ci.yml` — pytest invocation, coverage threshold, dep pins, pip caching, mypy step
- `.pre-commit-config.yaml` — hook versions, ci section, mypy hook
- `.github/dependabot.yml` — automated dep update PRs (pip + actions, weekly)
- `pyproject.toml` — mypy config added
- `queue_models.py`, `simulation.py`, `data_processing.py`, `pos_connector.py`, `test_imports.py` — type annotation fixes

## Session Summary — Cross-Page Consistency & Crash Hardening (2026-08-09)

### Problem
14 tests failing across 5 areas: i18n radio bug, divergent model/cost engines, false validation-success toast, stale validation, and Page 3 crashes.

### Root Causes & Fixes

1. **i18n radio bug (Page 1)** — `st.radio` options were translated label strings, so `data_source == "Import from POS transaction log"` broke under the `tl` locale. Fixed with stable values `["csv", "pos"]` + `format_func` for labels (`pages/1_current_metrics.py`).

2. **Divergent model selection** — `optimization._queue_metrics` and `api._segment_to_record` ignored `theta`, so Page 2/API dropped Erlang-A (M/M/c+M) while Page 1 used it. Added `theta` dispatch → `erlang_a()` in `optimization.py`, threaded through all `_queue_metrics` calls in `optimize_segment`, and added `"theta"` to `_segment_to_record` in `api.py`.

3. **Divergent cost engines** — `costing.py` clamped unstable Wq to 999999 and excluded NaN-Wq rows entirely; `optimization.py` used `UNSTABLE_FIXED_COST` (5000). Unified: both now use `UNSTABLE_FIXED_COST` for inf/NaN/negative Wq; `compute_all_costs` treats Wq as optional (unstable rows still get server+abandonment costs). Also fixed `cost_current`/`cost_optimal` in `optimization.py` to be TOTAL costs (server+wait+abandon), matching the "Total cost" help text on Pages 2/4.

4. **False success toast + stale validation (Page 2)** — `validated_comparison` was never invalidated, so "✅ Plan passed" toast persisted on reruns even with new settings. Added `validation_signature` (JSON of segments + all settings) that clears `validated_comparison` on change, and gated the success toast on `validated_df is not None`.

5. **Page 3 crashes** — `int(seed_text)` raised ValueError on non-numeric input (now `try/except` → `None`); queue-bar HTML multiplied `rho_sim` which can be NaN/None on error rows (now `_safe_rho()` coerces to finite float).

6. **Pre-existing CI blockers** (files untouched by the 5 fixes) — `theme.py` breadcrumb had a mypy arg-type error (`st.session_state.get({...}.get(num))`); `streamlit_app.py:19` had an unsorted import (ruff I001). Both fixed so `mypy .`, `ruff check .`, and CI gates pass repo-wide.

### Test Notes
- Streamlit 1.58 AppTest: `Radio` uses `.set_value()`, not `.select()`; `radio.options` returns formatted labels, so assert stability behaviorally (set_value succeeds + UI appears).
- Full suite: **122 passed, 0 failed** (`python -m pytest tests/ -x --tb=short` — matches CI invocation).
- `ruff check .` and `mypy .` both fully clean.
- One flaky failure observed once under `coverage run` instrumentation (AppTest timeout under slower execution); not reproducible on re-run — watch-list only.
