# Plan: Shared Queue Phase 2, Dynamic Capacity Optimization

Spec: `docs/superpowers/specs/2026-09-24-shared-queue-capacity-optimization.md`.

1. Verify `b616e3ae` and the Phase 1 tests. Review the reference-case wording and the
   zero-demand and zero-capacity semantics, and fix any confirmed Phase 1 defect in its own
   commit first. (Done in `ad8ed236`: disclosure only, no value changed.)
2. Add `backend/queueing_engine/services/shared_capacity.py`: `CapacityConfig` validation,
   the per-candidate evaluation through the Phase 1 `evaluate_segment`, feasibility rules,
   duration-weighted costs, tolerant tie-breaking, current versus selected totals, and
   provenance.
3. Add `tests/test_shared_capacity.py` with the independent checks listed in the spec.
   Update the Phase 1 isolation test so it allows only the new shared-queue modules to
   import the foundation; the legacy code must still import neither.
4. Run the focused tests, the full backend suite, `ruff check .`, and `mypy .`.
5. Commit only if everything passes and the diff touches only the new files, the Phase 1
   isolation test, and these documents plus `handoff.md`. Do not push.
