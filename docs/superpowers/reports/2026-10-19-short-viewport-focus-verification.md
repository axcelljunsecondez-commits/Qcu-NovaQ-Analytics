# Final focus correction: source verification

Date: 2026-10-19, Asia/Shanghai. **Status: source repair, approved image build and isolated verification VERIFIED in the stated checks. Subsequent local activation and scoped smoke also passed; overall closure remains PARTIAL. See the [activation record](2026-10-19-local-compose-focus-activation.md).**

Owner scope: the existing UX-fix and verification-closure authorization, followed by resume. The specific CSS rules are implementation choices within that scope, not separately owner-selected designs. The owner's rebuild/commit/push approval rule is preserved.

## Verified findings and actual change

The [approved-build addendum](2026-10-19-approved-build-verification-addendum.md) records the failing image check: at 667x375 TL/light the sticky workflow footer covered the keyboard-focused selector. The first source matrix also reproduced sidebar width/main margin-left transitions temporarily covering the selector on an immediate mobile-to-desktop resize.

Only application file changed relative to that frozen candidate: `frontend/src/styles/global.css`.

1. Append the short-height footer rule: at height <=480px, `.workflow-footer` uses `position: static; bottom: auto;`. Existing actions remain after the content.
2. Replace the existing desktop width/margin-left transition with color/background-color/border-color transitions. Collapse/expand handlers, endpoint widths, route and selection remain unchanged.

The final byte comparison established exactly this one-line replacement plus the footer-rule append, preserving all other original bytes and line endings. No API, schema, authentication, labels/i18n keys, mathematics/statistics, simulation/optimization behavior or test assertion changed.

[Specification](../specs/2026-10-19-short-viewport-focus.md) and [plan](../plans/2026-10-19-short-viewport-focus-plan.md). The UI/UX skill's focus-visibility guidance informed the correction; actual execution below establishes its observed behavior.

## Final executed checks

Evidence base in the primary checkout: `output/playwright/verification-closure-20261019/focus-final-runtime/`.

| Check | Actual result |
|---|---|
| Full frontend | Exit 0: 683 tests / 82 files; 296.12s Vitest, 297.05s wrapper. Completed 2026-10-19T03:28:21.166156+00:00. Explicit threads/maxWorkers=1; no assertions/timeouts weakened. |
| Typecheck | Exit 0, 13.76s. |
| Lint | Exit 0, 0.17s. |
| Browser source matrix | 32 immediate-resize cases passed: EN/TL x light/dark x normal/reduced motion x 667x375, 812x375, 1280x720, 390x844. Native Tab focus, five unobscured selector hit-test points, correct value/unique options, no document-width overflow, six preserved step links and reachable Next action were required. |
| Sidebar behavior | PASS under normal motion: 200px -> 64px -> 200px; selected record 2 and route preserved; selector unobscured; zero width/margin-left animations observed. |
| Actual source provenance | Vite identified the worktree's real `global.css`; the temporary proposal style was absent. This is source-level integration, not a new production bundle/image pass. |

The final matrix uses the original immediate-resize sequence **without an animation-settling precondition**. Its running-animation diagnostics recorded paint-only color animation, with no width or margin-left animation. The broad first summary-generator assertion that rejected every animation was corrected to distinguish intended paint animation; browser visibility assertions were not changed.

The browser used a fresh synthetic SQLite API fixture and loopback Vite (8768) with an external test-only proxy to 8767. Inputs remained synthetic 4 arrivals/hour, 6 services/hour/counter, 2 counters, 08:00-09:00. The application database was not used. Evidence: `checks/frontend-checks.json` and logs, `matrix-{en,tl}-{light,dark}.json` and logs, `browser-final-summary.json`, `browser-cli.jsonl`, `browser-http.jsonl`, and screenshots. Named Chrome and verified task-owned Vite/API processes were closed; database/evidence retained in `cleanup.json`.

## Failed attempts retained

The intermediate footer-only source passed 683 frontend tests and 32 **settled-layout** cases (`focus-source-runtime/`). Its immediate TL/light matrix failed twice during the responsive geometric animation; diagnostics identified sidebar links/title over the selector. Those failures, the original runner and the temporary settled-layout experiment are retained. They motivated the second, same-file CSS correction. The final immediate matrix now passes without waiting for those animations, so that resize finding is closed for the tested source cases rather than waived.

The earlier image build remains valid historical evidence for its exact source, but lacks both final CSS corrections and was never activated on the existing stack. Its Nginx/static checks are not transferred as passes for the new candidate.

## Approved image and remaining status

The owner subsequently approved the exact `bea2d37ecac2` rebuild and isolated verification. Tag `novaq-ux-focus-web:20261019-bea2d37ecac2` built with inspect ID `sha256:14b8c0efa13c0db4055f5726c10c5dad1b1f7123b09efafb37b29ac4e6c93ae4`. Nginx/static checks and a fresh 32-case built-asset immediate matrix, sidebar and selector navigation passed. See the [image execution record and remaining status](2026-10-19-approved-focus-image-verification.md); its evidence distinguishes built assets with a synthetic API fixture from existing-stack activation.

Final source SHA256 `bea2d37ecac2b2560e74b238931464e12a33b68c7f797d85e26c8f42f887e5e3`, 256 frozen files. Only `global.css` differs from the previous selector image. `focus-final-prepared-build.json` and `focus-final-only.diff` retain exact provenance. The rebuild request is approved/executed; no additional rebuild is needed for this candidate. The isolated phase did not start/replace existing containers. The later owner-authorized [activation](2026-10-19-local-compose-focus-activation.md) started existing db/API and replaced only web. No commit, push or production action occurred.

OPEN: the prior seed-sensitive Decision failure, requiring separate statistical repair. NOT TESTED: native Excel recalculation/appearance, physical touch, true 200% browser zoom, qualified human Filipino review, native PDF font fidelity, application rollback/fresh-host recovery and production behavior. Backend/Ruff/mypy gates were not rerun for this CSS-only continuation; preservation checks compare the recorded backend/test files instead.
