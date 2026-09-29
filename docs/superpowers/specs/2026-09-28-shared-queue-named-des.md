# Shared Queue Enhancement: Phase 5B-4.3, Named-Employee Continuous Shared-Queue DES

Date: 2026-09-28. Status: implemented as `backend/queueing_engine/simulation/shared_named_des.py`,
with tests in `tests/test_shared_named_des.py`. Committed locally only; not pushed, merged, or
deployed.

Amended in Phase 5B-4.4 (2026-09-28): the approved closing, capacity, event-time, and staffing-gap
rules replace items 1-4 of "Undetermined" and change the P8 windows (engine version
`novaq-shared-named-des-v2`). See "Phase 5B-4.4 amendments"; statements below that the amendments
changed are marked.

Amended in Phase 5B-4.5 (2026-09-28): two trace-only changes, engine version
`novaq-shared-named-des-v3`. See "Phase 5B-4.5 amendments".

Plan: `docs/superpowers/plans/2026-09-28-shared-queue-named-des-plan.md`.
Policy contract: `2026-09-28-shared-queue-named-employee-des-policy.md`, updated with the decisions
below. Employee state machine: `2026-09-28-shared-queue-employee-state-machine.md`, amended in this
phase.

## Approved decisions used (Phase 5B-4.3 request, 2026-09-28)

The request states: "Use these rules exactly." Summarized, with the request's own terms:

| Item | Decision |
|---|---|
| P1 | A break delayed by service gets its full configured duration from its actual start. Later breaks cannot overlap it and are pushed by the minimum actual break gap. A break that cannot occur before final release is UNFULFILLED. |
| P2 | Record the actual break delay only. No hard delay threshold, no pre-break cutoff. |
| P3 | No pre-shift-end cutoff. An employee serving at the shift end finishes that customer, takes no new customer, then releases; the overrun is recorded. A later split shift waits for the actual release plus the required rest; its scheduled end stays fixed; activation at or after that end makes the shift missed. **New:** a break of a delayed split shift falls due at `actual_shift_start + (planned_break_start - planned_shift_start)`, then ordinary delay rules apply; if it cannot occur before the fixed shift end, it is UNFULFILLED. |
| P4 | Registers 1..K; never above K_phys; wait order earliest wait start, then employee_id; lowest-numbered free register first. |
| P5 (DRAIN) | The crew is frozen from employees accepting immediately before closing, including one whose shift ends exactly at closing. Excluded: on a break, pending a break or shift release, starting later, returning after closing. The crew serves until the admitted line is empty, regardless of shift end. |
| P6 (HARD_CUTOFF) | Arrivals stop; waiting customers become unserved; services under way finish; idle employees release at closing, busy ones after their completion; no service starts at or after closing. |
| P7 | A break in progress at closing is truncated at closing. A pending break that cannot occur is UNFULFILLED, `cancelled_at_closing`. Nobody returns from a break after closing to add DRAIN capacity. |
| P8 | Report scheduled_active, required_staffing, accepting_capacity, busy_employees, register_occupancy, and waiting_for_register separately, and `schedule_realization_gap = accepting_capacity - scheduled_active` and `requirement_gap = accepting_capacity - required_staffing` separately. No single staffing KPI. |
| P9 | Mutually exclusive base states; after-closing, past-shift-end, delay, and overrun are annotations that never double-count time. No monetary interpretation. |
| X1 | The AVAILABLE employee idle longest takes the next customer; ties by employee_id; never random. |
| X2 | Completions, closing boundary, shift ends, break ends, breaks due, shift starts, register handovers, arrivals, one FCFS assignment pass. |
| X3 | The opening state comes from the roster; no pre-opening customers. |
| X4 | Reject INVALID rosters; INCOMPLETE only when the missing data is purely monetary. |
| X5 | A minimal public wrapper or alias around the existing arrival generation, with no duplicated stochastic logic, and the 5B-4.0 pin unchanged if the anonymous module changes. |
| X6 | Under DRAIN, customers still waiting with an empty frozen crew are unserved, reason `no_eligible_employee`. |
| X7 | Required staffing segments are mandatory (no default, no empty list) and are the P8 reference. |

The request also sets a float safeguard: "Keep roster scheduling times in exact integer-minute
form wherever possible", no unsafe raw float equality for boundaries of stochastic times, "use the
repository's verified applicable tolerance", and no rounding of service durations.

