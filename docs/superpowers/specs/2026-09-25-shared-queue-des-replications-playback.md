# Shared Queue Enhancement: Phase 4, DES Replications and Event Playback

Date: 2026-09-25. Status: approved for Phase 4 by the product owner (backend only). No API,
frontend, Decision, Report, scenario, or workforce change.

Builds on Phases 1 to 3A: `b616e3ae`, `ad8ed236`, `b212d7ee`, `9eaf5d4a`, and `d7b8eff1`.

## Starting point (re-verified 2026-09-25)

- HEAD is `d7b8eff1`, parent `e0913258`. The branch is unpushed, and the tree is clean apart
  from the untracked `.claude/`.
- The legacy shared Monte Carlo (`simulation.py` `mc_simulate_segment`) recomputes the
  analytical formulas under ±20% arrival and ±10% service noise. It runs no DES.
- The legacy shared playback replays `POST /simulation/des/trace`.
- The continuous shared DES has no API or UI.

## A. Replications (`simulation/shared_replications.py`)

Every replication runs the Phase 3A continuous DES over the whole horizon:

- the same validated timeline;
- one explicit closing policy;
- the scenario's own rates.

There is **no parameter perturbation**. The legacy ±20%/±10% noise is not applied, and
parameter uncertainty is a separate experiment that is not implemented here.

### Count and seeds

- `replications` is required. The two existing defaults (2000 analytical Monte Carlo trials,
  and 5 separate-queue optimizer DES replications) were set for other methods. Neither is
  assumed here.
- The count must be a whole number from 1 to `config.MC_MAX_TRIALS` (100000), the existing
  NovaQ Monte Carlo limit, also enforced by the `num_trials` API fields.
- Seeds:
  - The root is `numpy.random.SeedSequence(seed)`. `seed=None` draws fresh entropy, which is
    recorded.
  - Replication *i* (0-based) uses child `root.spawn(R)[i]`, which equals
    `SeedSequence(entropy=root.entropy, spawn_key=(i,))`.
  - Inside each child, the Phase 3 engine spawns two streams: arrival gaps, then unit work.
  - numpy documents that spawned children seed independent bit generators (numpy 2.4.6
    `SeedSequence` docstring). Any replication can be regenerated alone from
    (root entropy, *i*).
- The engine gains `simulate_shared_replication(..., seed_sequence=...)`.
  `simulate_shared_day(seed=...)` now draws through the same helper, and its output is
  byte-identical: a digest of 100 runs was compared before and after the change.

### Per-replication row (retained; no events)

Each replication runs with `max_trace_events=0`; the trace cap does not affect metrics
(Phase 3 test). Only one scalar row per replication is kept:

- Customers: arrivals, served (departed), unserved, and conservation.
- Waiting:
  - the sum of served waits;
  - the replication mean wait, over customers who started service (denominator: served;
    undefined when 0);
  - waiting customer-hours before closing, after closing, and in total.
- Queue: the in-horizon time-average queue, total waiting customer-hours ÷ horizon hours,
  and the in-horizon maximum.
- Servers:
  - busy server-hours in the horizon and after closing;
  - available (present) server-hours in the horizon and after closing (regular and
    overtime);
  - scheduled server-hours and hours above schedule.
- Utilization, with explicit denominators:
  - `utilization_in_horizon` = busy ÷ present, both in the horizon (undefined when present
    is 0);
  - `utilization_whole_run` = (busy in + after) ÷ (present in + after).
- Overrun hours.
- Cost: per replication from `cost_shared_day`, when rates are given.
- Criterion outcomes, when criteria are given.

### Aggregation

- Continuous metrics use the NovaQ DES-replication convention
  (`separate_optimization._summarize_metric`):
  - mean, sample SD, SE, and a Student-t interval at `MC_CONFIDENCE_LEVEL` (0.95);
  - the contributing count, plus min and max;
  - with n < 2, a mean only;
  - undefined values are counted in `n_undefined`, never zero-filled.
- Waiting time is reported two ways:
  - the **mean of replication means**: Student-t over replications with ≥ 1 served
    customer, with excluded replications counted;
  - the **customer-weighted mean** = Σ served waits ÷ Σ served customers, with numerator
    and denominator shown. No interval is computed for it.
- Customer totals across replications are summed.
- Descriptive outcome counts, which are not verdicts: replications with an unserved
  customer, and replications with overrun.

### Cost

- `cost_rates` (Phase 3A `DayCostRates`) is optional. Without it, no monetary output is
  produced.
- With it, each replication is costed first, then aggregated: component means and the mean
  replicated total cost (Student-t).
