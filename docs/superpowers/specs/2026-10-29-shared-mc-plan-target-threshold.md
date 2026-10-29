# Shared-line Many variations: count failures at the plan's target

Date: 2026-10-29. Status: IMPLEMENTED, uncommitted (owner approved the fix as a separate, tested change on 2026-10-29, REPORTED by the parent session). Base: main `3ee8fe2c`. OD-T1 to OD-T4 DECIDED by the owner on 2026-10-29: all four recommended options (§8).

Protected area (AGENTS.md §5): the Monte Carlo failure criterion as used for a shared plan. The engine (`mc_simulate_segment`, `rho > failure_threshold`) is **not** changed. What changes is which threshold the shared selected-plan run passes to it.

## 1. Defect

For a shared-line plan, Many variations (Monte Carlo) counts a trial as failed when its utilization is above 75 % (NovaQ's default), not above the plan's own target. The full-day Decision table then shows "Plan's target 70 %" next to "Variations that failed" counted at 75 %. Separate-line plans already count at the plan's target.

## 2. Evidence (2026-10-29, this worktree at `3ee8fe2c`)

| # | Finding | Label | Source |
|---|---|---|---|
| E1 | `MC_DEFAULT_FAILURE_THRESHOLD = 0.75`; `DEFAULT_TARGET_UTILIZATION = 0.70`. | VERIFIED | `backend/queueing_engine/config.py:21,35` |
| E2 | Shared selected-plan MC (`POST /workflow/simulation/mc`, `run_mc`) takes `WorkflowMcRequest`, whose `failure_threshold` defaults to 0.75, and passes it straight to `mc_simulate_segments`. It never reads the plan's target and records no threshold source. | VERIFIED | `backend/api/workflow.py:145-151, 1448-1471` |
| E3 | Separate selected-plan MC (`/mc/selected`, `run_selected_mc`) takes `SelectedMcRequest` (threshold optional). Omitted → plan target, source `plan_target`; given → source `user`; no valid target → 0.75, source `default`. Both are recorded in the job params. | VERIFIED | `backend/api/workflow.py:154-157, 3072-3078, 3104-3110`; `tests/test_selected_mc_load.py:194-216` |
| E4 | The shared Checks panel (`LegacyPlanChecks`) builds its settings with `useMcSettings(null, '')`, so the threshold box starts at 0.75 and is always sent. It also passes the same value as `mc_failure_threshold` to the Results check (`/workflow/simulation/validation`). The separate panel starts at the plan target and omits the field when it equals the target. | VERIFIED | `frontend/src/components/queueSimulation/ChecksView.tsx:70-75, 118-133, 279-298, 395` |
| E5 | The frontend already knows the shared plan's target: `buildContext` sets `planTarget` from `scenario.settings.calculation.options.target_utilization` for shared and separate alike. | VERIFIED | `frontend/src/components/queueSimulation/simulationContext.ts:32-34` |
| E6 | The full-day shared Decision prints, per period, `target_utilization` = the plan row's `effective_constraints.target_utilization` and `variations_failure_rate` = the stored MC row's `failure_rate`. It never compares the MC run's threshold with that target. | VERIFIED | `backend/api/workflow.py:1687-1728`; table `ChecksView.tsx:403-424` |
| E7 | The shared optimizer uses one `target_utilization` per batch (default 0.70) and records it on every row as `effective_constraints.target_utilization`. A saved calculation's `options` may omit it (then the default 0.70 applied). | VERIFIED | `backend/api/optimization.py:80-88`; `backend/queueing_engine/services/optimization.py:366`; `frontend/src/pages/OptimizePage.tsx:266-268` |
| E8 | `tests/test_selected_mc_load.py::test_current_and_shared_mc_defaults_stay_075` pins `WorkflowMcRequest().failure_threshold == 0.75`. It was added with the separate fix (`bae8d30a`, 2026-09-19) as a scope guard. No spec or memory record found that makes 0.75 a deliberate shared-plan rule. | VERIFIED (test); INFERRED (purpose) | `git log -S` |
| E9 | Owner's NovaMart run: plan "Shared 70% default", 2,000 trials, threshold 0.75, cap 5 %, Decision shows "Plan's target 70 %". | REPORTED (parent session); not reproduced here | — |

## 3. Effect on real data (VERIFIED, scratch run, not stored evidence)

Dataset: `Daily data mmc/Avg_total_data_of_14_days.csv` (owner file, 13 hourly rows `time, lambda, mu, c`, 05:00-18:00, averages over 14 days; per-hour rates, unchanged). Transformation: `optimize_batch` with all defaults (target 0.70 recorded on every row), then `mc_simulate_segments` on the plan's `c_optimal`, 2,000 trials, seed 42, cap 0.05.

| Counted at | Periods failing (of 13) |
|---|---|
| 0.75 (today's behaviour) | 4: 05:00, 10:00, 11:00, 16:00 |
| 0.70 (the plan's target) | 8: also 09:00, 13:00, 14:00, 17:00 |

So the fix makes shared plans fail Many variations more often. This is the intended consequence of judging a plan by its own target, not a defect. Script: scratchpad `real_csv_probe.py` (outside the repo).

## 4. Rule

For a **shared-line selected plan**, the Many variations threshold is resolved exactly as for separate lines:

1. A `failure_threshold` sent in the request → that value, source `user`.
2. Otherwise the plan's target, source `plan_target`. The shared plan's target is:
   - the `effective_constraints.target_utilization` recorded on every plan row, when every row has one, all are equal, and the value is in (0, 1] (this is the number the Decision table prints); otherwise
   - `settings.calculation.options.target_utilization`, when it is a number in (0, 1].
3. Otherwise `MC_DEFAULT_FAILURE_THRESHOLD` (0.75), source `default`.

Steps 1 and 3 and the order are one shared helper used by both the separate and the shared endpoint, so the two cannot drift apart.

The resolved threshold is stored in the job params as `failure_threshold` (as today) plus the additive `failure_threshold_source`.

Unchanged: the MC engine, noise, trials, Wilson interval, cap, the Decision verdict rules, `/workflow/simulation/mc/current` (today's staffing has no plan; stays 0.75), the separate path's behaviour, the API request and response shapes (`failure_threshold` stays a number field that may be omitted; one new key in stored params).

## 5. Checks screen (frontend)

The shared panel (`LegacyPlanChecks`) uses the plan target exactly like the separate panel:

- The threshold box starts at the plan target and is labelled with the existing key `simulation.sep_mc_threshold_plan` ("Failure threshold (plan target: {{target}})" / tl "Failure threshold (target ng plan: {{target}})"). No new wording.
- Left at the plan target, the request omits `failure_threshold`, so the server applies and records `plan_target`. Changed by the user, the value is sent and recorded as `user`.
- No plan target known (`planTarget === null`): unchanged, starts at 0.75 and sends it.
- The Results check (period-by-period basis) reads the same box, so its `mc_failure_threshold` becomes the plan target too. See OD-T2.

## 6. Decision table

With this change, a run left at its default counts failures at the same target the table prints, so "Plan's target 70 %" and "Variations that failed" agree. No Decision code or wording changes in this step.

A user who types a different threshold still gets a table whose target column differs from the counting threshold. Showing the counting threshold, or refusing such runs, needs owner wording or a rule: OD-T3.

## 7. Stored evidence and version

The MC engine and the optimizer are unchanged, so no engine version moves. Shared MC jobs saved before this change have `failure_threshold` 0.75 (sent by the old screen) and no `failure_threshold_source`. They are still read and still count at 0.75. Options in OD-T1.

## 8. Owner decisions

Decided 2026-10-29 (owner, in chat: "go with your recommendations for OD-T1 to OD-T4"):

| OD | Decision | Code effect |
|---|---|---|
| OD-T1 | A: no version bump; old shared MC runs stay usable until rerun; the release note (§10) says to rerun shared plans. | None beyond §4-5. |
| OD-T2 | A: keep; the shared Results check counts at the plan target too. | Already in §5. |
| OD-T3 | A: no change for user-typed thresholds; the run records source `user`. | None. |
| OD-T4 | Confirmed: more failing periods (4 → 8 of 13 on the 14-day data) is the intended effect. | None. |

Options as proposed:

- **OD-T1 old shared MC evidence.** (A, recommended) No version bump; old runs stay usable until the owner reruns Many variations; the release note says to rerun shared plans. (B) Treat a shared MC job with no `failure_threshold_source` as stale for the full-day Decision (Decision says Many variations must be run again). (C) Bump a version so old shared MC runs are historical.
- **OD-T2 Results check.** The shared Results check shares the threshold box, so it now counts MC failures at the plan target too. (A, recommended) Keep: one plan, one threshold. (B) Keep the Results check at 0.75 (needs its own hidden setting; reintroduces the mismatch for the period-by-period Decision).
- **OD-T3 overridden thresholds.** (A, recommended for now) No change; the run records `user`. (B) The Decision table states the counting threshold (owner writes the en + tl wording). (C) The full-day Decision treats a run whose threshold differs from the plan target as insufficient.
- **OD-T4 more failures.** On the 14-day data, failing periods go from 4 to 8 of 13 (§3). Owner to confirm this is the intended effect before release.

## 9. Tests (reference cases and regression)

- R1 independent reference: for one period (λ = 4, μ = 6, c = 1, nominal ρ = 2/3) the failure probability P(ρ(1+a)/(1+b) > T), with a ~ U(−0.2, 0.2) and b ~ U(−0.1, 0.1), is integrated numerically (no MC code). The stored failure rate must lie in its 99.9 % Wilson band, at T = 0.70 when the threshold is omitted and the plan target is 0.70, and the 0.70 and 0.75 probabilities must differ (so the test can tell them apart).
- R2 shared omitted → `plan_target`, threshold 0.70 on the job params and every row, counts identical to `mc_simulate_segments(..., failure_threshold=0.70, seed)` called directly.
- R3 shared explicit 0.75 → `user`.
- R4 target from `calculation.options` when rows have none; R5 rows disagree or no target → 0.75 `default`.
- R6 parity: for the same targets and requests, the shared and separate endpoints record the same (threshold, source) pairs, and both call one helper.
- R7 full-day Decision: after a default shared run, each period's `target_utilization` equals the run's `failure_threshold`.
- R8 `/mc/current` still defaults to 0.75.
- Frontend: shared panel starts at the plan target, omits `failure_threshold` when left there, sends it when changed, and keeps 0.75 when no target is known.

## 10. Release note (OD-T1)

For the release that carries this change (record verbatim in the release record; the owner may reword):

- Shared-line plans: Many variations and the Results check now count a variation as failed when it is busier than the plan's own target (for example 70 %), not NovaQ's 75 % default. Separate lines already worked this way.
- Many variations runs saved for a shared plan before this release were counted at 75 %. They still open, but run Many variations again (and Check the plan) for any shared plan you rely on.
- Expect more periods to fail than before: on the 14-day sample data, 8 of 13 periods instead of 4.
