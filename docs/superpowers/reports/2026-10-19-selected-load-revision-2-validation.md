# Selected-load revision 2: isolated validation record

Date: 2026-10-19. **Research package COMPLETE with qualifications; overall repair PARTIAL / finding OPEN.** Owner authorized isolated proof/prototype/calibration of the [revision 2 specification](../specs/2026-10-19-selected-load-uncertainty-revision-2.md), following the [research plan](../plans/2026-10-19-selected-load-revision-2-plan.md). Application integration was not authorized and did not occur.

## Outcome

VERIFIED: 37 recorded numerical check groups passed; nine synthetic cases x 10,000 independent batches and three actual selected-routing modes x 500 corrected disjoint batches showed **no detected undercoverage** under the registered acceptance rule. The analytic bound is conditional on a valid input-rate Poisson envelope and independent ideal marginal replication streams. This is not a proof of PRNG independence, universal numerical certification, measured field accuracy or deployment correctness.

VERIFIED practical limit: in the retained NovaMart fixture, **all 60 required lane-period checks remain insufficient in every one of the five historical batches** at n=20. This is an external candidate evaluation, not a modified or passed original regression test. It supports no staffing pass/fail conclusion for that fixture. A larger illustrative payload exceeds the existing default result cap. Do not close the seed-sensitive finding or declare this a completed Decision repair.

No application, test, fixture, database schema or Docker change; no commit/push. Worktree HEAD remains `0b9423ec66d32620ed91769ac35a10e51ffae2ec`; pre-existing dirty work was preserved. Scope changes were limited to method/specification/plan/handoff/report documents and external research scripts/results.

## Conditional derivation and source findings

The registered external `derivation.md` provides the argument in full. Source inspected: `backend/api/workflow.py::_run_selected_plan_des`, `_run_selected_plan_day_des`, `_attach_mean_routed_loads`; `backend/queueing_engine/services/separate_optimization.py::evaluate_candidate_with_des`, `_run_routing_des`, `run_routing_day_des`, `_paired_stream_seeds`, `replication_seeds`, `date_seed`.

- Period-independent mode conserves the total rate from **all available input lanes**, including inactive lanes' demand, and routes to the active subset. Continuous/per-date modes use the actual active-lane sum in each arrival window. These bases must not be silently interchanged.
- Eligibility pauses/late starts add nonnegative delays. Couple against the unpaused exponential-gap process for the nominal window. Each attributed lane count is bounded by total potential arrivals with Poisson envelope mean `Lambda=rate*duration_hours`, under the ideal-stream model. Counts retain their original arrival-window labels across delays. A routed lane count is not thereby Poisson.
- Period-independent seeds `base+r+period_index` overlap across coordinates and replications. Within a two-period 20-run batch, 40 calls have only 21 distinct master seeds. Full vectors are not independent. Each fixed lane-period still has distinct seeds across replications, and a union bound needs only marginal replication independence. Independence of ideal random streams remains an inference assumption; deterministic seed uniqueness does not prove it.
- Date stride is 1,000,003. Corrected independent research batches use 64-seed base spacing, retaining the application's 20-run consecutive replication schedule. Verified no between-batch or between-mode master-seed aliases: 10,500 distinct seeds for period-independent cases, 10,000 representative-day, 20,000 per-date. Cross-coordinate aliases inside static batches are retained and disclosed.

For `Y=min(X,B)`, `0<=E[X]-E[Y]<=delta(B)=Lambda*P(N>=B)-B*P(N>=B+1)`. Hoeffding plus union allocation gives radius `B*sqrt(log(2m/.05)/(2n))`. Intersect the count interval with known `[0,Lambda]` and divide by actual duration. Choose B solely from frozen Lambda/n/m to minimize additive radius plus tail allowance; the forward difference is `a-P(N>B)`. No observed-data tuning, lane pooling, cap relaxation or count increase.

The external prototype's independently checked numerical domain is `0<=Lambda<=1000`; it abstains outside that range. It adds a documented floating-point guard to the tail allowance. Tests of a finite domain are not universal rounding certification. n=1, missing/invalid samples, unknown envelope, inconsistent known zero-demand data, or missing required evidence return insufficient. Zero sample variance with positive envelope does not collapse the interval.

## Registration and corrections

Evidence directory in the primary checkout: `output/selected-load-revision-2-2026-10-19/`.

- Initial registration `2026-10-19T06:31:59.742102+00:00`; original preregistration SHA256 `fa4a0bc1608191fb34e6beb1281c75d49205183ad7f73feba8a54c736979126f`. Original method, source scripts and derivation hashes remain intact.
- Attempt 1 exited 1 with external-harness `KeyError: duration_hours`: static periods keep duration at the parent result while continuous periods carry it directly. Corrected only the external reader; application contract unchanged. The first edit generator also stopped on an incorrect expected match count before writing; corrected to the observed count. `harness-correction.json` preserves both explanations. Completed synthetic cases were reproduced deterministically once to save complete results, with identical recorded family-error counts; no acceptance rule changed.
- Initial routing test batches spaced by 20 seeds shared one static period seed at adjacent batch boundaries (499 overlaps). Those routing outputs are superseded and excluded from acceptance. The run was interrupted; saved outputs remain under `superseded-20-spacing/`. `routing-stream-amendment.json` records the issue, including that a completed output already existed when detected. This is a corrected experiment-design defect, not a claimed passing independent run.
- Corrected run registered at `2026-10-19T06:35:59.307488+00:00` before its outcomes. `experiment-v3.py` uses spacing 64, reuses the completed synthetic/numeric records, and retains all estimator parameters/thresholds. No change to the application seed scheme. Corrected run exited **0** in **120.68347519999952 seconds** excluding interpreter/import startup. Its runtime includes the deliberately uncached 71.53-second scale benchmark below.

