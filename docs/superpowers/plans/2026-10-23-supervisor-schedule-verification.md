# Supervisor schedule: local verification record

Date: 2026-10-23.
Base HEAD: 151486ee04147f013857f69fe8ce77d899388660.
Branch: codex/supervisor-schedule-20261023.
Checkout: C:/Users/Administrator/.codex/worktrees/novaq-release/NovaQ.

## Scope and current status

VERIFIED: the first approved supervisor design is implemented locally: settings, combined check, review, confirmed break save, then the existing verified scenario save/selection path. The shared optimizer retains its existing path. Seed 42 remains the UI request seed. No queueing-engine, DES/MC methodology, confidence-interval, report, schema, Docker or production configuration files changed.

VERIFIED locally after the owner's "like this execute this" approval: clickable Settings / Review / Confirm tabs now show exactly one panel. The Confirm panel replaces the earlier modal; entering it never saves. The final explicit save still uses the unchanged server recheck and persistence guards. Fresh amendment verification is recorded below; earlier gate results describe the preceding implementation.

Verification is complete within the executed SQLite/browser boundary. The later native PostgreSQL/save/cost addendum below supersedes the original database limitation for that specific scope. This record is not production release approval and closes neither the existing seed-sensitive Decision finding nor unrelated native/manual findings.

## One-panel tabs amendment: fresh verification

Date: 2026-10-23. HEAD and branch unchanged. No commit, push, Docker rebuild or production action.

VERIFIED implementation:

- SupervisorSchedule.tsx: separate active tab state; three linked ARIA tabs/panels; inactive panels use hidden; values/evidence stay mounted. A single roving tab stop, Left/Right, Home/End, Back and Escape work. Check enters Review. Confirm holds the existing explicit break save and plan save/selection actions. Empty panels state that a check is needed. Stale/blocked results cannot persist. Navigation never invokes a computation or write.
- global.css: hidden panels explicitly use display:none; tab colors use existing semantic tokens; phone tabs stack their number and readable label.
- EN/TL translations: symmetric short tab labels, prerequisite and navigation copy.
- SupervisorSchedule.test.tsx: new single-panel, keyboard and retained-state behavior; existing persistence/blocker/freshness cases navigate through Confirm. SetupChangeWorkflowCache.test.tsx changes only its navigation and unused import in this amendment; its invalidation assertions remain.
- Approved spec/plan updated before implementation. No backend/API/math, database schema, exports, runtime configuration or dependency changes in this amendment. Existing earlier backend changes remain part of the uncommitted parent work.

| Fresh gate | Result | Evidence under output/supervisor-20261023/ in the primary checkout |
|---|---|---|
| Focused supervisor/shared/cache tests | 62 passed, 3 files, exit 0 | tabs-focused.log |
| Full frontend suite | 705 passed, 84 files, exit 0 | tabs-frontend-all.log |
| Frontend TypeScript | Passed, exit 0 | tabs-typecheck-final.log |
| Frontend lint | Passed, no emitted findings | tabs-lint-final.log |
| Final production frontend build | Passed, exit 0; existing large-chunk warning | tabs-build-final.log |
| Locale keys | 2,027 identical EN/TL keys | executed JSON key comparison |
| Final diff whitespace / staging | git diff --check passed; nothing staged | executed Git checks |

The full frontend suite preceded a final phone-tab CSS-only adjustment. TypeScript/build and the compiled display matrix were rerun after that adjustment; application TypeScript and test logic did not change afterward. Backend/Ruff/mypy were not rerun for this frontend-only amendment. Their earlier results below are retained as earlier evidence, not fresh execution.

VERIFIED against the compiled UI and a fresh isolated synthetic SQLite API (127.0.0.1:5190 -> 127.0.0.1:8019):

- Click and keyboard navigation show one accessible panel and two display:none panels. Hidden controls are excluded from focus; typed 72.5 survives tab changes. Prerequisites do not invent results. Back/Escape restores Review continuation focus without saving.
- Check is read-only, seed remains 42, and stale inputs disable break/plan saves across tabs. The fresh proposal had two break moves. Explicit Confirm returned 200; exact preview times and all non-break Setup fields were preserved; the rechecked schedule matched. Scenario save returned 201 with verified_snapshot provenance, followed by explicit selection returning 200.
- Final display matrix: EN/TL x light/dark x 375/768/1024/1440 x all 3 panels = 48 combinations. Actual theme state and computed white/dark surfaces were asserted before accepting labels. All 396 final display assertions passed; tab text contrast minimum 6.065:1 and targets at least 44px high. No page overflow in the tested combinations, 667x375 landscape or 200% CSS text sizing. Reduced-motion preference exercised. These are desktop-browser emulation checks, not physical-device, native zoom, native-language qualification or complete WCAG certification.
- No uncaught page errors or external requests during the recorded isolated interaction run. The initial logged-out /auth/me 401 is expected and outside that capture interval.

