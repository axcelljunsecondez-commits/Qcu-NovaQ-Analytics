# Shared Queue Enhancement: Phase 5B-4.4, Seeded Named-Employee DES Replications

Date: 2026-09-28. Status: implemented as
`backend/queueing_engine/simulation/shared_named_replications.py`, with tests in
`tests/test_shared_named_replications.py`. Committed locally only; not pushed, merged, or deployed.

Plan: `docs/superpowers/plans/2026-09-28-shared-queue-named-replications-plan.md`.
Related specs: `2026-09-28-shared-queue-named-des.md` (the 5B-4.3 engine, amended here),
`2026-09-28-shared-queue-employee-state-machine.md` (amended here),
`2026-09-28-shared-queue-named-employee-des-policy.md` (the policy contract, which records the
decisions below), and `2026-09-25-shared-queue-des-replications-playback.md` (the Phase 4 seed
convention reused here).

## Approved semantics used (Phase 5B-4.4 request, 2026-09-28)

The request says: "Freeze these rules before implementing replications."

| # | Rule (quoted) | Before this phase | Now |
|---|---|---|---|
| 1 | Service completion exactly at closing with a break due: "complete service first; at closing, that break becomes UNFULFILLED / cancelled_at_closing; do not manufacture a zero-duration break." | `UndeterminedPolicyError` | The service completes, no break starts, and the break is `cancelled_at_closing`; the employee is released at closing |
| 2 | Break ending exactly at closing: "classify as truncated_by_closing because closing is processed before break-end at the same timestamp." | `completed` (INFERRED) | `truncated_by_closing` |
| 3 | Accepting capacity: "AVAILABLE plus ordinary SERVING employees only." | same (INFERRED) | same (approved) |
| 4 | Event time: "no generic event-time epsilon; roster-derived boundaries remain based on exact integer-minute arithmetic; stochastic service times are not rounded or snapped to schedule boundaries." | same (tolerance UNKNOWN) | same (approved) |
| 5 | Staffing gaps: "report gaps per staffing segment and over the configured operating horizon; do not calculate schedule/requirement gaps before opening or after closing; report post-close capacity/time separately." | the schedule gap was also computed before opening and after closing | gaps only inside [opening, closing); `after_closing` always reported, series only |

Rules 1, 2, and 5 change named-engine behavior or output. The 5B-4.3 and 5B-4.2 specs record each
change and the three test expectations the rules changed ("Phase 5B-4.4 amendments" in each).

## Scope

- **In scope:** the five rules above; the X5 public arrival interface; seeded replications of the
  named engine with regenerable replications, common random numbers, and descriptive aggregation.
- **Not in scope:** named playback (5B-4.5), attribution reporting (5B-4.6), workforce monetary
  cost (5B-5), API, database, frontend, Decision, and Reports. No acceptance rule exists, and none is
  invented.
- **Files.**
  - New: `simulation/shared_named_replications.py`, `tests/test_shared_named_replications.py`, this
    spec, and the plan.
  - Changed (production):
    - `simulation/shared_continuous_des.py`: the X5 wrapper only.
    - `simulation/shared_named_des.py`: rules 1, 2, and 5, and texts.
    - `simulation/shared_employee_states.py`: rule 1.
  - Changed (tests): `tests/test_shared_named_des.py`, `tests/test_shared_employee_states.py`, and
    `tests/test_shared_segments.py` (the isolation list).
  - Changed (docs): the three related specs, `memory.md`, and `handoff.md`.
  - Not changed: every other production module, including the Phase 4 replications and playback,
    the 5B-1, 5B-2, and 5B-3 services, the legacy DES, and all Separate Queue code.

## X5: the public arrival interface

```python
shared_continuous_des.draw_arrivals(horizon, demand_periods, staffing_segments, *, seed_sequence)
```

- It runs the same two checks as `simulate_shared_replication`: `validate_timeline`, and an unused
  `SeedSequence`. It then returns `_draw_arrivals(horizon, demand_periods, seed_sequence)`. It has
  no stochastic logic of its own.