## Numerical and calibration verification

Poisson excess tails were compared with independent 60-digit Decimal nonnegative PMF sums and geometric remainder bounds for Lambda 0, 1e-8, .02, .4, 3.75, 24, 100 and 1000, with multiple cutoffs each. Cutoff optimality was independently enumerated. Hours conversion, missing/invalid/n=1/21, zero demand versus zero observed variance, unrounded cap equality, and both revision-1 count counterexamples were checked. **37 recorded numerical groups PASS**; exact references/tolerances in `numeric-results.json` and `preregistration.json`.

Acceptance was 24 one-sided exact binomial tests (family and sentinel for 12 cases) with total false-rejection allocation .05; rejection threshold .05/24. All cases used known means, not fitted routing population means. Reported error is an issued interval excluding the true mean; abstentions are separate, never counted as coverage.

| Case (SYNTHETIC inputs) | n | Coordinates | Batches | Family definite errors | Any abstention | Gate |
|---|---:|---:|---:|---:|---:|---|
| Poisson envelope/lane mean .4 | 20 | 60 | 10,000 | 0 | 2 | No undercoverage detected |
| Poisson envelope/lane mean 3.75 | 20 | 60 | 10,000 | 0 | 0 | No undercoverage detected |
| Conserved Poisson(24) split across 60 | 20 | 60 | 10,000 | 0 | 0 | No undercoverage detected |
| Capped Poisson total, dependent split | 20 | 60 | 10,000 | 0 | 0 | No undercoverage detected |
| Perfectly dependent coordinates | 20 | 60 | 10,000 | 0 | 0 | No undercoverage detected |
| Rare routed bursts, envelope 4 | 20 | 60 | 10,000 | 0 | 0 | No undercoverage detected |
| Small n, Poisson mean 3.75 | 2 | 1 | 10,000 | 2 | 0 | No undercoverage detected |
| Known zero input demand | 20 | 60 | 10,000 | 0 | 0 | No undercoverage detected |
| Sparse Poisson mean .02 | 20 | 60 | 10,000 | 0 | 0 | No undercoverage detected |
| Actual selected period-independent routing | 20 | 4 | 500 | 0 | 0 | No undercoverage detected |
| Actual selected representative-day routing | 20 | 4 | 500 | 0 | 0 | No undercoverage detected |
| Actual selected per-date routing | 20 | 8 | 500 | 0 | 0 | No undercoverage detected |

At 0/10,000 errors, the exact two-sided 95% binomial interval is `[0,.0003688199146187622]`; at 0/500 it is `[0,.007350610051907785]`. Small n has error 2/10,000, exact interval `[.000024221845640429847,.0007222800577237342]`. These quantify experiment uncertainty, not a new operational-risk allowance. Marginal tests, complete-coverage counts and widths are retained in `results.json`.

Routing cases called the **actual** `_run_selected_plan_des` 10,000 times per mode (30,000 wrapper calls; each static/per-date wrapper contains two period/date runs). Fixed synthetic inputs: identical lanes a/b, service samples [.02,.03] hours; two one-hour periods with total rates 2 and 4 customers/hour; two dates in per-date mode. Always-eligible symmetric lanes have algebraic expected routed counts 1 and 2 per lane-period under the ideal model. Whole vectors were retained in compressed NPZ files; no application database/API operation occurred (`DATABASE_URL=sqlite:///:memory:` before import).

Additional pause audit: **300 plan-date runs / 600 period checks PASS**, including breaks crossing the window boundary. An observational wrapper forwarded original RNG draws; the first wrapped/unwrapped full payloads matched exactly. Extending each potential stream gave routed counts no greater than its unpaused potential count. This checks coupling behavior, not an estimate of paused-routing true means. Trace limit 1 versus 10,000 preserved metric rows in all three mode preflights.

## Retained NovaMart fixture usefulness

Dataset: retained `seed-7.json` through `seed-11.json` from `output/seed-sensitivity-audit-2026-10-19/`, derived by the unchanged test helper from `tests/fixtures/novamart_events.csv` (1,600 rows, 14 day values, SHA256 `951d8f3d67af77f455396bac8bbb9adc072568ce0a1ac0df67b637e121fb6752`). Original field provenance remains unverified. Each payload has 20 representative-day DES repetitions, 13 one-hour periods, 60 required active lane-period pairs; units are count/hour and service completions/hour/counter.

