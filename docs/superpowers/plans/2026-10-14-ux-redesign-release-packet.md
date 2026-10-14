# Release packet — compact workflow UX redesign (`feat/ux-u1-shell`)

Status: PROPOSED 2026-10-14. The owner answered "approve all" to the offer to prepare a release; the release policy
(`memory.md`, G8 section) still requires this reviewed packet and an explicit owner GO before any production migration,
Render change or deployment. The standing rules for this work also apply: Claude never pushes `main`, never deploys and
never touches the production database. Every production step below is the owner's.

## 1. What the release changes (VERIFIED from `git diff origin/main e2ffc75e`)

- Candidate: `feat/ux-u1-shell` at `e2ffc75e` (plus this packet's docs commit), which is `334d5233` merged with
  `origin/main` `0959a0fe` (the 2026-10-13 large server-count release). The merge had no conflicts. 33 non-merge commits
  ahead of `main`: the redesign steps U1-U10, B1-B13, the U10 fixes F1-F16, OD-N2, OD-UX-13, Help screenshots, the
  Filipino Reports Decision text and the replay speed (D29). The list is in `handoff.md`.
- Size: 257 files (backend 32, frontend 161).
- **Database:** two new migrations, both add one column:
  - `0006` `datasets.purpose` (`planning` | `review`, not null, default `planning`, check constraint);
  - `0007` `analysis_projects.shared_closing_policy` (`DRAIN` | `HARD_CUTOFF` | null, check constraint).
- **Engine versions:** separate-lanes plans move from `novaq-2026-09-separate-des-v2` to `...-v4` (representative day)
  and `...-v5` (per date). Plans saved with v2 become HISTORICAL and must be recalculated in Suggested plans (F16, spec
  `2026-10-13-u10-f16-separate-cost-interval.md`). Production has only v2 plans.
- **New settings, all with defaults** (nothing has to be added on Render): `RATE_LIMIT_REPORT_PREVIEW` (60/min),
  `RATE_LIMIT_GUEST_COMPUTE` (30/min, guest calculator). `docker-compose.production.yml` passes both.
- **Unchanged:** `frontend/public/_headers` (CSP), `_routes.json`, the Pages `/api` bridge, `nginx/`, the Dockerfiles,
  `requirements.txt` and `frontend/package.json`.
- New public routes: `/help`, `/help/:topic`, `/calculator`, and API `POST /public/calculator/{model}` (no account; signed
  through the Pages bridge like every `/api` call).

## 2. Production state this packet assumes (REPORTED by `memory.md` and the session memory, not re-read)

- Render backend `43a54f7` (live 2026-10-13), `NOVAQ_ENV=production`, `NOVAQ_PROXY_MODE=pages_signed`, Auto-Deploy Off,
  migration-free Start Command.
- Supabase Postgres 17.6 at `0005`; daily encrypted backup on the owner's PC.
- Pages production `16a21277`; automatic deployments Disabled.

Step W2 re-reads these before anything changes.

## 3. Gates already passed (VERIFIED, local, 2026-10-14)

| Check | Result |
|---|---|
| ruff, mypy on `e2ffc75e` | clean (236 files) |
| pytest on `e2ffc75e` (SQLite) | 3185 passed, 123 skipped, 1 expected failure |
| Frontend on `e2ffc75e` | 78 files / 631 tests, tsc, oxlint, build all pass (one earlier full run on `334d5233` had 4 unexplained failures in untouched files; they passed alone and in two clean full runs since) |
| Postgres 17.11 rehearsal (scratch container) | released code (`0959a0fe`) migrated an empty database to `0005` and created a user, an analysis and two uploads through its API; this branch ran `alembic upgrade 0007`: both files became planning files, the current file and the Setup stayed the same, the closing rule stayed unset, the new workflow endpoint answered; the released code then reported `Database migration mismatch: expected ['0005'], got ['0007']` (so it would refuse to start); `alembic downgrade 0005` removed exactly the two columns and the released code read the data and accepted a new upload; upgrade to `0007` again succeeded |
| CI Postgres test set on Postgres 17.11 (+ the B10 and B4a migration tests) | 472 passed, 1 skipped (see section 7) |

## 4. Release steps

| Step | Action | Who | Stop if |
|---|---|---|---|
| W0 | Re-check `origin/main` is still `0959a0fe`; if it moved, merge again and repeat section 3. | Claude | conflict or a failing gate |
| W1 (GO) | Push the candidate to `ci/ux-redesign-<sha>` and open a draft PR into `main` in the browser (the GitHub CLI is not signed in; the owner must be signed in to GitHub in the app's browser). CI: lint, tests 3.10-3.13, frontend, secret-scan, production-preflight, postgres-integration (PG16), stack-integration, docker-build. Pages builds a Preview of that branch; do not promote it. | Claude, owner signs in | any CI job fails |
| W2 | Production read-back: Render live commit and Auto-Deploy Off; Pages production deployment and automatic deployments Disabled; `https://novaq.site/api/ready` 200; Supabase `select version_num from alembic_version` = `0005`. Optional count of plans needing recalculation (read-only): `select count(*) from scenarios where settings_json->'calculation'->>'engine_version' like '%separate-des%';` | Owner reads, Claude records | any difference from section 2 |
| W3 | Manual encrypted backup (weekly procedure) and its restore check. | Owner | backup or hash check fails |
| W4 (GO) | Migration from a clean copy of the candidate commit with production `DATABASE_URL`: `python -m alembic -c alembic.ini upgrade 0007`, then `python -m backend.operations.migration_status` must print `0007`. From this moment the running `43a54f7` keeps serving, but any restart of it fails the G7 guard, so do W5 and W6 straight away. | Owner | migration error: stop, keep the backend as is, do not retry blindly |
| W5 (GO) | Fast-forward `main` to the CI-green candidate and push (`git push origin <sha>:main`). Nothing deploys by itself. | Owner (Claude never pushes `main`) | push is not a fast-forward |
| W6 (GO) | Render Manual Deploy of that commit. Check `/api/ready` 200 and a clean startup log. | Owner | build or startup fails -> section 5 |
| W7 (GO) | Pages: switch automatic deployments on, push one docs-only commit to `main` (the release record), confirm a Production build of `main`, switch automatic deployments off and read back Disabled. | Owner | a Preview is built instead, or the build fails |
| W8 | Browser checks on `novaq.site`: Home and `/help` signed out; quick calculator as a guest; sign in; an existing analysis: Data and setup, Analysis results, Suggested plans, Queue simulation (all three pages), Reports; no CSP errors in the console. | Owner, Claude reads | any failure -> section 5 |
| W9 | Record: release record in this file, `handoff.md`, `memory.md`. | Claude | — |

## 5. Rollback

- **Before W4:** nothing to roll back.
- **After W4, before W6 succeeds:** the old backend cannot restart on `0007` (VERIFIED in the rehearsal). Options:
  1. **Fix forward** (preferred): correct the problem on the candidate and deploy.
  2. **Downgrade:** `python -m alembic -c alembic.ini downgrade 0005` from the candidate copy, then Render rollback to
     `43a54f7`. Rehearsed on Postgres 17: it drops only the two new columns. Any review-only labels or closing rules
     saved after the release are lost. Note: the G8 policy said never to downgrade for the G-A release; this is a
     different, column-only migration, so it is the owner's choice.
  3. **Restore** the W3 backup into a separate project and repoint, per the backup policy (never over live data).
- **Frontend only:** roll Pages back to `16a21277`. The branch removes no API route (VERIFIED: the backend diff adds 16
  routes and removes none), so the old frontend should keep working against the new backend (INFERRED; not run).

## 6. What users will notice

- New layout, Home, Help, guest calculator, Reports page.
- Every existing file becomes a planning file; review-only is chosen per upload from now on.
- A shared line's full-day run asks for a closing rule the first time.
- Saved separate-lanes plans show as needing recalculation (engine v2 -> v4/v5).
- A shared line with a current full-day run of its selected plan gets its Decision from that run (OD-UX-13).

## 7. Known risks and open items

- **NOT TESTED:** keyboard-only use; widths 768, 1024 and 1440 px; Render memory with the full-day run; Filipino
  wording by a native speaker.
- **Rehearsal limits:** scratch Postgres 17.11, not Supabase 17.6; the data was synthetic and small.
- **One skipped test** in the Postgres 17 set is by design: `tests/test_api_shared_named.py:609` documents the SQLite JSON path; PostgreSQL is covered by the next test.
- **Report formulas** are NOT TESTED in Excel (one sample workbook was made for the owner's check, OD-B8-4).
- The production limits for named runs remain NOT PRODUCTION-APPROVED (unchanged by this release).

## 8. Progress record

| Step | Result |
|---|---|
| Merge `origin/main` | `e2ffc75e`, no conflicts (2026-10-14) |
| Section 3 gates | passed as listed; scratch Postgres 17 container stopped and removed |
