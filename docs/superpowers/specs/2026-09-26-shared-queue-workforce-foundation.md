# Shared Queue Enhancement: Phase 5B-1, Workforce Foundation

Date: 2026-09-26. Status: approved for Phase 5B-1 only by the product owner.

Scope: one pure module and its tests. There is no solver, no DES change, no cost
integration, and no API, schema, scenario, frontend, Decision, or Report change. The Phase 5A
design report (2026-09-25, chat) is the context; its open decisions D1 to D16 stay open unless
stated below.

## Starting point (verified)

- HEAD is `a244e5b9`. The Phase 1 to 4 shared modules exist, and 274 shared tests pass.
- Workforce today:
  - The shared queue has only anonymous server counts, and `analysis_schemas.py` rejects breaks
    for shared queues.
  - Staff and breaks sheets, lane breaks, and `PRE_BREAK_CUTOFF_MINUTES` belong to the separate
    queue. None of them is used or assumed here.

## Module `services/shared_workforce.py`

Times are whole minutes since midnight in `[0, 1440]` (the Phase 1 unit). Intervals are
half-open `[start, end)`. Minutes are exact integers; hours = minutes / 60.

### Inputs (all required fields have no default; `None` means "not supplied")

- `Employee(employee_id, availability, pay)`
  - `employee_id`: 1 to 64 characters, letters, digits, `.`, `_`, or `-`, starting with a letter
    or digit. This rejects spaces and `@`, but pseudonymity itself cannot be verified; ids
    should be pseudonymous.
  - `availability`: one or more non-overlapping `AvailabilityWindow(start_minute, end_minute)`.
  - `pay`: an `EmployeePay(regular_rate_per_hour, overtime_rate_per_hour,
    daily_regular_paid_minutes)`. Each field is `None` or a valid value. Rates are finite and
    0 or more; the threshold is a whole number, 0 or more. Nothing is costed in this phase;
    the values are only validated and checked for completeness.
- `ShiftRules`:
  - `earliest_start_minute`, `latest_end_minute`, `min_shift_minutes`, `max_shift_minutes`;
  - `boundary_granularity_minutes`: shift starts and ends must be multiples of it, counted from
    midnight;
  - `max_shifts_per_employee`;
  - `min_minutes_between_shifts`: required when more than one shift is allowed, and `None`
    otherwise.
- `BreakRule(min_shift_minutes, max_shift_minutes, min_gap_minutes, breaks)` applies to shifts
  whose length is within its closed range. The ranges must not overlap. A shift length that
  no rule covers is reported, not assumed break-free. An explicit rule with an empty `breaks`
  tuple is how a break-free length is declared.
- `BreakRequirement(name, duration_minutes, paid, earliest_start_offset_minutes,
  latest_start_offset_minutes)`. Offsets are measured from the shift start, and `paid` must be
  an explicit bool.
- `WorkforceRules(shift_rules, break_rules, register_count)`, where `register_count` (≥ 1) is
  the number of physical service points.
- Roster: `ScheduledShift(employee_id, start_minute, end_minute, breaks)` with
  `ScheduledBreak(name, start_minute)`. A break's length and paid status come from its rule and
  are never repeated in the roster. A scheduled shift assigns the employee to staff one server
  whenever they are on shift and not on break. Registers have no identity in this phase (Phase
  5A D4 and D7 are open).
- Optional `required_staffing`: Phase 1 `StaffingSegment`s tiling the horizon, for example
  from `staffing_from_capacity_result`.

Malformed inputs raise `SharedSegmentError` with every problem listed: types, ranges,
duplicate ids, overlapping windows or rule ranges, or segments that do not tile the horizon.

### Roster violations (reported, not raised; each has a code, an employee, a shift, and a reason)

| Code | Violation |
|---|---|
| `UNKNOWN_EMPLOYEE` | The shift names an employee who is not in the input. |
| `OUTSIDE_AVAILABILITY` | The shift is not inside one availability window. |
| `OUTSIDE_SHIFT_BOUNDARIES` | The shift starts before the earliest start or ends after the latest end. |
| `SHIFT_LENGTH` | The shift length is outside `[min, max]`. |
| `OFF_GRID` | A shift start or end is not a multiple of the granularity. |
| `TOO_MANY_SHIFTS` | The employee has more shifts than allowed. |
| `SHIFT_OVERLAP` | Two shifts of one employee overlap. |
| `INSUFFICIENT_REST` | The gap between two shifts is below the minimum. |
| `NO_BREAK_RULE` | No break rule covers the shift length. |
| `BREAK_MISSING` | A required break is not scheduled. |
| `BREAK_UNKNOWN` | A scheduled break is not in the applicable rule. |
| `BREAK_DUPLICATE` | A break name is scheduled twice. |
| `BREAK_WINDOW` | The break starts outside its offset window. |
| `BREAK_OUTSIDE_SHIFT` | The break does not lie inside the shift. |
| `BREAK_OVERLAP` | Two breaks overlap. |
| `BREAK_GAP` | Two breaks are closer than `min_gap_minutes`. |
| `REGISTER_CAPACITY` | Active servers exceed `register_count`; the interval and counts are given. |

### Status

- `INVALID`: any violation.
- `INCOMPLETE`: no violation, but a pay value is missing; the missing fields and their
  consequences are listed.
- `COMPLETE`: no violation and nothing missing.

Coverage shortfall is reported but does not make a roster invalid.

## Definitions (per employee e; shifts `[a_s, b_s)`; breaks `[u_k, u_k + d_k)` with paid flag π_k)

| Quantity | Definition |
|---|---|
| Scheduled employee-minutes | S = Σ_s (b_s − a_s) |
| Break minutes | B = Σ_k d_k = B_paid + B_unpaid |
| Paid employee-minutes | P = S − B_unpaid |
| Scheduled active server-minutes | A = S − B, split into inside and outside the operating horizon |
| Regular paid minutes | R = min(P, θ), θ = `daily_regular_paid_minutes` |
| Overtime paid minutes | O = P − R |

- R and O are `None` when θ is missing.
- Overtime starts at the instant when paid time, walked in clock order (shifts minus unpaid
  breaks), first reaches θ. Regular and overtime are therefore disjoint by construction.
- The active server count is n(t) = the number of employees on shift and not on break at t.
  Its integral equals Σ_e A, and its steps are reported as `[start, end, count)` intervals.
- Register check: n(t) ≤ `register_count` for every t.
- Coverage, per staffing segment j with required count c_j:
  - shortfall server-minutes = ∫_j max(0, c_j − n) dt;
  - surplus server-minutes = ∫_j max(0, n − c_j) dt;
  - the minimum and maximum of n over the segment.
- Identities that are checked: S = P + B_unpaid = A + B; P = A + B_paid; R + O = P.

These are **scheduled** quantities. They are not simulated service or busy time: service
time comes only from the DES, and this module produces no optimized roster and no cost.

## Verification

- Hand-computed synthetic fixtures (labeled as test data): one shift with a paid and an
  unpaid break, split shifts, and overtime crossing a break.
- One test per violation code, and malformed-input rejection.
- Register-capacity intervals, coverage shortfall and surplus, and the identities on random
  valid rosters.
- The isolation test, the shared and separate suites, the full backend suite, ruff, and mypy.
