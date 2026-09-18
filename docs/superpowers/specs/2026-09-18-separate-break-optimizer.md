# Separate Queue Break Optimizer — Specification (2026-09-18)

## Problem (verified against the code and NovaMart `novaq_data.xlsx`)

- Breaks are fixed user input. `QueueBreak(queue_id, scheduled_start_time,
  duration_minutes)` (`backend/api/analysis_schemas.py:61-74`) is only valid
  for `separate_queues` (`analysis_schemas.py:126-127`). Nothing in NovaQ
  proposes different break times.
- The separate optimizer (`optimize_separate_schedule`,
  `separate_optimization.py:1599`; API `run_separate_optimize`,
  `workflow.py:961-1011`) chooses active lanes per period. It never moves a
  break.
- NovaMart stacks breaks. From the `Avg 15Min` sheet (λ, μ per 15 min, pooled
  over 14 days) with the current breaks, peak ρ is 1.3262 (11:30–11:45) and 5
  slots exceed 0.85 (07:15, 11:00, 11:15, 11:30, 12:15). Computed this session.

## Approved product decisions (user, 2026-09-18)

1. Separate queues only. The shared optimizer
   (`backend/queueing_engine/services/optimization.py`) is untouched.
2. A break keeps its cashier and length. Only its start moves, in 15-minute
   steps, within ±`max_shift_minutes` of the current start (default 120).
3. A break lies inside its cashier's shift and never in the first or last
   60 minutes of that shift.
4. A cashier's break order by time is preserved.
5. Greedy placement: longest break first, then cashiers in queue_id order. Each
   break takes the start that minimizes the day's peak 15-minute ρ. Ties go to
   the start nearest the current one.
6. `ρ_slot = λ_slot / (working_slot × μ_slot)`, where working means on shift
   and not on break. Target ρ defaults to 0.85 and is configurable.
7. Success means the peak ρ goes down and every slot is below target when
   possible. "No slot may get worse" is not a rule.
8. Proof: the existing separate-queue DES runs on both schedules and compares
   simulation with simulation. Recorded waits are never compared with
   simulated waits.
9. Staffing gaps that no break move can fix are reported separately. The
   recorded-wait data warning is dropped from this feature (user, option b):
   stored records hold no customer timestamps (`analysis_ingestion.py:299-316`),
   so it cannot be computed from what the optimizer reads.
10. The Optimize page shows the break optimizer only for separate queues.
    For shared queues it shows "Break optimization is available for separate
    queues."

## Slot inputs in the app (hourly segments)

The optimizer reads the Setup and the stored dataset records, not the upload
file.

- **Required basis:** `event_period_basis = representative_day`. Only this
  basis gives one record per segment and queue
  (`analysis_ingestion.py:278-281`). It is also the only basis with a
  continuous-day DES (`workflow.py:1474`). A `per_date` analysis is rejected
  with an exact reason.
- **Record contents** (`analysis_ingestion.py:299-316`):
  - `lambda = arrivals / (segment_hours × D)`, where D is the number of
    observed dates
  - `mu = 1 / mean service`
  - `service_samples_hours` holds every service time
- **Slot grid:** 15-minute slots from the earliest segment start to the
  latest segment end. This is the same origin as `des_day_start_minutes`
  (`separate_optimization.py:630`). Every segment start and end must lie on
  this grid, otherwise the request fails with an exact reason.
- **λ_slot:** the sum of `lambda` over the segment's queue rows
  (`index_period_queues`). This is the same total the day DES uses
  (`separate_optimization.py:1133-1134`).
- **μ_slot:** the segment's pooled rate, `count(samples) / sum(samples)` over
  all its queue rows. This is the same pooled definition as the `Avg 15Min`
  sheet (arrivals ÷ total service time).
- **Consequence:** in the app, λ and μ are constant across the four slots of
  an hourly segment, so the in-app result can differ from the 15-minute
  reference. The placement core takes per-slot λ and μ as input, so the
  reference can be tested exactly.
- **On shift:** a queue is on shift in a slot when the slot's segment lists it
  in `active_queue_ids`. With fixed staffing, every `queue_id` is on shift.
  A cashier's shift is its one continuous run of active segments. A second,
  separate run fails the request with an exact reason.
