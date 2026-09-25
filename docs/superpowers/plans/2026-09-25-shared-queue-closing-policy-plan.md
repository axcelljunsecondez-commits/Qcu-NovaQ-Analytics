# Plan: Shared Queue Phase 3A, Closing Policy and Day Cost

Spec: `docs/superpowers/specs/2026-09-25-shared-queue-closing-policy.md`.

1. Verify `9eaf5d4a` and the clean backend and test tree since it. Run the backend baseline.
2. In `backend/queueing_engine/simulation/shared_continuous_des.py`:
   - require `closing_policy` (DRAIN or HARD_CUTOFF, no default) in `simulate_prescribed`
     and `simulate_shared_day`;
   - add the closing step and the after-close loop, keeping events before closing unchanged;
   - report `closing` and `cost_quantities`, the new statuses, and the provenance text,
     including that server-hours are modeled capacity hours.
3. Add `backend/queueing_engine/services/shared_day_cost.py` with `DayCostRates` and
   `cost_shared_day`, with no monetary defaults.
4. Tests:
   - update `tests/test_shared_continuous_des.py`: pass a policy, run every Phase 3 exact
     case under both policies, and replace the UNRESOLVED horizon-end test;
   - add closing cases, identities, and cross-policy equivalence;
   - add `tests/test_shared_day_cost.py`;
   - add the new module to the isolation list in `tests/test_shared_segments.py`.
5. Run the focused tests, the separate-queue suites, the full backend suite, `ruff check .`,
   and `mypy .`.
6. Mark the Phase 3 spec's closing section as resolved by Phase 3A. Update `handoff.md` and
   `memory.md`.
7. Commit only the files above after every gate passes. Do not push. Stop before Phase 4.
