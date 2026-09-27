# Generation Identity — Implementation Contract (ACCEPTED; not implemented)

- **Status:** APPROVED SPECIFICATION. The design direction was accepted on 2026-09-26, and this
  contract on 2026-09-28, with OD-G2 approved (§8) and the legacy policy (§6) confirmed.
  - Approval sets the intended engineering behaviour. It does not show that the migration, the
    application integration or a production deployment is ready.
  - This document is a specification only. It authorizes no migration, model, endpoint,
    configuration, engine-version or production change, and no stage in §14.
  - Nothing here is implemented. The migration and model changes exist only as a scratchpad
    prototype (§5), and application behaviour with enforcement on is NOT TESTED.
- **Base:** `4db54722` (interim Step 5 commit) on `fix/d1-replication-costs`. The repository has
  no migration 0005 and no generation code (VERIFIED by grep and file listing).
- **Related:** spec `2026-09-25-analytical-versioning-historical-evidence.md` §5.4 (the release
  blocker) and §3.1 (corrected identity table); plan Steps 5 and 9; `docs/operations.md` (release
  and rollback runbook).
- **Prototype:** everything in §5 and §15 was run only in scratchpad copies of `4db54722`
  (`gen_base` = committed code, `gen_proto` = prototype), against disposable SQLite files and
  disposable PostgreSQL 16.15 containers.
- **Evidence labels:** VERIFIED, APPROVED SPECIFICATION, REPORTED, PROPOSED, INFERRED, NOT TESTED,
  UNKNOWN, CONFLICTING. A VERIFIED result in §4–§6, §11 and §15 applies to the level that was
  actually run: the prototype migration, the ORM models, or a throwaway app. It does not apply to
  the full NovaQ backend.

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

## 2. Verified baseline (at `4db54722` unless stated)

| Fact | Evidence | Label |
|---|---|---|
| Dataset rows are created only in `analyses.py:218`, `analyses.py:271`, `datasets.py:112` | grep of `Dataset(` | VERIFIED |
| Scenario rows are created only in `scenarios.py:321` (`POST /scenarios`), which verifies against the `dataset` row loaded at `:274` | schema 1 `scenarios.py:232-238`; schema 2 `scenarios.py:159-180` | VERIFIED |
| Saved settings and results are immutable | `PATCH` returns 409 (`scenarios.py:381-386`); `ScenarioPatch` has only `name`, `settings`, `results` | VERIFIED |
| Every Job is built in `_save_job` (`workflow.py:518`), with 13 callers | grep of `Job(` in `backend/` | VERIFIED |
| Evidence and selections are resolved by integer | `_job_matches` (`workflow.py:453`); `_selected_scenario` (`:540`); `_require_selected_separate_plan` (`:1792-1810`) | VERIFIED |
| Selected MC and validation have no dependency gate at write time; `run_validation_current` compares `dataset_id` inline (`:1100`) | source | VERIFIED |
| The dataset report reads no jobs (`reports.py:529-575`) | source | VERIFIED |
| Deletes are hard: `datasets.py:161`, `scenarios.py:406`; dataset → scenarios cascades in the ORM; there is no user-delete route | source | VERIFIED |
| `scenarios.dataset_id` foreign key is created in `0001:72`. PostgreSQL enforces it (dev database: `NO ACTION`); SQLite does not (no `PRAGMA foreign_keys`) | source, read-only dev query | VERIFIED |
| Alembic: `env.py` runs the whole upgrade inside one `begin_transaction()`. Alembic `SQLiteImpl.transactional_ddl = False` and `PostgresqlImpl.transactional_ddl = True` (local 1.19.1; production pins 1.19.2) | source, runtime check | VERIFIED |
| Image: `Dockerfile.api` copies `alembic.ini` and `migrations/`; `CMD ["/bin/sh", "/app/backend/api/entrypoint.sh"]` | source | VERIFIED |
| `entrypoint.sh` runs `backend.operations.preflight` (settings only), then uvicorn `backend.api.main:app` | source | VERIFIED |
| `create_app` has no startup hook; `app = create_app()` runs at import (`main.py:266`); `/ready` is `SELECT 1` | source | VERIFIED |
| `migration_status` exits 1 on any head mismatch | source; run in the prototype | VERIFIED |
| Production Compose orders migrate → bootstrap-admin → api (`depends_on … service_completed_successfully`); the `migrate` service runs `alembic upgrade head && migration_status` | `docker-compose.production.yml` | VERIFIED |
| Runbook: "Rollback is backup-first, not `alembic downgrade`" (`operations.md:216-220`); "Migration failure prevents API startup" describes the Compose ordering | `docs/operations.md` | VERIFIED (document) |
| Production settings require `API_WORKERS=1` (`settings.py:238`) | source | VERIFIED |
| The hosted API is the Render web service `Qcu-NovaQ-Analytics`; pushing `main` deploys Render and Pages | `memory.md:185-188`, `handoff.md:256-257` | REPORTED |
| The hosted database is Supabase | 2026-09-14 spec, plan and report | REPORTED |
| The repository holds no Render blueprint or start command (`render.yaml`, Procfile); Render's runtime, start command, pre-deploy command, instance count and deploy overlap are not recorded | file search | VERIFIED absence; the settings are **UNKNOWN** |

