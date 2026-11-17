# Separate lines: optional lane closing in Optimize — design

- **Date:** 2026-11-10
- **Status:** DRAFT — awaiting owner review of this written spec. Not implemented.
- **Base:** branch `codex/repository-cleanup-20261101`, HEAD `39aa93802`.
- **Risk class:** HIGH (optimization behavior, Decision inputs, saved-plan verification).
  Protected-change authorization is required before implementation (AGENTS.md §5).

## 1. Problem (VERIFIED)

Every separate-lines plan reports "Counter changes: none". In the owner's downloads,
reports 2, 3, 5, 7, 18 (novamart) and 27 all show identical "Current staffing
(simulated)" and "With the plan" columns. The shared-line reports 6 and 11 do show
changes.

Cause: Separate optimization runs under **full coverage**.
`full_coverage_min_lanes` (`backend/queueing_engine/services/separate_optimization.py:135-150`)
forces `min_active_lanes` to equal the configured queue count, and
`optimize_separate_schedule(..., full_coverage=True)` (`:1873-2011`) sets each period's
lower bound to its scheduled lanes. Each period therefore has exactly one candidate.
The full-report Excel for report 27 shows that one candidate in "Plan search"
(`2 | chosen` for every period). This is a recorded known limitation
(`docs/superpowers/specs/2026-09-18-separate-representative-day.md`, "Known
limitation"). Full coverage was approved in commit `f9e6e69f6` as "existing lane-bound
mechanism; no new mathematics". It is a product rule, not a mathematical limit.

## 2. Owner decisions (2026-11-10, in chat)

| ID | Question | Decision |
| --- | --- | --- |
| D1 | What may the optimizer suggest beyond today? | **Close lanes only.** Never open lanes beyond each period's scheduled lanes. |
| D2 | Which lane closes? | **Fixed order:** close from the end of the Setup lane list (`queue_setup.queue_ids`). No combinations, no new Setup field. |
| D3 | Whole-day setups (lines carry across hours) | **Hour by hour, in order**, then use the complete plan's evidence. |
| D4 | How is it turned on? Summary-only data? | **Opt-in switch, off by default.** It is unavailable for summary-only data, and the reason is shown. |
| — | Section approvals | Sections 1–3 of the in-chat design approved. |

## 3. Existing capability reused (VERIFIED)

- Reduced lane sets are evaluated by the routing DES: one conserved arrival stream,
  shortest-system-size routing with seeded ties, and each lane served from its own
  empirical service samples (`separate_optimization.py` module docstring;
  `evaluate_candidate_with_des_replications`, `_optimize_separate_des:1575-1654`).
- Analytical (summary-only) rows return UNSUPPORTED for reduced sets
  (`evaluate_candidate:287-330`). No approved representation exists. This spec keeps it so.
- Candidate ranking: lowest mean replicated total cost among feasible candidates, with
  ties going to fewer lanes. The recommendation is KEEP, REDUCE or INCREASE
  (`_optimize_separate_des`, `rank_des_candidates`).
- Downstream consumers already read each period's `optimum.active_queue_ids` and
  `inactive_queue_ids`. These are the selected-plan DES (`backend/api/workflow.py` ~2640-2680),
  the continuous-day selected-plan DES (~2878-2905), Monte Carlo, the Results check, the
  Decision and reports (`backend/reports/separate_report.py:59-66`). Tests already pin
  REDUCE plans: `tests/test_selected_plan_simulation.py`, `test_selected_plan_validation.py`,
  `test_selected_plan_decision.py`, `test_separate_report.py`.
- Not yet supported: the continuous-day optimizer runner `_day_candidate_runner`
  (`:1735-1870`) returns INVALID_INPUT for any active set other than the scheduled
  lanes ("Continuous-day evaluation needs the scheduled lanes of every period.").

## 4. Behavior

### 4.1 Switch and bounds

- `SeparateOptimizeRequest` (`backend/api/workflow.py:179-190`) gains an optional
  `lane_closing: bool = False`. This is **additive**: existing clients are unchanged.
- `lane_closing == False`: today's behavior, byte-for-byte. `full_coverage_min_lanes` is
  still enforced, and results equal today's for the same inputs.
- `lane_closing == True`:
  - `min_active_lanes` is required, an integer with `1 <= min_active_lanes <=` the
    configured queue count. The UI defaults it to 1.
  - Each period's candidates are lane counts from `max(min_active_lanes, 1)` up to
    that period's **scheduled** lane count. If a period's scheduled count is below
    `min_active_lanes`, that period keeps its scheduled lanes (single candidate). It is
    never raised (D1).
  - `max_active_lanes` must be absent or equal to the configured count. Any other value
    returns 422 with an exact reason. Opening lanes is out of scope (D1).
  - The records-equal-scheduled-lanes check stays (a period's records must name exactly
    its scheduled lanes). Only the lower bound changes.
- The candidate active set for count *k* is the first *k* lanes of
  `queue_setup.queue_ids` **filtered to that period's scheduled lanes** (D2). This fixes
  a VERIFIED gap: today `build_candidates` uses the order of the period's data rows,
  which may differ from the Setup order when staffing varies by period.

### 4.2 Summary-only data (D4)

- If any lane the search could activate lacks valid `service_samples_hours`, then
  `lane_closing == True` returns **422** with an exact reason. There is no silent fallback
  to full coverage and no analytical approximation.
- The Optimize page disables the switch for such analyses and shows the owner's reason
  text (W-3). How the page detects summary-only data is **UNKNOWN**. The plan must locate
  an existing field that marks the upload type, or add an additive response field.

### 4.3 Per-period setups (independent 24 h runs per period)

These are setups where neither `event_period_basis == "representative_day"` nor
`per_date_continuous(setup)` holds, for example report 27. Each period runs
`_optimize_separate_des` over its candidates exactly as today, only with more than one
candidate. Status semantics are unchanged: `OPTIMAL` means the cheapest feasible
candidate within the fixed-order search, estimated by simulation.

### 4.4 Whole-day setups: hour-by-hour search (D3)

Applies when `_day_candidate_runner` is used (representative day, or B13 per-date
continuous). Each calendar day (one per date for B13; one representative day otherwise)
is searched independently, because dates start empty (B13).

For one day with periods `P1..Pn` in time order:

1. Set every period to its scheduled lanes.
2. For `i = 1..n`: for each candidate count of `Pi` (§4.1), run the continuous-day DES
   with `P1..P(i-1)` at their chosen sets, `Pi` at the candidate, and `P(i+1)..Pn` at
   their scheduled lanes. Use the configured replications and the **same replication
   seeds for every candidate** (common random numbers). Classify each candidate with the
   existing aggregate feasibility rule for period `Pi` (`apply_des_aggregate_feasibility`).
   Choose the feasible candidate with the lowest mean **whole-day** total cost, with ties
   going to fewer lanes. If none is feasible, `Pi` is INFEASIBLE, as today.
3. Lock `Pi`'s choice and continue.
4. The reported per-period evidence (utilization, wait, costs, uncertainty) comes from
   the **final complete plan's** runs, so every number describes the plan as saved.

Supporting claims:

- **INFERRED — must be proven by a test (T5):** with identical seeds, a change at `Pi`
  leaves every period before `Pi` identical, because the simulation is causal and its
  arrival, per-customer service-quantile and tie streams are paired by seed
  (`_paired_stream_seeds` / `_paired_streams`, `separate_optimization.py:838-854`).
- Each period result gains an additive field `search_method: "hour_by_hour"`. Per-period
  setups get `search_method: "per_period"`. The plan is the **best found by this
  search**, not a proven global optimum. Reports and the Decision must not describe a
  `hour_by_hour` plan as "optimal" (wording slot W-5).
- `_day_candidate_runner` is extended to accept non-scheduled active sets that are
  subsets of the scheduled lanes, in the fixed order. The INVALID_INPUT refusal stays
  for any other set.

### 4.5 Work limit (refusal before running)

- Whole-day work = `replications × Σ_days Σ_periods (candidate count)` continuous-day
  runs, plus the final plan's `replications` runs per day. Example (VERIFIED from
  report 18's lane counts 3, 5×11, 2; 5 replications; minimum 1): 5 × 60 = 300 day
  runs, versus 5 today.
- Before running, the API computes the expected simulated customers for the whole
  search. If they exceed a limit, it returns 422 with
  `code: "limit_exceeded"`, the computed value and the limit. The limit then becomes a
  required request option. This follows the existing pattern in
  `backend/api/shared_continuous.py` (`C_MAX`, `limit_exceeded`).
- **The limit value is UNKNOWN** (OD-1). It is set only after the NovaMart local timing
  measurement (§7, step M1) and owner approval.

### 4.6 Saved scenarios and engine versions

- Saved separate scenarios record `lane_closing` in `options`. `_verify_calculation`
  (`backend/api/scenarios.py:174-213`) passes it when recomputing. Scenarios without the
  key verify as `lane_closing == False`, unchanged.
- The `min_active_lanes` check in `scenarios.py:188-191` keeps full coverage when
  `lane_closing` is absent or false. When it is true, it accepts the §4.1 bounds.
- Plans calculated with `lane_closing == True` carry a **new engine version string**.
  The value is chosen in the plan, distinct from `novaq-2026-10-separate-des-v4` and
  `-v5` (`separate_optimization.py:73-74`). Plans with the switch off keep the current
  versions, so existing saved plans stay current and verifiable.

## 5. Unchanged (protected)

Queueing formulas and central model selection; the utilization/feasibility rule and
tolerance; cost formulas (`_segment_server_cost`, `_compute_waiting_cost`); routing and
tie policy; break lifecycle (3-minute pre-break cutoff, drain, rest); continuous-day DES;
Monte Carlo semantics; Results-check thresholds; confidence intervals; **Decision rules**
(including "Modeled savings are unavailable for Separate plans"); shared-line behavior;
summary-only analytical behavior; reports in minutes.

## 6. Wording slots (owner writes; en + tl, placed verbatim)

| Slot | Where | Purpose |
| --- | --- | --- |
| W-1 | Optimize | Switch label |
| W-2 | Optimize | Switch help text (closes from end of lane list; customers move to shortest open line) |
| W-3 | Optimize | Reason the switch is unavailable (summary-only data) |
| W-4 | Optimize | Minimum open lanes label and help |
| W-5 | Plan/Report/Decision | Note that an hour-by-hour plan is the best found, not proven optimal |
| W-6 | Optimize | Work-limit refusal message (shows value and limit) |
| W-7 | Report (PDF + Excel) | Line naming the search method and closed lanes per period |
| W-8 | Decision, Report (PDF + Excel) | Note beside "Net lane change across periods" (owner request 2026-11-10, so a negative value does not alarm readers). Must convey: plan lanes minus current lanes summed over periods (lane-hours); negative = fewer open lane-hours, positive = more, 0 = same; negative is not an error or a loss. The value stays signed and is never floored (2026-10-29 floor decision excludes differences). |

Agents do not write or translate these. The plan stops at each slot until the owner
supplies the text.

## 7. Verification (required before claiming complete)

| ID | Check |
| --- | --- |
| T1 | Switch off: every existing test passes unchanged (incl. `tests/test_separate_full_coverage.py`), and saved scenarios re-verify. |
| T2 | Closing order follows `queue_setup.queue_ids` when period rows are in another order. |
| T3 | Bounds: min < 1, min > lane count, max ≠ lane count, or a non-full min with the switch off → 422 with an exact reason. |
| T4 | Hand-checkable reference cases: (a) a very low-load period where fewer lanes must win on cost and pass the target; (b) a high-load period where closing breaks the target and the scheduled count is kept or INFEASIBLE. The expected outcomes are derived in the plan before the code. |
| T5 | Causality: a change at `Pi` leaves all earlier periods' per-lane results identical (same seeds). |
| T6 | Hour-by-hour search on a small fixed 3-period example returns the expected per-period sets; the reported evidence equals the final complete-plan runs. |
| T7 | Work-limit refusal returns `limit_exceeded` with exact numbers; summary-only data with the switch on returns 422. |
| T8 | Save → re-verify round trip with the switch on; new engine version recorded; Simulate / Monte Carlo / Results check / Decision / PDF + Excel report run on a lane-closing plan and show the per-period changes. |
| T9 | Frontend: switch and minimum field send the new fields; switch disabled for summary-only; en/tl keys symmetric. |
| T10 | Mutation checks on the new search, bounds and order code (project practice). |
| M1 | Local timing of NovaMart (report 18 setup) with the switch on, default replications. The result is recorded and the owner sets OD-1. |
| B1 | Browser check: Optimize switch, plan view, store floor closed-lane badge (REPORTED to exist; verify). |
| G | Gates: `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`; in `frontend/`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`. |

Independent review by Kyoya is required (HIGH risk). Production behavior stays
NOT TESTED until an authorized release.

## 8. Open decisions

- **OD-1:** Work-limit value (§4.5), set after M1.
- **OD-2:** Wording W-1..W-8 (§6), en + tl.
- **OD-3 (future, out of scope):** whether a later spec lets the Decision compare
  current-staffing cost with a lane-closing plan. Today savings stay unavailable for
  Separate plans.

## 9. Out of scope

Opening lanes beyond the schedule; choosing which lanes close by cost (combinations) or
by a new Setup priority field; analytical approximations for reduced sets with
summary-only data; Decision/savings changes; shared-line changes; production release.