Evidence: tabs-browser.js, tabs-browser-private.log, tabs-browser-results.json; tabs-layout-final.js, tabs-layout-verified.log, tabs-layout-results.json; tabs-final-*.png. The final EN/light desktop and TL/dark phone screenshots were visually inspected. Full-page captures retain the pre-existing sticky workflow footer; this is not a claim that every possible focus path is unobscured.

Retained failed attempts and corrections:

- Initial new test queries used an unsupported exact option; TypeScript caught it. Corrected without changing assertions. Lint found an unused import after the modal was removed; removed and reran cleanly.
- The first browser run encountered a blank tab. Its later fixture already contained saved changes; API logs established prior writes, but their actor was not established. That run is not counted as final verification. Created a separate synthetic database and unique ports rather than resetting existing data.
- External harness initially used relative API URLs without a base URL. Corrected to absolute loopback URLs; source behavior was not changed.
- The first display harness treated the missing data-theme attribute as an explicit theme. Source getTheme treats missing as light; the initial labels did not prove both themes. Final display harness normalizes that default, waits for the requested theme and checks painted surfaces. Only tabs-layout-verified.log establishes the final theme matrix. Earlier failed/superseded logs remain retained.

Status at this amendment: the requested tab presentation is COMPLETE locally within the tested boundary. Native PostgreSQL/JSONB/concurrency verification was not yet executed at that point; see the later addendum for its completed scope. The seed-sensitive Decision finding remains OPEN. No release GO, operational-safety claim or closure of unrelated native/manual findings is implied. Both task-owned browser sessions were closed and all four task-owned test-server sessions were interrupted after evidence collection; synthetic evidence files are retained.

## Implementation evidence

- backend/api/supervisor_schedule.py: SupervisorPreviewRequest, _check, preview_supervisor_schedule and apply_supervisor_schedule. Additive endpoints reuse existing analytical services. Preview does not write. Apply recomputes, checks the bound request/Setup/dataset/results, rechecks freshness and conditionally writes the draft breaks, preserving legacy Setup fields.
- backend/api/main.py: router registration only.
- frontend/src/api/optimization.ts: additive types and calls.
- frontend/src/components/SupervisorSchedule.tsx: precise percentage entry, slider, optional breaks, combined review, stale-result/persistence guards, confirmation and scenario save/selection.
- frontend/src/components/SeparateScheduleCard.tsx: extracted existing schedule evidence presentation.
- frontend/src/pages/OptimizePage.tsx: separate-queue routing and removal of superseded separate controls; shared controls retained.
- frontend/src/styles/global.css: scoped layout, phone cards and theme-aware controls.
- Both locale JSON files: supervisor strings.
- Tests: tests/test_supervisor_schedule_api.py, frontend/src/components/SupervisorSchedule.test.tsx, and the adapted OptimizePage.test.tsx / SetupChangeWorkflowCache.test.tsx.

New endpoints:

    POST /analyses/{id}/workflow/optimize/separate/supervisor/preview
    POST /analyses/{id}/workflow/optimize/separate/supervisor/apply

Legacy endpoints and queueing-engine implementations were not edited. The chosen limit is explicitly passed to both existing checks; their distinct metric bases are disclosed. An interval crossing zero is described as no clear wait improvement. Longer waits, missing wait evidence, failed accounting, unmet staffing/break limits, stale inputs or non-current planning data block applying breaks.

## Executed gates

Evidence directory: C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/output/supervisor-20261023/.

