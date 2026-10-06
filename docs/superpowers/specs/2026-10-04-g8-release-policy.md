# G8 G-A release policy — approved decision, execution gated

Date: 2026-10-04. Target candidate at decision time:
`2ccb86527a0f48928e4d5c26f3d9bd5f0e6abc35` on `port/g-a-stage1`.

## Decision and scope

**APPROVED SPECIFICATION:** The owner selected Option A in this chat on
2026-10-04. For the G-A production release only, retain the G7 production
exact-head Alembic guard. Plan a maintenance window for migration `0005`,
deploy the matching G-A code only after the schema is verified at `0005`, and
use backup-first recovery if the cutover fails. Do not claim continuous
availability or a restartable rollback to the older backend.

This decision supersedes the older-backend availability half of §1 rule 6 of
`2026-09-26-generation-identity-contract.md` **for this G-A release**. The
newer-backend refusal on an unmigrated schema and the G7 fail-closed guard stay
in force. No queueing mathematics, analytical semantics, data, migration logic,
API contract, or generation-enforcement flag changes are approved here.

The owner authorized local release preparation. This document does **not**
authorize a production migration, Render change, deployment, push, database
restore, password reset or infrastructure change. Each needs its own reviewed
scope and authorization. G-B/G9 remains outside this decision.

## Why maintenance is required

**VERIFIED in candidate source:** `backend/api/main.py` installs the G7 guard
when `Settings.environment == "production"`; it requires the live database
heads to equal the code heads, and `/ready` checks again. The candidate head is
`0005`. The historical contract §11.1–11.3 records that a pre-G release is
not a verified restartable release on `0005` through its migration-checking
startup path. Neither old-code rollback nor zero-downtime overlap is a
recovery promise.

**VERIFIED from the read-only Render connector on 2026-10-04:** The current
`Qcu-NovaQ-Analytics` service (`srv-daiikrbm8hqs73d15rtg`) is a single Free
Python instance in Singapore, with auto-deploy off. Its live deploy is
`2d063c91a929f5845be2e9d0243d6d5609b257a1`. Its Start Command is
`alembic upgrade head && uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT`,
so starting candidate code through that command can invoke `0005`
automatically. This is an inference from the verified command and candidate
head, not an observed migration. The exact production runner and cutover order
must be reviewed before any deployment. No isolated edit to the Start Command
is approved. The connector did not establish a pre-deploy command or this
service's actual deploy overlap behaviour.

**VERIFIED in Render's published deployment documentation on 2026-10-05:**
The normal web-service deploy sequence keeps the old instance receiving
traffic while the new one starts. A pre-deploy command is available to paid
web services, private services and background workers; built-in maintenance
mode requires a paid compute plan. The observed service is Free. These
platform rules do not prove this service's exact deployment behaviour or
provide a maintenance control for it. The traffic-control method, migration
runner and cutover order remain **UNKNOWN** and must be demonstrated before
GO. Sources: <https://render.com/docs/deploys> and
<https://render.com/docs/blueprint-spec>.

## Required release gates

All gates below must have current evidence in a release packet before a
production GO decision:

1. Pin the exact candidate commit, tree status, migration head, production
   service identity, environment, served application object, working directory,
   instance count, Start Command, deploy overlap and every start/restart/rollback
   path. Resolve the verified automatic migration command in a reviewed cutover
   sequence that prevents an unintended migration. Demonstrate the actual
   maintenance traffic control on the current service and plan.
2. Read production PostgreSQL version (at least 13), Alembic revision
   (`0004` before cutover), role privileges and relevant schema facts through
   read-only checks. Stop on any difference from the rehearsal baseline.
3. Verify the release-time encrypted off-host backup, its manifest and
   checksums, key availability, age, and an isolated restore result. Keep
   plaintext and credentials out of the release packet. Validate the recovery
   destination and operator access before the maintenance window.
4. Re-run the required clean-clone source, CI, tests, security and public
   operational gates in `docs/operations.md`. Explain or resolve the local
   default frontend-test discrepancy. Complete any required migrated-candidate
   calculation and PDF/Excel smoke checks in isolation.
5. Prepare and review exact maintenance entry, traffic handling, the one-shot
   `alembic -c alembic.ini upgrade 0005` mechanism, immediate revision and
   `migration_status` checks, matching-code deployment, readiness, login,
   Analysis, calculation, report and monitoring checks. Pin stop points and
   backup-first recovery. Reconfirm every command target immediately before
   execution. The proposed one-shot command is **NOT EXECUTED in production**.
6. Obtain separate explicit authorization for the reviewed production sequence.
   A successful isolated rehearsal or CI run cannot replace this step.

**NO-GO** if any required gate is missing, failed, conflicting or unexplained.
Do not use `alembic downgrade` as the production recovery assumption. Stop and
preserve evidence on a failed migration, readiness, data-integrity, login,
calculation, report or monitoring check. Backup-first recovery is a separate,
reviewed action; never restore over the live database by default.

## Evidence at decision time

- **VERIFIED:** The exact-commit GitHub Actions run
  <https://github.com/axcelljunsecondez-commits/Qcu-NovaQ-Analytics/actions/runs/36892385671>
  completed successfully with 11 successful jobs. This is CI evidence for the
  pinned commit only.
- **VERIFIED for an isolated rehearsal only:** A disposable PostgreSQL 17
  restore of the encrypted pre-`0005` backup and `0005` migration was checked;
  it does not establish current production state or release readiness.
- **REPORTED by the owner:** Google sign-in, opening an existing Analysis and
  logout succeeded in the isolated candidate application.
- **NOT TESTED in that migrated-candidate application rehearsal:**
  calculations and PDF/Excel exports.
- **VERIFIED:** The Render service identity, plan, instance count, live commit,
  Start Command and auto-deploy setting named above.
- **VERIFIED by a read-only Supabase query on 2026-10-04:** The project
  `cltvswcopkjvnonjutre` returned PostgreSQL `17.6`, one Alembic row at
  `0004`, nine `public` tables, zero with RLS enabled, and 126
  `information_schema.role_table_grants` rows for `anon` and
  `authenticated`. The query connected as `postgres`; it did not establish
  the Render application's database role or Data API exposure. The connector's
  project list was empty, but direct project lookup and SQL query succeeded.
- **UNKNOWN:** Service-specific Render deployment overlap and maintenance
  traffic control, effective application role,
  Supabase Data API exposure, release-time backup freshness, and full public
  operational readiness. The public grants/RLS result must be reviewed as a
  separate security gate; this release policy authorizes no grant or RLS edit.

The historical contract was restored from local Git blob
`bf02d4ad:docs/superpowers/specs/2026-09-26-generation-identity-contract.md`
before this policy note was added. Its earlier “G8 not started” statements
describe that historical point in time and do not constitute a current release
authorization.