- **Working count:** the number of cashiers on shift, minus the fraction of
  the slot each on-shift cashier spends on break. For breaks on the 15-minute
  grid this is a whole number.
  - If working is 0 and λ > 0, ρ is `null` (reported as a gap).
  - If λ = 0, ρ is 0.
- **Not modelled in ρ:** the DES 3-minute pre-break drain
  (`PRE_BREAK_CUTOFF_MINUTES`, `backend/queueing_engine/config.py:30`) and
  routing. The DES proof does include both.

## Placement algorithm (pure function)

Input: per-slot `(start_minute, λ, μ)`, shifts per queue, current breaks,
queue order, `target`, `max_shift_minutes`.

1. **Order:** duration descending, then queue position in Setup `queue_ids`,
   then current start ascending.
2. **Placement starts from an empty schedule.** Breaks are added one at a
   time. A candidate is scored with only the already-placed breaks plus
   itself.
   - Verified this session: this reproduces the reference exactly.
   - The alternative, scoring with not-yet-placed breaks at their current
     times, stops at peak 0.9833 with 4 slots above target.
3. **Candidates:** `current + 15k` for every k with `|15k| ≤
   max_shift_minutes`. A candidate is feasible when:
   - `start ≥ shift_start + 60` and `start + duration ≤ shift_end − 60`
   - it keeps its order against the cashier's already-placed breaks (by
     current order) and does not overlap them
4. **Score:** the peak ρ over all slots, where `null` (no one working) counts
   as infinity. Ties (within 1e-9) go to the smallest `|shift|`, then the
   earlier start.
5. **No feasible candidate:** the request fails and names the break.
6. **Outcome:**
   - `improved`: the proposed peak is below the current peak by more than
     1e-9.
   - `no_improvement`: otherwise. The proposed schedule then equals the
     current schedule and there are no moves.
   - `all_below_target`: every proposed slot has ρ < target.
7. **Staffing gaps:** slots where ρ ≥ target even with nobody on break, or
   where nobody is on shift while λ > 0. No break move can fix these.

**Reference check (15-minute `Avg 15Min` inputs, NovaMart Setup, defaults),
computed this session:**

| Cashier | Break | Current start | Proposed start |
|---|---|---|---|
| cashier_2 | lunch | 11:00 | 10:30 |
| cashier_3 | breakfast | 07:00 | 06:45 |
| cashier_3 | lunch | 11:00 | 11:45 |
| cashier_4 | lunch | 12:00 | 13:45 |
| cashier_5 | lunch | 12:00 | 12:45 |

- Peak ρ goes from 1.3262 to 0.7202.
- Slots above 0.85 go from 5 to 0.

## DES proof

- **Reuses existing code:** `run_routing_day_des`
  (`separate_optimization.py:978`), `breaks_to_des_offsets` (`:653`),
  `resolve_des_breaks` (`:692`), `des_day_start_minutes`, `_segment_window`,
  `index_period_queues` and `replication_seeds` (`:404`). No new simulator.
- **Windows:** one window per configured segment. Each window uses the
  scheduled `active_queue_ids`, the record λ (no multiplier) and the record
  service samples. This mirrors `_run_selected_plan_day_des`
  (`workflow.py:1474-1516`), but takes lanes from Setup instead of a saved
  plan.
- **Breaks:**
  - Current: `resolve_des_breaks(setup)`.
  - Proposed: `resolve_des_breaks({**setup, "breaks": proposed})`.
- **Runs:** the same seeds for both schedules. Defaults are 5 replications
  and base seed 42, matching the existing defaults
  (`separate_optimization.py:75, 81`).
- **Output per schedule:**
  - per replication: the served-weighted mean wait (min), max queue,
    admitted, served, conservation
  - summary: the mean over replications of each value
  - mean wait per period
- **Comparison:** change in mean wait, and the number of replications where
  the proposed schedule has the lower mean wait.

## API

`POST /analyses/{id}/workflow/optimize/separate/breaks` (compute rate limit).

Request:

```json
{ "dataset_id": null, "target_rho": 0.85, "max_shift_minutes": 120,
  "des": { "replications": 5, "base_seed": 42 } }
```

