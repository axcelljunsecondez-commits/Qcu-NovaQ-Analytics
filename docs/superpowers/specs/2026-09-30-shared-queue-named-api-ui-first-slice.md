# Named Shared Queue: First API and UI Exposure Slice (Specification)

Status: **PROPOSED. Nothing in this document is implemented.**

- OD-1 to OD-9 were approved on 2026-09-30 (section 19).
- Numeric identity option B1 was approved on 2026-10-01; it is NOT IMPLEMENTED (section 3). B2 is not
  approved.
- G-A is BLOCKED (incomplete). API/UI implementation is NOT AUTHORIZED.
- The Stage 0 measurements were taken on 2026-09-30 (section 6.4). The API limits remain provisional and
  **NOT PRODUCTION-APPROVED**, because the production result-storage cap and the production request and
  response limits are UNKNOWN.
- No code, test, schema, migration, or dependency was changed while writing or correcting this document.

**Update 2026-10-01 (implementation; the status lines above are kept as history):**

- G-A is complete. Its final implementation commit `e7e3cdae` was integrated into `feat/shared-queue-segments` by
  the no-fast-forward merge `a49bb1f1` (section 21.1). `GENERATION_ENFORCEMENT_ENABLED` stays `False`.
- The product owner's master continuation prompt (2026-10-01) authorized LOCAL implementation of this first
  slice. The backend (Stage 1) and frontend (Stage 2) are implemented locally, including B1 (section 21).
- The API limits remain provisional and **NOT PRODUCTION-APPROVED**. Production facts are still UNKNOWN, so
  this is LOCAL IMPLEMENTATION COMPLETE, not production or deployment ready. Nothing is pushed or deployed.

- Date: 2026-09-30
- Branch: `feat/shared-queue-segments` at `90fdf9e2` (re-verified before writing, section 1.1)
- Approved inputs: decisions A1-A6 and the first-slice flow supplied by the product owner on
  2026-09-30 (section 2)
- Builds on (all APPROVED SPECIFICATION and implemented):
  - `2026-09-26-shared-queue-workforce-foundation.md` (5B-1)
  - `2026-09-28-shared-queue-named-employee-des-policy.md` (P1-P9, X1-X7)
  - `2026-09-28-shared-queue-named-des.md` (5B-4.3)
  - `2026-09-28-shared-queue-named-replications.md` (5B-4.4)
  - `2026-09-28-shared-queue-named-playback.md` (5B-4.5, playback v4)
  - `2026-09-29-shared-queue-named-attribution.md` (5B-4.6, D1-D8)
  - `2026-09-30-shared-queue-named-workforce-cost.md` (5B-5, C1-C16; stays backend-only here)

Evidence labels follow `AGENTS.md` section 2. Measurements in section 6 come from scratch probes that
were run in this runtime and are not committed. They are local measurement evidence only and never
production evidence.

---

## 1. VERIFIED inherited architecture

### 1.1 Repository and worktrees (re-verified 2026-09-30)

| Item | State | Evidence |
|---|---|---|
| Current branch | `feat/shared-queue-segments`, HEAD `90fdf9e2` | `git rev-parse HEAD` |
| Chain | `19ff54a1` -> `6777ad3f` -> `90fdf9e2` | `git log --format='%h %p'` |
| Working tree | untracked: `.claude/` and this specification; nothing else | `git status --short` |
| Remote | no `origin/feat/shared-queue-segments` | `git ls-remote --heads` returned nothing |
| Divergence | 25 commits ahead of local `main` (`1d3294cb`); local `main` is 1 docs commit ahead of `origin/main` (`2d063c91`) | `git rev-list --left-right --count` |
| API, DB, frontend changes on this branch | none (`git diff main...HEAD` touches only `backend/queueing_engine/`, tests, docs, and the governance files) | `git diff --stat main...HEAD` |

Other worktrees:

| Worktree | Branch / HEAD | State relevant here |
|---|---|---|
| `.claude/worktrees/fix-d1-replication-costs` | `fix/d1-replication-costs` `bb9ada41` | Clean. The committed G-A line (32 commits past `main`). It includes `migrations/versions/0005_generation_identity.py`, `backend/api/evidence_status.py`, `backend/api/current_dataset.py`, `backend/db/generation_guards.py`, and +545 lines in `workflow.py`. `GENERATION_ENFORCEMENT_ENABLED = False` (its `workflow.py:102`). |
| `.claude/worktrees/port-g-a-stage1` | `port/g-a-stage1` **`00582c11`** (re-verified 2026-09-30 23:56 +0800) | Another session's work, read only and never edited by this work. The chain is `2d063c91` (`origin/main`) -> `92d95bed` -> `00582c11`. There is no later commit, no operation is in progress, and nothing is pushed. The worktree is **not clean**: it holds uncommitted D7 frontend work (4 files, modified 23:47-23:52, section 13). It is in neither `main` nor `feat/shared-queue-segments`. **`92d95bed`** (30 paths, VERIFIED) holds migration `0005` with `Dataset.generation` and `Scenario.generation`, `evidence_status.py`, `current_dataset.py`, `generation_guards.py`, and the `workflow.py`, `main.py`, and `models.py` changes. That this is the G-A backend (steps 1-5, D7 backend, G1-G7) is REPORTED from the port session's record. 25 of its 30 paths are byte-identical to `fix/d1-replication-costs`; the other 5 differ only by leaving out the D1/D5/D10 accounting. **`00582c11`** changes one test file (`tests/test_step5_missing_dependency.py`, +33/-8), making two id-reuse cases portable to PostgreSQL; the blob equals the `fix/d1` version. It carries **no** frontend, CI, or docs change. The G-A PostgreSQL gate is REPORTED green on PG 18.6: CI command 74/74 and Stage-1 set 666/666, from the other session's memory record. The logs in that session's scratchpad corroborate the counts ("74 passed" at 21:38, "666 passed" at 23:17), but the logs do not show the server version. |
| `.claude/worktrees/nervous-hodgkin-2b6ef1` | `claude/nervous-hodgkin-2b6ef1` | Uncommitted edits to both locale files and an untracked `translationKeys.test.ts`. |
| `.claude/worktrees/jovial-keller-b530f7` | detached `dac2577e` | One modified test (`tests/test_step5_missing_dependency.py`). |
| `clever-boyd-87ff32`, `unruffled-hawking-257d18` | clean | Not relevant. |

### 1.2 API and persistence conventions (this branch)

- **Stateless compute routers**: `/analysis`, `/simulation/*`, and `/optimize/*`. These are frozen contracts
  (`AGENTS.md` Constraints) and are CSRF-exempt.
- **Workflow evidence**: `/analyses/{analysis_id}/workflow/*` (`backend/api/workflow.py`).
  - Evidence is a `Job` row (`backend/db/models.py:181-197`): `kind` `String(64)`, `status`, `params_json`,
    `result_json`, `tenant_id`, `created_at`, and `finished_at`.
  - `_save_job` (`workflow.py:469-514`):
    - accepts only `WORKFLOW_KINDS` (`workflow.py:64`);
    - stamps `analysis_id`, `scenario_id`, `dataset_id`, `engine_version` (the legacy
      `ENGINE_VERSION = "novaq-2026-09-unified-des-v1"`), and `setup_hash`;
    - rejects a `result_json` larger than `settings.result_jsonb_max_bytes` with **413**. The default is
      512 KiB, and the `RESULT_JSONB_MAX_BYTES` environment variable can set it from 1 KiB to 10 MiB
      (`settings.py:174`).
  - Evidence is current only while `setup_hash` equals the Setup fingerprint (`_job_setup_current`,
    `workflow.py:228-234`). The fingerprint is `scenarios.setup_fingerprint` (`scenarios.py:195`).
  - Only `workflow.py` queries `Job`, and always filtered by `kind` (`workflow.py:445-446`). On the committed
    G-A line the same holds (`workflow.py:536-537` there). A new kind is therefore invisible to existing
    evidence logic on both lines (VERIFIED on committed code; the uncommitted port was not inspected
    line by line).
- **Execution** is synchronous in the request, with no background worker. `API_WORKERS` defaults to 1
  (`backend/api/entrypoint.sh:10`).
- **Auth and ownership**:
  - `get_current_user` returns **401** "Not authenticated." (`deps.py:27`), and a role guard returns **403**.
  - `own_analysis` returns **404** "Analysis not found." for a missing or foreign analysis
    (`analyses.py:75-79`).
  - The compute rate limit returns **429** (`deps.py:63`; category `compute`, default 30,
    `settings.py:189`).
- **CSRF**: a non-GET request with a session cookie needs `X-CSRF-Token` equal to the CSRF cookie, or it
  gets **403** "CSRF token mismatch." (`main.py:53-72`). The exempt families `("/analysis", "/simulation",
  "/optimize", "/onboarding")` are pinned by `tests/test_production_hardening.py`. The SPA attaches the
  header automatically (`frontend/src/lib/http.ts:13-15`).

### 1.3 Named pipeline (backend only, VERIFIED)

- **Isolation guard**: `tests/test_shared_segments.py:363-380` fails when any `backend/**/*.py` file outside
  the 15 enhancement modules contains any module name as a substring. No such file exists today.
- **Required inputs.** None of these has a default.
  - Horizon and demand: `OperatingHorizon(start_minute, end_minute)` and
    `DemandPeriod(period_id, start_minute, end_minute, arrival_rate_per_hour, service_rate_per_hour)`
    (`shared_segments.py:64-81`).
  - Required staffing, X7: `StaffingSegment(segment_id, start_minute, end_minute, servers)`
    (`shared_segments.py:84-90`).
  - Workforce: `Employee`, `AvailabilityWindow`, `EmployeePay`, `ShiftRules`, `BreakRule`,
    `BreakRequirement`, `WorkforceRules`, `ScheduledShift`, and `ScheduledBreak`
    (`shared_workforce.py:66-137`).
  - Policies: `closing_policy` in `CLOSING_POLICIES = (DRAIN, HARD_CUTOFF)`
    (`shared_continuous_des.py:50`), and `employee_policy: EmployeeDesPolicy`. Each of its six fields
    accepts only its `APPROVED_EMPLOYEE_POLICY` value (`shared_named_des.py:78-98`, check at 250-257).
- **Timeline rules** (`validate_timeline`, `shared_segments.py:176-224`):
  - demand periods and required-staffing segments must each tile the horizon exactly;
  - a staffing segment may not cross a demand-period boundary.
- **X4 precondition** (`shared_employee_states.py:274-285`): an INVALID roster is rejected, and so is an
  INCOMPLETE one unless only pay fields are missing. Pay values may therefore be `null` for the DES.
- **Demand adapter** (`timeline_from_aggregate_rows`, `shared_segments.py:373-416`) accepts only rows whose
  `time` matches `^HH:MM-HH:MM$` (line 35). It rejects `variance`, `K`, or `theta` (line 53, lines 399-405)
  and separate-queue rows (line 398). It also builds staffing segments from the dataset's `c`. This
  specification **discards** them (A3).
- **Consequence for datasets** (VERIFIED by reading; NOT TESTED against a stored dataset): event uploads for
  a shared queue always write `variance` (`analysis_ingestion.py:306`) and label rows
  `"YYYY-MM-DD <segment> UTC"` (`analysis_ingestion.py:60-62`). The adapter rejects every such row. Only
  aggregate uploads with clock-range labels and no `variance`, `K`, or `theta` qualify.
- **Replications**: `run_named_replications` (`shared_named_replications.py:419-496`):
  - needs `replications` from 1 to `MC_MAX_TRIALS` (100000), and a `seed` that is a whole number ≥ 0 or
    None;
  - returns `{"replications": rows, "summary": aggregate, "provenance": {...}}`;
  - `provenance` holds `inputs` (`named_inputs_snapshot`), `inputs_sha256`, `root_entropy`, `seed`,
    `closing_policy`, `employee_policy`, `runtime`, and all engine and method versions;
  - retains no events, customer rows, or timelines (`provenance.retained`);
  - sets the aggregate's `verdict: None` and `verdict_reason: NO_VERDICT_REASON`;
  - `root_entropy` is the seed itself when a seed is supplied (source comment at the `assert` in
    `run_named_replications`).
- **Playback**: `playback_from_named_replications(run, i)` (`shared_named_playback.py:1222-1291`):
  - refuses (`NamedPlaybackError`, checks `regeneration_identity`, `closing_policy`, `stored_row`) on a
    version, seed-scheme, digest, rebuild, or stored-row mismatch;
  - returns only the playback, not the regenerated engine result;
  - reports `runtime_matches_recorded` without refusing on it.
- **Attribution**: `build_named_attribution(result, employees)` needs the regenerated named result.
  Attribution D6 (approved) says to regenerate through
  `simulate_named_replication(..., seed_sequence=replication_seed_sequence(root_entropy, i))` and adds no
  runner that mirrors the playback refusal checks.
