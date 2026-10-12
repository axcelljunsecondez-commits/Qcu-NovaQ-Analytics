# B13 — Per-date separate-lines plans as one continuous day per date

**Status:** APPROVED by the owner in chat on 2026-10-12 ("go" = the recommended answer to every question in §9). No code is changed by this document. Implementation is plan step 10b, after step 10 (B4a + U7b) and before step 11, and starts only with the owner's GO for that step.

**Parent:** compact workflow UX redesign (`2026-10-09-compact-workflow-ux-redesign.md`), found while verifying plan step 9. It is not part of step 10 (B4a).

## 1. Problem

For separate lines with `event_period_basis: per_date`, NovaQ judges staffing options (optimizer) and checks the selected plan (selected-plan DES) by simulating **each period alone for the DES horizon**, which defaults to 24 h (`DES_DEFAULT_DURATION_HOURS = 24.0`, `separate_optimization.py:90`). The breaks a period owns are placed at their offset from the operating day's start (`period_des_breaks`, `separate_optimization.py:760-789`).

This is already recorded as known limitation **K1** in `memory.md` (2026-09-19). The fix for the representative-day basis ("Finding K", commit `9b1f95a4`, `_day_candidate_runner`, `separate_optimization.py:1666`) was never extended to per-date. A test pins today's per-date behaviour: `tests/test_separate_day_feasibility.py::test_per_date_basis_keeps_the_24_hour_candidate_runs`.

Two errors follow (VERIFIED):

1. **Dilution.** A break that fills a one-hour period is about 1/24 of a 24 h run. Its effect on utilization and waits nearly disappears, and a break hour can be marked FEASIBLE when the same hour inside the real day is not.
2. **No carry-over.** Each period starts empty. Customers still waiting at the end of a busy hour, or of a break, never reach the next hour.

Correcting only the break's start time does not fix either error (§2).

## 2. Evidence (proof run, 2026-10-12)

NovaQ's own engine, SYNTHETIC fixtures of `tests/test_separate_day_feasibility.py`: lanes `a`, `b`; 4.5 customers/h each; recorded service samples with mean 6 min; periods 10:00, 11:00, 12:00; lane `b` on break 11:00-12:00; 30 seeds (scratchpad script `break_proof.py`, read-only).

| Lane `a`, 11:00 hour | Today (24 h per period) | Break time corrected only | One continuous day |
|---|---|---|---|
| Utilization | 0.477 | 0.477 | 0.749 |
| Average wait | 1.86 min | 1.68 min | 8.34 min |
| Wait at 12:00 | 1.14 min | 1.14 min | 1.71 min |
| Simulated customers (all periods, 30 seeds) | 19,876 | 19,876 | 845 |
| Time on the development PC | 1.62 s | 1.50 s | 0.10 s |

Conservation check of the continuous day: lane `a` received 9.03 customers in the 11:00 hour (0.90 h of work at 6 min each). Its busy time over 11:00-12:00 was 0.749 + 0.579 = 1.328 h, which equals the work that arrived in those two hours, (9.03 + 4.27) × 0.1 = 1.33 h. Utilization in the break hour is below 0.9 because work carries into 12:00, which the per-period runs cannot show.

## 3. Basis

- Treating each period as an independent stationary queue is the SIPP approach. It can miss service targets during a significant part of the day, and peak congestion lags the arrival peak (Green, Kolesar and Soares, *Operations Research* 49(4), 2001; Green, Kolesar and Whitt, *Production and Operations Management*, 2007; Eick, Massey and Whitt, *Management Science*, 1993).
- A store that opens empty and closes is a terminating system. It is simulated from opening to closing with independent replications, not as long steady-state runs (simulation output-analysis tutorials, Winter Simulation Conference, after Law and Kelton).
- NovaQ already applies this to representative-day plans (`_day_candidate_runner`, `_run_selected_plan_day_des`). B13 applies the same engine to per-date plans; it adds no new queueing model.

## 4. Scope