Verified each active identity, its input-rate envelope and captured replication mean against persisted MC lambda. No absent count was filled with zero. All **300 external checks (60 per seed)** were insufficient; all five external candidate Decisions would be `insufficient_evidence`. The actual stored original Decisions remain conditional/conditional/revise/revise/revise; no record was updated.

Example: cashier_2, 13:00-14:00 has total period envelope Lambda=12.928571428571429 counts/hour-long period. Seed 7's mean lane rate is 3.75/hour, but the candidate interval is `[0,10.875616734192512]` customers/hour and the conditional stress-probability interval spans essentially `[0,1]`. It cannot resolve the unchanged .05 cap. Same unresolved conclusion holds at the other four means; this is not evidence of pass or failure. Overlapping historical seed batches are a usefulness example, **not independent calibration**, and identical insufficient labels do not close the original regression finding.

## Runtime, storage and independent read-back

Synthetic inference scale scenario: n=20, 100,000 coordinates with repeated envelope 24. The 16,000,000-byte count array took **71.52760509999644 seconds** with redundant per-coordinate configuration calculations. External caching keyed by frozen `(Lambda,n,m)` reduced the same scenario to **0.15237270000216085 seconds** (one miss, 99,999 hits). Cached/uncached bounds were bitwise equal for all saved routing batches in all three modes. Cache changes only the external verifier, not application source.

`verify_and_cache.py` exited 0 and independently checked original/corrected registration hashes, disjoint master-seed sets, saved-sample classifications, historical unresolved counts and cached bound equality. Actual cutoff for the scale scenario is B=22. The first benchmark's illustrative JSON row hardcoded B=24; the verifier used actual B=22, recomputed the truncated statistic and confirmed the byte count is unchanged. No storage acceptance relies on that placeholder.

Minimal four-field statistic JSON at that scale is **5,100,001 bytes**, above the inspected **default** result limit **524,288 bytes** (`backend/api/settings.py:198`, enforced in `workflow.py::_save_job`). The 100,000 coordinate scale matches the default upload row-cap magnitude, **not an established largest accepted selected plan**. Existing plans/jobs also have identity/trace/metadata overhead. Illustrative extra statistics for the 60-row fixture were 5,409–5,418 bytes; these are not actual serialized versioned job sizes. Do not change limits or claim a whole-job fit without testing.

NOT TESTED: diverse-envelope worst-case overhead, largest complete DES runtime, actual deployed limits, production image behavior and actual persistence of the proposed fields. No finite maximum for all supported arrival rates/plan shapes was established; trace cap is not a simulation-work cap. This research benchmark does not pass a universal largest-input acceptance gate.

## Remaining status and recommendation

The method has a conditional finite-sample derivation and no detected undercoverage in the stated experiments. It is very conservative at the existing budget. Do not present all-insufficient fixture output as a completed analytical-quality repair or a passed original test. Application/currentness/report behavior remains unchanged and NOT TESTED for the new method.

Inspection identified dependent report edits needed for any future integration: `backend/api/reports.py::_selected_report_chain` checks job linkage/currentness but no selected-load method version; `_selected_report_model` exposes raw MC diagnostics. `backend/reports/full_report.py::separate_full_sections` currently displays raw MC within-cap counts separately from validation. `backend/reports/separate_report.py::build_separate_report_model` copies selected MC/validation fields. A new gate must disclose its distinct evidence meaning and reject incompatible legacy chains for new reports/Decisions, while preserving historical records and shared/Current behavior.

The [proposed integration scope](../plans/2026-10-19-selected-load-revision-2-integration-proposal.md) is a reviewable next step if the owner accepts insufficient outcomes with the current budget. It requires explicit source/statistical-contract approval because this turn approved research only. A more precise method or a larger/adaptive replication budget remains a separate research/specification decision. No rebuild is needed for this document/external-prototype phase.

Native Excel/PDF fidelity, physical touch/true 200% zoom, qualified Filipino review and production/recovery items retain their previous separate NOT TESTED/UNKNOWN status; none was newly exercised here.

## Sources and reproducibility

- [Hoeffding (1963), Probability Inequalities for Sums of Bounded Random Variables](https://www.tandfonline.com/doi/abs/10.1080/01621459.1963.10500830): primary bounded-independent-variable result. The routing-envelope/truncation adaptation and elementary argument are project derivations with stated assumptions.
- [Official SciPy Poisson documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.poisson.html): PMF and survival/inverse-survival methods; independently checked by Decimal summation.
- [Official SciPy binomial-test documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html): exact binomial calibration checks and uncertainty intervals.

Commands from primary checkout: `./.venv/Scripts/python.exe -u output/selected-load-revision-2-2026-10-19/experiment-v3.py` and `./.venv/Scripts/python.exe output/selected-load-revision-2-2026-10-19/verify_and_cache.py`. They require retained prerequisite registration/numeric/synthetic files; v3 deliberately does not rerun completed synthetic experiments. Original attempts and all outcomes remain available. Final baseline/HEAD/staging preservation is recorded in `final-preservation.json`; full application suites were not rerun because no application/test source changed.
