# Plan: Analytical Versioning and Historical Evidence Integrity

Spec: `docs/superpowers/specs/2026-09-25-analytical-versioning-historical-evidence.md`.
Status: **Each step needs explicit authorization.** Original status line, now HISTORICAL: "Steps 1
and 2 implemented. Steps 3-13 PROPOSED — not started." Since then, Steps 3 and 4 were committed in
part (`bc303109`, `2038845b`) and Step 5 as INTERIM (`4db54722`), all on
`fix/d1-replication-costs`; release grouping is decided by OD-12 (Step 0).
Current status (2026-10-01): the G-A implementation milestone is COMPLETE on `port/g-a-stage1` at
`e7e3cdae` (Step 0, "G-A implementation completion record"). This is not a release: G8, CI,
PostgreSQL 16, production verification and G-B/G9 are not complete.

Base: a new branch from `fix/d1-replication-costs` (`d4bca6af`) unless a step says otherwise.
Release G-A is not built on this base: under OD-12 option (b)-G (Step 0) it is built on a
`main`-based line by a separate porting stage. That line is `port/g-a-stage1`, branched from `main`
at `2d063c91` (VERIFIED 2026-10-01).
Test numbers (T1-T15) refer to spec section 14. Every step ends with the full gates: `python -m
pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`, and in `frontend/` `npm test`, `npm run
typecheck`, `npm run lint`, `npm run build`, plus locale symmetry. The Monte Carlo strict xfail
stays untouched.

Global rules:
- One step per commit (or a small series); independent repairs are never folded together.
- No step rewrites, deletes or recomputes a stored record.
- The D-repair commits (D1, D5, D10, D2) are never released without steps 9 and 10.
- Nothing is pushed to `main` (production for Pages and Render) without a separate authorization.

---

## Step 0 — Approval gate

- Output: answers to OD-2 … OD-11 (spec section 15). OD-1 is decided: NOT APPROVED for release
  G-A / DEFERRED (2026-09-30, spec section 15). OD-12 is decided: option (b)-G (2026-09-30,
  below). OD-GA-C1 and OD-GA-C2 are decided (2026-10-01, below).
- Stop condition: written approval of the spec and of the chosen options. No code before this.

**OD-12 (release grouping) — DECIDED by the product owner on 2026-09-30: option (b)-G.**

The options as first written on 2026-09-25, before the generation-identity stages G1–G7 existed:
option (a), ship everything below in one release after Release A; option (b), ship steps 1-6
first from a branch off `main` (they only tighten eligibility), then rebase the D-repairs on top.
Option (b) resolves D7 sooner but needs a rebase of `fix/d1` over changed `workflow.py`. The
recommendation then was (a). It is superseded by the decision and no longer applies.

Option (b)-G adapts option (b) to the later stages. Release G-A:

- is built on a line based on `main`;
- includes:
  - Steps 1–5. Not steps 1–6: OD-1 is deferred for G-A, so Step 6 is excluded;
  - the D7 frontend compatibility work that spec section 5.1 requires before the D7 repair is
    deployed (the current-only state of spec section 9.2; Step 3);
  - the generation-identity stages G1 through G7 (`2026-09-26-generation-identity-contract.md`
    §14);
- excludes:
  - the D-repairs D1, D5, D10 and D2. They stay for a later line or a rebase;
  - engine v3 (Step 9), the M3 accounting marker (Step 10) and any other version-marker release
    work;
- keeps `GENERATION_ENFORCEMENT_ENABLED = False`.

A separate porting stage must build that line before G-A can exist. The committed Step and G
commits on `fix/d1-replication-costs` cannot be reused there as they are (VERIFIED 2026-09-30 at
`d771d1e7`):

- `SELECTED_DES_PER_PERIOD_EXECUTION` and `SELECTED_DES_CONTINUOUS_DAY_EXECUTION` were added by D10
  (`66ba238e`, `separate_optimization.py`) and do not exist on `main` (`1d3294cb`);
