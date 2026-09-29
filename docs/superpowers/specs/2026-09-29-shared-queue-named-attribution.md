# Shared Queue Enhancement: Phase 5B-4.6, Named-Employee Attribution Reporting

Date: 2026-09-29. **Status: APPROVED SPECIFICATION (decisions D1-D8, 2026-09-29; see section 11).
Implemented 2026-09-29 as `backend/queueing_engine/simulation/shared_named_attribution.py`, with tests
in `tests/test_shared_named_attribution.py` (section 12). Committed locally only; not pushed, merged,
or deployed.**

Plan: `docs/superpowers/plans/2026-09-29-shared-queue-named-attribution-plan.md`.

This document separates these kinds of statement:

- **VERIFIED** statements describe the repository at `5a9738e2` (branch `feat/shared-queue-segments`)
  or the output of scratch probes run on it. Each cites its source.
- **APPROVED SPECIFICATION** statements are the 5B-4.6 contract.
  - The contract was first proposed in the 2026-09-29 specification request.
  - The product owner approved it in the 2026-09-29 follow-up request, through decisions D1-D8
    (section 11). That request replaced the originally proposed D7 rule.
  - None of it was approved before 2026-09-29.
  - Approval is not implementation. At approval no code or test for 5B-4.6 existed; the implementation
    that followed is recorded in section 12.
- **PROPOSED** now marks only statements outside the approved contract, for example the note in
  section 9 on how 5B-5 might use these records.

Related specs: `2026-09-28-shared-queue-named-employee-des-policy.md` (policy contract, P1-P9),
`2026-09-28-shared-queue-employee-state-machine.md` (state machine v3),
`2026-09-28-shared-queue-named-des.md` (engine v3), `2026-09-28-shared-queue-named-replications.md`
(method v2), and `2026-09-28-shared-queue-named-playback.md` (playback v3).

## 1. What the repository defines for 5B-4.6 (VERIFIED)

The repository names the phase and lists its open selections. No earlier spec, plan, test, or commit
defines its scope.

| Source | Content |
|---|---|
| Policy spec, line 19-20 | The sub-phase list comes from the "Phase 5B-4A design", a chat report that "is not a repository file". |
| Policy spec, P8 row (line 396) | Names "5B-4.6 (attribution reporting)" as the sub-phase that needs P8. |
| Policy spec, P9 row (line 397) | "Per employee and shift, record quantities only: break delay, break shortening or loss, shift overrun, time after closing, and time waiting for a register. No cost is attached. Which quantity counts as paid overtime belongs to 5B-5, not here." Base elapsed-time states are mutually exclusive, and descriptive attributes never create duplicate elapsed time. Open: "How 5B-4.6 reports a minute that carries both attributes, for example as a separate 'overrun after closing' quantity." |
| Policy spec, open selections (line 491) | "5B-4.6 attribution quantities: P2 threshold (if chosen), P8 reporting, P9 reporting of a minute with both attributes". The table calls its own mapping INFERRED. |
| Named-DES spec, line 457 | 5B-4.6 and 5B-5 "are not started. None may begin without explicit approval." |
| `handoff.md` lines 778, 821, 843, 864 | "Next (needs explicit approval): 5B-4.6 attribution reporting, 5B-5 workforce cost, an acceptance rule, and API or UI exposure." |

### P2 (VERIFIED: no threshold)

- Policy spec, P2 row (line 390): "Decided 2026-09-28 (5B-4.3): record the actual delay only; no
  threshold." The row names no sub-phase that still needs P2.
- Policy spec, line 76 quotes the 5B-4.3 request: "Record actual break delay only. No hard delay
  threshold. No pre-break cutoff."
- Code: `APPROVED_EMPLOYEE_POLICY.break_delay == "record_actual_delay_only"` (`shared_named_des.py:98`),
  meaning "there is no delay threshold" (line 124).
- Named-DES spec, lines 366-368: `delay` is measured from the scheduled start, and `due` is recorded,
  "so the delay from the due time is `actual_start - due`".

**CONFLICTING (documentation only).** The open-selections entry "P2 threshold (if chosen)" is stale:
the threshold option was decided as "none". The entry should be corrected when the implementation is
approved (section 10). 5B-4.6 introduces no threshold.

### P8 (VERIFIED: implemented upstream)

- The six series, the two separate gaps, and the per-segment, horizon, before-opening, and
  after-closing windows are implemented. See `_staffing` (`shared_named_des.py:524-622`) and the
  named-DES spec, lines 212-227.
- The before-opening window shape and the timeline's extension to the last scheduled shift end are
  INFERRED (`shared_named_des.UNDETERMINED`, lines 203-205).
- The P8 row's mapping to 5B-4.6 is stale in the same way as the P2 entry.

### Existing per-employee and run-level quantities (VERIFIED)

Source: the employee timeline record, `EmployeeTimeline._record` (`shared_employee_states.py:720-779`).
It sits in every named result as `result["employee_timeline"]` (`shared_named_des.py:685`), and
`max_trace_events` does not truncate it.

- **`intervals`**: `employee_id`, `start`, `end`, `state` (one of the seven base states), `register_id`,
  `shift_index`, `after_closing`, and `past_scheduled_end` (lines 419-428).
  - `after_closing` is the machine's `closed` flag when the interval is flushed.
  - `past_scheduled_end` is `shift is not None and shift.end_reached`.
  - Every employee is flushed at closing (lines 654-657), and an employee is flushed at the shift's
    scheduled end (line 520). So no interval straddles closing or its own shift's scheduled end.
- **`shifts`**: `employee_id`, `shift_index`, `scheduled_start`, `scheduled_end`, `activated`,
  `actual_start`, `activation_delay = actual_start - scheduled_start`, `release`, `release_trigger`,
  `release_basis`, `overrun = max(0, release - scheduled_end)`, and `not_activated_reason`. The
  duration fields are `None` when the shift is not activated.
- **`breaks`**: `employee_id`, `shift_index`, `name`, `paid`, `duration_minutes`, `scheduled_start`,
  `due`, `actual_start`, `actual_end`, `delay = actual_start - scheduled_start`, `outcome` (`completed`,
  `truncated_by_closing`, or `unfulfilled`), and `unfulfilled_cause` (`released`,
  `shift_not_activated`, or `cancelled_at_closing`; `shared_named_replications.UNFULFILLED_CAUSES`).
- **`state_totals`**: per employee and base state. This is per employee, not per shift.
- **Shift identity.** `shift_index` is the position of the shift in the input roster (`enumerate(roster)`,
  `shared_workforce.py:552`). It is therefore unique across the whole roster, and
  `(employee_id, shift_index)` identifies a shift.
- **Break identity.** `evaluate_roster` reports duplicate break names within a shift as the
  `BREAK_DUPLICATE` violation (`shared_workforce.py:432-433`), and the X4 precondition rejects an
  INVALID roster (`shared_employee_states.py:276-277`). So `(employee_id, shift_index, name)`
  identifies a break in any run the engine accepts.
- **Run-level totals already exist per replication.** `named_replication_row(...)["employees"]`
  (`shared_named_replications.py:284-315`) reports `overrun_hours_total`, `break_delay_hours_total`,
  `employee_hours_by_state`, and `employee_hours_after_closing_by_state` (which includes OFF time), among
  others. `aggregate_named_replications` summarizes them descriptively with `verdict: None` (line 414).
- **Named DES convention.** The engine always runs with `hold_past_shift_end=True`
  (`shared_named_des.py:316`). After closing, a release comes only from a P5 or P6 Release input.
- **Units.** Everything is in hours from the horizon start. Output names carry `_hours`, as in
  `wait_hours`, `duration_hours`, and `overrun_hours_total`.
