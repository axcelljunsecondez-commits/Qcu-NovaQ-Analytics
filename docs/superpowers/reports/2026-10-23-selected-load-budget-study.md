# Selected-load precision versus runtime: completed offline study

Date: 2026-10-23. Research COMPLETE. Application statistical repair OPEN. Production release held.

## Decision

**NO-GO for simply increasing the application's replication limit or declaring seed sensitivity repaired.** At 5,120 replications per batch, the registered external bound supported 57 of 60 lane-period passes in all four batches, with no supported failures or contradictory definitive classifications. The same three checks remained insufficient, with probability-interval widths above the registered .02 target. No completed sample size met all three prespecified research yardsticks.

This is useful evidence of improvement and its computational cost, not a completed repair. The classification-count yardstick PASSED at 5,120; cross-batch definitive-consistency yardstick PASSED at every completed look; the remaining-precision yardstick FAILED at every look. The numerical/calibration and independent evidence-review gates passed within their tested scope. Do not conflate those passing engineering gates with the failed combined research target.

The application's seed 42, MC seed 42, 1-20 replication contract, thresholds, caps, Wilson intervals, DES/RNG logic, Decision and exports remain unchanged. No implementation, rebuild, commit, push or deployment was performed in this study.

## Authorization, provenance and scope

The owner approved the explicitly offered next step: offline precision/runtime research only, with no production changes. Controlling specification: docs/superpowers/specs/2026-10-23-selected-load-budget-study.md. Execution plan: docs/superpowers/plans/2026-10-23-selected-load-budget-study.md. Their larger sample sizes and 90%/.02 yardsticks are registered research choices, not user-approved operational-safety rules, production settings or a latency SLA.

Candidate checkout: C:/Users/Administrator/.codex/worktrees/novaq-release/NovaQ; branch codex/supervisor-schedule-20261023; HEAD 151486ee04147f013857f69fe8ce77d899388660. Existing supervisor changes remain uncommitted and preserved. The primary checkout is different, at main 6093d78a5874d8cbdfa0026e9c25bdb5ddc70881; it was used for output evidence, not substituted for the candidate.

Evidence directory E: C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/output/seed-budget-study-20261023/. Key records:

- registration.json, protocol.json, source-baseline.json: local pre-execution registration and source hashes.
- numeric-results.json, calibration-results.json, calibration-*.npz, method-gates.json, method-check.log: actual method gates.
- input.json, fixture-start.json, progress.jsonl: current fixture inputs, runtime versions and execution chronology.
- counts-seed-{42,100042,200042,300042}.npz: actual count vectors, master seeds and per-replication kernel timings.
- checkpoint-{20,80,320,1280,5120}.json: every completed registered look, all row endpoints and classifications.
- study-results.json, fixture-study.log/.xml: actual completion and pytest result.
- independent-review.json/.log and verify_study.py: independent arithmetic review.
- precision-runtime.csv: the 20 batch/checkpoint summaries, copied from checkpoint results without changing classifications.

Registration was frozen at 2026-10-23T11:55:58.8971854Z before method or fixture execution. SHA-256: 17013912b1183daa4a24bddf9fc82bcd0553375cb7c13d2d29e5fc2c126cd09a. The 476 pinned files include the four helpers, specification/plan/protocol/input reference and 467 source/test/configuration/fixture files. Their hashes were checked before execution and by the independent review afterward. This is local registration, not an external preregistration service or a complete hash of every installed dependency.

## Actual fixture and computation

The unchanged tests/test_selected_mc_load.py:40-95 helpers uploaded the repository's tests/fixtures/novamart_events.csv-derived workbook, applied its existing break proposal, optimized at target .85 with minimum five lanes, saved and selected the plan, and ran the existing DES -> MC -> Validation -> Decision chain in temporary SQLite. This verifies a constructed repository fixture, not live analysis 18 or authenticated original paper-run records.

The actual mode was representative_day: one continuous selected-plan day per replication, with 13 recorded periods and 60 active required lane-period coordinates. Source backend/api/workflow.py:2620 dispatches this mode to _run_selected_plan_day_des at :2846. The study directly called that unchanged adapter with base+r seeds. It did not change the selected-plan HTTP request bound at workflow.py:2524-2526 or reimplement the DES. Each measured execution checked completed status, customer conservation, complete active identities, positive matching period durations, integer counts and unchanged input fingerprints. Missing rows were not zero-filled.

