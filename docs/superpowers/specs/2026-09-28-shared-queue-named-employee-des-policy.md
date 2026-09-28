# Shared Queue Enhancement: Phase 5B-4.0 and 5B-4.1, Anonymous-Engine Pin and Named-Employee DES Policy Contract

Date: 2026-09-28. Status: Phase 5B-4.0 is implemented (one test module and one fixture). Phase
5B-4.1 is this document. It records approved design semantics; none of them is implemented.

## Approval and how to read it

- On 2026-09-28 the product owner wrote: "The Phase 5B-4A design is approved using P1–P9 and
  X1–X7 exactly as supplied by the user."
- The Phase 5B-4A design was a read-only chat report on 2026-09-28, with a correction message
  that added X7. It is not a repository file, and this document is its first repository record.
- **Where the design supplied one rule**, that rule is an APPROVED SPECIFICATION. This document
  records it without change.
- **Where the design supplied alternatives or open questions**, the approval does not choose
  among them:
  - the selection is UNKNOWN;
  - no default is assumed;
  - the sub-phase that needs it is blocked until the product owner supplies it.

  The table in "Open selections" lists each one.
- **Nothing here describes existing behavior.**
  - No named-employee DES exists.
  - `simulation/shared_named_des.py` does not exist and is not created in this phase.
  - The employee state machine is not implemented.
  - Statements labeled VERIFIED describe the code at `d5723aba`. Every other statement is design.

## Starting point (verified at `d5723aba`)

Paths are relative to `backend/queueing_engine/` unless they start with `backend/`, `tests/`,
or `requirements`.

### Anonymous shared-queue engine

`simulation/shared_continuous_des.py`, ENGINE_VERSION `novaq-shared-continuous-des-v2`:

- **Servers** are anonymous numbers in the states CLOSED, IDLE, BUSY, and DRAINING.
- **Same-time order** is completion, then capacity change, then arrival (line 44). After each
  single event, waiting customers go first come, first served to the lowest-numbered idle server
  (`assign`, lines 248-263; main loop lines 321-331).
- **Capacity changes** happen at staffing-segment starts (`apply_capacity`, lines 265-305):
  - A decrease closes idle servers first (highest number first), then drains busy servers
    (highest number first).
  - An increase reactivates draining servers first, then reopens closed ones, then creates new
    numbers.
  - There is no register limit.
- **Service** lasts `work / μ`. The work is drawn once from Exp(1), and μ is the rate in force when
  service starts (line 255). Service is never interrupted.
- **Closing** is in lines 334-381. Phase 3A DRAIN and HARD_CUTOFF are as in
  `2026-09-25-shared-queue-closing-policy.md`. `_unserved_possible` (lines 394-407) decides
  from the configuration alone: HARD_CUTOFF, or DRAIN with 0 servers in the final segment.
- **Random numbers.** `_draw_arrivals` (lines 593-609) depends only on the horizon, the demand
  periods, and the `SeedSequence`. Every staffing therefore sees the same customers.
- **Entry points.** `simulate_prescribed` (lines 137-387) draws no random numbers. It is the
  deterministic entry point used by the Phase 5B-4.0 pin.

### Other shared-queue modules

- **Playback.** `simulation/shared_playback.replay_events` rejects unknown event types
  (line 104).
- **Timeline validation.** `services/shared_segments.validate_timeline` rejects an empty staffing
  list: `_sequence_problems` returns "At least one staffing segment is required."
  (lines 132-133).
- **5B-1 workforce** (`services/shared_workforce.py`):
  - The REGISTER_CAPACITY check applies to *scheduled* active staff (lines 641-645).
  - "Registers are counted, not identified" (line 676).
  - Overtime is scheduled paid time past the daily threshold, in clock order (`_overtime_start`,
    line 472). There is no rule for time actually worked past a shift end.
  - The status is INVALID when there are violations, otherwise INCOMPLETE when anything is
    missing, otherwise COMPLETE (line 655).
  - "Missing" means one of two things:
    - a pay field: `regular_rate_per_hour`, `overtime_rate_per_hour`, or
      `daily_regular_paid_minutes` (lines 617-621);
    - a break-rule gap, with field `break_rules` (line 646).
- **5B-2 and 5B-3** return rosters as `asdict(ScheduledShift)` rows
  (`services/shared_rostering.py:748-749`, `services/shared_integrated.py:744-745`).

### Separate-queue break behavior

This applies to separate queues only:

- `PRE_BREAK_CUTOFF_MINUTES = 3.0` (`config.py:30`).
- A lane accepts arrivals only when ACTIVE (`simulation/queue_lifecycle.py:74-75`).
- The break controller drains the lane, starts the break when the lane is empty, and runs the
  full duration from the actual start (`services/separate_optimization.py:946-977`). It emits
  `draining_start`, `break_start`, and `break_end` (lines 953, 970, 976, 1150-1161).
- `backend/api/analysis_schemas.py:152` rejects break schedules for shared queues.

### Dependency pins (CONFLICTING)

| Source | numpy | scipy |
|---|---|---|
| `requirements.txt` (CI) | `>=1.24.0,<2.3` | `>=1.14.0` |
| `requirements-lock.txt` | 2.4.6 | 1.17.1 |
| `requirements-production.lock` | 2.2.6 | 1.17.1 |
| Local environment | 2.4.6 | 1.17.1 |

- The local 2.4.6 is outside the `requirements.txt` range.
- Whether `default_rng(...).exponential` returns the same values across these numpy versions is
  UNKNOWN. It has not been tested.

## Phase 5B-4.0: anonymous-engine whole-output pin (implemented)

- Existing coverage: `tests/test_shared_continuous_des.py` already pins individual behaviors
  with hand-computed cases (34 test functions, 111 collected tests). The pin adds whole-output
  coverage; it does not replace those tests.
- **What it adds.** `tests/test_shared_continuous_des_pin.py` compares the complete result
  dictionary of `simulate_prescribed` with `tests/fixtures/shared_continuous_des_output_pin.json`,
  key by key, with exact equality.
  - The result covers customers, segments, totals, capacity transitions, drains, closing, cost
    quantities, the trace, the truncation flag, and provenance.
  - Floats round-trip exactly through JSON (`repr`).
- **Inputs** are fixed and prescribed. There is no seed and no random number. Every input time
  and work amount is binary-exact. There are 7 cases:
  - the main "transitions" case, run under DRAIN, under HARD_CUTOFF, and under DRAIN with a
    7-event trace cap;
  - "no one on duty at closing", under both policies;
  - "no arrivals", under both policies.
- **Paths exercised by the main case:**
  - opening a new server number;
  - closing idle servers before draining;
  - reactivating a draining server before reopening a closed one;
  - a drain into a 0-server segment;
  - ties of completions, arrivals, and capacity changes;
  - a μ change between demand periods;
  - completions exactly at closing;
  - a backlog that DRAIN serves at the final μ and HARD_CUTOFF records as unserved.
- **Origin of the expected values.** They are the engine's own output at `d5723aba`, so the pin is
  a characterization of that output.
  - The main case's customer schedule, capacity transitions, at-close state, and overrun were also
    derived by hand. They agreed with the engine output.
  - `test_transitions_case_matches_hand_derivation` asserts that hand derivation without using the
    fixture.
- **Fault injection** (a scratch script, not committed) applied 15 source-level mutants to an
  in-memory copy of the engine. The pin caught all 15. The unmutated copy matched the fixture, and
  the engine file was never modified.
- **Regeneration.** Run `python -m tests.test_shared_continuous_des_pin --write`, and only for an
  authorized, documented change to the anonymous engine.
- **No engine change.** `shared_continuous_des.py` is unchanged; it already had a safe
  deterministic entry point.

## Constraints on the named-employee DES (approved)

### Protected behavior

- **The anonymous engine's semantics and outputs do not change.** The 5B-4.0 pin guards them. A
  change to `shared_continuous_des.py` for the named work, such as an X5 public alias, must leave
  the pin passing without regenerating the fixture.
- **Separate Queue break behavior is protected and is not reused or generalized:**
  - `PRE_BREAK_CUTOFF_MINUTES`;
  - `queue_lifecycle.py` (`begin_draining`, `begin_break`, `end_break`);
  - the `separate_optimization` break controller and break validation;
  - `break_optimization.py`.

  Its 3-minute cutoff is not transferable (P2).
- **Event names.** Named-employee trace events use an `employee_` prefix. They never reuse the
  separate-queue names `draining_start`, `break_start`, or `break_end`.
- **No input relaxation.** `backend/api/analysis_schemas.py:152` is not relaxed in an engine-only
  phase.
- **No change** to the 5B-2 or 5B-3 mathematics, or to the API, database, scenarios, frontend,
  Decision, Reports, or Separate Queue.

### Random numbers

- **Customers.** The named engine gets its customers only from the anonymous engine's existing
  stream (`_draw_arrivals`, reached as X5 decides). It draws no random numbers of its own and
  introduces no new random process.
  - X1 is deterministic and uses no random numbers.
  - The same seed gives the same customers across rosters and across both engines.
