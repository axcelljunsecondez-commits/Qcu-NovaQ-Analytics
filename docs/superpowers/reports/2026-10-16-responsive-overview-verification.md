# NovaQ responsive overview — implementation and verification

Date: 2026-10-16, Asia/Shanghai.

**Status: approved local web refresh COMPLETE; broader acceptance PARTIAL.** The approved presentation changes are implemented, the exact web-container replacement was subsequently approved and performed, and actual Docker-served browser checks passed within the recorded scope. Native touch, 200% browser zoom, reduced-motion emulation, native Excel recalculation and other limits below remain NOT TESTED. This is not a production release or a claim that all NovaQ reconstruction work is complete.

The owner approved implementation after the combined preview: “approve with no hallucination and zero fabrication, be professional as a full stack devs”. The [approved specification](../specs/2026-10-16-responsive-overview-ui-refinement.md) and [implementation plan](../plans/2026-10-16-responsive-overview-ui-refinement-plan.md) define the scope. General UI approval does not replace the separate Docker removal rule in the [reconstruction plan, phase 5](../plans/2026-10-15-post-sign-in-reconstruction-plan.md). After reviewing the exact container, candidate and 80 KiB layer disclosure, the owner separately replied “approve”; only that bounded web replacement was then executed.

## Verified source and change boundary

- Implementation checkout: `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/.claude/worktrees/ux-workflow-audit`, branch `feat/ux-u1-shell`, HEAD `0b9423ec66d32620ed91769ac35a10e51ffae2ec`.
- Root `main` is a different checkout at `6093d78a5874d8cbdfa0026e9c25bdb5ddc70881`. Neither HEAD was advanced by this task. No stage, commit or push was performed.
- Existing dirty reconstruction and mathematical-repair work was preserved before editing. The task baseline contains 616 source/document files and byte copies, plus working/staged diffs. Comparison: 593 baseline files unchanged, 23 modified (21 existing frontend files and these two task documents), none missing. Five frontend files were added; this report is a sixth new file.
- All 281 protected baseline files under `backend/`, `tests/` and `frontend/src/lib/` are byte-identical to the task baseline. Existing EN/TL values are preserved. The two stylesheet changes insert scoped rules; they do not delete/change prior rules. OptimizePage's handler/state/payload section is identical to baseline. The staged diff is unchanged and `git diff --check` passed.
- These comparisons establish preservation of the inspected baseline. They do not independently establish the mathematical correctness of pre-existing repairs, certify every application state, or verify production.

Evidence directory for commands, scripts, original files and manifests:

`C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/output/ux-audit-2026-10-16/implementation/`

Key records: `before.json`, `original/`, `before.diff`, `before-staged.diff`, `preservation.json`, `own-changes.diff`, `final-source-evidence.json`, `final-diff-check.log`. The task diff is against the preserved dirty baseline, not just Git HEAD.

## Actual modifications

Paths below are relative to the identified implementation checkout.