## 3. The token

- 128 random bits written as 32 lowercase hex characters, generated independently of id, time and
  content.
- One per row in `datasets.generation` and `scenarios.generation`: NOT NULL, unique
  (`uq_<table>_generation`).
- Immutable after insert. No code path writes it, `PATCH` cannot reach it, and the unique
  constraint refuses a copy.
- `scenarios.dataset_generation` records the dataset token that the save verified. It is nullable,
  has no default of any kind, and only the scenario save path writes it.

## 4. Application default vs database default

| Layer | Value | Role |
|---|---|---|
| Application: model `default=new_generation` (`uuid.uuid4().hex`) | set by every ORM insert, before flush | authoritative; known inside the same transaction |
| Database: default installed by 0005 | PostgreSQL `replace(gen_random_uuid()::text,'-','')`; SQLite `lower(hex(randomblob(16)))` | safety net for inserts that omit the column (an older backend on 0005, raw SQL) |

- Both layers give the same 32-hex format (VERIFIED on both engines). An ORM insert always
  supplies the application value.
- `create_all` builds (tests; `seed.py` on an empty database) get NOT NULL, unique and the
  application default, but no database default. This is documented and deliberate; M2 covers the
  database default.
- `gen_random_uuid()` is built into PostgreSQL 13 and later. The production version is UNKNOWN,
  which is a stop condition.

## 5. Migration 0005 (verified prototype)

This section describes a scratchpad prototype, not repository code. The repository has no
migration 0005, and stage G1 (§14) would add it under separate authorization.

### 5.1 What it writes

- **Every existing `datasets` and `scenarios` row gets a newly assigned token**, written into the
  new `generation` column. On SQLite the constraint step rebuilds both tables (Alembic batch mode
  copies every row into a new table).
- All pre-existing column values of those rows are unchanged. VERIFIED by a digest of every
  original column, before and after, on both engines.
- `scenarios.dataset_generation` is added and left NULL for every existing row: the relationship
  cannot be established.
- The `jobs` table is not written. VERIFIED by a digest of every stored job row, on both engines.
- No job's params or results are touched, and no analytical claim is rewritten.

### 5.2 Structure

Helpers are shared by `upgrade()` and the recovery tests:

- `upgrade_table(table)`:
  1. On SQLite, drop any leftover `_alembic_tmp_<table>`.
  2. Add a nullable `generation` if it is absent.
  3. `UPDATE … SET generation = <token> WHERE generation IS NULL`. An existing token is never
     replaced.
  4. **Refuse duplicated tokens** with an explicit error. They are never regenerated.
  5. If the column is nullable or `uq_<table>_generation` is absent, set NOT NULL plus the
     database default and add the constraint.