- **Test values.** The numpy pins conflict, and cross-version stream equality is UNKNOWN. So:
  - reference values in tests come from prescribed arrivals, never from seeded golden values;
  - seeded tests may assert only properties that hold in any single environment, such as
    identical customers across rosters for one seed, and never cross-environment values.

### X7: staffing segments are required (approved, mandatory)

- **Required input.** The named DES takes `required_staffing`, a list of `StaffingSegment`, as a
  required input with no default. It is never optional.
- **Validation.** The named DES validates
  `validate_timeline(horizon, demand_periods, required_staffing)`. It never passes an empty
  staffing list, and it has no substitute validation path for the horizon and demand periods.
- **Role of the segments.** They validate the timeline.
  - The correction that introduced X7 also named them as the reference for P8's
    scheduled-versus-actual comparison. How that comparison is reported is P8, which is open.
  - Their server counts do not set named-engine capacity. The design says "No schedule is forced
    on the queue": capacity comes from employee states.

## Employee state machine (approved design semantics, not implemented)

Each employee is in exactly one state at a time:

| State | At a register | Customers | Takes new customers |
|---|---|---|---|
| OFF (before shift, between split shifts, after release) | no | 0 | no |
| WAITING_FOR_REGISTER (P4) | no | 0 | no |
| AVAILABLE | yes | 0 | yes |
| SERVING | yes | 1 | yes, after this one |
| SERVING_BREAK_DUE | yes | 1 | no |
| SERVING_SHIFT_ENDED | yes | 1 | no |
| ON_BREAK | no | 0 | no |

Capacity:

- **Accepting servers** at time t are the employees in AVAILABLE or SERVING. This is the named
  equivalent of the anonymous IDLE plus BUSY.
- **Register occupancy** is the accepting servers plus SERVING_BREAK_DUE and SERVING_SHIFT_ENDED.
  It never exceeds the register count K.
- **Busy servers** are the employees in the three SERVING states.
- Before closing, accepting servers never exceed the 5B-1 scheduled active count. This is
  INFERRED from the rules and is to be asserted by a test.

## Transition rules (approved design semantics, not implemented)

Rules that depend on an open selection name it.

- **Shift start.**
  - OFF becomes AVAILABLE if a register is free.
  - Otherwise the employee becomes WAITING_FOR_REGISTER.
- **Assignment.**
  - AVAILABLE becomes SERVING and takes the customer at the head of the one shared FCFS line.
  - Service lasts `work / μ(start)`, unchanged.
- **Completion.**
  - SERVING becomes AVAILABLE.
  - SERVING_BREAK_DUE becomes ON_BREAK and releases the register.
  - SERVING_SHIFT_ENDED becomes OFF and releases the register.
- **Break due at its scheduled start.**
  - AVAILABLE becomes ON_BREAK and releases the register.
  - SERVING becomes SERVING_BREAK_DUE.
  - WAITING_FOR_REGISTER becomes ON_BREAK.
- **Break end.**
  - Its time is set by P1 (open).
  - The employee becomes AVAILABLE if a register is free, otherwise WAITING_FOR_REGISTER.
  - If the break ends at or after the shift end, the employee becomes OFF (subject to P3, open).
- **Shift end.**
  - AVAILABLE becomes OFF and releases the register.
  - SERVING or SERVING_BREAK_DUE becomes SERVING_SHIFT_ENDED.
  - WAITING_FOR_REGISTER becomes OFF.
  - ON_BREAK follows P3 and P7 (open).
- **Register release.** The first waiting employee takes the register and becomes AVAILABLE. The
  order among waiting employees is P4 (open).
- **Closing.**
  - The Phase 3A order holds: completions at closing first, then the recorded state at close,
    then the policy.
  - Employee eligibility after closing is set by P5, P6, and P7 (open).
- **End of run.** Every customer has an outcome, and every employee is OFF.

## Policies P1-P9 and X1-X7

