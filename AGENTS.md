# AGENTS.md — Agent Instructions

Guidance for AI agents and developers working in this repository: the **NovaQ — Queueing Analytics**, a web-based queueing analytics, simulation, and service-operations optimization system with a React frontend and FastAPI backend.

## Required Context

Before substantial work, read:

1. `AGENTS.md`
2. `memory.md`
3. `handoff.md`
4. Relevant files under `docs/`
5. Relevant existing Superpowers spec or plan when one exists

Use `memory.md` for durable project decisions and `handoff.md` for the current development state.

Treat the current repository state as authoritative over old session history.

## Mandatory Zero-Fabrication Engineering Protocol

This protocol governs all technical work on NovaQ. This section is its only copy: `CLAUDE.md` imports this file, and skills and other documents refer to this section instead of restating it.

Your primary obligation is to preserve engineering correctness, mathematical validity, analytical traceability, data integrity, reproducibility, and existing verified functionality.

**Zero fabrication is mandatory. Never substitute plausible assumptions for evidence.** The protocol sets evidence and verification requirements; it does not guarantee error-free work.

### 1. Repository Truth and Evidence

Before answering technical questions or modifying code:

- Read the relevant repository instructions and project context.
- Inspect actual source code, configurations, dependencies, database schemas, and relevant tests.
- Verify the behavior of the affected components.
- Do not treat previous AI responses, conversation summaries, documentation, or project memory as proof of current implementation.

If the repository contradicts previous context, report the discrepancy.

Every material technical claim needs identifiable evidence: inspected source code, applicable tests and their actual results, verified configuration, approved project specifications, reproducible mathematical derivations, relevant experimental observations or validated datasets, or official documentation when external behavior must be established. Cite the source file, function, line range, test, or command output whenever practical. Never fabricate a reference.

### 2. Evidence Classification

Label claims with:

- VERIFIED — Directly established from inspected code, actual data, reproducible calculations, or executed tests.
- APPROVED SPECIFICATION — An authoritative project requirement approved by the product owner; not proof that it is implemented.
- REPORTED — Described by the user or documentation but not independently verified.
- PROPOSED — A requested change not yet implemented.
- INFERRED — A reasoned interpretation that is not directly established.
- NOT TESTED — Behavior that has not been executed or independently validated.
- UNKNOWN — Required information that has not been established.
- CONFLICTING — Evidence is inconsistent.

Only VERIFIED claims may be presented as verified. Never silently convert UNKNOWN into VERIFIED, and never turn an approved specification into an implementation claim without inspecting the implementation.

### 3. No Invented Facts

Never fabricate:

- Existing source files, functions, APIs, or database fields.
- Implemented features or system behavior.
- Arrival rates, service rates, or service-time distributions.
- Staffing schedules or operational constraints.
- Queueing formulas or assumptions.
- Optimization results or feasibility.
- Monte Carlo or discrete-event simulation results.
- Waiting times, utilization, costs, or customer counts.
- Test execution, passing tests, commits, pushes, or deployment status.

If necessary information is unavailable, explicitly identify it as UNKNOWN.

### 4. Engineering Scope Control

Identify exactly what the task requires. Before editing:

1. Identify the defect or approved requirement.
2. Locate the responsible implementation.
3. Identify dependent contracts and tests.
4. Establish the permitted file scope.
5. Determine the expected observable outcome.

Do not modify unrelated files, formulas, simulation algorithms, optimization objectives, constraints, API contracts, database schemas, or user workflows unless explicitly required and authorized. Do not introduce unrelated refactors or architecture changes.

Do not silently change existing analytical semantics to make a requested feature appear functional. Do not change an API contract merely to make a frontend test pass, and do not alter test expectations to conceal incorrect implementation behavior.

### 5. Protected Mathematics

Do not silently alter:

- Queueing formulas and central model selection.
- Arrival-rate and service-time calculations.
- Server and lane definitions.
- Utilization and waiting-time calculations.
- Optimization objectives, constraints, and cost functions.
- Discrete-event simulation behavior and Monte Carlo methodology.
- Statistical confidence-interval definitions.
- Scenario comparison calculations.

A change to mathematical behavior requires separate authorization, documented justification, independent reference cases, and regression verification. A governance-only or documentation-only task never authorizes a mathematical change.

For any analytical change:

- Verify equations and model assumptions.
- Verify units and dimensional consistency.
- Verify input provenance.
- Check boundary conditions.
- Validate applicable feasibility constraints.
- Reproduce numerical results.
- Compare against independent reference cases where available.

Never claim mathematical correctness solely because software tests pass.

### 6. Data Integrity

Do not invent observations, manufacture arrival or service samples, replace missing values with zero without an approved rule, silently modify source data, conceal reconciliation differences, substitute hypothetical results for actual experimental outputs, or treat missing records as proof of zero demand.

Every data-related conclusion must name the dataset, the transformation, the units, and the aggregation period.

### 7. Supported Analytical Conclusions

Every analytical conclusion must come from the actual scenario and the relevant computation. Keep these apart: current operational measurements, analytical model estimates, optimization outputs, DES results, Monte Carlo estimates, validation results, and decision-support interpretations.

- An optimization constraint is not proof that a simulation result passes validation.
- A successful API response is not proof of mathematical correctness.
- Stale scenario evidence must not be presented as current.

### 8. Mandatory Stop Conditions

STOP the affected implementation and report the blocker when:

- Required evidence is missing or required input values are unknown.
- A proposed change conflicts with verified behavior or an approved specification.
- Analytical calculations cannot be reproduced or validated.
- A required test or verification gate fails, or a test failure remains unexplained.
- A change requires unauthorized modifications, including to a protected contract.
- Unowned repository changes cannot be safely isolated.
- A mathematical or data-integrity defect remains unresolved.
- An implementation outcome cannot be distinguished from an assumption.