- **Cost** (`cost_named_workforce`) is single-run only (C12), with no route. It stays backend-only (section 2).

### 1.4 Frontend (this branch)

- Simulate route: `/analyses/:analysisId/simulate`, rendered by `SimulationPage` (`SimulationPage.tsx:617`).
- For a non-separate analysis without a Compare-selected scenario, the page returns a "select a scenario
  first" screen (`SimulationPage.tsx:724-738`). This happens after all hooks and before any shared view.
- Shared playback is `LiveSimulationPlayback`, which reads the legacy anonymous `SimulationTrace`
  (`types.ts:274-310`: `server_id`, `queue_len_after`, segment rows). The named playback shape differs
  (section 10).
- Wait times are shown in minutes (`x 60` at display time: `SimulationPage.tsx:394, 489, 603, 981`).
- Locale files are flat dotted keys in `frontend/public/locales/{en,tl}/translation.json`, with a
  symmetry test at `frontend/src/lib/translationKeys.test.ts`.

---

## 2. Approved decisions A1-A6 (APPROVED SPECIFICATION, 2026-09-30)

| Id | Decision | Rules derived for this slice |
|---|---|---|
| A1 | Workforce input comes from a user-supplied form. Employee ids are pseudonymous, no real names, and there is no upload. | Section 3 schema. No name field anywhere. No defaults. |
| A2 | The roster is user-supplied. 5B-2 and 5B-3 are not exposed. | The adapter never imports `shared_rostering`, `shared_integrated`, or `shared_capacity`, and runs no MILP. |
| A3 | `required_staffing` (X7) is explicit and mandatory. | It is never derived from the dataset `c`, the roster headcount, or an optimizer, and the UI never prefills it. |
| A4 | The legacy shared Simulate stays. A distinct, explicit Named Shared Queue mode is added. | Legacy mode is unchanged and remains the mode when none is selected. Separate Queue is untouched. |
| A5 | Each run persists as one `Job` holding an immutable input snapshot. There is no workforce table, no migration `0005`, no stored trace, and no cross-replication cost. | Section 5. Playback is regenerated on demand. |
| A6 | Exactly one thin adapter, `backend/api/shared_named.py`, may import the named modules. | The isolation test changes narrowly (section 14). The adapter holds no queueing, DES, playback, attribution, or cost logic. |

Also approved for this slice, from the task statement:

- Workforce cost stays backend-only.
- Nothing is added to Compare, Decision, or Reports.
- There is no PASS/FAIL, no acceptance rule, no D15 interpretation, and no cross-replication cost
  aggregation.
- Every numeric API field must be finite.
- The model scope is what the named timeline accepts, and nothing is silently degraded.

---

## 3. Workforce input schema (PROPOSED; mirrors the domain dataclasses 1:1)

Field names equal the dataclass field names, so the recorded snapshot (`named_inputs_snapshot`) equals
what the client sent after type conversion. Times are **whole minutes since midnight** (0-1440), as in the
domain. The UI converts `HH:MM` to and from minutes; the API parses no clock strings.

Every request model uses `ConfigDict(extra="forbid", allow_inf_nan=False)`.

- Integer fields are `StrictInt`: a float such as `60.0`, a string, or a boolean is rejected. This is required
  because the input digest distinguishes an int from a float of equal value (`INPUTS_DIGEST_DEFINITION`).
- Float fields accept JSON numbers and reject booleans and strings.
- The limits `N_MAX`, `S_MAX`, `E_MAX`, and `R_MAX` are defined in section 6.

```text
NamedWorkforceInput {
  dataset_id: StrictInt >= 1                        # required; see OD-2
  horizon: { start_minute: StrictInt 0..1440, end_minute: StrictInt 0..1440 }          # required
  required_staffing: list[1..S_MAX] of {             # required (X7); never inferred (A3)
      segment_id: str 1..64, start_minute: StrictInt 0..1440, end_minute: StrictInt 0..1440,
      servers: StrictInt >= 0 }
  employees: list[1..E_MAX] of {                     # required
      employee_id: str 1..64                         # pseudonymous; the domain regex is authoritative
      availability: list[1..AV_MAX] of { start_minute: StrictInt, end_minute: StrictInt }
      pay: {                                         # every key required; the value may be null = "not supplied" (never 0)
        regular_rate_per_hour: finite float >= 0 | null,     # digest-critical: B1 persistence identity check below
        overtime_rate_per_hour: finite float >= 0 | null,    # digest-critical: B1 persistence identity check below
        daily_regular_paid_minutes: StrictInt >= 0 | null } }
  rules: {                                           # required
      shift_rules: { earliest_start_minute, latest_end_minute, min_shift_minutes, max_shift_minutes,
                     boundary_granularity_minutes, max_shifts_per_employee: StrictInt,
                     min_minutes_between_shifts: StrictInt | null }   # key required
      break_rules: list[0..BR_MAX] of { min_shift_minutes, max_shift_minutes, min_gap_minutes: StrictInt,
                     breaks: list[0..BQ_MAX] of { name: str 1..64, duration_minutes: StrictInt,
                               paid: StrictBool, earliest_start_offset_minutes: StrictInt,
                               latest_start_offset_minutes: StrictInt } }
      register_count: StrictInt >= 1 }
  roster: list[0..R_MAX] of {                        # required key; an empty list is a valid engine input
      employee_id: str 1..64, start_minute: StrictInt, end_minute: StrictInt,
      breaks: list[0..BS_MAX] of { name: str 1..64, start_minute: StrictInt } }
  closing_policy: one of CLOSING_POLICIES ("DRAIN" | "HARD_CUTOFF")   # required; no default
  employee_policy: { drain_crew, drain_duration, hard_cutoff_release, breaks_at_closing,
                     break_delay, employee_choice }   # required; each must equal APPROVED_EMPLOYEE_POLICY
}

NamedRunRequest = NamedWorkforceInput + {
  replications: StrictInt 1..N_MAX                   # required; no default
  seed: StrictInt 0..9007199254740991                # required; no default; see OD-5
}
```

**Validation boundary.** The API schema checks shape, finiteness, integer strictness, and list lengths only.

- Every semantic rule stays in the domain and is surfaced unchanged. This covers the id pattern, interval
  order, overlaps, coverage, shift and break rules, register excess, X4, X7, and the policies.
- `shared_workforce.validate_workforce_inputs` / `evaluate_roster`, `validate_timeline`, and the named DES
  `_validate` raise or report those rules.
- The API never re-implements them.

**Numeric identity policy: option B1, persistence identity verification** (APPROVED SPECIFICATION by the
product owner, 2026-10-01). **NOT IMPLEMENTED.** B2 is **NOT APPROVED.**

**Historical evidence** (VERIFIED on disposable PostgreSQL 16.15, through the app's `Job.result_json` path,
in one test run on 2026-09-30; section 6.4). These are individual measured values, not a domain.
- The tested `1e-07` survived: it came back as a float with identical bits.
- The tested `1e15` survived.
- The tested `0.0`, `99.5`, `100.0`, `123.456`, `150.0`, and the NovaMart demand rates in the two tested
  payloads survived.
- The tested `1e16` changed representation: it came back as the integer `10000000000000000`. That broke
  `inputs_sha256`, and `playback_from_named_replications` then refused every replication with
  `regeneration_identity`.

**Domain status**

- **The complete safe PostgreSQL numeric domain remains UNKNOWN.**
  - No numeric interval is claimed or accepted as safe.
  - The earlier `[1e-7, 1e15]` rule was withdrawn on 2026-09-30 and is **not** reintroduced.
  - Option A, a characterization, was not performed.
- B1 is a **fail-closed persistence check**. It does not establish a safe floating-point interval. It
  detects a representation change on the actual database at write time.
- The only floating-point values in the recorded inputs (`named_inputs_snapshot`) are these four:
  - `employees[].pay.regular_rate_per_hour` and `employees[].pay.overtime_rate_per_hour` (request);
  - `demand_periods[].arrival_rate_per_hour` and `demand_periods[].service_rate_per_hour` (from the
    selected dataset).

  Every other recorded value is an integer, a string, a boolean, or `null` (VERIFIED from the snapshot
  fields).
- An integer came back unchanged through JSONB (`123456789012345678`, as a JSONB literal; VERIFIED). Integer
  values in these fields are not the observed failure mode.
**Persistence identity verification contract (B1; APPROVED; NOT IMPLEMENTED)**

Before the transaction that creates a new named-run Job is committed, R3 must do the following, in order:

1. Produce the validated named-run result normally (`run_named_replications`, section 4, R3).
2. Compute the authoritative **pre-persistence** values from that result:
   - the inputs fingerprint: `named_inputs_digest(provenance.inputs, provenance.closing_policy,
     provenance.employee_policy)`, which must equal `provenance.inputs_sha256`;
   - the compact replication rows (`replications`);
   - the required provenance: the version fields, `seed_scheme`, `root_entropy`, `replications`,
     `closing_policy`, and `employee_policy`, which `playback_from_named_replications` reads.
3. Insert and flush the Job.
4. Re-read the persisted JSONB representation through the normal PostgreSQL/ORM path **within the same
   transaction**.
   - The re-read must come from the database, not from the ORM identity map. For example, expire the
     `result_json` attribute before reading it, or select the column value directly.
   - Otherwise the check compares the in-memory object with itself. This is INFERRED from SQLAlchemy
     behavior and must be proven by the test below.
5. Recompute the fingerprint, and the deterministic stored-row identity, from the re-read representation.
6. Require **exact** agreement with the pre-persistence values:
   - the fingerprint must match;
   - every stored row must equal its pre-persistence row by type and value;
   - the required provenance fields must be equal.

**On any difference:**

- roll back the transaction, so no usable named run is persisted;
- return **HTTP 422** `{"detail": {"code": "persistence_identity_mismatch", "checks": [...]}}` (approved
  2026-10-01). This applies only to create-time failures in R3;
- never coerce, round, or "repair" the changed value;
- never accept the run with a warning.

**Run ID exposure:** no run ID, and no success response, is returned before the verification succeeds and
the transaction commits. The Job id assigned at flush (step 3) is never exposed on failure.

**Regeneration still fails closed on its own.** B1 does **not** replace the existing regeneration identity
checks. Later playback and attribution regeneration (R6, section 7) must still fail closed when:

- the regenerated fingerprint differs (`regeneration_identity`);
- the regenerated stored row differs (`stored_row`, and the OD-1 attribution row guard);
- required provenance differs (the version, seed-scheme, and closing-policy checks).

These mismatches on an **existing** run return **HTTP 409** with code `regeneration_identity` (approved
2026-10-01; section 7). They are distinct from the create-time **422** `persistence_identity_mismatch`.

**Coverage notes:**

- The only floating-point values in the recorded inputs (`named_inputs_snapshot`) are these four:
  - `employees[].pay.regular_rate_per_hour` and `employees[].pay.overtime_rate_per_hour` (request);
  - `demand_periods[].arrival_rate_per_hour` and `demand_periods[].service_rate_per_hour` (from the
    selected dataset).

  Every other recorded value is an integer, a string, a boolean, or `null` (VERIFIED from the snapshot
  fields). B1 covers these four fields through the fingerprint, and covers the stored rows through row
  identity.
- An integer came back unchanged through JSONB (`123456789012345678`, as a JSONB literal; VERIFIED).
- A JSONB round trip was VERIFIED on PostgreSQL only for the light-demand representative and
  maximum-structure payloads (section 6.4). Busy and stress payloads were NOT TESTED; the required test
  below covers them.

**B2** (a canonical storage form for digest-critical floats) is **NOT APPROVED**. It would change the
recorded snapshot shape that `rebuild_named_inputs` consumes.

**Required implementation test (later; not written now).** A real PostgreSQL integration test
(`NOVAQ_TEST_DATABASE_URL`) must prove that:

1. a normal persisted run survives write, re-read, and identity verification, and commits;
2. a representation-changing value (for example a recorded float that the database returns as an integer,
   as `1e16` did) causes a rollback;
3. no successful Job remains after the rollback (a row count check);
4. no run ID is exposed as successful: the response carries no Job id, and R4 does not list it;
5. the existing regeneration checks still operate independently: a stored run tampered after commit is
   still refused by R6 with the matching check.

The test must run on PostgreSQL, not SQLite, and a skip does not count as a pass.

**Demand** does not come from the form. It is read from the selected dataset through
`timeline_from_aggregate_rows`. Only its `DemandPeriod` list is used; its staffing segments are discarded
(A3). This is PROPOSED; see OD-2 for the dataset choice.

**Eligibility gates** (PROPOSED; enforced by the adapter before any domain call):

