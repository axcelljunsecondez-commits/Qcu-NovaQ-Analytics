# NovaQ responsive overview: implementation plan

Date: 2026-10-16 (Asia/Shanghai).

**Current status, 2026-10-16: implementation, source/build verification and the separately approved local Docker web refresh finished. Actual Docker browser checks passed within the recorded scope; broader native/fixture acceptance remains PARTIAL.** See the [verification report](../reports/2026-10-16-responsive-overview-verification.md). Follow the [specification](../specs/2026-10-16-responsive-overview-ui-refinement.md) for approved behavior and protected boundaries. The task lists below are requirements, not evidence that every acceptance axis passed.

Historical documentation baseline: the owner's initial “go” authorized this consolidated specification and plan. Application work was not started during that documentation step.

**Approval update, 2026-10-16:** the owner approved the completed combined preview and application implementation. No test result or runtime completion is inferred from that approval; actual evidence is recorded separately.

## 1. Scope and working baseline

Work in `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/.claude/worktrees/ux-workflow-audit`, currently `feat/ux-u1-shell` at `0b9423ec66d32620ed91769ac35a10e51ffae2ec`, with existing dirty reconstruction and mathematical repairs. The root checkout is not the implementation source. No reset, stash, checkout, bulk formatter, commit, push, schema/API/mathematical change or Docker cleanup is part of this plan.

Do not edit Home/auth/public routing, global root/body theme values, existing model/calculation helpers or the backend. Fix signed-in appearance through `.app-shell` scope. Keep the public calculator's existing path unchanged; corrected explanations opt in for signed-in consumers.

## 2. Expected file scope

Existing files, only for the following responsibilities:

| File, relative to this worktree | Permitted purpose |
|---|---|
| `frontend/src/styles/theme.css` | Add approved canonical mappings/compatibility aliases inside signed-in shell scope, both themes. Leave root/public values intact. |
| `frontend/src/styles/global.css` | Scoped signed-in fitting, typography, colour pairs, focus, chart/list/table and help rules. No public/global-selector rewrite. |
| `frontend/src/components/analysis/AnalysisWorkspace.tsx` | Controlled bounded selector; analysis name as context rather than h1. Preserve tabs/footer/navigation behavior. |
| `frontend/src/pages/ResultsPage.tsx` | Approved default composition, operational summary, reference-view query, context-preserving links and existing query guards. |
| `frontend/src/components/results/KeyResults.tsx` | Two main cards and compact existing attention/demand answers; stable brief explanation controls; unchanged values/helpers. |
| `frontend/src/components/results/ResultsDetails.tsx` | Full technical table/model reference on the dedicated read-only view, preserving every current field/explanation and filters. |
| `frontend/src/components/results/ResultsCharts.tsx` | Accessible exact-value semantic lists integrated with existing HTML bars, eliminating duplicate visible tables. |
| `frontend/src/components/results/BusyStrip.tsx` | Add a presentation-only opt-out for its duplicate selected-period table when ResultsSummary already renders those filtered rows. Defaults preserve other consumers; levels, warnings and selection remain unchanged. |
| `frontend/src/components/results/FileSelector.tsx` | Neutral planning identity, fitting source context and removal of deferred-feature filler; unchanged file selection/data-date semantics. |
| `frontend/src/pages/OptimizePage.tsx` | Place controls/run before full-width results; replace fixed light/incorrect inline styles and undersized inputs. Preserve all handlers, signatures, options and persistence. |
| `frontend/src/pages/ReportsPage.tsx` | Bounded selector and existing-preview plan/dataset/available shared multiplier context; preserve level/refusal/download logic and exact contents. |
| `frontend/src/api/reports.ts` | Type only inspected existing preview data/assumption/provenance fields needed by the context. No URL/payload/helper behavior change. |
| `frontend/src/pages/QueueSimulationPage.tsx` | Use the controlled bounded selector only. Preserve run modes, navigation, evidence and existing label repairs. |
| `frontend/src/components/ui/InfoTip.tsx` | Explicit opt-in stable interaction with a compatibility-preserving default. No hidden authentication lookup or public opt-in. |
| `frontend/src/pages/QuickCalculatorPage.tsx` | Pass stable interaction only for authenticated consumers, preserving all request/metric-basis behavior and the guest path. |
| `frontend/public/locales/en/translation.json`, `frontend/public/locales/tl/translation.json` | Add symmetric keys for approved changed copy; preserve existing unrelated edits. |
| Relevant existing frontend tests | Extend the behavioral coverage below without weakening mathematics, request or evidence expectations. |

New files proposed now, not claims of existing components:

