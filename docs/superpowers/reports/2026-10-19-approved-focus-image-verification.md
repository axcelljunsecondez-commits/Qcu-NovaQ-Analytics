# Approved focus image: verification and remaining status

Date: 2026-10-19, Asia/Shanghai. **Scoped rebuild and isolated verification: COMPLETE. Subsequent local activation also completed; overall closure remains PARTIAL.** See the [activation execution record](2026-10-19-local-compose-focus-activation.md). Statements below about untouched/stopped existing containers describe the earlier isolated phase.

Owner authorization: “Approve rebuild and isolated verification”, responding to the exact `novaq-ux-focus-web:20261019-bea2d37ecac2` request. No existing NovaQ container was started or replaced; no commit, push, production action or mathematical repair occurred.

## Exact built candidate

- Worktree: `.claude/worktrees/ux-workflow-audit`, branch `feat/ux-u1-shell`, HEAD `0b9423ec66d32620ed91769ac35a10e51ffae2ec`, plus preserved dirty source.
- Tag: `novaq-ux-focus-web:20261019-bea2d37ecac2`.
- Docker image inspect ID: `sha256:14b8c0efa13c0db4055f5726c10c5dad1b1f7123b09efafb37b29ac4e6c93ae4`.
- Canonical source manifest SHA256: `bea2d37ecac2b2560e74b238931464e12a33b68c7f797d85e26c8f42f887e5e3`; all 256 source/context file hashes checked before the build.
- Build exit 0, 57.52 seconds, 2026-10-19T03:31:49.987252Z to 03:32:47.500949Z (11:31–11:32 local). Dockerfile typecheck/lint/build succeeded. Lint reported 0 warnings/errors; Vite's large-chunk warning remains. Existing `apk upgrade` upgraded 22 packages; exact versions are in the build log. Source identity does not establish bit-identical image reproducibility.

Evidence in the primary checkout: `output/playwright/verification-closure-20261019/`: `focus-final-prepared-build.json`, `focus-approved-build.log`, `focus-approved-build-result.json`, `focus-image-verification.json`, `focus-image-runtime/`, and `focus-approved-final-preservation.json`.

## Actual change and executed verification

The [source correction report](2026-10-19-short-viewport-focus-verification.md) records both real defects, their failing attempts and the exact bounded correction. Only `frontend/src/styles/global.css` changed relative to the earlier selector image: the footer returns to normal flow at viewport height <=480px, and desktop width/margin-left transitions are replaced by color/background/border transitions. Workflow actions, collapse endpoints, route/selection handling, labels, APIs, schemas and mathematics were not changed by this correction. The archived-selector component/test correction is also included in this frozen candidate.

| Executed check | Actual result and limit |
|---|---|
| Fresh final source frontend gates | PASS: 683 tests / 82 files; typecheck and lint exit 0. Explicit thread pool/maxWorkers=1. Completed before the approved build; frozen hashes establish the source correspondence. No assertion/timeout weakened. |
| Isolated image startup/configuration | PASS: Nginx started; `nginx -t` exit 0 and `/healthz` returned 200 with `ok`. Unprivileged `user` directive warning retained. |
| Nginx static files and SPA fallbacks | PASS: all 66 image-extracted files matched served bytes; root and `/analyses/2/data` returned the same index. Image API upstream deliberately had no connected application API. |
| Built-asset browser matrix | PASS: 32 immediate-resize cases, EN/TL x light/dark x normal/reduced motion x 667x375, 812x375, 1280x720, 390x844. Normal Tab focus, all five selector hit-test points, correct selected identity/options, no document-width overflow, six step links, correct short-height footer behavior and reachable Next action required. No animation-settling precondition. |
| Sidebar collapse/expand | PASS under normal motion: 200 -> 64 -> 200px, record 2 and `/analyses/2/data` preserved; selector unobscured, no width/margin-left animations observed. |
| Built asset provenance and selector navigation | PASS: browser stylesheet `/assets/index-Ds2szXmS.css`; no Vite/proposal style. All 66 fixture-served files matched image hashes. Archived route selected 2 exactly once; switching to 1 navigated to `/analyses/1/data` with value/options 1. |
| Visual sampling | Viewed actual TL/light and TL/dark 667x375 screenshots: focused selector visible. This sampling does not assert whole-application accessibility or qualified language review. |

The browser fixture served the exact extracted image assets at loopback 8767 with the current real API source, `FakeEmailSender` and a new synthetic SQLite database. Existing helpers supplied 4 arrivals/hour, 6 services/hour/counter, 2 counters, 08:00–09:00; these are synthetic access/UX inputs, not operational measurements. The application database was not used. Separate Nginx static tests used loopback 8870. These checks do **not** establish existing-stack Nginx/API integration or PostgreSQL deployment behavior.

Only pre-login `/api/auth/me` returned the expected 401; subsequent recorded API requests succeeded. The built matrix observed `color`, `flex-grow`, `min-height` and `order` animation properties; none was width/margin-left, and every immediate visibility assertion passed. It is not claimed that all animation is absent.

## Preservation and cleanup

- Final image archive retained: `candidate-focus-web-bea2d37ecac2.tar`, 38,289,408 bytes, SHA256 `4bfcd7412cb2f536ffff95976477320ebfa3d522bc0d3108e5a99d1cdf628dc8`.
- Both prior archives retained and rehashed. Archive loading and actual application rollback remain NOT TESTED.
- Task-owned container `d7a656af9d5471026c1d4abedb2ce76b52af5e313bd36ba1ae7a0bc9bb71135f` was checked by full ID/name/image/purpose label, stopped and removed. Its logs, image, archive and extracted files remain.
- Named Chrome `novaq-focus-image-20261019` closed. Identity-verified synthetic fixture PID 17916 stopped; its database/evidence retained. Verification ports closed after cleanup.
- Existing web/API/database IDs, images, states, restart counts and mounts matched the pre-build records after cleanup. All three remain exited 255; their exit cause is UNKNOWN. No restart/replacement performed.
- Final source/context, 232 recorded backend/test baseline files, HEAD and staged diff checked unchanged. `git diff --check` passed. This is scoped preservation, not a clean-working-tree claim.

## Remaining status

| Item | Status / next requirement |
|---|---|
| Selector identity, short-height focus, resize obstruction; exact candidate build | VERIFIED for the executed source/image cases; scoped local gates closed. |
| Existing-stack activation and integrated smoke | Subsequently VERIFIED in the scoped [activation record](2026-10-19-local-compose-focus-activation.md) under the owner's separate “update it” instruction. No further rebuild needed. |
| Seed-sensitive Decision | OPEN: unchanged prior `--runxfail` execution failed. Seeds 7/8 gave conditional; 9/10/11 revise. Separate statistical scope, authorization, independent references and regression verification required. Literature does not waive the failure. |
| Native Excel recalculation/appearance | NOT TESTED: native setup observation/session gates unavailable in this thread; no registration retry loop repeated. |
| Physical touch; true 200% browser zoom | NOT TESTED; viewport resizing and reduced-motion emulation do not verify them. |
| Qualified Filipino review; native PDF font fidelity | NOT TESTED; rendered text and browser images are not those manual/native checks. |
| Default fork-pool reliability | UNKNOWN; the successful suite explicitly used threads. |
| Production; application rollback; fresh-host recovery; owner PostgreSQL restore | NOT TESTED and outside this local approval. |

No unresolved failure was waived, and no whole-project completion claim is made. The new candidate supersedes the earlier selector-only image for these UX repairs. This isolated phase stopped at its authorization boundary. The subsequent owner-authorized activation is recorded separately; commit/push remain unperformed.