| Files | Actual change and reason |
|---|---|
| `frontend/src/styles/theme.css`, `global.css` | Signed-in `.app-shell` tokens for light/dark, readable supporting text, navy text on gold, explicit status/focus/disabled pairs, bounded form/select layouts and wrapping. Body/input target 16px; sampled functional labels at least 14px. Fixed the measured mobile Setup grid overflow. Scoped reference-table scrolling and mobile operational lists. Root/public styles retained. |
| `components/analysis/AnalysisSelector.tsx` and its new test, `AnalysisWorkspace.tsx` and test | Shared controlled selector, full name description and bounded width; workspace analysis name becomes context rather than a second h1. Existing selection/navigation handlers retained. |
| `pages/ResultsPage.tsx` and test, `components/results/ResultsSummary.tsx` and new test, `ResultsDetails.tsx` | Default view shows operational fields; wide technical values and explanations move to the allowlisted `view=reference` branch on the same route. File/period/line survive reference/return links. Mobile list retains every summary field. Existing current-dataset guard retained; added matching-dataset guard for observed wait. |
| `components/results/KeyResults.tsx`, `FileSelector.tsx`, `BusyStrip.tsx`, `ResultsCharts.tsx` | Removed redundant calculation disclosure and duplicate chart/strip numeric tables from the default screen. Kept source identities, unavailable/unstable warnings, units, period filters, exact chart values and target warnings. Charts use semantic textual lists with decorative bars. Single-period summary keeps its target warning. BusyStrip's default retains numbers for other callers. Removed “coming later” filler. |
| `components/ui/InfoTip.tsx` and new test | Signed-in opt-in behavior: first activation pins open, repeated activation closes; Escape/outside/blur dismiss. Viewport-bounded popup and pointer transition handling. Existing compatibility default retained for guest consumers. |
| `pages/OptimizePage.tsx` | Controls precede full-width results; responsive fields and semantic color tokens replace fixed light fills/foregrounds. No handler, state, optimization objective, request or mathematical change. |
| `pages/ReportsPage.tsx` and test, `api/reports.ts`, `components/results/PlanChanges.tsx` | Report context uses actual preview plan/source file fields and an available finite shared demand multiplier; missing multiplier is not invented. Optional types describe existing preview fields. Reports link says “View plan exports”. Existing export endpoints, workbook/PDF generation, refusal/gating and Decision semantics retained. |
| `pages/QueueSimulationPage.tsx`, `QuickCalculatorPage.tsx` | Shared selector markup and signed-in stable explanation opt-in, respectively. Existing simulation/run-basis and calculator math changes from before this task remain intact. |
| `frontend/public/locales/en/translation.json`, `tl/translation.json` | Thirteen new keys in both languages; all pre-existing key/value pairs retained. |
| Two responsive-overview spec/plan documents, this report | Recorded approval, narrow BusyStrip scope addition, actual completion evidence and remaining acceptance work. |

No Bootstrap, dependency, font, backend, schema, report generator, auth/CSRF, protected numerical helper or public-page implementation was changed by this task. New component paths in the table are under `frontend/src/`.

## Executed verification

Commands ran in the implementation checkout, frontend commands in `frontend/`. Python used the root `.venv/Scripts/python.exe`, not bare system pytest. Log names below refer to the evidence directory.

| Check | Actual result | Evidence |
|---|---|---|
| Full frontend: `npm.cmd test -- --pool=threads` | **681 passed, 82 files**, printed duration 831.94s. Same tests/assertions and existing 10s test timeout; CLI worker-pool override only. The shell session was lost after a new user turn, so a final wrapper exit code was not recovered; the complete passing Vitest summary was observed. | `frontend-tests-thread-final.log` |
| Backend: `python -m pytest tests/ -x --tb=short -o faulthandler_timeout=120 --basetemp=<task evidence>/pytest-temp-host` | Exit 0; **3,208 passed, 123 skipped, 1 xfailed, 9 subtests passed**, one Starlette/AnyIO deprecation warning. Printed duration 5390.65s. Skipped/expected-failing cases are not claimed passed. | `backend-tests-host.log` |
| `python -m ruff check .` | Exit 0, all checks passed. | `ruff-final.log` |
| `python -m mypy .` | Exit 0, success in 237 source files; annotation-unchecked notes remain. | `mypy-final.log` |
| `npm.cmd run typecheck` | Exit 0. | `typecheck-final.log` |
| `npm.cmd run lint` | Exit 0. | `frontend-lint-final.log` |
| `npm.cmd run build` | Exit 0, wrapper 23.0692s; Vite printed built in 2.88s. Existing >500kB chunk warning, including QueueSimulationPage 1,535.18kB, remains. | `frontend-build-final.log`, `frontend-build-status.json` |
| Unique Docker web build | Exit 0, wrapper 72.5116863s. Existing Dockerfile also ran frontend typecheck/lint/build. Only this web image was built in this phase. | `docker-web-build.log`, `docker-web-build-status.json` |
| Source/image integrity | Preservation, source/build manifest equality, `git diff --check`, both image-archive checks and 47 candidate asset comparisons passed. | `preservation.json`, `final-source-evidence.json`, archive verification JSONs, `candidate-assets.json` |