- Step 1's `tests/test_evidence_status.py` (from `84e502bd`, lines 615-616) imports both;
- Step 5's evidence policy in `backend/api/workflow.py` (from `4db54722`, line 725) lists both as
  the current selected-plan DES basis.

The port is not implemented. Whether it applies without conflicts is UNKNOWN, and so is any other
dependency of the Step or G commits on the D-series.

Update (2026-10-01; the paragraph above is HISTORICAL, as of 2026-09-30): the port is implemented
on `port/g-a-stage1` (`92d95bed` and the commits after it; see the completion record below). There
the two execution constants are labels only: `separate_optimization.py` defines them as exactly the
two `execution` strings that `main`'s `workflow.py` already writes. No D10 accounting change was
ported (VERIFIED 2026-10-01).

This is a release-grouping decision only. It does not decide the `main` base revision, or whether
Steps 4 and 5 ship in full or in their current interim scope. It authorizes no porting,
cherry-picking or rebasing, no frontend work, no Step 4 or 5 completion work, no deployment, no
gathering of the contract's §11.2 production facts, and neither G8 nor G9.

Unchanged by it:

- the D-repairs are never released without steps 9 and 10 (global rules above);
- the D7 repair is not deployed without its frontend compatibility work (spec section 5.1). That
  work is not implemented (as of 2026-09-30; implemented on `port/g-a-stage1` since `88c6f4da`, see
  the completion record below);
