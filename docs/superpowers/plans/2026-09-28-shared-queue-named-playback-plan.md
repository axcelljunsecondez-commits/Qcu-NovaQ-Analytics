# Plan: Phase 5B-4.5, Named-Employee DES Playback

Spec: `docs/superpowers/specs/2026-09-28-shared-queue-named-playback.md`.
Branch `feat/shared-queue-segments`, base `fd67bbf2` (parent `a67ab51c`). Local commit only; no push,
merge, or deploy.

## Baseline (before any edit)

1. Verify HEAD `fd67bbf2`, its parent, the branch, and a clean tree (only the untracked `.claude/`).
2. Read `AGENTS.md`, `memory.md`, `handoff.md`, the 5B-4.1 to 5B-4.4 specs, the named engine
   (`shared_named_des.py`), the state machine (`shared_employee_states.py`), the replications
   module (`shared_named_replications.py`), and the Phase 4 playback (`shared_playback.py`).
3. Re-run the 5B-4.4, 5B-4.3, 5B-4.2, and 5B-4.0 pin tests (expected 183 passed).
4. Probe the actual engine output (scratch): the customer trace types and fields, the transition
   tuples, and the order of DRAIN releases at one instant. Derive the vocabulary from the code, not
   from earlier reports.

## Step 1: engine trace changes (named DES v3)

1. Record `employee_transitions_before` on every customer trace event, so the customer trace and
   the employee transitions interleave exactly as recorded.
2. Record simultaneous DRAIN releases in employee_id order (approved trace-order rule); X1 still
   decides who stays.
3. Bump `NAMED_ENGINE_VERSION` to v3 and update the one test that pins the version string.
4. Gate: a scratch comparison with the `fd67bbf2` engine on many seeded runs shows identical
   customers, counts, queue, staffing, and employee intervals, shifts, and breaks; only the release
   order within one instant and the new key differ. The 5B-4.0 pin passes without regenerating its
   fixture.

## Step 2: run-input provenance

1. Add `named_inputs_snapshot`, `named_inputs_digest` (SHA-256 of canonical sorted JSON, floats as
   `float.hex()`), and `provenance.inputs_sha256`; bump the replications method version to v2.
2. Map every simulation input of `simulate_named_replication` to the digest or to a separately
   recorded field (seed, versions), and pin that mapping with a signature test.

## Step 3: playback module

1. New `simulation/shared_named_playback.py`: the accepted vocabulary, the merge by
   `employee_transitions_before`, an independent replay with the required invariants, the
   reconciliation with the regenerated result and the stored row (each quantity exact, within the
   Phase 4 playback tolerance, or not applicable), the regeneration from a run's provenance, and
   structured failures (`NamedPlaybackError`) that never repair a trace.
2. Register the module in the isolation list.
3. New `tests/test_shared_named_playback.py`: hand-derived event sequences, prescribed days reaching
   every vocabulary entry, seeded acceptance, the digest, the interleaving field, regeneration and
   refusal, zero random numbers, and corrupted traces (including ones with plausible final counts).

## Step 4: verification

1. Fault injection on a scratch copy of `backend/` and `tests/` (the working tree is untouched).
   Classify survivors as coverage gap, equivalent, or UNKNOWN; add tests for gaps, never weaken
   one, and re-run on the final text. Remove replay checks that are provably unreachable instead of
   counting them as coverage.
2. Gates on the final tree: the focused playback, 5B-4.4, 5B-4.3, 5B-4.2, and pin tests; all
   shared-queue tests; the Separate Queue regressions; the full backend suite
   (`python -m pytest tests/ -x --tb=short`); ruff; and `mypy . --exclude '^outputs/'`.
3. Docs: this plan, the spec, the 5B-4.3, 5B-4.4, and policy specs (amendments), `memory.md`, and
   `handoff.md`.
