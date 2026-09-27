# Shared Queue Enhancement: Phase 5B-2, Sequential Rostering MILP

Date: 2026-09-26. Status: approved for Phase 5B-2 only by the product owner.

Scope: one pure module and its tests. It adds no named-employee DES, no workforce cost
integration, and no API, schema, scenario, frontend, Decision, or Report change. The Phase 5A
design report (2026-09-25, chat) is the context.

## Starting point (verified)

- HEAD is `3f49a43a`. The 5B-1 module `services/shared_workforce.py` exists, and its 53 tests
  pass.
- Solver:
  - `scipy.optimize.milp` (HiGHS) works locally: Python 3.13.13, scipy 1.17.1, numpy 2.4.6,
    HiGHS 1.12.0.
  - It also works in the running `novaq-api-1` container: Python 3.11.16, scipy 1.17.1, numpy
    2.2.6, HiGHS 1.12.0. A test MILP returned status 0.
  - CI installs `requirements.txt` (`scipy>=1.14`), so the CI solver version is UNKNOWN.
  - No backend module used `milp` before this phase.
- HiGHS 1.12.0 defaults, read from its options object: `mip_rel_gap` 1e-4, `mip_abs_gap` 1e-6,
  `mip_feasibility_tolerance` 1e-6, `time_limit` inf. scipy exposes only `mip_rel_gap`,
  `time_limit`, `node_limit`, `presolve`, and `disp`.

## Decisions

- Phase 5A decisions settled by the product owner for this phase:
  - D1, sequential only. Phase 2's selected server counts are the coverage target.
  - D2, `scipy.optimize.milp`.
  - D11, hard coverage: at least the required servers at every instant, and no shortfall in a
    feasible result.
  - D16, split shifts through the 5B-1 rules.
- D3, break placement (answered 2026-09-26): the caller supplies
  `break_start_granularity_minutes`, with no default. A break may start only at a clock minute
  that is a multiple of it, counted from midnight like shift boundaries. Results are optimal
  over rosters on this grid. A grid of 1 covers every 5B-1-valid placement.
- Surplus (answered 2026-09-26): surplus server-minutes are counted and reported. Their cost is
  the wages already in the labor cost, and there is no separate surplus rate or term.
  Surplus is not attributed to individual employees, because which employee is "surplus" at a
  given minute is not unique. It is measured only inside the operating horizon. Active time
  outside the horizon has no requirement (UNKNOWN, not zero) and is reported separately.
- Solver limits are required inputs with no defaults, like the Phase 4 replication count:
  `time_limit_seconds` (a number, or `None` for no limit), `mip_rel_gap`, and `max_patterns`
  (a cap on generated patterns). The HiGHS defaults that are not exposed (`mip_abs_gap`,
  `mip_feasibility_tolerance`) are not changed and are reported.
- Settled by 5B-1 and unchanged:
  - one day;
  - the daily threshold `daily_regular_paid_minutes` for overtime;
  - paid and unpaid breaks from the rule;
  - every employee can staff every register;
  - registers are counted, not identified.

  Overtime after the shift end or after closing arises only in simulation (Phase 5A D6 and D8)
  and is outside this phase.

## Module `services/shared_rostering.py`

### Inputs

- The 5B-1 `OperatingHorizon`, `Employee`s, and `WorkforceRules`, validated by
  `validate_workforce_inputs`.
- `required_staffing`: Phase 1 `StaffingSegment`s tiling the horizon. It is required.
  `optimize_roster_for_capacity_plan` builds it from a Phase 2 result with
  `staffing_from_capacity_result`, and checks that the plan's horizon matches.
- `RosterOptimizationConfig(break_start_granularity_minutes, time_limit_seconds, mip_rel_gap,
  max_patterns)`. Every field is required.

Malformed inputs raise `SharedSegmentError` with every problem listed.

### Patterns

A pattern q is one shift `[s_q, f_q)` of one employee, with every break of its rule placed. It
is admissible when it passes every 5B-1 single-shift check:

- the shift boundaries, length, boundary grid, and availability;
- a break rule exists for its length;
- every break is placed once, inside its offset window and inside the shift;
- breaks do not overlap and respect the rule's minimum gap.

Every break must also start on the break grid. Pattern generation enumerates exactly this set.
The count is capped at `max_patterns`; the run stops with `PATTERN_LIMIT_EXCEEDED` rather than
truncating.

For each pattern:

- p_q = paid minutes = length − unpaid break minutes;
- a_{q,i} = 1 when the pattern is active (on shift, not on break) over the elementary
  interval i.

### Formulation

- Elementary intervals i come from the breakpoints of every pattern's active intervals, the
  horizon, and the segment boundaries. Every pattern's activity is constant on each one, so
  interval constraints are exact in continuous time.
