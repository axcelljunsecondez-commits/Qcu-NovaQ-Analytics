# Plan — Compact stored per-date Current result (C-PD-C)

Spec: [2026-11-02-current-per-date-compact-result.md](../specs/2026-11-02-current-per-date-compact-result.md).

Status: **APPROVED 2026-11-02, all recommended options. IN PROGRESS.**
- Nothing is committed or pushed without the owner's approval.
- Never push `main`: pushing `main` is a production release.
- Workflow: Vongola V2. Chrome investigates, Hayato builds, Kyoya reviews, the owner decides.

## Step 0: integration (needs OD-C8)

1. Create a new branch from `origin/main` (`4dd99465`).
2. Bring in `b484d8f2`. Bring in `554d978d` only if it does not duplicate `f23bfbd3`; the hunk is identical, so expect it to drop out.
3. Resolve `run_des_current` against `_validate_current_des_date_scope`.
4. Under OD-C8 (i):
   - rewrite or retire `tests/test_current_des_per_date_scope.py` to match the approved behaviour;
   - record the change in `docs/superpowers/specs/2026-11-01-chart-live-integration.md`.
5. All gates must pass before Step 1 starts.

## Step 1: snapshot

Before any code edit, capture byte snapshots on the integrated base for these runs, and store them in `tests/fixtures/current_per_date_compact_snapshot_<base>.json`:
- a one-date per-date run;
- Representative day;
- shared lines;
- aggregate separate data;
- the legacy `/simulation/des*` endpoints.

## Step 2: engine, additive (`backend/queueing_engine/simulation/simulation.py`)

- Add a canonical-digest helper.
- Add `simulate_parallel_days_compact(days, setup, sim_hours, seeds, max_events)`. It calls the unchanged core and uses one recorder per date, only to compute digests. It returns the shape in spec §6.4.
- Existing functions do not change.

## Step 3: workflow (`backend/api/workflow.py`)

- In `run_des_current`, runs with two or more dates use the compact path.
- Record `seed_used`.
- Set the marker to v2, and set the policy to current = {v2}, historical = {v1}.
- Apply the 413 check after compaction.
- Add the day-detail GET route, reusing `_current_evidence` and `_evidence_is_current`.
- Detail strings stay placeholders until OD-C6 (W1 to W3).

## Step 4: tests

- Add `tests/test_current_per_date_compact.py`.
- Update `tests/test_current_separate_per_date.py` for the compact shape.
- Cover the list in spec §10, and run the mutants.

## Step 5: measurement

- Measure the SYNTHETIC 14 × 13 × 5 case, plus a sweep for the largest number of dates (25 and 37 are expected).
- Record local time and peak memory.
- Render: NOT TESTED unless the owner authorizes a check.

## Step 6: A6 frontend (later)

Start from `origin/main`, after the owner writes the wording.

Files:
- `api/workflow.ts`, `api/types.ts`
- `simulationContext.ts`, `KeyResultsView.tsx`, `ReplayView.tsx`, `RunBar.tsx`
- the en and tl locales

Behaviour:
- Fetch each date's detail on demand and cache it by (jobId, date).
- Choose the display by `execution`.
- Show the DatePicker.
- Key the replay by date (K-CPD-4).
- Offer a CSV download per date.

Checks: Vitest, and a browser check with SYNTHETIC data.

## Files Hayato may write (Steps 0 to 4)

- `backend/queueing_engine/simulation/simulation.py`
- `backend/api/workflow.py`
- `tests/test_current_per_date_compact.py` (new)
- `tests/test_current_separate_per_date.py`
- the new snapshot fixture
- under OD-C8 (i) only: `tests/test_current_des_per_date_scope.py` and the note in the 11-01 spec

`evidence_status.py` is not needed for C-rows.

## Gates

- `python -m pytest tests/ -x --tb=short`
- `python -m ruff check .`
- `python -m mypy .`
- In A6, also: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`

## Stop conditions

Stop and report if any of these happens:
- OD-C8 is not decided;
- any snapshot differs;
- any date's day detail differs from its slice of the full run;
- the 14-date compact result is over 524,288 B;
- a gate fails and the cause is not known;
- a consumer not listed in spec §3 is found;
- reproducibility fails on the deployed Python and Alpine image (checked only if the owner authorizes a runtime check).
