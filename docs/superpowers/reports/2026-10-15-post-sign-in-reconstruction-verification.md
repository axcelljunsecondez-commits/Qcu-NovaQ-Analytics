# NovaQ reconstruction after sign-in: implementation and verification

Date: 2026-10-15 (Asia/Shanghai).

**Status: PARTIAL — F1-F4 implemented and verified on the rebuilt localhost:80 interface.** The owner approved the itemized web recreation, which completed. The subsequent [runtime/math audit](2026-10-15-local-runtime-math-audit.md) found one active metric-labeling issue and two legacy mathematical helper defects; no mathematical repair has been made. Aggregate routing-DES limitations and unexecuted cases below remain. The whole reconstruction is not declared complete.

Plan: [post-sign-in reconstruction](../plans/2026-10-15-post-sign-in-reconstruction-plan.md). Baseline audit: [2026-10-15](../specs/2026-10-15-post-sign-in-reconstruction-audit.md). Owner implementation instruction: "lets proceed to this project reconstruction".

## Implementation

- F1: Results, Reports and Simulation now enter their own area without a valid remembered analysis. A shared authenticated entry component lists unarchived saved analyses, supports search and distinguishes loading, failed lookup, empty account and no search match. A valid owned/unarchived last-used hint still opens directly. An explicit malformed ID is not silently replaced with a remembered record.
- F1 continuation: New analysis accepts only an allowlisted after-sign-in destination. Ordinary creation still opens Data and setup. Creation from an area's picker returns to that area with the new record; the existing no-data state then explains its setup prerequisite. The create payload and persistence order are unchanged.
- F2: each sidebar link carries its existing translated label as an explicit accessible name. The real collapsed browser state remains a separate verification requirement.
- F3: the no-selected-plan Results state now offers eligible saved plans for both structures. Selection remains explicit and uses the existing endpoint. Current results remain available without a selected plan. Simulation's missing-selection state links to Results to choose an existing saved plan as well as Suggested plans to generate one.
- F4: run action wording and the no-run instruction follow the existing run-basis helper. Period-by-period paths say Run period by period; supported continuous paths retain Run full operation. Browser verification found and corrected the additional mismatched no-run hint in KeyResultsView. No run parameter or engine behavior was changed.
- Seven new labels were added symmetrically in EN and TL. Existing Home strings were not changed. Native-speaker language review is NOT TESTED.

## Executed checks so far

Targeted command (in `frontend/`):

```powershell
npm test -- --maxWorkers=1 src/components/analysis/AnalysisEntry.test.tsx src/components/layout/Sidebar.test.tsx src/pages/NewAnalysisPage.test.tsx src/pages/ResultsPage.test.tsx src/pages/QueueSimulationPage.test.tsx src/pages/ReportsPage.test.tsx
```