- **Tolerance.** The house tolerance is `{"rel": 1e-9, "abs": 1e-12}` (`shared_named_playback.TOLERANCE`,
  line 227).
  - Playback applies it to float sums only; times compare exactly.
  - Its form is `math.isclose(a, b, rel_tol=TOLERANCE["rel"], abs_tol=TOLERANCE["abs"])` (`_close_enough`,
    lines 266-267).
  - 5B-4.6 uses the same constant, with no new one, for its reconciliation checks and the D7 rule
    (section 3).
- **Versions.** Module versions follow `novaq-shared-<module>-vN`: named DES v3, state machine v3,
  replications method v2, playback v3.

### Scratch probe evidence (VERIFIED in this runtime only; scripts not committed)

The probes ran on Python 3.13.13 and numpy 2.4.6 with `PYTHONDONTWRITEBYTECODE`. They used the
synthetic scenarios of `tests/test_shared_named_replications.py`: 10 scenarios × 2 closing policies ×
25 replications, root entropy 20260929, so 500 runs. The working tree was unchanged afterwards.

- **0 violations** of each of these:
  - `shift_index is None` if and only if `state == "OFF"`;
  - `shift_index` unique across the roster;
  - an activated shift's intervals are contiguous and span exactly `[actual_start, release)`;
  - no activated shift without intervals, and no interval on a non-activated shift;
  - after-closing geometry, in both directions;
  - past-end geometry, in both directions;
  - on-duty sum ≈ `release - actual_start`;
  - past-end hours ≈ `overrun`;
  - ON_BREAK hours ≈ the started breaks' actual lengths;
  - break `delay >= 0` and `actual_start >= due`;
  - completed break length ≈ configured length;
  - non-OFF `state_totals` ≈ the sum over the employee's shifts;
  - per employee, the sum of `state_totals` ≈ `finish - begin` (800 employee timelines).
- **Observed:**
  - intervals carrying both flags: 5068;
  - after-closing only: 6;
  - past-end only: 246;
  - on-shift register-wait intervals: 50;
  - truncated breaks with zero shortening (a break ending exactly at closing): 44;
  - unfulfilled breaks: only `cancelled_at_closing`, so `released` and `shift_not_activated` need
    prescribed cases.
- **Float finding.** For 12 of 398 completed breaks, `(duration_minutes / 60) - (actual_end - actual_start)`
  was ±2.22e-16 rather than 0. Six of these were negative. Computing "shortening" by subtraction would
  therefore create shortening, including negative values, that the engine never produced. Section 2.4
  avoids this for completed breaks, and the D7 rule (section 3) covers derived durations in general.
- The eight hand cases in section 6 were derived by hand and then matched against the engine's raw
  records. Every value matched.

## 2. Contract (APPROVED SPECIFICATION, 2026-09-29; implemented, see section 12)

### 2.1 Objective and boundary

- 5B-4.6 derives auditable, per-shift operational attribution quantities from one existing
  named-employee DES result.
- It is a pure read of `result["employee_timeline"]` plus the authoritative input employees. It
  changes none of the following:
  - customer simulation, employee transitions, scheduling, breaks, or closing;
  - stochastic inputs;
  - staffing optimization or rostering;
  - any P8 quantity.
- It reports quantities only. It attaches no wage, overtime pay, penalty, waiting cost, break
  compensation, or after-closing cost. It does not decide whether any quantity is paid (5B-5).
- The breaks' `paid` input flag is **not** carried into the attribution output (D5, approved). That
  keeps pay meaning out. The engine record keeps the flag unchanged for future 5B-5 logic.
- The attribution does not interpret paid or unpaid time, payroll, overtime compensation, break
  compensation, or any monetary consequence. Those remain Phase 5B-5 scope.

### 2.2 Interface (APPROVED SPECIFICATION)

- New module: `backend/queueing_engine/simulation/shared_named_attribution.py`.
  - `ATTRIBUTION_VERSION = "novaq-shared-named-attribution-v1"`.
  - `build_named_attribution(result, employees) -> dict`:
    - `result` is a `simulate_named_prescribed` or `simulate_named_replication` result;
    - `employees` is the run's input `Sequence[Employee]`, the authoritative employee set;
    - neither argument has a default.
  - `NamedAttributionError(failure)`, where `failure = {"check", "message", "evidence"}`. This follows
    the pattern of `NamedPlaybackError`.
  - `CHECKS`, `DEFINITIONS`, and `UNDETERMINED` dictionaries, in house style.
- **Determinism.** No random numbers. The input is never mutated. The same input gives the same output.
- **Stale sources are refused.** `result["provenance"]["engine_version"]` must equal `NAMED_ENGINE_VERSION`,
  and `state_machine_version` must equal `STATE_MACHINE_VERSION`. Otherwise the call fails with check
  `source_versions`.
- **The customer trace is not used.** A truncated trace (`max_trace_events`) does not matter.
- **No repair.** Any failed check raises with evidence.
  - The source result is never altered.
  - No source timestamp or interval is normalized, snapped, or rounded.
  - The only normalization anywhere is the approved D7 rule for derived durations (section 3): a
    derived duration that is within tolerance below zero is reported as `0.0`.
- **Provenance (D4, approved).**
  - `inputs_sha256` is `None`, and `inputs_sha256_reason` says why: the full run inputs are
    unavailable to `build_named_attribution`, which receives only the result and the input employees.
  - The 5B-4.5 digest needs the complete simulation-defining input snapshot, so no partial digest is
    computed or labeled as the canonical run-input digest.
  - The available provenance is recorded separately, as the schema in section 4 shows:
    - engine and state-machine versions (`provenance`);
    - employee identity (the `employees` records, checked against the input employees);
    - replication identity (`provenance.replication`).

### 2.3 Primary granularity (APPROVED SPECIFICATION)

- The primary record is **one employee × one shift × one run**. Records keep the engine's
  `employee_timeline.shifts` order: employee_id, then scheduled start.
- A per-employee summary is derived by summing that employee's activated-shift records. The run's OFF
  time is not attributed to any shift.
- **Out of scope:**
  - cross-replication aggregation;
  - percentiles, confidence intervals, cross-replication means;
  - acceptance thresholds or PASS/FAIL verdicts.

  No repository source requires any of these for 5B-4.6. The existing 5B-4.4 run-level aggregation
  and its `verdict: None` are unchanged.

### 2.4 Quantities and their derivation (APPROVED SPECIFICATION)

The index sets are defined as follows. `I(e, s)` is the set of intervals with `employee_id == e` and
`shift_index == s`. `|x| = end - start`. Every sum is `math.fsum`.

- **Units (D1, approved).** Hours are the domain unit, and every output duration field ends in
  `_hours`. The only source-unit field is `configured_minutes`, copied from the engine's
  `duration_minutes` and named for its unit. Minutes belong only to later display conversion.
- **Derived durations.** Every duration computed as a difference `a - b` is reported under the D7 rule
  (section 3).
- **`_total` (D2, approved).** The suffix means a sum across several breaks, at shift or
  employee-summary level. No per-break field is a total.

**Shift timing**

| Field | Derivation | Not activated |
|---|---|---|
| `scheduled_start_hours`, `scheduled_end_hours` | copied from `scheduled_start`, `scheduled_end` | copied |
| `scheduled_duration_hours` | `scheduled_end - scheduled_start`, under the D7 rule | computed |
| `actual_start_hours`, `release_hours` | copied from `actual_start`, `release` | `None` |
| `release_trigger`, `release_basis`, `not_activated_reason` | copied | copied |
| `activation_delay_hours` | copied from `activation_delay`; checked `== actual_start - scheduled_start` exactly, after the exact order check `actual_start >= scheduled_start` (section 3) | `None` |
| `overrun_hours` | copied from `overrun`; checked `== max(0.0, release - scheduled_end)` exactly | `None` |
| `on_duty_hours` | `fsum(|x| for x in I(e, s))` | `None` |
| `hours_by_state` | for each of the six on-duty base states (OFF excluded): `fsum(|x|)` over `I(e, s)` with that state | `None` |
| `register_wait_hours` | `hours_by_state["WAITING_FOR_REGISTER"]` | `None` |

