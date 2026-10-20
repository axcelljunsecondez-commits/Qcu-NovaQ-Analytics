# Selected-plan routed-load uncertainty and Decision evidence

Date: 2026-10-19. **Status: APPROVED SPECIFICATION.** The owner approved the explicit selected-plan statistical/contract amendment and implementation plan after review. Prototype/calibration gates must pass before application integration; approval does not establish method validity or implementation completion.

**Execution update: candidate REJECTED; application integration STOPPED.** Three of nine prespecified synthetic calibration cases failed. [Actual results](../reports/2026-10-19-selected-load-method-calibration.md); [revision 2 proposal](2026-10-19-selected-load-uncertainty-revision-2.md). The method below is retained as the approved candidate evaluated, not an accepted production estimator.

[Verified investigation](../reports/2026-10-19-selected-decision-seed-investigation.md). Existing frozen contract: [Separate MC/validation semantics](2026-09-17-separate-mc-validation-semantics.md). Application integration remains conditional on the independent gates below. No Docker/rebuild, commit/push or production action is included.

## Required observable behavior

For selected Separate plans, show insufficient evidence when measured routed-load uncertainty cannot resolve the allowed stress-failure probability. Preserve configured target, cap, perturbation assumptions and raw conditional MC outputs. Clearly supported failures still require revise. All currentness/ownership/conservation/missing-data checks remain mandatory. No forced favorable verdict or blanket invariance guarantee.

## Approved conditional contract amendment

The selected-plan adequacy/validation rule would change; this is protected statistical behavior. Owner approval is recorded above, with integration conditional on the prototype gates. The amendment is limited to sections 2,6,7,9 of the frozen contract for versioned selected-plan load evidence. Shared MC, Current MC, raw selected MC point PASS/FAIL, conditional Wilson intervals, optimizer math, routing/DES mechanics and Decision taxonomy remain unchanged. A raw conditional MC FAIL near the boundary may be classified as unresolved selected-plan evidence by the new gate; that difference must be explained rather than concealed. This is not averaging away a failure proven by adequate uncertainty bounds.

## Estimand and proposed method to validate first

The estimand stays the configured stress probability at the true simulated mean routed rate under the frozen dataset/plan, with empirical service parameters treated as fixed. It is **p(E[lambda_replication])**, not E[p(lambda_replication)], and not the probability a whole day fails. No inference about real-world parameter uncertainty or future operations is implied.

1. Retain the same 20 full-replication lane-count vectors (or sufficient statistics validated for the chosen method) while preserving the current mean and replay trace. Whole-replication units preserve within-day routing dependence. Units: counts divided by the actual period duration -> customers/hour. No zero substitution for missing evidence. Keep request bounds/defaults and current seed schedule unchanged initially.
2. Prototype replication-mean Student-t bounds with a prespecified nominal 95% family level and Bonferroni allocation across the schedule's required active lane-period pairs: per-lane nominal interval `max(0, mean - q*s/sqrt(n)) .. mean + q*s/sqrt(n)`, `q=t(1-0.05/(2*m), n-1)`. This is a **candidate**, justified by replication analysis, not a validated finite-sample interval for routed counts. For n<2, missing/invalid samples, structural missingness or unsupported adequacy assumptions: insufficient. Zero observed variance is not automatic proof of precision. Do not silently replace it with another estimator if calibration fails.
3. Propagate a validated nonnegative mean-load interval monotonically through the independently derived exact conditional utilization-stress probability for the current independent uniforms. This proposed new bound avoids adding inner MC sampling error to this evidence gate; existing MC point estimates/Wilson fields remain conditional diagnostics, unchanged. Verify formula boundaries, configuration domains and units independently before adding any production helper.
4. For unrounded probability bounds [L,U] and unchanged allowed cap c: U<=c -> supported pass; L>c -> supported fail; otherwise -> insufficient. Any required supported fail dominates; otherwise any insufficient row dominates; all supported pass -> the existing selected Separate conditional Decision. Preserve each lane identity and explain unresolved lanes. Rounded display values must never drive classification.
5. Label coverage **nominal/approximate**, conditional on the simulation/input model and validated assumptions. Bonferroni does not make invalid marginal t intervals valid. No production integration until coverage and runtime gates pass. Wider honest bounds may yield insufficient evidence with 20 runs; no unapproved count increase, automatic rerun loop or relaxed cap.

Sources and limitations are in the investigation. Bootstrap and alternative intervals are not silently authorized as fallbacks; a failed candidate requires a revised evidence-backed proposal.

## Validation gates before application edits

- Independently check t quantiles/df and mean/variance/units on reference cases; compare exact stress area against numerical integration, zero/certain failure and monotonicity.
- Register calibration cases and random-stream scheme before outcomes: known normal replication means, discrete count and routed-like dependent-lane cases, small n/zero variance and boundary probabilities. Separate whole-replication dependence from cross-replication independence. Use disjoint validation batches rather than the legacy overlapping bases 7–11.
- Choose calibration effort from precision: for estimating coverage near 0.95, 10,000 independent batches gives MC SE approximately 0.00218 (a proposed precision target, not a universal sufficient count). Report coverage with its binomial uncertainty and the true/reference parameter precision. The prespecified acceptance check must not show undercoverage below nominal after accounting for calibration/reference error. Marginal and family coverage both require evidence; synthetic cases alone do not prove universal coverage for every real plan. Stop before integration if routed-count validity remains unsupported.
- Prespecify behavior when precision is insufficient. Keep the existing five-seed identical-Decision assertion and lane-interval criterion unchanged while evaluating the prototype. No claim that the new policy will pass until executed. Seed invariance is a fixture regression requirement, not a theorem.

## Versioning and dependent contracts

Persist new method metadata in existing job JSON with a selected-load-specific method version; do not globally bump unrelated engines. Keep original jobs/exports immutable. New Decision generation must reject or mark insufficient legacy evidence lacking the required measurement information, with a clear rerun reason. Audit workflow/report freshness readers so an old Decision is not silently presented as current after a method change. Any new response information is additive; no endpoint or existing field is removed/retyped. No database schema migration is planned.

## Proposed application file scope after validation

- `backend/api/workflow.py`: capture selected-load measurement metadata and add a selected-only adequacy gate; preserve general `_separate_validation_verdict` callers unless a separate scoped change is proven necessary.
- **New, proposed file** `backend/queueing_engine/statistics/selected_load_uncertainty.py`: reviewed pure inference helpers; no central queue-model dispatch changes.
- `tests/test_selected_mc_load.py`, `tests/test_selected_plan_decision.py`, **new proposed reference/regression test** `tests/test_selected_load_uncertainty.py`: preserve existing assertions; add coverage of measurement/provenance/legacy/threshold/unknown cases. Remove strict xfail only after it actually passes and independent statistical gates pass.
- `frontend/src/api/workflow.ts`, `frontend/src/components/queueSimulation/ChecksView.tsx`, and both EN/TL translation files only if needed to explain the selected-only point-versus-evidence distinction. Keep the visible explanation compact. Qualified Filipino review remains separate.
- Report consumers are an **inspection requirement**, not blanket edit scope. If current exporters cannot honestly represent the versioned evidence, stop and name exact necessary report edits before expanding scope. No unrelated formatting or workflow restructure.

No edit to queueing formulas/model selection, costing/optimizer objectives, DES/routing/closing rules, source dataset, stored historical evidence, current/shared MC semantics, default/bounded trial counts, target, cap or uncertainty assumptions. No Docker action, commit/push or deployment is authorized by approval of this source repair unless separately requested.
