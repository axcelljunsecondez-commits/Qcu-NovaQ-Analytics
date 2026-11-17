# Separate lines: apply Setup breaks in the Current simulation — design

- **Date:** 2026-11-10
- **Status:** APPROVED SPECIFICATION — owner approved the written spec on 2026-11-10. Not implemented.
  OD-1 and OD-2 (§8) remain open. The implementation plan and code wait for SEED-001 (D4).
- **Status update (2026-11-17):** IMPLEMENTED differently and SUPERSEDED in part. Codex PR #58
  (commit 37381fed) made the Current simulation use the uploaded break times with the rule "customers
  stay in their own line during a break"; the owner chose that rule on 2026-11-16, superseding this
  spec's D1. Kept for history; do not implement from this file.
- **Source base:** `origin/main` `702a6aa10` (contains C-PD). Line numbers below refer to that commit.
  This spec file sits on branch `codex/repository-cleanup-20261101` (`39aa93802`), which is behind `main`.
- **Risk class:** HIGH (discrete-event simulation behavior, evidence versioning). Protected-change
  authorization is required before implementation (AGENTS.md §5).
- **Sequencing (owner, 2026-11-10):** implementation starts only after Codex SEED-001 is committed,
  because SEED-001 also plans changes in `simulation.py`.

## 1. Problem (VERIFIED)

A separate-lines customer-event workbook carries a `breaks` sheet (`queue_id`, `break_name`, `start`,
`minutes`; `backend/data/templates.py:121-160`). Upload reads it into `QueueSetup.breaks`
(`backend/data/setup_derivation.py:135-224`). Optimize, the selected-plan simulation, the Results check and
break suggestions apply those breaks through the routing DES (`separate_optimization.py`
`resolve_des_breaks:719`, `_validate_breaks:804`, `_run_routing_des:862`, `run_routing_day_des:1032`).

The separate-lines **Current** simulation does not. `run_des_current` (`backend/api/workflow.py:1526-1571`)
calls `simulate_segments_with_trace` or the C-PD per-date runners (`simulate_parallel_days_with_trace:1126`,
`simulate_parallel_days_compact:1207`). All of them reach `_simulate_parallel_segments_core`
(`simulation.py:767`; callers at ~956, ~1029, ~1156), which has no break logic (no break reference in
`simulation.py`). The app labels this ("Breaks not included", `simulation.run_basis_continuous_no_breaks`,
`charts.key_basis_no_breaks_separate`; `simulationContext.ts:81,98`, `KeyResultsView.tsx:50,244-248`,
`RunBar.tsx:94`), and the 2026-10-29 chart spec records it (K-UC-3). No record states a decision to keep
Current without breaks. That it was never built is **INFERRED**.

Effect: on the Simulation page, separate Current looks better than reality (no cashier ever leaves), and
Current vs plan is not the same basis. PDF/Excel reports are unaffected: no report code reads
`workflow_des_current`. Their "Current staffing (simulated)" column comes from the routing DES, which
already applies breaks.

## 2. Owner decisions (2026-11-10, in chat)

| ID | Question | Decision |
| --- | --- | --- |
| D1 | New customers of a lane that is draining for, or on, a break | **Shortest open line**, the same rule as the plan simulation. No customer lost. |
| D2 | Existing saved Current runs | **Rerun only if the Setup has breaks.** Without breaks, old runs stay current. |
| D3 | Approach | **A:** add breaks to the existing Current engine; customers keep their own lane's recorded rate outside break windows. (Rejected B: run Current through the routing DES, which routes every customer all day.) |
| D4 | Sequencing | Code after SEED-001. |
| — | Section approvals | Sections 1–3 of the in-chat design approved. |

## 3. Behavior

### 3.1 Scope

Separate-lines Current simulation only: the single-day path and both C-PD per-date paths. It applies when
`QueueSetup.breaks` is non-empty. A Setup without breaks behaves exactly as today (§3.4).

### 3.2 Break rule (identical to the routing DES)

For each break of lane *L* with scheduled start *s* and duration *d*:

1. **Draining** from `max(0, s − PRE_BREAK_CUTOFF_MINUTES)` (3 min, `backend/queueing_engine/config.py:30`): *L* accepts no new
   customers and serves everyone already in its line (`DedicatedQueueLifecycle.begin_draining`,
   `queue_lifecycle.py:114`).
2. **On break** once *L* is empty: the cashier rests the full *d* (`begin_break:127`). A break never
   strands a customer (`begin_break` raises while occupied).
3. **Back**: *L* returns to ACTIVE (`end_break:138`) and takes customers at its own rate again.
4. **Routing during 1–2:** an arrival generated for *L* joins the shortest open lane by system size
   (waiting + in service) via `route_arrival` (`separate_optimization.py:214`), with seeded fair ties and
   configured lane order. The customer keeps its own arrival period's identity for statistics.
