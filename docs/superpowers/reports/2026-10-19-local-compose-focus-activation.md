# Local Compose activation: verified focus image

Date: 2026-10-19, Asia/Shanghai. **Local image activation and scoped connected verification: COMPLETE. Overall verification closure: PARTIAL.**

Owner authorization: “update it”, after the assistant identified the new local image, old Compose web image, stopped services and the exact intended action: start the existing db/API, replace only web with the verified image, and test the connected app. This authorized that local action. No rebuild, pull, migration/bootstrap rerun, commit, push or production action occurred.

## Actual update

The retained override `output/playwright/verification-closure-20261019/activation/verified-images.compose.yml` pins web to `novaq-ux-focus-web:20261019-bea2d37ecac2` and preserves the API image reference `novaq-excel-api:20261018-7dac44d078c2`, both with pull policy never. Base Compose ports were not changed. Docker Compose recorded the override in the new web container's labels.

Executed commands, in order:

1. `docker start e7830fab049112dae8382aa27fc58ce87fc9ddfa587d82d982bf842c9f073b2a`: exit 0, 3.20s; actual `pg_isready -U novaq -d novaq` returned accepting connections.
2. `docker start 0e6b336685421290baa8417630bc88238c0f4f4c735af8857a08bc9528fb0277`: exit 0, 1.02s; `/health` and `/ready` each returned 200 before web replacement. The copied deployed entrypoint runs configuration preflight and Uvicorn, without migration commands.
3. `docker compose --project-name ux-workflow-audit --file <worktree>/docker-compose.yml --file <evidence>/activation/verified-images.compose.yml up --detach --no-deps --no-build --pull never web`: exit 0, 3.02s; Compose recreated/started only web. Full absolute command/outputs are in `activation-result.json`.

Execution: 2026-10-19T05:26:02.542370Z to 05:26:34.880349Z (13:26 local). New web container `0725122066c1eb54fffe6a89efe8ed921c3dd88dcdb5f237bccf6f23d9b32c95` uses image `sha256:14b8c0efa13c0db4055f5726c10c5dad1b1f7123b09efafb37b29ac4e6c93ae4`. Source manifest remains `bea2d37ecac2b2560e74b238931464e12a33b68c7f797d85e26c8f42f887e5e3`.

## Executed connected checks

| Check | Actual result |
|---|---|
| Service state | Web running/healthy; existing API running; existing db running/healthy. API has no Docker HEALTHCHECK; its health/readiness are verified by actual HTTP 200. |
| Localhost static content | PASS: all 66 candidate image files matched served bytes; root/deep-link/health brought the total to 69 static-route checks. |
| Nginx-to-API proxy | PASS: `/api/health`, `/api/ready` and `/api/auth/config` returned 200; unauthenticated `/api/auth/me` correctly returned 401. |
| Database revision | Read-only `SELECT version_num FROM alembic_version` returned `0007`. This is a revision read-back, not a schema migration or restore test. |
| Sign-in and existing analysis | Documented local admin login succeeded. The real list rendered 11 analyses. Opened existing `SYNTHETIC — Excel layout activation QA (2026-10-18 UTC)`, analysis 11; no analysis/dataset/scenario save, upload or computation rerun. |
| Activated light/dark focus and layout | Four EN normal-motion cases passed: light/dark x 667x375 and 1280x720. Normal Tab focus, five unobscured selector points, value 11 present once, no document-width overflow, six step links, static short-height/sticky desktop footer and reachable Next action required. Built CSS `/assets/index-Ds2szXmS.css` observed. Actual narrow screenshots inspected in both themes. |
| Sidebar | PASS: 200 -> 64 -> 200px. Initial light theme restored. No non-GET API requests occurred during the matrix. |
| Browser/runtime observations | Only expected pre-login auth/me 401 in inspected console; no later console entries recorded. No page errors observed during the matrix. The matrix itself made no additional API requests; earlier navigation/auth requests are separate evidence. Bounded activation log patterns matched zero traceback/5xx/emerg/fatal lines; not an exhaustive error audit. |

The prior source suite (683 tests / 82 files, typecheck/lint) and 32-case EN/TL x themes/motion/viewports isolated matrix remain evidence for this exact frozen image. They were not rerun or relabeled as new connected-stack tests. No mathematical, data-integrity or whole-application correctness conclusion follows from these smoke checks.

## Preservation, initial preflight correction and warnings

- API and db full IDs/images/configuration/host configuration/mounts are preserved; only their authorized running state/start time changed. Database volume remains `ux-workflow-audit_pgdata`.
- Migration/bootstrap containers retain their IDs, full states, start times and restart counts; neither was rerun. The older `/novaq-report-archive-startup-20261017` test container was untouched.
- The first preflight exited 1 because enumeration by Compose project/service labels also included that archive-test container as an API. The diagnostic initially suggested an ID change; direct inspection established the canonical API ID was unchanged. Exact-name filtering corrected the verification harness, not the application. Initial inspection and corrected preflight are retained; no container mutation preceded the successful preflight.
- All 256 frozen source hashes and three retained archive hashes passed the preflight. No application source changed during activation. Final HEAD/staging and source preservation are recorded in `activation/final-preservation.json`; no clean-working-tree claim is made.
- PostgreSQL logs report recovery after an interrupted shutdown, then a completed recovery checkpoint and readiness. The original shutdown cause is UNKNOWN. Existing Nginx unprivileged-user warning remains. No image/volume/cache cleanup or restore was executed; actual application rollback remains NOT TESTED.
- The test admin session was logged out, theme restored to light, and only Chrome session `novaq-focus-active-20261019` closed. Application containers remain running for the owner.

Evidence in the primary checkout: `output/playwright/verification-closure-20261019/activation/`: plan/override, `preflight.json`, `containers-before.json`, copied entrypoint, `activation-result.json`, `localhost-http-verification.json`, `browser-verification.json`, CLI evidence/screenshots, `runtime-preservation.json`, scoped logs and `final-preservation.json`.

## Remaining status

The requested local Docker update is complete. Seed-sensitive Decision remains OPEN under its separate protected-statistics scope. Native Excel recalculation/appearance, physical touch, true 200% zoom, qualified Filipino review, native PDF font fidelity, production and recovery/actual rollback remain NOT TESTED; default fork-pool reliability UNKNOWN. No additional rebuild or activation is needed for this verified local candidate. Commit/push remain unperformed and require the owner's separate instruction.
