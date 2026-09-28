# Shared Queue Enhancement: Phase 5B-4.2, Pure Named-Employee State Machine

Date: 2026-09-28. Status: implemented as `backend/queueing_engine/simulation/shared_employee_states.py`,
with tests in `tests/test_shared_employee_states.py`. Committed locally only; not pushed, merged,
or deployed.

Amended in Phase 5B-4.3 (2026-09-28): the approved P3 rule for breaks of a delayed split shift,
whole-minute arithmetic for roster-derived instants, and a `snapshot()` accessor. See "Phase 5B-4.3
amendments"; statements below that the amendments changed are marked.

Plan: `docs/superpowers/plans/2026-09-28-shared-queue-employee-state-machine-plan.md`.
Policy contract: `2026-09-28-shared-queue-named-employee-des-policy.md` (P1-P9 and X1-X7, approved
2026-09-28, with the explicit decisions of the Phase 5B-4.2 request).

## Scope

- **In scope:** the employee, break, shift, and register timeline of one validated Phase 5B-1
  roster.
- **Not in scope:**
  - customers, a queue, arrivals, or service-time generation;
  - random numbers or Monte Carlo;
  - the named-employee DES (added in Phase 5B-4.3 as `shared_named_des.py`, with its own spec);
  - workforce cost, playback, API, database, frontend, Decision, and Reports.
- **Service starts and completions are caller inputs.** `ServiceStart` and `ServiceCompletion`
  say that a service starts or completes at a given instant. The module never invents a service
  duration. Tests choose these instants by hand to reach each transition; they are synthetic, not
  estimates.
- **Isolation.**
  - No existing production module changed.
  - The only existing test touched is `tests/test_shared_segments.py`. It adds the new module to
    `SHARED_QUEUE_ENHANCEMENT_MODULES`, so the existing isolation test also checks that nothing
    legacy imports it.
  - The module imports only the standard library, `services/shared_segments.py`
    (`OperatingHorizon`, `SharedSegmentError`), and `services/shared_workforce.py`.
    `test_no_customer_randomness_or_separate_queue_code` pins that import set.
  - It uses none of the separate-queue break code (`PRE_BREAK_CUTOFF_MINUTES`, `queue_lifecycle`,
    or the `separate_optimization` break controller). Its event names carry an `employee_`
    prefix.

## Inputs

- `EmployeeTimeline(horizon, employees, rules, roster, *, hold_past_shift_end)` and
  `run_timeline(horizon, employees, rules, roster, inputs, *, hold_past_shift_end, finish)`.
- **X4 roster precondition.** The roster is checked by 5B-1 `evaluate_roster`.
  - An INVALID roster is rejected with `SharedSegmentError` ("The roster is INVALID (X4): ...").
  - An INCOMPLETE roster is accepted only when every missing entry is a pay field
    (`regular_rate_per_hour`, `overtime_rate_per_hour`, `daily_regular_paid_minutes`). Otherwise
    it is rejected ("INCOMPLETE beyond pay fields (X4): ...").
  - Test: `test_roster_precondition_x4`.
- **`hold_past_shift_end` is required, with no default.** It must be `True` or `False`.
  - Omitting it is a `TypeError`.
  - Any other value raises `EmployeeTimelineError` ("there is no default").
  - Test: `test_hold_past_shift_end_has_no_default`.
- **Timeline inputs** are frozen dataclasses `(time, employee_id)`, with time in hours from the
  horizon start:

  | Input | When it may apply | Meaning |
  |---|---|---|
  | `ServiceStart` | any instant, after that instant's events (the assignment pass) | An AVAILABLE employee starts a service. |
  | `ServiceCompletion` | any instant | The employee's service under way completes. |
  | `Release` | at or after closing | The employee's duty ends for the rest of the run. |
  | `EndBreakAtClosing` | at closing only | The employee's break in progress ends now. |
  | `CancelPendingBreaks` | at closing only | The employee's breaks not yet started are not taken. |