| Gate | Actual result | Evidence |
|---|---|---|
| Entire final backend collection | 3,409 unique primary cases accounted for: 3,285 passed, 123 skipped, 1 expected failure | backend-partitions.json, four partition logs/XML files, backend-staleness-final.log, backend-final-coverage.json |
| Final frontend full suite | 702 passed; 84 files passed; exit 0 | frontend-all-final.log |
| Final focused supervisor/shared UI | 56 passed | frontend-final-focused.log |
| Migrated cache test and previously unstarted file | 7 passed | frontend-cache-recovery.log |
| Backend lint | All checks passed | ruff-final.log |
| Backend typing | Success, 241 source files; informational untyped-function notes | mypy-final.log |
| Frontend typing | Exit 0 | typecheck-final.log |
| Frontend lint | Exit 0, no emitted findings | frontend-lint-final.log |
| Frontend production build | Exit 0; large-chunk warning emitted | build-final.log |
| Diff whitespace | git diff --check passed before this record | command output |

The initial monolithic backend run was interrupted while progressing slowly. Its incomplete log is not a pass. Every collected node was then assigned exactly once across four isolated processes using the same Python/pytest runtime, -x --tb=short, separate temporary SQLite databases and JUnit outputs. All four exited 0. One subsequently added staleness case passed separately. A fresh final collection equals the partition manifest union that extra case, without missing or duplicate node IDs. Successful subtests are not double-counted as primary cases.

Reproduction helpers: run_backend_partitions.py and summarize_evidence.py in the evidence directory. The latter validates actual browser output and exact final backend collection coverage.

Frontend command:

    npm test -- --pool=forks --maxWorkers=1 --reporter=verbose

Backend commands used the existing root .venv/Scripts/python.exe, PYTHONDONTWRITEBYTECODE=1, and no NOVAQ_TEST_DATABASE_URL. No existing or production database was targeted.

## Actual browser verification

VERIFIED against the final compiled frontend, a fresh synthetic local SQLite database and the real local API:

- Preview preserved Setup, retained seed 42 and blocked plan persistence while break moves remained unapplied.
- Confirmation returned 200, saved the preview's exact times, preserved other Setup fields and returned the same rechecked schedule.
- Scenario save returned 201 with provenance verified_snapshot; selection returned 200.
- Cancel/Escape returned focus. Forward/reverse Tab stayed inside the dialog. Apply focus was not covered.
- English/Filipino and light/dark were checked at 375, 768, 1024 and 1440 px; no page overflow in those combinations. Phone cards matched the actual preview rows.
- Narrow landscape and 200% CSS text-size checks passed. Reduced-motion preference was exercised. This is not physical-device or native-browser-zoom certification.
- No uncaught page errors or external requests occurred during the recorded compiled preview matrix.

Evidence: compiled-style-check.log, compiled-browser-check.log, compiled-final-layout.log, compiled-browser-apply.log, browser-summary.json and final-*.png. The 34 layout assertions and 15 confirmed-flow assertions passed.

Full-page screenshots include the existing sticky workflow navigator, which can appear over a document section in such captures. The separate focus-obstruction assertion used the viewport.

| Measured contrast pair | Light | Dark |
|---|---:|---:|
| Body / surface | 15.680 | 13.238 |
| Hint / surface | 6.065 | 8.546 |
| Input text / input | 15.680 | 11.536 |
| Primary action text / fill | 6.832 | 7.900 |
| Slider/checkbox accent / surface | 6.172 | 9.066 |
| Slider/checkbox accent / control background | 6.172 | 7.900 |

summarize_evidence.py calculates these ratios from actual computed colors using sRGB linearization and relative luminance. This is not a claim of complete WCAG conformance.

## Failures and corrections

- Router-registration indentation was corrected before endpoint tests collected.
- An initial SQLite timestamp comparison refused a valid conditional update. The final conditional write compares Setup JSON, alongside the before-write freshness check. Valid apply, stale input and concurrent-change cases passed.
- Earlier fixtures used a missing temp-parent directory, an illegal mutation of immutable dataset generation, missing upload metadata or a CSRF helper before authentication. Fixtures were corrected without weakening production constraints.
- One focused UI test used the wrong existing label; it now uses Assumptions and limits.
- The first broad frontend run had an integration test calling removed legacy buttons and a fork-worker startup timeout. The cache test was migrated while preserving its no-stale-evidence assertions. The previously unstarted file passed, followed by a clean final full suite.
- An added backend test incorrectly expected decision_stale without a prior Decision. Its fixture now includes prior selection/Decision records, matching the established legacy contract; it passed.
- Visual inspection found cramped phone table headings. Final phone presentation uses equivalent cards.
- The original light-theme gold slider measured 2.081:1 against white. The existing focus token raises that pair to 6.172:1.
- A development preview contained an empty injected global stylesheet. Unstyled captures were excluded. Fresh compiled CSS was confirmed active before the final successful matrix.
- Automatic approval review temporarily stopped the evidence-summary/Docker probe because of its usage limit. The resumed read-only check later completed. This was not a determination that the action was unsafe.

