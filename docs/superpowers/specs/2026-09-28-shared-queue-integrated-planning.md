# Shared Queue Enhancement: Phase 5B-3, Integrated Planning MILP

Date: 2026-09-28. Status: approved for Phase 5B-3 only by the product owner.

Scope: one pure module and its tests. It adds no named-employee DES, no break-delay simulation,
no workforce cost in the DES, and no API, schema, migration, scenario, frontend, Decision, or
Report change. The 5B-2 sequential optimizer stays unchanged and remains available.

## Starting point (verified)

- HEAD is `99d94b4d` (5B-2). The Phase 1, Phase 2, 5B-1, and 5B-2 modules exist and their tests
  pass; the full backend suite gave 1448 passed, 3 skipped, 1 xfailed at `99d94b4d`.
- The solver is `scipy.optimize.milp` with HiGHS 1.12.0 (scipy 1.17.1, numpy 2.4.6 locally). No
  new dependency is added.
- Reused, unchanged:
  - 5B-2 (`shared_rostering.py`): `enumerate_patterns`, `max_paid_minutes`, `_labor_case`,
    `_build_model`, `_interval_cover`, `_labor_rows`, `_highs_details`, the status and
    feasibility labels, the tolerances, and `optimize_roster_for_capacity_plan`;
  - 5B-1 (`shared_workforce.py`): `validate_workforce_inputs`, `evaluate_roster`, `_count_at`;
  - Phase 2 (`shared_capacity.py`): `evaluate_candidate` (the admissibility rule and the
    expected waiting customer-hours) and `optimize_shared_capacity`;
  - Phase 1 (`shared_segments.py`): `validate_timeline` and the M/M/c evaluation behind
    `evaluate_candidate`.

## Decisions

- Capacity semantics, "every interval" (product owner, 2026-09-28):
  - The analytical server count is the number of employees on duty on every elementary interval
    between shift, break, demand-period, and staffing-segment boundaries.
  - Each interval is evaluated with Phase 1/2's stationary M/M/c formula, with its demand
    period's λ and μ and its own length.
  - Waiting cost is the sum over intervals of waiting rate × λ × Wq(c) × length (hours).
  - Stability, the utilization target, and the maximum wait are checked on every interval.
  - Staffing segments only group the report, and their server counts are not used.
  - Short intervals, such as a break, are a stronger steady-state approximation, and this is
    disclosed in the output. Backlog carried between intervals is not represented.
- Labor is wages only: the 5B-1 regular and overtime minutes at the employee's rates. Phase 2's
  server cost per server-hour is never charged. `CapacityConfig` is used only for Phase 2's
  rule, with placeholder rates whose cost fields are never read.
- Surplus employees are never hidden: every employee on duty is paid and staffs the queue, so a
  surplus employee lowers the priced waiting and raises wages.
- The objective is analytical planning cost. It is not the continuous-DES operating cost.
- Settings come from the caller, with no defaults (`PlanningConfig`):
  - waiting cost per customer-hour (None means not supplied, never 0);
  - target utilization;
  - maximum wait in minutes (None means no limit, as in Phase 2);
  - minimum and maximum servers on duty inside the horizon.
  The run settings are 5B-2's `RosterOptimizationConfig`.

## Module `services/shared_integrated.py`

### Entry points

- `optimize_integrated_plan(horizon, demand_periods, staffing_segments, employees, rules, *,
  planning, config)` solves the integrated MILP.
- `evaluate_planning_cost(..., roster, *, planning, break_start_granularity_minutes)` prices any
  roster exactly, without the MILP, and states whether it is in the integrated feasible set.
- `compare_with_sequential(..., *, capacity_config, planning, config, integrated=None)` runs Phase
  2 and then 5B-2, and prices both rosters with `evaluate_planning_cost`.

### Formulation

- Refinement: the pieces between consecutive horizon, demand-period, and staffing-segment
  boundaries.
