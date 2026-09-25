# D2: Current-State Separate-Queue DES Accounting (Fixed Horizon)

Date: 2026-09-25. Status: authorized by the product owner ("NOVAQ — D2 CURRENT-STATE DISCRETE-EVENT
SIMULATION CORRECTNESS REPAIR"). Branch `fix/d1-replication-costs`, after D1 `c25591a7`, D5
`5291f7ec` and D10 `66ba238e`. Written before the implementation was changed.

## Scope

`_simulate_parallel_segments_core` in `backend/queueing_engine/simulation/simulation.py` (the
Current-state separate-queue DES behind `simulate_segments` / `simulate_segments_with_trace` for
separate-queue rows), the separate-queue branch of `summarize_simulation`, and the Simulation-page
DES table that displays these rows.

Consumers (verified by tracing):

- `POST /analyses/{id}/workflow/simulation/des/current` (Current-mode DES job `workflow_des_current`);
- `POST /analyses/{id}/workflow/simulation/des` for a legacy (non-schema-v2) separate scenario
  (`workflow_des`);
- `POST /simulation/des` and `POST /simulation/des/trace` with a separate-queue QueueSetup.

Not consumers: selected-plan DES / MC / validation / decision / report (per-period and
continuous-day routing DES in `separate_optimization.py`), Monte Carlo (`mc_simulate_segments`),
Current validation (reads Current MC only), the pooled shared-queue `simulate_segment`, and the
shared-queue continuous DES (`shared_continuous_des.py`, another branch, imports nothing from
`simulation.py`). The legacy Decision reads DES rows only for period labels, support and errors.

Out of scope: break modeling (the Current DES does not model configured breaks; reported, not
authorized), the available-time utilization denominator, horizon extension, engine versions,
D3/D7/D11 and findings A/B.

## Verified defects (HEAD `66ba238e`)

1. Busy time is recorded only when a service completes; a service in progress at the horizon adds
   nothing.
2. Each service is tagged with the customer's arrival period and clipped to that period; the part
   of a service that occurs in a later period is credited nowhere.
3. Consequently in-progress service and cross-boundary service are missing from utilization.
4. `Wq_sim = wait_sum / served`: the numerator sums the waits of customers who started service,
   the denominator counts only customers who completed.
5. A row with no completed customer reports `Wq_sim = 0.0`, including rows whose customers waited.
6. Customers still waiting at the horizon are excluded from `Wq_sim` without a stated population;
   the horizon counts (`waiting`, `in_service`) sit on the last period's row whatever the
   customers' arrival period.

NovaMart (derived from `NOVAMART_DATA_UPLOAD.xlsx`, SHA-256 `b39e2e42…`, through the upload
pipeline; seed 42; 13 periods, 5 lanes, horizon 13 h): trace busy time 22.8524 h, credited
19.2211 h (15.89% lost); 18 under-credited lane-periods; 6 lane-periods report rho 0 with positive
busy time; 13 rows with no started customer report Wq 0.0; 1 row's Wq divides 4 started waits by 3
completions.

## Definitions (one run)

Reporting periods are the QueueSetup segments in schedule order, laid end to end on the DES clock:
period p = [a_p, b_p), duration d_p = b_p - a_p. The horizon H = b_last. For customer i on lane q:
arrival (= admission; no routing) t_i, service start s_i, service end e_i. At H each arrival is
exactly one of: completed (s_i, e_i < H), in service (s_i < H <= e_i), waiting (not started).
SimPy stops before events scheduled at exactly H, so a service ending at H is in service.

## Busy time (occurrence attribution)

B_{p,q} = sum over customers i on lane q with s_i < H of max(0, min(e_i, b_p, H) - max(s_i, a_p)),
with e_i unknown (treated as >= H) for a customer in service at H.

Service is credited to the period in which it occurs, never to the arrival period, never after H,
never twice. This is the attribution the continuous-day routing DES already uses ("busy time is
credited to the window in which it occurs").

## Utilization (calendar time, preserved)

rho_{p,q} = min(1, B_{p,q} / d_p). Denominator unchanged (calendar period length); the existing
clamp is kept (it cannot bind: one server). No target, feasibility rule or availability assumption
changes. A lane that is not scheduled in period p but is finishing its own queue there
(`drain_existing`) is busy in p and is credited there; each row records the schedule's `active`
flag so this is visible.

## Waiting time (arrival-period started cohort)

Owner of a customer: the arrival period (the existing Current DES attribution and the
continuous-day DES attribution). For row (p, q), cohort A = customers who arrived in p on q;
started population S = {i in A : s_i < H}.

Wq_{p,q} = sum_{i in S} (s_i - t_i) / |S|, and undefined (None) when |S| = 0.

Numerator and denominator both range over S. Customers in service at H belong to S (their wait
is complete). A true zero (customers started without waiting) stays 0.0.

## Censored customers (fixed horizon, D10 policy)

The horizon is not extended. Customers of A still waiting at H are censored: their count
`censored_customers` and their observed partial waits `censored_waiting_hours` = sum (H - t_i) (a
lower bound, never used as a complete wait) are reported. No service start is invented.

Per row: arrivals = started + censored_customers; served <= started (started - served customers
are in service at H). Summed over a lane's rows, censored_customers equals the lane's `waiting`
count at H.

## States of Wq (never represented as zero)

| State | Row values |
|---|---|
| Observed zero wait | started > 0, Wq = 0.0 |
| No arrivals | arrivals = 0, started = 0, censored = 0, Wq = None |
| Arrivals, none started (all waiting at H) | started = 0, censored > 0, Wq = None |
| Some started, some waiting | Wq over started; censored > 0 disclosed |
| Missing input data | unchanged capability-error rows (`simulation_supported` false, error) |
| Stored before D2 | no `wait_population` field: shown as recorded with the earlier accounting |

## Additive row fields

`started`, `censored_customers`, `censored_waiting_hours`, `active`, and `wait_population` (the
recorded population statement). Existing fields keep their meaning; `busy_time`, `rho_sim` and
`Wq_sim` take the corrected values. `waiting`, `in_service`, `final_Lq`, `customer_conservation`,
`served`, `arrivals`, `max_queue`, `throughput` and the trace are unchanged.

`summarize_simulation` (separate rows): avg_Wq = sum of started waits / sum of started, None when
none started (it previously weighted `Wq_sim` by `served`, and would fail on an undefined Wq).

## Presentation

Simulation-page DES table, separate-queue rows only:

- Rows recorded with D2 add "Started service" and "Still waiting at horizon" columns and a note stating
  the Wq population and that rho includes service carried over from an earlier period.
- Rows without `wait_population` (stored before D2) show a note that the run used the earlier
  accounting and should be rerun; nothing is inferred from the metric values.

Simulated values are never labeled observed.

## Unchanged

Arrival generation, routing (none), FIFO discipline, service sampling, the shared RNG call order,
schedule transitions, drain policy, seeds, the trace, MC, the optimizer, break optimization,
D1/D5/D10, the continuous-day and shared-queue simulators, engine versions.

## Verification plan

- Independent references: hand-built service intervals (busy-time equation); a FIFO (Lindley)
  reconstruction from the trace's arrival times and deterministic or recorded service times;
  closed-form cases with one deterministic service sample.
- The 15 cases of the D2 directive, including the conservation checks.
- Before/after: identical traces and unchanged fields over many runs; NovaMart before/after table.
- D1/D5/D10 regressions, full backend and frontend gates.

## Verification results (2026-09-25)

- `tests/test_current_des_accounting.py` (15 tests) passes on the repair. Against the pre-repair
  code (HEAD `66ba238e` export, new-field checks made optional), all 15 fail; 12 fail on
  existing metrics (7 busy time, 5 Wq: 2 population, 3 zero instead of undefined; 1 whole-horizon
  busy conservation). The other 3 cover the new helper, the new summary field and a guard that a
  true zero stays 0.0 (the old code already got true zero right).
- Sample path unchanged: 101 runs (21 NovaMart seeds, 80 synthetic schedules with 1-3 lanes,
  mixed durations, variable staffing and draining; 9,518 events): traces and 23 non-accounting
  fields identical before and after. Only `busy_time`, `rho_sim` and `Wq_sim` change. After the
  repair every row satisfies arrivals = started + censored, served <= started, 0 <= rho <= 1 and
  Wq undefined exactly when started = 0; per lane, censored customers sum to the horizon waiting
  count, started - served sums to the horizon in-service count, and period busy time sums to the
  trace's whole-horizon busy time (1,854 rows, 245 lanes).
- NovaMart (seed 42): busy time 19.2211 h -> 22.8524 h, equal to the trace. 18 lane-periods'
  rho corrected (largest: 14:00 cashier_1 0.35 -> 0.8002; 14:00 cashier_3 0 -> 0.4584; 06:00
  cashier_1 0 -> 0.4034). 13 rows with no started customer: Wq 0.00 -> undefined. 17:00
  cashier_5: Wq 5.42 -> 4.07 min (4 started, 3 served, 1 still waiting at H with 1.41 min
  observed). Customers: 116 arrivals = 115 started + 1 censored; 114 served, 1 in service at H.
  Every value equals the independent trace reference. No unscheduled lane was draining in this run.
- Local database (read-only): 13 stored `workflow_des_current` jobs, all separate-queue, none with
  `wait_population` (pre-D2); they display the earlier-accounting note. 6 legacy `workflow_des`
  jobs are pooled-queue runs, 7 are selected-plan routing DES: neither uses this code.
- Pre-commit re-verification (final source, fresh `66ba238e` export as the pre-repair side): 106
  runs (41 NovaMart seeds, 60 new synthetic schedules with draining, 5 pooled-queue runs; 54,255
  events; 7 synthetic schedules end in the existing capability error, identically before and
  after). Traces, pooled-queue rows and every non-accounting field identical; every row and lane
  equals a reference rebuilt from the trace alone (3,036 rows, 308 lanes, 0 mismatches; the
  pre-repair rows fail the same reference on busy time in 1,127 rows and on Wq in 883). NovaMart
  seed 42 reproduces every value above.

## Recorded findings (not fixed; not authorized)

- **Breaks:** the Current DES ignores configured breaks. NovaMart's setup has 15 breaks (for
  example cashiers 1-3 on a 60-minute break at 11:00), and in the DES those lanes keep serving.
- **Status column:** separate-queue rows carry no `status`, so the DES table's Status cell is blank
  and the Stable / Critical cards count 0 for them.
- **`throughput`:** completed customers of the arrival cohort divided by the period length (it
  mixes arrival and completion attribution). It is not displayed.
- **Refused arrivals:** an arrival to a lane that is not accepting would be dropped without a
  count. No case was observed: 3,478 arrival checks over the 101 comparison runs, 0 refused.
- **D7:** Current DES evidence is keyed to the Setup, not the dataset. It stays visible after a
  dataset replacement.
