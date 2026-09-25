# Plan: Analytical Versioning and Historical Evidence Integrity

Spec: `docs/superpowers/specs/2026-09-25-analytical-versioning-historical-evidence.md`.
Status: **Steps 1 and 2 implemented. Steps 3-13 PROPOSED — not started. Each step needs explicit
authorization.**

Base: a new branch from `fix/d1-replication-costs` (`d4bca6af`) unless a step says otherwise.
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

- Output: answers to OD-1 … OD-11 (spec section 15) and to OD-12 below.
- Stop condition: written approval of the spec and of the chosen options. No code before this.

**OD-12 (release grouping).** Option (a): ship everything below in one release after Release A.
Option (b): ship steps 1-6 first from a branch off `main` (they only tighten eligibility), then
rebase the D-repairs on top. Option (b) resolves D7 sooner but needs a rebase of `fix/d1` over
changed `workflow.py`. Recommended: (a).

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
  shape, stricter meaning). With OD-1, additive history entries (identity, status, reasons, no
  values).
- Frontend:
  - the "CURRENT configuration" badge and results appear only for current jobs;
  - otherwise "No current run for dataset #N";
  - Validate stays disabled without a current Current MC job.
- Tests: T6 (Current kinds), T7 (setup), T8 (dataset deleted); revised probe tests keep their
  dataset fingerprints.
- Historical compatibility: jobs on replaced datasets become `STALE_DATASET`; jobs on deleted
  datasets become `MISSING_DEPENDENCY`.
- Engine version: none.
- Stop: the revised probe tests are presented for review with the old and new assertions side by
  side; full gates green.

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

## Step 6 — Historical read-only access (only if OD-1 approves)

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

- Base: a branch from `main` (`scenarios.py` is not changed by the D-repair branch, so no conflict).
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

Release order: Release A (step 7), then Release B (steps 1-6, 8-12 with the D-repairs), unless
OD-12 (b) is chosen. No point in this order makes historical or incompatible evidence eligible
for a current Decision or report:

- Release A changes no eligibility.
- Release B only tightens eligibility, and the D-repairs ship together with their version markers.
- During deploy skew, the server enforces eligibility and new clients fail closed.