**Closing and shift-end attribution (the P9 overlap rule)**

`after_closing` and `past_scheduled_end` are independent annotations of on-shift intervals. Each
on-shift interval falls into exactly one of four disjoint cells, and each cell is summed **directly**
over its intervals, never by subtraction:

| Field | Intervals in `I(e, s)` |
|---|---|
| `neither_hours` | not after closing, not past end |
| `after_closing_only_hours` | after closing, not past end |
| `past_scheduled_end_only_hours` | past end, not after closing |
| `after_closing_and_past_scheduled_end_hours` | both |
| `after_closing_hours` | after closing (either past-end value) |
| `past_scheduled_end_hours` | past end (either after-closing value) |
| `after_closing_or_past_scheduled_end_hours` | either flag |

All seven fields are `None` for a non-activated shift. For an activated shift they are always numbers
(`0.0` when no interval qualifies; that zero is established from the shift's full interval set).

- **Direct summation (D3, approved).** Every one of the seven fields is summed directly over its
  intervals. No primary value is derived by subtracting overlapping totals.
  - The original request's formula `after_closing_only = after_closing - both` is mathematically equal
    but not used. Direct summation of positive terms cannot produce a negative or residual value from
    float cancellation.
  - The subtraction and union formulas are reconciliation identities only (section 3,
    `closing_partition`).
- OFF time after closing belongs to no shift. It is not in these fields.
- No field is called overtime, paid, or unpaid. `past_scheduled_end_hours` and `overrun_hours` are
  descriptive durations.

**Breaks.** There is one record per scheduled break of the shift, in the engine's order (planned
start). Identity is `(employee_id, shift_index, name)`.

| Field | completed | truncated_by_closing | unfulfilled |
|---|---|---|---|
| `configured_minutes` (copied from `duration_minutes`) | copied | copied | copied |
| `configured_hours` | `configured_minutes / 60.0` | same | same |
| `scheduled_start_hours`, `due_hours` | copied | copied | copied (`due` may be `None`) |
| `actual_start_hours`, `actual_end_hours` | copied | copied | `None` |
| `outcome`, `unfulfilled_cause` | copied | copied | copied |
| `delay_from_scheduled_hours` | the engine's `delay`, checked `== actual_start - scheduled_start` exactly; reported under the D7 rule | same | `None` |
| `delay_from_due_hours` | `actual_start - due`, after the exact order check `actual_start >= due`; reported under the D7 rule | same | `None` |
| `actual_hours` | `actual_end - actual_start`, after the exact order check `actual_start < actual_end`; reported under the D7 rule | same | `None` |
| `shortened_hours` | `0.0` by P1 (full configured duration), not computed by subtraction; `actual_hours` checked ≈ `configured_hours` within tolerance | `configured_hours - actual_hours`, reported under the D7 rule (section 3) | `None` (never started) |
| `unfulfilled_hours` | `0.0` | `0.0` | `configured_hours` |

- **Two delay fields (D2, approved).** Both are per-break durations with distinct meanings. Neither is
  a total, and neither sets a threshold.
  - **`delay_from_scheduled_hours`** is measured from the roster's planned break start: the break's
    actual start minus its scheduled start. It is the engine's `delay`, which is P2's recorded delay
    (VERIFIED). It includes every reason the break started after its planned time:
    - a delayed split-shift activation, which moves the break's due time by P3 (hand case H4: the
      whole 0.625 h);
    - the minimum-gap push of a later break (P1; the existing `test_pushed_second_break`,
      `tests/test_shared_named_des.py:404`: "second" was scheduled 1.75, due 2.0, started 2.0, delay
      0.25);
    - waiting for a service to finish.
  - **`delay_from_due_hours`** is measured from the instant the break fell due: the break's actual
    start minus its due time. The named-DES spec, lines 366-368, already names it as derivable.
    - A due break starts at once unless the employee is serving. When the employee is serving, the
      break starts at that service's completion (`shared_employee_states.py`, `_break_due` from line
      542; `_complete`, line 515).
    - So this field is the part of the delay caused by the service under way (VERIFIED from code). In
      the gap-push example it is 0.0.
- **Completed breaks.** `shortened_hours` is 0.0 by P1 (a completed break lasts its full configured
  duration), not computed by subtraction. This follows the float finding in section 1: subtraction
  gives ±2.22e-16 on 12 of 398 completed breaks. The `actual_hours ≈ configured_hours` comparison is a
  reconciliation check (section 3), not the D7 rule.
- **Unfulfilled breaks.**
  - `unfulfilled_hours` is the configured length of a break not taken. The cause is kept beside it, so
    `shift_not_activated`, `released`, and `cancelled_at_closing` stay distinguishable.
  - Whether any of these is a "loss" for pay purposes is a 5B-5 question.

**Per-shift break totals.** For each activated or non-activated shift:

- `breaks_scheduled`, `breaks_completed`, `breaks_truncated_by_closing`, and
  `breaks_unfulfilled_by_cause` (all three causes, including zero counts);
- `delay_from_scheduled_hours_total`, `delay_from_due_hours_total`, and `actual_break_hours_total`
  (fsum over started breaks);
- `shortened_hours_total` (fsum over started breaks);
- `unfulfilled_hours_total` (fsum over unfulfilled breaks).

**Per-employee summary.** One summary per input employee, in `employee_id` order:

- `shift_count` and `activated_shift_count`;
- fsum over the employee's **activated** shifts of every per-shift duration field and each
  `hours_by_state` entry;
- break counts and totals over all of the employee's shifts;
- `off_hours`, copied from `state_totals[e]["OFF"]`.

For an employee with no activated shift, the duration sums are 0.0. That zero is established, not
assumed: the reconciliation requires the employee's non-OFF `state_totals` to be ≈ 0.

### 2.5 Per-shift allocation rule (VERIFIED feasible; APPROVED SPECIFICATION as the rule)

- An interval belongs to shift `(e, s)` if and only if its `employee_id == e` and `shift_index == s`.
  Allocation is exact: no proportional or heuristic split.
- VERIFIED (sections 1 and 6):
  - every on-duty interval carries its shift's index;
  - OFF intervals carry `None`;
  - no interval straddles closing or its shift's scheduled end;
  - the probe found 0 exceptions in 500 runs.
- **Register waiting is NOT blocked for per-shift attribution.** WAITING_FOR_REGISTER intervals carry
  `shift_index`. The concern in the request, that only per-employee totals exist, does not apply,
  because the intervals are already per shift.
- The implementation must still **check** the allocation preconditions (section 3) on every input and
  fail if one does not hold. It must not trust them.

### 2.6 Closing boundary (APPROVED SPECIFICATION)

- DRAIN and HARD_CUTOFF are not redefined. Attribution uses the engine's own flags and instants, which
  follow the approved P5, P6, P7, and X2 rules.
- There is no event-time epsilon and no rounding. Times compare exactly. The house tolerance is used
  only for:
  - the reconciliation checks, marked "≈" in section 3;
  - the D7 rule for derived durations (section 3).

  It is never used for event ordering or timing comparisons (the D7 boundary, section 3).
- Before-opening attribution (an interval with `start < 0`) is **out of scope**. It gets no separate
  field; such time is ordinary on-duty time in `hours_by_state`. The P8 before-opening window shape
  stays INFERRED and is not revisited.

### 2.7 P8 relationship (APPROVED SPECIFICATION)

- No P8 series, gap, or window is recomputed, re-exposed, or redefined. The attribution result does
  not copy `result["staffing"]`; callers read it from the named result.
- No new gap formula.

### 2.8 Replications (APPROVED SPECIFICATION)

- `build_named_attribution` accepts a `simulate_named_replication` result. It copies that result's
  identity into provenance: `seed_entropy`, `spawn_key`, and `customer_inputs.sha256`.
- `run_named_replications` rows and `aggregate_named_replications` are **unchanged**:
  - the replication rows stay protected and summary-only;
  - replications method v2 and the row shape are unchanged. Adding attribution to the rows would change
    the v2 row contract.
