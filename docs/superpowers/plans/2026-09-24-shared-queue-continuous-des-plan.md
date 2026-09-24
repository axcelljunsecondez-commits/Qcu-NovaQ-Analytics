# Plan: Shared Queue Phase 3, Continuous Shared-Queue DES

Spec: `docs/superpowers/specs/2026-09-24-shared-queue-continuous-des.md`.

1. Verify `b616e3ae`, `ad8ed236`, and `b212d7ee` and their tests. Re-check the legacy DES,
   the recorder schema, and the separate-queue closing semantics.
2. State the tolerance policy in the Phase 2 provenance (no computed value changes), with a
   test pinning the optimizer's limit tolerance to `utilization.THRESHOLD_TOLERANCE`.
3. Add `backend/queueing_engine/simulation/shared_continuous_des.py`:
   - a core engine driven by prescribed (arrival time, unit work) pairs;
   - a seeded entry that generates arrivals and work from two numpy `SeedSequence` streams;
   - a helper that turns a complete Phase 2 plan into staffing segments.
   Do not edit `simulation/__init__.py` or `simulation.py`.
4. Add `tests/test_shared_continuous_des.py`: exact deterministic cases, sample-path
   identities, conservation and identity, statistical benchmarks, and reproducibility.
   Extend the Phase 1 isolation test to the new module.
5. Run the focused tests, the full backend suite, `ruff check .`, and `mypy .`.
6. Commit only if everything passes and the diff touches only the new files, the Phase 2
   provenance text and its test, the isolation test, these documents, and `handoff.md`.
   Do not push.
