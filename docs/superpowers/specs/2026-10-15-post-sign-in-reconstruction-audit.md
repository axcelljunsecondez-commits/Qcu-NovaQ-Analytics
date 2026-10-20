# NovaQ reconstruction after sign-in: audit

Date: 2026-10-15 (Asia/Shanghai).

**Status: audit completed; implementation NOT STARTED.** The owner requested an audit and documented plan before application changes. This is local evidence, not production verification or a release approval.

## Scope and evidence rules

- Owner requirement: reconstruct the experience after sign-in using the supplied workflow diagram. Home is explicitly excluded, including indirect changes through shared styling. Authentication screens and behavior remain outside the reconstruction.
- Diagram: `C:/Users/Administrator/Downloads/mermaid-diagram.png`; SHA256 `2484AD73811B56FF8DA3F6D8FF02CE760E6131CE0CA7CFF4169421E0C61779EA`. It defines requested workflow, not proof of implementation.
- Four requested areas: My Analyses (create/setup/plan/save), Analysis Results (reopen saved work and view KPIs), Queue Simulation (choose saved analysis/plan, run, inspect metrics), Quick Calculator (manual inputs and independent assessment).
- Existing Reports, Decision, Help and Settings are preserved. Their omission from a business-flow diagram does not authorize removal.
- Read `AGENTS.md`, relevant `memory.md` and `handoff.md` context, the 2026-10-09 compact-workflow spec/plan, and `design-system/novaq/MASTER.md`. Used the ui-ux-pro-max accessibility and navigation guidance.
- VERIFIED means inspected source, actual command output or an observed browser state. PROPOSED remediation is not an implemented result. Mocked frontend tests do not establish numerical correctness or a real database workflow.

## Checkout and local runtime

VERIFIED at the start and before writing these documents:

```text
Worktree: C:\Users\Administrator\Desktop\QUEUING_THEORY_NOVAMART\NovaQ\.claude\worktrees\ux-workflow-audit
Branch: feat/ux-u1-shell
HEAD: 0b9423ec66d32620ed91769ac35a10e51ffae2ec
git status --short: ?? novaq_local.db
Tracked/staged diffs: empty
```

The pre-existing untracked database was left untouched. The root checkout was not used as the implementation source.

Actual local command output:

```text
docker info --format "{{.MemTotal}}"
4022951936

Windows TotalPhysicalMiB: 8031.70
Windows FreePhysicalMiB: 1180.60
Later, before the third test batch: FREE_PHYSICAL_MIB=1102.8

curl.exe -sS --max-time 10 -w "\nHTTP %{http_code}\n" http://localhost/healthz
ok
HTTP 200

curl.exe -sS --max-time 10 -w "\nHTTP %{http_code}\n" http://localhost/api/health
{"status":"ok"}
HTTP 200
```

Actual `docker compose ps -a` snapshot (relative ages are those printed by Docker):

```text
NAME                                  IMAGE                               COMMAND                  SERVICE           CREATED        STATUS                         PORTS
ux-workflow-audit-api-1               ux-workflow-audit-api               "/bin/sh /app/backen…"   api               15 hours ago   Up About an hour               127.0.0.1:8000->8000/tcp
ux-workflow-audit-bootstrap-admin-1   ux-workflow-audit-bootstrap-admin   "python -m backend.d…"   bootstrap-admin   15 hours ago   Exited (0) About an hour ago
ux-workflow-audit-db-1                postgres:16-alpine                  "docker-entrypoint.s…"   db                15 hours ago   Up About an hour (healthy)     127.0.0.1:5432->5432/tcp
ux-workflow-audit-migrate-1           ux-workflow-audit-migrate           "alembic upgrade head"   migrate           15 hours ago   Exited (0) About an hour ago
ux-workflow-audit-web-1               ux-workflow-audit-web               "/docker-entrypoint.…"   web               15 hours ago   Up About an hour (healthy)     127.0.0.1:80->8080/tcp
```

No build, restart, migration, Docker cleanup or production operation was performed during this audit. No image-to-Git-SHA attestation was established; the browser checks describe the running local image, while source references describe the HEAD above.

## Mapping the requested diagram to the implementation

