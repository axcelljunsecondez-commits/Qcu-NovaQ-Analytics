# Selected-load uncertainty: candidate rejected before integration

Date: 2026-10-19. **Status: PARTIAL / application integration BLOCKED by failed method gate.** Owner approved the [specification](../specs/2026-10-19-selected-load-uncertainty.md) and [plan](../plans/2026-10-19-selected-load-uncertainty-plan.md). Their mandatory pre-integration gate was executed; it rejected the proposed Student-t/Bonferroni candidate. The original seed-sensitive Decision finding remains OPEN. Approval is not evidence of statistical validity.

## Scope and actual changes

VERIFIED: isolated prototype and calibration only. No NovaQ application, test, fixture, request/response, database or runtime behavior was edited. No new production statistics helper was added. Existing xfail/assertions remain unchanged. No Docker command, rebuild, activation, commit, push or deployment occurred.

Worktree: `.claude/worktrees/ux-workflow-audit`, branch `feat/ux-u1-shell`, HEAD `0b9423ec66d32620ed91769ac35a10e51ffae2ec`. Pre-existing dirty work was baselined and preserved. Changes to repository documents: approval/gate status in the existing spec, plan and handoff; this report; a separate revised-method proposal. External evidence lives in the primary checkout at `output/selected-load-uncertainty-2026-10-19/`.

## Prespecified experiment

`preregistration.json` and `calibrate.py` were SHA256-recorded in `registration-record.json` at `2026-10-19T06:14:15.153699+00:00`, before `run-start.json` at `06:14:23.926855+00:00`. The verifier confirmed both hashes remained unchanged. The preregistration hash is `b60c3698d41133f80558edc7886871c9e2a6c462727a0ebc1dfa687b0579ba40`.

- Nine SYNTHETIC calibration cases, 10,000 independent batches each (90,000 total). Known population means; no reference-mean estimation error. Count units are customers per one-hour period, numerically equal to customers/hour in these calibration cases. Normal controls are synthetic rates. A separate half-hour reference verifies count-to-rate conversion.
- Each batch contains n independent full replication vectors; m=1 or 60 coordinates. Multinomial vectors conserve 24 counts across 60 categories within each replication and have dependent coordinates. They do not reproduce NovaQ shortest-system routing. Separate PCG64 streams derive from `SeedSequence(202610190317, spawn_key=(case_index,))`; batches do not reuse overlapping DES seeds.
- Candidate: mean +/- `t.ppf(1-.05/(2*m), n-1) * sample_sd/sqrt(n)`, lower clipped at zero. Zero variance/missing/invalid evidence abstains. No posthoc low-count exclusion or replacement estimator.
- Family definite error: at least one issued interval excludes its known true mean. An abstention is neither coverage nor definite error; complete family coverage and abstentions are reported separately. Sentinel coordinate 0 also has a marginal error check at `.05/m`.
- Reject any of 18 prespecified checks (family and sentinel for each case) using a one-sided exact binomial test with allocation `.05/18`. Report two-sided 95% exact binomial uncertainty plus simultaneous one-sided lower bounds. This guards against treating calibration noise as a failure. No rejection does not prove validity, especially with abstentions.

These are method experiments, not operational observations, new NovaMart measurements, or executions of the NovaQ DES. The 3.75 scale was motivated by the previous fixture run; it is not a fitted population truth. Actual routed-count distributions must not be assumed Poisson.

## Executed results

Command from primary checkout:

```powershell
./.venv/Scripts/python.exe output/selected-load-uncertainty-2026-10-19/calibrate.py
```

Exit **1**, deliberately signaling the failed acceptance gate; no unexplained exception. Harness time **8.8522793000011 seconds**, excluding interpreter/import startup. Python 3.13.13, NumPy 2.2.6, SciPy 1.18.1 on Windows. Host SciPy differs from the application's 1.17.1 production lock; this was an external method experiment, not exact-image verification. Independent quantile/deterministic checks below corroborate the rejection.

| Synthetic case | n | m | Family definite error / 10,000 | Complete family coverage / 10,000 | Any abstention / 10,000 | Calibration gate |
|---|---:|---:|---:|---:|---:|---|
| Normal mean 10, SD 1 | 20 | 1 | 508 | 9,492 | 0 | No undercoverage detected |
| Normal mean 10, SD 1 | 20 | 60 | 488 | 9,512 | 0 | No undercoverage detected |
| Poisson mean 3.75 | 20 | 1 | 480 | 9,520 | 0 | No undercoverage detected |
| Poisson mean 3.75 | 20 | 60 | **805** | 9,195 | 0 | **FAIL** |
| Poisson mean 0.4 | 20 | 60 | **5,420** | 4,499 | 193 | **FAIL** |
| Multinomial total 24, 60 categories (mean 0.4) | 20 | 60 | **5,444** | 4,476 | 182 | **FAIL** |
| Poisson mean 3.75 | 2 | 1 | 0 | 8,579 | 1,421 | No undercoverage detected; abstentions |
| Poisson mean 3.75 | 5 | 60 | 378 | 9,153 | 487 | No undercoverage detected; abstentions |
| Poisson mean 0.02 | 20 | 60 | 0 | **0** | **10,000** | Entirely inconclusive |

