# Plan: Phase 5B-5, Named Workforce Costing

Spec: `docs/superpowers/specs/2026-09-30-shared-queue-named-workforce-cost.md` (APPROVED SPECIFICATION,
decisions C1-C16, 2026-09-30; completion boundary in section 17). Branch `feat/shared-queue-segments`,
base `40ee8dbe` (parent `b0040508`). One local commit only; no push, merge, or deploy.

This plan adds no costing policy. Every rule below is the spec's; where the spec names a section,
the implementation follows that section.

## Baseline (before any edit)

1. Verify the branch, HEAD `40ee8dbe`, the staged, unstaged, and untracked state, and that no merge,
   rebase, or cherry-pick is in progress. Only the untracked spec and `.claude/launch.json` may be
   present. Verify that no other session writes to the checkout.
2. Re-check the playback integration: playback v4, `TOLERANCE` value, type, and module, attribution's
   import of the same object, `derived_duration`, and attribution v1. Run the focused suites.
3. Record the dated implementation-precondition corrections in the spec (section 14.1).

## Step 1: cost module

1. New `backend/queueing_engine/services/shared_named_cost.py` (C16, section 10):
   - `NAMED_COST_VERSION = "novaq-shared-named-cost-v1"`;
   - `NamedCostRates(waiting_rate, unserved_customer_rate)`, frozen, no defaults;
   - `cost_named_workforce(result, employees, rates)`;
   - `NamedCostError`, carrying `{check, message, evidence}`;
   - `ZERO_QUANTITY` and `HOURS_UNDETERMINED`; `COSTED`, `RATE_MISSING`, and `NOT_APPLICABLE` are
     imported from `shared_day_cost`, which is not changed;
   - `CHECKS`, `DEFINITIONS`, `RECONCILIATION`, and `UNDETERMINED`.
2. Pipeline (C16):
   1. `build_named_attribution(result, employees)`; its error propagates unchanged.
   2. `rate_structure`, `pay_structure`, `result_structure`.
   3. Paid-time classification of the same validated `employee_timeline.intervals` (C3, C4, C7,
      section 4), with `break_mapping` (exact containment, one break, exact tiling; `paid` read
      from the engine break record).
   4. The chronological pay walk per employee (C5, C6, C14, C15, section 5): `F`, `G`, and `T`
      pieces, `C_k` as the `fsum` of every earlier paid length, exact comparisons, D7 only for
      `R_k` and the crossing's `T` piece (through `derived_duration`).
   5. Attribution quantities are read, never recomputed (section 10.1). The walk only reconciles
      with them: `paid_partition` and `overtime_partition`.
   6. `unserved_consistency` (section 7, exact) and `waiting_consistency`.
   7. Components and totals (C8, C9, C10b, C13, section 3 and 9); `finite_nonnegative` and
      `cost_arithmetic` on the output.
3. No verdict or acceptance field (C11); one run only (C12); no Phase 3A capacity term (C2).
4. Register the module in `SHARED_QUEUE_ENHANCEMENT_MODULES` (`tests/test_shared_segments.py`).

## Step 2: tests (`tests/test_shared_named_cost.py`)

1. Hand cases HC-A to HC-W3 (section 12), each on the named engine through the independent 5B-4.3
   checker. Expected values are recomputed by hand from the scenario definitions; the derivation is
   in the comments. The explicit regression for earlier flagged overtime consuming the threshold
   before later unflagged time in a split shift is HC-C.
2. The status vocabulary, a supplied zero rate, the exact zero test (a tiny positive quantity),
   the C10b asymmetry (HARD_CUTOFF zero unserved is `ZERO_QUANTITY`; DRAIN zero unserved is
   `NOT_APPLICABLE`), and missing values of every kind.
3. Paid and unpaid break variants produce identical engine timelines; only the pay differs.
4. Seeded identities on the 10 named scenarios x 2 policies x 25 replications, reconciled with
   attribution.
5. Rule-level tests of the pay walk on synthetic intervals, labeled as such, for branches no engine
   lifecycle reaches (section 15, item 4) and for float-length slices.
6. Malformed inputs: rates, pay, break `paid`, break mapping, counts, reasons, customer rows,
   `at_close`, and queue. Each fails its named check and nothing is repaired.
7. Purity, determinism, no random numbers, no shared mutable output, units, provenance, and
   isolation.

## Step 3: verification

1. Fault injection on a scratch copy of the new module, with the working tree untouched. Every
   mutant is classified: killed, reachable survivor (test gap), implementation defect, equivalent,
   input-unreachable, timeout, or harness failure. Gaps get tests; tests are never weakened.
2. Gates on the final tree, narrow to broad:
   - the new cost tests;
   - attribution, state machine, named DES, named replications, named playback, and segments;
   - all `tests/test_shared_*.py`;
   - the 20 Separate Queue files (`ls tests/*.py | grep -E "separate|queue_lifecycle|routing"`);
   - the full backend suite (`python -m pytest tests/ -x --tb=short`);
   - `ruff check .`, `mypy . --exclude '^outputs/'`, and `git diff --check`.
3. Protected paths compared against `40ee8dbe`.

## Step 4: documentation and commit

1. The spec's status and implementation record; the stale PROPOSED and UNKNOWN wording that the
   implementation resolves.
2. The policy spec: dated corrections to the 5B-5 row, P1, P9, and X6, keeping the original text.
3. `handoff.md` and `memory.md`.
4. Review the full diff, then make one local commit.

## Execution record (2026-09-30)

Executed in the order above on `40ee8dbe`; the spec's section 18 is the implementation record.

- Baseline: the state was as reported; no other session wrote to the checkout. The focused suites
  passed on `40ee8dbe` before any code was written (605 tests).
- Deviation within Step 3: fault injection ran twice. The first pass (86 of 106 killed) found eight
  test gaps and one output-equivalent mutant; tests were added, and a direct self-check test covers
  the partition checks. The final pass on the final code killed 101 of 106; the 5 survivors are
  equivalent (spec section 18.5).
- No step changed the approved contract.