| Gate | Rule | Status on failure |
|---|---|---|
| Queue structure | `queue_setup.queue_structure == "shared_queue"` | 422 |
| Capacity | `capacity_mode == "unlimited"` (`finite` is VERIFIED incompatible; `unknown` per OD-3) | 422 |
| Abandonment | `abandonment_mode == "not_modeled"` (`modeled` is VERIFIED incompatible; `unknown` per OD-3) | 422 |
| Dataset | owned by the user, `analysis_id` equals this analysis, and `validation_report_json.ok` is truthy | 404 (missing or foreign) or 422 (not processed) |
| Model scope | `timeline_from_aggregate_rows(rows)` succeeds | `runnable: false` from validate; 422 from run |

`single_server`, `separate_queues`, and `unknown` structures are ineligible in this slice.
Separate Queue is untouched.

---

## 4. Named API routes (PROPOSED)

Router: `backend/api/shared_named.py`, `APIRouter(prefix="/analyses", tags=["shared-named"])`. Paths use
kebab-case, as `/workflow/observed-wait` and `/setup/workbook` do.

| # | Method and path | Purpose | Rate limit | Persists |
|---|---|---|---|---|
| R1 | `GET /analyses/{analysis_id}/shared-named/contract` | Eligibility of this analysis, closing policies, approved employee policy values with `POLICY_MEANINGS`, API limits, seed range, versions, `NO_VERDICT_REASON`, and the model-scope note | none | no |
| R2 | `POST /analyses/{analysis_id}/shared-named/validate` | Validate a `NamedWorkforceInput` against the dataset demand and the domain rules | compute | no |
| R3 | `POST /analyses/{analysis_id}/shared-named/runs` | Run named seeded replications and persist one Job | compute | yes (1 Job) |
| R4 | `GET /analyses/{analysis_id}/shared-named/runs` | List this analysis's named runs, newest first, in compact form | none | no |
| R5 | `GET /analyses/{analysis_id}/shared-named/runs/{run_id}` | The stored run: rows, summary, and provenance | none | no |
| R6 | `GET /analyses/{analysis_id}/shared-named/runs/{run_id}/replications/{replication_index}` | Regenerate replication i, validate it, and return the playback and attribution | compute | no |

No route touches `/simulation/*`, `/optimize/*`, or `/analyses/{id}/workflow/*`. The legacy workflow DES
response is not overloaded, and there is no cost route.

### R1 contract

Response:

```text
{ eligible: bool, ineligible_reasons: [str], closing_policies: [str],
  employee_policy: {<field>: {approved: str, meaning: str}}, limits: {...section 6...},
  seed: {min: 0, max: 9007199254740991}, versions: {...},
  verdict: null, verdict_reason: str, model_scope: str }
```

The approved values come from the imported constants, so the UI never hard-codes them.

### R2 validate

The adapter runs these steps in order. Nothing is persisted.

1. Parse the schema (422 on failure).
2. Check authorization and ownership (401/403/404).
3. Apply the eligibility gates (422 or 404).
4. Read the dataset rows and call `timeline_from_aggregate_rows`, keeping only the demand periods.
5. Numeric identity: R2 applies no numeric-domain rule. Persistence identity is verified at write time in R3
   (B1, section 3), because R2 persists nothing.
6. Build the dataclasses. This is field mapping only.
7. **Authoritative domain validation:** `validate_timeline(horizon, demand_periods, required_staffing)` and
   `evaluate_roster(horizon, employees, rules, roster, required_staffing=...)`. The latter also runs
   `validate_workforce_inputs`, and its report is returned unchanged.
8. **Additional structural check only (OD-4, approved):**
   - Call `simulate_named_prescribed(..., arrivals=[], closing_policy, employee_policy, required_staffing,
     max_trace_events=0)`. It runs the engine's own `_validate` (X7, timeline, policies) and the X4
     precondition with no customers and no random numbers, and its result is discarded.
   - It is never the sole validator: `runnable` is true only when step 7 raised nothing and this check also
     passed.

Any `SharedSegmentError` from steps 4, 7, or 8 gives `200` with `runnable: false` and the problems, tagged by
stage (`demand`, `workforce`, `engine`).

Response:

```text
{ runnable: bool, stage_failed: "demand" | "workforce" | "engine" | null, problems: [str],
  demand: { dataset_id, demand_periods: [...] } | null,
  roster_report: <evaluate_roster output, unchanged> | null, limits: {...} }
```

`roster_report` contains scheduled minutes and hours only, and no money (VERIFIED: the keys of
`evaluate_roster`).

### R3 run

1. Apply R2 steps 1-3. Then refuse an archived analysis (`archived_at` set) with **409**
   `{"code": "analysis_archived"}` (OD-7, approved), before any computation.
2. Pre-check the limits: `replications <= N_MAX`, `len(required_staffing) <= S_MAX`, `len(employees) <= E_MAX`,
   `len(roster) <= R_MAX`, and the list bounds. A failure gives **422 before any computation**, so it is
   deterministic.
3. Apply R2 steps 4-7. Any domain rejection gives 422 with `problems`, and nothing is persisted.
4. Call `run_named_replications(horizon, demand_periods, employees, rules, roster, replications=...,
   seed=..., closing_policy=..., employee_policy=EmployeeDesPolicy(**...), required_staffing=...)`.
   A `SharedSegmentError` gives 422 with `problems`.
5. Serialize with `json.dumps(result, allow_nan=False)`. A failure gives 500 with a structured detail,
   and nothing is persisted. If the length exceeds `settings.result_jsonb_max_bytes`, the response is
   **413** and nothing is persisted.
6. Persist the Job (section 5) under the **persistence identity verification contract** (B1, section 3):
   - compute the pre-persistence fingerprint, rows, and required provenance;
   - insert and flush the Job;
   - re-read `result_json` from the database inside the same transaction;
   - recompute, and require exact agreement.

   Commit only if every check agrees. On any difference: roll back, persist no usable run, return the
   **422** `persistence_identity_mismatch`, and expose no run ID.

Response `200` is `{"evidence": <job_out>}`, the same shape as the workflow `_job_out`: `id`, `kind`,
`status`, `params`, `result`, `created_at`, and `finished_at`. It is sent only after the verified commit.

### R4 list

Response:

```text
{ runs: [ { id, created_at, dataset_id, replications, seed, root_entropy, closing_policy,
            inputs_sha256, method_version, named_engine_version, runtime, setup_matches_current } ] }
```

- The source is Jobs where `user_id` is the user, `kind` is `shared_named_replications`, `status` is
  `completed`, and `params.analysis_id` is this analysis.
- `setup_matches_current` is `params.setup_hash == setup_fingerprint(analysis.queue_setup_json)`.

### R5 detail

Response: `{ "evidence": <job_out>, "setup_matches_current": bool }`. The stored `result` is returned
unchanged: no key is added, renamed, or recomputed.

### R6 selected replication

See section 7. Response:

```text
{ replication_index, playback: <playback_from_named_replications output, unchanged>,
  attribution: <build_named_attribution output, unchanged>,
  regeneration: { runtime_matches_recorded, runtime_recorded, runtime_current, basis } }
```

---

## 5. Job kind and persisted schema (PROPOSED)

- **Kind**: `shared_named_replications` (`String(64)` fits).
  - It follows the snake_case family convention and mirrors the producing method.
  - It deliberately does **not** use the `workflow_` prefix. It is not in `WORKFLOW_KINDS`, not in
    `_current_evidence`, and does not feed the Decision chain.
  - The adapter writes the row itself (it does not call `workflow._save_job`), so the legacy
    `ENGINE_VERSION` is never stamped on named evidence and `workflow.py` is not edited.
- **Row**: `user_id`, `kind`, `status="completed"`, `tenant_id=user.tenant_id`, and `finished_at=now`.
- **`params_json`**. The key order below is the write order, and server keys are written after the request
  keys so a request value cannot replace them. This mirrors the G-A convention (`fix/d1` `workflow.py:610-613`).

  ```text
  { "analysis_id", "scenario_id": null, "dataset_id",
    "replications", "seed", "closing_policy",                       # request values
    "named_api_version": "novaq-shared-named-api-v1",
    "engine_version": <provenance.method_version>,                  # the method that produced result_json
    "method_version", "named_engine_version", "state_machine_version", "arrival_engine_version",
    "inputs_sha256", "root_entropy",                                # copied from result provenance
    "dataset_generation": <Dataset.generation of dataset_id>,       # OD-2 (approved); requires G-A
    "setup_hash": setup_fingerprint(analysis.queue_setup_json) }
  ```

- **Dataset identity (OD-2, approved).**
  - The run records the explicitly selected `dataset_id` and that row's `generation` token.
  - `Dataset.generation` exists only on the G-A line (`92d95bed`, migration `0005`; VERIFIED) and not on
    `feat/shared-queue-segments`. **This field cannot be implemented until G-A is integrated.**
  - The token is recorded as provenance. It is never recomputed or inferred, and it is not `null` when the
    column exists.
  - `result_json` itself is not modified: it stays the unchanged `run_named_replications` output.

- **`result_json`**: exactly the `run_named_replications` return value, `{replications, summary,
  provenance}`, unmodified.
  - It already contains the complete input snapshot (`provenance.inputs`: horizon, demand periods,
    required staffing, employees with pay, rules, and roster).
  - It also contains `closing_policy`, `employee_policy`, `seed`, `root_entropy`, `seed_scheme`, `runtime`,
    every version, and `inputs_sha256`.
  - The rows are compact (one scalar row per replication), the aggregate is the approved descriptive
    summary with `verdict: null`, and there are no events, customer rows, or timelines.
  - This is exactly what `playback_from_named_replications` consumes (VERIFIED, section 7).
- **Immutability**: no route updates or deletes a named Job. A rerun creates a new Job.
- **Not stored**: playback traces, attribution, and any cost.

---

## 6. Replication cap (provisional, NOT PRODUCTION-APPROVED)

### 6.1 Evidence from the first probe (superseded for the limits by section 6.4)

The evidence comes from scratch probes run on 2026-09-30, before Stage 0. The Stage 0 grid in section 6.4
supersedes these limits.

- Runtime: Python 3.13.13, numpy 2.4.6, Windows 11 (this machine), other load unknown.
- Demand: the committed `NOVAMART_AVERAGE_ROWS` (`tests/test_shared_segments.py:28`), 05:00-18:00, with
  about 108 arrivals per replication.
- Workforce: **synthetic**. Employees `E..`, availability 05:00-18:00, one 30-minute unpaid meal on 6-9 h
  shifts, 8 registers per 8 employees, and synthetic hourly required staffing
  `[2,3,3,3,3,4,3,4,4,3,3,2,2]`, split for S = 26 and S = 52.
- Byte counts are `len(json.dumps(result, allow_nan=False).encode())`, as `_save_job` measures them.
  The limit is 524,288 B.

| S (segments) | E = R | n | Total bytes | % of 512 KiB | Largest row | Summary | Provenance | Run time |
|---|---|---|---|---|---|---|---|---|
| 13 | 8 | 10 | 137,628 | 26.3 | 8,177 | 45,707 | 12,262 | 0.60 s |
| 13 | 8 | 20 | 217,513 | 41.5 | 8,177 | 45,873 | 12,262 | 1.14 s |
| 13 | 24 | 20 | 222,100 | 42.4 | 8,092 | 45,508 | 17,279 | 2.74 s |
| 13 | 8 | 100 | 853,019 | 162.7 | 8,164 | 46,438 | 12,218 | 4.86 s |
| 26 | 8 | 20 | 355,783 | 67.9 | 13,685 | 74,507 | 13,278 | 1.70 s |
| 26 | 24 | 20 | 360,356 | 68.7 | 13,557 | 74,467 | 18,295 | 2.52 s |
| 52 | 8 | 10 | 389,533 | 74.3 | 24,549 | 131,566 | 15,312 | 0.84 s |
| 52 | 24 | 10 | 393,381 | 75.0 | 24,362 | 130,729 | 20,329 | 1.30 s |
| 52 | 8 | 20 | 633,026 | 120.7 | 24,549 | 132,327 | 15,312 | 1.26 s |
| 52 | 8 | 100 | 2,575,666 | 491.3 | 24,549 | 134,809 | 15,281 | 5.99 s |

Findings (VERIFIED in this runtime, on these inputs only):

- **Size is the binding limit, not time.**
  - 100 replications do not fit even at 13 segments, the minimum for 13 hourly demand periods.
  - Row and summary size grow with the number of required-staffing segments, because each segment adds a
    staffing window to every row and to the summary.
  - Employees add only to the provenance, by about 5 KB per 16 employee-plus-shift pairs.
- Per-replication time was 0.05-0.12 s at about 108 arrivals.
- **Playback** of one replication (not persisted):
  - 476,634-492,953 B and 599 events, generated in 0.10-0.24 s;
  - `valid: true` and `runtime_matches_recorded: true` after a `json.dumps`/`json.loads` round trip of
    the stored run.
