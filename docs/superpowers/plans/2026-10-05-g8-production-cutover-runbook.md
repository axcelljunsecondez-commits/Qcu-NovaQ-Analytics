# G8 G-A production cutover runbook — draft for review, NOT AUTHORIZED

Date: 2026-10-05. Status: **NO-GO.** This runbook is a proposal for a separate,
explicit production authorization. Nothing in it has been executed against
production. It implements the owner's Option A policy
(`../specs/2026-10-04-g8-release-policy.md`) and closure plan
(`2026-10-04-g8-g-a-release-closure-plan.md`): retain the G7 exact-head guard,
planned maintenance, one-shot `0005`, backup-first recovery.

Evidence labels follow `AGENTS.md`. "Prior session" evidence is dated and
must be re-read at release time; it is not current production state.

## 0. Pinned identities

| Item | Value | Label |
| --- | --- | --- |
| Candidate commit | `2ccb86527a0f48928e4d5c26f3d9bd5f0e6abc35` (`port/g-a-stage1`) | VERIFIED local HEAD 2026-10-05; worktree has uncommitted docs only (`docs/operations.md`, `handoff.md`, `memory.md`, three untracked spec/plan files incl. this one) |
| Candidate Alembic head | `0005` | VERIFIED (`migrations/versions/`, migration_status run below) |
| Live backend commit | `2d063c91a929f5845be2e9d0243d6d5609b257a1`; `origin/main` = same | `origin/main` VERIFIED by `git ls-remote` 2026-10-05; live deploy VERIFIED 2026-10-04 (prior session), re-read at release |
| Live is ancestor of candidate | yes (fast-forward possible) | VERIFIED `git merge-base --is-ancestor` |
| Render service | `srv-daiikrbm8hqs73d15rtg`, Free, 1 instance, auto-deploy off, branch `main`, Start Command `alembic upgrade head && uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT` | VERIFIED 2026-10-04 (prior session); re-read at release |
| Render `NOVAQ_ENV` | `development` | VERIFIED 2026-10-05 (§0a) |
| Supabase project | `cltvswcopkjvnonjutre`, PostgreSQL 17.6, `alembic_version` = `0004`, 9 `public` tables | VERIFIED 2026-10-04 (prior session, role `postgres`) |
| Last encrypted backup | `novaq-g8-pre-0005-20261004T002510Z.tar.age`, 389,382 bytes, SHA-256 `d76bda9accb61aeb1539e6051c0f62abc28227103edcc053dac9aa643a1f199c`; two identical copies in Downloads | VERIFIED 2026-10-05 (both rehashed); OneDrive copy, key, freshness UNKNOWN |

### CONFLICTING: PR #26 branch no longer points at the candidate

`git ls-remote` on 2026-10-05: `origin/ci/verify-fcbc8db1` = `1fbe812c`, three
commits beyond the candidate (`81bc427a` "feat(g8): fence old clients at the
API boundary", `6ef85712` "test(ci): cover client compatibility fence",
`1fbe812c` "Add signed Pages ingress for Render"; 2026-10-02/03; 27 files,
+1,359/−58, including `frontend/src/lib/http.ts`, `frontend/src/router.tsx`
and new backend tests). They live on `codex/g8-old-client-fence` in
`C:/Users/Administrator/.codex/worktrees/g8-old-client-fence/NovaQ`. They are
**not** part of the reviewed candidate, and this runbook does not use them.
Public GitHub API, 2026-10-05: CI run 37033297305 (pull_request, head
`1fbe812c`) completed success on 2026-10-02T16:20:48Z; PR #26 is open, draft,
unmerged, head `1fbe812c`. That CI result says nothing about release review of
those commits. Consequence: "PR #26" or that branch name must never
be used as the release reference; every step pins the SHA. The owner must
decide whether that work is in or out of the G-A release (§9, Q4).

## 0a. Owner-authorized read-only diagnosis (2026-10-05, ~07:55–08:20 UTC)

Owner authorized read-only checks in chat. Dashboards were read in the built-in
browser with the owner signed in. No setting, deploy, suspend, grant or data
was changed. Supabase SQL: two single-statement `SELECT`s as `postgres`; the
editor reported `transaction_read_only = off`, so the read-only property rests on
the statements themselves. They returned aggregates only, with no row contents.

| Fact | Result | Label |
| --- | --- | --- |
| Public readiness | `/api/ready` 200 `{"status":"ready"}` via `novaq.site`, `novaq-frontend.pages.dev`, `novaq-frontend.onrender.com`; `/api/health` 200 | VERIFIED 07:55 and 08:09 UTC |
| Supabase Data API | Overview toggle "Enable Data API" unchecked, Save disabled (no pending edit); Settings tab: "Data API is disabled" | VERIFIED ~08:05 UTC. Conflict resolved: the owner REPORTED disabling it on 2026-10-05, after reporting it on with `public` exposed. The exposure therefore lasted until 2026-10-05; when it began is UNKNOWN |
| Data API use | Edge logs 2026-10-01 → 2026-10-05 08:30 UTC filtered `rest`: no data. Unfiltered 2026-10-04 08:00 → 2026-10-05 08:30: only dashboard `/admin/v1/network-bans/retrieve` calls | VERIFIED for the retained window only; earlier use UNKNOWN (Free log retention short) |
| PostgreSQL / revision | `postgres` db, 17.6, `alembic_version` = `0004` | VERIFIED |
| Tables | 9 in `public`, all owned by `postgres`, none with RLS | VERIFIED |
| Grants | `anon`, `authenticated`: DELETE/INSERT/REFERENCES/SELECT/TRIGGER/TRUNCATE/UPDATE on 9 tables each | VERIFIED (unchanged since 2026-10-04) |
| Default privileges in `public` | For objects created by `postgres` (and `supabase_admin`): tables `arwdDxtm`, sequences `rwU`, functions `X` to `anon`, `authenticated`, `service_role` | VERIFIED. ⇒ `0005`'s `generation_registry` and trigger functions, if created by `postgres`, will be granted to `anon`/`authenticated` (INFERRED) |
| Role attributes | `postgres` and `service_role` BYPASSRLS; `anon`, `authenticated`, `authenticator` not; none superuser | VERIFIED |
| Effective app role | Render deploy log 2026-10-03: `password authentication failed for user "postgres"` against `aws-0-ap-south-1.pooler.supabase.com:5432` (Supavisor session pooler). `pg_stat_activity`: 5 idle `postgres`/`Supavisor` client backends after waking the API | Role `postgres` via session pooler VERIFIED from the log; current connection attribution INFERRED |
| Other DB clients | `authenticator`/`PostgREST 14.5` ×2 idle, `pgbouncer`, `supabase_admin` exporter | VERIFIED |
| Row counts | users 10, auth_identities 9, auth_challenges 242, analysis_projects 16, sessions 59, datasets 11, scenarios 13, jobs 87 | VERIFIED (release baseline must be re-read in W1) |
| Tamper indicators | All 10 users `analyst`, active; no `admin` exists. `max(id)` = count for users (10) and sessions (59). Users created 2026-10-04 (1) and 2026-10-05 (1); 10 live sessions | VERIFIED aggregates; absence of tampering NOT established (updates leave no trace) |
| Render backend | Branch `main`; build `pip install -r requirements.txt`; Pre-Deploy empty; Start Command `alembic upgrade head && uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT`; Auto-Deploy Off; PR previews Off; region Singapore; Maintenance Mode "only available for paid instances"; a **Suspend Web Service** control is present | VERIFIED |
| Render env | 16 keys: ALLOWED_ORIGINS, API_WORKERS, DATABASE_URL, EMAIL_DELIVERY_MODE, GOOGLE_CLIENT_ID, GOOGLE_SIGN_IN_ENABLED, NOVAQ_ENV, NOVAQ_PROXY_ASSERTION_SECRET, PUBLIC_APP_URL, SECURE_COOKIES, SMTP_FROM_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USE_TLS, SMTP_USERNAME. Only `NOVAQ_ENV` value read: `development` | VERIFIED. `NOVAQ_PROXY_ASSERTION_SECRET` is read only by `1fbe812c` (git grep: absent from `2d063c91` and `2ccb8652`) |
| Render runtime | `/opt/render/project/src/.venv/lib/python3.14/` in deploy traceback | VERIFIED: production runs **Python 3.14**; CI matrix is 3.10–3.13 |
| Render events | 2026-10-03 02:39–02:44 UTC four instance failures; 02:46 manual deploy of `2d063c9` failed (DB password authentication for `postgres`); 03:04 manual deploy live 03:06 UTC. Live = `2d063c9` | VERIFIED; cause of the password mismatch (rotation?) UNKNOWN |
| Legacy static `srv-daijlcp5efls73dq41v0` | Auto-Deploy Off | VERIFIED |
| Cloudflare Pages | Production "Automatic deployments paused", production = `main` `2d063c9` (`a69cbebf`); `ci/verify-fcbc8db1` previews incl. `1fbe812` show "No deployment available"; old preview `6809090f` (`2fe22a3`) still listed | VERIFIED |