- Initial run: 139 passed / 1 failed, 6 files, duration 102.24 s; command elapsed 106.34 s. The new loading-state test collided with the implicit status role of its diagnostic output element. Its setup hook also returned a mock function, which Vitest invoked as cleanup after that mock had been configured with an unresolved loading promise; the log recorded a 10-second hook timeout. Product assertions were not weakened. Corrected the diagnostic element and used a setup-hook block with no returned function.
- Identical targeted command rerun: **140 passed / 0 failed, 6 files, duration 73.95 s**. Both logs are retained. Canvas not-implemented warnings were printed by jsdom; canvas rendering is not proved by these tests.
- First full frontend run: **659 passed / 1 failed, 79 files, duration 551.71 s**. The sole failure was `CurrentDatasetCache.test.tsx:454`, which still expected Run full operation for the period-by-period Current path. Its failure output showed the new Run period by period button. Updated only that label expectation and added an assertion that the inaccurate label is absent; all dataset-deletion, stale-evidence and cache assertions remain unchanged. Isolated cache rerun: **6/6 passed, duration 16.08 s**.
- Final full frontend rerun (`npm test -- --maxWorkers=1 --reporter=verbose`): **660 passed / 0 failed, all 79 files, exit 0, duration 568.24 s**. The corrected cache case and the previously intermittent unknown-Settings redirect passed within this full run (the latter in 589 ms). React act and undefined-query-data warnings were printed and are retained in the log; passing assertions do not erase those warnings. The older redirect failure's original cause remains UNKNOWN, but it did not recur in these two full runs.
- Initial typecheck exited 2 because the new Sidebar test used Testing Library's unsupported `exact` role-query option. Removed that option; a string name still matches the full accessible name. Rerun: **typecheck, lint and production build passed**. Vite printed a large-chunk warning; client build completed in 5.34 s. No lint/build setting or timeout was loosened.
- Scope check: `git diff --exit-code` for Home, authentication, shared illustration, global styles and backend returned 0. JSON comparison against HEAD verified all **1,915 existing labels per language unchanged**, with **7 matching new keys**. Native-language quality is NOT TESTED.
- Ruff: **All checks passed**. Mypy: **Success: no issues found in 236 source files**. Backend pytest finished: **3,185 passed, 123 skipped, 1 xfailed, 6 subtests passed, 1 deprecation warning in 1,918.16 seconds**. The expected failure was `test_novamart_failing_lanes_are_stable_across_base_seeds`. Skipped tests were not executed; this is not a Postgres regression claim. `NOVAQ_TEST_DATABASE_URL` was absent and the suite used its temporary SQLite path. The finished command session was no longer available when polled after resumption; the test summary was recovered from the retained log.
- After the final KeyResultsView wording correction: affected QueueSimulationPage and CurrentDatasetCache files passed **67/67, 2 files, 23.06 seconds**. The first attempt could not execute any tests because Windows sandbox denied a compiler-cache rename (EPERM). The first unsandboxed rerun passed 66 and failed 1 because the new assertion had been inserted into the wrong test; moved the assertion to its intended separate-Current case, without weakening it. The final rerun passed. The 660-test full-suite result above precedes this final wording correction; it is not represented as a full-suite run on the last one-line change.
- Final local production bundle passed (Vite 2.30 seconds, existing large-chunk warning). Both Docker builds ran typecheck, lint and build; final Docker lint printed **0 warnings and 0 errors**, final Vite build completed in **1.51 seconds** with the existing large-chunk warning. Docker build results are detailed below.

## Live verification data

Two QA files were copied verbatim from existing constants in `tests/test_analyses_api.py` using AST extraction. They are synthetic software-test inputs, not operational observations:

| File | Source | Inputs and period | SHA256 |
|---|---|---|---|
| SYNTHETIC-reconstruction-shared.csv | `test_analyses_api.py:12`, `AGGREGATE` | 08:00-09:00; lambda 4/hour; mu 6/hour; 2 counters | `596ecf43f1947f8226e0be00799871d665fbeafdd477d1e8abaeba05d95547ea` |
| SYNTHETIC-reconstruction-separate.csv | `test_analyses_api.py:101` | 08:00-09:00; lambda 4/hour; mu 6/hour; 1 counter; variance 0.02 hours squared; queue_a | `464a245b46014c001b8754fce134422929b22b30a38ded2a89d01f5076f9a77a` |

Local files and test logs are stored in `C:/Users/Administrator/.codex/visualizations/2026/10/14/01a13b2b-3883-7bb2-ad6c-05667dc49ecf/`.

The pre-existing analyses 1 and 2 are not QA scratch records for this phase.

### Live browser observations (Vite preview on localhost:5173, existing local Docker API)

