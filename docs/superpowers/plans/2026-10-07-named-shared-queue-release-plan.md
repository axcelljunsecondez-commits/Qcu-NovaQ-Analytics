# Named Shared Queue Release Plan (PROPOSED)

Status: **PROPOSED, not approved.** Nothing in this plan has been pushed, merged to `main`, or deployed.
Pushing `main` is a production release (`memory.md`, Deployment Topology). Every step marked GO needs the
owner's explicit go-ahead at that step.

- Date: 2026-10-07
- Candidate: `release/named-shared-queue-prep` at `f150561e`, a local merge of `feat/shared-queue-segments`
  (`c0d3db8b`) and `origin/main` (`f08b55ae`). Worktree: `.claude/worktrees/release-named-prep`.
- Spec: `docs/superpowers/specs/2026-09-30-shared-queue-named-api-ui-first-slice.md` (sections 21 and 22).

## 1. What the release changes (VERIFIED from `git diff origin/main f150561e`)

- 37 commits not on `main`.
- **No** change to `migrations/`, `requirements.txt`, `requirements-production.lock`, `.github/`,
  `frontend/functions/`, `frontend/public/_headers`, `_routes.json`, `package.json`, or `package-lock.json`.
  No database migration is needed; production is already at `0005`.
- Backend: 16 new files (the adapter `backend/api/shared_named.py` and 15 `shared_*` engine modules) and
  2 added lines in `backend/api/main.py` (import and `include_router`). The engine modules are imported only by
  the adapter (isolation guard in `tests/test_shared_segments.py`).
- Frontend: new Named components, `lib/namedWorkforce.ts`, `api/sharedNamed.ts`, and fixture; modified
  `SimulationPage.tsx` (+27/-1: the mode switch on shared-queue analyses, `?mode=named`) and both locale
  files (en/tl, symmetric keys).
- Docs: specs and plans, `handoff.md`, `memory.md`, and the zero-fabrication protocol in `AGENTS.md` and
  `CLAUDE.md` (`c37c4f00`, `0244e975`, `e0913258`), which `main` does not have yet.
- New HTTP surface: `/analyses/{id}/shared-named/*` (R1-R6). Existing routes and contracts are unchanged.

## 2. Production state this plan assumes (REPORTED by `handoff.md` on `origin/main` `f08b55ae`)

- Render backend runs `1c8e8de` (deploy `dep-db33kc2d0e5s73f0rf2g`, 2026-10-07 12:27 UTC), `NOVAQ_ENV=production`,
  `NOVAQ_PROXY_MODE=pages_signed`, 18 env keys including `RESULT_JSONB_MAX_BYTES=786432`, auto-deploy and PR
  previews off.
- Start Command: `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-proxy-headers --no-access-log`.
- Pages: deployment `b7ac08c8` (`main` `1c8e8de`), automatic deployments disabled. Previous deployment
  `a4f60c31`.
- Supabase at `0005`, RLS on, Data API off, SSL enforced.

These are re-read at the start of the window (step W1); any difference stops the release.

## 3. Gates already passed on `f150561e` (VERIFIED, local, 2026-10-07)

- Backend `python -m pytest tests/ -x --tb=short` (Python 3.13.13, SQLite): 2897 passed, 123 skipped
  (PostgreSQL variants), 1 xfailed.
- CI's PostgreSQL list plus `tests/test_api_shared_named.py`: 466 passed, 1 skipped (SQLite-only case) on
  PostgreSQL 16.15 and on 17.11 (disposable containers).
- Frontend after `npm ci`: 61 files, 449 tests; `typecheck`, `lint`, `build` exit 0.
- `ruff check .` clean; `mypy . --exclude '^outputs?/'` no issues in 203 files.

