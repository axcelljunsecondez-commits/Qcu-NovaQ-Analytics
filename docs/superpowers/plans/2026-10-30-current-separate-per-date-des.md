# Plan — Current separate-lines DES on a per-date file (C-PD)

Spec: [2026-10-30-current-separate-per-date-des.md](../specs/2026-10-30-current-separate-per-date-des.md). Status: **IN PROGRESS (2026-11-02).** The owner chose Path A (OD-C1..C5 = a, i, i, i, i) and OD-C7 = (iii) now, (ii) next. Steps A0-A5 are implemented by Hayato and reviewed by Kyoya (PASS, uncommitted). A7 was measured: over the size cap, giving HTTP 413. Steps A7b (size refusal) and A7c (K-CPD-2 and test tightening) are next. A6 (frontend) and OD-C6 (wording) are open. The `mypy .` gate fails on a pre-existing error in `shared_continuous.py:447` (VERIFIED identical on HEAD); its handling is an owner decision before commit. No commit or push without the owner's approval. Never push `main`.

Base: `main` `3ee8fe2c`, worktree `confident-cori-664a54`. Backend steps do not depend on `feat/ulit-chart-redesign`. The frontend step (A6) must start from that branch after it merges, or be rebased onto it (spec §7.4).

## Step 0 — Done (2026-10-30)

- RED tests: `tests/test_current_separate_per_date.py`, 3 failing and 3 passing on `3ee8fe2c` (spec §2.1). Uncommitted.
- Reach check: Current MC and Current validation are not affected (spec §3).

## Path B — refuse (OD-C1 = b, or the interim step of "b then a")

B1. **Engine guard** (`backend/queueing_engine/simulation/simulation.py`, `_parallel_schedule`). Replace the `next(...)` lookup with a collection of all matching records. With more than one match, return the refusal string. Wording comes from the owner (OD-C6). Placeholder until then: "Current simulation of separate lines needs one record per segment and lane; this file has records from N dates for {segment}/{lane}." Count the dates from the matching labels. Today `_parallel_capability_error` turns the string into unsupported rows, so the API shape does not change.
B2. **Test** for the guard, called directly with two records for one pair. Keep the six C-PD tests: the RED ones pass through the refusal branch.
B3. **Frontend**: the run bar already lists the reasons of unsupported rows (handoff step 9). Check in the browser with SYNTHETIC data. Add en+tl strings only if a new key is needed (owner text).
B4. **Versioning** as decided in OD-C4. See A5; the same marker applies.
B5. Gates (below), mutants: restoring `next(...)` must fail B2 and the C-PD tests.

## Path A — each date as its own day (OD-C1 = a)

A1. **Engine guard** as in B1. It is kept under A as the second check.
A2. **Per-date runner** in `backend/api/workflow.py`, next to `run_des_current`, modelled on `_run_selected_plan_day_des`:
   - `per_date_continuous(setup)` decides the path. Otherwise today's single call is unchanged.
   - `labels` = distinct record `time` in stored order. `rows_by_label` from the stored records. Group with `per_date_days(setup, labels, rows_by_label)`. A `ValueError` gives HTTP 422 with its message (OD-C5 (i)), the same refusal style as `SelectedPlanError`.
   - Each date: `_simulate_parallel_segments_core(that date's records, setup, sim_hours, date_seed(seed, i), recorder, max_events)` with one shared `_TraceRecorder` (OD-C3 (i)). Tag each new event with `date`. The engine function needs an additive `date` argument passed to `recorder.record`, or a post-pass over the events the recorder added for that date. Choose the post-pass to keep the engine signature unchanged.
   - Merge: `results` and `segments` in date order. `total_hours` = sum of day horizons. `days` from each date's rows (arrivals, served, `waiting` and `in_service` at close, conservation, hours). `execution = "current_per_date_days"`.
   - Keep the `simulation.py` imports one way (api → services/engine). No import of `workflow` from the engine.
A3. **OD-C2 rule** in `_parallel_schedule`, only if the owner chooses (i) or (iii). Today a missing open-lane record is refused (line 697). (i): build a λ = 0 context for that lane and hour, active, with empty samples allowed only when λ = 0. A backlog customer is served from the samples of their own arrival period (`customer_process`, line 809), so an empty sample set at λ = 0 is never drawn. List the pair in `zero_arrival_lane_periods`. (iii): an inactive context, as for lanes the Setup closes. (ii): no change.
A4. **Tests**: the spec §10 list. Byte-identical regression for Representative day and single-date per-date: take a snapshot of `simulate_segments_with_trace` and the API result on `3ee8fe2c` before the change and compare after. Seeds per date. `days` totals equal the sum of the rows. OD-C2 and OD-C5 cases. Trace `date` on every event. Cap shared across dates.
A5. **Versioning (OD-C4 (i))**: `run_des_current` writes `params.current_des_basis = "per_date_days_v1"` for separate-lines runs. `_current_evidence_policy` sets `current_des_accounting = AccountingRequirement(VersionFamily.of("Current DES accounting", current={"per_date_days_v1"}), "current_des_basis", frozenset({"workflow_des_current"}))`. Update the docstring (it says the hook stays unset by design). Test that an old separate Current DES job is no longer Current and a shared-lines one is unchanged. Check how the page shows a non-current Current run ("Not run" or a rerun message) in the browser. For (ii) or (iii), re-plan this step.
A6. **Frontend** (after A1-A5 are verified; based on the chart-redesign branch): Current Key results and Replay get the date picker for per-date Current runs (`dayPeriods`, `DatePicker`, `date=`), the replay filters events by `date`, and the run basis says one continuous run per date. Owner wording (OD-C6) in en and tl. Vitest for the new branches. Browser check with SYNTHETIC two-date data.
A7. **Budget**: time and peak memory of one Current run on a SYNTHETIC file shaped like the owner's file (14 dates × 13 segments × 5 lanes), before and after. Render: NOT TESTED unless the owner authorises it.
A8. Gates and mutants (below). Update `handoff.md` and `memory.md` with the decision, the commits and the results.

## Gates (both paths)

```
python -m pytest tests/ -x --tb=short
ruff check .
mypy .
```

When the frontend changes, in `frontend/`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`.

## Stop conditions

- Any representative-day or single-date Current result changes: stop and report (spec §6.1).
- A gate fails and the cause is not understood: stop.
- OD-C2 not decided: A3 is blocked. A1, A2 (with today's refusal for a missing open lane) and A4 for the decided parts can go ahead.
