# Shared Queue Enhancement: Phase 5B-5, Named Workforce Costing

Date: 2026-09-30. **Status: APPROVED SPECIFICATION (approved by the product owner, 2026-09-30).
Implemented 2026-09-30 as `backend/queueing_engine/services/shared_named_cost.py`, with tests in
`tests/test_shared_named_cost.py` (section 18). Committed locally with the implementation; not pushed,
merged, or deployed.**

The approval covers this whole text, including the contract detail marked PROPOSED (section 14).
Section 17 is the completion boundary, and section 18 records the implementation. Until the
implementation, this status read "Implementation not started: nothing in this document is
implemented. Uncommitted: this file is in no commit, and it stays uncommitted until this repository
update is completed."

Plan: `docs/superpowers/plans/2026-09-30-shared-queue-named-workforce-cost-plan.md`.

Decisions C1-C16 were decided by the product owner on 2026-09-30 (section 2):

- C1-C12 are approved as proposed.
- C10b is selected, and C10a is rejected.
- C13 is Option U.
- C14 is approved with a refinement.
- C15 and C16 are approved.

This revision writes those decisions into the contract. Section 16 lists what changed.

This document separates these kinds of statement:

- **VERIFIED** statements describe the repository at `156de75f` (branch `feat/shared-queue-segments`)
  or scratch probes run on it. Each cites its source.
- **APPROVED** marks a product-owner decision. It is not an implementation claim.
- **PROPOSED** marks contract detail that this revision adds to carry out an approved decision. It
  needs approval together with this text. (Approved with this text on 2026-09-30 and implemented;
  section 18. The labels are kept as written.)
- **INFERRED** marks reasoning that has not been established directly.
- **UNKNOWN** or **NOT TESTED** marks everything that is still undefined or unexecuted.

This is a NovaQ modeled workforce-cost contract. It is not an employment-law or payroll-compliance
interpretation, and it makes no claim about what any law requires.

Related specs:

- `2026-09-28-shared-queue-named-employee-des-policy.md` (policy P1-P9, X1-X7);
- `2026-09-26-shared-queue-workforce-foundation.md` (5B-1);
- `2026-09-26-shared-queue-sequential-rostering.md` (5B-2);
- `2026-09-28-shared-queue-integrated-planning.md` (5B-3);
- `2026-09-28-shared-queue-named-des.md` (named engine v3);
- `2026-09-28-shared-queue-named-replications.md` (5B-4.4, method v2);
- `2026-09-29-shared-queue-named-attribution.md` (5B-4.6, attribution v1);
- `2026-09-25-shared-queue-closing-policy.md` (Phase 3A day cost).

## 1. Inherited repository rules (VERIFIED)

### What the repository says 5B-5 needs

- Policy spec, line 498: 5B-5 needs "X6 redefinition, overtime classification, the pay consequence
  of unfulfilled or truncated breaks (P1), D15 acceptance rule".
- P1 (line 395) leaves open "the pay consequence of an unfulfilled or truncated unpaid break".
- P9 (line 403): "Which quantity counts as paid overtime belongs to 5B-5".
- Policy spec, lines 192-193: 5B-1 overtime is scheduled paid time past the daily threshold, and
  "There is no rule for time actually worked past a shift end."
- Rostering spec, line 52: "Overtime after the shift end or after closing arises only in simulation
  (Phase 5A D6 and D8)". The content of D6 and D8 is not in the repository.

### Phase 3A day cost (anonymous engine)

Source: `services/shared_day_cost.py`, lines 1-16 and 67-106, and the closing-policy spec, lines
21-32, 75-77, and 109-125.

```text
total_cost = regular_server_hours × regular_server_rate
           + overtime_server_hours × overtime_rate
           + total_waiting_customer_hours × waiting_rate
           + unserved_customer_count × unserved_customer_rate
```

- `regular_server_hours` and `overtime_server_hours` are **modeled capacity**: server-hours present
  inside the horizon, and after closing. The code says they are "not necessarily paid
  employee-hours".
- The DES reports quantities only. `DayCostRates` holds four caller rates, with no defaults.
- Statuses (line 27):
  - `COSTED`: quantity × rate.
  - `RATE_MISSING`: the rate is `None`, so the cost is `None` and `total_cost` is `None`, with the
    missing rates named. A missing rate is never read as 0.
  - `NOT_APPLICABLE`: used only for the unserved term, when `unserved_possible` is false. Its cost is
    `None`, and it is left out of the total.
- Every other term applies whatever its quantity. For example, a zero-hour overtime term with no
  rate still gives `RATE_MISSING`.
- The unserved term depends on configured possibility, not the realized count. The closing-policy
  spec (lines 75-77) says a run where the term applies "but nobody was unserved still needs the
  rate".

Phase 3A is not changed by 5B-5. Section 9 records where 5B-5 departs from it, under C13.

### 5B-1 pay fields and scheduled pay

Source: `services/shared_workforce.py`, lines 43-52, 73-78, 199-208, and 472-479.

- `EmployeePay(regular_rate_per_hour, overtime_rate_per_hour, daily_regular_paid_minutes)`.
  - Rates are finite and 0 or more, or `None`.
  - The threshold is a whole number of minutes, 0 or more, or `None`.
  - `None` means "not supplied (never zero)".
- The scheduled definitions:
  - paid = scheduled − unpaid breaks;
  - regular = min(paid, θ);
  - overtime = paid − regular, taken in clock order.
- `_overtime_start` (lines 472-479) begins overtime only once paid time **exceeds** θ. So paid time
  up to and including θ is regular.
- A missing θ means "Regular and overtime minutes cannot be classified."
- These are **scheduled** quantities, not simulated ones.

### 5B-2 and 5B-3 rules on when a rate is required

- 5B-2 (rostering spec, lines 134-145): "A pay value that the objective does not need… is not
  required." θ is needed when paid time is above 0. When θ is missing, any missing rate is listed
  too, because whether it is needed cannot be decided.
- 5B-3 (integrated spec, lines 88-92): a missing waiting rate gives INCOMPLETE only "when some
  in-horizon λ > 0".
- 5B-3 (integrated spec, lines 37-38): "Labor is wages only… Phase 2's server cost per server-hour is
  never charged."

These precedents conflicted with Phase 3A about when a rate is required. For 5B-5 only, the
conflict is **resolved by the approved C13 (Option U)**.

### Named engine facts

- **Base states** (`simulation/shared_employee_states.py`, lines 47-55): `OFF`,
  `WAITING_FOR_REGISTER`, `AVAILABLE`, `SERVING`, `SERVING_BREAK_DUE`, `SERVING_SHIFT_ENDED`, and
  `ON_BREAK`. Exactly one holds at each instant.
- **The break `paid` flag.**
  - It is copied into each engine break record (lines 323 and 746) and never used for a transition.
    So a paid break and an unpaid break with the same timing produce identical timelines.
  - Attribution does not read it: `_BREAK_FIELDS` (`simulation/shared_named_attribution.py`, line
    191) omits `paid`, and D5 excludes it from the output. So its type is **not validated by
    5B-4.6**.
- **Break outcomes** (`shared_employee_states.py`, lines 75-76): `completed`,
  `truncated_by_closing`, and `unfulfilled`.
  - The unfulfilled causes (`shared_named_replications.py`, line 66) are `released`,
    `shift_not_activated`, and `cancelled_at_closing`.
  - No other shortening outcome exists.
- **Unserved customers** (`simulation/shared_named_des.py`, lines 371-375 and 413-417) are
  produced only by `unserve()`, which is called only at the closing instant:
  - under HARD_CUTOFF, every waiting customer gets `hard_cutoff`;
  - under DRAIN, every waiting customer gets `no_eligible_employee` (X6), **only when** the frozen
    crew `at_close["drain_crew"]` is empty.

  Under DRAIN with a non-empty crew, the crew serves the admitted line until it is empty (P5), so no
  customer is unserved.
- **The result exposes** (`shared_named_des.py`, lines 404-411 and 640-678):
  - `closing_policy`;
  - `at_close` (`waiting_customer_ids`, `in_service_customer_ids`, `drain_crew`, `closing_inputs`).
    It is initialized to `{}` (line 334) and filled at the closing instant;
  - `customers` rows with `customer_id`, `status` (`departed` or `unserved_at_close`, line 69),
    `unserved_reason`, and `elapsed_wait_at_close_hours`;
  - `counts.unserved_at_close`, and `counts.unserved_by_reason` with exactly the keys `hard_cutoff`
    and `no_eligible_employee` (line 70);
  - `queue.customer_hours_in_horizon`, `queue.customer_hours_after_closing`, and
    `queue.customer_hours_total`. The total is computed as the sum of the other two (line 676).

  The queue total is the integral of the number waiting. It equals the served customers' waits
  plus the unserved customers' elapsed waits at closing (`DEFINITIONS["queue_customer_hours"]`).
- **A truncated break is never followed by work.**
  - A break is shortened only by closing (P7; outcome `truncated_by_closing`).
  - Every employee on a break at closing is released, so the truncation always ends in a release
    (`shared_named_playback.NOT_PRODUCED_BY_THE_NAMED_ENGINE`, lines 149-156 at `156de75f`; lines
    152-159 at `40ee8dbe`, content unchanged; corrected 2026-09-30, section 14.1).
  - Nobody returns from a break after closing (`shared_named_des.py`, lines 117-122).