Error and abstention categories can overlap within a family; they must not be added as a partition. Every count, sentinel check and exact interval is recorded in `results.json`.

For mean 3.75/m=60, family error is **8.05%**, exact 95% CI **7.5240–8.6005%**; the multiplicity-adjusted one-sided lower bound is **7.3137%**, exceeding 5%. One-sided binomial p=`2.39236483142846e-38`.

For mean 0.4/m=60, family definite error is **54.20%**, exact 95% CI **53.2174–55.1802%**. Dependent multinomial family error is **54.44%**, exact 95% CI **53.4577–55.4197%**. The corresponding floating-point binomial p-values underflowed to 0; these are not claims that the mathematical probabilities equal zero.

VERIFIED numerical checks: **45 recorded reference/check groups passed**, including six t quantiles independently inverted by quadrature of the gamma-normalized density (df 1/9/19, m 1/60; tolerance 1e-8), moments and hours conversion, eight invalid/zero-variance cases, 36 exact conditional stress-area comparisons against adaptive quadrature (tolerance 1e-9), monotonicity/endpoint propagation and unrounded cap-equality rules. These do not establish valid confidence coverage for counts.

## Deterministic corroboration, independent of calibration draws

For 20 independent Poisson(0.4) counts and m=60, let E_k be the event that exactly k replications contain one count and every other replication is zero, k=1 or 2. Both events have positive sample variance, so neither is an abstention. The candidate upper bounds are **0.2481613488613** and **0.3727679876427**, both below the known mean **0.4**.

By direct enumeration, `P(E_k) = choose(20,k) * .4^k * exp(-8)`. The disjoint events alone imply marginal error at least **0.0128817649114565**, exceeding `.05/60 = .0008333333333333`. With 60 independent coordinates this implies family error at least `1-(1-.0128817649114565)^60 = .540642846831395`. This is a synthetic counterexample, not a bound on actual NovaQ lane error.

`verify_results.py` recomputed those moments/probabilities separately, used the quadrature-inverted quantile rather than the candidate ppf value, verified preregistration integrity/timing, and checked all recorded counts. Command exited **0**; `independent-verification.json` records corroboration of rejection, not repair.

## Consequence and remaining verification

VERIFIED: three prespecified cases fail; this candidate does not meet its own count-data validation gate. Normal controls show no detected undercoverage; a universal bug in the interval arithmetic does not explain the count failures. Bonferroni allocation cannot fix invalid marginal intervals.

NOT TESTED / intentionally stopped: application integration, versioned evidence/freshness/report handling, new selected Decision classification, all-three-mode regressions, post-repair five-seed/holdout tests, largest-input runtime acceptance and Docker build/runtime verification. Full backend/frontend/Ruff/mypy suites were not rerun because application/test files were not edited and integration was stopped. The earlier original five-seed failure remains the existing evidence; it was not relabeled or rerun here.

UNKNOWN: actual routed-DES coverage of this candidate; the synthetic failures reject the general candidate but do not measure its error rate on the NovaMart fixture. The [revised proposal](../specs/2026-10-19-selected-load-uncertainty-revision-2.md) remains PROPOSED. No replacement method is silently authorized or implemented. Native Excel, PDF fidelity, physical touch/true 200% zoom and qualified Filipino review retain their existing separate NOT TESTED status; production/recovery remains outside this scope.

## References

- [SciPy Student-t documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.t.html): ppf and density used for the numerical reference; not a justification for applying t intervals to arbitrary counts.
- [SciPy binomial test documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html): exact binomial test and proportion intervals for calibration error uncertainty.
- [Law (2023), Design and Analysis of Simulation Experiments Using Three Simple Statistical Formulas](https://informs-sim.org/wsc23papers/124.pdf): replication/output analysis motivation; not proof of finite-sample calibration for this routed-count estimator.

All application/test/configuration baseline hashes, HEAD and staging are checked separately in `final-preservation.json`; that file is the final preservation authority for this turn.

Tooling correction: an initial preservation-output capture used an unnecessary `core.autocrlf=false` override and failed decoding Git output with Windows cp1252 (`UnicodeDecodeError`, then `TypeError`). It did not modify files. Repeating `git diff --check` with repository defaults and byte capture exited 0 with empty stdout; existing LF/CRLF advisory warnings remained on stderr. This was a harness capture failure, separate from the genuine statistical rejection above.
