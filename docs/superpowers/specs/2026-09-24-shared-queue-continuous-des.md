# Shared Queue Enhancement: Phase 3, Continuous Shared-Queue DES

Date: 2026-09-24. Status: approved for Phase 3 only by the product owner. Not wired into
any API, page, report, or saved scenario, and not approved for production use.

Numbering: the product owner's Phase 3 is the continuous DES. It was Phase 4 in the Phase 0
audit order. Workforce scheduling moves later.

Builds on Phase 1 (`2026-09-24-shared-queue-segment-foundation.md`, `b616e3ae`, `ad8ed236`)
and Phase 2 (`2026-09-24-shared-queue-capacity-optimization.md`, `b212d7ee`).

## Why

The Phase 0 audit verified four defects in the legacy shared DES (`simulation.py`, left
unchanged):

- it drops customers in service at segment boundaries;
- it re-issues carried-over customers as new arrivals with new ids and reset waits;
- it runs every segment as its own 24-hour stationary run;
- it discards up to half of each segment as warm-up.

Phase 3 adds a separate engine that simulates one continuous operating horizon.

## Scope

One new pure module, `backend/queueing_engine/simulation/shared_continuous_des.py`, plus
tests. It imports only the Phase 1 foundation and numpy. It is not exported from
`simulation/__init__.py`, and nothing legacy imports it. There is no API, schema, database,
frontend, report, or locale change, and no workforce, break, Monte Carlo, or playback work.

## Model (M/M/c with piecewise-constant rates)

- **Arrivals:** a Poisson process whose rate is λ_p inside demand period p. Inside each
  period, arrivals come from exponential gaps with mean 1/λ_p, starting at the period start.
  The overshoot past the period end is discarded. By memorylessness this is exactly a
  Poisson process on each period, independent across periods. A period with λ = 0 has no
  arrivals.
- **Service:** each customer i carries a unit work amount E_i ~ Exp(1), drawn once. When
  service starts at time s, the duration is E_i / μ(s), where μ(s) is the rate of the demand
  period containing s (half-open intervals). This is Exp(μ(s)). A service already started is
  never redrawn, rescaled, or interrupted when μ or capacity changes later.
- **Queue discipline:** one common first-come, first-served line. A free accepting server
  takes the customer at the head of the line; with several free servers, the lowest server
  number serves first.
- **Clock:** one event clock in hours from the horizon start. There is no restart, warm-up,
  or reset at any boundary, and customer ids and arrival times persist for the whole run.
- **Initial condition:** the system is empty at the horizon start. This is an assumption,
  and it is disclosed.

## Capacity transitions (non-preemptive; the approved Phase 0 transition policy)

At each staffing-segment start, the number of **accepting** servers is set to the scheduled
c:

- **Decrease by k:** idle servers close first, highest number first. If more are needed,
  busy servers are **designated to drain**, highest number first: they take no new customer,
  finish their current service, and close at that completion. No service is interrupted and
  no customer is removed.
- **Increase by k:** draining servers are reactivated first, lowest number first. Then closed
  servers reopen, lowest number first, and new server numbers are created only when needed.

Accepting servers therefore always equal the schedule. Present servers (accepting plus
draining) can exceed the schedule while a designated server finishes. Every open, close,
drain start, drain completion, and reactivation is recorded with its actual time, and the
excess is reported as `server_hours_above_schedule`.

Which busy server drains is an engine rule (highest number first) that does not look at
remaining service times. If every busy server started service under the same μ, their
remaining times are independent Exp(μ) (memoryless), so the choice does not change the
distribution of the queue process.

## Ordering of events at the same time

At equal times: service completions first, then capacity changes, then arrivals. After each
event, free accepting servers take waiting customers. So a server finishing exactly at a
decrease boundary is idle and closes without draining, and an arrival exactly at a boundary
sees the new capacity. Ties among arrivals follow customer id.

## Horizon end and closing

- The run observes [start, end). Arrivals exist only inside the horizon because the demand
  data covers only the horizon. This is data coverage, not a closing rule.
- **Closing policy: UNRESOLVED.** No approved shared-queue closing rule exists. The
  separate-queue continuous day stops arrivals at the day end and keeps serving admitted
  customers (`separate_optimization.run_routing_day_des`), but that is separate-queue
  behavior and was not approved for shared queues. This engine does **not** serve anyone
  after the horizon end and does **not** remove anyone. Customers still waiting or in service
  at the end are reported as unfinished, with their waits so far as lower bounds.
- Decision needed: after closing, should waiting customers be served (drain, as in separate
  queues), should admission stop some minutes before closing, or something else?

## Outputs

- Customers: id, arrival, arrival segment, service start, service end, server, wait, and
  status (`departed`, `in_service_at_end`, `waiting_at_end`).
- Per staffing segment:
  - arrivals, service starts, and the mean wait of arriving customers who started service
    (arrival-attributed);
  - still waiting at the end (censored);
  - time-average queue length, busy / present / scheduled server-hours, and hours above
    schedule (all time-attributed);
  - utilization of present servers, and the maximum queue.
- Totals and conservation: arrivals = departed + waiting at end + in service at end.
- Capacity transitions and drain records (designated at, released at, customer).
- A bounded event trace. It uses legacy-compatible customer events (`t`, `type`,
  `customer_id`, `server_id`, `queue_len_after`, `segment_id`) plus server events. The cap
  limits only the trace; every metric uses the full run.
- Provenance: engine version, seed, and the numpy `SeedSequence` entropy. With `seed=None`,
  the generated entropy is recorded, so the run can be repeated exactly. Also the inputs,
  event-order rules, transition rules, the closing status, and the assumptions.

## Tolerance policy for the new pipeline

The new shared-queue pipeline (Phases 1 to 3) uses one float-noise tolerance:
`utilization.THRESHOLD_TOLERANCE = 1e-9`.

- It is the tolerance that `is_saturated` already applies inside `mmc` and `mm1`, so
  stability and the utilization and wait limits share one boundary rule.
- It is far above the rounding error of λ/(cμ) (about 1e-16 relative) and far below the
  smallest displayed utilization step (1e-6).
- The legacy optimizer's `+ 1e-12` stays unchanged in the legacy path. The two paths can
  disagree only when ρ or the wait is within 1e-9 of a limit.
- Phase 2 now states this policy in its provenance.
- The DES compares event times exactly. Every boundary time is computed the same way
  ((minute − horizon start) / 60), so equal boundaries compare equal.

## Verification

- **Exact deterministic cases** with prescribed arrivals and work, using binary-exact times:
  constant capacity; an increase; a decrease with drain; idle-first closing; zero capacity
  with backlog; zero demand with backlog; same-time ordering; a service started before a μ
  change; and the horizon end.
- **Sample-path identities:** ∫ queue dt = Σ (min(service start, end) − arrival), and busy
  server-hours = Σ service time inside the horizon.
- **Conservation, identity, and first-come-first-served order** on seeded multi-transition runs.
- **Statistical checks, within 4 standard errors of replication means:**
  - constant capacity against Erlang C (λ = 40, μ = 20 per hour, c = 3, 24 h: Lq = 8/9,
    P(wait) = 4/9, Wq = 1/45 h);
  - Poisson arrival counts and dispersion;
  - exponential service means under two μ values.
- **Reproducibility** from a seed and from recorded entropy.
- **Regression:** the full backend suite, ruff, and mypy.
