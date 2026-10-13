# Large server-count and capacity numerics for M/M/c, M/G/c, M/M/c/K, M/G/c/K

- Status: **OD-N1 APPROVED** by the owner 2026-10-13 (recursion for `mmc`, fallback for `mmck`, `mgc` text), implemented, uncommitted (§8). **OD-N4 APPROVED** by the owner 2026-10-13 (limit of 24,000,000 counter-trials), implemented, uncommitted (§10). **OD-N6 RESOLVED** 2026-10-13: no version bump is needed (§11). OD-N2, OD-N3 and OD-N5 are open.
- Date: 2026-10-12
- Protected scope: `backend/queueing_engine/models/queue_models.py` (AGENTS.md §5, Protected Mathematics). This document does not authorize a mathematical change.
- Investigated code: worktree `ux-workflow-audit`, branch `feat/ux-u1-shell`, HEAD `4a4fc58b`. The engine file has no uncommitted changes there (`git diff --stat HEAD -- backend/queueing_engine/` is empty).
- This file was written in worktree `clever-boyd-87ff32` (branch `claude/keen-feistel-626da0`) because that session may not write into another worktree. It is uncommitted.
- Evidence labels follow AGENTS.md §2.

## 1. Summary

`mmc()` and `mmck()` compute probabilities from raw powers and factorials (`offered_load ** n`, `math.factorial(n)`, `c ** (n - c)`). When an intermediate value is larger than the largest double (about 1.8e308), Python raises `OverflowError`. The functions catch it and return `stable=False` with a "numerical instability" error. Lightly loaded systems therefore come back as not stable, and `mgc()` then reports the failure as "Unstable system", which is false.

The failure region is **wider than "c >= 171"** (§2.2). At realistic loads it starts around 144 to 162 counters. Any offered load above about 142.9 Erlangs cannot be computed by M/M/c for any server count. M/M/c/K fails from K = 231 at c = 24 and 80 % load.

Proposal:

- (a) M/M/c through the Erlang B recursion and the Erlang B to Erlang C identity.
- (a') M/M/c/K through closed-form log weights.
- (b) `mgc` reports a numerical failure as a numerical failure.
- (c) Tests and a pin-safety argument.

## 2. Verified findings

### 2.1 Reproduction (VERIFIED, run 2026-10-12 against `feat/ux-u1-shell` @ `4a4fc58b`, Python 3.13.13)

The scripts are read-only and import the repository code without modifying it. They live in the session scratchpad (`probe_large_c.py`, `pin_grid.py`, `mmck_closed_log.py`). Their essential cases are reproduced here so the results can be rerun.

| Call | rho | stable | error |
|---|---|---|---|
| `mmc(1, 1, 170)` | 0.00588 | True | — (Lq = 3.0e-310, subnormal) |
| `mmc(1, 1, 171)` | 0.00585 | **False** | Calculation failed due to numerical instability. |
| `mmc(150, 1, 171)` | 0.877 | **False** | Calculation failed due to numerical instability. |
| `mgc(1, 1, 5000, 1)` | 0.0002 | **False** | **Unstable system: lambda must be less than c * mu for M/G/c.** (false) |
| `mgc(1, 1, 171, 1)` | 0.00585 | **False** | **Unstable system: …** (false) |
| `mgc(200, 1, 171, 1)` | 1.17 | False | Unstable system: … (true) |
| `mmck(1, 1, 171, 171)` | None | **False** | M/M/c/K calculation failed due to numerical instability. |
| `mmck(1, 1, 2, 1100)` | None | **False** | M/M/c/K calculation failed due to numerical instability. |
| `mmck(10, 1, 11, 400)` | None | **False** | M/M/c/K calculation failed due to numerical instability. |
| `mmck(0.5, 1, 1, 100000)` | 0.5 | True | — (c = 1 never overflows) |
| `mgck(1, 1, 2, 1, 1100)` | None | **False** | passes the M/M/c/K error through (truthful) |
| `erlang_a(1, 1, 171, theta=0)` | 0.00585 | **False** | delegates to `mmc` (queue_models.py:514) |
| `erlang_a(1, 1, 171, theta=0.5)` | 0.00585 | True | — (already log-space, unaffected) |
| `mmc_priority(0.5, 0.5, 1, 171)` | — | — | **raises `TypeError`** (`None / float`). There is no production caller; it is only exported from `models/__init__.py`. |

The overflow mechanism (VERIFIED by reading queue_models.py:173-183 and 293-299):

- `math.factorial(c) * (1.0 - rho)` converts an int above about 1.8e308 to float, which happens for c >= 171.
- `offered_load ** c` overflows a float when c·log10(a) > about 308.25.
- In `mmck`, `math.factorial(c) * (c ** (n - c))` overflows during int-to-float conversion.

### 2.2 Failure boundaries (VERIFIED, measured)

`mmc(rho·c, 1, c)`, smallest failing c >= 2:

| rho | 0.5 | 0.7 | 0.8 | 0.9 | 0.95 | 0.99 | at a = 1 |
|---|---|---|---|---|---|---|---|
| first failing c | 162 | 153 | 149 | 146 | 145 | 144 | 171 |

- The largest offered load (step 0.1) for which any server count can be computed with M/M/c is **142.9 Erlangs**. Above that, every candidate fails.
- `mmck(0.8c, 1, c, K)`, smallest failing K: c=2 → 1025, c=5 → 444, c=10 → 312, c=24 → **231**, c=50 → 193, c=1 → never.

**CONFLICTING with the brief:** the brief describes the defect as c >= 171. The measured region also covers c from 144 to 170 at realistic loads, and modest K at any c >= 2.

### 2.3 Where large c or K can reach the functions (VERIFIED by reading code; the user-visible outcome is VERIFIED by a run where marked)

| Entry | Bound on c / K | Path | What the user sees |
|---|---|---|---|
| `POST /analysis/{model}` (`backend/api/analysis.py:33-38`) | c >= 1, K >= 1, **no upper bound** | direct `mmc`/`mgc`/`mmck`/`mgck`/`erlang_a` | The raw engine dict. For `mgc` that is the false "Unstable system" text. |
| `POST /public/calculator/{model}` (B2, `backend/api/public_calculator.py`, **uncommitted** on `feat/ux-u1-shell`) | same `AnalysisRequest` | same | The Quick calculator UI decides "Can counters keep up?" from rho >= 1 and shows "not calculated" otherwise (`frontend/src/lib/quickCalculator.ts:97`, VERIFIED by reading). The raw API response still carries the false text. |
| Upload ingestion (`backend/data/ingestion.py`, `validate_and_normalize`) | c, K in 1..100000 | `process_segments` / `analyze_segments` → `select_model` (`data_processing.py:174`, `model_explanations.py:61`) | VERIFIED by a run: `process_segments(c=171, variance=1)` gives model M/G/c, rho 0.00585, **status "Lean"**, `stable False`, warning "Unstable system…". The Results table classifies `stable === false` as "Unstable"/can't keep up (`frontend/src/lib/results.ts:26-35`, `ResultsDetails.tsx:46-51`), so a nearly idle period is shown as unable to keep up. |
| Setup (`backend/api/analysis_schemas.py:124-127`) | `fixed_server_count`, `total_system_capacity` 1..100000 | same as uploads | same |
| Legacy optimizer `optimize_segment` (`backend/api/optimization.py:58-85`, `max_servers <= 256`; UI `OptimizePage.tsx:931`, max 256, default 24) | candidates up to 256; current c up to 100000 | `_queue_metrics` → `select_model` | VERIFIED by a run: λ=180, μ=1, c=200, max 256 gives `NO_FEASIBLE_CONFIGURATION`, violated `model_stability`, `target_utilization`, `analytical_metrics`, although 190 counters would be stable at rho ≈ 0.947. VERIFIED by a run: λ=1, c=200, variance 1 gives `FEASIBLE`, c_optimal 2, `warning` **"Unstable system: lambda must be less than c * mu for M/G/c."**, which `OptimizePage.tsx:1282` displays. |
| Shared-line segments (`shared_segments.evaluate_segment`, `shared_segments.py:300`); shared capacity (`shared_capacity.py`, `MAX_CANDIDATE_SERVERS = 256`) | servers up to 256 for candidates | `select_model(lambda, mu, servers)` → `mmc` | VERIFIED by a run: servers=171 gives status `CALCULATION_FAILED`, note "Calculation failed due to numerical instability." (truthful, because shared code distinguishes `is_saturated(rho)` at `shared_segments.py:305-310`). Candidates from 144 to 256 are lost as infeasible. |
| Monte Carlo (`mc_simulate_segment`, `simulation.py:1183-1185`) | c from the segment (up to 100000) | `mmc` per trial | VERIFIED by a run: c=171, λ=1 gives `status "PASS"`, `failure_rate 0.0`, `Wq_mean None`, `Lq_mean None`, `error None`. A PASS is reported although no trial produced a waiting time. |
| Separate-queue optimizer (`separate_optimization.py:326`) | c fixed to 1 | `mg1` | Not affected. |
| Reports (`backend/reports/`) | — | consume stored rows | No direct engine call (grep, VERIFIED). They inherit whatever rows were stored. |
| Erlang-A (theta > 0) | — | log-space birth-death | Not affected (VERIFIED by a run). |

## 3. Proposal

### 3.1 (a) M/M/c through the Erlang B recursion (PROPOSED)

With a = λ/μ and ρ = a/c:

- Erlang B recursion: B(0) = 1, B(n) = a·B(n−1) / (n + a·B(n−1)).
- Erlang C from B: C = B(c) / (1 − ρ·(1 − B(c))).
- Lq = C·ρ/(1 − ρ). Then Wq = Lq/λ (0 when λ = 0), W = Wq + 1/μ, L = λ·W, in the **same order and with the same guards as the current code**.

Derivation (reproducible, checked here). Let S = Σ_{n<c} aⁿ/n! and T = a^c/c!.

- The current code computes p0 = 1/(S + T/(1−ρ)) and Lq = p0·T·ρ/(1−ρ)², so Lq = C·ρ/(1−ρ) with C = (T/(1−ρ))/(S + T/(1−ρ)).
- With B = T/(S+T), dividing by (S+T) gives C = B/((1−ρ)(1−B) + B) = B/(1 − ρ(1 − B)).
- From 1/B(n) = 1 + (n/a)·(1/B(n−1)) follows the recursion.

Every quantity stays in [0, 1], so nothing can overflow.

Sources:

- REPORTED: the recursion and the B to C identity are standard. See H. C. Tijms, *A First Course in Stochastic Models*, Wiley, 2003, in the treatment of the Erlang loss and delay models; and D. Gross, J. F. Shortle, J. M. Thompson, C. M. Harris, *Fundamentals of Queueing Theory*, 4th ed., Wiley, 2008, M/M/c and M/M/c/c sections.
- UNKNOWN: section and page numbers were not checked against the books in this session.
- The derivation above and the exact-arithmetic comparison below are the evidence this proposal relies on.

Accuracy (VERIFIED by a run):

- Grid: c = 1..170 × 21 loads (0 to 0.999999) × μ ∈ {0.25, 1, 1.05, 4, 37.5}. That gives 16,515 cases the current `mmc` computes and 1,335 it fails.
- Maximum relative difference between the proposal and the current code: Lq 3.4e-15, Wq 3.5e-15, W 1.6e-15, L 1.6e-15, rho 0.
- Values below 1e-300 (subnormal) were excluded, 5,126 metric values.
- Against an exact `fractions.Fraction` reference on 62 cases (c up to 170, rho 0.01 to 0.99): current 1.29e-14, proposal 1.27e-14. The worst-Lq grid case (λ=275.625, μ=37.5, c=147) has exact 4.553475760951643e-134, current …612e-134, proposal …628e-134.
- Beyond 170, reference cases:

| λ, μ=1, c | Proposed Lq | Reference | Rel. diff | Reference method |
|---|---|---|---|---|
| 150, 171 | 0.4298670649541082 | 0.42986706495410837 | 3.9e-16 | exact Fraction |
| 200, 250 | 0.0015489421656682447 | 0.0015489421656682436 | 7.0e-16 | exact Fraction |
| 4500, 5000 | 1.1626486270673953e-12 | 1.1626486270673929e-12 | 2.1e-15 | exact Fraction (14 s); the 60-digit Decimal recursion gives the same double |
| 9500, 10000 | 3.6642397405494632e-06 | 3.6642397405494717e-06 | 2.3e-15 | exact Fraction (136 s); the 60-digit Decimal recursion gives the same double |

- An `lgamma`/log-sum-exp alternative was measured at 1.6e-11 relative at c = 10000, so it is rejected for M/M/c.

Cost (VERIFIED, timed):

| c | Proposed time per call |
|---|---|
| 24 | 0.010 ms |
| 170 | 0.024 ms |
| 10,000 | 1.7 ms |
| 100,000 | 22.6 ms |

The current code takes 0.052 ms per call at c=24. It "returns fast" above the boundary only because it fails.

**Risk:** `mc_simulate_segment` calls `mmc` once per trial (trials up to 100,000 in `backend/api/simulation.py:49`, c up to 100,000 from uploads). The worst case would be about 2,260 s per segment. Performance at that scale is NOT TESTED. A decision is needed (OD-N4).

### 3.2 (a') M/M/c/K through closed-form log weights (PROPOSED)

The formula is unchanged. Only the evaluation changes:

- log wₙ = n·ln a − lnΓ(n+1) for n ≤ c.
- log wₙ = n·ln a − lnΓ(c+1) − (n−c)·ln c for n > c.
- Subtract the peak, exponentiate, normalize with `math.fsum`. This is the pattern `erlang_a` already uses in the same file (queue_models.py:494-575).
- Use λ = 0 → p0 = 1 as an explicit branch.
- The metric definitions (L, Lq, W, Wq, rho, blocking probability, effective λ) stay unchanged.

Accuracy (VERIFIED by a run):

- Grid: c ∈ {1,2,3,5,10,24,50,100,150,170} × K−c ∈ {0,1,5,20,100,500} × rho ∈ {0…2}. That gives 350 cases the current code computes and 130 it fails.
- Maximum relative difference from the current code: blocking 1.35e-13, Lq/Wq 9.5e-14, W 3.6e-14, L 2.7e-15, rho 8.2e-16.
- Against exact Fraction: current ≤ 4.9e-16, proposal ≤ 1.35e-13. The proposal is slightly less accurate than the current form where the current form works. It stays inside 1e-12.
- Beyond the current range (exact Fraction): (1,1,2,1100) ≤ 3.3e-16; (19.2,1,24,231) ≤ 1.4e-13; (160,1,200,260) ≤ 7.1e-14; (40,1,50,400) ≤ 6.6e-14.
- A cumulative log-sum version was measured at 6.9e-12 (blocking at (0.6,1,2,502)), which **fails** 1e-12. That is why the closed form is proposed.
- Bound argument (INFERRED): where the current form succeeds, every log term is below ln(DBL_MAX) ≈ 709.8. The absolute error of each log weight is therefore about 1e-13, which bounds the relative error of the weights.

### 3.3 Implementation option for pin safety (decision OD-N1)

- **Option R (replace):** one code path. Existing results change in the last bits: ≤ 3.5e-15 for M/M/c and ≤ 1.35e-13 for M/M/c/K, relative.
- **Option F (fallback):** keep the current closed form exactly. Use 3.1/3.2 only when it raises `OverflowError` or gives a non-finite value. Every result that computes today stays **bit-identical**. This adds two code paths and a sub-1e-13 seam at the switch point.
- Recommendation: **F for `mmck`, R for `mmc`.**
  - M/M/c: the recursion is as accurate as the current form (both about 1.3e-14 against exact) and one path is easier to keep correct.
  - M/M/c/K: the current form is about 300 times more accurate where it works, and F keeps it there.

### 3.4 (b) `mgc` error text (PROPOSED)

In `mgc` (queue_models.py:231-239), when `base` is not stable:

- Return the existing unstable text **only if** `lambda_ >= c * mu or is_saturated(rho)`. This is the same test `mmc` uses at line 164, and `is_saturated` is already imported.
- Otherwise return `"M/G/c calculation failed due to numerical instability."`, the string the function already uses at line 253, with `rho` and `stable=False`.

No new strings, so no i18n change. `mgck` already passes the `mmck` error through and needs no change.

### 3.5 Out of scope, listed for separate decisions (no change proposed here)

- **OD-N2:** frontend `cantKeepUp` = `stable === false` (`frontend/src/lib/results.ts:26`) labels any numerical failure "can't keep up". The Quick calculator already uses rho >= 1. After 3.1/3.2 such failures become rare, but they are still possible (for example λ near 1e308).
- **OD-N3:** `mc_simulate_segment` reports PASS with `Wq_mean None` when every trial failed numerically.
- **OD-N5:** `mmc_priority` raises `TypeError` on a non-stable base. There is no production caller.
- **OD-N6:** engine-version stamp. `backend/api/workflow.py:95` `ENGINE_VERSION = "novaq-2026-09-unified-des-v1"` and `shared_capacity.ENGINE_VERSION`. Should previously stored plans in which rows failed numerically be marked historical? UNKNOWN which stored plans contain such rows.

## 4. Pin-safety argument (PROPOSED; the numbers above are VERIFIED)

1. **Pre-change pin capture (step 0):** with the unchanged engine at a recorded commit, write the current `mmc`/`mgc`/`mmck`/`mgck` outputs for a fixed grid into a committed fixture (`tests/fixtures/erlang_pins_pre_change.json`). The grid is the §3.1 and §3.2 grids plus every case in `tests/test_queue_models.py`, `tests/analytical_benchmarks.py` and `tests/test_stability_boundary.py`.
2. **Tolerance:** `math.isclose(new, pinned, rel_tol=1e-12, abs_tol=1e-300)`. The abs_tol only covers subnormal values below 1e-300, where relative error is meaningless. `stable`, `error` and `rho` must be equal (rho bit-identical, as measured).
3. **Measured margin:** worst observed drift is 3.5e-15 (M/M/c, R) and 1.35e-13 (M/M/c/K, R) relative. With option F, M/M/c/K drift is 0 by construction.
4. **Saved-scenario recheck:** `scenarios._verify_calculation` recomputes and compares with `rel_tol=1e-10, abs_tol=1e-10` (`backend/api/scenarios.py:128-139`, VERIFIED by reading). The drift is far inside that.
   - Exception: a snapshot computed **before** the change for a row that failed numerically will no longer match, because the row is now stable with values. Saving it would return 422 "Results do not match the calculation inputs". INFERRED: this is a deploy-boundary effect that a recalculation clears. NOT TESTED.
5. **Behaviour that changes on purpose:** rows that failed numerically become stable with finite metrics. The optimizer can then choose 144 to 256 counters. Shared candidates in that range become available. Monte Carlo yields waiting times. `mgc` text changes only for non-saturated failures.
6. **Behaviour that must not change:** truly unstable inputs (rho >= 1, including the 3.15/(3·1.05) float case) keep the same `stable=False` and the same error strings. Invalid-input errors and dispatch in `model_selection.py` stay unchanged. Erlang-A with theta > 0 stays unchanged.

## 5. Tests (PROPOSED)

- **T1 pins:** the fixture from §4.1, using the §4.2 tolerance, over all of `mmc`/`mgc`/`mmck`/`mgck`.
- **T2 independent oracle:** a test-local `Fraction` (exact) implementation of the textbook p0 formula for M/M/c and M/M/c/K. It runs on c ≤ 300 and K ≤ 1100 cases inside and outside the old range, at rel 1e-12. It must not import the engine's helper.
- **T3 large-c reference values** from §3.1: (150,1,171), (200,1,250) exact, (4500,1,5000), (9500,1,10000) with the 60-digit Decimal reference, rel 1e-12.
- **T4 large-K reference values:** (1,1,2,1100), (19.2,1,24,231), (160,1,200,260), (40,1,50,400) exact, rel 1e-12.
- **T5 `mgc` text:**
  - `mgc(1,1,5000,1)` becomes stable.
  - `mgc(200,1,171,1)` still says "Unstable system…".
  - With `mmc` monkeypatched to return a non-saturated numerical failure, `mgc` returns "M/G/c calculation failed due to numerical instability." and never the unstable text.
- **T6 service level:**
  - `process_segments` with c=171 is stable.
  - `optimize_segment(λ=180, c=200, max 256)` is FEASIBLE with an optimum between 190 and 200, and the expected value is derived from T2.
  - `optimize_segment(λ=1, c=200, var=1)` gives a warning other than "Unstable system".
  - `evaluate_segment(servers=171)` gives STABLE.
- **T7 identities:** Little's law L = λW and Lq = λWq; M/M/c with c=1 equals `mm1`; `mgc` with Cs² = 1 equals `mmc`.
- **T8 mutation check:** mutants of the recursion (n ↔ n−1, the 1−ρ(1−B) term, the peak shift, the min(n,c)) must each fail a test.
- **T9 performance:** the time of `mmc` at c = 100000 and of the worst-case MC request. This is the input to OD-N4.
- **Gates:** `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`. Frontend is unchanged.

## 6. Owner decisions requested

- **OD-N1:** authorize the change to `queue_models.py` (§3.1, §3.2, §3.4) as a protected-mathematics change. Choose option R or F per function (recommendation: R for `mmc`, F for `mmck`).
- **OD-N4:** Monte Carlo cost at large c. The options are:
  - (A) a request-level budget of trials × c, refused with a clear message (the C_MAX pattern);
  - (B) accept the cost;
  - (C) compute once per distinct (λ, μ) per trial, which is not possible because λ and μ are perturbed every trial.
  - Recommendation: A, value to be set from T9.
- **OD-N2, OD-N3, OD-N5, OD-N6:** separate decisions (§3.5).

## 7. Unknowns (as of the proposal)

- UNKNOWN: whether any stored production plan or scenario contains rows that failed numerically.
- UNKNOWN: real-world maximum counter counts for NovaQ users. The uploads allow up to 100000.
- UNKNOWN: textbook section and page numbers (§3.1).
- NOT TESTED: the worst-case Monte Carlo request time.
- NOT TESTED: PostgreSQL. No database code is touched.

## 8. Implementation record (2026-10-13, uncommitted)

Branch `claude/keen-feistel-626da0` (worktree `clever-boyd-87ff32`, base `6093d78a`). `queue_models.py` was byte-identical to `feat/ux-u1-shell` @ `4a4fc58b` before the change (blob `e0158217`).

Changes in `backend/queueing_engine/models/queue_models.py`:

- **`mmc`:** the p0 and factorial form is replaced by the Erlang B recursion and C = B/(1 − ρ(1 − B)), then Lq = C·ρ/(1 − ρ). Validation, the instability test, the Wq/W/L derivation and every error string are unchanged.
- **`mmck`:** the closed form runs unchanged. Only when it raises `OverflowError`, or its sum is not finite, the weights come from the new `_mmck_scaled_weights` (closed-form logarithms, peak shift, `math.fsum`). λ = 0 gives the weights [1, 0, …]. An offered load whose logarithm is not finite raises `OverflowError`, so the existing "numerical instability" result is returned.
- **`mgc`:** the "Unstable system" text only when λ ≥ cμ or `is_saturated(rho)`. Any other base failure returns its existing "M/G/c calculation failed due to numerical instability." text.

Findings made during implementation (VERIFIED by runs on the unchanged engine):

- **Silent sum overflow:** `mmck(1.5, 1, 1, K)` for K = 1748, 1749 and 1750 returned `stable=True` with rho = L = Lq = blocking = 0. Each weight 1.5ⁿ fits in a double, but their sum overflowed to infinity without an exception, so p0 = 0. `mgck(1.5, 1, 1, 1, 1749)` passed the wrong result through. The fallback now also triggers on a non-finite sum (test `test_capacity_sum_overflow_is_no_longer_reported_as_an_idle_system`).
- **Zero `mmc` results checked:** the 52 old `mmc` results with Lq = 0 at λ > 0 are genuine underflow. The true Lq is below 1e-321 in every one.

Tests (`tests/test_large_server_numerics.py`, 40 tests, about 60 s):

- **Pin fixture:** `tests/fixtures/erlang_numerics_pin.json` holds 1,393 cases written from the unchanged engine. Of these, 854 computed before, 187 were truly unstable or outside the M/G/c/K bounds, and 352 failed numerically. The 352 include 54 `mgc` cases that the old text called "Unstable system" at ρ < 1.
- **Pin assertions:**
  - `mmck`/`mgck` results that computed before are bit-identical;
  - `mmc`/`mgc` match within rel 1e-12 (abs 1e-300), with rho bit-identical;
  - unstable and invalid results are identical;
  - former numerical failures match an exact `Fraction` oracle at rel 1e-12 for ρ ≤ 0.99. For ρ = 0.999999 they are checked for finiteness and Little's law only, because the rounding of ρ is amplified by about 1/(1 − ρ).
- **Reference values and services:** the §3.1 and §3.2 reference values, the `mgc` text cases (including λ=3.15, μ=1.05, c=3), Little's law, M/M/c with c=1 against M/M/1, and the current-metrics, optimizer and shared-segment callers.
- **Mutation check (scratch script, file restored byte-identical):** 13 of 13 mutants killed. They covered:
  - the recursion bound, the recursion denominator, the B to C term and the Lq factor;
  - the `mgc` branch, three variants;
  - the fallback trigger, two variants;
  - lgamma(n), the tail exponent, the peak shift and the λ = 0 branch.

T9, measured while another test run shared the machine, so the times are approximate:

| c | `mmc` per call | Monte Carlo per trial |
|---|---|---|
| 24 | 0.032 ms | 0.091 ms |
| 170 | 0.058 ms | 0.133 ms |
| 1,000 | 0.36 ms | 0.52 ms |
| 10,000 | 4.9 ms | 4.4 ms |
| 100,000 | 22.6 to 46.7 ms | 50.8 ms |

`McRequest` allows 1,000 segments × 100,000 trials. OD-N4 (a request budget) stays open: it needs a value from the owner and would change the `/simulation/*` contract.

## 9. OD-N4 measurement (2026-10-13, ESTIMATES, not production measurements)

The method is the one approved in `2026-09-30-shared-queue-named-api-ui-first-slice.md` §22.8:

- **Container:** `--cpus 0.1 --memory 512m --memory-swap 512m`, on the same Intel Core i3-8145U host.
- **Image:** `python:3.14` (3.14.8) with `pip install -r requirements.txt`. That resolved numpy 2.2.6, scipy 1.18.1 and pandas 2.3.3, saved locally as `novaq-mc-bench:py314`.
- **Code:** this branch's working tree, mounted read-only. The benchmark calls `mc_simulate_segments` exactly as `POST /simulation/mc` does, in one warm process, with 3 repeats per size.
- **Unit:** counter-trials, meaning trials × the sum of `c` over the request's segments.

| Workload | Counter-trials | Seconds (3 runs) | Within 60 s |
|---|---|---|---|
| 1 segment, c = 100,000, 120 trials | 12 million | 26.3 / 25.2 / 22.3 | yes |
| 1 segment, c = 100,000, 140 trials | 14 million | 28.4 / 27.9 / 30.2 | yes |
| 1 segment, c = 100,000, 170 trials | 17 million | 39.5 / 33.8 / 38.0 | yes |
| 1 segment, c = 100,000, 200 trials | 20 million | 48.6 / 47.8 / 51.5 | yes |
| 1 segment, c = 100,000, 240 trials | 24 million | 47.2 / 53.1 / 50.2 | yes |
| 1 segment, c = 100,000, 280 trials | **28 million** | 59.4 / 56.7 / 58.7 | yes (worst 99 % of 60 s) |
| 24 segments × c = 3, 2,000 trials (default size) | 0.144 million | 26.2 / 13.5 / 11.2 | yes |

- 32 million and above were not measured on 3.14.
- The same workloads on Python 3.11.16 (image `novaq-g8-api:latest`) were about twice as slow: 12 million took 49.2 to 53.7 s, and 17 million took 69.0 to 72.2 s, which fails.

Each segment and trial also has a fixed cost that is not proportional to `c`, so a counter-trial limit alone does not hold every request under 60 s. VERIFIED on 3.11: 100 segments × c = 1,000 at 12 million took 73.7 to 79.5 s, and 1,000 segments × c = 24 × 20 trials (0.48 million) took 125 to 168 s. The second case is accepted by today's `McRequest` limits.

Still open:

- Render's Python version and hardware speed (REPORTED as 3.14 in §22.8, not verified here).
- A cold first request after a Render spin-up.
- Resolved 2026-10-13: the owner chose 24,000,000 and approved the contract change (§10).

## 10. OD-N4 implementation record (2026-10-13, uncommitted)

**Decision:** `MC_MAX_COUNTER_TRIALS = 24_000_000` in `backend/queueing_engine/config.py`.

- It is the largest value measured in §9 whose every run kept a margin under 60 s: worst 53.1 s.
- 28,000,000 also passed, but at worst 59.4 s.
- Choosing the margin was a judgement (INFERRED), not a separate measurement.

**Implementation:**

- **The check:** `require_mc_workload_within_limit` in `simulation.py` counts each segment's `c` as `mc_simulate_segment` validates it. A segment that function would refuse runs no trial and counts 0.
- **Where it runs:** at the start of `mc_simulate_segments`, which every Monte Carlo route reaches, and in `validate_with_simulation` before its DES run.
- **The refusal:** a run with trials × total counters above the limit raises `McWorkloadError` before any trial. One handler in `backend/api/main.py` returns HTTP 422 with a string `detail`.
- **What the user sees:** the Simulation page shows a string `detail` as it is (`SimulationPage.tsx:64-66`), so there is no frontend or i18n change.

**Message:** "Monte Carlo run too large: {trials} trials x {counters} counters = {value} counter-trials; the limit is 24,000,000. Use at most {n} trials for these counters." When even one trial is over the limit, the last sentence is "The counters alone exceed the limit."

**Routes covered:**

- `POST /simulation/mc`
- `POST /simulation/validate`
- `POST /analyses/{id}/workflow/simulation/mc`
- `POST /analyses/{id}/workflow/simulation/mc/current`
- `POST /analyses/{id}/workflow/simulation/validation`
- the selected-plan Monte Carlo route (`workflow.py`, `_selected_mc_segments` → `mc_simulate_segments`)

**Tests:** `tests/test_mc_workload_limit.py`, 9 tests.

- Refusal before any trial, with the exact message, and the exact limit allowed.
- Counter counting.
- Validation refused before DES.
- 422 from `/simulation/mc`, `/simulation/validate` and the workflow Current Monte Carlo route.
- Mutation check (scratch script, files restored): 6 of 6 mutants killed.

## 11. OD-N6 resolution (2026-10-13): no engine version bump

The question was whether any stored plan or scenario holds a result that the old formulas got wrong. If so, it would need an engine-version stamp to mark it out of date.

**Local database** (VERIFIED, read-only; container `novaq-db-1`, volume `novaq_pgdata`, migration 0004, 5 scenarios and 105 jobs):

- 0 stored results contain "numerical instability" or the M/G/c "Unstable system" text.
- The largest stored `c` is 5.
- The largest K is 31 (15 in datasets).
- The largest λ/μ is 2.58.

**Production** (REPORTED: the owner ran read-only queries in the Supabase SQL editor of the NovaQ production project and shared screenshots):

- 0 scenarios and 0 jobs contain the failure text.
- 0 dataset rows have c >= 144.
- The largest K in datasets is NULL (none stored).
- The largest K in Setups (`total_system_capacity`) is 31.
- The largest λ/μ is 2.583.

**The old engine on those bounds** (VERIFIED, `queue_models.py` from `6093d78a` loaded from `git show`):

- `mmck`: every c from 1 to 31, every K from c to 31, and offered loads 0 to 2.58 in steps of 0.01 plus 2.5830405391523. That is 128,960 cases, all stable and equal to an exact `Fraction` evaluation (rel 1e-9).
- `mmc`: 0 numerical failures for c <= 143 at those loads.
- `mgc` and `mgck` are built on these two functions, so they are covered too.

**Conclusion:** no stored result came from the defective region, so no engine version changes. A dataset uploaded later with c >= 144 or a large K is computed by the fixed engine.