New gates from this diagnosis:

- **G-13 Python 3.14.** PASSED locally on 2026-10-05 (§0b). Render's build
  image itself remains untested, and dependencies stay unpinned. Re-resolve at
  release time, because a newer upstream release can change the outcome.
- **G-14 Recovery credential path.** The 2026-10-03 outage shows a database
  password change takes the backend down until `DATABASE_URL` is updated. The
  window procedure must not include any password change. Recovery steps that
  repoint `DATABASE_URL` need the new credential prepared in advance.
- **G-2 update.** Data API is now disabled (VERIFIED). Still required: the owner
  confirms when it was disabled, accepts that historical use beyond the log
  window is UNKNOWN, and decides separately on the grants, RLS and default
  privileges. Because `postgres` is the table owner and has BYPASSRLS, enabling
  RLS should not block the app (INFERRED; requires R-1 proof). `0005`
  will add objects that inherit `anon`/`authenticated` grants unless the default
  privileges change first.

## 0b. Local verification executed 2026-10-05 (disposable; owner-authorized)

All runs used Docker containers on a private network with no published ports
and only rehearsal credentials, against a disposable `postgres:17-alpine`
(PostgreSQL 17.11) since removed. Code trees were `git archive` exports of
`2d063c91` (old) and `2ccb8652` (candidate). Evidence, scripts and SHA-256 sums
are in `output/g8-r1-20261005/` in the main checkout.

**G-13 Python 3.14 — PASSED locally.** Image `python:3.14` (Python 3.14.8),
`pip install -r requirements.txt` (Render-style, unpinned) plus the CI test
dependencies. The `python:3.14-slim` attempt failed at install because
`numpy<2.3` has no cp314 wheel and needs a compiler. On the full image numpy
2.2.6 was compiled from source; the install took about 9 minutes. Resolved:
fastapi 0.142.2, starlette 1.7.0, uvicorn 0.54.0, SQLAlchemy 2.1.3, alembic
1.20.0, psycopg 3.3.6, pandas 2.3.3, numpy 2.2.6, scipy 1.18.1, reportlab
5.0.1, openpyxl 3.1.5; `pip check` clean.
- `python -m pytest tests/ -x --tb=short`: **1580 passed, 118 skipped, 1 xfailed, 1 warning** (611.66 s). The warning is the test client's `StarletteDeprecationWarning` about httpx.
- CI PostgreSQL list (9 files) against PostgreSQL 17.11: **319 passed**, 0 skipped (207.66 s).
- Render's own build image is not this image; Render behaviour is INFERRED. Render probably also compiles numpy from source, so builds will be slow (INFERRED).

**R-1 synthetic rehearsal — PASSED (`R1_SYNTHETIC=PASS`).** Supabase-like
roles: non-superuser BYPASSRLS `postgres` owns the database; `anon`,
`authenticated` and `service_role` receive the same default privileges seen in
production (§0a). Synthetic data only; the production backup was **not**
restored (key/tooling UNKNOWN, G-12).

| Step | Result |
| --- | --- |
| Old Start Command on empty DB | 0001→0004, exit 0 |
| Old app writes on 0004 | login 200, dataset + `verified_snapshot` scenario created |
| Before G-2 SQL | 63 grants each for `anon`/`authenticated`; `SET ROLE anon; SELECT … users` **ALLOWED** |
| G-2 remediation SQL (`g2_remediation.sql`) as `postgres` | grants 0; default ACL keeps only `service_role`; RLS on all 9 tables; anon probe **DENIED (42501)** |
| Old app after G-2 SQL | ready, login, read, upload, logout PASS |
| Preflight then one-shot `alembic -c alembic.ini upgrade 0005` | preflight `r1_main / postgres / 17.11 / 0004`; exit 0; `Database migration status: 0005` |
| After 0005 | pre-existing table counts identical to the pre-0005 baseline; `generation_registry` 3 rows, owner `postgres`, no anon grants, RLS **off**; anon probe DENIED |
| Old Start Command on 0005 | `Can't locate revision identified by '0005'`, exit 255, uvicorn not reached |
| Candidate Start Command prefix on 0005 | no-op, exit 0 |
| Candidate `NOVAQ_ENV=production` preflight | `PASS: NovaQ production configuration preflight` (rehearsal values) |
| Candidate production app on 0005 | `/ready` 200; login; pre-0005 scenario snapshot **reproduces exactly** via `/optimize/batch`; PDF (5485 B) and Excel (8786 B) of old scenario; new upload, calculation, scenario, PDF and Excel; cookies Secure; logout then `/auth/me` 401 |
| Candidate production app on a 0004 DB | refused: `Database migration mismatch: expected ['0005'], got ['0004'].` |
| Follow-up `g2_post_0005.sql` (RLS on `generation_registry`) | RLS true; anon DENIED; candidate production smoke PASS again |

Observed: the candidate reported `evidence_status = STALE_SETUP` for both
synthetic scenarios. They were created by direct API calls without the
onboarding/Setup workflow, which is the INFERRED reason; this run did not
investigate it further. Script defects found and fixed during the run (a
`.test` email the validator rejects, a redundant second login, and a
mis-placed count baseline) are recorded in the console logs. None was a
product failure.

