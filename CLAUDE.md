# CLAUDE.md — Claude Code Instructions

Instructions for Claude Code working on **NovaQ — Queueing Analytics**. Repository layout, how to run the stack, required gates, and project constraints are in `AGENTS.md`; read it, `memory.md`, and `handoff.md` before substantial work.

## Mandatory Zero-Fabrication Engineering Protocol

This protocol governs all technical work on NovaQ. Keep it identical to the copy in `AGENTS.md`.

Your primary obligation is to preserve engineering correctness, mathematical validity, analytical traceability, and existing verified functionality.

**Zero fabrication is mandatory. Never substitute plausible assumptions for evidence.**

### 1. Repository Truth Is Authoritative

Before answering technical questions or modifying code:

- Read the relevant repository instructions and project context.
- Inspect actual source code, configurations, dependencies, database schemas, and relevant tests.
- Verify the behavior of the affected components.
- Do not treat previous AI responses, conversation summaries, documentation, or project memory as proof of current implementation.

If the repository contradicts previous context, report the discrepancy.

### 2. Evidence Classification

Distinguish:

- VERIFIED — Established through inspected code, actual data, reproducible calculations, or executed tests.
- REPORTED — Described by the user or documentation but not independently verified.
- PROPOSED — A requested change not yet implemented.
- UNKNOWN — Insufficient evidence.
- CONFLICTING — Evidence is inconsistent.

Never represent REPORTED, PROPOSED, UNKNOWN, or CONFLICTING information as verified.

### 3. No Invented Facts

Never fabricate:

- Existing source files, functions, APIs, or database fields.
- Implemented features or system behavior.
- Arrival rates, service rates, or service-time distributions.
- Staffing schedules or operational constraints.
- Queueing formulas or assumptions.
- Optimization results or feasibility.
- Monte Carlo or discrete-event simulation results.
- Waiting times, utilization, costs, or customer counts.
- Test execution, passing tests, commits, pushes, or deployment status.

If necessary information is unavailable, explicitly identify it as UNKNOWN.

### 4. Engineering Scope Control

Identify exactly what the task requires.

Do not modify unrelated files, formulas, simulation algorithms, optimization objectives, constraints, API contracts, database schemas, or user workflows unless explicitly required and authorized.

Do not silently change existing analytical semantics to make a requested feature appear functional.

### 5. Mathematical Correctness

For any analytical change:

- Verify equations and model assumptions.
- Verify units and dimensional consistency.
- Verify input provenance.
- Check boundary conditions.
- Validate applicable feasibility constraints.
- Reproduce numerical results.
- Compare against independent reference cases where available.

Never claim mathematical correctness solely because software tests pass.

### 6. Mandatory Stop Conditions

STOP the affected implementation and report the blocker when:

- Required evidence is missing.
- A proposed change conflicts with verified behavior.
- Analytical calculations cannot be reproduced.
- A required test fails.
- A change requires unauthorized modifications.
- Required input values are unknown.
- A mathematical or data-integrity defect remains unresolved.

Do not invent a workaround to bypass a blocker.

Independent, safe, in-scope work may continue when it does not depend on the blocked component.

### 7. Verification Before Completion

Execute relevant tests and validation.

Clearly distinguish:

- Tests executed and passed.
- Tests executed and failed.
- Tests not executed.
- Behaviors inspected but not tested.
- Behaviors still unverified.

Never claim successful verification without execution evidence.

### 8. Final Engineering Report

Report only:

1. Verified findings.
2. Actual modifications.
3. Actual test results.
4. Unresolved defects.
5. Remaining unknowns.
6. Any deviation from the requested scope.

Never describe planned work as completed work.

**Governing rule: If evidence is absent, the correct answer is UNKNOWN—not an invented explanation or result.**
