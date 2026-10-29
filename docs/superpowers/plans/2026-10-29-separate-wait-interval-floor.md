# Plan: separate lines, the simulated wait interval stops at 0 (Part B) — 2026-10-29

Spec: `docs/superpowers/specs/2026-10-29-separate-wait-interval-floor.md`. Protected statistics change (AGENTS.md §5); owner approved the two-part fix 2026-10-29 (REPORTED). Worktree `clever-boyd-87ff32`, branch `claude/friendly-bell-4801f0`, base `3ee8fe2c`. Do not commit, do not push.

## Files

- `backend/queueing_engine/services/separate_optimization.py`: three call sites (`waiting_end`, `Wq`, `waiting_time`) and the `_summarize_metric` docstring.
- `tests/test_separate_wait_interval_floor.py`: new.
- `tests/test_separate_des_replications.py`: one assertion that pinned the plain `waiting_time` lower bound.
- The spec and this plan.

Not touched: API code, reports, frontend, engine version constants (OD-W1 DECIDED 2026-10-29: no version change, owner "Option 1, leave them as they are", REPORTED via the parent session), `handoff.md`, `memory.md` (updated when the owner approves a commit).

## Steps

1. Tests first (red):
   - `_summarize_metric` reference cases R1-R5 of the spec, with hand-computed literals.
   - Aggregator with a stubbed single-lane run (5 replications, `Wq` 0,0,0,0,0.1 h; `waiting` 0,0,0,0,2; utilization 0,0,0,0,0.5): `waiting_time`, `Wq`, `waiting_end` lower bounds are 0; their upper bound, mean, SD, SE, n equal the plain summary; `utilization` lower bound stays negative (scope check).
   - A case where the floor does not bind leaves the summary identical to the plain one.
   - API: a computed plan's `wait_ci` lower bound is ≥ 0 (`/workflow/comparison/separate`), using existing test fixtures.
   - Run them and see the floor tests fail on the current code.
2. Implement: add `floor=0.0` to the three call sites; widen the docstring to name waits.
3. Update the existing `waiting_time` lower-bound assertion in `tests/test_separate_des_replications.py` to `max(0, …)`, citing the spec.
4. Mutation check: remove `floor=0.0` from each call site in turn; at least one test must fail each time; restore.
5. Gates: `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`. No frontend files changed, so frontend gates are not run.
6. Report diff, test results, and OD-W1..W3 for the owner. No commit. (Done 2026-10-29; OD-W1 decided: no version change.)
