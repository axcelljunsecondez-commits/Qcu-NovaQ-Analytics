# Selected-plan Decision: seed-sensitivity investigation

Date: 2026-10-19, Asia/Shanghai. **Investigation and proposed repair plan: COMPLETE. Statistical repair: NOT IMPLEMENTED. Existing failure: OPEN.**

Owner approved the explicitly proposed investigation and repair-plan preparation. Application/statistical behavior, existing assertions, configured thresholds and running Docker were not changed. The investigation used temporary observation wrappers in an isolated pytest process; wrappers returned the original function results unchanged. No live database was used.

## Verified scope and source chain

Worktree HEAD `0b9423ec66d32620ed91769ac35a10e51ffae2ec`, branch `feat/ux-u1-shell`, with pre-existing dirty source preserved. The repository implementation overrides older narrative claims.

- `tests/test_selected_mc_load.py:43–103` constructs/uploads `novamart_workbook`, applies the break proposal, optimizes at 0.85/full five-lane coverage, saves/selects, then runs DES -> MC -> validation -> Decision. The strict xfail and unchanged invariant assertion are at lines 147–168.
- Fixture `tests/fixtures/novamart_events.csv`: 1,600 rows, 14 distinct day values, five cashier IDs, SHA256 `951d8f3d67af77f455396bac8bbb9adc072568ce0a1ac0df67b637e121fb6752`. Existing helper maps to placeholder dates. Original real-world provenance was not independently established. These are test-fixture simulations, not new field measurements.
- Actual execution was a continuous representative day with queue/break carryover. The output has 13 one-hour periods and 60 active lane-period MC rows; it is not the period-independent mode described in some older comments.
- `backend/api/workflow.py:2506–2512, 2798–2829`: 20 load replications by default, range 1–20; replication zero is the replay, and lane mean routed counts divided by period hours become the MC input. Subsequent replicate counts are currently discarded after computing the mean.
- `workflow.py:2974–3013, 3020–3101`: selected MC treats the estimated mean load as fixed, uses empirical mean service rate, and defaults to the plan's utilization target.
- `simulation.py:1193–1230, 1272–1350`: independent uniform arrival/service perturbations ±20%/±10%, conditional failure fraction, Wilson interval; point status uses fraction <= cap. `workflow.py:1291–1340` validates the point fraction when existing adequacy rules pass. It does not test whether the interval excludes the cap.
- `workflow.py:3256–3392`: validation fail -> revise; insufficient -> insufficient_evidence; pass -> conditional for Separate plans because comparable savings are unavailable. Decision is consuming the existing validation classification, not introducing random draws itself.

## Fresh executed result

The exact existing test was executed with `--runxfail`, its original assertions unchanged, plus an external observational plugin. Actual pytest: **1 failed, 1 existing Starlette/AnyIO warning, 39.95 seconds**. Wrapper: 89.05 seconds including startup/imports. Exit 1 is retained; wrapper completion is not counted as a test pass.

DES base seeds 7,8,9,10,11 produced `conditional, conditional, revise, revise, revise`. All runs used 20 DES replications, MC seed 42, 2,000 trials/lane, target 0.85 and cap 0.05; setup/scenario/dataset generation stayed fixed within the isolated case. `frontend/src/api/simulation-defaults.json` also specifies 2,000 trials. The previously source-checked manuscript (current PDF SHA256 reconfirmed as `F795BD019B3AC5F2AC55D7C20B3B7FDB9D9C5E2A21908C8111D07CAB243C0CD9`) describes 10,000 trials. That description is therefore not the default setting used by this failure test/current selected UI; the UI permits changing it. This difference does not by itself explain or repair upstream load uncertainty.

Actual cashier_2 results at **13:00–14:00** (lambda in simulated routed customers/hour; mu fixed at 5.414634146341464 customers/hour/counter):

| DES base seed | Mean lambda/hour | MC failure fraction | Conditional Wilson interval | Independently calculated conditional probability | Decision |
|---|---:|---:|---|---:|---|
| 7 | 3.75 | 4.85% | [3.99%, 5.88%] | 4.6361% | conditional |
| 8 | 3.70 | 3.10% | [2.43%, 3.95%] | 3.2550% | conditional |
| 9 | 3.85 | 8.20% | [7.08%, 9.48%] | 8.0525% | revise |
| 10 | 3.95 | 12.10% | [10.74%, 13.60%] | 12.2861% | revise |
| 11 | 3.90 | 10.00% | [8.76%, 11.39%] | 10.0711% | revise |

The changing upstream mean estimates alone cross the 5% stress allowance. Independently evaluating all 60 rows at each observed mean using the exact conditional probability gives the same five overall classifications. Thus eliminating finite MC trial noise does not remove this observed overall sensitivity.

