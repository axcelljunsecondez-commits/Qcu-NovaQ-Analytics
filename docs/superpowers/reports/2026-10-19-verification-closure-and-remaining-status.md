# Verification closure and remaining status

Date: 2026-10-19, Asia/Shanghai. Worktree: `.claude/worktrees/ux-workflow-audit`, branch `feat/ux-u1-shell`, HEAD `0b9423ec66d32620ed91769ac35a10e51ffae2ec`, with the pre-existing dirty work preserved.

**Current status: local Docker update and scoped verification COMPLETE; overall closure PARTIAL.** Owner authorized “update it”. Existing db/API were started and only web was recreated with `novaq-ux-focus-web:20261019-bea2d37ecac2`. Web/db are healthy; API health/readiness 200; all 66 served image files and four connected light/dark focus cases passed. See the [current local Compose activation record](2026-10-19-local-compose-focus-activation.md). API/db configuration and mounts and migration/bootstrap states are preserved. Seed-sensitive Decision remains OPEN; native/manual limits remain explicit. No rebuild, commit or push occurred during activation.

## Historical closure-phase record

The statements below describe the original pre-build phase. Later build/source statements and the current remaining-status table are superseded by the linked image report; original execution records remain retained.

The owner requested closure of remaining verification items and an explicit remaining status, and separately instructed that any commit, push or rebuild requires approval. This report reconciles the older reports; their original execution records remain historical evidence. No production action, mathematical repair, schema/API/auth change, commit, push, image build or container replacement was performed in this phase.

## Scope and evidence

Evidence directory in the primary checkout: `output/playwright/verification-closure-20261019/`. The 850-file before manifest, frozen source hashes, staged-diff hash and HEAD are in `before.json`. Task-only source diff: `selector-only.diff`. Reconstructed pre-edit copies for the two changed files were accepted only after their byte hashes matched that original before manifest (`prepare_review.py`, `prepared-build.json`).

The browser tests used the existing built frontend. Current CSS/report appearance observations therefore apply to that build, not to the unbuilt selector correction. At 21:17 UTC / 05:17 local, four local HTTP paths returned 200 and all 65 recorded build assets matched their served bytes; all 256 frontend/nginx source hashes then matched the build. After the two-file source correction, exactly those two source/test hashes differ from that build manifest. Evidence: `runtime-check.json`, `prepared-build.json`.

## Items closed or resolved for this check

| Item | Actual result and scope | Evidence |
|---|---|---|
| Browser Excel file selection, preview and processing | VERIFIED in a new isolated instance: the original SYNTHETIC workbook was selected through the real file chooser, preview returned 200, datasets POST returned 201 and the UI said input data is valid. The ingested rows exactly match the documented fixture: 08:00–09:00 arrivals 40/hour and 09:00–10:00 arrivals 20/hour, service 15/hour/counter and 2 counters in each period. No observed operational data or mathematical validation is implied. | `browser-observations.json`, `browser-http.jsonl`, `fixture-result.json`; fixture source `output/excel-layout-2026-10-18/verify_live_activation.py` |
| Own/foreign/missing/archived Results access | VERIFIED in isolated SQLite with two synthetic users through the unchanged browser UI. Each user saw only its own default list and own Results. Cross-user Results and the owner's missing ID returned 404 and displayed `Analysis not found.` without result tables. An owner could read its archived Results; another user could not. Archived workbook preview/processing was refused with 409, leaving its one dataset unchanged. This is the stated Results/list matrix, not an exhaustive authorization audit of every route or a PostgreSQL/browser matrix. | `browser-fixture-identity.json`, `browser-http.jsonl`, `browser-observations.json`, `fixture-result.json` |
| Browser list-error handling and recovery | VERIFIED against a deliberately injected HTTP 500 in the loopback test wrapper only. The UI showed its generic server-error alert and no results; normal list rendering returned after the flag was removed. This verifies client presentation of an HTTP 500; no genuine production/backend internal fault was induced or claimed. | `browser-fixture-plan.md`, `browser_fixture.py`, `force-list-500.completed`, HTTP trace and browser observations |
| Earlier missing-record generic-error concern | NOT REPRODUCED in the current running stack check: Results displayed `Analysis not found.`, with no tables. Authenticated API calls returned actual 404 with that detail. | `runtime-check.json`, `browser-observations.json` |
| Dark striped badge concern | NOT REPRODUCED in the current check. Screenshots visibly showed pink text in dark mode and red text in light mode; computed dark `color` and `-webkit-text-fill-color` both were `rgb(255,138,156)`, 14px, opacity 1, no filter. Contrast against both observed stripe colors was 7.1207/7.2798 in dark mode and 5.8634/6.4771 in light mode. The earlier discrepancy's cause is still UNKNOWN; no theme code was changed and no root-cause repair is claimed. | CUA screenshots displayed during the turn; `browser-observations.json`, `runtime-check.json` |
| Narrow landscape sampling | VERIFIED: nine measured Results/Reports cases, EN/TL and light/dark, primarily 667×375 with one 812×375 Results case. Document/main scroll width equalled client width in each, with one h1 and sampled input/select fonts 16px. At 667px the operational mobile cards retained the fields. Keyboard Enter opened the narrow menu; Escape closed it. Busy-level help opened and Escape dismissed it. This sampling does not close every application's landscape, native touch, zoom or reduced-motion axis. | `browser-observations.json` |
| Earlier report/provenance defects and clipped Excel layout | Closed by the separately completed repairs and local activations in the linked reports. They were not reimplemented in this phase. Native font/Excel gates below remain independent. | [Report evidence repair](2026-10-16-report-evidence-fixes-verification.md), [Excel layout repair](2026-10-18-excel-export-layout-verification.md) |
| Previously skipped PostgreSQL cases, upload/staleness and supported Current simulation | The October 17–18 addendum records 123 isolated PostgreSQL cases passing, live Excel upload, six stale export refusals, and shared/supported separate Current runs. Those are prior executed evidence, not fresh passes here and not items to repeat without a changed dependency. The last formatting-phase backend run retained 123 skips. | `2026-10-16-report-evidence-fixes-verification.md`, October 17–18 addendum |

