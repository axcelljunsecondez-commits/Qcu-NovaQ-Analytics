# NovaQ Current Handoff

## Critical Semantic Regression Gate (2026-09-14)

The mandatory pre-redesign semantic gate is complete and green:

- `docs/superpowers/specs/2026-09-13-critical-semantic-regression-gate.md`
- `docs/superpowers/plans/2026-09-13-critical-semantic-regression-gate-plan.md`
- `docs/superpowers/reports/2026-09-14-critical-semantic-regression-gate-report.md`

Behavior-level coverage now protects unknown setup values, exact optimizer-preset meaning, saved validation parameters, report preview/export parity, canonical route resolution, missing-versus-zero semantics, and scenario-scoped/current Decision evidence. The smallest approved truth repairs were made in Guided Setup, optimizer copy, Simulation validation presentation, report preview, Dashboard route targets, and complete-value frontend aggregation.

No backend production code or protected queueing, model-selection, optimizer, DES/Monte Carlo, Decision, authentication/CSRF, provenance/staleness, API, report-calculation, or report-unit behavior changed.

Verification baseline: backend **466 passed, 3 skipped, 6 subtests passed**; frontend **31 files / 140 tests passed**; Ruff, mypy, TypeScript, frontend lint, production build, 565-key locale symmetry, and diff hygiene passed. Two pre-existing Fast Refresh warnings and the existing large Plotly chunk warning remain non-blocking.

Page-by-page UI refinement may now begin through the approved full refinement plan and `design-system/novaq/MASTER.md`. Retain the executable workflow order `Setup → Current → Optimize → Compare → Simulate → Decision → Reports` because Compare's persisted scenario selection remains a simulation prerequisite.

## Shared Design System Definition (Part 4, 2026-09-13)

The mandatory shared design-system phase is defined and approved:

- `docs/superpowers/specs/2026-09-13-shared-design-system.md`
- `design-system/novaq/MASTER.md`

No application code was changed in Part 4. The Master defines the light/dark semantic token contract, type/spacing scales, responsive shell, shared components, API/content states, evidence banners, workflow completion predicates, chart rules, accessibility requirements, page-override policy, and verification gates.

The current React/global-CSS/Plotly/i18next stack, Inter/system font, and NovaQ navy/gold identity are retained. The generated replacement fonts/palette, GSAP, new UI framework, and component library were rejected as unsupported.

The requested Setup → Current → Optimize → Simulate → Compare order conflicts with the repository: Compare persists the verified scenario selection required by simulation, and the backend/test suite rejects simulation without it. The Master therefore retains Setup → Current → Optimize → Compare → Simulate → Decision → Reports until a separate workflow specification authorizes relocation of that prerequisite.

## Full UI/UX Refinement Specification and Plan (Part 3, 2026-09-13)

The repository-grounded refinement specification and ordered implementation plan are approved:

- `docs/superpowers/specs/2026-09-13-ui-ux-full-refinement.md`
- `docs/superpowers/plans/2026-09-13-ui-ux-full-refinement-plan.md`

No application code was changed in Part 3. Implementation has not started.

The specification verifies eight P0 trust defects: broken entry links/false Login claims, incorrect onboarding flow, divergent Guided Setup, non-data-derived Current conclusions, misleading Optimize semantics, synthetic Comparison/ROI evidence, mutable-threshold Simulation display, and report-preview/export mismatch. Cross-cutting accessibility, responsive, theme, language, icon, and localization work follows only after the P0 gate.

The approved separate-FIFO product intent conflicts with the current repository, which marks separate queues unsupported and runs shared-FIFO DES/playback. This conflict is explicit: the UI may disclose the limitation but must not claim support or change queueing mathematics under the refinement plan. Priority-class queueing remains outside scope.

The earlier “DES equivalence not proven” and “Decision evidence missing” findings are superseded by current source and tests. Unified DES execution, aggregate/playback equivalence, persisted workflow evidence, Decision derivation, and staleness are protected invariants.

## UI/UX Refinement Governance (Part 2, 2026-09-13)

The product owner established a mandatory five-phase refinement sequence:

1. Trust Repair
2. Specification
3. Safety Boundary
4. Implementation
5. Verification

Full UI refinement must not start before the specification and safety boundary are documented. Phase 1 is limited to correcting misleading or inconsistent P0 behavior. Phase 5 must prove both defect removal and non-regression of protected behavior.

The governing document is `docs/superpowers/specs/2026-09-13-ui-ux-refinement-governance.md`. No UI or protected backend behavior was changed while recording Part 2.

## UI/UX Refinement Decision Baseline (Part 1, 2026-09-13)

Part 1 of the UI/UX refinement preparation is complete. The product owner confirmed the following authoritative constraints:

1. Onboarding is required once for first-time authenticated users, is not forced again after completion, is replayable from Help, and must collect real values.
2. The intended product behavior is separate FIFO cashier queues; priority-class queueing is outside scope. The current repository's unsupported/shared-FIFO implementation is a documented conflict and must not be relabeled as separate support.
3. Optimization continues to minimize configured cost subject to constraints; short-wait presets are constraint profiles, not distinct objectives.
4. Costs cover the explicitly analyzed operating period. Monthly/annual values are disclosed projections, not observations, and ROI requires an explicit investment cost.
5. Report previews must exactly match implemented export sections.

These decisions are documented in `docs/superpowers/specs/2026-09-13-ui-ux-refinement-product-decisions.md`. No UI, API, queueing-engine, simulation, or report implementation was changed in this part.

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
→ Comparison
→ Simulation
→ Decision
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

## Full UI/UX Refinement Complete (2026-09-14)

The approved page-by-page refinement and shared design system are implemented. See:

- `docs/superpowers/reports/2026-09-14-ui-ux-full-refinement-report.md`
- `design-system/novaq/MASTER.md`

Current verified state:

- Required-once onboarding is enforced after authentication and replayable from Help.
- Guided Setup redirects to canonical analysis Setup.
- Global navigation and the evidence-aware footer use the single canonical workflow: Setup → Current → Optimize → Compare → Simulate → Decision → Reports.
- Current, Optimize, Compare, Simulation, Decision, and Reports no longer advertise synthetic, stale, unsupported, or incorrectly scoped evidence.
- Accessible responsive navigation, focus, reduced motion, table/chart alternatives, keyboard tabs, semantic states, and symmetric EN/TL copy are in place.
- Backend: 466 passed, 3 skipped, 6 subtests. Frontend: 141 passed. Ruff, mypy, TypeScript, lint (0 warnings/errors), build, locale symmetry, diff hygiene, real-browser checks, Docker rebuild, and HTTP health checks passed.
- No protected backend production logic or API contract changed. Separate-queue analytical/DES support remains unimplemented and is not claimed.
