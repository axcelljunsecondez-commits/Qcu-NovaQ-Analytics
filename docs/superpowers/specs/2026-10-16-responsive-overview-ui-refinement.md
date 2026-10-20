# NovaQ responsive overview: consolidated UI refinement specification

Date: 2026-10-16 (Asia/Shanghai). Version: 1.0.

**Current status, 2026-10-16: approved UI implementation, source/build verification and the separately approved local Docker web refresh finished. Actual Docker browser checks passed in the recorded scope; broader native/fixture acceptance remains PARTIAL.** See the [actual verification report](../reports/2026-10-16-responsive-overview-verification.md) for executed tests, runtime identity, earlier failures, and remaining NOT TESTED/UNKNOWN items.

Historical documentation baseline: this was initially a proposed design prepared under the owner's “go”; that documentation step did not implement the application or approve its new presentation choices.

**Approval update, 2026-10-16:** after the combined interactive preview, the owner explicitly approved implementation: “approve with no hallucination and zero fabrication, be professional as a full stack devs”. The presentation choices below, including the separate Inputs and model reference, are APPROVED SPECIFICATION. The owner later separately approved the exact web-container replacement; that bounded local operation is verified in the report. Future-tense sections record the approved design, not independent evidence of completion. Further Docker removals, commits, pushes and production remain separately unauthorized.

## 1. Outcome and relationship to existing work

Make the signed-in NovaQ interface readable in light and dark mode, fit its available space, and put operational answers before calculation detail. Use **Responsive overview** as the layout direction, with the owner's later requirement that computation detail should not fill the main screen even inside collapsed sections.

This is one coordinated correction specification and the companion [implementation plan](../plans/2026-10-16-responsive-overview-ui-refinement-plan.md). It refines the existing compact workflow; it does not restart reconstruction or replace the stack.

Authoritative context:

- [After-sign-in reconstruction plan](../plans/2026-10-15-post-sign-in-reconstruction-plan.md), particularly Hard boundaries. Its Home/public/authentication exclusions remain in force.
- [Compact-workflow specification](2026-10-09-compact-workflow-ux-redesign.md), particularly section 7.7 and D14–D21, D31–D33.
- [B8 report specification](2026-10-09-b8-reports-pdf-excel.md), governing the protected calculation exports.
- [NovaQ MASTER](../../../design-system/novaq/MASTER.md), governing tokens, typography, accessibility, evidence vocabulary and protected behavior.
- Inspection record: `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/output/ux-audit-2026-10-16/preflight/readiness.md`. Its observations and test results describe that audit, not implementation of this specification.

VERIFIED source baseline: worktree `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/.claude/worktrees/ux-workflow-audit`, branch `feat/ux-u1-shell`, HEAD `0b9423ec66d32620ed91769ac35a10e51ffae2ec`, with existing dirty reconstruction and approved mathematical-repair work. Root `main` is a different checkout at `6093d78a5874d8cbdfa0026e9c25bdb5ddc70881`. Recheck both the worktree and dirty files before implementation; HEAD alone does not identify the source state.

## 2. Evidence and current defects

| Evidence classification | Finding and identifiable source |
|---|---|
| VERIFIED, source and audit browser | Gold actions use white text in both themes; supporting light text is too faint. See `frontend/src/styles/theme.css`, `.btn-primary`/`.button-link` rules in `global.css`, and the audit's computed styles/contrast matrix. |
| VERIFIED, source and audit browser | `.table-scroll table` has a blanket 620 px minimum (`global.css:3218-3226`). At requested 1440 px, small chart tables are 620 px inside 539 px panels. At 1024 px their panels narrow to 331 px. |
| VERIFIED, audit browser | At requested 375 px, Results and Reports main content is 360 px wide with 381 px scroll width in both themes. Their analysis selectors are not bounded by their flex children. |
| VERIFIED, source | `global.css` sets body text to 14 px; MASTER requires 16 px body/input text and at least 14 px functional labels. Existing mockups contain 12–13 px functional text and light-only palettes. Neither mockup is implementation-ready unchanged. |
| VERIFIED, source and audit browser | `InfoTip.tsx` opens on focus/hover and toggles on click. First pointer click leaves the explanation closed in both themes; keyboard focus and Escape worked in the audit. |
| VERIFIED, source | `ResultsDetails.tsx` combines a wide technical table with nested model explanations. `KeyResults.tsx` repeats a visible “How was this calculated?” disclosure. `ResultsCharts.tsx` repeats each visual's values in a second visible table. |
| VERIFIED, source | `AnalysisWorkspace.tsx:30` uses the analysis name as an h1 above page h1s. `.form-hint` is globally capped at 16rem. `OptimizePage.tsx` has equal control/result columns and fixed light gradients, plus gold fills paired with the blue action's foreground alias. |
| VERIFIED, source | Results may show any processed file; its non-planning branch disables plan/workflow requests. The plan workbook requires a current selected plan (`backend/api/plan_reports.py:_plan_model`). |
| VERIFIED, source; additional finding during specification | A shared what-if run multiplies arrival rates before storing `calculation.input_segments` (`OptimizePage.tsx:run`, `handleWhatIf`). `build_shared_plan_model` exports that snapshot. Matching dataset IDs alone do not establish that the workbook documents unchanged Current inputs. |
| VERIFIED, source | `generate_plan_workbook` and `formula_check.py` export inputs, results and applicable formulas, but do not serialize all `selection_reason`, `operational_facts`, `measured_characteristics` and `model_assumptions` text rendered by `ResultsDetails`. A successful plan export is not exhaustive Current-result coverage. |

