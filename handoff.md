# NovaQ Current Handoff

## Named Shared Queue release (2026-10-08; current)

The Named Shared Queue API/UI first slice is released. The step record is
`docs/superpowers/plans/2026-10-07-named-shared-queue-release-plan.md` §9.

- Backend: Render `srv-daiikrbm8hqs73d15rtg` runs `491a9d3` (owner Manual
  Deploy, live 2026-10-08 04:04 UTC). Same settings as below: 18 env keys,
  `RESULT_JSONB_MAX_BYTES=786432`, the same Start Command, Auto-Deploy and PR
  Previews Off. No migration ran; the database stays at `0005`.
- Frontend: Pages production `16a21277` (`main` `285b35e`, serving by 2026-10-08
  04:24:30 UTC, bundle `index-DxMbj5_C.js`). Automatic deployments were switched
  on for that one build and read back Disabled afterwards.
- `main` is `285b35ef` (`491a9d31` plus the docs-only release record).
- VERIFIED after release: `/api/ready` 200; R1 contract through the app
  returns `limits.result_max_bytes = 786432` and
  `max_expected_customers_per_run = 2900` (owner's logged-in read of
  analysis 6, 04:16 UTC); the Named view loads on analysis 17 and the legacy
  pages still return 200; no 5xx or traceback in the Render log. CI green on
  `491a9d31` (PR #28 run 37704686284; push run 37725205872, 11/11 each).
- Release backup: the scheduled `novaq-sched-20261007T141913Z` (owner choice).
- Rollback: Render `1c8e8de` (no database change needed), Pages `b7ac08c8`.
- Open:
  - The limits (9 replications, 52 segments, 24 employees, 48 shifts, 2,900
    expected customers per run) stay provisional and NOT PRODUCTION-APPROVED:
    the owner skipped the production timing run (W9), so production R3/R6
    time near 2,900 customers and the first request after a spin-down are
    NOT TESTED. Startup after the deploy took about 57 s.
  - Draft PR #28 (`ci/verify-491a9d31`) exists for CI only; never merge it.
  - Analyses 6 and 11 were archived by the owner on 2026-10-08 (intentional).
- Everything below in the G8 section still holds except its "current"
  backend and Pages deployment lines, which this section supersedes.

## G8 G-A release (2026-10-06)

G-A `2ccb86527a0f48928e4d5c26f3d9bd5f0e6abc35` is released. The full step
record is `docs/superpowers/plans/2026-10-05-g8-go-packet.md` §6; the
runbook is `docs/superpowers/plans/2026-10-05-g8-production-cutover-runbook.md`.

- Production state, VERIFIED 2026-10-06:
  - Supabase `cltvswcopkjvnonjutre` is at revision `0005`, applied 13:16 UTC
    with one-shot `alembic upgrade 0005` from a clean `2ccb8652` tree.
  - Row counts were unchanged by the migration.
  - RLS is on for all 10 public tables, with 0 table or routine grants to
    `anon`/`authenticated`.
  - The Data API is off.
- Backend: Render `srv-daiikrbm8hqs73d15rtg` runs `1c8e8de`: G-A `2ccb8652`
  plus the `event=` logging fix (`0ddefa6`) and the signed Pages ingress
  (`38fa998a`); the other commits in between are docs or frontend only.
  - The release first went live as `2ccb865` at 13:39 UTC on 2026-10-06.
  - The current deploy is `dep-db33kc2d0e5s73f0rf2g` (2026-10-07 12:27 UTC, same
    `1c8e8de`, redeployed after removing `FORWARDED_ALLOW_IPS`), with:
  - `NOVAQ_ENV=production`, so the G7 exact-head guard and `/ready` revision
    check are active;
  - `NOVAQ_PROXY_MODE=pages_signed` and `NOVAQ_PROXY_ASSERTION_SECRET` (also set
    in Pages): only requests signed by the novaq.site bridge are served;
    direct `onrender.com` API calls get 403 `proxy_assertion_required`
    (`/health`, `/ready` and OPTIONS are exempt). Rate limits key on the
    verified client IP;
  - no `FORWARDED_ALLOW_IPS` key (removed 2026-10-07 at the owner's request;
    unused under `--no-proxy-headers`);
  - 18 env keys (read back 12:28 UTC; `RESULT_JSONB_MAX_BYTES=786432` among
    them), auto-deploy off and PR previews off.
- The Start Command is migration-free and has no uvicorn access log:
  `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-proxy-headers --no-access-log`.
  - Each request is logged once, by the app's `event=http_request` line, which
    carries the path without the query string (and no client IP).
  - Ingress rollback: set `NOVAQ_PROXY_MODE=direct`, **re-add
    `FORWARDED_ALLOW_IPS=127.0.0.1`** (otherwise `direct` mode refuses Render's
    injected value at startup), drop `--workers 1 --no-proxy-headers`,
    redeploy; `direct` keeps the pre-ingress rate-limit keys. Record:
    `docs/superpowers/plans/2026-10-07-signed-pages-ingress-plan.md`.
  - Deploys never migrate. A future migration is a deliberate one-shot `alembic upgrade
  <rev>` from a clean checkout, as in GO packet W4. If the database is behind
  the code, the G7 guard refuses to start the app.
- Frontend: the G-A build went live on Cloudflare Pages as `2f88918f`
  (`main` `2ccb865`) at 14:09 UTC. The current Pages deployment is `b7ac08c8`
  (`main` `1c8e8de`, 2026-10-07 11:59 UTC, bundle `index-jBXJZ6bl.js`): the
  G-A app, the Comparison `<label for>` accessibility fix, the signing `/api`
  bridge (`frontend/functions/api/[[path]].ts`), and
  `frontend/public/_headers` (since `64e47b29`/`4feb6f8`), which sends an enforcing
  `Content-Security-Policy` equal to `nginx/production.conf`,
  `X-Frame-Options: DENY` and `Permissions-Policy` (VERIFIED 02:17 UTC).
  Production automatic deployments are disabled (read back 2026-10-07 after
  12:08 UTC). The previous deployment is `a4f60c31` (`574e1a9`, unsigned
  bridge); the pre-G-A rollback deployment is `a69cbebf` (`2d063c9`). The legacy Render
  static site stays suspended.
- Cloudflare Web Analytics is off, both on the Pages project and in the
  `novaq.site` site's Real User Measurements, because the CSP does not allow
  its beacon. Turning it back on would need a CSP change.
- Supabase "Enforce SSL on incoming connections" is ON (2026-10-06 ~17:10 UTC);
  a fresh-connection restart passed and `/ready` returned 200.
- Scheduled backups (since 2026-10-07): the Windows task "NovaQ daily backup"
  runs `output/g8-backup-tools/novaq_scheduled_backup.sh` in WSL daily at
  12:00 local (catch-up after missed runs, allowed on battery). Encrypted to
  the gpg public key `…F4DCFA84E2B2E617`, copied to
  `OneDrive/NovaQ-backups/scheduled` (30-day retention), status in
  `LAST_STATUS.txt`. Restore drill: `novaq_restore_check.sh` (passed
  2026-10-07, 10/10 table counts). The weekly Claude task "NovaQ weekly backup
  check" (Mondays) checks freshness, status and hash read-only. A WSL
  console window shows for about two minutes at each noon run (owner decision
  to keep it; a hidden start was tested and declined).
- Release backup: `20261006T125254Z`, gpg AES256 (passphrase of the manual
  script; its plaintext dump was shredded 2026-10-07), held in WSL `~/novaq-backups`
  and OneDrive `NovaQ-backups`. An isolated restore verified `0004` and the
  counts. The recovery target is the separate Supabase project
  `kjtkkdatiapmzcmhmlbp` (novaq-RECOVERY).
- Smoke test (Render logs): Google login, Analysis 6, calculations,
  Comparison, PDF, Excel and logout all returned 200, with no 5xx.
- SMTP test passed on 2026-10-06 at 15:28 UTC. A password reset for the
  owner's own account was REPORTED delivered. The request returned 200 with no
  delivery error, and reset token `259` was issued (GO packet §6).
- `event=` logging fixed and live (`0ddefa6`, `configure_event_logging` in
  `backend/api/main.py`).
  - Before it, the `novaq` loggers inherited root WARNING, so every INFO
    `event=` line was dropped.
  - CI #98 (37493271324) passed 11/11.
  - Render's logs now show UTC `event=http_request` and
    `event=password_reset_request` lines, verified 16:31 UTC.
  - Details: `docs/superpowers/plans/2026-10-06-api-event-logging.md`.
- Issue found in the window:
  - Render injects a `FORWARDED_ALLOW_IPS` value outside the dashboard keys,
    and the production validator refuses it. The first deploy therefore failed
    at startup, with no data effect.
  - The 2026-10-05 preflight had supplied the variable itself.
- Open:
  - GO packet §3 is closed (all four items fixed; GO packet §6).
  - Backups: a copy of the backup private key (fingerprint
    `B86C89C88962872B2515A2CCF4DCFA84E2B2E617`) off the owner's PC is not yet
    made; without it, losing the PC makes every backup undecryptable.
- `1fbe812c` (signed Pages ingress) was excluded from G-A and released
  separately on 2026-10-07 as the port `38fa998a`, without the client-version
  fence (PR #27, merged). Its branch `feat/signed-pages-ingress` and the
  `ingress-probe` worktree were removed afterwards (2026-10-07).
  - Draft PR #26 (`ci/verify-fcbc8db1`) was closed unmerged on 2026-10-06.
  - Its branch is kept at `1fbe812c` and still holds the unreleased fence
    commits `81bc427a` and `6ef85712`.
- Pushing `main` is a production release path: auto-deploys are off, but
  confirm both Render and Pages settings before any push.

Earlier G8 preparation (2026-10-04/05): the Option A policy is in
`docs/superpowers/specs/2026-10-04-g8-release-policy.md`, and the closure plan
is `docs/superpowers/plans/2026-10-04-g8-g-a-release-closure-plan.md`. Before
the release, Supabase had RLS off and 126 `anon`/`authenticated` grant rows.
The owner revoked those grants and enabled RLS on 2026-10-05, and turned the
Data API off.

Historical entries below describe their own dates and are not the current
release instruction.

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

Resolved after this feature landed: `evaluate_candidate_with_des` now returns the DES
`trace_events` and `trace_truncated` evidence for both FEASIBLE and INFEASIBLE measured
verdicts. The selected-plan endpoint therefore keeps real playback events for periods
above the utilization target; evaluator-level and endpoint regression tests cover it.

## Public Deployment: Cloudflare Pages + novaq.site (2026-09-24)

The public frontend moved from the Render static site to Cloudflare Pages; the Render API is unchanged.

Current verified state:

- Public URL: `https://novaq.site`. `https://www.novaq.site` returns a 301 to the same path and query on `novaq.site` (Cloudflare zone Single Redirect "Redirect from WWW to root"). `http://` upgrades to `https://`.
- Domain registered at Spaceship; nameservers are Cloudflare (`gail.ns.cloudflare.com`, `maxim.ns.cloudflare.com`). DNSSEC is off at Spaceship (it can be re-enabled later through Cloudflare).
- Cloudflare Pages project `novaq-frontend` builds `main` (root `frontend`, `npm run build`, output `dist`) and serves `novaq.site`, `www.novaq.site` and `novaq-frontend.pages.dev`. Every non-`main` branch gets a preview deployment; use the hash URL from the Deployments list (the branch alias URL returned 404).
- `/api` bridge: `frontend/functions/api/[[path]].ts` strips `/api` and forwards to the `NOVAQ_API_ORIGIN` Pages variable (`https://qcu-novaq-analytics.onrender.com`, set for Production and Preview). `frontend/public/_routes.json` limits the Function to `/api` and `/api/*`. See `docs/operations.md` "Cloudflare Pages frontend". Merged to `main` in `2d063c91`.
- Render API service `Qcu-NovaQ-Analytics`: the user set `PUBLIC_APP_URL` to `https://novaq.site` and added `https://novaq.site` to `ALLOWED_ORIGINS`. Neither environment-variable value was inspected directly. Observed externally only: a CORS preflight from the API accepts `https://novaq-frontend.onrender.com` and `https://novaq.site` and rejects `https://www.novaq.site`, `https://novaq-frontend.pages.dev` and an unrelated origin; the user reported that the password-reset email link opens `novaq.site`. `www` and `pages.dev` do not need to be allowed because the bridge makes API calls same-origin.
- Google OAuth client "NovaQ Web" authorized JavaScript origins: `http://localhost:5173`, `http://localhost`, `https://novaq-frontend.onrender.com`, `https://novaq-frontend.pages.dev`, `https://novaq.site`, `https://www.novaq.site`. Local Docker must be opened at `http://localhost`, not `127.0.0.1` (Google returns `origin_mismatch`).
- Verification: frontend 51 files / 350 tests, typecheck, lint and build passed; bridge e2e against the local Docker API (config, Google nonce, password login, session, CSRF-refused and CSRF-accepted logout, M/M/c, M/M/1 and Erlang-A outputs byte-identical to direct calls); live checks on `novaq.site` and `www` (pages, `/api` JSON, `Secure; HttpOnly` cookies, HTTPS). User confirmed password login, Google login, a calculation, logout and a password-reset email linking to `novaq.site`.

Open items:

- The Render static site `novaq-frontend` (`novaq-frontend.onrender.com`) is still live as a fallback. Suspend it after a few stable days; keep `Qcu-NovaQ-Analytics` running.
- Remote branch `feat/cloudflare-pages-api-bridge` is merged and can be deleted.
- Pages Functions are set to fail open: past the free 100,000 requests/day, `/api/*` would fall back to the SPA HTML.
- Pre-login rate limits key on client IP. Through the Worker, many users may reach Render from shared Cloudflare egress IPs, so they can share one auth bucket. Watch for 429s on login.

## Shared Queue Enhancement: Phase 1 Segment Foundation (2026-09-24)

Spec and plan:

- `docs/superpowers/specs/2026-09-24-shared-queue-segment-foundation.md`
- `docs/superpowers/plans/2026-09-24-shared-queue-segment-foundation-plan.md`

Current verified state:

- New pure module `backend/queueing_engine/services/shared_segments.py`. It keeps demand periods (λ, μ per hour) apart from staffing segments (c), in whole minutes inside one day. It rejects gaps, overlaps, out-of-order items, incomplete horizon coverage, and staffing segments that cross a demand boundary. A shorter staffing segment inherits its demand period's rates and is labelled `inherited_from_demand_period`. Each segment is evaluated through `select_model` (M/M/c, or M/M/1 when c = 1), with duration-weighted arrivals, server-hours, offered work, and steady-state waiting customer-hours. Unstable, no-capacity, and failed segments report `None`, never 0.
- Nothing imports it yet (a test enforces this). No API, schema, database, frontend, report, legacy shared DES, or separate-queue code changed.
- Verification: `tests/test_shared_segments.py` has 50 tests, including independent Erlang-B references, exact textbook cases, and the NovaMart 14-day rows. An in-memory mutation check confirmed that five deliberate faults are caught. Backend 1083 passed, 3 skipped, 1 xfailed (the 1033 baseline plus 50). Ruff and mypy are clean. The frontend was not re-run because it was untouched.
- Next (needs approval): Phase 2 dynamic capacity optimization. Workforce inputs, transition and closing policies, and model scope beyond M/M/c remain open decisions.

## Shared Queue Enhancement: Phase 2 Capacity Optimization (2026-09-24)

Spec and plan:

- `docs/superpowers/specs/2026-09-24-shared-queue-capacity-optimization.md`
- `docs/superpowers/plans/2026-09-24-shared-queue-capacity-optimization-plan.md`

Current verified state:

- Pre-Phase 2 review fix `ad8ed236`: segment rows now state `waiting_attribution` and `backlog_represented: false`. The zero-demand and closed notes say that backlog from earlier segments is not represented, and the textbook reference case states its full λ, μ, and c. No value changed.
- New pure module `backend/queueing_engine/services/shared_capacity.py`. For each staffing segment it evaluates every server count in [min, max] through the Phase 1 `evaluate_segment`, and costs each over the segment's duration:
  - server cost = c × server cost per hour × T;
  - waiting cost = λ × Wq × T × waiting cost per customer-hour, with Wq in hours.
  It enforces stability, the utilization ceiling, and the optional maximum wait, all with the 1e-9 `THRESHOLD_TOLERANCE`. It picks the cheapest feasible count; ties within a relative 1e-9 go to fewer servers. Closing (c = 0) is possible only when `min_servers` = 0 and nobody arrives. Undefined costs stay `None`, and totals and the cost change are withheld with a reason. The module holds no operating defaults; the caller supplies every cost, target, and bound. Every candidate, the configuration, and the inputs are kept as provenance.
- Nothing legacy imports either new module; a test enforces this. The legacy optimizer, `/optimize` and `/optimize/batch`, scenario schema versions, Decision, reports, the legacy shared DES, and all separate-queue code are unchanged.
- Verification: `tests/test_shared_capacity.py` has 28 tests, covering hand-computed costs, an exact 14.5/14.5 tie, float noise at the target, the max-wait boundary, zero demand and zero capacity, unstable and infeasible segments, duration scaling, a brute-force optimum from an independent Erlang-B recursion, and agreement with the legacy optimizer's `c_optimal`, `cost_optimal`, and `cost_current` on the NovaMart 14-day average (plan 2,3,3,3,3,4,3,4,4,3,3,2,2 = 39 server-hours versus 55 current). An in-memory mutation check confirmed that seven deliberate faults are caught. Backend 1112 passed, 3 skipped (Postgres migration chain), 1 xfailed. Ruff and mypy are clean.
- Next (needs approval): Phase 3 workforce scheduling. It is blocked on workforce inputs (availability, shift lengths, break rules, labor cost) and on the transition, closing, and sequential-versus-joint decisions.

## Shared Queue Enhancement: Phase 3 Continuous Shared DES (2026-09-24)

The product owner renumbered the phases: Phase 3 is now the continuous DES, and workforce scheduling moves later.

Spec and plan:

- `docs/superpowers/specs/2026-09-24-shared-queue-continuous-des.md`
- `docs/superpowers/plans/2026-09-24-shared-queue-continuous-des-plan.md`

Current verified state:

- New pure module `backend/queueing_engine/simulation/shared_continuous_des.py`. It is one event-driven run over the whole horizon, with no restart, warm-up, or reset at boundaries.
  - Arrivals: Poisson with the demand period's λ, exact by memorylessness.
  - Service: each customer carries unit work Exp(1), drawn once. Service lasts work / μ, with μ from the period in which service starts, and is never redrawn or interrupted.
  - One common first-come-first-served line; the lowest free server number serves first.
  - Capacity decreases close idle servers first and then drain busy ones (no new customer; close at completion). Increases reactivate draining servers before opening others.
  - Same-time order: completions, then capacity changes, then arrivals.
  - Customers keep their ids and waits for the whole run. Conservation is reported, and so are capacity transitions, drain records, and server-hours above schedule.
  - Seeds come from numpy `SeedSequence` with two streams; unseeded runs record their entropy.
  - `simulate_prescribed` runs exact deterministic cases. `staffing_from_capacity_result` feeds a complete Phase 2 plan to the DES.
- Tolerance policy: the new pipeline uses `THRESHOLD_TOLERANCE` (1e-9), the same constant `is_saturated` applies. It is stated in the Phase 2 provenance and pinned by a test. The legacy optimizer keeps its 1e-12.
- **Closing policy is UNRESOLVED.** The engine observes the horizon only and reports customers still waiting or in service at the end. Nobody is served after closing, and nobody is removed. The separate-queue day drains after closing, but that is not approved for shared queues.
- Nothing legacy imports the module; the isolation test covers it. The legacy shared DES, separate-queue code, APIs, scenarios, Decision, and reports are unchanged.
- Verification:
  - `tests/test_shared_continuous_des.py` has 49 tests: exact hand-computed cases (increase, decrease with drain, idle-first closing, zero capacity with backlog, zero demand with backlog, same-time ordering in both directions, a μ change, the horizon end), sample-path identities (∫queue = Σ waits; busy hours = Σ service), conservation, identity and first-come-first-served order on 20 seeded multi-transition runs, reproducibility, and statistical checks.
  - The Erlang C benchmark (λ 40, μ 20, c 3, 100 × 24 h, 95,670 customers) fell within 1.05 standard errors on Lq, P(wait), and Wq.
  - A source-level mutation check caught 9 of 9 faults after one ordering test was strengthened.
  - Backend 1162 passed, 3 skipped, 1 xfailed. Ruff and mypy are clean.

## Shared Queue Enhancement: Phase 3A Closing Policy and Day Cost (2026-09-25)

Spec and plan:

- `docs/superpowers/specs/2026-09-25-shared-queue-closing-policy.md`
- `docs/superpowers/plans/2026-09-25-shared-queue-closing-policy-plan.md`

The product owner approved the closing policy on 2026-09-25. It replaces the Phase 3 UNRESOLVED state.

Current verified state:

- `simulation/shared_continuous_des.py` (engine `novaq-shared-continuous-des-v2`): `simulate_prescribed` and `simulate_shared_day` require `closing_policy` (`DRAIN` or `HARD_CUTOFF`); there is no default. Events before closing are unchanged from Phase 3.
  - At closing, completions at exactly that time are processed first. The at-close state is recorded: waiting customers, customers in service, and accepting and draining servers.
  - HARD_CUTOFF: waiting customers become `unserved_at_close` (`hard_cutoff`). Services already under way finish, and nobody starts service at or after closing.
  - DRAIN: the accepting servers on duty serve the line first come, first served, with no cap. Services that start after closing use the final demand period's μ. A draining server only finishes its own customer. With nobody on duty, waiting customers become `unserved_at_close` (`no_eligible_server`), so draining cannot run forever. The engine asserts that every customer is resolved and every server closed.
  - Outputs: statuses are `departed` and `unserved_at_close`. The `closing` block replaces `horizon_end` and reports overrun, after-close server-hours, and after-close waits. `cost_quantities` holds hours and counts only. Events at or after closing carry `segment_id: None`. In-horizon keys keep their Phase 3 meaning.
- New `services/shared_day_cost.py`: `DayCostRates` takes four required rates, and `None` means not supplied. `cost_shared_day` computes regular server-hours × rate + overtime server-hours × rate + waiting customer-hours × rate + unserved count × rate. The unserved term applies only when `unserved_possible` (HARD_CUTOFF, or DRAIN with 0 servers in the final segment). A missing applicable rate withholds the total with a reason; it is never replaced by 0. Server-hours are modeled capacity hours, not necessarily paid employee-hours.
- Nothing legacy imports either module; the isolation test now covers the cost module too. The legacy shared DES, separate-queue code, APIs, scenarios, reports, config rates, and frontend are unchanged.
- Verification:
  - `tests/test_shared_continuous_des.py` grew from 49 to 111 tests.
    - Every Phase 3 exact case now runs under both policies and must agree.
    - New exact closing cases: an empty system; waiting customers under both policies; a completion exactly at closing; a server draining at closing; a zero-capacity final segment under both policies; a backlog from a zero-capacity period; an increase just before closing; the final-μ rule; arrivals stopping at closing; and a required, validated policy.
    - Whole-run sample-path identities, including overtime = service time after closing.
    - Cross-policy equivalence before closing on 40 seeded multi-transition runs.
    - An independent first-come-first-served recursion from the at-close state agrees on 30 seeded overloaded runs (every run closes with a line; 5 of 15 per policy with a draining server; 144 after-close starts under DRAIN).
    - The Erlang C benchmark passes under both policies.
  - `tests/test_shared_day_cost.py` has 16 tests: hand totals (DRAIN 255, HARD_CUTOFF 247.5 at rates 80, 120, 100, 50), missing and zero rates, the applicability rule, invalid rates, no defaults, and no config import.
  - A source-level mutation check caught 14 of 15 faults. The miss, a max-queue update after closing, is an equivalent mutant: the line cannot grow after closing.
  - Backend 1240 passed, 3 skipped, 1 xfailed (1162 + 78 new). Ruff is clean. `mypy .` reports 5 errors, all in the gitignored, untracked `outputs/technical-paper/build_chapters_4_5.py` (last modified 2026-09-20, imports only docx, matplotlib, and pandas). `mypy . --exclude '^outputs/'` is clean on 157 files. Frontend not run: nothing under `frontend/` changed.
- Next (needs approval): Phase 4. Monte Carlo and playback have not started.

## Shared Queue Enhancement: Phase 4 DES Replications and Event Playback (2026-09-25)

Spec and plan:

- `docs/superpowers/specs/2026-09-25-shared-queue-des-replications-playback.md`
- `docs/superpowers/plans/2026-09-25-shared-queue-des-replications-playback-plan.md`

Current verified state (backend only; no API, frontend, Decision, Report, scenario, or workforce change):

- Engine (`simulation/shared_continuous_des.py`): the random draws moved into `_draw_arrivals`, and `simulate_shared_replication(seed_sequence=...)` was added. `simulate_shared_day` output is byte-identical: a SHA-256 digest of 100 runs (2 policies × 25 seeds × 2 configurations) is unchanged.
- New `simulation/shared_replications.py`, `run_shared_replications(...)`:
  - Every replication runs the Phase 3A continuous DES over the whole horizon with the scenario's own rates. No ±20%/±10% perturbation is applied.
  - `replications` (1..`config.MC_MAX_TRIALS`), `seed`, and `closing_policy` are required. Replication i uses `SeedSequence(entropy=root_entropy, spawn_key=(i,))`.
  - Each replication keeps one scalar row (traces off):
    - customers: arrivals, served, and unserved;
    - waits: the sum and mean over served customers;
    - waiting-hours before and after closing, and the in-horizon time-average queue and maximum;
    - busy and available server-hours in the horizon and after closing (overtime);
    - scheduled hours and hours above schedule;
    - utilization with explicit denominators, and overrun;
    - cost per replication and criterion outcomes, when supplied.
  - Aggregates:
    - Student-t 95% intervals, matching the separate-queue `_summarize_metric` convention, with `n_undefined` counts;
    - the mean of replication mean waits and the customer-weighted wait, with numerator and denominator;
    - summed customer totals and descriptive outcome counts;
    - cost aggregated from per-replication costs; the total is withheld when an applicable rate is missing.
  - `FailureCriteria` (mean wait, utilization, unserved, and overrun) has no default thresholds. Per-criterion and combined proportions carry Wilson intervals with numerator, denominator, and not-evaluable counts. `verdict` is always `None`, because no approved pass/fail rule exists.
- New `simulation/shared_playback.py`: `prepare_shared_playback` and `playback_from_replications` regenerate one identified replication with its full trace.
  - Events are the engine's own trace.
  - An independent replay checks FCFS, legal server transitions, queue length at every event, schedule after staffing changes, the closing phase, and final resolution.
  - The replay recomputes timelines, counts, and time integrals and compares them with the engine. `playback_from_replications` also requires exact equality with the stored replication row and the same engine version.
  - Queue entry and departure are represented by the `arrival` and `service_end` events; the engine has no separate events for them.
- Nothing legacy imports these modules; the isolation test covers both.
- Verification:
  - `tests/test_shared_replications.py` has 46 tests:
    - every replication matches a recomputation from customer rows and transition intervals (both policies, including 0 servers at closing);
    - reproducibility and recorded entropy;
    - distinct, regenerable streams and uncorrelated counts (400 replications);
    - a Poisson dispersion index near 1 (no perturbation);
    - waiting-time denominators by hand;
    - intervals matching `scipy.stats.t.interval`, the separate-queue convention, and `binomtest(...).proportion_ci(method="wilson")`;
    - per-replication and aggregate cost;
    - missing rates, criteria counts, not-evaluable counting, the tolerance boundary, and validation;
    - Erlang C within 4 SE (λ 40, μ 20, c 3; 60 × 24 h).
  - `tests/test_shared_playback.py` has 21 tests:
    - an exact hand-computed playback, and events equal to the engine trace;
    - 72 regenerated replications equal their stored rows (3 configurations × 2 policies);
    - reproducibility;
    - six tampered event streams, each rejected for its intended reason;
    - mismatched rows, foreign engine versions, and invalid requests refused.
  - Fault injection caught 15 of 15 faults.
  - Backend 1307 passed, 3 skipped, 1 xfailed (1240 + 67 new; all 16 separate-queue test files included). The run's 6 h 29 min wall time includes a system sleep from 01:44 to 06:02. Ruff is clean. `mypy . --exclude '^outputs/'` is clean on 161 files; the gitignored `outputs/technical-paper/build_chapters_4_5.py` errors from Phase 3A remain. Frontend not run: nothing under `frontend/` changed.
- Not implemented: a parameter-uncertainty experiment, an acceptance (PASS/FAIL) rule, production API endpoints, the frontend player, Decision and Report integration, and workforce scheduling. Each needs approval.

## Shared Queue Enhancement: Phase 5B-1 Workforce Foundation (2026-09-26)

Spec and plan:

- `docs/superpowers/specs/2026-09-26-shared-queue-workforce-foundation.md`
- `docs/superpowers/plans/2026-09-26-shared-queue-workforce-foundation-plan.md`

Phase 5A (2026-09-25) was a read-only design report delivered in chat. Its decisions D1-D16 remain open.

Current verified state (one pure module; no solver, DES, cost, API, schema, scenario, frontend, Decision, or Report change):

- New `services/shared_workforce.py`:
  - Inputs:
    - `Employee`: a pseudonymous id, availability windows, and `EmployeePay` (regular rate, overtime rate, daily regular paid minutes). Every pay value may be `None` (not supplied) and is never read as 0.
    - `ShiftRules`: boundaries, length range, boundary granularity, maximum shifts, and rest between shifts (required only when split shifts are allowed).
    - `BreakRule` / `BreakRequirement`: a length range, a minimum gap, and named breaks with a duration, an explicit paid flag, and start-offset windows.
    - `WorkforceRules.register_count`.
    - A roster of `ScheduledShift` / `ScheduledBreak`. Break length and paid status come from the rule.
  - Validation:
    - Malformed inputs raise `SharedSegmentError` with every problem listed.
    - Roster rule breaches are returned as 17 coded violations with reasons. Status is INVALID, INCOMPLETE (missing pay values or break-rule coverage), or COMPLETE.
    - Hours are withheld, not guessed, for an employee whose time has no well-defined active/break split: overlapping shifts or breaks, a break outside its shift, or an unknown break length.
  - Outputs, all scheduled (not simulated):
    - scheduled, paid, break (paid and unpaid), and active server minutes (split inside and outside the horizon);
    - regular and overtime paid minutes, with the overtime start minute;
    - active-server steps, the register check, and coverage shortfall and surplus against optional required staffing segments.
  - No cost, no optimized roster. Registers are counted, not identified.
- Nothing legacy imports the module; the isolation test covers it. The separate-queue staff and break sheets, lane breaks, and pre-break cutoff are not used.
- Verification:
  - `tests/test_shared_workforce.py` has 53 tests on labeled synthetic data:
    - hand-computed hours, overtime start, steps, register intervals, and coverage;
    - split shifts;
    - four threshold edges;
    - every violation code with its exact code list;
    - malformed employees, rules, roster, and staffing;
    - identities and an independent minute-by-minute brute force (active count, coverage, register check, active minutes, and overtime start) on 200 generated rosters.
  - A first fault-injection pass caught 10 of 12 faults. The two misses exposed missing tests (an overtime-start boundary and a too-late break); after adding them, 12 of 12 were caught.
  - Backend 1360 passed, 3 skipped, 1 xfailed (1307 + 53; all 16 separate-queue test files included). Ruff is clean. `mypy . --exclude '^outputs/'` is clean on 163 files. Frontend not run: nothing under `frontend/` changed.
- Next (needs approval): Phase 5B-2 and later (sequential and integrated MILP, named-server DES, workforce cost), plus the open Phase 5A decisions.

## Shared Queue Enhancement: Phase 5B-2 Sequential Rostering MILP (2026-09-26)

Spec and plan:

- `docs/superpowers/specs/2026-09-26-shared-queue-sequential-rostering.md`
- `docs/superpowers/plans/2026-09-26-shared-queue-sequential-rostering-plan.md`

Product-owner decisions (2026-09-26):

- Sequential only: Phase 2's selected server counts are a hard coverage target, solved with `scipy.optimize.milp` (HiGHS). No dependency was added.
- Break starts lie on a caller-supplied clock grid, `break_start_granularity_minutes`, with no default.
- Surplus is counted and paid only through wages. There is no surplus rate.
- Solver limits are required inputs with no defaults: time limit, `mip_rel_gap`, and a pattern cap.

Current verified state (one pure module; no DES, cost-integration, API, schema, scenario, frontend, Decision, or Report change):

- New `services/shared_rostering.py`:
  - Patterns: every 5B-1-valid single shift with its breaks on the break grid. Generation stops with `PATTERN_LIMIT_EXCEEDED` rather than truncating.
  - MILP:
    - a binary choice per pattern;
    - on every elementary interval, which is exact in continuous time: active ≥ required inside the horizon, and active ≤ registers all day;
    - maximum shifts per employee, and interval-clique rows for split-shift rest;
    - exact regular and overtime: a per-pattern cost with one shift a day, and a big-M binary switch for split shifts;
    - a wages-only objective.
  - `INCOMPLETE`, with nothing solved and no cost invented, when an admissible shift length has no break rule, or when the objective needs a missing pay value. The overtime rate is needed only when an admissible plan exceeds the threshold, found by an exact maximum-paid recursion.
  - Certificates before solving: a requirement above the registers, and fewer available employees than required in an interval.
  - Statuses: `OPTIMAL`, `FEASIBLE_NOT_PROVEN_OPTIMAL`, `NO_SOLUTION_FOUND`, `INFEASIBLE`, `INCOMPLETE`, `PATTERN_LIMIT_EXCEEDED`, `SOLVER_ERROR`, `VERIFICATION_FAILED`.
  - Feasibility is FEASIBLE only after exact verification:
    - integrality within 1e-6;
    - every row holds in integer arithmetic;
    - 5B-1 `evaluate_roster` finds no violation, shortfall, or register excess;
    - the labor cost from the 5B-1 minutes equals the model objective.
  - Solver status, message, objective, dual bound, gap, nodes, wall time, options, unchanged HiGHS defaults, and versions are reported. Uniqueness is `NOT_ESTABLISHED`.
  - `optimize_roster_for_capacity_plan` takes a Phase 2 plan through `staffing_from_capacity_result`.
- Nothing legacy imports the module; the isolation test covers it.
- Verification:
  - `tests/test_shared_rostering.py` has 88 tests on labeled synthetic data:
    - all 12 required areas;
    - an independent brute force (minute loops plus the 5B-1 oracle) for pattern-set equality and optimal-set membership;
    - 40 seeded random instances;
    - a Phase 2 plan as the target;
    - simulated solver terminations.
  - Fault injection caught 22 of 22 faults, after 3 missing tests were added.
  - Ruff is clean. `mypy . --exclude '^outputs/'` is clean on 165 files.
  - The full backend suite, `python -m pytest tests/ -x`, gave 1448 passed, 3 skipped, and 1 xfailed. That run includes every Separate Queue test file.
- Scale, on this machine with synthetic employees and the NovaMart Phase 2 plan as the target:
  - an 8-employee, 13-hour day is proven optimal in 1.9 s with a 60-minute break grid and in 19.7 s with a 30-minute grid;
  - a 15-minute grid gives 62,568 patterns and no solution within 180 s.
  - Solve time on real inputs is UNKNOWN.
- Next (needs approval):
  - 5B-3 integrated MILP;
  - 5B-4 named-employee DES;
  - 5B-5 workforce cost integration;
  - DES validation of rosters, and an acceptance rule;
  - a formulation that scales to fine break grids.

## Shared Queue Enhancement: Phase 5B-3 Integrated Planning MILP (2026-09-28)

Spec and plan:

- `docs/superpowers/specs/2026-09-28-shared-queue-integrated-planning.md`
- `docs/superpowers/plans/2026-09-28-shared-queue-integrated-planning-plan.md`

Product-owner decision (2026-09-28), capacity semantics "every interval":

- The analytical server count is the number of employees on duty on every elementary interval between shift, break, demand-period, and staffing-segment boundaries.
- Each interval is Phase 1/2's stationary M/M/c evaluation, with its demand period's λ and μ, over its own length.
- Waiting cost = Σ waiting rate × λ × Wq(c) × hours. Stability, the utilization target, and the maximum wait are checked on every interval.
- Staffing segments only group the report.
- The short-interval steady-state approximation is disclosed in the output.

Current verified state (one pure module; no DES, API, schema, scenario, frontend, Decision, or Report change; the 5B-2 sequential optimizer is unchanged):

- New `services/shared_integrated.py`:
  - The objective is scheduled wages (5B-1 regular and overtime minutes at the employee's rates) plus analytical waiting cost. Phase 2's server cost per server-hour is never charged. Every employee on duty is paid and staffs the queue, so surplus is never hidden.
  - The model is 5B-2's `_build_model`, built with zero-requirement pieces. It keeps the pattern columns, register rows, max-shift and split-shift rows, and exact regular and overtime cost. On top of it, for every in-horizon elementary interval i and every admissible count c, it adds:
    - a binary `z[i,c]`;
    - the link row `Σ_q a[q,i] x_q − Σ_c c z[i,c] = 0`;
    - the choose-one row `Σ_c z[i,c] = 1`.
    Admissible counts lie in [min_servers, min(max_servers, registers)] and pass Phase 2's `evaluate_candidate` rule.
  - `PlanningConfig` has no defaults: waiting rate, target, maximum wait, and minimum and maximum servers. A missing waiting rate gives `INCOMPLETE` when some in-horizon λ > 0, never 0.
  - Certificates before solving:
    - `NO_ADMISSIBLE_CAPACITY`, which needs no patterns;
    - `INSUFFICIENT_WORKFORCE`, only with a complete pattern set.
    HiGHS status 2 gives `SOLVER_PROVED_INFEASIBLE`.
  - Statuses are as in 5B-2. A time limit without a solution is `NO_SOLUTION_FOUND` with UNKNOWN feasibility, never INFEASIBLE.
  - Feasibility is FEASIBLE only after exact verification:
    - integrality;
    - every row and bound in integer arithmetic;
    - no 5B-1 violation or register excess;
    - the selected count equals the 5B-1 on-duty count on every interval;
    - the independent `evaluate_planning_cost` places the roster in the feasible set;
    - R/O minutes match;
    - wages and waiting match the model's terms within a relative 1e-9.
  - `evaluate_planning_cost` prices any roster exactly without the MILP and states whether it is in the integrated feasible set.
  - `compare_with_sequential` runs Phase 2 and then 5B-2, and prices both rosters on the same objective. "Integrated no worse" is claimed only when the sequential roster is in the integrated feasible set.
- Nothing legacy imports the module; it joins the isolation list in `tests/test_shared_segments.py`.
- Verification:
  - `tests/test_shared_integrated.py` has 93 collected tests (43 test functions, with parametrization and 40 seeds) on labeled synthetic data:
    - an independent brute force: 5B-2 test enumeration, a minute-by-minute on-duty count, Phase 1 tests' Erlang-B recursion, and its own wage arithmetic;
    - hand-computed optima, including two tied rosters;
    - all 10 required verification points;
    - the comparison logic;
    - 40 seeded random instances;
    - simulated solver terminations and corrupted vectors.
  - Fault injection (28 mutants of the formulation, the verification, the evaluation, and the comparison; scratch script, not committed) caught 28 of 28, after 4 tests and 1 assertion were added. One mutant, register-capped candidate counts, changed only the certificate's reported counts; an assertion now pins them.
  - Ruff is clean. `mypy . --exclude '^outputs/'` is clean on 167 files.
  - The full backend suite, `python -m pytest tests/ -x`, gave 1541 passed, 3 skipped, and 1 xfailed (the 1448 baseline plus 93 new tests). That run includes every Separate Queue test file.
  - `git status` shows no change to any existing backend source file. The only existing test change is one line in `tests/test_shared_segments.py`, which adds the module to the isolation list.
- Benchmark (not a test): NovaMart 14-day-average λ and μ rows (`NOVAMART_AVERAGE_ROWS`); synthetic employees, pay, shift and break rules, and registers (the 5B-2 probe set: 8 employees, 05:00-18:00, 4 registers); waiting 100 per customer-hour, target 0.70, servers 1-24, Phase 2 server cost 94.375 per hour; time limit 300 s; mip_rel_gap 0. Phase 2 selected [2, 3, 3, 3, 3, 4, 3, 4, 4, 3, 3, 2, 2] servers per hour. The comparison prices both rosters with the same exact evaluator.
  - Grid 60 (5,424 patterns):
    - Integrated: OPTIMAL (HiGHS status 0, gap 0) at 3759.24 = wages 3206 + waiting 553.24, in a 4.7 s solve.
    - Sequential: 5B-2 OPTIMAL at wages 3307, which is 3828.02 on the planning objective.
    - The sequential roster is in the integrated feasible set, so the integrated plan is no worse, by 68.77.
  - Grid 30 (19,528 patterns):
    - Integrated: OPTIMAL at 3670.78 = 3047 + 623.78, in 96.5 s.
    - Sequential: OPTIMAL at wages 3124, in 34.4 s. That is 3684.31 on the planning objective.
    - The integrated plan is no worse, by 13.54.
  - Grid 15 (62,568 patterns; integrated model 62,670 columns, 158 rows, 3,306,228 nonzeros): no solution within the 300 s limit, integrated or sequential.
    - Both runs are `NO_SOLUTION_FOUND` with feasibility UNKNOWN, and nothing is compared.
    - The integrated `milp` call returned after 342.4 s, 42 s over the limit; the cause of the overrun is UNKNOWN.
  - Integrated on-duty counts differ from Phase 2's. For example, at grid 60 the count is 2-3 in 06:00-07:00, where Phase 2 selected 3, and 3-4 in 07:00-10:00, where Phase 2 selected 3.
  - The grid-60 optimum is above the grid-30 optimum. That is consistent with the grid-60 patterns being a subset of the grid-30 patterns (INFERRED from the grid definition).
  - Runtimes depend on the machine and its load. The 5B-2 grid-30 solve is recorded at 19.7 s in the 5B-2 section, took 27.6 s in the 15-minute investigation, and took 34.4 s here.
- 15-minute-grid investigation (5B-2 sequential model, same benchmark):
  - The model is 58 rows × 62,568 binary columns with 1,684,296 nonzeros, built in about 5 s.
  - The LP relaxation alone is optimal at 3006.7 in 16.3 s of HiGHS time.
  - MIP with presolve:
    - Presolve ran from 3 s to 187 s. It made only the reductions (1,008 columns, 21,960 nonzeros) that the LP presolve made in 7 s.
    - The root started at 199.7 s, and each root cut round took about 5-10 s.
    - At 303 s there were 0 nodes and no incumbent (dual bound 3007).
  - MIP without presolve: feasibility jump found 3582 at 12.8 s. At the limit the root cut loop was still running, with 0 nodes and a 16.05% gap.
  - The time therefore goes to MIP presolve and then the root cut loop, not to the LP or the build.
  - Which presolve rule takes the time is UNKNOWN. SciPy's HiGHS options reject `presolve_rule_logging`, and `highspy` is not installed and was not added.
  - The grid-30 patterns are a subset of the grid-15 patterns, so the grid-15 optima are at most the grid-30 optima (INFERRED, not solved).
  - No constraint was changed. PROPOSED only:
    - an exact formulation with implicit break placement;
    - dropping the in-horizon register rows of the integrated model. The link and choose-one rows already imply them, since every admissible c ≤ registers. That preserves the feasible set; the runtime effect is UNKNOWN. The link rows repeat the pattern coefficients of those rows, which is why the integrated model has about twice the nonzeros.
- Next (needs approval):
  - 5B-4 named-employee DES;
  - 5B-5 workforce cost integration;
  - DES validation of rosters, and an acceptance rule;
  - a formulation that scales to fine break grids;
  - API and UI exposure.

## Shared Queue Enhancement: Phase 5B-4.0 Anonymous-Engine Pin and 5B-4.1 Named-Employee DES Policy Contract (2026-09-28)

Spec and plan:

- `docs/superpowers/specs/2026-09-28-shared-queue-named-employee-des-policy.md`
- `docs/superpowers/plans/2026-09-28-shared-queue-named-employee-des-policy-plan.md`

Product-owner approval (2026-09-28): "The Phase 5B-4A design is approved using P1–P9 and X1–X7 exactly as supplied by the user." The 5B-4A design was a chat report, and this spec is its first repository record.

- Single rules in the design are APPROVED SPECIFICATION.
- Where the design offered alternatives or open questions, the approval did not choose, so the selection is UNKNOWN with no default:
  - P1, P2, P5, P7, X1, and X5 have unselected alternatives;
  - P3, P4, P6, P8, P9, and X6 have open sub-questions.

  The spec's "Open selections" table maps each to the sub-phase it blocks.
- X7 is mandatory: the named DES takes `required_staffing` as a required input with no default, validated by `validate_timeline`, never empty and never optional.

Current verified state (tests and docs only; no production code change):

- 5B-4.0 (implemented):
  - `tests/test_shared_continuous_des_pin.py` and `tests/fixtures/shared_continuous_des_output_pin.json` pin the complete result dictionary of the anonymous engine's `simulate_prescribed`, key by key with exact equality, on 7 fixed-arrival cases:
    - the main transitions case under DRAIN, under HARD_CUTOFF, and under DRAIN with a trace cap of 7;
    - "no one on duty at closing" under both policies;
    - "no arrivals" under both policies.
  - No seed and no random number are used, and every input is binary-exact.
  - The expected values are the engine's output at `d5723aba` (a characterization). The main case's schedule, transitions, at-close state, and overrun were also derived by hand, and one test asserts that derivation without the fixture.
  - The existing 34 hand-computed test functions (111 collected) in `tests/test_shared_continuous_des.py` are unchanged; the pin adds whole-output coverage.
  - `shared_continuous_des.py` is unchanged.
- 5B-4.1 (documented, not implemented):
  - the employee state machine, capacity definitions, transition rules, invariants 1-14, and the proposed interface;
  - Separate Queue break code is protected and is not reused;
  - the numpy pins CONFLICT (`requirements.txt` <2.3, lock 2.4.6, production lock 2.2.6, local 2.4.6), and cross-version RNG equality is UNKNOWN;
  - the named engine adds no random process, and test reference values come from prescribed arrivals.
- No named-employee DES exists, and `shared_named_des.py` was not created.
- Verification:
  - The new pin file has 9 tests, all passing.
  - Fault injection (15 source-level mutants of an in-memory engine copy; scratch script, not committed): 15 of 15 caught, and the unmutated copy matched.
  - The focused shared anonymous-engine suites gave 254 passed.
  - Ruff is clean. `mypy . --exclude '^outputs/'` is clean on 168 files.
  - The full backend suite, `python -m pytest tests/ -x`, gave 1550 passed, 3 skipped, and 1 xfailed (the 1541 baseline plus 9 new tests). That run includes every Separate Queue test file.
  - `git status` shows no change to any existing backend source file or existing test.
- Next (needs approval): the open selections in the spec, then 5B-4.2 (employee timeline state machine). Superseded: 5B-4.2 is done (next section).

## Shared Queue Enhancement: Phase 5B-4.2 Pure Named-Employee State Machine (2026-09-28)

Spec and plan:

- `docs/superpowers/specs/2026-09-28-shared-queue-employee-state-machine.md`
- `docs/superpowers/plans/2026-09-28-shared-queue-employee-state-machine-plan.md`

The Phase 5B-4.2 request approved P1-P9 and X1-X7 and supplied explicit decisions (quoted in the policy spec, "Explicit decisions of 2026-09-28"):

- P1 (a): a delayed break keeps its full duration from its actual start, and a delay pushes later breaks by the minimum gap.
- No pre-break cutoff and no pre-shift-end cutoff; service is non-preemptive.
- A later split shift activates at its actual release plus the required rest.
- P4: registers are identified 1..K; the wait order is earliest wait start, then employee_id; the lowest-numbered free register is assigned first.
- P5-P7 must be representable without a selection.
- Base states are mutually exclusive, and attributes add no elapsed time.

Current verified state:

- `backend/queueing_engine/simulation/shared_employee_states.py` (new) is the employee, break, shift, and register timeline of a validated 5B-1 roster (X4 precondition).
  - Seven mutually exclusive base states, with identified registers and the X2 employee-only same-time order.
  - `hold_past_shift_end` is required, with no default.
  - The closing inputs `Release`, `EndBreakAtClosing`, and `CancelPendingBreaks` represent every P5, P6, and P7 alternative without choosing one.
  - There are no customers, queue, service-time generation, or random numbers. Service starts and completions are caller inputs.
- No existing production module changed. `tests/test_shared_segments.py` adds the module to the isolation list.
- The policy spec was updated first:
  - the decisions of 2026-09-28;
  - the undetermined cases;
  - the withdrawn capacity bound (below).
- Tests: `tests/test_shared_employee_states.py` (new, synthetic, binary-exact).
  - 33 test functions with hand-computed timelines cover every required case.
  - An independent checker of invariants 1-16 runs on every successful run.
  - The invariants are VERIFIED on these cases only, not proven for every input.
- Fault injection: 35 source-level mutants of a module copy (a scratch script, not committed).
  - The first run killed 32 of 35.
  - Three tests were added for the survivors (completion order, hold before closing, not-activated check order).
  - After that, 35 of 35 were killed.
- Discrepancy with the 5B-4.1 spec: the INFERRED bound "before closing, accepting servers never exceed the 5B-1 scheduled active count" is false under the gap push.
  - `test_gap_push_puts_the_employee_on_duty_in_scheduled_break_time` shows it.
  - The bound is withdrawn in the policy spec. A weaker bound is UNKNOWN (P8).
- Undetermined, recorded in the module's `UNDETERMINED` list:
  - A break due before a delayed split-shift activation: UNKNOWN, and the module raises `UndeterminedPolicyError`.
  - Closing is placed right after completions in the X2 order: INFERRED.
  - A delayed split shift keeps its scheduled end, and is not activated when the delayed activation reaches it: INFERRED.
  - The P5, P6, and P7 selections: UNKNOWN.
- NOT TESTED: tolerances for non-dyadic times. A scratch probe on a 5-minute grid showed a break's end minus start differing from 10/60 at the last binary digit.
- Next (needs explicit approval): 5B-4.3, customer and queue integration. It needs the P5, P6, and P7 selections, X1, the P8 output shape, the X6 output field, and decisions on the undetermined cases. Superseded: 5B-4.3 is done (next section).

## Shared Queue Enhancement: Phase 5B-4.3 Named-Employee Continuous Shared-Queue DES (2026-09-28)

Spec and plan:

- `docs/superpowers/specs/2026-09-28-shared-queue-named-des.md`
- `docs/superpowers/plans/2026-09-28-shared-queue-named-des-plan.md`

The Phase 5B-4.3 request supplied P1-P9 and X1-X7 as rules to use exactly (recorded in the policy spec, "Explicit decisions of 2026-09-28 (Phase 5B-4.3)"): DRAIN crew frozen from employees accepting immediately before closing and serving until the line is empty; HARD_CUTOFF releases idle employees at closing and busy ones at completion; breaks in progress at closing truncated, pending ones cancelled_at_closing; X1 longest available, ties by employee_id; X2 places the closing boundary second; X6 `no_eligible_employee`; P8 six series and two separate gaps; and a new P3 rule for breaks of a delayed split shift.

Current verified state:

- `backend/queueing_engine/simulation/shared_named_des.py` (new): `simulate_named_prescribed` on prescribed (hour, work) arrivals.
  - One FCFS line; named employees driven through the 5B-4.2 state machine; the X2 instant loop; closing inputs chosen by the state immediately before closing; X1 by earliest time of becoming AVAILABLE.
  - Required inputs, no defaults: `closing_policy`, `employee_policy` (`EmployeeDesPolicy`, each field accepts only its approved value, `APPROVED_EMPLOYEE_POLICY`), and `required_staffing` (X7, validated by `validate_timeline`).
  - Output: customer rows (`employee_id`, `register_id` replace `server_id`), counts, the queue integral, `at_close` (frozen crew, closing inputs), P8 staffing timeline and windows, the employee timeline, and a customer trace. No random numbers and no cost.
- `shared_employee_states.py` amended (version v2): the P3 split-shift break rule replaces the 5B-4.2 `UndeterminedPolicyError`; roster-derived instants are computed in whole minutes (float safeguard); read-only `snapshot()`.
  - The whole-minute change fixes a VERIFIED hazard: adding minutes in hours missed the exact conversion for 2,487 of 11,520 (start, duration) pairs; two new tests fail against dfa8fe75 and pass now. Binary-exact results are unchanged.
  - One 5B-4.2 expectation changed because the approved P3 rule changed it (`test_split_shift_overrun_delays_the_next_shift`: the delayed shift's break moves from 2.5 to 3.125 h).
- The anonymous engine `shared_continuous_des.py` is not changed; the 5B-4.0 pin passes. X5 is not exercised (prescribed arrivals only), so no public alias was added.
- Tests: `tests/test_shared_named_des.py` (new; 37 test functions, 59 tests) with `check_named`, an independent checker of invariants 1-19 that also runs the 5B-4.2 checker; every required hand-computed case; the reduction test (fixed crew and growing crew, both policies, 96 generated arrival sets, all identical to the anonymous engine; employee and server identity not compared). `tests/test_shared_employee_states.py`: 38 test functions.
- Fault injection: 28 source-level mutants of both modules (scratch script, not committed); first run killed 26 of 28; two tests added for the survivors (break-due service across closing, DRAIN release order); after that 28 of 28 killed on the final module text.
- Gates: named, state-machine, and pin tests 106 passed; shared suites plus Separate Queue regressions 654 passed (Separate Queue alone 42 passed); ruff clean; mypy clean on 172 files; full backend suite 1647 passed, 3 skipped, 1 xfailed (baseline 1583; +59 named DES, +5 net state machine).
- Undetermined (5B-4.3 spec): a break-due service completing exactly at closing raises `UndeterminedPolicyError` (zero-length truncated break vs cancelled_at_closing); a break ending exactly at closing is recorded completed (INFERRED); "accepting" = AVAILABLE or SERVING (INFERRED); no verified event-time tolerance exists, so instants are compared exactly as in the anonymous engine (UNKNOWN for seeded runs); the P8 window shape is INFERRED.
- Next (needs explicit approval): 5B-4.4 seeded named replications (X5 wrapper and an event-time tolerance decision), 5B-4.5 named playback, 5B-5 workforce cost. Superseded: 5B-4.4 is done (next section).

## Shared Queue Enhancement: Phase 5B-4.4 Seeded Named-Employee DES Replications (2026-09-28)

Spec and plan:

- `docs/superpowers/specs/2026-09-28-shared-queue-named-replications.md`
- `docs/superpowers/plans/2026-09-28-shared-queue-named-replications-plan.md`

The Phase 5B-4.4 request approved five remaining rules and said to freeze them before replications. The spec quotes them, and the policy spec records them ("Explicit decisions of 2026-09-28 (Phase 5B-4.4)"):

1. A break-due service completing exactly at closing completes first, and its break is `cancelled_at_closing`, with no zero-length break.
2. A break ending exactly at closing is `truncated_by_closing`.
3. Accepting capacity = AVAILABLE + SERVING.
4. No event-time epsilon; whole-minute roster arithmetic; no rounding or snapping of stochastic times.
5. Gaps are reported per segment and over the horizon only, none before opening or after closing, and post-close capacity and time are reported separately.

Current verified state:

- Rules 1, 2, and 5 changed behavior; rules 3 and 4 confirm what was implemented.
  - `shared_employee_states.py` v3: a SERVING_BREAK_DUE completion at closing, with that employee's `CancelPendingBreaks` at that instant, goes to AVAILABLE and starts no break.
  - `shared_named_des.py` v2:
    - rule 1 inputs, where 5B-4.3 raised `UndeterminedPolicyError`;
    - EndBreakAtClosing for every employee on a break before closing (rule 2);
    - `schedule_realization_gap` None outside [0, closing), no gaps or required hours in the before-opening and after-closing windows, and `after_closing` always present (rule 5).
  - Three 5B-4.3 test expectations changed because the approved rules changed them; each is documented in the 5B-4.3 spec, "Phase 5B-4.4 amendments":
    - the undetermined test replaced by a rule 1 test;
    - a break at 3.5-4.0 `completed` -> `truncated_by_closing`;
    - an after-closing schedule shortfall of 0.125 replaced by the after-closing series.
- X5: `shared_continuous_des.draw_arrivals` is a public wrapper: the same two checks as `simulate_shared_replication`, then `_draw_arrivals`. No existing function changed, and the 5B-4.0 pin passes without regenerating the fixture. A scratch SHA-256 digest of 100 `simulate_shared_day` runs, 40 `simulate_shared_replication` runs, and 4 `run_shared_replications` runs is identical before and after (`236d87ec...c610`, numpy 2.4.6).
- New `simulation/shared_named_replications.py`:
  - `replication_seed_sequence(root_entropy, i)` implements the Phase 4 scheme.
  - `simulate_named_replication(seed_sequence=...)` returns the unchanged 5B-4.3 result plus a `replication` block: entropy, spawn key, pool size, customer count and SHA-256 digest, and runtime (numpy and Python versions, bit generator).
  - `run_named_replications` keeps one scalar row per replication, regenerable from `(root_entropy, i)`.
  - `aggregate_named_replications` is descriptive: `summarize_metric`, explicit denominators, `verdict: None`. There is no cost, criterion, or threshold.
- Common random numbers: customers depend only on the horizon, the demand, the root entropy, and i. The named engine and the state machine draw nothing.
- Reproducibility is VERIFIED in this runtime only (numpy 2.4.6, Python 3.13.13, PCG64). Cross-version stream equality (production lock 2.2.6, CI `requirements.txt` below 2.3) is UNKNOWN.
- Module location differs from the 5B-4.1 proposed interface (`shared_named_des.py`). The replication entry points are in a new module, so the engine stays free of numpy, as its isolation test requires.
- Tests: `tests/test_shared_named_replications.py` (new; 33 test functions, 73 tests; synthetic data; no seeded golden values). They cover:
  - an independent recomputation of the draws with explicit PCG64 streams;
  - `check_row`, which recomputes every row field from the raw result;
  - `check_named` with `check_invariants(exact=False)` on every replication of 10 scenarios x 2 policies;
  - every draw counted across rosters;
  - the seeded reduction to the anonymous engine;
  - regeneration and common random numbers.

  The spec maps all 12 required points and 14 cases. `tests/test_shared_named_des.py`: 39 functions, 62 tests. `tests/test_shared_employee_states.py`: 39 tests.
- Fault injection: 41 source-level mutants on a scratch copy of `backend/` and `tests/` (script not committed; working tree untouched).
  - First run: 38 of 41 killed. Two survivors were test gaps: a replication with no activated shift, and the unknown-cause guard. Tests were added for both.
  - Final text: 40 of 41 killed. The survivor ("rule 1 cancel at any instant") is equivalent: a probe showed that the original and the mutant raise the same error at 3.9 h and 4.5 h.
- Gates (executed on the final text):
  - named DES, state machine, and pin: 110 passed;
  - 5B-4.4 tests: 73 passed;
  - all `tests/test_shared_*.py`: 691 passed;
  - Separate Queue, all 20 files: 182 passed;
  - ruff: clean;
  - `mypy . --exclude '^outputs/'`: clean on 174 files; plain `mypy .` shows only the 5 known errors in the gitignored `outputs/` script;
  - full backend suite (`python -m pytest tests/ -x --tb=short`): 1724 passed, 3 skipped, 1 xfailed (baseline 1647 + 77).
  - Frontend not run: nothing under `frontend/` changed.
- Undetermined:
  - cross-version stream equality: UNKNOWN;
  - "preserve the 5B-4.3 result" read as scalar rows plus regeneration: INFERRED;
  - no paired roster-comparison output: PROPOSED only;
  - rule 1 is exercised by prescribed tests only, since the event has probability 0 with continuous draws;
  - the acceptance rule: UNKNOWN;
  - DRAIN release order and before-opening window shape: INFERRED, carried over.
- Next (needs explicit approval): 5B-4.5 named playback, 5B-4.6 attribution reporting, 5B-5 workforce cost, an acceptance rule, and API or UI exposure. Superseded: 5B-4.5 is done (next section).

## Shared Queue Enhancement: Phase 5B-4.5 Named-Employee DES Playback (2026-09-29)

Spec and plan:

- `docs/superpowers/specs/2026-09-28-shared-queue-named-playback.md`
- `docs/superpowers/plans/2026-09-28-shared-queue-named-playback-plan.md`

Current verified state:

- New `simulation/shared_named_playback.py`:
  - `replay_named_trace` rebuilds the line, customers, employees, and registers from the named engine's two records and validates the 17 required invariants plus P4, work conservation, service length, the closing rules, and the end state. A failure returns the check, the event, and the evidence; nothing is repaired.
  - `build_named_playback`, `prepare_named_playback`, and `playback_from_named_replications` produce a checked playback of one regenerated replication.
- Named DES engine v3 (`shared_named_des.py`), trace-only:
  - `employee_transitions_before` on every customer trace event;
  - simultaneous DRAIN releases recorded in employee_id order (approved rule). DISCREPANCY: `fd67bbf2` recorded X1 order (B, C, A in the hand case).
  - A scratch comparison with `fd67bbf2` on 500 seeded runs showed identical customers, counts, queue, staffing, and employee intervals, shifts, and breaks.
- Named replications method v2: `provenance.inputs_sha256`, a canonical-JSON SHA-256 of the recorded inputs and both policies. It is not tamper-proof and not semantic equivalence.
- Regeneration refuses (`regeneration_identity`, `stored_row`) on:
  - a version, seed-scheme, row-identity, digest, or rebuild mismatch. A rebuild error was a `TypeError` crash before a fix in this phase.
  - a regenerated row that differs from the stored row.
- Vocabulary: 5 customer types and 22 transition tuples, all reached on prescribed days. Two state-machine tuples are rejected (INFERRED unreachable).
- Tests:
  - `tests/test_shared_named_playback.py`: new, 51 functions, 75 tests. It covers hand-derived event sequences, corrupted traces (including ones with plausible final counts), the digest, the interleaving field, regeneration and refusal, and zero random numbers.
  - `tests/test_shared_named_des.py`: 3 new tests (42 functions, 65 tests).
  - The version assertion in `tests/test_shared_named_replications.py` changed from v2 to v3.
- Fault injection (scratch copy; working tree untouched):
  - First run: 48 of 88 killed. Survivors were real gaps, or checks whose failure point tests did not pin. Tests were added for every reachable one, and provably unreachable checks were removed rather than counted. Analysis also found the rebuild crash above, which was fixed.
  - Final run: 88 of 88 killed.
- Gates on the final tree:
  - focused: playback 75, named replications 73, named DES 65, state machine 39, and pin 9, all passed;
  - all `tests/test_shared_*.py`: 769 passed;
  - Separate Queue (20 files): 182 passed;
  - ruff: clean;
  - `mypy . --exclude '^outputs/'`: clean on 176 files; plain `mypy .` shows only the 5 known errors in the gitignored `outputs/` script;
  - full backend suite (`python -m pytest tests/ -x --tb=short`): 1802 passed, 3 skipped, 1 xfailed (baseline 1724 + 75 + 3).
- Undetermined:
  - cross-version numpy stream equality: UNKNOWN;
  - the rejected tuples' unreachability: INFERRED;
  - which idle DRAIN crew members stay: INFERRED;
  - the before-opening window shape: INFERRED;
  - the acceptance rule: UNKNOWN.
- Next (needs explicit approval): 5B-4.6 attribution reporting, 5B-5 workforce cost, an acceptance rule, and API or UI exposure.

## Shared Queue Enhancement: Phase 5B-4.5 Playback Validation Hardening (2026-09-29)

Recorded in the playback spec, "Follow-up: validation hardening (2026-09-29)". Only `simulation/shared_named_playback.py` and its tests changed; the engine (v3), replications method (v2), digest, merge, and named-DES rules are unchanged.

- Two defects, reproduced on `028917fe` before any change:
  - `replay_named_trace` and `build_named_playback` accepted any closing-policy label (`"FOO"`, `None`, `"drain"`, ...) when the events are the same under both policies.
  - An unhashable value at a set or dict membership test raised `TypeError` (customer `type`; transition `event`, `stage`, `from_state`, `to_state`, `employee_id`; a started engine break's `employee_id` or `actual_start`).
- Fix:
  - New first check `closing_policy`: the engine's exact `CLOSING_POLICIES` test behind a string test. Nothing is normalized or inferred.
  - `playback_from_named_replications` applies it before regeneration (`NamedPlaybackError`, check `closing_policy`).
  - Membership values are tested as strings (or finite reals) first and fail the check a hashable wrong value already failed. Nothing is converted.
  - `PLAYBACK_VERSION` is v2.
- Tests: 22 new (97 in the file). Against the `028917fe` module, all 22 fail and the other 75 pass.
- Gates on the final text:
  - focused: playback 97, named replications 73, named DES 65, state machine 39, pin 9, all passed;
  - all `tests/test_shared_*.py`: 791 passed;
  - Separate Queue (20 files): 182 passed;
  - full backend suite: 1824 passed, 3 skipped, 1 xfailed;
  - `ruff check .`: clean; `mypy . --exclude '^outputs/'`: clean on 176 files; `git diff --check`: clean.
- Open (VERIFIED, not fixed, needs approval): an extra engine break, shift, or interval record naming an employee who is not in the timeline (for example `"Z"`) is still accepted, because the reconciliation compares only the timeline's employees.
- Next (needs explicit approval): the open finding above, 5B-4.6 attribution reporting, 5B-5 workforce cost, an acceptance rule, and API or UI exposure.

## Shared Queue Enhancement: Phase 5B-4.5 Employee Referential Integrity (2026-09-29)

Recorded in the playback spec, "Follow-up: employee referential integrity (2026-09-29)". This resolves the open finding above. Only `simulation/shared_named_playback.py` and its tests changed; `PLAYBACK_VERSION` is v3.

- Defect, reproduced on `086075f7`: an extra record naming an employee outside the timeline was VALID in `replay_named_trace` and `build_named_playback`. It affected intervals, shifts, breaks, and closing inputs (the last was not in the earlier report). A non-string `state_totals` key raised `TypeError`.
- Authoritative employee set: the run's input employees. `evaluate_roster` reports every one, rostered or not, so the timeline's `state_totals` keys are the input employees.
- Rule (new check `employee_identity`):
  - timeline keys are strings;
  - every interval, shift, break, and closing input names one exactly (case-sensitive, never normalized);
  - `prepare_named_playback` (and the stored-run path) requires the timeline's employees to equal the input employees.
  - Existing checks keep their codes.
- Limit (VERIFIED): from a result alone, an extra employee copying an unrostered employee's records cannot be told apart; only the input check rejects it.
- Tests: 20 new (117 in the file); one assertion changed from v2 to v3. Against the `086075f7` module the final test file fails 21 (17 accept the orphan, 1 `TypeError`, 1 no refusal, 2 on the v3 version) and passes the other 96.
- Gates on the final text:
  - focused: playback 117, named replications 73, named DES 65, state machine 39, pin 9, `test_shared_segments.py` 51, all passed;
  - all `tests/test_shared_*.py`: 811 passed;
  - Separate Queue (20 files): 182 passed;
  - full backend suite: 1844 passed, 3 skipped, 1 xfailed;
  - `ruff check .`: clean; `mypy . --exclude '^outputs/'`: clean on 176 files; `git diff --check`: clean.
- Next (needs explicit approval): 5B-4.6 attribution reporting, 5B-5 workforce cost, an acceptance rule, and API or UI exposure.

## Shared Queue Enhancement: Phase 5B-4.6 Named-Employee Attribution Reporting (2026-09-29)

Spec and plan:

- `docs/superpowers/specs/2026-09-29-shared-queue-named-attribution.md` (approved as decisions D1-D8 on 2026-09-29; its section 12 records the implementation)
- `docs/superpowers/plans/2026-09-29-shared-queue-named-attribution-plan.md`

Current verified state:

- New `simulation/shared_named_attribution.py` (`novaq-shared-named-attribution-v1`). `build_named_attribution(result, employees)` is a pure read of one named result's `employee_timeline` and the run's input employees.
  - Its primary record is employee × shift × run. It adds per-employee sums over activated shifts.
  - It adds no aggregation across replications, no verdict, and no pay or cost.
  - Failures raise `NamedAttributionError` (check, message, evidence), through 11 checks. Nothing is repaired.
- Per-shift allocation is exact, by `(employee_id, shift_index)`. The preconditions are checked on every input.
- The quantities:
  - shift timing, on-duty hours by base state, and register wait;
  - after-closing and past-scheduled-end time as four disjoint cells, including `after_closing_and_past_scheduled_end_hours`, summed directly (D3);
  - per break, `delay_from_scheduled_hours` and `delay_from_due_hours` (D2), and shortened and unfulfilled hours.
- Units are hours (D1). `inputs_sha256` is `None`, with the reason (D4). There is no `paid` field (D5). There is no replication runner, and the rows are unchanged (D6).
- D7: a derived duration within the house tolerance below zero is reported as 0.0; beyond the tolerance the call fails. Timing comparisons stay exact.
- Defect found and fixed in the new module: malformed values beyond the float range (for example `10**400`) raised `OverflowError` instead of failing a check. This was VERIFIED before and after the fix.
- Out-of-scope finding: the protected playback `_time()` helper was observed to raise `OverflowError` for `_time(10**400)`. Whether this propagates through `replay_named_trace` was not tested. Playback v3 was not modified during Phase 5B-4.6. A separate task was opened for it. (Resolved 2026-09-30: the propagation was VERIFIED and fixed in playback v4; see "Phase 5B-4.5 Playback Numeric Range Hardening" below.)
- Spec correction: the section 7.4 example "stable day = zero attribution" was wrong. VERIFIED: 24 of 25 seeded stable replications are nonzero under each policy. The test uses `zero_arrivals` and a prescribed quiet day, and the contract is unchanged.
- Docs: the policy spec's stale 5B-4.6 entries (P2 threshold, P8 mapping, P9 question) are corrected, with the original text kept. The named-DES spec's next-steps line is updated.
- Tests: `tests/test_shared_named_attribution.py` is new, with 46 functions and 141 tests. It covers:
  - hand cases H1-H8 and H1b;
  - seeded identities on 10 scenarios × 2 policies × 25 replications, including the 5B-4.4 row;
  - 85 malformed or order-violation cases;
  - the D7 rule and its boundary;
  - purity and isolation.

  `tests/test_shared_segments.py`: the module joins the isolation set.
- Fault injection, on a scratch copy; the working tree was untouched:
  - Final pass on the final attribution implementation: 99 mutants in total. 94 were killed. 3 survived because the guarded conditions are input-unreachable through validated execution paths. 2 were demonstrated to be equivalent mutants. There were 0 timeouts and 0 harness failures.
  - The three defensive checks (on-duty span, closing partition, and base-state partition) were retained, because forced or bypassed validation demonstrated that they still detect real malformed states.
  - Earlier passes: 95 mutants with 55 killed, then 95 with 90 killed.
  - The earlier 900-second mutation timeout did not reproduce, and its cause remains UNKNOWN. A separate scratch restore-path mistake occurred during manual reproduction and was corrected. There is no evidence that it caused the timeout.
- Gates on the final code:
  - focused: attribution 141, state machine 39, named DES 65, named replications 73, playback 117, segments 51, and pin 9, all passed;
  - all `tests/test_shared_*.py` (15 files): 952 passed;
  - Separate Queue (20 files): 182 passed;
  - full backend suite (`python -m pytest tests/ -x --tb=short`): 1985 passed, 3 skipped, 1 xfailed (baseline 1844 + 141). The skips are the PostgreSQL migration rehearsal tests, which need `NOVAQ_TEST_DATABASE_URL`; the xfail is the known 2026-09-19 `test_selected_mc_load` finding.
  - The full backend suite completed in approximately 65 minutes. Other processes were active during the run; whether they caused the longer runtime is UNKNOWN.
  - `ruff check .`: clean.
  - `mypy . --exclude '^outputs/'`: success on 178 files. Plain `mypy .` shows only the 5 known errors in the gitignored `outputs/` script.
  - `git diff --check`: clean.
  - Documentation-only edits came after the gates, and no test reads those files.
- Unchanged (`git diff 5a9738e2`): named DES v3, state machine v3, replications method v2, playback v3, Separate Queue, services, API, database, frontend, dependencies, and fixtures.
- Undetermined:
  - cross-version numpy stream equality: UNKNOWN;
  - whether a derived duration ever takes the D7 zero or failure branch on engine output: NOT TESTED;
  - whether 5B-4.6 must precede 5B-5: UNKNOWN;
  - D15: UNKNOWN (undefined);
  - the before-opening window shape: INFERRED and out of scope.
- Next (needs explicit approval): 5B-5 workforce cost, an acceptance rule, API or UI exposure, and the playback overflow task.

## Shared Queue Enhancement: Phase 5B-4.5 Playback Numeric Range Hardening (2026-09-30)

Recorded in the playback spec, "Follow-up: numeric range (2026-09-30)". Made on branch `fix/named-playback-overflow`, from `156de75f`, as commit `b0040508`. On 2026-09-30 `b0040508` was fast-forwarded into `feat/shared-queue-segments` (`git merge --ff-only fix/named-playback-overflow`, conflict-free), which moved that branch from `156de75f` to `b0040508`. Nothing was pushed. Only `simulation/shared_named_playback.py` and its tests changed. `PLAYBACK_VERSION` is v4. `shared_named_replications.py` is unchanged, and its `METHOD_VERSION` is still v2.

- Defect, VERIFIED on the v3 module (probe 2026-09-29, and the tests below): values beyond the float range raised `OverflowError` instead of failing a check. This covered huge whole-number or `Fraction` times, engine totals, and `unit_work`, and finite floats whose exact sum is beyond the range. Where probed, each escaped `replay_named_trace`, `build_named_playback`, or both. `playback_from_named_replications` with a doctored engine raised for every case probed: times, `unit_work`, a state total, and an after-closing interval. `build_named_playback` also raised from `named_replication_row`, which ran before the replay: `OverflowError`, or `SharedSegmentError` for inconsistent counts. The v2 hardening covered unhashable values only.
- Fix (approved as Part A and B1, 2026-09-30):
  - `_time` and `_close_enough` catch `OverflowError`, and `near` guards its `float()` conversions. The value then fails the existing check.
  - A new `_fsum` wrapper is used at the served-wait sum (`customer_reconciliation`), the state totals, and `_hours_in` (`employee_reconciliation`).
  - `unit_work` is tested before the division (`service_duration`).
  - `_outside_horizon` runs inside the exception boundary of both entry points. Its overflow was reproduced: in the replay with the timeline beginning at -DBL_MAX, and in the build within the replay's tolerance band. That the band is the only route in the build is INFERRED.
  - B1: `build_named_playback` replays first, then builds the row. A row `OverflowError` fails the new check `summary_row`. Corrupted counts now raise `NamedPlaybackError(customer_reconciliation)` instead of `SharedSegmentError`.
- Valid output: a scratch comparison of 276 outputs from the v3 and v4 modules was identical apart from `provenance.playback_version` and the appended `summary_row` check (VERIFIED; not committed).
- Tests: 10 new functions and 50 new tests (167 in the file); two version assertions changed from v3 to v4. Against the v3 module, the final test file fails 52 and passes 115. Of the 52: 43 `OverflowError`, 2 `SharedSegmentError`, 2 `TypeError`, 2 old-message `service_duration`, and 3 on the version. Fault injection: 13 of 13 mutants killed. The first run killed 12; the build `_outside_horizon` mutant was killed after the tolerance-band test was added.
- Gates on the final code (2026-09-30):
  - focused: playback 167, named replications 73, named DES 65, state machine 39, pin 9, segments 51, and attribution 141, all passed;
  - all 15 `tests/test_shared_*.py` files: 1002 passed;
  - Separate Queue (20 files): 182 passed;
  - full backend suite (`python -m pytest tests/ -x --tb=short`): 2035 passed, 3 skipped, 1 xfailed, 6 subtests passed. The skip reasons were not printed in this run. The full suite was not rerun before the change in this worktree, so the difference from the 1985 recorded for 5B-4.6 is not a verified delta;
  - `ruff check .`: clean; `mypy . --exclude '^outputs/'` and plain `mypy .` in this worktree: no issues in 178 files; `git diff --check`: clean.
  - The documentation was edited after the gates. No test reads these files.
- Integration check (2026-09-30, after the fast-forward; separate from the gate runs above):
  - the feature branch's tree was identical to `b0040508`, and `git diff --check` was clean for `156de75f..b0040508` and for the working tree;
  - on that identical tree (run in the fix worktree), focused playback 167, named replications 73, named DES 65, state machine 39, pin 9, segments 51, and attribution 141 passed, and all 15 `tests/test_shared_*.py` files passed (1002);
  - the full backend suite was not rerun after the integration. The full-suite result above is from the gate run before the integration.
- Open (VERIFIED, not fixed; each needs approval):
  - the queue-area accumulation in `_reconcile` still raises `OverflowError` with exact `Fraction` times (present on v3 too);
  - an unknown `unfulfilled_cause` passes the replay, and `build_named_playback` raises `SharedSegmentError` from `named_replication_row` (present on v3 too; not an overflow);
  - non-finite values are accepted: a timeline beginning at -inf, and infinite queue integrals, replay as VALID (`math.isclose(inf, inf)` is True);
  - from the 2026-09-29 probe: a huge or `Fraction` `register_count` (playback `handover`), a caller-supplied service rate beyond the float range (playback `_Replay.__init__`), `shared_segments._is_finite_real`, the named DES `servers` sum, and `shared_employee_states._handover`.
- Next (needs explicit approval): the open items above, 5B-5 workforce cost, an acceptance rule, and API or UI exposure.

## Shared Queue Enhancement: Phase 5B-5 Named Workforce Costing (2026-09-30)

Spec and plan:

- `docs/superpowers/specs/2026-09-30-shared-queue-named-workforce-cost.md` (approved on 2026-09-30 as decisions C1-C16, with C10b and C13 Option U; section 14.1 records the dated implementation-precondition corrections after the playback integration, and section 18 the implementation)
- `docs/superpowers/plans/2026-09-30-shared-queue-named-workforce-cost-plan.md`

Current verified state:

- Base `feat/shared-queue-segments` at `40ee8dbe`. One local commit; not pushed, merged, or deployed. (Superseded 2026-09-30: the implementation `19ff54a1` is followed by the docs-only spec clarification `6777ad3f` and a docs-only `handoff.md` and `memory.md` follow-up; see the owner decisions below. None is pushed, merged, or deployed.)
- New `services/shared_named_cost.py` (`novaq-shared-named-cost-v1`). `cost_named_workforce(result, employees, rates)` costs one named-DES run or one regenerated replication (C12). It is a pure read: no simulation, no random numbers, no input changed.
  - It first runs `build_named_attribution`, whose failures propagate unchanged, and reads every operational quantity from it (C16). It then walks the same validated intervals in time order only to split paid time into regular and overtime.
  - Failures raise `NamedCostError` (check, message, evidence) through 10 checks after attribution's 11. Nothing is repaired.
- Cost = per employee `regular_paid_hours × regular_rate_per_hour + overtime_paid_hours × overtime_rate_per_hour` + `queue.customer_hours_total × waiting_rate` + `counts.unserved_at_close × unserved_customer_rate` when the unserved term applies. Named wages replace the Phase 3A capacity labor terms (C2); `shared_day_cost.py` is unchanged.
- Paid time (C3, C4, C7): WAITING_FOR_REGISTER, AVAILABLE, and the three serving states are paid; OFF (including activation delay and split-shift rest) is unpaid; ON_BREAK is paid only when the engine break record it maps to (exact containment and tiling) has `paid` True. No break penalty or bonus.
- Overtime (C5, C6, C14, C15): an instant past its shift's scheduled end, after closing, or after cumulative actual paid time (all earlier paid time, flagged or not, across split shifts) reaches the daily threshold; one premium per instant. A missing required threshold gives `HOURS_UNDETERMINED` (labor and total `None`), never `RATE_MISSING`. D7 (`derived_duration`) is used only for `R_k` and a crossing's T piece.
- Statuses (C13): `COSTED`, `ZERO_QUANTITY` (an exact zero needs no rate, cost 0.0), `RATE_MISSING`, `HOURS_UNDETERMINED`, `NOT_APPLICABLE`. X6 (C10b): HARD_CUTOFF applies the unserved term even at 0 (`ZERO_QUANTITY`); DRAIN applies it only when the realized count is above 0. No verdict or acceptance field (C11); D15 stays UNKNOWN.
- Implementation choices within the spec (section 18.3): `total_cost` is the fsum of the component costs (sections 9 and 11; section 3's `fsum(L, W, U)` grouping can differ only by rounding: CONFLICTING at rounding level); under DRAIN with an empty crew, the unserved ids must equal the waiting ids (the engine's X6 rule). (Superseded 2026-09-30: the product owner resolved both points in docs commit `6777ad3f`. The grouping is no longer CONFLICTING, and the DRAIN equality is an approved invariant; see the owner decisions below.)
- Tests: `tests/test_shared_named_cost.py` is new, with 53 functions and 137 tests: hand cases HC-A to HC-W3 plus the split-shift threshold regression; seeded identities on 10 scenarios × 2 policies × 25 replications against an exact-arithmetic walk; 78 malformed or overflow cases; rule-level walk tests; purity and isolation. `tests/test_shared_segments.py`: the module joins the isolation set.
- Fault injection on scratch copies (working tree untouched): 106 mutants. First pass 86 killed; eight test gaps got tests. Final pass: 101 killed, 5 equivalent, 0 timeouts, 0 harness failures. `paid_partition`, `overtime_partition`, and `cost_arithmetic` are input-unreachable and kept; direct tests show they fire.
- Gates on the final code:
  - focused: cost 137, attribution 141, state machine 39, named DES 65, named replications 73, playback 167, segments 51, pin 9, and day cost 16, all passed;
  - all 16 `tests/test_shared_*.py` files: 1139 passed;
  - Separate Queue (20 files): 182 passed;
  - full backend suite (`python -m pytest tests/ -x --tb=short`): 2172 passed, 3 skipped, 1 xfailed, 6 subtests passed (734 s), which is the 2035 recorded for playback v4 plus the 137 new tests. The skips are the three `test_real_postgres_upgrade_paths_preserve_ownership` cases (PostgreSQL rehearsal; the reason was not printed); the xfail is the known `test_selected_mc_load::test_novamart_failing_lanes_are_stable_across_base_seeds`.;
  - `ruff check .`: clean; `mypy . --exclude '^outputs/'`: no issues in 180 files; `git diff --check`: clean.
  - The documentation was edited after the gates. No test reads these files.
- Docs: the policy spec's P1, P9, X6, and 5B-5 rows carry dated corrections, with the original text kept.
- Unchanged (`git diff 40ee8dbe`): named DES v3, state machine v3, attribution v1, playback v4, replications method v2, Phase 3A day cost, 5B-1 to 5B-3, Separate Queue, API, database, frontend, dependencies, and fixtures.
- Undetermined: the C14 all-flagged branch and the D7 branches in the walk are INFERRED unreachable; tiny float slices are engine-reachable (tested on a 5-minute roster) but NOT TESTED on the seeded runs; Phase 5A D6 and D8 and D15 are UNKNOWN; cross-version numpy stream equality is UNKNOWN.
- Owner decisions after the implementation (2026-09-30), written into the spec by docs-only commit `6777ad3f` (parent `19ff54a1`). `git diff 19ff54a1 6777ad3f` changes only the spec, so the implementation `19ff54a1` is unchanged.
  - Total-cost grouping, resolved: the canonical `total_cost` is a single flat `fsum` over every applicable component cost (each employee's regular and overtime labor costs, the waiting cost, and the unserved cost when it applies; COSTED and ZERO_QUANTITY components only), as spec sections 9 and 11 define. Section 3 now states this, with its old nested line kept as a dated quote. Employee `labor_cost` (`L_e`) and `labor.total_cost` (`L`) remain reported subtotals. `total_cost` is not recomputed as the nested `fsum(L, W, U)`. The code matches (VERIFIED: `shared_named_cost.py` lines 710-713, and the `cost_arithmetic` check at line 627).
  - DRAIN empty-closing-crew equality, approved as a validation and reconciliation invariant: it applies only in the engine branch where DRAIN has an empty frozen crew (`at_close.drain_crew` empty) and the remaining waiting customers are made unserved (`no_eligible_employee`). It checks that those unserved customers are exactly the waiting population at closing (`at_close.waiting_customer_ids`). This is the `unserved_consistency` branch in `_check_unserved`, lines 518-521.
  - The invariant does not determine cost applicability. C10b stays authoritative: under DRAIN, `counts.unserved_at_close > 0` applies the unserved component, and zero realized unserved gives `NOT_APPLICABLE` (line 701; the crew is not read there). Employee eligibility is not independently recomputed; the module reads the engine's frozen `drain_crew`.
- Phase status (2026-09-30): implementation `19ff54a1`; spec clarification `6777ad3f`. Phase 5B-5 remains closed. API or UI exposure is not approved. Cross-replication cost aggregation is not approved. D15 and the acceptance rule remain UNKNOWN, and no verdict exists.
- Next (needs explicit approval): cross-replication cost aggregation, an acceptance rule, API or UI exposure, and the open playback items listed above.

## Shared Queue Enhancement: Named Shared Queue API/UI First Slice (2026-10-01)

Spec: `docs/superpowers/specs/2026-09-30-shared-queue-named-api-ui-first-slice.md` (A1-A6 and OD-1 to OD-9 approved 2026-09-30; numeric identity B1 and the 422/409 identity codes approved 2026-10-01). Section 21 is the implementation record. No separate plan file was written; the spec's section 20 stages served as the plan.

Current verified state:

- Authorization: the product owner's master continuation prompt (2026-10-01) authorized LOCAL implementation. Production facts stay release blockers, not local blockers. Nothing is pushed, merged to `main`, or deployed.
- G-A integration: `e7e3cdae` (final G-A) merged into `feat/shared-queue-segments` as `a49bb1f1` (`--no-ff`; parents `620f20df`, `e7e3cdae`). No file was changed on both lines. Gates on `a49bb1f1`: SQLite 2719 passed, 118 skipped (all PostgreSQL variants), 1 xfailed; PostgreSQL 16.15 (CI postgres file list plus the 22 G-A test files) 777 passed, 0 skipped; frontend 53 files and 388 tests, typecheck and lint clean. `GENERATION_ENFORCEMENT_ENABLED` stays `False`.
- Implementation commit: `6ecd9c6f` (parent `a49bb1f1`) (local, not pushed).
- Backend: `backend/api/shared_named.py` is the one thin adapter (A6). Routes R1-R6 under `/analyses/{analysis_id}/shared-named/`: `contract`, `validate`, `runs` (create and list), `runs/{run_id}`, `runs/{run_id}/replications/{i}`. Each run is one Job of kind `shared_named_replications` with the unchanged `run_named_replications` output and `params_json.dataset_generation` from the explicitly selected dataset row. No migration, workforce table, stored playback, or cost.
  - B1: insert and flush, re-read `result_json` with a column `SELECT` in the same transaction, and compare the fingerprint, every stored row (int, float, and bool distinct; floats by bits), and the required provenance. Any difference rolls back and returns 422 `persistence_identity_mismatch` with no run id. On PostgreSQL 16.15 a pay rate of `1e16` is refused this way (JSONB returns it as an integer).
  - R6 keeps the protected regeneration contract: 409 `regeneration_identity` (with the domain check, or `attribution_stored_row` for the D6 guard) on an existing run that no longer reproduces; other playback or attribution failures are 500.
  - The named router keeps NaN and ±Infinity bodies at 422 with its own route class. App-wide, such bodies return 500 (pre-existing; not fixed).
  - Limits stay provisional and NOT PRODUCTION-APPROVED: replications 9, required-staffing segments 52, employees 24, roster shifts 48 (availability 3, break rules 3, breaks per rule 2, breaks per shift 2). The 413 backstop reads `RESULT_JSONB_MAX_BYTES` at run time.
- Frontend: `?mode=named` on `/analyses/:analysisId/simulate`, offered only for `shared_queue` analyses. Without the parameter the page renders as before (`SimulationPage.test.tsx` unchanged and passing). The named view covers eligibility, a persistent banner, an explicit dataset selector, the workforce form with no defaults, validation, a run control gated on a runnable validation of the exact form, the runs list with Setup currency, run evidence, the replication table and descriptive aggregate (minutes for waits, "—" for null, no verdict), and the selected replication's playback and attribution. 248 `simulation.named_*` keys in each of `en` and `tl`; the Filipino wording quality is UNKNOWN.
- Findings: PostgreSQL `jsonb` does not keep object key order (a first test version failed on it; the key set is now checked, order only on SQLite); `handoff.md`'s "Separate Queue (20 files)" is not enumerated, and 18 files match `*separate*`.
- Gates on the final code: backend full suite 2856 passed, 123 skipped (all PostgreSQL variants), 1 xfailed; within it the named module 137 passed and 5 skipped, all 16 `tests/test_shared_*.py` files 1139 passed, and the 18 `*separate*` files 168 passed. On PostgreSQL 16.15 the named module had 141 passed and 1 skipped (SQLite-only by design), including B1's five points and the light, maximum-structure, busy, and stress round trips. Frontend 61 files and 443 tests (388 before, 55 new); typecheck, lint, and build exit 0. Ruff clean; mypy clean on 200 files.
- NOT TESTED: the spec's Stage 3 browser and local-stack checks; production behavior of any kind.
- Phase status (2026-10-01): LOCAL IMPLEMENTATION COMPLETE; not production or deployment ready. Out of scope and not started: Compare, Decision verdict, D15, Reports, workforce-cost UI or aggregation, roster-optimizer API or UI, G8 release, G9/G-B, generation enforcement.
- Next (needs approval): Stage 3 browser and local-stack integration; production limit verification (with G8); the app-wide NaN-to-500 defect; owner review of the Filipino wording.

## Shared Queue Enhancement: Stage 3 Local Integration (2026-10-01)

This dated update supersedes only the first-slice section's Stage 3 `NOT TESTED` and "Next" statements above. The previous implementation and gate history remains as recorded there. Detailed evidence is in spec section 21.7; browser screenshots and synthetic fixtures are untracked under `output/playwright/stage3/`.

- VERIFIED: `docker-compose.integration.yml` ran locally as `novaq_stage3` with PostgreSQL 16.15; `/healthz` and `/api/ready` returned 200 at `127.0.0.1:18080`.
- VERIFIED: a new shared queue (`unlimited`, `not_modeled`) accepted a two-period aggregate CSV without variance, K, or theta; named validation was runnable with period-aligned staffing. Seed 7 and 9 replications created one completed `shared_named_replications` Job. Browser list, run detail, R6 replication 0 and 8, playback, attribution, and the `X-CSRF-Token` header on named POSTs were checked.
- VERIFIED: variance-bearing aggregate data produced the named M/M/c scope refusal. An intentional stored-row edit in the disposable database produced R6 409 `regeneration_identity` / `stored_row`; restoration was checked by R6 200.
- VERIFIED: legacy shared DES, Compare, Decision, and Reports worked on the same stack. Separate Queue used a synthetic event-derived fixture for a selectable replicated-DES scenario; its selected-plan DES playback, Monte Carlo, validation, conditional Decision, and Reports rendered. The app withheld unsupported savings and ROI. These outcomes are local test results, not operational conclusions.
- VERIFIED: no first-slice defect was reproduced, so no application or test file was changed. Generation enforcement remains `False`. No production access, push, merge, or deployment occurred.
- UNKNOWN: production result-size cap, Render timeout, Cloudflare `/api` limits, production PostgreSQL version, and Filipino wording quality. The 9/52/24/48 limits remain NOT PRODUCTION-APPROVED. The app-wide NaN-to-500 behavior and NumPy pin conflict remain separate findings.

- VERIFIED final-tree gates: backend 2856 passed, 123 PostgreSQL-variant skips, 1 known xfail, 6 subtests; named API on local PostgreSQL 16.15 141 passed, 1 SQLite-only skip; frontend 61 files / 443 tests passed, typecheck, lint, build exited 0; Ruff passed; mypy had no issues in 200 source files; git diff --check passed. The first bare Ruff command could not resolve on PATH, so the installed .venv Ruff executable ran the same gate. No frontend timeout occurred. Build kept its large-chunk advisory.

## Engineering Governance: Zero-Fabrication Protocol (2026-09-25)

Current verified state:

- `AGENTS.md` holds the only copy of the protocol. The product owner's 2026-09-25 directive was merged into it. It adds evidence citation, three more evidence labels (APPROVED SPECIFICATION, INFERRED, NOT TESTED, next to VERIFIED, REPORTED, PROPOSED, UNKNOWN, CONFLICTING), protected mathematics, data integrity, supported analytical conclusions, scope-controlled commits, and a complete, partial, or blocked status in the final report. Every earlier requirement is kept.
- `CLAUDE.md` no longer repeats the protocol. It imports `AGENTS.md` with `@AGENTS.md`. Reason: with a `CLAUDE.md` present, Claude Code reads `CLAUDE.md` and not `AGENTS.md` under the default Project instructions setting (official memory documentation, read 2026-09-25). The 2026-09-25 session on Claude Code 2.1.281 showed the same: its loaded project instructions held `CLAUDE.md` only. The layout, gates, and constraints in `AGENTS.md` reached Claude only when it chose to open the file.
- Stale `AGENTS.md` statements were corrected against source. Model-selection dispatch now names the separate-queue branch that runs first (`model_selection.py`). The CSRF exemptions now include `/onboarding`, as `backend/api/main.py` and `tests/test_production_hardening.py` show. The frontend line names the Cloudflare Pages public deployment. The Session History now says that the Streamlit files it names were removed in `8b0df382`.
- `memory.md` records the adoption and the role of each governance file.
- Skills: none added. Claude Code loads no project skills here (`.claude/skills/` does not exist; `.agents/skills/` holds design skills for other agents). The proposed `novaq-verification`, `novaq-engineering-audit`, and `novaq-workflow-audit` skills were rejected: the Gates section and protocol sections 1, 2, 9, and 11 already cover their procedures, and no repeatable gap was shown.
- Verification (static only): a script checked encoding and CRLF preservation, trailing whitespace, final newlines, fence and inline-code balance, the single `@AGENTS.md` import, that no nested imports exist, that the protocol exists only in `AGENTS.md`, that section numbering is 1 to 11, that every earlier protocol line is still present or deliberately reworded, that outside the protocol only the three corrected lines and the Session History note changed, that every cited path and commit exists, and that only the four governance files changed. No tests or tools read these files, so application tests were not required and were not run.
- NOT TESTED: runtime loading of the import. Headless `claude -p` runs, including `/context`, failed with "Credit balance is too low" before any answer. In the next interactive session, run `/context` (Memory files) or `/memory` and confirm that `AGENTS.md` is listed through `CLAUDE.md`.
- No application source, test, queueing, optimization, DES, Monte Carlo, authentication, schema, API, or report file changed.

Open items:

- CONFLICTING: `POST /onboarding/complete` writes user state (`backend/api/onboarding.py`), but the CSRF middleware docstring in `backend/api/main.py` says exempt families never mutate server state. The session and CSRF cookies are `SameSite=lax` (`backend/api/auth.py`); whether that is enough was not assessed. The exemption was not changed and needs an owner decision.
- The `fix/d1-replication-costs`, `claude/clever-boyd-87ff32`, and `claude/nervous-hodgkin-2b6ef1` worktrees have their own `AGENTS.md` without the protocol and no `CLAUDE.md`. Merging those branches will need care in `AGENTS.md`.
- Resolved: the Session History moved unchanged to `docs/history/agents-session-history.md`, so the `AGENTS.md` that Claude Code loads at session start is now 220 lines, down from 290. The official guidance targets under 200 lines per `CLAUDE.md` file.
- `.claude/launch.json` is untracked and was left alone.
