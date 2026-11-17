# D2: Current separate-lanes DES accounting at the fixed horizon (2026-11-17)

Status: APPROVED by the product owner on 2026-11-17 ("fix it after this", given after the D2 measurement
on NovaMart). Base: origin/main `c2316ed4`. Branch `fix/d2-current-accounting-20261117`. Risk: HIGH
(protected mathematics, AGENTS.md §5). Written before the engine was changed.

This spec adapts the archived D2 spec (`archive/fix-d1-replication-costs-20261117`,
`docs/superpowers/specs/2026-09-25-d2-current-separate-des-accounting.md`, commit `d4bca6af`) to the
current core: PR58 break windows, per-date days (C-PD) and the compact stored result (C-PD-C).

## Owner decisions (2026-11-17)

- The Current DES basis becomes `current_break_windows_v5`. `per_date_days_v1`, `per_date_days_v2`,
  `per_date_days_v3` and `current_break_windows_v4` are historical. PR59's K-PR58-4 exemption (v3
  current when the Setup has no breaks) is removed: every earlier Current run needs one rerun.
- "Unstable" stays the band for rho = 1.0. A lane-period fully occupied by service now reports
  rho = 1.0 and so shows Unstable.
- OD-D2-1 = yes: the public `POST /simulation/des` and `POST /simulation/des/trace` also return
  `Wq_sim: null` for a separate-lanes row where nobody started service.
- OD-D2-2 = later follow-up: legacy separate `workflow_des` jobs keep their stored rows and markers.
- OD-D2-3 = no new columns or wording. A null wait already renders as "—" / "Unavailable".
- D5 and D10 are NOT authorized and are not part of this change.

## Scope

`_simulate_parallel_segments_core` in `backend/queueing_engine/simulation/simulation.py` (the
separate-lanes Current DES behind `simulate_segments`, `simulate_segments_with_trace`,
`simulate_parallel_days_with_trace` and `simulate_parallel_days_compact`), `COMPACT_ROW_FIELDS`,
the separate branch of `summarize_simulation`, and in `backend/api/workflow.py` the Current basis
marker, `_current_evidence_policy` and `_wait_and_line`.

Not affected (they read the selected-plan DES, not this core): reports, `report_export`,
`separate_report`, validation, `ChecksView`, `separate_comparison`, Monte Carlo, the shared-lane
engines and the selected-plan routing DES.

## Defects at c2316ed4

1. Busy time is recorded only when a service completes; a service still running at H adds nothing.
2. Each service is tagged with the customer's arrival period and clipped to that period: the part of a
   service that occurs in a later period is credited nowhere.
3. `Wq_sim = wait_sum / served`: the numerator sums the waits of customers who started service; the
   denominator counts only those who completed.
4. A row with no completed customer reports `Wq_sim = 0.0`, including rows with no arrivals.

NovaMart (owner file, read in place; seed 42, 13 periods, 5 lanes, H = 13 h): busy time credited
17.2669 h of the trace's 25.7493 h.

## Definitions (one run, one date)

Periods are the QueueSetup segments laid end to end on the DES clock: period p = [a_p, b_p),
d_p = b_p - a_p, H = b_last. Per-date runs apply this per date, each with its own H. For customer i
on lane q: arrival t_i, service start s_i, service end e_i. At H each arrival is exactly one of
completed, in service (s_i < H <= e_i), or waiting (not started). SimPy stops before events at exactly
H, so a service ending at H is in service.

Break windows (PR58, unchanged): a service may not start inside a lane's break window; a customer
whose turn comes inside a window keeps waiting (holding FIFO) until the window ends; a service already
under way when a window opens continues. The time a customer waits through a window is queue wait.

### Busy time (occurrence attribution)

B_{p,q} = sum over customers i on lane q with s_i < H of max(0, min(e_i, b_p, H) - max(s_i, a_p)),
with e_i taken as H for a customer in service at H (`_window_busy_hours`, `math.fsum`).

Service is credited to the period in which it occurs, never after H and never twice. A lane that is
unscheduled in p but drains its queue there (`drain_existing`) is busy in p; the row's `active` flag
records the schedule.

### Utilization

rho_{p,q} = min(1, B_{p,q} / max(d_p, 1e-12)). Calendar denominator unchanged.

### Waiting time (arrival-period started cohort)

S_{p,q} = customers who arrived on q in p and started service before H.
Wq_{p,q} = sum_{i in S} (s_i - t_i) / |S|; None when |S| = 0. A true zero stays 0.0.

### Censored customers

Customers of (p, q) still waiting at H: `censored_customers` (count) and `censored_waiting_hours`
= sum (H - t_i), a lower bound that is never used as a wait. The horizon is not extended.

## Row fields

Added: `started`, `censored_customers`, `censored_waiting_hours`, `active`. Changed values:
`busy_time`, `rho_sim`, `Wq_sim`. Unchanged: `arrivals`, `served`, `wait_sum`, `waiting`,
`in_service`, `final_Lq`, `customer_conservation`, `max_queue`, `throughput` and every other field,
the trace, events, RNG call order and seeds. `COMPACT_ROW_FIELDS` adds `started` and
`censored_customers`. Compact `rows_digest` values change (they hash the rows); `trace_digest`
values do not.

## Aggregates

- `summarize_simulation` (separate rows): `avg_Wq = sum(wait_sum) / sum(started)`, None when nothing
  started; adds `total_started`. It no longer multiplies a possibly-None `Wq_sim`.
- `workflow._wait_and_line`: weights a row's wait by `started` when the row carries a numeric
  `started`, otherwise by `served` (selected-plan rows have no `started` and are unchanged).

## Invariants (per lane, per run or date)

- arrivals = started + censored_customers for every row; served <= started.
- Sum of censored_customers over the lane's rows = `waiting` at H.
- Sum of busy_time over the lane's rows = the trace's busy time up to H.

## Verification

- Trace identity: `tests/test_current_des_trace_identity.py` with fixture
  `tests/fixtures/current_des_trace_identity_c2316ed4.json`, written on unmodified c2316ed4 before
  the engine edit (representative day with breaks, without breaks, per-date two dates compact and
  full, draining lane; seeds 1, 7, 42). It must stay byte-identical.
- Independent oracle: `tests/test_current_des_accounting.py`, one-server FIFO rebuilt from the
  trace's arrival times only, extended for break windows.
- NovaMart acceptance (local only, never committed): rows equal the measured trace oracle within
  2e-6 h and totals match the handoff table for seeds 42, 7, 123 and 2026, with traces unchanged.
- Snapshot fixtures regenerated only with a recorded field-level diff under
  `output/d2-fix-20261117/`.

## Out of scope

D5, D10, the selected-plan DES, reports, shared-lane engines, wording, frontend columns and legacy
`workflow_des` markers.