- **Day boundary.**
  - The operating horizon and every roster shift use whole minutes from 0 to 1440
    (`services/shared_workforce.py`, lines 152-157, 282, and 325).
  - Closing is the horizon end (`shared_employee_states.py`, line 313).

  So any paid instant after the horizon end is after closing. It is overtime under C5 condition 2,
  whatever calendar day it falls on (INFERRED from the three facts above).

### 5B-4.6 attribution (v1)

- `build_named_attribution(result, employees)` validates the timeline through 11 checks, and
  raises `NamedAttributionError` on any failure. Its output per shift and per employee includes:
  - `on_duty_hours` and `hours_by_state`;
  - the seven closing cells;
  - break records and break totals;
  - `off_hours` (employee).
- Every monetary value is excluded, and so is the `paid` flag (D5).
- `derived_duration(a, b, *, field)` (lines 260-267) is the public D7 rule.
  - A difference `a - b` whose true value is nonnegative is reported as `x` when `x >= 0`.
  - It is reported as `0.0` when `x < 0` and
    `math.isclose(a, b, rel_tol=TOLERANCE["rel"], abs_tol=TOLERANCE["abs"])`.
  - Otherwise the rule fails with the check `finite_nonnegative`.
- `TOLERANCE = {"rel": 1e-9, "abs": 1e-12}` is imported from `shared_named_playback` (attribution
  line 44; playback line 227 at `156de75f`, line 233 at `40ee8dbe`, value and type unchanged;
  corrected 2026-09-30, section 14.1).
- Attribution's per-shift sums cannot express a daily threshold crossed partway through an interval.
  That needs the chronological interval sequence (section 5).
- The employee's intervals, in record order, are contiguous from `begin` to `finish`, with exact
  `end > start` (`_check_geometry`, lines 428-463). So record order is time order across split
  shifts.

### D15 and acceptance

- D15 is UNKNOWN: an undefined repository reference, labeled "acceptance rule" (policy spec, line
  498; introduced in `48b2499e`).
- No approved acceptance rule exists (policy spec, line 499; named-replications spec, lines 196 and
  299).

## 2. Decisions (APPROVED 2026-09-30)

| ID | Decision | Approved rule | Repository basis |
|---|---|---|---|
| C1 | Scope | Backend or domain workforce costing only. No API, frontend, Reports, Compare, or Decision | Nothing approves API or UI work |
| C2 | Labor model | Named employee wages **replace** the Phase 3A capacity labor terms; both are never charged (section 3) | Matches the 5B-3 precedent (VERIFIED, planning scope) |
| C3 | Paid states | `AVAILABLE`, `WAITING_FOR_REGISTER`, `SERVING`, `SERVING_BREAK_DUE`, and `SERVING_SHIFT_ENDED` are paid. `OFF` is unpaid. `ON_BREAK` is paid if and only if the `paid` flag of the break it maps to is `True` (section 4) | The state names are VERIFIED against `BASE_STATES` |
| C4 | Activation and split gaps | Time before actual activation, and rest gaps between split shifts, are unpaid. Only simulated paid time is costed | The engine records such time as `OFF` (VERIFIED) |
| C5 | Overtime union | A paid instant is overtime when **any** of these holds: (1) it is past its shift's scheduled end; (2) it is after closing; (3) the employee's cumulative actual paid time has reached the daily threshold. At most one premium applies to an instant. The threshold is applied in time order across split shifts (section 5) | New. Phase 5A D6 and D8 are UNKNOWN; C5 is a new rule, not a restatement of them |
| C6 | Regular time | regular = paid − overtime. The implementation sums regular pieces directly and checks the identity (section 5) | New |
| C7 | Breaks | No separate penalty or bonus for delayed, shortened, truncated, or unfulfilled breaks. Only actual time is costed: a paid break is paid for its actual time, an unpaid one is unpaid for its actual time, and work done instead is paid normally | New; this answers P1's open question |
| C8 | Rates | Labor uses each employee's `EmployeePay`. The waiting and unserved rates are caller inputs, with no defaults. A missing rate is never read as 0. When a rate is required and missing, the status is `RATE_MISSING` (section 9) | Matches Phase 3A and 5B-1 semantics |
| C9 | Waiting cost | Realized `queue.customer_hours_total` from the named result × waiting rate. The 5B-3 analytical estimate is not used | New |
| C10 | X6 (named) | **C10b.** HARD_CUTOFF: the unserved term applies, as inherited from Phase 3A. DRAIN: the term applies if and only if the realized `counts.unserved_at_close > 0`, reconciled to the engine's closing evidence (section 7). An empty frozen DRAIN crew with nobody unserved does **not** make the term apply. **C10a is rejected** | Redefines X6, as the policy spec requires |
| C11 | D15 and verdict | D15 stays UNKNOWN. 5B-5 produces costs only: no PASS/FAIL, no Monte Carlo threshold, and no `verdict` field. Deterministic costing does not depend on D15 | VERIFIED: no approved rule exists |
| C12 | Replications | Cost one named-DES run, or one replication regenerated through 5B-4.4. No aggregation across replications, threshold, or acceptance logic. Method v2 is unchanged | Matches 5B-4.6 D6 |
| **C13** | When a rate is required | **Option U.** For each component with a **determined** quantity Q: if Q == 0 (exact), no rate is required and the cost is 0.0; if Q > 0, the rate is required, and a missing rate gives `RATE_MISSING`. This applies independently to regular hours, overtime hours, waiting customer-hours, and realized unserved customers. An undetermined quantity is not zero, and this rule never turns one into zero. Whether the unserved term applies (C10) is recorded separately from whether its rate is required | Resolves the Phase 3A versus 5B-2/5B-3 conflict for 5B-5 only; Phase 3A is unchanged |
| **C14** | Daily threshold θ | θ is required if and only if the employee has paid time whose regular-or-overtime class can depend on cumulative daily paid time: paid time that is neither past its shift's scheduled end nor after closing. It is **not** required when the employee has no paid time, or when every paid instant is already overtime by C5 condition 1 or 2. If a required θ is missing, regular and overtime hours are `None` (`HOURS_UNDETERMINED`, not `RATE_MISSING`), the labor cost is `None`, and `total_cost` is `None`. θ is never inferred, and equal regular and overtime rates never bypass an undetermined split | Follows 5B-1 and 5B-2 |
| **C15** | Derived pay durations | Every pay duration computed as a difference `x = a − b` goes through the 5B-4.6 D7 rule (`derived_duration`), using the same tolerance. If `x >= 0`, it gives `x`. If `x < 0` and `math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)`, it gives 0.0. Otherwise the call fails. No new tolerance is introduced. The tolerance never changes event order, interval order, the closing boundary, shift or break boundaries, the threshold-reached instant, or any state transition. Raw times stay exact | Reuses 5B-4.6 D7 (VERIFIED approved) |
| **C16** | Interface and source of truth | New `services/shared_named_cost.py`. It first calls `build_named_attribution`, whose failures propagate unchanged. It then walks the **same validated** `employee_timeline.intervals` in time order, only for pay classification that shift totals cannot give, such as a threshold crossed inside an interval. Attribution quantities are read from the attribution output, never recomputed (section 10.1) | New |

## 3. Cost equations (APPROVED model; PROPOSED status rules, approved with this text)

For a component with quantity Q and supplied-or-missing rate r, applied only when the component
applies:

```text
cost(Q, r) = None     if Q is None                        (HOURS_UNDETERMINED; labor only)
           = 0.0      if Q == 0            (exact test)   (ZERO_QUANTITY; r not required)
           = None     if Q > 0 and r is None              (RATE_MISSING)
           = Q × r    if Q > 0 and r is supplied          (COSTED; r = 0 gives 0.0)
```

```text
For each input employee e:
  L_e_reg = cost(regular_paid_hours_e,  regular_rate_per_hour_e)
  L_e_ot  = cost(overtime_paid_hours_e, overtime_rate_per_hour_e)
  L_e     = fsum(L_e_reg, L_e_ot)       if neither is None, else None

L       = fsum over e of L_e            if no L_e is None,  else None
W       = cost(queue.customer_hours_total, waiting_rate)
U       = cost(counts.unserved_at_close, unserved_customer_rate)   if X6 applies (section 7)
        = NOT_APPLICABLE (not a term)                                otherwise

C_total = fsum(L, W, U if X6 applies)   if none of them is None, else None
```

- **Units:**
  - paid hours × currency per hour;
  - customer-hours × currency per customer-hour;
  - customers × currency per customer.

  The currency is the caller's; the module assumes none.
- **Cost is only one multiplication.** Every cost is `quantity * float(rate)`, as in Phase 3A. A
  result that is not finite fails `finite_nonnegative`.
- **Not charged (C2):**
  - Phase 3A `regular_server_hours` and `overtime_server_hours`;
  - the named result's `staffing` capacity integrals;
  - Phase 2 server cost.

  Surplus staff costs only through wages (5B-2 precedent).
- **Not part of this total:** 5B-1 scheduled pay. It stays a planning quantity and is never mixed in.
- **Retained from Phase 3A (VERIFIED):** unserved customers are charged both their elapsed waiting
  time (inside `customer_hours_total`) and the unserved rate.