- `target_rho`: greater than 0 and at most 1.
- `max_shift_minutes`: a multiple of 15, from 0 to 240.
- `replications`: 1 to 20.

Response:

```json
{ "status": "improved | no_improvement", "target_rho": 0.85,
  "all_below_target": true,
  "current_breaks":  [{ "queue_id", "label", "scheduled_start_time", "duration_minutes" }],
  "proposed_breaks": [{ "queue_id", "label", "scheduled_start_time", "duration_minutes",
                        "current_start_time", "shift_minutes" }],
  "moves": [{ "queue_id", "label", "from", "to", "duration_minutes" }],
  "slots": [{ "start", "end", "lambda", "mu", "working_before", "working_after",
              "rho_before", "rho_after" }],
  "peak_rho": { "before", "after" },
  "slots_above_target": { "before", "after" },
  "staffing_gaps": [{ "start", "end", "on_shift", "rho_no_breaks" }],
  "des": { "seeds": [42,43,44,45,46],
           "current":  { "summary": {...}, "replications": [...], "periods": [...] },
           "proposed": { "summary": {...}, "replications": [...], "periods": [...] },
           "comparison": { "mean_wait_change_minutes", "proposed_better_runs", "runs" } },
  "notes": ["ρ uses hourly segment λ/μ ...", "Simulation vs simulation only ..."] }
```

- `label`: "Break 1, 2, 3" per cashier in current time order. `QueueBreak`
  has no name field.
- Nothing is persisted. The Setup is not changed; the user applies moves in
  the Setup break editor.
- Errors return 422 with exact reasons:
  - "Break optimization is available for separate queues."
  - "Break optimization requires the representative day basis."
  - "This Analysis has no configured breaks to move."
  - off-grid segment, split shift, no feasible start for a named break
  - existing DES errors, passed through

## UI (Optimize page)

- **Separate queues:** a "Break schedule" card with inputs for target ρ and
  maximum move (minutes), plus a Run button. Results:
  1. Status line with peak ρ before → after and slots above target before →
     after.
  2. Before/after break table: cashier, break, current start, proposed start,
     minutes, moved.
  3. ρ before/after for each changed slot only (where |Δρ| > 1e-9).
  4. Staffing gaps, as a separate list.
  5. DES before/after summary: mean wait, max queue, admitted/served, and
     "proposed better in n of R runs", plus the simulation-only note.
- **Shared queues:** no card. Instead the note "Break optimization is
  available for separate queues."
- New strings go in both `en` and `tl` locales.

## Unchanged (protected)

- the shared optimizer and `test_shared_optimizer_outputs_unchanged`
- queueing formulas
- `optimize_separate_schedule` and its API
- the DES and the break lifecycle
- representative-day pooling
- Decision rules, reports, migrations
- the stored Setup (read only)

## Acceptance

- A unit test feeds the `Avg 15Min` λ/μ (committed as a small fixture) and
  the NovaMart Setup. It gets exactly the 5 moves above, peak ρ 1.3262 →
  0.7202, and slots above 0.85 going from 5 to 0.
- Property tests on every proposed break: same cashier and length, inside the
  shift, not in the first or last 60 minutes, within ±120 minutes, order
  preserved, no overlap.
- An API test on a representative-day NovaMart-shaped analysis:
  - returns both schedules, per-slot ρ before/after, and DES results from
    `run_routing_day_des` for both schedules with identical seeds
  - leaves the Setup unchanged
- Shared analysis → 422. The Optimize page hides the card and shows the note.
- The existing suite passes, except the known
  `test_parallel_des_long_stable_case_matches_pollaczek_khinchine`.

## Resolved decisions

1. **Data warning:** dropped (option b). The staffing-gap report stays, and
   the proof stays simulation vs simulation only.
2. **`queue_id` order:** Setup `queue_ids` order (same as lexical order for
   NovaMart).
3. **Equal-distance tie:** the earlier start wins. The reference result is the
   same under either rule.

## Out of scope

- The recorded-wait data warning.
- Applying the proposed breaks to Setup automatically.
- Break optimization for shared queues or the `per_date` basis.