Primary base seed: 42. Additional registered research bases: 100042, 200042, 300042. All four sets of 5,120 master seeds were disjoint; no per-date reseeding was applicable to this representative-day fixture. Distinct seed numbers do not establish mathematical PRNG-stream independence. Mode, inputs and input digest d794bacf0e7a71734c55ec781e366d3e6a03cbbe94686c47cd5aa118d4077539 are retained in input.json.

The first 20 new base-42 count vectors exactly matched every retained identity/count in the earlier fresh-seed-42.json capture. Current point means, mu, staffing, perturbation fractions, thresholds/caps and baseline MC trial count were also matched. Baseline MC used 2,000 trials and seed 42. No larger-count MC job or replacement application Decision was created. This study concerns DES-derived load uncertainty; it is not a new 10,000-trial paper reproduction.

## External interval and multiple-look control

The previous external method was retained: for routed count X dominated by a modeled potential-arrival Poisson envelope N with fixed mean Lambda, deterministically truncate Y=min(X,B). B is input-only and is never selected from the observed counts. Bound E[X]-E[Y] by

    delta(B) = Lambda*P(N>=B) - B*P(N>=B+1).

For R=4 batches, K=5 registered looks and m=60 coordinates, invert the bounded-mean binary-KL inequality at

    kl(mean(Y)/B,p) <= log(2*m*R*K/.05)/n.

The count-mean interval is [B*l,B*u+delta(B)] intersected with [0,Lambda], with an outward floating-point guard. Divide by actual positive hours for rate endpoints. The same earlier cutoff rule is evaluated at the newly registered allocation, so the n=20 interval is more conservative than the preceding single-look study; its width is not an equal-confidence comparison to that old interval.