- `add_dataset_generation()`: add the column if it is absent.
- `assert_postconditions()`: raise unless both `generation` columns exist, are NOT NULL, have a
  database default and their unique constraint, no row lacks a token, and
  `scenarios.dataset_generation` exists.
- `upgrade()` = `upgrade_table("datasets")`, `upgrade_table("scenarios")`,
  `add_dataset_generation()`, `assert_postconditions()`. Alembic records `0005` only after
  `upgrade()` returns, so it never records 0005 over a partial schema.
- An unsupported dialect raises.
- `downgrade()`: guarded drops, for **rehearsal only**. Production rollback is backup-first
  (`operations.md:216-220`).

### 5.3 Recovery behaviour (VERIFIED, §15.2)

| Engine | What a failed run leaves behind | Why |
|---|---|---|
| PostgreSQL | nothing: `alembic_version` 0004, no new column | Transactional DDL; the upgrade runs in one transaction and is rolled back |
| SQLite | `datasets.generation`, nullable, with no tokens; `alembic_version` 0004; everything later is rolled back | Non-transactional DDL: the first `ADD COLUMN` commits before any row change. The first `UPDATE` opens a transaction that covers the remaining steps, including the batch rebuild |

- A plain retry completes from every state, on both engines.
- The first, unguarded prototype got stuck on SQLite (`duplicate column name`), which is why every
  step is guarded.

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

- The S2–S4 columns are specified behaviour (APPROVED SPECIFICATION). None of it is implemented.
- Application behaviour in S3 and S4 is NOT TESTED.

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
  `2026-09-25-analytical-versioning-historical-evidence.md` §5.4, release blocker).
  - Enforcement (S3) is what closes it. S2 only records the tokens that S3 needs.
  - **Release G-A does not complete the identity repair.** The release blocker stays open until
    G-B.
- **Rollback G-B → G-A:** enforcement off, Step 5 rules only, and the defect returns. Tokens stay,
  and stamped evidence becomes eligible again when enforcement returns.
- **Rollback G-A → pre-G on 0005:**
  - Schema-compatible at the ORM layer: the pre-G models read and insert on 0005 (VERIFIED in the
    prototype). A full pre-G application on 0005 is NOT TESTED.
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
| `POST /scenarios` (`scenarios.py:321`) | `generation`; `dataset_generation = dataset.generation` | the row loaded at `:274` and verified by `_verify_calculation`; NULL when the scenario has no dataset (never selectable, `workflow.py:302`) |
| Legacy dataset re-parent (`scenarios.py:309`) | nothing | identity unchanged |
| `_save_job` (all 13 callers) | `params.scenario_generation`, `params.dataset_generation` | the ORM rows the computation read |

- `_save_job` receives the dataset row. For Current kinds that is the `_current_dataset` row; for
  scenario-bound kinds it is the scenario's dataset row.
- It always stamps what was read. Under enforcement only, it refuses with 409 when
  `dataset.generation != scenario.dataset_generation`. With enforcement off it records the tokens
  and changes nothing else.
- Stamping itself is behaviour-neutral in S2. The one intended S2 behaviour change is the OD-G2
  write-time gate (§8).

| Caller (`workflow.py`) | Scenario read | Dataset read |
|---|---|---|
| selection `:902` | `_own_verified_scenario` | `:309` |
| DES `:941` | `_require_selection` | `:931` |
| DES/MC/validation current `:972`, `:1032`, `:1139` | — | `_current_dataset` |
| MC `:1001`, validation `:1062` | `_require_selection` | the scenario's dataset row |
| selected DES/MC/validation `:2045`, `:2312`, `:2467` | `_require_selected_separate_plan` | `:1829` |
| Decision `:2700`, `:2730` | as above | as above |

## 8. Where the token is checked

Every row applies under enforcement (S3 and later). The write-time gates also apply in S2, without
their token part (OD-G2, below).

