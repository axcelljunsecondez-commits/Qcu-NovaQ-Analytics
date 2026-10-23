# Selected-load precision research: outcome and implementation boundary

Date: 2026-10-23. Status: research COMPLETE; application repair NOT IMPLEMENTED; seed-sensitive Decision finding OPEN; deployment held.

## Decision

**NO-GO for integrating this candidate as the seed repair.** The registered bounded binary-KL candidate produced narrower uncertainty intervals, but did not produce one additional supported lane-period classification at the unchanged 20-replication budget. All 60 checks in each of eight studied fixture batches remained insufficient: 480/480. Its prespecified usefulness gate therefore FAILED. No statistical application source, raw conditional MC verdict, Wilson interval, configured threshold, seed, cap or run limit was changed.

**GO for accepting the bounded research and the separately completed native save/cost verification as evidence within their stated boundaries.** Neither establishes operational safety, seed stability, a completed application repair or a successful release. The newer owner request holds deployment for a justified repair; the earlier option to release with the finding open does not override it.

## Scope, provenance and authority

The owner asked to repair seed sensitivity before deployment, then selected "Research a more useful, justified correction before implementation" after the earlier conservative method returned insufficient for all 60 checks. The approved research scope is recorded in docs/superpowers/specs/2026-10-23-selected-load-precision-research.md. That choice does not authorize statistical application integration.

- Candidate checkout: C:/Users/Administrator/.codex/worktrees/novaq-release/NovaQ.
- Branch: codex/supervisor-schedule-20261023. HEAD: 151486ee04147f013857f69fe8ce77d899388660. Supervisor changes remain uncommitted.
- Primary checkout is different: C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ, main at 6093d78a5874d8cbdfa0026e9c25bdb5ddc70881. It was not treated as the current application candidate.
- New experiment evidence: C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/output/seed-precision-research-20261023/ (called E below).
- Native save/cost evidence: primary-checkout output/supervisor-release-20261023/.
- Retained historical captures: primary-checkout output/seed-sensitivity-audit-2026-10-19/seed-{7,8,9,10,11}.json.
- Fresh application captures use tests/fixtures/novamart_events.csv and the unchanged tests/test_selected_mc_load.py helper chain, in temporary SQLite. This is repository-fixture evidence, not verification of a live saved analysis, an authenticated historical paper execution or future operations.

E/registration.json was written before execution at 2026-10-23T09:57:13.4038303Z. It pins 18 source/protocol/input files by SHA-256, including the research scripts, specification, current workflow/DES services, unchanged seed test and fixture, earlier research and retained captures. Registration SHA-256 is e556c18c05102ae13ef5fe7c216d761e4a2fbf47dba9946c1e7b278640658589. Both the experiment and independent review checked the pinned hashes. This is local registration, not an external preregistration service or a claim that every transitive dependency is hashed.

## Reconfirmed application finding

VERIFIED: the unchanged regression was executed with its xfail disabled by pytest --runxfail. It failed its original assertion that all Decisions agree. Evidence: primary-checkout output/supervisor-20261023/seed-regression-current.log; source tests/test_selected_mc_load.py:147-168.

| DES base seed | 7 | 8 | 9 | 10 | 11 |
|---|---:|---:|---:|---:|---:|
| Failing conditional-MC lane checks | 0 | 0 | 2 | 1 | 1 |
| Actual Decision | conditional | conditional | revise | revise | revise |

MC seed was 42. The differing pairs included 13:00-14:00/cashier_1 and cashier_2. The regression result was 1 FAILED, not a passing expected-failure result. Its strict xfail marker and assertions remain unchanged. The fresh capture test later passing means capture assertions passed; it is not a passed stability regression.

Source trace in the candidate checkout:

- backend/api/workflow.py:2524-2526 bounds load_replications at 1-20, default 20.
- workflow.py:2620 (_run_selected_plan_des) and :2846 (_run_selected_plan_day_des) execute selected-plan routing.
- workflow.py:2812-2843 (_attach_mean_routed_loads) computes and stores mean routed arrivals and replication metadata. It does not persist complete replication-level count vectors for downstream uncertainty inference.
- workflow.py:3034 (run_selected_mc) consumes those mean routed rates and preserves the existing configured perturbation/Wilson contract; :1291 (_separate_validation_verdict) is the shared separate validation verdict logic. Changing upstream routed means can change the conditional MC and Decision even when MC seed 42 stays fixed.
- backend/queueing_engine/services/separate_optimization.py:421 defines base+r replication seeds; :852 creates the paired RNG streams; :1689 derives per-date seeds. Static period execution reuses some seed numbers across different coordinates within a batch. This is recorded, not silently repaired by the research.

