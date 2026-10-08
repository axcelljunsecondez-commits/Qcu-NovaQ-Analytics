# Named Shared Queue Release Plan (PROPOSED)

Status: **PROPOSED, not approved.** Nothing in this plan has been pushed, merged to `main`, or deployed.
Pushing `main` is a production release (`memory.md`, Deployment Topology). Every step marked GO needs the
owner's explicit go-ahead at that step.

- Date: 2026-10-07
- Candidate: `release/named-shared-queue-prep` at `110a450b`: the merge `f150561e` of `feat/shared-queue-segments`
  (`c0d3db8b`) and `origin/main` (`f08b55ae`), then P1 (`9bb79801`) and the W0 merge of `origin/main` `16e7ddbc`
  (five docs-only commits). Worktree: `.claude/worktrees/release-named-prep`.
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
| W1 | Production read-back. Done from records for W2 only (section 8): W2 does not touch production. A fresh read-back (Render live commit, env key count and `RESULT_JSONB_MAX_BYTES`, Start Command, Auto-Deploy and PR Previews Off; Pages production deployment and automatic deployments Disabled; `/api/ready` 200) is repeated immediately before W4. | Owner reads, Claude records | any difference from section 2 |
| W2 (GO) | Push the candidate to a `ci/` branch and open a draft PR into `main` (CI runs on `pull_request` to `main`): lint, test matrix 3.10-3.13, docker-build with Trivy, frontend, secret-scan, production-preflight, postgres-integration (PostgreSQL 16), stack-integration. | Claude with owner GO | any CI job fails |
| W3 | Take a manual encrypted backup (weekly-backup procedure). No migration runs, so this is a safety copy only. | Owner | backup or hash check fails |
| W4 (GO) | Fast-forward `main` to the CI-green candidate and push. Auto-deploys are off, so nothing deploys yet. | Claude with owner GO | push is not a fast-forward |
| W5 (GO) | Render: Manual Deploy of that commit. Render runs `pip install -r requirements.txt` (floors), so the build may pick up newer dependency versions than the last deploy. | Owner | build fails, startup fails (G7 guard), `/api/ready` not 200 |
| W6 | Backend checks: `/api/ready` 200; Render log shows startup complete and no tracebacks; logged-in R1 `GET /api/analyses/{id}/shared-named/contract` returns `limits.result_max_bytes = 786432` (this VERIFIES the production cap through the app) and `max_expected_customers_per_run = 2900`. The old frontend never calls the new routes, so it stays working. | Owner logs in, Claude reads | any check fails -> rollback R1 |
| W7 (GO) | Pages production deploy. Do **not** retry a deployment of the candidate commit: Pages first sees it on the `ci/` branch and builds Preview deployments of that branch instead (REPORTED: the 2026-10-07 ingress release, ingress plan step 4). Instead, with automatic deployments switched on by the owner and Render Auto-Deploy and PR Previews re-read Off, push one new docs-only commit to `main` (the release record), so Pages builds Production from `main`; then switch automatic deployments off and read back Disabled. | Owner (Pages switch), Claude (push, with GO) | a Preview instead of Production is built, or any deploy fails |
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

## 8. Progress record (2026-10-07; local only, nothing pushed)

- **P1 DONE:** `9bb79801` adds `tests/test_api_shared_named.py` to the `postgres-integration` job. Verified as CI
  runs it (`python:3.11.16-slim`, `requirements.txt` plus `pytest~=9.0` and `httpx~=0.28`, PostgreSQL 16.15):
  466 passed, 1 skipped (the SQLite-only case), 1 Starlette deprecation warning about `httpx`.
- **P2 DONE:** the full suite in `python:3.14.8` on `3911e301` with `requirements.txt` (numpy 2.2.6, scipy 1.18.1,
  SQLAlchemy 2.1.3, FastAPI 0.142.2) and CI's test dependencies: 2897 passed, 123 skipped, 1 xfailed.