- spec section 5.4 (exact source identity) stays CONFLICTING: the spec and Step 5 below call it an
  open release blocker, while the contract (§6.2) has G-A ship with the defect present and closes
  it only with enforcement in G-B (as of 2026-09-30; resolved for G-A by OD-GA-C2 below, which adopts
  the contract's staging; the defect itself stays open);
- G8 (release G-A operations) stays BLOCKED. Its stop condition, any §11.2 fact UNKNOWN (contract
  §14), holds: every §11.2 production fact is UNKNOWN;
- G9 is not started;
- `GENERATION_ENFORCEMENT_ENABLED = False` (`backend/api/workflow.py:102`).

**OD-GA-C1 (CI and PostgreSQL 16) — DECIDED by the product owner on 2026-10-01.**

- Actual CI, including its PostgreSQL 16 `postgres-integration` job, is not a prerequisite of the
  G-A implementation milestone. That milestone is declared from the agreed implementation scope and
  its required local gates (Base paragraph above).
- CI and PostgreSQL 16 remain required release and integration assurance before any production or
  release action whose gates require them. G8 or a release may require them, or stronger evidence.
- Their status is unchanged: CI is NOT RUN and PostgreSQL 16 is NOT TESTED. Neither is claimed to
  pass, and CI is neither removed nor weakened.
- The pending "CI … gates" in the contract's stage statuses (contract header, §5.5, §16) are read
  under this decision.

**OD-GA-C2 (spec section 5.4 versus contract §6.2) — DECIDED by the product owner on 2026-10-01:
the contract's staging is adopted.**

- G-A keeps `GENERATION_ENFORCEMENT_ENABLED = False`.
- The exact-generation (source-identity) defect of spec section 5.4 stays an explicitly known OPEN
  defect. G-A does not claim it is repaired, and its severity is unchanged.
- The G-A implementation milestone may complete with the defect open, because the
  identity-enforcement repair belongs to G-B/G9 under the approved staged contract (§6.1, §6.2,
  §14).
- G-B/G9 must close the defect before the stage that requires exact-generation enforcement, and
  before any release criterion that requires exact identity is treated as met.
- "Release blocker" in spec section 5.4 and in Step 5 below is qualified accordingly: the defect
  blocks the stage that requires exact-generation enforcement, not the G-A implementation milestone.

**G-A implementation completion record (2026-10-01).**

"G-A implementation complete" means:

- the agreed G-A scope (OD-12 option (b)-G, with Steps 4 and 5 at the owner-approved final scope)
  exists on the G-A line;
- the required local gates (Base paragraph above) passed;
- no VERIFIED G-A implementation defect is open, except defects the staged contract explicitly
  defers (the section 5.4 defect, OD-GA-C2);
- `GENERATION_ENFORCEMENT_ENABLED = False`.

It does **not** mean that G-A is deployed or production-approved, that G8 is complete, that the
§11.2 production facts are known, that CI passed, that PostgreSQL 16 was tested, that section 5.4 is
fixed, or that G-B/G9 is complete.

Line: `port/g-a-stage1` at `e7e3cdae`, branched from `main` at `2d063c91`; local, no upstream, not
pushed. Commits: `92d95bed` (port of Steps 1–5 and G1–G7), `00582c11` (portable Step 5 id-reuse
tests), `88c6f4da` (D7 frontend current-only state), `822d5053` (cached workflow evidence dropped
when the current dataset changes), `32e00ce7` (Steps 4 and 5 at the final scope), `e7e3cdae`
(cached workflow evidence dropped when the Setup changes).

Scope, each COMPLETE (VERIFIED 2026-10-01 by inspecting `e7e3cdae` and by the tests below):

- Steps 1–5 at the owner-approved final scope:
  - 4c: scenario responses report `evidence_status` and `evidence_reasons`;
  - 4d/4e: the shared Compare view shows each scenario's status and reasons, gives totals, chart
    and selection to `CURRENT` scenarios only, names the dataset of its totals, and drops cached
    statuses when the dataset or the Setup changes;
  - 4f/5e: Simulate names an unavailable selection's status and reason;
  - 5d: a dependency refusal names the missing record when it is known (generation refusals keep
    their G5/G6 texts), and the Decision page shows the server's detail.
- D7 frontend: Current mode shows current runs only, and otherwise "No current run for dataset #B"
  (spec sections 5.1 and 9.2).
- G1–G7. On the port, migration 0005, `models.py`, `generation_guards.py`, `evidence_status.py`,
  `current_dataset.py`, `main.py`, `migration_status.py` and `datasets.py` are byte-identical to
  this branch at `bb9ada41`. `workflow.py` and `scenarios.py` differ because the D-repairs are
  excluded and 4c/5d were added.
- Dataset-change cache fix (`822d5053`) and Setup-change workflow-cache fix (`e7e3cdae`).
- Excluded work is absent: no D-repair test module, no engine v3 marker, no Step 6 endpoint and no
  Step 11 report change.
- Enforcement OFF: `GENERATION_ENFORCEMENT_ENABLED = False` (`backend/api/workflow.py:106` on the
  port), and no production code switches it on.

Verification:

- Full SQLite backend suite (VERIFIED 2026-10-01 at `e7e3cdae`, run without `-x`): 1699
  collected; 1580 passed, 118 skipped, 1 xfailed, 0 failed, 0 errors; 6 subtests passed.
  - Every skip requires `NOVAQ_TEST_DATABASE_URL` (PostgreSQL only).
  - The xfail is the Monte Carlo strict xfail.
- `ruff check .` and `mypy .` (166 source files) clean (VERIFIED 2026-10-01 at `e7e3cdae`).
- Frontend: 53 files / 388 tests passed, including the EN/TL locale symmetry test; `typecheck`,
  `lint` and `build` passed. VERIFIED 2026-10-01 on the tree committed as `e7e3cdae`: the gates ran
  before the commit, and the committed content was checked identical to the tested tree.
- Local PostgreSQL 18.6: REPORTED, not re-run on 2026-10-01.
  - Earlier sessions reported, on `port/g-a-stage1`, the Stage-1 PostgreSQL set at 666/666
    (`00582c11`) and a targeted 144 passed (`32e00ce7`).
  - This branch's contract §5.5 records the G1 migration's PostgreSQL 18.6 gate.
  - Migration 0005 and its tests on the port are byte-identical to this branch (VERIFIED
    2026-10-01).
- PostgreSQL 16: NOT TESTED. Actual CI: NOT RUN (OD-GA-C1). Live browser: NOT TESTED.

Still open after the milestone; none of these is resolved by this record:

- G8 (release G-A) is not started and stays BLOCKED: every §11.2 production fact, including the
  production revision, is UNKNOWN.
- G-B/G9 is not started, and the section 5.4 defect stays open (OD-GA-C2).
- Contract §1 rule 6 versus G7 (CONFLICTING).
- The contract's S0 ("pre-G backend (`4db54722` rules)") does not describe `main`, which the G-A
  line is based on: `4db54722` is not an ancestor of `main` at `2d063c91` (VERIFIED 2026-10-01).
  Recorded here, not resolved.
- The placement of historical report labels (4h) between Step 4's test T9 and Step 11.
- OD-2 … OD-11, Steps 6–13, the D-repairs and engine v3.

## Step 1 — Evidence status module (pure, not wired) — IMPLEMENTED

- Files: new `backend/api/evidence_status.py`, new `tests/test_evidence_status.py`, new
  `tests/fixtures/evidence_status_local_reference_2026-09-25.json`.
- The module holds:
  - the status enum and its precedence (spec 4.1);
  - reason codes, each mapped to exactly one status (the spec names statuses only);
  - the chain rule (4.2): every non-current upstream adds an `UPSTREAM_<status>` reason, so a
    downstream artifact is never more current than a required upstream one;
  - `classify(record, context)`: pure and deterministic. It uses no database, I/O, clock or
    application import. Reasons are de-duplicated and sorted, and every applicable reason is kept
    under the one primary status;
  - extraction helpers (`scenario_record`, `job_record`, `job_references`) that read recorded
    identity fields only. No cost, wait, utilization or `calculated_at` value is read.
- Version knowledge is supplied by the caller as an `EvidencePolicy` of `VersionFamily` values:
  current, historical and unsupported, with anything else unrecognized.
  - The module imports no engine-version constant and names no future version.
  - The registry of spec 3.3 is built by the caller at integration, from the application
    constants of that commit. Until step 9, the caller's plan family has
    `SEPARATE_DES_ENGINE_VERSION` (v2) as current.
- Refinements of the spec made in this step:
  - Spec 4.1's "unknown `execution`" is split. An absent value gives `VERSION_UNRECORDED`
    (`MISSING_PROVENANCE`). A recorded value the policy does not list gives `VERSION_UNRECOGNIZED`
    (`UNSUPPORTED`). An absent value is never read as an old version.
  - Fail-closed reasons beyond the spec's conditions:
    - `OWNER_UNRECORDED`;
    - `CREATION_TIME_UNRECORDED`;
    - `DEPENDENCY_UNASSESSED`, for a reference the caller did not resolve;
    - `RESULT_INCOMPLETE`.
  - Spec 4.4 lists reasons for scenario 30: replications per period and missing period costs.
    These are supporting facts from the Milestone 5 replay, not classifier reasons. The classifier
    classifies scenario 30 by its recorded engine string only. It is `CURRENT` until a v3 policy
    lists v2 as historical.
  - A Current DES job without M3 gets `VERSION_UNRECORDED` only when the caller supplies the M3
    requirement (`AccountingRequirement`). It is never labelled "pre-D2".
- Analytical implications: none.
- Persisted evidence: none; read-only computation.
- API: none. Frontend: none.
- Tests:
  - SYNTHETIC unit cases for:
    - every status and the full reason-to-status table;
    - every precedence pair;
    - the chain rule;
    - the Milestone 7 required cases.
  - RECORDED cases from a minimized read-only export of the local development database:
    - scenario 30;
    - scenario 12, with datasets 7 and 8;
    - Current DES jobs 34 and 12, with their supersession peers and the checked absence of
      datasets 17 and 23.
  - Scenarios 30 and 12 are also classified under a placeholder v3 policy that the test supplies;
    the placeholder is not an application value.
- Historical compatibility: not applicable (not wired).
- Engine version: none.
- Stop:
  - new tests green, and the full suite count equals the previous count plus the new tests;
  - no backend module other than `evidence_status.py` mentions it (a test checks this);
  - in-memory fault injection is caught by the tests.

## Step 2 — One current-dataset helper — IMPLEMENTED

- Files:
  - new `backend/api/current_dataset.py` (`resolve_current_dataset`);
  - `backend/api/workflow.py`: `_current_valid_dataset_id` delegates to it, and `_current_dataset`
    is unchanged and calls it;
  - `backend/api/analyses.py`: `current_analysis` replaces its inline copy with the resolver;
  - new `tests/test_current_dataset.py`.
  - `evidence_status.py` keeps no database access.
- Rule (verified identical in both former copies, unchanged): among the Analysis's datasets owned
  by the user, the highest id whose validation report has a truthy `ok`.
  - Ordering is by id, not `created_at`.
  - Legacy rows with `analysis_id` NULL and deleted rows are never selected.
  - Archival does not change the result.
- The resolver also tells "no dataset" apart from "no valid dataset". Existing callers keep their
  single 404 message for both.
- Analytical implications: none (identical rule).
- Persisted evidence: none. API: none. Frontend: none.
- Not changed: the frontend's own copy of the rule (`OptimizePage.tsx`, `latestValidDatasetId`), and
  scenario selection, Decision and Reports.
- Tests:
  - existing Current and workflow tests unchanged;
  - the new tests check the resolver, both former copies and `GET /analyses/{id}/current` against
    literal expectations.
- Historical compatibility: unchanged.
- Engine version: none.
- Stop: no test changes other than the added tests; full gates green.

## Step 3 — D7: Current kinds bound to the current dataset

- Files: `backend/api/workflow.py` (`_current_evidence`, `run_validation_current`),
  `tests/test_dataset_staleness_probe.py` (deliberate revision, spec 5.3), `SimulationPage.tsx`
  (Current mode), EN and TL locales.
- Analytical implications: none (no value recomputed).
- Persisted evidence: none written differently; old jobs untouched and no longer current.
- API: `des_current`, `mc_current` and `validation_current` return `null` when not `CURRENT` (same
  shape, stricter meaning). No history entries: OD-1 is not approved for release G-A and is
  deferred (spec section 15).
- Frontend (current evidence only; owner decision 2026-09-30, spec 5.1 and 9.2):
  - the "CURRENT configuration" badge and results appear only for current jobs;
  - when no current run exists for the current dataset: "No current run for dataset #B", with B the
    actual current dataset id. A never-run analysis and one whose earlier Current results are no
    longer current show this same state;
  - no historical entry, and no earlier dataset or run is named or exposed to explain the absence;
  - Validate stays unavailable unless the Current MC job is current.
- Tests: T6 (Current kinds), T7 (setup), T8 (dataset deleted); revised probe tests keep their
  dataset fingerprints.
- Historical compatibility: jobs on replaced datasets become `STALE_DATASET`; jobs on deleted
  datasets become `MISSING_DEPENDENCY`.
- Engine version: none.
- Stop: the revised probe tests are presented for review with the old and new assertions side by
  side; full gates green.
- Status (2026-10-01): COMPLETE for G-A on `port/g-a-stage1`.
  - The backend (`bc303109` on this branch) is ported in `92d95bed`.
  - The frontend current-only state is `88c6f4da`.
  - Cached workflow evidence is dropped when the current dataset changes (`822d5053`) or the Setup
    changes (`e7e3cdae`), so no page shows a previous dataset's or Setup's evidence as current.

## Step 4 — Schema-1 dataset currentness

- Files: `backend/api/workflow.py` (`_own_verified_scenario` schema-1 path, `_selected_scenario`,
  `create_decision`, `current_decision_for_report`), `backend/api/scenarios.py` and
  `backend/api/analyses.py` (scenario list outputs), `frontend/src/api/scenarios.ts`,
  `ComparisonPage.tsx` (shared view), locales.
- Analytical implications: none.
- Persisted evidence: none changed.
- API: additive `evidence_status` and `evidence_reasons` on scenario list/get outputs; selecting a
  non-current schema-1 scenario returns 422 with the reason.
- Frontend:
  - the shared Compare view shows each scenario's status;
  - totals and "Select for simulation" only for `CURRENT` scenarios;
  - "current total cost" names its dataset.
- Tests: T9 (scenario-12 fixture), T10 (shared part), revised
  `test_shared_scenario_evidence_stays_pinned_to_dataset_a`.
- Historical compatibility: scenario 12-type rows become `STALE_DATASET`, still stored and viewable.
- Engine version: none.
- Stop: full gates; a local read-only check that scenario 12 would be reported `STALE_DATASET` and
  scenario 13 `CURRENT` (offline, no DB writes).
- Status (2026-10-01): COMPLETE at the owner-approved final scope on `port/g-a-stage1` (`92d95bed`,
  `32e00ce7`): 4c and 4d/4e (Step 0, completion record). The "report labelled historical" clause of
  T9 is not implemented: historical report labels (4h) and their placement between T9 and Step 11
  stay open (Step 0).

## Step 5 — Missing-dependency guard

- Files: `backend/api/workflow.py` (chain resolution: selection, DES, MC, validation, decision),
  `backend/api/reports.py` (`_selected_report_chain`).
- Analytical implications: none.
- Persisted evidence: none.
- API: jobs referencing deleted or later-created scenarios/datasets never populate current slots or
  report chains; error details name the missing dependency.
- Frontend: reason text for "source deleted".
- Tests: T8 (dataset delete cascade, deleted scenario selection such as local analysis 21, id-reuse
  ordering guard on SQLite).
- Historical compatibility: orphaned jobs become `MISSING_DEPENDENCY`.
- Engine version: none.
- Stop: full gates.
- Status (2026-09-26): INTERIM, committed locally.
  - Done:
    - one dependency gate across every workflow slot, both Decision endpoints and the
      selected-plan report chain;
    - `decision_stale` keeps its pre-Step-5 meaning when no eligible scenario is selected
      (Option A).
  - Not done:
    - the error detail is one generic `MISSING_DEPENDENCY_DETAIL`, not per dependency;
    - there is no frontend "source deleted" text.
  - **Open release blocker:** exact source identity (spec section 5.4). The `created_at` guard
    is not an exact-generation solution, and the generation-token mechanism is approved in
    principle only.
- Status (2026-10-01): COMPLETE at the owner-approved final scope on `port/g-a-stage1` (`92d95bed`,
  `00582c11`, `32e00ce7`). The INTERIM status above is HISTORICAL.
  - Both "Not done" items are done: 5d (a dependency refusal names the missing record when it is
    known, for example "dataset #N") and 4f/5e (Simulate shows an unavailable selection's status,
    such as "Source deleted", and its reason).
  - The open release blocker above is qualified by OD-GA-C2 (Step 0), not withdrawn. The
    exact-source-identity defect stays OPEN and G-A does not repair it. It blocks the stage that
    requires exact-generation enforcement (G-B/G9), not the G-A implementation milestone.
  - The generation-token mechanism is now implemented as G1–G7, with enforcement off (contract §14).

## Step 6 — Historical read-only access (only if OD-1 approves)

- Status (2026-09-30): OUT OF SCOPE FOR RELEASE G-A. OD-1 is not approved for G-A and is deferred,
  not permanently prohibited (spec section 15). Not implemented.
- Files: `backend/api/workflow.py` or a new read-only router, frontend historical view component,
  locales.
- Analytical implications: none; stored values only.
- Persisted evidence: none.
- API: additive read-only endpoint(s), returning payload plus status and reasons.
- Frontend: bannered historical view, no actions; undefined values shown as "—" with reason.
- Tests: T1 (values byte-identical to storage), T10 (never rendered in current slots), T12.
- Historical compatibility: this is the viewability guarantee of Decision 2.
- Engine version: none.
- Stop: full gates; no current-slot rendering path accepts a historical payload (component tests).

## Step 7 — Server-authoritative engine version at save (Release A; only if OD-4 approves)

- Base: a branch from `main`. Original rationale, now HISTORICAL and no longer sufficient:
  "`scenarios.py` is not changed by the D-repair branch, so no conflict". The D-repair commits
  (D1, D5, D10, D2) do not change `scenarios.py` (VERIFIED), but G2 (`f495f0bd`) does, and
  OD-12 option (b)-G places G2 on the `main`-based G-A line. Step 7 also plans to change
  `scenarios.py` (Files below). Whether the two conflict is UNKNOWN until that line is built or
  the changes are compared.
- Files: `backend/api/scenarios.py` (`_verify_separate_calculation`, `_verify_calculation`,
  stamping in `create_scenario`), tests.
- Analytical implications: none; results are still the server's recomputation.
- Persisted evidence: the stored engine value is always the server constant (identical to today's
  value, because today it must equal it).
- API: the client `engine_version` becomes optional and advisory; a stale value or a recomputation
  mismatch returns a distinct "engine updated, rerun" error.
- Frontend: none yet.
- Tests: T14 (absent, stale and current client values; stored value = server constant; mismatch
  error).
- Historical compatibility: unchanged.
- Engine version: none.
- Stop: gates green. Released and verified on Render (separate authorization) **before** the
  release containing step 9.

## Step 8 — Frontend stops sending the engine version (after Release A is live)

- Files: `frontend/src/pages/OptimizePage.tsx` (remove the hard-coded strings at 669 and 713),
  tests.
- API, analytical and persisted implications: none (server-authoritative after step 7).
- Tests: T14 contract test (no hard-coded engine value in frontend sources).
- Engine version: none.
- Stop: gates green.

## Step 9 — Separate plan engine v3 (requires D1, D5, D10 present)

- Files:
  - `separate_optimization.py` (M1 constant; M2 per-date `utilization_basis`);
  - the caller's evidence policy, built where the module is integrated and not inside
    `evidence_status.py`: v3 current, v2 historical-recalculable, v1 per OD-11;
  - `workflow.py` (`_separate_schedule_problem` reasons, `separate_comparison` split per OD-5);
  - `reports.py` / `separate_report.py` (pre-D5 wording, spec section 10);
  - `SimulationPage.tsx` (reason-specific selected-plan messages);
  - `ComparisonPage.tsx` (current plans only in the value table);
  - `OptimizePage.tsx` (only if step 8 was not done: its constant must change in the same commit);
  - locales;
  - tests.
- Analytical implications: none beyond D1/D5/D10 already committed; this step changes identity
  only.
- Persisted evidence: new plans store v3; v2 rows untouched.
- API: plan validity reasons distinguish engine version from dataset or setup; comparison response
  per OD-5.
- Frontend: historical plans listed without values; reasons named.
- Tests:
  - T1, T2, T3, T4, T10, T11, T12, T13;
  - scenario-30 acceptance: a v3 recalculation reproduces 5422.62562890955 and the per-period
    values in spec 7.2, and the old row stays byte-identical.
- Historical compatibility: v2 → `HISTORICAL_REQUIRES_RECALCULATION` or a stale status; their
  chains are inherited, never current.
- Engine version: `…separate-des-v2` → `…separate-des-v3`.
- Stop: gates green; the scenario-30 acceptance values reproduced in the test log.

## Step 10 — Current DES accounting marker (requires D2 present)

- Files: `backend/queueing_engine/simulation/simulation.py` (constant next to
  `_simulate_parallel_segments_core`), `workflow.py` (stamp M3 in `run_des_current` and in legacy
  `run_des` when separate rows are present), the caller's evidence policy (it supplies the M3
  `AccountingRequirement`), `SimulationPage.tsx` (legacy note driven by the status), tests.
