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
- Known limitation (K1, per-date basis): a single-date upload (`event_period_basis: per_date`) still judges each period's staffing candidates, and simulates the selected plan, one period at a time over the 24 h default (`DES_DEFAULT_DURATION_HOURS`). A break that fills a period is only a small part of that run, so break-hour utilization and waits are understated and a break hour can be marked FEASIBLE when the same hour inside a continuous day is not (`tests/test_separate_day_feasibility.py::test_per_date_basis_keeps_the_24_hour_candidate_runs`: below 0.55 per-date vs above 0.70 on the continuous day). Optimizer and selected-plan DES agree with each other on this basis. Not fixed; the representative-day path (NovaMart) is not affected.
- Representative-day layout (K2-a): the optimizer rejects a representative-day schedule with `INVALID_INPUT` (no periods, no `utilization_basis`) when the operating day cannot be laid out: no operating segments, a malformed segment time, or a period label that matches no segment id (e.g. Setup segments renamed without re-uploading). It never falls back to independent 24 h per-period runs. The per-date basis is unchanged (K1).

## Store Floor Playback View (2026-09-20)

- The separate-queue playback renders as a checkout floor by default; the stacked diagram
  remains behind a "Floor layout" selector. Both are presentation-only readers of the same
  pure snapshot reducer and must stay that way: no queueing values may be generated in the
  browser.
- Lane identity comes from `trace.segments` first and from trace events second, so a lane
  the run declared but never used is still drawn.
- `inactive_queue_ids` means **closed / not staffed in this plan**. It must not be
  presented as a break. The trace schema emits no break transition, so an ON_BREAK window
  cannot be shown on the playback clock even though the DES models one internally.
- Locale catalogues must declare each key exactly once. Duplicate keys silently killed the
  earlier value until 2026-09-20; `frontend/src/lib/translationKeys.test.ts` now guards
  both uniqueness and en/tl symmetry.
- The former empty-playback defect for INFEASIBLE periods is resolved:
  `evaluate_candidate_with_des` returns `trace_events` and `trace_truncated` for both
  FEASIBLE and INFEASIBLE measured verdicts, with evaluator and selected-plan endpoint
  regression coverage.

## Deployment Topology (2026-09-24)

- Public frontend: Cloudflare Pages project `novaq-frontend` at `https://novaq.site` (`www` redirects to the apex). API: Render web service `Qcu-NovaQ-Analytics` (`https://qcu-novaq-analytics.onrender.com`). Local Docker Compose with nginx remains the development and rehearsal stack.
- Static Pages has no nginx proxy. The `/api` bridge is the Pages Function `frontend/functions/api/[[path]].ts`, limited by `frontend/public/_routes.json`. It must keep nginx's contract: strip only the leading `/api`, forward cookies, `Origin`, `X-CSRF-Token` and `X-Request-ID`, drop client-supplied proxy and `cf-*` headers, keep each `Set-Cookie` as its own header, and rewrite API-origin redirects under `/api`.
- The browser sees one origin, so session and CSRF cookies stay first-party and the CSRF double-submit check is unchanged. `ALLOWED_ORIGINS` only needs the origin that `PUBLIC_APP_URL` names (production refuses to start otherwise), plus any origin that calls the API cross-origin.
- `main` deploys both Cloudflare Pages and Render, so pushing `main` is a production release. Test on a branch preview first.
- Each new public origin must be added to the Google OAuth client's authorized JavaScript origins, or Google Sign-In fails with `origin_mismatch`.

## Engineering Governance (2026-09-25)

- The product owner adopted the Zero-Fabrication Engineering Protocol as a permanent project instruction. Its only copy is the "Mandatory Zero-Fabrication Engineering Protocol" section of `AGENTS.md`. `CLAUDE.md` imports `AGENTS.md` instead of repeating it.
- File roles: `AGENTS.md` holds permanent engineering rules and repository guardrails. `CLAUDE.md` holds Claude-specific configuration and imports only. `memory.md` holds approved durable decisions and technical context. `handoff.md` holds current status, verified completed work, unresolved defects, and authorized next actions. Skills hold repeatable procedures and refer to the protocol instead of restating it.
- The "Engineering Rules" list above is a short summary. Where it and the protocol differ, the protocol governs.
- The protocol sets evidence and verification requirements. It does not guarantee error-free work.

## Shared-Queue Closing Policy (2026-09-25)