- **Attribution** of one replication: 31,417-31,423 B in 0.05-0.16 s. Regenerating through the D6 path
  gave a row equal to the stored row.
- **Validation evidence**:
  - A synthetic roster with more employees on duty than its 4 registers was rejected as INVALID under X4,
    with 10 register-excess violations.
  - A single 05:00-18:00 required-staffing segment was rejected ("crosses a demand-period boundary").

### 6.2 Provisional API limits (NOT PRODUCTION-APPROVED)

Corrected after Stage 0 (2026-09-30). The earlier `N_MAX = 10` is **withdrawn**. At 52 segments, 24
employees, and 48 shifts with busy demand, 10 replications reached 428,601 B (81.7 % of 524,288 B, above
the 80 % ceiling of OD-9; section 6.4).

| Constant (in `shared_named.py`) | Provisional value | Basis |
|---|---|---|
| `N_MAX` (replications) | **9** | Worst measured case: 401,652 B = 76.6 % of the **local** 524,288 B, at the envelope below with demand x10 (5 seeds x 2 policies). |
| `S_MAX` (required-staffing segments) | **52** | Largest measured |
| `E_MAX` (employees) | **24** | Largest measured |
| `R_MAX` (roster shifts) | **48** | Largest measured (split shifts, 2 per employee) |
| `AV_MAX` (availability windows per employee) | 3 | Largest measured (heavy variant) |
| `BR_MAX` (break rules) | 3 | Largest measured |
| `BQ_MAX` (breaks per rule) | 2 | Largest measured |
| `BS_MAX` (breaks per shift) | 2 | Largest measured |

- **These values are NOT final and NOT PRODUCTION-APPROVED.**
  - They satisfy the OD-9 ceiling only against the local configured cap of 524,288 B (the code default in
    `settings.py:174`). The production `RESULT_JSONB_MAX_BYTES` on Render is UNKNOWN.
  - They become final only when the production cap is VERIFIED and the worst measured size is at or below
    80 % of it, and when the production request and response limits are VERIFIED to leave headroom
    (sections 6.3 and 19).
- No limit is raised because a smaller probe passed. Every value above is the largest combination
  actually measured together.
- A tiered cap, for example more replications at 26 segments or fewer, is not proposed. At 26 segments
  and 20 replications only the light-demand case was measured (378,535 B = 72.2 %). The busy-demand
  equivalent was not measured.

- Demand periods are bounded by `S_MAX` without a separate limit. Both lists tile the horizon, and each
  segment lies inside one period, so the number of periods is at most the number of segments. This is
  INFERRED from the verified rules in `validate_timeline`.
- The engine maximum of 100,000 is never exposed.
- The size check against the runtime setting (413) remains as a backstop, so an input set that was not
  measured can never persist oversized evidence.

### 6.3 Measurement gate status (after Stage 0, 2026-09-30)

The acceptance rule is OD-9 (approved). A persisted run must stay at or below **80 % of the VERIFIED
production result-size cap**, and runtime limits must derive from VERIFIED platform timeouts.

| Gate | Status |
|---|---|
| **M1 Size** | Measured locally (section 6.4). It meets 80 % of the **local** cap at `N_MAX = 9`. Against production: **BLOCKED**, because the production cap is UNKNOWN. |
| **M2 Time** | Measured locally only (section 6.4). Production runtime is **UNKNOWN**: no production-like hardware was measured, and no production request timeout is VERIFIED. |
| **M3 PostgreSQL JSONB** | Done on disposable PostgreSQL **16.15** for two payloads and a few edge values (section 6.4). The `1e16` identity failure led to the approved B1 persistence identity check (section 3; NOT IMPLEMENTED). The complete safe domain remains UNKNOWN. Production PostgreSQL version: **UNKNOWN**. |
| **M4 Playback response** | Measured: up to **4,163,473 B** (about 4.16 MB) uncompressed (section 6.4). Compatibility with the Cloudflare Pages bridge and Render is **UNKNOWN**. |
| **M5 Production cap** | **UNKNOWN.** There is no Render configuration in the repository, and no account access was available (section 19). |

### 6.4 Stage 0 results (2026-09-30; local measurement evidence only)

**Measurement setup:**

- Machine: Intel Core i3-8145U, 4 logical CPUs, 7.8 GiB RAM, with memory load at 88-93 % before the runs.
- Software: Windows 11 (10.0.26300), Python 3.13.13, numpy 2.4.6.
- Demand: the committed `NOVAMART_AVERAGE_ROWS`, 05:00-18:00. Busy days are those λ values x5 or x10
  (SYNTHETIC).
- Workforce: SYNTHETIC.
  - Employees are single-shift or split (two 4 h shifts).
  - "Heavy" means 3 availability windows, 3 break rules, and up to 2 breaks per shift (a 15-minute paid
    rest and a 30-minute unpaid meal).
  - Registers equal the employee count.
  - Required staffing is SYNTHETIC, hourly, split to reach 26 or 52 segments.
- Bytes are measured exactly as `_save_job` measures them.
- The scripts are in the session scratchpad (`stage0/`) and are not committed.

**Persisted run size** (worst of the seeds shown; the local cap is 524,288 B, so 80 % is 419,430 B):

| Replications | Segments | Employees | Shifts | Demand | Seeds x policies | Bytes | % of local cap |
|---|---|---|---|---|---|---|---|
| 20 | 13 | 24 | 48 heavy | x1 | 1 x 1 | 237,312 | 45.3 |
| 20 | 26 | 24 | 48 heavy | x1 | 1 x 1 | 378,535 | 72.2 |
| 10 | 26 | 24 | 48 heavy | x10 | 5 x 2 | 248,899 | 47.5 |
| 10 | 52 | 24 | 24 | x1 | 3 x 1 | 394,456 | 75.2 |
| 10 | 52 | 24 | 48 heavy | x1 | 5 x 2 | 412,906 | 78.8 |
| 8 | 52 | 24 | 48 heavy | x10 | 5 x 2 | 375,349 | 71.6 |
| **9** | **52** | **24** | **48 heavy** | **x10** | **5 x 2** | **401,652** | **76.6** |
| 10 | 52 | 24 | 48 heavy | x5 | 5 x 2 | 425,312 | **81.1 (over)** |
| 10 | 52 | 24 | 48 heavy | x10 | 5 x 2 | 428,601 | **81.7 (over)** |
| 15 | 52 | 24 | 48 heavy | x1 | 3 x 1 | 539,001 | 102.8 |

- Size is driven by the number of segments.
- Employees, shifts, and breaks add 5-10 KB through the recorded inputs.
- Busy demand adds about 3 %.
- The full grid (3 segment counts x 6 workforce shapes x 5 replication counts) produced 106 local
  measurements.

**PostgreSQL JSONB round trip.** Run on the repository's disposable `docker-compose.integration.yml` `db`
service (PostgreSQL 16.15), in a fresh schema created and dropped as `tests/conftest.py` does, with
`jobs.result_json` of type `jsonb`.

- Two payloads were written as `Job` rows, read back through a new engine and session, and decoded:
  - representative: 13 segments, 8 employees, 8 shifts, 10 replications, DRAIN;
  - maximum structure: 52 segments, 24 employees, 48 shifts, 10 replications, HARD_CUTOFF.
- For both, the input digest matched, `playback_from_named_replications` was valid for replications 0 and 9,
  the D6 regenerated row equalled the stored row, and attribution built.
- The only changes were tuples becoming lists, which the digest treats identically.
- A pay value of `1e16` came back as an integer, the digest no longer matched, and regeneration refused
  with `regeneration_identity` (fail-closed). Pay values `1e15`, `1e-07`, `100.0`, `0.0`, `99.5`, and
  `123.456` were unchanged.
- JSONB literals checked directly: `1e+16` -> `10000000000000000`, `1e-07` -> `0.0000001`, `100.0` ->
  `100.0`, `123456789012345678` -> unchanged.

**Run time of R3** (10 replications, 3 repeats; **local only, not production timing**):

| Case | Arrivals per day (mean) | Median run time | Max run time |
|---|---|---|---|
| Light: 13 segments, 8 employees, 8 shifts | 108 | 0.57-0.59 s | 0.68 s |
| 52 segments, 24 employees, 24 shifts | 108 | 1.73-5.09 s | 6.90 s |
| 52 segments, 24 employees, 48 shifts (split) | 108 | 1.16-2.48 s | 3.11 s |
| Busy x5: 52 segments, 24 employees, 24 or 48 shifts | 552 | 1.64-2.92 s | 7.78 s |
| Stress x10, overloaded: 52 segments, 24 employees, 24 shifts | 1,093 | 3.42-4.04 s | 4.05 s |

- Repeat-to-repeat variation reached 3x on this loaded machine.
- R6 (playback, then the D6 regeneration, then attribution, for one replication) took 0.11-1.08 s.

**R6 response size** (uncompressed; Starlette compact JSON; not persisted):

| Case | Events | Response bytes | gzip level 6 |
|---|---|---|---|
| Light | 599 | 470,120-471,154 | about 33 KB |
| Maximum structure | 695 | 593,246-607,961 | about 41 KB |
| Busy x5 | 2,922-2,995 | 2,168,661-2,221,380 | about 136 KB |
| **Stress x10** | **5,990** | **4,163,473 (about 4.16 MB)** | 232,098 |

- Every regeneration was valid, and `runtime_matches_recorded` was true in this runtime.
- Whether the Cloudflare Pages bridge or Render compresses, accepts, or times out on a 4+ MB response is
  **UNKNOWN**.

**Dataset eligibility**, confirmed by running the committed ingestion (`normalize_analysis_input`) and the
unchanged `timeline_from_aggregate_rows`:

- **Accepted:** aggregate `HH:MM-HH:MM` rows without variance, `K`, or `theta`. The rates were unchanged.
- **Rejected, with every row listed:**
  - variance rows;
  - rows under finite capacity (`K` added by ingestion) or modeled abandonment (`theta` added by
    ingestion);
  - a mix with one variance row (the whole call was rejected);
  - labels such as `5:00 AM`;
  - event-derived shared rows (date-prefixed labels, with variance present).
- The Setup schema also rejects a shared-queue `representative_day` basis.
- No silent reduction to M/M/c occurred.

---

## 7. Regeneration and playback contract (PROPOSED)

R6 runs these steps in order. Each step either succeeds or ends the request, and nothing is persisted.

1. Authorize the analysis (404). Load the Job by `id` with `user_id`, `kind`, `status == "completed"`, and
   `params.analysis_id` all matching; otherwise 404.
2. Range check: `0 <= replication_index < result.provenance.replications`, otherwise **404** "Replication
   not found." This bound check is input validation, not regeneration logic.
3. Call **`playback_from_named_replications(job.result_json, replication_index)`**. This is the unchanged,
   protected regeneration and refusal contract: versions, seed scheme, digest, rebuilt-input digest,
   closing policy, exact stored-row equality, and the full independent replay with all playback v4 checks.
   - `NamedPlaybackError` with `regeneration_identity`, `closing_policy`, or `stored_row` gives **409**
     `{code: "regeneration_identity", check, message, evidence}` (approved 2026-10-01). `check` keeps the
     specific domain check that failed.
   - Any other playback check gives **500** `{code: "playback_check_failed", check, message, evidence}`
     and is logged. That would be an engine or replay defect, never a user error.
   - No partial playback, fallback trace, or synthesized event is ever returned.
4. For attribution, regenerate the engine result through the approved D6 path:
   - `inputs = rebuild_named_inputs(provenance.inputs)`;
   - `result = simulate_named_replication(..., seed_sequence=replication_seed_sequence(root_entropy, i),
     closing_policy, employee_policy=EmployeeDesPolicy(**provenance.employee_policy),
     required_staffing, max_trace_events=0)`, the same arguments the run used for its rows
     (`run_named_replications`).
   - **Guard (OD-1):** require `named_replication_row(result, i) == stored_row`. If they differ, return
     **409** `{code: "regeneration_identity", check: "attribution_stored_row", fields}` (approved 2026-10-01).
5. `build_named_attribution(result, inputs["employees"])`. A `NamedAttributionError` gives **500**
   `{code: "attribution_check_failed", check, message, evidence}`.
6. Return section 4's R6 body.
   - `regeneration.runtime_matches_recorded` is copied from the playback provenance.
   - The UI shows it verbatim. When it is false, the UI also shows the domain `regeneration_basis` text, and
     no cross-version claim is made.

**NumPy (CONFLICTING, recorded, not fixed).** `requirements.txt` says `numpy>=1.24.0,<2.3`, the lock pins
2.4.6, and the production lock pins 2.2.6. Cross-version stream equality is UNKNOWN.

- A run created under one NumPy and regenerated under another either reproduces its stored row exactly,
  or R6 refuses with 409 `stored_row`. This fails safe.
- Runs can become unplayable after a dependency change. The UI must say so.
- The pins are not changed in this slice.

