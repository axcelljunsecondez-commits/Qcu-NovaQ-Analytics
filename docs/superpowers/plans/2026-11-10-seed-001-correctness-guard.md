# SEED-001 correctness guard: bounded implementation plan

Date: 2026-11-10. **Owner-approved objective/outcome; independent written-plan/derivation and bounded Phase 1 reference reviews PASS; Phase 2A/final verification pending.** Governing contract: [correctness-guard specification](../specs/2026-11-10-seed-001-correctness-guard.md). Implement conservative truthful assessment at the existing budget; useful precision stays OPEN. No commit, push or deployment is authorized by this plan.

## Baseline and ownership

Checkout: `output/seed-001-repair-20261110/worktree`; branch `codex/seed-001-repair-20261110`; starting HEAD `d87cb514e3a41af2aa7a82c6c00446e3aa4e2745`; tree `9f472b16a63aaff91221de3d80fdf84f16960a0c`. Preserve dirty root/unowned work and the separate UI worktree. Root Vongola V2 instructions supplied by the owner govern role boundaries. One writer per application scope.

- Chrome owns only these two specification/plan files. No application/test implementation or permanent memory updates by Chrome.
- Hayato owns the application/test changes listed below after capability preflight and the parent's technical handoff. Do not revert others' changes or edit a newly discovered consumer without naming its justified scope to the parent first.
- Kyoya is the independent reviewer, with source/Git/command/output access verified separately. A review PASS covers its named evidence, not production release authority.
- Parent owns evidence coordination and supplied the owner's exact approved single shared EN/TL notice, recorded in the specification. Apply that text verbatim; no invented production text/placeholders.

## Writable application and test scope

Backend implementation:

- New `backend/queueing_engine/statistics/selected_load_uncertainty.py`: canonical v1 identifier, immutable bounded cached settings, strict summary/bound/stress helpers and reasons. Use existing dependencies; no installation or mathematical changes elsewhere.
- `backend/api/workflow.py`: summarize existing selected DES replications, record the additive method/assessment, preserve raw MC, apply selected-only validation, propagate method identity/summary and enforce selected-chain compatibility.
- `backend/api/evidence_status.py`: optional supplied method family and selected-job params/result version requirements; preserve generic classifier/status precedence and all unrelated policies.
- `backend/api/reports.py`, `backend/reports/full_report.py`, `backend/reports/separate_report.py`, `backend/reports/selected_scope.py`, `backend/reports/report_export.py`: only actual affected selected-chain/model whitelists, recorded method/assessment provenance and truthful conditional notice. Legacy Excel currently whitelists provenance fields and requires the narrow addition; its PDF branch already iterates model provenance. No speculative new endpoint/module or report redesign.
- Read-only verified B8 consumers: `backend/api/plan_reports.py` already delegates its Separate full-report chain to `_selected_report_chain` and passes full stored jobs; `backend/reports/plan_report.py` and `backend/reports/report_pdf.py` already iterate existing Checks rows. No edits to these files are needed for the approved minimal projection. Shared and plan-only paths remain unchanged.

Frontend implementation:

- `frontend/src/api/types.ts`: additive selected method/assessment types. `frontend/src/api/reports.ts`: type-only optional recorded `selected_load_method` on `ReportPreview.model.decision`, whose type lives here rather than in types.ts. `frontend/src/api/workflow.ts` only if its existing exported/imported contract needs the additive types; do not change requests.
- `frontend/src/components/queueSimulation/ChecksView.tsx`, `frontend/src/components/decision/DecisionEndpoint.tsx`, `frontend/src/pages/ReportsPage.tsx`: conditional current/legacy notices, correct raw-MC versus supported validation status, existing status labels and minimal accessible display.
- Both `frontend/public/locales/{en,tl}/translation.json`: only the single reviewed notice key and any separately identified/reviewed unavoidable gap. Preserve existing approved wording and key symmetry.

Verification:

- New `tests/test_selected_load_uncertainty.py` for the pure independent references and domain/boundary behavior.
- Existing `tests/test_selected_mc_load.py`, `tests/test_selected_plan_simulation.py`, `tests/test_selected_plan_validation.py`, `tests/test_selected_plan_decision.py`, `tests/test_model_aware_workflow.py`, `tests/test_evidence_status.py`, `tests/test_evidence_status_generation.py`, `tests/test_report_evidence_fixes.py`, `tests/test_generation_decision_report.py`, `tests/test_separate_report.py`, `tests/test_b8_full_report.py` and existing affected frontend consumer tests. Verify these paths and actual ownership before modifications; use new focused tests when no existing one owns the behavior.
- Existing fixtures that represent current selected evidence may gain valid additive metadata/assessments necessary for the approved contract. Do not universally stamp legacy fixtures as v1, hide missingness, weaken assertions or alter expected raw MC/math. The original five-seed fixture/assertions remain byte-for-byte; marker-only reconciliation follows the specification's evidence gate.