- 5B-2's model is built with one zero-requirement segment per piece. That gives:
  - the pattern columns `x_q`;
  - the register rows on every elementary interval of the day;
  - the max-shift and split-shift rows;
  - the exact per-pattern regular and overtime cost, and the R/O/w split for split shifts.
  Its breakpoints include every pattern's active ends and every piece boundary.
- For every elementary interval i inside the horizon, and every admissible count c:
  - a binary `z[i,c]` is added;
  - the objective coefficient is the waiting rate × λ × Wq(c) × length_i / 60;
  - a link row `sum_q a[q,i] x_q - sum_c c z[i,c] = 0` is added;
  - a choose-one row `sum_c z[i,c] = 1` is added.
- Admissible means c is in [min_servers, min(max_servers, registers)] and passes Phase 2's rule
  on the interval. Phase 2's rule is:
  - STABLE or ZERO_DEMAND, with ρ ≤ target + 1e-9, and Wq × 60 ≤ maximum wait + 1e-9 when a
    maximum is set; or
  - CLOSED, meaning c = 0 with λ = 0.
  NO_CAPACITY, UNSTABLE, and CALCULATION_FAILED are never admissible.
- An interval with no expected waiting costs 0 whatever the rate.
- The model is exact in time: the on-duty count is constant on every elementary interval, and
  Wq depends only on c and the period.

### Statuses and certificates

- Status order, as in 5B-2:
  1. exact certificates;
  2. PATTERN_LIMIT_EXCEEDED;
  3. INCOMPLETE (a missing break rule, missing pay, or a missing waiting rate when some
     in-horizon λ > 0);
  4. solve.
- `NO_ADMISSIBLE_CAPACITY`: a piece where no count within the bounds and registers is
  admissible. It needs no patterns.
- `INSUFFICIENT_WORKFORCE`: an interval where the smallest admissible count exceeds the number
  of employees with any pattern active there. It is checked only with a complete pattern set.
- Solver mapping:

  | HiGHS status | Solution | Result |
  |---|---|---|
  | 2 | — | INFEASIBLE, certificate SOLVER_PROVED_INFEASIBLE |
  | 3 or 4 | — | SOLVER_ERROR |
  | 1 | none | NO_SOLUTION_FOUND, feasibility UNKNOWN, never INFEASIBLE |
  | 1 | vector | FEASIBLE_NOT_PROVEN_OPTIMAL, after verification |
  | 0 | vector | OPTIMAL, after verification |

  Optimal means within `mip_rel_gap` and the unchanged HiGHS `mip_abs_gap` (1e-6), for this
  model and break grid.
- Verification. FEASIBLE is given only when every check passes; otherwise the status is
  VERIFICATION_FAILED. The checks are:
  - integrality within 1e-6;
  - every row and bound in integer arithmetic;
  - no 5B-1 violation and no register excess;
  - the z-selected count equals the 5B-1 on-duty count on every interval;
  - the independent evaluation places the roster in the feasible set;
  - the model's R/O minutes equal the 5B-1 minutes;
  - wages and waiting cost from the independent evaluation equal the model's labor and capacity
    terms, within a relative 1e-9.

### Output

The output has these fields:
- the status, feasibility, and status reason;
- the roster and its 5B-1 evaluation;
- `planning_cost`: total, labor, waiting, and the explicit exclusion of the server charge;
- labor rows per employee;
- waiting totals, including the expected waiting customer-hours;
- capacity rows per stretch of constant count, with:
  - λ, μ, the status, the model, ρ, Wq, the waiting cost, and admissibility;
  - the smallest admissible count;
- per-segment summaries;
- active minutes outside the horizon;
- server-minutes above the smallest admissible count;
- optimality, with the dual bound and gap;
- uniqueness (NOT_ESTABLISHED);
- missing inputs and certificates;
- the verification checks;
- the solver fields: status, message, objective, bound, gap, nodes, and wall seconds;
- the model size and timings, including the pattern count and limit;
- the formulation;
- provenance.