| Diagram stage | Current evidence | Boundary or gap |
|---|---|---|
| My Analyses / Saved Records | VERIFIED: `/analyses` lists owned, unarchived analyses; `frontend/src/pages/AnalysesPage.tsx:88-143`, `backend/api/analyses.py:79-96`. Browser displayed analyses 1 and 2 during this audit. | An analysis record is not proof of processed data, a selected plan or completed simulation. |
| New Analysis / Queue Setup / queue arrangement | VERIFIED: the new form offers shared/separate structures and optional help; `NewAnalysisPage.tsx:47-62`. Success redirects to `/analyses/:id/data`. | Structure is chosen on the New Analysis form today. The diagram is a business flow, not proof that these must become separate wizard screens. |
| Save Analysis and Plans | VERIFIED in source: analysis creation commits immediately (`backend/api/analyses.py:99-116`); setup patches commit separately (`:128-148`); plans save through `OptimizePage.tsx:658-731`. | This is not one atomic final Save transaction. Preserve the API/persistence order; do not create a new draft contract implicitly. Real create/upload/save sequences were NOT TESTED in this audit. |
| Generate Suggested Plan | VERIFIED in source: both shared and separate save handlers exist, with stale/incomplete guards and save-then-select behavior; `OptimizePage.tsx:647-731`. Browser opened the separate-queue optimizer and its source-dataset selector. | Optimization was not invoked. No staffing or feasibility conclusion is established by this audit. |
| Analysis Results / KPIs | VERIFIED: `/results?analysis=2` rendered its processed-file selector, source-labelled KPIs and tables without a selected plan. `ResultsPage.tsx:37-60,101-106` supports this. | Current results require processed data, not a suggested-plan selection. No valid last-used context exposes finding F1. |
| Reopen a saved suggested plan | VERIFIED in source: saved plans are read and existing selections can be switched (`useSelectedPlan.ts:29-54`, `PlanChanges.tsx:109-133,198-245`). | The initial no-selection branch hides those options: F3. |
| Queue Simulation / choose analysis / Current and Suggested | VERIFIED: `/simulation/results?analysis=2` displayed an analysis selector and Current/Suggested controls. Suggested without selection showed its prerequisite message. Replay retained `analysis=2&plan=suggested`. | Preserve saved selection and server eligibility. A Current run and a suggested-plan run have different prerequisites. F1, F3 and F4 affect this flow. |
| Run Simulation / metrics | VERIFIED: an already saved Current run for analysis 2 rendered as Done, with a period-by-period basis and unavailable day totals. | The audit did not execute that run. Who ran it, the underlying inputs' provenance and mathematical correctness are UNKNOWN or NOT TESTED here. Do not present the stored Done state as an audit-executed simulation. |
| Quick Calculator | VERIFIED: its signed-in route opened. Source calls its independent analysis/calculator APIs (`QuickCalculatorPage.tsx:74-105`, `frontend/src/api/analysis.ts`). | Manual calculation against the live API was NOT TESTED. Existing mocked tests passed; no saved analysis is needed by this source flow. |
| Decision / Reports | VERIFIED: routes and evidence-gated components remain. Reports for empty analysis 1 explained missing files/selection. MASTER section 9.4 defines the evidence gates. | No Decision creation or PDF/Excel export was executed. These features must remain available under their existing prerequisites. |

The browser initially showed only analysis 1, `SYNTHETIC — sidebar wiring check (no data)`. Later it showed analysis 2, `test`, with a processed file labelled `NOVAMART_DATA_UPLOAD.xlsx`. The audit did not create or upload analysis 2; its creation/input provenance is UNKNOWN. Dates and metrics displayed for that file were not independently reconciled against the workbook. They are evidence that the result view renders, not verification of those numerical values.

## Findings

### F1 — Direct entry silently returns to My Analyses without context

**VERIFIED from source; priority: high for the requested workflow.**

`frontend/src/components/layout/navigation.ts:28,34,40` sends Results, Reports and Queue Simulation to `/analyses` when no valid last-used analysis exists. The pages repeat that fallback at `ResultsPage.tsx:66-69`, `ReportsPage.tsx:87-90` and `QueueSimulationPage.tsx:46-49`.

This does not provide the analysis-picker empty state required by the approved compact-workflow spec section 7.3 (`2026-10-09-compact-workflow-ux-redesign.md:308`). The same branches also omit an explicit list-query error state when no valid analysis ID is supplied. A failed lookup must not be described as an empty account.

The current browser has a valid remembered analysis, so this audit verified that valid-context links open their destinations. It did not clear browser storage or recreate a first-use account. The earlier local-sidebar audit recorded a browser reproduction of the empty-account fallback; that is prior evidence, not a newly executed reproduction here.