## 4. Paid-time classification (APPROVED C3, C4, C7)

For each employee interval `x = [start, end)`:

| State | Paid? |
|---|---|
| `AVAILABLE`, `WAITING_FOR_REGISTER`, `SERVING`, `SERVING_BREAK_DUE`, `SERVING_SHIFT_ENDED` | paid |
| `ON_BREAK` | paid if and only if `paid is True` on the break record `x` maps to |
| `OFF` | unpaid, and not counted toward the threshold |

**Break mapping.** This is the `break_mapping` check. It is deterministic and exact, and it never
changes the timeline.

1. Every engine break record must carry `paid` as a `bool`. Attribution does not check this field
   (section 1).
2. An `ON_BREAK` interval `x` maps to the break record `b` for which all of these hold:
   - `b` has the same `(employee_id, shift_index)`;
   - `b` was started (`b.actual_start is not None`);
   - `b.actual_start <= x.start` and `x.end <= b.actual_end`, compared exactly.

   Exactly one such `b` must exist.
3. For each started break, the intervals mapped to it must tile `[actual_start, actual_end)`
   exactly, with no gap and no overlap. The engine can split one break's time at the scheduled
   shift end, as in H6 (VERIFIED).
4. The `paid` value is read from the engine break record, which is authoritative. It is never taken
   from the roster or from attribution.

**Consequences, with no special cases** (VERIFIED from the engine rules):

- Late activation and split-shift rest are `OFF`, so they are unpaid.
- A missed shift is entirely `OFF`.
- Register waiting is paid.
- Time on duty before opening is paid like any other on-duty time (as in 5B-1 scheduled pay).
- An unfulfilled break has no `ON_BREAK` time. The time the employee actually worked instead is
  paid.
- A truncated break is `ON_BREAK` only for its actual time, and the release follows at once.

## 5. Time-classification algorithm (APPROVED C5, C6, C14, C15)

### 5.1 Inputs

- The validated attribution output.
- The same result's `employee_timeline.intervals` and `breaks`.
- Each employee's `EmployeePay`.

The algorithm reads the interval flags `after_closing` and `past_scheduled_end`. It does not recompute
them: attribution has already checked them exactly against closing and the scheduled end.

### 5.2 Per employee, in `employee_id` order

1. `P` = the employee's paid intervals (section 4), in record order, which is time order.
2. For each `x` in `P`, `ℓ(x) = x.end − x.start`. This is a float with `ℓ > 0`, because attribution
   checked `end > start` exactly. It is the same raw length attribution sums.
3. `x` is **flagged** if `x.after_closing or x.past_scheduled_end`, which is C5 condition 1 or 2.
4. `threshold_required = any(not flagged(x) for x in P)`, an exact test on the flags (C14).
5. If θ (`daily_regular_paid_minutes`) is `None` and `threshold_required`, the hours are
   **undetermined**:
   - `regular_paid_hours`, `overtime_breakdown.daily_threshold_only_hours`, and
     `overtime_paid_hours` are `None`;
   - `hours_status = "HOURS_UNDETERMINED"`;
   - only `paid_hours`, the break hours, and the flagged sum Σ F (step 8) are computed. No `G` or
     `T` piece is formed.
6. If θ is `None` and not `threshold_required`, the hours are determined with no threshold:
   - every paid instant is flagged, so each piece is `F`;
   - `regular_paid_hours = 0.0` and `daily_threshold_only_hours = 0.0`;
   - `threshold_reached_at_hours = None`;
   - `hours_status = "DETERMINED"`.
7. Otherwise, `hours_status = "DETERMINED"`. Let `θ_h = daily_regular_paid_minutes / 60`, and set
   `exhausted = False`. For `k = 1..n` over `P` in time order, let
   `C_k = math.fsum(ℓ(x_1), …, ℓ(x_{k−1}))`: every earlier paid length, flagged or not (C5
   condition 3 counts **all** paid time).

   a. **Exhaustion test**, at each `k` while `exhausted` is `False`. It succeeds at most once:
      - if `C_k >= θ_h`: `exhausted = True`. The threshold-reached instant is `x_k.start` if `k` is
        the first paid interval (this happens when `θ_h = 0`), and otherwise `x_{k−1}.end`;
      - otherwise, let `R_k = derived_duration(θ_h, C_k)` (D7):
        - if `R_k == ℓ_k`: `exhausted` becomes `True` after this interval, and the instant is
          `x_k.end`, the exact boundary;
        - if `R_k < ℓ_k`: `exhausted` becomes `True` inside this interval, and the instant is
          `x_k.start + R_k`.

      Every comparison is an exact float comparison. The tolerance never decides this.
   b. **Classify `x_k`:**
      - **flagged:** the whole of `ℓ_k` is an `F` piece (overtime by condition 1 or 2). No threshold
        split is made, so an instant never receives two premiums.
      - **not flagged, and either exhausted before `x_k` or `C_k >= θ_h`:** the whole of `ℓ_k` is a
        `T` piece (threshold overtime).
      - **not flagged, and `R_k >= ℓ_k`:** the whole of `ℓ_k` is a `G` piece (regular).
      - **not flagged, and `R_k < ℓ_k`:** this is a crossing inside the interval. There is a `G`
        piece of `R_k` and a `T` piece of `derived_duration(ℓ_k, R_k)` (D7). No event, interval, or
        boundary is created or moved. The crossing instant is only reported.
      - After exhaustion, no later piece is `G`. This is monotone by construction.
8. Sums, all with `math.fsum`:
   - `paid_hours` = Σ ℓ;
   - `overtime_breakdown.past_end_or_after_closing_hours` = Σ F (always determined);
   - `regular_paid_hours` = Σ G;
   - `daily_threshold_only_hours` = Σ T;
   - `overtime_paid_hours` = `fsum(Σ F, Σ T)`.
9. **Per shift:** the same pieces, grouped by the interval's `shift_index`. There are no extra
   comparisons and no proportional allocation.
10. `threshold_reached_at_hours` is the instant found in step 7a, or `None` when θ is `None` or the
    exhaustion test never holds.
    - It is a **derived instant**. It is not an event, and it never takes part in any ordering or
      classification.
    - It can fall inside a flagged interval, where it has no pay effect.

### 5.3 Properties

- **Pieces.** `G`, `T`, and `F` are disjoint, and they cover each paid interval exactly.
  - regular = ΣG;
  - overtime = ΣF + ΣT;
  - regular + overtime = paid, within the house tolerance, because the sums are rounded
    separately.
- **Agreement with 5B-1.** Paid time up to and including θ is regular. Overtime begins only once θ
  is exceeded, which agrees with `_overtime_start` (VERIFIED).
- **Paid breaks.** Paid break time is classified like work, and it counts toward the cumulative
  total. A paid break past the shift end or after closing is `F`.
- **Unpaid breaks and `OFF` time.** Neither is paid, and neither is counted.
- **Split shifts.** The threshold runs across split shifts in one walk, because `P` is the
  employee's whole day in time order.
- **D7 in the walk** is used only for `R_k` and for the `T` piece of a crossing.
  - Both are computed only in branches where the exact comparison already shows a positive true
    value.
  - The D7 zero and failure branches are therefore INFERRED to be unreachable here: under IEEE-754,
    the difference of two distinct finite doubles is nonzero, with the correct sign. This is NOT
    TESTED. D7 decides either way.
  - A D7 failure raises `NamedCostError` with the check `finite_nonnegative`. The evidence carries
    the D7 failure.
- **Float representation.**
  - Event times are floats, and they can be inexact, for example 10 minutes = 1/6 h.
  - So `C_k` can differ from the true cumulative time by rounding. A very small `G` or `T` piece can
    then result. It is reported as computed and never snapped to a boundary (C15).
  - Whether this happens on seeded runs is NOT TESTED.

## 6. Break treatment (APPROVED C7) and the hand-case correction

| Break | Pay effect | Reachable engine case |
|---|---|---|
| Ordinary paid break (completed on time) | its actual `ON_BREAK` time is paid, and classified regular or overtime normally | H1 A (0.5-1.0): HC-P |
| Ordinary unpaid break (completed on time) | its actual `ON_BREAK` time is unpaid and not counted | H1 A with the unpaid rule (0.5-1.0): HC-H |
| Delayed break (starts after it fell due, or after its schedule) | no separate effect. The time worked while it was due is paid, and the break's own time is paid or unpaid by its flag | H6, delayed 0.25 by service and carried past the shift end: HC-E (paid) and HC-F (unpaid). H4, delayed 0.625 by late activation: HC-C |
| Truncated by closing | only its actual time, paid or unpaid; the release follows (the engine never resumes work after it) | H1 B, unpaid: HC-H. H1 B, paid: HC-P |
| Unfulfilled (`released`, `shift_not_activated`, `cancelled_at_closing`) | no break time; any time worked instead is paid; no phantom deduction or bonus | `released` with work instead: HC-G. `cancelled_at_closing` with work after closing: HC-K |

**Correction (VERIFIED engine limitation).** An earlier request listed the case "shortened unpaid
break with work replacing the break time". It is **removed** from the required hand cases, because
the named engine cannot produce that lifecycle:

- the only shortening outcome is `truncated_by_closing`;
- every employee on a break at closing is released at once;
- nobody returns from a break after closing.