- The product owner approved two closing policies for the new continuous shared-queue DES (`simulation/shared_continuous_des.py`, Phase 3A). Every run must name one; there is no default. DRAIN: arrivals stop at closing, and the servers on duty at closing serve everyone still waiting, with no overrun cap. A server draining at closing only finishes its own customer. When nobody is on duty, waiting customers are recorded as unserved (`no_eligible_server`). HARD_CUTOFF: arrivals stop at closing, waiting customers are recorded as unserved (`hard_cutoff`), and services already under way finish.
- Services that start after closing use the final demand period's service rate.
- Day cost comes only from `services/shared_day_cost.py`, with four caller-supplied rates that have no defaults: regular server, overtime (server-hours after closing), waiting (customer-hours), and unserved customer. The unserved term applies only when the configured closing can leave customers unserved: HARD_CUTOFF, or DRAIN with 0 servers in the final segment. A missing rate withholds the total; it is never replaced by 0. The legacy `REGULAR_RATE`/`OT_RATE` are not used here.
- Server-hours in this pipeline are modeled service-capacity hours, not necessarily paid employee-hours.
- The separate-queue day DES drain rule was not used to derive the shared rule; the shared rule comes from this approval.

## Shared-Queue DES Replications and Playback (2026-09-25)

- The new continuous shared-queue pipeline's repeated simulation (`simulation/shared_replications.py`) runs the Phase 3A DES itself for every replication. It uses the scenario's own rates, never the legacy analytical ±20%/±10% perturbation. Parameter uncertainty would be a separate, explicitly configured experiment and is not implemented.
- Seeds: the root is `SeedSequence(seed)`, and replication i uses `SeedSequence(entropy=root_entropy, spawn_key=(i,))`, so any replication can be regenerated alone. The replication count is required (no default) and limited to 1..`config.MC_MAX_TRIALS`.
- Intervals follow NovaQ conventions: Student-t for continuous replication metrics (as in the separate-queue DES replications), and Wilson for proportions. Undefined values are counted, never zero-filled.
- Failure criteria are optional and supplied by the caller: mean wait, utilization, unserved count, and overrun, with no default thresholds. Violation proportions are descriptive. No approved PASS/FAIL rule exists for this engine, so no verdict is produced; the legacy 0.75/0.05 rule is not applied.
- Playback (`simulation/shared_playback.py`) shows exactly one regenerated replication. Its events are the engine trace, checked by an independent replay; it never combines replications. There is no API or frontend yet.

## Shared-Queue Workforce Foundation (2026-09-26)

- `services/shared_workforce.py` (Phase 5B-1) validates pseudonymous employees, availability, shift and break rules, pay parameters, registers, and a roster. It works in whole minutes since midnight with half-open intervals, and has no operating defaults: a missing value is `None` and reported, never 0.
- Definitions: paid = scheduled - unpaid breaks; scheduled active server time = scheduled - all breaks; regular = min(paid, daily_regular_paid_minutes); overtime = paid - regular, taken in clock order, so the two never overlap. These are scheduled quantities, never simulated service time. The module builds no optimized roster and computes no cost.
- Roster status: INVALID (any coded violation), INCOMPLETE (a pay value or break-rule coverage is missing), or COMPLETE. A coverage shortfall against the required staffing is reported but is not a violation. Registers are counted, not identified.
- The separate-queue staff and break sheets, lane breaks, and the 3-minute pre-break cutoff are not used for shared queues. The Phase 5A decisions D1-D16 (solver approach, DES employee model, break-delay and overtime rules, and so on) remain open.

## Shared-Queue Sequential Rostering (2026-09-26)

- `services/shared_rostering.py` (Phase 5B-2) is the sequential workforce optimizer, using `scipy.optimize.milp` (HiGHS) with no new dependency.
  - Phase 2's selected server counts are a hard coverage target: at every instant, active employees are at least the required servers and at most the registers.
  - The objective is wages only: regular and overtime per the 5B-1 definitions.
- Product-owner decisions:
  - Break starts lie on a caller-supplied clock grid, `break_start_granularity_minutes`, with no default. Results are optimal over that grid only.
  - Surplus server-minutes are counted, reported, and paid only through wages. They are not attributed to employees.
  - Active time outside the operating horizon has no requirement and is reported separately.
  - Solver limits (time limit, `mip_rel_gap`, pattern cap) are required inputs.
  - This settles Phase 5A D1 (sequential for this phase), D2, D3, and D11.
- A pay value is required only when the objective uses it. For example, the overtime rate is needed only when an admissible plan exceeds the threshold. A missing value gives INCOMPLETE, never 0.
- OPTIMAL means HiGHS proved optimality within the reported tolerances for this model and grid, and the roster passed an exact 5B-1 re-check. It is never a claim about the real queue or a unique roster. Rosters are not yet simulated.

