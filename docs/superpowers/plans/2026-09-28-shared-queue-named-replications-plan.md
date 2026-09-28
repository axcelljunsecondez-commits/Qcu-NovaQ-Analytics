# Plan: Phase 5B-4.4, Seeded Named-Employee DES Replications

Spec: `docs/superpowers/specs/2026-09-28-shared-queue-named-replications.md`.
Branch `feat/shared-queue-segments`, base `a67ab51c` (parent `dfa8fe75`). Local commit only; no push,
merge, or deploy.

## Baseline (before any edit)

1. Verify HEAD `a67ab51c`, its parent, the branch, and a clean tree (only the untracked `.claude/`).
2. Read `AGENTS.md`, `memory.md`, `handoff.md`, the 5B-4.1 to 5B-4.3 specs, the anonymous engine's
   `_draw_arrivals`, and the Phase 4 seed handling (`shared_replications.run_shared_replications`,
   `SEED_SCHEME`).
3. Re-run the named-DES, state-machine, and 5B-4.0 pin tests (expected 106 passed).
4. Reconfirm the numpy pins (`requirements.txt`, `requirements-lock.txt`,
   `requirements-production.lock`), the runtime numpy version, and what CI installs.
5. Record a SHA-256 digest of the anonymous engine's seeded outputs (scratch script) for the X5
   no-change check.

## Step 1: freeze the approved rules (engine and state machine)

1. State machine: a SERVING_BREAK_DUE completion at closing, with the employee's
   `CancelPendingBreaks` at that instant, goes to AVAILABLE with no break started (rule 1). Version
   v3.
2. Named DES: issue CancelPendingBreaks and Release for that employee (rule 1); issue
   EndBreakAtClosing to every employee on a break before closing (rule 2); compute gaps only
   inside [0, closing) and always report `after_closing` (rule 5); update the definitions, P7 text,
   and `UNDETERMINED`; version v2.
3. Tests:
   - replace the "undetermined" test with the rule 1 test;
   - change the two expectations the rules change;
   - add the rule 2 and rule 5 tests and a machine-level rule 1 test;
   - extend `check_named` (rule 5 on every step and window, the break rules on every run, the
     employee checker on inexact runs);
   - give `check_invariants` an `exact` flag and the approved truncation bound.
4. Gate: the named-DES, state-machine, and pin tests pass.

## Step 2: X5

1. Add `shared_continuous_des.draw_arrivals`, a validated call to `_draw_arrivals`. Change nothing
   else in the module.
2. Gate: the anonymous digest is unchanged, and the 5B-4.0 pin passes without regenerating the
   fixture.

## Step 3: named replications

1. New `simulation/shared_named_replications.py`: `replication_seed_sequence`,
   `simulate_named_replication`, `named_replication_row`, `aggregate_named_replications`, and
   `run_named_replications`. The Phase 4 seed scheme and `summarize_metric` are reused.
2. Register the module in the isolation list.
3. New `tests/test_shared_named_replications.py` covering the 12 required verification points and
   the 14 required cases, with an independent recomputation of the draws and an independent row
   checker. No seeded golden values.

## Step 4: verification

1. Fault injection on a scratch copy of `backend/` and `tests/` (the working tree is untouched). Add
   tests for survivors, never weaken one, and re-run on the final text.
2. Gates: the focused 5B-4.4, 5B-4.3, and 5B-4.2 tests and the pin; the shared-queue and Separate
   Queue regressions; the full backend suite (`python -m pytest tests/ -x --tb=short`); ruff; and
   `mypy . --exclude '^outputs/'`.
3. Docs: this spec and plan; amendments to the 5B-4.3 spec, the state-machine spec, and the policy
   spec; `memory.md`; `handoff.md`.
4. Inspect the diff and the file list, then commit locally. Stop after 5B-4.4.