The sources are section 1 and `NOT_PRODUCED_BY_THE_NAMED_ENGINE`. The engine is not changed to
manufacture it. The reachable cases above take its place.

## 7. X6 named definition (APPROVED C10b)

| Closing policy | The unserved term applies when | Quantity | Rate required when (C13) |
|---|---|---|---|
| HARD_CUTOFF | always, as inherited from Phase 3A | `counts.unserved_at_close` | the quantity is > 0 |
| DRAIN | if and only if `counts.unserved_at_close > 0` (realized) | `counts.unserved_at_close` | always, when the term applies (the quantity is then > 0) |

**Separate statements.** Whether the term applies and whether its rate is required are recorded
separately:

- Under HARD_CUTOFF with nobody unserved, the term applies. Its quantity is 0, its status is
  `ZERO_QUANTITY`, and its cost is 0.0. No rate is required.
- This departs from the Phase 3A statement that such a run "still needs the rate". C13 approves the
  departure, and it applies to 5B-5 only.
- Under DRAIN with nobody unserved, the term is `NOT_APPLICABLE`, even when the frozen crew is empty
  (for example H6 or H7, where the only employee was released before closing).

**No eligibility is recomputed.**

- The cost module never inspects employee states to decide who could serve at closing.
- It reads only the engine's recorded outcome: the counts, the customer rows, and
  `at_close.drain_crew` and `at_close.waiting_customer_ids`.
- It checks that these agree. This is the `unserved_consistency` check, which is exact because every
  value is an integer or an id:
  1. `at_close` carries `waiting_customer_ids` and `drain_crew` as lists. The `{}` left by a run that
     never processed closing fails.
  2. `counts.unserved_by_reason` has exactly the keys `hard_cutoff` and `no_eligible_employee`, with
     whole values of 0 or more. `unserved_at_close` is a whole number, 0 or more, and equals their
     sum.
  3. The `customers` rows with `status == "unserved_at_close"` number `unserved_at_close`. Their
     `unserved_reason` counts equal `unserved_by_reason`. No other row has a reason.
  4. HARD_CUTOFF: `no_eligible_employee == 0`. The unserved rows' ids are exactly
     `waiting_customer_ids`.
  5. DRAIN: `hard_cutoff == 0`. Also:
     - if `unserved_at_close > 0`, then `no_eligible_employee == unserved_at_close`,
       `drain_crew == []`, and the unserved rows' ids are exactly `waiting_customer_ids`. This is the
       approved X6 mechanism, confirmed from the engine's evidence;
     - if `drain_crew` is non-empty, then `unserved_at_close == 0`.

A failure raises `NamedCostError` with the evidence. Nothing is repaired.

## 8. D15 handling (APPROVED C11)

- D15 = UNKNOWN / undefined repository reference.
- 5B-5 adds no PASS/FAIL, no acceptance threshold, no Monte Carlo verdict, and no `verdict` field.
- Nothing is inferred from D15.
- Deterministic costing of one run does not depend on D15, so it is not blocked by it.

## 9. Statuses, zero, `None`, and missing values (APPROVED C8, C13, C14; PROPOSED names, approved with this text)

| Status | Quantity | Rate | Cost | In `total_cost` | Withholds `total_cost` |
|---|---|---|---|---|---|
| `COSTED` | determined, > 0 | supplied (finite, ≥ 0) | `Q × r` (0.0 when r = 0) | added | no |
| `ZERO_QUANTITY` | determined, exactly 0 | not required; echoed if supplied, never used | `0.0` | added (adds 0.0) | no |
| `RATE_MISSING` | determined, > 0 | `None` | `None` | — | **yes** |
| `HOURS_UNDETERMINED` (labor only) | `None`: θ is required and missing (C14) | echoed; not used | `None` | — | **yes** |
| `NOT_APPLICABLE` (unserved only) | reported (0) | echoed if supplied, never used | `None` | not a term | no |

These values are never conflated:

- **0.0** is an established zero: a zero quantity, or a supplied zero rate.
- **`None`** is "not established". It is never read as 0.
- **`NOT_APPLICABLE`** means the term is not part of this run's model.
- **`RATE_MISSING`** and **`HOURS_UNDETERMINED`** mean an input the calculation needs was not
  supplied.

The status names come from two places:

- `COSTED`, `RATE_MISSING`, and `NOT_APPLICABLE` are imported from `shared_day_cost` (line 27).
- `ZERO_QUANTITY` and `HOURS_UNDETERMINED` are defined in the new module. They are new names
  (PROPOSED).

| Component | Quantity (source) | Rate or threshold field | Required when |
|---|---|---|---|
| Regular labor, per employee | `regular_paid_hours` (section 5) | `regular_rate_per_hour` | the quantity is determined and > 0 |
| Overtime labor, per employee | `overtime_paid_hours` (section 5) | `overtime_rate_per_hour` | the quantity is determined and > 0 |
| Regular and overtime split, per employee | — | `daily_regular_paid_minutes` | `threshold_required` (C14) |
| Waiting | `queue.customer_hours_total` | `waiting_rate` | the quantity is > 0 |
| Unserved | `counts.unserved_at_close` | `unserved_customer_rate` | X6 applies and the quantity is > 0 |

- **Zero is tested exactly.**
  - A positive quantity, however small, requires its rate.
  - The tolerance never turns a quantity into zero.
  - A quantity that is zero only within tolerance is not zero.
- **When hours are undetermined:**
  - both labor components are `HOURS_UNDETERMINED`, with `rate_required: None`;
  - the `missing` list names `daily_regular_paid_minutes` as `required`;
  - it also lists any `None` rate of that employee as `requirement: "undetermined"` (5B-2
    precedent);
  - equal regular and overtime rates change none of this.
- **Totals:**
  - `labor.total_cost` = fsum of the employees' `labor_cost`, or `None` if any is `None`;
  - `total_cost` = fsum of the `COSTED` and `ZERO_QUANTITY` costs, or `None` if any component is
    `RATE_MISSING` or `HOURS_UNDETERMINED`.

  Every missing field is named with its scope, employee id, field, and status.
- **Rate validation:**
  - a supplied rate must be finite and 0 or more, and not a `bool` (Phase 3A and 5B-1 validation);
  - an overtime rate below the regular rate is allowed (5B-2 notes this case).

## 10. Interface and output schema (APPROVED C16; PROPOSED field names, approved with this text)

```text
module  backend/queueing_engine/services/shared_named_cost.py
NAMED_COST_VERSION = "novaq-shared-named-cost-v1"

@dataclass(frozen=True)
class NamedCostRates:                           # no defaults; None = not supplied (never 0)
    waiting_rate: float | None                  # per customer-hour waiting
    unserved_customer_rate: float | None        # per customer unserved_at_close

cost_named_workforce(result: dict, employees: Sequence[Employee], rates: NamedCostRates) -> dict
class NamedCostError(Exception)                 # .failure = {"check", "message", "evidence"}
                                                # NamedAttributionError from build_named_attribution propagates unchanged
```

- Labor rates and θ come from each input `Employee.pay`, which is the same `employees` list passed
  to attribution.
- The module is pure: it runs no simulation, draws no random numbers, and changes no input.

### 10.1 What is read, and what is computed

| Quantity | Where it comes from |
|---|---|
| on-duty hours, `hours_by_state`, the closing cells, break delay, shortening, and non-fulfilment, register wait, `off_hours`, and every attribution reconciliation value | **read** from the attribution output; never recomputed |
| paid or unpaid for each interval, the break mapping, `paid_hours`, `paid_break_hours`, `unpaid_break_hours`, the G, T, and F pieces, `threshold_required`, `threshold_reached_at_hours` | computed by the pay walk (sections 4 and 5), the new module's only responsibility |
| waiting customer-hours, unserved count and reasons, `at_close` | **read** from the named result; checked, never recomputed |

The pay walk visits the same validated intervals as attribution, but it produces no attribution
field. It reconciles with the attribution instead (section 11).

### 10.2 Output

