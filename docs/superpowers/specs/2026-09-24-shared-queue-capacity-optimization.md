# Shared Queue Enhancement: Phase 2, Dynamic Capacity Optimization

Date: 2026-09-24. Status: approved for Phase 2 only by the product owner. Not wired into
any API, page, report, or saved scenario, and not approved for production use.

Builds on the Phase 1 segment foundation
(`docs/superpowers/specs/2026-09-24-shared-queue-segment-foundation.md`, commits `b616e3ae`
and `ad8ed236`).

## Scope

One new pure module, `backend/queueing_engine/services/shared_capacity.py`, plus tests.
The legacy optimizer (`optimization.optimize_segment`, `/optimize`, `/optimize/batch`),
scenario schema versions 1 and 2, model selection, Decision, reports, the legacy shared DES,
and all separate-queue code stay unchanged. Nothing existing imports the new module.

## Inputs (all supplied by the caller; the module holds no operating defaults)

- The Phase 1 timeline: horizon, demand periods (λ, μ per hour), and staffing segments.
  Each staffing segment's `servers` is the current staffing, evaluated as the baseline.
- `CapacityConfig`:
  - `server_cost_per_hour`: currency per server-hour, finite and above 0 (the same rule as
    the legacy API);
  - `waiting_cost_per_customer_hour`: currency per customer-hour of waiting, finite, 0 or more;
  - `target_utilization`: a utilization ceiling in (0, 1];
  - `min_servers`, `max_servers`: whole numbers with 0 ≤ min ≤ max ≤ 256 (256 is the
    legacy API ceiling). `max_servers` is the physical capacity;
  - `max_wait_minutes`: optional, finite, 0 or more.

## Formulation

The objective, for every staffing segment s with duration T_s in hours (minutes / 60),
chooses c_s from the candidates {min, …, max}:

- server cost = c_s × server_cost_per_hour × T_s
- expected waiting customer-hours = λ_s × Wq(λ_s, μ_s, c_s) × T_s, with Wq in hours from
  `select_model` (M/M/c, or M/M/1 when c = 1)
- waiting cost = expected waiting customer-hours × waiting_cost_per_customer_hour
- total cost = server cost + waiting cost

The objective minimizes Σ_s total cost. Segments are independent in the stationary model,
so minimizing each segment separately is exactly the horizon minimum for this objective. It
is **not** a workforce or payroll optimum: shifts, breaks, and paid hours are Phase 3.

Units: [c] = servers; [cost per hour] = currency / (server·h); [T] = h. Server cost is in
currency. [λ] = customers / h and [Wq] = h, so λ·Wq·T has units of customer·h, and waiting
cost is in currency.

## Candidate feasibility

| Candidate status (Phase 1) | Feasible when | Violation recorded |
|---|---|---|
| `STABLE` | ρ ≤ target + 1e-9, and Wq × 60 ≤ max wait + 1e-9 when set | `target_utilization`, `max_wait_minutes` |
| `ZERO_DEMAND` | Always: ρ = 0 and Wq = 0 in the stationary model | none |
| `CLOSED` (c = 0, λ = 0) | Only if `min_servers` = 0; no customer arrives, so the utilization and wait limits do not apply | none |
| `UNSTABLE` | Never | `stability` |
| `NO_CAPACITY` (c = 0, λ > 0) | Never | `no_capacity` |
| `CALCULATION_FAILED` | Never | `calculation_failed` |

The 1e-9 tolerance is `utilization.THRESHOLD_TOLERANCE`, the repository's float-noise
constant. The legacy optimizer uses 1e-12; the two can differ only for a ρ or wait within
1e-9 of the limit.

## Selection and outcomes

- `OPTIMIZED`: the cheapest feasible candidate. Candidates whose total cost is within a
  relative 1e-9 of the minimum count as tied, and the tie goes to fewer servers (the same
  rule as the legacy optimizer, with a float tolerance).
- `NO_FEASIBLE_CANDIDATE`: no candidate qualifies. The selection and costs are `None`, and
  the violations seen are listed.
- The current staffing is always evaluated with the same formulas, even outside
  [min, max] (flagged). An unstable or no-capacity current segment has `None` waiting and
  total cost, never 0.

Horizon totals (current and selected) are sums only when every segment has a defined value.
Otherwise they are `None`, with the segments responsible listed. The cost change (selected
minus current) exists only when both totals exist, and a reason is given when it does not.

## Provenance kept in the output

The engine version, the configuration, the full inputs, the objective, the tie rule, the
tolerances, units, assumptions, and every candidate evaluation for every segment.

## Limits (disclosed in the output)

- Stationary analysis: waits are steady-state estimates for customers arriving in the
  segment. Backlog carried between segments is not represented, and closing a segment
  (c = 0) cannot be checked for customers left waiting. The continuous DES (Phase 4) is
  the tool for that.
- M/M/c only. Service variance, finite capacity, and abandonment remain an open decision.

## Verification

Independent tests: hand-computed duration-weighted costs; an exact tie (λ = 1, μ = 2,
server cost 7, waiting cost 15 gives 14.5 for both c = 1 and c = 2); utilization and
max-wait boundaries, including float noise (λ = 2.1, μ = 1, c = 3); zero demand; zero
capacity; unstable and infeasible segments; duration scaling; a brute-force optimum from an
independent Erlang-B recursion on the NovaMart 14-day average; agreement with the legacy
optimizer's server counts on 1-hour segments; and the isolation of the new module.
Regression: the full backend suite, ruff, and mypy.
