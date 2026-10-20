# Approved mathematical helper and calculator repairs

Started: 2026-10-15; verification continued 2026-10-16 after owner "resume" and activation approval. Status: **COMPLETE for the approved M1-M3 repairs and local Docker activation; broader reconstruction remains PARTIAL with the limits below.** New API/web images are active and the bounded live checks passed. Only the two itemized API/web containers were replaced after approval. No production action, commit, push, staging or image/volume/cache cleanup was performed. Earlier build/preview/request snapshots below are historical; the activation section records current state.

## Authorization and source gate

Owner explicitly approved implementing the three-item plan, with formula/source/assumption/unit/independent-case mapping before mathematical changes. Owner then confirmed `finals (1).pdf` as the authoritative capstone and asked about workforce scope. The [source register](2026-10-15-formula-source-register.md) was written before application edits. It distinguishes the paper's bibliography from supplementary product references and records unresolved approximation/workforce source gaps.

**VERIFIED citation defect:** the former `mmc_priority` citation to Kleinrock Volume I §3.3 refers to Discouraged Arrivals. Corrected direct reference is Larson/Odoni (1981), *Urban Operations Research*, §4.9.3, equations4.111–4.112, whose two equation images were inspected. No exact uninspected Kleinrock Volume II page was substituted. The capstone PDF was read only and not edited.

## Actual modifications

- M1: `frontend/src/pages/QuickCalculatorPage.tsx` and symmetric EN/TL strings now call the leaving-situation value **Queue workload per customer served**, disclose that it is not an individual customer's average wait, and use that meaning for both neighboring counter interpretations. `quickCalculator.ts` documents the existing returned basis. No numeric conversion or backend Erlang-A formula/contract changed. Tests cover guest/signed-in paths, Filipino wording and independent ordinary-wait limits.
- M2: `backend/queueing_engine/models/queue_models.py:mmc_priority` now uses residual W0=Wq_mmc(1-rho), not the full aggregate wait, in the two class denominators. The existing float-safe saturation guard is reused; unavailable/nonfinite base waits are refused before division. Corrected assumptions/reference and removed the misleading dedicated express/regular lane example. Public success/error structures and function signature are retained. Exact cases and independent aggregate normalization are in `tests/test_priority_reference.py`.
- M3: `backend/queueing_engine/services/costing.py` multiplies both waiting and abandonment hourly flows by interval duration in scalar and vectorized paths. Summary inherits the corrected vector totals. Units are explicit. No changes to input validation, missing-Wq semantics, keys, existing rounding, `shared_day_cost.py` or optimizer hourly objective. References and regression cases are in `tests/test_costing.py`.

## Verification executed so far

Evidence folder: `C:/Users/Administrator/.codex/visualizations/2026/10/14/01a13b2b-3883-7bb2-ad6c-05667dc49ecf/`.