- The pairs depend only on the horizon, the demand periods, and the sequence. The staffing segments
  serve validation only. `test_the_public_interface_reuses_the_private_generation_and_ignores_staffing`
  gives two different staffing lists the same pairs.
- No existing function changed. `simulate_shared_day`, `simulate_shared_replication`, and
  `simulate_prescribed` still call `_draw_arrivals` or take prescribed pairs exactly as before.
  - The 5B-4.0 pin passes without regenerating the fixture.
  - A scratch digest covered 100 `simulate_shared_day` runs, 40 `simulate_shared_replication` runs,
    and 4 `run_shared_replications` runs (2 configurations x 2 policies). Its SHA-256 was the same
    before and after the change: `236d87ec...c610` on numpy 2.4.6.
- The named modules do not import `_draw_arrivals`.
  `test_module_uses_only_the_public_arrival_interface` checks the imports and attributes of
  `shared_named_replications.py`.

## Seeds and streams

- **Convention.** This is the Phase 4 convention, reused unchanged (`shared_replications.SEED_SCHEME`,
  VERIFIED in the Phase 4 tests).
  - The root is `SeedSequence(seed)`. `seed=None` draws fresh entropy, recorded as `root_entropy`.
  - Replication i uses `replication_seed_sequence(root_entropy, i)`, which is
    `SeedSequence(entropy=root_entropy, spawn_key=(i,))`. That is the i-th child of
    `SeedSequence(root_entropy).spawn(n)`; `test_replication_seed_is_the_phase_4_child` compares
    entropy, spawn key, pool size, and generated state.
  - `run_named_replications` builds every replication through `replication_seed_sequence`. Its rows
    are therefore regenerated by construction from `(root_entropy, i)`.
- **Streams.** `draw_arrivals` spawns two children of the replication's sequence and draws from a
  `numpy.random.default_rng` for each:
  - arrival gaps: exponential at the demand period's rate, restarted at each period start;
  - unit work: Exp(1), one per customer in arrival order.
- **No other randomness.** The named engine and the employee state machine import neither numpy nor
  `random`, which static tests of both modules check. Employee choice (X1) and every workforce
  transition are deterministic.
- **Common random numbers.** The customers of replication i depend only on the horizon, the demand
  periods, `root_entropy`, and i. With the same seed, every roster, required staffing, closing
  policy, and employee policy sees the same customers. Each row records `customer_inputs_sha256`, a
  SHA-256 of the pairs written with `float.hex()`, so this can be checked after the fact.
- **Provenance.** Each replication records `seed_entropy`, `spawn_key`, `pool_size`, the customer
  count and digest, the arrival function and anonymous-engine version, and the runtime: numpy
  version, Python version, and the bit generator `default_rng` builds (PCG64 in the verified
  runtime). The run records the seed, `root_entropy`, the seed scheme, and the same runtime.

## Reproducibility claim and its limits

- **VERIFIED (this runtime: numpy 2.4.6, Python 3.13.13, Windows 11, PCG64):**
  - the same root entropy, index, scenario, roster, and policies reproduce the same full result;
  - a run's rows equal the rows of each replication regenerated alone;
  - a longer run shares its first rows with a shorter run of the same seed;
  - `seed=None` records entropy that reproduces the run;
  - the drawn pairs equal an independent recomputation with explicit
    `Generator(PCG64(SeedSequence(entropy, spawn_key=(i, j))))` streams, j = 0 for gaps and 1 for
    work.
- **UNKNOWN:** equality of streams across numpy versions. The pins conflict, and it has not been
  tested:
  - `requirements.txt` allows `>=1.24.0,<2.3`, and CI installs from it;
  - `requirements-lock.txt` pins 2.4.6, the local runtime;
  - `requirements-production.lock` pins 2.2.6, the Docker image.

  The supported claim is reproducibility under the recorded numpy version and bit generator. No
  test compares a seeded value with a stored golden value.

## Interface