The fixed-n bounded-mean inequality is supported by [Foong, Bruinsma and Burt (2022), Theorem 3](https://arxiv.org/html/2205.07880). Allocating .05 across R*K*m controls the finite family under the assumed independent identically distributed marginal replications; the union step requires neither independent coordinates nor independent looks. This does not prove NovaQ's Poisson-envelope mapping, idealized RNG independence, correctness of estimated source rates or real-world safety. No lane-Poisson or Normal approximation was made.

All five nested sample sizes were evaluated regardless of intermediate results. The fixed 900-second resource limit was not extended. Incomplete prefixes would not have been classified as an unregistered sample-size look; all registered looks actually completed. The existing exact independent-uniform stress event was used externally to propagate rate endpoints, conditional on fixed mu/staffing and arrival/service perturbation assumptions. The application's MC algorithm and Wilson intervals were not replaced.

Research classification uses unrounded probabilities: supported pass when upper<=.05, supported fail when lower>.05, otherwise insufficient. These are external research labels, not new persisted application MC/Decision values.

Locations under E: budget_bounds.py:16 (settings), :68 (count bounds), :91 (descriptions); method_check.py:47 (numeric), :97 (calibration); fixture_study.py:44 (collection), :83 (isolated driver); verify_study.py:62 (independent review).

## Actual gates and outcomes

| Executed gate | Actual result | Interpretation |
|---|---|---|
| Numerical references and boundaries | 81 groups passed, including 40 normalized inverse checks against 80-digit Decimal references, tail sums at all five looks, invalid/domain/duration/zero/unit/cap checks | VERIFIED / PASS within tested domain |
| Generated known-mean calibration | Four cases x 2,000 independent batches, each evaluated at five nested looks; no rejection among the 48 registered tests | VERIFIED observation; not universal coverage proof |
| Fixture driver | 1 pytest test passed in 725.42s, exit 0; 20,480 measured study DES executions | VERIFIED capture/execution pass, not a repaired seed regression |
| First 20 seed-42 count vectors | Exact match to retained capture | VERIFIED reproducibility |
| Independent arithmetic review | 476 hashes, 40 inversions, all 48 probability tests, stored histogram sums and all 1,200 checkpoint rows reproduced; exit 0 | VERIFIED evidence-review pass |
| At least 54/60 supported in every batch | Met at 5,120, not lower registered sizes | PASS at final look |
| No conflicting definitive pass/fail across batches | Met at every look | PASS for studied batches only |
| Every remaining insufficient probability width <=.02 | Not met at any look | FAIL |
| Combined research yardsticks | Not met at any look | NO-GO for presenting this budget/method as the useful repair |

The calibration cases were Poisson .4, Poisson 3.75, perfectly dependent coordinates with Poisson .4, and rare routed bursts Bernoulli(.02)*Poisson(12), each with 60 coordinates. Exact categorical histograms with a final tail bin generated the truncated sums; no normal approximation to a sum was used. Each case used 2,000 independent generated batches; the five looks within a batch share prefixes and are not five independent batches.

| Calibration case | Union-over-looks family definite errors / 2,000 | Sentinel errors / 2,000 | Abstaining batches at each look |
|---|---:|---:|---|
| Poisson .4 | 1 | 0 | 0,0,0,0,0 |
| Poisson 3.75 | 0 | 0 | 0,0,0,0,0 |
| Perfect coordinate dependence | 0 | 0 | 0,0,0,0,0 |
| Rare routed burst | 1 | 0 | 0,0,0,0,0 |

The calibration has five family/sentinel tests per case plus union-family/sentinel tests, 48 in total, rejecting at .05/48. Per-look limits are .0025 for family and .0025/60 for sentinel; union-over-looks limits are .0125 and .0125/60. This calibration rejection allocation is distinct from the interval family's confidence allocation. Exact 95% binomial intervals and p-values are saved. With 2,000 batches, especially for very small sentinel error targets, statistical power is limited; lack of rejection is not proof.

## Measured precision and runtime

Every supported classification in this fixture study was a supported pass. There were no supported failures at any look. Ranges below span the four registered batches, not confidence intervals.

| Replications per batch | Supported checks / 60 | Insufficient checks / 60 | Local DES kernel seconds per batch |
|---:|---:|---:|---:|
| 20 | 0 | 60 | 0.31-0.48 |
| 80 | 6-7 | 53-54 | 1.37-1.62 |
| 320 | 25-27 | 33-35 | 5.74-6.19 |
| 1,280 | 42-44 | 16-18 | 23.25-26.44 |
| 5,120 | 57 | 3 | 96.94-110.47 |

Actual measured study wall time was 723.675s, below the registered 900s limit. Fixture setup and baseline DES/MC/Validation/Decision took 8.830s within that total. Kernel timing excludes the study's repeated input-hash auditing, count collection, checkpoint serialization and bound computation; it is not complete application-response time. At 5,120 the final bound calculation took approximately .075-.137s per batch, separate from kernel execution. No production concurrency, HTTP timeout, storage-cap or page-latency test was performed. A satisfactory production latency limit is UNKNOWN and was not invented from local timing.

The same three coordinates remained insufficient in all four final batches:

| Coordinate | Seed-42 mean rate, customers/hour | Seed-42 rate interval, customers/hour | Seed-42 conditional failure probability interval | Upper probability range across four batches |
|---|---:|---|---|---|
| 10:00-11:00 / cashier_3 | 2.58203125 | [2.1678723772,3.0953475050] | [0,0.0620306787] | 0.0501085430-0.0620306787 |
| 13:00-14:00 / cashier_2 | 3.295703125 | [2.8333622401,3.8471065937] | [0,0.0794189335] | 0.0754554893-0.0798123582 |
| 13:00-14:00 / cashier_3 | 2.975 | [2.5331645279,3.5076947853] | [0,0.2190816696] | 0.2134844539-0.2482499522 |

All those intervals straddle the .05 cap. For example, .0501085430 must not be rounded to .05 and accepted. Their widths exceed .02 even at the final size. The worst remaining width is 0.21348-0.24825 across batches, about 21.35-24.82 percentage points, compared with the registered two-point total-width target. Their point estimates do not justify classifying their entire uncertainty intervals as passing.

The 90% classification and .02 width requirements are research yardsticks. Failing the latter does not establish that every business needs that width, that these three real operations fail, or that every possible estimator at this budget would fail. The true fixture population routed means and original-input uncertainty remain UNKNOWN. No new operational-safety statement follows.

## Independent verification, failures and preservation

verify_study.py does not import budget_bounds.py. It uses scalar-log/Brent inversion, positive Poisson PMF tail sums, numerical quadrature of the stress event and binomial survival/beta-quantile checks. It regenerated the categorical histogram sums from the frozen seeds, compared the stored arrays and timing sums, checked disjoint master seeds, source/input digests, original first-20 counts and all checkpoint summaries. This is an independent implementation of arithmetic checks on the same evidence, not an independent real-world dataset.

There was no numerical, calibration, fixture-driver or independent-review failure in this study. The combined usefulness/precision research target FAILED and is retained. No method, acceptance criterion, sample-size ceiling or runtime ceiling was changed after seeing results. The preceding study's OpenBLAS failure remains preserved in its own directory; this study used its registered one-thread environment from the start.

One progress message initially described the 1,280-run range as 43-44 before inspecting all four batches. It was explicitly corrected to 42-44; all saved checkpoint tables and this final report use the actual 42-44 range. Some exploratory Windows file searches rejected a wildcard path; subsequent directory/glob searches succeeded. Neither was a passing verification gate or changed the study data.

## Recommendation and remaining status

Do not change the production replication cap to 5,120 on these results. It would add substantial measured local kernel time and still leave the three identified checks outside this study's precision target. More runs improved the external classifications, but did not establish the required complete repair, acceptable runtime or a minimum sufficient count.

The smallest justified next specification should address uncertainty explicitly, using these three retained coordinates as reference cases and stating what a supervisor sees when the evidence cannot separate a check from the cap. It must reconcile the existing raw conditional MC/Wilson contract with DES-load uncertainty, define persisted evidence/freshness/export behavior and agree on an acceptable precision/runtime tradeoff before another statistical application change. This is a PROPOSED next scope, not an implemented rule or permission to silently weaken the registered yardsticks. No new statistical method is established as necessary by this study.

The original tests/test_selected_mc_load.py strict xfail remains unchanged and OPEN. The unchanged regression failed in the prior current-source execution; it was not rerun or replaced by this external fixture-driver test. Agreement in four registered batches is not universal seed stability, and the raw-MC assertion still needs an explicit, justified reconciliation in any future correction. Application mathematical correctness and operational safety are not established by passing these scripts.

No production application source, tests, fixture, configuration, Docker state, operational database, paper, export implementation or Git state was modified by this phase. Only the new research specification/plan/report and new output helpers/evidence were added. Native PostgreSQL/cost verification from the earlier phase remains separately recorded; it is not a new test result here. Full backend/frontend suites were not rerun because no application change was made. No rebuild is required for this research-only phase. Production inspection and release were not performed.

Status: offline study COMPLETE; candidate budget/precision target NOT MET; integration NOT AUTHORIZED/NOT IMPLEMENTED; seed finding OPEN; production deployment NO-GO under the repair-first instruction. No commit or push occurred.

## Reproduction

Use the existing primary-checkout .venv/Scripts/python.exe. Runtime recorded: Python 3.13.13, NumPy 2.2.6, SciPy 1.18.1. Set PYTHONDONTWRITEBYTECODE=1 and OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=NUMEXPR_NUM_THREADS=1. Before fixture execution set NOVAQ_ENV=development, remove NOVAQ_TEST_DATABASE_URL from that process environment, and include the candidate checkout and E on PYTHONPATH. No credentials or operational database are needed.

Recorded command forms, with absolute paths defined above:

    python -B <E>/method_check.py
    python -B -m pytest -c <candidate>/pyproject.toml -p tests.conftest <E>/fixture_study.py -q -s --tb=short -p no:cacheprovider -o addopts= --junitxml=<new-output>/fixture-study.xml
    python -B <E>/verify_study.py

Use a separately preserved/copy output package and a pre-execution path-only registration amendment for a new run; do not overwrite this dated evidence. The helpers deliberately pin the source/input hashes and write results next to themselves. Extending the grid, choosing another estimator, changing confidence allocation or using a larger deadline is a new study, not a retry that can be substituted for these results.
