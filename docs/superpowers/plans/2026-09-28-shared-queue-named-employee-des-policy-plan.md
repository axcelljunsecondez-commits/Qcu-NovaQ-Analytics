# Plan: Shared Queue Phase 5B-4.0 and 5B-4.1, Anonymous-Engine Pin and Named-Employee DES Policy Contract

Spec: `docs/superpowers/specs/2026-09-28-shared-queue-named-employee-des-policy.md`.

1. Re-verify the starting state:
   - HEAD `d5723aba`, the branch, and the working tree;
   - the repository instructions;
   - the anonymous engine's deterministic entry point, `simulate_prescribed`;
   - the existing tests in `tests/test_shared_continuous_des.py`.
2. 5B-4.0: add `tests/test_shared_continuous_des_pin.py` and
   `tests/fixtures/shared_continuous_des_output_pin.json`.
   - Use fixed, binary-exact prescribed arrivals, with no seed.
   - Include the main transitions case (DRAIN, HARD_CUTOFF, and a trace cap), "no one on duty at
     closing", and "no arrivals".
   - Derive the main case by hand and assert that derivation without using the fixture.
   - Generate the fixture from the unchanged engine. Make no engine change.
3. Fault-inject the pin with source-level mutants of an in-memory engine copy (a scratch script,
   not committed). Every mutant must be caught, and the unmutated copy must match.
4. 5B-4.1: record the approved P1-P9 and X1-X7 contract in the spec.
   - Single rules are APPROVED SPECIFICATION.
   - Unselected alternatives are UNKNOWN and block the named sub-phase that needs them.
   - X7 (staffing segments required) is mandatory.
   - Record that Separate Queue break behavior is protected and not reused, that the numpy pins
     conflict, that cross-version RNG equality is UNKNOWN, and that the named engine adds no
     random process.
5. Run the focused tests, the shared and separate suites, the full backend suite, `ruff check .`,
   and `mypy . --exclude '^outputs/'`.
6. Update `handoff.md` and `memory.md`, review the exact file list, and commit locally only if every
   gate passes. Do not push. Stop after 5B-4.1.
7. Next, which needs approval together with the open selections in the spec: 5B-4.2, the employee
   timeline state machine.