### Integrated versus sequential

- Phase 2 and 5B-3 must share the waiting rate, target, maximum wait, and server bounds, or
  nothing is compared. Phase 2's own objective (server charge plus waiting) is reported and not
  compared.
- "Integrated no worse" is claimed only when all of these hold:
  - the sequential roster is verified by 5B-2;
  - the roster is in the integrated feasible set;
  - both costs are defined;
  - the integrated plan is verified;
  - the integrated cost ≤ the sequential cost + 1e-9 relative.
- Otherwise the numbers and the reason are reported. A cheaper sequential roster against an
  OPTIMAL integrated plan, beyond the solver tolerance, is labeled CONFLICTING.

## Verification

- `tests/test_shared_integrated.py`, synthetic data only. It has an independent brute force:
  - rosters from the 5B-2 test enumeration, filtered by `evaluate_roster`;
  - the on-duty count per minute;
  - waiting from the Phase 1 tests' independent Erlang-B recursion;
  - wages from its own paid minutes.
- The 10 required points:
  1. 5B-1 validity;
  2. staffing equals capacity, minute by minute;
  3. hard constraints: max wait, target, min servers, registers, availability, break dips;
  4. wages charged once, with no server charge and surplus paid;
  5. waiting at the on-duty count over each interval's length, with hand-computed break-dip and
     surplus cases;
  6. objective equals the independent recomputation;
  7. missing money stays undefined: waiting rate, pay, and break rule;
  8. infeasible (both certificates, solver-proved) versus incomplete and the pattern limit;
  9. multiple optima (a hand-computed pair);
  10. truthful solver statuses: simulated limit with and without an incumbent, errors, and
      corrupted vectors.
- Also covered:
  - the comparison logic: strictly better, equal, mismatched settings, outside the set, and
    CONFLICTING;
  - 40 seeded random instances against the brute force, with a generator coverage guard.
- `tests/test_shared_segments.py`: the module joins the isolation list.

### Results (2026-09-28)

From executed runs only. The details are in the 5B-3 section of `handoff.md`.

- `tests/test_shared_integrated.py`: 93 passed.
- Fault injection (28 mutants; scratch script, not committed): 28 caught, after 4 tests and 1
  assertion were added.
- Ruff and mypy are clean. The full backend suite gave 1541 passed, 3 skipped, and 1 xfailed, and it
  includes the Separate Queue tests.
- Benchmark (not a test) on the NovaMart average λ and μ rows, with synthetic employees, pay, and
  rules (the 5B-2 probe set). Settings: waiting 100, target 0.70, servers 1-24, 300 s limit,
  `mip_rel_gap` 0. The sequential roster is priced on the same objective.

  | Grid | Patterns | Integrated | Sequential (wages / planning cost) | Comparison |
  |---|---|---|---|---|
  | 60 | 5,424 | OPTIMAL 3759.24 (3206 + 553.24), 4.7 s | 3307 / 3828.02 | no worse, by 68.77 |
  | 30 | 19,528 | OPTIMAL 3670.78 (3047 + 623.78), 96.5 s | 3124 / 3684.31 | no worse, by 13.54 |
  | 15 | 62,568 | NO_SOLUTION_FOUND, feasibility UNKNOWN | NO_SOLUTION_FOUND | not compared |

  In both grid-60 and grid-30 runs, the sequential roster is in the integrated feasible set and
  at or above the integrated dual bound. At grid 15, the integrated `milp` call returned after
  342.4 s against the 300 s limit.
- The 15-minute grid, measured on the 5B-2 model:
  - MIP presolve takes about 184 s for reductions the LP presolve makes in 7 s;
  - the root cut loop then runs without an incumbent.
  The responsible presolve rule is UNKNOWN. No constraint was changed. Two exact reformulations
  are PROPOSED only.
