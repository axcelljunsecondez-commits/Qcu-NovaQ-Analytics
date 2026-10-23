# Selected Separate Decision: scope disclosure and context correction

Status: APPROVED SPECIFICATION following the owner's approval of the prepared bounded correction. Local implementation and actual verification are recorded in docs/superpowers/reports/2026-10-23-selected-decision-scope-implementation.md. No statistical-method integration or deployment is authorized by this specification. Existing supervisor changes and the numerical seed finding remain separate.

## 1. Purpose and verified evidence

Correct two concrete interpretation/presentation defects without pretending that a new numerical method has passed. Preserve the current configured-run calculations and expose their actual scope.

Candidate: C:/Users/Administrator/.codex/worktrees/novaq-release/NovaQ, branch codex/supervisor-schedule-20261023, HEAD 151486ee04147f013857f69fe8ce77d899388660. Primary-checkout main is different, at 6093d78a5874d8cbdfa0026e9c25bdb5ddc70881.

| Finding | VERIFIED evidence in candidate source | Proposed outcome |
|---|---|---|
| SCOPE-001: a selected conditional result is presented as if accepting cost is the only remaining consideration | backend/api/workflow.py:3391-3402 says all validation checks passed and to adopt only with cost acceptance. EN translation.json:710 says to use the plan only if accepting cost. workflow.py:2812-2843 stores DES-derived mean loads/replication metadata, not a completed assessment of uncertainty in those means. | Qualify this as a saved configured-run result, preserve the cost limitation, and disclose that uncertainty in the average load has not been assessed. Apply consistently to the UI and both final-report paths. |
| CONTEXT-001: Separate data can receive a Shared cost explanation | frontend/src/components/decision/DecisionEndpoint.tsx:58 calls plainDecision with separate:false. DecisionEndpointPage already computes isSeparate but passes no line-context prop. router.tsx:134 exposes the page. | Pass the actual line context and selected facts; never say Separate costs more than Current when comparable savings are unavailable. |

Executed source/pure-function probe: primary-checkout output/selected-decision-scope-spec-20261023/source_probe.cjs and source-probe.json. It reads the actual TypeScript AST and runs the actual formatter after transpilation. With the hardcoded false flag it returns "The plan passed every check, but it costs more than today." With Separate context it selects the unavailable-savings message. This is not a browser test or an implemented repair.

The strings/control flow are VERIFIED. The risk of a reader interpreting cost acceptance as the sole remaining barrier is an INFERRED communication risk, not a measured user-study outcome. The backend already has a generic warning about simulated versus observed outcomes; this proposal makes the distinct unassessed mean-load uncertainty explicit instead of claiming that no warning exists.

Export consumers verified: backend/reports/full_report.py:167-192; separate_report.py:314-321; backend/api/plan_reports.py:99-107; report_pdf.py:173-178; plan_report.py:454-459; report_export.py:281-284 and :499-506. The qualification must reach both supported final Separate PDF/Excel paths, their previews and the Reports page.

## 2. Preserve the statistical distinctions

- **Configured-run verdict:** current raw MC and validation result conditional on supplied DES-derived average loads, model inputs and perturbation assumptions. Preserve exact counts/comparisons, Wilson intervals, adequacy, status, precedence and evidence links.
- **Uncertainty in the estimated average load:** NOT ASSESSED by the current application. Perturbing load around a supplied average is not an uncertainty interval for that average. MC adequacy=true does not establish average-load precision.
- **Measured insufficient uncertainty result:** may exist only after a separately approved interval method is actually applied and cannot classify a pair. Do not synthesize this state from "not assessed."
- **Operational safety / observed outcomes:** not established by these modeled checks. Preserve the existing provenance warning.

The three insufficient pairs from the offline 5,120-run study are reference cases only: 10:00-11:00/cashier_3; 13:00-14:00/cashier_2; 13:00-14:00/cashier_3. Do not hardcode them, import the study into a user analysis or show "57 passed, 3 uncertain" for a live 20-run result. The researched n=20 bound classified none of the 60 fixture pairs. Neither that all-insufficient gate nor a larger run limit is approved for integration.

Authority for actual research results: docs/superpowers/reports/2026-10-23-selected-load-budget-study.md. Its combined precision/usefulness yardsticks were not met. It did not establish that a particular new statistical method is necessary, sufficient or approved.

## 3. Phase A: bounded correction recommended next

This phase fixes scope disclosure and line-context wiring. It changes no analytical outcome or Decision taxonomy and cannot close numerical seed sensitivity.

| Persisted selected evidence | Existing behavior, preserved | Qualified presentation |
|---|---|---|
| All current/adequate raw checks pass; DES conserves customers | conditional | Saved checks passed for this run; comparable savings remain unavailable; review estimated loads and costs. |
| A valid raw check fails | revise | This saved run did not pass the recorded checks/periods. Preserve actual failed pairs/counts, without claiming a load-robust or observed operational failure. |
| Missing/unsupported/inadequate/conservation-inconsistent evidence | Existing insufficient_evidence or refusal | Preserve the actual reason. Do not replace it with a generic uncertainty message or missing-to-zero data. |
| Stale, wrong-owner or mismatched evidence | Existing refusal/stale behavior | No fresh recommendation; scope copy must not hide a refusal. |