| Item | Approved content (APPROVED SPECIFICATION) | Open selection (UNKNOWN until supplied) | Earliest sub-phase blocked |
|---|---|---|---|
| **P1** Length of a break delayed by service | The delay is recorded (P9). The break is never dropped silently (invariant 8). | (a) full length from the actual start; (b) keep the planned end, so the break is shortened, or lost if the delay reaches its length; (c) full length, cut off at the shift end. Also: may a delayed break overlap the next break or its minimum gap? Is a shortened or lost unpaid break recorded with no pay consequence until 5B-5? | 5B-4.2 |
| **P2** Maximum break delay | No hard cap is possible (INFERRED). Service is non-preemptive and work is Exp(1), so the delay is the remaining service time, which is unbounded; given the employee is busy, it is Exp with mean 1/μ. Any caller-supplied value has no default: `None` means not supplied, and an explicit 0 means none. The separate queue's 3 minutes is not transferable. | (1) no cap, delay recorded; (2) a caller-supplied threshold L, reported only; (3) a caller-supplied pre-break cutoff τ minutes. | 5B-4.2 (τ changes transitions) |
| **P3** Shift end during service | The employee finishes the customer: handing over mid-service would be preemption. | An optional pre-shift-end cutoff. A split-shift overrun that reaches the next shift or the required rest. A break still pending at the shift end: forfeited, or taken afterwards? | 5B-4.2 |
| **P4** Register handover and physical capacity | An incoming employee who finds all K registers occupied waits (WAITING_FOR_REGISTER). K is never exceeded, and no service is interrupted. With 5B-1's register check satisfied, contention arises only from overruns (INFERRED). | The order among waiting employees. Whether registers are identified 1..K (for playback) or only counted. | 5B-4.2 (order); 5B-4.5 (identity) |
| **P5** Eligibility after closing, DRAIN | Phase 3A DRAIN semantics for customers are unchanged: arrivals stop, completions at closing come first, and waiting customers are served FCFS. | (a) employees accepting just before closing, including those whose shift ends exactly at closing (the anonymous engine's rule); (b) only employees whose shift runs past closing; (c) (a) plus employees returning from a break or starting after closing. Also: do eligible employees serve until the line is empty regardless of shift end (no cap, as in the anonymous engine), or leave at their shift end? | 5B-4.2 |
| **P6** After closing, HARD_CUTOFF | Phase 3A HARD_CUTOFF semantics are unchanged: waiting customers become unserved, and services under way finish. | Is an employee released at their last service completion or at their scheduled shift end? Does a break pending at closing still happen? | 5B-4.2 |
| **P7** Breaks interrupted by closing | A break in progress at closing, or scheduled after it, needs an explicit rule. | Finish the break, then rejoin the drain; or end the break at closing; or make the employee ineligible after closing. | 5B-4.2 |
| **P8** Actual versus scheduled coverage | Actual (simulated) staffing is reported against scheduled staffing. The X7 correction names the staffing segments as a reference. | Which count is "actual staffing": accepting, occupancy, or busy? Does time waiting for a register count? How are shortfall and excess minutes reported (per demand period, per staffing segment), and against which reference (the 5B-1 schedule, the segments' required counts, or both)? | 5B-4.3 (output shape) |
| **P9** Attribution | Per employee and shift, record quantities only: break delay, break shortening or loss, shift overrun, time after closing, and time waiting for a register. No cost is attached. Which quantity counts as paid overtime belongs to 5B-5, not here. A minute that is both past the shift end and after closing is counted once. | Which of the two quantities holds such a minute. | 5B-4.6 |
| **X1** Choice among available employees | Deterministic, with no random numbers. | Lowest id, longest idle, or avoid an employee whose break is imminent. | 5B-4.3 |
| **X2** Same-time event order | Completions, then shift ends, then break ends, then breaks due, then shift starts, then register handovers, then arrivals, then one FCFS assignment pass. This differs from the anonymous engine, which assigns after every single event; the two coincide on inputs with no ties (INFERRED). | None. | None |
| **X3** Time before opening | The state at opening follows directly from the schedule, because no customers exist before opening. Time after a shift's scheduled end falls under P3, P5, and P6. | None beyond P3, P5, and P6. | None |
| **X4** Roster precondition | Reject an INVALID roster. Accept an INCOMPLETE roster only when every missing entry is a pay field (`regular_rate_per_hour`, `overtime_rate_per_hour`, `daily_regular_paid_minutes`). A `break_rules` gap is not a pay field, so such a roster is rejected. | None. | None |
| **X5** Random-number interface | The anonymous stream is reused unchanged (see "Random numbers"). | Import the private `_draw_arrivals` unchanged, or add a one-line public alias in `shared_continuous_des.py`. The alias must leave the 5B-4.0 pin passing. | 5B-4.4 |
| **X6** When customers can go unserved under named DRAIN | Phase 3A's configuration-level `_unserved_possible` does not carry over: under named DRAIN it can depend on the simulated run, for example when the only closer is on a delayed break. It must be redefined before 5B-5 uses it. | The redefinition. | 5B-4.3 (output field); 5B-5 |
| **X7** Staffing segments | Required, with no default; validated by `validate_timeline`; never empty; never optional (see above). | None. | None |

## Invariants (approved; to be asserted in 5B-4.3)

1. **Customer conservation.** Arrivals equal served plus unserved, with one outcome per customer.
2. **One shared FCFS line.** Services start in arrival order.
3. **No preemption.** Each service runs `work / μ(start)` on one employee without a break in time.
4. **Employee exclusivity.**
   - Each employee has one state at a time, at most one customer, and at most one register.
   - ON_BREAK and OFF mean no customer and no register.
5. **Physical capacity.** Register occupancy ≤ K at all times.
6. **Work conservation.** After same-time events are processed, a non-empty line implies no
   AVAILABLE employee.
7. **Schedule consistency.**
   - Employees take customers only on shift and not break-due, except under the approved DRAIN
     rule (P5, open).
   - Before closing, accepting servers ≤ the 5B-1 scheduled active count.
8. **Breaks.**
   - The actual start is at or after the scheduled start.
   - The delay is 0 if the employee was AVAILABLE when the break fell due, otherwise it equals
     the remaining service time.
   - Every scheduled break is either taken or explicitly recorded as lost.
9. **Time partition.**
   - For each employee, the time in all states sums to the elapsed time.
   - Busy time summed over employees equals the sum of service durations.
10. **Waiting-time integral.** The integral of the line length equals the served waits plus the
    censored waits of unserved customers.
11. **Closing.** No arrivals after closing, no service start after a HARD_CUTOFF, and the run
    terminates.
12. **Common random numbers.** Customers come only from the anonymous stream (X5), and the named
    engine draws no random numbers.
13. **Reduction.** A fixed crew with no breaks, or a crew that only grows, reproduces the anonymous
    engine's customer results exactly. This is INFERRED and must be tested. Because of X2, the test
    inputs must avoid ties or account for the order difference (also INFERRED).
14. **Units.** Times are hours from the horizon start, using the anonymous engine's `_hours`
    conversion. Integer-minute roster inputs are never rounded.

## Proposed interface (approved design, not implemented)

- **Module.** `simulation/shared_named_des.py`.
- **`EmployeeDesPolicy`** holds the approved P and X selections. Every field is required, with no
  default.
- **`simulate_named_prescribed`:**

  ```python
  simulate_named_prescribed(
      horizon, demand_periods, employees, rules, roster, arrivals, *,
      closing_policy, employee_policy, required_staffing, max_trace_events=None,
  )
  ```

  `required_staffing` is required under X7. The 5B-4A report's `required_staffing=None` is
  superseded.
- **`simulate_named_replication(..., seed_sequence, ...)`** takes a numpy `SeedSequence`.
- **Later:** `run_named_replications` and `replay_named_events`. The named replay is separate
  from `shared_playback.replay_events`, which rejects unknown event types.
- **Isolation.** The module joins `SHARED_QUEUE_ENHANCEMENT_MODULES` in
  `tests/test_shared_segments.py`, and it never imports separate-queue break code.

## Open selections (must be supplied before the named sub-phases)

This dependency mapping is INFERRED from the transition rules above.

| Sub-phase | Needs |
|---|---|
| 5B-4.2 employee timeline state machine | P1, P2 (whether τ applies), P3, P4 order, P5, P6, P7 |
| 5B-4.3 named engine on prescribed arrivals | the above, plus X1, P8 output shape, and the X6 output field |
| 5B-4.4 seeded replications | X5 |
| 5B-4.5 named playback replay | P4 register identity |
| 5B-4.6 attribution quantities | P2 threshold (if chosen), P8 reporting, P9 minute attribution |
| 5B-5 workforce cost | X6 redefinition, overtime classification, D15 acceptance rule |

## Separate Queue regression risks

- **Shared break code.** Reusing or generalizing the separate break code listed above would
  change Separate Queue results. It is not done.
- **Event-name collision.** The `employee_` prefix avoids collision with `draining_start`,
  `break_start`, and `break_end`.
- **Input validation.** Relaxing `analysis_schemas.py:152` would admit shared-queue breaks through
  the API. It is not done.
- **Tests that must pass unchanged:**
  - `tests/test_separate_break_des.py`, `tests/test_separate_break_periods.py`,
    `tests/test_separate_break_wiring.py`;
  - `tests/test_queue_lifecycle.py`, `tests/test_routing_des_pairing.py`;
  - the isolation test in `tests/test_shared_segments.py`;
  - the 5B-4.0 pin.

## Out of scope for 5B-4.0 and 5B-4.1

- The employee state machine.
- `shared_named_des.py`.
- Any change to `shared_continuous_des.py` or the other shared modules.
- Any change to the API, database, scenarios, frontend, Decision, Reports, or Separate Queue.
- Push, merge, and deploy.
