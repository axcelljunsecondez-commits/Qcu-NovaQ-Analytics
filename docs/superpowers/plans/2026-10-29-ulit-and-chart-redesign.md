# Plan: ulit wording + chart redesign (combined frontend build)

Date: 2026-10-29. Status: PROPOSED (nothing implemented). Spec: `docs/superpowers/specs/2026-10-29-ulit-and-chart-redesign.md` (section numbers below are the spec's).
Worktree: `C:\Users\Administrator\Desktop\QUEUING_THEORY_NOVAMART\NovaQ\.claude\worktrees\ulit-chart-build`, branch `feat/ulit-chart-redesign`. All paths are relative to `frontend/` unless they start with `docs/` or `backend/`.

## Ground rules for every step

- Frontend only. No backend file, API shape, CSRF, docker or route change. If a step finds it needs one, it stops and reports.
- Wording: only keys and texts from spec App. A. No agent-written copy. A slot in spec App. B that is still empty means the element is omitted.
- Do not edit `docs/wording/2026-10-27-local-wording-application.json` or `src/lib/wordingPolicy.test.ts`. A failure there means approved wording changed: stop.
- Test expectations may change only where the spec changes the visible text or layout. Never to hide a behaviour difference.
- One writer per file at a time (memory `novaq-one-writer-per-file`). The parallel lanes below are drawn so no two lanes own the same file.
- No commit or push unless the owner asks. If commits are authorized, one commit per step, no Claude co-author lines (memory `no-claude-commit-credit`).
- Per-step check = the step's targeted tests + `npm run typecheck` + `npm run lint`. Full gates at step 13.

## Steps

### Step 0 — Baseline (no code)

- Run in `frontend/`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`. Record test count (handoff reports 745/745 on the engine branch; re-measure here), and the `dist/assets` JS sizes from the build output (Plotly chunk included).
- Re-open every file:line cited in spec §4-§9 and confirm it still shows the cited code. Any drift → update the step's line numbers before editing; a behaviour drift → stop and report.
- Start the local stack per `.claude/launch.json` / AGENTS.md (backend :8000 + Vite :5173). Prepare, on a scratch database only: the NovaMart xlsx (from the owner's `NOVAMART_DATA_UPLOAD.xlsx`; path to confirm with the owner if not found) as (a) separate lines, representative day; (b) separate lines, per_date with segments; (c) shared line. Sign in with the seed admin from the project's compose defaults (test credentials, local host only). Calculate and save one plan per analysis; run Current and Suggested simulations and Many variations. Record analysis ids and run ids.
- Screenshot today's screens at 375 and 1280, light and dark: Results (both tabs' current sections), Key Results (separate and shared), Checks (Many variations), Suggested Plans review, Field Guide.
- Done when: gates recorded (pass/fail as observed), sizes recorded, three analyses ready, screenshots saved under the scratchpad.

### Step 1 — Locale keys (single writer for both catalogues)

- Files: `public/locales/en/translation.json`, `public/locales/tl/translation.json`; tests that assert old label text: `src/components/analysis/AnalysisWorkspace.test.tsx`, `src/components/analysis/WorkflowNavigator.test.tsx`, `src/components/layout/AppLayout.test.tsx`, `src/components/layout/Sidebar.test.tsx`, `src/components/SupervisorSchedule.test.tsx`, `src/pages/CurrentDatasetCache.test.tsx`, `src/pages/HomePageLearning.test.tsx`, `src/pages/NewAnalysisPage.test.tsx`, `src/pages/OptimizePage.test.tsx`, `src/pages/QueueSimulationPage.test.tsx`, `src/pages/ReportsPage.test.tsx`, `src/pages/ResultsPage.test.tsx`, `src/pages/SetupSemantics.test.tsx`, `src/routerDataRedirect.test.tsx` (list from a grep at step 0; re-grep now).
- Change: App. A.1 (24 keys, EN and TL), A.2 (including both cost-basis keys), A.3 every drafted key exactly as listed (typographic apostrophes kept), App. B W1-W17. After this step no lane edits a locale file.
- Write the JSON with a script that loads, sets the keys and dumps with the file's existing indentation and key order (new keys appended at the end of the file), so the diff contains only the intended lines. Check the diff line count equals the number of changed + added keys per file.
- Tests to update: only literal text assertions of the 24 changed keys (for example "Analysis results" → "Analysis Results", "Customers served" → "Customer Served", region names in `QueueSimulationPage.test.tsx:325-326, 697, 844, 1000`).
- Done when: `npx vitest run src/lib/translationKeys.test.ts src/lib/wordingPolicy.test.ts src/lib/headingText.test.ts` pass unchanged; full `npm test` passes with only the text-assertion edits; a script confirms every App. A key has the exact EN and TL value from the spec and that en/tl key sets are equal.

### Step 2 — Shared primitives and chart CSS

- Files (new unless noted): `src/components/ui/InfoTip.tsx` (edit), `src/components/ui/InfoTip.test.tsx` (edit), `src/components/ui/HoursChip.tsx`, `src/components/charts/RowChart.tsx`, `src/components/charts/RowChart.test.tsx`, `src/lib/chartScale.ts`, `src/lib/chartScale.test.ts`, `src/styles/charts.css`, `src/main.tsx` (one import line after `./styles/global.css`).
- InfoTip (spec §7.6): optional `ariaLabel` (full accessible name, used for drafted ⓘ names) and optional `label` (renders the dotted label as the trigger instead of ⓘ). Defaults unchanged; existing callers untouched.
- RowChart: SVG rows, one focusable group with `aria-label`, Arrow/Home/End, hover and tap select a row, an in-flow readout panel (the mockup tip's lines; `TooltipPopup` takes a single string), polite live region text supplied by the caller, `row.hl` highlight, axis from 0 with ticks from `chartScale`. It draws what the caller passes (marks, ranges, gaps); it computes nothing.
- `chartScale.ts`: `niceMax` and tick list (port of the mockup's helper), axis always starts at 0.
- `charts.css`: every class the spec needs, ported from `output/chart-redesign/index.html` and `output/ulit-mockup/index.html` styles, using only theme tokens (`.row-bg`, `.row.hl`, `.row.active`, `.m-est`, `.m-rec`, `.m-plan`, `.l-gap`, `.l-ci`, `.m-clip`, `.l-cap`, `.m-mc`, `.ribbon`, `.matrix` incl. `.closed` hatching and `.maxcol`, legend swatches, `.hours-chip`, `.tip-trigger`, `pointer: coarse` 44 px rules). After this step, later steps do not edit `charts.css` except as a coordinated, single-writer change.
- Tests: InfoTip `ariaLabel` sets the button name; `label` variant opens on hover, focus, click, closes on Escape (same assertions as the existing InfoTip tests); RowChart keyboard moves the active row and updates the live text; `niceMax` cases (0, 0.07, 1.4, 12).
- Done when: targeted tests, typecheck, lint pass; existing InfoTip, Tooltip and tooltipPlacement tests unchanged and green.

### Step 3 — Setup, Suggested Plans and Replay fixes (spec §4)

- Files: `src/components/analysis/SetupDataTemplates.tsx`, `src/styles/global.css` (owned by this step; later only step 11 edits it), `src/components/SupervisorSchedule.tsx`, `src/components/SupervisorSchedule.test.tsx`, `src/components/simulation/LiveSimulationPlayback.tsx`, `src/components/simulation/LiveSimulationPlayback.test.tsx`, `src/components/analysis/SetupDataTemplates.test.tsx`.
- 3a Field Guide (§4.1): class on the field-guide table; scoped no-break rule for its row headers. `global.css:5144` unchanged.
- 3b Break table spacing (§4.2): caption padding and right-edge room for `.supervisor-break-table` (desktop only).
- 3c Auto-name (§4.3): `nameTyped` flag; default name re-set on each successful check unless typed.
- 3d Replay (§4.4): `LiveSimulationPlayback.tsx:136` prints the time only.
- 3e Step bar (§4.5): first measure in the browser at 1280 and 375 (the footer's height, the table's last row position when scrolled). Apply bottom space / `scroll-margin-bottom` only if the measurement shows the overlap; otherwise report what was seen and stop 3e.
- Tests: SetupDataTemplates field `th` carries the class; Supervisor: check at 70% → name "Schedule at 70%", change limit to 75% and re-check → "Schedule at 75%"; type a name, re-check → typed name kept; clear it, re-check → default again; LiveSimulationPlayback: model name ("M/M/1" in the fixture) not in the eyebrow.
- Done when: tests pass; browser screenshots at 375/768/1280 show field names on one line with no page horizontal scroll, break table with the new spacing, and the last break row not under the step bar.

### Step 4 — Results tabs and wait by hour (spec §5.1, §5.2, §5.4)

- Files: `src/pages/ResultsPage.tsx`, `src/components/results/ResultsChartTabs.tsx` (new), `src/components/results/WaitByHourCard.tsx` (new), `src/lib/waitChart.ts` (new) + `src/lib/waitChart.test.ts`, `src/components/results/PlanChanges.tsx` (remove `PlanTable` only), `src/components/results/ResultsCharts.tsx` (remove `WaitByPeriodChart` only), `src/pages/ResultsPage.test.tsx`, `src/components/results/WaitByHourCard.test.tsx` (new).
- `waitChart.ts`: build rows for Today (from `ObservedWaitSummary`), separate Plan (from `SeparateComparison` + selected plan), shared Plan (from `scenarioRows`); shown lower = `max(0, wait_ci[0])`, `cut` flag when the shown lower is 0 (OD-1); highlighted index = max Estimated; nulls kept null.
- Tabs: roving tabindex, `.tabs/.tab` classes, `?chart=wait|level` via the page's existing `update()` helper (`ResultsPage.tsx:79-86`). Tab 2 is a placeholder slot filled in step 5 (until then the existing `BusyStrip` renders inside tab 2 unchanged).
- Tests: tab keyboard and URL; single-tab fallback; no plan → no Plan view switch and the no-plan prompt present (OD-4 default); Today view never renders Plan marks; Plan view never renders Recorded marks; separate fixture with lower −0.0239 h → prints 0, marker, legend entry and ⓘ (`charts.clip_text`), and the negative value appears nowhere; fixture with lower 0 → same note; fixture with lower > 0 → no note; shared fixture → no range element, EN text contains no "simulated"; values in tooltip = table alternative; Unavailable gap labelled.
- Done when: tests pass; old `ResultsPage.test.tsx:391` list assertion replaced by the new chart's accessible name and table alternative; browser check on analyses (a), (b), (c) in EN/TL, light/dark, 375/1280.

### Step 5 — Busy Level tab (spec §5.3)

- Files: `src/components/results/BusyLevelCard.tsx` (new) + test, `src/lib/busyLevel.ts` (new) + test, `src/components/results/ResultsChartTabs.tsx`, `src/components/results/BusyStrip.tsx` (delete), `src/pages/ResultsPage.tsx` (import swap), `src/pages/ResultsPage.test.tsx`.
- Depends on step 4 (same files). Keep the `?period=` sync and the plan-target warnings.
- Tests: every period prints word + `fmtPctDecimal`; 0.0019 → "0.19%"; legend lists only present levels; separate Current tap → cashier table; separate plan tap → `charts.level_plan_no_lanes`; shared tap → counter group (counters, workload, level), no cashier names; `level_take_plan_separate` omitted when a period is at or above target; ribbon wraps (CSS checked in the browser at 375).
- Done when: tests pass; `grep -r BusyStrip src` returns nothing; browser check as step 4.

### Step 6 — Hours chip, Combined Waiting Line legend, Wq/ρ tooltips (spec §7.1, §7.2, §7.6)

- Files: `src/lib/replay.ts`, `src/lib/replay.test.ts`, `src/components/queueSimulation/RunBar.tsx`, `src/components/queueSimulation/KeyResultsView.tsx`, `src/components/queueSimulation/ContinuousRun.tsx` (only the hours line `:146-152`), `src/pages/QueueSimulationPage.test.tsx`.
- `operatingHours()` separator → `' - '`; same for `ContinuousRun.tsx:146`. `HoursChip` at `RunBar.tsx:69` and `ContinuousRun.tsx:152`; text stays `simulation.operating_hours`.
- Legend (2 entries, breaks entry only with breaks); remove `simulation.chart_breaks_marked` from `KeyResultsView.tsx:37`.
- Tooltips: `InfoTip label` variant on "Wq (min)" and "ρ" at `KeyResultsView.tsx:92` and on "ρ" at `:114`.
- Tests: `operatingHours` returns "08:00 - 13:00" (new case); chip text "Operating hours: 08:00 - 13:00." EN and the TL sentence; legend 2 vs 1 entries; `chart_breaks_marked` text absent; tooltips open/close by hover, focus, click, Escape; `wordingPolicy.test.ts` still green (pinned sentence).
- Done when: tests pass; browser: chip and legend in light/dark; tooltip readable at 375 without page scroll.

### Step 7 — Key Results (separate + legacy per-period) and Longest Single Line table (spec §7.3, §7.4, §9 part)

- Files: `src/components/queueSimulation/KeyResultsView.tsx`, `src/components/queueSimulation/LongestLineTable.tsx` (new) + test, `src/lib/longestLine.ts` (new) + test, `src/components/queueSimulation/KeyResultsView.test.tsx` (new), `src/pages/QueueSimulationPage.test.tsx`.
- Depends on step 6 (same files).
- Cards: Average wait, Longest Single Line, no arrow; basis ⓘ only when bases differ and `charts.key_basis` is true (plan basis `continuous_day` and setup breaks present); closing alert with `count`; Customer Served pair at the top of More Results with Unavailable ⓘ on `per_period` sides; remove `per_period_totals_note` rendering; LegacyMore Plotly cards and the `Charts` import removed (table kept).
- Longest Single Line: Current from `SimDesOut` rows; plan from the chosen day's `SelectedDesPeriod.results`; staffed rule per spec §7.4. Verify the Current-run hatching rule against analysis (a)'s setup segments in the browser before relying on it; if `active_queue_ids` does not explain the missing lanes, show only lanes present in the rows and report.
- Tests: no "→" in cards; ⓘ presence matrix (per_period vs continuous_day, with/without breaks, per-date plan); alert absent at 0/null, `_one` at 1, `_other` at 2 (EN), TL output for 1, 2, 4 recorded for the owner (spec §14 plural risk); no `.plotly` element; matrix: row max over staffed lanes, null stays "Unavailable", hatched cells have the text alternative, ≤520 px headers via a width mock, roving keyboard.
- Done when: tests pass; updated assertions at `QueueSimulationPage.test.tsx:325-326, 697, 844, 1000` reflect the new card/More Results layout; browser on analyses (a) and (b) incl. the DatePicker day switch.

### Step 8 — Shared full-day run (spec §7.5)

- Files: `src/components/queueSimulation/ContinuousRun.tsx`, `src/components/queueSimulation/ContinuousRun.test.tsx` (new), `src/pages/QueueSimulationPage.test.tsx`.
- Depends on step 7 (shared test file) and step 6 (same component).
- Two headline cards with ranges; Customer Served into More Results; "Not served at closing" card unchanged (OD-2 default); "People waiting through the day" with y-axis ticks and clock x labels (closing line kept; its legend label waits for W9); "Average wait by period" as a `RowChart`; `continuous.by_period_hint` into details; no takeaways until W9; no per-hour longest line (BLOCKED, C4); older per-period section gets no Unavailable ⓘ until W6.
- Tests: 2 cards + kept closing card; ranges text unchanged from `rangeText`; y-axis tick labels 0..max integers; row chart rows = `by_period` length, null → gap; `QueueSimulationPage.test.tsx:1000` updated to the More Results location.
- Done when: tests pass; browser on analysis (c), 5 repeated days, day picker, light/dark, 375.

### Step 9 — Plan cost label: verify, then show (spec §6)

- Files: `src/lib/costBasis.ts` (new) + test, `src/api/types.ts` (optional `observation_days?: number`, `period_basis?: string` on `DatasetValidation`; type only), `src/components/results/PlanChanges.tsx`, `src/components/results/PlanChanges.test.tsx` (new).
- Depends on step 4 (PlanChanges edited there). Independent of steps 6-8.
- 9a Verify (no code): on analyses (a) and (b) read `GET /analyses/:id/workflow/comparison/separate` and the dataset; check `totals.total_cost_mean` equals the sum of `periods[].total_cost_mean` (to float tolerance), that (a)'s periods are one averaged day and its dataset has `observation_days`, and that (b)'s period labels are per-date with N distinct dates matching `data_dates`. Do the same check for the shared plan of analysis (c) against `comparisonTotals`. Record the numbers.
- 9b Implement `costBasis()` and the label placement only for the setups that passed 9a.
- 9c The keys exist from step 1 (W1/W2 drafts). Show the label only for setups that passed 9a. Also W17: separate lines use `results.suggests_wait_separate` in `CalculatedResult`; shared lines keep `results.suggests_wait`.
- Tests: representative day → days from `observation_days`; per_date → distinct date tokens + `data_dates`; aggregate → null; missing `observation_days` → null.
- Done when: 9a numbers recorded VERIFIED (or the setup reported BLOCKED); tests pass; with W1/W2 absent the screen is unchanged.

### Step 10 — Many variations (spec §8)

- Files: `src/components/queueSimulation/ChecksView.tsx`, `src/components/queueSimulation/ManyVariationsChart.tsx` (new) + test, `src/lib/manyVariations.ts` (new) + test, `src/pages/QueueSimulationPage.test.tsx`.
- Depends on step 8 (shared test file).
- ⓘ text from stored row parameters only; chart (highest-risk lane per period, shared single row, cap line, axis to `niceMax`); tap → all lanes for that period (separate); `fmtPctDecimal` in the separate table and `McTable`; remove `McTable`'s Plotly pair and the `Charts` import.
- Tests: ⓘ filled from rows with threshold 0.85 while the form shows 0.75 (form change does not change the ⓘ); rows with two different thresholds → no ⓘ; shared rows → no lane label; tie rule; 0.0019 → "0.19%", CI "0% – 0.19%"; no `.plotly` element; validation tables unchanged (snapshot of their cells).
- Done when: tests pass; browser on (a) plan, (a) Current, (c) older shared plan section: stored threshold printed (85% for a plan target 85% run; 75% for an old shared run if one exists).

### Step 11 — Remove Plotly charts file (spec §9)

- Files: `src/components/charts/Charts.tsx` (delete), `src/components/charts/Charts.test.tsx` (delete), `src/test/setup.ts` (remove the `react-plotly.js` mock if nothing else needs it), `src/styles/global.css` (`.plotly-wrap` rules `:724-732` if unused).
- Depends on steps 7 and 10 (last importers) and step 3 (`global.css` owner).
- Before deleting: `grep -rn "charts/Charts\|react-plotly\|plotly.js\|plotly-wrap" src` must show only the files being removed. `package.json` unchanged (OD-3).
- Done when: grep clean; `npm test`, typecheck, lint, build pass; JS bundle sizes compared with step 0 and recorded (Plotly chunk expected to disappear: INFERRED until measured).

### Step 12 — Named-staff interval note (spec §7.7; OD-1 decided, spec §16)

- Files: `src/components/simulation/NamedReplicationTable.tsx`, `src/components/simulation/NamedReplicationTable.test.tsx`.
- Display clamp: print `max(0, ci_lower)`; when the printed lower is 0, append `charts.clip_legend` + ⓘ (`charts.info_clip_name` / `charts.clip_text`). Tests with `src/test/fixtures/sharedNamed.json` (do not regenerate the fixture) and an in-test copy with a negative lower bound.
- Done when: both fixtures render 0 with the note; a positive lower bound has no note.

### Step 13 — Final verification and report

- Gates in `frontend/`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`. Backend pytest only if any backend file changed (`git diff --stat -- backend tests` must be empty; if not, stop: out of scope).
- `git diff --stat` file list equals the union of the steps' file lists plus the two docs; no other file.
- Browser walk (built-in browser, local stack, analyses a/b/c): Results both tabs and both views, Key Results, Longest Single Line, Replay header, Checks Many variations, Suggested Plans review/confirm, Field Guide; at 375, 768, 1280; light and dark; EN and TL; keyboard-only pass; `document.documentElement.scrollWidth <= innerWidth` on every screen at 375. Screenshots named `<screen>-<theme>-<width>-<lang>.png`.
- Pinned wording: `wordingPolicy.test.ts` green, record file untouched (`git diff --quiet docs/wording`).
- Report (AGENTS.md §11): files changed, gates with counts, bundle sizes before/after, screenshots, drafts awaiting owner review (App. A drafts, App. B W1-W17), OD-3 follow-up, BLOCKED items (spec §12), anything NOT TESTED (physical touch, other engines, PostgreSQL, production).

## Order and parallel lanes

```
Step 0 ─► Step 1 ─► Step 2 ─┬─► Lane X: Step 3 ───────────────────────────────┐
                            ├─► Lane Y: Step 4 ─► Step 5 ─► Step 9 ─────────────┤
                            └─► Lane Z: Step 6 ─► Step 7 ─► Step 8 ─► Step 10 ──┴─► Step 11 ─► Step 13
                                                         (Step 12: any time after Step 2, own files)
```

- Steps 0, 1, 2 are serial (baseline, then the shared locale catalogues and primitives every lane uses).
- Lanes X, Y and Z can run in parallel: their file sets are disjoint.
  - X owns `global.css`, `SupervisorSchedule*`, `LiveSimulationPlayback*`, `SetupDataTemplates*`.
  - Y owns `ResultsPage*`, `components/results/*`, `lib/waitChart*`, `lib/busyLevel*`, `lib/costBasis*`, `api/types.ts`.
  - Z owns `components/queueSimulation/*`, `lib/replay*`, `lib/longestLine*`, `lib/manyVariations*`, `QueueSimulationPage.test.tsx`.
- Inside a lane, steps are serial (shared files).
- Step 9b/9c also needs the owner's W1/W2 TL text to show the label; 9a can run as soon as step 4 is done.
- Step 12 owns only `NamedReplicationTable*` and can run in parallel with any lane.
- `charts.css` and the locale files are single-writer resources after steps 1-2: a lane that needs a change there pauses and hands the change to one writer.
- Step 11 waits for X (global.css), Z (last Plotly importers) and must run alone.

Step count: 14 (steps 0-13). OD-1..OD-6 and W1-W17 were decided/drafted by the parent session under owner delegation (spec §16), so no step waits for wording; steps 9b/9c still depend on the 9a check.

## Gates

- Per step: the listed targeted tests, `npm run typecheck`, `npm run lint`.
- Final (step 13): `npm test`, `npm run typecheck`, `npm run lint`, `npm run build` in `frontend/`.
- Backend: `python -m pytest tests/ -x --tb=short` only if a backend file changes. None should; a backend diff stops the build.
- A failed or skipped gate is reported as such, with the reason. No gate is bypassed to finish a step.