## Remaining limits and release boundary

Historical limitation at the original run: native PostgreSQL, including JSONB/concurrency behavior, was NOT TESTED. The Docker probe reported the missing dockerDesktopLinuxEngine pipe (docker-final.log). The WSL read-only probe failed with Wsl/Service/CreateInstance/CreateVm/ERROR_TIMEOUT. Those failed probes are retained; the later addendum supersedes this limitation for the supervisor save checks only.

Skipped cases are not passing tests. The preserved strict expected failure at tests/test_selected_mc_load.py:147 identifies the existing base-seed-sensitive Decision finding. It remains open; no operational-safety or seed-stability claim is established here.

No commit, push, production migration, deployment or live-account mutation was performed. The later single-panel tab design and native database addendum supersede the corresponding original presentation and database limitations. Normal release gates remain prerequisites for production release.

## Native PostgreSQL, concurrent saves and cost review addendum

Date: 2026-10-23. Same candidate HEAD. Owner started Docker and authorized isolated verification. The subsequent owner request holds deployment for seed-correction research before implementation.

VERIFIED execution against a new temporary PostgreSQL 16 container, using the existing image sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685. Test database/user novaq_test; loopback 127.0.0.1:25433; tmpfs data. No existing NovaQ stack was started, replaced or rebuilt. Exact container 0538528f20e8d4b2c8f83e721cc5964f805dda022eefa81b817e1b78d10a51c2 was label/image checked, evidence retained, and removed after the tests. This does not verify production PostgreSQL configuration or all database behavior.

| Executed gate | Actual result | Evidence under primary-checkout output/supervisor-release-20261023/ |
|---|---|---|
| Original supervisor cases on PostgreSQL | 15 passed, 1 dependency deprecation warning, 36.16s | postgres-initial.log / .xml |
| Final supervisor cases including two new concurrent transaction tests | 17 passed, 1 dependency deprecation warning, 32.16s | postgres-concurrency.log / .xml |
| Focused costing, ROI wording, report integrity, feasibility, comparison, selected Decision and plan save regressions | 91 passed, 3 subtests passed, 1 dependency deprecation warning, 44.69s | cost-save-review.log / .xml |
| Full Ruff check after the test additions | All checks passed | ruff.log |
| Mypy after the test additions | Success, 241 source files; informational untyped-function notes retained | mypy.log |

New tests in tests/test_supervisor_schedule_api.py:175-244 exercise real PostgreSQL transactions. One commits a competing Setup update after the final read and before the conditional write: apply returns 409 and retains that update. The other synchronizes two apply requests immediately before their conditional writes: one returns 200, one 409; the winning schedule matches the preview and other Setup fields remain intact. These extend verification; no production source correction was needed. An initial Ruff import-order failure was corrected, then the full check passed. The full backend/frontend suites were not rerun for these two test-only additions; earlier broad results remain identified as earlier results.

Cost reference in tests/test_costing.py:20-38 verifies 2 servers at 10 currency/server-hour, arrival rate 4 customers/hour, wait .25 hours/customer, waiting cost 100 currency/customer-hour and abandonment fraction .1 at 5 currency/customer: hourly components 20 + 100 + 2 = 122; half-hour 61, two-hour 244. Scalar, vector and summary paths agree. Missing waits retain independently known components but make the total unavailable. Separate comparison still explicitly excludes server cost from Current (backend/api/workflow.py:2511); it does not manufacture savings against a DES total on a different basis. The ROI/report regressions preserve unavailable/incomplete totals rather than substituting zero. This verifies modeled cost handling, not observed payroll or realized savings.

The unchanged seed regression was separately executed with --runxfail and FAILED (output/supervisor-20261023/seed-regression-current.log). Across DES bases 7-11, failing lane counts were [0,0,2,1,1] and Decisions [conditional,conditional,revise,revise,revise]. MC seed remained 42. Its strict expected-failure marker is preserved. Native save verification is closed within the stated scope; the seed finding remains OPEN and deployment is held for the separately registered research.