In scope:
- Separate lines, `event_period_basis: per_date`, customer-record uploads with configured operating segments (so a day can be laid out).
- The optimizer's full-coverage path (the one Suggested plans and scenario verification use: `workflow.py:1734`, `scenarios.py:208`).
- The selected-plan DES (`_run_selected_plan_des`) and the checks that read it (Validation, Decision).
- The Queue simulation pages: per-date plans replay a whole day per date, and the per-date break notice from step 9 is removed for runs made with B13.

Out of scope:
- Per-date uploads without configured segments (legacy hourly buckets): no operating hours to lay out a day (§9, OD-B13-3).
- Shared lines (B4a, B4b, B4c).
- Monte Carlo (analytic per period, spec G11): unchanged.
- The break optimizer (requires `representative_day`, `break_optimization.py:299`): unchanged.
- A staffing search across the continuous day (§8, B13b).

## 5. Rules

1. **One day per date.** Periods are grouped by calendar date: the first token of the per-date label `"<YYYY-MM-DD> <segment> UTC"` (`analysis_ingestion.py:61-63`). Each record's `segment_id` names its configured segment, and that gives its window on the day clock (`_segment_window`, origin `des_day_start_minutes`). For each date and each replication seed, one `run_routing_day_des` call simulates the date from its first configured segment to its last.
2. **Dates are independent.** Each date starts empty. Nothing carries from one date to the next (separate terminating runs). Each date also gets its own seed (implementation note 2026-10-12: `date_seed`, date 0 keeps the replication seed), so dates with equal inputs are independent samples rather than identical replays.
3. **Breaks.** `resolve_des_breaks(setup)` is applied to every date, placed at their real time and length within that date.
4. **Evaluation.** Each period's lane values come from its own date's day run, as `_day_candidate_runner` already does: utilization = busy time in the period / period length (clamped at 1), waiting cost with the period as the horizon, and `utilization_basis = "continuous-day DES"`. As on the representative-day path, the day runner evaluates the scheduled lanes of each period. Other candidates are refused (`separate_optimization.py:1717-1720`), never silently run as 24 h periods.
5. **No silent fallback.** If a date cannot be laid out, the schedule is `INVALID_INPUT` with a reason naming the date and segment, as K2-a does for representative-day. NovaQ never falls back to 24 h period runs. Causes include a period whose `segment_id` matches no configured segment, a malformed segment time, or a configured segment with no records on that date (§9, OD-B13-2).
6. **Selected-plan check.** `_run_selected_plan_des` dispatches per-date plans with segments to a per-date day run (`_run_selected_plan_day_des` applied date by date). The stored result records `execution = SELECTED_DES_CONTINUOUS_DAY_EXECUTION`, which is already a current value of the `selected_des_basis` family (`workflow.py:850-852`).
7. **Totals.** The B12 pattern applies: the server adds up per-date day totals (arrivals, served, still in line at closing) per date and for all dates. The browser sums nothing new.

## 6. Versioning (saved plans)

A saved separate-lines plan must carry `engine_version == SEPARATE_DES_ENGINE_VERSION` (`"novaq-2026-09-separate-des-v2"`). Otherwise it is not selectable (`workflow.py:253-256`) and cannot be saved (`scenarios.py:166`).

Option A: bump the single version to v3.
- Every saved separate-lines plan, representative-day ones included, becomes unselectable until recalculated.
- Representative-day results do not change under B13, so this marks correct evidence as outdated.

Option B (recommended): a basis-specific current set.
- `…-separate-des-v2` stays current for representative-day snapshots.
- Per-date snapshots must carry `…-separate-des-v3`.
- A per-date v2 plan is "historical: recalculate" and is shown with that reason (4d).
- The basis is read from the plan's own bound Setup (its `setup_hash` snapshot), not from today's Setup.

## 7. Free-tier budget

Free tier as published: Render free web service 512 MB RAM, 0.1 CPU.

Simulated customers per optimizer evaluation (R replications, λ_p total arrival rate of period p, d_p its length in hours, K_p candidates tried):
- Today: Σ_p K_p · R · 24 · λ_p.
- B13: Σ_dates R · Σ_p d_p · λ_p.

For one-hour periods B13 simulates at least 24 times fewer customers (§2: 845 vs 19,876). It also needs only one day run per seed and date, cached across the date's periods, as `_day_candidate_runner` does.