```text
{
  "employees": [ {                                   # every input employee, employee_id order
    "employee_id": str,
    "pay": {"regular_rate_per_hour": float|None, "overtime_rate_per_hour": float|None,
            "daily_regular_paid_minutes": int|None},             # echoed EmployeePay; None kept
    "paid_hours": float,                                         # always determined
    "paid_break_hours": float, "unpaid_break_hours": float,      # ON_BREAK split by the paid flag
    "threshold_required": bool,                                  # C14
    "daily_threshold_hours": float|None,                         # θ / 60; None when not supplied
    "threshold_reached_at_hours": float|None,                    # derived instant (5.2 step 10)
    "hours_status": "DETERMINED" | "HOURS_UNDETERMINED",
    "regular_paid_hours": float|None,
    "overtime_paid_hours": float|None,
    "overtime_breakdown": {"past_end_or_after_closing_hours": float,         # always determined
                           "daily_threshold_only_hours": float|None},
    "shifts": [ {"shift_index": int, "activated": bool,                      # engine shift order
                 "paid_hours": float|None, "paid_break_hours": float|None,
                 "unpaid_break_hours": float|None,
                 "regular_paid_hours": float|None, "overtime_paid_hours": float|None,
                 "overtime_breakdown": {...}|None} ],        # all None when not activated
    "components": [ <component "regular_labor">, <component "overtime_labor"> ],
    "labor_cost": float|None,
    "labor_cost_withheld": [ {"field": str, "status": "RATE_MISSING"|"HOURS_UNDETERMINED"} ]
  } ],
  "labor": {"total_cost": float|None,
            "withheld": [ {"employee_id": str, "field": str, "status": str} ]},
  "waiting": <component "waiting">,
  "unserved": <component "unserved_customer"> + {
      "applicability_basis": {"closing_policy": str,
                              "rule": "X6 HARD_CUTOFF (inherited)" | "C10b DRAIN (realized)",
                              "unserved_at_close": int, "unserved_by_reason": {str: int},
                              "drain_crew": [str], "waiting_customer_count": int}},
  "total_cost": float|None,
  "missing": [ {"scope": "employee"|"run", "employee_id": str|None, "field": str,
                "status": "RATE_MISSING"|"HOURS_UNDETERMINED",
                "requirement": "required"|"undetermined"} ],
  "total_withheld_reason": str|None,                 # human-readable; None when total_cost is a number
  "formula": str, "currency": "The caller's currency; this module assumes none.",
  "reconciliation": [...], "definitions": {...}, "checks": {...}, "undetermined": [...],
  "provenance": {
    "cost_version": NAMED_COST_VERSION,
    "attribution_version", "named_engine_version", "state_machine_version", "closing_policy",
    "replication": {...}|None,                       # copied from the attribution provenance
    "inputs_sha256": None,
    "inputs_sha256_reason": "full run inputs unavailable: the module receives only the result, the
                             input employees, and the rates; no partial digest is computed (5B-4.6 D4)",
    "time_unit": "hours", "tolerance": {TOLERANCE, "applies_to": "reconciliation and D7 only;
                                        times, order, and the threshold instant compare exactly"},
    "capacity_terms_not_charged": "Phase 3A server-hour terms and staffing capacity (C2)",
    "scheduled_pay_not_mixed": "5B-1 scheduled pay is a planning quantity and is not part of this cost",
    "scope_note": "Modeled workforce cost; not an employment-law or payroll-compliance interpretation."
  }
}

<component> = {
  "component": "regular_labor" | "overtime_labor" | "waiting" | "unserved_customer",
  "quantity": float | int | None,          # None only with HOURS_UNDETERMINED
  "unit": "paid hours" | "customer-hours" | "customers",
  "source": str,                           # e.g. "queue.customer_hours_total"
  "rate_field": str,
  "rate": float | None,                    # the supplied value; None = not supplied
  "applies": bool,                         # False only for unserved_customer under C10b
  "rate_required": bool | None,            # True: applies and Q > 0; False: not applies or Q == 0;
                                           # None: Q undetermined
  "cost": float | None,
  "status": "COSTED" | "ZERO_QUANTITY" | "RATE_MISSING" | "HOURS_UNDETERMINED" | "NOT_APPLICABLE",
  "note": str | None
}
```

There is no `verdict` field, and there is no acceptance field (C11).

## 11. Validation checks (PROPOSED check list for the approved contract, approved with this text)

| Check | Rule |
|---|---|
| (attribution) | `build_named_attribution` must succeed. All 11 of its checks apply unchanged, and its error propagates unchanged |
| `rate_structure` | `rates` is a `NamedCostRates`. Each rate is finite and 0 or more (not a `bool`), or `None` |
| `pay_structure` | Each input `Employee.pay` is an `EmployeePay` that passes the 5B-1 value rules (`shared_workforce.py`, lines 199-208) |
| `result_structure` | Every field the module reads beyond attribution is present with the engine's type: `counts`, `customers`, `queue`, `at_close`, and each break's `paid` (a `bool`) |
| `break_mapping` | Section 4: exact containment, a unique break, and exact tiling of each started break |
| `paid_partition` | Per activated shift: `paid_hours + unpaid_break_hours` ≈ attribution `on_duty_hours`, and `paid_break_hours + unpaid_break_hours` ≈ attribution `hours_by_state[ON_BREAK]`. Per employee: the same identities against the attribution employee record |
| `overtime_partition` | Section 5.3, per shift and per employee. When determined, `regular + overtime ≈ paid`, and `regular ≤ θ_h` or ≈ θ_h. In every case, `F` + unpaid `ON_BREAK` time in the flagged cells ≈ attribution `after_closing_or_past_scheduled_end_hours`, and each part is ≥ 0 |
| `unserved_consistency` | Section 7, exact |
| `waiting_consistency` | `customer_hours_total` ≈ in-horizon + after-closing. Each is finite and ≥ 0 |
| `finite_nonnegative` | D7 (C15) for `R_k` and the crossing's `T` piece. Every hour and cost is finite and ≥ 0, or `None` only where section 9 allows it |
| `cost_arithmetic` | Each component's status and cost follow section 9. The totals are fsums of the `COSTED` and `ZERO_QUANTITY` costs, and `None` propagates as section 3 says |

- "≈" is the house tolerance (`TOLERANCE`), used only for reconciliation.
- Every check fails with evidence, and nothing is repaired.

## 12. Hand cases (expected values; hand-derived and probe-reproduced)

**Evidence.**

- The engine timelines and every hour, cost, and status below were reproduced on 2026-09-30 at
  `156de75f`.
- A scratch script applied sections 4, 5, 7, and 9 to the real engine output, after
  `build_named_attribution` succeeded on each run.
- The script is in the session scratchpad. It is not the implementation, it is not a test, and it
  is not committed.

**Data.** All data is synthetic:

- horizon 08:00-12:00 (hours 0-4), service rate 4 per hour;
- regular rate 20, overtime rate 30, and θ = 480 minutes, unless a case says otherwise;
- waiting rate 10 and unserved rate 50.

**Breaks.** The test helpers' breaks are paid: `BreakRequirement(name, minutes, True, 0, 480)` in
`tests/test_shared_employee_states.py`, line 80.

- Each "unpaid" variant uses `BreakRequirement("rest", 30, False, 0, 480)` with the same timing,
  which gives an identical timeline.
- A break rule applies by shift length, so in H1 the unpaid rule makes both A's and B's breaks
  unpaid.

