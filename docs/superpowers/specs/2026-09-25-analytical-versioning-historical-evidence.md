# Analytical Versioning and Historical Evidence Integrity (Milestone 6)

Date: 2026-09-25. Status: **PROPOSED — awaiting product-owner review. Nothing here is implemented.**

Status update (2026-10-01): "Nothing here is implemented" above is HISTORICAL.

- The product owner has decided OD-1 (section 15), OD-12, OD-GA-C1 and OD-GA-C2 (plan Step 0).
- The release G-A scope of this design is implemented, and the G-A implementation milestone is
  complete on `port/g-a-stage1` at `e7e3cdae` (plan Step 0, "G-A implementation completion
  record"). It is not released.
- Everything outside G-A stays as written: engine v3, the M3 marker, OD-1 history, Step 11 report
  identity and OD-2 … OD-11.
- The section 5.4 defect stays open (OD-GA-C2).

Base code for every source reference: `fix/d1-replication-costs` at `d4bca6af` (main `1d3294cb` plus
D1 `c25591a7`, D5 `5291f7ec`, D10 `66ba238e`, D2 `d4bca6af`). Shared-queue references:
`feat/shared-queue-segments` at `c37c4f00`.

Labels: VERIFIED (inspected source, local data or an executed test), REPORTED (documentation or
earlier sessions, not re-checked here), PROPOSED (a design choice in this document), UNKNOWN,
CONFLICTING.

Governing rule: NovaQ never presents results produced under different datasets, setups, models,
accounting definitions or engine versions as interchangeable evidence. Historical evidence is
preserved, never overwritten, never silently recomputed.

---

## 1. Scope and non-goals

In scope: version identity for saved separate-queue plans and Current separate-queue DES, one
currentness policy for all persisted workflow evidence (D7, schema-1 scenarios, deleted
dependencies), frontend and report presentation of non-current evidence, deploy-time version
compatibility, shared-queue applicability.

Not in scope and not changed by this design: Monte Carlo methodology (the strict xfail in
`tests/test_selected_mc_load.py:147` stays), Current DES break modeling, utilization definitions,
cost objectives, database schema (the minimum design needs no migration), production data.

## 2. Verified baseline this design relies on

| Fact | Evidence | Status |
|---|---|---|
| Dataset content never changes after creation: `normalized_json` and `validation_report_json` are only written in the constructors (`datasets.py:112-121`, `analyses.py:217-226`, `analyses.py:270-279`); the only later write is attaching a legacy dataset's `analysis_id` (`scenarios.py:309-310`) | grep of all API writes | VERIFIED |
| Deleting a dataset deletes its scenarios (`models.py:154-156`, `cascade="all, delete-orphan"`) but not their jobs; jobs have no foreign key to scenarios or datasets (`models.py:181-197`) | source | VERIFIED |
| The "current dataset" is the highest-id dataset of the analysis whose validation report is ok; implemented twice (`workflow.py:378-386`, `analyses.py:349-354`) | source | VERIFIED |
| `setup_hash` = sha256 of the canonical setup JSON (`scenarios.py:195-198`); stamped server-side on every job (`workflow.py:508`) and on schema-2 plans (`scenarios.py:314-320`) | source | VERIFIED |
| Saved schema-2 results are the server's own re-execution (`scenarios.py:178-192`); the client-sent `engine_version` must equal the server constant (`scenarios.py:145`); `calculated_at` is client-supplied | source | VERIFIED |
| The frontend hard-codes both engine strings in the save payload (`OptimizePage.tsx:669`, `OptimizePage.tsx:713`); there is no build-version or reload logic in `frontend/src` | grep | VERIFIED |
| None of D1, D5, D10, D2 changed any version string; the workflow `ENGINE_VERSION` (`workflow.py:66`) is written on every job and read by nothing | grep | VERIFIED |
| Selected-plan DES reuses the optimizer's evaluators: per-period via `evaluate_candidate_with_des` (`workflow.py:1651`), continuous day via `run_routing_day_des` (`workflow.py:1910`), which `_day_candidate_runner` also uses (`separate_optimization.py:2015`) | source | VERIFIED |
| D2 stamps `wait_population` on every supported separate Current DES row (`simulation.py:862`); capability-error rows carry `queue_structure: "separate"` and `simulation_supported: false` but no metrics (`simulation.py:618-629`) | source | VERIFIED |
| The SPA never calls the stateless `/simulation/*` endpoints; all browser DES runs go through persisted workflow jobs | grep of `frontend/src/api` | VERIFIED |
| Scenario 30 (analysis 21, dataset 35, local DB) re-exported today is byte-identical to the Milestone 5 export; pre-D1 replay reproduces it exactly; the D1-branch replay keeps every lane count and status and moves the day total 5343.884674276859 → 5422.62562890955 with the same engine string | read-only export + offline replay, executed today | VERIFIED |
| Scenario 12 (analysis 2, schema 1) is pinned to dataset 7 while dataset 8 is current, and passes every current schema-1 selection predicate (`_scenario_setup_problem` → None, `_operationally_complete` → True) | read-only export + real predicate functions, executed today | VERIFIED |
| Targeted suites today: D1 branch 169 passed, 1 xfailed; shared-queue suites 129 passed | executed | VERIFIED |

## 3. Analytical version identity (requirement A)

### 3.1 Existing mechanisms reused unchanged

| Identity | Mechanism | Sufficient? |
|---|---|---|
| Dataset | `dataset_id` | **No (corrected 2026-09-26).** Content is immutable (section 2), but an integer id names a row, not a generation: after a deletion the id can be issued to a different row, and a job that recorded only the id cannot tell the two apart (VERIFIED, section 5.4). A content hash is not identity either: a byte-identical replacement is still a different record. Exact source identity needs the generation mechanism of section 5.4. |
| Current dataset | "highest-id dataset with ok validation" | Yes, as a rule. PROPOSED: one helper used everywhere (section 5). |
| Setup | `setup_hash` | Yes. Server-computed, canonical, on every job and schema-2 plan. |
| Selected-plan DES basis | `result.execution` (`SELECTED_DES_PER_PERIOD_EXECUTION` / `SELECTED_DES_CONTINUOUS_DAY_EXECUTION`) | Yes. Recorded since `9cddeb55` (REPORTED in the D10 spec; the constants are VERIFIED). |
| Selected-plan DES accounting | The plan's `SEPARATE_DES_ENGINE_VERSION` | Yes, because the selected DES runs the optimizer's own evaluators (section 2). Rule: any change to `_run_routing_des`, `evaluate_candidate_with_des` or `run_routing_day_des` accounting bumps the separate engine version. |
| Chain linkage | `params.engine`, `des_job_id`, `mc_job_id`, `validation_job_id`, `evidence_ids` | Yes. |
| Reference ordering | `created_at` on scenarios, datasets and jobs | **A guard only, not an identity proof (corrected 2026-09-26).** It rejects a reference to a record created strictly after the job. It cannot reject a replacement whose recorded `created_at` equals or precedes the job's: SQLite stores whole seconds, and any engine accepts an explicit id and timestamp. SQLite without AUTOINCREMENT reissues a deleted newest id; PostgreSQL did not reissue ids in the inspected default configuration but does after a sequence reset or an explicit-id insert (VERIFIED, section 5.4). |

### 3.2 New or changed markers (minimum set, PROPOSED)

| # | Marker | Why an existing mechanism is not enough |
|---|---|---|
| M1 | `SEPARATE_DES_ENGINE_VERSION = "novaq-2026-09-separate-des-v3"` (value change of the existing field) | D1, D5 and D10 change saved-plan results under the same v2 string (scenario 30). Without a new value, v2 records are indistinguishable from corrected ones. |
| M2 | v3 schedules always record `utilization_basis`, adding a per-date value (for example `"per-period DES"`) next to the existing `"continuous-day DES"` (`separate_optimization.py:1957`, `2192`, `2198`) | Today only representative-day schedules carry the key, so a per-date schedule is identified only by its absence. Reuses the existing key. |
| M3 | `params_json.current_des_accounting = "current-separate-fixed-horizon-v1"` on jobs whose result contains separate-queue Current DES rows (`workflow_des_current`, and legacy `workflow_des` of a schema-1 separate scenario); constant defined next to `_simulate_parallel_segments_core` | `wait_population` (section 6) is an English disclosure sentence, names only the wait population (not the busy-time attribution), is per row, and is absent on capability-error rows. It cannot serve as a versioned identity. |

Not added (not necessary): a global workflow engine bump (Decision 1), a dataset content hash,
version fields on selected-chain MC/validation/decision jobs (they inherit through the chain), a
persisted report version (reports are not persisted; the exported file carries its evidence block,
section 10), a copy of the separate engine version on selected DES jobs.

### 3.3 Server-side version registry (code constant, not persisted)

| Family | Value | Registry class |
|---|---|---|
| Separate plan | `…separate-des-v3` | current |
| Separate plan | `…separate-des-v2` | historical, recalculable (known deviations: D1, D5, and D10 for per-date) |
| Separate plan | `…separate-des-v1` | unsupported (existing behavior, `test_pre_day_des_engine_plan_is_unsupported_everywhere`) — see OD-11 |
| Separate plan | anything else | unsupported |
| Schema-1 scenario | `…integrity-v1`, `…system-v2` | current (unchanged; no D-repair touches the shared optimizer) |
| Current separate DES | `current-separate-fixed-horizon-v1` | current |
| Current separate DES | marker absent | accounting unrecorded (section 4) |

Historical identity never rests on a missing field alone: a v2 plan is identified by its recorded
`v2` string; a Current DES job without M3 is not identified as "pre-D2" — it is classified as
*accounting unrecorded* and is never current (fail-closed). The absent `wait_population` sentence
is shown only as supporting detail.

## 4. Evidence status model (requirement B)

### 4.1 Statuses and precedence

Each artifact gets exactly one headline status (first match in this order) plus the full list of
failed checks as reason codes.

| Order | Status | Condition |
|---|---|---|
| 1 | `MISSING_DEPENDENCY` | A referenced analysis, scenario, dataset or linked job does not exist, is not owned by the user, belongs to another analysis, or was created after the referencing job. |
| 2 | `MISSING_PROVENANCE` | An identity needed to decide currentness is not recorded: no calculation snapshot, no `dataset_id`, no `setup_hash`, unknown `execution`, or no M3 marker on a job with separate Current DES rows. |
| 3 | `UNSUPPORTED` | The recorded engine version is registry-unsupported, or the result records the calculation itself as unsupported (every row `simulation_supported: false`). |
| 4 | `STALE_DATASET` | Its dataset is not the analysis's current dataset. |
| 5 | `STALE_SETUP` | Its `setup_hash` differs from the current setup fingerprint (schema-1: the existing queue-type mismatch, `workflow.py:273-274`). |
| 6 | `HISTORICAL_REQUIRES_RECALCULATION` | Recorded version is registry-historical (v2 plan); dataset and setup are current, so the same inputs can be recalculated. |
| 7 | `HISTORICAL_VIEWABLE` | Compatible and on current identities, but superseded: not the latest completed job of its kind for its scope, or not referenced by the current chain (for example a decision whose `evidence_ids` no longer match). |
| 8 | `CURRENT` | Every check passes. |

An incompatible engine (3, 6) is always reported separately from a changed dataset (4) or setup
(5); when both apply, the headline follows the order and both reason codes are listed.

An orphaned job is `MISSING_DEPENDENCY`, never "an outdated simulation".

### 4.2 Chain rule

A downstream artifact is never more current than its upstream: DES ← selection + plan; MC ← DES;
validation ← DES + MC (selected) or ← Current MC (current mode); decision ← selection + DES + MC +
validation. The status of a chained artifact is the worst (by the order above) of its own status
and its upstream statuses.

### 4.3 Eligibility

| Use | Allowed statuses |
|---|---|
| Selection, simulation input, Decision derivation, current report, current value positions in any page | `CURRENT` only |
| Historical detail view (read-only, bannered) | all except `MISSING_DEPENDENCY` values whose subject no longer exists (shown as identity plus reason only) |
| Historical export | only if OD-7 approves it, always labelled |

### 4.4 Local reference classification (PROPOSED application to VERIFIED local data)

| Artifact | Status after this design | Reasons |
|---|---|---|
| Scenario 30 (v2, dataset 35 current, setup current) | `HISTORICAL_REQUIRES_RECALCULATION` once v3 is the current plan engine (`CURRENT` under today's v2 policy) | `VERSION_HISTORICAL`: the recorded engine string is v2. Supporting explanation, not a status reason: the optimum cost of 9/13 periods was priced from 2-4 of 5 replications, and there are no period costs (Milestone 5 replay). |
| Jobs 74-89 (scenario 30 chain) | `HISTORICAL_REQUIRES_RECALCULATION` via the chain; superseded ones also carry `HISTORICAL_VIEWABLE` reasons | upstream plan v2 |
| Jobs 90-91 (scenario 31, deleted) | `MISSING_DEPENDENCY` | scenario missing |
| 13 `workflow_des_current` jobs | `MISSING_DEPENDENCY` | dataset missing (also M3 absent; 12 of 13 are capability-error only) |
| Scenario 12 (schema 1, dataset 7; current is 8) | `STALE_DATASET` | selectable today (section 2) |
| Scenario 13 (schema 1, dataset 8) | `CURRENT` if no other check fails | — |
| Scenario 32 + jobs 92-97 (analysis 22) | `CURRENT` (setup hash of all six jobs equals the current fingerprint `5bb80650…`, dataset 37 is current) | — |

The "Reasons" column separates three kinds of evidence:

- **Recorded engine identity determines version compatibility.** A status reason comes only from a
  recorded field compared with the supplied version policy.
- **Numerical discrepancies support the engineering explanation only.** Examples are
  replications per period, missing `period_costs` and cost totals. They never set or change a status.
- **Missing provenance is never replaced by inferred history.** An absent field is
  `MISSING_PROVENANCE`, not an assumed earlier version.

## 5. D7 dataset-currentness correction (requirement C)

### 5.1 Dataset-currentness checks (VERIFIED against `bc303109`)

Line references are verified against the committed source at `bc303109`, in which Step 3 (D7)
added the Current-mode gate. They shift whenever `workflow.py` changes, so each entry names its
function as well.

| Check | Location | Scope |
|---|---|---|
| Setup hash on every returned job | `_job_setup_current` (`workflow.py:243-249`), applied by `_current_evidence.current` (`workflow.py:654-656`) | scenario-bound kinds |
| Recorded dataset is the current dataset, plus owner, analysis, setup and dependency chain | `_current_evidence.current_mode` (`workflow.py:658-663`), applied at `workflow.py:666`, `667`, `674` via `_current_mode_evidence_is_current` (`workflow.py:638-643`) | `des_current`, `mc_current`, `validation_current` (**D7, corrected in Step 3**) |
| Plan dataset is current | `_own_verified_scenario` (`workflow.py:321-325`) | schema-2 only |
| Plan dataset is current (Compare flag) | `separate_comparison`, against `_current_dataset` (`workflow.py:1502`), flagged at `workflow.py:1546`, `1554`, `1558-1559` | schema-2 only |
| Current MC dataset at validation time | `run_validation_current` (`workflow.py:1000-1004`) | creation of `workflow_validation_current` only |
| Proposal dataset at break apply | `apply_separate_breaks` (`workflow.py:1331-1332`) | break apply |
| Decision staleness by evidence ids | `_current_evidence` (`workflow.py:686-694`) | legacy decision |
| Report chain linkage + setup | `_selected_report_chain` (`reports.py:152-230`) | selected report |
| **None** | `_own_verified_scenario` schema-1 path (`workflow.py:332-339`) | **dataset never compared with the current dataset** |

**The pre-D7 defect (historical).** Before `bc303109`, `_current_evidence` gated `des_current`,
`mc_current` and `validation_current` on the recorded setup hash alone and never compared the
recorded `dataset_id` with anything. A job produced from a replaced, invalidated or deleted dataset
therefore stayed visible in a slot the page labels "CURRENT". The defect was locked in as expected
behavior by `tests/test_dataset_staleness_probe.py::test_separate_current_jobs_stay_visible_after_replacement`.

**Corrected Current-mode behavior (VERIFIED).** That probe is now
`::test_separate_current_jobs_stop_being_current_after_replacement`, asserting the inverted
expectation and keeping its Dataset-A fingerprint assertions against the stored rows.
`tests/test_d7_current_evidence_dataset.py` covers the rule directly. Step 3 enforces dataset
identity and dependency integrity only: it deliberately applies no version rule (the workflow
engine version and the Current DES accounting marker of section 6 are left to their own phase),
and it changes no stored row.

**Still unresolved.** Schema-1 saved-scenario dataset currentness is **not** addressed by D7: a
schema-1 scenario's dataset is checked for existence and validity (`workflow.py:305-312`) but never
compared with the current dataset, so `::test_shared_scenario_evidence_stays_pinned_to_dataset_a`
still passes unchanged (VERIFIED). D7 resolves Current-mode evidence only; it does not resolve
historical-evidence compatibility across NovaQ's other workflows — scenario-bound evidence,
selected-plan chains, decisions and reports keep their existing rules. Section 5.3 and plan Step 4
carry the remaining work.

**Release blocker (recorded, not implemented).** The backend now suppresses incompatible Current
evidence, but the user interface does not yet distinguish a never-run analysis from one whose
historical Current results are no longer eligible: both render as an empty slot. No endpoint serves
historical evidence either (decision OD-1 is not approved), so a superseded Current job is stored
but unreachable. The coordinated frontend compatibility phase must address this distinction before
the D7 repair is deployed.

**Owner decision (2026-09-30), for release G-A.** OD-1 is not approved for G-A and is deferred
(section 15). For G-A, "address this distinction" means: the user interface never presents
non-current or stale evidence as current, and it states clearly that no current run exists for the
current dataset. G-A is not required to tell a never-run analysis apart from one whose earlier
Current results are no longer current: both deliberately show the one current-only state "No
current run for dataset #B" (section 9.2). The blocker stays open until that frontend behavior is
implemented (plan Step 3); it is not implemented (as of 2026-09-30).

**Status (2026-10-01).** The frontend behavior is implemented on `port/g-a-stage1` (`88c6f4da`).
The cache fixes `822d5053` and `e7e3cdae` keep a previous dataset's or Setup's evidence from being
shown as current. This blocker's condition is therefore met for the G-A implementation. That is an
implementation result: the D7 repair is not deployed.

### 5.2 One currentness policy (PROPOSED)

A single module (for example `backend/api/evidence_status.py`) computes the status of section 4
for scenarios and jobs. Every consumer uses it: `_current_evidence`, `_own_verified_scenario`,
`_selected_scenario`, `_require_selected_separate_plan`, `separate_comparison`,
`run_validation_current` (for its MC input), `create_decision`, `create_selected_decision`,
`_selected_report_chain`, `current_decision_for_report`, and the scenario list endpoints. The two
"current dataset" implementations collapse into one helper.

A job is current only if all hold:

1. analysis, scenario (when referenced), dataset and linked jobs exist, are owned, belong to the
   analysis, and were created no later than the job;
2. `params.dataset_id` (Current kinds) or the scenario's `dataset_id` (scenario kinds) equals the
   current dataset id;
3. `params.setup_hash` equals the current setup fingerprint;
4. the scenario, if any, is `CURRENT` (engine registry + completeness + dataset + setup);
5. accounting is recorded and current where the kind needs it (M3);
6. chain links resolve to current jobs;
7. it is the latest completed job of its kind for its scope.

`_current_evidence` returns only `CURRENT` jobs in its existing slots. Old jobs stay in the
database untouched. Whether the workflow payload also lists them as history (identity, status,
reasons, no values) or a separate read-only endpoint serves them is decision OD-1. OD-1 is not
approved for release G-A and is deferred (section 15), so G-A does neither; the old jobs stay stored.

Dataset replacement then makes every dataset-bound artifact `STALE_DATASET` in one step; a setup
change makes every job `STALE_SETUP` (as today). Nothing is recomputed.

### 5.3 Deliberate test changes

**Completed under `bc303109` (Current mode only).**

- `test_separate_current_jobs_stay_visible_after_replacement` is renamed
  `test_separate_current_jobs_stop_being_current_after_replacement` in
  `tests/test_dataset_staleness_probe.py`. The assertion that `workflow["des_current"]["id"]`
  equals the old job inverted: `workflow["des_current"]` and `workflow["mc_current"]` are now
  `None`. The Dataset-A lambda fingerprint assertions are kept, but read from the stored job rows,
  **not** from a historical listing: OD-1 was not approved, no endpoint serves historical evidence,
  and no payload exposes a `STALE_DATASET` status. The statuses and reasons the classifier computes
  are used only to decide eligibility and are then discarded.
- New `tests/test_d7_current_evidence_dataset.py` (21 test functions, 27 cases with
  parametrization) covers the rule directly: recorded dataset identity, replacement, deletion, no
  valid current dataset, setup change, the DES, MC and validation dependency paths, owner and
  analysis isolation, historical rows remaining stored, and the absence of any fallback that would
  promote an older matching job.
- `tests/test_evidence_status.py`: the Step 1 guard asserting the classifier was referenced by no
  backend module now expects exactly `["backend/api/workflow.py"]`, so it still guards against
  unreviewed integration by the later steps.
- `tests/test_break_apply_api.py`: the `_add_job` fixture now records `dataset_id` and the
  validation-to-MC link, as the real endpoints do. It previously recorded no dataset at all — a
  state D7 correctly rejects — so it no longer stood in for a real run.

**Pending Step 4 (schema-1 and scenario-bound evidence).**

- `test_shared_scenario_evidence_stays_pinned_to_dataset_a` is **unchanged and still passes**: it
  still asserts `workflow["scenario"]["id"]` is the Dataset-A scenario. Under Step 4
  `workflow["scenario"]` becomes `None` (no history entry: OD-1 is not approved for release G-A,
  section 15) and the scenario row stays unchanged. D7 did not touch this path.
- `test_separate_decision_after_replacement_stays_insufficient` and
  `test_historical_dataset_report_stays_available_after_replacement` are unchanged and still pass.
  The historical report label of section 10 is not implemented.

No test is deleted; each keeps its dataset fingerprint assertions under its current expectation.

D7 closes Current-mode dataset currentness only. The rest of the historical-evidence compatibility
problem is unresolved: schema-1 and scenario-bound currentness (Step 4), the missing-dependency
guard (Step 5), version and accounting-marker policy (sections 3.2 and 6), and any historical
display or endpoint (OD-1: not approved for release G-A, deferred; section 15).

### 5.4 Exact source identity (Step 5 finding) — RELEASE BLOCKER for exact-generation enforcement (G-B/G9; qualified by OD-GA-C2), unresolved

**What the Step 5 interim repair provides (VERIFIED on its tested tree).** Every persisted workflow
job used as evidence — every workflow slot, both Decision endpoints and the selected-plan report
chain — must resolve each recorded dataset, scenario and job reference to an existing record of the
same owner and analysis. The referenced record must not be recorded as created after the job, and
its own recorded dataset must resolve in turn. When no eligible scenario is selected,
`decision_stale` keeps its pre-Step-5 meaning (Option A): the stored Decision is not served, and
the page is not asked to regenerate a Decision that no regeneration could clear.

**What it does not provide.** It does not prove exact source identity. Records are referenced by
integer id inside `params_json`/`result_json`. The chronology guard compares recorded `created_at`
values and cannot distinguish a replacement record that carries the same id with a creation time
equal to or earlier than the job's.

Write-time consumers that the guard does not cover:

- Selected-plan MC and selected-plan validation pick their input DES/MC job by integer scenario
  id, and apply no dependency gate before computing. A job built on a broken input is stored, and
  is rejected only when it is read.
- `run_validation_current` compares the Current MC job's `dataset_id` by integer.

**Reproduced defect (VERIFIED).**

- Natural timing, SQLite: delete and recreate within the same clock second, so the id is reissued
  and `created_at` is equal. Outcomes:
  - the deleted scenario's DES, MC, validation and Decision were served as current for the
    replacement;
  - a new Decision was built on them;
  - the ID-scoped scenario PDF and Excel reports carried the deleted scenario's Decision headline;
  - the selected-plan Decision and report returned 200;
  - a Current DES computed on a deleted dataset was served for its replacement.
- Deterministic construction, SQLite and a disposable PostgreSQL 16: a replacement inserted with
  the deleted row's id and its stored `created_at`. All of these were promoted:
  - a schema-1 scenario with different content;
  - a byte-identical schema-1 scenario;
  - a byte-identical schema-2 selected plan;
  - a byte-identical dataset under a Current DES.
- A stored selection job re-attaches to a reissued scenario id with no new selection.
- Test coverage caveat. `test_scenario_id_reuse_does_not_inherit_the_previous_generations_evidence`
  advances the replacement's `created_at` by a direct row edit before asserting. It therefore
  covers only the strictly-later case, not the same-timestamp case. Its comment says the advanced
  time is "what a real save would carry"; that is not true for a save in the same clock second.
  The test is a chronology-guard test, not evidence of exact-generation protection.

**Status.** This is an unresolved identity/provenance defect and a release blocker. The Step 5
guard rejects broken references; it is not an exact-generation solution.

**Staging (owner decision OD-GA-C2, 2026-10-01; plan Step 0).** The contract's staging is adopted.

- The defect above stays OPEN and unrepaired in G-A, with its severity unchanged. G-A does not
  claim otherwise.
- "Release blocker" is qualified, not withdrawn:
  - the defect blocks the stage that requires exact-generation enforcement, and any release
    criterion that requires exact identity;
  - G-B/G9 must close it before then;
  - it does not block the G-A implementation milestone, which keeps
    `GENERATION_ENFORCEMENT_ENABLED = False` (contract §6.1, §6.2).
- Since this section was written, the token mechanism described below has been implemented as
  G1–G7 with enforcement off. Enforcement (S3) belongs to G-B.

**Direction approved in principle (2026-09-26); implementation not authorized.**

- Immutable, independently generated generation tokens for scenario and dataset rows.
- Every analytical job and selection records the generation of the source row it actually used.
- A different generation is rejected even when the id, timestamp and content match.
- Conservative legacy policy:
  - existing rows may receive new identities for the rows that exist at migration time;
  - historical jobs' generations are never inferred by joining integer ids;
  - legacy scenario-to-dataset generation links are never inferred from a resolving foreign key;
  - missing provenance stays missing, and current use requires recalculation into a new artifact.
- The transition is coordinated with the separate-plan engine v3 release. Generation-identity and
  engine-version reasons stay separate.

## 6. Current DES accounting marker policy (requirement E)

- Findings (VERIFIED): D2 stamps `wait_population` on supported separate rows only; pooled
  (shared) Current DES rows never come from `_simulate_parallel_segments_core`
  (`simulation.py:926-936`); local DB holds 0 rows carrying `wait_population`.
- `wait_population` alone is insufficient as a historical detector (section 3.2, M3). PROPOSED:
  M3 on the job, set by the workflow layer from a constant owned by the simulation module, shipped
  in the same release as the D2 code so that every production job produced by D2 carries it.
- A job needs M3 only when a result row records `queue_structure: "separate"` (a positive recorded
  field). Pooled Current DES and every selected-plan or shared-queue artifact are unaffected: no
  marker, no reclassification.
- Classification: M3 current → accounting ok. M3 absent → `MISSING_PROVENANCE`
  (`current_des_accounting_unrecorded`). If rows carry `wait_population` but M3 is absent (only
  possible from an unreleased build), the reason list adds `conflicting_accounting_signals`.
- The existing Simulation-page legacy note (`SimulationPage.tsx:88-97`) becomes presentation of
  that status, not its source.

## 7. Saved-plan v3 compatibility policy (requirement D, Decisions 1 and 2)

### 7.1 Consequences by artifact family

| Family | Change under v3 | Treatment of v2 records |
|---|---|---|
| Representative-day plans | D1 (replication pricing), D5 (period costs). D10 does not apply (continuous-day runner unchanged, REPORTED D10 spec; replay of scenario 30 shows unchanged lanes, VERIFIED) | `HISTORICAL_REQUIRES_RECALCULATION` when dataset and setup are current, else stale status |
| Per-date plans | D1, D5, D10 (utilization up to the horizon, Wq population, censoring makes cost undefined; REPORTED sweep: full-coverage OPTIMAL 24/24 → 15/24) | same; recalculation may legitimately return BLOCKED/UNSUPPORTED (see OD-6) |
| Saved scenarios | schema-2 v2 rows unchanged byte for byte; schema-1 rows unaffected by v3 | never rewritten |
| Selected-plan DES | produced by the plan's engine; a v2 plan is not selectable, so no new v2 DES can be produced; existing v2-chain DES jobs inherit the plan status | historical via the chain |
| Monte Carlo | MC code unchanged by all four repairs (VERIFIED hunks); MC jobs inherit from their DES job | historical via the chain |
| Validation | verdict logic unchanged; displayed ρ/Wq copied from DES; inherits | historical via the chain |
| Decision | selected Decision facts carry no cost/ρ/Wq (`workflow.py:2294-2302`); inherits | historical via the chain; `create_selected_decision` refuses a non-current chain (already true once the plan is not selectable) |
| Reports | selected report requires a `CURRENT` chain (section 10) | blocked for v2 (as for v1 today) |

### 7.2 Rules

- Classification uses the recorded `engine_version`. The detectors (`costs.total.n <
  replication_count`, absent `period_costs`, absent `censored_customers`) are used only to explain
  why a v2 plan differs; they never make a v2 plan current.
- Unchanged staffing does not justify carrying a v2 cost forward: scenario 30 keeps every lane
  count and status yet its cost evidence changes in 9 of 13 periods.
- Recalculation = a new optimization run under v3 on the current dataset and setup, saved as a new
  scenario (new id, own snapshot, own seeds). The v2 scenario and its jobs are untouched. A lineage
  link (`recalculated_from`) is optional (OD-2).
- Acceptance reference (reproduced today): scenario 30 stored = pre-D1 replay exactly; v3 replay
  period totals 297.16, 450.23, 480.35, 436.51, 452.36, 453.87, 445.93, 446.42, 464.85, 445.95,
  435.00, 436.44, 177.54 (hourly rates, 60-minute periods, so equal to period costs); day total
  5422.62562890955 vs stored 5343.884674276859. A v3 recalculation of scenario 30's options on
  dataset 35 must reproduce these values.

### 7.3 Historical detail view (Decision 2)

Safe to display original v2 results if all hold: served by a read-only endpoint that returns the
status and reasons with the payload; rendered in a separate view with a persistent banner naming
the accounting version and the known deviations; no select, decide, current-report or compare
action; null values rendered as undefined with their recorded reason. Compare never shows these
values beside Current (section 9.2). Needs an additive endpoint (OD-1). OD-1 is not approved for
release G-A and is deferred (section 15), so this view is not part of G-A.

## 8. Schema-1 dataset policy (Decision 3)

- A schema-1 scenario is `CURRENT` only when its `dataset_id` is the current dataset, in addition to
  the existing snapshot, queue-type and completeness checks. Scenario 12 is the local reference.
- Scenarios with `dataset_id` NULL stay `MISSING_PROVENANCE` (already unselectable, in
  `_own_verified_scenario`, `workflow.py:298`).
- Nothing is deleted or invalidated in storage; the status is computed on read.

**Known limitation (unresolved; no new policy is implemented).** A schema-1 scenario records no
`setup_hash`. Its only Setup identity is the queue type of its snapshot.

- The queue type is computed by `_legacy_snapshot_queue_type`: "separate" if any input segment is
  a separate-queue or `parallel_mg1` row, otherwise "shared".
- It is compared with the Setup's `queue_structure`.
- Any other Setup change leaves a schema-1 scenario's Setup check passing. That includes server
  counts, capacity, abandonment, segments, breaks and queue ids.
- The Step 1 classifier mirrors this rule (`SetupBinding("queue_type")`) and does not strengthen it.
- A stronger schema-1 Setup identity needs a separate decision. It cannot be derived
  retroactively, because the stored snapshots carry no setup fingerprint.
- Restore investigation (VERIFIED behavior):
  - There is no explicit "make this dataset current" action.
  - Deleting newer datasets makes an older one current again, but the cascade deletes the newer
    datasets' scenarios and orphans their jobs — not an acceptable restore path.
  - Re-uploading the same file creates a new `dataset_id`, so old scenarios stay stale.
  - Inspection already works: `GET /datasets/{id}` returns the stored rows and
    `/reports/datasets/{id}/{format}` exports them.
- Restore options (OD-3): (a) none — recalculate on the current dataset; (b) an explicit
  current-dataset pointer on the analysis (schema migration, explicit user action); (c) content
  equivalence — a canonical hash of `normalized_json` plus the validation basis lets identical
  re-uploads count as the same dataset. Recommended: (a) now, (b) if restore is required later.

## 9. Frontend requirements (requirement F)

### 9.1 Value vocabulary (all pages; EN and TL keys added together)

| State | Presentation |
|---|---|
| Current | normal |
| Historical | only inside a bannered historical section or view; banner states status, reason, dataset id, setup change, engine/accounting version; never in the same column, card or chart as current values |
| Undefined | "—" plus the recorded reason; never 0 |
| Unsupported | "Not supported" plus the reason |
| Missing source | "Source deleted" / "Not recorded"; no values |

A frontend receiving no status field treats the artifact as unverified and does not render its
values in current positions (fail-closed across deploy skew, section 11).

### 9.2 Pages

- **Current:** computed on request from the current dataset (`analyses.py:342-370`); show the
  dataset name, id and upload time as the basis. No stored evidence here.
- **Optimize:** fresh runs are current by construction. Save errors caused by an engine update say
  so and ask for a rerun (section 11).
- **Compare (separate):** only `CURRENT` plans appear in the value table and the selector. Other
  plans are listed below without values: name, status, reasons, link to the historical view. The
  server enforces this (OD-5), so a stale client cannot place historical values beside Current.
- **Compare (schema-1):** the scenario list shows each scenario's status; only `CURRENT` scenarios
  show totals and can be selected; "current total cost" states the dataset it was computed from.
- **Simulate (Current mode):** the "CURRENT configuration" badge and results appear only for
  `CURRENT` jobs. When no current run exists for the current dataset, the page shows "No current
  run for dataset #B", where B is the actual current dataset id. A never-run analysis and one whose
  earlier Current results are no longer current show this same state (owner decision 2026-09-30,
  section 5.1). The page shows no historical entry and does not name or expose an earlier dataset
  or run to explain the absence: that would need OD-1, which is not approved for release G-A
  (section 15). The Validate action stays unavailable unless the Current MC job is `CURRENT`.
- **Simulate (selected plan):** replace the single generic message (`SimulationPage.tsx:831-846`,
  "no longer matches the current analysis data") with reason-specific text: engine version, dataset,
  setup, deleted scenario.
- **Decision:** only from a `CURRENT` chain; the stale message names the failing identity.
- **Reports:** section 10.

## 10. Report integrity (requirement G)

- **Selected (separate) report** (`reports.py:427-471`): generated only from a `CURRENT` chain.
  Every export carries an evidence block: analysis id, dataset id, setup hash prefix, plan engine
  version, DES execution basis, Current DES accounting (when relevant), job ids, generation time,
  and the line "Current evidence". A historical selected report is not provided unless OD-7 approves
  one; if approved, it must say "Historical evidence — not current" on every page and sheet and must
  contain only stored values.
- **Scenario report** (`reports.py:588-602`): states the scenario status. Not `CURRENT` → titled
  historical, no current Decision section, dataset identity shown.
- **Dataset report** (`reports.py:575-585`): states whether the dataset is the analysis's current
  dataset.
- Old exported files are never regenerated under their original identity with new calculations.
  A recalculated plan has its own scenario id and its own reports.
- **Pre-D5 wording fix:** the limitation at `separate_report.py:262-263` blames a missing configured
  length. For a plan whose recorded engine is v2 the reason must read, in substance: "Period costs
  are not available: this plan was calculated under separate-des-v2 accounting, which recorded
  hourly cost rates only." The existing unknown-length wording stays for v3 periods whose
  `period_costs.unavailable_reason` says so. The same distinction applies to Compare and to any
  historical view.

## 11. Frontend/backend version compatibility (requirement H)

Findings (VERIFIED unless noted):

- `main` deploys Cloudflare Pages and Render separately (REPORTED, `memory.md` "Deployment
  Topology"); there is no deploy ordering in the repository and no Render config file.
- A loaded SPA keeps its bundle until reload; no reload or version check exists.
- The save gate is strict equality, and the server recomputes and compares results key by key
  (`_same_result`). So during any skew a save fails closed: an old client's `v2` is refused by a v3
  server, and a result computed before the deploy never equals the v3 recomputation (v3 adds
  fields). No mislabelled record can be written; the cost is a confusing 422 until reload/rerun.

Proposed approach:

1. **Server-authoritative stamping (OD-4, API relaxation):** the server ignores the client's
   `engine_version` for the verified families and stamps its own constant after its own
   recomputation; an absent value is accepted. Deploy this backend change on its own release before
   the v3 release. The v3 bump then needs no frontend change.
2. Distinct error for engine drift: "NovaQ was updated; rerun the optimization" instead of the
   generic results mismatch (OD-4).
3. Eligibility is enforced by the server (section 5); the frontend only presents. Old clients
   therefore fail safe: they cannot select, decide or report on non-current evidence, and they do
   not receive historical values in current slots (OD-5).
4. New clients treat a missing status field as unverified (section 9.1).
5. Preferred order inside a release: Render before Pages (UNKNOWN whether Pages can be held).

## 12. Shared-queue integration (requirement I)

Verified on `feat/shared-queue-segments`:

- `shared_segments.py`, `shared_capacity.py` (`ENGINE_VERSION = "novaq-shared-capacity-v1"`,
  emitted in result provenance) and `shared_continuous_des.py`
  (`ENGINE_VERSION = "novaq-shared-continuous-des-v1"`) are pure modules.
- Nothing imports them. `test_no_existing_module_depends_on_the_new_foundation`
  (`tests/test_shared_segments.py:366-375`) fails if any other backend file contains their
  module names; the D1 branch backend contains none (VERIFIED).
- No API, persistence, scenario schema, Decision or report uses them.

Policy:

- The status model, the dataset/setup currentness rules and the chain rule apply to shared-queue
  results as soon as they are persisted — with their own engine families in the registry, never
  the separate engine's version, never D10's censoring policy by default.
- Registry entries for them are added only in the approved persistence phase. Until then the
  registry must not import their constants (the isolation test would fail by design).
- Items needing separate approval before persistence:
  - the closing policy (UNRESOLVED in the Phase 3 spec);
  - whether customers waiting at the horizon make shared costs undefined (the D10 rule) or use
    another estimator;
  - a new scenario schema version and API endpoints;
  - coexistence with the legacy `/optimize/batch` schema-1 path;
  - the tolerance difference (1e-9 new modules vs 1e-12 legacy optimizer, REPORTED in the Phase 2
    handoff).

## 13. Proposed production inventory procedure (Decision 4 — NOT authorized)

To be run only after explicit authorization, by the owner, against production:

1. Connect with a read-only role or with `default_transaction_read_only=on`; no credentials are
   shared with the agent.
2. Run count-only queries (no names, emails or payloads):
   - scenarios by schema and engine version;
   - schema-2 plans by `utilization_basis` presence;
   - schema-2 plans with any FEASIBLE candidate whose `costs.total.n` is below `replication_count`;
   - `workflow_des_current` jobs with and without separate rows and `wait_population`;
   - selected DES jobs by `execution`;
   - jobs whose scenario or dataset no longer exists;
   - schema-1 scenarios whose dataset is not the latest valid dataset.

   The local versions of these queries are in the Milestone 5/6 session scratchpad.
3. Record only the counts and the date; attach them to the release decision.

## 14. Required regression tests (Phase 2 specification)

| # | Requirement | Proposed test | Kind |
|---|---|---|---|
| 1 | v2 plans stored unchanged | After the bump, a stored v2 schedule and settings stay byte-identical through list, compare, workflow and report calls (pattern of `test_pre_day_des_engine_plan_is_unsupported_everywhere`) | backend |
| 2 | v2 cannot produce current Decisions | Selecting a v2 plan → 422 with the v2 reason; `decision/selected` and `decision` → refused / insufficient; the existing v2 chain is absent from current slots | backend |
| 3 | v3 plans complete the workflow | Optimize → save (v3 stamped) → select → DES → MC → validation → decision → report on a representative-day fixture and on a per-date fixture that stays OPTIMAL | backend |
| 4 | Recalculation creates new evidence | Recalculating scenario-30-like options creates a new scenario id; old row and jobs unchanged; new totals equal the v3 replay | backend |
| 5 | Old Current DES classified | Job without M3 → `MISSING_PROVENANCE`; with M3 on current dataset/setup → `CURRENT`; pooled Current DES needs no M3 | backend |
| 6 | Dataset replacement | After a new upload: `des_current`, `mc_current`, `validation_current`, schema-1 and schema-2 scenarios all non-current; Current MC from dataset A cannot feed validation (revised probe tests) | backend |
| 7 | Setup change | Every job and plan → `STALE_SETUP`; break apply path included | backend |
| 8 | Deleted references | Delete a dataset (cascade removes scenarios): selection/DES/MC/validation/decision jobs → `MISSING_DEPENDENCY`, never current; a job created strictly before a reused id's new record is refused (an equal or earlier recorded time is not, section 5.4) | backend |
| 9 | Schema-1 dataset scope | Scenario-12 fixture: not selectable, not decidable, report labelled historical | backend |
| 10 | Compare does not mix | Separate comparison returns no values for non-current plans in current positions; shared Compare hides totals of non-current scenarios; frontend test renders historical plans without numbers | backend + frontend |
| 11 | Reports preserve provenance | Evidence block present and correct; v2 wording fix; historical label on scenario/dataset reports | backend |
| 12 | Undefined stays undefined | D1/D5/D10 undefined costs remain null through compare, report and UI ("—" + reason) | backend + frontend |
| 13 | D1/D5/D10/D2 regressions | Existing suites (`test_separate_replication_costs`, `test_separate_period_costs`, `test_separate_routing_des_accounting`, `test_current_des_accounting`) unchanged and green; scenario 30 reference values | backend |
| 14 | Version compatibility | Save with absent / old / current client version under server stamping; stored version is always the server's; old-client result mismatch returns the drift error; contract test that no frontend source hard-codes a stale engine value | backend + frontend |
| 15 | Shared-queue protected | `test_shared_segments.py`, `test_shared_capacity.py`, `test_shared_continuous_des.py` green on the merged tree, isolation test included | backend |

Also kept: the Monte Carlo strict xfail stays xfail.

## 15. Open decisions for the product owner

- **OD-1** Historical access: additive history entries in `GET /workflow` and/or a read-only
  `GET /analyses/{id}/evidence/{job_id}` for the historical detail view.
  - **Decided by the product owner on 2026-09-30: NOT APPROVED for release G-A
    (`2026-09-26-generation-identity-contract.md` §6.1); DEFERRED, not permanently prohibited.**
  - G-A exposes current evidence only: no history entries in `GET /workflow`, no historical
    endpoint and no historical view. Plan Step 6 is out of scope for G-A.
  - Current mode shows "No current run for dataset #B" when no current run exists for the current
    dataset (section 9.2). The owner's reading of the section 5.1 release blocker applies.
  - Stored evidence is unchanged: historical jobs stay stored as today and nothing is deleted. The
    decision concerns UI and API exposure only.
- **OD-2** Optional `recalculated_from` lineage link on recalculated scenarios.
- **OD-3** Dataset restore: none / explicit current-dataset pointer (migration) / content
  equivalence.
- **OD-4** Server-authoritative engine version at save plus a distinct engine-drift error (API
  relaxation).
- **OD-5** Separate comparison response: move non-current plans out of `plans` into a value-free
  list (response shape change).
- **OD-6** Per-date v3 consequence (REPORTED: many per-date periods become UNSUPPORTED because of
  censoring): accept for release, or first specify a cost-under-censoring policy.
- **OD-7** Historical exports: allowed with labels, or not provided.
- **OD-8** Archived analyses: `own_analysis` does not block workflow runs on archived analyses
  (VERIFIED `analyses.py:75-79`); decide whether evidence may still be produced there.
- **OD-9** External callers of the stateless `/simulation/des*` endpoints receive D2's changed
  values; inform or version them.
- **OD-10** A frontend reload prompt for stale bundles.
- **OD-11** Keep v1 plans `UNSUPPORTED` (current behavior) or reclassify them as recalculable like
  v2.

## 16. Unknowns

- Production contents and scale; which environments ran unreleased D-repair builds.
- Whether Pages deploys can be held until Render is live.
- Tests on a merged tree (not executed; merging is not authorized).
- Whether any PDF/Excel produced from v2 plans is in circulation.
- D1 defect #2 (arrivals without completed service priced 0) in stored per-date plans — stored
  summaries cannot show it.
- External consumers of the stateless simulation API.