| Command / evidence | Actual result |
|---|---|
| New independent backend regressions before repair, `novaq-repair-reference-before.log` | Exit1: pytest printed14 failed,29 passed,1 warning,2.25s (including duration subfailures). Expected counterexamples, boundary None-division and injected numerical refusal reproduced. |
| Same focused backend tests after repair, `novaq-repair-reference-after.log` | Exit0:41 passed,1 warning,0.91s. |
| Focused frontend first attempt, `novaq-repair-calculator-before.log` | Exit1:2 suite setup failures, no tests ran; Windows sandbox EPERM renaming Vite temp files. |
| Frontend before repair rerun with normal temp access, `novaq-repair-calculator-before-rerun.log` | Exit1:3 failed/14 passed,16.68s; the new EN guest/signed-in and TL assertions reproduced the old average-wait captions. No mathematical target weakened. |
| First frontend after repair, `novaq-repair-calculator-after.log` | Exit1:2 failed/16 passed,9.45s. Caption/numbers were correct; tests clicked InfoTip, whose unchanged focus-open then click-toggle closed it. Explained below; retained log. A mistyped translation-test path selected no file; the actual path was subsequently used. |
| Caption tests using existing hover behavior, `novaq-repair-calculator-after-rerun.log` | Exit0:3 files,21 tests,11.80s, including the actual translation symmetry file. The two subsequently added ordinary-wait cases passed in the full frontend gate below. |
| Original independent audit expectations after repair, `novaq-independent-math-repair-after.log` | Exit0:131 cases,131 passed,0 failed. Used byte-identical copy `novaq_independent_math_repair_after.py`; both script SHA256 values BC6EFBB343507EE075DB2B2141CD3C80402EB2B50D183D056D2AF991233B7B1A. Original six-failure JSON/log retained. |
| Full backend `python -m pytest tests/ -x --tb=short`, `novaq-repair-backend-full.log` | Exit0:3,208 passed,123 skipped,1 xfailed,9 subtests passed,1 Starlette/AnyIO deprecation warning; pytest1521.85s, wrapper1576.9s. No external test DB configured (`NOVAQ_TEST_DATABASE_URL` absent); PostgreSQL-specific cases skipped, not verified. |
| `python -m ruff check .`, `novaq-repair-ruff.log` | Exit0: All checks passed. |
| `python -m mypy .`, `novaq-repair-mypy.log` | Exit0: no issues in237 source files. Existing untyped-body notes retained; type checking does not cover those untyped bodies by default. |
| Full frontend `npm test`, `novaq-repair-frontend-full.log` | Exit0:666 tests in79 files passed,602.72s (wrapper607.07s), configured maxWorkers1. Saved log has2 jsdom canvas getContext warnings, not test failures. |
| `npm run typecheck` / `npm run lint`, `novaq-repair-frontend-typecheck.log` / `novaq-repair-frontend-lint.log` | Both exit0 on host. Production `npm run build` executed inside the web Dockerfile's typecheck/lint/build chain; all completed successfully. No redundant separate host production bundle was run. |
| `docker compose build api`, `novaq-repair-api-build.log` | Exit0,11.39s. Image `sha256:000d04ec1c224a05774766c16ba0267052d68b46d24a4823d21a8f010dfa22cc`,716,998,098bytes. Not activated in the existing API container. |
| `docker compose build web`, `novaq-repair-web-build.log` | Exit0,121.35s. Image `sha256:685bf28a6cdc09176f8416ac2bdabf35e194d4d2a229587411e181422c868b1b`,135,332,808bytes. Typecheck/lint/build chain passed, lint0 warnings/errors; Vite printed its >500kB chunk warning. Existing Dockerfile apk-upgrade stage also refreshed Alpine packages, as printed in the raw log; no Dockerfile edit. Not activated in the existing web container. |
| Changed UI in a real browser | PASS for the bounded preview checks below, using the real existing local Docker API. This is not a claim that the new API/web containers have been activated. |

Host/VM preflight before the sequential full gate printed host total8031.70MiB/free1543.80MiB; Docker allocation4,022,951,936bytes; VM MemAvailable2,939,284kB. Existing API up9h, db healthy, one-shots Exited0, web healthy on its prior image. This is a point-in-time reading, not a guarantee that memory cannot change.

During backend verification another read printed host free956.6MiB; web5.426MiB, API190.7MiB, db51.45MiB and BuildKit19.95MiB container memory. After backend completion, before the single-worker frontend suite, host free1862.8MiB and VM MemAvailable2,931,100kB. No build was run concurrently with those suites.

## Resume and resource record (2026-10-16)

- A late resource diagnostic was not executed because automatic approval review could not complete after an account usage limit. No unsafe-action determination was returned. On owner "resume", later reviewed commands ran successfully; no approval check was bypassed. The already-running frontend suite completed successfully and its session returned exit0.
- Fresh Compose state differed from the earlier healthy snapshot: API Exited137; web/db Exited0, all roughly3h earlier. Inspect returned `OOMKilled=false` for all three. Cause **UNKNOWN**; exit137 alone does not prove an out-of-memory event.
- API existing id `48407dbb00e4549e5b1f4f7d4a2e589f07b6b892231e5abca470df31bdcff17c`; web `767af13c18dd228a9e0c4ce551298041d0813619bc8c395dd732e08e2c22aa18`; db `e7830fab049112dae8382aa27fc58ce87fc9ddfa587d82d982bf842c9f073b2a`. Read-only listener check had no matches at80/8000/5432/5173 before startup (findstr no-match exit1, not a failed Docker inspect).
- `docker compose start db` exited0 and the same db became healthy. `docker compose start api web` exited0, also starting the existing dependent migrate/bootstrap containers; both one-shots exited0. No container was removed/recreated. Recent logs: `Bootstrap user exists.`; Alembic printed PostgreSQL context/transactional DDL headers, no fresh upgrade line in the bounded recent log. Existing API/web were started on their previous images. Both localhost health endpoints returned HTTP200 with `ok` / `{"status":"ok"}`.
- Fresh `docker system df`: Images65,18 active,12.93GB,9.026GB reclaimable; Containers21,1 active at that pre-start reading,491.5kB,450.6kB reclaimable; Volumes19,4 active,5.789GB,2.103GB reclaimable; Build Cache740,30.77GB,21.29GB reclaimable. No cleanup was performed.
- Before builds: host free363.2MiB, free virtual7673.1MiB; Docker VM MemAvailable2,903,844kB. Only the API image was built first. Between API/web builds: host free457.9MiB, free virtual7636.8MiB, VM available2,914,780kB. The web image then built alone. No separate host production bundle process was started; its required `npm run build` runs in the Docker build stage.
- After web build: host free1175.4MiB, VM available2,732,136kB. Read-only `docker compose exec -T api alembic current` printed `0007 (head)`.