## Scope

- **In scope:** customers from prescribed (arrival hour, unit work) pairs, one shared FCFS line,
  and named employees driven through the 5B-4.2 state machine.
- **Not in scope:** seeded replications, Monte Carlo, playback, workforce cost, API, database,
  frontend, Decision, and Reports.
- **Files.**
  - New: `backend/queueing_engine/simulation/shared_named_des.py`, `tests/test_shared_named_des.py`,
    this spec, and the plan.
  - Changed: `shared_employee_states.py` and its test (see "Changes to the 5B-4.2 state
    machine"); `tests/test_shared_segments.py` (the module joins
    `SHARED_QUEUE_ENHANCEMENT_MODULES`); the policy and state-machine specs; `handoff.md`;
    `memory.md`.
  - Not changed: `shared_continuous_des.py` (the anonymous engine) and every other production
    module. The named module imports only the closing-policy names `DRAIN`, `HARD_CUTOFF`, and
    `CLOSING_POLICIES` from the anonymous engine.
- **Isolation.** No separate-queue break code, no `random` or numpy import, and no separate-queue
  event name as a value (`test_no_random_numbers_and_no_separate_queue_code`).

## Changes to the 5B-4.2 state machine

1. **P3 split-shift break rule.** A break's planned due time is now `actual shift start +
   (planned break start - planned shift start)`. For a shift that starts on time this equals the
   break's scheduled start exactly (whole-minute arithmetic, item 2). The 5B-4.2
   `UndeterminedPolicyError` branch in `_after_release` is removed.
   - **Behavior change to an existing 5B-4.2 expectation.**
     `test_split_shift_overrun_delays_the_next_shift` expected the delayed shift's 10:30 break at
     its scheduled 2.5 h. Under the approved rule it falls due at 2.125 + 1.0 = 3.125 h. The
     expectation was changed to the hand-computed value because the approved rule changed, not to
     make a test pass.
   - `test_split_shift_break_before_delayed_activation_is_undetermined` is replaced by
     `test_delayed_split_shift_break_keeps_its_planned_offset` (break due 2.625 h),
     `test_delayed_split_shift_breaks_follow_ordinary_delay_and_gap_rules`, and
     `test_delayed_split_shift_break_due_at_its_fixed_end_is_unfulfilled`.
2. **Whole-minute arithmetic for roster-derived instants (float safeguard).** Break ends, gap
   pushes, rest after release, and the P3 offset add whole minutes to an instant. When that instant
   is itself a whole roster minute, the minutes are now added in integers and converted once
   (`_plus`); otherwise they are added in hours as before.
   - **Evidence of the hazard (VERIFIED by computation).** With a horizon starting at minute 480,
     `(s - 480) / 60 + d / 60 != (s + d - 480) / 60` for 2,487 of 11,520 (start minute, duration)
     pairs tried (start 0-1439, durations 5-60 minutes).
     - Example: a 10-minute break at 08:40 on a shift ending 08:50 ended one unit in the last place
       *before* the shift end, leaving an AVAILABLE sliver in which a customer could be assigned.
     - Example: at 09:10-09:20 it ended one unit *after*, recording an overrun of about 1e-16 h.
     - Example: rest from 08:35 to a split shift at 08:55 activated about 1.1e-16 h late.
   - **Tests.** `test_break_ending_at_the_shift_end_in_minutes_ends_there_exactly` and
     `test_split_shift_rest_ending_at_the_next_start_in_minutes_is_on_time` pass now and fail
     against the dfa8fe75 module (run in scratch).
   - For binary-exact inputs, which all earlier tests use, results are unchanged: those sums were
     already exact.
3. **`snapshot()` accessor.** A read-only view of each employee's state, register, and current
   break end (`current_break_end`), used for X1 and for the closing inputs.
4. **Documentation.** X2 now places closing (second), so the "closing within X2" INFERRED note is
   withdrawn. The P3 decisions settle the delayed shift's fixed end. `UNDETERMINED` keeps one entry
   (the machine selects no closing policy). `STATE_MACHINE_VERSION` is
   `novaq-shared-employee-states-v2`.
   - `UndeterminedPolicyError` stays in the module; the named DES raises it for one case (see
     "Undetermined").

All 38 state-machine tests pass (33 before, less the replaced one, plus 6 new).

## Interface

```python
simulate_named_prescribed(
    horizon, demand_periods, employees, rules, roster, arrivals, *,
    closing_policy, employee_policy, required_staffing, max_trace_events=None,
)
```

- **`closing_policy`:** `DRAIN` or `HARD_CUTOFF`, the anonymous engine's names; no default.
- **`employee_policy`:** an `EmployeeDesPolicy`, every field required. Each field has exactly one
  approved value, collected in `APPROVED_EMPLOYEE_POLICY`: `drain_crew`, `drain_duration` (P5),
  `hard_cutoff_release` (P6), `breaks_at_closing` (P7), `break_delay` (P2), and `employee_choice`
  (X1). Any other value is rejected, not simulated.
- **`required_staffing` (X7):** a non-empty list of `StaffingSegment`, no default. It is validated
  with `validate_timeline(horizon, demand_periods, required_staffing)`, so segments tile the
  horizon and nest in demand periods. Its counts never set capacity; they are the P8 reference and
  label each customer's `arrival_segment_id`.
- **Roster (X4):** checked by the state machine (`evaluate_roster`); INVALID, or INCOMPLETE beyond
  pay fields, is rejected.
- **Arrivals:** a list of (hour, work) pairs with the anonymous engine's checks: `0 <= hour <
  closing`, non-decreasing, work finite and above 0, and no arrival in a period whose arrival rate
  is 0.
- **Not implemented:** `simulate_named_replication` (5B-4.4). X5 is therefore not exercised, and no
  public alias was added to the anonymous module. (Amended in 5B-4.4: implemented in
  `shared_named_replications.py`, with the X5 wrapper `shared_continuous_des.draw_arrivals`.)

## Time

- Hours from the horizon start, the anonymous engine's conversion
  (`test_time_conversion_is_the_anonymous_engines`).
- Service: non-preemptive; `duration = unit_work / mu(start)`, with `mu` the service rate of the
  demand period containing the start, and the final period's rate at or after closing. This is the
  anonymous engine's formula. Durations are never rounded.
- **Tolerance.** The repository has no verified event-time tolerance (VERIFIED by search):
  - `utilization.THRESHOLD_TOLERANCE` (1e-9) is for utilization threshold bands and rho = 1;
  - `shared_playback._TOLERANCE` is for playback consistency checks;
  - the legacy `simulation.py` uses `math.isclose` on its own segment starts.

  Like the anonymous engine, the named engine compares instants exactly. Roster-derived instants
  coincide exactly because the state machine computes them in whole minutes, and each instant it
  processes is the value it computed. Two independently computed floats that differ only by
  rounding, such as a service end one unit away from a roster boundary, are ordered by their float
  values. An event-time tolerance for stochastic times is UNKNOWN (see "Undetermined"). (Amended in
  5B-4.4: approved rule 4 settles it: no generic event-time epsilon, roster-derived boundaries in
  exact integer minutes, and stochastic service times never rounded or snapped.)
- A service shorter than the time scale resolves (`t + duration == t`) raises
  `EmployeeTimelineError` rather than being simulated.

## Event semantics

At each instant `t`, the earliest of the machine's next instant, the next arrival, and the next
completion, the engine does the following (X2):

1. **Completions.** Every service ending at `t` departs; its employee is passed to the machine as a
   completion.
2. **Closing boundary** (at closing only).
   - The crew is frozen from each employee's state on the interval ending at closing: under DRAIN,
     those AVAILABLE or SERVING (P5); under HARD_CUTOFF, nobody.
   - Closing inputs by state immediately before closing:

     | State just before closing | Inputs, in order | Result |
     |---|---|---|
     | Crew (DRAIN: AVAILABLE, SERVING) | CancelPendingBreaks | keeps serving; pending breaks cancelled |
     | SERVING_BREAK_DUE, not completing at closing | Release, CancelPendingBreaks | finishes the customer as SERVING_SHIFT_ENDED, released at completion; break cancelled |
     | SERVING_BREAK_DUE completing at closing | CancelPendingBreaks, Release (5B-4.4; 5B-4.3 raised `UndeterminedPolicyError`) | the service completes first, no break starts, the break is cancelled_at_closing, released at closing |
     | ON_BREAK, break ending after closing | CancelPendingBreaks, Release, EndBreakAtClosing | break truncated at closing; released at closing |
     | ON_BREAK, break ending at closing | CancelPendingBreaks, Release, EndBreakAtClosing (5B-4.4; 5B-4.3 issued no EndBreakAtClosing) | break truncated_by_closing at closing; released |
     | Any other (OFF, WAITING_FOR_REGISTER, AVAILABLE or SERVING under HARD_CUTOFF, SERVING_SHIFT_ENDED) | CancelPendingBreaks, Release | idle or waiting: OFF at closing; serving: released at completion; not yet started: never activated (`released_after_closing`) |

   - Waiting customers become unserved: `hard_cutoff` under HARD_CUTOFF, and
     `no_eligible_employee` under DRAIN with an empty crew (X6). Under DRAIN with a crew they stay
     in line.
   - Cancelling first gives every not-yet-started break the cause `cancelled_at_closing` (P7).
     For SERVING_BREAK_DUE, Release comes first so that the employee never passes through SERVING.
3. **DRAIN releases** (at and after closing). The crew members idle after this instant's
   completions are ordered by X1; the first `len(line)` stay for the assignment pass and the rest
   receive `Release` now (P5, "until the admitted queue is empty"). Nobody arrives after closing,
   so a crew member left idle has nothing further to serve.
4. **State machine stages** (`process`): completions, closing inputs, shift ends, break ends,
   breaks due, shift starts, register handovers. `hold_past_shift_end=True`, so every release at or
   after closing comes from a Release input chosen under P5 or P6.
5. **Arrivals** at `t` join the line (none at or after closing).
6. **One FCFS assignment pass.** While the line is not empty and an employee is AVAILABLE, the
   AVAILABLE employee with the earliest time of becoming AVAILABLE (ties by employee_id) takes the
   line's head (X1). Under HARD_CUTOFF at or after closing the pass has nothing to do, and the
   engine asserts so.

Engine assertions after every instant: a non-empty line means nobody is AVAILABLE; after closing
only crew members accept; after closing nobody is left AVAILABLE. The run ends when every customer
is resolved and every employee is released.

## Output

- **`customers`:** `customer_id`, `arrival_hours`, `unit_work`, `arrival_segment_id`,
  `service_start_hours`, `service_end_hours`, `employee_id`, `register_id`, `wait_hours`,
  `elapsed_wait_at_close_hours`, `status` (`departed` or `unserved_at_close`), and
  `unserved_reason` (`hard_cutoff` or `no_eligible_employee`). The anonymous engine's columns keep
  their names; `employee_id` and `register_id` replace `server_id`.
- **`counts`** (arrivals, departed, unserved, by reason, served after closing), `mean_wait_hours`,
  and **`queue`** (customer-hours waiting in the horizon and after closing, their total, and the
  maximum line length in the horizon).
- **`at_close`:** waiting and in-service customer ids, the frozen `drain_crew`, and the closing
  inputs issued at closing.
- **`staffing` (P8).**
  - `timeline`: steps `[start, end)` from the run's begin to the later of its finish and the last
    scheduled shift end (every employee is OFF after the finish). Each step carries the six series
    and the two gaps. `required_staffing` and `requirement_gap` are `None` before opening and after
    closing; None is not zero.
  - `windows`: per staffing segment, `horizon` (0 to closing), `before_opening` (when a shift
    starts early), and `after_closing`. Each gives employee-hour integrals of the series and, for
    each gap separately, `shortfall_hours` (integral of `max(0, -gap)`) and `excess_hours`.
  - `scheduled_active` is the roster report's `active_server_steps`: planned shifts minus planned
    breaks. `accepting_capacity` counts AVAILABLE and SERVING employees (INFERRED reading of
    "accepting"; see "Undetermined"). (Amended in 5B-4.4: approved rule 3.)
  - (Amended in 5B-4.4, approved rule 5.) `schedule_realization_gap` is `None` on timeline steps
    before opening and after closing, like `requirement_gap`. The `before_opening` and
    `after_closing` windows report the series only: their gaps and `required_staffing_hours` are
    `None`. The `after_closing` window is always present, with zero duration when the timeline ends
    at closing.
- **`employee_timeline`:** the state machine's record (intervals, transitions, shifts, breaks,
  state totals). Break delays, shift overruns, and after-closing and past-shift-end annotations
  come from it (P9).
- **`trace`:** customer events (`arrival`, `service_start`, `service_end`, `closing`,
  `unserved_at_close`) with employee and register; `max_trace_events` truncates it as in the
  anonymous engine. Employee transitions are in `employee_timeline`.
- **`definitions`, `policy`** (selections and meanings), **`undetermined`**, and
  **`provenance`** (`novaq-shared-named-des-v1`, the state-machine version, "prescribed ... no
  random numbers"). No cost is computed.

## Invariants and their evidence

`check_named` in the test module is an independent checker. It works from the inputs and the
result only and runs on every binary-exact run. On the generated reduction runs it runs with float
tolerance and without the 5B-4.2 checker, whose sums are exact by design.

| # | Invariant (request) | How it is checked |
|---|---|---|
| 1 | arrivals = served + unserved | row count and `counts` |
| 2 | one outcome per customer | fields consistent with exactly one status |
| 3 | one shared FCFS line | service starts non-decreasing in customer order; unserved customers form a suffix |
| 4 | identity never changes | `customer_id`, arrival, and work equal the input pair at that position |
| 5, 12 | non-preemptive; transitions never interrupt a customer | `end = start + work / mu(start)`; the employee is in a serving state on the same register throughout `[start, end)` |
| 6 | one employee per customer | employee and register set exactly for served customers |
| 7 | one customer at a time per employee | an employee's services do not overlap; busy time equals service time |
| 8 | 5B-4.2 invariants | `check_invariants` on `employee_timeline` |
| 9 | occupancy <= K | 5B-4.2 checker, and every staffing step |
| 10 | a non-empty line after the pass means no AVAILABLE employee | checked on every piece between event points |
| 11 | no service start on a break-due, shift-ended, OFF, or waiting employee | every `service_start` transition is AVAILABLE to SERVING and matches a served customer |
| 13 | no arrivals after closing | every arrival `< closing`; an arrival at closing is rejected |
| 14 | HARD_CUTOFF starts nothing at or after closing | no start at or after closing |
| 15 | DRAIN uses only the frozen crew | crew recomputed from the intervals ending at closing; later starts and accepting states only by crew |
| 16 | actual metrics from employee state | every staffing step recomputed from the intervals |
| 17 | the two gaps computed independently | scheduled active recomputed from the roster and rules, required from the segments; each gap and its integrals checked separately |
| 18 | line integral reconciles with waits | `customer_hours_total` equals served waits plus censored waits at closing |
| 19 | common arrivals give identical demand | `test_common_prescribed_arrivals_give_identical_demand_across_rosters` |

X6 is checked too: under DRAIN, unserved customers exist only with an empty crew and carry
`no_eligible_employee`.

## Hand-computed cases

Horizon 08:00-12:00 (0-4 h, closing 4.0); service rate 4 per hour, so a service lasts work / 4.
Every case below is derived in the test's comments.

| Case | Test | Key results |
|---|---|---|
| normal service | `test_normal_service` | #2 waits 0.125 and is served 0.75-0.875; line integral 0.125 |
| break due during service | `test_break_due_during_service` | SERVING_BREAK_DUE 1.0-1.25; break 1.25-1.75 (delay 0.25); #2 waits 0.625 |
| shift end during service | `test_shift_end_during_service` | A released 2.25 (overrun 0.25) without taking #3; #3 served by B 2.5-2.625 |
| register handover | `test_register_handover` | B waits for the register 2.0-2.25, then takes #2 at 2.25 (wait 0.125) |
| backlog during break | `test_backlog_during_break` | waits 0.375 and 0.5; requirement shortfall 0.5, schedule gap 0 |
| delayed split shift | `test_delayed_split_shift` | shift 1 activates 2.125; break 2.625-2.875; schedule shortfall 0.75, excess 0.125 |
| pushed second break | `test_pushed_second_break` | first 1.25-1.5; second pushed to 2.0-2.25 |
| shortfall from a delayed break | `test_capacity_shortfall_caused_by_a_delayed_break` | #3 waits 0.125; schedule shortfall 0.25, requirement shortfall 1.25 |
| DRAIN | `test_drain_freezes_the_crew_and_serves_the_admitted_line` | crew [A]; B's break truncated 3.75-4.0; C never activated; A serves to 4.875 (overrun 0.875); line 0.875 + 1.0 |
| HARD_CUTOFF | `test_hard_cutoff`, `test_hard_cutoff_releases_an_idle_employee_at_closing` | #4, #5 unserved (0.375, 0.125); A released 4.375; idle A released at 4.0 |
| empty frozen crew | `test_empty_frozen_crew_marks_the_line_no_eligible_employee` | break 3.5-4.0 completed; #1 unserved `no_eligible_employee`, 0.25 |
| same-time cases | `test_completion_at_closing` (both policies), `test_shift_end_at_closing_keeps_an_idle_employee_in_the_crew`, `test_completion_and_shift_end_at_one_instant`, `test_break_due_at_closing_is_cancelled_for_a_crew_member`, `test_break_due_service_completing_exactly_at_closing_is_undetermined` | as named |
| DRAIN release order | `test_drain_crew_left_idle_is_released_in_x1_order` | A and B complete at closing with one waiting: A (X1 tie by id) serves 4.0-4.25, B released at 4.0 |
| break due across closing | `test_break_due_service_across_closing_finishes_then_releases` | SERVING_BREAK_DUE to SERVING_SHIFT_ENDED at closing (no SERVING step); break cancelled_at_closing; released 4.25 |
| FCFS, several employees | `test_fcfs_with_several_employees` | #4 and #5 wait 0.25 each, served in arrival order by B |
| X1 longest idle | `test_x1_longest_available_employee` | employees A, B, C, A, B, A (lowest id would give A for #3) |

A first draft of the DRAIN and HARD_CUTOFF expectations assumed A and B tied for #1. A's 08:30
break made A AVAILABLE since 1.0 h against B's 0.0 h, so X1 gives #1 to B. The engine did this;
the expectations were re-derived by hand, and the engine was not changed.

## Reduction to the anonymous engine

`test_reduction_to_the_anonymous_engine` compares every customer's arrival, work, segment, start,
end, wait, censored wait, status, and reason with `shared_continuous_des.simulate_prescribed` on the
same prescribed arrivals. It covers:

- two rosters: a fixed crew of two with no breaks on the whole horizon, and a crew that grows from
  one to two at 10:00;
- both closing policies;
- two demand periods with different service rates;
- 12 generated arrival sets per combination, in two variants: continuous values, and values on a
  1/64-hour and 1/16-work grid, which makes arrival and completion ties frequent.

All 96 comparisons are identical. Which employee or server serves is not compared: X1 and the
anonymous engine's lowest free server id differ.

Equivalence is claimed only for these two rosters. Breaks, shift ends before closing, overruns,
register contention, delayed split shifts, and DRAIN crews smaller than the final staffing segment
legitimately differ, and nothing is claimed for them. The arrival sets are generated in the test
with `random.Random(seed)`; they are prescribed inputs to both engines, not golden values.

## Fault injection

- **Method.** A scratch script, not committed, applied source-level mutants to copies of both
  modules. It loaded each copy in place of its module and ran the named-DES tests (and, for the
  state machine, its tests too). A mutant is killed when a test fails. The unmutated copies passed.
- **Mutants.** 23 in the named DES and 5 in the state-machine changes of this phase:
  - X1 by lowest id, and by most recently available;
  - SERVING_BREAK_DUE counted as accepting; crew limited to AVAILABLE; a crew under HARD_CUTOFF;
  - swapped or wrong unserved reasons; HARD_CUTOFF leaving the line;
  - a break ending at closing truncated; no truncation at closing; cancel before release for a
    break-due service;
  - DRAIN releasing every idle crew member, keeping one idle, or releasing those X1 ranks first;
  - the service rate taken at arrival; the queue integral split at the wrong side of closing;
    assignment before arrivals;
  - P8 accepting as register holders; the requirement gap against the schedule; required 0 outside
    the horizon; the timeline stopping at the finish;
  - the X7 check and the policy check removed;
  - float minute arithmetic; the P3 rule reverted; the gap push omitted; the rest omitted; the
    snapshot hiding the break end.
- **First run: 26 of 28 killed.** Two survivors showed test gaps:
  - "cancel before release for a break-due service", where the employee briefly passes through
    SERVING at closing;
  - "DRAIN releases those X1 ranks first".
- **Tests added for the gaps:** `test_break_due_service_across_closing_finishes_then_releases` and
  `test_drain_crew_left_idle_is_released_in_x1_order`. No test was weakened.
- **After the added tests: 28 of 28 killed**, rerun on the final module text.

## Undetermined (UNKNOWN or INFERRED)

Items 1-4 are settled by the approved Phase 5B-4.4 rules 1-4, and item 5 in part by rule 5 (see
"Phase 5B-4.4 amendments"). Items 6 and 7, and the before-opening part of item 5, remain.

1. **A break-due service completing exactly at closing.** X2 starts the break at the completion,
   before the closing boundary, and P7 would truncate it with zero length. Whether that
   zero-length `truncated_by_closing` break or an unfulfilled `cancelled_at_closing` break is the
   approved outcome is UNKNOWN. The engine raises `UndeterminedPolicyError`
   (`test_break_due_service_completing_exactly_at_closing_is_undetermined`). It needs an exact
   coincidence of a completion with closing.
2. **A break ending exactly at closing** is recorded `completed`: breaks occupy `[start, end)`, so
   it is not in progress at closing, and it had its full duration. INFERRED; X2 processes the
   closing boundary before break ends and the request does not address this case.
3. **"Accepting" means AVAILABLE or SERVING**, for both the P5 crew and P8's `accepting_capacity`.
   SERVING_BREAK_DUE and SERVING_SHIFT_ENDED are "pending break/shift release" in P5's words.
   INFERRED.
4. **Event-time tolerance.** No verified event-time tolerance exists (see "Time"). Exact comparison
   is kept, as in the anonymous engine. Whether seeded runs (5B-4.4) need one is UNKNOWN.
5. **P8 output shape.** The windows (per staffing segment, whole horizon, before opening, after
   closing) and the extension of the timeline to the last scheduled shift end are INFERRED choices
   of shape; the series and gaps follow P8.
6. **P2.** "Record actual break delay only": no threshold is implemented; `delay` is measured from
   the scheduled start, and `due` is recorded, so the delay from the due time is `actual_start -
   due`.
7. **DRAIN release order.** When fewer customers wait than crew members are idle, the ones X1
   ranks first serve and the rest are released. INFERRED from X1 and P5.

## Phase 5B-4.4 amendments

The Phase 5B-4.4 request (2026-09-28) lists "APPROVED REMAINING SEMANTICS" and says to freeze them
before implementing replications. They are quoted in
`2026-09-28-shared-queue-named-replications.md`. In this engine:

1. **Completion at closing with a break due** (rule 1; "Undetermined" item 1). `_closing_inputs`
   issues CancelPendingBreaks, then Release, for such an employee, as for any non-crew employee. The
   state machine then completes the service without starting the break (see its spec, "Phase
   5B-4.4 amendments"). The break is `unfulfilled`, `cancelled_at_closing`, and the employee is
   released at closing. `UndeterminedPolicyError` is no longer raised or imported here.
   - Test: `test_break_due_service_completing_exactly_at_closing_cancels_the_break` (both policies).
     It replaces `test_break_due_service_completing_exactly_at_closing_is_undetermined`.
2. **Break ending exactly at closing** (rule 2; item 2). EndBreakAtClosing is issued to every
   employee on a break immediately before closing, so such a break is `truncated_by_closing`.
   - `test_empty_frozen_crew_marks_the_line_no_eligible_employee` expected `completed`. It now
     expects `truncated_by_closing`. The expectation changed because the approved rule changed it,
     not to make a test pass.
   - New test: `test_break_ending_exactly_at_closing_is_truncated_by_closing` (both policies).
3. **Accepting capacity** (rule 3; item 3). AVAILABLE plus SERVING, as implemented; now approved.
4. **Event time** (rule 4; item 4). No generic event-time epsilon, whole-minute roster
   arithmetic, and no rounding or snapping of stochastic service times. This is what the engine
   already does; now approved.
5. **Staffing gaps** (rule 5; part of item 5). "Report gaps per staffing segment and over the
   configured operating horizon; do not calculate schedule/requirement gaps before opening or after
   closing; report post-close capacity/time separately."
   - Timeline steps outside [0, closing) carry `schedule_realization_gap: None`.
   - The `before_opening` and `after_closing` windows carry no gap and no required hours.
   - `after_closing` is always reported, with zero duration when the timeline ends at closing.
   - `test_drain_freezes_the_crew_and_serves_the_admitted_line` expected an after-closing schedule
     shortfall of 0.125. It now asserts the after-closing series instead: 1.0 h scheduled, 0.875 h
     accepting and busy, and no gap. This is the approved rule's change.
   - New test: `test_staffing_gaps_are_calculated_only_inside_the_operating_horizon`.
6. **`check_named`** (test checker).
   - It now asserts rule 5 on every step and window, and it counts window kinds.
   - It checks the approved break rules on every run: no break starts at or after closing, a
     completed break ends before closing, and a truncated break ends at closing.
   - Inside the horizon it checks the requirement gap's excess as well as its shortfall. It had
     checked only the requirement gap's shortfall; the schedule gap's shortfall and excess were
     already checked.
   - It runs the 5B-4.2 employee checker in float-tolerant mode on inexact runs, where it had
     skipped that checker. The 5B-4.3 reduction runs pass it.
7. `NAMED_ENGINE_VERSION` is `novaq-shared-named-des-v2`. `UNDETERMINED` now lists only the DRAIN
   release order and the before-opening window shape (INFERRED).

## Phase 5B-4.5 amendments

The Phase 5B-4.5 request (named playback) needs the engine's exact recording order. It also
approves a DRAIN trace-order rule: "If several excess idle DRAIN employees are released at the same
instant after the admitted queue is empty: they are semantically released at the same time; use
employee_id ascending only as deterministic trace ordering; this ordering must not change any
customer result." Engine version `novaq-shared-named-des-v3`.

1. **Recording order is now recorded.** Every customer trace event carries
   `employee_transitions_before`: the number of `employee_timeline.transitions` recorded before it.
   The event comes after `transitions[:k]` and before `transitions[k:]`. Before this change the two
   records were separate lists with no recorded interleaving. The value is `len(machine.transitions)`
   at the moment `record` runs.
   - The trace keeps its v2 keys and gains this one key only
     (`test_trace_schema_v3_adds_only_employee_transitions_before`). The transition record is
     unchanged.
   - Hand values: `test_trace_records_employee_transitions_before`.
2. **DRAIN releases in employee_id order.** At a DRAIN instant, X1 still decides which idle crew
   members stay for the waiting customers. Those released are now recorded in employee_id order
   (`released = sorted(idle[len(queue):])`).
   - DISCREPANCY found at `fd67bbf2`: the releases were recorded in X1 order. In
     `test_drain_releases_idle_crew_in_employee_id_order`, three idle crew members, AVAILABLE since
     0.75 (A) and 0.0 (B, C), were released B, C, A; they are now released A, B, C.
   - Evidence that no customer result changed (scratch comparison with the `fd67bbf2` module, not
     committed): 500 seeded runs (10 scenarios, 2 policies, 25 replications) and the hand case.
     Customers, counts, mean wait, the queue integrals, staffing, the closing time, begin, finish,
     and the employee intervals, shifts, breaks, and state totals were identical. The trace was
     identical apart from the new key. Transitions were equal as multisets, and every positional
     difference was a Release inside one closing-input group (1 of 500 runs). The `at_close` blocks
     were identical apart from the order of the Release inputs.
   - The 5B-4.3 test `test_drain_crew_left_idle_is_released_in_x1_order` (who stays) passes
     unchanged.
3. `SAME_TIME_ORDER`, `DEFINITIONS["trace"]`, and `UNDETERMINED` state the rule. Which idle crew
   members stay remains INFERRED from X1 and P5.

## Out of scope and next steps

- Seeded named replications (5B-4.4) need X5 and a decision on item 4 above. (Done in 5B-4.4:
  `2026-09-28-shared-queue-named-replications.md`.)
- Named playback (5B-4.5): done, `2026-09-28-shared-queue-named-playback.md`.
- Attribution reporting (5B-4.6): done, `2026-09-29-shared-queue-named-attribution.md`. It reads this
  engine's `employee_timeline` and changes nothing in the engine (still v3).
- Workforce cost (5B-5) is not started and may not begin without explicit approval.