Finite MC noise remains relevant to individual lanes: cashier_1 at seeds 10/11 has point MC failure fraction 3.90%, while the exact conditional probability is 5.02148894%. Both actual overall Decisions remain revise because cashier_2 fails. This is not proof of an incorrect Wilson formula: a nominal interval need not contain the true conditional probability in every finite run. No confidence interval was replaced or widened in the application.

`replication_seeds` is base, base+1,... (`services/separate_optimization.py:421–432`). Adjacent 20-run batches overlap in 19 seeds; all five share 16. Only 24 distinct replication seeds occur among 100 captured executions. The 76 repeated-seed payload comparisons matched. This establishes repeatability for captured seed/plan combinations, not universal determinism or independent batches. Equal seed schedules alone are not claimed as a proof of full common-random-number coupling.

## Independent conditional reference

For fixed base utilization r=lambda/(c*mu), stress factors A~Uniform(a0,a1) and B~Uniform(b0,b1), failure is r*A/B > t. All factors and bounds here are the already configured assumptions. Define k=t/r and H(x)=(max(x-k*b0,0)^2-max(x-k*b1,0)^2)/(2*k). Then:

`p(r) = [H(a1)-H(a0)] / [(a1-a0)*(b1-b0)]`, with p(0)=0.

This is a direct rectangle-area derivation, independently checked against numerical midpoint integration in **36 fixed cases**, absolute error <1e-9. It applies only to the configured conditional utilization event, with positive service factors; it does not calculate waiting-time intervals, full-day DES failure probability, or real-world risk. At target 0.85 the exact conditional p=0.05 boundary is r approximately 0.6947791547065059. The sampled lane loads move around that boundary.

This reference lives only in the audit output. It was not substituted into the application, and its passing cases do not close the failed seed gate or validate a new uncertainty interval.

## Interpretation and limits

**VERIFIED limitation:** upstream simulation-estimation uncertainty is not represented by the conditional MC Wilson interval. The Decision uses point validation after a broad precision check. This explains the observed route from changing loads to different Decisions. **INFERRED consequence:** an uncertainty-aware selected-plan evidence rule may correctly return insufficient evidence near the allowance, rather than force conditional/revise from a point estimate. This remains a proposed behavioral change, not an implemented repair.

The literature supports reporting replication-level uncertainty and simulation precision; it does not impose identical labels for every finite seed or prescribe NovaQ's replication count, 0.85 target, 0.05 cap or perturbation ranges. [Law 2023](https://informs-sim.org/wsc23papers/124.pdf) gives a direct queueing example and replication-mean analysis. [Morris et al. 2019](https://onlinelibrary.wiley.com/doi/10.1002/sim.8086), sections 4/5.2/5.3, connects reproducibility and Monte Carlo precision to experimental effort. [Barton et al. 2014](https://users.iems.northwestern.edu/~nelsonb/Publications/BartonNelsonXieIJOC.pdf) distinguishes conditional simulation error from estimated-input uncertainty; NovaQ's upstream DES measurement error is related but not identical to their real-world input-estimation problem. [NIST's Bonferroni inequality](https://www.itl.nist.gov/div898/handbook/prc/section4/prc473.htm) supports simultaneous error allocation only if the underlying marginal intervals are valid.

## Proposed next work and protected boundary

[Proposed specification](../specs/2026-10-19-selected-load-uncertainty.md); [implementation plan](../plans/2026-10-19-selected-load-uncertainty-plan.md). These are reviewable proposals, not authorization or deployment proof. The frozen separate validation specification must be explicitly amended for the selected-plan evidence gate; no shared/current rule is silently changed.

NOT TESTED: candidate replication-mean interval coverage, simultaneous coverage for routed-count outputs, an end-to-end repaired Decision, runtime budget, or UI/export integration. Exact-label invariance cannot be promised universally near a boundary with finite simulation effort. The existing five-seed criterion remains in force and its failure stays OPEN until an approved repair actually satisfies it or the owner explicitly revises that requirement. Fixing seed 42, choosing favorable seeds, increasing only MC trials, changing the cap/target, or weakening the assertion are not accepted repairs.

Audit evidence in primary checkout: `output/seed-sensitivity-audit-2026-10-19/`: baseline, plugin/runner, diagnostic log/XML/result, five per-seed payloads with 100 captured DES executions, fixture provenance, analysis summary, conditional-reference checks, references and final preservation. Source files and the running Docker configuration were not modified. No rebuild, commit or push.

Final scope verification: all baseline application/test/configuration files remained byte-identical; only `handoff.md` changed among baseline files, with three new scoped spec/plan/report documents. HEAD/staging unchanged and diff check passed; exact results in `final-preservation.json`. Backend/full frontend/Ruff/mypy suites were not rerun because this phase changes documentation and uses external audit scripts only. This does not convert the failed seed test into a pass.