## Real-browser preview verification

Temporary Vite server at `http://127.0.0.1:5173`, bound only to127.0.0.1, with the existing configured proxy to the local Docker API on8000. It was started only after both image builds finished. New temporary tab7 was used; existing user tab1/GitHub and tab6/localhost simulation were left untouched. No Home visit or edit. Login used the explicitly approved Compose demo account; no real secret or session token was printed or written into evidence files. No analysis, dataset, plan or simulation was created/modified by these calculator checks.

Synthetic mathematical inputs, not observations:

| Flow | Actual displayed output |
|---|---|
| Guest, leaving: lambda20/h, mu6/h/counter, c2, patience60min | Workload40.8599min, effective busy99.1475%, waiting8.1023, leaving40.5115%. Correct distinct label. Keyboard focus opened the explanatory tooltip; Escape closed it. |
| Guest neighboring counters | c1:140.0110min; c3:12.6822min. Both interpretations disclose workload per customer served and explicitly deny an individual mean-wait interpretation. |
| Guest Basic40/15/3 | Average wait9.5701min; fewer2 counters refused as cannot keep up; more4 counters1.1353min. |
| Guest variable service: lambda2/h, mu4/h, c1, spread0min | Average wait7.5min, the independent deterministic-service PK limit; neighbor c2 displayed0.5min under the disclosed approximation. This does not validate arbitrary service distributions. |
| Guest limited space: lambda2/h, mu4/h, c1, K1, optional spread blank | M/M/c/K, average wait0min, turned-away33.3333%, one counter only; no invalid neighbor request. |
| Signed-in leaving, same20/6/2/patience60 | Workload40.8599min, same correct label and all three interpretations. Signed-in workspace/account controls were visible. |
| Filipino, signed-in leaving | Correct new label and distinct-meaning sentence rendered; translated tooltip opened by keyboard. Native-language quality remains NOT TESTED. |
|375x812 viewport, Filipino | Label wrapped within the card; DOM viewport375px and document scroll width360px (no horizontal overflow in this inspected page). Temporary viewport override was reset; English restored through the menu. |

Captured browser warning/error list for this tab was empty. Evidence: `novaq-repair-browser-evidence.json`, `novaq-repair-calculator-guest.png`, `novaq-repair-calculator-signed-in-viewport.png`, `novaq-repair-calculator-filipino.png`, `novaq-repair-calculator-mobile-label.png`. The first full-page signed-in screenshot visibly distorted the fixed sidebar; DOM width was200px and a fresh normal viewport screenshot showed its correct position/width. That full-page capture is retained but is not used as layout proof.

The temporary tab was closed and Vite stopped with Ctrl-C (session exit1 after the intentional stop). Its terminal emitted repeated `Assets in public directory cannot be imported from JavaScript` warnings for EN/TL JSON; existing `frontend/src/lib/i18n.ts:3-4` imports those public files. No translation-import configuration was changed. Both language views worked in this browser check, and the separate production build passed; the development warnings remain a disclosed limitation, not silently repaired in this scope.

## Historical itemized activation request (before approval)

Proposed command, only after owner approval and rechecking these identities:

```powershell
docker compose up -d --no-deps --no-build api web
```

| Existing container to be removed/recreated | Exact ID | Measured writable layer |
|---|---|---:|
| `ux-workflow-audit-api-1` | `48407dbb00e4549e5b1f4f7d4a2e589f07b6b892231e5abca470df31bdcff17c` |8192bytes (8KiB)|
| `ux-workflow-audit-web-1` | `767af13c18dd228a9e0c4ce551298041d0813619bc8c395dd732e08e2c22aa18` |81920bytes (80KiB)|

Measured old writable layers total90,112bytes (88KiB). This is not a promise of net host-disk recovery: logs/metadata, shared layers, new-container allocation and Windows VHDX compaction mean **net Windows space freed is UNKNOWN**. Neither container has a mounted volume. Keep db container `e7830fab049112dae8382aa27fc58ce87fc9ddfa587d82d982bf842c9f073b2a`, named volume `ux-workflow-audit_pgdata` and both one-shot containers. Do not issue image, volume or cache removal/prune commands. No Docker cleanup/removal command was issued by this agent. The new API/web image identities are in the verification table above.