- **Rejected inputs** raise `EmployeeTimelineError` (test `test_rejected_inputs`):
  - a service start by an employee who is not AVAILABLE;
  - a completion with no service under way;
  - a closing input before closing;
  - `EndBreakAtClosing` or `CancelPendingBreaks` after closing;
  - `EndBreakAtClosing` for an employee not on a break;
  - a repeated `Release`;
  - an unknown employee;
  - an input after `finish`;
  - an instant that is not after the last processed instant, or that skips a scheduled instant;
  - a `start_service` call that does not follow `process` at the same instant;
  - a `result` call while any employee is still on duty or a scheduled instant is unprocessed.
- **X7 does not apply here.** X7 requires `required_staffing` as an input to the named DES. This
  state machine is not the DES and makes no coverage comparison, so it takes no staffing segments.
  The 5B-4.3 engine must take them as X7 requires.

## Time

- **Units.** Roster minute m becomes `(m - horizon.start_minute) / 60` hours. This is the
  anonymous engine's `shared_continuous_des._hours`, and
  `test_time_conversion_is_the_anonymous_engines` checks that the two agree on 11 minutes.
  Integer-minute inputs are never rounded.
- **Begin.** The timeline begins at the earlier of 0 (the horizon start) and the earliest
  scheduled shift start (X3). Test: `test_pre_opening_shift_and_exact_partition`, which begins
  at -1.0 h.
- **Closing** is the horizon end. The caller sets **finish**, which must be at or after closing
  and after the last processed instant.
- **Numerical representation.**
  - Tests use binary-exact times: roster minutes are multiples of 15, and input times multiples
    of 1/8 h. On those, the partition sums and durations are compared with exact equality.
  - A scratch probe (not committed) used a 5-minute grid and 10-minute breaks. The partition sum
    was exact in that run, but `actual_end - actual_start` of a break was 0.16666666666666674
    against 10/60 = 0.16666666666666666.
    - The module computes a break's end as `actual_start + duration`, so its own timeline is
      consistent.
    - A consumer that recovers a duration by subtraction can see a difference at the last
      binary digit.
    - This is floating-point rounding, not a semantic difference (INFERRED).
    - Tolerances for non-dyadic inputs are NOT TESTED. The anonymous engine uses the same float
      hours.
  - **Amended in 5B-4.3.** Adding minutes in hours could also miss a roster boundary by one unit
    in the last place, which is a semantic difference (a sliver of AVAILABLE time, or a tiny
    overrun or activation delay). Roster-derived instants are now computed in whole minutes; see
    "Phase 5B-4.3 amendments".

## State representation

Each employee is in exactly one base state at every instant:

| State | Register | Meaning |
|---|---|---|
| `OFF` | no | Not on duty: before a shift, between split shifts, or after release. |
| `WAITING_FOR_REGISTER` | no | On duty, not on a break, and waiting for a free register (P4). |
| `AVAILABLE` | yes | At a register and idle; may start a service. |
| `SERVING` | yes | At a register and serving. |
| `SERVING_BREAK_DUE` | yes | Serving; a break is due and starts at the completion (no pre-break cutoff). |
| `SERVING_SHIFT_ENDED` | yes | Serving the last service before release; released at the completion. |
| `ON_BREAK` | no | On a break. |

- **`SERVING_SHIFT_ENDED` covers two causes of a due release:**
  - the scheduled shift end passed (P3);
  - a `Release` input was applied after closing.

  The shift's `release_basis` (`scheduled_shift_end` or `release_input`) records which. The
  policy spec's state table names only the shift-end cause. Using the same state for a
  closing-input release is how this module represents the P5 and P6 alternatives, and it adds no
  new elapsed-time state.
- **Register states** are AVAILABLE and the three SERVING states. A register state holds exactly
  one register id, from 1 to K; every other state holds none.