PROPOSED: retain valid last-used convenience, but otherwise enter the requested area and show a saved-analysis picker, honest loading/error/empty states and a create action that preserves the intended destination. Do not silently select a different analysis when an explicit URL names an inaccessible record.

### F2 — Collapsed sidebar links have no accessible names

**VERIFIED in the running browser and source; priority: high for accessibility.**

All five collapsed navigation links had `aria-label: null`; their `.nav-label` elements had computed `display: none`. The accessibility tree exposed link URLs without names. The expanded sidebar was restored after inspection.

Source: `Sidebar.tsx:91-99`, `global.css:4520-4525`, `Tooltip.tsx:10-13,36`. Tooltip text is deliberately `aria-hidden` and cannot supply the link name.

PROPOSED: add each link's existing translated label as its accessible name and verify it with the collapsed CSS applied. Current Vitest configuration sets `css: false`; a DOM-only test that leaves label text visible is insufficient proof of the collapsed browser behavior.

### F3 — Saved plans cannot be chosen from the initial no-selection state

**VERIFIED conditional source behavior; priority: high for reopening saved records.**

`useSelectedPlan.ts:38,52` can return `kind: 'none'` together with available separate comparisons or shared scenarios. `PlanChanges.tsx:188-195` then renders only a no-plan message and a Suggested plans link. It does not render the saved-plan switcher. The switcher is reached only after a selected plan has been resolved (`:198-245`).

Both Save without using and a save-success/selection-failure path can leave a saved plan without selection (`OptimizePage.tsx:647-731`). The failure copy says the plan can be selected in Analysis Results (`en/translation.json:1604`, symmetric TL key), but that initial branch has no selection control. Queue Simulation also points back to Suggested plans when a plan is absent (`QueueSimulationPage.tsx:107-124`).

PROPOSED: expose eligible saved plans before the first selection as well as after it. Reuse server-reported currentness/validity and the existing selection endpoint; keep foreign, stale, historical and incomplete plans ineligible. Only an explicit user action may persist a selection. Do not regenerate or duplicate a saved plan just to select it.

NOT TESTED: a real local save-without-selection followed by a fresh-session reopening. No saved plan was created solely to manufacture that state during this read-only audit. Existing no-plan tests use an empty scenario list (`ResultsPage.test.tsx:126-137,175-181`), so they do not cover available-but-unselected plans.

### F4 — A period-by-period run is offered as Run full operation

**VERIFIED in browser and source; priority: medium for truthful simulation wording.**

For separate-queue analysis 2, Current displayed a `Run full operation` button immediately above `One period at a time`. `QueueSimulationPage.tsx:129-132` supplies no label override for a separate context. `RunBar.tsx:11,26-28,73-78` therefore uses its full-operation default, while `simulationContext.ts:85-91` identifies Current as period-by-period. The Current API invokes `simulate_segments_with_trace` (`backend/api/workflow.py:1404-1428`).

PROPOSED: choose the action label from the existing run basis. Preserve the API, hours, seed, carryover options, simulation code, saved summaries and truthful unavailable totals. A real continuous Current engine for an unsupported path would be separate mathematical/backend work, not a wording fix.

## Design details that must not be silently inferred

- The diagram's saved records are existing owned analyses, datasets and scenarios, not evidence that a new generic record store is required.
- Current results may be opened before a plan exists. A plan is needed for the suggested-plan simulation; do not impose that prerequisite on every current view.
- The compact-workflow spec section 7.6 describes an evidence-driven Next step panel, while MASTER section 9.1 still assigns the stepper and Previous/Next to `WorkflowNavigator`. The current workspace renders that stepper (`AnalysisWorkspace.tsx:46`). This is a documentation/design ambiguity, not proof that its links are broken. The plan preserves the existing footer initially and requires a separate explicit design decision before replacing it.
- A source-labelled KPI is not an independently verified measurement. A stored simulation is not a new audit run. A rendered route is not proof of its complete workflow.

## Checks actually executed

All test batches ran in `frontend/`, one worker, sequentially. API calls in these component tests are mocked. No application/test source was edited.