## Shared-Queue Integrated Planning (2026-09-28)

- `services/shared_integrated.py` (Phase 5B-3) is the integrated planning optimizer, using `scipy.optimize.milp` (HiGHS) with no new dependency. It chooses shift-and-break patterns and, through them, the server count on duty on every interval. It minimizes wages plus analytical customer waiting cost. The 5B-2 sequential optimizer is unchanged and remains available as the reference.
- Product-owner decision on capacity semantics ("every interval"):
  - The analytical server count is the number of employees on duty on every elementary interval between shift, break, demand-period, and staffing-segment boundaries.
  - Each interval is a stationary M/M/c queue with its demand period's λ and μ, over its own length.
  - Waiting cost = waiting rate × λ × Wq(c) × hours.
  - Stability, the utilization target, and the maximum wait are checked on every interval.
  - Staffing segments only group the report; their server counts are not used.
  - Short intervals, such as a break, are a stronger steady-state approximation, and backlog between intervals is not represented. The output discloses both.
- Labor is wages only (5B-1 regular and overtime). Phase 2's server cost per server-hour is never charged in this objective. Every employee on duty is paid and counted as a server, so surplus is never hidden.
- The planning settings (`PlanningConfig`) have no defaults. A missing waiting rate gives INCOMPLETE whenever customers arrive in the horizon, never 0.
- The objective is analytical planning cost, not the continuous-DES operating cost. OPTIMAL holds for this model, the break grid, and the reported solver tolerances. Rosters are not yet simulated.
- "Integrated no worse than sequential" is claimed only when the sequential roster is in the integrated feasible set and the same exact evaluator prices both rosters.

## Shared-Queue Named-Employee DES Policy (2026-09-28)

- The anonymous engine's complete `simulate_prescribed` output is pinned by `tests/test_shared_continuous_des_pin.py` against `tests/fixtures/shared_continuous_des_output_pin.json`. It uses fixed, binary-exact arrivals, with no seed. Regenerate the fixture only for an authorized, documented engine change (`python -m tests.test_shared_continuous_des_pin --write`).
- The named-employee DES contract is recorded in `docs/superpowers/specs/2026-09-28-shared-queue-named-employee-des-policy.md` (product-owner approval of P1-P9 and X1-X7, 2026-09-28). Its prescribed-arrival engine is implemented (Phase 5B-4.3); the rest is design.
- The approval did not choose among the alternatives the design offered. The Phase 5B-4.2 request (2026-09-28) then decided:
  - P1 (a): a delayed break keeps its full duration from its actual start, and a delay pushes later breaks by the minimum gap;
  - no pre-break cutoff and no pre-shift-end cutoff (P2, P3);
  - a later split shift waits for the actual release plus the required rest;
  - P4: registers identified 1..K, waiting in order of earliest wait start then employee_id, lowest-numbered free register first;
  - P5-P7 must be representable without a selection.

  Still UNKNOWN with no default at 5B-4.2: the P5, P6, and P7 selections, X1, X5, X6, P8, the P2 threshold, and P9 reporting. Phase 5B-4.3 supplied all of them except P9 reporting (below).
- X7: the named DES requires staffing segments (`required_staffing`, no default), validated by `validate_timeline`. They are never empty and never optional.
- Separate Queue break behavior (`PRE_BREAK_CUTOFF_MINUTES`, `queue_lifecycle`, the separate break controller, `break_optimization.py`) is protected and not reused. Named events use an `employee_` prefix.
- The numpy pins conflict across environments (`requirements.txt` <2.3, `requirements-lock.txt` 2.4.6, `requirements-production.lock` 2.2.6). Cross-version RNG equality is UNKNOWN.
  - The named engine adds no random process.
  - Test reference values come from prescribed arrivals, never from seeded golden values.
- `simulation/shared_employee_states.py` (Phase 5B-4.2) is the pure employee timeline, specified in `docs/superpowers/specs/2026-09-28-shared-queue-employee-state-machine.md`.
  - Seven mutually exclusive base states and identified registers.
  - Closing inputs represent the P5-P7 alternatives without choosing: `hold_past_shift_end` (required, no default), `Release`, `EndBreakAtClosing`, and `CancelPendingBreaks`.
  - No customers and no random numbers; service starts and completions are caller inputs.
  - Undetermined cases raise `UndeterminedPolicyError` or are recorded as INFERRED in its `UNDETERMINED` list.
