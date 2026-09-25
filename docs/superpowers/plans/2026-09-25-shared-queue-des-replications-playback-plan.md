# Plan: Shared Queue Phase 4, DES Replications and Event Playback

Spec: `docs/superpowers/specs/2026-09-25-shared-queue-des-replications-playback.md`.

1. Re-verify `d7b8eff1`, its parent, the tree, the concurrent worktrees, and the existing
   Monte Carlo, interval, threshold, and limit conventions. Record an engine output digest.
2. Engine: move the random draws of `simulate_shared_day` into a helper, and add
   `simulate_shared_replication(seed_sequence=...)`. Confirm the digest is unchanged.
3. Add `simulation/shared_replications.py`: validation, the per-replication row, cost per
   replication, criteria, and aggregation.
4. Add `tests/test_shared_replications.py`: independent recomputations, scipy reference
   intervals, Erlang C, seeds and streams, cost, and criteria.
5. Add `simulation/shared_playback.py`: regeneration, the replay check, derived timelines,
   and summary equality.
6. Add `tests/test_shared_playback.py`: consistency and continuity on many seeds and both
   policies, plus refusal of mismatched or invalid inputs.
7. Add both modules to the isolation test in `tests/test_shared_segments.py`.
8. Run fault injection, the focused suites, the separate-queue suites, the full backend
   suite, ruff, and mypy.
9. Update `handoff.md` and `memory.md`. Review the exact file inventory, commit, and do not
   push. Stop after Phase 4.