Render run time is NOT TESTED. The implementation gate measures run time and peak memory locally on the largest per-date fixture. It also checks that every day run stays within the existing `max_events` and trace bounds.

## 8. Later option (not in B13): B13b, staffing search across the day

On a continuous day the periods are not independent, so lanes cannot be chosen period by period.

The simulation-based iterative staffing algorithm (ISA) of Feldman, Mandelbaum, Massey and Whitt (*Management Science* 54(2), 2008) sets time-varying staffing by repeated simulation of the whole day. A NovaQ adaptation for separate lanes could work like this:
- start from the per-period analytic minimum;
- simulate the day;
- add a lane in the earliest period over target;
- repeat until every period meets the target or no lanes remain.

This adaptation is PROPOSED only. Its convergence and quality for routed separate lanes are UNKNOWN until tested, and it needs its own spec after B4a/B4b.

## 9. Owner decisions

- **OD-B13-1 Versioning:** Option A or Option B (§6). Recommended: B. **Owner answer (2026-10-12): B.**
- **OD-B13-2 A configured segment with no records on a date:** refuse the schedule naming the date and segment, or treat that date's segment as zero arrivals. Recommended: refuse. Zero arrivals would claim the store was open and empty, which the upload does not show. Today full coverage already refuses a period whose lanes do not match the schedule (`separate_optimization.py:1862-1866`). **Owner answer (2026-10-12): refuse.**
- **OD-B13-3 Per-date uploads without configured segments:** keep today's method with the step 9 notice, or refuse. Recommended: keep, with the notice. **Owner answer (2026-10-12): keep, with the notice.**
- **OD-B13-4 Order:** B13 after step 10 (B4a + U7b) and before step 11. Recommended: yes. B13 reuses tested representative-day code and fixes a known correctness limit, so it should not wait for the help or report phases. **Owner answer (2026-10-12): yes (plan step 10b).**

## 10. Tests (implementation gate)

- Replace `test_per_date_basis_keeps_the_24_hour_candidate_runs`: a per-date schedule now carries `utilization_basis = "continuous-day DES"`, and the 11:00 break hour's candidate utilization matches the continuous day of its date (above 0.70 in that fixture, as for representative-day).
- Two dates: each date's results equal its own day run. Day 2 starts empty. A break on day 1 never affects day 2.
- The selected-plan per-date run equals the per-date day runs (event multiset equality, as `test_b5_break_events.py` does for representative-day).
- No fallback: an unmappable date gives `INVALID_INPUT` naming the date, and no 24 h run happens (spy on `evaluate_candidate_with_des`).
- Versioning (Option B):
  - a representative-day v2 plan stays CURRENT;
  - a per-date v2 plan is historical, unselectable and shows its reason;
  - a new per-date plan saves v3 and passes re-verification.
- The B12 totals per date and for all dates come from the server.
- Budget: simulated-customer count per evaluation is at most today's / 24 on the §2 fixture.
- Frontend: the per-date break notice is gone for continuous-day results, and the replay offers a date picker plus a full-day replay.
- Mutation testing on the date grouping, dispatch, version gate and no-fallback rule.
- PostgreSQL: NOT TESTED unless the owner authorizes the WSL PostgreSQL run.

## Sources

- Green, Kolesar, Soares (2001), Improving the SIPP approach for staffing service systems that have cyclic demands: https://pubsonline.informs.org/doi/fpi/10.1287/opre.49.4.549.11228
- Green, Kolesar, Whitt (2007), Coping with time-varying demand when setting staffing requirements (summary): https://academicnewsletter.sufe.edu.cn/info/406031
- Eick, Massey, Whitt (1993), peak congestion lag: https://ideas.repec.org/a/inm/ormnsc/v39y1993i2p241-252.html
- Feldman, Mandelbaum, Massey, Whitt (2008), Staffing of time-varying queues to achieve time-stable performance: https://pubsonline.informs.org/doi/fpi/10.1287/mnsc.1070.0821
- Terminating vs steady-state simulation (WSC tutorial): https://www.informs-sim.org/wsc06papers/004.pdf
- Render compute plans: https://render.com/docs/compute-plans.md