- The 5B-4.1 INFERRED bound "before closing, accepting servers ≤ the 5B-1 scheduled active count" is withdrawn: the gap push can put an employee on duty during scheduled break time.
- Phase 5B-4.3 (2026-09-28) supplied the selections: DRAIN crew = employees AVAILABLE or SERVING immediately before closing, serving until the line is empty; HARD_CUTOFF releases idle employees at closing and busy ones at completion; P7 truncates breaks in progress and cancels pending ones; X1 longest available then employee_id; X2 places closing second; X6 `no_eligible_employee`; P8 reports six series and two separate gaps; a delayed split shift's breaks keep their planned offset from its actual start.
- `simulation/shared_named_des.py` (`simulate_named_prescribed`) is the named-employee DES on prescribed arrivals, specified in `docs/superpowers/specs/2026-09-28-shared-queue-named-des.md`. `employee_policy` accepts only the approved selections. The engine itself draws no random numbers; seeded replications are in `shared_named_replications.py` (below); playback and cost do not exist.
- The state machine computes roster-derived instants in whole minutes: adding minutes in hours can miss a roster boundary by one unit in the last place. Instants are otherwise compared exactly, as in the anonymous engine. Approved in Phase 5B-4.4: no generic event-time epsilon, and stochastic service times are never rounded or snapped to roster boundaries.
- Superseded by the Phase 5B-4.4 rules below: at 5B-4.3, a break-due service completing exactly at closing raised `UndeterminedPolicyError`, and a break ending exactly at closing was recorded completed (INFERRED).

## Shared-Queue Named Replications (2026-09-28)

- The Phase 5B-4.4 request approved five rules, frozen before replications (quoted in `docs/superpowers/specs/2026-09-28-shared-queue-named-replications.md`):
  1. A service with a break due that completes exactly at closing completes first; its break is unfulfilled, `cancelled_at_closing`. No zero-length break is created.
  2. A break ending exactly at closing is `truncated_by_closing`, because closing is processed before break ends.
  3. Accepting capacity = AVAILABLE + SERVING only.
  4. No event-time epsilon; whole-minute roster arithmetic; no rounding or snapping of stochastic times.
  5. Staffing gaps are reported per staffing segment and over the operating horizon only, never before opening or after closing. Post-close capacity and time are reported separately (the `after_closing` window is always present).