- **D6, approved.** 5B-4.6 creates no new replication runner or helper. To attribute replication i:
  1. regenerate it through the existing, protected 5B-4.4 seed and regeneration path,
     `simulate_named_replication(..., seed_sequence=replication_seed_sequence(root_entropy, i))`;
  2. take the resulting named-DES result;
  3. call `build_named_attribution` on it.
- No runner mirroring `playback_from_named_replications`' refusal checks is added: it would duplicate or
  refactor protected playback logic.
- No aggregation across replications is added (section 2.3).

## 3. Validation checks (APPROVED SPECIFICATION: `CHECKS`)

Each check fails with its code and evidence. Membership values are tested as strings or finite reals
**before** any hashing, so a malformed value fails its check instead of raising `TypeError`. This is the
5B-4.5 hardening lesson.

| Check | Rule |
|---|---|
| `source_versions` | engine and state-machine versions equal the current constants |
| `record_structure` | the timeline has `begin`, `finish`, `closing_time`, `intervals`, `shifts`, `breaks`, and `state_totals` with the engine's field names; times are finite reals (not bool); `shift_index` is an int (not bool) or `None`; flags are bool |
| `employee_identity` | `employees` is a list or tuple of `Employee`; the `state_totals` keys are strings equal to the input ids (exact, case-sensitive); every interval, shift, and break names one of them |
| `shift_identity` | `(employee_id, shift_index)` is unique across shifts; every non-`None` interval `shift_index` names a shift of the same employee; every break names a shift of the same employee; break names are unique within a shift |
| `interval_geometry` | per employee, intervals are contiguous from `begin` to `finish` with `end > start` (exact); `shift_index is None` if and only if `state == "OFF"`; `after_closing` if and only if `start >= closing_time`; on shift `s`, `past_scheduled_end` if and only if `start >= s.scheduled_end`; OFF intervals are never past end |
| `shift_reconciliation` | activated: `actual_start >= scheduled_start` (exact); intervals span exactly `[actual_start, release)`; `activation_delay` and `overrun` equal the source formulas exactly; `on_duty_hours ≈ release - actual_start`; `past_scheduled_end_hours ≈ overrun`. Not activated: no intervals, and `actual_start`, `release`, and `overrun` are `None` |
| `closing_partition` | `neither + ac_only + pe_only + both ≈ on_duty`; `after_closing ≈ ac_only + both`; `past_scheduled_end ≈ pe_only + both`; `union ≈ after_closing + past_scheduled_end - both`; `both <= after_closing` and `both <= past_scheduled_end` exactly (fsum of a subset of positive terms) |
| `base_state_partition` | the fsum of `hours_by_state` values ≈ `on_duty_hours` |
| `break_reconciliation` | outcome and cause come from the engine's vocabularies; started if and only if outcome ≠ unfulfilled; `delay` equals `actual_start - scheduled_start` exactly; `actual_start >= due` (exact); started: `actual_start < actual_end` (exact); completed: `actual_hours ≈ configured_hours`; truncated: `actual_end == closing_time` exactly, and `shortened_hours` comes from the D7 rule; the shift's ON_BREAK hours ≈ its `actual_break_hours_total` |
| `employee_reconciliation` | for each non-OFF state, the sum over the employee's shifts ≈ `state_totals[e][state]`; the fsum of `state_totals[e]` ≈ `finish - begin` |
| `finite_nonnegative` | every derived duration passes the D7 rule below (a failure is reported here with evidence), and every output duration is a finite float ≥ 0, or `None` where section 2.4 says `None` |

"≈" means `math.isclose` with the house tolerance (`rel 1e-9`, `abs 1e-12`). An output
`reconciliation` list records, for each identity, whether it is compared `exact` or with `tolerance`, as
the playback does.

### The D7 rule for derived durations (approved 2026-09-29)

**Scope.** The rule covers every duration `x = a - b` that the attribution computes by subtraction and
whose true value is mathematically nonnegative:

- `scheduled_duration_hours`;
- `delay_from_scheduled_hours`;
- `delay_from_due_hours`;
- `actual_hours`;
- a truncated break's `shortened_hours`.

**The rule.** "Tolerance" is the existing house tolerance. No new constant is introduced. It is
applied to the two operands, as playback's `_close_enough(a, b)` applies it, so
`tolerance = max(1e-9 * max(|a|, |b|), 1e-12)`.

| Computed `x` | Reported value |
|---|---|
| `x >= 0` | `x`, as computed |
| `-tolerance <= x < 0`, that is `a < b` and `math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)` | `0.0`. The tiny negative is not retained |
| `x < -tolerance` | validation **fails** under `finite_nonnegative`, with evidence: the field, the record identity, `a`, `b`, `x`, and the tolerance |

**What the rule does not do:**

- It changes no source record. For example, the engine's `delay` stays as recorded; only the
  attribution's `delay_from_scheduled_hours` goes through the rule.
- It never changes a source timestamp or interval.
- It adds no residual or round-off output field. No repository convention requires one.
- It does not adjust a tiny positive `x`, which is reported as computed.
- It does not cover copied source durations whose nonnegativity is exact. `finite_nonnegative` still
  checks them:
  - `activation_delay_hours`, after its exact order check;
  - `overrun_hours`, which is the engine's `max(0.0, ...)`;
  - `off_hours`, a sum of interval lengths.

  `delay_from_scheduled_hours` is covered, because no exact order check establishes it (see below).
- Sums of interval lengths, and every `_total` and per-employee sum, are sums of positive or
  nonnegative terms. They are nonnegative without the rule.

**Boundary.** The tolerance is never used for any of the following:

- DES event ordering or same-time event sequencing;
- roster boundaries;
- shift start or end comparisons;
- closing-time comparisons;
- break due, start, or end ordering;
- employee-state transition timing;
- deciding whether one raw event occurred before or after another.

These keep the repository's exact timing semantics. So every exact check in the table above stays
exact:

- interval contiguity and `end > start`;
- the `after_closing` and `past_scheduled_end` geometry;
- `actual_start >= scheduled_start` for shifts;
- `actual_start >= due`;
- `actual_start < actual_end`;
- `actual_end == closing_time`.

When a derived duration's operands are two instants with an exact order check (`delay_from_due_hours`
and `actual_hours`), that check runs first, and a violation fails with no tolerance. The difference is
then already ≥ 0, so the D7 branch cannot trigger. The attribution runs no DES and alters no event
order; it applies the rule only to its own derived output values.

**Where the rule can matter (NOT TESTED whether it ever triggers):**

- **A truncated break's `shortened_hours`.** Its operands are `configured_hours` (from whole minutes)
  and `actual_hours`, and mathematically the break's planned end is at or after closing. The probe
  observed 0 negative values in 96 truncated breaks.
- **`delay_from_scheduled_hours`.** The engine never compares a break's actual start with its scheduled
  start: `_due_time` (`shared_employee_states.py`, lines 357-371) places a delayed shift's breaks by
  `_plus` from the actual shift start. The probe observed 0 negative delays.

## 4. Output schema (APPROVED SPECIFICATION)