Protected/read-only: queue formulas/model selection, DES/routing kernels and RNG helpers, simulation/MC/Wilson implementations, optimization/costing, migrations/models/auth/security/deployment configuration, package manifests/lockfiles, replay/time/reducer machinery, unrelated Current/shared/version families, wording-policy source/test, UI redesign work and operational records. Changes outside this list require evidence and an explicit scoped handoff; a failed test grants no permission to cross a protected boundary.

## Execution sequence and observable gates

### 0. Rebaseline and independently review the contract

Confirm branch/HEAD/status and actual permitted paths. Record source hashes and the historical failed/passed receipts. Verify the actual project venv and package versions before commands. Read qualified revision-2 derivation, preregistration, numeric checks, corrected stream records and independent verification. Confirm the current static/continuous/per-date source mapping and current MC configuration still meet the specified assumptions. Use the accepted fixed R2 Hoeffding rule; no repeat of the rejected method or wholesale old research.

Gate: bounded spec/ownership and method assumptions are independently reviewable. Unsupported mode/evidence remains insufficient; missing proof or a conflicting requirement stops only dependent integration. No speculative PASS.

### 1. Implement and reference-check pure inference

Implement settings, strict validation, summary bounds and stable monotone conditional-stress propagation exactly as specified. V1 supports reproducible nonnegative base seeds and n2..20; None/negative/n1 abstain without changing raw requests. Reuse the input-only cutoff and qualified Lambda0..1000 domain. Do not claim full-width optimality. Include exact zero/one stress branches so the old `(rho=1e16, threshold=1)` cancellation bug is absent. An empty required family is insufficient, never a vacuous pass.

Independent tests must not import the candidate to manufacture expected values: use Decimal positive Poisson sums/remainder checks, rational clipped-uniform area references and quadrature. Cover invalid types/booleans/noninteger counts, zero/observed-zero, durations, arbitrary identities, sparse/rare counts, mean bounds, monotonicity, unrounded cap equality, extreme rho and unsupported seeds/configuration. A small immutable settings cache must preserve results.

Gate: actual numerical/reference outputs and explicit qualifications, reviewed independently. Any unexplained discrepancy stops workflow integration. Keep prior failures and numerical-domain abstentions visible.

Actual bounded Phase 1 gate: Kyoya's `../evidence/kyoya-independent-references/phase1-closure-review.json` records PASS on 360 Fraction-neighbor enclosures, 9 rational and 12 Decimal-tail references; the inspected pytest log records 125 passed. Helper/test hashes are recorded in the specification. This closes the named pure-helper reference gate only; it is not a workflow, full-application or universal numerical PASS.

### 2. Capture summaries and integrate the selected-only guard

Add one measurement pass over the already executed selected DES replications; do not add runs, alter draw order, change raw totals/means or first replay data. Build the fixed required family from the saved schedule. Preserve failed/missing provenance and actual mode/rate/horizon mapping. Persist the specified summary/version schema in existing JSON and preserve the result-size guard.

Run original selected MC unchanged, then add its separate assessed probability bounds using the actual saved/resolved threshold/cap and supported perturbation metadata. Apply the new selected-only verdict after existing evidence-quality gates. Record `raw_mc_verdict` separately; raw point FAIL cannot alone establish supported failure. Keep the global `_separate_validation_verdict` Current/shared default behavior unchanged. Existing Decision taxonomy consumes the new selected verdict without new categories or re-optimization.

Gate: raw first trace, raw means, MC result/status/CI, seeds/RNG call pattern and protected numerical paths are unchanged; all three selected execution modes and known pause/date cases have executed evidence. Explicit cases establish guard FAIL with raw PASS, guard PASS with raw FAIL, overlap with raw FAIL, inadequate raw evidence, unsupported/invalid DES or MC and empty-family insufficiency. Complete summaries are present; missing/invalid evidence does not become zero or pass.

### 3. Enforce method freshness across actual consumers

Enable the supplied selected-load version family for the four existing selected job types. Method requirements, ordinary references and upstream DFS must use the same selected-producer predicate. In addition to existing engine/SELECTED markers, recover the audited producers from selected DES execution identity and typed direct links: MC->DES, validation->DES+MC, Decision->validation+DES+MC. Do not infer selected identity from metrics or scenario ID alone. Missing method remains missing provenance, unknown versions unsupported, recognized obsolete versions rerun-required; retain historical records/export files and unrelated Current/shared evidence.