The previous inspection passed 43 focused frontend tests and 20 formula/report tests. Its 34 sampled approved colour pairs met numerical targets in both themes. These are prior executed results, not a new run or an integrated redesign pass. Native Excel, native-language quality, real touch input, and production remain NOT TESTED by that audit.

## 3. Scope and safety boundary

APPROVED SPECIFICATION, preserved:

- React, React Router, TanStack Query, global CSS, Plotly, i18next and the existing font/icon foundation remain. No Bootstrap migration, replacement component/chart framework, new font, or new dependency is needed.
- Home, public navigation, authentication screens and behavior, session/CSRF/ownership/roles remain outside scope, including indirect changes through shared CSS.
- Queueing formulas, model dispatch, units, rate preparation, optimizer objectives/constraints, DES/Monte Carlo, replay timing/accounting, Decision derivation, schemas and HTTP contracts remain unchanged.
- Preserve existing saved records, planning/review purpose, selected-plan persistence, current/stale evidence, refusal handling, Current versus Suggested simulation, and report eligibility/content.
- No commits, pushes, production actions, Docker cleanup, or container replacement are authorized by this document. Existing itemized replacement approvals are not reusable.

PROPOSED permitted changes: signed-in presentation, bounded selectors, semantic styling, grouping and copy reduction, accessible chart/list rendering, a read-only calculation-reference view, and explicit plan-export context. Existing handlers, payloads, row values, filter semantics and formatters are reused.

There is no new computation export in this scope. Full Excel-only access to every review/no-plan calculation would require a separately specified protected export extension. Do not manufacture export coverage in the browser.

## 4. One default Results composition

PROPOSED order, from top to bottom:

1. **Context and one page title.** Bounded analysis selector, “Analysis results”, and the existing Help action. File selector and compact source facts: planning/review role, source filename, data dates or Unavailable, upload date. Keep the review/older-file warning and recalculation meaning.
2. **Two primary answers.** Recorded average wait and estimated average wait, with visible units/source distinction. Use short accessible help controls instead of repeating the same explanatory sentence and disclosure label. Keep material unavailable-data and unstable-period exclusions visible.
3. **Compact attention and demand answers.** Retain the existing period-needing-attention and busiest-arrivals answers as compact text blocks rather than two more large KPI cards. Reuse current server fields/helpers; do not calculate new rankings or averages.
4. **Current operation by period.** A short operational table: Period; Service line when applicable; Counters open; Estimated wait (min); Busy level. This replaces the technical table on the default screen. Preserve period/line filtering, all matching rows, unavailable/non-finite handling, and inability-to-keep-up warnings.
5. **Patterns where useful.** Retain the existing arrivals, applicable workload, and recorded-versus-estimated wait visuals, with the same source values. Keep the busy-period strip for multi-period navigation; with one period, the operational row already supplies its busy level. Fixed busy-level meaning and distinction from the plan target remain accessible and explicit. No new chart appears for unsupported/missing data.
6. **Selected plan, when applicable.** Preserve saved-plan switching/explicit selection, calculated-result evidence label, counter/wait/busy changes, cost availability/reason, simulation continuation and Reports continuation. Keep this visually separate from Current data. Plans continue to use the planning file. Review-only files do not show or fetch planning evidence.

The default screen contains no nested model-explanation blocks, full λ/μ/model/input table, candidate-search rows, or formula working below its operational table. Do not replace these with a new “More technical details” collapse on the same screen.