```python
replication_seed_sequence(root_entropy, replication_index) -> SeedSequence

simulate_named_replication(
    horizon, demand_periods, employees, rules, roster, *,
    seed_sequence, closing_policy, employee_policy, required_staffing, max_trace_events=None,
) -> dict   # the unchanged 5B-4.3 result plus a "replication" block

named_replication_row(result, replication_index) -> dict

run_named_replications(
    horizon, demand_periods, employees, rules, roster, *,
    replications, seed, closing_policy, employee_policy, required_staffing,
) -> {"replications": rows, "summary": ..., "provenance": ...}

aggregate_named_replications(rows) -> dict
```

- **Required inputs, no defaults:** `replications` (1 to `config.MC_MAX_TRIALS`), `seed` (a whole
  number of 0 or more, or None), `closing_policy`, `employee_policy`, and `required_staffing`.
  - X7 is checked before any draw.
  - The named engine validates the policies, the roster (X4), and the arrivals, as in 5B-4.3.
- **Preserving the 5B-4.3 result.** `simulate_named_replication` adds one key, `replication`, to the
  5B-4.3 result. Without that key, the result equals `simulate_named_prescribed` on the same draws
  (`test_a_selected_replication_is_regenerated_alone`).
- **Rows.** `run_named_replications` keeps one scalar row per replication (traces off). There are no
  events, customer rows, or timelines. Replication i is regenerated in full with
  `simulate_named_replication(..., seed_sequence=replication_seed_sequence(root_entropy, i))`. This
  is the INFERRED reading of "each replication must preserve the Phase 5B-4.3 result": it follows
  the Phase 4 convention of scalar rows plus regeneration, so memory does not grow with full results
  of up to `MC_MAX_TRIALS` replications.

## Row contents (all read from the 5B-4.3 result; nothing new is modeled)

- **Identity:** `replication_index`, `spawn_key`, `customer_inputs_sha256`, `customer_conservation`.
- **`customers`:** arrivals, served, unserved, unserved by reason (`hard_cutoff`,
  `no_eligible_employee`), and served after closing.
- **`waiting`:** the sum of served waits and the engine's mean wait (None when nobody was served);
  the waiting customer-hours in the horizon, after closing, and in total; the maximum line in the
  horizon.