## Confirmed selector defect and actual source correction

At `/analyses/2/data` in the isolated fixture, context correctly said `SYNTHETIC closure archived owner`, while `#analysis-switcher` displayed active analysis 1. The default API list excludes archived records. `AnalysisWorkspace.tsx` supplied that list with controlled value 2, but it had no option 2, so the select showed its first option.

The correction includes the already successfully authorized current analysis when it is absent from the list, once only. It does not request other archived/foreign records, change access rules, rename labels, alter the navigation handler, or change the child remount key.

Actual application file scope:

- `frontend/src/components/analysis/AnalysisWorkspace.tsx`: two local option-preparation lines and the options prop.
- `frontend/src/components/analysis/AnalysisWorkspace.test.tsx`: two new absent-current regression cases, asserting selected identity, one option, and navigation back to a listed record. Existing child-state/navigation assertions remain.

Specification and plan: [selector specification](../specs/2026-10-19-archived-analysis-selector.md), [selector plan](../plans/2026-10-19-archived-analysis-selector-plan.md). No new label/i18n key or dependency was introduced.

| Verification | Actual result |
|---|---|
| Focused regression before source fix | Exit 1: 2 failed / 1 passed; both new cases expected selected value 2 but observed 1. `selector-red.log`. |
| Focused regression after source fix | Exit 0: 3 passed / 1 file, Vitest duration 7.46s; wrapper 9.33s. `selector-green.log`, `focused-checks.json`. The new test mock was made route-aware for its switch-back assertion; no assertion was removed or weakened. |
| First full frontend attempt | INCOMPLETE. `frontend-full.log` ends without a summary or result JSON. Its tool session was lost; the process was absent on resumption. Cause UNKNOWN. Partial lines are not counted as a completed gate. |
| Resumed full frontend, typecheck and lint | All exit 0. **683 tests / 82 files passed**; full-run wrapper 664.05s, completed 2026-10-18T22:01:58.034086+00:00. Typecheck 49.14s; lint 3.5s. Exact commands/results: `full-host-r2/frontend-checks.json`, individual logs and `frontend-final-summary.json`. No test assertion or timeout was weakened; threads/maxWorkers=1 are explicit. |
| Build, runtime activation and new-fix browser check | NOT EXECUTED. Awaiting the owner's requested rebuild approval. The previous build continues to contain the defect; none of the earlier browser observations is a deployed-fix pass. |

The resumed full suite completed and its exit-0 result JSON was written before the detached wrapper failed while printing the checkmark character to a Windows charmap stream (`UnicodeEncodeError`, retained in `full-host-r2/runner-error.log`). That output error is not a failing Vitest result. The continuation executes only the remaining typecheck/lint steps with explicit UTF-8 output; the completed full suite is not repeated. No application source, assertion or timeout was changed for this runner correction.

## Reproduced mathematical/statistical defect

The existing `test_selected_mc_load.py::test_novamart_failing_lanes_are_stable_across_base_seeds` was run with `--runxfail` to inspect the known finding rather than count an expected failure as a pass. The host run exited 1: **1 failed, 1 existing warning, 41.31s** (wrapper 55.06s). Seeds 7/8 yielded `conditional`; 9/10/11 yielded `revise`, failing the unchanged identical-decision assertion. Evidence: `host/seed-recheck.log`, `.xml`, `.json`.

The first restricted attempt produced no completed result. Two CPU inspections were unchanged at 16.4375s and its log remained at the test name. Only the verified task-owned pytest process was stopped after 456.36s; interruption and raw exit 4294967295 are retained. That is an incomplete runner attempt, not a mathematical result. Underlying waiting cause UNKNOWN.