- Rules 1, 2, and 5 changed the named engine (`novaq-shared-named-des-v2`) and the state machine (`novaq-shared-employee-states-v3`: a SERVING_BREAK_DUE completion at closing, with that employee's `CancelPendingBreaks` at that instant, starts no break).
- X5: `shared_continuous_des.draw_arrivals` is the public wrapper around `_draw_arrivals`, with the same checks as `simulate_shared_replication`. No existing anonymous function changed; a seeded-output digest was identical before and after.
- `simulation/shared_named_replications.py`: `simulate_named_replication(seed_sequence=...)` returns the 5B-4.3 result unchanged plus a `replication` block. `run_named_replications` keeps one scalar row per replication; `replication_seed_sequence(root_entropy, i)` regenerates any replication.
  - Seeds follow the Phase 4 scheme: `SeedSequence(entropy=root_entropy, spawn_key=(i,))`.
  - Common random numbers: the customers depend only on the horizon, the demand, the root entropy, and i. Each row records `customer_inputs_sha256`.
  - Provenance records the numpy version, the Python version, and the bit generator (PCG64 locally).
- Reproducibility is claimed only under the recorded numpy version. Stream equality across numpy 2.2.6, 2.4.6, and the CI range below 2.3 is UNKNOWN.
- Aggregation is descriptive: `summarize_metric` (Student-t, `n_undefined`), explicit denominators, and `verdict: None`. There is no acceptance rule, no 0.75 rule, no employee-level threshold, and no cost.

## Shared-Queue Named Playback (2026-09-29)

- Phase 5B-4.5 is specified in `docs/superpowers/specs/2026-09-28-shared-queue-named-playback.md`. `simulation/shared_named_playback.py` replays and validates one regenerated named replication. It is not a second engine: it consumes the engine's customer trace and employee transitions, synthesizes nothing, rejects unknown events, and never repairs a trace.
- Named DES engine v3 (`novaq-shared-named-des-v3`) made two trace-only changes:
  - Every customer trace event records `employee_transitions_before`, the number of transitions recorded before it. The playback merges the two records by it and by nothing else.
  - Simultaneous DRAIN releases are recorded in employee_id order (approved). The engine had recorded them in X1 order (DISCREPANCY, fixed). X1 still decides who stays.
  - A comparison with `fd67bbf2` on 500 seeded runs showed identical customers, counts, queue, staffing, and employee intervals, shifts, and breaks.
- The event vocabulary is 5 customer types and 22 employee transition tuples, each reached on prescribed days. Two state-machine tuples are rejected because the named engine's closing inputs never produce them (INFERRED).
- Named replications method v2: `provenance.inputs_sha256` is the SHA-256 of canonical sorted JSON (floats as `float.hex()`) over the six input blocks, the closing policy, and the employee policy.
  - The seed and the code versions are recorded separately and checked exactly.
  - Equal digests mean equal recorded values only; the digest is not tamper-proof and not semantic equivalence.
- `playback_from_named_replications(run, i)` refuses when versions, the stored row's identity, the input digest, or the rebuilt inputs do not match. It then regenerates through the unchanged 5B-4.4 seed path and requires the regenerated row to equal the stored row exactly.
- Float sums are compared with the Phase 4 playback tolerance (rel 1e-9, abs 1e-12); times are always compared exactly. Reproducibility is still claimed only under the recorded runtime.
- Playback v2 (2026-09-29 hardening): the closing policy must be exactly `DRAIN` or `HARD_CUTOFF` (check `closing_policy`, the engine's `CLOSING_POLICIES` test behind a string test; never normalized or inferred from events), and a malformed trace value fails a check instead of raising. An engine timeline record naming an employee outside the timeline is still accepted (open, needs approval).
- Playback v3 (2026-09-29, resolves the item above): the run's input employees are the authoritative employee set (`evaluate_roster` reports every one, so they are the timeline's `state_totals` keys). Check `employee_identity` requires string timeline keys, requires every interval, shift, break, and closing input to name one of them exactly (case-sensitive, never normalized), and, in `prepare_named_playback`, requires the timeline's employees to equal the input employees. A result alone cannot tell an extra employee who copies an unrostered employee's records from a real one; only the input check can.

## Shared-Queue Named Attribution (2026-09-29)

- Phase 5B-4.6 is specified in `docs/superpowers/specs/2026-09-29-shared-queue-named-attribution.md`, approved by the product owner on 2026-09-29 as decisions D1-D8. `simulation/shared_named_attribution.py` (`novaq-shared-named-attribution-v1`) reports operational quantities per employee × shift × run from one named result's `employee_timeline` and the run's input employees.
  - It runs no simulation and changes no record.
  - It adds no aggregation across replications, no verdict, and no pay, overtime, or cost meaning (5B-5).
- The engine interval's `shift_index` is the shift's position in the input roster, unique across the roster. It is `None` exactly on OFF intervals. No interval crosses closing or its own shift's scheduled end. So attribution to a shift is exact, and the module checks these preconditions on every input.
- The after-closing and past-scheduled-end flags are independent. On-shift time falls into four disjoint cells (neither, after_closing_only, past_scheduled_end_only, both), and every field is summed directly from the intervals (D3). Subtraction and union formulas are reconciliation checks only. `past_scheduled_end_hours` equals the engine's `overrun`.
- Per break (D2):
  - `delay_from_scheduled_hours` is the engine's `delay` (from the roster start). It includes late split-shift activation, the minimum-gap push, and service.
  - `delay_from_due_hours` is `actual_start - due`, the part caused by the service under way.
  - `_total` means a sum across breaks only.
  - A completed break reports `shortened_hours` exactly 0.0 by P1. Configured minus actual is ±2.2e-16 on some completed breaks, so it is not computed by subtraction.
- Units are hours (D1); `configured_minutes` is the only source-unit field. `inputs_sha256` is `None`, because the full run inputs are unavailable (D4). The break `paid` flag is excluded (D5). There is no replication runner: regenerate through 5B-4.4, then attribute (D6).
- D7: a derived duration `x = a - b` with a nonnegative true value is reported as `x` when `x >= 0`. It is `0.0` when `a < b` and `math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)` (the playback tolerance applied to the operands). Otherwise the check `finite_nonnegative` fails. The tolerance is never used for event order or timing comparisons, which stay exact.
- Three checks are input-unreachable through validated paths but are retained, because the spec requires them and they fire when upstream validation is bypassed:
  - on-duty span;
  - closing partition;
  - base-state partition.
- Values beyond the float range must fail a check, not raise `OverflowError`. This was fixed in attribution. The protected playback `_time()` shows the same pattern; propagation is NOT TESTED, and it was not fixed in 5B-4.6.
- The seeded `SCENARIOS["stable"]` day is not a zero-attribution day (24 of 25 replications nonzero under each policy). Use `zero_arrivals` or a prescribed quiet day for zero cases.