Preserve the information behind those views as described in section 5. Remove the “Compare with another file: coming later” filler from this composition; this does not implement file comparison. Avoid duplicate eyebrow/title words and repeated metric explanations. Required source, units, stale/missing evidence and model limitations are not filler.

### 4.1 Tables and charts

- At larger widths, the operational table spans the content width and wraps headings/long identifiers. It has no arbitrary 620 px floor.
- Below 768 px, show a labelled row/card list containing every operational field, with at least 14 px text. Do not drop the service line or other columns merely to fit. Use the same rows, values and filters in both presentations; only one presentation is exposed at a time.
- Truly wide analytical tables in the reference view may scroll locally inside a focusable, labelled region with captions, row/column headers and visible focus. The page/main container must fit.
- For the current HTML bar charts, combine the exact text labels/values and decorative bars in one semantic list/figure. This supplies the accessible data alternative without a duplicate visible table. Keep every important value, period/line, unit and flagged state. Do not apply `role=img` to an ancestor that hides the only text alternative.
- Do not remove Plotly data alternatives elsewhere. This specification does not standardize or rewrite all chart components.
- Panels use two columns only when both have enough usable width; otherwise stack. Specify this against available content width, including the sidebar, not just viewport size. Long English/Filipino labels and zoom must wrap.
- Reuse `fmtDecimal`, `fmtPctDecimal`, `minutes`, existing busy-level logic and row helpers. No precision change, truncation of numeric values, or frontend total is introduced to force fitting.

## 5. Read-only calculation reference and export coverage

PROPOSED exception to Excel-only detail: keep one separate **Inputs and model** reference view for information not fully represented by the eligible workbook. It does not expand on the main screen.

Use the existing Results route with an allowlisted presentation parameter:

```text
/results?analysis=<id>&file=<existing file id>&period=<existing period>&line=<existing line>&view=reference
```

The new `view=reference` parameter changes presentation only. It does not select a plan, write state to the server, create a file, call a new endpoint or run an optimizer/simulation. Omitted `file` retains the existing planning-file resolver. Existing explicit file and filter parameters retain their meaning; file changes clear period/line filters as they do today.

- A secondary “Inputs and model” link beside the operational table opens this view while retaining analysis/file/period/line context. It is a native link and appears in the keyboard order.
- The reference view has one h1, a clear return-to-results link, the same source identity, the existing full input/metric table and source-returned model explanations. It uses current API data and contains no invented derivation.
- Return removes only `view`, preserving context and filters. Browser Back works normally. Analysis changes retain the existing clearing behavior for file/period/line state.
- The default Results and reference view share the existing current/observed queries and guards; do not introduce a second data loader with different semantics. A review-only file still makes no planning/selection/workflow requests.
- The reference view states a matching workbook's limitations where relevant. It never relabels a data-only file as computation evidence.

### 5.1 Coverage matrix

| Viewed state | Default Results | Calculation reference | Excel behavior |
|---|---|---|---|
| Planning file, no current selected plan | Operational results remain usable | Available for the viewed file | No computation-workbook availability claim. Existing Reports explains the selection prerequisite; data-only download remains distinct. |
| Current selected shared plan, unchanged demand | Current data and saved-plan comparison remain separate | Preserves inputs/model reasons not fully exported | Existing plan/full export via Reports, labelled with its actual plan and planning dataset. Successful server preview remains the eligibility authority. |
| Current selected shared what-if plan | Current headline values remain file results; plan values retain their own basis | Preserves Current file inputs/model reasons | Plan workbook uses the saved changed-demand snapshot. Do not call it the workbook for all Current results, even when its dataset ID matches. Show the available shared multiplier in report context. |
| Separate-line plan | Current line estimates and simulated plan outcomes retain distinct labels | Preserves per-line inputs/model reasons | Workbook Formula check checks today's analytical lines; staffing candidates come from routing simulation. Do not claim a closed-form formula reproduces the selected routing plan. |
| Review-only or older file | Read-only results and review warning | Available for that file; no planning requests | No matching computation workbook is asserted. Data-only export is not a replacement. Do not redirect a “this file's calculations” action to another file's plan workbook. |
| Stale plan or refused report | Current file results stay available; stale plan state remains visible | Available from existing successful current-file response | Preserve the server refusal and existing recovery. Do not disable freshness checks or reconstruct a report client-side. |
| Formula unavailable in Excel | Keep the relevant limitation/source meaning | Preserve existing returned explanation | Keep the workbook's existing stored-value/formula-unavailable distinction. Do not promise native recalculation. |

