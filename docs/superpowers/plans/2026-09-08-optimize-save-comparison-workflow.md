# Optimize → Save Scenario → Comparison implementation plan

1. Add optimizer regressions for stable baseline, unstable feasible baseline,
   unstable infeasible bounds, configurable utilization target, and null current
   steady-state/financial metrics.
2. Update optimization cost composition so a missing analytical waiting metric
   propagates as unavailable for current total and deltas while candidate costs
   remain evaluated only after model stability/constraint checks.
3. Add frontend comparison helpers for normalized scenario IDs and operational
   eligibility without weakening aggregate financial completeness.
4. Refactor Comparison state and derivations to use normalized IDs, distinguish
   selected/incomplete/valid scenarios, keep Current vs Optimized independent,
   and render operational charts with null wait values preserved.
5. Add symmetric English/Tagalog messages and frontend regressions for zero/one/
   two selections, numeric and string IDs, unchecking, incomplete scenarios,
   unstable-current comparisons, and unavailable finance.
6. Add scenario API coverage proving verified unstable-baseline results survive
   create/list retrieval with target, model, staffing, utilization, null waits,
   and optimized metrics intact.
7. Run focused tests, the complete backend/frontend suites, ruff, mypy,
   TypeScript, lint, and production frontend build. Record any environment-only
   limitations rather than masking them.