- Direct Results, Reports and Simulation entry showed their own saved-analysis chooser. The first Simulation snapshot was still Loading; the settled check passed. The five collapsed sidebar links had translated accessible names while their visible label spans were hidden by the real CSS. Keyboard Enter activated Queue simulation.
- Created analysis 3, `SYNTHETIC — reconstruction shared QA`, through the Results continuation. The empty Results state explained the missing processed file. Saved an explicit shared setup (2 counters, unlimited capacity, no abandonment, representative day, 08:00–09:00, no breaks), then uploaded the identified shared fixture for planning. Validation succeeded. Recorded wait remained unavailable; the detailed modeled wait was 1.25 minutes, matching the independent reference. The summary card displayed 1.2 because its existing one-decimal formatter receives the floating-point value 1.2499999999999998; no calculation or formatter was changed.
- Generated and saved `SYNTHETIC shared saved-only plan` without selecting it. Left/reopened Results, chose the existing plan by keyboard, and explicitly used it for simulation. Reload confirmed persisted plan ID 1. No regeneration was needed.
- Suggested and Current full-day runs completed using 5 repeated days, seed 42 and explicitly saved DRAIN closing rule. The suggested tiny-fixture UI start-to-Done observation was 1,089 ms; this is not a backend or production benchmark. Saved replay Play/Pause worked. Direct automation fill of the native time field did not commit its controlled input and produced validation errors twice; native ArrowUp/ArrowDown/Tab then Enter committed 08:30 and the slider read 0.5. This browser-automation limitation was not hidden or treated as a product fix.
- Checks returned Adopt for synthetic selected-plan full-day run 3 with 5 repeated days and Many variations. On resumption, the same analysis had a different queue structure/operating window and an additional `NOVAMART_DATA_UPLOAD` file; Reports correctly showed stale evidence. Who changed it and when is UNKNOWN. Its later state is not attributed to the earlier synthetic run; no further mutations were made to analysis 3 during this resumption.
- Created analysis 4, `SYNTHETIC — reconstruction separate QA`, with queue_a, one fixed counter, unlimited capacity, no abandonment, representative day and generated segment_1 (08:00–09:00). Uploaded the identified separate aggregate fixture for planning. Validation succeeded; modeled wait was 17.2 minutes and recorded wait was unavailable, matching the reference for those inputs.
- Separate optimization refused that aggregate fixture: `period(s) 08:00-09:00 match no configured operating segment`. Source confirms exact ID matching in `backend/queueing_engine/services/separate_optimization.py:1766`; the UI generates IDs segment_1 etc. in `frontend/src/pages/AnalysisSetupPage.tsx:335` and exposes no segment ID editor. Save/use buttons remained disabled. This limitation remains unresolved; no protected engine check, contract or input observation was changed to bypass it.

A third fixture, `SYNTHETIC-reconstruction-separate-events.csv`, was copied verbatim from the `events` constant in `tests/test_workflow_api.py:526`, function `test_separate_current_des_end_to_end_with_arbitrary_ids`. SHA256: `f2284cd6335ff72abec501afbbaaad8de583f10612dfad3ea4973471c2032866`. It contains three synthetic customer events on 2026-09-08 between 07:05 and 07:26 UTC, queues cashier-east and express. Preparation is not proof of upload, optimization or simulation.

- The event fixture was subsequently exercised in new analysis **5**, `SYNTHETIC — reconstruction event lanes QA`: queue IDs cashier-east and express, fixed count 1, unlimited capacity, no abandonment, representative day, segment_1 from 07:00–08:00, no breaks. Upload validation succeeded; the observed wait in these synthetic records was 1 minute. The existing optimizer returned a feasible saved plan at the unchanged 70% target, costs 94.375/counter-hour and 100/customer-hour. Saved `SYNTHETIC event lanes saved-only plan` without using it, left/reopened Results, selected it explicitly and reloaded; plan **3** persisted. No regeneration was needed for selection.
- Analysis 5 Current simulation completed with the period-by-period label; served/closing totals remained Unavailable with their explanatory note. The selected-plan continuous simulation completed with seed 42; displayed served 5, in system at close 1, and customer conservation holds. Replay retained analysis/plan context and Step advanced the saved trace from the 07:00 start to 07:02, Event 2 of 15. These are synthetic stochastic outputs, not observations or independently verified finite-run predictions.
- Analysis 5 checks completed: Many variations Done, Results check Passed, Decision **CONDITIONAL**. The stated reason was that cost savings cannot be calculated for separate queues. Reports showed Checked by simulation / Conditional and the correct saved plan name. Downloaded `C:/Users/Administrator/Downloads/novaq_full_report_5.pdf`, file existence/length **8,031 bytes** verified. The download tool took 804.6 seconds to return; server-only generation duration is UNKNOWN. PDF visual/content review and real Excel formula execution are NOT TESTED.
- Refreshing the static preview bundle invalidated a lazy asset URL in the already-open tab (`Failed to fetch dynamically imported module`). Reload restored Reports. This occurred during an intentional local rebuild, not a proved production issue; it is retained in the evidence.
- Quick Calculator on `/tools/calculator`, without an analysis query, returned **9.5701 minutes** for lambda 40/hour, mu 15/hour and 3 counters, matching the independent reference rounded to four decimals. Setting counters to zero displayed `Enter a whole number, 1 or more.` A live server-refusal case is NOT TESTED.
- Explicit nonexistent analysis 999999 stayed on its own Results URL and displayed `Analysis not found.`; it did not silently reopen the remembered analysis. Picker search displayed `No analyses match this filter.` for an unmatched query and recovered when cleared. Fresh-account, list failure/retry, foreign/archived hint, storage failure and continuation restrictions are covered by executed component tests; distinct live-account failure injection, live foreign-user ownership and live archived-record cases are NOT TESTED.
- Picker layout was checked at **375/768/1024/1440 px** in English/light and Filipino/dark. Document widths were 360/753/1009/1440 respectively; no horizontal page overflow was measured. All five navigation names were present in each language. Settled English and Filipino mobile screenshots were visually inspected. One rapid-resize screenshot was transiently scaled; a settled separate capture replaced it for visual assessment. These checks cover the changed picker, not a full responsive audit of every existing page. Native-speaker wording review is NOT TESTED. Original English/light preference and default viewport were restored.
- Keyboard checks covered collapsed navigation activation, saved-plan choice/use, create submission, replay Step and native time editing. They are not a complete keyboard-only audit of every existing control. Live review-only upload isolation, induced save/selection partial failure, live stale-plan refusal and every report export variant are NOT TESTED; existing automated coverage passed, and no such gate was loosened.