- `frontend/src/components/analysis/AnalysisSelector.tsx` and `AnalysisSelector.test.tsx`: controlled selector/presentation only; all querying/defaults/ownership/URLs stay in callers.
- `frontend/src/components/results/ResultsSummary.tsx` and `ResultsSummary.test.tsx`: one set of operational rows rendered as the desktop table/mobile labelled list, using existing value helpers.
- `frontend/src/components/ui/InfoTip.test.tsx`: meaningful opt-in interaction regressions.

Primary existing test files: `frontend/src/pages/ResultsPage.test.tsx`, `ReportsPage.test.tsx`, `OptimizePage.test.tsx`, `QuickCalculatorPage.test.tsx`, `QueueSimulationPage.test.tsx`, `CurrentDatasetCache.test.tsx`, `frontend/src/components/layout/AppLayout.test.tsx`, and `frontend/src/lib/translationKeys.test.ts`. Inspect test ownership and existing coverage before deciding which assertions to add. Do not add tests that merely mirror CSS strings or lock in the known guest defect.

These are the bounded expected implementation files. If a needed change falls outside them, first establish its source dependency and revise the reviewable scope explicitly; do not drift into unrelated cleanup. The two new specification/plan files are the only repository documents written in the current documentation step.

## 3. Step 0 — Preserve and confirm the source

Before any application edit:

1. Read AGENTS, current memory/handoff, the parent reconstruction plan and this specification. Recheck `git worktree list --porcelain`, branch/HEAD and `git status --short`; inspect every overlapping dirty hunk.
2. Save a path/hash manifest for tracked and non-ignored untracked application files and existing documents. Record the diff/staged state. Never claim a clean tree where earlier work exists.
3. Recheck the audit's source locations, current container/assets if relevant, and the current source/public boundary. Shared `InfoTip` and calculator paths are especially sensitive.
4. Confirm the Results reference is a presentation query, not a new API or a new plan selection. Confirm that the report preview already has the plan/dataset fields used by the UI. A missing field must show unavailable context, not an invented default.
5. If overlapping work cannot be isolated or a protected dependency is required, stop that affected edit. Continue independent documented work where safe.

Exit evidence: exact baseline, permitted file list and no unexplained dependency on mathematical/auth/report-generation changes.

## 4. Step 1 — Produce one combined review preview

This is the next deliverable after the current documentation step. Create a separate preview artifact; preserve the earlier two mockups unchanged as historical references. Do not generate another competing layout or silently copy their light-only/small-text rules.

The combined preview must implement this specification's hierarchy and show light/dark paired views at desktop/mobile. Include:

- Existing synthetic aggregate fixture as a labelled example with unavailable recorded wait; do not invent new numerical outcomes.
- A no-plan state with readable operational results and an Inputs and model reference link.
- A review-file reference state with no false computation-workbook availability.
- A selected-plan export-context state, using only verified fixture data or explicit blanks/“Example” labels. Do not substitute invented saving/Decision numbers.
- The reference view, return/context behavior, semantic chart/list alternative, normal/focused/disabled actions, long EN/TL labels and stable explanations.

Use local preview interactions only; a preview action does not claim to save, calculate, simulate or download a real report. Verify actual text sizes and colour pairs, document/main overflow at 375/768/1024/1440, keyboard and explanation behavior. Record real touch/native-language limitations. No application fix is proved by this preview.

Review the **whole** proposal once, including the reference-view exception to Excel-only detail, before application editing. The current “go” to prepare documents does not approve presentation details that were discovered while writing them. Use the review to settle those concrete choices together rather than revising isolated screens repeatedly.

## 5. Step 2 — Signed-in colour, type and fitting foundation

After the concrete preview/scope is accepted:

1. Add MASTER mappings in `theme.css` under `.app-shell`, with dark overrides under the existing document theme. Leave global/public values untouched. Set shell canvas/text/16 px body roles.
2. Pair gold foreground/background explicitly and repair status pairs, supporting text, focus and meaningful control borders. Do not remap blue `--primary-contrast` to the gold role.
3. Add scoped minimum sizes and fitting rules. Inputs/select values 16 px, functional labels/tables/buttons/badges at least 14 px; no forced clipping or precision reduction. Scope helper-text measure changes to signed-in context.
4. Build the controlled `AnalysisSelector` and replace only selector markup in the four callers. Retain caller filtering, API/query enabling, analysis selection, URL generation and remembered-analysis behavior.
5. Change the workspace analysis h1 to context text. Preserve the actual page h1, tabs and existing workflow footer. No replacement Next step component is introduced.
6. Remove fixed light fills/incorrect inline action foregrounds and 14 px input values in Optimize; do not broadly refactor its control/state implementation.

