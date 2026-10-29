# Shared-queue CSV diagnostic — 2026-10-29

## Outcome and scope

VERIFIED: the supplied CSV completed upload, Current analysis, current and suggested full-day
simulation, replay regeneration, and the older period-by-period simulation in an isolated local
API. The freshly built application also completed the tested browser workflows, including
calculating, saving and selecting a genuine suggested plan, Many variations, and Decision.
No application crash was reproduced in this bounded check. No application repair is established
or applied. This does not establish that an existing saved analysis or the deployed application
has no defect.

Status: bounded source/API/browser diagnosis COMPLETE; reproduction of the initially reported
failure UNKNOWN; verification of the existing Docker and authenticated production workflows
PARTIAL. The owner did not provide a specific failing analysis, error text, or failing control,
and authorized independent checking with the CSV.

## Source and input identity

- Checkout: `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ`, branch `main`.
- Starting and final application HEAD: `e2dbe5d57f859644849a5c445fceb099ff15bfa9`.
- Existing untracked entries at startup: `.claude/launch.json`, `.playwright-cli/`, `output/`.
  They were preserved; diagnostic files use a dedicated new output subdirectory.
- Other worktrees were enumerated. No worktree switch, fetch, commit, push, release, Docker
  activation, migration, operational-record edit, or production-data write was performed.
- Dataset: owner-supplied
  `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/Daily data mmc/Avg_total_data_of_14_days.csv`.
- SHA-256: `236fc05861b4a59ce3216c41fb52b3c529aec6b6f57003f610bd4cc3a91f938e`.
- VERIFIED structure: 13 hourly aggregate rows, `05:00-06:00` through `17:00-18:00`, columns
  `time,lambda,mu,c`. Values were uploaded unchanged through the real ingestion endpoint.
  The filename describes 14-day averages; the underlying daily observations and averaging
  method were not supplied or independently verified.
- Diagnostic configuration: shared queue, staffing varies by period, unlimited capacity,
  abandonment not modeled, no breaks. These are explicit TEST SETTINGS, not observations
  established by the CSV. Lambda and mu use the application's per-hour rate convention;
  each uploaded row represents one hour. Sum(lambda × one hour) = 107.5 expected arrivals
  in the modeled 13-hour day, not a measured customer count from a newly observed day.
- Full-day tests: five replications, seed 42, both explicit closing policies `DRAIN` and
  `HARD_CUTOFF`. The suggested plan was actually calculated and verified through the normal
  save/selection APIs; no invented optimization results were inserted.
- Runtime: repository `.venv/Scripts/python.exe`, Python 3.13.13, NumPy 2.2.6, pytest 9.1.1;
  Node v24.16.0. Browser checked the freshly built `frontend/dist` through a disposable
  loopback-only server on `127.0.0.1:18765`.

## Verified behavior

1. API: analysis creation and CSV upload returned 201; Current analysis returned 200.
   Full-day current and suggested runs returned 200 under both closing policies. Their
   replication-0 playback endpoints returned 200. Both current and suggested older
   period-by-period requests returned 200 with 24-hour per-period settings, event cap 3000,
   seed 42 and carryover true, matching the page's existing request options.
2. Browser: Current full-day and older runs completed in the initial harness. In the corrected
   browser harness, optimization, Save/Use this plan, suggested full-day run, suggested older
   run, Current full-day run and replay completed. The replay clock advanced after Play at
   10x, and Pause worked. No warning/error console entries were returned for the inspected tab.
3. Browser: Check the plan sent Many variations and Decision requests, both returning 200.
   The displayed Decision was `Revise`, identifying `05:00-06:00`, `10:00-11:00`,
   `11:00-12:00`, and `16:00-17:00`. This records the actual configured result; this diagnostic
   did not independently validate or alter the protected statistical/Decision methodology.
4. A new analysis's full-day control is disabled until a closing rule is chosen and saved.
   A Suggested run without a selected plan displays the plan-selection prerequisite.
   These gates were observed in the browser and follow `shared_continuous._assess`,
   `ContinuousRunBar`, and `QueueSimulationPage`.

## Actual test execution

- PASS: `.venv/Scripts/python.exe -m pytest tests/test_b4a_continuous_preview.py
  tests/test_shared_continuous_des_pin.py -x -q --tb=short --basetemp
  output/shared-queue-debug-20261029/pytest-baseline-2`: **36 passed**, one Starlette/AnyIO
  deprecation warning, 89.55 seconds.
