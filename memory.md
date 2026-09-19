# NovaQ Project Memory

## Product Direction

NovaQ is currently a web-based, pilot-deployable capstone system, not a full commercial SaaS product.

Primary development priorities:

1. Correctness
2. Understandability
3. Usability
4. Deployability

The system should remain usable by people without formal queueing-theory knowledge.

## Architecture

- Frontend: React 19 + Vite
- Backend: FastAPI
- Database: PostgreSQL 16
- Reverse proxy: nginx
- Deployment architecture: Docker Compose
- Simulation: SimPy discrete-event simulation
- Monte Carlo simulation is also supported

## Queueing Principles

- Queueing-model selection must use the existing centralized model-selection service.
- Do not silently substitute one queueing model for another.
- Service-time variability must be considered when determining whether M/M/c or M/G/c is appropriate.
- Analytical, optimization, and DES outputs answer different questions and must not be presented as interchangeable.

## Optimization

- Utilization targets are configurable operational/study parameters.
- A utilization target must not be presented as a universal mathematical optimum.
- Stability constraints must be enforced.
- Optimizer recommendations must respect configured constraints.

## Monte Carlo

- Default Monte Carlo trials: 2,000.
- Monte Carlo failure must have an explicit operational definition.
- Monte Carlo settings must remain configurable where exposed by the application.

## UX Direction

Preferred user flow:

Login
→ Introduction / onboarding
→ Setup
→ Upload data
→ Current Analysis
→ Optimize
→ Comparison
→ Simulation
→ Decision
→ Report

Avoid duplicate setup inputs across pages.

Technical queueing terminology should be translated into understandable operational language where possible.

## UI/UX Refinement Product Decisions (2026-09-13)

- Onboarding is required once for first-time authenticated users, is not forced again after completion, and is replayable from Help. It must collect real preferences rather than silently saving placeholders.
- The intended product behavior is separate FIFO cashier queues. Priority-class queueing is outside the capstone scope and must not be represented as supported.
- The current repository still marks separate queues unsupported and executes shared-FIFO DES/playback. Treat this as a documented product/implementation conflict: do not claim separate-queue support or silently substitute shared FIFO. A separate analytical feature specification is required before changing that protected behavior.
- The current optimization objective remains configured cost minimization subject to enabled constraints. A short-wait preset changes constraints; it is not an independent minimum-wait objective.
- Cost represents the explicitly analyzed operating period. Monthly and annual amounts are projections based on disclosed scaling assumptions, never observed costs.
- ROI must not be reported unless an explicit investment cost is defined.
- A report preview must match the sections actually implemented in the selected generated export. A section may be advertised only after its data/calculation and export implementation exist.

## UI/UX Refinement Governance (2026-09-13)

NovaQ UI/UX work must follow this sequence:

1. Trust Repair: correct misleading or inconsistent P0 behavior without broad redesign.
2. Specification: document exactly what the full refinement will change.
3. Safety Boundary: declare the analytical, optimization, simulation, decision, security, provenance, and reporting behaviors that must not change.
4. Implementation: refine only within the approved specification and safety boundary.
5. Verification: prove that the P0 defects are gone and that protected NovaQ behavior remains unchanged.

A validated protected behavior may change only when a separately documented defect establishes the evidence, justification, replacement behavior, and required regression coverage.

The full repository-grounded refinement specification and ordered implementation plan are:

- `docs/superpowers/specs/2026-09-13-ui-ux-full-refinement.md`
- `docs/superpowers/plans/2026-09-13-ui-ux-full-refinement-plan.md`

Implementation completed on 2026-09-14. Current unified DES aggregate/playback execution and persisted workflow evidence/Decision behavior remain proven and protected; older findings that those capabilities were missing are superseded.

## Shared Design System (2026-09-13)

- `design-system/novaq/MASTER.md` is the mandatory UI source of truth before page-by-page refinement.
- The system formally adopts the current React, React Router, global CSS, Plotly, i18next, Inter/system-font, and NovaQ navy/gold foundation. No replacement framework, component library, chart library, font, or motion dependency is authorized.
- The requested Simulate-before-Compare navigation conflicts with current scenario-selection behavior: simulation requires a verified scenario selected in Compare. Until a separate workflow specification relocates that prerequisite, the executable order remains Setup → Current → Optimize → Compare → Simulate → Decision → Reports.
- Workflow completion is evidence-backed, never visit-backed. Saved evidence is not automatically passed, valid, or complete.

## Critical Semantic Regression Gate (2026-09-14)

- The pre-redesign semantic gate is implemented and green. Its specification, plan, and verification report are:
  - `docs/superpowers/specs/2026-09-13-critical-semantic-regression-gate.md`
  - `docs/superpowers/plans/2026-09-13-critical-semantic-regression-gate-plan.md`
  - `docs/superpowers/reports/2026-09-14-critical-semantic-regression-gate-report.md`