Focused verification: selector labels/controlled changes and no duplicate h1; browser main/document fitting with long names and both themes; Home/public/auth computed styles unchanged relative to the baseline. CSS-disabled component tests cannot establish visual isolation.

## 6. Step 3 — Stable explanations within the permitted scope

1. Define an explicit stable interaction opt-in on `InfoTip`; the existing default preserves the public caller. Signed-in calculator and new Results help controls opt in explicitly.
2. Separate focus/hover opening from explicit pinned activation. First activation pins open, second closes. Leaving to the popup must not dismiss it; Escape/outside/blur dismissal must not immediately reopen from the same event. Keep the native button and accessible name/description/state.
3. Keep critical warnings, units and evidence basis visible. Shorten optional repeated explanation copy only; do not remove the Erlang-A workload-basis disclosure from the approved repairs.
4. Add meaningful tests for pointer hover+focus+first click, keyboard focus/Enter/Space, repeated activation, Escape, movement into the popup, and dismissal. A pure `.click()` test that skips actual focus/hover ordering is insufficient.
5. Exercise real browser pointer and keyboard paths in both themes. Exercise actual touch input if supported; otherwise leave touch NOT TESTED and the corresponding acceptance item open. Do not relabel a mouse click at mobile width as a touch test.

The guest first-click defect is not claimed fixed in this bounded phase. Do not add a test asserting that defect as desired behavior.

## 7. Step 4 — Concise Results with intact reference access

1. Implement `ResultsSummary` from the existing rows, filters and formatters. Render an accessible full-width operational table on larger screens and a complete labelled row list on mobile. Preserve line identifiers and every matching row; no new cross-line total/average.
2. Recompose the existing KeyResults answers into two cards and compact attention/demand blocks. Preserve recorded/estimated source meaning, missing values, overload exclusions and existing supported ranking helpers.
3. Add the allowlisted `view=reference` presentation branch in `ResultsPage`. Reuse existing current/observed data and selected-file guards. Move `ResultsDetails` there, remove its outer technical collapse, and preserve all metric/model/explanation content. The reference remains read-only.
4. Link into and back from the reference without dropping analysis/file/period/line. File changes clear period/line as today; analysis changes preserve current clearing behavior. Make the heading/focus reflect the presentation change, including same-path query navigation.
5. Combine each current HTML bar chart with its exact-value semantic list so the extra visible table is unnecessary. Preserve all values/units/flags and missing-state semantics. Do not remove unrelated Plotly alternatives.
6. Keep multi-period strip navigation and fixed busy-level meaning; avoid repeating a one-period strip beside an identical operational row. Preserve plan-target warnings wherever applicable.
7. Keep the existing PlanChanges behavior and distinct saved-plan basis. Use its Reports continuation for plan exports. Never advertise a planning workbook as an arbitrary reviewed file's computation export.

Meaningful regression cases:

- Shared/separate; aggregate/customer-record data; supported unavailable/unstable/empty/error states.
- No plan, eligible saved plan, stale plan, what-if plan and failed selection. No automatic save/selection/run.
- Planning/review/older-file switching, filters, reference deep link and return, reload, changed analysis, cached data and data from a mismatched response while loading.
- Review-only reference makes no workflow/scenario/comparison/selection request; existing current/observed query keys and dataset guard remain intact.
- Every moved field/explanation is reachable in the reference; every chart has the same important textual values; no nested technical calculations remain on the default screen.

Do not weaken existing tests merely because the same preserved content now appears on the reference view. Update the test's navigation/context and retain the evidence/value assertions.

## 8. Step 5 — Supporting page composition and report identity

1. Move Suggested plans' existing controls/run action ahead of its results; use full-width results rather than a permanently empty half-column. Keep separate/shared branches, break section, advanced options and all handler/state/disabled semantics intact.
2. Keep Data and setup's main upload/template flow and planning/review purpose intact. Only shared context, hierarchy, helper measure and fitting changes apply.
3. Read the server report preview's existing dataset/assumption/provenance fields; extend frontend types only as necessary. Display the actual report plan/dataset and available shared multiplier. Do not infer a missing multiplier, baseline equality or native formula support.
4. Preserve Reports' server-derived stamp, refusal codes, full-report Decision gate, exact PDF/Excel contents, download URLs and data-only controls. No report workbook/PDF source changes.
5. Queue simulation only receives the common selector/readability changes. Current/Suggested, named mode, operating hours, closing rules, breaks, run settings and existing basis labels remain untouched.
6. Add changed copy to both locale files. Inspect labels in both languages in the preview/application. Record native-language quality as unverified when no qualified review was performed.