```text
{
  "shifts": [                                  # one per roster shift, engine order
    {
      "employee_id": str, "shift_index": int, "activated": bool,
      "not_activated_reason": str | None, "release_trigger": str | None, "release_basis": str | None,
      "scheduled_start_hours": float, "scheduled_end_hours": float, "scheduled_duration_hours": float,
      "actual_start_hours": float | None, "release_hours": float | None,
      "activation_delay_hours": float | None, "overrun_hours": float | None,
      "on_duty_hours": float | None,
      "hours_by_state": {<6 on-duty base states>: float} | None,
      "register_wait_hours": float | None,
      "closing_attribution": {
        "after_closing_hours", "past_scheduled_end_hours",
        "after_closing_and_past_scheduled_end_hours",
        "after_closing_only_hours", "past_scheduled_end_only_hours",
        "neither_hours", "after_closing_or_past_scheduled_end_hours": float
      } | None,
      "breaks": [ {
        "name": str, "configured_minutes": int, "configured_hours": float,
        "scheduled_start_hours": float, "due_hours": float | None,
        "actual_start_hours": float | None, "actual_end_hours": float | None,
        "outcome": str, "unfulfilled_cause": str | None,
        "delay_from_scheduled_hours": float | None, "delay_from_due_hours": float | None,
        "actual_hours": float | None, "shortened_hours": float | None, "unfulfilled_hours": float
      } ],
      "break_totals": {
        "breaks_scheduled": int, "breaks_completed": int, "breaks_truncated_by_closing": int,
        "breaks_unfulfilled_by_cause": {"released": int, "shift_not_activated": int,
                                        "cancelled_at_closing": int},
        "delay_from_scheduled_hours_total": float, "delay_from_due_hours_total": float,
        "actual_break_hours_total": float, "shortened_hours_total": float,
        "unfulfilled_hours_total": float
      }
    }
  ],
  "employees": [                               # one per input employee, employee_id order
    { "employee_id": str, "shift_count": int, "activated_shift_count": int, "off_hours": float,
      <fsum over activated shifts of every duration field, hours_by_state, and closing_attribution cell>,
      "break_totals": <same shape, over all of the employee's shifts> }
  ],
  "reconciliation": [ {"identity": str, "method": "exact" | "tolerance"} ],
  "definitions": {...}, "checks": {...}, "undetermined": [...],
  "provenance": {
    "attribution_version": "novaq-shared-named-attribution-v1",
    "named_engine_version": str, "state_machine_version": str,
    "closing_policy": "DRAIN" | "HARD_CUTOFF",
    "begin_hours": float, "closing_hours": float, "finish_hours": float,
    "replication": {"seed_entropy", "spawn_key", "customer_inputs_sha256"} | None,
    "source": "result['employee_timeline'] only; no customer trace; nothing synthesized",
    "time_unit": "hours from the horizon start",
    "tolerance": {"rel": 1e-9, "abs": 1e-12,
                  "applies_to": "reconciliation checks and the D7 derived-duration rule only; "
                                "times and event order compare exactly"},
    "monetary_cost": "None: quantities only; pay and cost are Phase 5B-5",
    "inputs_sha256": None,
    "inputs_sha256_reason": "full run inputs unavailable: build_named_attribution receives only the "
                            "result and the input employees, and no partial digest is computed (D4)"
  }
}
```

The output holds no intervals, transitions, or customer trace, so its size grows with shifts plus
breaks plus employees. Every value can be rebuilt from the named result.

**Units (D1, approved 2026-09-29).** Hours are the domain unit.

- Every output duration field ends in `_hours`.
- `configured_minutes` is the one field copied in its source unit, and it is named for that unit.
- The original request said "minutes". Hours were approved because:
  - hours are the engine's unit (VERIFIED), and converting would add ×60 float values and a second
    unit inside the domain layer;
  - `AGENTS.md` makes minutes a report display rule ("multiply hour-valued Wq by 60 at display time").
    Minutes therefore belong only to a later display or presentation conversion.

**Omitted fields.** The engine break record's `paid` flag is not in the schema (D5).

## 5. Reconciliation rules (APPROVED SPECIFICATION)

These rules apply to each activated shift `(e, s)` and each employee `e`. Every one is a runtime check
(section 3) and is also tested.

1. `on_duty = Σ_{x∈I(e,s)} |x| ≈ release - actual_start`, and the intervals exactly tile
   `[actual_start, release)`.
2. `Σ_state hours_by_state[state] ≈ on_duty`. Base states never overlap, because each interval has
   exactly one state.
3. `neither + ac_only + pe_only + both ≈ on_duty`. The four cells partition the on-duty time.
4. `after_closing ≈ ac_only + both`, `past_scheduled_end ≈ pe_only + both`,
   `|AC ∪ PE| = union ≈ after_closing + past_scheduled_end - both`. Raw `after_closing` and raw
   `past_scheduled_end` are never added as elapsed time without subtracting `both`.
5. `both <= min(after_closing, past_scheduled_end)`, compared exactly.
6. `past_scheduled_end ≈ overrun`. VERIFIED on the probe and on hand cases H1-H8.
7. The shift's ON_BREAK hours ≈ `Σ actual_hours` over its started breaks.
8. `Σ_{s of e} hours_by_state[state] ≈ state_totals[e][state]` for every non-OFF state, and
   `Σ_state state_totals[e][state] ≈ finish - begin`.
9. Per employee, every summed field equals the fsum of that field over the employee's activated shifts
   (or all shifts, for break totals). This holds by construction and is checked in tests.
10. Tests only: the attribution reconciles with the existing 5B-4.4 row, `named_replication_row(...)`
    `["employees"]`:
    - `overrun_hours_total ≈ Σ overrun_hours`;
    - `break_delay_hours_total ≈ Σ delay_from_scheduled_hours`;
    - `employee_hours_by_state[state] ≈ Σ_e hours_by_state[state]` for every non-OFF state;
    - `employee_hours_after_closing_by_state[state]` for every non-OFF state equals an independent
      interval sum.

## 6. Hand cases (derived by hand; each value matched the engine's raw records in the scratch probe)

The hand cases use `tests/test_shared_named_des.py` conventions: horizon 08:00-12:00 (0-4 h), μ = 4 per
hour, and service time = work / 4.

| Case | Setup | Expected attribution (hours) |
|---|---|---|
| H1 DRAIN closing | `CLOSING_ROSTER`, `CLOSING_ARRIVALS`, DRAIN (existing test) | A (shift 0): on_duty 4.875; overrun 0.875; after_closing 0.875, past_end 0.875, **both 0.875**, ac_only 0, pe_only 0; break completed 0.5-1.0, delay_from_scheduled 0, delay_from_due 0, shortened 0. B (shift 1): on_duty 4.0; overrun 0; all closing cells 0; break truncated 3.75-4.0: delay_from_scheduled 0.25, delay_from_due 0.25, configured 0.5, actual 0.25, **shortened 0.25**. C (shift 2): not activated (`released_after_closing`), every duration `None` |
| H1b HARD_CUTOFF closing | as H1, HARD_CUTOFF | A: released 4.375, overrun 0.375, both 0.375. B as H1 |
| H2 shift end during service | A 08-10, B 10-12, two registers, arrivals (1.75, 2), (2.0, 2), (2.125, 0.5) | A: overrun 0.25, **past_end_only 0.25**, after_closing 0. B: on_duty 2.0, all cells 0 |
| H3 register handover | as H2 with one register, arrivals (1.75, 2), (2.125, 1) | B (shift 1): **register_wait 0.25** (2.0-2.25). A: past_end_only 0.25 |
| H4 delayed split shift | existing `test_delayed_split_shift` | A shift 0: overrun 0.625 (past_end_only). A shift 1: activation_delay 0.625, on_duty 1.375; break scheduled 2.0, due 2.625, actual 2.625-2.875: **delay_from_scheduled 0.625, delay_from_due 0.0** |
| H5 after closing only | A 08:00-13:00 (0-5 h), one register, arrival (3.75, 2), HARD_CUTOFF (the same values under DRAIN) | A: release 4.25, overrun 0, **after_closing_only 0.25**, past_end 0, both 0 |
| H6 break carried past shift end | A 08:00-10:30 with a 30-minute break at 10:00, arrival (1.75, 2) | break scheduled and due 2.0, delayed to 2.25-2.75 (delay_from_scheduled 0.25, delay_from_due 0.25, completed); release 2.75; overrun 0.25; past_end_only 0.25, spent ON_BREAK |
| H7 unfulfilled at release | as H6, arrival (1.75, 4) | service 1.75-2.75; overrun 0.25; break `unfulfilled`/`released`, due 2.0, **unfulfilled_hours 0.5**, delay_from_scheduled and delay_from_due both `None` |
| H8 split shift not activated | the H4 roster, arrival (0.5, 10) | shift 0: release 3.0, overrun 2.0. Shift 1: not activated (`rest_after_actual_release_reaches_scheduled_end`); its break `unfulfilled`/`shift_not_activated`, unfulfilled_hours 0.25 |

