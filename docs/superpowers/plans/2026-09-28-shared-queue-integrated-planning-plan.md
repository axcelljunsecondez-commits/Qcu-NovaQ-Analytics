# Plan: Shared Queue Phase 5B-3, Integrated Planning MILP

Spec: `docs/superpowers/specs/2026-09-28-shared-queue-integrated-planning.md`.

1. Verify `99d94b4d`, the tree, the reused 5B-2, 5B-1, Phase 2, and Phase 1 interfaces, and the
   solver.
2. Investigate the 15-minute-grid scaling problem of the 5B-2 model on the synthetic NovaMart
   benchmark, without assuming its cause:
   - model size;
   - LP relaxation time;
   - MIP presolve time;
   - the root node;
   - incumbents.
   Change no constraint for runtime.
3. Obtain the product owner's capacity-semantics decision (made: every interval at the on-duty
   count).
4. Add `backend/queueing_engine/services/shared_integrated.py`:
   - the planning configuration and its validation;
   - the capacity evaluation through Phase 2's `evaluate_candidate`;
   - the independent roster evaluation;
   - the integrated model on top of 5B-2's `_build_model`;
   - certificates, the solve, status mapping, and exact verification;
   - the comparison with the sequential pipeline.
5. Add `tests/test_shared_integrated.py` on labeled synthetic data:
   - an independent brute force;
   - the 10 required verification points;
   - comparison logic;
   - seeded random instances;
   - simulated solver terminations.
   Add the module to the isolation list in `tests/test_shared_segments.py`.
6. Run the focused tests and fault injection on the formulation, the verification, and the
   comparison. Then benchmark integrated against sequential at grids 60, 30, and 15.
7. Run the shared and separate suites, the full backend suite, `ruff check .`, and `mypy .`
   (excluding the gitignored `outputs/`).
8. Update `handoff.md` and `memory.md`, review the exact file list, commit, and do not push.
   Stop after 5B-3.