| Case | Setup | Expected (hours; cost; status) |
|---|---|---|
| HC-A ordinary regular | A 08-12, no break, no customer, DRAIN | paid 4.0 = regular 4.0; overtime 0.0 (`ZERO_QUANTITY`); labor 80.0; waiting 0.0 (`ZERO_QUANTITY`); crew [A], nobody unserved, so `NOT_APPLICABLE`; total 80.0 |
| HC-B threshold in one shift | HC-A with θ = 180 | regular 3.0; threshold overtime 1.0; reached at 3.0; labor 60 + 30 = 90.0; total 90.0 |
| HC-B0 θ = 0 | HC-A with θ = 0 and the regular rate `None` | regular 0.0 (`ZERO_QUANTITY`, so no regular rate is required); threshold overtime 4.0, so 120.0; reached at 0.0; total 120.0 |
| HC-C threshold across split shifts, activation delay, delayed paid break | H4 roster; arrivals (0.5, 4.5), (1.75, 1.0), (2.75, 0.5); θ = 120 | shift 0 paid 0-1.625, past end 1.0-1.625 (F 0.625); `OFF` 1.625-2.125 (unpaid); shift 1 paid 2.125-3.5, including the paid break 2.625-2.875 (delayed 0.625 by late activation). Walk: G 0.5 + 0.5, then 0.25, then 0.125; the crossing is at 2.5 inside the interval 2.375-2.625. Regular 1.375; F 0.625; T 1.0; overtime 1.625; paid 3.0. Labor 27.5 + 48.75 = 76.25. Waiting 0.5, so 5.0. DRAIN crew empty and nobody unserved, so `NOT_APPLICABLE` (C10b). Total 81.25 |
| HC-D register waiting | H3 (one register) | A: regular 2.0 and F 0.25, so 47.5. B: paid 2.0, including 0.25 waiting for a register, all regular, so 40.0 (overtime `ZERO_QUANTITY`). Waiting 0.125 × 10 = 1.25. Crew [B], so `NOT_APPLICABLE`. Total 88.75 |
| HC-E delayed paid break past the shift end | H6 | paid 2.75; the break 2.25-2.75 (delayed 0.25 by service) is paid, and 2.5-2.75 is past the end (F 0.25); regular 2.5; labor 57.5. DRAIN crew empty, nobody unserved, so `NOT_APPLICABLE` (C10b: an empty crew alone does not make the term apply); total 57.5, with or without an unserved rate |
| HC-F delayed unpaid break | H6 with the unpaid rule | paid 2.25; the unpaid break 2.25-2.75 is neither paid nor counted, so there is no overtime (`ZERO_QUANTITY`); regular 2.25; labor 45.0; total 45.0 |
| HC-G unfulfilled unpaid break, worked instead | H7 with the unpaid rule | break `unfulfilled`, `released`, so no break time; paid 2.75; F 0.25 (serving past the end); regular 2.5; labor 57.5; `NOT_APPLICABLE`; total 57.5 |
| HC-H ordinary unpaid break and truncated unpaid break | H1 (DRAIN) with the unpaid rule | A: the break 0.5-1.0 is unpaid; paid 4.375; regular 3.5; F 0.875; labor 96.25. B: paid 0-3.75; the break 3.75-4.0 (delayed 0.25, truncated by closing) is unpaid; regular 3.75; overtime `ZERO_QUANTITY`; labor 75.0; no work follows (engine rule). C: no paid time, labor 0.0. Waiting 1.875, so 18.75; crew [A], so `NOT_APPLICABLE`; total 190.0 |
| HC-I shift overrun before closing | HC-D's A | covered in HC-D (past end only, before closing) |
| HC-J after closing, before the scheduled end | H5 (A 08-13), HARD_CUTOFF | paid 4.25; F 0.25 (after closing only); regular 4.0; labor 87.5. Unserved **applies** (HARD_CUTOFF) with quantity 0, so `ZERO_QUANTITY`, 0.0, and no rate is required; total 87.5, also with the unserved rate `None` |
| HC-K cancelled pending unpaid break, work after closing | A 08-13, unpaid break at 12:30; arrival (3.75, 2.0); DRAIN | break `cancelled_at_closing`; A serves 3.75-4.25; paid 4.25; F 0.25; regular 4.0; labor 87.5; crew [A], so `NOT_APPLICABLE`; total 87.5 |
| HC-L past end and after closing at once | H1 (DRAIN) A | 4.0-4.875 is both, counted once: F 0.875; regular 4.0; labor 106.25 |
| HC-M threshold, past end, and after closing at once | H1 with A's θ = 210 (B keeps 480) | A: regular 3.5 (reached at 3.5); T 3.5-4.0 = 0.5; F 4.0-4.875 = 0.875 (no second premium); overtime 1.375; paid 4.875; labor 70 + 41.25 = 111.25; run total 210.0. With θ = 240: reached exactly at 4.0 (a boundary: `R_k == ℓ_k`), with the same hours as HC-L and a run total of 205.0 |
| HC-N activation delay | HC-C shift 1 | 1.5-2.125 is `OFF`, so unpaid |
| HC-O HARD_CUTOFF | H1b | A: paid 4.375, F 0.375, so 91.25. B: paid 4.0 (paid break, truncated), so 80.0. C: 0.0. Labor 171.25. Waiting 0.875, so 8.75. Unserved 2 (`hard_cutoff`) × 50 = 100.0. Total 280.0 |
| HC-P DRAIN, crew serves | H1 | labor 106.25 + 80.0 + 0.0 = 186.25; waiting 1.875, so 18.75; two customers waited at closing and were served by crew [A], so nobody was unserved and the term is `NOT_APPLICABLE`; total 205.0 |
| HC-Q DRAIN, `no_eligible_employee` | A 08-11; arrival (3.5, 1.0); DRAIN | A paid 3.0, regular, so 60.0; crew empty; customer 1 unserved (`no_eligible_employee`, elapsed 0.5); the term applies (C10b realized); waiting 0.5, so 5.0; unserved 1 × 50 = 50.0; total 115.0 |
| HC-R missing regular rate | HC-A, regular rate `None` | regular labor `RATE_MISSING`; the employee labor, labor total, and `total_cost` are all `None`, naming `A.regular_rate_per_hour` |
| HC-S missing overtime rate | HC-B, overtime rate `None` (overtime 1.0) | `RATE_MISSING`; total `None`. With HC-A and the overtime rate `None` (overtime 0.0): `ZERO_QUANTITY`, and the total is 80.0 |
| HC-T missing waiting rate | HC-D, waiting rate `None` (0.125 customer-hours) | `RATE_MISSING`; total `None`. With HC-A and the waiting rate `None` (0.0): `ZERO_QUANTITY`, and the total is 80.0 |
| HC-U missing required unserved rate | HC-O and HC-Q, unserved rate `None` | `RATE_MISSING`; total `None`. With HC-J (HARD_CUTOFF, 0 unserved) and HC-E (DRAIN, 0 unserved): not required, so the totals are 87.5 and 57.5 |
| HC-V non-applicable unserved term | HC-P, unserved rate `None` or supplied | `NOT_APPLICABLE`; total 205.0; a supplied rate is recorded but not used |
| HC-W missing required threshold | HC-A, θ `None` | `threshold_required` true; `HOURS_UNDETERMINED`; regular and overtime `None`; total `None`, naming `A.daily_regular_paid_minutes` (not `RATE_MISSING`). The same with regular rate = overtime rate = 20 |
| HC-W2 missing threshold, flagged part known | H1b with A's θ `None` | A `HOURS_UNDETERMINED`; F 0.375 is still reported; regular, T, and overtime `None`; total `None` |
| HC-W3 threshold not required | H1 with C's pay all `None` | C has no paid time, so `threshold_required` is false: regular 0.0 and overtime 0.0, both `ZERO_QUANTITY`; labor 0.0; total 205.0 |

**Further required tests** (to be written in the implementation phase, not now; written 2026-09-30,
section 18.4):

- the seeded identities, on the 10 scenarios × 2 policies × 25 replications, reconciled with
  attribution;
- the status vocabulary: one test that tells 0.0, `None`, `NOT_APPLICABLE`, `RATE_MISSING`,
  `HOURS_UNDETERMINED`, and `ZERO_QUANTITY` apart;
- a supplied zero rate, which gives `COSTED` 0.0;
- the exact zero test: a tiny positive quantity still requires its rate;
- a tiny `G` or `T` slice from float lengths, which must be reported as computed and never snapped;
- malformed rates, pay, break mapping, `paid` type, counts, reasons, customer rows, and `at_close`;
- D7 on the two pay differences, through a scratch fault injection, because the branches are
  INFERRED unreachable;
- purity: no random numbers, no mutation, determinism;
- isolation: the module joins `SHARED_QUEUE_ENHANCEMENT_MODULES`, and imports no API or Separate
  Queue code.

## 13. Protected scope

- **Unchanged:**
  - the named DES engine v3 and the state machine v3;
  - attribution v1 (imported, not changed);
  - playback v4 (corrected 2026-09-30: this line read "playback v3", the version at `156de75f`; the
    implementation base `40ee8dbe` carries v4 from `b0040508`; section 14.1); replications method v2;
  - `services/shared_day_cost.py` (only its status constants are imported), and the Phase 3A rule
    that it keeps;
  - 5B-1, 5B-2, and 5B-3; the queueing mathematics and optimizers;
  - Separate Queue, API, frontend, and database; dependencies and fixtures;
  - existing rates and defaults (there are none).
- **No employment-law interpretation.** No output or text states what any law requires.

## 14. Implementation preconditions (merge order)

**Concurrent work (VERIFIED 2026-09-30, read-only):**

- Worktree `.claude/worktrees/unruffled-hawking-257d18` is on branch `fix/named-playback-overflow`.
- Its branch ref is still `156de75f`.
- It has uncommitted changes to `simulation/shared_named_playback.py` and
  `tests/test_shared_named_playback.py` (`git --no-optional-locks status --porcelain`).
- 5B-5 edits neither file.
- Attribution imports playback's `TOLERANCE` (attribution, line 44), and 5B-5 reuses that tolerance
  and `derived_duration`.

Whether the playback work changes anything 5B-5 depends on is **UNKNOWN**. Nothing is inferred
before it lands. Before 5B-5 implementation begins:

1. Inspect the final playback-hardening commit (its diff and message).
2. Confirm that the name, value, and module of `TOLERANCE`, attribution's import of it, and
   `derived_duration`'s signature and behavior are still compatible.
3. Establish the implementation base and merge order with the product owner.
4. Overwrite neither branch's work. One writer per file.

A further precondition: nothing is implemented until this text is approved. The approval covers
the PROPOSED names in sections 9-11 (`ZERO_QUANTITY`, `HOURS_UNDETERMINED`, the output field names,
and the check list).

### 14.1 Implementation-precondition corrections (2026-09-30)

The concurrent-work statement above was true when it was written and is kept as written. The
playback integration then made it, and the references below, stale. Checked on 2026-09-30 before
any 5B-5 code was written (VERIFIED):

- **Merge order and base.** `b0040508` (playback v4) was fast-forwarded into
  `feat/shared-queue-segments` at 12:54:13 +0800 (reflog "Fast-forward"; `156de75f..b0040508`). A
  documentation commit, `40ee8dbe` (`handoff.md` only), was then made on `fix/named-playback-overflow`
  at 13:03:42 and fast-forwarded into `feat/shared-queue-segments` at 13:03:55. The implementation
  base is `feat/shared-queue-segments` at `40ee8dbe`, as the product owner's implementation request
  states. Nothing was pushed.
- **Concurrent work.** The worktree `unruffled-hawking-257d18` is clean on
  `fix/named-playback-overflow`, which now also points at `40ee8dbe`; its playback changes are
  committed and integrated.
- **Preconditions 1 and 2 (section 14).** The `b0040508` diff changes only `shared_named_playback.py`,
  its test file, the playback spec, `handoff.md`, and `memory.md`. `TOLERANCE` is still
  `{"rel": 1e-9, "abs": 1e-12}` (a dict of floats) in `shared_named_playback` (line 233, formerly
  227), and attribution imports the same object (`TOLERANCE is shared_named_playback.TOLERANCE`).
  `shared_named_attribution.py` is byte-identical to `156de75f`, so `derived_duration` (lines
  260-267), its signature `(a, b, *, field)`, and every attribution v1 field 5B-5 reads are
  unchanged. The focused suites (attribution, playback, named DES, state machine, named
  replications, Phase 3A day cost, workforce, and segments) passed on `40ee8dbe`: 605 tests.