- PASS: `npm test -- --run src/pages/QueueSimulationPage.test.tsx` in `frontend/`:
  **61 passed**, one test file. jsdom emitted its existing canvas-not-implemented messages.
- PASS: `npm run build` in `frontend/`, including TypeScript build. Vite reported a large
  chunk warning for the existing QueueSimulation bundle and plugin timing information.
- PASS: both `reproduce.py` executions outside the sandbox exited 0; the extended execution
  covered the genuine selected-plan calculation/save/selection path.
- NOT TESTED: full backend/frontend suites, Ruff and mypy. No application source was changed;
  this was a focused diagnosis, not a claim of completing all gates for an application patch.

## Harness problems and corrections

- The first pytest command hit a sandbox temporary-directory permission error: 9 engine pin
  cases passed, 27 API cases errored during fixture setup. A workspace-local basetemp removed
  that filesystem issue.
- Sandboxed FastAPI TestClient then stalled while Python created its asyncio local socket pair
  (`socket.accept` / `_fallback_socketpair`). The stalled owned processes were stopped.
  The same diagnostic/tests were run with tool-approved execution outside the sandbox and
  completed. The frontend test worker also stalled in the sandbox and completed outside it.
- The first browser harness used StaticPool with one shared in-memory SQLite connection.
  Concurrent browser requests caused one logged InterfaceError. That harness was stopped and
  corrected to use a unique disposable file database with separate connections. The corrected
  browser log contains no ERROR or 5xx matches through completion of Check the plan.
  This harness error is not evidence of a production PostgreSQL defect.
- Browser automation also encountered a transient stale node and a navigation wait timeout.
  Fresh page inspection and direct navigation to the observed plan link resolved the automation
  steps. These were not classified as application crashes.

## Remaining limits and changes

- VERIFIED: `docker ps` could not connect to `dockerDesktopLinuxEngine`; Docker Desktop was
  not running in the inspected app inventory. The existing Docker application's data and
  containers were not used for these tests or modified. Starting/rebuilding Docker was not
  necessary to test the isolated source application.
- VERIFIED: the live `https://novaq.site/simulation/results` entry redirected this browser
  to sign-in. NOT TESTED: the authenticated live simulation workflow and the owner's saved
  setup/data/plan. Deployment parity and the cause of any failure in that existing analysis
  remain UNKNOWN.
- NOT TESTED: Named Shared Queue execution, which needs employee/roster inputs absent from
  this CSV; other seeds, all setup combinations, cross-browser coverage, and production math
  or performance assurance.
- Actual additions: this report and owned diagnostic scripts/logs/database in
  `output/shared-queue-debug-20261029/`. `frontend/dist` was regenerated by the build.
  No tracked application, test, locale, schema, mathematical or API-contract file was edited.
- Cleanup: the owned diagnostic server was stopped after verification, and both owned browser
  tabs were closed. Diagnostic logs and the unique test database remain as local evidence.
- Next bounded action if the failure persists: reproduce the exact failing saved analysis
  and request/error in an authenticated runtime; compare its stored setup, selected dataset,
  selected plan and closing rule against the tested prerequisites. No speculative source
  change is justified by the evidence collected here.

## Evidence and applicable specifications

- `output/shared-queue-debug-20261029/reproduce.py`, `serve.py`.
- `reproduction-unsandboxed.log`, `reproduction-selected.log`, `direct-engine.log`.
- `baseline-tests-unsandboxed.log`, `frontend-tests-unsandboxed.log`, `frontend-build.log`.
- `browser-server.log` (superseded single-connection harness),
  `browser-server-filedb.log` (corrected browser execution).
- Browser accessibility/screenshot/console observations in this chat.
- `backend/api/shared_continuous.py`, `backend/api/workflow.py`,
  `backend/data/analysis_ingestion.py`, `backend/api/scenarios.py`.
- `frontend/src/pages/QueueSimulationPage.tsx`,
  `frontend/src/components/queueSimulation/ContinuousRun.tsx`, `RunBar.tsx`.
- `docs/superpowers/specs/2026-10-09-b4a-continuous-shared-run-preview.md`;
  `docs/superpowers/plans/2026-10-09-compact-workflow-ux-redesign-plan.md`, phase 10;
  `docs/superpowers/specs/2026-10-13-od-ux-13-full-day-decision.md`.
