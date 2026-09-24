# Plan: Shared Queue Phase 1, Segment Foundation

Spec: `docs/superpowers/specs/2026-09-24-shared-queue-segment-foundation.md`.

1. Confirm the Phase 0 baseline: clean `main` at `1d3294cb`; backend 1033 passed,
   3 skipped, 1 xfailed.
2. Add `backend/queueing_engine/services/shared_segments.py`: clock parsing, the horizon,
   demand-period and staffing-segment types, validation, the timeline builder, the
   per-segment evaluation through `select_model`, and the strict aggregate-row reader.
   Do not export it from `services/__init__.py`, so no existing import path changes.
3. Add `tests/test_shared_segments.py`: independent Erlang references, unit identities,
   every validation rule, every segment outcome, and sub-hour inheritance.
4. Run the focused tests, then the full backend suite, `ruff check .`, and `mypy .`.
5. Commit only if everything passes and the diff touches only the new files and these two
   documents.
