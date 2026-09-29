# Plan: Phase 5B-4.6, Named-Employee Attribution Reporting

Spec: `docs/superpowers/specs/2026-09-29-shared-queue-named-attribution.md` (APPROVED SPECIFICATION,
decisions D1-D8, 2026-09-29). Branch `feat/shared-queue-segments`, base `5a9738e2` (parent
`086075f7`). One local commit only; no push, merge, or deploy.

## Baseline (before any edit)

1. Verify the branch, HEAD `5a9738e2` and its parent, and the tree. Only the untracked spec and
   `.claude/launch.json` may be present.
2. Re-read the approved spec, and confirm D1-D8 are recorded as approved.
3. Re-run the named-queue suites: the state machine, named DES, named replications, named playback,
   the 5B-4.0 pin, and `test_shared_segments.py`.

## Step 1: attribution module

1. New `backend/queueing_engine/simulation/shared_named_attribution.py`:
   - `ATTRIBUTION_VERSION = "novaq-shared-named-attribution-v1"`;
   - `build_named_attribution(result, employees)`, a pure read of `result["employee_timeline"]` and the
     input employees;
   - `NamedAttributionError`, carrying `{check, message, evidence}`;
   - `CHECKS`, `DEFINITIONS`, `UNDETERMINED`, and `RECONCILIATION`;
   - `derived_duration(a, b, field=...)`, the D7 rule.
2. Check order: `record_structure`, `source_versions`, `employee_identity`, `shift_identity`,
   `interval_geometry`, `shift_reconciliation`, `closing_partition`, `base_state_partition`,
   `break_reconciliation`, `employee_reconciliation`, `finite_nonnegative`.
   - Membership values are tested as strings or finite reals before hashing.
   - Timing comparisons are exact.
   - The house tolerance (`shared_named_playback.TOLERANCE`, imported, not copied) is used only for
     reconciliation checks and the D7 rule.
3. Register the module in `SHARED_QUEUE_ENHANCEMENT_MODULES` (`tests/test_shared_segments.py`).

## Step 2: tests (`tests/test_shared_named_attribution.py`)

1. Hand cases H1-H8 and the section 7 situations. Expected values are recomputed by hand from each
   scenario's definition; they are not copied from engine output.
2. Seeded reconciliation: 10 scenarios × 2 policies × 25 replications, including the unchanged 5B-4.4
   `named_replication_row`.
3. Malformed inputs: each is a deep-copy edit of an engine result. Each fails its named check, never
   with `TypeError`, and nothing is repaired.
4. The D7 rule on synthetic operands: positive, zero, tiny negative, the exact tolerance boundary,
   beyond the boundary, and tiny positive. Also: exact order violations that D7 does not forgive.
5. Purity, units, isolation, and absence of `paid` and money fields.

## Step 3: verification

1. Fault injection on a scratch copy of the new module, with the working tree untouched.
   - Survivors are classified as a test gap, equivalent, or unreachable.
   - Gaps get tests. Tests are never weakened.
   - A provably unreachable check is removed or justified.
2. Gates on the final tree, narrow to broad:
   - the attribution tests;
   - the state machine, named DES, named replications, named playback, pin, and segments suites;
   - all `tests/test_shared_*.py`;
   - the Separate Queue files listed in the policy spec;
   - the full backend suite (`python -m pytest tests/ -x --tb=short`);
   - `ruff check .`, `mypy . --exclude '^outputs/'`, and `git diff --check`.
3. Protected paths compared against `5a9738e2`.

## Step 4: documentation and commit

1. The spec's status and implementation record.
2. The policy spec: the stale "P2 threshold (if chosen)" entry and the P8 mapping (spec section 10).
3. The named-DES spec's "next steps" line, `handoff.md`, and `memory.md`.
4. Review the full diff, then make one local commit.