Adopt remains unavailable for Separate plans under current economics. Shared and Current workflows retain their existing text/statuses/math. Displaying a qualifier triggers no DES/MC/optimization run.

### 3.1 Simple English copy

Show one compact notice next to the selected Separate result, outside collapsed Details. Keep the technical explanation in Details/exports. No new modal, screen, parameter or educational panel.

- Conditional: "Saved checks passed for this run. Savings cannot be compared. Review the estimated loads and costs before using the plan."
- Failed periods: "This saved run did not pass in {{periods}}. Review the plan and estimated loads."
- Failed count: "This saved run did not pass {{failed}} of {{total}} checks. Review the plan and estimated loads."
- Failed generic: "This saved run did not pass. Review the plan and estimated loads."
- Notice label: "Load estimate uncertainty: Not checked."
- Notice body: "The variation test changes the load around a simulation average. It does not measure how much that average may change."
- Technical clarification: "Repeating the simulation with another seed can change its mean load and the configured-run result. This does not establish seed stability or future operational safety."

Do not say "load variation was not tested": MC already varies load. The unassessed uncertainty concerns the average supplied to MC. Preserve the generic statement that analytical/simulated results are not observed future outcomes.

Newly derived selected Decisions use qualified recommendation text in existing fields. Preserve status/headlines where compatible, numeric facts, IDs, missing reasons and the truthful pass-count rationale. Changing a wording test never authorizes changing a validator or fixture values. Use the existing warning style for a conditional Separate aggregate, consistent with the Reports badge; raw MC PASS rows remain raw PASS rows. Shared alerts remain unchanged.

### 3.2 Line context and accurate types

Pass DecisionEndpointPage's verified isSeparate value explicitly to DecisionEndpoint. For Separate plain answers use the actual root failed_periods/inadequate_periods and selected facts.validation_checks/failed_checks. Do not treat lane-period check counts as period counts. Shared keeps its current facts and overloaded-today branch.

Reuse SelectedDecision/SelectedDecisionFacts where appropriate, or add optional declarations for fields already returned. Do not use an unchecked cast, invent server fields or alter API shapes to fix the mismatch. ReportsPage already selects line type correctly; preserve that behavior while adding the qualifier.

### 3.3 Legacy records, report models and exports

Do not rewrite, backfill or invalidate persisted numeric jobs for a wording-only amendment. Old valid Decisions retain exact status, counts, IDs and saved wording. Clearly distinguish a current display note from the original saved text. Newly derived Decisions use qualified text.

Add optional view-model-only decision.scope_notice (string or null) to both final Separate report models. It is a current interpretation note, not a persisted statistical assessment. A tiny pure backend/reports/selected_scope.py may hold canonical text to avoid inconsistent wording across consumers; it imports no API, DB, simulation or optimizer code.

- Full-model route: add the note only in separate_full_sections. Shared/basic plan-only models do not gain it.
- Older Separate-model route: add the same note to its Decision view while keeping source headline/recommendation/facts unchanged.
- PDF: display adjacent to Decision text. Excel: append a labeled scope-note row after existing Decision-sheet rows, preserving prior positions, formulas, sheet names and order; size/wrap the appended row.
- Preview/Reports page: match file interpretation, with an optional scope_notice view type only if needed. Deduplicate the exact note if a newly stored recommendation already contains it.
- Leave basic plan and data-only exports unchanged. Existing owner/currentness/chain checks remain intact. Exporting does not derive a Decision or run a calculation.

## 4. Exact proposed file scope after application approval

| Files | Permitted edit |
|---|---|
| backend/api/workflow.py | Selected _derive_selected_decision recommendation/scope text only; optional pure text import. No status rules or calculations. |
| New backend/reports/selected_scope.py, only if shared canonical copy is needed | Pure text constants, no statistical policy or side effects. |
| backend/reports/full_report.py; separate_report.py | Selected-only optional view-model notice; source evidence unchanged. |
| backend/reports/report_pdf.py; report_export.py; plan_report.py | Render optional notice in both final report paths, guarded away from Shared/basic reports. |
| frontend/src/lib/decisionPlain.ts | Separate-only qualified keys and correct existing-field precedence. |
| frontend/src/components/analysis/DecisionEndpointPage.tsx; components/decision/DecisionEndpoint.tsx | Explicit line context, selected facts and visible localized scope. |
| frontend/src/components/queueSimulation/ChecksView.tsx | Compact selected qualifier and conditional warning style, unchanged requests/persistence. |
| frontend/src/pages/ReportsPage.tsx | Selected full-report qualifier, no calculations. |
| frontend/src/api/workflow.ts; types.ts; reports.ts | Accurate optional typings only for existing selected fields / additive report-view scope_notice. |
| Both frontend/public/locales/en/translation.json and tl/translation.json | Symmetric Separate copy/keys. |