**Failed retention lookup:** a final attempt to inspect the two previous container image IDs directly returned `No such image` for both old API `sha256:aac286d798276e949d9ef5b4d04783302d3bbd41a2ae5d90b1d6a0db47be34ef` and old web `sha256:987e2c88e52e426ed995bb967ada948156d14d166c65bd0399bea50f0229d698`. Their containers still report those IDs and remain running/healthy as applicable. The image lookup itself failed even though later independent Compose/health commands succeeded. Reason, old image-object/layer retention and rollback-image availability are **UNKNOWN**; do not claim the old images were verified retained or were deliberately deleted. This work issued builds that retag the service names, not image cleanup commands. Preserve the running old containers until the owner approves their specific replacement with this limitation disclosed.

Pre-activation live state: API running on old image `sha256:aac286d798276e949d9ef5b4d04783302d3bbd41a2ae5d90b1d6a0db47be34ef`; web healthy on old image `sha256:987e2c88e52e426ed995bb967ada948156d14d166c65bd0399bea50f0229d698`; db healthy; migrate/bootstrap Exited0. Both health bodies/HTTP200 passed. Bounded last150-lines/since15-minutes API/web log read matched zero `Traceback`, `Internal Server Error`, `" 500 ` or `ERROR` lines. This does not certify all historical logs or paths.

Pre-activation `docker compose ps -a` (exit0), summarized from `novaq-repair-final-compose.log`:

| Service | Actual status | Actual port |
|---|---|---|
|api|Up17minutes|127.0.0.1:8000->8000/tcp|
|bootstrap-admin|Exited(0)17minutes ago|none|
|db|Up18minutes(healthy)|127.0.0.1:5432->5432/tcp|
|migrate|Exited(0)17minutes ago|none|
|web|Up17minutes(healthy)|127.0.0.1:80->8080/tcp|

Final repository checks: `git diff --check` exit0, staged-diff exit0 (nothing staged), protected-path diff exit0. HEAD remains `0b9423ec66d32620ed91769ac35a10e51ffae2ec`. Temporary preview listener count at5173 was0 after its stop. Evidence: `novaq-repair-final-diff-status.log`, `novaq-repair-final-compose.log`, `novaq-repair-container-refresh-plan.json`. No commit/push or production access.

## Approved activation and live verification (2026-10-16)

The owner replied "approve" to the itemized API/web replacement after the old-image lookup and UNKNOWN rollback limitation were disclosed. The sandbox first denied Docker/CIM/WSL diagnostics; those failures are not valid zero-memory readings. Reviewed local permissions then allowed the checks and approved mutation. Before activation, `docker info --format '{{.MemTotal}}'` printed4022951936; host free1165.2MiB and VM MemAvailable2915528kB. `docker system df`: images65/16active/12.94GB/9.074GB reclaimable; containers21/4active/499.7kB/348.2kB reclaimable; volumes19/4active/5.789GB/2.103GB reclaimable; build cache747/30.83GB/21.35GB reclaimable. No rebuild or cleanup was run during activation. Net Windows disk recovery remains UNKNOWN.

The approved command `docker compose up -d --no-deps --no-build api web` started at03:27:50+08:00 and exited0 in10.89s. Both targets were recreated and started. Inspect established:

| Service | New container ID | Active image ID |
|---|---|---|
|api|`6a5f8e87475457293dd6df426d22b44402b5696ff4148c523f2330918386162c`|`sha256:000d04ec1c224a05774766c16ba0267052d68b46d24a4823d21a8f010dfa22cc`|
|web|`71bc233c6f144b291854f188e5a100e298396da6be8938fc09c374622562464a`|`sha256:685bf28a6cdc09176f8416ac2bdabf35e194d4d2a229587411e181422c868b1b`|

The db, migrate and bootstrap-admin IDs, StartedAt values and mounts matched the saved before snapshot exactly. The database volume remains `ux-workflow-audit_pgdata`; neither one-shot was rerun by this activation. `docker compose exec -T api alembic current` printed `0007 (head)`. The retained migration log contains `Running upgrade 0006 -> 0007, add the saved closing rule for the continuous shared-line run (B4a)`; this is historical migration evidence, not a newly executed upgrade.

Actual HTTP checks: `/healthz` body `ok`, HTTP200; `/api/health` body `{"status":"ok"}`, HTTP200. The new API completed configuration preflight and startup. The since10m/last150-lines server scan found0 error-pattern matches. Nginx printed2 warning lines that its `user` directive is ignored when the master runs without super-user privileges; retained, not repaired in this scope.