Earlier failures and reruns are retained:

- Restricted-environment backend/focused-frontend attempts did not complete valid suite results. Only their identified task processes were stopped. They are not counted as passing tests.
- First host focused run: 176 passed, 2 failed. One exposed a real tooltip pointer transition defect, fixed with bounded leave handling. The other still looked for a technical row in its old page context; its numerical assertion was retained in the reference context. Affected rerun: 41 passed across 5 files. See `focused-tests-host-1.log` and `focused-tests-host-2.log`.
- First full frontend fork-pool run: 678 passed, 3 failed. The workspace assertion expected the superseded analysis-name h1; it now verifies context plus one child page heading. Two named shared-simulation tests hit the existing timeout. The focused default-pool rerun passed the workspace case but had worker-startup failure. The untouched named simulation suite passed all 12 tests with threads, then the entire suite passed all 681 with threads. No timeout or simulation expectation was weakened. The exact cause of the host's default-pool startup/timeouts is UNKNOWN; default-pool reliability is not claimed. See `frontend-tests-final.log`, `frontend-failure-rerun.log`, `named-thread-diagnostic.log` and the final full-suite log.
- jsdom Canvas `getContext()` warnings remain in frontend output. No canvas dependency or test suppression was added.
- A Docker inspection template initially assumed the API had a healthcheck and failed on that missing field. The corrected inspection exited 0: web/db have healthy status; API is running with no configured health status. A denied CIM measurement produced nulls, not zero memory. The successful host measurement is recorded below.

Software regression passes do not by themselves prove mathematical correctness or production readiness.

## Browser evidence and its limits

**VERIFIED, development runtime:** 112 measurements across seven pages (Results, reference, Suggested plans, Setup, simulation, calculator, eligible Reports), EN/TL, light/dark and 375/768/1024/1440 requested widths. Final measured document/main scroll widths fit; one h1 per case; sampled functional labels at least 14px and inputs 16px. The initial 375px Setup overflow (360px available, 376px content) was corrected and all Setup combinations rechecked. The wide reference stays inside a local scrolling region rather than widening the document. See `browser-verification.json`.

Twenty sampled actual text/background pairs exceeded 4.5:1 (minimum 5.5359:1). Gold-action text measured 7.5335:1 light / 10.0253:1 dark; supporting text on card surfaces 6.0647:1 / 8.5461:1. These samples are not a complete accessibility certification.

Actual browser interaction covered first tooltip activation in both themes, repeat activation, keyboard activation/Escape, filtered reference/return/browser Back, and older-file reference/return with no plan panel. Analysis 3's name includes “shared QA” but its current content is separate-line uploaded data; its name was not used as proof of a shared analytical fixture. Earlier rapid chained automation observed stale UI before React Router committed; settled-render checks passed. Exhaustive rapid-input concurrency is NOT TESTED.

**VERIFIED, production-build preview:** `http://localhost:5175`, Vite preview of the built `frontend/dist` using the existing configured API proxy. Results 4, reference 4 and Reports 5 each passed both themes at four widths: **24 cases**. Extra dark Results checks passed at 812×375 landscape and with collapsed sidebar at 1024px. No captured warn/error console entries on this preview tab. The real existing report preview displayed its saved plan, source file ID 5 and stored Conditional Decision; the inspection did not independently recompute that Decision. See `production-browser-verification.json`.

Runtime identity:

- Observed entry `/assets/index-CHjoNdru.js`; local SHA-256 `bb9493feefdb4f03beddefec757c25ebf61b7c7edd9d046a08ff5706238f4a8c`.
- Observed CSS `/assets/index-Dw5W_eRv.css`; exported observed CSS SHA-256 `d9d4f622a03d9f492c29b8153facaf1cf882c55cb0b435b63e23bec3dbc02f68`, identical to local dist.
- Local `index.html` SHA-256 `7005673caefeecfe75aeaefa54036c627a56a0d20d1425526d3dfa9065b83777`.
- Browser JS bytes were not exported; its DOM asset name was verified. Candidate archive inspection separately confirms all selected JS/CSS/index/locale files match local dist.