| Check | Rule |
|---|---|
| `_own_verified_scenario` | `dataset_generation` must be present and equal the live dataset token. Otherwise 422 "Scenario provenance is incomplete; recalculate and save a new plan." This check runs last, so existing reasons keep their messages. |
| Selection-binding helper (used by `_selected_scenario` and `_require_selected_separate_plan`) | `selection.params.scenario_generation == scenario.generation`, otherwise no eligible selection. Selected-plan endpoints: 409 "The selected plan was replaced; select it again in Compare." |
| Classifier (§9) via `_current_evidence`, `require_dependencies_current`, `current_decision_for_report` | every recorded token must equal the live row's |
| Write-time gates (OD-G2): selected MC (`des_job`), selected validation (`des_job`, `mc_job`) | from G-A: `require_dependencies_current` on every input before computing, whether enforcement is on or off. Under enforcement: matching recorded tokens as well |
| `run_validation_current` `:1100` | classifier on the MC job, plus `mc.params.dataset_generation == dataset.generation` |
| Existing integer `result.scenario_id` checks | kept as consistency checks |

- `_latest_job` keeps selecting by id, with no fallback (D7 rule).

### 8.1 OD-G2 — write-time dependency integrity (APPROVED 2026-09-28; not implemented)

1. Before creating a new analytical job, the selected-plan Monte Carlo and validation endpoints
   check that their input evidence satisfies the existing Step 5 dependency-integrity rules
   (`require_dependencies_current`, `workflow.py:710`). If it does not, they refuse with 409
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

## 10. Reports

- **Selected report:** 409 on any mismatch, through `require_dependencies_current`.
- **ID-scoped scenario PDF/Excel:** the Decision section comes only from
  `current_decision_for_report`. A mismatched or unrecorded token gives "Management recommendation
  unavailable", which closes the reproduced leak of a deleted scenario's Decision.
- **Dataset report:** unchanged (reads no jobs).
- Eligibility is decided before any historical labelling. OD-7 and Step 11 are out of scope.

## 11. Deployment

### 11.1 Findings

- **The Docker image runs `entrypoint.sh`** (VERIFIED). Whether Render runs that command, overrides
  it, or uses a native runtime with its own start command is **UNKNOWN**. So a guard placed only in
  `entrypoint.sh` might never run.
- **Proposed guard: inside the application.** A FastAPI lifespan hook in `create_app` verifies,
  when `NOVAQ_ENV=production`, that the database is exactly at the code's Alembic head. It uses the
  same logic as `migration_status`; `alembic.ini` and `migrations/` are in the image.
  - It runs whenever `backend.api.main:app` is served, however uvicorn is launched.
  - Mechanism VERIFIED locally on a throwaway app with uvicorn 0.48.0 (§15.3): a lifespan exception
    gives "Application startup failed. Exiting.", exit code 3, and nothing is served. The guard
    itself is not implemented.
  - On the production pins (uvicorn 0.52.4, FastAPI 0.141.1) it is **NOT TESTED**.
  - `entrypoint.sh` may run `migration_status` as well, as defence in depth.
  - `/ready` also returns 503 on a mismatch, in case the schema changes under a running process.
- **Limit of the guard:** it cannot help if Render serves a different application object (UNKNOWN,
  and a stop condition).
- **How each backend behaves on each schema:**
  - Older backend on 0005: the pre-G ORM models read and insert (VERIFIED in the prototype). So
    migrating first is expected to keep the service available (INFERRED). A full pre-G
    application on 0005 is NOT TESTED.
  - Newer backend on 0004: it would refuse to start through the guard (PROPOSED). Without the
    guard, the new ORM models fail on their first query: `no such column` on SQLite,
    `UndefinedColumn` on PostgreSQL (VERIFIED in the prototype).
- **Deploy overlap:** whether Render keeps the previous instance serving when a deploy fails, and
  whether old and new instances overlap during a deploy, is **UNKNOWN**. Until it is known, assume
  both.