Live evidence: `reconstruction-live-verification.json`, `reconstruction-final-picker.png`, `reconstruction-picker-en-375.png`, `reconstruction-picker-tl-mobile-final.png`, `reconstruction-first-saved-plan-choice.png`, `reconstruction-shared-simulation.png`, `reconstruction-current-instruction-final.png`, and `reconstruction-separate-aggregate-refusal.png` in the artifact folder above.

## Docker image and replacement

The build and pre-replacement observations below are retained as historical evidence. The owner subsequently approved the exact operation. `docker compose up -d --no-deps web` exited 0 and recreated web only. New container `767af13c18dd228a9e0c4ce551298041d0813619bc8c395dd732e08e2c22aa18` runs the final image below and is healthy. No other Docker resource was removed. Actual localhost:80 picker, saved Results/Reports, Simulation/Replay/Checks, Current hint and Quick Calculator were then exercised. Both health endpoints returned their expected bodies and HTTP 200. See the linked runtime/math audit for final Compose output, browser evidence, authorization and exact findings.

Builds were sequential and only the changed web service was built:

| Build | Command | Elapsed | Result |
|---|---|---:|---|
| Initial implementation | docker compose build web | 129.43 s | exit 0 |
| Final hint correction | docker compose build web | 64.23 s | exit 0 |

No API, migrate or bootstrap-admin rebuild was required or performed in this reconstruction phase. Logs: `reconstruction-docker-web-build.log` and `reconstruction-docker-web-build-final.log`.

Before the first build: host free 752.7 MiB; Docker allocation 4,022,951,936 bytes; VM MemAvailable 2,950,716 kB. Docker system df printed images 65 / 12.93 GB, containers 21 / 499.7 kB, volumes 19 / 5.789 GB and build cache 734 / 30.67 GB. No cleanup was performed. Before final build: host free 1,276 MiB, VM MemAvailable 2,937,088 kB. After final build: host free 1,074.8 MiB, VM MemAvailable 2,802,688 kB. Allocation is not free memory.

Fresh pre-replacement inspect:

- Existing web container `ux-workflow-audit-web-1`, ID `4390889e95cc22cf343a66d54515a8d5fa96580646ce3fb94a9e737abf4361bb`.
- Existing web image `sha256:7912f32c55e60cd5c4c36f001f268c226dbbe2572fe39fd7fbd552aa41113987`.
- Measured writable layer `81,920` bytes (**80 KiB**); root filesystem size 97,161,216 bytes. No mounts were listed for this web container. Net Windows disk recovery from recreation is **UNKNOWN**; image layers are not being deleted and Docker's VM disk need not shrink.
- Built final image `ux-workflow-audit-web:latest`, ID `sha256:987e2c88e52e426ed995bb967ada948156d14d166c65bd0399bea50f0229d698`, size 135,331,854 bytes.
- At that preflight the proposed operation was not yet executed: `docker compose up -d --no-deps web`. The later owner approval and execution are recorded above. Database volume, API/db and one-shot containers were retained.