- **Attributes.** Each interval carries `after_closing` (it starts at or after closing) and
  `past_scheduled_end` (on duty at or after the current shift's scheduled end).
  - They split intervals but never add elapsed time (P9 decision of 2026-09-28).
  - A minute that is both past the scheduled end and after closing is one minute of its base
    state, carrying both attributes.
- **Break outcomes** (terminal): `completed`, `truncated_by_closing`, `unfulfilled`.
- **Causes of an unfulfilled break:**
  - `released`: still pending when the employee was released;
  - `cancelled_at_closing`: removed by `CancelPendingBreaks`;
  - `shift_not_activated`: the break's shift was never worked.

## Same-time order

At one instant the stages run in this order:

1. completions;
2. closing;
3. closing inputs;
4. shift ends;
5. break ends;
6. breaks due;
7. shift starts;
8. register handover;
9. service starts.

- **Sources.**
  - Completions through the register handover are X2's employee-only order, with arrivals left
    out because there are no customers.
  - The caller's service starts are X2's single assignment pass.
  - X2 does not place closing. Closing right after completions follows the Phase 3A order
    ("completions at closing first, then the recorded state at close"). It is the only placement
    that keeps P5 (a) representable. This is INFERRED and listed as undetermined. (Amended in
    5B-4.3: the approved X2 order places the closing boundary second, after completions, which is
    this placement.)
  - Closing inputs follow closing, in their given order.
- **Within a stage.**
  - Completions, shift ends, break ends, breaks due, and shift starts are taken in employee_id
    order.
  - This order only fixes the order of the recorded transitions; it does not change the timeline
    (INFERRED from code). A transition in these stages depends only on that employee's own state,
    and registers are assigned only in the handover stage.
  - Tests: `test_same_time_order_x2` (every stage at one instant) and
    `test_same_stage_events_follow_employee_id` (inputs given in reverse id order).

## Transitions

| Stage | From | To | Register | Event |
|---|---|---|---|---|
| completion | SERVING | AVAILABLE | kept | `employee_service_completion` |
| completion | SERVING_BREAK_DUE | ON_BREAK (the break starts now) | freed | `employee_break_start` |
| completion | SERVING_SHIFT_ENDED | OFF (released) | freed | `employee_service_completion` |
| closing | any | unchanged; the open interval is split and `after_closing` begins | unchanged | none |
| closing input `Release` | AVAILABLE, WAITING_FOR_REGISTER | OFF | freed | `employee_release_input` |
| closing input `Release` | SERVING, SERVING_BREAK_DUE | SERVING_SHIFT_ENDED | kept | `employee_release_input` |
| closing input `Release` | SERVING_SHIFT_ENDED, ON_BREAK | unchanged; OFF at the completion or the break end | unchanged | none |
| closing input `Release` | OFF (between or before shifts) | unchanged; later shifts not activated (`released_after_closing`) | none | none |
| closing input `EndBreakAtClosing` | ON_BREAK | break `truncated_by_closing`; then OFF if a release is due, else WAITING_FOR_REGISTER | none | `employee_break_truncated_at_closing` |
| closing input `CancelPendingBreaks` | any | unstarted breaks of the current and later shifts become unfulfilled; SERVING_BREAK_DUE becomes SERVING | unchanged | `employee_breaks_cancelled_at_closing` (state change only) |
| shift end | AVAILABLE, WAITING_FOR_REGISTER | OFF (released) | freed | `employee_shift_end` |
| shift end | SERVING, SERVING_BREAK_DUE | SERVING_SHIFT_ENDED | kept | `employee_shift_end` |
| shift end | ON_BREAK | unchanged; OFF at the break end | none | none |
| break end | ON_BREAK | break `completed`; then OFF if a release is due, else WAITING_FOR_REGISTER | none | `employee_break_end` |
| break due | AVAILABLE, WAITING_FOR_REGISTER | ON_BREAK | freed | `employee_break_start` |
| break due | SERVING | SERVING_BREAK_DUE | kept | `employee_break_due_while_serving` |
| shift start | OFF | ON_BREAK if a break falls due at this instant, else WAITING_FOR_REGISTER | none | `employee_break_start_at_shift_start` or `employee_shift_start` |
| register handover | WAITING_FOR_REGISTER | AVAILABLE | assigned | `employee_register_assigned` |
| service start (caller) | AVAILABLE | SERVING | kept | `employee_service_start` |

- **Shift end under hold.** A shift end at or after closing with `hold_past_shift_end=True`
  changes no state. The employee stays on duty, marked `past_scheduled_end`, until a `Release`
  input. Before closing, the flag has no effect (`test_hold_applies_only_from_closing`).
- **Shift end with a release already due.** If a release is already due (a `Release` at closing
  before a shift end at closing), the shift end changes nothing.
- **Zero-length waits.** A shift start or break end that finds a free register passes through
  WAITING_FOR_REGISTER for zero time.
  - The transitions record both steps.
  - No interval is recorded for the zero-length wait, so the elapsed time equals the policy
    spec's "becomes AVAILABLE if a register is free".
- **Breaks and a due release.** No break falls due while a release is due. A break still pending
  at release becomes unfulfilled (`released`).
- **Transition records.** Each transition is recorded as `{t, stage, employee_id, from_state,
  to_state, register_before, register_after, event}`.

### Breaks (P1, P2, P3 decisions of 2026-09-28)

- **When a break falls due.** A shift's first break falls due at its scheduled start. Break k
  falls due at `max(scheduled start of k, actual end of k-1 + min_gap_minutes / 60)`. A break
  cannot fall due before the previous one has ended. (Amended in 5B-4.3: "scheduled start" is
  now the planned due time, `actual shift start + (planned break start - planned shift start)`,
  which equals the scheduled start for a shift that starts on time.)
- **Starting.** A due break starts at once unless the employee is serving. A serving employee
  becomes SERVING_BREAK_DUE and starts the break at the completion. There is no pre-break cutoff.
- **Duration.** The break lasts its full configured duration from its actual start
  (`actual_end = actual_start + duration`), even when that runs past the shift end.
- **Recorded fields.** Each break records `due`, `actual_start`, `actual_end`, and
  `delay = actual_start - scheduled_start`.

### Shifts (P3 and the split-shift decision of 2026-09-28)

- **Activation.** A later split shift activates at
  `max(scheduled start, actual release of the previous shift + min_minutes_between_shifts / 60)`.
- **Scheduled end.** The scheduled end does not move.
- **Overrun.** Each shift records `overrun = max(0, release - scheduled_end)`.
- **Activation delay.** Each shift records `activation_delay = actual_start - scheduled_start`.
- **Not activated.** If the delayed activation is at or after the scheduled end, the shift is not
  activated.
  - Its reason is `rest_after_actual_release_reaches_scheduled_end`.
  - Its breaks are unfulfilled (`shift_not_activated`).
  - This reading is INFERRED. (Amended in 5B-4.3: approved by the P3 decision.)
- **Undetermined split-shift break.** If a delayed activation passes a break's scheduled start,
  the outcome is UNKNOWN, and the module raises `UndeterminedPolicyError` instead of choosing
  (`test_split_shift_break_before_delayed_activation_is_undetermined`). (Amended in 5B-4.3: the
  approved P3 rule decides this case; the branch and the test are replaced.)

### Registers (P4)

- **Identity and capacity.** Registers are numbered 1..K, and the holder map never has more than
  K entries.
- **Order.** At the handover stage, the free registers, in ascending order, are paired with the
  waiting employees sorted by earliest wait start, then employee_id.
- **Wait start.** An employee's wait start is the instant they entered WAITING_FOR_REGISTER.

## Representing P5, P6, and P7 without selecting

The P5, P6, and P7 selections are UNKNOWN. The state machine represents each alternative with the
hold flag and the closing inputs; it does not choose one. A 5B-4.3 engine would generate these
inputs from the selected policy.

| Alternative | Representation | Test |
|---|---|---|
| P5 (a): accepting just before closing, including a shift ending exactly at closing; no cap | `hold_past_shift_end=True`; `Release` at closing for those not accepting just before closing; later `Release` inputs end duty | `test_drain_crew_a_accepting_before_closing` ({A, B}) |
| P5 (b): only employees whose shift runs past closing | `hold_past_shift_end=False` (a shift ending at closing releases the employee after the service) | `test_drain_crew_b_shift_runs_past_closing` ({A, C, D}) |
| P5 (c): (a) plus employees returning from a break or starting after closing | `hold_past_shift_end=True`, no `Release` at closing | `test_drain_crew_c_includes_returning_and_late_starters` ({A, B, C, D}; D waits 4.25-4.5 h for a register) |
| P5: serve until the line is empty versus leave at the shift end | `hold_past_shift_end=True` with later `Release` inputs versus `False` | the three DRAIN tests |
| P6: released at the last service completion | `Release` at closing (idle: OFF now; serving: OFF at the completion; on a break: OFF at the break end) | `test_hard_cutoff_released_at_last_completion`, `test_hard_cutoff_break_taken_then_released` |
| P6: released at the scheduled shift end | `hold_past_shift_end=False`, no `Release` | `test_hard_cutoff_released_at_scheduled_end_with_pending_break` |
| P6: a break pending at closing still happens, or not | no input, or `CancelPendingBreaks` at closing | `test_hard_cutoff_released_at_scheduled_end_with_pending_break`, `test_hard_cutoff_pending_break_cancelled_at_closing` |
| P7: finish the break, then rejoin | no input | `test_break_at_closing_default_finishes_and_rejoins` |
| P7: end the break at closing | `EndBreakAtClosing` (outcome `truncated_by_closing`) | `test_break_at_closing_ended_at_closing` |
| P7: ineligible after closing | `Release` at closing (the break keeps its full duration, then OFF), or `EndBreakAtClosing` then `Release` (OFF at closing) | `test_break_at_closing_then_ineligible` |

"Accepting after closing" in these tests means the set of employees with an AVAILABLE or SERVING
interval flagged `after_closing`. That is the P8 "accepting" count; P8 still has to select which
count is reported.

## Output

`result(finish)` returns:

- `begin`, `finish`, `closing_time`, `hold_past_shift_end`, and `register_count`.
- **`intervals`:** `{employee_id, start, end, state, register_id, shift_index, after_closing,
  past_scheduled_end}`, which partition `[begin, finish)` for each employee.
- **`transitions`:** as described above.
- **`shifts`:** `{employee_id, shift_index, scheduled_start, scheduled_end, activated,
  actual_start, activation_delay, release, release_trigger, release_basis, overrun,
  not_activated_reason}`.
- **`breaks`:** `{employee_id, shift_index, name, paid, duration_minutes, scheduled_start, due,
  actual_start, actual_end, delay, outcome, unfulfilled_cause}`.
- **`state_totals`:** hours per base state per employee.
- **`definitions`, `undetermined`, and `provenance`:** `state_machine_version`
  `novaq-shared-employee-states-v1` (`-v2` from 5B-4.3), and the scope statement.

No cost, wage, or coverage quantity is computed.

## Invariants and their evidence

- **The independent checker.** `check_invariants` in the test module runs on every successful
  run in the file. It works only from the result, the rules, and the roster, and does not call
  the module's internals.
- **What "verified" means here.** Each invariant below is VERIFIED only on the synthetic cases
  in the test module. That is not a proof for every input.
- **The mutant column.** It names the scratch fault-injection mutants aimed at each invariant
  (see "Fault injection"). Every one was killed by the test module. The runner stops at the first
  failure and records only killed or survived, so which assertion killed a mutant is not
  recorded.
- **Structural invariants.** Invariants 2 and 3 also hold by construction (INFERRED from code):
  an employee has one register field, and the register holder map is keyed by register. No
  mutant targets them directly.

| # | Invariant | Checker evidence | Hand-computed test evidence | Related mutants |
|---|---|---|---|---|
| 1 | One base state at any instant | intervals tile `[begin, finish)` with no gap or overlap, each in `BASE_STATES`; replayed transitions equal the intervals | every timeline test | interval not advanced; closing duplicates the open interval |
| 2 | One employee occupies at most one register | each interval holds one `register_id`, present exactly in register states and in 1..K; the transition chain checks `register_before` | `test_register_handover_order` | none dedicated |
| 3 | One register holds at most one employee | at every interval boundary, the registers held are distinct | `test_register_handover_order`, `test_delayed_break_no_register_wait_and_handover` | none dedicated |
| 4 | Register occupancy ≤ K | at every interval boundary, the number held is at most K | `test_drain_crew_c_includes_returning_and_late_starters` (D waits while K registers are held) | K + 1 registers |
| 5 | OFF and ON_BREAK hold no register | register present exactly in register states | `test_immediate_break`, `test_delayed_break_no_register_wait_and_handover` | register kept on a break |
| 6 | WAITING_FOR_REGISTER holds no register | as 5 | `test_delayed_break_no_register_wait_and_handover`, `test_register_handover_order` | none dedicated |
| 7 | A delayed break starts no earlier than its scheduled start | `scheduled_start ≤ due ≤ actual_start`; `delay = actual_start - scheduled_start` | `test_delayed_break_no_register_wait_and_handover`, `test_first_break_delay_pushes_the_second` | delay measured from due (the recorded delay only) |
| 8 | A delayed break receives its full configured duration | completed: `actual_end - actual_start` equals the duration exactly; truncated only at closing, strictly inside the break | `test_first_break_delay_pushes_the_second`, `test_break_in_progress_at_shift_end_keeps_its_full_duration` | delayed break truncated; on-break employee released at the shift end |
| 9 | No two actual breaks of one employee overlap | taken breaks sorted, each ends before the next starts; ON_BREAK time equals the taken break time | `test_first_break_delay_pushes_the_second` | none dedicated |
| 10 | Required minimum gaps between sequential breaks are respected | a later break starts at or after the earlier actual end plus the rule's gap | `test_first_break_delay_pushes_the_second` (second due at 2.75, not 2.5) | gap ignored; gap measured from the previous break's scheduled end |
| 11 | Shift overrun is recorded without a second simultaneous shift | a shift's intervals merge to exactly `[actual_start, release)`; `overrun = max(0, release - scheduled_end)` | `test_split_shift_overrun_delays_the_next_shift`, `test_shift_end_while_serving` | overrun not clamped; shift end preempts the service |
| 12 | Split-shift rest is measured from the actual release | `actual_start = max(scheduled_start, previous release + rest)` | `test_split_shift_overrun_delays_the_next_shift` (2.125, not 1.5) | rest from the scheduled end; no activation delay |
| 13 | Every scheduled break has an explicit terminal outcome | one break row per scheduled break, each outcome in `BREAK_OUTCOMES`; unfulfilled rows have a cause and no times; a non-activated shift's breaks are unfulfilled | `test_break_due_while_serving_is_unfulfilled_at_release`, `test_split_shift_not_activated_leaves_its_breaks_unfulfilled`, `test_hard_cutoff_pending_break_cancelled_at_closing`, `test_break_at_closing_ended_at_closing` | pending break not unfulfilled at release; truncated break recorded as completed |
| 14 | Elapsed time partitions exactly across the base states | `state_totals` equal the interval sums and sum to `finish - begin` exactly; attributes match their definitions | `test_pre_opening_shift_and_exact_partition`, `test_delayed_break_no_register_wait_and_handover` (totals by hand) | after_closing never set; past_scheduled_end never set; closing duplicates the open interval |
| 15 | Register handover follows the approved order | at each handover, the (employee, register) pairs equal the waiters sorted by (wait start, employee_id) zipped with the ascending free registers; nobody waits while a register is free | `test_register_handover_order` (Z before X although "X" < "Z") | wait order by employee_id only; wait order latest first; highest-numbered free register first |
| 16 | Same-time order follows X2 for employee-only events | the stages at each instant are in `STAGES` order; employee_id order within the completion, shift end, break end, break due, and shift start stages | `test_same_time_order_x2`, `test_same_stage_events_follow_employee_id`, `test_completion_at_the_shift_end_instant` | stage order: break end before shift end; closing after shift ends; employees in reverse id order within a stage; completions in reverse id order |

## Hand-computed cases

All data is SYNTHETIC. The horizon is 08:00-12:00, so closing is at 4.0 h. Each test's comments
give the derivation.

| Required case | Test(s) |
|---|---|
| normal shift start and end | `test_normal_shift_start_and_end` |
| no-register wait | `test_delayed_break_no_register_wait_and_handover` (B waits 1.0-1.125 h) |
| deterministic register handover | `test_register_handover_order` |
| immediate break | `test_immediate_break` |
| delayed full break | `test_delayed_break_no_register_wait_and_handover` (break 1.125-1.375 h) |
| two breaks where the first delay pushes the second | `test_first_break_delay_pushes_the_second` |
| unfulfilled break at release | `test_break_due_while_serving_is_unfulfilled_at_release` |
| split-shift overrun and delayed next shift | `test_split_shift_overrun_delays_the_next_shift` |
| shift end while serving | `test_shift_end_while_serving`, `test_completion_at_the_shift_end_instant` |
| break due while serving | `test_delayed_break_no_register_wait_and_handover`, `test_break_due_while_serving_is_unfulfilled_at_release` |
| break at closing | `test_break_at_closing_default_finishes_and_rejoins`, `test_break_at_closing_ended_at_closing`, `test_break_at_closing_then_ineligible` |
| HARD_CUTOFF release semantics | the four `test_hard_cutoff_*` tests |
| DRAIN crew eligibility | the three `test_drain_crew_*` tests |
| exact partitioning | `test_pre_opening_shift_and_exact_partition`, `test_delayed_break_no_register_wait_and_handover` |
| same-time ordering | `test_same_time_order_x2`, `test_same_stage_events_follow_employee_id` |

Additional cases:

- `test_split_shift_break_before_delayed_activation_is_undetermined`;
- `test_split_shift_that_cannot_start_before_its_end_is_not_activated`;
- `test_split_shift_not_activated_leaves_its_breaks_unfulfilled`;
- `test_hold_applies_only_from_closing`;
- `test_break_in_progress_at_shift_end_keeps_its_full_duration`;
- `test_gap_push_puts_the_employee_on_duty_in_scheduled_break_time`;
- the input, units, and isolation tests.

The test module has 33 test functions.

## Fault injection

- **Method.** A scratch script, not committed, applied 35 source-level mutants to a copy of the
  module. It loaded each copy in place of the module and ran the test module. A mutant is killed
  when a test fails; the unmutated copy passed.
- **First run: 32 of 35 killed.** Three survivors showed test gaps:
  - completions in reverse id order;
  - hold applied before closing;
  - the not-activated check moved after the undetermined check.
- **Tests added for the gaps.** Each closes one survivor:
  - `test_same_stage_events_follow_employee_id`;
  - `test_hold_applies_only_from_closing`;
  - `test_split_shift_not_activated_leaves_its_breaks_unfulfilled`.

  No test was weakened.
- **After the added tests: 35 of 35 killed.**

## Findings

- **Discrepancy with the policy spec: the withdrawn bound.** The 5B-4.1 INFERRED bound "before
  closing, accepting servers never exceed the 5B-1 scheduled active count" is false under the
  2026-09-28 gap rule.
  - Counterexample: `test_gap_push_puts_the_employee_on_duty_in_scheduled_break_time`. One
    employee is AVAILABLE during 2.5-2.75 h, which 5B-1 schedules as that employee's second
    break, while the scheduled active count is 0.
  - The bound is struck through and withdrawn in the policy spec (the capacity list and
    invariant 7). Whether a weaker bound replaces it is UNKNOWN (P8).
- **Representation difference: `SERVING_SHIFT_ENDED`.** The state also covers a release due from
  a `Release` input after closing (see "State representation"). The policy spec's table names
  only the shift-end cause.
- **Representation difference: break end under hold.** The policy spec's break-end rule says an
  employee whose break ends at or after the shift end becomes OFF. With
  `hold_past_shift_end=True` after closing, the employee rejoins instead. This is the "serve
  regardless of shift end" alternative that P5 leaves open. Without hold, the rule holds as
  written.

## Phase 5B-4.3 amendments

1. **P3 split-shift break rule (approved 2026-09-28).** `_due_time` uses the planned due time
   `actual shift start + planned offset` for every break of the current shift; the gap push and
   the delay rules are unchanged. The `UndeterminedPolicyError` branch in `_after_release` is
   removed. A break whose planned due time is at or after the fixed shift end is unfulfilled
   (`released`), as for any break pending at release.
   - `test_split_shift_overrun_delays_the_next_shift`: the delayed shift's break moves from its
     scheduled 2.5 h to 2.125 + 1.0 = 3.125 h. This expectation changed because the approved rule
     changed.
   - `test_split_shift_break_before_delayed_activation_is_undetermined` is replaced by three
     hand-computed tests: `test_delayed_split_shift_break_keeps_its_planned_offset`,
     `test_delayed_split_shift_breaks_follow_ordinary_delay_and_gap_rules`, and
     `test_delayed_split_shift_break_due_at_its_fixed_end_is_unfulfilled`.
2. **Whole-minute arithmetic.** `_plus(t, minutes)` adds whole minutes in integers when `t` is the
   exact conversion of a roster minute, else in hours. It is used for break ends, gap pushes, rest
   after release, and the P3 offset.
   - Evidence and tests: `test_break_ending_at_the_shift_end_in_minutes_ends_there_exactly` and
     `test_split_shift_rest_ending_at_the_next_start_in_minutes_is_on_time`. Both fail against the
     dfa8fe75 module (run in scratch). They use 5-minute rosters and their own exact assertions,
     because `check_invariants` compares float sums exactly and so applies to binary-exact inputs
     only.
   - On binary-exact inputs, which every earlier test uses, the results are unchanged.
3. **`snapshot()`** returns each employee's state, register, and `current_break_end`
   (`test_snapshot_reports_state_register_and_break_end`).
4. **`UNDETERMINED`** keeps one entry: the machine selects no closing policy; the named DES applies
   the approved ones.

The test module has 38 test functions after these changes.

## Undetermined (UNKNOWN or INFERRED)

Items 1-3 below are settled by the Phase 5B-4.3 decisions (see "Phase 5B-4.3 amendments"), and
item 4 by the named DES, which applies the approved P5-P7 selections. The module's `UNDETERMINED`
list at 5B-4.2 recorded:

1. **A break due before a delayed split-shift activation.** Taking it at activation or leaving
   it unfulfilled is UNKNOWN; the module raises `UndeterminedPolicyError`.
2. **The place of closing within X2.** INFERRED, as above.
3. **The end of a delayed split shift.** It keeps its scheduled end, and the shift is not
   activated when the delayed activation reaches that end. INFERRED.
4. **The P5, P6, and P7 selections.** UNKNOWN; represented, not chosen.

Also open:

- whether within-stage employee_id order matters for any future customer-level quantity
  (INFERRED not to matter for the employee timeline);
- tolerances for non-dyadic inputs (NOT TESTED);
- X1, X5, X6, P8, and the P2 threshold (UNKNOWN; outside 5B-4.2).

## Out of scope

- Customer and queue integration (Phase 5B-4.3). It needs explicit approval and the open
  selections. (Done in 5B-4.3: `2026-09-28-shared-queue-named-des.md`.)
- Seeded replications, playback, attribution reporting, and workforce cost.
