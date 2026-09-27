# Plan: Shared Queue Phase 5B-2, Sequential Rostering MILP

Spec: `docs/superpowers/specs/2026-09-26-shared-queue-sequential-rostering.md`.

1. Verify `3f49a43a`, the tree, the 5B-1 public interfaces (`validate_workforce_inputs`,
   `evaluate_roster`, and the input dataclasses), `staffing_from_capacity_result`, and
   `scipy.optimize.milp` in the local and container runtimes.
2. Add `backend/queueing_engine/services/shared_rostering.py`:
   - config validation and pattern generation, with the cap;
   - the exact maximum paid minutes, pay requirements, and certificates;
   - the MILP build, the solve, status mapping, and exact verification;
   - the output and the Phase 2 entry point.
3. Add `tests/test_shared_rostering.py`, all on labeled synthetic data:
   - an independent brute force, and pattern-set equality;
   - the 12 required areas;
   - seeded random brute-force comparisons;
   - the Phase 2 path and simulated solver terminations.
4. Add the module to the isolation list in `tests/test_shared_segments.py`.
5. Run the focused tests, the shared and separate suites, the full backend suite, `ruff check
   .`, and `mypy .` (excluding the gitignored `outputs/`). Run a fault-injection check on the
   formulation and the verification.
6. Update `handoff.md` and `memory.md`, review the exact file list, commit, and do not push.
   Stop after 5B-2.