### 5.2 Reports presentation

Preserve the Reports page's server-derived level, Decision wording, exact section/sheet lists, file endpoints and download handlers. Add concise context from the **existing report preview payload**: plan name, `model.data.dataset_name`/dataset ID, and shared `model.assumptions.what_if_multiplier` when present. A missing multiplier is not silently displayed as 1. Extend only the frontend TypeScript description of these inspected existing fields if necessary; do not change the backend payload.

Use the existing plan-section Reports continuation (labelled “View plan exports” where changed). The actual **Download Excel** action stays on Reports. No duplicate download implementation or generic “all computation details” action is added to the Results header.

This resolves the immediate content-loss problem without changing a protected export: the main screen is concise, the existing workbook remains available for its actual scope, and uncovered reference information stays accessible on its own view. The additional reference view is a PROPOSED presentation choice for review, not an already approved or implemented capability.

## 6. Theme, typography and shared-component isolation

APPROVED SPECIFICATION: MASTER semantic colours, 16 px body/input values, at least 14 px functional labels/buttons/badges/tables, 12 px only for nonessential metadata, tabular numerals, visible focus, and paired light/dark states.

PROPOSED implementation boundary:

- Put canonical signed-in token mappings under `.app-shell` and `[data-theme='dark'] .app-shell` in `theme.css`. Leave existing root/public token values intact. Bind necessary compatibility aliases inside this scope only. Set the shell's own canvas/text/body-size roles so inherited `body {font-size:14px}` does not determine signed-in body text.
- Scope corrective component rules to `.app-shell`. Do not change `:root`, `body`, unqualified `a`/`table`/`th`/`button`, `.home-*`, auth selectors or public-shell styles to obtain a signed-in fix.
- Gold actions pair `--color-action-primary-bg` with `--color-action-primary-fg`. Light: `#E8A838`/`#0A2345`; dark: `#F0B84C`/`#071729`. Never globally redefine `--primary-contrast`, which also belongs to existing blue controls.
- Supporting text uses MASTER `#52647A` light and `#B0BDCC` dark on the approved surfaces. Status controls use explicit background/foreground pairs; do not substitute one legacy `--success` value for both roles. Planning-file identity uses neutral/info styling, not a validation-pass verdict.
- Inspect normal, hover, focus, pressed, disabled, selected, stale and error states, including inline overrides and chart labels. Passing one default pair does not establish the other states.
- Replace the fixed light gradients/status fills in the signed-in `OptimizePage.tsx` with semantic surface/status roles. Fix its inline gold foreground and 14 px editable values directly; stylesheet overrides alone will not supersede those inline declarations.
- Allow explanation text to use its panel's width with a readable text measure rather than a global 256 px cap. Keep field help grouped with its own field.
- The analysis name becomes context text rather than a second h1. Navigation's functional labels and section headings meet the approved minimum; do not make the sidebar fit by shrinking them.

## 7. Context, setup, suggested plans and simulation

Use one small controlled `AnalysisSelector` presentation component in Results, Reports, Queue simulation and the workspace context. Callers retain their own queries, option inclusion rules, selection handlers and destination URLs. The component does not load data, remember analyses, filter ownership, choose defaults or mutate workflow state.

Bound the selector and every flex/grid wrapper (`min-width:0`, maximum available width); stack title/context fields on narrow screens. Native option text remains available. Long source/analysis names wrap in adjacent context text; do not rely on clipped option text as the only identity.

Data and setup keeps Excel-template/upload as the main path, the current planning/review choice, real validation readback and advanced-settings boundary. Only the shared context/readability/fitting rules change here. No additional entry step or duplicate input is introduced.

Suggested plans groups its existing source/target/cost controls with the run action before the result area. Before a run, no empty result column consumes half the page. After a run, the existing results, saved-plan controls and explicit selection actions get the full content width. Keep defaults, handlers, dirty/stale state, signatures, save/selection order, refusals, what-if semantics and break scheduling behavior unchanged. Break scheduling remains a secondary section after primary staffing results.

Queue simulation gets bounded context, readable semantic colours and fitting controls. Do not regroup its evidence, change its run mode, relabel period-independent output as continuous, alter engine/replay settings, or move Decision prerequisites. Preserve the current action-basis fixes already in the dirty tree.

## 8. Tooltip interaction and copy

PROPOSED signed-in explanation contract:

