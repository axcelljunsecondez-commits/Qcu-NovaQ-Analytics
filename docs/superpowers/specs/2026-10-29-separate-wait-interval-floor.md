# Separate lines: the simulated wait interval stops at 0 (Part B)

Status: IMPLEMENTED and committed 2026-10-29 on branch `claude/friendly-bell-4801f0` (owner asked for both changes to be committed separately), NOT pushed. Changes a statistics output of the separate-lanes optimizer, so it is a protected change under AGENTS.md §5. Owner approved the two-part fix on 2026-10-29 (REPORTED by the session that started this one). OD-W1 below (engine version) DECIDED 2026-10-29: no version change (REPORTED via the parent session, owner's words: "Option 1, leave them as they are").

Plan: `docs/superpowers/plans/2026-10-29-separate-wait-interval-floor.md`.

## 1. Finding

- VERIFIED. `_summarize_metric(values, floor=None)` (`backend/queueing_engine/services/separate_optimization.py:1276-1302`) returns mean ± t(0.975, n−1) · SD / √n. With `floor` given, the lower bound is `max(floor, mean − half width)`.
- VERIFIED. The cost intervals pass `floor=0.0` (`:1456-1459`, U10 F16, `docs/superpowers/specs/2026-10-13-u10-f16-separate-cost-interval.md` §2-§3, commit `de733c5c`).
- VERIFIED. The wait intervals do not: plan wait `waiting_time` (`:1453`), each lane's `Wq` (`:1409`) and each lane's `waiting_end` (`:1408`).
- REPORTED (parent session; not rerun here). NovaMart, `NOVAMART_DATA_UPLOAD.xlsx`, plan "Schedule at 85%", 5 replications, seed 42: at 10:00-11:00 the plan wait interval is [−0.02395 h, 0.05091 h] = −1.44 to 3.05 min around a mean of 0.81 min. 12 of 13 hours have a negative lower bound.

A wait below 0 minutes is impossible, so a negative lower bound only reflects the symmetric t interval with n = 5. The new wait-by-hour chart shows it as a dip below 0.

## 2. Mathematics

- Each quantity below is non-negative in every replication, so its true mean μ is ≥ 0:
  - `Wq` of a lane in one replication = `wait_sum / served`, where every term of `wait_sum` is `service_start − arrival` (`:949-950` per-period run, `:1134-1135` continuous day). SimPy time never goes backwards, so every term is ≥ 0 and `served > 0`. VERIFIED from code.
  - `waiting_time` of one replication = Σ served·Wq / Σ served over active lanes with served > 0 (`:1414-1421`): a weighted mean of non-negative values with positive weights, so ≥ 0. VERIFIED from code.
  - `waiting_end` of a lane = customers still waiting at the end of the run: `len(waiting_customer_ids)` (`:559`, per-period run) or `max(0, arrivals − served)` (`:1833`, continuous day). Both ≥ 0. VERIFIED from code.
- For L ≤ U and μ ≥ 0: μ ∈ [L, U] ⇔ μ ∈ [max(0, L), U]. So P(μ ∈ [max(0, L), U]) = P(μ ∈ [L, U]): the coverage stays exactly 95 % under the same t assumptions as before (§2 of the F16 spec states the same rule for cost). The floored interval is the old interval cut to the values μ can take.
- The rule only replaces a negative lower bound. A lower bound ≥ 0, the upper bound, the mean, SD, SE and n are unchanged. With n = 1 there is still no interval (both bounds None).

## 3. Change

1. `waiting_time` (plan wait across lanes), per-lane `Wq` and per-lane `waiting_end` call `_summarize_metric(..., floor=0.0)`.
2. Nothing else changes:
   - Per-lane `utilization`, `arrivals`, `served` and plan `arrivals`, `served` keep the plain interval. They are also non-negative, but they are outside this approval (open item OD-W2). The utilization upper bound feeds the near-target note (`apply_des_aggregate_feasibility`, `:1517-1530`); its lower bound is not used.
   - The paired wait change of the break optimizer (`backend/queueing_engine/services/break_optimization.py:403`) is a difference that may be negative and must never be floored. It calls `_summarize_metric` without `floor`, so it is unchanged.
   - Means, costs, cost intervals, ranking (mean total cost), feasibility (mean utilization), seeds, replication count, the per-replication evaluators and the analytical evaluator are unchanged.
   - The shared-line summaries (`backend/queueing_engine/simulation/shared_replications.py:281-297`) have their own interval code and are not part of this task (open item OD-W3).
3. API shape unchanged: the same keys, types and nullability; only a negative `ci_lower` of these three metrics becomes `0.0`.

## 4. Who reads these values (checked 2026-10-29)

| Reader | Reads | Effect |
|---|---|---|
| `GET /analyses/{id}/workflow/comparison/separate` (`backend/api/workflow.py:2429-2442`) | `evidence.waiting_time.ci_lower/ci_upper` as `wait_ci` | New plans: `wait_ci[0]` ≥ 0. VERIFIED by code reading; covered by the API-level test in the plan. |
| Scenario save check (`backend/api/scenarios.py:156-219`) | reruns the optimizer and compares the whole result | Rerun and saved result both use the new code. A plan calculated before a deploy and saved after it fails once with "Results do not match"; recalculating fixes it (INFERRED from the code; NOT TESTED across a deploy). |
| Plan report (`backend/reports/plan_report.py:181-216`) | `waiting_time.mean` only; cost interval via `cost_uncertainty` | No change. |
| Excel/report export (`backend/reports/report_export.py:430-445`) | single-run selected-plan DES lane `Wq` (a number, not this summary) | No change. |
| Frontend | `SeparatePlanPeriod.wait_ci` type only (`frontend/src/api/types.ts:643`); no component renders it today | No frontend change. The wait-by-hour chart (Part A, chart redesign) is the first reader. |

## 5. Stored plans and version (OD-W1, owner decision)

- VERIFIED. Saved separate plans store the full evidence in `results_json.schedule`, stamped `novaq-2026-10-separate-des-v4` (representative day) or `-v5` (per-date day). Stored v4/v5 plans keep their negative wait lower bounds; the database is not changed.
- This implementation does NOT change the engine version. Reasons: the stored interval is not wrong (it contains the new one and has the same coverage, §2), and the chosen plan, its costs, ranking and feasibility are identical. A version change would mark every saved separate plan "run Suggested plans again" for a change to one interval end.
- CONFLICTING with the F16 precedent, which did move v2/v3 → v4/v5. F16 changed the mean cost (the objective), which changes rankings; this change does not. The Erlang numerics decision (spec 2026-10-12, §11) kept the version because no stored result changed; here stored results would differ if recalculated, so that precedent does not settle it either.
- Consequence for Part A: while old v4/v5 plans exist, `wait_ci[0]` can still be negative for them. The chart's cut-at-0 marker can only be removed after one of:
  - (a) no version change (as implemented): keep the display cut for old plans, or recalculate them;
  - (b) new engine versions v6/v7, old v4/v5 plans become historical (same flow as F16);
  - (c) apply `max(0, lower)` when `workflow.py` builds `wait_ci`, so the API is consistent for old and new plans without touching stored data.
- Recommendation: (a) now; choose (b) or (c) only if the owner wants the display marker removed while old plans remain.
- DECISION (2026-10-29, owner, REPORTED via the parent session): (a), "Option 1, leave them as they are". No engine version change; saved v4/v5 plans keep their stored bounds; the chart's cut-at-0 marker stays for those older plans.

## 6. Reference cases (hand-computed; t quantiles from the Student-t table: t(0.975, 2) = 4.302653, t(0.975, 4) = 2.776445)

| Case | Values | Mean | SD | SE | Half width | Plain [L, U] | Floored [L, U] |
|---|---|---|---|---|---|---|---|
| R1 Wq binds (h) | 0, 0, 0, 0, 0.1 | 0.02 | √0.002 = 0.0447214 | 0.02 | 0.0555289 | [−0.0355289, 0.0755289] | [0, 0.0755289] |
| R2 Wq does not bind (h) | 0.10, 0.12, 0.14 | 0.12 | 0.02 | 0.0115470 | 0.0496828 | [0.0703172, 0.1696828] | unchanged |
| R3 waiting_end binds | 0, 0, 0, 0, 2 | 0.4 | √0.8 = 0.894427 | 0.4 | 1.110578 | [−0.710578, 1.510578] | [0, 1.510578] |
| R4 no spread | 0, 0, 0 | 0 | 0 | 0 | 0 | [0, 0] | [0, 0] |
| R5 one replication | 0.3 | 0.3 | None | None | None | None | None |
| R6 NovaMart 10:00 (REPORTED inputs) | — | 0.81 min | — | — | — | [−0.02395 h, 0.05091 h] | [0 h, 0.05091 h] = 0 to 3.05 min |

R6 is arithmetic on the reported bounds only (max(0, −0.02395) = 0); the NovaMart run itself was not rerun here (NOT TESTED).

## 7. Verification

- Unit (new `tests/test_separate_wait_interval_floor.py`): R1-R5 against the literals above; the aggregator floors `waiting_time`, `Wq`, `waiting_end`, leaves the upper bound, mean, SD, SE and n unchanged, and leaves utilization, arrivals and served unfloored.
- API: `wait_ci` of a computed plan never has a negative lower bound.
- Existing test `tests/test_separate_des_replications.py::…` pinned the plain lower bound of `waiting_time` (0.20 − 0.248 < 0). It is updated to `max(0, 0.20 − half width)`, because the specified behavior changed, not to hide a defect.
- Mutation: removing `floor=0.0` from each of the three call sites must make a test fail.
- Gates: `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`. No frontend file changes, so the frontend gates are not required.

Results 2026-10-29 (local Windows, Python 3.13, SQLite; PostgreSQL not run):

- New tests failed on the unchanged code for the two behavior tests (aggregator, API) and passed after the change. Targeted set (`test_separate_wait_interval_floor.py`, `test_separate_des_replications.py`, `test_u10_f16_separate_cost.py`): 20 passed.
- Mutation: removing `floor=0.0` from `waiting_end`, `Wq`, `waiting_time` each made at least one test fail (1, 1 and 3 failures). 3/3 killed.
- `ruff check .`: passed.
- `mypy .` (mypy 2.1.0): 1 error at `backend/api/shared_continuous.py:447` (`_assess` argument type). The same single error occurs on a clean export of base `3ee8fe2c`, so it predates this change; this change does not touch that file.
- Full suite `python -m pytest tests/ -x --tb=short`: 3294 passed, 125 skipped, 1 xfailed, 9 subtests passed, exit 0 (43 min). The 125 skips are PostgreSQL-dependent tests (no PostgreSQL here: NOT TESTED).
- CI's mypy is installed unpinned (`.github/workflows/ci.yml:25`); whether CI reports the `shared_continuous.py:447` error is UNKNOWN.

## 8. Open items for the owner

- OD-W1: engine version (§5). DECIDED 2026-10-29: (a), no version change, as implemented.
- OD-W2: also floor `utilization`, `arrivals`, `served` (all non-negative)? Not done; outside this approval.
- OD-W3: the shared-line replication summaries (`shared_replications.py` `summarize_metric`, `:277-297`; named `shared_named_replications.py:368, 391`) use the same symmetric interval with no floor. Independent read-only review 2026-10-29 (gokudera subagent) found negative wait lower bounds on SYNTHETIC inputs. Examples:
  - anonymous, DRAIN, 5 reps, seed 42: [−0.018, 0.647] h;
  - named fixture (`scripts/generate_shared_named_fixture.py`), 3 reps, seed 20261001: [−0.511, 1.567] h.

  The named one is shown today by `frontend/src/components/simulation/NamedReplicationTable.tsx:96-104` (about −30.7 to 94.0 min for that fixture).

  NovaMart evidence (REPORTED by the parent session's chart agent, 2026-10-29). It ran the NovaMart xlsx as a shared line with 5 fixed counters: a full-day continuous run, 5 days, seed 42, scratch SQLite at `3ee8fe2c`. Negative lower bounds it saw:
  - current run: `mean_wait_hours` −0.00059 h, `wait_sum_hours` −0.09122 h, `time_average_queue_in_horizon` −0.00702;
  - plan run: `waiting_hours_after_close` −0.01505 h, `server_hours_above_schedule_in_horizon` −0.0189 h.

  The anonymous `ContinuousRun.tsx` shows the lowest–highest day, not these intervals, so it shows no negative; this agrees with the review above. The named table is the one screen that shows the interval. Shared Results plan rows are analytical M/G/c and carry no interval.

  The owner has not authorized any shared-line engine change: this is evidence only. A fix is a separate protected change; it cannot be one blanket floor (`server_hours_above_schedule_in_horizon` may be negative, UNKNOWN), needs the interval-method text and probably a version decision. Not part of this task.
- Observation, corrected 2026-10-29: in the continuous day, `waiting_end` = `max(0, arrivals − served)` (`:1833`) is always 0 in valid evidence. The run continues to `day_end + 24` h (`:1230`) and must serve every admitted customer (`:1231`); the aggregator rejects any run that does not. The earlier note that it "may count a customer in service" cannot reach valid evidence. INFERRED from code; the review's 200-seed check found no window with arrivals ≠ served.
- Older run-type differences, not caused by this change and not changing the sign (INFERRED from code, size NOT TESTED):
  - In the per-period run, a customer still in service at the horizon adds to `wait_sum` (`:950`) but not to `served` (counted at service end), so it is in the numerator but not the denominator.
  - Time spent waiting for an open lane counts in the continuous day only (arrival taken before that wait, `:1191`) and not in the per-period run (taken after it, `:1020`).