Proposed production SQL (owner runs it as `postgres` in the Supabase SQL
editor; tested above, NOT run in production):

```sql
begin;
revoke all privileges on all tables in schema public from anon, authenticated;
revoke all privileges on all sequences in schema public from anon, authenticated;
revoke all privileges on all functions in schema public from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on functions from anon, authenticated;
alter table public.alembic_version   enable row level security;
alter table public.users             enable row level security;
alter table public.auth_identities   enable row level security;
alter table public.auth_challenges   enable row level security;
alter table public.analysis_projects enable row level security;
alter table public.sessions          enable row level security;
alter table public.datasets          enable row level security;
alter table public.scenarios         enable row level security;
alter table public.jobs              enable row level security;
commit;
```

**Production verification, 2026-10-05 ~09:14 UTC (read-only, after the owner
REPORTED running the fix): NOT APPLIED.** `anon` and `authenticated` still
hold all seven privileges on all nine tables, and RLS is off on every table.
The `postgres` default ACL still grants tables, sequences and functions to
both roles. `has_table_privilege('anon','public.users','SELECT')` returns
`true`. Also observed: 592 column-grant rows, 16 sequence-grant rows and 0
routine-grant rows for these roles. The revision is still `0004`, row counts
are unchanged from §0a, and `/api/ready` returned 200. Postgres logs for
08:15–09:20 UTC show no `revoke` and no `ERROR` match; statement logging scope
is UNKNOWN, so that is not proof the SQL never ran. Cause UNKNOWN. A re-check
at 09:18 UTC was identical.

**Applied and VERIFIED 2026-10-05 09:25:05 UTC.** Claude typed the SQL into a
new SQL Editor tab for this project. A content check confirmed an exact match
with the tested SQL (1,103 characters, 17 statements); Claude did not run it.
The owner ran it and REPORTED "Success. No rows returned." The read-only
check as `postgres` then showed:
- 0 `anon`/`authenticated` rows in table, column, sequence and routine grants;
- RLS true on all nine tables, all owned by `postgres`;
- `postgres` default ACL now `postgres` + `service_role` only, for tables, sequences and functions;
- `has_table_privilege` false for anon SELECT `users`, anon INSERT `sessions` and authenticated UPDATE `users`; true for `postgres` SELECT `users`;
- `service_role` still holds 63 table-grant rows (unchanged by design);
- revision `0004`; row counts unchanged (users 10, sessions 59, datasets 11, scenarios 13, jobs 87, analysis_projects 16, auth_identities 9, auth_challenges 242).

`/api/ready` and `/api/health` returned 200 at 09:25:24 UTC. Render application
logs for 09:00–09:40 UTC show no errors. However, `/ready` runs only
`SELECT 1`, and no table-reading request was observed after the change, so app
table access after the fix was not yet tested in production at that point.

**Post-fix app check, 2026-10-05.** The owner REPORTED logging in and opening
an Analysis successfully. Render application logs (read-only) corroborate it,
09:52–09:54 UTC:
- `POST /auth/login` 401, then `POST /auth/google` 200;
- `GET /onboarding/status` 200, `GET /analyses` 200;
- `GET /analyses/6` 200, `/analyses/6/datasets` 200, `/analyses/6/current` 200;
- no 5xx responses.

The app's table reads work under the revoked grants and RLS (VERIFIED for those
endpoints). Writes after the fix were not exercised in production (NOT TESTED);
the synthetic rehearsal covered them.

After `0005` (window step W5): `alter table public.generation_registry enable row level security;`.
Not covered by the rehearsal: Supabase-managed `supabase_admin` default
privileges, which `postgres` cannot change, and any platform process that
re-grants. Re-read grants after running.

## 0c. Public operations checks (read-only, 2026-10-05 ~10:10–10:25 UTC)

`docs/operations.md` "public GO evidence" assumes the single-host Compose
topology. Each item below is checked against the real topology: Cloudflare
(DNS, Pages, edge), Render web service, Supabase PostgreSQL.

| Item | Result | Label |
| --- | --- | --- |
| Certificates | `novaq.site`, `www.novaq.site`: Google Trust Services WE1, not after 2026-12-23. `novaq-frontend.pages.dev`: Let's Encrypt YE1, 2026-12-22. `qcu-novaq-analytics.onrender.com`: GTS WE1 `*.onrender.com`, 2026-12-20 | VERIFIED |
| TLS 1.2 / 1.3 | negotiated on all four hosts | VERIFIED |
| TLS 1.0 / 1.1 refusal | the local OpenSSL 3.5.6 refused to offer them, so server behaviour is untested. Cloudflare Edge Certificates shows **Minimum TLS Version: TLS 1.0 (default)** | Setting VERIFIED; old TLS likely accepted at the edge (INFERRED) |
| HTTP→HTTPS | `http://novaq.site/` and `http://www.novaq.site/` 301 to HTTPS; `https://www.novaq.site/` 301 to apex; Render direct 301 to HTTPS | VERIFIED |
| HSTS | no `Strict-Transport-Security` on `https://novaq.site/`; Cloudflare shows "Enable HSTS" (off) | **GAP**, VERIFIED |
| Security headers on SPA | **CORRECTED 2026-10-05 13:08 UTC.** The original 10:12 check used a broken filter (`^(x-content-type|content-security|x-frame|strict-transport):`) that could never match the full header names, so its "missing" results were invalid. A full header-name listing shows `x-content-type-options: nosniff` and `referrer-policy: strict-origin-when-cross-origin` **present**; HSTS, `content-security-policy` and `x-frame-options` **absent**. Whether nosniff was present at 10:12 is UNKNOWN. The candidate has no `frontend/public/_headers` | CSP / frame-protection / HSTS **GAP** VERIFIED |
| CORS, direct backend | `Origin: https://novaq.site` echoed with credentials; `https://evil.example` not echoed (preflight 400) | VERIFIED |
| Direct backend exposure | `qcu-novaq-analytics.onrender.com` is publicly reachable, bypassing Cloudflare. The signed-ingress remedy is in the excluded `1fbe812c` | Accepted-risk candidate; owner decision |
| Production config preflight (G-4) | Render's non-secret values (read individually; secrets not opened) plus a placeholder DB URL of the pooler form: `PASS: NovaQ production configuration preflight`; also PASS with the retired legacy origin removed from `ALLOWED_ORIGINS` | VERIFIED; real DB password vs demo-default check UNKNOWN |
| `ALLOWED_ORIGINS` | contains the retired `https://novaq-frontend.onrender.com` (with a stray space) plus `https://novaq.site` | VERIFIED; cleanup PROPOSED in window |
| SMTP | `EMAIL_DELIVERY_MODE=smtp`, Brevo relay, port 2525, TLS 1; live delivery not exercised (it would send mail) | Config VERIFIED; delivery NOT TESTED |
| Google sign-in | owner's Google login on `novaq.site` succeeded 09:54 UTC (`POST /auth/google` 200) | VERIFIED |
| Dependency scans | `pip-audit` 2.10.1, no known vulnerabilities in either the Render-like Python 3.14 resolved set (55 packages) or `requirements-production.lock`. `npm audit --omit=dev --audit-level=high`: 0. CI run 36892385671 Trivy/gitleaks passed for `2ccb8652` | VERIFIED at 10:21 UTC |
| Tracked secrets | only `.env.example` among env-like files in git | VERIFIED |
| Supabase SSL enforcement | "Enforce SSL on incoming connections" **off**; whether the app's `DATABASE_URL` requires TLS is UNKNOWN (secret not read) | **GAP**, setting VERIFIED |
| Scheduled DB backups | Supabase Backups page: "Free Plan does not include project backups." The doc's RPO 24 h / daily encrypted backup policy is not met | **GAP**, VERIFIED |
| Monitoring / alerting | Render notifications: workspace default "Only failure notifications". No external `/api/ready` monitor identified | Partial; external monitor UNKNOWN |
| DB connection logging | Supabase "Log connections" / "Log disconnections" off | VERIFIED (informational) |