- c_i is the required servers of the segment containing i (inside the horizon only). K is
  `register_count`, k is `max_shifts_per_employee`, and ρ is `min_minutes_between_shifts`.
- Variables: x_q ∈ {0,1}, one per pattern. When split shifts are allowed (k > 1), employees
  whose pay splits into regular and overtime also get R_e, O_e ∈ ℤ≥0 and w_e ∈ {0,1}. Every
  variable is integer.

```
minimise   Σ_e labor_e / 60                                  (currency per hour × minutes / 60)
subject to Σ_q a_{q,i} x_q ≥ c_i         every i inside the horizon      (coverage)
           Σ_q a_{q,i} x_q ≤ K           every i, whole day              (registers)
           Σ_{q∈Q_e} x_q ≤ k             every e                         (max shifts)
           Σ_{q∈Q_e: s_q ≤ t < f_q+ρ} x_q ≤ 1   every e, every start t   (only when k > 1)
```

- The last constraint is exact for split shifts. Two shifts of one employee conflict exactly
  when their intervals extended by ρ, `[s, f+ρ)`, intersect: they overlap, or the rest between
  them is below ρ. Those extended intervals form an interval graph, whose maximal cliques are
  found at left endpoints. When k = 1, the max-shifts row alone applies.
- Labor per employee e, with θ_e the daily threshold, r_e and o_e the rates, P_e = Σ p_q x_q,
  and P̄_e the exact maximum admissible paid minutes (a weighted interval-scheduling recursion
  over shifts with at most k shifts and rest ρ):

| Case | labor_e | Rates required |
|---|---|---|
| no admissible pattern | none (no variables) | none |
| P̄_e = 0 | 0 | none |
| θ_e = 0 | o_e · P_e | o_e |
| P̄_e ≤ θ_e | r_e · P_e | r_e |
| otherwise, k = 1 | Σ_q (r_e · min(p_q, θ_e) + o_e · max(0, p_q − θ_e)) · x_q | r_e, o_e |
| otherwise, k > 1 | r_e · R_e + o_e · O_e, with P_e = R_e + O_e, R_e ≥ θ_e·w_e, O_e ≤ (P̄_e − θ_e)·w_e, 0 ≤ R_e ≤ θ_e | r_e, o_e |

- With k = 1, an employee works at most one pattern, so each pattern's regular and overtime
  minutes are known and its cost is exact. This keeps the LP relaxation tight. With the big-M
  form instead, HiGHS did not prove optimality on a 4-employee synthetic case in 30 s. With exact
  pattern costs, it proved optimality in about 15 s, about 12 s of it presolve.
- The last row forces R_e = min(P_e, θ_e) and O_e = P_e − R_e, whatever the rates. With w = 0,
  O = 0 and so R = P ≤ θ. With w = 1, R = θ and so O = P − θ ≥ 0. A P below θ makes w = 1
  infeasible, and a P above θ makes w = 0 infeasible. This matches the 5B-1 definitions exactly,
  even when the overtime rate is below the regular rate.

### Missing inputs (reported as `INCOMPLETE`; nothing is solved and no cost is invented)

- An admissible shift (on grid, inside availability and boundaries, with a permitted length)
  whose length has no break rule. Its breaks are unknown, so the pattern set is incomplete.
- A pay value the objective needs, per the table above:
  - θ_e when P̄_e > 0;
  - when θ_e is missing, any missing rate is also listed, because whether it is needed cannot
    be decided without θ_e.
- A pay value that the objective does not need, such as an overtime rate when no admissible
  plan reaches θ_e, is not required. The embedded 5B-1 roster evaluation still lists it under
  its own completeness rule.

### Infeasibility certificates (checked before solving; exact)

- `REQUIREMENT_EXCEEDS_REGISTERS`: some segment requires more servers than K.
- `INSUFFICIENT_WORKFORCE`: in some elementary interval, fewer employees have any pattern
  active there than required. Each employee is active at most once at an instant. This check is
  valid only when the pattern set is complete.

### Solving and statuses

The MILP runs with `presolve` on, the caller's `mip_rel_gap`, and `time_limit_seconds` when
given.

| Status | Meaning | Feasibility |
|---|---|---|
| `INCOMPLETE` | Required inputs missing (above) | UNKNOWN |
| `PATTERN_LIMIT_EXCEEDED` | More than `max_patterns` patterns | UNKNOWN |
| `INFEASIBLE` | A certificate above, or HiGHS status 2 | INFEASIBLE |
| `OPTIMAL` | HiGHS status 0, and verification passed | FEASIBLE |
| `FEASIBLE_NOT_PROVEN_OPTIMAL` | HiGHS status 1 with an incumbent, and verification passed | FEASIBLE |
| `NO_SOLUTION_FOUND` | HiGHS status 1 without an incumbent | UNKNOWN |
| `SOLVER_ERROR` | HiGHS status 3 or 4 | UNKNOWN |
| `VERIFICATION_FAILED` | The solver's vector failed an exact check below | UNKNOWN |

