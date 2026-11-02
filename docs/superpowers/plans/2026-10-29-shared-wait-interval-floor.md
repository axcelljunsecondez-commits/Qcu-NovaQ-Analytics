# Plan: shared lines, simulated wait intervals stop at 0 (OD-W3 / N2), 2026-10-29

Spec: `docs/superpowers/specs/2026-10-29-shared-wait-interval-floor.md`. Protected statistics change (AGENTS.md §5).

Owner approval, as relayed by the parent session: "N1 and N2 apply your recommendation" (REPORTED).

Worktree `clever-boyd-87ff32`, branch `claude/friendly-bell-4801f0`, base `3ee8fe2c`. This change is kept apart from the separate-lines change: no file in common. Do not commit, do not push.

## Files

- `backend/queueing_engine/simulation/shared_replications.py`:
  - `summarize_metric(values, floor=None)`;
  - the floored keys in `aggregate_replications` and `_cost_summary`;
  - `CONTINUOUS_INTERVAL_METHOD` text.
- `backend/queueing_engine/simulation/shared_named_replications.py`: path-aware `_summaries`, plus the floored keys and the mean of means.
- `tests/test_shared_wait_interval_floor.py`: new.
- `frontend/src/test/fixtures/sharedNamed.json`: regenerated, but only if the diff is limited to the spec's changes.
- The spec and this plan.

Not touched:
- frontend copy and translations (OD-S3);
- `METHOD_VERSION` and the engine versions (OD-S1);
- the separate-lines files;
- `handoff.md` and `memory.md`.

## Steps

1. Tests first (red):
   - `summarize_metric` cases S1-S5 with hand-computed literals.
   - Synthetic aggregate rows check that exactly the §3 keys are floored. Rows have mostly zero waits and one positive; `server_hours_above_schedule_in_horizon` has a negative mean.
   - The same check for the named aggregator.
   - A real anonymous run and a real named run, comparing each floored key with max(0, plain lower) and leaving the rest equal to the plain summary.
   - Run them and see them fail.
2. Implement:
   - add the `floor` argument (default None keeps every other caller unchanged);
   - floor the §3 keys;
   - make `_summaries` pass a key path and floor the named §3 paths;
   - add the method-text sentence.
3. Run the existing shared tests (`test_shared_replications.py`, `test_shared_named_replications.py`, and any test that reads shared API summaries). Update a pinned value only where §3 defines the change; report each one.
4. Regenerate the fixture into a scratch copy and diff it against the committed fixture. Replace the committed fixture only if every difference is a floored lower bound or the interval-method text.
5. Mutation check: remove each floor group in turn; at least one test must fail each time.
6. Gates:
   - `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`;
   - frontend gates in `frontend/` (`npm test`, `npm run typecheck`, `npm run lint`, `npm run build`) if the fixture changed.
7. Report the diff, the results and OD-S1..S3. No commit.
