# Optimize → Save Scenario → Comparison repair

## Observed failures

An infinite-capacity current baseline can legitimately be unstable. The model
layer already returns that condition as data (`stable=false`, actual `rho`, and
null steady-state queue metrics), and candidate evaluation can still find a
feasible larger server count. The optimization service nevertheless converts a
missing current `Wq` into a fixed waiting-cost penalty and derives aggregate
cost/savings from it. Frontend completeness predicates then use financial
comparability as a global rendering gate, hiding valid operational results.

The saved-scenario selector stores scenario names, while the source selector
uses normalized IDs. Selected scenarios are also filtered through the full
financial-completeness predicate before the minimum-two check. Consequently,
two checked scenarios can become fewer than two derived scenarios whenever a
current baseline is unstable or financial fields are incomplete, and duplicate
scenario names are not independently selectable.

## Design

1. Preserve the model-selection and formula layers. Treat model `stable` and
   returned metrics as authoritative for both the actual current server count
   and every bounded candidate.
2. Keep current staffing, utilization, stability, and the model error. When the
   current model supplies no valid `Wq`, keep waiting cost, total current cost,
   cost delta, savings, and ROI unavailable instead of applying a fixed penalty.
3. Continue candidate search across the configured inclusive min/max bounds.
   A candidate must be model-valid, stable according to its selected model,
   within the configured utilization target, and within the optional wait and
   capacity constraints.
4. Split operational eligibility from financial completeness. A feasible
   optimized row with real current/optimized staffing and utilization is enough
   to render Current vs Optimized operational charts, even if current steady-
   state wait or aggregate costs are unavailable. Financial charts and ROI
   remain gated by complete costs.
5. Store saved-scenario selections as normalized string IDs, derive selected
   scenarios from those IDs, and only then classify selected scenarios as valid
   or incomplete. The minimum-two message depends on selected count, not valid
   count. Incomplete selected scenarios receive a specific warning; any two
   valid selected scenarios still render the existing multi-scenario chart.
6. Preserve the Source scenario selector as the independent Current vs
   Optimized mode. It selects one saved optimization snapshot whose paired
   baseline/recommendation rows are rendered side by side.
7. Preserve the existing verified snapshot payload and JSON persistence. No
   schema migration or API contract change is required; widen only the frontend
   ID type to acknowledge number/string boundary inputs and normalize locally.

## Non-goals

No queueing formula, model dispatch, simulation logic, database schema, API
shape, utilization target, or staffing input is changed. No unavailable metric
is replaced with zero or another synthetic finite value.