Sampled public Home, guest calculator and public Help styling matched the existing Docker build in both themes. Login colors matched; autofill/viewport differences prevented a like-for-like typography comparison. Guest calculator retains its earlier tooltip/gold styling because the approved phase excludes public behavior.

Actual screenshots were displayed inline through CUA. A screenshot-file export attempt was rejected by browser protocol policy; it was not bypassed and **no screenshot file is supplied**. The final light Results preview is retained for review, viewport override reset, sidebar expanded.

**NOT TESTED at this preview stage:** native touch, native 200% browser zoom, reduced-motion browser emulation, qualified native-language review, native Excel opening/recalculation, a live shared changed-demand/stale/review-purpose fixture, new Docker image startup and changed Docker-served browser flows, production. The Docker startup/browser items were subsequently executed as recorded below. Relevant component regressions cover available report-context/guard cases, but are not substitutes for unperformed live checks. No new analytical run, selection or data upload was performed merely to manufacture browser evidence.

## Built image and pre-activation record

This section preserves the exact candidate and resource disclosure made before the owner's subsequent replacement approval. Current runtime evidence follows in the next section.

Source identity includes the full dirty frontend state and nginx config, 256 files:

`sha256:ab8830dd217352e0ee1b51785da1cdabb81382bff2a0eae6965aa8381386b1df`

`build-identity.json` records every source/build hash. Final comparison confirms the source file set and hashes still match the built candidate.

Candidate tag: **`novaq-ux-overview-web:20261016-ab8830dd2173`**.

Docker's image inspect reports the OCI index/image Id:

`sha256:a59519addc5e38a2a6fe5a7f24bf17692cdd2f8e34b789ee70fe18afe191b289`

Its Linux/amd64 manifest is `sha256:3c6cc2c348e02ed0ba28d302ac683b1fbb1f4b1173f31ec09c614e56801fa2a3`; image config is `sha256:22a6204977ba29d5ed8e135fbc91c5fd7640fec74e6abde19354f13e8c053dfa`. These are different OCI object types, not conflicting measurements. Inspect confirms the source-digest label, user `101:101` and image size 135,383,829 bytes. Archive inspection compared **47** index/assets/locale files with local dist: no differences. The image had not been started at this pre-approval snapshot.

Fresh post-build container inspection, before any replacement:

| Resource | Exact identity / observed state |
|---|---|
| Web to replace | `ux-workflow-audit-web-1`, container `71bc233c6f144b291854f188e5a100e298396da6be8938fc09c374622562464a`, image `sha256:685bf28a6cdc09176f8416ac2bdabf35e194d4d2a229587411e181422c868b1b`, running/healthy. Compose project `ux-workflow-audit`; mounts `[]`; writable layer **81,920 bytes (80 KiB)**. |
| API to retain | Container `6a5f8e87475457293dd6df426d22b44402b5696ff4148c523f2330918386162c`, image `sha256:000d04ec1c224a05774766c16ba0267052d68b46d24a4823d21a8f010dfa22cc`, running; no healthcheck status. |
| Database to retain | Container `e7830fab049112dae8382aa27fc58ce87fc9ddfa587d82d982bf842c9f073b2a`, image `sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685`, running/healthy. |

The proposed replacement discarded the old web container's measured 80 KiB writable layer. Its contents and net space recovery were UNKNOWN. No dependency restart, image removal, volume deletion or cache cleanup was proposed. The earlier migrate/bootstrap one-shots were outside the replacement scope. The build phase did not recreate containers; the later authorized web replacement is recorded below.

The current web image was successfully saved to `rollback/current-web-685bf28a-20261016.tar`, 38,279,680 bytes, SHA-256 `6c83856c8c36144c72309ea575c5d12892c3acf4c0ddad6edce6ed6b8a7a9556`. Archive verification passed: 17 SHA-256 blobs, 17 descriptors, one compatibility manifest and the expected config. **Archive import and rollback startup remain NOT TESTED**; the archive does not back up database volumes or Compose environment.