**Hand cases and D7.**

- The expected shortening values are exact dyadic results: H1 B 0.25 (truncated), and 0.0 for H1 A and
  H6 (completed, by P1).
- Each derived duration in these cases takes the D7 `x >= 0` branch.
- No hand case exercises the D7 zero branch or its failure branch. Section 7, item 6a tests them with
  synthetic records.

## 7. Required tests (APPROVED SPECIFICATION: `tests/test_shared_named_attribution.py`)

1. **Hand cases H1-H8.** Assert the exact values above against the attribution output. Dyadic inputs
   give exact floats.
2. **Individual situations:**
   - a single shift with no event: every closing cell 0.0, not `None`;
   - split shifts;
   - a delayed start;
   - an overrun;
   - after closing but not past end (H5);
   - past end but not after closing (H2);
   - both (H1);
   - register waiting (H3);
   - a delayed break (H6);
   - truncated (H1), unfulfilled `released` (H7), unfulfilled `shift_not_activated` (H8), and
     unfulfilled `cancelled_at_closing` (a pending break at closing);
   - a break ending exactly at closing: truncated with `shortened_hours == 0.0`;
   - a shift ending exactly at closing (H1 A);
   - HARD_CUTOFF and DRAIN.
3. **An unrostered employee** (in the input list, with no shift):
   - no shift records;
   - an employee summary with `shift_count == 0` and duration sums 0.0;
   - `off_hours == finish - begin`.
4. **Zero-attribution day.** On the stable day, every closing cell is 0.0, `overrun == 0`, and
   `register_wait == 0`. The distinction between `None` and 0.0 is asserted.
   - **Correction (implementation, 2026-09-29): a defect in this test example, not in the contract.** The
     seeded "stable" day (`SCENARIOS["stable"]`) is not a zero-attribution day.
   - VERIFIED: 24 of 25 replications (root entropy 20260929) have a nonzero overrun, after-closing time,
     or register wait under each closing policy. At closing someone is usually serving, so the approved
     DRAIN and HARD_CUTOFF rules give real after-closing and overrun time.
   - The test uses days that are zero by construction instead:
     - the seeded `SCENARIOS["zero_arrivals"]` (no demand; the break is taken on time; released at
       closing);
     - a prescribed quiet single shift.
   - The attribution contract is unchanged.
5. **Reconciliation.** Every identity in section 5 holds on each of the 10 synthetic scenarios × 2
   policies × at least 25 seeded replications. This includes the check against the unchanged
   5B-4.4 `named_replication_row`.
6. **Malformed inputs.** Each fails with its named check, never with a `TypeError`, and nothing is
   repaired:
   - an orphan employee in an interval, shift, or break;
   - a missing input employee, or an extra one;
   - a non-string or unhashable employee_id;
   - `shift_index` given as a bool or a string;
   - a duplicate shift key;
   - an interval naming an unknown shift;
   - an OFF interval carrying a shift, or an on-duty interval without one;
   - a gap or overlap between intervals;
   - a flipped `after_closing` or `past_scheduled_end` flag;
   - NaN or infinite times;
   - a tampered `overrun`, `activation_delay`, or `delay`;
   - a completed break with the wrong length;
   - a truncated break not ending at closing;
   - an unknown outcome or cause;
   - a version mismatch;
   - exact order violations, which fail even when they are tiny (for example off by 1e-15), because no
     tolerance applies to them:
     - a shift with `actual_start < scheduled_start`;
     - a break with `actual_start < due`;
     - a started break with `actual_end <= actual_start`.

6a. **The D7 rule.** Tested with synthetic operands and with tampered truncated-break records:
   - `x >= 0` is reported as computed;
   - `-tolerance <= x < 0` (for example a truncated break whose `actual_hours` exceeds
     `configured_hours` by 2.2e-16) is reported as exactly `0.0`, never as a negative value;
   - `x < -tolerance` fails under `finite_nonnegative`, with evidence;
   - the source result is unchanged in every case;
   - the output has no residual field;
   - the tolerance is the house tolerance applied to the operands.
7. **Purity:**
   - no random numbers are drawn (monkeypatched numpy and `random`, as the existing tests do);
   - the input result is unmodified (deep-copy equality);
   - two calls give equal output.
8. **Isolation.**
   - The module joins `SHARED_QUEUE_ENHANCEMENT_MODULES` in `tests/test_shared_segments.py`.
   - It imports no separate-queue break code.
   - Its tolerance equals `shared_named_playback.TOLERANCE`.
9. **Protected regression.** These run unchanged and must pass:
   - the named DES, state machine, replications, and playback suites;
   - the 5B-4.0 pin;
   - all `tests/test_shared_*.py`;
   - the Separate Queue files named in the policy spec.
10. **Fault injection.** Source-level mutants of the new module run on a scratch copy, following the
    5B-4.4 and 5B-4.5 practice. Survivors are either explained as equivalent or closed with tests.

**Gates:**

- `python -m pytest tests/ -x --tb=short`;
- `ruff check .`;
- `mypy . --exclude '^outputs/'` (plain `mypy .` has 5 known errors in the gitignored `outputs/`);
- `git diff --check`.

Frontend gates do not apply: no frontend file changes.

## 8. Protected scope

- **Unchanged files:**
  - `shared_employee_states.py`, `shared_named_des.py`, `shared_named_replications.py`,
    `shared_named_playback.py`, `shared_continuous_des.py`, and everything under `services/`;
  - the 5B-4.0 fixture;
  - all existing tests. The only exception is adding the module name to the isolation set.
- **Unchanged versions:** named DES v3, state machine v3, replications method v2, playback v3. Nothing
  is bumped, because none of their contracts changes.
- **Unchanged behavior:**
  - `employee_transitions_before`, canonical `inputs_sha256`, and the deterministic trace merge;
  - closing-policy, malformed, unhashable, and employee-identity validation;
  - DRAIN and HARD_CUTOFF semantics, X1, same-time ordering, and `verdict: None`;
  - Separate Queue.
- **Out of scope:**
  - API, database, scenarios, frontend, Decision, and Reports;
  - cost, pay, and overtime classification;
  - acceptance rules;
  - cross-replication statistics;
  - before-opening attribution.
- **Allowed files on approval:**
  - the new module and test file;
  - `tests/test_shared_segments.py` (isolation set only);
  - this spec and a plan;
  - the stale entries in the policy spec (section 10);
  - the named-DES spec's "next steps" line;
  - `handoff.md` and `memory.md`.
- **Completion boundary:** one local commit. No push, merge, or deploy.

## 9. Relationship to 5B-5

- **VERIFIED.** 5B-5 needs:
  - the X6 redefinition;
  - the overtime classification;
  - the pay consequence of unfulfilled or truncated breaks (P1);
  - a "D15 acceptance rule" (policy spec, line 492). D15 is not defined anywhere in the repository:
    UNKNOWN.
- **UNKNOWN.** Whether 5B-4.6 must come before 5B-5. No repository source states an order, and the
  handoff lists them as separate options.
- **PROPOSED.** 5B-5 may use these per-shift records, for example `past_scheduled_end_hours` or
  `unfulfilled_hours` by cause, as inputs to its own pay rules. 5B-4.6 neither decides nor constrains
  those rules.
- No evidence shows that 5B-4.6 was superseded or renumbered.

## 10. Repository conflicts and stale entries found

1. **CONFLICTING (documentation).** The policy spec's open-selections entry "P2 threshold (if chosen)"
   contradicts the P2 row and the code (no threshold). Correct it on implementation approval.