- **Versions at the base.** Playback `novaq-shared-named-playback-v4`, attribution v1, named engine
  v3, state machine v3, replications method v2.
- **Line references.** `NOT_PRODUCED_BY_THE_NAMED_ENGINE` moved from lines 149-156 to 152-159, with
  unchanged content. The other line references in section 1 point at files the integration did not
  change.

## 15. UNKNOWN, NOT TESTED, and resolved items

**Still UNKNOWN or NOT TESTED:**

1. **The contents of Phase 5A D6 and D8:** UNKNOWN. C5 is a new rule, not a restatement.
2. **D15:** UNKNOWN; handled by C11, with no verdict.
3. **The effect of the playback-overflow branch on the shared tolerance or D7:** UNKNOWN until its
   final commit is inspected (section 14). Resolved 2026-09-30 (section 14.1): no effect; the
   tolerance, `derived_duration`, and attribution v1 are unchanged (VERIFIED).
4. **Reachability of the C14 branch "paid time above 0, all of it flagged":** UNKNOWN.
   - No engine lifecycle producing it has been identified. In every hand-case run, each employee
     with paid time had some unflagged paid time (scratch probe).
   - The zero-paid-time branch is reachable (HC-W3).
   - The rule decides both branches either way.
   - Implementation 2026-09-30 (section 18.6): INFERRED unreachable, now with a code argument and a
     wider probe; tested at rule level.
5. **The D7 zero and failure branches inside the pay walk:** INFERRED unreachable (section 5.3);
   NOT TESTED. Implementation 2026-09-30 (section 18.5): still INFERRED unreachable; the mutants that
   replace either D7 call with a plain subtraction survive as equivalent, and the D7 failure path of
   the wrapper is tested directly.
6. **Tiny `G` or `T` slices from float event times on seeded runs:** NOT TESTED; they are reported
   as computed. Implementation 2026-09-30 (section 18.6): engine-reachable on a 5-minute roster and
   tested there; on the seeded runs, the exact-arithmetic comparison holds within the tolerance, and
   whether a tiny slice occurs on them is NOT TESTED.
7. **Cross-version numpy stream equality:** UNKNOWN (replications only).
8. **Cross-replication cost aggregation:** out of scope (C12). Any later need requires its own
   approval.

**Resolved by the 2026-09-30 decisions:**

- the conflicting precedents on when a rate is required (C13-U, for 5B-5 only);
- the DRAIN applicability basis (C10b; C10a rejected);
- the unconstructible break case (removed; the engine limitation is recorded in section 6).

## 16. Revision record (2026-09-30, specification only)

- **Header and section 2:** the decisions are recorded as approved. C10 is C10b only. C13 is Option U,
  applied to all four quantities, unserved included. C14 is refined as `threshold_required`. C15
  gives its exact timing boundary. C16 gives its non-duplication rule.
- **Section 1:** added the facts the finalized rules depend on:
  - attribution does not validate `paid`;
  - `at_close` starts as `{}`;
  - the customer rows and the reason keys;
  - break outcomes and causes;
  - the day boundary;
  - `_overtime_start`'s "exceeds";
  - D7 and `TOLERANCE`.

  The named-replications spec was added to the related specs.
- **Section 3:** exact cost equations, with the `cost(Q, r)` rule.
- **Sections 4 and 5:**
  - the break mapping now validates `paid` and requires exact tiling;
  - the walk is fully specified, with the exhaustion test, the pieces, a monotone `exhausted` flag,
    and the threshold-reached instant, including the boundary and θ = 0 cases;
  - the θ-not-required path is added;
  - D7 applies to exactly two differences.
- **Section 6:** the "shortened unpaid break with work replacing it" hand case is removed as
  unconstructible. Reachable cases are named for each break type.
- **Section 7:** rewritten for C10b. `unserved_consistency` now reconciles the counts, the customer
  rows, `waiting_customer_ids`, and `drain_crew`, without recomputing eligibility.
- **Section 9:** the new `ZERO_QUANTITY` status (C13: "cost is mathematically zero"). The earlier
  draft used `NOT_APPLICABLE` for a zero quantity, which conflated the two. The zero-versus-`None`
  table is added.
