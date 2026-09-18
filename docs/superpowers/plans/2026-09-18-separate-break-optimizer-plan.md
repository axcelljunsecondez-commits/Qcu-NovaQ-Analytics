# Separate Queue Break Optimizer — Implementation Plan (2026-09-18)

Spec: `docs/superpowers/specs/2026-09-18-separate-break-optimizer.md`
(approved with option (b): no recorded-wait data warning).

Test-first: every task writes its failing tests, then the code, then runs the
task's tests plus the protected tests listed below.

## Files

| File | Change |
|---|---|
| `backend/queueing_engine/services/break_optimization.py` | **New.** Pure placement core, Setup/records → slot inputs, DES before/after comparison. |
| `backend/api/workflow.py` | Add `SeparateBreakOptimizeRequest` and `POST /{analysis_id}/workflow/optimize/separate/breaks`. No existing route changes. |
| `frontend/src/api/optimization.ts` | Add response/request types and `optimizeSeparateBreaks()`. |
| `frontend/src/pages/OptimizePage.tsx` | Add an inline `BreakOptimizerCard` (separate queues) and the shared-queue note. Inline components follow the existing `SeparateScheduleCard` pattern (`OptimizePage.tsx:170`). |
| `frontend/src/pages/OptimizePage.test.tsx` | Add tests for the card and the note. |
| `tests/test_break_optimization.py` | **New.** Unit tests for the core. |
| `tests/test_break_optimize_api.py` | **New.** API tests. |
| `frontend/public/locales/en/translation.json`, `frontend/public/locales/tl/translation.json` | New `optimize.breaks_*` keys. **Outside the listed Scope, needs your approval** (see below). |

Untouched: `optimization.py` (shared), `separate_optimization.py`, DES and
break lifecycle, ingestion/pooling, Decision, reports, migrations,
`analysis_schemas.py`.

## Module: `break_optimization.py`

- **`slot_rho(slots, shifts, breaks) -> list[dict]`**
  - Returns the working count and ρ for each slot.
  - The working count is the number of cashiers on shift minus each
    cashier's fraction of the slot on break.
  - `None` when nobody is working and λ > 0; 0 when λ = 0.
- **`place_breaks(slots, shifts, breaks, queue_order, *, target=0.85,
  max_shift_minutes=120, edge_minutes=60, step_minutes=15) -> dict`**
  - Pure function. Implements spec §Placement exactly: breaks are placed one
    at a time onto an empty schedule, longest first, then queue order, then
    current start.
  - Scores each candidate by peak ρ (`None` counts as infinity).
  - Ties go to the smallest |shift|, then the earlier start.
  - Enforces the shift edges, the ±window and per-cashier order/no overlap.
  - Raises `ValueError` naming any break with no feasible start.
  - Returns:
    - status (`improved` or `no_improvement`)
    - proposed breaks, moves and per-slot before/after
    - peak and above-target counts, `all_below_target`
    - staffing gaps
  - Slots are `{"start": min, "end": min, "lambda": /h, "mu": /h}`. Shifts
    are `{queue_id: (start_min, end_min)}`. Breaks use the persisted Setup
    shape.
- **`slot_inputs_from_setup(setup, records) -> (slots, shifts)`**
  - Requires `separate_queues`, `representative_day`, segments and breaks.
    Each missing requirement raises its exact spec error message.
  - Uses a 15-minute grid from `des_day_start_minutes` and rejects segment
    bounds that are off the grid.
  - λ = sum of the segment's record `lambda`, via `index_period_queues`.
  - μ = `count / sum` of the pooled `service_samples_hours`.
  - Shifts come from the segments' `active_queue_ids` (every queue under
    fixed staffing). A split shift is rejected.
- **`compare_break_schedules_des(setup, records, current, proposed, *,
  replications, base_seed, max_events) -> dict`**
  - Builds one window per segment from Setup lanes and records, using
    `_segment_window`, `index_period_queues` and `des_day_start_minutes`.
  - Breaks come from `resolve_des_breaks` for each schedule.
  - Runs `run_routing_day_des` for each seed in `replication_seeds`, with the
    same seeds for both schedules.
  - Summarizes the served-weighted mean wait (minutes), max queue,
    admitted/served, conservation and per-period mean wait.
  - The comparison uses simulated values only.

## Endpoint

`POST /analyses/{id}/workflow/optimize/separate/breaks`, with rate limit
`compute`.

- **Request:** `dataset_id?`, `target_rho` (in (0, 1], default 0.85),
  `max_shift_minutes` (0–240, multiple of 15, default 120), `des.replications`
  (1–20, default 5), `des.base_seed` (int, default 42).