**OPEN / requires separate scope:** correcting simulation/load uncertainty or Decision statistical behavior would affect protected mathematics/statistics. `AGENTS.md`, Protected Mathematics, requires: “A change to mathematical behavior requires separate authorization, documented justification, independent reference cases, and regression verification.” This phase stopped the mathematical repair path and made no such changes. Full-suite xfail classification is not proof that this finding is resolved.

## Remaining status

| Remaining item | Classification and exact reason | Requirement to close |
|---|---|---|
| Archived selector correction | Source corrected; focused/full frontend tests, typecheck and lint VERIFIED. Build/activation and deployed-fix browser check remain NOT TESTED. | Approve the prepared frontend/web rebuild, then review the exact new image and separately authorize any container recreation before deployed browser verification. |
| Seed-sensitive Decision | VERIFIED existing failure; OPEN. | Separately authorized statistical/mathematical specification and independent reference verification. |
| Native Excel recalculation and appearance of the formatted file | NOT TESTED. This thread exposes no native application inspection, so current workbook/pane/sign-in setup gates cannot be verified. No fresh connected-session absence is asserted and no discovery retry was performed without those gates. Previous screenshots and offline formula evaluation remain sampled/historical evidence only. | A working, verified native Excel setup and connected workbook session; then native recalculation, error scan and visual checks. |
| Physical touch, true 200% browser zoom and reduced motion | NOT TESTED. Advertised browser capabilities were visibility/viewport and pageAssets/webmcp, with no touch/zoom/media emulation. Viewport sampling is not those checks. CSS reduced-motion support alone is not execution evidence. | A supported browser/device surface or recorded manual verification. |
| Qualified Filipino review | NOT TESTED. EN/TL rendering/key symmetry is not a qualified human language review. | Human reviewer confirmation of terminology and usability. |
| Native PDF font fidelity | NOT TESTED. Prior Poppler Symbol/ArialUnicode warnings and Greek-rho rendering limitation remain; no native viewer proof was obtained. | Native PDF viewer/font verification. |
| Current Docker runtime after interruption | UNKNOWN. A later read-only inspect exited 1 because the Docker engine API pipe was absent. The empty identity output is not evidence of zero containers. Earlier 05:17 health/asset checks remain timestamped evidence only. No Docker start/recreation was performed in this phase. | Restore engine availability and inspect fresh identities/health before any approved build or activation. |
| Default fork-pool worker reliability | UNKNOWN / retained runner limitation. Full successful earlier suites used threads; no permanent fork-pool repair is claimed. | Separate runner diagnosis if default-pool reliability is a requirement; do not alter timeouts/assertions to hide it. |
| Production, actual application rollback, fresh-host recovery, owner PostgreSQL restore | Outside this local verification authorization; NOT TESTED. | Separate reviewed scope and explicit authorization. |

The Excel live-control skill requires: “Call `list_document_sessions(surface=\"excel\")` only after the previous gates pass.” See [the exact skill](C:/Users/Administrator/.codex/plugins/cache/openai-primary-runtime/spreadsheets/26.1015.12040/skills/excel-live-control/SKILL.md), Setup State Machine. The unavailable native setup observation prevents that gate; this is not a new claim that a signed-in workbook failed registration. Prior retry loops were not repeated or bypassed through COM/cell editing.

## Prepared next action and preservation

The proposed unique web tag is `novaq-ux-selector-web:20261019-537e3aed4ccf`, **NOT BUILT**. The copied 256-file build context has canonical source manifest digest `537e3aed4ccfef5daffa5589d58c8b1ae701d4420169099dc3ece0c3af76cd7e`. `prepared-build.json` defines the digest and each file hash. The previous web archive is still 38,289,920 bytes with SHA-256 `477edc378d18bd7b70c8117d695c2f2a7cf5aeb21551b3b21f99b74338532f80`; importing/rolling back from that archive remains NOT TESTED.

The browser fixture used loopback port 8766, current API source, unchanged built frontend, a task-owned SQLite database and `FakeEmailSender`. Existing test helpers seeded synthetic users and one-period 4/hour arrivals, 6/hour/counter service and 2 counters for access checks. The separate workbook ingestion test used the preserved 40/20, 15, 2 two-period fixture described above. The active application database was not the test target. `fixture-result.json` verified the exact ingested inputs, unchanged source workbook hash, two own datasets, one unchanged archived dataset and a disabled test fault. The fixture process was absent at final inspection; database and artifacts were retained. CUA transport closed before final tab cleanup could be confirmed. English/light and viewport reset were observed before that failure; final tab state is UNKNOWN.

Final scope check at 2026-10-18T22:03:53.292003+00:00 passed: 850 baseline files, 844 unrelated files unchanged, six scoped existing files changed and three scoped documents added. All 256 prepared source/context hashes and all 65 existing dist hashes matched; HEAD and staging were unchanged; `git diff --check` exited 0 and new-document links resolved. Final report/plan completion text was then updated within the same allowed documentation scope. This phase's only application scope addition was the verified selector correction described above. No global 'all verified' or whole-project completion claim is made. No rebuild, commit or push is authorized by this report.
