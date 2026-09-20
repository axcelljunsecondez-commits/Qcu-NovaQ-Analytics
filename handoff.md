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

## API Image Vulnerability Gate Remediated Locally (2026-09-14)

The approved remediation is implemented and locally verified. See:

- `docs/superpowers/specs/2026-09-14-api-image-vulnerability-remediation.md`
- `docs/superpowers/plans/2026-09-14-api-image-vulnerability-remediation-plan.md`
- `docs/superpowers/reports/2026-09-14-api-image-vulnerability-remediation-report.md`

Current evidence:

- API runtime changed from the blocking Debian base to the verified digest-pinned Python 3.11.16 Alpine 3.24 base; application and dependency-lock contents are unchanged.
- Strict Trivy 0.74.0 result improved from 44 HIGH/0 CRITICAL to 0 HIGH/0 CRITICAL without ignores or policy changes.
- Backend: 466 passed, 3 skipped, 6 subtests. Frontend: 141 passed. Ruff, mypy, TypeScript, lint, build, locale symmetry, production Compose preflight, Docker rebuild, migrations, bootstrap, and HTTP health/readiness checks passed.
- Next: inspect diff, commit/pull/push, wait for green GitHub CI, then identify and verify the authenticated Render service/public URL.
- Supabase is deliberately unchanged: this remediation contains no migration. Do not perform a hosted schema mutation for this work.
- Overall production GO is still separate from this image fix; TLS, SMTP, backup/restore, monitoring, edge, and secret-permission evidence remain required.

## Problem 1 Closed — Separate-Queue Current Independence

`tests/test_current_independence.py` (9 tests) proves Current Analysis keeps each (time, queue_id) an independent analytical entity through centralized model selection, with no pooled λ-total/c-total entity.

- SUPPORTED: configurable separate queue IDs; Current Analysis processes separate queues independently by (time, queue_id); each queue uses centralized model selection independently.
- STILL LIMITED: separate-queue staffing optimization remains blocked where demand redistribution is undefined; separate-queue DES/playback remains unsupported unless current source proves otherwise.

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
- Known limitation (K1, per-date basis): a single-date upload (`event_period_basis: per_date`) still judges each period's staffing candidates, and simulates the selected plan, one period at a time over the 24 h default (`DES_DEFAULT_DURATION_HOURS`). A break that fills a period is only a small part of that run, so break-hour utilization and waits are understated and a break hour can be marked FEASIBLE when the same hour inside a continuous day is not (`tests/test_separate_day_feasibility.py::test_per_date_basis_keeps_the_24_hour_candidate_runs`: below 0.55 per-date vs above 0.70 on the continuous day). Optimizer and selected-plan DES agree with each other on this basis. Not fixed; the representative-day path (NovaMart) is not affected.
- Representative-day layout (K2-a): the optimizer rejects a representative-day schedule with `INVALID_INPUT` (no periods, no `utilization_basis`) when the operating day cannot be laid out: no operating segments, a malformed segment time, or a period label that matches no segment id (e.g. Setup segments renamed without re-uploading). It never falls back to independent 24 h per-period runs. The per-date basis is unchanged (K1).

## Store Floor Playback View (2026-09-20)

The separate-queue playback now renders as a checkout floor by default. Spec and plan:

- `docs/superpowers/specs/2026-09-20-store-floor-playback-view.md`
- `docs/superpowers/plans/2026-09-20-store-floor-playback-view-plan.md`

Current verified state:

- `StoreFloorView` draws lanes as grid columns with the waiting queue stacked toward its
  own counter, the serving customer at the counter, and the elapsed service time computed
  from the traced `service_start`. The panel stays vertically bounded; past ten lanes it
  switches to a dense layout and the lane strip overflows horizontally only.
- The existing stacked diagram is retained behind a "Floor layout" selector. Both views
  read the same `deriveSeparateLaneSnapshots` output and keep the same lane, customer, and
  server test identifiers, so separate-queue isolation stays provable in either view.
- Lane identity is now seeded from `trace.segments` before events. A lane the run declared
  but never used is drawn as a real empty lane instead of disappearing.
- A lane in the period's `inactive_queue_ids` is labeled **Closed / not staffed in this
  plan**. It is deliberately not labeled as a break: the trace schema emits no break
  transition, so an ON_BREAK window cannot be shown truthfully on the playback clock.
- Playback speeds now include 0.25x in both the shared and separate playbacks. Dot
  transitions are disabled at 5x and above.
- Presentation-only: no queueing mathematics, DES behavior, API contract, or aggregate
  field changed.
- Locale catalogues were de-duplicated in the same working tree: four repeated keys in
  `en` and five in `tl` had made the earlier value dead. The shipping (later) value was
  kept in every case and `frontend/src/lib/translationKeys.test.ts` now fails on any
  repeated key and on any en/tl key-set difference.
- Verification: frontend **47 files / 312 tests passed**; typecheck, oxlint, production
  build, and locale symmetry passed. Visual check used a real selected-plan DES payload
  (735 events over 5 lanes and 2054 over 14) in both light and dark themes; the displayed
  service timers matched the traced `service_start` values exactly. The pre-existing large
  Plotly chunk warning and chart canvas notices remain non-blocking.

Known limitation, not fixed and out of this feature's scope: `evaluate_candidate_with_des`
omits `trace_events` on its INFEASIBLE early return
(`backend/queueing_engine/services/separate_optimization.py:591`), so any period whose
simulated utilization exceeds the target renders an empty playback in both views.
