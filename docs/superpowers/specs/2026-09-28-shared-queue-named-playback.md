# Shared Queue Enhancement: Phase 5B-4.5, Named-Employee DES Playback

Date: 2026-09-28 (finished 2026-09-29). Status: implemented as
`backend/queueing_engine/simulation/shared_named_playback.py`, with tests in
`tests/test_shared_named_playback.py`. Committed locally only; not pushed, merged, or deployed.

Plan: `docs/superpowers/plans/2026-09-28-shared-queue-named-playback-plan.md`.
Related specs: `2026-09-28-shared-queue-named-des.md` (engine, amended to v3 here),
`2026-09-28-shared-queue-named-replications.md` (run provenance, amended here),
`2026-09-28-shared-queue-named-employee-des-policy.md` (policy contract), and
`2026-09-25-shared-queue-des-replications-playback.md` (the Phase 4 anonymous playback, whose
conventions are reused and which is unchanged).

## Scope

- **In scope:** an isolated replay and validation layer for one regenerated named-employee DES
  replication. The replay consumes the named engine's own records and is not a second simulation.
- **Not in scope:** workforce cost, paired roster comparison, API, database, frontend, Decision,
  Reports, and any acceptance or PASS/FAIL rule.
- **Files.**
  - New: `simulation/shared_named_playback.py`, `tests/test_shared_named_playback.py`, this spec,
    and the plan.
  - Changed (production):
    - `simulation/shared_named_des.py`: engine v3, two trace-only changes (below).
    - `simulation/shared_named_replications.py`: method v2, `inputs_sha256` (below).
  - Changed (tests):
    - `tests/test_shared_named_des.py`: three new tests.
    - `tests/test_shared_named_replications.py`: one version-string assertion, v2 to v3.
    - `tests/test_shared_segments.py`: the module joins the isolation list.
  - Changed (docs): the three related specs, `memory.md`, and `handoff.md`.
  - Not changed (verified by `git diff fd67bbf2`):
    - the anonymous engine, the state machine, and the Phase 4 replications and playback;
    - `services/`, which includes 5B-1 to 5B-3 and Separate Queue;
    - `backend/api/` and `frontend/`;
    - the 5B-4.0 fixture.

## Engine changes (named DES v3)

The engine's customer trace and its employee transitions were two separate lists, with no recorded
interleaving. So "playback event order must preserve the engine's exact ordering" could not be met
without inferring the order. Two trace-only changes were made (details and evidence in the 5B-4.3
spec, "Phase 5B-4.5 amendments"):

1. Every customer trace event records `employee_transitions_before`: the number of transitions
   recorded before it. This is the only new trace key, and the transition record is unchanged.
2. Simultaneous DRAIN releases are recorded in employee_id order. This is the approved rule; the
   engine had recorded them in X1 order, a DISCREPANCY. X1 still decides who stays.

**Evidence that no customer result changed.** A scratch comparison with the `fd67bbf2` engine, re-run
on the final tree, covered 500 seeded runs and the hand case. Customers, counts, the queue, staffing,
and the employee intervals, shifts, breaks, and totals were identical. One run's releases were
permuted within one instant, and the hand case went from B, C, A to A, B, C.

## Event vocabulary (derived from the engine code; everything else is rejected)

**Customer trace** (`CUSTOMER_EVENT_TYPES`): `arrival`, `service_start`, `service_end`, `closing`,
`unserved_at_close`.

**Employee transitions** (`EMPLOYEE_TRANSITIONS`, 22 tuples `(stage, event, from, to)`): the
tuples the 5B-4.2 state machine emits under the named engine's inputs.

| Stage | Event | From -> To |
|---|---|---|
| completion | employee_service_completion | SERVING -> AVAILABLE; SERVING_BREAK_DUE -> AVAILABLE (at closing only, rule 1); SERVING_SHIFT_ENDED -> OFF |
| completion | employee_break_start | SERVING_BREAK_DUE -> ON_BREAK |
| closing_input | employee_release_input | AVAILABLE, WAITING_FOR_REGISTER -> OFF; SERVING, SERVING_BREAK_DUE -> SERVING_SHIFT_ENDED |
| closing_input | employee_break_truncated_at_closing | ON_BREAK -> OFF |
| shift_end | employee_shift_end | AVAILABLE, WAITING_FOR_REGISTER -> OFF; SERVING, SERVING_BREAK_DUE -> SERVING_SHIFT_ENDED |
| break_end | employee_break_end | ON_BREAK -> WAITING_FOR_REGISTER; ON_BREAK -> OFF |
| break_due | employee_break_start | AVAILABLE, WAITING_FOR_REGISTER -> ON_BREAK |
| break_due | employee_break_due_while_serving | SERVING -> SERVING_BREAK_DUE |
| shift_start | employee_shift_start | OFF -> WAITING_FOR_REGISTER |
| shift_start | employee_break_start_at_shift_start | OFF -> ON_BREAK |
| register_handover | employee_register_assigned | WAITING_FOR_REGISTER -> AVAILABLE |
| service_start | employee_service_start | AVAILABLE -> SERVING |

