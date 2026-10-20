# Verified mathematical and labeling issues: approved remediation

Date: 2026-10-15; verification continued2026-10-16. Status: COMPLETE for this approved repair scope. Reference/backend/frontend gates, sequential API/web builds and bounded preview checks passed; the owner then approved the itemized API/web replacement. New images are active, database/one-shot IDs and start times retained, both health endpoints200, seven in-container synthetic cases passed and signed-in localhost calculator captions/numbers verified. Broader reconstruction/source limits remain documented in the repair report.

Evidence and exact reproductions: [local runtime/math audit](../reports/2026-10-15-local-runtime-math-audit.md). That audit found M1-M3 and initially stopped repairs. The owner subsequently explicitly approved implementing this three-item plan, requiring formula/source/assumption/unit/reference mapping first. That mapping and the corrected book-reference findings are in [formula source register](../reports/2026-10-15-formula-source-register.md). The owner confirmed `finals (1).pdf` as the authoritative capstone; product workforce features are a separate source-audited scope. Actual implementation and verification are recorded in [repair verification](../reports/2026-10-15-approved-math-repairs-verification.md); the old audit remains the before-repair record.

## Boundaries

Work only in `.claude/worktrees/ux-workflow-audit`, branch feat/ux-u1-shell. Preserve unrelated uncommitted reconstruction changes and `novaq_local.db`. No Home, authentication, schema, API route/response shape, model dispatch, DES/routing behavior, optimizer objective or production change. No commits/pushes/cleanup. If a repair requires a rebuilt Docker container, build one image at a time with memory checks and obtain itemized approval for that specific container recreation.

## A. Correct the active Erlang-A presentation (M1)

1. Retain backend Wq and its `workload_per_served_throughput` contract. Do not overwrite it with Lq/lambda or conditional served wait.
2. In Quick Calculator's leaving situation, use the label **Queue workload per customer served**. Explain: average number waiting divided by customers served per hour, converted to minutes; this is not an individual customer's average wait. Both main and neighboring-counter interpretations must disclose this same basis. Keep the same numeric value and no ordinary mean-wait claim for this situation.
3. Limit code scope to `frontend/src/lib/quickCalculator.ts`, `frontend/src/pages/QuickCalculatorPage.tsx`, their tests and symmetric EN/TL labels. Home and public layout stay unchanged. The calculator component is shared by signed-in and guest flows; verify both affected calculator variants without editing Home/auth.
4. Trace the related Results and report Erlang-A captions before claiming global wording is repaired. If they need additional code or metadata changes, document that exact additional scope before proceeding. This plan does not silently extend an API contract.
5. Tests: 20/6/2, theta=1 must preserve returned ratio 40.8598511976 minutes and stop describing it as an ordinary mean wait. Basic M/M/c 40/15/3 remains 9.570093458 minutes. All four situations, neighbors, tooltip, EN/TL and guest/signed-in calculator regressions must pass.

## B. Correct the exported priority helper (M2, protected mathematical change)

1. Files: `backend/queueing_engine/models/queue_models.py`, focused independent tests in `tests/test_queue_models.py` or a dedicated priority reference file. Keep parameter/result keys and dispatch unchanged.
2. Re-derive the nonpreemptive identical-exponential-service priority expressions against the inspected MIT single/multiserver references. MIT Larson/Odoni (1981) §4.9.3 equations4.111–4.112 and their equation images were directly inspected. Replace the incorrect Kleinrock Vol.I§3.3 attribution: that section is Discouraged Arrivals. Use residual workload W0, not the full aggregate M/M/c wait, as the class denominator numerator. For these assumptions W0 = P(wait)/(c*mu) = Wq_mmc*(1-rho). Do not assume a different service distribution or preemption rule. Remove the unsupported express-versus-regular lane example from this shared-server helper's docstring.
3. Reproduce exact c=1 case lambda1=lambda2=2, mu=6: priority 1/6 h, regular 1/2 h, arrival-weighted wait 1/3 h. Verify conservation for c=1/2/4 and independently sourced multi-server cases before accepting the formula for c>1.
4. Cover unequal class loads, heavy/light load, invalid and saturated inputs, float boundary 3.15 versus 3*1.05, and numerical refusal without dereferencing an unavailable base Wq. Preserve existing invalid-input behavior unless an independently documented defect requires a separate decision.

## C. Correct legacy interval cost units (M3, protected mathematical change)

1. File: `backend/queueing_engine/services/costing.py`; regression tests in `tests/test_costing.py`. Preserve all existing keys and missing-value semantics. Do not change the separate newer `shared_day_cost.py` or the shared optimizer's disclosed hourly objective.
2. For interval totals, multiply hourly waiting and abandonment flows by `hours_per_interval`, consistently in scalar and vectorized paths; summary must aggregate matching interval totals. Update the formula documentation to state units.
3. Exact synthetic reference: c=2, lambda=4/hour, Wq=0.25 h, server rate 10, waiting rate 100, abandonment fraction .1 and per-customer abandonment cost 5 gives totals **122 / 61 / 244** at H=1/.5/2 hours. Verify component costs, scalar/vector/summary equality, one-hour backwards compatibility, zero demand, unavailable Wq, missing costs and rounding. Preserve existing input-policy/rounding behavior; add no new validation of duration or missing monetary rates. Supported interval interpretation assumes finite nonnegative hours; invalid-input policy expansion is outside this repair.

## Verification / completion

First add failing independent counterexample regressions, then make only the authorized corrections. Keep the original audit log with six failures. Re-run the independent script without changing its expected mathematical targets; M1 presentation verification is a distinct browser test. Execute repository backend gates and relevant frontend/full gates sequentially. Review exact diffs and protected paths. No numerical or semantic repair is complete from tests alone: document derivation, assumptions, units and limits, and verify affected live output after any separately approved image refresh.

The aggregate routing-DES limitation is outside this repair set. Its variance-only file lacks empirical service samples in addition to its period-ID mismatch. No distribution or samples may be inferred to make that path appear supported.