- **Flow:**
  - Shared structure → 422 "Break optimization is available for separate
    queues."
  - The dataset is resolved the same way as `run_separate_optimize`
    (`workflow.py:986-992`).
  - Then: slot inputs → `place_breaks` → DES comparison.
  - `ValueError` → 422 with the message.
- **Response:** the spec §API shape. Nothing is persisted and the Setup is
  never written.

## Tests

**`tests/test_break_optimization.py`**

1. `test_reference_avg15min_reproduces_prototype`
   - The 52 `Avg 15Min` rows are embedded as `(arrivals_14d,
     total_service_min)` integers, with λ = a·4/14 and μ = 60·a/svc. These
     reproduce the sheet's `Lambda / hr` and `Mu / hr` columns, so nothing
     depends on the Downloads path.
   - Asserts exactly the 5 moves, peak 1.3262 → 0.7202 (to 4 decimals), and
     above-target slots 5 → 0.
2. `test_proposed_breaks_respect_rules`: same cashier and length, 15-minute
   step, within ±120 minutes, inside the shift and not in the first or last
   60 minutes, order preserved, no overlap. Runs on the reference and on a
   small synthetic case.
3. `test_max_shift_window_is_configurable` (`max_shift_minutes=0` → no moves,
   `no_improvement`).
4. `test_tie_prefers_nearest_then_earlier`.
5. `test_no_improvement_keeps_current_schedule`.
6. `test_unplaceable_break_raises_named_error`.
7. `test_staffing_gaps_reported_when_no_move_can_fix`, covering both ρ ≥
   target with nobody on break and λ > 0 with nobody on shift.
8. `test_partial_slot_break_counts_fractional_working`.
9. `test_slot_inputs_pool_hourly_records`: λ is summed and μ is `count/sum`,
   using records from `normalize_analysis_input` with `representative_day`.
10. `test_slot_inputs_reject_per_date_off_grid_split_shift_no_breaks`, with
    the exact messages.

**`tests/test_break_optimize_api.py`**

1. `test_break_optimize_returns_schedules_rho_and_des`: a representative-day
   analysis built from synthetic events. Asserts the response keys, before
   and after ρ per slot, and DES summaries for both schedules.
2. `test_break_optimize_runs_existing_day_des_with_same_seeds`: a spy on
   `run_routing_day_des` records the seeds and breaks. The current and
   proposed schedules each run once per seed, with identical seeds.
3. `test_break_optimize_does_not_change_setup`.
4. `test_break_optimize_rejects_shared_queue` (exact note text).
5. `test_break_optimize_rejects_per_date_and_missing_breaks`.
6. `test_break_optimize_request_bounds` (target, window multiple of 15,
   replications).
7. `test_break_optimize_requires_auth`.

**`frontend/src/pages/OptimizePage.test.tsx`**

1. Shared analysis: the break card is absent and the note "Break optimization
   is available for separate queues." is shown.
2. Separate analysis: the card renders. Run calls `optimizeSeparateBreaks`
   (mocked). The page shows the before/after break table, the changed-slot ρ
   rows only, staffing gaps, and the DES summary with the simulation-only
   note.

**Protected (run after every backend task):**
- `tests/test_separate_optimization.py::test_shared_optimizer_outputs_unchanged`
- `tests/test_separate_day_des.py`
- `tests/test_optimize_separate_api.py`
- `tests/test_representative_day.py`
- `tests/test_queue_breaks.py`

## Order

1. Core placement: tests 1–8, then `slot_rho` and `place_breaks`.
2. Setup → slots: tests 9–10, then `slot_inputs_from_setup`.
3. DES comparison: covered by API test 2 and a unit smoke test inside it,
   then `compare_break_schedules_des`.
4. Endpoint: API tests 1–7, then the request model and route.
5. Frontend: the client, `OptimizePage` tests, the card and note, and the
   locale keys (after approval).
6. In-app NovaMart check, not committed: a scratch script normalizes the
   Downloads events as a representative day with the NovaMart Setup and
   calls the endpoint's core. The in-app moves and ρ are reported as
   computed, and may differ from the 15-minute reference as the spec states.
7. Gates: `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`,
   and in `frontend/`: `npm test`, `npm run typecheck`, `npm run lint`,
   `npm run build`.
   - `-x` stops at the known
     `test_parallel_des_long_stable_case_matches_pollaczek_khinchine`
     failure, so the suite is run again with that one test deselected and
     both outputs are quoted.

## Needs approval

- **Locale files.** AGENTS.md requires new strings in both
  `frontend/public/locales/en/translation.json` and `.../tl/translation.json`.
  These files are outside the listed Scope. Without approval, the plan would
  have to hard-code English strings, which breaks the i18n rule.