The candidate archive is `candidate-web-ab8830dd2173.tar`, 38,289,920 bytes, SHA-256 `477edc378d18bd7b70c8117d695c2f2a7cf5aeb21551b3b21f99b74338532f80`. Its archive integrity checks also passed; archive import and startup from that archive remain NOT TESTED. Normal startup of the locally built candidate was later verified. Saving these files did not import images or create containers.

Host memory after the build, from a successful `Get-CimInstance Win32_OperatingSystem`: total visible 8,224,452 KiB, free physical 605,964 KiB. This is a point-in-time observation, not a capacity guarantee. Single-image build only; no cleanup performed.

**PROPOSED at the pre-approval snapshot:** replace only the exact web container above with the identified candidate. The existing reconstruction plan explicitly requires: “Before replacing an existing web container ... identify the exact ... container from a fresh inspect, report its measured writable-layer size ... and obtain explicit approval for that specific recreation.” See phase 5, step 4, line 169. The previous recreation approval was not reused; the owner then gave a new “approve” for this exact request.

Prepared override (outside the worktree):

`C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/output/ux-audit-2026-10-16/implementation/web-candidate.compose.yml`

It sets only `services.web.image` to the unique candidate and `pull_policy: never`. `docker compose ... config --images` verified the candidate resolves for web while the API/db/one-shot image names remain the existing ones. The exact command below was subsequently executed after approval:

```powershell
# Working directory: the ux-workflow-audit checkout above.
docker compose -p ux-workflow-audit -f docker-compose.yml -f C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/output/ux-audit-2026-10-16/implementation/web-candidate.compose.yml up -d --no-deps --no-build web
```

This override remains outside the worktree; the base Compose file is unchanged. The verified command selects the unique candidate for web. No production operation, commit, push or broader Docker removal was authorized by this request.

## Approved local Docker activation and browser acceptance

**VERIFIED, 2026-10-16:** fresh preflight matched the exact approved old web container and candidate image. Source file set/hashes still matched the build; the saved old-image archive hash still matched. Compose resolved project `ux-workflow-audit`, the unique web candidate and `pull_policy: never`.

The exact bounded command above exited **0** in **3.1055429 seconds**. Its log contains only web Recreate/Recreated/Starting/Started operations. The new container is:

`0a123e5f81aa9f175dab20f41a69f9595c5e6b3863c6771c9eb08da5ccae68b2`

It started at `2026-10-16T11:36:29.122127305Z` with image `sha256:a59519addc5e38a2a6fe5a7f24bf17692cdd2f8e34b789ee70fe18afe191b289`. Final inspection at `2026-10-16T11:49:44.6201080Z` confirmed running/healthy. API and database container IDs, start times and mounts match the preflight snapshot; the database volume is retained. Existing migrate/bootstrap containers remained Exited (0). The old web image `sha256:685bf28a6cdc09176f8416ac2bdabf35e194d4d2a229587411e181422c868b1b` remains inspectable. No image, volume or cache cleanup was performed.

Actual local endpoint checks: `/healthz` returned HTTP **200**, body `ok\n`; `/api/health` returned HTTP **200**, body `{"status":"ok"}`. Health responses are not treated as UI or mathematical proof.

All **47** selected index/assets/locale files copied read-only from the new container match the verified local dist hashes. CUA observed the actual `http://localhost` entry and CSS filenames. The exported **Docker-served** CSS bytes also match SHA-256 `d9d4f622a03d9f492c29b8153facaf1cf882c55cb0b435b63e23bec3dbc02f68`.

The actual Docker UI passed **112 settled layout measurements**: seven pages × EN/TL × light/dark × four requested widths. All 28 page/language/theme groups contain four cases. No measured document/main overflow, no extra h1, and all sampled visible input/select/textarea fonts were 16px. Technical reference tables scroll locally at narrow widths. The mobile operational list exposes period, service line, counter count, estimated wait with minutes and busy level. Extra light Results checks passed at 812×375 landscape and with the collapsed sidebar at 1024px.