- **Section 10:**
  - `paid_hours_by_state` is removed (it would have recomputed attribution's `hours_by_state`) and
    replaced by `paid_break_hours` and `unpaid_break_hours`;
  - `threshold_required`, `hours_status`, `rate_required`, `missing`, and the structured `withheld`
    lists are added;
  - `applicability_basis.rule` records C10b.
- **Section 11:** added `result_structure`. Refined `paid_partition` and `overtime_partition`, so
  that they reconcile with attribution rather than recompute it.
- **Section 12:**
  - HC-C, HC-E, HC-J, HC-U, and HC-W restated under C10b, C13-U, and C14;
  - HC-H corrected: the shared break rule also makes A's break unpaid;
  - added HC-B0, HC-W3, the zero-quantity variants, and equal rates under a missing θ;
  - every value re-reproduced by a scratch probe.
- **Sections 14-15:** the merge-order precondition, and the updated UNKNOWN list.
- **Unchanged:** C1-C9, C11, and C12, as approved.

**Approval record (2026-09-30, after the product owner's approval; specification only):**

- **Header:** the status is APPROVED SPECIFICATION. Implementation has not started, and the file is
  uncommitted.
- **Section 17:** restores the completion boundary. The finalization pass dropped the first draft's
  section 15, "Proposed completion boundary", and this record did not list the removal. The restored
  text is that section's, with two changes on the product owner's instruction: the closing approval
  line now states the approved state, and a final complete diff review is added before the commit.
- **No other section changed.** The VERIFIED statements still describe `156de75f`.

## 17. Completion boundary (APPROVED; restored 2026-09-30)

This is the already-approved implementation scope, restored as section 16 records. It is not a new
policy decision.

- **Files:**
  - new `services/shared_named_cost.py` and `tests/test_shared_named_cost.py`;
  - `tests/test_shared_segments.py` (isolation set only);
  - this spec and a plan;
  - the policy spec's 5B-5 row, P1, P9, and X6 (dated corrections, keeping the original text);
  - `handoff.md` and `memory.md`.
- **Fault injection:** on a scratch copy, as in 5B-4.6.
  - Every reachable check must be killed.
  - Equivalent and unreachable mutants are justified with evidence.
  - Timeouts are recorded as TIMEOUT.
- **Gates, narrow to broad:**
  - the focused suites;
  - all `tests/test_shared_*.py` (Shared Queue regressions);
  - the 20 Separate Queue files (Separate Queue regressions);
  - `python -m pytest tests/ -x --tb=short`;
  - `ruff check .`, `mypy . --exclude '^outputs/'`, and `git diff --check`.
- **Final complete diff review** before the commit.
- **One local implementation commit.** No push, merge, or deploy.
- **Approval:** this specification, C1-C16, and C10b are approved (header). Implementation has not
  started. (Superseded 2026-09-30: implemented; section 18.)

## 18. Implementation record (2026-09-30)

Base: `feat/shared-queue-segments` at `40ee8dbe` (section 14.1). One local commit; not pushed, merged,
or deployed. Every statement below is VERIFIED from the code, the tests, or the recorded runs unless it
carries another label.

### 18.1 Files

- New `backend/queueing_engine/services/shared_named_cost.py` (`novaq-shared-named-cost-v1`).
- New `tests/test_shared_named_cost.py`: 53 test functions, 137 tests.
- `tests/test_shared_segments.py`: the module joins `SHARED_QUEUE_ENHANCEMENT_MODULES` (one line).
- Documentation: this spec (header, sections 3 and 9-11 headings, 12, 14.1, 15, 17, and 18), the
  plan, the policy spec (dated corrections to P1, P9, X6, and the 5B-5 row, keeping the original
  text), `handoff.md`, and `memory.md`.

### 18.2 Interface and pipeline

- Public names: `cost_named_workforce(result, employees, rates)`, `NamedCostRates`, `NamedCostError`
  (`failure` = check, message, evidence), `NAMED_COST_VERSION`, `ZERO_QUANTITY`, `HOURS_UNDETERMINED`,
  `PAID_STATES`, `CHECKS`, `DEFINITIONS`, `RECONCILIATION`, and `UNDETERMINED`. `COSTED`,
  `RATE_MISSING`, and `NOT_APPLICABLE` are imported from `shared_day_cost`, which is unchanged.
- Order:
  1. `build_named_attribution` (its `NamedAttributionError` propagates unchanged; it runs first, so
     a malformed result is reported before malformed rates);
  2. `rate_structure`, `pay_structure`, `result_structure`, and `break_mapping`;
  3. per employee: the pay walk (a D7 failure is `finite_nonnegative`), `paid_partition`, and
     `overtime_partition`;
  4. `unserved_consistency` and `waiting_consistency`;
  5. the components, then `finite_nonnegative` and `cost_arithmetic` on the output.
- The output follows section 10.2; a test pins its key order. Attribution quantities are read, never
  recomputed. The result's `staffing` and `trace` are never read (a test sets them to `None`).

### 18.3 Implementation choices within the approved text

None changes an approved rule.

1. **`total_cost` grouping (CONFLICTING within this spec, at float-rounding level only).** Section 3
   writes `C_total = fsum(L, W, U)`; sections 9 and 11 define `total_cost` as the fsum of the
   `COSTED` and `ZERO_QUANTITY` component costs. The two groupings can differ only by rounding. The
   implementation follows sections 9 and 11 (`cost_arithmetic`). `labor.total_cost` is the fsum of the
   employees' `labor_cost`, and each `labor_cost` is the fsum of its two component costs, where
   sections 3 and 9 agree. On the hand cases, all binary-exact, both groupings give the same values.
2. **DRAIN with an empty crew (`unserved_consistency`).** Section 7 rule 5 checks a positive unserved
   count and a non-empty crew. The implementation also requires, with an empty crew, that the unserved
   ids equal the waiting ids, so an empty crew with customers waiting and nobody unserved fails. This
   is the engine's X6 rule (`shared_named_des.py`, lines 416-417: with an empty crew, every waiting
   customer is unserved). It changes no cost of a valid run.
3. **Withheld lists.** `labor_cost_withheld` and `labor.withheld` name only required items (a
   missing required rate or threshold). A `None` rate beside a missing required threshold appears only
   in `missing`, with status `HOURS_UNDETERMINED` and requirement `undetermined` (section 9).
4. **Ranges.** `result_structure` checks presence and types; `unserved_consistency` and
   `waiting_consistency` check the values. A rate, pay rate, or queue integral beyond the float range
   (for example `10**400`) fails its check instead of raising `OverflowError`, and so does a threshold
   whose hours are beyond the float range (`pay_structure`).
5. **Internal quantity.** `overtime_partition` uses the unpaid ON_BREAK hours in flagged intervals;
   they are not an output field.
6. **`total_withheld_reason`** reads `Withheld: <employee id or run>.<field> (<status>)`, joined by
   semicolons, over the required items.

### 18.4 Tests (`tests/test_shared_named_cost.py`)

- Hand cases HC-A to HC-W3 (section 12). Every expected value is derived by hand in the comments from
  the scenario's timeline and C1-C16. Each run goes through the independent 5B-4.3 checker, and each
  pay-bearing run equals the pay-free run.
  - The explicit regression for earlier flagged overtime consuming the threshold before later
    unflagged split-shift time (the threshold is never reset between split shifts) is HC-C, plus a
    theta = 105 minutes variant.
- Two paid, and two unpaid, breaks in one shift. Paid and unpaid variants of five seeded scenarios
  give identical timelines apart from the flag.
- Status rules: the C10b asymmetry (HARD_CUTOFF with zero unserved: `applies` true, `ZERO_QUANTITY`,
  0.0, no rate required; DRAIN with zero unserved: `NOT_APPLICABLE`); the status vocabulary; a
  supplied zero rate (`COSTED` 0.0); and a waiting quantity of 2**-51 h that still requires its rate.
- Seeded identities on the 10 named scenarios × 2 policies × 25 replications, with thresholds of 0,
  45, 180, and 480 minutes in turn. Every employee's G, T, and F sums and threshold instant match an
  independent exact-arithmetic (`Fraction`) walk within the tolerance, and the partition, labor,
  waiting, unserved, and total identities hold.
- Rule-level tests on synthetic intervals, labeled as such: the C14 all-flagged branch; the instant at
  the previous interval's end through float sums; the boundary `R_k == l_k` on the last interval;
  the D7 wrapper's failure path.
- Malformed inputs, each failing its named check: 9 rate, 11 pay, 20 result-structure, 4
  break-mapping, 19 HARD_CUTOFF and 5 DRAIN unserved-record, 7 queue, and 3 overflow cases.
  Attribution failures propagate unchanged. Direct tests show the partition and output self-checks
  fire on inconsistent records.
- Purity (no random numbers, no change to the result, employees, rates, or attribution, and no
  shared mutable output), schema, provenance, replication identity, and isolation.

### 18.5 Fault injection

Run on four scratch copies of `backend/`, `tests/`, and `pyproject.toml`; the working tree was
untouched. Each mutant ran `tests/test_shared_named_cost.py` with `-x`.

- 106 mutants: a sentinel; 11 rate and pay validation; 6 result structure; 13 break mapping and paid
  time; 20 pay walk and D7; 6 hour sums; 6 partitions; 14 unserved consistency; 3 applicability
  (C10b); 4 waiting; 15 components and totals; 7 output checks and provenance.
- First pass: 86 killed, 20 survived.
  - Eight were reachable test gaps, and a test was added for each: the instant after an unpaid gap;
    the boundary on the last interval; an extra unserved row with an unknown or no reason; a
    consistent negative queue; the `labor_cost_withheld` content; a valid shift with two breaks; a
    break starting before its first interval; and the overflow evidence field.
  - Six were the partition checks (input-unreachable, below); a direct self-check test was added.
  - One (a zero-length T piece when `R_k == l_k`) was output-equivalent; a piece-level assertion was
    added.
- Final pass, on the final code and tests: 101 killed, 5 survived, 0 timeouts, 0 harness failures;
  the four unmutated baselines passed. The 5 survivors are equivalent:
  - `remaining < length` made `<=`: the branch follows `if remaining == length`, so equality never
    reaches it.
  - Either D7 call replaced by a plain subtraction (two mutants): each difference is taken only after
    an exact comparison shows `a > b`, and IEEE-754 subtraction of distinct finite doubles is nonzero
    with the correct sign, so D7 returns the plain difference.
  - Unpaid break hours without the ON_BREAK condition: every on-duty non-break state is in
    `PAID_STATES` (pinned by a test), so only an ON_BREAK row can be unpaid.
  - The replication identity not copied: attribution builds a fresh provenance dict and `spawn_key`
    list on every call (`shared_named_attribution.py`, lines 736-740), and that output is local to
    the cost call.
- `paid_partition`, `overtime_partition`, and `cost_arithmetic` are input-unreachable through the
  public function: the walk and attribution sum the same validated intervals, partitioned into paid
  and unpaid (and G, T, and F) pieces, and the components are built by the rules the check restates.
  They are kept because this spec requires them; direct tests show each fires on an inconsistent
  record.

### 18.6 Reachability evidence

- **C14, paid time above 0 that is entirely flagged:** INFERRED unreachable.
  - A split shift activates only before its scheduled end (`shared_employee_states.py`, lines
    496-498), and a closing Release stops every later activation (lines 584-588); within one instant,
    closing is processed before shift starts (lines 657-673).
  - An interval's flags are set from closing and the shift end when it is recorded (lines 426-427),
    so each activated shift's first on-duty interval is unflagged.
  - If that interval is an unpaid break, the break ends in a release (at or past the scheduled end, or
    truncated at closing) or is followed by unflagged paid time.
  - A scratch probe of 2,500 cost runs (10 scenarios × 2 policies × 25 replications × 5 thresholds)
    found no such employee, and no failure. The branch is tested at rule level.
- **Tiny slices:** engine-reachable. A shift 08:15-10:45 with a paid 20-minute break at 08:20 and a
  5-minute threshold leaves a G piece of 2**-56 h at the break start, where the exact threshold
  instant is the boundary. The piece is kept (`regular_paid_hours` is 5/60, not 20/60 - 0.25), and the
  derived instant rounds to 20/60. A scratch search of 5,808 roster and threshold combinations found
  66 pieces below 1e-9 h.

### 18.7 Gates on the final code

- Focused: cost 137, attribution 141, state machine 39, named DES 65, named replications 73,
  playback 167, segments 51, pin 9, and Phase 3A day cost 16, all passed.
- All 16 `tests/test_shared_*.py` files: 1139 passed.
- Separate Queue (the 20 files matching `separate|queue_lifecycle|routing`): 182 passed.
- Full backend suite (`python -m pytest tests/ -x --tb=short`): 2172 passed, 3 skipped, 1 xfailed, 6
  subtests passed (734 s), which is the 2035 recorded for playback v4 plus the 137 new tests. The
  skips are the three `test_real_postgres_upgrade_paths_preserve_ownership` cases (PostgreSQL
  rehearsal; the reason was not printed); the xfail is the known
  `test_selected_mc_load::test_novamart_failing_lanes_are_stable_across_base_seeds`.
- `ruff check .`: clean. `mypy . --exclude '^outputs/'`: no issues in 180 files. `git diff --check`:
  clean.
- The documentation was edited after the gates; no test reads these files.

### 18.8 Protected paths (compared with `40ee8dbe`)

Unchanged: named DES v3, state machine v3, attribution v1, playback v4, replications method v2,
`shared_day_cost.py`, 5B-1 to 5B-3, the optimizers and queueing mathematics, Separate Queue, API,
database, frontend, dependencies, and fixtures. The only tracked code file changed is
`tests/test_shared_segments.py` (one line).

### 18.9 Still UNKNOWN, INFERRED, or CONFLICTING

- Phase 5A D6 and D8 contents: UNKNOWN. D15: UNKNOWN; no verdict (C11).
- The C14 all-flagged branch and the D7 branches in the walk: INFERRED unreachable.
- Tiny slices on the seeded runs: NOT TESTED. Cross-version numpy stream equality: UNKNOWN.
- The `total_cost` grouping: CONFLICTING at rounding level within this spec (18.3).
- Cross-replication cost aggregation, an acceptance rule, and API or UI exposure: out of scope; each
  needs its own approval.