**Attribution independence of `max_trace_events`** is INFERRED:

- attribution reads only `employee_timeline`, `closing_policy`, and `provenance`
  (`shared_named_attribution.py:288-317`);
- the cap truncates only the customer `trace` (`shared_named_des.py:343`);
- step 4 uses the run's own argument (`0`) regardless.

---

## 8. Attribution API contract (PROPOSED)

- It is delivered only inside R6, for one selected replication. There is no standalone attribution route in
  this slice, which keeps to one playback validation plus one D6 regeneration per request.
- The payload is the unchanged `build_named_attribution` output (attribution spec section 4):
  - `shifts[]`: employee × shift × run;
  - `employees[]`: sums over activated shifts;
  - `reconciliation`, `definitions`, `checks`, `undetermined`, and `provenance`.
- Units are hours, per D1. `provenance.inputs_sha256` is `null`, with its reason, per D4. There is no `paid`
  field (D5) and no money (`monetary_cost` note).
- There is no aggregation across replications (D6) and no verdict.

---

## 9. Simulate-page UX (PROPOSED)

### 9.1 Mode

- The mode is a URL search parameter, `?mode=named`, on the existing `/analyses/:analysisId/simulate` route.
  `router.tsx` is unchanged.
- `SimulationModeSwitch` appears **only** when `queue_structure === "shared_queue"`. It offers two options:
  "Legacy shared queue simulation" (the current behavior) and "Named Shared Queue simulation".
- With no `mode` parameter, the page renders exactly as it does today (A4). Existing `SimulationPage` tests
  must pass unchanged.
- `mode=named` renders `NamedSharedQueueSimulation`:
  - before the "select a scenario first" early return (`SimulationPage.tsx:724`);
  - independent of Compare selection and of the legacy workflow evidence.
  The switch also appears on that early-return screen, so a shared analysis without a scenario can
  still reach named mode.
- Separate Queue, `single_server`, and `unknown` structures show no switch. `mode=named` on them renders the
  legacy page unchanged. The named view is never shown for them.
- The page header names the active mode, and the named view has a persistent banner:
  - employees are pseudonymous ids;
  - M/M/c aggregate demand only (the model-scope note from R1);
  - no verdict (`verdict_reason` from R1);
  - workforce cost is not shown in this version.

### 9.2 Named view layout (`NamedSharedQueueSimulation`)

1. **Eligibility.** The view loads R1. When the analysis is ineligible, it lists `ineligible_reasons` and
   shows no form.
2. **Demand source.**
   - A required dataset selector (OD-2) lists the analysis datasets whose `validation.ok` is true, from the
     existing `GET /analyses/{id}/datasets`.
   - After validation, the read-only `demand_periods` (period, λ/h, μ/h) are shown.
3. **Operating horizon.** Opening and closing time inputs (HH:MM, converted to minutes). There is no prefill.
   Validation reports a mismatch with the demand span.
4. **Required staffing (X7).**
   - An editable table of segment id, start, end, and servers. It starts empty, with an "Add segment"
     control.
   - There is no copy-from-dataset `c`, copy-from-roster, or optimizer button (A3).
   - Help text: it is the requirement the run is measured against (staffing windows and gaps), and it does
     not change customers (VERIFIED: `COMMON_RANDOM_NUMBERS`, `METRIC_DEFINITIONS.staffing`).
5. **Registers**: `register_count`.
6. **Shift rules**: every `ShiftRules` field. `min_minutes_between_shifts` is enabled only when
   `max_shifts_per_employee > 1` and is sent as `null` otherwise, matching the domain rule.
7. **Break rules**: a table of rules, each with nested break requirements (name, minutes, paid
   yes/no, start-offset window).
8. **Employees**:
   - an "Employee ID (pseudonymous)" column, with hint text telling the user not to enter names;
   - availability windows;
   - three pay fields, each with an explicit "not supplied" state sent as `null`, never 0.
   There is no name field.
9. **Roster**: an employee selector, shift start and end, and placed breaks (name and start).
10. **Closing policy**: a radio for `DRAIN` or `HARD_CUTOFF`, with **none preselected**, and each meaning
    shown.
11. **Employee policy**: a read-only panel listing R1's six approved selections and meanings. They are sent
    with each request, not editable, and hidden from no one.
12. **Validate** (R2) shows:
    - `runnable`, and the problems grouped by stage;
    - the roster report: status, violation codes and messages, missing fields, scheduled minutes, register
      check, and coverage shortfall and surplus.
13. **Run control**:
    - `replications` is a number input with no default and is bounded by `limits.max_replications`, shown
      as text;
    - `seed` is a required integer with no default and is bounded by R1's seed range;
    - **Run** is enabled only when the last R2 response was `runnable: true` for exactly the current form
      content (same form fingerprint) and both fields are valid.
14. **Runs list** (R4): the newest first, with created time, replications, seed, closing policy, dataset,
    and a `setup_matches_current` badge. A run recorded under an earlier Setup is labelled so, and never
    presented as current.
    - Selecting a run loads R5.
    - PROPOSED: the form may be prefilled from a selected run's `provenance.inputs` only by an explicit
      "Load inputs from this run" action (OD-6).
15. **Run evidence** (R5):
    - Provenance and status: versions, runtime, seed, `root_entropy`, `inputs_sha256` (shortened with a
      copy action), and `verdict: none` with `verdict_reason`.
    - **Replication table**, one row per replication:
      - index, arrivals, served, unserved (hard cutoff / no eligible employee), and served after closing;
      - mean wait **in minutes**, max queue, waiting customer-hours, waiting at close, and DRAIN crew size;
      - run after closing (min), shifts with overrun, breaks unfulfilled, and conservation.
      - `null` renders as "—", never 0.
    - **Aggregate panel** (descriptive only):
      - replications;
      - customer totals;
      - mean of replication means, with its Student-t interval, `n` and `n_undefined`;
      - customer-weighted mean wait, with numerator and denominator;
      - `outcome_counts`, labelled "descriptive frequencies, not failure rates".
      There is no PASS/FAIL, badge colour for acceptability, expected cost, ROI, or verdict.
16. **Selected replication.**
    - Choosing a row sets `selectedReplication = i` and calls R6, with a loading state because it
      regenerates.
    - On 200 it renders `NamedSharedQueuePlayback` and `NamedAttributionTables`, plus the regeneration
      status. When `runtime_matches_recorded` is false, the basis text is shown.
    - On 409 it shows the refusal code, check, and message, and **no** playback or attribution.

**Display units.** API values stay in hours. Wait times display in minutes (× 60 at display, as the page
already does). Employee durations display in hours. Numbers use the existing `fmt` / `fmtDecimal`
helpers (the up-to-4-dp rule).

Not changed: Compare, Decision, Reports, `WorkflowNavigator` completion (a named run does not mark
Simulate complete), `LiveSimulationPlayback`, `SeparateSimulationPlayback`, and `StoreFloorView`.

---

## 10. Named playback UI data contract (PROPOSED)

`NamedSharedQueuePlayback` consumes R6's `playback` object as `playback_from_named_replications` produces
it (`shared_named_playback.py:1080-1160`). It does **not** reuse the `SimulationTrace` contract.

| Field | Shape (VERIFIED from source) | Use |
|---|---|---|
| `events[]` | `seq, source ("customer_trace" or "employee_transition"), source_index, t, period, type, stage, customer_id, employee_id, register_id, employee_state_before, employee_state_after, register_before, register_after, queue_len_before, queue_len_after, accepting_capacity_after, busy_employees_after, register_occupancy_after, waiting_for_register_after, unserved_reason, closing_policy, drain_crew, break` | Step-by-step event log and the state at each step |
| `instants[]` | `t, period, queue_len, accepting_capacity, busy_employees, register_occupancy, waiting_for_register` | Scrubber positions and series charts |
| `customers[]` | `customer_id, arrival_hours, service_start_hours, service_end_hours, employee_id, register_id, status` | Customer table and hover |
| `employees` | `{employee_id: [{start, end, state, register_id}]}` | Employee lanes: state and register over time |
| `shifts`, `breaks` | rebuilt records; breaks carry `name, shift_index, scheduled_start, due, delay` | Shift and break markers |
| `not_represented_by_events` | `unfulfilled_breaks[]`, `shifts_not_activated[]` | A separate list, clearly marked "no event exists" |
| `closing` | `policy, closing_hours`, plus the at-close state | Closing marker and closing-phase shading |
| `outside_horizon`, `summary`, `validation`, `reconciliation`, `event_vocabulary`, `unsupported`, `provenance` | as produced | Validation badge, the vocabulary legend (meanings shown), unsupported notes, provenance panel |

`period` values are `before_opening`, `operating_horizon`, `closing`, and `after_closing`. Times are hours
from the horizon start and can be negative before opening. The UI displays clock time as
`horizon.start_minute + t × 60`.

Rendering rules:

- Discrete stepping over `events` in `seq` order; play advances event by event at a chosen speed.
- No interpolation, no synthesized events, and no reordering.
- Before opening, operating, and after closing are visually distinct.
- Event types and transition meanings come from `event_vocabulary`, not hard-coded text.

TypeScript types live in a new `frontend/src/api/sharedNamed.ts`. Fields the components read are typed
exactly. Pass-through blocks are `Record<string, unknown>`.

---

## 11. Validation and error contract (PROPOSED)

| Condition | Status | Body |
|---|---|---|
| Not authenticated | 401 | existing `{"detail": "Not authenticated."}` |
| CSRF header missing or mismatched (POST with session cookie) | 403 | existing `{"detail": "CSRF token mismatch."}` |
| Analysis missing or not owned | 404 | existing `{"detail": "Analysis not found."}` |
| Dataset missing, foreign, or of another analysis | 404 | `{"detail": {"code": "dataset_not_found"}}` |
| Run missing, foreign, of another analysis, or of another kind | 404 | `{"detail": {"code": "run_not_found"}}` |
| Replication index out of range | 404 | `{"detail": {"code": "replication_not_found", "max_index"}}` |
| Schema failure (missing key, NaN or ±Infinity, float in an int field, bool, extra key, list too long) | 422 | FastAPI validation list |
| Over `N_MAX`, `S_MAX`, `E_MAX`, `R_MAX`, or a list bound (checked before computing) | 422 | `{"detail": {"code": "limit_exceeded", "limit", "value", "max"}}` |
| Ineligible Setup | 422 | `{"detail": {"code": "ineligible_setup", "reasons": [...]}}` |
| Archived analysis on R3 (OD-7) | 409 | `{"detail": {"code": "analysis_archived"}}`, with nothing computed or persisted |
| Persistence identity mismatch at create time in R3 (B1; section 3) | **422** | `{"detail": {"code": "persistence_identity_mismatch", "checks": [...]}}`, rolled back, with no usable run persisted and no run ID exposed |
| Dataset not processed OK | 422 | `{"detail": {"code": "dataset_not_processed"}}` |
| Domain rejection in R3 (demand, workforce, X4, X7, or policy) | 422 | `{"detail": {"code": "named_input_invalid", "stage", "problems": [...]}}` |
| Domain rejection in R2 | 200 | `{"runnable": false, "stage_failed", "problems"}` |
| Persisted size over `result_jsonb_max_bytes` | 413 | `{"detail": {"code": "evidence_too_large", "bytes", "max_bytes"}}`, with nothing persisted |
| Result not JSON-serializable (NaN or inf) | 500 | `{"detail": {"code": "result_not_serializable"}}`, with nothing persisted |
| Regeneration mismatch on an existing run in R6: playback (`regeneration_identity`, `closing_policy`, `stored_row`) or the attribution row guard | **409** | `{"detail": {"code": "regeneration_identity", "check", "message", "evidence"}}` |
| Other playback or attribution check failure | 500 | `{"detail": {"code", "check", "message", "evidence"}}`, logged |
| Rate limited | 429 | existing |

- NaN and ±Infinity: Python's JSON parser accepts the `NaN` and `Infinity` tokens, so the rejection must
  come from `allow_inf_nan=False` on **every** nested model. It must not rely on downstream playback checks,
  which accept some non-finite values (open item in playback v4).
- No 4xx or 5xx response ever creates a Job.

---

## 12. Authentication, ownership, and CSRF (PROPOSED)

- Every route depends on `get_current_user`. An unauthenticated request gets **401**.
- Every route calls `own_analysis(db, user, analysis_id)` first. A non-owner gets **404**, never 403, as
  the repository already does.
- Every lookup filters by `user_id == user.id` and by `params.analysis_id`. Datasets are filtered by
  `user_id` and `analysis_id`.
- R2 and R3 are POSTs under `/analyses`, so the CSRF middleware applies; a missing or mismatched header gets
  **403**. `EXEMPT_FAMILIES` is **not** changed, and `tests/test_production_hardening.py` stays green
  unchanged.
