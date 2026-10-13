# U10: the shared Decision when today's staffing cannot keep up

Status: IMPLEMENTED and committed 2026-10-13 (owner "go 2 1st": decide what the Decision says when today's staffing cannot keep up in a period). Branch `feat/ux-u1-shell`.

## 1. Finding (VERIFIED)

On analysis 10 (scratch copy, plan 8), after U10 F1/F2 the DES and validation are supported for every period, but the Decision stays `insufficient_evidence`: "a complete modeled cost comparison". Period segment_3 has `current_stable` false (today 3 counters, rho 1.0008) and `cost_current` None. The Decision requires a finite current and plan cost in every period (`backend/api/workflow.py:1585-1593`, `:1613-1616`), so a plan that passes every check can never be decided when it fixes an overloaded period.

## 2. Mathematics

With rho >= 1 the queue has no steady state: the analytical waiting time, and with it today's waiting cost, has no finite value (the optimizer sets `current_stable` false and `cost_current` None, `backend/queueing_engine/services/optimization.py:298-305`, `:395`). The saving "today cost - plan cost" is therefore undefined, not large and not zero. "Adopt" requires a saving of 0 or more (`workflow.py:1702`), which cannot be established, so it cannot be given.

## 3. Rule

When every period's plan cost is finite and every missing today cost belongs to a period where today's staffing cannot keep up (`current_stable` false), the cost comparison no longer counts as missing evidence. Then:

- any validation period fails: `revise` (unchanged rule);
- every period passes: `conditional`, saying the cost change cannot be calculated and naming the periods where today's staffing cannot keep up. Facts: `current_modeled_cost` and `modeled_savings` null, `selected_modeled_cost` the plan total, `today_overloaded_periods` the labels.

A today cost missing for any other reason, or any plan cost missing, stays "a complete modeled cost comparison" (insufficient).

Precedent (consistent wording and outcome):
- the optimizer already withholds savings for the same reason: "customers arrive faster than the current staff can serve them (rho >= 1), so today's waiting cost has no finite value" (`optimization.py:497-504`);
- the separate-lanes Decision gives `conditional`, never `adopt`, when a plan passes but its saving cannot be calculated (spec 2026-10-09 G13).

No threshold, formula, simulation or validation rule changes.