Seven synthetic reference cases executed inside the new API image, exit0,7 passed/0 failed: four exact priority cases and three interval-duration cases checking scalar/vector/summary components and totals122/61/244 for1/.5/2hours. Script and raw output: `novaq-repair-activated-reference.py` and `.log`. These bounded cases do not certify every formula or dataset.

Signed-in browser checks ran against `http://localhost/tools/calculator`, using temporary tab8 and the existing demo session. Erlang-A20/6/2, patience60min displayed the repaired workload label and40.8599min, including the distinct-meaning text and neighboring values140.0110/12.6822min. Basic40/15/3 displayed9.5701min with the ordinary average-wait label; c2 refused and c4 showed1.1353min. No analysis, plan, dataset or simulation record was created. The tab captured no warning/error entries and was closed afterward; existing user tabs were untouched. Evidence: `novaq-repair-activated-browser.json` and `novaq-repair-activated-calculator.png`. This verifies the new Docker runtime for the inspected paths, independently of the earlier Vite preview.

Final `docker compose ps -a` at03:31:39+08:00, exit0 (`novaq-repair-activated-final-compose.log`):

| Service | Actual status | Actual port |
|---|---|---|
|api|Up3minutes|127.0.0.1:8000->8000/tcp|
|bootstrap-admin|Exited(0)40minutes ago|none|
|db|Up42minutes(healthy)|127.0.0.1:5432->5432/tcp|
|migrate|Exited(0)40minutes ago|none|
|web|Up3minutes(healthy)|127.0.0.1:80->8080/tcp|

After activation, memory readings printed host free655.2MiB and VM MemAvailable2854356kB; container memory web5.184MiB, API167.2MiB, db48.11MiB and BuildKit20MiB. These are point-in-time readings.

Artifacts: `novaq-repair-activation-preflight.log`, before/after JSON, activation log/result JSON, activated health/migration/reference/browser evidence and final server/Compose logs. An optional source read used `backend/entrypoint.sh` and returned not found; the inspected Dockerfile names `backend/api/entrypoint.sh`. The read did not affect runtime gates. A documentation patch failed its context check without writing files; the corrected scoped patch succeeded.

Final repository verification: the first check used an unnecessary command-local `core.autocrlf=false` override and exited2, treating existing CRLF carriage returns as trailing whitespace. Repository `core.autocrlf` is `true`; the normal required `git diff --check` exited0, with its existing LF/CRLF conversion warnings. No Git configuration or source line endings were changed to obtain the pass. The failed diagnostic log is retained separately from the normal rerun log. Staged diff and protected-path diff both exited0; HEAD remains `0b9423ec66d32620ed91769ac35a10e51ffae2ec`. Only the phase records were edited during activation.

Open `http://localhost`, sign in with Compose demo `admin@example.com` / `admin123`, and refresh an already-open tab to load the rebuilt bundle. From this worktree, `docker compose down` stops/removes stack containers while retaining the database volume (do not add `-v`); `docker compose up -d` starts again without a rebuild. These stop/start instructions were not executed during activation.

## Limits and unresolved issues

- No global Results/report Erlang-A caption repair is claimed. These use separate processed/persisted row paths; a new live Erlang-A analysis/report was not created. See source register for the exact trace and contract boundary.
- Existing InfoTip opens on hover/focus and toggles on click. The test's first click closed the focus-opened tooltip. The repair verifies caption content using hover; the shared component is unchanged and click interaction remains an out-of-scope limitation to audit separately.
- Paper/book metadata correctness is separate from formula correctness. Exact edition equation pages for the two main capstone books are uninspected. Direct Whitt passage, arbitrary-distribution MGc/MGcK accuracy and full independent workforce verification remain UNKNOWN/NOT TESTED as detailed in the source register. No blanket correctness certificate.
- Native Filipino wording review, native Excel recalculation and production behavior are NOT TESTED. No observation or service sample was invented to bypass the aggregate routing-DES gate.
- Existing unrelated reconstruction changes and untracked `novaq_local.db` were retained. Source diff for Home, authentication, APIs, ingestion, model dispatch, schemas, DES algorithms, shared-day cost and the unrelated optimizer is empty. AST comparison against HEAD returned True for everything in queue_models except `mmc_priority`, and everything in costing except the two authorized interval helpers; priority signature and success keys are identical. Final whitespace/staging checks are recorded in the final status artifact.
- The itemized API/web replacement permission was consumed by this successful activation. Any future Docker container recreation/removal requires fresh itemized owner approval. Broader reconstruction defects and source gaps above remain outside this completed repair scope.