**Not yet run (NOT TESTED):** the full suite on Python 3.10, 3.11, and 3.12 (CI matrix) and on Python 3.14
(Render's runtime); the CI Docker build and Trivy scan; the stack-integration job.

## 4. Pre-release changes (PROPOSED; each needs owner approval before it is made)

- **P1. CI covers the Named API on PostgreSQL.** Add `tests/test_api_shared_named.py` to the
  `postgres-integration` pytest list in `.github/workflows/ci.yml`. Today CI never runs B1 (the persistence
  identity check) or the PostgreSQL round trips. Verify locally on PostgreSQL 16 before committing.
- **P2. Python 3.14 full suite.** Run the full suite in `python:3.14` as G-13 did for G8 (numpy 2.2.6 compiles
  from source there). Render installs `requirements.txt` floors on Python 3.14, so this is the closest local
  check of the deployed environment.

## 5. Release steps

| Step | Action | Who | Stop if |
|---|---|---|---|
| W0 | Re-check `origin/main` is still `f08b55ae`. If it moved, re-merge into the candidate and re-run section 3. | Claude | merge conflict or any gate fails |
| W1 | Re-read production: Render live commit, env key count and `RESULT_JSONB_MAX_BYTES`, Start Command, auto-deploy Off; Pages production deployment and auto-deploy Disabled; `/api/ready` 200. | Owner reads, Claude records | any difference from section 2 |
| W2 (GO) | Push the candidate to a `ci/` branch and open a draft PR into `main` (CI runs on `pull_request` to `main`): lint, test matrix 3.10-3.13, docker-build with Trivy, frontend, secret-scan, production-preflight, postgres-integration (PostgreSQL 16), stack-integration. | Claude with owner GO | any CI job fails |
| W3 | Take a manual encrypted backup (weekly-backup procedure). No migration runs, so this is a safety copy only. | Owner | backup or hash check fails |
| W4 (GO) | Fast-forward `main` to the CI-green candidate and push. Auto-deploys are off, so nothing deploys yet. | Claude with owner GO | push is not a fast-forward |
| W5 (GO) | Render: Manual Deploy of that commit. Render runs `pip install -r requirements.txt` (floors), so the build may pick up newer dependency versions than the last deploy. | Owner | build fails, startup fails (G7 guard), `/api/ready` not 200 |
| W6 | Backend checks: `/api/ready` 200; Render log shows startup complete and no tracebacks; logged-in R1 `GET /api/analyses/{id}/shared-named/contract` returns `limits.result_max_bytes = 786432` (this VERIFIES the production cap through the app) and `max_expected_customers_per_run = 2900`. The old frontend never calls the new routes, so it stays working. | Owner logs in, Claude reads | any check fails -> rollback R1 |
| W7 (GO) | Pages: production deploy of the same commit (enable automatic deployments, deploy, disable again, read back Disabled). | Owner | deploy fails |
| W8 | Frontend checks: the Simulate page of an existing analysis loads; a shared-queue analysis shows the mode switch; `?mode=named` loads the contract; no CSP violations in the console. | Owner in browser, Claude reads | any check fails -> rollback R2 |
| W9 | Post-release timing (spec section 22.8 "Still open"): one real Named run on a shared-queue analysis, near but under 2,900 expected customers, timing R3 and one R6; then repeat after at least 15 minutes idle so Render has spun down (first request after wake-up). This writes one Job row; it is the owner's decision to run it on production. | Owner runs, Claude reads Render `event=http_request` durations | R3 or R6 over 60 s -> owner decides on a lower bound |
| W10 | Record: handoff, memory, spec section 22 status (limits PRODUCTION-APPROVED only if W6 and W9 pass). | Claude | — |

## 6. Rollback

- **R1, backend:** redeploy the previous Render commit `1c8e8de`. No migration ran, so the database needs no
  change. Named Jobs already created stay as rows of kind `shared_named_replications`; the existing evidence code queries Jobs
  only by its own kinds, so it never reads them (spec section 1.2, VERIFIED on the committed code then).
- **R2, frontend:** roll Pages back to `b7ac08c8`. If only the frontend is rolled back, the new backend routes stay
  unused.
- Ingress rollback is unrelated to this release (see `handoff.md`).

## 7. Known risks and open items

- **Run time:** the 2,900 bound comes from a Render-Free-like container, not Render (spec 22.8). W9 checks it.
- **NumPy:** regeneration fails closed with 409 if the runtime's numerics differ from the recording run (spec
  section 7, NumPy pins CONFLICTING). A Render rebuild that picks up a different NumPy could make older Named
  runs refuse playback; they are not lost, but they cannot be replayed until rerun.
- **App-wide NaN/Infinity -> 500** outside the Named router is a pre-existing defect, not fixed here.
- **Filipino wording** of the new strings is not reviewed by a native speaker.
- **Render memory:** the Render-like container peaked at 293 MB process memory; production memory is
  not measured.