- R1, R4, R5, and R6 are GETs and read-only. R6 regenerates in memory and writes nothing.
- R2, R3, and R6 use `user_rate_limit("compute")`.
- Archived analyses (OD-7, approved): an archived analysis **cannot create a new named run**.
  - R3 returns **409** `analysis_archived` before any computation. This matches the existing refusal for
    uploads (`analyses.py:189`, `:300`) and scenario creation (`scenarios.py:280`).
  - The read-only routes R1, R2, R4, R5, and R6 stay available, so earlier runs remain viewable and
    replayable.

---

## 13. Persistence and generation-identity interaction

- **No schema change and no migration.** The Job table and JSON columns are reused (A5). This slice adds no
  `0005` and cannot collide with `0005_generation_identity.py`.
- **No Setup change.** Named inputs live only in Job snapshots. `QueueSetup` (`extra="forbid"`) and
  `analysis_schemas.py:153`, which rejects shared-queue break schedules, are unchanged.
- **G-A is a prerequisite** (OD-2, approved, 2026-09-30).
  - The run must record the selected dataset's `generation` (section 5). `Dataset.generation` exists
    only on the G-A line (VERIFIED: `92d95bed` `backend/db/models.py`, migration `0005`).
  - The named implementation therefore starts only on a base that already contains G-A.
- **No G-A classification of named Jobs** (INFERRED from the committed G-A code):
  - G-A stamps `dataset_generation` and `scenario_generation` into workflow Jobs through `_save_job`, and
    classifies Jobs per known kind.
  - Every Job query on both lines filters by kind, so a `shared_named_replications` Job is neither read nor
    classified by G-A.
  - Named evidence never feeds Decision, and the G-A enforcement flag stays off.
- **Currentness shown, not enforced.** `setup_matches_current` is displayed. Regeneration does not depend on
  the Setup or the dataset still existing, because the snapshot is self-contained (VERIFIED:
  `rebuild_named_inputs` uses only `provenance.inputs`).
- **Sequencing** (re-verified 2026-09-30; OD-8, approved):
  - The G-A tip is `port/g-a-stage1` **`00582c11`**. It is unpushed, and no later G-A commit exists
    (re-verified 23:56 +0800).
  - At that check the port worktree held **uncommitted** D7 frontend work by the owning session, modified
    23:47-23:52: `SimulationPage.tsx` (+23/-1), `SimulationPage.test.tsx` (+110), and one key each in the
    `en` and `tl` locales. The G-A frontend stage is in progress, not done.
  - `92d95bed` contains the port's `main.py` change: the G7 migration-head lifespan guard.
  - `feat/shared-queue-segments` and `00582c11` change **no file in common** relative to `2d063c91`.
    A read-only trivial three-way merge check (`git merge-tree 2d063c91 HEAD 00582c11`) showed 0 conflicts.
  - G-A is **not complete**:
    - Its frontend stage (the D7 "no current run for dataset" state in `SimulationPage.tsx`, plus EN/TL keys
      and a test) is not ported. `00582c11` changes no file under `frontend/`.
    - The locale portion is REPORTED BLOCKED on the unresolved `nervous-hodgkin` leftovers.
    - The CI and docs scope is REPORTED UNDECIDED.
    - The G-A contract records open CONFLICTING items (`2026-09-26-generation-identity-contract.md` lines
      84, 1039, 1247 on `fix/d1`).
  - This slice's frontend edits `SimulationPage.tsx` and the locales, the same files as the unported D7
    frontend. The named frontend (Stage 2) should therefore follow the G-A frontend stage.
  - The named backend (Stage 1) needs only the G-A backend. The integration boundary for it is
    `00582c11`. Whether to integrate that incomplete G-A line now, or to wait for G-A completion, is an
    owner decision (section 20).

---

## 14. File scope (PROPOSED)

**Backend**

| File | Change |
|---|---|
| `backend/api/shared_named.py` | **New.** Router, request models, limit constants, eligibility gates, dataclass mapping, domain calls, Job write and read, error mapping. |
| `backend/api/main.py` | Import and `app.include_router(shared_named_router)`, about 2 lines. |
| `tests/test_shared_segments.py` | Isolation guard, narrow: exempt exactly the path `backend/api/shared_named.py` through a named constant. All other files stay forbidden. |
| `tests/test_api_shared_named.py` | **New.** Section 15. |

The adapter may import only these, and a test pins the list:

- `shared_segments`: dataclasses, `SharedSegmentError`, `timeline_from_aggregate_rows`;
- `shared_workforce`: dataclasses, `evaluate_roster`;
- `shared_continuous_des`: `CLOSING_POLICIES`;
- `shared_named_des`: `EmployeeDesPolicy`, `APPROVED_EMPLOYEE_POLICY`, `POLICY_MEANINGS`,
  `simulate_named_prescribed`, and versions;
- `shared_named_replications`: `run_named_replications`, `simulate_named_replication`,
  `replication_seed_sequence`, `named_replication_row`, `NO_VERDICT_REASON`, and versions;
- `shared_named_playback`: `playback_from_named_replications`, `rebuild_named_inputs`,
  `NamedPlaybackError`;
- `shared_named_attribution`: `build_named_attribution`, `NamedAttributionError`.

It must **not** import `shared_named_cost`, `shared_day_cost`, `shared_rostering`, `shared_integrated`,
`shared_capacity`, `shared_replications`, or `shared_playback` (the anonymous engine's).

Unchanged: every `backend/queueing_engine/**` file, `workflow.py`, `simulation.py`, `optimization.py`,
`analysis_schemas.py`, `scenarios.py`, `reports.py`, `models.py`, `migrations/`, `settings.py`,
`config.py`, and `requirements*`.

**Frontend**

| File | Change |
|---|---|
| `frontend/src/api/sharedNamed.ts` | **New.** Types and client for R1-R6. `types.ts` and `workflow.ts` are not edited. |
| `frontend/src/lib/namedWorkforce.ts` | **New.** Pure form-to-request mapping (HH:MM and minutes, nulls kept), the form fingerprint, and limit checks. |
| `frontend/src/components/simulation/SimulationModeSwitch.tsx` | **New.** |
| `frontend/src/components/simulation/NamedSharedQueueSimulation.tsx` | **New.** The named view (sections 9.2.1-9.2.16). |
| `frontend/src/components/simulation/NamedWorkforceForm.tsx` | **New.** |
| `frontend/src/components/simulation/NamedReplicationTable.tsx` | **New.** The table and aggregate panel. |
| `frontend/src/components/simulation/NamedSharedQueuePlayback.tsx` | **New.** |
| `frontend/src/components/simulation/NamedAttributionTables.tsx` | **New.** |
| `frontend/src/pages/SimulationPage.tsx` | Small insertion: read `mode`, render the switch, and route to the named view (section 9.1). |
| `frontend/public/locales/en/translation.json`, `.../tl/translation.json` | Append `simulation.named_*` keys, symmetric. The Filipino wording needs owner review (quality UNKNOWN). |
| New `*.test.tsx` / `*.test.ts` beside each new file, and additions to `SimulationPage.test.tsx` | Section 16. |

Unchanged: `router.tsx`, `types.ts`, `workflow.ts`, `ComparisonPage`, `DecisionEndpointPage`,
`DecisionEndpoint`, `ReportsPage`, `WorkflowNavigator`, `LiveSimulationPlayback`,
`SeparateSimulationPlayback`, and `StoreFloorView`.

---

## 15. Required backend tests (`tests/test_api_shared_named.py`)

1. **Auth and CSRF.**
   - Each route returns 401 without a session.
   - R2 and R3 return 403 with a session cookie and a missing or wrong `X-CSRF-Token`, and succeed with the
     token.
   - `EXEMPT_FAMILIES` is unchanged, asserted by the existing test.
2. **Ownership.** 404 for:
   - another user's analysis;
   - a dataset of another user or another analysis;
   - a run of another analysis, another user, or another kind (for example a `workflow_des` Job id);
   - a missing run;
   - a replication index at or above `replications`, or negative.
3. **Eligibility.**
   - 422 for `separate_queues`, `single_server`, and `unknown` structures, for `capacity_mode=finite`, and for
     `abandonment_mode=modeled`.
   - 422 for `unknown` capacity or `unknown` abandonment (OD-3, approved: unknown is never read as
     absent).
   - 409 `analysis_archived` from R3 on an archived analysis, with the engine spy not called and no Job
     written (OD-7). R2, R4, R5, and R6 still answer on that analysis.
4. **Model scope.** A dataset with `variance`, a date-labelled event dataset, `K`, `theta`, or separate rows
   gives `runnable: false` at stage `demand` (R2) and 422 (R3). There is no silent reduction to M/M/c.
5. **Schema.**
   - Each required key is missing in turn: `closing_policy`, `employee_policy`, `required_staffing`,
     `replications`, `seed`, and the `pay` keys.
   - Each case gives 422, with no default applied.
   - A non-approved employee-policy value gives 422 at stage `engine`.
   - Raw request bodies containing `NaN`, `Infinity`, and `-Infinity` in every numeric field class (minutes,
     counts, pay, seed) give 422.
   - `60.0` in an integer field, booleans, strings, and extra keys give 422.
   - **Persistence identity (B1).** The required PostgreSQL integration test is defined in section 3; all
     5 of its points are mandatory. In SQLite runs, a unit-level test also checks two things:
     - the re-read bypasses the ORM identity map, and a monkeypatched read-back that differs causes a
       rollback;
     - no Job remains, and no run ID is returned.
     A SQLite pass does not replace the PostgreSQL test.
6. **Limits.**
   - `N_MAX + 1`, `S_MAX + 1`, `E_MAX + 1`, and `R_MAX + 1` give 422.
   - A monkeypatched `run_named_replications` spy asserts that the engine was **not called**.
   - `N_MAX` itself is accepted.
7. **Faithfulness.**
   - The R3 `result` is JSON-equal to a direct `run_named_replications` call on the same dataclasses.
   - The R2 `roster_report` equals `evaluate_roster`.
   - The R1 values equal the imported constants.
8. **X4 and X7.**
   - A register-excess roster gives `runnable: false` with its violations (R2) and 422 (R3).
   - An INCOMPLETE roster with only pay missing is runnable.
   - A segment that crosses a demand boundary gives `runnable: false`.
   - An empty roster is runnable, and every customer is unserved.
9. **Persistence.**
   - The Job has the right `kind`, `status`, and exact `params_json` keys, with server keys written after
     request keys.
   - `result_json` is unmodified, and it contains no `events`, `customers`, or `employee_timeline`.
   - No Job exists after any 4xx or 5xx.
   - With `result_jsonb_max_bytes` monkeypatched small, the response is 413 and no Job exists.
10. **Isolation of evidence.** `GET /analyses/{id}/workflow` is byte-identical before and after named runs
    exist. The legacy Decision and Report outputs are unchanged.
11. **Regeneration.**
    - R6's `playback` equals a direct `playback_from_named_replications(stored, i)`.
    - R6's `attribution` equals the direct D6 path plus `build_named_attribution`.
    - Each of these tamperings gives 409 `regeneration_identity` with the matching `check`, and neither a
      `playback` nor an `attribution` key appears:
      - a stored row;
      - `provenance.inputs`;
      - `inputs_sha256`;
      - `method_version`;
      - `closing_policy` set to `"drain"`.
12. **D6 guard.** A monkeypatched regeneration whose row differs gives 409 `regeneration_identity` with
    `check: "attribution_stored_row"`.
13. **Cost stays backend-only.** No route or response contains a key named `*cost*`. The adapter source
    imports no `shared_named_cost`.
14. **Adapter import pin.** A source test lists the allowed and forbidden named modules (section 14).
15. **Round trip.**
    - SQLite: persist, reload, and regenerate.
    - **PostgreSQL** (`NOVAQ_TEST_DATABASE_URL`): the same, for the light, maximum-structure, **busy**, and
      **stress** payloads. Stage 0 covered only the first two; the other two are NOT TESTED.
    - Also on PostgreSQL: the B1 persistence identity test (section 3; all 5 points).
    - It skips without the variable, so the Stage 1 and Stage 3 gates must run it and report the result,
      not the skip.
16. **Dataset generation (OD-2).** `params_json.dataset_generation` equals the selected dataset row's
    `generation`. It is never `null` and never taken from another dataset. This test needs the G-A base.

---

## 16. Required frontend tests

1. `npm run typecheck`, covering the `sharedNamed.ts` types against the fixtures.
2. `sharedNamed.ts` client: every function uses the exact method, URL, and body. POSTs rely on the existing
   CSRF interceptor (asserted with the mocked `http`).
3. `namedWorkforce.ts`:
   - the HH:MM and minutes round trip, including `24:00`;
   - `null` pay stays `null`, never 0;
   - the fingerprint changes on any field edit;
   - limit checks.
4. `SimulationPage`:
   - no `mode` gives the unchanged legacy render, and existing tests pass unmodified;
   - the switch appears only for `shared_queue`;
   - `mode=named` renders the named view without a scenario;
   - `separate_queues` with `mode=named` renders the legacy page and no switch.
5. `NamedWorkforceForm`:
   - no defaults: the closing policy is unselected, replications and seed are empty, and required staffing
     is empty;
   - there is no name field;
   - the employee policy is read-only and taken from R1;
   - Run is disabled until the last validate was runnable for the current fingerprint.
6. `NamedReplicationTable`:
   - wait values display in minutes (× 60);
   - `null` shows "—";
   - the aggregate shows the interval with `n` and `n_undefined`;
   - no PASS, FAIL, verdict, cost, or ROI text is rendered.
7. `NamedSharedQueuePlayback`, against a fixture **generated by the backend** from synthetic inputs and
   committed as test data:
   - steps in `seq` order;
   - lanes show employee state and register;
   - there is a closing marker;
   - `not_represented_by_events` is listed separately;
   - no event is invented, because the rendered count equals `events.length`.
8. `NamedAttributionTables`: per-shift and per-employee rows and the closing cells, in hours.
9. R6 error: a 409 shows the refusal `check` and renders no playback or attribution.
10. Locale symmetry: `translationKeys.test.ts` passes, and every new key is in both `en` and `tl`.

Gates: `npm test`, `npm run typecheck`, `npm run lint`, and `npm run build`.

---

## 17. Integration tests (Stage 3)

- **Local stack** (Docker Compose or `npm run dev` plus the API):
  1. create a `shared_queue` analysis with `unlimited` capacity and `not_modeled` abandonment;
  2. upload an aggregate `HH:MM-HH:MM` dataset without variance;
  3. validate, run `N_MAX` replications, list, and open the run;
  4. open replication 0 and the last index;
  5. verify the playback and attribution render and that the CSRF header was sent.
  Use browser checks through the preview tools, with screenshots and network evidence.
- **Negative checks in the browser**: an event-derived dataset gives the model-scope message, and a tampered
  run (DB edit in the test stack) gives the 409 message.
- **PostgreSQL-backed API run**: persist, then regenerate through R6 (M3 end to end).
- **Legacy parity**: legacy shared Simulate, Separate Queue Simulate, Compare, Decision, and Reports behave
  exactly as before on the same stack.

---

## 18. Protected regressions (must pass unchanged)

- The full backend suite (`python -m pytest tests/ -x --tb=short`). Baseline from the latest recorded
  full run: 2172 passed, 3 skipped, 1 xfailed, and 6 subtests passed (REPORTED, `handoff.md`). It must be
  rerun, not assumed.
- All `tests/test_shared_*.py` files, including the 5B-4.0 pin (`tests/test_shared_continuous_des_pin.py`)
  and the isolation test, which changes only as section 14 describes.
- The Separate Queue test files (20, per `handoff.md`), `tests/test_production_hardening.py` (CSRF
  exemptions), `tests/test_workflow_api.py`, `tests/test_simulation_api.py`, `tests/test_optimization_api.py`,
  `tests/test_scenarios_api.py`, and `tests/test_reports_api.py`.
- `ruff check .` and `mypy . --exclude '^outputs/'`.
- Frontend: every existing test file, plus typecheck, lint, and build.
- `git diff` shows no change under `backend/queueing_engine/`, `migrations/`, or `requirements*`, and none
  in the unchanged-file lists of section 14.

---

## 19. UNKNOWN, CONFLICTING, and open decisions

**Decisions approved by the product owner on 2026-09-30** (APPROVED SPECIFICATION):

| Id | Approved decision | Where applied |
|---|---|---|
| OD-1 | Deterministic regeneration must match the stored replication row before attribution. A mismatch fails closed with 409. | Section 7, step 4; section 11 |
| OD-2 | Dataset selection is explicit, and its identity and generation are recorded with the run. | Sections 3, 5, and 13 (needs G-A) |
| OD-3 | Unknown capacity or abandonment is ineligible; unknown is never read as absent. | Section 3 gates; section 15, item 3 |
| OD-4 | Real domain validation is authoritative. A zero-customer engine run is only an additional structural check, never the sole validator. | Section 4 (R2 steps 7-8) |
| OD-5 | An explicit seed (root entropy) is required. There is no random hidden seed. | Section 3 (`seed` required, 0..2^53−1) |
| OD-6 | No saved drafts. Past run inputs may be reloaded. | Section 9.2, item 14 |
| OD-7 | Archived analyses cannot create new named runs. | Section 4 (R3 step 1); sections 11 and 12 |
| OD-8 | Verify G-A (`92d95bed`, now tip `00582c11`) and settle the sequencing before implementation. | Sections 1.1, 13, and 20 |
| OD-9 | A persisted run must stay within 80 % of the actually VERIFIED production result-size cap. Runtime limits must derive from VERIFIED platform timeouts, not guesses. | Sections 6.2 and 6.3 |
| Numeric identity (2026-10-01) | Option **B1** approved: fail-closed persistence identity verification before commit. **B2 is not approved.** No safe numeric interval is claimed. | Section 3; section 4 (R3 step 6); sections 11 and 15 |
| Identity status codes (2026-10-01) | B1 create-time persistence failure: **HTTP 422** `persistence_identity_mismatch`. Playback or attribution regeneration mismatch on an existing run: **HTTP 409** `regeneration_identity`. | Sections 3, 7, 11, and 15 |

**UNKNOWN** (re-checked 2026-09-30; no Render, Cloudflare, or Supabase account access was available)

- Access checked:
  - no Render, Wrangler, or Supabase CLI on PATH, and no platform token variables;
  - the built-in browser shows the Render sign-in page, and signing in was not attempted;
  - no Claude in Chrome browser is connected.
- Production `RESULT_JSONB_MAX_BYTES` on Render. The repository has no Render config. The code default is
  524,288 when unset, and `.env.example` and `docker-compose.production.yml` also use 524,288, but none of
  these is the deployed value.
- The Render request or runtime timeout for the deployed backend. No app-level request timeout is
  configured (`entrypoint.sh`: workers, concurrency limit, and graceful shutdown only).
- The Cloudflare Pages `/api` bridge timeout, and its response or body limit for a 4+ MB JSON response. The
  bridge code sets neither (`frontend/functions/api/[[path]].ts`).
- The production PostgreSQL version. Production is REPORTED as Supabase in `memory.md`; the version is
  unknown.
- Production runtime. Only local timings exist (section 6.4).
- The complete floating-point domain that survives the JSONB path with digest identity. Only the listed
  values were measured (section 3), and no interval is claimed. B1 (approved, NOT IMPLEMENTED) makes
  persistence fail closed without depending on that domain.
- The PostgreSQL round trip of busy and stress payloads (NOT TESTED).
- The quality of the Filipino wording for new keys.
- D15 and the acceptance rule. No verdict exists, and none is added.
- The contents of Phase 5A D6 and D8.
- Whether real datasets used with this slice meet the aggregate M/M/c scope. VERIFIED only that event
  uploads cannot.

**CONFLICTING**

- The NumPy pins (`<2.3` / 2.4.6 / 2.2.6). Regeneration fails safe with 409; the pins are not changed.
- The G-A contract's own open CONFLICTING items (REPORTED in the contract on `fix/d1`, lines 84, 1039,
  and 1247). G-A is also not complete: its frontend stage is not ported, and its CI and docs scope is
  REPORTED undecided (section 13).