Actual pre-replacement `docker compose ps -a`:

| Container | State printed | Ports |
|---|---|---|
| ux-workflow-audit-api-1 | Up 8 hours | 127.0.0.1:8000->8000/tcp |
| ux-workflow-audit-bootstrap-admin-1 | Exited (0) 8 hours ago | — |
| ux-workflow-audit-db-1 | Up 8 hours (healthy) | 127.0.0.1:5432->5432/tcp |
| ux-workflow-audit-migrate-1 | Exited (0) 8 hours ago | — |
| ux-workflow-audit-web-1 | Up 8 hours (healthy), old image | 127.0.0.1:80->8080/tcp |

Actual health outputs from the still-running old stack: `/healthz` -> `ok`; `/api/health` -> `{"status":"ok"}`. This does not verify the new frontend on localhost:80. Full raw status/inspect output: `reconstruction-docker-before-refresh.log`.

## Modified files (uncommitted)

Application: `frontend/src/components/analysis/AnalysisEntry.tsx` (new), `frontend/src/lib/analysisDestination.ts` (new), `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/components/layout/navigation.ts`, `frontend/src/components/results/PlanChanges.tsx`, `frontend/src/components/queueSimulation/RunBar.tsx`, `frontend/src/components/queueSimulation/KeyResultsView.tsx`, `frontend/src/pages/NewAnalysisPage.tsx`, `frontend/src/pages/ResultsPage.tsx`, `frontend/src/pages/ReportsPage.tsx`, `frontend/src/pages/QueueSimulationPage.tsx`, and both `frontend/public/locales/{en,tl}/translation.json`.

Tests: `frontend/src/components/analysis/AnalysisEntry.test.tsx` (new), `frontend/src/components/layout/Sidebar.test.tsx`, `frontend/src/pages/NewAnalysisPage.test.tsx`, `frontend/src/pages/ResultsPage.test.tsx`, `frontend/src/pages/QueueSimulationPage.test.tsx`, `frontend/src/pages/CurrentDatasetCache.test.tsx`.

Records: `handoff.md`, `memory.md`, this report (new), the linked 2026-10-15 audit (new) and reconstruction plan (new). Existing untracked `novaq_local.db` is not owned or modified by this phase.

Independent rational-arithmetic reference calculations were prepared in `reconstruction_reference_cases.py`: M/M/3 at lambda 40/hour, mu 15/hour gives Wq `256/1605` hours = `9.570093458` minutes; shared fixture M/M/2 gives `1/48` hours = `1.25` minutes; separate queue_a fixture Pollaczek-Khinchine gives `43/150` hours = `17.2` minutes. These are steady-state model references for the identified synthetic inputs, not observed waits, executed browser results or finite-horizon DES expectations.

## Protected scope and outstanding work

Home, public navigation, authentication, backend APIs, schema, queueing/optimization/simulation mathematics, Decision derivation and report calculations are outside the edit scope. Final protected-path diff returned **0** for Home, auth, shared illustration, global styles, Login and backend. No shared CSS or dependency file changed. No commit, staging, push or production operation has been performed. The only Docker removal was the specifically approved old web container during recreation; images, volumes, cache and all other containers were retained.

Final repository check: branch `feat/ux-u1-shell`, HEAD `0b9423ec66d32620ed91769ac35a10e51ffae2ec`; `git diff --check` exit 0; `git diff --cached --quiet` exit 0 (nothing staged). Status listed 24 phase-owned changed/new files plus the pre-existing untracked `novaq_local.db`. The record itself is included in that count.

Web recreation and localhost:80 checks are now executed. Remaining: review the new runtime/math findings and [proposed repair plan](../plans/2026-10-15-verified-math-issues-remediation-plan.md), which needs separate authorization for mathematical changes. Preserve the aggregate limitation: period IDs do not match, and aggregate variance alone also lacks the empirical service samples required by routing DES. Do not claim an ID-only fix would enable that path. Unexecuted cases above remain NOT TESTED.

Resource note: a sandboxed CIM probe was denied and its script printed a derived zero. That zero is invalid and is not treated as a memory measurement. An elevated read subsequently reported 893.1 MiB free; a later elevated read reported 960.7 MiB free. Heavy checks remain sequential.