- The unserved term follows Phase 3A `unserved_possible`. That flag depends only on the
  policy and the final staffing, so it is the same for every replication.
- If an applicable rate is missing, costed components are still aggregated. The total is
  withheld with the Phase 3A reason, never replaced by 0.
- Server-hours are modeled capacity, not payroll.

### Failure criteria (no defaults, no verdict)

`FailureCriteria` is optional. Each field defaults to `None` (not evaluated), and at least
one must be set. Thresholds are supplied by the caller:

| Criterion | Replication value | Violated when | Not evaluable when |
|---|---|---|---|
| `max_mean_wait_minutes` | mean wait of served customers × 60 | value > limit + 1e-9 | no customer served |
| `max_utilization` (0 < limit ≤ 1) | `utilization_in_horizon` | value > limit + 1e-9 | present hours are 0 |
| `max_unserved_customers` (whole) | unserved count | value > limit | never |
| `max_overrun_minutes` | overrun × 60 | value > limit + 1e-9 | never |

- The tolerance is the pipeline's `THRESHOLD_TOLERANCE`, as in Phase 2.
- The utilization limit is independent of any Phase 2 target utilization.
- A replication **fails** if any set criterion is violated. It **passes** if every set
  criterion is evaluable and satisfied. Otherwise it is **not evaluable**.
- Each proportion is violations ÷ evaluable replications, with a Wilson interval
  (`statistics.proportions.wilson_ci`, z for `MC_CONFIDENCE_LEVEL`). The report states the
  numerator, denominator, not-evaluable count, threshold, confidence level, and method.
- No PASS/FAIL or acceptable label is produced. No approved acceptance rule exists for this
  engine, so `verdict` is `None` with that reason. The legacy utilization > 0.75 rule and
  the 0.05 cap are not used.

## B. Playback (`simulation/shared_playback.py`)

- `prepare_shared_playback(horizon, periods, segments, *, root_entropy, replication_index,
  closing_policy)` regenerates exactly one replication with a full trace.
- `playback_from_replications(replication_result, replication_index)` rebuilds the inputs
  from the replication run's provenance, regenerates that replication, and **raises** unless
  its summary row equals the stored row. Events from different replications are never
  combined.

### Events

Events are the engine's own trace, in engine order: `seq`, `t`, `type`, customer, server,
segment, and `queue_len_after`. The event types are:

- `arrival`: the customer enters the line. The engine appends every arrival to the line, and
  service may start at the same time, so no separate queue-entry event exists.
- `service_start`.
- `service_end`: service completion. It is also the departure, since there is no
  post-service time.
- `server_open`, `server_drain_start`, `server_drain_complete` (the server closes),
  `server_close`, `server_reactivate`.
- `capacity_change`.
- `closing`: the closing policy runs.
- `unserved_at_close`.

### Replay check

An independent replay rebuilds state from the events alone, and each event carries the
resulting state (queue length and head, and idle, busy, and draining server counts). The
replay **raises** on any inconsistency:

- time goes backwards;
- a service start other than the queue head (first come, first served);
- an illegal server transition;
- a queue length that differs from `queue_len_after`;
- after a capacity change, accepting servers that differ from the schedule;
- an arrival or capacity change after `closing`;
- a customer or server left unresolved at the end.

Customer and server timelines are derived from the events and cross-checked against the
engine's customer rows. The replay also recomputes served and unserved counts, busy and
present server-hours in the horizon and after closing, and waiting-hours. These must equal
the replication summary row.

## Verification

1. Conservation in every replication.
2. Seeded reproducibility, and recorded entropy for `seed=None`.
3. Distinct streams:
   - children differ, and each regenerates from (entropy, index);
   - arrival counts of paired replications are uncorrelated within 4 SE.
4. Waiting-time denominators, checked against an independent recomputation from full
   customer rows.
5. Busy and available server-hours, recomputed independently from customer rows and
   capacity-transition intervals.
6. Overtime equals service time after closing.
7. Unserved counts.
8. Per-replication cost matches the hand-computed formula.
9. Aggregate cost is the mean of per-replication totals, and the Student-t interval matches
   `scipy.stats.t.interval`.
10. Wilson intervals match `scipy.stats.binomtest(...).proportion_ci(method="wilson")`.
11. The playback summary equals the stored replication row.
12. Replay continuity across staffing and closing boundaries on many seeds and both
    policies.
13. Statistical: the mean in-horizon queue over replications matches Erlang C Lq within 4 SE
    (λ 40, μ 20, c 3, 24 h).
14. A fault-injection check, the full backend suite, ruff, and mypy.