- File overlap by the one-writer rule: none between `feat/shared-queue-segments` and `00582c11`
  (VERIFIED). The unported D7 frontend and this slice's Stage 2 share `SimulationPage.tsx` and the
  locales.

**Out of scope (restated)**

- Workforce cost display, and any expected, average, interval, or verdict cost.
- Cross-replication cost aggregation, paired roster comparison, CRN comparison, Compare, Decision, and
  Reports.
- The 5B-2 and 5B-3 optimizers, upload of workforce data, a workforce table, migration `0005`, and
  dependency pins.
- The open playback v4 items: `Fraction` queue-area overflow, an unknown `unfulfilled_cause`, and accepted
  non-finite values. The API's finite validation keeps them unreachable from this API (INFERRED).

---

## 20. Proposed implementation stages

Each stage needs explicit approval, is verified on its own, and is committed locally only when approved.
Nothing is pushed.

| Stage | Content | Gate |
|---|---|---|
| 0 | OD-1 to OD-9: **approved**. M1-M4 measured locally (section 6.4). **Still open:** M5 and the production request and response limits (UNKNOWN), so the section 6.2 constants are provisional and NOT PRODUCTION-APPROVED. | Production cap and limits VERIFIED; constants finalized under OD-9. **BLOCKED** until then. |
| 0.5 | G-A integration into the named line's base: the owner chooses between integrating the backend-only G-A tip `00582c11` now, or waiting for G-A completion (the frontend D7 stage, the CI and docs scope, and the contract's CONFLICTING items). No merge, cherry-pick, or rebase has been done. | The integration commit is re-verified and the G-A PostgreSQL gate is rerun on the integrated tree. |
| 1 | Backend: `shared_named.py` (including the B1 persistence identity check), 2 lines in `main.py`, the isolation-test change, and `tests/test_api_shared_named.py`. It needs stage 0.5 for `dataset_generation` (OD-2). | Section 15 passes, including the B1 PostgreSQL integration test (section 3, all 5 points) and the busy and stress PostgreSQL round trips; the full backend suite, ruff, and mypy pass; the section 18 diff check passes. |
| 2 | Frontend: the section 14 files and tests. It follows the G-A frontend (D7) stage, which edits the same `SimulationPage.tsx` and locale files. | Section 16 passes, along with `npm test`, typecheck, lint, and build. |
| 3 | Integration (section 17), browser proof, then `handoff.md` and `memory.md` updates and the final report. | Section 17 is complete, and the protected regressions (section 18) are rerun green. |

STOP: no implementation has started.

Status (2026-10-01):

| Item | Status |
|---|---|
| Numeric identity policy | APPROVED B1, NOT IMPLEMENTED |
| B2 | NOT APPROVED |
| Identity status codes | Approved: 422 `persistence_identity_mismatch` (create); 409 `regeneration_identity` (existing-run regeneration) |
| G-A | BLOCKED: incomplete |
| Platform limits | UNKNOWN |
| API limits | Provisional: 9 replications, 52 segments, 24 employees, 48 shifts; NOT PRODUCTION-APPROVED |
| API/UI implementation | NOT AUTHORIZED |

---

## 21. Implementation record (2026-10-01; LOCAL IMPLEMENTATION, not production or deployment ready)

Authorized by the product owner's master continuation prompt of 2026-10-01 (local commits only; no push, merge to
`main`, or deploy). Sections 1-20 above are kept as written; where they say "not implemented" or "not authorized",
this section is the dated update.

### 21.1 G-A integration (Stage 0.5)

- Before: `e7e3cdae` (final G-A, `port/g-a-stage1`) was not an ancestor of `620f20df`. Merge base `2d063c91`.
  The two lines changed no file in common, and `git merge-tree --write-tree` reported no conflict (VERIFIED).
- Method: `git merge --no-ff e7e3cdae` gave merge commit `a49bb1f1` (parents `620f20df`, `e7e3cdae`). A
  fast-forward was impossible (both lines had moved on). A merge keeps `e7e3cdae` reachable by ancestry and
  rewrites none of the 27 Shared Queue commits; a cherry-pick or a rebase would have done one or the other.
- Checked after the merge (VERIFIED): the tree equals the trial merge; the diff from each parent into the merge
  equals the other line's own change; `GENERATION_ENFORCEMENT_ENABLED = False` (`backend/api/workflow.py:106`).
- Gates on `a49bb1f1`, run from a detached scratch checkout (VERIFIED, local only):
  - SQLite full suite: 2719 passed, 118 skipped (every skip is a `NOVAQ_TEST_DATABASE_URL` PostgreSQL variant),
    1 xfailed (the known `test_selected_mc_load` finding).
  - PostgreSQL 16.15 (disposable `postgres:16-alpine`, the digest pinned in `Dockerfile.db`): the CI
    `postgres-integration` file list plus all 22 test files G-A added or changed, 777 passed, 0 skipped.
  - Frontend (byte-identical to the frontend of `e7e3cdae`): 53 files, 388 tests passed; `tsc -b` and `oxlint`
    clean.
- G-A compatibility (VERIFIED by reading the merged code): the only `Job` query in G-A filters by `kind`
  (`workflow._latest_job`), so `shared_named_replications` Jobs are never read or classified by G-A evidence
  logic; the generation guards cover only `datasets` and `scenarios`. The run records the selected row's
  `Dataset.generation` as stored (OD-2); no second generation mechanism exists.

### 21.2 Production unknowns, classified

None is a local implementation blocker; each is a RELEASE/DEPLOYMENT blocker:

- production `RESULT_JSONB_MAX_BYTES` (the adapter reads `settings.result_jsonb_max_bytes` at run time for the 413
  backstop and reports it in R1);
- the Render request timeout and the production runtime;
- the Cloudflare Pages `/api` bridge timeout and response limits for multi-megabyte R6 responses;
- the production PostgreSQL version (B1 fails closed on whatever database it runs on).

The section 6.2 constants are implemented as provisional module constants in `shared_named.py`, exposed through
R1 with `status: "provisional_not_production_approved"`. They are still NOT PRODUCTION-APPROVED.

### 21.3 Files

- Backend: `backend/api/shared_named.py` (new); `backend/api/main.py` (import and `include_router`, 2 lines);
  `tests/test_api_shared_named.py` (new); `tests/test_shared_segments.py` (the isolation guard now requires the
  adapter to be the exact single importer, by path).
- Frontend: `src/api/sharedNamed.ts`; `src/lib/namedWorkforce.ts`; in `src/components/simulation/`:
  `SimulationModeSwitch.tsx`, `NamedSharedQueueSimulation.tsx`, `NamedWorkforceForm.tsx`,
  `NamedReplicationTable.tsx`, `NamedSharedQueuePlayback.tsx`, `NamedAttributionTables.tsx`, with a test beside
  each (the switch is covered by the page tests); `src/pages/SimulationPage.tsx` (an insertion, +27/-1);
  `src/pages/SimulationPageNamedMode.test.tsx` (new); 248 `simulation.named_*` keys in each of `en` and `tl`.
- Test data: `src/test/fixtures/sharedNamed.json` holds the unchanged R1-R6 responses for SYNTHETIC inputs,
  written by `scripts/generate_shared_named_fixture.py` (SQLite, this machine's runtime; not observed data).
- Unchanged (VERIFIED by `git diff`): `backend/queueing_engine/**`, `migrations/`, `requirements*`, `workflow.py`,
  `simulation.py`, `optimization.py`, `analysis_schemas.py`, `scenarios.py`, `reports.py`, `backend/db/**`,
  `settings.py`, `router.tsx`, `types.ts`, `workflow.ts`, Compare, Decision, Reports, `LiveSimulationPlayback`,
  `SeparateSimulationPlayback`, `StoreFloorView`, and `SimulationPage.test.tsx`.

### 21.4 Implementation decisions inside the approved contract

1. **NaN and ±Infinity (section 11).** FastAPI's default validation response echoes each offending input. A
   non-finite input cannot be encoded as JSON, so on an ordinary route such a 422 becomes a 500. This is VERIFIED
   and pre-existing across the app (reproduced on `POST /analyses`); it is not fixed here. The named router uses
   its own `APIRoute` class that returns FastAPI's validation list with each non-finite input shown as its JSON
   token text, so R2 and R3 return 422 as section 11 requires.
2. **Limits.** Counts above `N_MAX`, `S_MAX`, `E_MAX`, `R_MAX`, and the list bounds are refused by the adapter
   with `limit_exceeded` before any computation, in R3 and also in R2 (section 11 states the rule without naming
   a route). The schema checks types, finiteness, strict integers, extra keys, and minimum lengths only.
3. **Ineligible reasons** are stable codes: `queue_structure_not_shared_queue`, `capacity_not_unlimited`,
   `abandonment_not_not_modeled`.
4. **B1 checks**, made on the database's representation, read by a column `SELECT` inside the flushed
   transaction: `inputs_fingerprint` (recomputed from the re-read inputs), `recorded_fingerprint`,
   `stored_row_count`, `stored_row` (int, float, and bool kept distinct, floats compared by bits, arrays equal
   whether list or tuple), each `REQUIRED_PROVENANCE` field, and `persisted_structure`. The aggregate summary is
   not a B1 field, because section 3 lists only the fingerprint, rows, and required provenance.
5. A pre-persistence fingerprint that differs from `provenance.inputs_sha256` would be a domain defect; the
   adapter answers 500 `inputs_digest_inconsistent` (no test reaches it).
6. **JSONB key order (VERIFIED finding).** PostgreSQL `jsonb` does not keep object key order: the first version
   of test 9 failed on PostgreSQL 16.15 because `params_json` came back reordered. The "server keys after request
   keys" order exists at construction and in SQLite's JSON text only. What the order protects holds on its own:
   every request model forbids extra keys, so a request can never supply a server key (tested for each server
   key). The test now checks the exact key set everywhere and the order only on SQLite.
7. **Cost (section 15, item 13).** The only response keys containing "cost" are the domain's `monetary_cost`
   disclaimer strings; no cost value is exposed, and the named workforce-cost module is not imported.
8. **R1 versions:** `named_api_version` (`novaq-shared-named-api-v1`), `method_version`, and
   `named_engine_version`; every run's provenance carries all versions.
9. **Frontend.** The named-mode page tests live in a new file, so `SimulationPage.test.tsx` is unchanged and
   passes unmodified. The switch also renders on the legacy shared-queue screens (section 9.1). Pay fields start
   as an explicit "Not supplied" (sent as `null`, never 0); every other field starts empty. Run is enabled only
   for a runnable R2 result on the identical form fingerprint plus a valid replication count and seed. The event
   log shows 100 events per page and the scrubber steps through all events; employee lanes are derived only from
   recorded transitions.
10. **Process deviation.** No separate implementation plan file was written; section 20's stages served as the
    plan.

### 21.5 Verification on the final code

All results below come from the final tree, committed as `6ecd9c6f` (parent `a49bb1f1`; local, not pushed).

- Backend full suite (`python -m pytest tests/ -x --tb=short`, SQLite): 2856 passed, 123 skipped, 1 xfailed
  (the known `test_selected_mc_load` finding). Every skip is a `NOVAQ_TEST_DATABASE_URL` PostgreSQL variant:
  the 118 of the `a49bb1f1` run plus the 5 PostgreSQL tests of the named module. From the same run's JUnit
  report:
  - `tests/test_api_shared_named.py`: 137 passed, 5 skipped;
  - all 16 `tests/test_shared_*.py` files: 1139 passed;
  - the 18 files matching `*separate*`: 168 passed;
  - `test_production_hardening` 19, `test_workflow_api` 18, `test_simulation_api` 27, `test_optimization_api` 8,
    `test_scenarios_api` 14, and `test_reports_api` 14 passed.
- PostgreSQL 16.15 (disposable local container): `tests/test_api_shared_named.py` 141 passed, 1 skipped (the
  SQLite-only `1e16` case, by design). This includes the B1 test with all five points of section 3 (a normal run
  commits; a `1e16` pay rate, which `jsonb` returns as an integer, is rolled back with
  `persistence_identity_mismatch`; no Job remains; no run id appears in the response or in R4; a run tampered
  after commit is refused by R6 with 409 `stored_row`) and the light, maximum-structure (52 segments, 24
  employees, 48 split shifts with breaks), busy (demand x5), and stress (demand x10) round trips. An earlier run
  of a previous test revision had 1 failure, the key-order finding in 21.4 item 6.
- Frontend: `npm test` 61 files, 443 tests passed (388 before this slice, 55 new; `SimulationPage.test.tsx`
  unmodified). `npm run typecheck`, `npm run lint`, and `npm run build` exited 0; the build keeps the existing
  large-chunk warning. An earlier full run had 1 timeout (10 s) in `CurrentDatasetCache.test.tsx` while three
  suites ran at once; that file passed 6/6 alone and the full rerun passed.
- `ruff check .`: clean. `mypy . --exclude '^outputs/'`: no issues in 200 files. `git diff --cached --check`:
  clean.
- Protected paths: `git diff` shows no change under `backend/queueing_engine/`, `migrations/`, or
  `requirements*`, nor in the unchanged lists of section 14. `GENERATION_ENFORCEMENT_ENABLED = False`.

### 21.6 Not done, UNKNOWN, or CONFLICTING

- Stage 3 (section 17: local-stack browser checks with network evidence) is NOT TESTED.
- The production facts in 21.2 remain UNKNOWN; this work neither affects nor claims G8.
- The quality of the Filipino wording is UNKNOWN (the keys are symmetric; the wording needs owner review).
- `handoff.md` records the Separate Queue regressions as "20 files" but never lists them; 18 test files match
  `*separate*` (CONFLICTING count, recorded, not resolved).
- The NumPy pins stay CONFLICTING (section 7); regeneration fails closed with 409 across versions.
- The app-wide NaN-to-500 behavior outside the named router (21.4, item 1) is a pre-existing defect, not fixed.

### 21.7 Stage 3 local integration record (2026-10-01)

This dated record supersedes only the Stage 3 `NOT TESTED` statement in 21.6. All inputs below were synthetic local fixtures, not operational observations. The stack was `docker-compose.integration.yml` under the `novaq_stage3` project, with PostgreSQL 16.15 and the web/API bridge on `127.0.0.1:18080`; `/healthz` and `/api/ready` returned 200. Browser evidence was captured with Playwright in the untracked `output/playwright/stage3/` directory. No production endpoint or credential was used.

- **VERIFIED — Named shared positive path.** In a new `shared_queue` analysis with `unlimited` capacity and `not_modeled` abandonment, a two-hour aggregate CSV (`time,lambda,mu,c`; no variance, K, or theta) was accepted. Named validation initially refused one staffing segment crossing the demand boundary, then returned runnable after matching the two hourly segments. With explicit seed 7 and `N_MAX = 9`, the browser POST created run 1; the run appeared in the list and opened with nine replication rows and descriptive aggregate evidence. PostgreSQL stored one completed `shared_named_replications` Job. R6 returned 200 for replications 0 and 8; playback advanced through recorded events and employee/shift attribution rendered. The browser request log showed `X-CSRF-Token` on both named POSTs (the token value is not recorded here).
- **VERIFIED — Refusals and restoration.** A separate aggregate dataset containing service variance was accepted as data but named validation returned `Not runnable` at the demand stage with the M/M/c-only scope message. An intentional edit to run 1 replication 8's stored `closing.drain_crew_size` in the disposable PostgreSQL database made R6 return 409 `regeneration_identity` / `stored_row`; the browser showed the refusal without playback or attribution. The original value was restored with a conditional update, and a later browser R6 request returned 200.
- **VERIFIED — PostgreSQL persistence/regeneration.** The nine-replication POST and subsequent R6 reads ran against the local PostgreSQL-backed API; the Job row and restored stored value were inspected in that database. This is local integration evidence only.
- **VERIFIED — Legacy parity exercised on the same stack.** A selected legacy shared scenario ran DES and exposed a 31-event trace; its validation passed, while Decision remained insufficient because the unstable synthetic baseline lacked a comparable modeled total cost. Reports previewed that evidence and a scenario PDF download returned 200 with a `%PDF-1.4` signature. For Separate Queue, an aggregate-only plan was not selectable because it had no per-period estimated optimum. A new synthetic event-derived dataset supplied empirical service samples; its replicated-DES plan was selectable in Compare, selected-plan DES rendered a separate-queue trace and advanced on Step, Monte Carlo and validation completed (`PASS`), Decision rendered `CONDITIONAL`, and Reports displayed the selected scenario while leaving savings and ROI unavailable because current and plan cost bases differ. These UI outcomes are not operational performance conclusions.
- **VERIFIED — Scope.** No first-slice defect was reproduced; no application source, test, mathematical, API-contract, schema, or locale file was changed. The protected legacy surfaces were exercised, not extended with named-run cost or decision logic. Generation enforcement remained `False`.
- **UNKNOWN / NOT TESTED.** Production behavior, result-size cap, Render and Cloudflare limits, production PostgreSQL version, and the Filipino wording quality remain unverified. Provisional limits (9 replications, 52 segments, 24 employees, 48 shifts) remain **NOT PRODUCTION-APPROVED**. The known app-wide NaN-to-500 behavior and NumPy pin conflict remain outside this stage.
- **VERIFIED — Final-tree gates.** `python -m pytest tests/ -x --tb=short`: 2856 passed, 123 skipped (PostgreSQL variants), 1 xfailed (known `test_selected_mc_load`), 6 subtests passed. `NOVAQ_TEST_DATABASE_URL` on the local `postgres:16-alpine` `_test` database, `python -m pytest tests/test_api_shared_named.py -x --tb=short`: 141 passed, 1 skipped (the SQLite JSON-path case, as marked in that test). Frontend `npm test`: 61 files and 443 tests passed, with no timeout; `npm run typecheck`, `npm run lint`, and `npm run build` exited 0 (build reported the existing large-chunk advisory). Ruff via `.venv/Scripts/ruff.exe check .` passed; mypy via `.venv/Scripts/mypy.exe . --exclude '^outputs/'` found no issues in 200 source files. The initial bare `ruff` invocation was unavailable on PowerShell's PATH; the installed executable ran the gate. `git diff --check` passed.
