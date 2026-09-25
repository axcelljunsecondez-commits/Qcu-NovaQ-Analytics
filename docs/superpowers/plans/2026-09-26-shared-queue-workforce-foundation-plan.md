# Plan: Shared Queue Phase 5B-1, Workforce Foundation

Spec: `docs/superpowers/specs/2026-09-26-shared-queue-workforce-foundation.md`.

1. Verify `a244e5b9`, the tree, and the Phase 1 public interfaces (`OperatingHorizon`,
   `StaffingSegment`, `SharedSegmentError`, `format_clock`, `MINUTES_PER_DAY`).
2. Add `backend/queueing_engine/services/shared_workforce.py`: input dataclasses,
   malformed-input validation, roster violations, the hour definitions, the active-server
   steps, the register check, and coverage.
3. Add `tests/test_shared_workforce.py`: hand-computed synthetic fixtures, one test per
   violation code, malformed inputs, identities on generated rosters, and coverage.
4. Add the module to the isolation list in `tests/test_shared_segments.py`.
5. Run the focused tests, the shared and separate suites, the full backend suite, `ruff check
   .`, and `mypy .` (excluding the gitignored `outputs/`). Run a fault-injection check on the
   definitions.
6. Update `handoff.md` and `memory.md`, review the exact file list, commit, and do not push.
   Stop after 5B-1.