- **Every entry is produced.** `test_every_vocabulary_entry_is_produced_by_the_engine_and_accepted`
  reaches all 22 tuples and all 5 customer types on prescribed days only; no seeded coverage is
  relied on.
  - 14 tuples also appeared in a 400-run seeded probe.
  - Eight need prescribed days (`COVERAGE`, one test each), plus one more day for a tuple that is
    rare under seeds.
- **Rejected state-machine tuples** (`NOT_PRODUCED_BY_THE_NAMED_ENGINE`): the state machine can emit
  these two, but the named engine's closing inputs never produce them (INFERRED from
  `_closing_inputs`).
  - `closing_input/employee_breaks_cancelled_at_closing` SERVING_BREAK_DUE -> SERVING
  - `closing_input/employee_break_truncated_at_closing` ON_BREAK -> WAITING_FOR_REGISTER
- **Unsupported concepts** (`UNSUPPORTED`): no event exists for these, so none is invented.
  - abandonment;
  - a queue entry separate from the arrival;
  - a break becoming unfulfilled, and a shift never activated (both reported from the engine's
    record under `not_represented_by_events`);
  - closing inputs that change no state;
  - scheduled and required staffing;
  - cost.

## Trace merge (recording order)

`_merge` places customer event k after `transitions[:employee_transitions_before]`. It keeps
customer events that share a count in trace order, and appends the remaining transitions at the
end. Nothing else is used to order events.

- **Rejected:** a missing count or a missing field (`trace_structure`), a count that decreases or
  lies outside `[0, len(transitions)]` (`trace_structure`), and a truncated trace (`trace_complete`).
- **Order within one instant.** Derived from the engine loop and checked, not assumed:
  1. `service_end` events, in customer_id order (the completion heap);
  2. the `closing` event;
  3. `unserved_at_close` events, in line order;
  4. the state machine's transitions, in stage order: completion, closing_input, shift_end,
     break_end, break_due, shift_start, register_handover;
  5. arrivals;
  6. each `employee_service_start` transition followed at once by its customer's `service_start`.
- **Within a stage.**
  - completion, shift_end, break_end, break_due, and shift_start come in employee_id order, once
    each.
  - At closing, non-crew closing inputs come before DRAIN releases, each group in employee_id
    order.
- A consequence of recording order: at a customer's `service_end` its employee is still SERVING,
  until the completion transition later in that instant. Per-event counts show this. `instants`
  gives the state at the end of each instant, which the engine's P8 steps describe.

## Replay and validation

`replay_named_trace(result, horizon, demand_periods)` rebuilds the line, customers, employees, and
registers from the two records alone.

- It returns `{"valid": True, ...}` with the events, instants, and rebuilt tables. On the first
  failed check it returns `{"valid": False, "failure": {check, message, seq, source, source_index,
  t, event, evidence}}`.
- Nothing is repaired. `build_named_playback` and the regeneration functions raise
  `NamedPlaybackError` carrying the same failure.
- The horizon and demand periods are used only for the service-duration check.