### 11.2 Required order (none of it authorized now)

**Pre-release facts (stop until each is established):**

- Render runtime and start command, pre-deploy command, instance count and deploy overlap.
- Production PostgreSQL version (≥ 13) and current Alembic revision, read-only.
- Backup and restore evidence per `operations.md`.

**G-A:**

1. Take the backup required by the runbook.
2. Apply 0005 explicitly, with the mechanism named in the pre-release facts. Never assume Render
   applies it.
3. `migration_status` must exit 0. From here, pre-G code is serving on 0005 (S1).
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
| pre-G (`4db54722`) | S0: normal | S1: ORM read and insert VERIFIED in the prototype; full application NOT TESTED; writes unstamped evidence (fails closed later) |
| G-A (stamping, enforcement off) | refuses to start: PROPOSED guard; only the mechanism is VERIFIED, on a throwaway app | S2: stamps tokens and applies the OD-G2 gate; **the identity defect remains** |
| G-B (enforcement, v3) | refuses to start (PROPOSED guard) | S3/S4: unstamped evidence is never current (specified; NOT TESTED) |

- Rollback is backup-first.
- Code-only rollback G-B → G-A and G-A → pre-G is expected to be schema-compatible: the ORM layer
  is VERIFIED in the prototype, the full application is NOT TESTED.
- Schema rollback means restoring the backup (§6.2 R).

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
| G-T3 Job stamping | all 13 `_save_job` callers record the tokens of the rows actually read |
| G-T4 Current DES (and Current MC/validation, `:1100`) | a replaced dataset (same id, same time, byte-identical) is rejected |
| G-T5 Selected-plan DES | rejected on a replaced scenario |
| G-T6 MC and validation write-time gates (OD-G2) | Flag off: a DES/MC input that fails Step 5 rules is refused with 409 before computing, and no job is stored; an unstamped but otherwise eligible input is accepted. Enforcement on: a wrong-generation or unrecorded input is also refused |
| G-T7 Decision evidence | never served or produced from a mismatched or unrecorded chain |
| G-T8 PDF and Excel | ID-scoped export shows "recommendation unavailable"; selected report 409 |
| G-T9 Missing and mismatched identities | `GENERATION_UNRECORDED` and `GENERATION_MISMATCH` with the correct statuses; all reasons kept; mutation tests |
| G-T10 Same id, same timestamp | rejected at every consumer |
| G-T11 Byte-identical replacement | rejected at every consumer |
| G-T12 Legacy jobs | every pre-existing job kind is non-current under enforcement; stored rows unchanged |
| G-T13 Flag off | identical results to Steps 1–5 on the existing tests and the local fixture, except the OD-G2 refusals (G-T6). Each existing test those refusals affect is reported for review, never silently rewritten |
| G-T14 Both engines | all of the above on SQLite, and on PostgreSQL through `NOVAQ_TEST_DATABASE_URL` |
| G-T15 Rollback and retry | M1–M7 and R1–R11 below |
| G-T16 Startup guard | the production app refuses to start on a mismatched head; `/ready` 503; dev and test unaffected |
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

## 15. Verification evidence (disposable databases only)

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
production pins.

## 16. Remaining unknowns

- Render runtime and start command, pre-deploy command, instance count, deploy overlap, and
  failed-deploy behaviour.
- Production PostgreSQL version and current Alembic revision, and whether production is exactly
  Supabase.
- Whether anything writes explicit ids or timestamps in production, and whether any deployment
  uses SQLite.
- Startup-guard behaviour on uvicorn 0.52.4 and FastAPI 0.141.1.
- Full application behaviour with enforcement on (NOT TESTED: only the migration and ORM layer were
  prototyped). Likewise a full pre-G application on 0005, and the full G-A application.
- Which existing tests or stored workflows reach selected MC or validation with an input that
  fails Step 5 rules, and so would meet the new OD-G2 refusal (NOT TESTED).
- OD-G2 itself is resolved: approved 2026-09-28 (§8.1).
