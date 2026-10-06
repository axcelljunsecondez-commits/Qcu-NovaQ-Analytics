# G8 G-A release closure plan — local preparation only

Status on 2026-10-04: **PARTIAL; production `0005` NO-GO.** This plan is not
an execution authorization. The release policy is
`../specs/2026-10-04-g8-release-policy.md`; the underlying generation
contract is `../specs/2026-09-26-generation-identity-contract.md`.

## Frozen candidate and protected scope

- Candidate at review time: `2ccb86527a0f48928e4d5c26f3d9bd5f0e6abc35`.
  Re-pin the exact commit and inspect the final diff before any later release.
- The reviewed code head is Alembic `0005`; generation enforcement remains
  off in G-A. No mathematical, analytical, optimization, DES, API or data
  semantics are changed by this document.
- Owner policy: Option A, planned maintenance, exact-head production guard,
  backup-first recovery. Do not count old-code restart or zero downtime as a
  recovery path.

## Evidence already obtained

| Check | Evidence | Classification |
| --- | --- | --- |
| Exact-commit CI | GitHub run 36892385671: 11 jobs succeeded for the pinned SHA. | VERIFIED for that SHA |
| Isolated migration | The prior disposable PostgreSQL 17 restore and `0005` rehearsal completed. | VERIFIED only for that rehearsal |
| Isolated application | Health/readiness endpoints returned 200. Owner reported Google login, Analysis opening and logout. | Endpoint checks VERIFIED; browser outcomes REPORTED |
| Local backend suite | `python -m pytest tests/ -x --tb=short` exited 0 on Windows Python 3.13: 1,580 passed, 118 skipped, 1 xfailed, 6 subtests passed (2026-10-04 run). `NOVAQ_TEST_DATABASE_URL` was absent, so PostgreSQL-only cases were skipped locally. | VERIFIED local result; PostgreSQL variants NOT TESTED locally |
| Render service | Read-only connector: `srv-daiikrbm8hqs73d15rtg`; one Free Python instance; auto-deploy off; live deploy `2d063c91a929f5845be2e9d0243d6d5609b257a1`; Start Command `alembic upgrade head && uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT`. | VERIFIED on 2026-10-04 |
| Render deployment rules | Published Render docs say normal web-service deployment keeps the old instance serving during new-instance startup, a pre-deploy command is available to paid web services, and built-in maintenance mode requires a paid plan. The observed service is Free. Sources: <https://render.com/docs/deploys>, <https://render.com/docs/blueprint-spec>. | VERIFIED platform documentation on 2026-10-05; this service's actual traffic control UNKNOWN |
| Current production database | Read-only Supabase query returned PostgreSQL 17.6, one Alembic row at `0004`, and nine `public` tables. The query role was `postgres`, so the Render application's role is unverified. | VERIFIED on 2026-10-04; application role UNKNOWN |
| Public schema access | The same query returned zero RLS-enabled `public` tables and 126 grant rows for `anon`/`authenticated`. It did not inspect Supabase Data API settings. | Grants and RLS VERIFIED; Data API exposure UNKNOWN |
| Supabase security advisor | The connector returned an empty security-lint list. This does not establish that the Data API is disabled or that the verified grants are safe. | VERIFIED advisor result; exposure UNKNOWN |
| Migrated-candidate calculation and exports | No post-`0005` calculation, PDF or Excel application check recorded. | NOT TESTED |
| Local frontend suite | Earlier default Windows run reported two failures and did not finish; a serial run passed 388 tests. On 2026-10-05, full `npm test -- --reporter=verbose` and then exact plain `npm test` each exited 0 with 53 files / 388 tests. All three `SetupChangeWorkflowCache` tests passed in the verbose run. The cause of the earlier difference remains UNKNOWN. | Two current full runs VERIFIED; historical discrepancy unexplained |
| Existing encrypted backup | The local Downloads copy was rehashed read-only on 2026-10-05: 389,382 bytes, SHA-256 `d76bda9accb61aeb1539e6051c0f62abc28227103edcc053dac9aa643a1f199c`, matching the earlier recorded archive hash. This does not verify the OneDrive copy, passphrase or release-time freshness. | Local encrypted copy VERIFIED; release-time gate UNKNOWN |