Per `docs/operations.md`, every GAP above needs either a fix or an owner
exception with an owner, rationale, compensating control and expiry date before
public GO. The GO packet lists them.

**Backup tooling (G-12), 2026-10-05.** Owner decision: stay on Supabase Free and
use manual backups. Claude wrote `output/g8-backup-tools/novaq_manual_backup.sh`
(main checkout) and its README:
- WSL, session pooler with `verify-full` TLS, `pg_dump -n public -Fc`;
- gpg AES256 symmetric encryption, SHA-256, a OneDrive copy that is re-hashed, and a manifest.

VERIFIED in a disposable round-trip test (README): backup, decrypt (identical
hash) and restore with a TOC filter that skips `CREATE SCHEMA public`; the
restored copy showed `0004`, the user and 9 tables. Pooler TLS verification
against `Downloads/prod-ca-2021.crt` succeeded from WSL (`*.pooler.supabase.com`,
TLS 1.3, code 0). The OneDrive copy of the 2026-10-04 `.age` backup hashes to
`d76bda9a…199c` (VERIFIED), but its key is still UNKNOWN. **Production run of
the script: NOT EXECUTED** (owner-run; needs the DB password).

**Postgres error noise (CONFLICTING evidence on the Data API timeline).** The
Supabase overview showed 111 Postgres errors from 09:47 to 10:46 UTC. They are
`schema "pg_pgrst_no_exposed_schemas" does not exist`, about every 32 s,
present in every hourly bucket from the start of the retained window
(2026-10-04 10:00 UTC) to now. INFERRED: emitted by Supabase's own PostgREST
while no schema is exposed. It is not a NovaQ app error and was not caused by
the grants fix or D-1 (it predates both). This conflicts with the owner's
report that the Data API was on and was turned off on 2026-10-05; the timeline
is UNKNOWN. The noise inflates the project's Postgres error count, which matters
for monitoring.

## 0d. Manual production backup and real-data rehearsal (2026-10-05)