Verification of a solver vector, before any `FEASIBLE` label:

1. Every variable must be within 1e-6 (the HiGHS `mip_feasibility_tolerance`) of an integer.
   The vector is then rounded.
2. Every model row and bound must hold exactly in integer arithmetic.
3. The roster built from the chosen patterns goes through 5B-1 `evaluate_roster` with the
   required staffing. It must have no violation, zero shortfall, and no register excess.
4. For every employee with R_e and O_e variables (k > 1), they must equal the 5B-1 regular and
   overtime minutes.
5. The labor cost recomputed from the 5B-1 minutes and the rates must equal the model's
   objective at the rounded vector, within a relative 1e-9 (floating-point summation only).

Reported:

- solver status, message, objective, dual bound, `mip_gap`, node count, and wall time;
- the options passed, the unchanged defaults, and the scipy and HiGHS versions;
- the verified objective, and its absolute and relative distance to the dual bound.

`OPTIMAL` means optimal for this model, the break grid, and the reported tolerances. It does not
mean optimal for the real queue. Other rosters can have the same objective, so the result states
`uniqueness: NOT_ESTABLISHED` and never presents the roster as the unique optimum.

### Output

- The roster (`ScheduledShift`s) and the full 5B-1 evaluation.
- Labor cost per employee: regular and overtime minutes and cost.
- Surplus server-minutes inside the horizon, and active minutes outside it.
- The model size and the certificates.
- The scope, definitions, and provenance, including the coverage-target source.

These are scheduled quantities. The roster has not been simulated. Phase 5A says any roster must
still be validated by the DES, which is a later phase.

## Verification

- An independent brute force enumerates every single-shift plan by nested minute loops,
  validated with 5B-1 `evaluate_roster`. It checks:
  - equality with the generated pattern set;
  - optimal objectives, and membership of the solver's roster in the optimal set, on
    hand-computed and seeded random tiny instances. These include split shifts, overtime, an
    overtime rate below the regular rate, and register limits.
- Tests for the 12 required areas:
  - exact optimum;
  - availability edges;
  - shift lengths;
  - breaks;
  - paid and unpaid time;
  - regular and overtime cost;
  - surplus;
  - insufficient workforce;
  - registers;
  - multiple optima;
  - missing inputs;
  - solver infeasibility, and non-optimal terminations simulated by wrapping the solver.
- A Phase 2 capacity plan as the coverage target.
- The isolation test, the shared and separate suites, the full backend suite, ruff, and mypy.

### Results (2026-09-26)

- `tests/test_shared_rostering.py`: 88 tests.
  - The 40 seeded random instances cover proven optima, infeasibility (certificate and HiGHS),
    overtime (also at a rate below the regular rate), binding registers, and split-shift rules.
    A guard test fails if the generator stops covering any of these.
- Fault injection, source mutation with the original restored byte for byte:
  - The first pass caught 16 of 18 faults. The misses were a break-gap boundary and a break
    running past the shift end; the test rules had only one break and never reached the shift
    end.
  - A second pass caught 21 of 22. It missed requiring cover after closing: no test let shifts
    run past closing while the last segment required servers.
  - After adding those tests, 22 of 22 were caught. That includes each verification safety
    net: integrality, model rows, 5B-1 violations, 5B-1 shortfall, and cost consistency.
- Full backend suite, `python -m pytest tests/ -x`: 1448 passed, 3 skipped, 1 xfailed. That
  run includes every Separate Queue test file.
- Scale observations: synthetic workforce, not tests, on this machine.
  - The 5B-1 fixture day: 4 employees, 12 h, a 60-minute break grid, 6,021 patterns. The big-M
    form for one shift a day was not proven optimal in 30 s (gap 0.85%). With exact pattern
    costs, it was proven optimal in about 15 s.
  - The NovaMart 14-day-average Phase 2 plan as the target, with 8 synthetic employees:
    - a 60-minute break grid: 5,424 patterns, proven optimal in 1.9 s;
    - a 30-minute break grid: 19,528 patterns, proven optimal in 19.7 s;
    - a 15-minute break grid: 62,568 patterns and 1.68 million nonzeros. There was no solution
      within the 180 s limit, reported as `NO_SOLUTION_FOUND` with feasibility UNKNOWN.
  - Solve time on real inputs remains UNKNOWN.
