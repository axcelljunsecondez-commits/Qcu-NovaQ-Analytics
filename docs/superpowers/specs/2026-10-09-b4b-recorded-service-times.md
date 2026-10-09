# B4b: Recorded service times in the continuous shared-line run

**Status:** APPROVED by the owner on 2026-10-09 (OD-B4b-1 = A resample recorded durations, OD-B4b-2 = A nearest-period fallback listed on the page, OD-UX-9 = the §5 checks are the acceptance set). This is a **mathematical change** to a simulation engine: implementation is plan step 11 and needs the owner's GO for that step; the §5 tests are written before any engine code.
**Parent spec:** `docs/superpowers/specs/2026-10-09-compact-workflow-ux-redesign.md` (D24, backend item B4b, open decision OD-UX-9). Builds on `2026-10-09-b4a-continuous-shared-run-preview.md` (approved).
**Plan:** step 6 (this spec), step 11 (implementation).
**Evidence labels:** VERIFIED (read in code at `ef05827e`, cited), PROPOSED, UNKNOWN, NOT TESTED.

## 1. Goal

Make the full-day shared-line run use the service times customers actually took, so that analyses built from customer records (the usual upload) can use it. After B4b this is the standard version of the run; B4a's exponential version stays available for count-per-period data.

## 2. What exists (VERIFIED)

| Fact | Evidence |
|---|---|
| A shared customer-record upload stores, for each period, the arrival rate, `mu = 1 / mean service time`, the variance of service times, and every recorded service duration in hours (`service_samples_hours`, `service_time_source`). | `backend/data/analysis_ingestion.py:296-316` |
| With a representative day, arrivals are divided by the number of observed days and service samples are pooled over those days. | `analysis_ingestion.py:278-281, 302-303` |
| The continuous engine draws each customer's service as `work / mu`, with `work ~ Exp(1)` drawn once per customer and `mu` from the period in which service starts; a started service is never redrawn. After closing (DRAIN) the final period's rate applies. | `backend/queueing_engine/simulation/shared_continuous_des.py:85-97` (ASSUMPTIONS) |
| The engine refuses rows with `variance`, so customer-record uploads are outside its scope today. | `backend/queueing_engine/services/shared_segments.py:53, 401-403` |
| The separate-lines routing DES already serves customers from each lane's own resampled recorded durations. | `backend/queueing_engine/services/separate_optimization.py:1-29, 428, 497` |
| The continuous engine's current results are pinned. | `tests/test_shared_continuous_des_pin.py` |

## 3. Proposed representation (PROPOSED; OD-B4b-1)

| Option | What it means | For | Against |
|---|---|---|---|
| **A. Resample recorded durations (recommended)** | When a service starts, draw its duration uniformly at random, with replacement, from the recorded durations of the period in which it starts. Same rule as the separate-lines DES. | Uses exactly what was recorded; no distribution is assumed; same approach the app already uses for separate lines. | Cannot produce a duration that was never recorded; periods with few customers have few distinct durations. |
| B. Fit a distribution (e.g. matching mean and variance) | Draw from a fitted lognormal or gamma. | Smooth; works with few samples. | Adds an assumption the data does not prove; the choice of family changes waits. |

Rules shared by both options:

- The duration is fixed when service starts and never changes (as today).
- After closing (DRAIN), services use the final period's recorded durations (as today with rates).
- A period where service starts but no durations were recorded (no customers that period in the data): **OD-B4b-2**: A (recommended) use the nearest earlier period that has recordings, else the nearest later one, and list each such period on the page; B refuse the run.
- Arrivals stay Poisson with the period's recorded rate (unchanged).
- `K` (waiting-room limit) and `theta` (customers leaving) stay out of scope, each for its own spec.

## 4. Engine change (PROPOSED)

- Add an optional service model to the engine: `exponential` (default, today's code path, bit-identical) or `recorded` (per-period samples). The `recorded` path uses its own random stream, so the default path and the pin test are untouched.
- Runs with recorded service times carry their own engine version string (for example `novaq-shared-continuous-des-v2+recorded-v1`; exact string set at implementation) in every stored result and replay.
- The compatibility check of B4a accepts rows with `variance` **only** when every row also carries `service_samples_hours` with `service_time_source` = recorded; `K` and `theta` stay refused.

## 5. Reference cases and acceptance tests (PROPOSED; OD-UX-9)

Exact checks:

1. Exponential mode: the pin test and all existing engine tests pass unchanged.
2. One customer, one counter, recorded duration list `[0.25]` h: wait 0, service exactly 0.25 h.
3. Every recorded duration equal to `d`: every simulated service lasts exactly `d` (deterministic service).
4. A service that starts in period 1 and ends in period 2 keeps its period-1 duration.
5. Same seed and inputs: identical results and identical replay; replay totals equal engine totals (`shared_playback` check).
6. Empty-period fallback (OD-B4b-2 A) uses the stated period and lists it; with option B the run is refused.

Statistical checks (fixed seeds, stated tolerances, many replications):

7. The mean of simulated service durations in a period is within the 99% interval of its recorded mean.
8. When the recorded durations are themselves a large exponential sample, the recorded mode's average wait agrees with the exponential mode within the replications' 95% interval.
9. Little's law on long runs: time-average people waiting ≈ arrival rate × average wait, within tolerance.
10. Against NovaQ's analytical M/G/c estimate for a long, stable, single-period day: same order of magnitude, with the gap reported, not asserted equal (the analytical value is an approximation).

Mutation testing of the sampling path is required (drawing from the wrong period, redrawing at boundaries, ignoring the fallback list).

## 6. What the user sees

- The run says "Uses your recorded service times" (B4b) or "Uses estimated service times (counts per period)" (B4a).
- Periods using a fallback are named.
- No Decision until OD-UX-13 is answered (unchanged from B4a).

## 7. Risks

- This changes simulation math. Implementation needs separate authorization after this spec, the reference tests above written first, and a full engine regression run.
- Runtime with long sample lists is not measured (NOT TESTED). B4a's expected-customer cap still applies.

## 8. Decisions for the owner

- **OD-B4b-1:** resample recorded durations (A, recommended) or fit a distribution (B).
- **OD-B4b-2:** periods without recordings: nearest-period fallback and list them (A, recommended) or refuse (B).
- **OD-UX-9:** approve the reference cases in §5 as the acceptance set.