Test actual report identity using a shared changed-demand fixture in component tests; a matching dataset ID must not make the UI label it as a workbook for unchanged Current inputs. Keep existing no-plan/stale/refusal/ownership export tests unchanged.

## 9. Step 6 — Repository gates and integrated browser acceptance

Run focused tests during implementation, then the required final gates once on the finished source. Run serially where resource pressure is relevant. Preserve complete output, elapsed time and exit status. A restricted-environment failure is not a product assertion pass or a valid measurement; diagnose it and report any authorized rerun separately.

Frontend, from this worktree's `frontend/`:

```powershell
npm.cmd test
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

Backend and lint/type, from this worktree, using the verified root virtual environment rather than bare system pytest:

```powershell
$taskPython = 'C:\Users\Administrator\Desktop\QUEUING_THEORY_NOVAMART\NovaQ\.venv\Scripts\python.exe'
& $taskPython -m pytest tests/ -x --tb=short
& $taskPython -m ruff check .
& $taskPython -m mypy .
```

No mathematical changes are planned; no new mathematical-correctness claim is earned by these software gates. Preserve current formula/report tests and protected numerical helpers byte for byte.

Browser acceptance on an identified build:

| Axis | Required checks |
|---|---|
| Themes/languages | Light and dark, EN and TL; computed colours/sizes and all relevant interactive states. |
| Width/access | 375/768/1024/1440 px, sidebar shown/rail as applicable, narrow landscape, 200% zoom, reduced motion, keyboard, actual touch if supported. |
| Fitting | Document and main scroll widths fit; long context names wrap; compact summary fits/mobile list retains every field; only wide reference tables scroll locally. |
| Results/reference | Both queue structures, real stored source identity, unavailable/unstable warnings, filters, reference/deep-link/return and no stale values after switching. |
| Evidence/export | No-plan, eligible/stale/changed-demand plan, review-only file; honest plan/dataset labels and unchanged report/data-only eligibility. |
| Workflow | Existing saved-plan reopen/selection, run-basis labels, Reports continuation and stored Decision remain intact. Do not initiate new runs on the owner's records merely to generate acceptance evidence. |
| Isolation | Home, guest calculator, public Help and authentication appearance/behavior unchanged; no protected request/body changes. |

Use existing synthetic records read-only where sufficient. Any fixture creation or analytical run needed later must be explicitly identified and in scope; do not overwrite existing records. Inspect console/network failures through supported tools without exposing secrets.

Record source-to-runtime identity: HEAD plus dirty diff/hash manifest, web image/container if used, JS/CSS asset names and hashes. The earlier audit found equal served/dist CSS but different JS/i18n entry names. A new browser pass must identify what was actually served; source tests alone do not resolve that discrepancy.

## 10. Step 7 — Local Docker preview, only within the owner's boundary

This is a future conditional phase, not an action in the current documentation task.

1. Re-read the current Docker retention/replacement instructions; inspect actual resources and available memory. Report UNKNOWN when a measurement is unavailable. Build at most one image at a time with a unique date/digest tag and retain existing resources. No pruning/deletion.
2. For frontend-only changes, the existing API/db/one-shots need no rebuild. A build is not permission to recreate an active container.
3. If replacement is needed for final local Docker verification, first prepare exact current web container/image identity, proposed command, measured writable layer, asset/source evidence, test results and rollback limits. Obtain the owner's fresh itemized approval for that specific replacement, as required by the existing reconstruction plan. Do not reuse the old approval.
4. After authorization, replace only the approved web container, preserve dependencies/volumes/images/cache, and verify the actual built assets and changed signed-in behavior. Health checks alone are insufficient.

A separately identified temporary source preview can support earlier UI testing, but it must be reported separately from the final Docker runtime. This phase never authorizes deployment, migration, production settings, commit or push.

## 11. Final diff and completion report

Compare the final manifest/diff with the preserved baseline. Verify that pre-existing dirty hunks and untracked work survive; inspect the exact file list and confirm no protected/source/public files changed beyond the reviewed frontend scope. Do not stage unrelated work.

Report actual modifications, executed results including failures, build identity, unresolved defects, NOT TESTED/UNKNOWN items and any scope deviation. Distinguish preview success, source regression success, local Docker proof and production proof. Native Excel remains unverified unless it is actually opened/recalculated and recorded through an authorized check.

The current documentation deliverable is complete when these two files are internally consistent, source references/links are verified, and existing files remain untouched. The application task is complete only after the reviewed implementation and applicable acceptance gates; no planned task above is a completion claim.
