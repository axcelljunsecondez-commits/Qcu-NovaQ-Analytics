# Shared lines: simulated wait intervals stop at 0 (OD-W3 / N2)

Status: IMPLEMENTED and committed 2026-10-29 on branch `claude/friendly-bell-4801f0` (base `3ee8fe2c`; owner asked for both changes to be committed separately), NOT pushed. OD-S1 remains open (implemented as option (a)); OD-S2 and OD-S3 DECIDED 2026-10-29 (§8). Protected statistics change (AGENTS.md §5).

Approval: the owner approved, quoted verbatim as relayed by the parent session on 2026-10-29: "N1 and N2 apply your recommendation". The recommendation was: "fix shared-line ranges below 0 as a separate tested change, the same way as the separate-line fix." This is REPORTED; it was not typed in this session.

This is a separate change from the separate-lines fix (`docs/superpowers/specs/2026-10-29-separate-wait-interval-floor.md`), with no file in common. Plan: `docs/superpowers/plans/2026-10-29-shared-wait-interval-floor.md`.

## 1. Finding

- VERIFIED. `shared_replications.summarize_metric` (`backend/queueing_engine/simulation/shared_replications.py:277-297`) returns mean ± t(0.975, n−1)·SD/√n with no floor. The anonymous summaries use it at `:360/367` (cost), `:391` (customer counts), `:395` (mean of replication means), `:409` (`CONTINUOUS_METRICS`), `:441` (period utilization) and `:547` (breaks).
- VERIFIED. The named summaries use the same function: `shared_named_replications._summaries` (`:361-368`) for every number in `customers`, `waiting`, `closing`, `staffing` and `employees`, and `:391` for the mean of replication means.
- Negative lower bounds seen in real runs:
  - SYNTHETIC inputs (read-only review, 2026-10-29):
    - anonymous, DRAIN, 5 reps, seed 42: mean of means [−0.018, 0.647] h;
    - named fixture (`scripts/generate_shared_named_fixture.py`), 3 reps, seed 20261001: [−0.511, 1.567] h.
  - NovaMart as a shared line with 5 counters, 5 days, seed 42 (REPORTED by the parent session's chart agent):
    - `mean_wait_hours` −0.00059 h, `wait_sum_hours` −0.09122 h, `time_average_queue_in_horizon` −0.00702;
    - `waiting_hours_after_close` −0.01505 h, `server_hours_above_schedule_in_horizon` −0.0189 h.
- VERIFIED. Shown to users only in `frontend/src/components/simulation/NamedReplicationTable.tsx:96-104`: "{mean} min (Student-t interval {lower} to {upper} min; …)". For the committed fixture that reads about −30.68 to 94.03 min. The anonymous `ContinuousRun.tsx` shows the min–max across replications, not this interval.

## 2. Mathematics

Same rule as U10 F16 and the separate-lines fix. If the true mean μ is ≥ 0 and L ≤ U, then μ ∈ [L, U] ⇔ μ ∈ [max(0, L), U]. So the floored interval has the same coverage as the plain t interval and is that interval cut to the values μ can take.

What changes and what stays:
- Only a negative lower bound changes.
- Unchanged: mean, SD, SE, upper bound, min, max, n, n_undefined.
- `ci_half_width` stays t·SE (= upper − mean). With a floored lower bound it is no longer (upper − lower)/2; this is documented in the method text (§4).

## 3. Which quantities get the floor

Rule ("the same way as the separate-line fix"): floor quantities that measure customers waiting, customers left unserved, or cost, and only where every replication value is ≥ 0 by construction. Do not floor arrivals, served or utilization: the owner kept those plain for separate lines (OD-W2). Do not floor capacity, staffing, employee, overrun or break quantities: they are outside the approved scope, and one can legitimately be negative.

Code evidence that the floored quantities are never negative (VERIFIED from code unless marked):

- **Waits.** A customer's wait is `service_start − arrival`. Service starts at the current event time, after the customer joined the queue at arrival:
  - anonymous: `shared_continuous_des.py:403` (`service_start = now`), `:648` (wait);
  - named: `shared_named_des.py:455` (`service_start = t`), `:654`/`:660` (wait).

  So `wait_sum_hours` ≥ 0, and `mean_wait_hours` = wait_sum / served (served > 0, else None) is ≥ 0. The mean of replication means is a mean of values ≥ 0.
- **Waiting customer-hours.** These are accumulated only as `len(queue) × elapsed` with `elapsed > 0`:
  - anonymous: `shared_continuous_des.py:377-380` (in-horizon and after-close areas), `:700`, `:743`, `:751` (total = sum of the two);
  - named: `shared_named_des.py:353-356`, `:674-676`.

  `time_average_queue_in_horizon` = queue area / horizon hours (`:711`, horizon > 0).
- **Queue maximum.** It starts at 0 and only takes `max(…, len(queue))`:
  - anonymous: `shared_continuous_des.py:357`, `:682`, `:713`;
  - named: `shared_named_des.py:339`, `:461`, `:677`.
- **Customers left unserved or waiting at closing.** These are counts of rows or ids: `unserved` (anonymous `shared_continuous_des.py:680`), named `unserved`, `unserved_hard_cutoff`, `unserved_no_eligible_employee` (`counts`), and `waiting_at_close` = `len(waiting_customer_ids)` (`shared_named_replications.py:348`).
- **Costs.** Each component is quantity × rate:
  - rates must be finite and ≥ 0 (`shared_day_cost.py:54-64`);
  - the quantities are server-hours (present-server areas, `shared_continuous_des.py:382`), waiting customer-hours (above) and the unserved count.

  So every costed component and the total is ≥ 0.

Floored:

| Run type | Summary | Keys |
|---|---|---|
| Anonymous | `summary.waiting_time.mean_of_replication_means_hours` | — |
| Anonymous | `summary.metrics` | `wait_sum_hours`, `mean_wait_hours`, `waiting_hours_before_close`, `waiting_hours_after_close`, `total_waiting_hours`, `time_average_queue_in_horizon`, `max_queue_in_horizon` |
| Anonymous | `summary.customers.per_replication` | `unserved` |
| Anonymous | `summary.cost` | `total_cost` and each costed component's `per_replication` |
| Named | `summary.waiting_time.mean_of_replication_means_hours` | — |
| Named | `summary.metrics.waiting` | all six: `wait_sum_hours`, `mean_wait_hours`, `customer_hours_in_horizon`, `customer_hours_after_closing`, `customer_hours_total`, `max_queue_in_horizon` |
| Named | `summary.metrics.closing` | `waiting_at_close` |
| Named | `summary.customers.per_replication` | `unserved`, `unserved_hard_cutoff`, `unserved_no_eligible_employee` |

Not floored (plain interval as before):

| Quantity | Reason |
|---|---|
| `server_hours_above_schedule_in_horizon` | "Available minus scheduled" (`shared_continuous_des.py:686, 717`). It can be below 0 when a server is absent for part of a scheduled segment (INFERRED from the definition), so it must never be floored. |
| `arrivals`, `served`, named `served_after_closing` | OD-W2 parity. |
| `utilization_in_horizon`, `utilization_whole_run`, `period_utilization` | OD-W2 parity. |
| Busy, available, overtime and scheduled server-hours; `overrun_hours`; breaks; named `in_service_at_close`, `drain_crew_size`, `run_after_closing_hours`; every `staffing` and `employees` value | Outside the approved scope. Many are ≥ 0 too; OD-S2 decided they stay plain. |

Proportions (Wilson) are unchanged: they are already within [0, 1].

## 4. Interval-method text

`CONTINUOUS_INTERVAL_METHOD` (`shared_replications.py:80-84`) is stored in each run's provenance:
- anonymous `provenance.interval_methods.continuous`;
- named `provenance.interval_method` (`shared_named_replications.py:483`).

It gains one sentence naming the rule: for a quantity that cannot be negative (waits, waiting customer-hours, queue lengths, customers left unserved, costs) the lower bound is max(0, mean − t·SE), and `ci_half_width` stays t·SE. Each run therefore says how its own bounds were made. Stored runs keep the old text and their old (unfloored) bounds, which matches them. The frontend does not display this text (VERIFIED: no `interval_method` reader in `frontend/src`).

Screen wording (OD-S3, owner decision):
- What it shows now: `simulation.named_agg_mean_of_means_value` reads "Student-t interval {lower} to {upper} min" (en and tl). For a new run whose lower bound is floored this shows e.g. "Student-t interval 0 to 94.03 min".
- Is that truthful? The numbers are the Student-t interval cut at 0, so the label is correct but does not say the lower end was cut.
- Why I didn't change it: under the project rule, agents do not write or translate UI copy.
- Slots for the owner if wanted: en and tl text for a note such as "(lower end stops at 0)" in `simulation.named_agg_mean_of_means_value`.
- No frontend copy is changed by this change.

## 5. Version (OD-S1, owner decision)

Implemented: no method or engine version change. This mirrors OD-W1 ("Option 1, leave them as they are").

Reasons:
1. The replication rows are unchanged; only the summaries change.
2. Named playback refuses a run whose `method_version` differs from the code's (`shared_named_playback.py:1233-1238`). A bump to `novaq-shared-named-replications-v3` would block playback of every stored named run although its rows regenerate exactly.
3. Each run carries its own interval-method text (§4), so old and new runs are each described correctly.

Consequences:
- A shared run stored before this change still returns its negative lower bounds from `GET …/continuous/runs/{id}` and `GET …/shared-named/runs/{id}`. The named table shows them for such runs.
- Alternatives:
  - (b) bump `METHOD_VERSION` (anonymous `novaq-shared-des-replications-v2`, named `-v3`), which costs named playback of old runs;
  - (c) apply the floor when the API returns a stored run.

Recommendation: (a), as implemented.

## 6. Reference cases (hand-computed; Student-t table t(0.975, 2) = 4.302653, t(0.975, 4) = 2.776445)

| Case | Values | Mean | SE | Half width | Plain [L, U] | Floored [L, U] |
|---|---|---|---|---|---|---|
| S1 binds | 0, 0, 0, 0, 0.1 | 0.02 | 0.02 | 0.0555289 | [−0.0355289, 0.0755289] | [0, 0.0755289], `ci_half_width` 0.0555289 |
| S2 does not bind | 0.10, 0.12, 0.14 | 0.12 | 0.0115470 | 0.0496828 | [0.0703172, 0.1696828] | unchanged |
| S3 undefined value | None, 0, 0, 0, 0, 0.1 | 0.02 (n 5, n_undefined 1) | 0.02 | 0.0555289 | as S1 | as S1 |
| S4 count | 0, 0, 0, 0, 2 | 0.4 | 0.4 | 1.110578 | [−0.710578, 1.510578] | [0, 1.510578] |
| S5 one value | 0.3 | 0.3 | None | None | None | None |

## 7. Verification

- Unit (new `tests/test_shared_wait_interval_floor.py`):
  - S1-S5 against the literals above;
  - the anonymous and named aggregators floor exactly the §3 keys and leave the others plain;
  - a real anonymous and a real named run, where some floored lower bound would be negative, give 0 there and identical other statistics.
- Existing tests that compare with the plain t interval keep passing where the bound is positive. Any that pinned a negative floored key is updated only to the §3 rule.
- Fixture: `frontend/src/test/fixtures/sharedNamed.json` is regenerated with `scripts/generate_shared_named_fixture.py`. Its diff must contain only floored lower bounds and the interval-method text; any other change stops the update.
- Mutation: removing the floor from each group (anonymous waits, anonymous unserved, anonymous cost, named waiting, named closing/customers, both mean-of-means) must fail a test.
- Gates: `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`. If the fixture changes, also run `npm test`, `npm run typecheck`, `npm run lint` and `npm run build` in `frontend/`.

Results 2026-10-29 (local Windows, Python 3.13.13, SQLite; PostgreSQL not run):

- All 9 new tests failed on the unchanged code and pass after the change.
- `test_shared_replications.py`, `test_shared_named_replications.py` and the new tests: 128 passed.
- One existing assertion was updated to §3: `test_shared_named_replications.py::test_aggregation_counts_every_replication_and_matches_independent_statistics` pinned the plain lower bound of `customer_hours_total` (−1.03); it now expects max(0, plain).
- Related shared-line, API, playback, B4a/B4b/B4c and full-day tests (`test_api_shared_named.py`, `test_b10_dataset_purpose.py`, `test_b4a_continuous_preview.py`, `test_b4b_recorded_service.py`, `test_b4c_counter_breaks.py`, `test_od_ux_13_full_day_decision.py`, `test_shared_named_attribution.py`, `test_shared_named_cost.py`, `test_shared_named_playback.py`, `test_shared_playback.py`): 723 passed, 5 skipped.
- Fixture:
  - The scratch regeneration differed from the committed fixture in 27 fields. 20 are §3 changes: 9 floored lower bounds (old −0.511 to −5.50, new 0.0) and the method text, in each of the 2 run copies. The other 7 are not §3 changes: the run timestamps and `dataset_generation`.
  - So the fixture was NOT replaced. Only the 20 §3 fields were patched into the committed file (each new lower bound checked to equal max(0, old)).
  - Result: 20 lines changed.
- Mutation: removing the floor from each group (anonymous metrics, anonymous unserved, anonymous cost total, anonymous cost components, anonymous mean of means, named paths, named mean of means) made the new tests fail. 7/7 killed.
- `ruff check .`: passed.
- `mypy .`: only the pre-existing `backend/api/shared_continuous.py:447` error (same as base `3ee8fe2c`).
- Frontend (dependencies installed with `npm ci` from the lockfile):
  - `npm run typecheck`, `npm run lint` and `npm run build` passed.
  - `npm test` while the backend suite ran: 742 passed, 3 failed. The failures were in `NewAnalysisPage.test.tsx` (2) and `ReplayStates.test.tsx` (1), which do not use the changed fixture. Both files passed alone (22/22).
  - Full `npm test` rerun after the backend suite: 745 passed, 0 failed (90 files). The earlier failures are INFERRED to be timing under load.
- Full suite `python -m pytest tests/ -x --tb=short`: 3303 passed, 125 skipped (PostgreSQL tests, NOT TESTED), 1 xfailed, exit 0. This run includes the uncommitted separate-lines change in the same worktree.

## 8. Open items for the owner

- OD-S1: version (§5). Implemented as (a); recommendation (a).
- OD-S2: also floor the other non-negative quantities (server-hours, overrun, breaks, staffing, employees)? DECIDED 2026-10-29 (owner, "S2 and S3 apply your recommendation", REPORTED via the parent session): leave them unfloored. No further engine change.
- OD-S3: screen wording note for a floored lower end (§4). DECIDED 2026-10-29 (same owner words, REPORTED): the parent session's main UI build adds a short "range cut at 0" note to the named-staff interval text (`NamedReplicationTable.tsx:96-104`). It reuses the chart redesign's range-cut ⓘ text. This change makes no frontend change for it.
