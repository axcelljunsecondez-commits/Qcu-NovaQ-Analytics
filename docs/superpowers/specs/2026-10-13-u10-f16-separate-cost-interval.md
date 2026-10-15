# U10 F16: the separate-lanes cost estimate counts every replication

Status: IMPLEMENTED and committed 2026-10-13 (owner "go" after the F16 explanation). Branch `feat/ux-u1-shell`. Changes the separate-lanes optimizer objective (protected): owner authorized.

## 1. Finding (VERIFIED)

- A replication whose own active-lane utilization exceeds the target returns `total_cost` None, in both DES evaluators (`backend/queueing_engine/services/separate_optimization.py:608-613`, 24 h per period; `:1840-1843`, continuous day), since 2026-09-18.
- The candidate's cost summary averages only the replications that have a cost (`:1444-1449`, `_summarize_metric` `:1277`), while the candidate's feasibility uses the mean utilization over all replications (`apply_des_aggregate_feasibility`).
- So a FEASIBLE candidate's mean cost is the mean over its low-utilization replications only, with a varying n. On analysis 11 (scratch), 09:00-10:00 was FEASIBLE at 87.79% with n = 1 of 5.
- The interval is mean ± t(0.975, n-1) · SD / sqrt(n). With n = 2, t = 12.71: the walkthrough's -252.20 to 1242.94 around 495.37 needs a replication SD of only 83.21.

## 2. Mathematics

- The candidate's objective is its expected cost per period. Its unbiased estimator over independent replications is the mean over all of them. Leaving out the replications above the target conditions on low utilization, which correlates with low waiting cost, so the estimate is biased low and the candidate is favoured in the ranking.
- A replication's cost (server cost + served / horizon x Wq x waiting rate) is defined whether or not its utilization is above the target; the target is a feasibility rule, decided on the aggregate.
- Cost is never negative, so its true mean is at least 0. Replacing the lower bound L by max(0, L) keeps the coverage exactly: P(mu in [max(0, L), U]) = P(mu in [L, U]) when mu >= 0.

## 3. Change

1. Both DES evaluators return the replication's cost also when that replication is over the target. Its status stays INFEASIBLE with the same reason; feasibility stays the aggregate rule. Mean cost and its interval use every replication (n = replications).
2. The cost intervals (staffing, waiting, total) report a lower bound of max(0, mean - t x SE). Other metrics are unchanged.
3. Engine versions: representative-day `novaq-2026-10-separate-des-v4` (was v2), per-date day `novaq-2026-10-separate-des-v5` (was v3). Plans saved with v2 or v3 become historical: "run Suggested plans again" (the B13 per-date message stays for v2 plans on a per-date day setup).

Unchanged: the per-replication waiting cost formula (customers still waiting at the end are not costed, as before), the feasibility rule, the target, the seeds, the replication count, the analytical evaluator.

## 4. Verification

- Unit: an over-target replication carries its cost; the mean uses all replications; the lower bound is never below 0; candidates with no over-target replication are unchanged.
- Rerun of analysis 11 (scratch): 09:00-10:00 cost now uses n = 5.
- Old v2/v3 plans are reported as historical, not current.