2. **Stale mapping.** The P8 row names 5B-4.6 as the sub-phase that needs P8, but P8 reporting is
   implemented (5B-4.3 and 5B-4.4). 5B-4.6 treats P8 as upstream. Correct it on approval.
3. **Definitional difference (not a defect).** The 5B-4.4 row's
   `employee_hours_after_closing_by_state` includes OFF time. The attribution's per-shift
   `after_closing_hours` covers on-shift time only. The two reconcile on the non-OFF states (section 5,
   rule 10).
4. **Request versus repository (resolved 2026-09-29):**
   - units: the original request said minutes, and the engine uses hours. Resolved by D1: hours.
   - exclusive fields: the original request said subtraction. Resolved by D3: direct sums, with the
     subtraction formulas as checks.
5. No repository source requires API or UI exposure in 5B-4.6, so the no-API/UI boundary conflicts with
   nothing.

## 11. Product-owner decisions (2026-09-29)

The product owner decided D1-D8 in the 2026-09-29 follow-up request. D7 replaced the rule this
document originally proposed, which was to fail on any negative truncated-break shortening. That rule
is withdrawn.

| ID | Question | Decision | Where applied |
|---|---|---|---|
| D1 | Units | APPROVED. Hours are the domain unit; output durations end in `_hours`; minutes belong only to later display conversion; `configured_minutes` stays in its source unit, named for it | §2.4, §4 |
| D2 | Break delay fields | APPROVED. Both `delay_from_scheduled_hours` and `delay_from_due_hours`, with distinct stated meanings. `_total` means a sum across breaks at shift or employee level; no per-break field is a total | §2.4, §4 |
| D3 | Exclusive closing cells | APPROVED. Buckets are summed directly from source intervals; no primary value comes from subtracting overlapping totals; subtraction and union formulas are reconciliation identities only | §2.4, §3, §5 |
| D4 | `inputs_sha256` in provenance | APPROVED. `inputs_sha256 = None` with an explicit reason (full run inputs unavailable); no partial digest is labeled canonical; versions, employee identity, and replication identity are recorded separately | §2.2, §4 |
| D5 | The breaks' `paid` flag | APPROVED. Excluded from the output; no paid, payroll, overtime, break-compensation, or monetary interpretation; the engine record keeps the flag for 5B-5 | §2.1, §4 |
| D6 | Replication runner helper | APPROVED. None. Regenerate through the protected 5B-4.4 path, then call `build_named_attribution`; replication rows, method v2, and row shape are unchanged; no aggregation across replications | §2.3, §2.8 |
| D7 | Tiny negative derived durations | APPROVED (replacement rule). The existing house tolerance, applied to the operands: `x >= 0` is reported as is; `-tolerance <= x < 0` is reported as `0.0`; `x < -tolerance` fails with evidence. It applies only to derived durations whose true value is nonnegative, and never to event ordering or timing comparisons, which stay exact | §2.2, §2.4, §2.6, §3, §4, §6, §7 |
| D8 | Approval of the whole specification | APPROVED, on condition that a final read-only review after the D1-D7 edits finds no internal contradiction. Review result: see below | whole document |

**Final read-only review (D8 condition), 2026-09-29.** Done after the D1-D7 edits.

- A search for the withdrawn D7 wording found only the withdrawal note above.
- The review found these wording inconsistencies. All were corrected before this record:
  - bare "delay" in hand cases H1, H6, and H7 (D2);
  - "float sums only" as the tolerance scope, in section 2.6 and the provenance string (the
    reconciliation checks also compare non-sums);
  - the playback tolerance note in section 1, now marked as describing playback;
  - whether copied source durations fall under D7.
- No internal contradiction remains. The D8 condition is met, and the specification is approved. It was
  not implemented at the time of the review.

## 12. Implementation record (2026-09-29)

Base `5a9738e2` (parent `086075f7`), branch `feat/shared-queue-segments`. Every statement below is
VERIFIED from the final tree or from runs on it, unless labeled otherwise.

### Files

- New: `backend/queueing_engine/simulation/shared_named_attribution.py`.
- New: `tests/test_shared_named_attribution.py`, with 46 test functions and 141 tests.
- Changed: `tests/test_shared_segments.py`. The module joins `SHARED_QUEUE_ENHANCEMENT_MODULES`, a
  one-line change.
- Docs:
  - this spec and the plan;
  - the policy spec's stale entries (section 10);
  - the named-DES spec's "next steps" line;
  - `handoff.md` and `memory.md`.
- Unchanged (`git diff 5a9738e2`):
  - the named engine, state machine, replications, playback, and continuous DES modules;
  - `services/`, the API, the database layer, and the frontend;
  - dependencies and fixtures.
- Unchanged versions: named DES v3, state machine v3, replications method v2, playback v3.
  `ATTRIBUTION_VERSION` is `novaq-shared-named-attribution-v1`.

### As implemented

- **Interface.** As specified in section 2.2:
  - `build_named_attribution(result, employees)`;
  - `NamedAttributionError(failure)` with `check`, `message`, and `evidence`;
  - `CHECKS`, with the 11 checks in spec order, plus `DEFINITIONS` and `UNDETERMINED`.
- **Additions beyond section 2.2.** None changes the contract.
  - `derived_duration(a, b, *, field)`: the D7 rule as a public function, so the rule can be tested on
    synthetic operands.
  - `RECONCILIATION`: 16 identities, each marked exact or tolerance.
  - Named field tuples.
  - `TOLERANCE` is imported from `shared_named_playback`. It is the same object; no new constant.
- **Checks beyond the literal section 3 table.** Each follows exactly from the approved rules.
  - `record_structure` also checks:
    - the closing policy (exactly `DRAIN` or `HARD_CUTOFF`);
    - the replication block, when present;
    - that each `state_totals` entry gives finite hours for every base state;
    - that `duration_minutes` converts to a finite float.
  - `interval_geometry` also rejects an interval that crosses closing or its own shift end, and requires
    each employee's intervals to reach `finish`.
  - `shift_reconciliation` also requires:
    - `activated == (actual_start is not None)`;
    - an activated shift to have a release, activation delay, and overrun;
    - a shift that was not activated to have no activation delay.
  - `break_reconciliation` also requires:
    - a started break to have its due time, actual end, and delay;
    - an unfulfilled break to have neither an actual end nor a delay.

    The ON_BREAK reconciliation runs on every shift, so a started break on a shift that was not
    activated fails.
  - `finite_nonnegative` also covers an overflowing sum or D7 difference. A final pass checks every
    output duration.
- **D1-D7.** As approved. In brief:
  - D1: hours throughout; `configured_minutes` is the only source-unit field.
  - D2: two per-break delay fields; `_total` only at shift or employee level.
  - D3: seven fields summed directly from the intervals.
  - D4: `inputs_sha256` is `None`, with the reason.
  - D5: no `paid` field and no monetary field.
  - D6: no replication runner; the replication rows are unchanged.
  - D7: the house tolerance is applied to the operands; tiny negatives become `0.0`; beyond the
    tolerance the call fails; timing stays exact.
- **Per-shift allocation.** Exactly by `(employee_id, shift_index)`. The preconditions are checked on
  every input, never assumed. The 500-run seeded reconciliation test found no exception.

### Defect found and fixed during implementation

- **The defect.** `_time` called `float(value)` without a guard. Malformed inputs raised
  `OverflowError` instead of `NamedAttributionError`:
  - a time of `10**400`;
  - `duration_minutes` of `10**400`;
  - `Fraction` times whose difference exceeds the float range.
- **Evidence.** VERIFIED on the pre-fix module: all three crashed. After the fix they fail
  `record_structure`, `record_structure`, and `finite_nonnegative`.
- **Fix.** `_time` and `_close_enough` guard the float conversion. D7 operands are converted to float
  first. `duration_minutes` must convert to a finite float. Regression tests were added.
- **Out-of-scope finding.** The protected playback `_time()` helper was observed to raise
  `OverflowError` for `_time(10**400)`. Whether this propagates through `replay_named_trace` was not
  tested. Playback v3 was not modified during Phase 5B-4.6. A separate task was opened for it.