Inspection-only: backend/api/reports.py and plan_reports.py gates. Protected outside scope: all queueing/statistics/DES/optimizer calculations, _attach_mean_routed_loads, validators, schemas, auth/CSRF, fixture data, runtime settings, original strict seed test and unrelated dirty work.

Relevant verification: tests/test_selected_plan_decision.py, test_selected_plan_validation.py, test_selected_mc_load.py (execute only; preserve xfail/assertions), test_separate_report.py, test_b8_full_report.py, test_b8_plan_report.py; frontend decisionPlain.test.ts, DecisionEndpointPage.test.tsx, QueueSimulationPage.test.tsx and ReportsPage.test.tsx. New narrowly scoped tests only where an existing suite cannot exercise a real consumer.

## 5. Acceptance and stop gates

1. Preserve source hashes/diff. Add a regression reproducing the actual Separate context defect, distinguishing unavailable savings from the Shared higher-cost message. Cover selected root failed periods/counts; protect Shared/overloaded-today behavior.
2. Visible qualification with Details closed on compact Checks, standalone Decision and selected full Reports; no invented interval/count or live three-row finding. Current uncertainty status is NOT ASSESSED.
3. Verify qualified new recommendations and unchanged status/facts/raw MC/Wilson fields, seeds, limits, provenance, generation/currentness and side-effect counts against reference outputs.
4. Verify old/new report models, preview/PDF/Excel parity, appended-row wrapping, preserved sheet data/formulas, and no calculations during export. Cover stale/owner/missing/null/arbitrary-ID/failed+inadequate cases and unchanged Shared/basic/data-only outputs.
5. Verify EN/TL symmetry and compiled browser light/dark behavior at 375/768/1024/1440 widths, keyboard and wrapping. Native-language/native Excel behavior remains NOT TESTED unless actually checked.
6. Execute relevant tests and required backend/frontend/Ruff/mypy/typecheck/lint/build gates. Record actual failures/skips/xfail. The seed xfail is not a passing seed-stability test. Inspect final exact diff/staging before claiming Phase A complete.

## 6. Later numerical correction remains gated

Statistical integration is NO-GO. A future method needs its own justified assumptions, finite-sample references/calibration, meaningful discrimination, exact evidence schema/version, provenance/freshness/size/export handling, agreed runtime and abstention semantics. Do not integrate the rejected t method, either all-insufficient default bound, or offline 5,120-run data.

Only an approved, executed interval can support upper<=cap pass, lower>cap fail or overlapping insufficient. A failing required pair must not be averaged away; unresolved required uncertainty cannot support a robust all-pass claim. Combining that gate with current conditional MC requires explicit amendment to the frozen Separate contract, not a hidden substitution in _separate_validation_verdict.

Do not promise identical outputs for every seed at finite sample size. Preserve the historical raw-MC regression. Any future retirement/replacement needs explicit contract approval and independently validated acceptance, not weakened assertions to make CI green. Closing a disclosure/context defect is distinct from closing numerical seed sensitivity.

## 7. Bilingual copy draft

Retain/change decision.plain.conditional_separate only for Separate contexts. Proposed new keys: decision.plain.revise_separate_periods, revise_separate_count, revise_separate, selected_scope_label and selected_scope_body. Both locales must contain the same full keys. Draft Filipino, not native-language certification:

- Conditional: "Pumasa ang mga naka-save na pagsusuri para sa run na ito. Hindi maikumpara ang matitipid. Suriin ang tinatayang dami ng customer at gastos bago gamitin ang plano."
- Failed periods: "Hindi pumasa ang naka-save na run sa {{periods}}. Suriin ang plano at ang tinatayang dami ng customer."
- Failed count: "Hindi pumasa ang naka-save na run sa {{failed}} sa {{total}} na pagsusuri. Suriin ang plano at tinatayang dami ng customer."
- Failed generic: "Hindi pumasa ang naka-save na run. Suriin ang plano at tinatayang dami ng customer."
- Notice label: "Hindi pa nasusuri kung gaano katiyak ang tantiya ng dami ng customer."
- Notice body: "Binabago ng variation test ang dami batay sa average mula sa simulation. Hindi nito sinusukat kung gaano maaaring magbago ang average na iyon."

## 8. GO / NO-GO

GO to review the bounded Phase-A interpretation/context correction. SCOPE-001 and CONTEXT-001 close only after actual implementation/verification; this document does not assert a fix.

NO-GO for numerical seed closure, a new statistical method, raising the cap or production deployment under the repair-first instruction. Releasing a clearly qualified configured-run product while accepting numerical sensitivity would be a separate explicit release-scope decision followed by normal release gates, not evidence of repaired seed stability.