Actual Docker interactions passed: tooltip first activation in both themes, Escape dismissal, repeated click dismissal; one-row filtered reference/return with period/line preserved; older-file switch clearing period/line, reference/return preserving `file=2`, and no plan panel for that older file. Existing Reports 5 displays the actual saved plan and source identity. Simulation 4 remains honestly “Not run”; no new run or scenario selection was initiated. No captured warn/error console entries on the verification tab. These are UI/integration observations, not new numerical or Decision validation.

Six actual Docker text/background samples passed the recorded contrast calculation: supporting text 6.0647:1 light / 8.5461:1 dark; tooltip 15.6804:1 / 13.2382:1; gold actions 7.5335:1 / 10.0253:1. This is sampled evidence, not all-state accessibility certification.

Automation limitations are preserved in the evidence: one incorrect translated-heading locator was corrected from the current DOM; an early header-only simulation measurement was replaced after the real run control appeared; helper language metadata retained the prior TL value after the visible English switch and was corrected using the recorded sequence; a combined screenshot/theme cleanup did not complete, so its state was inspected separately and dark mode was separately confirmed. No application change or weakened assertion was used for these automation issues. An actual dark Docker screenshot was displayed inline; screenshot-file export was not retried after the prior browser policy block. The viewport override was reset and the actual Docker page was retained for review. The earlier source-preview tab was outside the current browser session's close scope and was left intact.

Evidence under `implementation/activation/`: `before-containers.json`, `candidate.json`, `memory-before.json`, `compose-up.log`, `compose-up-status.json`, `after-containers.json`, `compose-ps.jsonl`, `health.json`, `running-assets.json`, `observed-docker.css`, `browser-verification.json`, `contrast.json` and `final-runtime.json`.

Host memory measured before replacement: 390,592 KiB free; final runtime measurement: 1,028,988 KiB free of 8,224,452 KiB total visible. These are actual point-in-time host measurements, not VM free-memory estimates or capacity guarantees. No image rebuild was required for activation.

No frontend/backend application source changed during activation. The previously executed regression gates therefore remain the source-test evidence for this exact source digest; the full suites were not rerun merely for a container replacement and report update. Final preservation and source/build identity checks are rerun after documentation updates.

## Remaining status

Implementation/source checks and the separately approved web refresh are finished with the results and earlier failures disclosed above. **Broader acceptance remains PARTIAL:** the available browser API did not expose native touch, native 200% zoom or reduced-motion emulation; qualified Filipino review and native Excel recalculation were not performed; no new live shared changed-demand/stale/review-purpose fixture was created; archive import/rollback startup was outside the approved refresh; production was outside scope. Those items remain NOT TESTED. The host's default fork-pool timeout/startup cause remains UNKNOWN, with the complete unchanged test suite passing under threads as disclosed above. The only implementation scope addition was the optional BusyStrip numeric suppression recorded in the plan; its default is retained. No mathematical/API/export contract change was made to achieve UI acceptance.


## October 19 verification closure and remaining status

See the [consolidated verification closure and remaining-status record](2026-10-19-verification-closure-and-remaining-status.md). This section supersedes earlier pending-item statements only where that record names executed evidence; the original execution history above is preserved.

New isolated browser checks verified Excel upload/processing, the stated own/foreign/missing/archived Results/list matrix, archived upload refusal, and injected list-error presentation/recovery. Current badge and missing-record concerns were not reproduced. Results/Reports landscape sampling passed in EN/TL and both themes. A newly verified archived workspace selector defect received a narrow source correction; build/activation remain pending the owner's requested approval. The known seed-sensitive Decision failure was reproduced and remains open. Native Excel, physical-device/media/zoom checks, qualified language review and native PDF fidelity remain NOT TESTED. Current Docker state became UNKNOWN when its API was unavailable on a later read-only check. This is not blanket acceptance, production proof, or a new rebuild/commit/push authorization.