- Analytical implications: none (D2 already committed).
- Persisted evidence: new Current separate DES jobs carry M3; old jobs untouched.
- API: additive param in stored job params.
- Frontend: the status replaces the `wait_population` inference as the source of the legacy note.
- Tests: T5, including a pooled Current DES job needing no marker.
- Historical compatibility: unmarked separate Current DES jobs → `MISSING_PROVENANCE`.
- Engine version: none (a new accounting marker, not a bump).
- Stop: gates green; selected-plan DES and shared-queue outputs byte-identical before and after
  (trace comparison, as in the D2 verification).

## Step 11 — Report evidence identity and historical labels

- Files: `backend/api/reports.py`, `backend/reports/separate_report.py`,
  `backend/reports/report_export.py`, `ReportsPage.tsx`, locales.
- Analytical implications: none.
- Persisted evidence: none; exports are generated on request.
- API: the preview model gains the evidence block (additive).
- Frontend: the preview shows the block and status.
- Tests: T11 (PDF text and Excel cells contain the evidence block; scenario and dataset reports
  labelled historical when not current).
- Historical compatibility: no historical file is regenerated under its original identity.
- Engine version: none.
- Stop: gates green.

## Step 12 — Documentation

- Files: `handoff.md`, `memory.md` (records of D1, D5, D10, D2, v3, the currentness policy and the
  marker).
