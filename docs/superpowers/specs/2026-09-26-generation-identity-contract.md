# Generation Identity — Implementation Contract (ACCEPTED; G1, G1-H, G2, G3, G4, G5, G6 and G7 committed locally)

> **2026-10-04 G8 policy update:** The product owner selected Option A for the
> G-A release: retain the production exact-head guard and use a planned maintenance
> window with backup-first recovery. The older-backend availability requirement in
> §1 rule 6 is superseded for this release by
> [the G8 release policy](2026-10-04-g8-release-policy.md). Historical test and
> deployment statements below remain scoped to when they were recorded. This
> update authorizes no production migration, configuration change or deployment.

- **Status:** APPROVED SPECIFICATION. The design direction was accepted on 2026-09-26, and this
  contract on 2026-09-28, with OD-G2 approved (§8) and the legacy policy (§6) confirmed.
  - Approval sets the intended engineering behaviour. It does not show that the migration, the
    application integration or a production deployment is ready.
  - This document is a specification only. It authorizes no migration, model, endpoint,
    configuration, engine-version or production change, and no stage in §14.
  - Stages in the repository, all local and unpushed on `fix/d1-replication-costs`:
    - G1: migration 0005 and the model fields, committed provisionally as `1f5c3ab3`. Its status
      is **PROVISIONALLY COMMITTED — SQLITE AND LOCAL POSTGRESQL 18.6 VERIFIED; CI AND PRODUCTION
      GATES PENDING** (§5.5).
    - G1-H: persistence-layer immutability and non-reuse of the token, hardened into 0005 in
      place, committed as `05d64083` (§3, §5.5).
    - G2: creation stamping, committed as `f495f0bd`. Its status is **COMMITTED — G-T1 VERIFIED
      ON SQLITE AND LOCAL POSTGRESQL 18.6, EXCEPT ONE POSTGRESQL VARIANT NOT RUN; CI AND
      PRODUCTION GATES PENDING** (§7.1).
    - G3: job and selection stamping and the OD-G2 write gates, with enforcement off, committed as
      `cb7f78be`. Its status is **COMMITTED — TARGETED SQLITE AND LOCAL POSTGRESQL 18.6
      VERIFICATION; FULL POSTGRESQL SUITE, CI AND PRODUCTION GATES PENDING** (§7.2).
    - G4: generation identity in the evidence classifier, committed as `446a1e18`. The generation
      check is **off by default**, and no application code turns it on. Its status is **COMMITTED
      — CLASSIFIER TESTS, FULL SQLITE SUITE AND A TARGETED LOCAL POSTGRESQL 18.6 RUN VERIFIED;
      FULL POSTGRESQL SUITE, CI AND PRODUCTION GATES PENDING** (§9.1).
    - G5: enforcement wiring in `workflow.py`, committed as `1b8a8bd2`. The wiring exists, but
      `GENERATION_ENFORCEMENT_ENABLED = False` and no application code turns it on, so the
      application's default behaviour is **enforcement off**. Its status is **COMMITTED — WIRING
      VERIFIED ONLY BY TESTS THAT SWITCH THE FLAG ON, ON SQLITE AND A TARGETED LOCAL POSTGRESQL 18.6
      RUN; FULL POSTGRESQL SUITE, CI AND PRODUCTION GATES PENDING** (§8.2).
    - G6: Decisions and reports under enforcement, committed as `4e89b7a8`. It adds one
      enforcement-only check on the selection's dataset generation at both Decision endpoints and
      pins G-T7 and G-T8 with tests; `reports.py` needed no change. The flag is still off. Its status
      is **COMMITTED — VERIFIED ONLY BY TESTS THAT SWITCH THE FLAG ON, ON SQLITE AND A TARGETED LOCAL
      POSTGRESQL 18.6 RUN; FULL POSTGRESQL SUITE, CI AND PRODUCTION GATES PENDING** (§10.1).
    - G7: the production startup and readiness guard on the database's Alembic heads, committed as
      `e64b50cc`. It applies only when `Settings.environment == "production"`, requires exact head
      equality, fails closed, and is independent of generation enforcement. Its status is
      **COMMITTED — VERIFIED BY TESTS ON SQLITE AND A TARGETED LOCAL POSTGRESQL 18.6 RUN; FULL
      POSTGRESQL SUITE, CI, PRODUCTION PINS AND PRODUCTION GATES PENDING** (§11.4). It is in
      CONFLICT with §1 rule 6 once a later migration exists (§1).
  - Nothing after G7 is implemented: G8–G9 are not started and not authorized. Enforcement is not
    active in the application: `GENERATION_ENFORCEMENT_ENABLED = False`, so its default behaviour is
    enforcement off. Behaviour with enforcement on is tested only with the flag switched on in
    tests, for G5's consumers (§8.2) and for the Decision and report paths (G6, §10.1). The
    exact-generation defect is not resolved in the running application (§6.2).
  - G-A (2026-10-01): G1–G7 are ported to `port/g-a-stage1` (`92d95bed`), and the G-A
    implementation milestone is complete there at `e7e3cdae` (plan Step 0, "G-A implementation
    completion record").
    - Under owner decision OD-GA-C1 (plan Step 0), the "CI … gates pending" in the stage statuses
      above are release and integration assurance, not prerequisites of that milestone. CI is NOT
      RUN and PostgreSQL 16 is NOT TESTED, and G8 or a release may still require them.
    - Under OD-GA-C2, the exact-generation defect stays open in G-A, and G-B/G9 must close it
      (§6.2).
- **Base:** `4db54722` (interim Step 5 commit) on `fix/d1-replication-costs`. Historical: at that
  base the repository had no migration 0005 and no generation code (VERIFIED then by grep and file
  listing). Since `1f5c3ab3` it has both.
- **Related:** spec `2026-09-25-analytical-versioning-historical-evidence.md` §5.4 (the release
  blocker) and §3.1 (corrected identity table); plan Steps 5 and 9; `docs/operations.md` (release
  and rollback runbook).
- **Prototype (historical):** everything marked "in the prototype", including §5.3 and all of
  §15, was run only in scratchpad copies of `4db54722` (`gen_base` = committed code, `gen_proto` =
  prototype), against disposable SQLite files and disposable PostgreSQL 16.15 containers. It is
  not evidence for the committed 0005, whose own status is in §5.5.
- **Evidence labels:** VERIFIED, APPROVED SPECIFICATION, REPORTED, PROPOSED, INFERRED, NOT TESTED,
  UNKNOWN, CONFLICTING. A VERIFIED result in §3–§6, §11 and §15 applies to the level that was
  actually run: the prototype migration, the committed 0005 on SQLite or on local PostgreSQL 18.6,
  the ORM models, or a throwaway app. It does not apply to the full NovaQ backend, to CI or to
  production.

## 1. Governing rules

1. A matching integer id, `created_at`, content, fingerprint or resolving foreign key never proves
   that a job used a given source row.
2. Every analytical job and every selection records the generation token of each source row it
   actually read. A different token is rejected even when the id, timestamp and content match.
3. No provenance is manufactured:
   - The migration **writes a newly assigned token into every existing dataset and scenario
     row**. The token identifies that row as it exists at migration time, and says nothing about
     jobs that referenced the row before.
   - No job or selection is ever given a token. They are never joined by integer id.
   - No legacy scenario gets a `dataset_generation`, even though its foreign key resolves.
4. Missing provenance stays missing: `GENERATION_UNRECORDED` is never current. Current analytical
   use then requires recalculation into a new artifact.
5. Generation identity and engine version are separate reasons, and neither implies the other.
   A token proves which record was used, not that its mathematics or accounting is current.
6. Service availability: an older backend must keep working on the migrated schema, and a newer
   backend must refuse to serve on an unmigrated one.
   - At 0005 the first half holds only at the ORM layer. A pre-G release does **not** start
     through the production Compose migration chain on 0005, because its own Alembic and
     `migration_status` reject the revision (§6.2, §11.1). ORM compatibility is not deployment
     startability.
   - **CONFLICTING since G7 (`e64b50cc`, §11.4).** The G7 production guard admits only a database
     exactly at the code's Alembic heads (§11.1, G-T16, decision D1). Once a later migration exists,
     a production backend that carries the guard refuses to start on the newer schema, although the
     first half of this rule says an older backend must keep working on a migrated schema. The
     second half (a newer backend refuses an unmigrated schema) holds. This conflict is recorded,
     not resolved; resolving it needs a separate decision.

## 2. Verified baseline (at `4db54722` unless stated)

| Fact | Evidence | Label |
|---|---|---|
| Dataset rows are created only in `analyses.py:218`, `analyses.py:271`, `datasets.py:112` | grep of `Dataset(` | VERIFIED |
| Scenario rows are created only in `scenarios.py:321` (`POST /scenarios`), which verifies against the `dataset` row loaded at `:274` | schema 1 `scenarios.py:232-238`; schema 2 `scenarios.py:159-180` | VERIFIED |
| Saved settings and results are immutable | `PATCH` returns 409 (`scenarios.py:381-386`); `ScenarioPatch` has only `name`, `settings`, `results` | VERIFIED |
| Every Job is built in `_save_job` (`workflow.py:518`), from 12 call sites. Corrected 2026-09-29: this row said "13 callers"; the count at `4db54722` and at `cb7f78be` is 12 calls plus the definition | grep of `Job(` in `backend/`; `_save_job(` call sites counted, definition excluded | VERIFIED |
| Evidence and selections are resolved by integer | `_job_matches` (`workflow.py:453`); `_selected_scenario` (`:540`); `_require_selected_separate_plan` (`:1792-1810`) | VERIFIED |
| Selected MC and validation have no dependency gate at write time; `run_validation_current` compares `dataset_id` inline (`:1100`) | source | VERIFIED |
| The dataset report reads no jobs (`reports.py:529-575`) | source | VERIFIED |
| Deletes are hard: `datasets.py:161`, `scenarios.py:406`; dataset → scenarios cascades in the ORM; there is no user-delete route | source | VERIFIED |
| `scenarios.dataset_id` foreign key is created in `0001:72`. PostgreSQL enforces it (dev database: `NO ACTION`); SQLite does not (no `PRAGMA foreign_keys`) | source, read-only dev query | VERIFIED |
| Alembic: `env.py` runs the whole upgrade inside one `begin_transaction()`. Alembic `SQLiteImpl.transactional_ddl = False` and `PostgresqlImpl.transactional_ddl = True` (local 1.19.1; production pins 1.19.2) | source, runtime check | VERIFIED |
| Image: `Dockerfile.api` copies `alembic.ini` and `migrations/`; `CMD ["/bin/sh", "/app/backend/api/entrypoint.sh"]` | source | VERIFIED |
| `entrypoint.sh` runs `backend.operations.preflight` (settings only), then uvicorn `backend.api.main:app` | source | VERIFIED |
| `create_app` has no startup hook; `app = create_app()` runs at import (`main.py:266`); `/ready` is `SELECT 1`. Since G7 (`e64b50cc`): a production app has a lifespan guard and its `/ready` also checks the Alembic heads; `app = create_app()` is at `main.py:315` (§11.4) | source | VERIFIED |
| `migration_status` exits 1 on any head mismatch | source; run in the prototype | VERIFIED |
| Production Compose orders migrate → bootstrap-admin → api (`depends_on … service_completed_successfully`); the `migrate` service runs `alembic upgrade head && migration_status` | `docker-compose.production.yml` | VERIFIED |
| Runbook: "Rollback is backup-first, not `alembic downgrade`" (`operations.md:216-220`); "Migration failure prevents API startup" describes the Compose ordering | `docs/operations.md` | VERIFIED (document) |
| Production settings require `API_WORKERS=1` (`settings.py:238`) | source | VERIFIED |
| The hosted API is the Render web service `Qcu-NovaQ-Analytics`; pushing `main` deploys Render and Pages | `memory.md:185-188`, `handoff.md:256-257` | REPORTED |
| The hosted database is Supabase | 2026-09-14 spec, plan and report | REPORTED |
| The repository holds no Render blueprint or start command (`render.yaml`, Procfile); Render's runtime, start command, pre-deploy command, instance count and deploy overlap are not recorded | file search | VERIFIED absence; the settings are **UNKNOWN** |

## 3. The token

- Written as 32 lowercase hex characters (`^[0-9a-f]{32}$`), generated independently of id, time
  and content. The random-bit count depends on the generator:

  | Generator | Random bits | Evidence |
  |---|---|---|
  | Application default `uuid.uuid4().hex` | 122: a version-4 UUID, so the 13th hex character is always `4` and the 17th is one of `8`–`b` | VERIFIED: 50,000 samples, all distinct, only those two positions restricted |
  | PostgreSQL default `replace(gen_random_uuid()::text,'-','')` | 122: a version-4 UUID | INFERRED from the PostgreSQL documentation; not measured |
  | SQLite default `lower(hex(randomblob(16)))` | 128 | VERIFIED: 50,000 samples on SQLite 3.50.4, all distinct, no restricted position |

- Consumers accept any value in the specified 32-hex format. They compare tokens as opaque
  strings and never require or assume UUID version or variant bits.
- One per row in `datasets.generation` and `scenarios.generation`: NOT NULL, unique
  (`uq_<table>_generation`).
- Immutable after insert and never reissued (APPROVED SPECIFICATION).
  - Historical: at G1 (`1f5c3ab3`) neither property was enforced. On SQLite (VERIFIED then, by a
    scratchpad probe), NOT NULL and UNIQUE refused neither an `UPDATE` to a fresh token nor an
    insert that reused a deleted row's token.
  - Since G1-H (`05d64083`) the database enforces both for `generation`. Sources:
    `migrations/versions/0005_generation_identity.py` (docstring and DDL) and
    `backend/db/generation_guards.py` (VERIFIED by inspection). The refusals are VERIFIED on SQLite
    by the module's tests in the full suite on the `f495f0bd` tree; on PostgreSQL 18.6 they are
    REPORTED (§5.5).
    - `generation_registry` records every issued token per table (`table_name`, `token`,
      `row_id`, `registered_at`). It has no foreign key, so a registration outlives its row.
    - Triggers refuse any change to a set token and any reissue of a registered token. They also
      refuse registry `UPDATE` and `DELETE`, and on PostgreSQL `TRUNCATE`. SQLite `OR IGNORE` /
      `OR REPLACE` and PostgreSQL `ON CONFLICT` do not bypass them.
    - Uniqueness is per table: a dataset and a scenario may hold the same token.
  - Trust boundary (documented in the 0005 docstring): a PostgreSQL table owner or superuser can
    disable or drop the triggers, and whoever owns a SQLite file can change anything in it. The
    integer id is not made immutable.
- `scenarios.dataset_generation` is **not** covered by these guards: they check only `generation`
  (`generation_guards.py:64-69`, `:84-91`; VERIFIED by inspection).
- Application writes (VERIFIED by grep at `f495f0bd`): the model default sets `generation` on
  insert, and `create_scenario` sets `dataset_generation` on insert (§7). No application path
  writes either column after insert. `PATCH` cannot reach them (`ScenarioPatch` has only `name`,
  `settings`, `results`), and client-supplied values are ignored (§7.1).
- `scenarios.dataset_generation` records the dataset token that the save verified. It is nullable,
  has no default of any kind, and only the scenario save path writes it, and only when the save
  verified a calculation snapshot against that dataset (§7).

## 4. Application default vs database default

| Layer | Value | Role |
|---|---|---|
| Application: model `default=new_generation` (`uuid.uuid4().hex`) | set by every ORM insert, before flush | authoritative; known inside the same transaction |
| Database: default installed by 0005 | PostgreSQL `replace(gen_random_uuid()::text,'-','')`; SQLite `lower(hex(randomblob(16)))` | safety net for inserts that omit the column (an older backend on 0005, raw SQL) |

- Both layers give the same 32-hex format; the random-bit count differs by generator (§3). The
  format was VERIFIED on both engines in the prototype. For the committed 0005 it is VERIFIED on
  SQLite and on local PostgreSQL 18.6 (§5.5). An ORM insert always supplies the application value.
- `create_all` builds (tests; `seed.py` on an empty database) get NOT NULL, unique and the
  application default, but no database default. This is documented and deliberate; M2 covers the
  database default.
  - Since G1-H they also get the registry and the same guards, installed by
    `generation_guards.register` (`generation_guards.py:156-164`). `create_all` refuses to add the
    registry to existing `datasets` and `scenarios` tables and asks for migration 0005 instead
    (`:142-148`), so seeding a 0004 database fails closed.
- `gen_random_uuid()` is built into PostgreSQL 13 and later. The production version is UNKNOWN,
  which is a stop condition.

## 5. Migration 0005

Migration 0005 is in the repository as `migrations/versions/0005_generation_identity.py`,
committed provisionally in `1f5c3ab3` and hardened in place by G1-H in `05d64083` (both local,
unpushed). It follows the prototype design; §5.2 marks where it differs.

- Historical: before `1f5c3ab3`, this section described only a scratchpad prototype, and the
  repository had no 0005.
- §5.3 is prototype evidence. The committed migration's own verification status is §5.5, and
  its supported SQLite environment is §5.4.

### 5.1 What it writes

- **Every existing `datasets` and `scenarios` row gets a newly assigned token**, written into the
  new `generation` column. On SQLite the constraint step rebuilds both tables (Alembic batch mode
  copies every row into a new table).
- All pre-existing column values of those rows are unchanged. VERIFIED by a digest of every
  original column, before and after: in the prototype on both engines, and for the committed
  0005 on SQLite and on local PostgreSQL 18.6 (§5.5).
- `scenarios.dataset_generation` is added and left NULL for every existing row: the relationship
  cannot be established.
- The `jobs` table is not written. VERIFIED by a digest of every stored job row, with the same
  engine coverage.
- No job's params or results are touched, and no analytical claim is rewritten.

### 5.2 Structure

Helpers are shared by `upgrade()` and the recovery tests:

- `upgrade_table(table)`:
  1. On SQLite, drop a leftover `_alembic_tmp_<table>` only if `<table>` itself still exists.
     Otherwise refuse, because the leftover may hold the only copy of the rows. (Committed 0005;
     the prototype dropped any leftover.)
  2. Add a nullable `generation` if it is absent.
  3. `UPDATE … SET generation = <token> WHERE generation IS NULL`. An existing token is never
     replaced.
  4. **Refuse duplicated tokens** with an explicit error. They are never regenerated.
  5. If the column is nullable, has no database default, or `uq_<table>_generation` is absent,
     set NOT NULL plus the database default and add any missing constraint. (Committed 0005; the
     prototype did not check the default.)
- `add_dataset_generation()`: add the column if it is absent.
- `assert_postconditions()`: raise unless both `generation` columns exist, are NOT NULL, have a
  database default and their unique constraint, no row lacks a token, and
  `scenarios.dataset_generation` exists. The committed 0005 also requires
  `scenarios.dataset_generation` to be nullable with no default.
- `upgrade()` = `upgrade_table("datasets")`, `upgrade_table("scenarios")`,
  `add_dataset_generation()`, then (since G1-H) `create_registry()`, `backfill_registry()` and
  `install_guards()`, then `assert_postconditions()` (`0005_generation_identity.py:425-432`).
  Alembic records `0005` only after `upgrade()` returns, so it never records 0005 over a partial
  schema.
  - The guards are installed after the last table rebuild, because a SQLite batch rebuild drops
    the rebuilt table's triggers.
  - Since G1-H the post-conditions also require every live token to be registered to its own row
    and every guard to be present exactly as defined (`:384-422`). A registration that names a
    different row, or a registry with an unexpected structure, stops the upgrade and is never
    rewritten.
- An unsupported dialect raises. The committed 0005 also refuses PostgreSQL below 13, which lacks
  a built-in `gen_random_uuid()` (`_token_sql`).
- `downgrade()`: guarded drops, for **rehearsal only**. Production rollback is backup-first
  (`operations.md:216-220`). Since G1-H it removes the guards, the registry and the columns, then
  asserts that nothing is left (`:435-497`). Dropping the registry destroys the record of issued
  tokens, so a reissue is no longer refused after a downgrade.

### 5.3 Recovery behaviour (VERIFIED in the prototype, §15.2)

For the committed 0005, the recovery cases have passed on SQLite and on local PostgreSQL 18.6
(§5.5), and both rows below hold for it there. On PostgreSQL 16 and in CI they are NOT TESTED.

| Engine | What a failed run leaves behind | Why |
|---|---|---|
| PostgreSQL | nothing: `alembic_version` 0004, no new column | Transactional DDL; the upgrade runs in one transaction and is rolled back |
| SQLite | `datasets.generation`, nullable, with no tokens; `alembic_version` 0004; everything later is rolled back | Non-transactional DDL: the first `ADD COLUMN` commits before any row change. The first `UPDATE` opens a transaction that covers the remaining steps, including the batch rebuild |

- A plain retry completes from every state, on both engines.
- The first, unguarded prototype got stuck on SQLite (`duplicate column name`), which is why every
  step is guarded.

### 5.4 Supported SQLite migration environment

The committed 0005 is verified on SQLite only with foreign-key enforcement **off**. That is
SQLite's default, and neither `migrations/env.py` nor `backend/` issues `PRAGMA foreign_keys`
(VERIFIED by grep). With enforcement on, the migration is not safe in general. Scratchpad probe
on the committed 0005 (VERIFIED):

| Probe | Result |
|---|---|
| `PRAGMA foreign_keys=ON` on the migration connection, one scenario referencing a dataset | fails in the `datasets` batch rebuild at `DROP TABLE datasets` with `FOREIGN KEY constraint failed`. The database stays at 0004 with only `datasets.generation` added (nullable), and no leftover table |
| Retry with enforcement still on | fails the same way; state unchanged |
| Retry with enforcement off | completes; 0005 |
| Enforcement on, no scenarios | completes |
| `PRAGMA foreign_keys=OFF` issued inside an open transaction | no effect; enforcement stays on |

- Supported: SQLite connections without foreign-key enforcement during the migration. A
  deployment that turns it on, for example through a connect listener, must run 0005 on a
  connection where it is off from the start. It cannot be switched off once a transaction is open.
- PostgreSQL alters the tables in place rather than rebuilding them, so this failure is specific
  to the SQLite batch rebuild (INFERRED). On local PostgreSQL 18.6, which always enforces foreign
  keys, the committed 0005 upgrades seeded scenarios that reference datasets (§5.5).
- Whether any deployment uses SQLite is UNKNOWN (§16).

### 5.5 Verification status of the committed 0005

The table records the G1 migration (`1f5c3ab3`, gated at `11053465`). The G1-H migration is
covered by the bullets after it.

| Evidence | SQLite | PostgreSQL |
|---|---|---|
| `tests/test_generation_identity_migration.py` (62 items: M and R cases per engine, plus SQLite-only and model tests) | 34 passed | 28 passed, 0 skipped: local PostgreSQL 18.6, at `11053465` |
| `tests/test_postgres_migration_chain.py` (expects head 0005) | — | 3 passed, 0 skipped: local PostgreSQL 18.6, at `11053465` |
| Full backend suite on the G1 tree | 1275 passed, 31 skipped (the PostgreSQL cases above, without `NOVAQ_TEST_DATABASE_URL`), 1 xfailed (the strict MC xfail) | — |
| Scratchpad probes: old code on 0005 (§11.1), foreign keys (§5.4), token reassignment (§3) | VERIFIED | NOT TESTED |
| CI `postgres-integration` job (`postgres:16-alpine`; includes both files since `11053465`) | — | **NOT RUN** |
| PostgreSQL 16 | — | NOT TESTED: not executed locally |
| Production PostgreSQL | — | version **UNKNOWN**; nothing run |

- The local PostgreSQL run: an isolated PostgreSQL 18.6 cluster in WSL Ubuntu on
  `127.0.0.1:55432`, a non-superuser test role, and disposable databases created and dropped by the
  tests. All 31 required PostgreSQL cases (28 + 3) passed with 0 skipped; the whole run was 65
  passed, 0 skipped, 0 failed.
- This is local verification only. It is not CI verification (the CI job has not run), not
  PostgreSQL 16 verification, and not production verification.
- G1 is **PROVISIONALLY COMMITTED — SQLITE AND LOCAL POSTGRESQL 18.6 VERIFIED; CI AND PRODUCTION
  GATES PENDING**. Full application behaviour with enforcement on remains NOT TESTED (§6.2).
  Under OD-GA-C1 (2026-10-01, plan Step 0), the pending CI gate does not block the G-A
  implementation milestone. It stays release and integration assurance and is NOT RUN.
- Any later change to the migration, the models or these tests repeats every G1 gate on both
  engines. The results above do not verify a modified 0005.
- G1-H (`05d64083`) modified 0005, so the rule above applied to it:
  - REPORTED in the `05d64083` commit message, not re-run in the G2 session: SQLite full suite
    1340 passed, 94 PostgreSQL-only skips, 1 strict xfail; the generation and chain tests on WSL
    PostgreSQL 18.6 with zero skips; ruff and mypy clean.
  - VERIFIED in the G2 session on the `f495f0bd` tree: the SQLite full suite gave 1348 passed, 94
    skipped and 1 xfailed. All 94 skips need `NOVAQ_TEST_DATABASE_URL`: 91 are in
    `test_generation_identity_migration.py` (now 190 items) and 3 in
    `test_postgres_migration_chain.py`. On local PostgreSQL 18.6 the four `db_engine` tests of
    `test_generation_identity_migration.py` passed, including
    `test_create_all_guards_work_in_the_suite_schema`.
  - Not re-run in the G2 session: the hardened 0005's PostgreSQL migration and recovery cases.
    They create their databases through the cluster's `postgres` maintenance database, which the
    G2 session was not authorized to use.
- The §15 PostgreSQL results come from the prototype and do not substitute for this gate.

## 6. Legacy and compatibility-interval eligibility, stage by stage

### 6.1 Stages

- **S0:** today. Schema 0004, pre-G backend (`4db54722` rules).
- **S1:** schema 0005 while a pre-G backend still serves. This is the migration-first window, or a
  failed new deploy.
- **S2 (release G-A):** schema 0005, new backend stamping tokens, enforcement off.
- **S3:** enforcement on.
- **S4:** engine v3 on. S3 and S4 ship in one release (G-B), per the 2026-09-26 decision to
  coordinate with v3.
  - Their effects are listed separately here.
  - Engine v3 remains a separate analytical-compatibility requirement (plan Steps 7–9). This
    contract neither defines it nor changes any engine version.
- **R:** rollback or re-upgrade.

### 6.2 Evidence by stage

"Step 5 rules" means the current gate: existence, owner and analysis scope, chronology, current
dataset and setup (Steps 1–5 and Option A).

- The S2–S4 columns are specified behaviour (APPROVED SPECIFICATION).
  - S2 stamping and the OD-G2 write gates are implemented (G2, G3; §7.1, §7.2).
  - The S3 checks are wired but switched off (G5, §8.2), so the application is not in S3.
  - S4 is not implemented.
- Application behaviour in S3 is tested only with the flag switched on in tests: G5's tests of its
  own consumers (§8.2) and G6's tests of the Decision and report paths (§10.1). S4 is NOT TESTED.

| Artifact | S0 | S1 | S2 | S3 | S4 (v3) |
|---|---|---|---|---|---|
| **Existing datasets** | usable | usable; token assigned by the migration | usable; token read by stamping | usable as a source; new evidence stamps the token | unchanged: datasets carry no engine |
| **Existing scenarios** (`dataset_generation` NULL) | Step 5 rules | same | same: eligible under Step 5 rules, and jobs on them are stamped | **not eligible**: `GENERATION_UNRECORDED` on the dataset binding; `_own_verified_scenario` 422 "recalculate and save a new plan" | also `HISTORICAL_REQUIRES_RECALCULATION` for v2 separate plans (engine reason, kept separate) |
| **Scenarios saved in S1** (pre-G code; database-default token; `dataset_generation` NULL) | — | Step 5 rules | Step 5 rules | not eligible (as legacy) | as legacy |
| **Scenarios saved in S2 or later** (`dataset_generation` stamped) | — | — | Step 5 rules | eligible when tokens match | v2 separate plans become historical under v3 |
| **Existing selections** (no token) | Step 5 rules; the reused-id rebind defect exists | same | same | **no eligible selection** (Option A: `decision_stale` false, "select a scenario") | same |
| **Selections made in S2 or later** (stamped) | — | — | Step 5 rules | eligible only if the token equals the scenario row's | also subject to the scenario's engine status |
| **Existing Current DES / MC / validation jobs** | Step 5 rules | same | same: still current if they pass Step 5 | **never current**: `GENERATION_UNRECORDED` | also the M3 accounting marker where it applies (spec §6), a separate reason |
| **Existing selected-plan and scenario-bound jobs** (DES, MC, validation, Decision) | Step 5 rules | same | same | **never current**: `GENERATION_UNRECORDED`; Decisions withheld; reports 409 or "recommendation unavailable" | plus the engine reasons |
| **New jobs in S1** (pre-G code, unstamped) | — | Step 5 rules | Step 5 rules | never current: `GENERATION_UNRECORDED` | — |
| **New jobs in S2** (stamped) | — | — | Step 5 rules; tokens recorded, not checked | current only if every token matches **and** the scenario is eligible. So S2 jobs on legacy scenarios are **not** current, while S2 Current-mode jobs on the current dataset are | v2 separate-plan chains become historical under v3 |
| **Creating a selected-plan MC or validation job** (OD-G2) | existence, engine and setup checks (and, for validation, the MC → DES link); no `require_dependencies_current` on the input (`workflow.py:2261-2277`, `:2417-2438`; VERIFIED) | same (pre-G code) | input DES/MC jobs must pass Step 5 rules, or 409 before computing. An input that lacks a token but is otherwise eligible is accepted | Step 5 rules **and** matching recorded tokens on every input | plus the engine reasons |

- **The known exact-generation defect is still present in S0, S1 and S2** (spec
  `2026-09-25-analytical-versioning-historical-evidence.md` §5.4, release blocker; qualified by
  owner decision OD-GA-C2, 2026-10-01: it blocks the stage that requires exact-generation
  enforcement).
  - Enforcement (S3) is what closes it. S2 only records the tokens that S3 needs.
  - **Release G-A does not complete the identity repair.** The release blocker stays open until
    G-B.
  - Under OD-GA-C2 (plan Step 0), this defect does not block the G-A implementation milestone. G-A
    does not claim it is repaired, and G-B/G9 must close it.
- **Rollback G-B → G-A:** enforcement off, Step 5 rules only, and the defect returns. Tokens stay,
  and stamped evidence becomes eligible again when enforcement returns.
- **Rollback G-A → pre-G on 0005:**
  - ORM compatibility: the pre-G models read and insert on 0005 (VERIFIED in the prototype, and on
    SQLite against the committed 0005).
  - Startability is a separate question, and the answer through the production Compose chain is
    no:
    - Pre-G `alembic upgrade head` fails on 0005 ("Can't locate revision identified by '0005'").
    - Pre-G `migration_status` exits 1 ("expected ['0004'], got ['0005']").
    - Both are VERIFIED on SQLite against the committed 0005.
    - The Compose `api` service starts only after `migrate` completes successfully (§2), so a pre-G
      release does not start there (INFERRED; not run).
    - Started directly through `entrypoint.sh`, which checks settings only, it would start
      (INFERRED). On Render it is UNKNOWN.
  - Through Compose, rolling back to pre-G therefore means the backup-first path below.
  - A full pre-G application on 0005 is NOT TESTED.
  - Rows written in that window get database-default tokens, their jobs are unstamped, and their
    scenarios have NULL `dataset_generation`. After rolling forward, all of them fail closed.
- **Schema rollback (runbook: restore the pre-migration backup):** everything written after the
  backup is lost from the restored database.
  - Re-upgrading assigns new tokens to every row (VERIFIED in the prototype: 0 tokens shared after
    a rehearsal downgrade and re-upgrade).
  - Every stamped job then mismatches and every `dataset_generation` is NULL again, so all evidence
    fails closed and plans must be recalculated.
  - `alembic downgrade` is rehearsal only.
- **Enforcement off never makes a legacy job current in a way that S0 did not already allow.
  Enforcement on never makes an unstamped job current.**

## 7. Where the token is written

| Path | Records | Source |
|---|---|---|
| Dataset upload (three constructors) | `datasets.generation` | application default; no call-site change |
| `POST /scenarios` (`scenarios.py:323` at `f495f0bd`) | `generation`; `dataset_generation = dataset.generation` | the row loaded at `:276` and verified by `_verify_calculation` (`:315`). NULL when the scenario has no dataset (never selectable, `workflow.py:302`). Also NULL when the save carries no calculation snapshot, because `_verify_calculation` then verifies nothing (`:205`); such legacy_unverified scenarios are never selectable either (`workflow.py:298-308`). Approved 2026-09-28, narrowing the earlier "NULL only without a dataset" wording |
| Legacy dataset re-parent (`scenarios.py:312`) | nothing | identity unchanged; a save that verified a snapshot against the re-parented row records that row's token |
| `_save_job` (all 12 call sites) | `params.scenario_generation`, `params.dataset_generation` | the ORM rows the computation read |

- `_save_job` receives the dataset row. For Current kinds that is the `_current_dataset` row; for
  scenario-bound kinds it is the scenario's dataset row.
- It always stamps what was read. Under enforcement only, it refuses with 409 when
  `dataset.generation != scenario.dataset_generation`. With enforcement off it records the tokens
  and changes nothing else.
  - Wired in G5 (`workflow.py:570-575` at `1b8a8bd2`, §8.2). A binding that is not recorded is
    refused as well.
- Stamping itself is behaviour-neutral in S2. The one intended S2 behaviour change is the OD-G2
  write-time gate (§8).

| Caller (`workflow.py` at `cb7f78be`) | Scenario read | Dataset row stamped |
|---|---|---|
| selection `:933` | `_own_verified_scenario_and_dataset` (`:932`) | the row that call verified (`:320`) |
| DES `:971`, MC `:1031`, validation `:1092` | `_require_selection` (`:961`, `:1021`, `:1081`) | the row verified at `:320`, returned through `_selected_scenario_and_dataset` |
| DES/MC/validation current `:1002`, `:1062`, `:1169` | — | `_current_dataset` (`:990`, `:1050`, `:1122`) |
| selected DES/MC/validation `:2074`, `:2345`, `:2504` | `_require_selected_separate_plan` | `plan["dataset"]`: the row verified at `:320` (`:1835`) |
| selected Decision `:2737` | as above | as above |
| shared Decision `:2767` | `_selected_scenario_and_dataset` (`:2755`) | the row verified at `:320` |

- Historical: at `4db54722` the call sites were `:902`, `:941`, `:972`, `:1001`, `:1032`, `:1062`,
  `:1139`, `:2045`, `:2312`, `:2467`, `:2700` and `:2730`. `run_des` (`:931`) and
  `_require_selected_separate_plan` (`:1829`) read the dataset a second time. G3 removed both
  reads, so the stamped row is always the row the eligibility check verified.

### 7.1 G2 status (committed `f495f0bd`, local, unpushed)

- Implemented: the dataset and scenario creation rows above. `_save_job` stamping is G3 (§7.2).
- Outputs (additive): `ScenarioOut` and `DatasetOut` report `generation` (`scenarios.py:59`,
  `:91`; `datasets.py:33`, `:49`). So do the `analyses.py` endpoints that reuse those serializers
  (`:175`, `:232`, `:287`, `:361`, `:387`).
  - `dataset_generation` is not exposed (decision 2026-09-28).
  - The field is typed `str | None` so that serializing an unsaved row does not fail. A stored row
    cannot hold NULL (NOT NULL column).
  - The frontend types were not changed.
- Client-supplied `generation` and `dataset_generation` in a body are ignored. For `POST` with a
  dataset this is VERIFIED on SQLite and PostgreSQL 18.6. For `POST` without a dataset and for
  `PATCH` it is VERIFIED on SQLite only, by the amended test below.
- The G1-H test `test_application_on_the_migrated_schema_assigns_and_hides_tokens` pinned the
  pre-G2 rule that outputs carry no token. With approval it was renamed
  `..._assigns_and_reports_tokens` and amended in place; its other guarantees are unchanged.
- Gate G-T1 evidence (VERIFIED on the committed tree):

  | Evidence | SQLite | Local PostgreSQL 18.6 |
  |---|---|---|
  | `tests/test_generation_creation_stamping.py` (8 tests) | 8 passed | 8 passed, 0 skipped; `db_engine` dialect confirmed `postgresql` |
  | The four `db_engine` tests of `test_generation_identity_migration.py` | passed (full suite) | 4 passed |
  | Amended `..._assigns_and_reports_tokens` | passed | **NOT RUN**: its fixture uses the `postgres` maintenance database, which the G2 session was not authorized to use |
  | The 9 G2 tests against the pre-G2 source (`2fd18f99`) | 8 fail; the rejected-save test already held | not run |
  | Seven deliberate faults: no stamp, stamp without a snapshot, a token not read from the dataset, schema-2 only, scenario token missing, scenario token replaced by the binding, dataset token missing | 7 of 7 caught | 7 of 7 caught |
  | Creation-path regression files plus the Step 5 suite (13 files) | in the full suite | 190 passed, 0 skipped |
  | Full backend suite | 1348 passed, 94 skipped (all PostgreSQL-only), 1 xfailed | not run |
  | ruff, mypy | clean | — |

- NOT TESTED: the CI `postgres-integration` job, PostgreSQL 16, production, and the frontend
  gates (no frontend file changed).
- G2 does not repair the exact-generation defect. It only records the binding that enforcement
  (S3) will check.

### 7.2 G3 status (committed `cb7f78be`, local, unpushed)

- Implemented, with enforcement off:
  - every `_save_job` call site records `params.scenario_generation` and
    `params.dataset_generation` (§7);
  - the selected-plan MC and validation endpoints apply the OD-G2 gate (§8.1).
- Not implemented in G3 (later stages): token checks, the enforcement-on 409 in `_save_job`, and the
  classifier changes. The classifier changes have since been committed as G4 (`446a1e18`, §9.1),
  with the check off. The token checks and the `_save_job` refusal have since been wired as G5
  (`1b8a8bd2`, §8.2), with enforcement off.
- Decisions approved 2026-09-28:
  - D1: the only existing test the OD-G2 gate reached,
    `test_selected_plan_validation.py::test_null_failure_rate_stays_null_and_inadequate`, used a
    hand-built MC job without `params.dataset_id`. Its fixture `_craft_mc_job` now records the
    scenario's dataset id. Its assertions are unchanged.
  - D2: each gate runs last, immediately before the computation, so every earlier refusal keeps
    its status and message.
  - D3: a Current-mode job records `scenario_generation` as `null`; the key is present.
- Implementation (VERIFIED from source at `cb7f78be`):
  - `_save_job` (`workflow.py:503-559`) takes the dataset row as a required argument and writes
    both tokens after the caller's params (`:549-550`). It raises `ValueError` if a scenario-bound
    job is given a dataset other than the scenario's (`:522`).
  - `_own_verified_scenario_and_dataset` returns the dataset row it verified, and that row is
    passed through (table above).
  - Gates: `run_selected_mc` on the DES job (`:2323`); `run_selected_validation` on the DES and
    MC jobs (`:2485`).
- Evidence (VERIFIED). The runs used a working tree whose three changed files matched the committed
  content, compared with line endings normalized.

  | Evidence | SQLite | Local PostgreSQL 18.6 |
  |---|---|---|
  | `tests/test_generation_job_stamping.py` (13) and `tests/test_selected_plan_validation.py` (12) | 25 passed | 25 passed, 0 skipped; 19 confirmed on `postgresql`, 6 use no database |
  | The 13 new tests against the pre-G3 source (`b6399ada`) | 10 fail; the 3 that pass pin behaviour that holds before and after | not run |
  | Eleven deliberate faults: each stamp, stamp order, wrong row, D3, the guard, each gate, gate position | 11 of 11 caught | 11 of 11 caught |
  | Workflow and evidence regression suites (17 files) | in the full suite | 284 passed, 1 xfailed, 0 skipped |
  | Full backend suite | 1361 passed; 94 skipped, all needing `NOVAQ_TEST_DATABASE_URL`; 1 xfailed (the strict MC xfail) | not run |
  | ruff, mypy | clean | — |
  | Frontend `npm test`, `npm run typecheck` | 52 files / 379 tests passed; exit 0 | — |

- NOT TESTED or UNKNOWN:
  - the full backend suite on PostgreSQL. The migration module's PostgreSQL cases create their
    databases through the cluster's `postgres` maintenance database, which the G3 session was not
    authorized to use;
  - whether jobs already stored in any database would meet the OD-G2 refusal (UNKNOWN);
  - the CI job, PostgreSQL 16 and production;
  - frontend lint and build (no frontend file changed).
- G3 does not repair the exact-generation defect. It only records the tokens that enforcement (S3)
  will check.

## 8. Where the token is checked

Every row applies under enforcement (S3 and later). The write-time gates also apply in S2, without
their token part (OD-G2, below).

| Check | Rule |
|---|---|
| `_own_verified_scenario` | `dataset_generation` must be present and equal the live dataset token. Otherwise 422 "Scenario provenance is incomplete; recalculate and save a new plan." This check runs last, so existing reasons keep their messages. |
| Selection-binding helper (used by `_selected_scenario` and `_require_selected_separate_plan`) | `selection.params.scenario_generation == scenario.generation`, otherwise no eligible selection. Selected-plan endpoints: 409 "The selected plan was replaced; select it again in Compare." G5 uses this text for an actual token mismatch only; a selection with no recorded token gets its own approved text (§8.2) |
| Decision production (G6, decision D2): `create_decision`, `create_selected_decision` | the selection must also record the verified dataset row's generation: `selection.params.dataset_generation == dataset.generation`. Missing, blank or non-text: 409; different: 409; no Decision is stored. Checked last, immediately before persisting (§10.1) |
| Classifier (§9) via `_current_evidence`, `require_dependencies_current`, `current_decision_for_report` | every recorded token must equal the live row's |
| Write-time gates (OD-G2): selected MC (`des_job`), selected validation (`des_job`, `mc_job`) | from G-A: `require_dependencies_current` on every input before computing, whether enforcement is on or off. Under enforcement: matching recorded tokens as well |
| `run_validation_current`, where it compares `dataset_id` inline (`workflow.py:1250` at `1b8a8bd2`; `:1130` at `446a1e18`; `:1100` at `4db54722`) | classifier on the MC job, plus `mc.params.dataset_generation == dataset.generation`. G5 implements the token comparison only; the classifier part is not wired (approved deviation, §8.2) |
| Existing integer `result.scenario_id` checks | kept as consistency checks |

- `_latest_job` keeps selecting by id, with no fallback (D7 rule).

### 8.1 OD-G2 — write-time dependency integrity (APPROVED 2026-09-28; items 1–3 implemented in `cb7f78be`; item 4 wired, switched off, in `1b8a8bd2`)

1. Before creating a new analytical job, the selected-plan Monte Carlo and validation endpoints
   check that their input evidence satisfies the existing Step 5 dependency-integrity rules
   (`require_dependencies_current`, `workflow.py:741` at `cb7f78be`; `:710` at `4db54722`). If it does not, they refuse with 409
   before computing, so no evidence is stored on a broken input.
2. This check applies even when generation enforcement is off, from release G-A onward.
3. During the stamping-only stage (S2), evidence that is otherwise eligible is not rejected solely
   for lacking a future generation token. With enforcement off, the classifier policy has no
   generation kinds, so a token is never consulted.
4. When enforcement is on (S3 and later), the gate also requires the appropriate recorded source
   tokens to match, in addition to the existing dependency integrity.
5. At `4db54722` neither endpoint calls `require_dependencies_current` (VERIFIED):
   - Selected MC checks the selected plan, that a DES job exists, its engine, and that the setup is
     current (`workflow.py:2261-2277`).
   - Selected validation checks the same, plus the MC job's engine and the MC → DES link
     (`:2417-2438`).
   - So OD-G2 adds new 409 responses in G-A, and G-T6 and G-T13 cover them.
6. At `cb7f78be` both endpoints call it last, immediately before computing (decision D2, §7.2):
   selected MC on the DES job (`workflow.py:2323`), selected validation on the DES and MC jobs
   (`:2485`). Item 4, the token match under enforcement, is not implemented.
7. At `1b8a8bd2` (G5) item 4 is wired but not active. The gates are at `workflow.py:2455` and
   `:2617`. `require_dependencies_current` (`:837-852`) uses the policy, which enables both
   generation kinds only while `GENERATION_ENFORCEMENT_ENABLED` is on (`:699`). The flag is off, so
   item 4 does not apply in the application (§8.2).

### 8.2 G5 status (committed `1b8a8bd2`, local, unpushed)

- **Enforcement stays off.** VERIFIED from source at `1b8a8bd2`:
  - `GENERATION_ENFORCEMENT_ENABLED = False` (`workflow.py:102`). It is read at call time through
    `_generation_enforced` (`:105-106`). Nothing else in `backend/` assigns it (grep).
  - While it is off, every check below is skipped and the policy enables no generation kind. The
    application's default behaviour is therefore unchanged from Steps 1–5 and G1–G4. Turning it
    on is G9.
- **Implemented in `backend/api/workflow.py` only** (+148/−16), with the new
  `tests/test_generation_enforcement_wiring.py` (57 tests). No other file changed, and no existing
  test changed. VERIFIED from source at `1b8a8bd2`, all active only with the flag on:
  - Policy: `generation_kinds` is both kinds only while the flag is on (`:699`).
  - Live tokens: `_dataset_dependency` and `_scenario_dependency` supply the row's `generation`
    (`:731`, `:796`).
  - Scenario chain (decision D3): `_scenario_evidence_record` carries the scenario's stored
    `dataset_generation` for its dataset reference, exactly as stored (NULL stays NULL,
    `:774-776`). It is built in `workflow.py`, not through `evidence_status.scenario_record`.
  - Recorded values: `_recorded_generation` (`:109-116`). Only non-blank text is a token. None,
    blank text and non-text values are unrecorded and never match.
  - §8 row 1: `_require_verified_dataset_generation` (`:400-411`) runs last on both schema
    branches (`:377`, `:396`).
  - Selection binding: `_selection_binding_problem` (`:641-654`).
    - `_selected_scenario_and_dataset` uses it to report no eligible selection (`:636-637`).
    - `_require_selected_separate_plan` uses it after every existing check, which is decision D5
      (`:1996-2001`).
  - OD-G2 token match (§8.1 item 4, and G-T6 with enforcement on): `require_dependencies_current`
    (`:837-852`) with `_root_causes` (`:855-860`).
  - `run_validation_current`: token check only (`:1263-1271`).
  - `_save_job`: the §7 refusal (`:570-575`). No API path can reach it, because every
    scenario-bound caller verifies the scenario first and that check refuses the same condition
    (INFERRED from the call sites). It is tested by direct call.
  - Unchanged: `_latest_job` keeps selecting the latest job only, with no fallback (`:518-533`,
    D7 rule). `separate_comparison` is not changed (decision D7).
- **Refusals with enforcement on** (texts approved 2026-09-29):

  | Condition | Status | Text |
  |---|---|---|
  | Scenario without a matching verified dataset generation (§8 row 1) | 422 | "Scenario provenance is incomplete; recalculate and save a new plan." |
  | `_save_job` generation disagreement (§7) | 409 | same as above |
  | Selected-plan binding, token mismatch | 409 | "The selected plan was replaced; select it again in Compare." |
  | Selected-plan binding, no token recorded | 409 | "The selection has no recorded generation identity and cannot be verified; select the plan again in Compare." |
  | Shared-queue paths with no eligible selection | 409 | existing "Select a Scenario in Compare first." |
  | OD-G2 input whose only cause is an unrecorded generation | 409 | "Evidence has no recorded generation identity and cannot be verified. Rerun the affected step." |
  | OD-G2 input with a mismatch or any other Step 5 cause | 409 | existing `MISSING_DEPENDENCY_DETAIL` |
  | Current validation, no recorded token | 409 | "Current Monte Carlo evidence has no recorded generation identity and cannot be verified against the current dataset. Rerun Current Monte Carlo." |
  | Current validation, token mismatch | 409 | existing "Current Monte Carlo evidence is stale for this dataset. Rerun Current Monte Carlo." |

- **Evidence.** All runs below were executed on 2026-09-29, in the session that implemented G5.
  - The runs before the commit used the working tree. The committed blobs match that tree by
    sha256: the test module byte for byte, and `workflow.py` once the working copy's CRLF line
    endings are restored.
  - After the commit, the G5 module, ruff and mypy were run again on the clean `1b8a8bd2` tree,
    with the same results.

  | Evidence | Result |
  |---|---|
  | `tests/test_generation_enforcement_wiring.py` on SQLite | 57 passed (before the commit and again on `1b8a8bd2`) |
  | Full SQLite backend suite | 1474 passed; 94 skipped (91 in `test_generation_identity_migration.py`, 3 in `test_postgres_migration_chain.py`, all needing `NOVAQ_TEST_DATABASE_URL`); 1 xfailed (the strict MC xfail); exit 0 |
  | Targeted local PostgreSQL 18.6 run (`novaq_gen_verify_test`, non-superuser test role): the G5 module plus the 16 Step 1–5, D7, G2–G4, selected-plan and report regression files | 381 passed, 0 failed, 0 skipped. 233 ran on `postgresql`; 148 used no database |
  | The G5 module alone on PostgreSQL 18.6 | 57 passed. 56 ran on `postgresql`; 1 (the flag test) used no database |
  | Twenty-two deliberate faults in a scratch copy of `workflow.py`, run against the G5 module on SQLite | 22 of 22 caught; the copy was restored to the gated hash |
  | The G5 module against the pre-G5 source (`598b3ae3`) | not collectable: it references G5 names |
  | `ruff check .`, `mypy .` | clean; mypy: no issues in 167 source files (before the commit and again on `1b8a8bd2`) |

- **Caveats:**
  - Current validation performs the approved token-only check. It does not apply the broader
    classifier check of §8's `run_validation_current` row, which is not wired.
  - The Decision and report paths share the wired helpers, so their behaviour also changes when
    the flag is on. That behaviour is G6 (G-T7, G-T8): it is not tested and not claimed here. Their
    flag-off regressions pass. Since G6 (`4e89b7a8`) it is tested with the flag switched on
    (§10.1).
  - Enforcement is not enabled by default, so the checks above do not run in the application.
  - A stored token that is not text is reported as unrecorded by the workflow-level refusals. The
    G4 classifier reports it as `GENERATION_MISMATCH`, so at the OD-G2 gate it would receive
    `MISSING_DEPENDENCY_DETAIL`.
    - No code writes such a value (INFERRED from the G3 stamping).
    - That OD-G2 case is NOT TESTED.
- **NOT TESTED or UNKNOWN:**
  - the full backend suite on PostgreSQL (NOT RUN);
  - the fault run on PostgreSQL (NOT RUN);
  - the CI `postgres-integration` job (NOT RUN) and PostgreSQL 16 (NOT RUN);
  - production PostgreSQL version, Alembic revision and role privileges, and the Render facts in
    §2 and §11 (UNKNOWN);
  - which stored workflows would meet the OD-G2 refusal (UNKNOWN; §16);
  - enforcement in any deployment (not enabled; NOT TESTED).
- G5 does not repair the exact-generation defect in the running application. It wires the checks
  that enforcement (S3, release G-B, stage G9) will switch on.

## 9. Classifier changes (`evidence_status.py`)

- New fields:
  - `Dependency.generation` (the live row's token)
  - `EvidenceRecord.generations` (the recorded token for each generation-bearing reference)
  - `EvidencePolicy.generation_kinds` (empty = off; results identical to Steps 1–5)
- `job_record` reads `params.scenario_generation` and `params.dataset_generation`. The scenario
  record carries `dataset_generation` for its dataset reference.

| Case | Reason | Status |
|---|---|---|
| Token matches | none | — |
| Token differs | `GENERATION_MISMATCH` (new) | `MISSING_DEPENDENCY` |
| Token not recorded | `GENERATION_UNRECORDED` (new) | `MISSING_PROVENANCE` |
| Source missing | `DEPENDENCY_MISSING` | unchanged |
| Stale dataset | `DATASET_NOT_CURRENT` / `NO_CURRENT_DATASET` | unchanged |
| Stale scenario | `UPSTREAM_STALE_DATASET` / `UPSTREAM_STALE_SETUP` | unchanged |
| Unsupported engine | `VERSION_UNSUPPORTED` / `VERSION_UNRECOGNIZED` | unchanged; never merged with identity |

All reasons are collected; precedence picks only the headline. `DEPENDENCY_CREATED_AFTER` stays.

### 9.1 G4 status (committed `446a1e18`, local, unpushed)

- Implemented in `backend/api/evidence_status.py`, the only production file G4 changed (+85/−4).
  VERIFIED from source at `446a1e18`:
  - Reason codes `GENERATION_MISMATCH` → `MISSING_DEPENDENCY` and `GENERATION_UNRECORDED` →
    `MISSING_PROVENANCE` (`:59`, `:69`, `:104`, `:113`).
  - `GenerationRequirement` (`:228-237`), `Dependency.generation` (`:279`),
    `EvidenceRecord.generations` (`:299`) and `EvidencePolicy.generation_kinds` (`:493`). A policy
    may name only `dataset` and `scenario` (`GENERATION_KINDS`, `:473`); any other kind raises
    (`:495-498`).
  - `scenario_record` takes the scenario's `dataset_generation` for its dataset reference
    (`:545`, `:567`, `:571`). `job_record` reads `params.scenario_generation` for each scenario
    reference and `params.dataset_generation` for the recorded dataset (`:679-681`, `:689`).
    Requirements are built only for the kinds the policy enables (`_generation_requirements`,
    `:535-539`).
  - A job with no scenario reference, which is every Current kind (`job_references`, `:604-606`),
    gets no scenario requirement, whatever its `scenario_generation` says.
  - In `_classify` (`:357-364`, `:386-395`), a generation requirement makes its reference
    required. The token check runs only after existence and scope are established, and
    `DEPENDENCY_CREATED_AFTER` is still reported next to it.
  - A recorded token that is not text is kept tagged with its type, so it never equals a live
    token (`_recorded_token`, `:524-532`).
- Decisions of 2026-09-29, recorded in `tests/test_evidence_status_generation.py:4-6`:
  - D1: `generation_kinds` decides whether `job_record` and `scenario_record` build requirements;
    `classify` is unchanged.
  - D2: a live token that the caller did not supply gives `DEPENDENCY_UNASSESSED`
    (`MISSING_PROVENANCE`). The §9 table above does not list this case.
- The only existing test changed is `test_13_records_cannot_carry_metrics` in
  `tests/test_evidence_status.py`: `generations` was added to its expected field set, as record
  identity rather than a metric.
- **Off by default** (VERIFIED from source):
  - `generation_kinds` defaults to empty (`:493`). With it empty, no record carries a generation
    requirement and classification is unchanged. `test_flag_off_results_are_identical_with_or_without_token_data`
    covers this (G-T13; `tests/test_evidence_status_generation.py:347-358`).
  - The only `EvidencePolicy` the application builds is `workflow._current_evidence_policy`
    (`workflow.py:591-625` at `446a1e18`; `:662-700` at `1b8a8bd2`), and it enables no generation
    kind. Since G5 it enables both kinds only while `GENERATION_ENFORCEMENT_ENABLED` is on, and
    that flag is off (§8.2). `test_the_application_policy_enables_no_generation_kind` pins this
    (`:361-365`).
  - At `446a1e18`, `workflow.py` was unchanged since `cb7f78be` and no caller supplied
    `Dependency.generation`. G5 (`1b8a8bd2`, §8.2) has since wired both, with enforcement off.
- Evidence (VERIFIED). The PostgreSQL run (194), the full SQLite suite (1417) and the fault run
  (15 of 15) were not re-run on 2026-09-29. They are VERIFIED from the actual tool outputs
  recorded in the G4 session. The committed blobs of the three G4 files match, by sha256, the
  gated hashes those runs were checked against: before and after the SQLite and PostgreSQL runs,
  and in the fault run's scratch copy (its `evidence_status.py` was restored after the run). The
  107 classifier tests, ruff and mypy were re-run on 2026-09-29 against an export of `446a1e18`,
  with the same results.

  | Evidence | Result |
  |---|---|
  | `tests/test_evidence_status_generation.py` (56) and `tests/test_evidence_status.py` (51) | 107 passed. These tests use no database |
  | Local PostgreSQL 18.6 run (non-superuser test role): the two files above, plus `test_step5_missing_dependency.py`, `test_d7_current_evidence_dataset.py`, `test_step4_schema1_dataset_currentness.py` and `test_generation_job_stamping.py` | 194 passed, 0 failed, 0 skipped. 87 ran on `postgresql`; the 107 classifier tests used no database |
  | Full SQLite backend suite | 1417 passed; 94 skipped, all needing `NOVAQ_TEST_DATABASE_URL`; 1 xfailed (the strict MC xfail); exit 0 |
  | Fifteen deliberate faults in a scratch copy of `evidence_status.py`, run against the 107 classifier tests | 15 of 15 caught; the copy was restored to the gated hash |
  | `ruff check .`, `mypy .` | clean; mypy: no issues in 166 source files |

- **The PostgreSQL run does not verify dialect-specific classifier behaviour.** The classifier
  and the G4 tests use no database, so nothing in them depends on the engine. The 87 PostgreSQL
  cases are the Step 3–5, D7 and G3 integration suites. They show only that those suites still
  pass on PostgreSQL 18.6 with G4 present and the check off. None of them names a generation
  kind.
- NOT TESTED or UNKNOWN:
  - the full backend suite on PostgreSQL (NOT RUN);
  - the CI `postgres-integration` job (NOT RUN) and PostgreSQL 16 (NOT TESTED);
  - production PostgreSQL version, Alembic revision and role privileges, and the Render facts in
    §2 and §11 (UNKNOWN);
  - which stored workflows would meet the OD-G2 refusal (UNKNOWN; §16);
  - application behaviour with a generation kind enabled (NOT TESTED at G4, when nothing enabled
    one; G5 tests its own consumers with the flag switched on, §8.2).
- No frontend file changed.
- G4 does not repair the exact-generation defect. The check is now wired (G5, §8.2) but stays off
  until enforcement is switched on (S3, G9).

## 10. Reports

- **Selected report:** 409 on any mismatch in the Decision or job-chain generation evidence, through
  `require_dependencies_current`, and on a selection that does not bind (§8.2 texts).
  - Decision D1 (2026-09-29): a scenario whose own dataset generation is missing or is not the
    live dataset row's keeps the approved 422 of §8 row 1, which the selected-plan paths report as
    "Selected plan is not runnable: Scenario provenance is incomplete; recalculate and save a new
    plan." G-T8's "selected report 409" applies to broken Decision and job-chain generation
    evidence, not to that existing scenario-provenance refusal.
  - Amended 2026-09-29 (D1): this bullet said "409 on any mismatch".
- **ID-scoped scenario PDF/Excel:** the Decision section comes only from
  `current_decision_for_report`. A mismatched or unrecorded token gives "Management recommendation
  unavailable", which closes the reproduced leak of a deleted scenario's Decision.
  - A verified schema-2 plan stores only its schedule (`scenarios.py:191-194`), so its ID-scoped
    export is refused with 422 "Scenario has no comparison results to report on."
    (`reports.py:478-485`) whatever the flag, and never reaches a Decision section. The
    "recommendation unavailable" behaviour therefore applies to schema-1 scenarios.
- **Dataset report:** unchanged (reads no jobs).
- Eligibility is decided before any historical labelling. OD-7 and Step 11 are out of scope.

### 10.1 G6 status (committed `4e89b7a8`, local, unpushed)

- **Enforcement stays off.** `GENERATION_ENFORCEMENT_ENABLED = False` (`workflow.py:102` at
  `4e89b7a8`). The G6 check, like every G5 check, runs only while it is on, so the application's
  default behaviour is unchanged. Turning it on is G9.
- **Files** (VERIFIED from `git show --stat 4e89b7a8`): `backend/api/workflow.py` (+32/−1) and the
  new `tests/test_generation_decision_report.py` (56 tests). `reports.py` is byte-identical at
  `1b8a8bd2` and `4e89b7a8`; `evidence_status.py`, the models, the migrations and the frontend are
  unchanged. No existing test changed.
- **Decisions of 2026-09-29:** D1 (above); D2, the selection's dataset generation (below); D3, no
  new response fields; D4, a targeted PostgreSQL run against the dedicated test database only.
- **The new rule (D2).** VERIFIED from source at `4e89b7a8`:
  - The G5 selection binding compares only `scenario_generation` (`_selection_binding_problem`,
    `workflow.py:651`). A Decision records its selection, so before G6 a selection whose scenario
    token matched but whose dataset token was unrecorded or different still produced a stored
    Decision. Under enforcement that Decision was then never served, and producing it again stored
    another one without clearing `decision_stale`.
  - `_require_selection_dataset_generation` (`workflow.py:667-684`) closes that gap. With the flag
    off it returns at once. With it on, it reads the selection's `params.dataset_generation` through
    `_recorded_generation`, so only non-blank text is a token:
    - missing, null, blank or not text: 409, and no Decision is stored;
    - a token that is not the verified dataset row's `generation`: 409, and no Decision is stored.
  - Under enforcement a selection is therefore valid for Decision production only when both its
    `scenario_generation` matches the live scenario and its `dataset_generation` matches the
    verified dataset row.
  - Approved texts (`workflow.py:278-285`):
    - unrecorded: "The selection has no recorded dataset generation identity and cannot be
      verified; select the plan again in Compare."
    - mismatch: "The selection's recorded dataset generation does not match the verified dataset;
      select the plan again in Compare."
  - Call sites, each last before persisting, so every existing refusal keeps its status and text:
    - `create_selected_decision` (`:2817`) at `:2892`: after the plan and binding checks, the
      job-chain gate (`:2875`) and the validation scenario check; before `_save_job` (`:2899`). The
      dataset is `plan["dataset"]`, the row the scenario was verified against, and the selection is
      the latest one, which the Decision records in `evidence_ids`. `_derive_selected_decision` runs
      before the check; it builds a dict and stores nothing.
    - `create_decision` (`:2909`) at `:2929`: after the separate-queue return and the
      no-eligible-selection return (Option A, unchanged); before `_save_job` (`:2930`). The
      selection and dataset are those of `_selected_scenario_and_dataset`.
  - The selected report is not changed by D2. A Decision stored under such a selection with the
    flag off is refused there by the classifier, through its recorded selection: 409 with
    `GENERATION_UNRECORDED_DETAIL` for a missing, null, empty or blank token, and
    `MISSING_DEPENDENCY_DETAIL` for a different token or a non-text value, which the G4 classifier
    reports as a mismatch (§8.2 caveat). The tests pin both.
- **Inherited from G5, pinned by G6 tests, with no G6 code:**
  - The Decision is withheld when its own tokens, an upstream job's or its recorded selection's are
    mismatched or unrecorded: the classifier policy (`workflow.py:728`) and the Decision check in
    `_current_evidence` (`:949`). Option A is kept (`:957`): with no eligible selection
    `decision_stale` stays false; for an eligible plan whose Decision is broken it is true, and
    producing the Decision again from a valid chain clears it.
  - The selected Decision refuses a broken DES, MC or validation input (`:2875`) and a selection
    that does not bind (`_require_selected_separate_plan`, `:2028`).
  - The selected report (preview, PDF and Excel agree) refuses a broken Decision or job chain with
    409 (`reports.py:212`) and a selection that does not bind with 409 (`reports.py:161`). A scenario
    without its dataset generation keeps the 422 (D1; `_require_verified_dataset_generation`,
    `workflow.py:410`).
  - The ID-scoped export says "Management recommendation unavailable" whenever the Decision is not
    current (`current_decision_for_report`, `workflow.py:989`; `reports.py:604`).
  - Same-id and byte-identical scenario replacement, and a dataset replaced together with its
    cascaded scenario, serve and produce no Decision.
  - Latest only, no fallback: a broken latest Decision is never replaced by an older current one.
  - The dataset report is unchanged.
  - Evidence that this is inherited: the G6 module run against the pre-G6 source, with only the two
    new text constants added so that it can be collected, gave 41 passed and 15 failed. All 15
    failures are the D2 tests.
- **Evidence.** All runs were executed on 2026-09-29, before the commit, on files byte-identical to
  the committed blobs: the committed blob ids of both files equal `git hash-object` of the gated
  working files. The baseline and pre-G6 runs used exports of `3a617a86`; the fault run used a
  scratch copy of the gated tree, restored to the gated hashes afterwards.

  | Evidence | Result |
  |---|---|
  | Focused baseline at `3a617a86` (18 Decision, report, workflow and generation files; SQLite) | 394 passed, 1 xfailed |
  | G6 module against the pre-G6 source plus the two text constants (SQLite) | 41 passed, 15 failed (the D2 tests) |
  | `tests/test_generation_decision_report.py` on SQLite | 56 passed |
  | The same module on local PostgreSQL 18.6 (`novaq_gen_verify_test`, non-superuser test role) | 56 passed, all 56 on `postgresql` |
  | Full SQLite backend suite (`python -m pytest tests/ -x`, with `-p no:cacheprovider -q`) | 1530 passed; 94 skipped (91 in `test_generation_identity_migration.py`, 3 in `test_postgres_migration_chain.py`, all needing `NOVAQ_TEST_DATABASE_URL`); 1 xfailed (the strict MC xfail); exit 0 |
  | Targeted local PostgreSQL 18.6 run: the G6 module plus the 18 baseline files | 450 passed, 1 xfailed, 0 skipped, 0 failed. 290 ran on `postgresql`; 161 used no database |
  | Eighteen deliberate faults in a scratch copy of `workflow.py` and `reports.py`, run against the G6 module on SQLite | 18 of 18 caught |
  | `ruff check .`, `mypy .` | clean; mypy: no issues in 168 source files |

  - The faults: each D2 call removed; D2 active with the flag off; the two texts swapped; blank or
    non-text read as a token; the comparison inverted; each D2 call moved before an existing
    refusal; the report and Decision chain gates removed; the report ignoring the Decision's tokens;
    the policy enabling no generation kind; `_current_evidence` skipping the Decision's
    classification; the selection binding and the scenario provenance check disabled; a fallback to
    an older current Decision in `_current_evidence` and in the selected report; and the ID-scoped
    report taking the latest Decision unchecked.
- **NOT TESTED or UNKNOWN:**
  - the full backend suite on PostgreSQL (NOT RUN);
  - the PostgreSQL migration and chain tests, which create databases through the cluster's
    `postgres` maintenance database that this session was not authorized to use (NOT RUN);
  - the fault run on PostgreSQL (NOT RUN);
  - the CI `postgres-integration` job (NOT RUN) and PostgreSQL 16 (NOT RUN);
  - production PostgreSQL version, Alembic revision and role privileges, and the Render facts in
    §2 and §11 (UNKNOWN);
  - whether any stored selection holds the state D2 now refuses: a matching scenario token with an
    unrecorded or different dataset token (UNKNOWN). No code writes it, because `_save_job` stamps
    both tokens together (INFERRED);
  - enforcement in any deployment (not enabled; NOT TESTED).
- G6 does not repair the exact-generation defect in the running application: enforcement is off.
  It completes the Decision and report behaviour that enforcement (S3, release G-B, stage G9) will
  switch on.

## 11. Deployment

### 11.1 Findings

- **The Docker image runs `entrypoint.sh`** (VERIFIED). Whether Render runs that command, overrides
  it, or uses a native runtime with its own start command is **UNKNOWN**. So a guard placed only in
  `entrypoint.sh` might never run.
- **Guard inside the application** (proposed here; implemented in G7, `e64b50cc`, §11.4). A FastAPI
  lifespan hook in `create_app` verifies, when `NOVAQ_ENV=production`, that the database is exactly
  at the code's Alembic head. It uses the same logic as `migration_status`; `alembic.ini` and
  `migrations/` are in the image.
  - It runs whenever `backend.api.main:app` is served, however uvicorn is launched.
  - Mechanism VERIFIED locally on a throwaway app with uvicorn 0.48.0 (§15.3): a lifespan exception
    gives "Application startup failed. Exiting.", exit code 3, and nothing is served. Historical:
    the guard itself was not implemented then. Since G7 the application's own guard gives the same
    result with local uvicorn 0.48.0 (§11.4).
  - On the production pins (uvicorn 0.52.4, FastAPI 0.141.1) it is **NOT TESTED**.
  - `entrypoint.sh` may run `migration_status` as well, as defence in depth. Decision D6
    (2026-09-29): G7 does not add it, and `entrypoint.sh` is unchanged.
  - `/ready` also returns 503 on a mismatch, in case the schema changes under a running process.
    Implemented in G7, in production only (§11.4).
- **Limit of the guard:** it cannot help if Render serves a different application object (UNKNOWN,
  and a stop condition).
- **How each backend behaves on each schema:**
  - Older backend on 0005, ORM layer: the pre-G models read and insert (VERIFIED in the prototype,
    and on SQLite against the committed 0005). A pre-G process that is already serving when 0005
    is applied is therefore expected to keep serving (INFERRED).
  - Older backend on 0005, startup: a pre-G release does not start through the production Compose
    migration chain on 0005 (§6.2). Its Alembic cannot locate revision 0005, and its
    `migration_status` exits 1 (VERIFIED on SQLite). A migration-first release keeps service
    available only while no pre-G instance restarts, redeploys or rolls back through a
    migration-checking start path. Whether the production platform has such a path is UNKNOWN.
  - A full pre-G application on 0005 is NOT TESTED.
  - Newer backend on 0004: it would refuse to start through the guard (PROPOSED). Since G7 a
    production backend refuses to start on the previous revision: VERIFIED by tests on SQLite and
    local PostgreSQL 18.6, and by a local uvicorn 0.48.0 start on SQLite (§11.4); NOT TESTED on the
    production pins or on any deployment. Without the guard, the new ORM models fail on their first
    query: `no such column` on SQLite (VERIFIED in
    the prototype and with the committed models), `UndefinedColumn` on PostgreSQL (VERIFIED in the
    prototype). With the committed models on local PostgreSQL 18.6 the first query raises a
    `DBAPIError` (VERIFIED; the test does not pin the subclass).
- **Deploy overlap:** whether Render keeps the previous instance serving when a deploy fails, and
  whether old and new instances overlap during a deploy, is **UNKNOWN**. Until it is known, assume
  both.

### 11.2 Required order (none of it authorized now)

**Pre-release facts (stop until each is established):**

- Render runtime and start command, pre-deploy command, instance count and deploy overlap.
- Whether any start, restart, redeploy or rollback path runs a migration or `migration_status`
  step. On 0005, a pre-G release that starts through such a step refuses to start (§11.1).
- Production PostgreSQL version (≥ 13) and current Alembic revision, read-only.
- Backup and restore evidence per `operations.md`.

**G-A:**

1. Take the backup required by the runbook.
2. Apply 0005 explicitly, with the mechanism named in the pre-release facts. Never assume Render
   applies it.
3. `migration_status` must exit 0. From here, pre-G code is serving on 0005 (S1). A pre-G
   instance that restarts through a migration-checking path will not come back (§11.1).
4. Deploy the G-A backend. If the guard refuses it, the old backend keeps serving (if Render
   behaves that way; UNKNOWN).
5. Verify `/ready`, and check read-only that new jobs carry tokens.

**G-B (enforcement together with v3):** only when all of these hold:

- G-A is confirmed as the only serving revision;
- no pre-G instance can write;
- the v3 prerequisites are met (plan Steps 7–9, with the frontend in lockstep).

### 11.3 Release compatibility matrix

| Backend \ schema | 0004 | 0005 |
|---|---|---|
| pre-G (`4db54722`) | S0: normal | S1: ORM read and insert VERIFIED (prototype; committed 0005 on SQLite); **does not start through the Compose migrate chain** (its Alembic and `migration_status` reject 0005; VERIFIED on SQLite); full application NOT TESTED; writes unstamped evidence (fails closed later) |
| G-A (stamping, enforcement off) | refuses to start in production: the G7 guard (`e64b50cc`), VERIFIED by tests on SQLite and local PostgreSQL 18.6 and a local uvicorn 0.48.0 start; production pins and deployment NOT TESTED (§11.4) | S2: stamps tokens and applies the OD-G2 gate; **the identity defect remains** |
| G-B (enforcement, v3) | refuses to start in production (the same G7 guard, which does not depend on the enforcement flag; G-B itself is not built) | S3/S4: unstamped evidence is never current (specified; NOT TESTED) |

- Rollback is backup-first.
- Code-only rollback G-A → pre-G is schema-compatible at the ORM layer only (VERIFIED: prototype,
  and the committed 0005 on SQLite). It is not a restartable release through the production
  Compose chain, where the pre-G `migrate` step rejects 0005 (§6.2). The full application is NOT
  TESTED.
- Code-only rollback G-B → G-A: both are specified on head 0005; NOT TESTED.
- Schema rollback means restoring the backup (§6.2 R).

### 11.4 G7 status (committed `e64b50cc`, local, unpushed)

- **Files** (VERIFIED from `git show --stat e64b50cc`): `backend/api/main.py` (+50/−1),
  `backend/operations/migration_status.py` (+66/−7) and the new `tests/test_startup_schema_guard.py`
  (55 tests). `entrypoint.sh`, the migrations, the models, `workflow.py`, `evidence_status.py`,
  `reports.py`, the frontend and the docs are unchanged. No existing test changed.
- **Decisions of 2026-09-29:** D1 exact head equality (no subset, no superset); D2 the guard applies
  only when `Settings.environment == "production"`; D3 fail closed; D4 the readiness text; D5 one
  implementation shared with `migration_status`, whose CLI is unchanged; D6 no `entrypoint.sh`
  change; D7 a targeted PostgreSQL run against the dedicated test database only.
- **Generation enforcement is unaffected.** `GENERATION_ENFORCEMENT_ENABLED = False`
  (`workflow.py:102` at `e64b50cc`). The guard does not read the flag; the tests give the same
  result with the flag on and off.
- **Startup** (VERIFIED from source at `e64b50cc`):
  - `create_app` (`main.py:218`) sets `guard_schema = settings.environment == "production"`
    (`:243`) and passes a lifespan only then (`:247`). Every other environment builds the app as
    before, with no lifespan.
  - The lifespan (`_schema_revision_guard`, `main.py:191-215`) resolves `alembic.ini` and
    `migrations/` from the package (`REPO_ROOT`, `:47`), not from the working directory. It reads the
    code's heads (`:204`), compares them with the database's, raises on any problem (`:206`,
    `:211`), and keeps the verified heads for `/ready` (`:212`).
  - Shared logic in `migration_status.py`: `expected_heads` (`:16`), `current_heads` (`:21`),
    `head_mismatch` (`:26-30`, exact set equality), `code_config` (`:33-45`), `required_heads`
    (`:48-57`) and `schema_head_problem` (`:60-71`).
  - Startup is refused (fail closed) when:
    - the database's heads are not exactly the code's: a previous, unknown or newer revision, extra
      recorded heads, or no recorded revision at all (including a database built only by
      `create_all`). The message is `migration_status`'s: "Database migration mismatch: expected
      […], got […].";
    - the revision cannot be read (database unreachable, `alembic_version` unreadable): "Database
      migration revision cannot be read (<error type>).";
    - the code's heads cannot be determined: `alembic.ini` missing (checked explicitly, because
      Alembic reads a missing ini file as an empty one), `migrations/` missing, or a script directory
      with no head: "Database migration heads cannot be determined (…).".
  - These messages go to the startup exception and the server log only.
- **`/ready`** (`main.py:284-296`):
  - A database connectivity failure keeps its existing 503 "Database not ready." (`:289`).
  - In production the revision is read again on every call (`:290-295`). A mismatch, an unreadable
    revision, or heads the lifespan never established give 503 "Database schema is not at the
    required migration revision." (`:50`). The response names no revision.
  - At the exact head it returns 200.
- **The `migration_status` CLI** (`main`, `migration_status.py:74-85`) behaves as before: it reads
  `alembic.ini` from the working directory (`:75`), exits with the same mismatch message through
  `SystemExit` (`:84`), and prints the same success line (`:85`).
- **Environments.** Production is guarded; development, test and integration are not. The stacks
  follow their actual `NOVAQ_ENV`, with no special case by stack name: the integration `api` and the
  rehearsal `api-restored` run as integration (unguarded), and the rehearsal `api` runs as
  production (`docker-compose.rehearsal.yml:5`) and is guarded. In the integration stack the API
  starts only after `migrate` has run `alembic upgrade head && migration_status` (pinned by a test).
  The rehearsal stack is layered on it and does not change that order (INFERRED from the files; the
  stacks were not run).
- **Evidence.** All runs were executed on 2026-09-29, before the commit, on files byte-identical to
  the committed blobs: the committed blob ids of the three files equal `git hash-object` of the gated
  working files. The baseline ran on `adbbe7d2`; the fault run used a scratch copy of the gated tree,
  restored to the gated hashes afterwards.

  | Evidence | Result |
  |---|---|
  | Baseline at `adbbe7d2`: readiness, production-hardening, migration and chain test files (SQLite) | 120 passed, 94 skipped (PostgreSQL-only), 0 failed |
  | `tests/test_startup_schema_guard.py` on SQLite | 31 passed, 24 skipped (the PostgreSQL variants, which need `NOVAQ_TEST_DATABASE_URL`) |
  | The G7 module, `test_readiness.py` and `test_production_hardening.py` on local PostgreSQL 18.6 (`novaq_gen_verify_test`, non-superuser test role; each case migrates a disposable schema; the maintenance database is never used) | 76 passed, 0 skipped, 0 failed. 33 ran on `postgresql`, 30 on SQLite, 13 used no database |
  | Full SQLite backend suite (`python -m pytest tests/ -x`, with `-p no:cacheprovider -q`) | 1561 passed; 118 skipped (91 in `test_generation_identity_migration.py`, 3 in `test_postgres_migration_chain.py`, 24 in the G7 module, all needing `NOVAQ_TEST_DATABASE_URL`); 1 xfailed (the strict MC xfail); exit 0 |
  | Fifteen deliberate faults in a scratch copy of `main.py` and `migration_status.py`, run against the G7 module on SQLite | 15 of 15 caught |
  | `ruff check .`, `mypy .` | clean; mypy: no issues in 169 source files |

  - The G7 module includes a real uvicorn start (local 0.48.0, SQLite) on the previous revision:
    exit code 3 and "Application startup failed. Exiting.".
  - The faults: the guard off in production; the guard on outside production; the `/ready` check
    removed; a subset and a superset of the heads accepted; an unreadable revision treated as a
    match; a script directory with no head accepted; a missing `alembic.ini` tolerated; the public
    text changed; `/ready` trusting startup without re-reading; `/ready` treating an unverified
    startup as ready; startup never refusing; the CLI's output changed; the CLI made independent of
    the working directory; the application resolving its heads from the working directory.
  - In the first fault run the changed public text was not caught, because the tests compared with
    the application's own constant. The tests now state the approved text literally, and all 15
    faults were run again and caught.
- **An intermittent failure, cause UNKNOWN.** An earlier full SQLite run, made while other test runs
  were active, stopped at
  `test_dataset_staleness_probe.py::test_historical_dataset_report_stays_available_after_replacement`:
  login returned 500, logged as argon2 `VerificationError`. That test passed on its own and in the
  later uncontended full run above. The cause is UNKNOWN and is not attributed here.
- **NOT TESTED or UNKNOWN:**
  - the PostgreSQL migration and chain tests, which need the cluster's `postgres` maintenance
    database (NOT RUN);
  - the full backend suite on PostgreSQL and the fault run on PostgreSQL (NOT RUN);
  - the CI `postgres-integration` job and PostgreSQL 16 (NOT RUN);
  - the guard on the production pins, uvicorn 0.52.4 and FastAPI 0.141.1 (NOT TESTED);
  - Render's start command, working directory, served application object and deploy behaviour
    (UNKNOWN), and so whether the guard runs there at all;
  - the production PostgreSQL version and Alembic revision, and whether the production application
    role can read `alembic_version` (UNKNOWN).
- **CONFLICTING:** §1 rule 6 against exact head equality once a later migration exists (§1).
- `docs/operations.md:245-246` still describes `/ready` as a bounded database query only; it is not
  updated by this contract sync.

## 12. Protected behaviour

No change to:

- D1, D5, D10 or D2 calculations; queueing formulas; optimizer, DES, Monte Carlo;
- engine constants (`novaq-2026-09-unified-des-v1`, `novaq-2026-09-separate-des-v2`) in this work;
- Steps 1–4 rules; Step 5 guards; Option A semantics;
- the strict Monte Carlo xfail (`tests/test_selected_mc_load.py:147`).

Every stage re-runs the D-series, Step 1–5 and full suites.

## 13. Implementation gates (each must be verified independently)

Replacement construction: delete through the API, then insert directly with the deleted row's id
**and** stored `created_at`. It works on both engines, and it reproduced the defect at `4db54722`.

| Gate | Required evidence |
|---|---|
| G-T1 Scenario and dataset creation | every creation path sets a unique 32-hex token; the scenario save sets `dataset_generation` to the verified row's token |
| G-T2 Selection binding | a stamped selection binds only to the same generation; unstamped or mismatched → no eligible selection; Option A preserved |
| G-T3 Job stamping | all 12 `_save_job` call sites record the tokens of the rows actually read |
| G-T4 Current DES (and Current MC/validation: `run_validation_current`, `workflow.py:1250` at `1b8a8bd2`; `:1130` at `446a1e18`) | a replaced dataset (same id, same time, byte-identical) is rejected |
| G-T5 Selected-plan DES | rejected on a replaced scenario |
| G-T6 MC and validation write-time gates (OD-G2) | Flag off: a DES/MC input that fails Step 5 rules is refused with 409 before computing, and no job is stored; an unstamped but otherwise eligible input is accepted. Enforcement on: a wrong-generation or unrecorded input is also refused |
| G-T7 Decision evidence | never served or produced from a mismatched or unrecorded chain |
| G-T8 PDF and Excel | ID-scoped export shows "recommendation unavailable"; selected report 409 on broken Decision or job-chain generation evidence. A scenario without its verified dataset generation keeps the existing 422 (decision D1, §10) |
| G-T9 Missing and mismatched identities | `GENERATION_UNRECORDED` and `GENERATION_MISMATCH` with the correct statuses; all reasons kept; mutation tests |
| G-T10 Same id, same timestamp | rejected at every consumer |
| G-T11 Byte-identical replacement | rejected at every consumer |
| G-T12 Legacy jobs | every pre-existing job kind is non-current under enforcement; stored rows unchanged |
| G-T13 Flag off | identical results to Steps 1–5 on the existing tests and the local fixture, except the OD-G2 refusals (G-T6). Each existing test those refusals affect is reported for review, never silently rewritten |
| G-T14 Both engines | all of the above on SQLite, and on PostgreSQL through `NOVAQ_TEST_DATABASE_URL` |
| G-T15 Rollback and retry | M1–M7 and R1–R11 below |
| G-T16 Startup guard | the production app refuses to start on a mismatched head; `/ready` 503; dev and test unaffected. G7 (§11.4): "production" means `Settings.environment == "production"`; integration is unaffected too |
| G-T17 Protected behaviour | D-series suites, Step 1–5 suites, full backend and frontend suites; the strict xfail unchanged |

**Migration tests:**

| # | Test |
|---|---|
| M1 | backfill and the §5.1 invariants: every original column and every job digest unchanged |
| M2 | database default fills a column-less insert |
| M3 | a duplicate token insert is refused |
| M4 | rehearsal downgrade, and re-upgrade re-identifies rows |
| M5 | pre-G ORM against 0005 |
| M6 | new ORM against 0004 fails, and `migration_status` exits 1 |
| M7 | the post-conditions refuse an incomplete schema |

**Recovery tests** (both engines; real-run faults injected by patching Alembic operations from the
test, never by a hook in the migration):

| # | Test |
|---|---|
| R1 | failure before any schema change |
| R2 | failure after the first identity column is added |
| R3 | failure after the datasets constraint |
| R4 | failure after both constraints |
| R5 | a silently skipped constraint is caught by the post-conditions |
| R6 | hand-built committed state: first column only, plus an older-backend insert |
| R7 | hand-built partial backfill: existing token preserved, plus an older-backend insert |
| R8 | hand-built: datasets constrained |
| R9 | hand-built: both constrained |
| R10 | hand-built: schema complete but not recorded as 0005 |
| R11 | hand-built duplicate tokens: refused, not regenerated, stays at 0004 |

Every R test asserts:

- the retry completes (R11 excepted);
- `alembic_version` = 0005 only when the independent schema check agrees;
- every pre-existing token is unchanged;
- NOT NULL, the unique constraints and the database default are present;
- no leftover `_alembic_tmp_*` table;
- jobs and legacy digests unchanged; legacy `dataset_generation` NULL;
- a second retry changes nothing.

**Fixture impact:**

- 14 test files construct `Scenario` and 14 construct `Dataset` directly; the application default
  covers their tokens.
- Tests needing current use set `dataset_generation` explicitly.
- `test_separate_report`, `test_selected_plan_validation` and `test_break_apply_api._add_job`
  record job tokens.

## 14. Dependency-ordered stages (each needs its own authorization)

| Stage | Files | API / DB | Gates | Stop if |
|---|---|---|---|---|
| G1 migration + model | `migrations/versions/0005_generation_identity.py`, `backend/db/models.py` | three columns, two constraints | M1–M7, R1–R11 (both engines) | any invariant fails; production PostgreSQL < 13 or unknown |
| G2 creation stamping | `scenarios.py`, serializers | `generation` on outputs (additive) | G-T1 | a save path cannot name its verified row |
| G3 job and selection stamping, OD-G2 write gates | `workflow.py` | `params.*_generation` (additive); new 409 on a broken MC/validation input | G-T3, G-T6 (flag off), G-T13 | a caller cannot identify the rows it read; an existing test changes meaning other than through an OD-G2 refusal |
| G4 classifier | `evidence_status.py` + tests | none | G-T9, G-T13 | flag-off results differ |
| G5 wiring | `workflow.py` | none with the flag off | G-T2, G-T4, G-T5, G-T10–G-T12 | any Step 1–5 test changes meaning |
| G6 Decisions and reports | `workflow.py`, `reports.py` | additive details | G-T7, G-T8 | eligibility depends on labelling |
| G7 startup guard | `main.py` (lifespan), `/ready`, optionally `entrypoint.sh` | production refuses a mismatched head | G-T16 | — |
| G8 release G-A | operations only | 0005 applied explicitly | §11.2 | any §11.2 fact is UNKNOWN |
| G9 release G-B, with v3 | flag constant | legacy evidence non-current | G-T14, G-T17 | a pre-G writer may exist; v3 prerequisites missing |

Status at `e64b50cc`: G1 (`1f5c3ab3`, hardened by G1-H `05d64083`), G2 (`f495f0bd`), G3
(`cb7f78be`), G4 (`446a1e18`), G5 (`1b8a8bd2`), G6 (`4e89b7a8`) and G7 (`e64b50cc`) are committed
locally and unpushed.
- G2 changed `scenarios.py` and the dataset serializer in `datasets.py`.
- G3 changed only `workflow.py` in production code.
- G4 changed only `evidence_status.py` in production code, with the generation check off by
  default (§9.1).
- G5 changed only `workflow.py` in production code. It wires enforcement behind
  `GENERATION_ENFORCEMENT_ENABLED = False`, so enforcement is off in the application (§8.2).
- G6 changed only `workflow.py` in production code; `reports.py` needed no change, because the G5
  helpers already give the report paths their G-T8 behaviour. Decision D3 read the row's "additive
  details" as no new response fields, and G6 adds none. The flag is still off (§10.1).
- G7 changed `main.py` and `migration_status.py` in production code, and left `entrypoint.sh`
  unchanged (decision D6). The guard applies in production only and does not depend on the flag,
  which is still off (§11.4).
- G8–G9 are not started and not authorized.

Status at 2026-10-01: G1–G7 are ported to `port/g-a-stage1` (`92d95bed`), where the G-A
implementation milestone is complete (plan Step 0). G8 is still not started: it stays BLOCKED,
because the §11.2 facts are UNKNOWN. G9 is not started.

## 15. Prototype verification evidence (disposable databases only)

Historical: this section records the prototype, run on scratchpad copies of `4db54722`. It is not
evidence for the committed 0005; see §5.5.

### 15.1 Baseline, with the final prototype

| Check | SQLite | PostgreSQL 16.15 |
|---|---|---|
| New ORM on 0004 / `migration_status` | fails (`no such column`) / exit 1 | fails (`UndefinedColumn`) / exit 1 |
| Upgrade → 0005: tokens NOT NULL, unique, 32-hex, distinct | yes | yes |
| Original columns of legacy rows; job rows | unchanged; unchanged | unchanged; unchanged |
| Legacy `dataset_generation` | NULL | NULL |
| Pre-G ORM on 0005 (read, insert, default token, `dataset_generation` NULL) | yes | yes |
| Duplicate token insert | refused | refused |
| Rehearsal downgrade, then re-upgrade | ok; 0 of 3 tokens shared | ok; 0 of 3 shared |

### 15.2 Recovery

Retry means `alembic upgrade head` run again.

| Case | SQLite: persisted state → retry | PostgreSQL: persisted state → retry |
|---|---|---|
| R1 before any change | nothing; 0004 → completes | nothing → completes |
| R2 after the first column (older-backend insert in the window) | `datasets.generation` nullable, no tokens; 0004 → completes | nothing → completes |
| R3 after the datasets constraint | same as R2 (rolled back past the first `ADD COLUMN`) → completes | nothing → completes |
| R4 after both constraints | same as R2 → completes | nothing → completes |
| R5 silently skipped constraint | post-conditions raise; 0004; state as R2 → completes | raises; nothing → completes |
| R6 hand-built first column | → completes | → completes |
| R7 partial backfill | the 1 existing token is preserved | the 1 existing token is preserved |
| R8 datasets constrained | the 2 dataset tokens are preserved | same |
| R9 both constrained | the 2 + 1 tokens are preserved | same |
| R10 complete, not recorded | → 0005, tokens preserved | same |
| R11 duplicate tokens | refused twice; stays 0004; tokens unchanged | same |

In every completing case, on both engines:

- 0005 was recorded only with a complete schema (independent check);
- no `_alembic_tmp_*` table was left;
- job and legacy digests were unchanged, and legacy `dataset_generation` stayed NULL;
- a second retry was a no-op with tokens unchanged.

### 15.3 Startup guard mechanism

A throwaway FastAPI app whose lifespan raises the `migration_status` message: uvicorn 0.48.0 logs
"Application startup failed. Exiting." and exits with code 3. VERIFIED locally; NOT TESTED on the
production pins. Since G7 the application's own guard gives the same exit code and message with local
uvicorn 0.48.0 (§11.4); still NOT TESTED on the production pins.

## 16. Remaining unknowns

- Render runtime and start command, pre-deploy command, instance count, deploy overlap, and
  failed-deploy behaviour.
- Production PostgreSQL version and current Alembic revision, and whether production is exactly
  Supabase.
- Whether anything writes explicit ids or timestamps in production, and whether any deployment
  uses SQLite.
- Startup-guard behaviour on uvicorn 0.52.4 and FastAPI 0.141.1.
- Full application behaviour with enforcement on (NOT TESTED). The migration and ORM layer were
  prototyped; G5 tests its own consumers (§8.2) and G6 the Decision and report paths (§10.1), both
  with the flag switched on in tests only. Any deployment with enforcement on is not tested.
  Likewise a full pre-G application on 0005, and the full G-A application.
- Whether the production platform runs a migration or status step on start, restart, redeploy or
  rollback, and so whether a pre-G rollback on 0005 can start at all (§11.1).
- PostgreSQL behaviour of the committed 0005 beyond local PostgreSQL 18.6: the CI job (PostgreSQL
  16) has not run, PostgreSQL 16 has not been executed locally, and the production version is
  UNKNOWN. Locally on 18.6, 31 of 31 required cases passed with 0 skipped at `11053465` (§5.5).
- Whether any SQLite deployment enables foreign-key enforcement (§5.4).
- G1-H on PostgreSQL: only the local 18.6 run REPORTED in `05d64083` exists. CI, PostgreSQL 16
  and production are NOT TESTED. Privileged roles can still disable the guards (§3).
- G2: the PostgreSQL variant of `..._assigns_and_reports_tokens` (NOT RUN), the CI job,
  PostgreSQL 16, production and the frontend gates (§7.1).
- G3: the full backend suite on PostgreSQL (NOT RUN), the CI job, PostgreSQL 16 and production
  (§7.2).
- G4: the full backend suite on PostgreSQL (NOT RUN), the CI job, PostgreSQL 16 and production
  (§9.1). The local PostgreSQL 18.6 run does not verify the classifier on any database, because
  the classifier tests use none.
- G5: the full backend suite on PostgreSQL (NOT RUN), the fault run on PostgreSQL (NOT RUN), the
  CI job, PostgreSQL 16 and production (§8.2). Enforcement is off in the application, so no
  deployment has run the checks.
- G6: the full backend suite on PostgreSQL (NOT RUN), the PostgreSQL migration and chain tests that
  need the `postgres` maintenance database (NOT RUN), the fault run on PostgreSQL (NOT RUN), the CI
  job, PostgreSQL 16 and production (§10.1). Whether any stored selection holds the state decision
  D2 refuses (UNKNOWN).
- G7: the PostgreSQL migration and chain tests that need the `postgres` maintenance database, the
  full backend suite on PostgreSQL and the fault run on PostgreSQL (NOT RUN); the CI job and
  PostgreSQL 16 (NOT RUN); the guard on the production pins (NOT TESTED); Render's start command,
  working directory, served application object and deploy behaviour, the production PostgreSQL
  version and revision, and the production application role's access to `alembic_version`
  (UNKNOWN); the cause of the intermittent argon2 failure (UNKNOWN); §1 rule 6 against exact head
  equality (CONFLICTING) (§11.4).
- Which stored workflows reach selected MC or validation with an input that fails Step 5 rules,
  and so would meet the OD-G2 refusal (UNKNOWN). For the existing tests this is answered: exactly
  one, whose fixture was corrected (§7.2, D1).
- OD-G2 itself is resolved: approved 2026-09-28 (§8.1).