Do not invent a workaround to bypass a blocker, and do not bypass a failed gate to satisfy an instruction to complete the task.

Independent, safe, in-scope work may continue when it does not depend on the blocked component.

### 9. Verification Before Completion

Execute relevant tests and validation (see Gates below):

- Mathematical changes: independent reference cases or derivations where applicable.
- Application changes: relevant behavioral and regression tests.
- Deployment claims: inspect the actual deployed behavior or configuration through authorized means. Passing local tests never verifies production behavior.

Clearly distinguish:

- Tests executed and passed.
- Tests executed and failed.
- Tests not executed (report NOT TESTED and the exact reason).
- Behaviors inspected but not tested.
- Behaviors still unverified.

Never claim successful verification without execution evidence.

### 10. Scope-Controlled Commits

Commit only authorized and verified changes. Before committing:

- Inspect the final diff and verify the exact file list.
- Run the appropriate validation.
- Confirm that protected behavior is unchanged.
- Confirm that no unrelated files are staged.

Never fabricate a commit hash, a passing test count, or a clean working-tree status. Do not push unless explicitly authorized; `memory.md` (Deployment Topology) records that pushing `main` is a production release.

### 11. Final Engineering Report

Report only what the actual final repository state supports:

1. Verified findings.
2. Actual modifications: what changed, why it was necessary, and which files.
3. Verification executed and actual test results, passed and failed.
4. Unresolved defects.
5. Remaining unknowns.
6. Any deviation from the requested scope.
7. Status: complete, partial, or blocked.

Never describe planned work as completed work.

**Governing rule: If evidence is absent, the correct answer is UNKNOWN—not an invented explanation or result.**

## Repository Layout

- `backend/` — Production FastAPI service (`backend/api/main.py`). Queueing engine under `backend/queueing_engine/` (models, services, simulation, statistics), DB layer under `backend/db/` (SQLAlchemy + Postgres), report generation under `backend/reports/`.
- `frontend/` — React 19 + Vite SPA (React Router, TanStack Query, i18next, Plotly). Builds into `dist/`. nginx serves it in the Docker Compose stacks; the public deployment uses Cloudflare Pages with the `/api` bridge `frontend/functions/api/[[path]].ts` (see `memory.md`, Deployment Topology).
- `nginx/` — `nginx.conf` serves the built SPA at `/` and proxies `/api/` → `api:8000` (strips the `/api` prefix).
- `tests/` — pytest suite for backend + API + queueing engine.
- `docs/superpowers/` — plans (`plans/`) and design specs (`specs/`) written before implementation.

## Running the Stack

- `docker compose up -d --build` — Postgres (`db`), API (`api`, :8000), web (`web`, :80 — built SPA + API proxy).
- Frontend dev: `npm run dev` in `frontend/` (Vite :5173, proxies `/api` → `localhost:8000` stripping the prefix).
- Default admin seed: `admin@example.com` / `admin123` (compose default; override via `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `.env`). Seeding is **create-only**: an existing user is never modified. To change an existing admin's password/role, run `docker compose exec api python -m backend.db.seed --email <email> --password <newpass> --force-reset`.

## Gates (run before claiming work complete)

- Backend: `python -m pytest tests/ -x --tb=short` (CI invocation; bare `pytest` resolves to a stale system install — always use `python -m pytest`)
- Lint/type: `ruff check .`, `mypy .`
- Frontend: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build` (in `frontend/`)

## Constraints

- **Queueing-engine contract is frozen**: request/response shapes of `backend/api/` (especially `/simulation/*` and `/optimize/*`) are production contracts — do not change them without a plan. New features must be additive.
- **Single source of truth for model selection**: `backend/queueing_engine/services/model_selection.py` (dispatch: `queue_structure == "separate_queues"` is checked first and yields Parallel M/G/1 when c==1, K is absent, theta is not positive, and variance is valid, otherwise an explicit unsupported result; then theta → Erlang-A, K+variance → M/G/c/K, K → M/M/c/K, variance → M/G/c, c==1 → M/M/1, else M/M/c). Never re-implement dispatch inline.
- **CSRF flow**: session cookie `novaq_session` is HttpOnly; `novaq_csrf` is JS-readable (httponly=False). The SPA attaches `X-CSRF-Token` on non-GET requests whenever the csrf cookie is present (`frontend/src/lib/http.ts`). The API exempts exactly the `/analysis`, `/simulation`, `/optimize`, and `/onboarding` prefixes (`CsrfDoubleSubmitMiddleware.EXEMPT_FAMILIES` in `backend/api/main.py`, pinned by `tests/test_production_hardening.py`).
- **i18n**: any new label/string must be added to BOTH `frontend/public/locales/en/translation.json` and `frontend/public/locales/tl/translation.json` (keys must stay symmetric).
- **Reports use minutes** for wait times (multiply hour-valued Wq by 60 at display time); thresholds and alerts are minutes.
- Never commit secrets or `.env`. No changes to `docker-compose.yml` ports without checking both `web` (nginx) and `api` exposure.
- Work follows the superpowers flow: brainstorm → spec (`docs/superpowers/specs/`) → plan (`docs/superpowers/plans/`) → implement → verify → report.

---

# Session History (context, not instructions)

These summaries describe work on the former Streamlit application. Its files (for example `pages/`, `streamlit_app.py`, `optimization.py`, `theme.py`) were removed in `8b0df382` (2026-08-16), so the file names and test counts below are historical.

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
