# Shared Queue Enhancement: Phase 1, Segment Foundation

Date: 2026-09-24. Status: approved for Phase 1 only by the product owner. Not wired into
any API, page, report, or saved scenario, and not approved for production use.

## Why

The Phase 0 audit (main `1d3294cb`) verified that the shared-queue path has no notion of
segment duration: `SegmentInput` has no duration field, aggregate uploads keep only a free
`time` label, optimizer costs are per-hour rates that the Compare and Decision pages sum as
if every row lasted one hour, and `AnalysisSegment` rejects overlaps but allows gaps. The
later phases (right-sizing, continuous DES, workforce) need a duration-aware, gap-free
timeline first.

## Scope

One new pure module, `backend/queueing_engine/services/shared_segments.py`, plus tests.
Nothing existing imports it. No API, schema, database, frontend, report, or locale change.

It provides:

1. An operating horizon inside one calendar day, in whole minutes (`0` to `1440`;
   `"24:00"` is accepted as the end of day). Overnight horizons are rejected, matching
   `AnalysisSegment` (end must be after start).
2. **Demand periods**: the resolution at which demand was observed. Each carries an
   arrival rate λ and a per-server service rate μ, both per hour.
3. **Staffing segments**: the resolution at which the number of servers `c` may change.
   A staffing segment may be shorter than a demand period (for example 15 or 30 minutes
   inside an hourly period).
4. Validation, collecting every problem before raising: chronological order, positive
   whole-minute durations, no overlaps, no gaps, exact coverage of the horizon, unique
   ids, finite rates (λ ≥ 0, μ > 0), integer `c ≥ 0`, and every staffing segment lying
   inside exactly one demand period.
5. A steady-state analytical evaluation per staffing segment through the existing
   `select_model` (single source of truth), with duration-weighted, unit-explicit
   quantities.
6. A strict reader for aggregate rows whose `time` label is `HH:MM-HH:MM`.

## Decisions taken in this phase

- **Sub-hour staffing never creates sub-hour demand.** A staffing segment inherits λ and μ
  from the one demand period containing it. The output labels this as
  `demand_source: "inherited"` with the demand period id and its resolution in minutes.
  Holding λ constant inside a demand period is the piecewise-constant Poisson-rate
  assumption, and it is disclosed. A staffing segment that crosses a demand boundary is
  rejected rather than split or averaged.
- **Model scope is M/M/c (M/M/1 when c = 1) only.** The reader rejects rows with service
  variance, capacity K, or patience theta, with a message naming the open decision.
  Nothing is silently dropped or substituted.
- **The legacy shared DES, optimizer, scenarios, and all separate-queue code stay unchanged.**

## Segment outcomes

| Case | Status | ρ | Lq, Wq | Waiting customer-hours |
|---|---|---|---|---|
| c ≥ 1, λ > 0, λ < cμ | `STABLE` | λ/(cμ) | from `select_model` | λ · Wq · T |
| c ≥ 1, λ = 0 | `ZERO_DEMAND` | 0 | the equations' λ→0 limit (0) | 0 (no arrivals) |
| c ≥ 1, ρ ≥ 1 (with the 1e-9 tolerance) | `UNSTABLE` | λ/(cμ) | `None` | `None` |
| c = 0, λ > 0 | `NO_CAPACITY` | `None` | `None` | `None` |
| c = 0, λ = 0 | `CLOSED` | `None` | `None` | 0 (no arrivals) |

Unknown or undefined values are `None`, never 0. Horizon totals that depend on an undefined
segment value are `None`, and the affected segment ids are listed.

## Units

- λ, μ: customers per hour; μ is per server.
- T (`duration_hours`) = minutes / 60.
- Expected arrivals = λ · T (customers).
- Server-hours = c · T.
- Offered work = (λ / μ) · T (server-hours of service demanded).
- Expected waiting customer-hours = λ · Wq · T = Lq · T (Little's law). This is a steady-state
  estimate, not a transient prediction.
- No currency amounts. Costs belong to Phase 2.

## Verification

- Independent references in the tests: exact Erlang C cases (A = 2, c = 3 gives
  P(wait) = 4/9, Lq = 8/9; M/M/1 λ = 3, μ = 4 gives Lq = 2.25, Wq = 0.75 h), an Erlang-B
  recursion implemented in the test file, and rows from the NovaMart 14-day average.
- Boundary tests for every validation rule and every outcome row above.
- Regression: the full backend suite, ruff, and mypy. The frontend is untouched.

## Out of scope (later phases, each needs approval)

Costs and right-sizing (Phase 2), continuous DES (Phase 4), Monte Carlo and playback
(Phase 5), workforce shifts and breaks (Phase 3), and any API, UI, or report wiring (Phase 6).