- Unknown setup values remain explicit `unknown`/`null` values from frontend submission through persistence and API presentation.
- Optimization presets are constraint profiles; configured-cost minimization remains the only implemented objective.
- Validation presentation and Decision evaluation use parameters persisted with the validation run. Editable controls configure the next run and cannot reinterpret old evidence.
- Report previews enumerate only actual PDF sections and Excel sheets, including the conditional Recommendations sheet.
- Canonical navigation, missing-versus-zero behavior, and scenario-scoped/current Decision evidence have behavior-level regression coverage.
- Full verification baseline: backend 466 passed, 3 skipped, 6 subtests; frontend 140 passed; Ruff, mypy, TypeScript, frontend lint, build, locale symmetry, and diff hygiene passed.
- Page-by-page refinement is unblocked only within the approved shared design system, full refinement plan, and protected-behavior boundary.

## Full UI/UX Refinement Completion (2026-09-14)

- The approved repository-first refinement is implemented and verified. The report is `docs/superpowers/reports/2026-09-14-ui-ux-full-refinement-report.md`.
- Required-once onboarding, Help replay, canonical workflow navigation, semantic design tokens, responsive navigation, shared system states, accessible tables/charts/tabs, and evidence-safe Decision/Reports presentation are now the frontend baseline.
- Current and Compare use authoritative stored metrics only; synthetic radar scores, ROI, and unsupported calendar projections were removed.
- Full verification: backend 466 passed, 3 skipped, 6 subtests; frontend 141 passed; Ruff, mypy, TypeScript, lint, build, locale symmetry, browser checks, Docker rebuild, and health checks passed.
- No protected backend production logic or API contracts changed. Compare remains before Simulate because scenario selection is still a verified simulation prerequisite.

## Engineering Rules

- Preserve established queueing formulas unless a verified defect requires correction.
- Prefer minimal regression-safe changes.
- Investigate root cause before modifying code.
- Validate frontend, backend, and relevant tests before claiming completion.

## API Image Vulnerability Remediation (2026-09-14)

- The current CI-equivalent finding for the former Debian API image was 44 HIGH and 0 CRITICAL; the older 51 HIGH/3 CRITICAL count is superseded.
- `Dockerfile.api` now uses the verified official Python 3.11.16 Alpine 3.24 digest, applies `apk upgrade --no-cache`, preserves the exact dependency lock and UID/GID 10001, and retains the existing POSIX-shell entrypoint.
- The unchanged strict Trivy 0.74.0 gate reports 0 HIGH and 0 CRITICAL for both OS and Python package targets on the rebuilt image. No suppression or policy weakening was used.
- Full local regression and Compose smoke gates are green. See `docs/superpowers/reports/2026-09-14-api-image-vulnerability-remediation-report.md`.
- This closes only the local API image defect. GitHub CI and Render public deployment verification remain required, while Supabase must remain unchanged because this remediation has no migration.

## Problem 1 Closure — Separate-Queue Current Independence

Refines (does not rewrite) the 2026-09-13 separate-queue conflict note. Tree-verified by `tests/test_current_independence.py`:

- SUPPORTED: configurable separate queue IDs; Current Analysis processes separate queues independently by (time, queue_id); each queue uses centralized model selection independently.
- STILL LIMITED: separate-queue staffing optimization remains blocked where demand redistribution is undefined; separate-queue DES/playback remains unsupported unless current source proves otherwise.

## Problem 6B Freeze - Separate-Queue MC/Validation Semantics

Separate MC/Validation stay unavailable until proven. Frozen contract: `docs/superpowers/specs/2026-09-17-separate-mc-validation-semantics.md` — per-row `(time, queue_id)` execution, existing math/CI/failure definition reused unchanged, no pooled failure rates, missing stays missing, Decision taxonomy unchanged.

## Separate-Queue Status (2026-09-19, supersedes the "STILL LIMITED" and "unsupported" notes above)

The notes above are kept as history. Verified in source and tests at 9b1f95a4:

- Workflow: Setup → Current → Optimize → Compare → Simulate → Decision → Reports.
- Current: each (time, queue_id) is analysed on its own through centralized model selection (analytical estimate, not a measurement).
- Staffing optimization: `POST /analyses/{id}/workflow/optimize/separate`. Fewer-lane sets have no analytical model, so each period's candidates are judged by replicated routing DES (shortest-queue routing, one server per lane) over the operating day. A candidate is feasible when its highest mean lane utilization is at or below the target. Feasible means meeting the target, not a statistically proven improvement.
- Break optimization (separate from staffing optimization): `POST .../optimize/separate/breaks` (read-only) and `.../breaks/apply`. Placement is greedy, so the result is a local improvement, not a proven global optimum.
- Selected-plan evidence: `.../simulation/des/selected` (with playback trace), `.../simulation/mc/selected`, `.../simulation/validation/selected`, `.../decision/selected`.
- Compare: Current values are analytical and plan values are simulated. Waits, waiting costs and peak utilization are labelled with their basis and never subtracted. Current total cost, savings and ROI are N/A, with the reason shown.
- Model scope: the separate-queue DES has no finite capacity and no abandonment (`abandonment_supported: false`). K and theta affect only the per-lane analytical Current rows.
- Known finding: the selected-plan Monte Carlo Decision depends on the base seed for NovaMart with breaks applied (cashier_2 at 13:00 passes on seeds 7-8 and fails on 9-11). It is recorded as a strict xfail in `tests/test_selected_mc_load.py` and not yet fixed.