For fully erased producer identity, use default-OFF per-call `selected_load_context` only in `_current_evidence` and `require_dependencies_current` after existing verified selected Separate scenario/dataset resolution. Preserve ordinary ownership/setup/generation/chronology/reference checks and propagate the same policy through DFS. Shared/Current and None-policy callers remain unchanged. Scenario binding uses existing params JSON and resolved ownership; do not invent a `Job.scenario_id` column or add a migration. Use existing refusal shapes/status vocabulary.

Verify endpoint and workflow-slot behavior together; direct MC/validation/Decision/new report generation cannot bypass a stale/missing assessment. Test cross-owner/scenario/dataset/method links and corrupted marker mismatches with isolated databases. No migration or automatic operational-data rewrite.

Gate: actual currentness/refusal and preservation tests pass, including new full-report paths and legacy evidence. Do not claim current UI evidence merely because the endpoint refused it.

Progress, not a final gate: earlier lost-engine and marker-erasure negatives failed and were retained; recognition and default-OFF verified consumer context were refined in the actual source. The combined erasure-control log now records 10 passed/41 deselected. Parent-reported Phase 2A checks are 392 passed across 11 focused files with the original five-seed case deselected, plus scoped Ruff/mypy passes. The original native `--runxfail` run and independent Phase 2A source review remain pending at this update. Report/frontend integration has not started; no passing final-application claim follows.

### 4. Finish only affected displays/reports and reviewed wording

Apply the one exact owner-approved EN/TL notice recorded in the specification under `decision.plain.selected_load_assessment_notice`. Reuse old raw-MC body/details and status labels where accurate; the old Not-checked label is legacy-only. A completed inconclusive guard must not show a generic missing-DES/MC instruction. The existing MC column reflects raw MC; validation/Decision reflects supported inference. Carry method/confidence/bounds/reasons in selected report detail/provenance data without redesigning reports or introducing unreviewed labels.

For B8 preview/PDF/Excel, preserve the three existing summary Checks rows and append detail rows using the existing `Results check` label. Each Settings cell contains compact JSON for one pair's exact recorded method/family/rate/probability bounds and reasons, and Outcome contains its stored assessment status. Do not put the entire family into one cell, compute bounds again, add a section/table/chart or change renderer code. Legacy model provenance uses scalar-safe per-pair detail entries, and the existing Excel provenance writer receives only the required additional entries after its current fields. The model/preview retains the structured assessment. Generic scenario reports continue to obtain current selected Decisions through `current_decision_for_report`/`_current_evidence`; test method refusal there rather than creating an independent report currentness policy.

Gate: reviewed text applied symmetrically; actual consumer tests/browser states cover assessed, insufficient, unsupported and legacy/refusal cases. No invented translation, misleading checked/complete label, new chart or unrelated layout change. Inspect PDF/Excel outputs; state native/qualified-language checks NOT TESTED unless executed.

### 5. Verify the final candidate and return it for owner review

Run the original five-seed regression with `--runxfail`, unchanged fixture/assertions. Only after all assertions genuinely pass and independent review confirms may the obsolete strict-xfail marker/reason be removed; run it normally afterward. A failure remains a failure. Preserve old receipts and explicitly keep useful precision separate/open. Execute the specified disjoint holdouts without favorable-batch selection; reuse established known-mean calibration unless changed source/assumptions or unresolved concerns invalidate it.

Measure actual complete normal-fixture workflow time, assessment overhead and complete serialized job sizes near the existing cap. No new count ceiling, background system, timeout promise or invented production SLA. Report refusals and remaining scale unknowns.

Final required commands using the verified project runtime: `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`; in frontend, `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`. Use the project venv executable, not an unrelated system interpreter; record actual environments and output. Place standalone helpers/logs/evidence under the sibling `output/seed-001-repair-20261110/evidence/`, outside candidate source scans. Do not install dependencies or conceal platform limitations.

Kyoya inspects final source/diff/new files, independent references and actual outputs. Review the exact final file list and protected-path hashes. Return a bounded result distinguishing correctness-guard implementation, the bounded regression, useful-precision OPEN status, failed/skipped/not-run gates and production NOT TESTED. No commit/push/deploy. Approval for this implementation is not release authorization.

## Remaining explicit boundary

No further product or wording choice is needed to begin the approved conservative guard. The single notice is approved verbatim; its actual application, key symmetry and display/report verification remain required. Any genuinely additional wording gap returns to the parent rather than being invented. A later useful-precision effort needs separately chosen precision/runtime criteria; the old 90%/.02 research yardsticks are not silently adopted as business requirements. This plan does not pretend to know a minimum sufficient replication count or full production performance.