- Stop: the docs match the committed code (verified by reading, no claims beyond tests).

## Step 13 — Integration and release (each action separately authorized)

Status (2026-09-30): written for option (a) and SUPERSEDED for release G-A by OD-12 option (b)-G
(Step 0). G-A is not produced by item 1's merge: a separate porting stage builds it on a
`main`-based line, and the contract's §11.2 order applies to its release (stage G8, BLOCKED).
Whether items 2-6 also apply to G-A, and how this step applies to the later line carrying the
D-repairs, is not decided.

1. Merge the result of steps 1-12 with `fix/d1` on an integration branch.
   `feat/shared-queue-segments` merges independently: zero path overlap (VERIFIED); T15 must pass
   on the merged tree.
2. Run the full gates on the merged tree.
3. Run the production inventory (spec section 13) with the owner's authorization, and record the
   counts.
4. Test on a Pages branch preview. The Render preview capability is UNKNOWN.
5. Push `main`, preferably with Render live before Pages.
6. Verify post-deploy:
   - a v2 plan appears as historical;
   - a new v3 save works;
   - Current DES is dataset-bound.

Release order: OD-12 option (b)-G was chosen on 2026-09-30 (Step 0). The order "Release A
(step 7), then Release B (steps 1-6, 8-12 with the D-repairs)" was option (a) and no longer
applies.

- Release G-A, from a `main`-based line built by a separate porting stage: Steps 1–5, the required
  D7 frontend compatibility work and G1–G7, with `GENERATION_ENFORCEMENT_ENABLED = False`. Step 6
  is excluded (OD-1 deferred).
- The D-repairs (D1, D5, D10, D2) follow on a later line or rebase, and only together with their
  version markers (steps 9 and 10).
- Step 7 (Release A) still ships before the release containing step 9. OD-12 does not set its
  order relative to G-A, or the grouping of steps 8, 11 and 12.

The intent is that no point in this order makes historical or incompatible evidence eligible for
a current Decision or report (PROPOSED. As of 2026-10-01 the ported line is built and passes its
local gates (Step 0, completion record), but it is not released, its CI has not run and no deploy
skew has been exercised):

- Release A changes no eligibility.
- G-A only tightens eligibility: Steps 1–5 add refusals, and G1–G7 with enforcement off stamp
  tokens and add the OD-G2 write refusals (contract §6.2, §8).
- The D-repairs ship together with their version markers.
- During deploy skew, the server enforces eligibility and new clients fail closed.
