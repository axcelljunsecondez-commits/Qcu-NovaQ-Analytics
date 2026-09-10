# Optimize → Save Scenario → Comparison engineering report

## Root causes

The M/M/c model correctly returned the expected unstable-baseline result from
`queue_models.mmc`: actual utilization, `stable=false`, an explanatory error,
and null steady-state metrics. Candidate search in `optimize_segment` could
continue, but the service replaced null `Wq` with `UNSTABLE_FIXED_COST`, derived
false current total/savings, and frontend financial completeness then acted as
a global gate for staffing and Comparison output. The model exception text was
therefore presented as if the optimization had failed even when a feasible
higher server count existed.

Comparison stored checkbox selections by scenario name and derived `compared`
by filtering selected scenarios through `comparisonComplete`. That predicate
requires stable current baselines and complete costs. Two visible selections
could therefore become zero or one internally, causing the exact minimum-two
message. The same financial predicate also suppressed all Current vs Optimized
charts. Duplicate names were another identity defect.

## Save-scenario findings

The verified save path was complete: Optimize sent dataset ID, name, effective
options (including target), calculation inputs/version/time, and the complete
optimization result rows. The scenario API replayed the calculation, validated
the payload, stored settings/results as JSON, and returned them unchanged with
a numeric ID. No database or backend scenario-schema change was necessary.

## Repair

- Unavailable current `Wq` now propagates to unavailable waiting cost, total
  current cost, cost delta, savings, and ROI. Server and abandonment costs stay
  independently available. The shared costing service uses the same rule.
- Candidate enumeration still uses the selected model and inclusive configured
  bounds. Only stable candidates with valid analytical metrics satisfying the
  configured utilization and optional wait/capacity constraints enter the cost
  objective.
- Operational eligibility is separate from financial completeness. Current vs
  Optimized staffing, utilization, stability, and available wait results render
  even when aggregate finance is unavailable.
- Saved-scenario checkbox state uses normalized string IDs. Selected, valid,
  and incomplete collections remain distinct; the minimum-two message depends
  on selected count, while incomplete selected scenarios receive a named
  warning. The Source scenario selector remains the independent single-snapshot
  Current vs Optimized mode.
- Null wait/utilization values are passed to charts as null, never plotted as
  synthetic zeroes.

## Verification

- Backend: `382 passed` with the full suite.
- Frontend: `121 passed` across 17 test files.
- Focused workflow suite: `70 passed` backend and `29 passed` frontend.
- `ruff check .`: passed.
- `mypy .`: passed (73 source files).
- `npm run typecheck`: passed.
- `npm run lint`: passed.
- `npm run build`: passed; the pre-existing Plotly chunk-size warning remains.

The repaired reproduction (`lambda=20.214`, `mu=10`, current `c=2`, target
`0.7`, max `5`) retains `rho_current=1.0107`, null current wait/queue/total cost,
and returns feasible `c_optimal=3`, `rho_optimal=0.6738`, and valid optimized
waiting/cost metrics. No queueing formula, dispatch rule, Monte Carlo logic, DES
logic, database schema, or existing API response shape changed.

## Remaining limitations

The “Available cashiers today” control remains the existing post-result pool
coverage diagnostic, not an optimizer hard constraint; configured analytical
hard bounds remain minimum/maximum cashiers, model capacity, utilization target,
and optional maximum wait. Legacy scenarios without verified calculation rows
remain explicitly marked unverified and may be reported as incomplete.