These are distinct uncertainties: MC trials conditional on supplied means, finite DES replication uncertainty in those means, and uncertainty in the original estimated input rates/service model. This candidate addresses only the second, conditional on the first-stage inputs and simulation assumptions. It does not estimate the third.

## Candidate and conditional derivation

PROPOSED AND TESTED EXTERNALLY: replace only the earlier auxiliary truncated-count Hoeffding interval with a bounded-mean binary-KL interval. No application import or integration exists.

Let X be a nonnegative integer routed lane-period arrival count, h the positive period duration in hours, and N the potential-arrival Poisson envelope with fixed mean Lambda. The earlier source/coupling argument requires X <= N under the applicable modeled mapping. It does not assert that routed X is itself Poisson. The known bound on its mean is [0,Lambda]. Break pauses only support that envelope under the documented nonnegative-delay coupling; they do not establish equality or a known routed mean.

For the same input-only cutoff B as the earlier method, set Y=min(X,B), Z=Y/B and n=20. With m lane-period coordinates and alpha=.05, invert

    kl(mean(Z), p) <= log(2*m/alpha)/n

to obtain [l,u]. Since

    0 <= E[X]-E[Y] <= delta(B)
    delta(B) = Lambda*P(N>=B) - B*P(N>=B+1),

the count-mean interval is [B*l, B*u+delta(B)], intersected with [0,Lambda]. Rate bounds divide by h. The implementation adds an outward floating-point guard, validates complete nonnegative integer evidence and abstains for unsupported/invalid inputs or empty intersections. The registered numeric domain is Lambda <= 1000, n=2-20. Known zero demand is distinct from observing 20 zeros at a positive envelope.