| # | Required invariant | Check code(s) |
|---|---|---|
| 1 | timestamps never move backward | `time_order` |
| 2 | same-time order follows the verified named-DES order | `same_time_order` |
| 3 | customer identity preserved | `customer_identity` |
| 4 | at most one active service per customer | `customer_single_service` |
| 5 | an employee serves at most one customer | `employee_transition_legal` (a service starts only from AVAILABLE; a serving employee leaves the serving states only through a completion paired with its customer's service_end) |
| 6 | a register has at most one employee | `register_single_holder` |
| 7 | occupancy <= K_phys | `register_capacity` (registers 1..K, one holder each) |
| 8 | legal employee transitions | `event_vocabulary`, `employee_transition_legal` |
| 9 | OFF, ON_BREAK, WAITING_FOR_REGISTER hold no register | `no_register_off_break_waiting` |
| 10 | FCFS | `fcfs` |
| 11 | X1 | `x1_employee_choice` (the AVAILABLE employee available longest, then the lowest id; `available_since` from the transitions) |
| 12 | no HARD_CUTOFF start at or after closing | `hard_cutoff_no_start_after_closing` |
| 13 | DRAIN uses only the frozen crew | `drain_frozen_crew` (crew = AVAILABLE or SERVING at the closing event, before any transition at closing; only crew members start after closing; the idle crew members X1 ranks after the waiting customers are released, in employee_id order) |
| 14 | approved unserved reasons | `unserved_reason` |
| 15 | queue changes reconcile | `queue_reconciliation` (`queue_len_after` at every customer event) |
| 16 | final customer counts reconcile | `customer_reconciliation` |
| 17 | final employee quantities reconcile | `employee_reconciliation` |

**Also checked:**

- P4 handover order (`register_handover_order`);
- work conservation (`work_conservation`);
- service length `unit_work / mu(start)` exactly (`service_duration`);
- the closing rules (`closing_rules`):
  - exactly one closing event, at the horizon end;
  - no arrival, shift end, break end, break due, shift start, or handover at or after closing;
  - closing inputs only at or after closing;
  - P7 truncation of every break in progress at closing;
  - after the closing instant, only OFF, SERVING_SHIFT_ENDED, or a serving crew member;
- the end state (`end_state`).

**Removed as unreachable, proved and not counted as coverage:**

- a separate "employee already serving" check and two service-end variants (the transition check
  covers them);
- a register-occupancy count;
- a non-crew release after closing;
- an employee-on-duty end check;
- a customer-count check (the per-customer engine-row check and the full comparison cover it);
- the row-level customer, closing, and waiting comparisons (see "Reconciliation").

## Reconciliation (which quantities are exact)

**With the regenerated result:**

- **Exact:**
  - the customer rows (every field but `unit_work` and `arrival_segment_id`);
  - `counts`, `mean_wait_hours`, and `queue.max_length_in_horizon`;
  - `at_close`: waiting and in-service customers, and the drain crew;
  - `finish` and `begin`;
  - the per-employee (state, register) intervals, after merging splits that only change
    attributes;
  - the activated shifts (actual start, release);
  - the started breaks (actual start, actual end, outcome);
  - the P8 timeline's four employee-state series at every step.
- **Within the Phase 4 playback tolerance** (`TOLERANCE`: rel 1e-9, abs 1e-12; float sums only,
  times always exact):
  - the queue integrals;
  - `state_totals`;
  - the staffing windows' four employee-state series.
- **Not applicable:**
  - scheduled_active, required staffing, and both gaps (roster and requirement inputs);
  - `unit_work` and `arrival_segment_id` (inputs; `unit_work` feeds only the duration check);
  - `at_close.closing_inputs` (inputs without a transition);
  - unfulfilled breaks and shifts never activated (no event).

**With the replication row:**

- The regenerated row is `named_replication_row(result)`, a function of the result. Its fields
  follow from the reconciled result.
- The one row input not otherwise compared is each interval's `after_closing` flag. The row's
  after-closing employee-hours are therefore recomputed from the rebuilt intervals (tolerance).
- `playback_from_named_replications` then requires the regenerated row to equal the stored row
  exactly, and names the differing fields otherwise (`stored_row`).

## Run-input provenance and regeneration

- **Digest.** `inputs_sha256` (method v2; see the replications spec, "Phase 5B-4.5 amendments") is
  the SHA-256 of canonical JSON: sorted keys, compact separators, ASCII, floats as
  `{"float": float.hex()}`, whole numbers as integers, and lists and tuples as arrays. It covers
  the six input blocks (with `register_count` inside `rules`), the closing policy, and the employee
  policy.
- **Separately recorded and checked exactly:** the seed (`root_entropy` and the row's spawn key)
  and the code versions (method, named engine, state machine, arrival engine, seed scheme).
- **Limits.** Equal digests mean equal recorded values only. The digest is neither tamper-proof nor
  proof of semantic equivalence.
- **`playback_from_named_replications(run, i)` refuses** (`regeneration_identity`, with evidence)
  when:
  - a version or the seed scheme differs from the running code;
  - the index is out of range (`SharedSegmentError`);
  - the stored row's index or spawn key is wrong;
  - the recorded inputs cannot be digested or do not match their digest;
  - the inputs cannot be rebuilt into the dataclasses. This was a crash before a fix made in this
    phase.
  - the rebuilt inputs do not reproduce the digest.
- **Regeneration.** When those checks pass, it regenerates replication i with
  `simulate_named_replication(..., seed_sequence=replication_seed_sequence(root_entropy, i),
  max_trace_events=None)`. This is the unchanged 5B-4.4 seed path, and no second stochastic draw
  sequence exists. It then replays and reconciles, and compares the regenerated row with the stored
  one.
- **Randomness.**
  - The replay draws nothing: the module imports neither numpy nor `random`, and a test runs it
    with every random source disabled.
  - The regeneration draws exactly what a 5B-4.4 replication draws: two streams keyed (i, 0) and
    (i, 1), n + 1 gap draws, and one work draw of size n (counted in a test).
  - The playback has no setting that reaches the simulation. The run's rows are built with no
    trace and the playback with a full trace, and the customer digests agree.
- **Reproducibility.** Unchanged from 5B-4.4: VERIFIED only under the recorded runtime (numpy
  2.4.6, Python 3.13.13, PCG64 here). Cross-version stream equality is UNKNOWN.
  `runtime_matches_recorded` is reported. When it is False, equality with the stored row is
  established by comparison for that replication only.

## Pre-opening and post-closing activity

`outside_horizon` reports employee-hours by base state before opening and from closing on, rebuilt
from the events. No requirement or gap is calculated outside the operating horizon. Every event
carries `period`:

- `before_opening`: t < 0;
- `operating_horizon`: 0 <= t < closing;
- `closing`: t = closing;
- `after_closing`: t > closing.

## Verification

### Tests (`tests/test_shared_named_playback.py` unless named)

- **Hand-derived event sequences:** the ordinary day (all 19 events, per-event counts, and instants);
  several events at one timestamp (FCFS day at 0.0, 1.0, and 1.5); the register handover; X1 and
  FCFS; a break delayed by service; the split shift; DRAIN; idle surplus DRAIN releases in
  employee_id order; HARD_CUTOFF and unserved customers; no eligible employee; the exact closing
  boundaries, including rule 1.
- **Engine v3** (`tests/test_shared_named_des.py`):
  - `test_drain_releases_idle_crew_in_employee_id_order`;
  - `test_trace_records_employee_transitions_before` (hand values);
  - `test_trace_schema_v3_adds_only_employee_transitions_before`.
- **Interleaving field:**
  - monotone, bounded, and time-consistent on every prescribed day and 60 seeded runs;
  - four corrupted counts rejected (`trace_structure` or `same_time_order`);
  - a displaced customer event rejected at the first offending transition.
- **Digest:**
  - an independent recomputation on a hand-written document;
  - key order ignored;
  - 13 simulation-defining changes each change the digest;
  - an int versus a float of equal value differ, and a list versus a tuple do not;
  - unsupported types rejected;
  - the mapping to `simulate_named_replication`'s signature;
  - refusals: a changed input, a changed or missing digest, a version, a stored row, a spawn key, a
    root entropy, an unrepresentable value, an extra field without a matching digest, an extra field
    the rebuild drops, and an extra field the rebuild cannot accept.
- **Randomness:** the replay runs with every random source disabled; the regeneration's draws are
  counted and equal a 5B-4.4 replication's.
- **Corrupted traces rejected**, each with its check code and, where it matters, the offending event:
  - unknown event types (customer, employee, and a state-machine-only tuple);
  - timestamp reversal;
  - five same-time order violations (stage order, closing groups, completion heap order, pairing, a
    service_end without its completion);
  - customer duplication and a second service for a departed customer;
  - one employee serving two customers;
  - double register occupancy, a register beyond K, and a register held while OFF;
  - illegal transitions: a wrong tuple, a legal tuple with the wrong history, rule 1 before closing,
    a closing input before closing, a shift end at closing, a break at closing, and a register
    change while serving;
  - an unpaired service start, an arrival after closing, a start on another register, a service end
    with another employee, and a start while nobody waits;
  - unserved before the closing event, unserved out of line order, a customer left waiting after a
    hard cutoff, a second closing event, and no closing event;
  - a break not truncated at closing (P7), and an idle employee not released under HARD_CUTOFF;
  - an incorrect frozen DRAIN crew (engine claim), a dropped surplus release, and a non-crew
    employee serving after closing;
  - a HARD_CUTOFF start at closing;
  - invalid unserved reasons (policy relabel, wrong reason code);
  - an impossible queue length, a wrong service length, and a waiting employee with a free register;
  - work conservation and a trace ending with a customer in service;
  - a truncated trace, a missing field, and an unknown employee;
  - engine claims that differ from the events: customers, counts, `at_close`, mean wait, maximum
    queue, queue integral, finish, intervals, shifts, breaks, state totals, staffing steps and
    windows, and after-closing hours.
- **Corruptions that keep every final count plausible:** an X1 relabel, an FCFS swap, a dropped
  DRAIN release, and a dropped service start. All four are rejected.

### Fault injection

A scratch script, not committed, mutated a copy of `backend/` and `tests/`, so the working tree was
never touched. For each mutant it ran the playback, 5B-4.4, 5B-4.3, 5B-4.2, pin, and isolation
tests. The 88 source-level mutants covered:

- the merge and vocabulary;
- every ordering, customer, employee, closing, and DRAIN check;
- the reconciliation;
- the regeneration identity;
- the two engine changes;
- the digest construction.

- **First run: 48 of 88 killed.** The 40 survivors were:
  - real gaps: reachable checks that no test corrupted;
  - checks whose failure a later check also caught, where the tests did not pin the first offending
    event;
  - provably unreachable checks.

  Tests were added for every reachable check, asserting the check code, the message, and, where
  relevant, the event or time. Unreachable checks were removed:
  - a non-crew release after closing;
  - the customer-count check;
  - the row-level customer, closing, and waiting comparisons.

  Analysis also found a real defect: recorded inputs with an extra field and a matching digest made
  the rebuild raise `TypeError`. It now refuses with `regeneration_identity`.
- **Final run, on the final text: 88 of 88 killed.**
- No production behavior was changed to kill a mutant.

### Gates (executed on the final tree)

- Focused, all passed:
  - `tests/test_shared_named_playback.py`: 75 (51 test functions);
  - `tests/test_shared_named_replications.py`: 73;
  - `tests/test_shared_named_des.py`: 65;
  - `tests/test_shared_employee_states.py`: 39;
  - `tests/test_shared_continuous_des_pin.py`: 9, fixture not regenerated.
- All `tests/test_shared_*.py`: 769 passed.
- Separate Queue: all 20 files with `separate`, `queue_lifecycle`, or `routing` in the name, 182
  passed.
- Full backend suite, `python -m pytest tests/ -x --tb=short`: 1802 passed, 3 skipped, 1 xfailed, in
  718 s (the 5B-4.4 baseline of 1724, plus 75 playback and 3 named-DES tests).
- `ruff check .`: clean.
- `mypy . --exclude '^outputs/'`: clean on 176 files. Plain `mypy .`: the 5 known errors in the
  gitignored `outputs/technical-paper/build_chapters_4_5.py` only.
- Frontend: not run; nothing under `frontend/` changed.

## Follow-up: validation hardening (2026-09-29)

A read-only re-audit of `028917fe` found two defects, both reproduced on `028917fe` before any change
(scratch script, not committed). This follow-up changes only `simulation/shared_named_playback.py` and
its tests. The engine (v3), the replications method (v2), the digest, the merge, and every named-DES
rule are unchanged, and the playback's output for a valid trace is unchanged apart from the new
check in `validation.checks`. `PLAYBACK_VERSION` is now `novaq-shared-named-playback-v2`.

- **Defect 1: unapproved closing-policy labels were accepted.** On a day where nobody can serve after
  closing, the events are the same under both policies. So `replay_named_trace` and
  `build_named_playback` accepted any label: `"FOO"`, `None`, `"drain"`, `"Drain"`, `1`, `["DRAIN"]`,
  and `("DRAIN",)` were all VALID on the `nobody_on_duty` and `no_eligible_drain_employee` scenarios.
  - **Fix:** a new check, `closing_policy`, runs first. It applies the engine's own test
    (`closing_policy not in CLOSING_POLICIES`) behind a string test, so the check is exact and
    case-sensitive. It never normalizes a label or infers one from the events, and it never raises
    (a numpy array would otherwise raise `ValueError`).
  - `playback_from_named_replications` applies the same check before regeneration, raising
    `NamedPlaybackError` with check `closing_policy`. On `028917fe` the engine refused the policy
    there with `SharedSegmentError`. A relabel without a new digest is still `regeneration_identity`.
  - `prepare_named_playback` takes the policy as an argument, and the engine refuses an invalid one
    with `SharedSegmentError`, as it refuses any invalid input (unchanged).
- **Defect 2: unhashable values raised `TypeError`.** Five places test a value by set or dict
  membership: the customer `type`; a transition's `event`; the `(stage, event, from_state, to_state)`
  tuple; a transition's `employee_id`; and the `(employee_id, actual_start)` key of a started engine
  break. A list at any of them raised `TypeError`, including through `build_named_playback`.
  - **Fix:** each value is tested as a string (or, for `actual_start`, as a finite real) before the
    membership test. It then fails the check a hashable wrong value already failed: `event_vocabulary`
    (`type`, `event`), `employee_transition_legal` (`stage`, `from_state`, `to_state` with a known
    event), or `trace_structure` (`employee_id`). A malformed started break fails
    `employee_reconciliation`. Nothing is converted.
- **Tests** (`tests/test_shared_named_playback.py`, 22 new, 97 in the file). Run against the
  `028917fe` module, the final test file fails all 22 new tests (acceptance, `TypeError`, `ValueError`,
  or `SharedSegmentError`) and passes the other 75.
  - Both approved policies are accepted by the replay, the build, and the stored-run path (DRAIN and
    HARD_CUTOFF), with `playback_version` v2.
  - Eleven unapproved labels are each rejected by the replay and the build with the same failure
    (check, evidence), and the input is left unchanged. A numpy-array label is rejected.
  - The stored-run path refuses a relabel (`regeneration_identity` with the old digest, or
    `closing_policy` with a recomputed one); `prepare_named_playback` refuses `"drain"`.
  - Six membership fields, each wrapped in a list and in a dict: the replay and the build fail the
    pinned check at the pinned record, and the input is left unchanged.
  - Started engine breaks with an unhashable employee_id or actual_start fail
    `employee_reconciliation`.
  - A sweep wraps every field of every customer event and transition on six days, in a list and in a
    dict. Every replay returns a structured failure with a known check, and the days are unchanged.
- **Gates (executed on the final text, 2026-09-29):**
  - focused: playback 97, named replications 73, named DES 65, state machine 39, pin 9, all passed;
  - all 14 `tests/test_shared_*.py` files: 791 passed;
  - Separate Queue, the same 20 files: 182 passed;
  - full backend suite (`python -m pytest tests/ -x --tb=short`): 1824 passed, 3 skipped (PostgreSQL
    rehearsal, `NOVAQ_TEST_DATABASE_URL` unset), 1 xfailed (the known strict xfail), in 641 s;
  - `ruff check .`: clean; `mypy . --exclude '^outputs/'`: clean on 176 files; `git diff --check`:
    clean.
- **Open finding (VERIFIED, not fixed; outside this follow-up's scope).** An extra engine break,
  shift, or interval record naming an employee who is not in the timeline (a string such as `"Z"`)
  is still accepted. The reconciliation compares only the timeline's employees, so such a record is
  ignored rather than rejected. Fixing it needs approval.

## Follow-up: employee referential integrity (2026-09-29)

This follow-up resolves the open finding above. It changes only `simulation/shared_named_playback.py`
and its tests. `PLAYBACK_VERSION` is now `novaq-shared-named-playback-v3`.

- **Defect, reproduced on `086075f7` before any change** (scratch script, not committed). An extra
  record naming an employee outside the employee timeline (`"Z"`) was VALID in `replay_named_trace`
  and `build_named_playback`, with every legitimate record unchanged.
  - Affected record types: `employee_timeline.intervals`, `employee_timeline.shifts` (activated or
    not), `employee_timeline.breaks` (started or unfulfilled), and `at_close.closing_inputs`. The
    earlier report did not name the last one.
  - Cause (verified in the code): `_reconcile` compared intervals, shifts, and breaks only for the
    timeline's employees, and it did not compare closing inputs at all.
  - Also: a non-string `state_totals` key raised `TypeError` when the replay sorted its employees.
  - Already rejected, and unchanged: an extra DRAIN crew member (`drain_frozen_crew`), a customer row
    (`customer_reconciliation`), a transition (`trace_structure`), a trace service event
    (`same_time_order`), and a `state_totals` employee without intervals (`employee_reconciliation`).
- **Authoritative employee set: the run's input employees.** The chain, from the code:
  - `evaluate_roster` reports every input employee, rostered or not (`shared_workforce.py`).
  - `EmployeeTimeline` has one employee per row, and each gets intervals over `[begin, finish)`.
  - `state_totals` is built from those intervals.

  So within a result, the `state_totals` keys (the replay's employees) are the input employees. The
  sets legitimately differ elsewhere: the roster may omit input employees; only rostered employees
  have shifts and breaks; only employees who go on duty have transitions; and an unrostered employee
  appears only in intervals and state totals, OFF throughout.
- **Rule (new check `employee_identity`).**
  1. The `state_totals` keys are strings.
  2. Every interval, shift, break, and closing-input record names one of them. The comparison is
     exact: ids are case-sensitive strings (`shared_workforce._EMPLOYEE_ID`), and nothing is
     normalized, dropped, or reassigned.
  3. `prepare_named_playback`, and so the stored-run path, also requires the timeline's employees to
     equal the input employees.
  - The `086075f7` started-break key check and the existing checks above run first, so their check
    codes are unchanged. Closing inputs' values are still not reconciled ("not applicable"); only
    their employee ids are checked.
- **Limit (VERIFIED by probe).** From a result alone, an extra employee whose records copy an
  unrostered employee's (OFF intervals and totals) cannot be told apart. `replay_named_trace` and
  `build_named_playback` accept it; only the input check in `prepare_named_playback` rejects it.
- **Version.** No written versioning policy exists. In practice a version has changed whenever what a
  module emits changed:
  - named DES v3 for trace-only changes;
  - replications method v2 for a new provenance key;
  - playback v2 (`086075f7`) for a new `validation.checks` entry and a stricter acceptance contract.

  This follow-up does both of the last, hence v3. One existing assertion changed from v2 to v3 (in
  `test_approved_closing_policies_are_accepted_by_every_entry_point`).
- **Tests** (`tests/test_shared_named_playback.py`, 20 new, 117 in the file). Against the `086075f7`
  module, the final test file fails 21 and passes the other 96. Of the 21: 17 accept the orphan, 1
  raises `TypeError`, 1 does not refuse the doctored engine, and 2 assert the v3 version (the changed
  assertion and the unrostered-employee test).
  - An extra record for `"Z"` in each of 7 variants (two intervals, two shifts, two breaks, a closing
    input) is rejected by the replay and the build. The check, the record type, the index, the
    record, and the timeline employees are pinned, and the input is left unchanged.
  - Three of those variants change no aggregate (the replication row, counts, customers, queue,
    staffing, and state totals are the same) and are still rejected.
  - Ids that only resemble a timeline employee (`"a"`, `"A "`, `" A"`, `""`, `"D"`, and 64
    characters) are rejected in every variant.
  - Non-string ids fail without raising. A started break keeps `employee_reconciliation`; the others
    fail `employee_identity`. So does a closing input with no employee_id or that is not a record.
  - A non-string timeline employee fails `employee_identity`. A timeline employee without intervals
    still fails `employee_reconciliation`.
  - An unrostered input employee is on the timeline, OFF throughout, and accepted.
  - With doctored engines (an extra employee copying an unrostered one's records; a missing one),
    `prepare_named_playback` and the stored-run path refuse with `employee_identity`. The real engine
    is accepted.
- **Gates (executed on the final text, 2026-09-29):**
  - focused: playback 117, named replications 73, named DES 65, state machine 39, pin 9, and
    `tests/test_shared_segments.py` (isolation list) 51, all passed;
  - all 14 `tests/test_shared_*.py` files: 811 passed;
  - Separate Queue, the same 20 files: 182 passed;
  - full backend suite (`python -m pytest tests/ -x --tb=short`): 1844 passed, 3 skipped (PostgreSQL
    rehearsal, `NOVAQ_TEST_DATABASE_URL` unset), 1 xfailed (the known strict xfail), in 813 s;
  - `ruff check .`: clean; `mypy . --exclude '^outputs/'`: clean on 176 files; `git diff --check`:
    clean.

## Follow-up: numeric range (2026-09-30)

A read-only probe (2026-09-29, on a scratch copy of `5a9738e2`) found that values beyond the float range escaped as
`OverflowError`. The fix was made on branch `fix/named-playback-overflow` from `156de75f`, where this module and its
tests were unchanged since `5a9738e2`. It changes only `simulation/shared_named_playback.py` and its tests. The engine
(v3), `shared_named_replications.py` and its method (v2, `METHOD_VERSION` unchanged), the digest, the merge, and every
named-DES rule are unchanged. `PLAYBACK_VERSION` is now `novaq-shared-named-playback-v4`.

- **Correction to the v2 record.** The v2 hardening made unhashable values fail a check. It did not cover numeric
  range: a whole number or `Fraction` beyond the float range, and finite floats whose exact sum is beyond it, still
  raised `OverflowError` through v3 (VERIFIED on the v3 module).
- **Defects, reproduced on the v3 module before any change.** The results were doctored; the engine never produces
  these values.
  - `_time` (`float(value)`): a huge whole number or `Fraction` in a trace or transition `t`, or in a started engine
    break's `actual_start`.
  - `_close_enough` (`math.isclose`) and `near` (`float()`): a huge engine state total, queue integral, or
    staffing-window series value.
  - `unit_work / mu` in the service-duration check: a huge `unit_work`. `None` or a string raised `TypeError`.
  - `math.fsum` on finite floats: the served-wait sum (every float of a real replication times 2**1018), a
    per-employee state total, and `_hours_in` for a staffing window.
  - `_outside_horizon`, which ran after the exception boundary. With the timeline beginning at -DBL_MAX every check
    passed, and `replay_named_trace` raised from `_outside_horizon` -> `_hours_in`.
  - `build_named_playback` computed `named_replication_row` before the replay. It raised `OverflowError` from that
    function (the wait sum, state totals, after-closing intervals, overruns, activation and break delays, and finish
    minus closing) and `SharedSegmentError` for inconsistent counts, where `replay_named_trace` failed a check or
    accepted the result.
  - Where probed, each escaped `replay_named_trace`, `build_named_playback`, or both. `playback_from_named_replications`
    was probed with a doctored engine (trace and transition times, `unit_work`, a state total, an after-closing
    interval) and raised in every case.
- **Fix:**
  - `_time` and `_close_enough` return False on `OverflowError`. `near` treats an `OverflowError` from its `float()`
    conversions as outside the tolerance.
  - A new `_fsum` wrapper turns `OverflowError` into the caller's existing check. It is used at the served-wait sum
    (`customer_reconciliation`), the state totals (`employee_reconciliation`), and `_hours_in`
    (`employee_reconciliation`), which serves the staffing windows, the row's after-closing hours, and
    `_outside_horizon`.
  - `unit_work` is tested as a finite real before the division; otherwise `service_duration` fails with "The engine's
    unit_work is not a finite number." This also turns `None` or a string (formerly `TypeError`) into that failure, and
    gives `inf` or NaN (formerly `service_duration` with the duration message) the new message.
  - `_outside_horizon` runs inside the exception boundary of both `replay_named_trace` and `build_named_playback`.
  - B1: `build_named_playback` replays first, then computes `named_replication_row` inside the same boundary. An
    `OverflowError` from the row fails the new check `summary_row`, with the error text as evidence. A result the replay
    rejects fails the same check in the build, so inconsistent counts now raise
    `NamedPlaybackError(customer_reconciliation)` instead of `SharedSegmentError`.
  - Existing check codes are unchanged. `summary_row` is appended to `CHECKS`.
- **Reachability of the `_outside_horizon` boundary (VERIFIED by tests).** In the replay, a timeline beginning at
  -DBL_MAX reaches it. In the build, it is reached when the engine's OFF totals lie inside the replay's tolerance below
  the rebuilt ones (rel 5e-10 in the test), so that the row's cross-employee sum stays in the float range. That this is
  the only route in the build is INFERRED: the row sums each state's totals across employees before
  `_outside_horizon` runs.
- **Valid output unchanged (VERIFIED by a scratch comparison, not committed).** The v3 module (a `git archive` of
  `156de75f`) and the v4 module each produced 276 outputs: `replay_named_trace` and `build_named_playback` on 10 seeded
  scenarios x 2 policies x 6 seeds, `playback_from_named_replications` on each scenario and policy, and
  `replay_named_trace` on 16 prescribed days. After removing `provenance.playback_version` and the appended
  `summary_row` check, all 276 were identical.
- **Tests** (`tests/test_shared_named_playback.py`: 10 new functions, 50 new tests, 167 in the file; the two v3 version
  assertions changed to v4):
  - a time beyond the float range (4 values, in the trace and in the transitions): `trace_structure`;
  - a started break's `actual_start` beyond it: `employee_reconciliation`;
  - `unit_work` beyond it, `inf`, NaN, `None`, or a string: `service_duration`;
  - an engine state total, queue integral, or staffing-window value beyond it: its existing check;
  - finite floats whose sum is beyond it: the served-wait sum, a state total, and a staffing window, each with an
    accepted control;
  - `_outside_horizon` in the replay and in the build;
  - `summary_row` for an overrun, a finite overrun sum, an activation delay, and a break delay, which the replay
    accepts, and through the stored-run path with a doctored engine;
  - the build failing exactly as the replay does, for inconsistent or out-of-range counts, a wait, an after-closing
    interval, the finish, and the closing time;
  - every float field in turn replaced by the equal `Fraction`: valid, and the playback equal to the original.

  Against the v3 module (the `156de75f` archive with the new test file), 52 tests fail and 115 pass. Of the 52: 43
  raise `OverflowError`; 2 raise `SharedSegmentError` (counts); 2 raise `TypeError` (`unit_work` `None` and string);
  2 (`unit_work` `inf` and NaN) already failed `service_duration`, with the old message; and 3 assert the v4 version.
- **Fault injection** (scratch copy; the working tree was untouched). 13 mutants each undo one change: the `_time`,
  `_close_enough`, and `near` guards; `_fsum` at each of its three sites; the `unit_work` test; `_outside_horizon`
  outside the boundary in the replay and in the build; the `summary_row` guard; the row before the replay; the `CHECKS`
  entry; and the version. First run: 12 of 13 killed. The build `_outside_horizon` mutant survived, so the
  tolerance-band test was added. Final run: 13 of 13 killed.
- **Gates (executed on the final code, 2026-09-30):**
  - focused: playback 167, named replications 73, named DES 65, state machine 39, pin 9, `tests/test_shared_segments.py`
    51, and attribution 141, all passed;
  - all 15 `tests/test_shared_*.py` files: 1002 passed;
  - Separate Queue, the same 20 files: 182 passed;
  - full backend suite (`python -m pytest tests/ -x --tb=short`): 2035 passed, 3 skipped, 1 xfailed, 6 subtests
    passed, in 484 s. The skip reasons were not printed in this run. The full suite was not rerun before the change in
    this worktree, so no verified pre-change count is claimed;
  - `ruff check .`: clean; `mypy . --exclude '^outputs/'` and plain `mypy .` in this worktree: no issues in 178 files;
    `git diff --check`: clean.
- **Open (VERIFIED, not fixed, outside this follow-up; each needs approval):**
  - The queue-area accumulation in `_reconcile` (`area[...] += queue_len * (t2 - t1)`) is not an `fsum` site. With
    exact `Fraction` times (a consistent HARD_CUTOFF day times 2**1021), a term beyond the float range still raises
    `OverflowError` from `replay_named_trace`. It is present on v3 as well.
  - An engine break with an unknown `unfulfilled_cause` passes the replay, which does not reconcile unfulfilled breaks.
    `build_named_playback` then raises `SharedSegmentError` from `named_replication_row`. It is present on v3 as well.
    It is not an overflow, so `summary_row` does not cover it.
  - Non-finite values are accepted: a timeline beginning at -inf, and infinite queue integrals (floats times 2**1021),
    replay as VALID, because `math.isclose(inf, inf)` is True.
  - From the 2026-09-29 probe, outside this module or out of scope:
    - a huge or `Fraction` `register_count` (`MemoryError` or `TypeError` in `_Replay.handover`);
    - a caller-supplied service rate beyond the float range (`float()` in `_Replay.__init__`);
    - `services/shared_segments._is_finite_real`, which has the same unguarded `float()`;
    - the named DES `servers` sum (`shared_named_des.py`);
    - `simulation/shared_employee_states._handover` (`MemoryError` on a huge `register_count`).

## Undetermined (UNKNOWN or INFERRED)

1. Cross-version numpy stream equality: UNKNOWN (unchanged from 5B-4.4).
2. That the two rejected state-machine tuples never occur under the named engine: INFERRED from
   `_closing_inputs`. None appeared in the 400-run probe or in any test.
3. Which idle DRAIN crew members stay (X1 and P5): INFERRED, carried over. Only their trace order is
   approved.
4. The before-opening window shape: INFERRED, carried over.
5. The Phase 4 tolerance is the repository's playback convention for float sums. No separate
   analysis established it for named sums, and it is never applied to times.
6. The acceptance rule: UNKNOWN; none exists, and none is invented.
