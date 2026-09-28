# Plan: Shared Queue Phase 5B-4.3, Named-Employee Continuous Shared-Queue DES

Spec: `docs/superpowers/specs/2026-09-28-shared-queue-named-des.md`.
Policy contract: `docs/superpowers/specs/2026-09-28-shared-queue-named-employee-des-policy.md`.

1. **Re-verify the starting state.**
   - HEAD `dfa8fe75` and parent `48b2499e`, the branch `feat/shared-queue-segments`, and the
     working tree.
   - Rerun the 5B-4.0 pin and the 5B-4.2 tests.
   - Read the state machine, the anonymous engine, `validate_timeline`, and the roster report's
     `active_server_steps` in the code.
   - Search for an event-time tolerance.
2. **Record the 5B-4.3 decisions in the policy spec first.** P1-P9 and X1-X7 as supplied,
   including the new P3 rule for breaks of a delayed split shift.
3. **Amend the 5B-4.2 state machine.**
   - Replace the `UndeterminedPolicyError` split-shift branch with the P3 offset rule.
   - Compute roster-derived instants in whole minutes (the float safeguard). Show the hazard
     against the dfa8fe75 module.
   - Add the read-only `snapshot()` accessor and bump the version.
   - Update the one 5B-4.2 expectation the approved rule changes, with hand-computed values, and
     replace the undetermined test with hand-computed P3 tests.
4. **Implement `backend/queueing_engine/simulation/shared_named_des.py`.**
   - Prescribed arrivals validated like the anonymous engine.
   - X7 and policy validation.
   - The X2 instant loop: completions, the closing boundary (P5-P7 closing inputs, X6), DRAIN
     releases, the machine stages, arrivals, and one FCFS pass with X1.
   - P8 staffing timeline and windows, customer rows, the queue integral, and the trace.
   - No random numbers and no change to the anonymous engine.
5. **Write `tests/test_shared_named_des.py`.**
   - The independent checker `check_named` for invariants 1-19, running the 5B-4.2 checker on the
     employee timeline.
   - Every required hand-computed case, input and isolation tests, and the reduction comparison
     with `simulate_prescribed`.
   - Add the module to `SHARED_QUEUE_ENHANCEMENT_MODULES`.
6. **Fault-inject.**
   - Source-level mutants of scratch copies of both modules (a scratch script, not committed).
   - Close any surviving gap with a test, never by weakening one.
7. **Run the gates.**
   - Focused tests: named DES, state machine, and the pin.
   - Shared-queue suites.
   - Separate Queue regressions: `test_separate_break_des`, `test_separate_break_periods`,
     `test_separate_break_wiring`, `test_queue_lifecycle`, and `test_routing_des_pairing`.
   - `ruff check .`, `mypy . --exclude '^outputs/'`, and the full backend suite.
8. **Update `handoff.md` and `memory.md`, review the exact file list, and commit locally** only if
   every gate passes. Do not stage `.claude/`, and do not push, merge, or deploy.
9. **Stop after 5B-4.3.** Seeded named replications, named playback, and workforce cost each need
   explicit approval.