| Batch | Command after `npm test -- --maxWorkers=1` | Actual result | Vitest duration | Measured command elapsed |
|---|---|---|---|---|
| Navigation/create | `src/components/layout/Sidebar.test.tsx src/pages/NewAnalysisPage.test.tsx src/pages/AnalysesPage.test.tsx src/pages/AnalysesPageSearch.test.tsx` | 4 files passed; 42 tests passed; exit 0 | 43.92 s | 48.54 s |
| Results/simulation/calculator | `src/pages/ResultsPage.test.tsx src/pages/ReportsPage.test.tsx src/pages/QueueSimulationPage.test.tsx src/pages/QuickCalculatorPage.test.tsx` | 4 files passed; 90 tests passed; exit 0 | 65.78 s | 68.52 s |
| Setup/save/workspace | `src/pages/OptimizePage.test.tsx src/pages/AnalysisSetupPage.test.tsx src/components/analysis/WorkflowNavigator.test.tsx src/components/analysis/AnalysisWorkspace.test.tsx` | 4 files passed; 80 tests passed; exit 0 | 76.89 s | 79.97 s |

Total: **212 tests passed across 12 files; no failed test in these three batches.** The second batch printed two jsdom `HTMLCanvasElement.getContext()` not-implemented messages; tests still exited 0. This does not verify canvas rendering.

Passing baseline tests do not close F1-F4. Sidebar tests currently expect the My Analyses fallback (`Sidebar.test.tsx:78-107`), and the initial saved-plan-selection case is missing.

Browser checks executed: new-analysis form without submission; existing analysis 2's Data and setup; Suggested plans without Optimize; current result display; existing Current simulation display; missing Suggested selection; Replay context preservation; all four signed-in destinations; collapsed rail names, then expansion. An initial unscoped Open locator matched two existing records and was corrected to the observed `/analyses/2/data` link; no product defect is inferred from that automation error.

The browser changed its last-used-analysis hint through normal navigation. No create, upload, setup-save, archive, optimization, run, selection or export action was submitted during this audit.

### Prior failure retained separately

The earlier same-day local-sidebar audit recorded a sandbox cache EPERM before assertions, followed by 45 passed / 1 failed in a combined shell/router run. The failure was the unknown-Settings redirect while Loading. Its isolated rerun passed 11/11, and the browser redirect passed. Root cause remains UNKNOWN. That combined failure was not re-executed or diagnosed by this audit; the 212 passing tests above do not erase it.

Prior report: `C:/Users/Administrator/.codex/visualizations/2026/10/14/01a13b2b-3883-7bb2-ad6c-05667dc49ecf/novaq-local-sidebar-audit-2026-10-15.md`.

## NOT TESTED and UNKNOWN

- Full live create -> upload/process -> optimize -> save/select -> simulate -> Decision -> export -> reopen workflow for either structure: NOT TESTED by this audit.
- Live Quick Calculator computation, independent numerical reference cases, input reconciliation and simulation correctness: NOT TESTED.
- F3 with a real persisted unselected plan: NOT TESTED; source finding is stated conditionally above.
- Fresh-context picker, failed list request and ownership/deep-link browser cases: NOT TESTED in this pass. No picker fix exists yet.
- Full frontend suite, typecheck, lint, production build and backend pytest/ruff/mypy: NOT EXECUTED in this documentation-only audit. The targeted baseline tests above are the checks actually run.
- 375/768/1024/1440 viewport matrix, EN/TL matrix, dark-mode matrix, full keyboard-only walkthrough and real screen reader: NOT TESTED in this pass.
- Why analysis 2 was created, original workbook provenance, deployed-image source SHA and the earlier intermittent router failure's cause: UNKNOWN.
- Home, authentication changes, production, CI refresh, Render, Pages, Supabase and deployment: outside this audit; no current verification claim.

## Artifacts and next step

Raw test logs and local browser screenshots are under:

`C:/Users/Administrator/.codex/visualizations/2026/10/14/01a13b2b-3883-7bb2-ad6c-05667dc49ecf/`

- `reconstruction-audit-navigation-tests.log`
- `reconstruction-audit-results-tests.log`
- `reconstruction-audit-setup-plan-tests.log`
- `reconstruction-audit-collapsed-sidebar.png`
- `reconstruction-audit-results-existing-analysis.png`
- `reconstruction-audit-plan-prerequisite.png`
- `reconstruction-audit-browser-evidence.json`
- `reconstruction-audit-final.png` (My Analyses left open, expanded sidebar).

See [the proposed implementation plan](../plans/2026-10-15-post-sign-in-reconstruction-plan.md). Only the audit and plan are being added to the repository. Application reconstruction, commits, pushes and Docker rebuilds remain unperformed in this audit-first step.
