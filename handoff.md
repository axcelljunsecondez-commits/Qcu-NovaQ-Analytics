# NovaQ Current Handoff

## Simulation Playback (2026-09-12)

- Upgraded the existing Live trace into customer-level playback without changing queueing mathematics or aggregate DES behavior.
- Trace events now include stable recorder-assigned `customer_id` values; responses state `queue_structure: "shared"` and `abandonment_supported: false`.
- The Live tab now shows one truthful shared FIFO queue, exactly the configured number of servers, customer/server assignments, served exits, bounded queue tokens, relative simulation time, event accounting, and play/pause/restart/step/speed controls.
- Playback uses a pure event reducer and simulation-time conversion; it does not generate queueing or random values in React.
- Full verification: backend **450 passed, 3 skipped, 3 subtests**; frontend **24 files / 140 tests passed**; typecheck, Ruff, mypy, lint, build, and locale symmetry passed. Existing chart canvas notices, Fast Refresh warnings, and large-chunk warning remain non-blocking.
- Verified limitations: DES playback supports M/M/1 and M/M/c only, models a shared queue only, has no abandonment transition, and has count-based rather than identity-based cross-segment carryover.

## Current Development State

NovaQ is being prepared as a pilot-deployable web-based capstone.

The repository already uses:

- React frontend
- FastAPI backend
- PostgreSQL
- Docker Compose
- Superpowers workflow
- AGENTS.md repository instructions

## Current Priorities

1. Stabilize the core workflow.
2. Improve onboarding for users without queueing-theory knowledge.
3. Remove redundant setup/input flows.
4. Preserve queueing-engine correctness.
5. Prepare the system for deployment and real-user pilot use.

## Core Workflow

Login
→ Onboarding
→ Setup
→ Upload Data
→ Current Analysis
→ Optimize
→ Save Scenario
→ Simulation
→ Comparison
→ Report

## Before Starting Any Significant Task

Read:

1. `AGENTS.md`
2. `memory.md`
3. `handoff.md`
4. Relevant existing Superpowers spec/plan
5. Relevant source files

Do not assume the repository state from old documentation.

## Execution Rule

For bugs:

Investigate
→ reproduce/trace
→ identify root cause
→ plan
→ implement
→ test
→ verify

For substantial features:

Brainstorm
→ spec
→ plan
→ implement
→ test
→ verify
→ update handoff