The current database row above came from `supabase_execute_sql` for project
`cltvswcopkjvnonjutre`, using only `SELECT` expressions: `current_database()`,
`current_user`, `current_setting('server_version')`, count/min of
`public.alembic_version`, counts of `pg_catalog.pg_class` `public` tables and
`relrowsecurity`, and a count of `information_schema.role_table_grants` for
`anon`/`authenticated`. A second read-only query grouped those grants by
role and privilege: each role has nine table grants for DELETE, INSERT,
REFERENCES, SELECT, TRIGGER, TRUNCATE and UPDATE. No application table rows or
credentials were queried or copied into this plan. Repeating these checks at
release time still requires confirming the project identity and read-only
intent.

The read-only queries executed for these current facts were:

```sql
SELECT current_database() AS database_name,
       current_user AS connected_role,
       current_setting('server_version') AS server_version,
       (SELECT count(*) FROM public.alembic_version) AS alembic_rows,
       (SELECT min(version_num) FROM public.alembic_version) AS alembic_version,
       (SELECT count(*) FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')) AS public_tables,
       (SELECT count(*) FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
          AND c.relrowsecurity) AS rls_enabled_tables,
       (SELECT count(*) FROM information_schema.role_table_grants
        WHERE table_schema = 'public'
          AND grantee IN ('anon', 'authenticated')) AS anon_authenticated_grant_rows;

SELECT grantee, privilege_type, count(*) AS table_count
FROM information_schema.role_table_grants
WHERE table_schema = 'public'
  AND grantee IN ('anon', 'authenticated')
GROUP BY grantee, privilege_type
ORDER BY grantee, privilege_type;
```

## Closure work, in order

1. **Review the contract and docs.** Confirm that the imported historical
   contract and 2026-10-04 policy record the approved exception precisely.
   Review this plan against `docs/operations.md` and the candidate source.
   Run documentation hygiene checks. Do not change code or migration logic to
   manufacture compatibility.
2. **Finish local gates.** The candidate backend suite and two full frontend
   runs passed locally as recorded above; previous Ruff, mypy, frontend
   typecheck, lint and build runs passed. Keep those executions separate from
   the exact-commit CI success. Investigate the historical default frontend
   discrepancy before treating it as explained; do not weaken a test or
   acceptance threshold. Re-run gates on a changed release commit.
3. **Complete isolated application recovery evidence if required for release.**
   Under an applicable isolated rehearsal authorization, verify the
   encrypted archive and restore into an isolated PostgreSQL 17 target. Check
   revision, every public table, ownership and sequences; then exercise login,
   Analysis, a calculation, PDF, Excel and logout. Use private credentials
   only in their intended prompts. Dispose only of the isolated environment.
4. **Establish fresh production facts read-only.** Verify PostgreSQL version,
   Alembic revision, effective application role and access to
   `alembic_version`; verify relevant schema and data counts again at the
   release boundary. Independently establish Supabase Data API exposure and
   review the verified `public` grants and zero-RLS result before making any
   public-access security claim. Do not change grants or RLS through this G8
   plan. Cross-check
   Render service, code commit, root directory, served app, Start Command,
   any pre-deploy command, instance count, deployment overlap and all restart
   and rollback paths. Demonstrate a traffic-control method applicable to the
   current Free service; do not assume built-in maintenance mode or a
   pre-deploy command is available. The reported backup-time `0004` is not a
   substitute.
5. **Design the exact cutover.** Review a maintenance-window procedure that
   prevents the current automatic Start Command from applying an unreviewed
   migration. Name a one-shot migration runner and its connection/TLS method,
   with a preflight that proves the target is the approved production database.
   The candidate command `alembic -c alembic.ini upgrade 0005` is only
   PROPOSED for production; it must not run until the complete procedure and
   authorization are in place. Explicitly prevent the old application from
   serving incompatible reads or writes while schema and code differ. Specify
   traffic handling, command order,
   immediately checked `0005` revision and `migration_status`, matching-code
   deployment, readiness, app smoke, metrics and stop conditions.
6. **Prove recovery and public gates.** Verify an encrypted off-host backup,
   checksums, decryption key availability and recent isolated restore;
   prepare a reviewed backup-first recovery target and traffic cutover. Check
   the remaining security, TLS, SMTP, edge, firewall, secret-permission and
   monitoring gates in `docs/operations.md`. If any fails, remain NO-GO.
7. **Decision and authorization.** Present the packet with exact commands,
   commit, revision, backup, operator, stop points and recovery. Obtain a
   separate explicit owner authorization before any production migration,
   Render setting change, deployment, push or live restore.

## Stop rules

Stop the affected work on a checksum mismatch, decryption or TLS failure,
unexpected schema/dependency, unknown command target, failed test, unexplained
frontend discrepancy, app smoke failure, or any unapproved change. Preserve
evidence and the encrypted backup. Do not infer production success from a
local rehearsal or CI.