- **`closing`:** waiting and in service at closing, the DRAIN crew size, and `run_after_closing_hours`
  (the run's finish minus closing).
- **`staffing`:** the P8 windows, by kind:
  - `horizon`;
  - `segments` by segment id;
  - `after_closing` (always);
  - `before_opening` (when a shift starts before opening).

  Every window has duration, scheduled_active, accepting_capacity, busy_employee,
  register_occupancy, and waiting_for_register hours. Only the horizon and segment windows add
  required hours and the shortfall and excess of both gaps (rule 5).
- **`employees`:** from the employee timeline:
  - employee-hours by base state, over the whole timeline and after closing;
  - shifts scheduled, activated, and not activated; shifts with overrun; overrun total and maximum;
    activation delay total;
  - breaks scheduled, started, completed, truncated, and unfulfilled, with unfulfilled counts by
    cause (`released`, `shift_not_activated`, `cancelled_at_closing`; an unknown cause raises);
  - break delay total and maximum over started breaks;
  - the number of transitions.

  A maximum over an empty set is None.
- **No cost.** No pay, rate, or cost field exists (5B-5).

## Aggregation (descriptive only)

- **Every scalar:** `shared_replications.summarize_metric`, the Phase 4 convention, VERIFIED against
  scipy in its own tests. It gives the mean, the sample SD, the SE, a two-sided Student-t interval at
  `MC_CONFIDENCE_LEVEL`, the minimum and maximum, `n`, and `n_undefined`. None is counted, never
  zero-filled. With n < 2 there is no dispersion.
- **Customers:** totals over all replications, `conserved_in_every_replication`, and per-replication
  statistics.
- **Waiting time:** the mean of replication means (undefined replications counted in
  `n_undefined`), and the customer-weighted mean with its numerator (wait hours) and denominator
  (served customers). No interval is computed for the customer-weighted mean.
- **Outcome counts:** descriptive frequencies with an explicit `denominator_replications`, which is
  every replication. They count replications with unserved customers, with service after closing,
  with a shift overrun, and with unfulfilled breaks. They are not failure rates.
- **`verdict: None`**, with the reason: no approved acceptance rule exists. The legacy 0.75
  utilization rule is not applied, and no employee-level threshold is defined. No failure criteria
  are accepted.

## Verification

### Required points and their tests (`tests/test_shared_named_replications.py` unless named)

| # | Requirement | Evidence |
|---|---|---|
| 1 | Same seed, identity, scenario, and roster reproduce the same result | `test_same_identity_reproduces_the_same_result` (full results, both policies; whole runs; prefix sharing), `test_seed_none_records_entropy_that_reproduces_the_run` |
| 2 | Distinct identities give distinct child streams | `test_distinct_replication_identities_give_distinct_streams` (60 indices, distinct digests and first arrivals), `test_replication_seed_is_the_phase_4_child` |
| 3 | The same identity across rosters gives identical customer inputs | `test_common_random_numbers_across_rosters` (digests of 8 replications; regenerated customers equal across two rosters and the anonymous engine) |
| 4 | Employee transitions consume no random numbers | `test_employee_transitions_consume_no_random_numbers` (every draw counted through a wrapped `default_rng`: exactly two streams keyed (i, 0) and (i, 1), arrivals + 1 gap draws and one work draw, identical across three rosters and both policies); `test_the_named_engine_runs_with_every_random_source_disabled`; `test_global_random_states_are_untouched`; the static import tests of both engine modules |
| 5 | Named and anonymous engines get identical customers | `test_customers_are_the_anonymous_draws_and_match_an_independent_recomputation` (explicit PCG64 streams, not the engine); `test_seeded_reduction_to_the_anonymous_engine` (2 rosters x 2 policies x 8 replications: every compared customer field identical) |
| 6 | Customer conservation in every replication | `check_named` and `check_row` in `test_invariants_hold_in_every_replication` (10 scenarios x 2 policies x 6 replications) |
| 7 | Register and employee invariants in every replication | `check_named`, which runs `check_invariants(..., exact=False)` (register occupancy <= K, time partition, breaks, shifts, transition replay) on every replication above |
| 8 | DRAIN and HARD_CUTOFF unchanged | `check_named` closing checks on every replication; `test_closing_policies_on_an_overloaded_day` (releases recomputed from the service under way); the seeded reduction; the 5B-4.3 prescribed tests |
| 9 | Exact-close break rules | prescribed: `test_break_due_service_completing_exactly_at_closing_cancels_the_break`, `test_break_ending_exactly_at_closing_is_truncated_by_closing` (`tests/test_shared_named_des.py`), `test_break_due_completion_at_closing_with_cancel_starts_no_break` (`tests/test_shared_employee_states.py`); seeded: `test_break_scheduled_to_end_at_closing` and the `check_named` break checks |
| 10, 11 | Gaps scoped to the horizon; no post-close requirement gap | `check_named` on every step and window; `test_staffing_gaps_are_calculated_only_inside_the_operating_horizon` (prescribed, hand values); `test_staffing_gaps_stay_inside_the_operating_horizon` (seeded) |
| 12 | A regenerated replication matches its stored row | `test_a_selected_replication_is_regenerated_alone` (both policies; also equal to the prescribed engine on independently recomputed draws); every replication in `test_invariants_hold_in_every_replication` |

`check_row` recomputes every row field from the full result's customers, intervals, shifts, and
breaks, including the input digest from `float.hex()`.

The required cases each have a test:

- zero arrivals;
- an ordinary stable day and an overloaded day;
- a delayed break, where the break start is recomputed from the service under way;
- shift overrun and register contention, where the release and the wait for a register are
  recomputed;
- DRAIN and HARD_CUTOFF;
- no eligible DRAIN employee, and nobody on duty;
- completion at closing with a break due (prescribed);
- a break ending exactly at closing (prescribed and seeded);
- multiple replications and aggregation (`scipy.stats.t.interval`);
- reproduction of a selected replication;
- common random numbers across two rosters.

Coverage of the seeded branches in this runtime (scratch probe; these are counts, not assertions):

- 8 of 8 delayed breaks;
- 13 breaks ending at closing on time and 7 delayed, all truncated;
- a wait for a register in 8 of 8 replications;
- `no_eligible_employee` in 8 of 8;
- 12 delayed split-shift activations.

A break still pending when the service runs past closing did not occur in these seeds. The
prescribed tests cover it. The few coverage assertions ("at least one replication shows...") rely on
probabilities stated in the tests, not on stored values.

### Fault injection

A scratch script, not committed, applied 41 source-level mutants to a copy of `backend/` and
`tests/`, so the working tree was never touched. It then ran the 5B-4.4, 5B-4.3, 5B-4.2, and pin
tests on the copy. The mutants covered:

- seeds and streams: shifted spawn key, a reused seed, off-by-one indices, the digest, the wrapper's
  checks, an extra roster-dependent draw;
- the X7 check;
- every row block;
- aggregation: numerator, denominators, zero-filling, an invented verdict;
- run validation;
- rules 1, 2, 3, and 5 in both modules.

- **First run: 38 of 41 killed.** The survivors:
  - "overrun max over all shifts": no scenario had a replication with no activated shift. Added the
    `nobody_on_duty` scenario and `test_nobody_on_duty_leaves_every_customer_unserved_and_maxima_undefined`.
  - "unknown causes ignored": the guard was never exercised. Added
    `test_an_unknown_unfulfilled_cause_is_rejected_not_dropped`.
  - "rule 1 cancel at any instant": an equivalent mutant. Outside the closing instant, a
    `CancelPendingBreaks` input already makes `process` raise ("only at or after closing" before
    closing, "only at closing" after it), so the mutant changes only a path that raises anyway.
- **Final text: 40 of 41 killed.** Only the equivalent mutant survives. A scratch probe ran it and
  the original on a SERVING_BREAK_DUE completion with `CancelPendingBreaks` at 3.9 h and at 4.5 h.
  Both raised the same `EmployeeTimelineError` with the same message in both cases.
- No test was weakened.

### Gates (executed)

- Named DES, state machine, and pin: 110 passed after the rule changes (baseline 106).
- `tests/test_shared_named_replications.py`: 73 passed (33 test functions).
- All `tests/test_shared_*.py`: 691 passed.
- Separate Queue: all 20 files (`separate`, `queue_lifecycle`, `routing` in the name), 182 passed.
  The five files the policy spec names, with the isolation test and the pin: 102 passed.
- Full backend suite, `python -m pytest tests/ -x --tb=short`: 1724 passed, 3 skipped, 1 xfailed
  (baseline 1647 + 73 + 3 + 1).
- `ruff check .`: clean. `mypy . --exclude '^outputs/'`: clean on 174 files. Plain `mypy .`: the 5
  known errors in the gitignored `outputs/technical-paper/build_chapters_4_5.py` only.
- Frontend: not run; nothing under `frontend/` changed.

## Undetermined (UNKNOWN or INFERRED)

1. **Cross-version stream equality** (numpy 2.2.6, 2.4.6, and the CI range below 2.3): UNKNOWN,
   not tested.
2. **"Preserve the 5B-4.3 result" as scalar rows plus regeneration** (see "Interface"): INFERRED.
3. **A paired comparison output for two rosters under common random numbers** is not implemented.
   Common random numbers are provided and verified; per-replication differences are left to the
   caller. PROPOSED only, if wanted.
4. **Rule 1 on seeded runs.** A completion exactly at closing has probability zero with continuous
   draws, so the rule is exercised by prescribed tests only. Seeded runs check that no break starts
   at or after closing.
5. **The acceptance rule:** UNKNOWN. No PASS/FAIL rule is approved.
6. **Carried over from 5B-4.3:** the DRAIN release order and the before-opening window shape
   (INFERRED).

## Out of scope and next steps

Named playback (5B-4.5), attribution reporting (5B-4.6), workforce cost (5B-5), an acceptance rule,
and API or UI exposure are not started. None may begin without explicit approval.
