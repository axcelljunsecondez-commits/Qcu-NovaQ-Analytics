# OD-UX-13: a Decision from the full-day shared run

Status: APPROVED 2026-10-13 (owner "go 13", then in chat: rule "Day run + Monte Carlo", basis "Full-day run first"). IMPLEMENTED and committed on `feat/ux-u1-shell` after `de733c5c` (local, not pushed).

## 1. Before (VERIFIED)

- The full-day shared run (B4a estimated service, B4b recorded service) returns no verdict (`shared_replications.py:341`, `NO_VERDICT_REASON`); the Checks page says no Decision is made from it (`ContinuousRun.tsx:456`).
- A replication that loses a customer is rejected (`shared_replications.py:256-257`), so "every customer accounted for" can never fail a plan by itself.
- Stored runs keep one day-level row per repeat; per-period figures are computed and dropped (`shared_continuous_des.py:665-688`, `replication_row`).

## 2. Basis

- Green, Kolesar and Whitt 2007 (POM 16(1); author preprint pp. 9-11, read): staffing must meet the target in each staffing interval, and should be checked by simulating the system after an analytical method, with the empirical service-time distribution where service is not exponential; their §4.4 uses independent replications of the full day.
- NovaQ rules reused, no new threshold: the separate-lanes optimizer's aggregate rule (FEASIBLE iff the mean simulated utilization over the replications is at or below the target, `apply_des_aggregate_feasibility`); the separate-lanes Monte Carlo verdict (failure rate at most the cap with an adequate Wilson interval; FAIL > insufficient > PASS, `workflow.py:1220-1253`); the shared Decision's cost rule including the today-overloaded rule (spec 2026-10-13-u10-today-overloaded-decision.md).

## 3. Rule (approved)

Which evidence (basis "Full-day run first"): when the selected plan has an eligible full-day run, the shared Decision uses the full-day chain; otherwise the period-by-period chain, unchanged. The two are never mixed. Eligible run: the latest completed full-day run of the suggested plan whose recorded scenario id and generation, dataset id and generation, and Setup hash equal the selected plan's, its dataset's and the current Setup's. Its service model then follows the plan's own data (`shared_continuous.py:284-287`).

Per plan period (rule "Day run + Monte Carlo"):
- Day run: u = mean over the repeats of busy server-hours / present server-hours in that period. FAIL when u > the plan's target utilization (the row's recorded `effective_constraints.target_utilization`) + THRESHOLD_TOLERANCE; insufficient when the run has no figure for the period or the plan row has no recorded target.
- Many variations (the plan's Monte Carlo job): insufficient when missing, unsupported or not adequate; FAIL when the failure rate exceeds the job's recorded cap; PASS otherwise.
- The period FAILS if either part fails; otherwise it is insufficient if either part is; otherwise it passes.

Overall: any failed period gives `revise`; else any insufficient period gives `insufficient_evidence` naming the periods; else the shared cost rule (adopt when the saving is 0 or more, conditional when it is negative or cannot be calculated because today's staffing cannot keep up).

## 4. Changes

1. `run_shared_replications` adds `period_utilization` (new top-level key): per staffing segment, each repeat's busy and present server-hours and utilization. Replication rows are unchanged, so stored runs still regenerate. Runs saved before this have no `period_utilization`: the Decision says to run the full day again.
2. The full-day run endpoint records `period_labels` (staffing segment id to plan period label) in the job params.
3. `create_decision` (shared): full-day chain when an eligible run exists. Stored Decision: `basis` = `full_day_run` or `period_by_period`; evidence ids add `continuous` (the run). Facts add per-period results.
4. Currentness: a full-day Decision is current while its selection, Monte Carlo job and run are still the current ones and the run is no newer than the Decision. A period-by-period Decision is stale when an eligible full-day run exists (a new Decision would use it). The run id is not added to the protected G-A reference list (`evidence_status.job_references`); currentness follows from the comparison above.
5. GET workflow adds `decision_basis` and `full_day_run_id` so the page knows which checks to run. "Check the plan" runs Many variations then the Decision for the full-day basis, or the Results check then the Decision as before.

Not changed: formulas, simulations, Monte Carlo, thresholds, caps, the period-by-period Decision, separate lanes.