5. **No open lane:** the arrival waits until the next lane becomes eligible, then is routed by rule 4.
   This is the routing DES rule (`separate_optimization.py:883-884, 1009-1018`). Nobody is dropped.
6. Lanes closed by the schedule (not by a break) keep today's handling unchanged: the arrival `continue`
   at `simulation.py:869` applies only to them.

Break times come from `resolve_des_breaks` / `breaks_to_des_offsets` (`separate_optimization.py:680-751`),
reused, not copied, so wall-clock conversion, the cutoff and validation match the plan. Invalid breaks
(outside operating hours, overlapping, unknown lane) refuse the run with the existing exact reason.

### 3.3 Per-date (C-PD)

Each date is its own day starting empty (unchanged) and applies the same Setup breaks at their wall-clock
times. Date seeds (`date_seed`) are unchanged. For a lane that is closed by that date's schedule at the
break time, see OD-2.

### 3.4 No breaks → identical results

When the Setup has no breaks, the run must draw exactly the same random numbers as today. The tie stream is
created from the seed only when breaks exist, and it never consumes the main stream. Results and traces are
byte-identical to the current engine for the same inputs and seed (test T1).

### 3.5 Trace and replay

The run records `draining_start`, `break_start` and `break_end` events with the same names and fields the
routing DES records (`separate_optimization.py:971-994, 1168-1179`). Customer conservation
(`arrivals = served + waiting + in_service`) must still hold per lane and in total. A routed customer counts
as an arrival of the lane that served it, and the lane it was generated for is recorded on the event. Whether
Current replay already renders these events (the B5 playback work for plans) is **REPORTED**, and is
verified in B1.

## 4. Evidence versioning (D2)

- `CURRENT_DES_BASIS` (`workflow.py:106`) becomes `per_date_days_v4` for new separate-lines Current runs.
- A `per_date_days_v3` run stays current **only when the analysis Setup has no breaks**. With breaks it is
  "needs one rerun" through `_current_evidence_policy` (`workflow.py:985-1031`). `v1`, `v2` and unlabeled
  runs keep their current treatment.
- The rule reads the Setup the evidence was produced for (setup fingerprint), not a later Setup.

## 5. Screens and wording

These labels become untrue for separate Current once breaks apply, and must show only when true:
`simulation.run_basis_continuous_no_breaks`, `charts.chip_no_breaks` (Current side),
`charts.key_basis_no_breaks_separate`, `simulation.breaks_not_modeled`, and the "not the same basis"
break wording when both runs include breaks. Replacement or new texts are **owner wording** (OD-1), placed
verbatim in `en` and `tl`. Agents do not write or translate them.

## 6. Unchanged (protected)

Current arrival rates, recorded service sampling and per-lane arrivals outside break windows;
schedule-closed lane handling; routing DES, optimizer, break optimizer; break conversion and the 3-minute
cutoff; Monte Carlo, Results check, Decision; PDF/Excel reports; shared-line runs (the full-day run already
applies counter breaks, B4c; the per-period shared run stays as is); C-PD grouping, compact storage, size
limits and the 413 refusal.

## 7. Verification (required before claiming complete)

| ID | Check |
| --- | --- |
| T1 | No breaks: for several seeds, single-day and per-date (one and several dates), results and traces equal the pre-change engine exactly. |
| T2 | Hand-checkable case: 2 lanes, 30-min break on b at 09:00. b accepts nothing from 08:57, empties, rests 30 min after emptying, reopens. Its arrivals in that window are served by a. Conservation holds. The expected event sequence is written in the plan before the code. |
| T3 | Every lane on break at once: arrivals wait, then route on the first reopening. Nobody dropped. |
| T4 | Parity with the routing DES: matching inputs give the same break timing and event sequence. |
| T5 | Invalid breaks (outside hours, overlap, unknown lane) refuse with the exact reason. Nothing is skipped silently except per OD-2. |
| T6 | Per-date: breaks apply on each date, and date seeds are unchanged. |
| T7 | Versioning: v3 + no breaks stays current; v3 + breaks needs a rerun; new runs record v4. |
| T8 | Frontend: no-breaks labels only when true; Current replay shows break states; en/tl keys symmetric. |
| T9 | Mutation checks on the new break and routing code. |
| B1 | Browser: upload a workbook with a breaks sheet, run Current, replay shows the break. |
| G | Gates: `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`; in `frontend/`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`. |

Independent review by Kyoya is required (HIGH risk). Production behavior stays NOT TESTED until an
authorized release.

## 8. Open decisions

- **OD-1:** All new or changed screen texts (§5), en + tl.
- **OD-2:** Per-date file where a lane is closed by that date's schedule at its break time. Recommended:
  skip that break for that date and list it in the run's notes (no silent skip). Refusing would block every
  run whose staffing varies by date. Alternative: refuse the run naming the date, lane and break.

## 9. Out of scope

Replaying exact recorded arrivals instead of rates; breaks in the shared per-period run; Monte Carlo or
Results-check changes; report changes; a no-breaks toggle for Current.