- **W0 DONE:** `origin/main` had moved to `16e7ddbc` (five docs-only commits: scheduled daily backups, GO packet
  section 3 closed, ingress cleanup). Merged as `110a450b`. Each of the four files gained exactly `main`'s
  changes, no code changed, and no test reads those files, so the gates on the code still apply.
- **W1 (from records, REPORTED):** `main`'s handoff and ingress plan, written by the session that ran the
  2026-10-07 ingress release, record Render live `1c8e8de` (`dep-db33kc2d0e5s73f0rf2g`, 12:27 UTC), 18 env keys
  (12:28 UTC) including `RESULT_JSONB_MAX_BYTES=786432` (owner-read), the Start Command with `--workers 1
  --no-proxy-headers --no-access-log`, Auto-Deploy and PR Previews Off, Pages production `b7ac08c8`, and Pages
  automatic deployments read back Disabled after 12:08 UTC. These are hours old; W1 is repeated before W4.
- **Still open:** daily scheduled backups now exist (REPORTED by `main`'s handoff), so W3 may use the latest
  scheduled backup if the owner prefers. The backup private key has no off-PC copy yet (REPORTED), which is an
  operational risk outside this release.

## 9. Release record (2026-10-08, UTC)

- **W2 DONE:** `491a9d31` pushed to `ci/verify-491a9d31`; draft PR #28 into `main` (never merged). CI run
  37704686284 (`pull_request`): all 11 jobs succeeded, finished 00:13:39. Pages listed the branch as a Preview
  with "No deployment available" (nothing built).
- **W3 DONE (owner choice):** no new backup; the release backup is the scheduled `novaq-sched-20261007T141913Z`
  (status OK, revision `0005`, 2026-10-07 14:19:32, encrypted SHA-256 `45b70e9b…a337`), read from
  `LAST_STATUS.txt` in the OneDrive copy.
- **W1 repeated, all match (read in the dashboards, finished 03:56):** Render live `1c8e8de` (no later events),
  18 env keys, `RESULT_JSONB_MAX_BYTES=786432`, Start Command `uvicorn backend.api.main:app --host 0.0.0.0
  --port $PORT --workers 1 --no-proxy-headers --no-access-log`, Pre-Deploy Command empty, branch `main`,
  Auto-Deploy Off, PR Previews Off; Pages production `b7ac08c8` (from `1c8e8de`), Branch control
  "Automatic deployments: Disabled"; `/api/ready` 200.
- **W4 DONE (owner GO):** `main` fast-forwarded `16e7ddbc..491a9d31` (41 commits) between 03:56:19 and 03:57:55 (the push CI run's creation). No deploy
  started: Render's last event stayed `1c8e8de`, Pages listed `main 491a9d3` with "No deployment available".
  Push CI run 37725205872: all 11 jobs succeeded, finished 04:19:17.
- **W5 DONE:** owner Manual Deploy (specific commit) of `491a9d3`: started 04:02, "Deploy live for 491a9d3"
  04:04. Log: the Start Command above, about 57 s until "Started server process" (with Render's "No open ports
  detected" notice), "Application startup complete" 04:04:23, then the old instance shut down cleanly.
- **W6 DONE:** no tracebacks in the log; `/api/ready` 200 at 04:05:21; unauthenticated R1 returns 401 while an
  unknown route returns 404; the owner's logged-in R1 for analysis 6 returned 200 at 04:16:16 (Render log,
  `user_id=4`) with `limits.result_max_bytes = 786432`, `max_expected_customers_per_run = 2900` and
  `status = provisional_not_production_approved` (owner-pasted response). This VERIFIES the production cap
  through the app.
- **Owner actions in the same session (not part of the release):** analyses 6 and 11 archived (04:16:26,
  04:16:32; owner confirmed intentional) and analysis 17 created (04:16:46).
- **W7:** this docs-only commit is the one pushed to `main` with Pages automatic deployments on.