**Backup (owner-run, `novaq_manual_backup.sh` in WSL).** Four earlier attempts
(10:51–10:54 UTC) failed at the pre-check with `password authentication failed
for user "postgres"` (read from the owner's terminal panel). Nothing was dumped
and the app was unaffected (`/api/ready` 200 at 10:53 UTC). The run at
`20261005T105837Z` succeeded:
- pre-check: `postgres | postgres | 17.6 | 0004`;
- counts: users 10, auth_identities 9, auth_challenges 244, analysis_projects 16, sessions 60, datasets 11, scenarios 13, jobs 87;
- plaintext SHA-256 `6713f97815d518f350a5ef43f22280be60d8257cb1d4d69180d65d2bf53a0588`;
- encrypted SHA-256 `d44ae338b8b8226d4ca10306bd23fbe119d166826217a628e5b5ff442a7c33c4`, identical for the OneDrive copy.

Claude re-hashed all three independently (VERIFIED). The archive has 9
table-data entries and 9 row-security entries. Owner REPORTED (2026-10-05)
that decrypting the `.gpg` with their passphrase reproduces the plaintext hash
`6713f978…0588`, so the encrypted copies are usable. The WSL plaintext may now be
deleted; that is the owner's choice.

**Real-data rehearsal (R-1b, disposable, VERIFIED).** Setup:
- `postgres:17` (17.11) with Supabase-like roles (non-superuser BYPASSRLS `postgres`; `anon`, `authenticated`, `service_role`; the post-G-2 default privileges);
- restore of the plaintext dump (hash re-verified after copying) with `--no-owner --no-privileges --exit-on-error` and the `CREATE SCHEMA public` skip: `RESTORE_EXIT=0`;
- Python 3.14.8, Render-style install.

| Check | Result |
| --- | --- |
| Restored counts vs backup `.counts` | identical; RLS true on all tables; anon `SELECT users` DENIED (42501) |
| Old Start Command at `0004` | no-op, exit 0 |
| One-shot `alembic -c alembic.ini upgrade 0005` | `Running upgrade 0004 -> 0005`, exit 0; `Database migration status: 0005` |
| After `0005` | counts unchanged; datasets 11 and scenarios 13, all 32-hex distinct generation tokens; `generation_registry` 24 rows (= 11 + 13); after `enable row level security` anon DENIED; anon/authenticated grants 0 |
| Old Start Command at `0005` | `Can't locate revision identified by '0005'`, exit 255 |
| Candidate in `NOVAQ_ENV=production` over all real data | `/ready` 200; all 8 data owners authenticated (session rows inserted into the disposable copy only; real users sign in with Google); all 16 analyses: `GET /analyses/{id}`, `/datasets`, `/scenarios`, `/workflow` 200 and `/current` 200×10 / 404×6; all 13 scenarios 200, `verified_snapshot/CURRENT`; the 3 with a calculation snapshot **recompute identically** via `/optimize/batch`; scenario PDF+Excel OK for those 3 |
| **Per-item parity: live `2d063c91` @ `0004` (fresh second restore, development mode as live) vs candidate @ `0005` (production mode)** | **167 status entries, 0 differences** (each 200×108, 404×9, 409×24, 422×26) |

The non-200 results are pre-existing and explained by data state; both
versions return them with these details:
- "Scenario has no comparison results to report on." (10 scenarios × PDF/Excel);
- "Select a saved optimal plan in Comparison before running optimized simulation." (8 analyses × preview/PDF/Excel);
- "Selected-plan simulation requires a separate_queues analysis." (2 × 3);
- "Run selected-plan Monte Carlo before generating the final report." (1 × 3);
- `/current` 404 for 6 analyses without a valid current dataset.

Test-only deviations: `RATE_LIMIT_REPORT`/`RATE_LIMIT_COMPUTE` set to 1000;
SMTP host invalid and Google sign-in off; PostgreSQL 17.11 instead of 17.6.
Engine log lines "Unstable system: lambda must be less than mu" appeared during
report generation for unstable segments (expected model output).

Not covered: Google sign-in itself (owner-REPORTED working in the earlier
isolated rehearsal and VERIFIED on production today), and writes on real
data (exercised synthetically in R-1). Scripts are in `output/g8-r1b-20261005/`
(main checkout, SHA256SUMS; no data). The disposable database and Claude's
plaintext copy were deleted after the run.

## 1. Findings that shape the cutover

**F1. G7 is inert today.** VERIFIED in candidate source: the exact-head guard
and `/ready` revision check run only when `Settings.environment ==
"production"` (`backend/api/main.py:243`, `:284-297`). Render's `NOVAQ_ENV` was
REPORTED as `development` on 2026-10-01. Option A's guard therefore protects
nothing unless the cutover sets `NOVAQ_ENV=production`. Doing so also enables
`Settings._validate_production` (`backend/api/settings.py:200-239`):
`SECURE_COOKIES=1`; non-empty HTTPS `ALLOWED_ORIGINS` containing
`PUBLIC_APP_URL`; SMTP mode with host, from-address and `SMTP_USE_TLS=1`; a
complete PostgreSQL URL whose password is not a demo default;
`FORWARDED_ALLOW_IPS` not empty, `*` or `0.0.0.0/0` (default `127.0.0.1`
passes); `API_WORKERS=1`. A failure refuses startup. These two lines are the
only `environment`-dependent branches in `backend/` (VERIFIED by grep).

**F2. The old code cannot start on `0005` through the current Start Command.**
VERIFIED locally this session (SQLite temp DB, Python 3.13.13, Alembic 1.19.1,
SQLAlchemy 2.0.51; trees exported with `git archive` from both SHAs):

| Step | Command (cwd) | Result |
| --- | --- | --- |
| 1 | `alembic upgrade head && echo …` (live tree, empty DB) | 0001→0004, echo ran |
| 2 | `alembic -c alembic.ini upgrade 0005 && python -m backend.operations.migration_status` (candidate) | 0004→0005; `Database migration status: 0005` |
| 3 | `alembic upgrade head && echo …` (live tree, DB at 0005) | `FAILED: Can't locate revision identified by '0005'`, non-zero exit, echo **not** run |
| 4 | `alembic upgrade head && echo …` (candidate, DB at 0005) | no-op, echo ran |

Render runs a different Alembic version (built from unpinned
`requirements.txt` floors); the behaviour on Render is INFERRED from this, not
observed.

**F3. A running old instance keeps working on `0005` and writes data the
candidate cannot verify.** Local artifacts dated 2026-10-02 in
`output/g8-disposable-20261002/` (disposable PostgreSQL 17, synthetic
workspace; not re-run this session; REPORTED) show the old API, after `0005`
was applied under it, still served reads and accepted dataset/scenario writes;
the old-written scenario had `dataset_generation` NULL and the candidate then
reported it `legacy_unverified` / `MISSING_PROVENANCE`, refusing its selection
with 422 (`old_write_candidate_read.json`). Hence: **the old instance must not
be serving at any moment the schema is at `0005`.** Render's normal deploy
keeps the old instance serving while the new one starts (Render docs,
VERIFIED 2026-10-05), so a plain deploy is not a safe cutover.

**F4. Every public entry point reaches the same backend.** REPORTED
2026-10-01: `novaq.site` and `novaq-frontend.pages.dev` (Pages `/api` bridge,
`frontend/functions/api/[[path]].ts`, VERIFIED to forward to
`NOVAQ_API_ORIGIN` with no maintenance switch), Pages preview deployments
(public, same API origin), legacy `novaq-frontend.onrender.com` (rewrite),
and the direct `onrender.com` backend URL. Only stopping the backend
service closes all of them.

**F5. Render Free controls.** VERIFIED from Render docs 2026-10-05: Free web
services have no shell and no one-off jobs (`/docs/free`); pre-deploy is for
paid services; maintenance mode is paid (`/docs/blueprint-spec`); "Deploy a
specific commit" deploys a commit from the linked repo and disables auto-deploy
(`/docs/deploys`); env-var edits offer "Save only" (`/docs/configure-environment-variables`);
services can be suspended/resumed from the dashboard and API
(changelog + API reference). **UNKNOWN until demonstrated (D-1):** whether
suspend works the same on this Free service, what each entry point returns
while suspended, which commit and settings a resume starts, whether settings
can be saved and a specific-commit deploy started while suspended, whether a
commit not on `main` is selectable, and whether a Start Command edit triggers
a deploy.

**F6. Migration runner must be off-Render.** No shell/job/pre-deploy on Free
(F5) leaves an operator-host runner. REPORTED 2026-10-01: the direct database
host is IPv6-only; Windows has IPv6 egress, WSL does not. Use the direct host
or the Supavisor **session** pooler (port 5432); never the transaction pooler
(6543). TLS: `sslmode=verify-full` with the Supabase root CA; a file
`Downloads/prod-ca-2021.crt` exists (VERIFIED: CN "Supabase Root 2021 CA",
not after 2031-04-26, SHA-256 `7007235814…b2f3b7`); that it is the correct CA
for this project's endpoint is NOT TESTED. PostgreSQL DDL in `0005` runs in
one transaction (`env.py` `begin_transaction`), so a failure should leave
`0004`; INFERRED, verify in R-1.

**F7. Security gate (independent of G8, possibly live today).** VERIFIED
2026-10-04: zero `public` tables with RLS; `anon` and `authenticated` each
hold DELETE, INSERT, REFERENCES, SELECT, TRIGGER, TRUNCATE and UPDATE on all
nine. VERIFIED this session: the repository has no Supabase/PostgREST client
(grep over `.py/.ts/.tsx/.json/.toml/.yml`, excluding `node_modules`), so the
app does not need the Data API. Tables include `users` (`password_hash`,
`role`) and `sessions` (`token_hash` = SHA-256 of the cookie token,
`backend/api/auth.py:45`). **INFERRED, conditional on Data API enabled with
`public` exposed:** anyone holding the project's anon/publishable key could
read password hashes, change `users.role`, or insert a `sessions` row whose
hash they computed and so impersonate any user. **REPORTED by the owner on
2026-10-05: the Data API is enabled and `public` is exposed.** With the
VERIFIED grants and zero RLS, the exposure above is therefore INFERRED to be
live now, independent of G8. Not tested by access attempt (no request was or
should be made with a project key). Whether it has been used is UNKNOWN; the
owner can check the project's API (PostgREST `/rest/v1/`) request logs
read-only.
`0005` creates a new `generation_registry` table and PL/pgSQL trigger
functions in `public`; whether Supabase default privileges grant them to
`anon`/`authenticated` depends on the migrating role and is UNKNOWN (record
grants before and after in R-1 and in the window). This plan authorizes no
grant, RLS or Data API change; the remedy is a separate owner decision (§9, Q1).

**F8. Backup tooling.** `age` is not on the Windows PATH or in WSL (VERIFIED
2026-10-05); how the 2026-10-04 archive is decrypted, and where the key is
kept, is UNKNOWN to this session. WSL has `pg_dump`/`pg_restore`/`psql`
18.6 (VERIFIED), which can dump a 17.6 server; restore target must be
PostgreSQL 17. Docker daemon was not running on 2026-10-05 (VERIFIED), so no
disposable PostgreSQL 17 was started this session.

## 2. Design decisions proposed (owner to approve)

1. **Traffic control = suspend the Render backend** (F3, F4, F5). Expected
   result: every entry point shows an API error for the window. A friendly
   maintenance page needs code (e.g. the unreviewed fence/ingress commits) and
   is out of scope.
2. **Keep the current Start Command until the candidate is live.** With F2, if
   Render ever restarts or resumes the old commit after `0005`, it fails
   closed instead of serving. Removing `alembic upgrade head` earlier would let
   the old commit (no G7) serve on `0005`. On the candidate, the same command
   is a no-op at `0005` (F2 step 4). The owner's 2026-10-01 migration-free
   start decision (REPORTED, prior session) becomes a post-release step (§6)
   that redeploys the same commit.
3. **One-shot `alembic -c alembic.ini upgrade 0005`** from the operator host,
   at a clean checkout of the candidate SHA, with a target preflight (§5 W4).
4. **Set `NOVAQ_ENV=production` with "Save only" during the window**, so the
   candidate is the first code to start with G7 active (F1).
5. **Never deploy the candidate unless `0005` is verified first**; otherwise
   its Start Command would migrate implicitly.

## 3. Pre-window gates (all must be green; any red = NO-GO)

| # | Gate | How | Who | Status 2026-10-05 |
| --- | --- | --- | --- | --- |
| G-1 | Release scope fixed: candidate SHA, and in/out decision on `1fbe812c` line | Owner decision | Owner | OPEN (Q4) |
| G-2 | Security gate F7 resolved | Data API disabled (VERIFIED ~08:05 UTC); grants revoked, default privileges fixed and RLS enabled (VERIFIED 09:25 UTC, §0b). Post-fix login + Analysis reads VERIFIED from Render logs 09:52–09:54 UTC. Open: `generation_registry` RLS at W5; earlier Data API use beyond log retention UNKNOWN | Owner | GREEN |
| G-3 | Effective app role known | `postgres` via Supavisor session pooler `aws-0-ap-south-1.pooler.supabase.com:5432` (§0a) | — | VERIFIED |
| G-4 | Production config passes `_validate_production` | Owner runs locally, at candidate SHA: `NOVAQ_ENV=production` + Render's non-secret values + a placeholder non-demo DB password, then `python -m backend.operations.preflight` (no DB connection is made). Expect `PASS: NovaQ production configuration preflight` | Owner + agent | NOT TESTED |
| G-5 | R-1 full isolated rehearsal passed (§4) | Synthetic R-1 PASSED 2026-10-05 (§0b). Still open: the same run on a decrypted copy of the production backup | Agent + owner (key) | PARTIAL |
| G-6 | D-1 suspend demonstration passed (§4) | Executed 2026-10-05 10:01:55–10:06:24 UTC on owner instruction; suspend closes all backend paths (503); no deploy while suspended; resume reruns the Start Command on the existing build (§4, D-1 result) | Agent (owner-authorized) | PASSED |
| G-7 | Candidate reachable by Render | Either push candidate to `main` (fast-forward from `2d063c91`; **separate authorization**) after re-verifying Pages production auto-deploy Disabled, Pages preview None, legacy static and backend auto-deploy Off; or D-1 shows a non-`main` commit is selectable | Owner | OPEN |
| G-8 | CI green on the exact release SHA | Run 36892385671 covers `2ccb8652` only; any other SHA needs its own green run | Agent (read) | VERIFIED for `2ccb8652` |
| G-9 | Local gates on release SHA | `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`, frontend `npm test`/`typecheck`/`lint`/`build` | Agent | VERIFIED 2026-10-04/05 for `2ccb8652` (backend 1,580p/118s/1xf; frontend 53 files/388 tests ×2); earlier frontend hang cause UNKNOWN |
| G-10 | `docs/operations.md` public gates (TLS/redirect, SMTP, edge, secrets, monitoring) | Per that doc | Owner + agent | PARTIAL/UNKNOWN |
| G-11 | Recovery destination and operator access ready | New isolated Supabase project or other PG17 target named in advance; Free tier has no backups/PITR (REPORTED 2026-10-01) | Owner | UNKNOWN |
| G-12 | Backup tooling and key verified | Decrypt the 2026-10-04 archive into a disposable target; OneDrive copy hash = `d76bda9a…199c` | Owner | UNKNOWN |

## 4. Rehearsals before the window

**R-1 — full isolated dress rehearsal (local, disposable; needs owner key and
Google login).** Start Docker; PostgreSQL 17 container on a non-default
loopback port; decrypt the latest archive into the scratchpad; `pg_restore
--exit-on-error --no-owner`; verify revision `0004`, `count(*)` per table,
sequences. Run the §5 W4 preflight and one-shot exactly as written (only the
host differs). Then: `migration_status` = `0005`; counts equal; every
`datasets`/`scenarios` row has a 32-hex `generation`; guard triggers present;
grants/RLS diff recorded. Start the candidate with `NOVAQ_ENV=production` and
the same Start Command; `/health` 200, `/ready` 200; login, open an Analysis,
**run a calculation, export PDF and Excel**, logout. Negative checks: the live
tree's Start Command against the migrated copy fails (F2 step 3); the candidate
in production mode against a `0004` copy refuses startup. Dispose only of the
rehearsal environment.

**D-1 — suspend/resume demonstration on the live service (separate
authorization; schema stays `0004`; expected outage minutes).** Suspend
`srv-daiikrbm8hqs73d15rtg`; probe `https://novaq.site/api/health`,
`https://novaq-frontend.pages.dev/api/health`, the legacy static
`/api/health` and the direct backend `/health`; record status codes. While
suspended, **observe without saving**: can env vars be "Save only", can the
Start Command be edited without a deploy, is "Deploy a specific commit"
offered, which commits it lists. Resume; record which commit started and
`/ready` = 200. Stop if resume does not restore service.

### D-1 result — EXECUTED 2026-10-05 on owner instruction ("Do the suspend test now")

Schema stayed `0004` throughout; no setting was saved and nothing was
deployed. Times are UTC.

| Time | Observation |
| --- | --- |
| 10:00:22 | Baseline: `novaq.site/api/ready`, `novaq-frontend.pages.dev/api/ready`, `qcu-novaq-analytics.onrender.com/ready` and `/health` all 200 |
| 10:01:55 | Suspended `Qcu-NovaQ-Analytics` (`srv-daiikrbm8hqs73d15rtg`; Free, `main`, live `2d063c9`) through Settings → Suspend Web Service with the typed confirmation phrase. Dashboard: "Suspended by you … Resume service"; events "Service suspended" |
| 10:02:39 | All four URLs **503**; direct backend page title "Service Suspended". The Pages bridge passes the 503 through. `novaq.site/` itself still serves the SPA ("NovaQ — Queueing Analytics") |
| while suspended | Overview: **Manual Deploy button absent** (present before suspending). Settings: Edit enabled for Branch, Build Command, Start Command and Auto-Deploy; Pre-Deploy Edit disabled (Free). Environment: Edit and Export enabled. Nothing was opened for editing or saved |
| 10:04:50 | Resumed (Resume Web Service). Toast "Qcu-NovaQ-Analytics has been resumed." |
| 10:05:26 | Log: `==> Running 'alembic upgrade head && uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT'` |
| 10:05:42 | Alembic context only; no `Running upgrade` line (no-op at `0004`) |
| 10:06:14 | uvicorn "Application startup complete" |
| 10:06:24 | First external `/ready` 200 (≈94 s after Resume) |
| 10:06:47 | All four URLs 200 again |
| events | Only "Service suspended" / "Service resumed": **resume created no deploy** and restarted the existing `2d063c9` build |

Outage for this test: about 10:01:55–10:06:24 UTC (≈4.5 min).

**What D-1 establishes for the window (VERIFIED on this service and plan):**
1. Suspend is a working traffic control on this Free web service. It closes
   every backend path (Pages bridge, `pages.dev`, direct URL) with 503 while
   the static SPA stays up. The legacy static rewrite is already retired.
2. A deploy cannot be started while the service is suspended (Manual Deploy is
   absent). Settings and env vars can be edited while suspended.
3. Resume re-runs the full Start Command on the **existing** build. After the
   window's `0005` migration, a resume therefore starts the old `2d063c91`
   build, whose `alembic upgrade head` fails closed at `0005` (F2: VERIFIED
   locally on SQLite and PostgreSQL 17.11; on Render INFERRED from this log
   plus F2). The old code never reaches uvicorn and serves nothing.

**Resulting W6/W7 order (replaces the "if D-1 showed…" branch):** while
suspended, save `NOVAQ_ENV=production` as "Save only" (W6). Resume; expect the
old build to fail at Alembic (STOP if uvicorn starts instead). Then Manual
Deploy → "Deploy a specific commit" `2ccb8652`. The candidate build's
`alembic upgrade head` is a no-op at `0005`, and its G7 guard runs in
production mode. Not yet observed: Manual Deploy availability while the old
instance is failing, and whether Render restart-loops the failing instance.
Check both in the window and STOP if Manual Deploy is unavailable.

## 5. Window procedure (PROPOSED; NOT EXECUTED)

Entry criteria: every §3 gate green, D-1 and R-1 passed, written owner GO
naming this runbook revision, the SHA and the window. Operator: owner, agent
assisting. Re-read every target identifier immediately before use.

- **W0 Announce** the window.
- **W1 Freeze reads of facts (read-only).** Render: service ID, plan, branch,
  live commit `2d063c91`, Start Command unchanged, auto-deploy off. Pages and
  legacy static auto-deploy still off. Supabase SQL (§7 queries): version
  17.6, `alembic_version` = `0004`, table list and counts. **STOP** on any
  difference.
- **W2 Enter maintenance:** suspend the backend. Probe the four entry points
  (D-1 baseline). Supabase: `SELECT usename, application_name, state FROM
  pg_stat_activity WHERE datname = current_database()` shows no app session.
  **STOP/resume** if the backend still answers.
- **W3 Fresh backup:** `pg_dump -Fc` (WSL 18.6, session pooler or direct,
  `sslmode=verify-full`); encrypt; SHA-256; copy off-host; re-hash copy;
  `pg_restore` into disposable PG17; verify `0004` and per-table counts equal
  W1. **STOP** (resume old service, which is still `0004`-compatible) on any
  mismatch.
- **W4 One-shot migration** from a clean checkout of `2ccb8652`, in the
  candidate's venv, with `DATABASE_URL` set only in this shell:
  1. Preflight (read-only; PROPOSED, NOT TESTED until R-1): connect; assert
     host is the approved project endpoint and username matches G-3; print
     `current_database()`, `current_user`, `server_version`,
     `transaction_read_only`, `alembic_version`. **STOP** unless 17.6 and `0004`.
  2. `python -m alembic -c alembic.ini upgrade 0005`
  3. `python -m backend.operations.migration_status` → must print `Database migration status: 0005`.
  **On failure: STOP.** Confirm revision is still `0004` and counts match W1;
  if so, resume the old service (its Start Command is a no-op at `0004`) and
  exit the window. If the database is in any other state → §6 recovery.
- **W5 Post-migration DB checks:** counts equal W1; `generation_registry`
  exists; trigger/function list matches R-1; grants/RLS diff equals R-1 diff.
  **STOP → §6** on mismatch.
- **W6 Configure** (while suspended, "Save only"; mechanics from D-1):
  `NOVAQ_ENV=production` and any value G-4 required. Start Command
  **unchanged**.
- **W7 Deploy candidate:** "Deploy a specific commit" `2ccb8652` (or the
  approved release SHA). If D-1 showed resume is required first, resume: the
  old commit fails closed at `0005` (F2); then deploy. Watch logs: the Alembic
  step reports no upgrade; uvicorn starts; G7 passes.
  **STOP → §6** if the candidate does not become live.
- **W8 Verify:** `/health` 200, `/ready` 200 on all four entry points; login;
  open an Analysis; run a calculation; PDF and Excel export; logout; logs free
  of errors. **STOP → §6** on any failure.
- **W9 Exit maintenance**, announce; monitor `/api/ready` and logs.

## 6. Recovery and post-release

**Backup-first recovery (separate reviewed action; never `alembic downgrade`,
never restore over live by default).** Keep the backend suspended. Restore the
W3 backup into the pre-named G-11 target; verify `0004` and counts; then decide,
with the owner, between (a) pointing the old commit at the restored target
(its Start Command is a no-op at `0004`) and (b) a forward fix. Changing
Render's `DATABASE_URL` is itself a separate authorization. Preserve the
failed database and all logs.

**Post-release (separate authorization):** migration-free Start Command
`uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT`, redeploy the same
SHA, re-verify W8. Frontend release ordering is undecided (Q3).

## 7. Read-only SQL for W1/W5 (role and project re-confirmed before use)

The two queries in the closure plan (version/revision/RLS/grant counts and the
grant breakdown), plus:

```sql
SELECT c.relname, c.relrowsecurity
FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY 1;

SELECT 'users' AS t, count(*) FROM public.users UNION ALL
SELECT 'auth_identities', count(*) FROM public.auth_identities UNION ALL
SELECT 'auth_challenges', count(*) FROM public.auth_challenges UNION ALL
SELECT 'analysis_projects', count(*) FROM public.analysis_projects UNION ALL
SELECT 'sessions', count(*) FROM public.sessions UNION ALL
SELECT 'datasets', count(*) FROM public.datasets UNION ALL
SELECT 'scenarios', count(*) FROM public.scenarios UNION ALL
SELECT 'jobs', count(*) FROM public.jobs;
```

Counts only; no row contents are read.

## 8. Explicit non-actions of this document

No production migration, Render or Supabase setting change, suspend, deploy,
push, password reset, grant/RLS/Data API change or live restore has been
performed or is authorized by this file.

## 9. Owner questions blocking GO

- **Q1** ANSWERED 2026-10-05 (REPORTED): Data API on, `public` exposed.
  Follow-up: will the owner disable the Data API, and have the API request
  logs been reviewed?
- **Q2** ANSWERED by read-only diagnosis: `postgres` via session pooler :5432.
  Owner REPORTED disabling the Data API on 2026-10-05. Still open: was the
  `postgres` password rotated on 2026-10-03, and by whom?
- **Q3** Frontend: does the live `2d063c91` frontend stay, or is the
  candidate frontend (20 files changed under `frontend/src` vs live) deployed,
  and in what order relative to W7? Read-only compatibility analysis
  (2026-10-05) is in §9a.

## 9a. Live frontend (`2d063c91`) against the candidate backend (`2ccb8652`)

Method: static source comparison of the two `git archive` trees, plus an
OpenAPI diff of both apps built locally (`create_app().openapi()`, SQLite, no
network). Nothing ran in a browser; runtime behaviour is NOT TESTED.

| Finding | Evidence | Label |
| --- | --- | --- |
| Declared API contract unchanged | Both OpenAPI documents have identical operations and schemas (75,393 bytes each) | VERIFIED |
| Response changes are additive fields | `generation` on datasets/scenarios; `evidence_status` and `evidence_reasons` on every scenario response (`scenario_out`); `selection_evidence` on workflow | VERIFIED in source |
| New server-side refusals | Scenario selection refuses non-current evidence (422); selection dataset-generation checks (409); the selected report chain calls `require_dependencies_current` (409); workflow withholds a non-current selected scenario | VERIFIED in source |
| Live Comparison page shows totals and the cost waterfall for any selected scenario | `oldcode/frontend/src/pages/ComparisonPage.tsx:520` (`totals && operationallyComparable`) and `:605` (`totals && …CostWaterfall`); no `evidence_status` use anywhere in the live frontend source | VERIFIED in source |
| The candidate frontend adds exactly that gate | `isCurrentScenario` (= `evidence_status === 'CURRENT'`) gates totals, waterfall and selection, with a not-current warning and badge | VERIFIED in source |
| Live frontend shows the new refusals as a generic server error | `ComparisonPage.tsx:317`, `:509` render `t('errors.server')` | VERIFIED in source |
| Live Simulation page: a withheld selection shows "select a scenario first" instead of the reason | the candidate adds `selection_evidence` handling; the live page lacks it | INFERRED from source |
| Live cache defects (stale workflow evidence after an upload, Setup change or dataset delete) persist | fixed only in candidate commits `822d5053`, `e7e3cdae` | VERIFIED DEFECT per 2026-10-01 record; pre-existing, not new |

**Conclusion.** With the live frontend kept, nothing is expected to break at
the API level (INFERRED: additive fields, identical declared contract), and
decision-making actions stay protected server-side: a stale scenario cannot be
selected, and a stale report chain is refused. The Comparison page, however,
would still show current-looking totals and a cost waterfall for scenarios
the server reports as not current. Users would get the G-A server protections
without the G-A display protections, and refusals would appear as
"server error". Keeping the live frontend is therefore **fail-safe for
decisions but not for presentation**.

**Recommendation (PROPOSED).** Deploy the candidate frontend from the *same*
commit `2ccb8652`. It is already covered by CI run 36892385671 (frontend
job) and the local frontend runs, so no new code review is needed. Do it in
the window after W8 passes and before W9: Pages production deploy of
`2ccb8652`, then re-verify. Residual risks:
- Browser tabs opened before the window keep the old JavaScript until reloaded (INFERRED). Without the excluded fence there is no forced reload.
- Legacy `novaq-frontend.onrender.com` would keep serving the old frontend unless it is also deployed or retired. That needs an owner decision.

**Owner decision 2026-10-05 (in chat):** ship the candidate frontend
(`2ccb8652`) in the release window, and retire the legacy static site.

**Legacy static site retired (executed on owner instruction, 2026-10-05
~09:44 UTC).** Before acting, Claude verified the target in the Render
dashboard: static site `novaq-frontend`, `srv-daijlcp5efls73dq41v0`,
`https://novaq-frontend.onrender.com`, branch `main`, live `2d063c9`. Claude
**suspended** it (dashboard "Suspend Static Site" with the typed confirmation
phrase) and did **not** delete it; Resume restores it. Render then showed
"novaq-frontend has been suspended." and offered "Resume Static Site". External
probes at 09:45 UTC:
- `https://novaq-frontend.onrender.com/` and `/api/ready`: **503**, page title "Service Suspended" ("suspended by its owner").
- `https://novaq.site/`: 200. `https://novaq.site/api/ready`: 200 `{"status":"ready"}`.

The F4 entry-point list loses the legacy static rewrite. Deleting the site
permanently would be a separate owner decision. Side evidence for D-1: a
suspended Render **static site** answers 503 "Service Suspended". A suspended
**web service** may behave differently and still needs D-1.

**Browser demonstration, 2026-10-05 (local only, VERIFIED).** Setup:
- Candidate API `2ccb8652` served by uvicorn on 127.0.0.1:8000 (development mode) over a scratchpad SQLite database migrated to `0005`.
- Data: the candidate test fixture `_workspace` (user `owner@example.com`, analysis 1, scenario "Lean plan"), with `dataset_generation` recorded. The server reported `CURRENT`. A newer valid dataset was then added, and the server reported `STALE_DATASET` ("Scenario is stale for the current dataset.").
- Onboarding was marked complete in the demo database so both SPAs open the Comparison page.
- The live frontend (`2d063c91`, `npm ci` from its own lockfile) ran on :5175 and the candidate frontend on :5174, both through the Vite `/api` proxy.

| Comparison page, analysis 1 | Live frontend `2d063c91` | Candidate frontend `2ccb8652` |
| --- | --- | --- |
| Totals cards (₱100 → ₱50, 50.0%) | shown | hidden |
| "Staffing Reduction Possible" insight | shown | hidden |
| Any stale / not-current indication | none | "Stale: dataset replaced — Not current: totals and selection are unavailable. Scenario is stale for the current dataset." |
| "Select for Simulation" | enabled; click → `POST /api/analyses/1/workflow/selection` **422**, UI shows "The server encountered an error. Please try again." | disabled |
| Per-period operations table and charts | shown | shown |

This confirms §9a by observation: the live frontend presents stale evidence as
current and hides the server's refusal reason. The candidate frontend does
not. The demo used synthetic data on a local stack, not production.
- **Q4** ANSWERED 2026-10-05 (owner, in chat): `1fbe812c` and its two
  parents stay **out** of the G-A release. The release candidate remains
  `2ccb8652`. Live-frontend compatibility with that backend is being checked
  read-only (see Q3).
- **Q5** Approve the §2 design decisions, then authorize D-1 and R-1 separately.

Sources: <https://render.com/docs/free>, <https://render.com/docs/deploys>,
<https://render.com/docs/blueprint-spec>,
<https://render.com/docs/configure-environment-variables>,
<https://render.com/changelog/suspend-and-resume-services-in-bulk-from-the-render-dashboard>,
<https://api-docs.render.com/reference/suspend-service-1>,
<https://supabase.com/docs/guides/api/securing-your-api>.