- Hover and keyboard focus open the explanation. First pointer/touch/keyboard activation keeps it open and pins it; the next explicit activation closes it. Focus or synthetic hover must not cancel that first activation.
- Pointer movement from trigger into the explanation keeps it visible. Leaving the whole explanation region closes an unpinned explanation only when it no longer has relevant focus. Blur outside, outside activation, or Escape closes it. Escape clears the pinned state and does not immediately reopen from the same focus/hover event.
- Keep a native button, translated accessible name, stable described-by relationship, `aria-expanded`, readable text, visible focus and on-screen positioning. Plain explanatory text does not contain an interactive menu or hidden action.
- Required errors, unavailable reasons that materially affect interpretation, stale notices, units, model-basis limitations and recorded-versus-estimated distinctions remain visible. Tooltips hold brief optional definitions, not essential workflow instructions or full calculations.
- Use an explicit opt-in interaction mode on `InfoTip` for signed-in calculator/Results consumers. The default guest path remains unchanged in this bounded phase. No component infers authentication from CSS/DOM ancestry. The known guest first-click defect is outside this scope and must remain disclosed rather than claimed fixed.

Each new/changed label has symmetric EN/TL keys. Reuse existing terms: Counters to open, Recorded average wait, Estimated average wait, Busy level, Inputs and model, View plan exports. Translation key symmetry alone is not native-language validation. Do not translate arbitrary dataset/model-reason content by inventing new source facts.

## 9. Proposed amendments and retained requirements

| Existing requirement or prior proposal | Disposition in this specification |
|---|---|
| Compact-workflow section 7.7 manager questions | Retained; two primary cards plus compact attention/demand answers. This grouping is PROPOSED. |
| Repeated “How was this calculated?” disclosures | PROPOSED replacement with accessible brief help controls; material source/limitations remain visible. |
| Technical period/model detail below Results | PROPOSED relocation to `view=reference`, not deletion or another nested collapse. |
| Existing chart table/list alternative | Retained through a semantic exact-value list integrated with the current HTML bars. No chart-only loss of access. |
| Lean mockup's generic “Excel computation details” control | Replaced by honest plan-export context and the separate uncovered reference view. A plan workbook is not every viewed file's workbook. |
| Earlier mockups' 12–13 px functional text/light-only styling | Rejected as an implementation reference; MASTER minimums and both themes apply. |
| MASTER and after-sign-in exclusion of Home/public/auth changes | Retained through scoped tokens/styles and signed-in tooltip opt-in. |
| API/model selection/maths/evidence/report gates | Retained without amendments. |

The new presentation choices need review through the next combined light/dark preview before application editing. This document does not edit or silently supersede the approved MASTER/parent specifications.

## 10. Acceptance and completion

Required later verification, not results claimed by this document:

1. Identified source/build: record branch, HEAD, dirty diff, asset hashes and actual runtime. The earlier served/local-dist JS mismatch must not be carried forward as an unexplained integrated-build claim.
2. Both themes and EN/TL at 375/768/1024/1440 px, with sidebar shown/rail where supported; narrow landscape, 200% zoom and reduced motion. Main and document fit. Only genuinely wide reference tables have local scrolling.
3. Actual computed functional/body/input sizes meet MASTER. All final semantic pairs and meaningful states meet their assigned contrast target. No hardcoded light result card remains in dark mode.
4. First activation, focus, hover, repeated activation, Escape, outside dismissal and touch explanation behavior pass. If the browser cannot supply touch input, record NOT TESTED and keep that acceptance item open.
5. Default Results is concise; the reference view preserves the same file/filter context and source values. Shared/separate, recorded/aggregate, missing/unstable, no-plan, what-if, stale, review-only/older-file and errors are covered. No new planning request occurs for a review file.
6. Every visual has a named exact-value alternative; every operational row remains accessible on mobile. Reference-model explanations are preserved without a new analytical computation.
7. Report level/gates, data-only distinction, saved plan, dataset and changed-demand context remain honest. Workbook bytes/content/formulas are unchanged by this UI task. Native Excel is not claimed verified from Python tests.
8. Home/public/auth pages and protected source/requests remain unchanged. The guest tooltip correction is explicitly excluded, not accidentally activated by a shared-component edit.
9. Relevant behavioral tests and all required repository gates pass on the final source. A failing/unexplained gate stops the affected phase. Report failed attempts as well as successful reruns.

Completion means the reviewed scope is implemented, appropriately tested and verified in an identified local build, with unresolved items explicit. This documentation step completes only the specification/plan deliverable. No guarantee of zero later findings is made.