The bounded-mean inequality is supported by [Foong, Bruinsma and Burt (2022), Theorem 3](https://arxiv.org/html/2205.07880), for independent identically distributed observations in [0,1]. A union allocation alpha/m controls the coordinate family under that assumption without requiring independence across lanes. The project-specific Poisson envelope, routing correspondence, inputs and replication assumptions still require their own justification; the paper proves none of those NovaQ facts. The argument assumes ideal independent marginal replication streams. Distinct PRNG seed numbers are evidence of nonreuse, not a mathematical proof of random-stream independence.

The existing independent-uniform stress event is used only to propagate rate endpoints externally: arrival multiplier A in [.8,1.2], service multiplier S in [.9,1.1], event rho*A/S > configured threshold. It is conditional on fixed mu, staffing and perturbation assumptions. The application's simulation method and Wilson intervals were not replaced.

Implementation/reference locations under E: kl_candidate.py:13 (settings and tail), :32 (inverse), :51 (vector intervals); research.py:63 (numeric checks), :146 (synthetic calibration), :172 (routing), :214 (fixture use), :247 (hash checks and gates).

## Execution and actual results

The first fixture-capture attempt stopped with "OpenBLAS error: Memory allocation still failed after 10 retries, giving up." It produced no fresh JSON or JUnit result; its exit code was not retained. E/fresh-capture.log is retained. A read-only OS memory query was denied by the runtime and did not establish system free memory. The cause beyond the library-reported allocation failure is UNKNOWN.

Before retrying, E/execution-amendment-01.json recorded execution-only thread limits OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1, MKL_NUM_THREADS=1 and NUMEXPR_NUM_THREADS=1. Scripts, estimator, registered hashes, seeds, count limits and acceptance criteria were unchanged. The same frozen capture then passed: 1 test in 29.18s, exit 0. E/fresh-capture-retry.log/.xml and fresh-seed-{42,106,170}.json retain the evidence. Each captured 20 actual conserved DES replications through MC, Validation and Decision; MC seed remained 42. The three fresh batches' master-seed ranges were disjoint, including the static period offsets.

The registered experiment exited 0 in 83.85s. Exit 0 means the research ran to completion, not that its usefulness gate passed. Runtime: Python 3.13.13, NumPy 2.2.6, SciPy 1.18.1. E/run-start.json, research.log and results.json record versions/results.

| Gate | Actual result | Classification |
|---|---|---|
| Numerical references, domain/invalid evidence, units, endpoints, nesting | 65 groups passed, including 48 inversions against 80-digit Decimal references | VERIFIED / PASS within tested domain |
| Synthetic calibration | Nine cases x 10,000 independent generated batches; no registered rejection | VERIFIED observation; universal coverage NOT ESTABLISHED |
| Current routing calibration | Three modes x 500 disjoint batches x 20 replications; all recorded conservation/status checks passed, no registered rejection | VERIFIED within constructed symmetric fixtures |
| Fixture usefulness | 0 additional supported classifications; 480/480 insufficient across eight batches | VERIFIED / FAIL |
| Independent arithmetic review | 18 registered hashes, 48 inverse checks, nine regenerated synthetic cases, three stored routing arrays, all 480 fixture rows reproduced | VERIFIED / PASS for evidence arithmetic |
| Application statistical repair / seed-finding closure | No application integration; original failing regression preserved | NOT IMPLEMENTED / OPEN |

Calibration rejects if any of 24 one-sided exact binomial tests has p < .05/24. Each case tests family definite-error rate against .05 and its first coordinate against .05/m. Lack of rejection is not a proof of coverage. Exact 95% binomial intervals and p-values are retained in synthetic-results.json and routing-results.json; independent review recomputes them using binomial survival probabilities and beta quantiles.

| Synthetic case | Batches | Family definite errors | First-coordinate errors | Batches with any abstention |
|---|---:|---:|---:|---:|
| Poisson mean .4, 60 coordinates | 10,000 | 199 | 2 | 1 |
| Poisson near fixture scale | 10,000 | 0 | 0 | 0 |
| Conserved Poisson split | 10,000 | 0 | 0 | 0 |
| Dependent capped-total split | 10,000 | 0 | 0 | 0 |
| Perfect positive coordinate dependence | 10,000 | 1 | 1 | 0 |
| Rare routed burst | 10,000 | 0 | 0 | 0 |
| Small n (n=2) | 10,000 | 5 | 5 | 0 |
| Known zero demand | 10,000 | 0 | 0 | 0 |
| Sparse demand | 10,000 | 0 | 0 | 29 |

Abstentions are not passing classifications. The frozen script's mean-width diagnostic includes empty intersections in the two cases with abstentions; it must not be interpreted as a valid-interval width there. Independent-review.json additionally reports widths restricted to valid coordinates, complete covered-family counts and abstentions. The registered rejection counts and fixture conclusions are unchanged.

The three current routing cases (period_independent, representative_day, per_date) each had zero family errors, zero sentinel errors and zero abstaining batches among 500. Their known means come only from constructed identical symmetric lanes, randomized ties, no breaks, and known modeled total arrival intensities 2 or 4 customers/hour over one-hour periods. Per-lane expected counts are half those totals by label symmetry. These known means do not apply to the unequal/break-affected NovaMart fixture. Raw counts are retained as fresh-routing-*.npz.

Master-seed identities were checked: static 10,500 distinct, representative-day 10,000, per-date 20,000, with no cross-batch or cross-mode aliases. Static mode retains 9,500 duplicate calls across different coordinates within batches; the per-coordinate assumptions and family union allocation do not require those coordinates to be independent. No claim of proven PRNG independence is made.

## Fixture usefulness and concrete calculation

| Fixture DES base | Evidence | Actual configured-run Decision | MC seed | New bound pass / fail / insufficient | Additional supported vs old bound |
|---|---|---|---:|---|---:|
| 7 | retained, overlapping | conditional | 42 | 0 / 0 / 60 | 0 |
| 8 | retained, overlapping | conditional | 42 | 0 / 0 / 60 | 0 |
| 9 | retained, overlapping | revise | 42 | 0 / 0 / 60 | 0 |
| 10 | retained, overlapping | revise | 42 | 0 / 0 / 60 | 0 |
| 11 | retained, overlapping | revise | 42 | 0 / 0 / 60 | 0 |
| 42 | fresh current, disjoint | conditional | 42 | 0 / 0 / 60 | 0 |
| 106 | fresh current, disjoint | conditional | 42 | 0 / 0 / 60 | 0 |
| 170 | fresh current, disjoint | conditional | 42 | 0 / 0 / 60 | 0 |

Historical overlapping batches are usefulness evidence, not independent coverage calibration. Three fresh configured-run Decisions agreeing does not contradict or close the failing unchanged five-base regression.

Average interval-width reduction on these fixture batches was 4.668%-5.286%. There were no additional supported decisions. For the fresh base-42 13:00-14:00/cashier_2 row, the observed mean routed rate was 3.5 customers/hour, with input envelope Lambda=12.928571428571429 arrivals over h=1 hour. The new interval was [0.3816834429,10.4644111973] customers/hour; the previous one was [0,10.6256167342]. Propagated conditional failure probability ranged effectively from 0 to 1, straddling cap .05. A raw conditional MC PASS at the point estimate cannot turn that broad rate interval into a supported robustness claim. E/fixture-results.json retains all endpoints, source means, identities and classifications.

Post-experiment independent-review.py does not import the candidate. It independently uses scalar logarithms/Brent inversion, positive Poisson PMF tail sums, quadrature over the stress event and beta/binomial probability calculations. It verifies counts/identities and rates against all 20 replications, not rounded screenshots. Its PASS_EVIDENCE_ARITHMETIC_REPRODUCED_NOT_INTEGRATION_APPROVAL status is deliberately limited. It is not a second preregistered estimator or an independent real-world dataset.

## Smallest justified next step

1. Do not merge this candidate or remove/relax the strict xfail. The registered usefulness criterion failed; relabeling all outcomes insufficient would not meet the owner's request for a useful correction or close the original raw-MC regression.
2. Keep seed 42 and existing caps, limits and thresholds unchanged. More conditional MC trials alone do not address changing DES-derived means. Selecting a favorable DES seed would not establish robustness.
3. PROPOSED, NOT TESTED: prepare a separately registered offline precision-versus-runtime study before changing the application replication budget. Define the decision margin, desired simultaneous uncertainty guarantee, finite runtime ceiling and an explicit insufficient-evidence outcome. A larger budget may help; this experiment does not establish the number required or guarantee a decision near the boundary. Repeatedly inspecting fixed-n intervals and stopping at a favorable answer would require a justified multiple-look/sequential procedure. No such procedure or larger bound is approved or implemented here.
4. Before any eventual source correction, reconcile the raw conditional MC contract with selected-load uncertainty, persist enough replication evidence, define freshness/export/provenance behavior, independently calibrate the final method, and obtain concrete scope approval. Mathematical changes need their own plan and regression gate; the new UI does not resolve them.

This is a NO-GO for this estimator's application integration, not evidence that every possible finite-sample method is unusable or that Hoeffding is necessary. A general impossibility claim at n=20 has not been proved. The remaining useful method/budget choice is UNKNOWN.

## Native saves, costs and release status

The independent native save/cost work is complete within its stated boundary. See docs/superpowers/plans/2026-10-23-supervisor-schedule-verification.md, native addendum: 17 PostgreSQL supervisor tests passed, including a competing transaction after the last read and synchronized simultaneous applies; 91 cost/ROI/report/save tests and 3 subtests passed; final Ruff and mypy passed. A new temporary PostgreSQL container reused the existing image; its exact ID/label/image were checked and it was removed after evidence collection. The final read-only Docker inventory probe later failed because the engine pipe was unavailable, so the current running-container inventory is UNKNOWN; no engine repair/restart was attempted. Original successful execution logs remain evidence of the tests, not current Docker availability.

Baseline comparison in output/supervisor-release-20261023/closure-evidence.json shows no production application source hash changed during this research/native-verification phase. Two focused PostgreSQL tests and verification documents changed; the new research specification, report and output evidence were added. Existing uncommitted supervisor changes remain separate and preserved. Nothing was staged, committed or pushed. No production data/configuration/migration/deployment or live account change occurred. Current GitHub main and production status were not established by this local study; the read-only gh query was unauthenticated. Earlier full backend/frontend gates remain earlier evidence, not fresh reruns after test additions.

Remaining status: seed repair OPEN; statistical integration NOT IMPLEMENTED; precision/budget choice UNKNOWN; production release NO-GO under the current repair-first instruction. Native Excel verification and operational-safety claims are outside this research and are not closed by it.

## Reproduction

Use the existing primary-checkout .venv/Scripts/python.exe, candidate checkout on PYTHONPATH and the frozen E scripts. Execute with PYTHONDONTWRITEBYTECODE=1 and the four one-thread variables listed in execution-amendment-01.json. Fixture capture requires NOVAQ_ENV=development and no NOVAQ_TEST_DATABASE_URL; its fixtures create temporary SQLite, not a live database. Retain registration.json and verify its 18 file hashes before execution.

Recorded command forms (absolute E and candidate paths are given above):

    python -B -m pytest -c <candidate>/pyproject.toml -p tests.conftest <E>/fresh_seed_probe.py -q -s --tb=short -p no:cacheprovider -o addopts= --junitxml=<new-evidence-path>/fresh-capture.xml
    python -B <E>/research.py
    python -B <E>/independent-review.py

The scripts write their JSON/NPZ/log evidence beside themselves. For a new run, preserve/copy the evidence package and scripts to a new output directory before executing rather than overwrite this completed run; review path assumptions and register any required path-only harness amendment before starting. New results must not be substituted for this dated run. No commit or production deployment command is part of reproduction.
