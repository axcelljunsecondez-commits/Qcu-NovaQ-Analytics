# Plan: Shared Queue Phase 5B-4.2, Pure Named-Employee State Machine

Spec: `docs/superpowers/specs/2026-09-28-shared-queue-employee-state-machine.md`.
Policy contract: `docs/superpowers/specs/2026-09-28-shared-queue-named-employee-des-policy.md`.

1. **Re-verify the starting state.**
   - HEAD `48b2499e`, the branch `feat/shared-queue-segments`, and the working tree.
   - The 5B-1 roster report (`evaluate_roster`), the anonymous engine's `_hours`, and the
     isolation test in `tests/test_shared_segments.py`.
2. **Record the 2026-09-28 decisions in the policy spec first.**
   - Quote the Phase 5B-4.2 request's explicit decisions.
   - Mark P1-P4 as decided.
   - Record that P5-P7 must be representable without a selection.
   - Leave X1, X5, X6, P8, and the P2 threshold UNKNOWN.
   - List the cases the decisions do not determine.
3. **Implement `backend/queueing_engine/simulation/shared_employee_states.py`.**
   - Seven mutually exclusive base states, with identified registers 1..K and the P4 handover
     order.
   - The X2 same-time order for employee-only events, with closing placed after completions
     (INFERRED).
   - Full-duration delayed breaks with the gap push, no pre-break cutoff, and no pre-shift-end
     cutoff.
   - Split-shift activation from the actual release plus the rest.
   - Terminal outcomes for every break.
   - The required `hold_past_shift_end` flag and the `Release`, `EndBreakAtClosing`, and
     `CancelPendingBreaks` closing inputs for P5-P7.
   - `UndeterminedPolicyError` for the undetermined split-shift break.
   - X4 roster precondition.
   - No customers, queue, service-time generation, or random numbers.
   - No existing production module changes.
4. **Write `tests/test_shared_employee_states.py`.**
   - Synthetic, binary-exact, hand-computed cases for every required case.
   - An independent checker of invariants 1-16, run on every successful run.
   - Tests for rejected inputs, units, and isolation.
   - Add the module to `SHARED_QUEUE_ENHANCEMENT_MODULES` in `tests/test_shared_segments.py`.
5. **Fault-inject.**
   - Run source-level mutants of a module copy (a scratch script, not committed).
   - Close each surviving gap with a test, never by weakening one.
   - Rerun until every mutant is killed and the unmutated copy passes.
6. **Record any contradiction between the implementation and the policy spec in both specs.**
   - The INFERRED capacity bound was falsified by the gap rule, so it is withdrawn.
7. **Run the gates.**
   - The focused tests.
   - The shared-queue suites and the 5B-4.0 pin.
   - The Separate Queue regressions: `test_separate_break_des`, `test_separate_break_periods`,
     `test_separate_break_wiring`, `test_queue_lifecycle`, and `test_routing_des_pairing`.
   - `ruff check .` and `mypy . --exclude '^outputs/'`.
   - The full backend suite.
8. **Update `handoff.md` and `memory.md`, then commit locally.**
   - Review the exact file list first.
   - Commit only if every gate passes. Do not stage `.claude/`, and do not push, merge, or
     deploy.
9. **Stop after 5B-4.2.**
   - 5B-4.3 (customer and queue integration) needs explicit approval, the P5, P6, and P7
     selections, X1, the P8 output shape, the X6 output field, and decisions on the
     undetermined cases.