### Section 7.4 correction

See section 7, item 4. The seeded "stable" day is not a zero-attribution day (24 of 25 replications
nonzero under each policy). It was replaced by `zero_arrivals` and a prescribed quiet day. The contract
is unchanged.

### Hand cases and tests

- **Hand cases.** H1-H8, plus H1b under HARD_CUTOFF, are asserted exactly. Each expected value is
  derived by hand in the test comments from the scenario definition.
- **Further tests:**
  - the section 7 situations;
  - an unrostered employee;
  - zero-attribution days;
  - the seeded reconciliation: 10 scenarios × 2 policies × 25 replications, including the unchanged
    5B-4.4 row;
  - 85 malformed-input and order-violation cases (67 in the main parametrized test), each pinned to its
    check, and to its message where a later check could also catch the record;
  - the D7 rule: positive, zero and -0.0, tiny negative, the exact `abs_tol` boundary, beyond the
    boundary, tiny positive, non-finite results, and order violations that D7 does not forgive;
  - units and names;
  - provenance;
  - purity: no random numbers, no mutation of the source, determinism, and no shared objects;
  - isolation.

### Fault injection

- **Method.**
  - A scratch copy of the tracked tree was made (`git archive HEAD backend tests pyproject.toml`),
    plus the new files.
  - Each mutant replaced one exact snippet of the module, ran the attribution tests, and restored the
    module.
  - The module was verified byte-identical to the repository after each pass.
  - The working tree was never mutated. The script was not committed.
- **Final pass.** On the final attribution implementation: 99 mutants in total.
  - 94 were killed.
  - 3 survived because the guarded conditions are input-unreachable through validated execution
    paths.
  - 2 were demonstrated to be equivalent mutants.
  - There were 0 timeouts and 0 harness failures in the final pass.
  - The three defensive checks were retained, because forced or bypassed validation demonstrated that
    they still detect real malformed states.
- **Input-unreachable (3).** Each is retained because the spec requires it.
  - **`on_duty_hours ≈ release - actual_start`** (`shift_reconciliation`).
    - Upstream: the exact tiling check (first start, last end, and adjacency) and `end > start`.
    - Given those, the exact lengths telescope to `release - actual_start`, and each floating
      subtraction carries relative error at most 2^-53. With positive terms, the two sides differ by
      about 3·2^-53 relative, far below 1e-9. An overflow makes both sides inf, which the final finite
      check rejects.
    - Evidence: with the adjacency check bypassed, the H4 gap record fails this check.
  - **`closing_partition`.**
    - Upstream: `record_structure` makes the flags bool, so each on-shift interval lies in exactly one
      cell. Every field is an fsum of a subset of positive lengths.
    - The identities therefore hold to a few 2^-53 relative. `both <= after_closing` and
      `both <= past_scheduled_end` hold exactly, because fsum is correctly rounded and monotone.
    - Evidence: with the flag type check bypassed, non-bool flags are rejected earlier by
      `interval_geometry`. The check fired on a computation defect: `after_closing_only` computed
      without "not past end" fails it on H1.
  - **`base_state_partition`.**
    - Upstream: `record_structure` (the state is a base state) and `interval_geometry` (on a shift if
      and only if not OFF) place each on-shift interval in exactly one of the six on-duty states.
    - Evidence: with the OFF rule bypassed, an on-shift OFF interval on H1 fails this check.
- **Equivalent (2).**
  - **`delay_due_raw`**: `_derived("delay_from_due_hours", start, due, record)` becomes `start - due`.
    - The exact check `actual_start >= due` runs first. For finite floats with `a >= b`, IEEE-754
      subtraction gives a result of 0 or more (+0.0 when equal), which `_derived` returns unchanged.
    - Only if `start - due` overflows, which needs times near the float maximum, do the two differ.
      Both then fail `finite_nonnegative`, but with a different message; the mutant fails later, in
      the output check.
  - **`unfulfilled_total_over_all`**: `total("unfulfilled_hours", unfulfilled)` becomes
    `total("unfulfilled_hours", breaks)`.
    - Every started break carries `unfulfilled_hours = 0.0`.
    - `math.fsum` with added +0.0 terms returns the same value, and `fsum([])` equals
      `fsum([0.0, ...])` (+0.0).
- **Earlier passes (history).**
  - Pass 1, on the first test file: 95 mutants, 55 killed, 40 survived. Tests were added for every
    reachable survivor, and messages were pinned where a later check with the same code also caught the
    record.
  - Pass 2, on the updated tests: 95 mutants, 90 killed, 5 survived (the same five as above).
  - Pass 3 is the final pass above. The overflow fix added 4 mutants, and 3 existing snippets were
    updated to the new code: the two `_time` snippets and the zero-minute snippet.
- **Harness incidents.** None affects the final pass.
  - The first attempt at pass 2 was stopped by a harness check. The harness had restored the scratch
    module with CRLF line endings; the content was identical. The script was fixed to write bytes, and
    pass 2 was run again.
  - In that run one mutant (`off_past_end_unchecked`) hit the 900-second timeout, which aborted the
    script. The earlier 900-second timeout did not reproduce, and its cause remains UNKNOWN. Re-run
    alone, the mutant was killed. The script now records timeouts, and the complete pass was run
    again.
  - A separate scratch restore-path mistake occurred during manual reproduction and was corrected.
    There is no evidence that it caused the timeout.

### Gates (executed on the final code)

- **Focused suites.** All passed:
  - attribution 141;
  - state machine 39;
  - named DES 65;
  - named replications 73;
  - named playback 117;
  - `test_shared_segments.py` (isolation) 51;
  - 5B-4.0 pin 9.
- **All `tests/test_shared_*.py`** (15 files): 952 passed.
- **Separate Queue** (the 20 files with `separate`, `queue_lifecycle`, or `routing` in the name): 182
  passed.
- **Full backend suite** (`python -m pytest tests/ -x --tb=short`): 1985 passed, 3 skipped, 1 xfailed
  (baseline 1844 + 141).
  - The 3 skips are the PostgreSQL migration rehearsal tests, which need `NOVAQ_TEST_DATABASE_URL`.
    The xfail is the known 2026-09-19 finding in `test_selected_mc_load.py`.
  - The full backend suite completed in approximately 65 minutes (3917.55 s). Other processes were
    active during the run; whether they caused the longer runtime is UNKNOWN.
- **`ruff check .`**: clean.
- **`mypy . --exclude '^outputs/'`**: success on 178 source files.
  - It prints 30 informational `annotation-unchecked` notes across the repository.
  - 2 of them are in the new test file, from the same pattern the playback test uses.
- **Plain `mypy .`**: only the 5 known errors, in the gitignored
  `outputs/technical-paper/build_chapters_4_5.py`.
- **`git diff --check`**: clean.
- **Documentation edits made after the gates.** No test reads these documents; a grep finds only
  docstring mentions of other spec paths. The gate results therefore stand.

## Undetermined (UNKNOWN or INFERRED)

1. Cross-version numpy stream equality: UNKNOWN (unchanged from 5B-4.4). The probe results hold for
   this runtime only.
2. Whether a derived duration can ever come out float-negative, and so trigger the D7 zero or failure
   branch, is NOT TESTED. The cases are a truncated break's `shortened_hours` (0 of 96 truncated breaks
   observed) and `delay_from_scheduled_hours` (0 negative delays observed). D7 decides the handling
   either way.
3. The 5B-4.6 → 5B-5 order: UNKNOWN.
4. D15: UNKNOWN (not defined in the repository).
5. The before-opening window shape: INFERRED; out of scope.
6. The cause of the one 900-second mutation timeout (section 12): UNKNOWN; it did not reproduce.
7. Whether the playback `_time()` overflow propagates through `replay_named_trace`: NOT TESTED in this
   phase (out of scope; section 12).
