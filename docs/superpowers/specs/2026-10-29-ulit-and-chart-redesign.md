# Ulit wording + chart redesign (combined frontend build)

Date: 2026-10-29. Status: PROPOSED; open questions OD-1..OD-6 and wording slots W1-W17 DECIDED/DRAFTED by the parent session under owner delegation 2026-10-29 (§16). Implementation of plan steps 0-2 started 2026-10-29. Branch `feat/ulit-chart-redesign`, worktree `.claude/worktrees/ulit-chart-build` (main `e2dbe5d5` + engine fixes `8b0f2eab`, `6d17ab9a`, `344ac9ce` + docs commits).
Plan: `docs/superpowers/plans/2026-10-29-ulit-and-chart-redesign.md`.

Scope class: frontend only. Presentation, labels, layout, chart drawing and progressive disclosure. No backend file, formula, model selection, simulation, optimizer, Monte Carlo method, API request/response shape, CSRF, docker or route change. One additive, optional frontend query parameter (`?chart=` on `/results`, §5.1) is proposed with a justification.

## 0. Sources and how they were read

| Source | What it gives | Label |
|---|---|---|
| `output/ulit-mockup/index.html` (main checkout, untracked) | Owner's ulit.pdf change list, every "Decided" line, 31-row mapping table (keys, file:line, status) | APPROVED SPECIFICATION (owner decisions 2026-10-28) |
| `output/chart-redesign/index.html` (main checkout, untracked) | Final new design, 12 numbered changes, "What changed" lists, `DR` draft wording table (EN, TL, fact source, reused key) | APPROVED SPECIFICATION for the design (owner 2026-10-28/29); wording = drafts (decision H) |
| `scratchpad/ulit/ulit.txt` | ulit.pdf text (10 pages, text only; screenshots not extracted) | REPORTED reference only (decision A: no wording-lock record) |
| Memory `novaq-ulit-chart-redesign.md`, `owner-writes-wording.md` | Decisions #1-#8, 4a-4c, #5, #6; owner writes wording | REPORTED (owner decisions relayed by the parent session) |
| Engine specs 2026-10-29 (separate wait floor, shared wait floor, shared MC threshold) | OD-W1, OD-S1..S3, OD-T1..T4 | APPROVED SPECIFICATION |
| `docs/superpowers/specs/2026-10-27-local-wording-and-english-headings.md`, `lib/headingText.ts:4`, `lib/wordingPolicy.test.ts` | Headings stay English; 200 pinned records | APPROVED SPECIFICATION + VERIFIED (code) |
| `docs/superpowers/specs/2026-10-09-compact-workflow-ux-redesign.md` D21 (line 43), D30 (line 51) | Plan section and simulation-page layout rules this build touches | APPROVED SPECIFICATION |
| Repository source at this worktree | Every file:line below | VERIFIED (read this session) unless labelled otherwise |

The mockups' numbers come from local runs on the NovaMart xlsx (chart mockup: analysis 1, plan "Schedule at 85%", 2026-10-28) and on a synthetic fixture (ulit mockup). They are REPORTED by those files and are used here only as examples. No number from a mockup goes into code or locale files.

## 1. Owner decisions this spec implements (traceability)

All decisions are closed (2026-10-28/29). "Decided by" is the owner unless noted.

| ID | Decision (short) | Spec section |
|---|---|---|
| A1 | ~30 label changes EN+TL, verbatim (24 keys + 2 tooltip texts) | §3, App. A |
| A2 | "Customer Served" via `simulation.served_customers` in all 5 places; `live_served`/`sep_served` unchanged; the 26 listed sentences unchanged | §3.2 |
| A3 | Headings stay English (`headingText`) | §3.1 |
| A4 | Field Guide: widen Field column (cause `global.css:5144`) | §4.1 |
| A5 | Break Changes to Review: padded caption, room on the right; 375 px cards unchanged | §4.2 |
| A6 | Operating hours chip with clock icon, 24-hour `HH:MM - HH:MM`; pinned `simulation.operating_hours` unchanged | §7.1 |
| A7 | Combined Waiting Line 2-entry legend; remove `simulation.chart_breaks_marked` under it | §7.2 |
| A8 | Wq and ρ tooltips (exact owner text) | §7.6 |
| A9 | No new language control | §3.3 (no change) |
| A10 | New Analysis form labels | App. A |
| A11 | No new wording-lock record or test | §10 |
| B1 | Results tabs: "What the plan changes" first, "Your day, by Busy Level" second; app tab pattern | §5.1 |
| B2 | Wait by hour: Today = Recorded vs Estimated (view name = owner's "Recorded vs Estimated Wait, by period"); Plan = Estimated vs Suggested plan; recorded never next to plan | §5.2 |
| B3 | Separate plan ranges drawn cut at 0 with marker + ⓘ; marker kept for old saved plans (OD-W1) | §5.2.3 |
| B4 | Busy Level grid prints time, level word, %; wraps on phones | §5.3 |
| B5 | Key Results: 2 cards; closing alert only when plan `in_system_at_close` > 0 (`_one`/`_other`); Customer Served into More Results; "Unavailable" ⓘ replaces `per_period_totals_note` use; basis ⓘ where the arrow was, only when bases differ | §7.3 |
| B6 | Longest Single Line hour × cashier table (separate), "1–5" columns at ≤520 px + key line | §7.4 |
| B7 | Many variations on Checks: ⓘ with stored trials/threshold/cap; highest-risk-per-hour chart vs cap line | §8 |
| B8 | Percentages with `fmtPctDecimal` (0.19%, never 0%) | §8, §5.3 |
| B9 | Remove old More Results Plotly charts (both line types) and the 2 Plotly charts under Many variations | §9 |
| B10 | Progressive disclosure: visible = title, chart, legend, one takeaway, view switch, alerts; rest behind ⓘ or collapsed "details" | §2.3 |
| B11 | Remove unused `Charts.tsx:243-436` and their tests | §9 |
| C1 | Shared "What the plan changes": both sides calculated (M/G/c); no range, no cut marker, no "simulated" wording | §5.2.4 |
| C2 | Shared Busy Level tap shows the counter group | §5.3 |
| C3 | Shared Key Results: full-day run is the headline; no basis ⓘ; keep lowest–highest ranges; period-by-period "Unavailable" text points to the full-day run | §7.5 |
| C4 | Shared longest line: whole-day value only; per-hour BLOCKED (no API field) | §7.5, §12 |
| C5 | Shared Many variations: one row per hour, no cashier label; ⓘ uses the STORED threshold | §8.3 |
| C6 | Shared full-day charts in the new design: "People waiting through the day" (with y-axis) and "Average wait by period" | §7.5 |
| D1 (4a) | Plan auto-name follows the busy limit unless the user typed a name (`SupervisorSchedule.tsx:98`) | §4.3 |
| D2 (4b) | Replay shows time only, no model name (`LiveSimulationPlayback.tsx:136`) | §4.4 |
| D3 (4c) | Step bar must not cover the Break Changes table | §4.5 |
| E (#5) | Plan cost label by day basis, verified against `workflow.py` and per-date labels in both setups | §6 |
| F (OD-S3) | "Range cut at 0" note on the named-staff interval text (`NamedReplicationTable.tsx:96-104`) reusing the range-cut ⓘ text | §7.7 (conflict resolved by OD-1, §16) |
| G (#6) | No ranges where the API has none | §2.4 |
| H | Drafts go in as drafted (marked draft in App. A); decision-A updates applied to drafts; every string EN+TL, symmetric keys | §3, App. A |

## 2. Cross-cutting rules

### 2.1 Data kinds and marks (AGENTS.md §7)

Each kind has its own mark and legend entry; kinds are never one unlabelled series.

| Kind | Where it comes from | Mark | Token (light + dark already defined in `theme.css`) |
|---|---|---|---|
| Recorded (current measurement) | `ObservedWaitPeriod.observed_wait` (`api/types.ts:680`) | filled diamond | `--color-text-primary` |
| Estimated (analytical model, today's staffing) | `ObservedWaitPeriod.modeled_wait` (`:678`); `SeparateCurrentPeriod.wait_mean` (`:612`); `OptimizationOut.Wq_current` (`:56`) | hollow circle | stroke `--color-data-current` |
| Suggested plan, simulated (separate lines, DES replications) | `SeparatePlanPeriod.wait_mean` / `wait_ci` (`:642-643`), `wait_basis_kind = 'simulation'` (`:667`) | filled circle + range line | `--color-data-optimized` |
| Suggested plan, calculated (shared lines, M/G/c) | `OptimizationOut.Wq_optimal` (`:57`) | filled circle, no range | `--color-data-optimized` + legend chip `results.source_estimate` |
| Monte Carlo estimate | `SimMcOut.failure_rate`, `failure_rate_ci_lower/upper` (`:533, :540-541`) | filled circle + range line + dashed cap line | `--color-data-optimized`; cap `--color-danger-fg` |
| Unavailable / not staffed | null value; inactive lane | visible gap labelled `results.unavailable`; hatched cell labelled `simulation.state_closed` | `--color-unavailable-*`, `--color-bg-subtle` |
| Stale | `plan.stale` / not `usable` | existing `results.plan_not_current` alert; plan view switch not offered | `--color-stale-*` |

No smoothing, interpolation, trend lines or zero-filling. A null value is a labelled gap. Axes start at 0. Every chart value equals the tooltip and table value (same formatter).

### 2.2 Formatting

- Waits: `minutes()` (`lib/results.ts:152`) then `fmtDecimal(v, 1)` + `results.min`, as the app shows waits today (`PlanChanges.tsx:47`, `ResultsCharts.tsx:43`). A negative stored lower bound is shown as 0 (display clamp, OD-1, §16); the stored negative value is not printed.
- Percentages (utilization, failure rate, ranges, cap, target): `fmtPctDecimal` (`lib/format.ts:42`). `fmtPct` and `fmtFrCi` (integer rounding, `format.ts:53-69`) are no longer used on the Many variations surfaces. The functions themselves are not changed (other consumers keep them).
- Busy levels: `utilizationBand` with its 1e-9 tolerance (`lib/utilization.ts`), via `busyLevel`/`dayStrip` (`lib/results.ts:66-83`) for today and `band()` as in `PlanChanges.tsx:19-22` for plans.

### 2.3 Progressive disclosure (B10)

Visible on every chart card: heading (English, `headingText`), one takeaway sentence, view switch (if any), legend, chart, alerts. Behind an ⓘ (`components/ui/InfoTip.tsx`) or inside a collapsed `<details>` whose summary is `simulation.check_details` ("details"): run chips (records, model, runs, seed, breaks), axis note, the table alternative ("Show as a table"), BLOCKED notes. This is how the mockup is built (`chart-redesign/index.html`, cards s1-s5).

### 2.4 Not shown (G, #6)

No range is drawn or printed where the API returns none: Key Results numbers of the per-period and selected-plan DES (`RunSummary` has one value per run, `api/types.ts:363-371`), the day-total plan cost, per-cashier plan utilisation (not returned, §12). Ranges are shown only for: separate plan wait (`wait_ci`), Monte Carlo failure rate (`failure_rate_ci_*`), shared full-day run lowest–highest (`MetricSummary.min/max`, `api/continuous.ts:54-62`).

### 2.5 Accessibility and layout (hard constraints)

- 44 px targets: tabs, view-switch buttons, ribbon buttons (min-height 64 px), ⓘ (`.info-tip-button` is 44 px under `pointer: coarse`, `global.css:3706`), matrix cells (34 px tall in the mockup: raised to 44 px under `pointer: coarse`).
- Keyboard: tabs use the roving-tabindex pattern of `SupervisorSchedule.tsx:165-175` (Arrow/Home/End) with the `.tabs`/`.tab` classes of `QuickCalculatorPage.tsx:118-124`. Row charts are one focusable group: Up/Down/Left/Right/Home/End move the active row, its values go to a polite live region and to a visible readout panel under the chart (implementation note 2026-10-29: the existing `TooltipPopup` takes one string and anchors to one trigger element, so the mockup's floating multi-line tip is rendered as an in-flow readout; same lines, works by touch and at 375 px). Matrix: roving tabindex over cells with arrow keys.
- Screen readers: every chart has an accessible name, a live-region reading of the active row, and a table alternative with the same values. Colour is never the only signal (level words printed; marks differ in shape; hatched + text for closed lanes).
- Contrast AA in both themes; only existing tokens; no new token unless a gap is found during build (then added with its dark value in the same change).
- 375 px: no page horizontal scroll. Wide tables scroll inside their own `.table-scroll` region (as today). Row-chart label column narrows below 420 px (mockup: 82 px).
- `prefers-reduced-motion`: no chart animation is added; tooltip appear animation is the existing one.

### 2.6 Draft wording placement (H)

Draft texts from the chart mockup's `DR` table are placed as drafted, with two mechanical changes only, both listed per key in App. A:
1. Interpolation syntax `{name}` → i18next `{{name}}`.
2. Where a draft hard-codes a NovaMart run value (for example "1,600 customer records over 14 dates", "from 5 runs", "from 2,000 trials", "(Parallel M/G/1)", "base seed 42"), the value becomes a named variable filled from the API field the draft's own fact source names. The words around it are unchanged. Literal NovaMart numbers in a locale string would be false for every other store.

A draft is never shown in a case where its facts are false (for example "simulated" on a calculated shared plan). Those cases use the case-specific drafts of App. B (W1-W17, drafted under owner delegation, §16). Wherever this spec says a slot is "omitted until written", read: use the App. B draft for that slot. A case that no draft covers is omitted, never filled with a placeholder.

## 3. Wording and labels (A1-A3, A10, H)

### 3.1 Headings

Built-in headings keep `lang="en"` and `headingText(t, key)` (`lib/headingText.ts:4`). For a heading key the owner's Filipino still goes into `tl/translation.json`, because the same key is used in places that are not headings (screen-reader labels, sidebar, step bar). The ulit mockup lists those places per key (mapping table, rows 1, 5, 6, 12, 13, 16, 20, 22, 23, 25, 27). Tab labels on Results are headings (English in both languages, as in the mockup: `lang="en"` on each tab).

### 3.2 "Customer Served"

`simulation.served_customers` EN "Customer Served", TL "Nagsilbi sa Customer". Its five uses (VERIFIED): `KeyResultsView.tsx:69, 167`; `ContinuousRun.tsx:247, 341, 452`. After this build `KeyResultsView.tsx:167` (card) moves into More Results (§7.3); the key is the same. Unchanged on purpose: `simulation.live_served` (`LiveSimulationPlayback.tsx:121`), `simulation.sep_served` (`SeparateSimulationPlayback.tsx:167`, `KeyResultsView.tsx:92`), and the 26 sentence keys listed in the ulit mockup ("Left alone on purpose").

### 3.3 Language control

No change (A9). `AccountMenu.tsx:101-115` stays.

### 3.4 Pinned records (VERIFIED this session)

Checked every key this build changes against `docs/wording/2026-10-27-local-wording-application.json` (200 records). Pinned among touched keys:
- `simulation.operating_hours` (en, tl): text unchanged; only the `{{hours}}` value format changes (§7.1). Also asserted in `wordingPolicy.test.ts:35`.
- `simulation.per_period_totals_note` (en, tl): the key and its text stay in both catalogues unchanged. The build only stops rendering it in `KeyResultsView.tsx:160-168` (B5). It may become unused; it must not be deleted (the policy test reads the catalogue).
- `results.key_results` (en, tl): not changed (only reused as an existing accessible name).
None of the 24 changed label keys is pinned. Neither the record nor the test is edited (A11).

## 4. Data and Setup, Suggested Plans, Replay fixes

### 4.1 Field Guide column (A4)

- Cause (VERIFIED): `global.css:5144` `.app-shell :is(p, dd, td, th, label, .page-title, .card-title) { overflow-wrap: anywhere; }` breaks `th[scope=row]` field names mid-word in `SetupDataTemplates.tsx:104-121`.
- Change: a scoped rule for the field-guide table only (new class on the table, e.g. `.field-guide-table th[scope='row'] { overflow-wrap: normal; white-space: nowrap; }`). The global rule at 5144 is not changed (it protects 375 px everywhere else). On phones the table scrolls inside its existing `.table-scroll` region (owner decision: "the table scrolls sideways inside its own box").
- Done when: at 375/768/1024 every field name (`arrival_time`, `service_start`, ...) is on one line; no page horizontal scroll.

### 4.2 Break Changes to Review spacing (A5)

`SupervisorSchedule.tsx:272-280`, CSS `global.css:5455-5481`. Padded caption and extra room on the table's right edge (desktop table only); the ≤640 px card view (`.supervisor-break-cards`) unchanged.

### 4.3 Plan auto-name (D1, 4a)

- Today (VERIFIED, `SupervisorSchedule.tsx:98`): `setName(prev => prev || t('supervisor.default_name', { percent }))` keeps the first default, so a re-check at a new limit keeps the old "Schedule at 70%".
- Change: track whether the user typed in `#sup-name` (`onChange` at `:333` sets a `nameTyped` flag; clearing the field to empty resets it). On each successful check, if not typed, set the name to `supervisor.default_name` with the checked percent. A typed name is never overwritten.
- No API change: the name is sent as today in `save()`.

### 4.4 Replay time only (D2, 4b)

`LiveSimulationPlayback.tsx:136` `{segment.time} · {segment.selected_model ?? '—'}` becomes `{segment.time}`. The model name stays available elsewhere (Results reference view). Test fixture `LiveSimulationPlayback.test.tsx:29` keeps `selected_model`; an assertion that the model name is not printed is added.

### 4.5 Step bar over the break table (D3, 4c)

- Step bar = `WorkflowNavigator` (`components/analysis/WorkflowNavigator.tsx:16`, `nav.workflow-footer`), `position: sticky; bottom: 12px; z-index: 20` (`global.css:3048-3061`).
- Exact overlap: UNKNOWN until measured in the browser (the screenshot evidence is in the PDF, which was not extracted). INFERRED cause: the sticky footer overlays the last rows of `.supervisor-break-table` when the review panel is scrolled to the table.
- Change (after measuring): give the Suggested Plans page enough bottom space and `scroll-margin-bottom` equal to the footer's measured height so the table's last row and the Continue button are never under the footer; the footer itself is not moved or restyled. If measurement shows a different cause, the step stops and reports it.

## 5. Analysis Results (`/results`)

### 5.1 Tabs (B1)

- Component: new `ResultsChartTabs` in `components/results/`, placed where `BusyStrip` and `WaitByPeriodChart` render today (`ResultsPage.tsx:156, 161`). The other sections stay in place and unchanged: Key Results (`:144-153`), `ResultsSummary` (`:154`), Arrivals and Workload charts (`:157-160`), the plan Switcher / CalculatedResult / cost line from `PlanChanges` (§5.4).
- Tabs: "What the plan changes" (`results.plan_changes`, heading text, English) first; "Your day, by Busy Level" (`results.day_by_level`) second. Tablist accessible name `charts.tabs_label` (draft). One panel shows one card.
- When a tab has nothing to show: tab 1 needs either recorded waits (`observed.data.available`, today's condition at `ResultsPage.tsx:161`) or a usable selected plan; tab 2 needs more than one period (today's condition at `:156`). If only one tab has content, it renders as a plain card without a tablist. If neither has content, nothing renders (as today).
- URL (additive, optional): `?chart=wait|level`. Justification: Results already keeps its view state in the query string (`file`, `period`, `line`, `view`; `ResultsPage.tsx:79-92`) with `replace: true`; reload and Back return to the same tab; Help or "Check in simulation" return links can open a tab. Absent or invalid → first available tab. No route, no backend change.
- D21 fit: D21 says the plan comparison appears only once a plan is selected. Kept for the Plan view: the Plan view switch is offered only when a usable plan is selected; with no plan, tab 1 shows the Today view and the existing "no plan" prompt (`PlanChanges.tsx:191-203`, Switcher + link) below the chart. The tab title "What the plan changes" then shows a Today-only view: INFERRED acceptable because the owner named tab 1 this way; listed as OD-4 (confirm).
- Correction (review K-UC-2, 2026-10-29): the prompt is placed under the wait chart only while tab 1 is the open tab (`chartTabs()` in `ResultsChartTabs.tsx`, read by `ResultsPage.tsx`); with `?chart=level` and no plan selected, `PlanChanges` shows its own no-plan card, so the prompt never disappears and is never shown twice.

### 5.2 Wait by hour (tab 1) (B2, B3, C1)

Card heading `results.plan_changes`. View switch (`role="group"`, name `charts.view_group`): view 1 label = `results.wait_chart` (owner's "Recorded vs Estimated Wait, by period"), view 2 label = `charts.wait_view_plan` (draft). View state is local (not in the URL).

Chart form: one SVG row per period (dot plot). Why not a line chart: the reader looks up an hour ("which hour needs help"), not a trend; why not bars: two or three kinds per hour with a range read better as marks on one axis (mockup change 2). Rows: time label; counters under it ("5 counters" today; "5 → 5 counters" in plan view). Highlighted row (`.row.hl`) = period with the highest Estimated wait, which is the takeaway's hour.

#### 5.2.1 Today view (both line types)

| Field | Source | Notes |
|---|---|---|
| time, Recorded, Estimated, flagged | `ObservedWaitSummary.periods[]` (`api/types.ts:675-682`) from `getObservedWait` (`api/workflow.ts:259`), only when `available` and `dataset_id` matches (as `ResultsPage.tsx:161`) | Recorded hours→minutes; Estimated = `modeled_wait` |
| counters | `/current` rows: `finiteNumber(row.c)` summed per period for separate (active lanes) or the row's `c` for shared | INFERRED mapping; plan step verifies against `SeparateCurrentPeriod.active_lanes` |

- Marks: Estimated hollow circle, Recorded diamond, dotted gap line between them. `flagged` periods keep the existing text `current.observed_flagged` in the tooltip and the table alternative (not a chart colour).
- Takeaway `charts.wait_take_today` (draft): `{{time}}`, `{{est}}`, `{{rec}}` of the highlighted row.
- Details: `charts.wait_chip_recorded` (records = `DatasetOut.row_count` `:117`; days/first/last = §6.2 sources), `charts.wait_chip_estimate_separate` with `{{model}}` = `AnalysisCurrentOut.selected_model` (`:242`) (separate only; shared variant = owner slot W5), `charts.wait_axis_note` (only when every period label is a 60-minute `HH:MM-HH:MM` span; otherwise omitted, slot W16), table alternative `charts.show_table`.
- Aggregate uploads (no recorded waits): Today view is not offered; if a plan exists, tab 1 opens on the Plan view; otherwise tab 1 is absent (same as today: no wait chart for aggregate files).

#### 5.2.2 Plan view, separate lines

| Field | Source |
|---|---|
| Estimated (today's staffing, analytical) | `SeparateCurrentPeriod.wait_mean` (`:612`), `comparison.current.periods[]` |
| Suggested plan (simulated) | `SeparatePlanPeriod.wait_mean` (`:642`) of the selected plan (`useSelectedPlan.ts:37`) |
| 95% range | `SeparatePlanPeriod.wait_ci` (`:643`) |
| counters now → plan | `SeparateCurrentPeriod.active_lanes.length`, `SeparatePlanPeriod.optimal_active_lanes` (as `PlanChanges.tsx:175-176`) |
| runs, seed, target | `SeparatePlanComparison.replications`, `base_seed`, `target` (`:662-665`) |

- Recorded is never drawn in this view (B2).
- Legend: Estimated + `results.source_estimate` chip; `charts.wait_legend_plan_simulated`; `charts.range_label` with ⓘ (`charts.info_range_name` / `charts.range_wait`, `{{runs}}`); cut marker entry (§5.2.3) only if any row is cut.
- Takeaway `charts.wait_take_plan_separate` (draft).
- Details: `charts.wait_chip_estimate_separate`, `charts.wait_chip_plan_simulated` (`{{runs}}`, `{{seed}}`), `simulation.plan_target` + `fmtPctDecimal(target)`, table alternative (Time, Counters, Estimated, Suggested plan, 95% range).

#### 5.2.3 Range cut at 0 (B3)

- Display clamp (OD-1, DECIDED by parent under owner delegation, §16): the range is drawn, printed in the tooltip and printed in the table alternative from `max(0, lower)` to `upper`. Whenever the shown lower bound is 0, the row gets the small marker at the axis origin (`.m-clip`), the legend gets `charts.clip_legend` with ⓘ (`charts.info_clip_name` / `charts.clip_text`, W15 text), and the tooltip adds `charts.clip_legend`. The stored value is not changed and not shown when negative. The mockup's "API lower value" tooltip line (`clip.tip`) is dropped.
- After `8b0f2eab` new separate plans return lower ≥ 0 (engine floor). Saved v4/v5 plans keep negative lower bounds (OD-W1, no version bump), so they are clamped on screen; new plans already return 0 where the engine floored them. Both show the same note (VERIFIED floor/version facts: `docs/superpowers/specs/2026-10-29-separate-wait-interval-floor.md:50-55`).
- `wait_ci` null or a null side → no range drawn for that row; tooltip says `results.unavailable` for the range.

#### 5.2.4 Plan view, shared lines (C1)

| Field | Source |
|---|---|
| Estimated now | `OptimizationOut.Wq_current` (`:56`) from `scenarioRows(scenario)` (`useSelectedPlan.ts:7-11`) |
| Suggested plan (calculated) | `OptimizationOut.Wq_optimal` (`:57`) |
| stability | `current_stable`, `optimized_stable` (`:72-73`); unstable side → no mark, row text `results.cant_keep_up_wait` |
| counters | `c_current`, `c_optimal` (`:52-53`) |

- No range, no cut marker, no "simulated" wording. Legend: Estimated + `results.source_estimate`; Suggested plan = `simulation.run_suggested` + chip `results.source_estimate` (existing keys, both calculated).
- Takeaway: `charts.wait_take_plan_separate` says "simulated" and must not be used; shared takeaway = owner slot W4 (omitted until written).

### 5.3 Busy Level (tab 2) (B4, B8, C2)

Card heading `results.day_by_level`. View switch Current / Suggested plan (`simulation.run_current` / `simulation.run_suggested`); Suggested plan offered only with a usable plan.

| View | Separate lines | Shared lines |
|---|---|---|
| Current | `dayStrip(rows)` (`lib/results.ts:66-83`): busiest line's `rho` + worst level per period (as today's strip) | same function: the one line's `rho`/level |
| Suggested plan | `SeparatePlanPeriod.peak_util` (`:641`) with `band(…, null)` | `OptimizationOut.rho_optimal` + `optimized_stable` with `band()` |

- Grid: one button per period printing time, level word (`results.level.*`), and `fmtPctDecimal(rho)`; CSS grid `repeat(auto-fill, minmax(98px, 1fr))` wraps at 375 px (mockup `.ribbon`). `aria-pressed` on the chosen period; selecting keeps today's URL sync (`onPeriod` → `?period=`, `ResultsPage.tsx:156`), so `ResultsSummary` filters as it does now.
- Legend: only the levels present, word + range (`results.range.*`).
- Alerts stay visible: the plan-target warnings of `periodWarnings` (`BusyStrip.tsx:53-65`, `lib/results.ts:113`). They are computed from today's rows, so they are shown under the Current grid only, never under the Suggested-plan grid (review K-UC-4, 2026-10-29).
- Tap detail:
  - separate, Current: per-cashier table for that period from `/current` rows (Queue `simulation.sep_lane`, Workload `results.col_workload`, Busy level `results.col_level`).
  - separate, Suggested plan: `charts.level_plan_no_lanes` (draft) — per-cashier plan utilisation is BLOCKED (§12).
  - shared (C2): the counter group for that period: Counters (`results.col_counters`), Workload, Busy level (Current from `/current` row; plan from `c_optimal`, `rho_optimal`). No cashier names.
- Takeaways: `charts.level_take_today`, `charts.level_take_plan_separate` (drafts). `level_take_plan_separate` is true only when the peak is below the target; when any period is at or above the target the takeaway is omitted (slot W10). Shared variants of both takeaways: slot W8.
- Details: `results.source_estimate` chip (Current), `charts.level_chip_plan_simulated` (`{{runs}}`, separate plan) or `results.source_estimate` (shared plan), `results.levels_note` + `results.strip_separate_note` (separate only), separate-plan BLOCKED note in plain text (no API field) — wording of that note: the mockup's BLOCKED line is developer text and is not shipped; only `charts.level_plan_no_lanes` is shown.
- Replaces `BusyStrip.tsx` (colour-only strip; its `showNumbers` table branch has no other caller, VERIFIED: only `ResultsPage.tsx:156` imports it).

### 5.4 What stays from PlanChanges

`PlanChanges.tsx` keeps: `CalculatedResult` card (`:74-108`), Switcher (`:110-138`), `plan_not_current` alerts (`:212-221, :254-260`), the no-plan prompt (`:191-203`), cost line (`:241-245, :280-281`, label changed by §6). Removed: `PlanTable` (`:40-71`) — its counters, wait arrow and level arrow are now in tabs 1 and 2 (mockup change 2: "replaces the plan table's '11.4 min → 0.8 min' arrow"). The per-row `results.above_plan_target` flag moves to the Busy Level alert list (already there, `BusyStrip.tsx:60`).

OD-5 DECIDED (§16): `CalculatedResult`'s line stays, but must name both kinds. Today `results.suggests_wait` reads "Estimated wait (average of the periods): {{now}} → {{plan}} min." (VERIFIED), which calls the separate plan's simulated mean "Estimated". Shared lines keep `results.suggests_wait` (both sides are calculated, so it is true). Separate lines use the new draft `results.suggests_wait_separate` (W17), built from existing words (`results.source_estimate`, `simulation.run_suggested`, "simulated").

## 6. Plan cost label (#5, decision E)

### 6.1 Rule

| Setup (`QueueSetup.event_period_basis`, `api/types.ts:212`) | Label | Placement |
|---|---|---|
| `representative_day` | EN "per average day (from {{days}} days of data)" — owner's words | after the plan cost in the cost line (`PlanChanges.tsx:241-245, 280-281`) and in `results.suggests_cost` context (`:100`) |
| `per_date` | EN "total for {{days}} days ({{first}} – {{last}})" — owner's words | same |
| absent (aggregate upload) | no label (today's text) | — |

TL for both: drafted by the parent session under owner delegation (W1/W2, App. B), awaiting owner approval. The label still shows only for setups that pass the §6.2 check.

### 6.2 Evidence the label must match (verify before showing — decision E)

- Separate plan total: `totals.total_cost_mean = _sum_all(period total_cost_mean)` (`backend/api/workflow.py:2507`; per-period values built at `:2476`). VERIFIED by reading: a sum of the plan's periods.
- Representative day: periods are the averaged day's periods; `days` = `validation.observation_days` (`backend/data/analysis_ingestion.py:353-354`, returned as `DatasetOut.validation` by `backend/api/datasets.py:64`). The frontend type `DatasetValidation` (`api/types.ts:97-102`) does not declare `observation_days` or `period_basis`; an optional type field is added (frontend type only, field already in the response). INFERRED: sum over one averaged day = cost per average day.
- per_date: periods are per-date labels `YYYY-MM-DD <segment> UTC` (`separate_optimization.py:1684` `_DATE_LABEL`, `:1708-1730` `per_date_days`); `days` = count of distinct date tokens in the plan's period labels; `first`/`last` = `DatasetOut.data_dates` (`api/types.ts:125-132`). INFERRED: sum over all date periods = total for N days.
- Shared plan total: `comparisonTotals(source)` over scenario rows (`PlanChanges.tsx:225`; `results.cost_basis_shared` "added over the periods"). Whether shared per-date/representative scenario rows follow the same day semantics: UNKNOWN. The label is applied to shared plans only if plan step 9 verifies it; otherwise shared keeps today's text.
- Period length (review K-UC-1, 2026-10-29, VERIFIED by reading): each period's `total_cost_mean` is an HOURLY rate, not the period's cost. Lane server cost is a rate per hour (`backend/queueing_engine/services/optimization.py:79-93` `_segment_server_cost`), and the separate runners add those rates per period (`separate_optimization.py:613-620` and `:1855-1861`; waiting cost is `served / horizon × Wq × rate`, also per hour). `totals.total_cost_mean` adds the period values without weighting by duration (`workflow.py:2507`). So the sum is the cost of the day only when every period is 60 minutes. Rule in `lib/costBasis.ts` (`allSegmentsHourLong`): the label is shown ONLY when every Setup segment (`queue_setup.segments`) runs exactly 60 minutes; with 30-minute, 120-minute or mixed segments, or no segments, no label is shown (tests `lib/costBasis.test.ts`, `PlanChanges.test.tsx`). Weighting the total by duration is protected cost math and is deferred (§12).
- Both INFERRED points become VERIFIED only by the plan's step 9 check (a representative-day and a per-date analysis on the local stack, comparing the displayed total with the sum of the period costs and the date count). If either check fails, the label is not shown for that setup and the step reports BLOCKED.

## 7. Queue Simulation (`/simulation/*`)

Merge note (review K-UC-16, 2026-10-30): merge `f8bcc380` brought in the shared-queue workflow repair, which removed the older shared run panel (RunBar, results and replay with its "Run period by period" action) by owner direction (codex spec `2026-10-29-shared-full-day-visual-replay.md`). Shared lines now show only the full-day run (§7.5). The shared-line texts of the Key Results view in §7.3 and the older shared section in §7.5 can now be reached only for single-server setups.

### 7.1 Operating hours chip (A6)

- `lib/replay.ts:21-26` `operatingHours()` returns `HH:MM–HH:MM` (en dash, VERIFIED `:25`); change the separator to the owner's spaced hyphen `HH:MM - HH:MM`. 24-hour values already come from `wallClock` (`:29-`).
- `ContinuousRun.tsx:146` builds the shared hours with an en dash from `clockOfMinutes`; same change.
- New `components/ui/HoursChip.tsx`: inline SVG clock (as mockup, `stroke="currentColor"`, `aria-hidden`), text = unchanged `t('simulation.operating_hours', { hours })` (pinned). Tokens `--color-info-bg`/`--color-info-fg`. Used at `RunBar.tsx:69` and `ContinuousRun.tsx:152`. `operating_hours_unknown` stays plain text.
- Side effect (VERIFIED): `ReplayView.tsx:28-35` also prints `operatingHours()` as the replay period label, so it shows the spaced hyphen too. `lib/replay.test.ts` has no `operatingHours` case today (VERIFIED); one is added.

### 7.2 Combined Waiting Line legend (A7)

`KeyResultsView.tsx:22-41`. Legend between heading and chart: entry 1 = line swatch (`.waiting-chart-line`) + `t('simulation.chart_waiting')` (EN "Combined Waiting Line", TL "Pinagsama-samang Pila"); entry 2 = band swatch (`.waiting-chart-break`) + `help.guide.simulation.breaks.title` ("Breaks" / "Mga break"), only when `breaks.length > 0`. Remove the `simulation.chart_breaks_marked` sentence (`:37`); `simulation.chart_waiting_axis` stays. The SVG's accessible name stays `simulation.chart_waiting_summary` (unchanged key).

### 7.3 Key Results, separate lines and the legacy per-period run (B5)

`KeyResultsView.tsx:136-197`.

| Element | Source | Rule |
|---|---|---|
| Card "Average wait" | `RunSummary.average_wait_hours` (`api/types.ts:366`) of Current (`currentRun`) and Suggested (`suggestedRun`) | `Current: X` / `Suggested plan: Y`; no arrow |
| Card "Longest Single Line" | `RunSummary.longest_line` | same |
| Basis ⓘ | `RunSummary.basis` (`:365`) of both sides | shown in the arrow's place only when both exist and bases differ; ⓘ name `charts.info_basis_name`, text `charts.key_basis` |
| Closing alert | Suggested `RunSummary.in_system_at_close` (`:370`) | `role="status"` warning only when a number > 0; `charts.closing_alert_one/_other` with `count` |
| More Results → "Customer Served" row | `RunSummary.served` | Current/Suggested pair; an Unavailable side gets the ⓘ (`charts.info_unavailable_name` / `charts.key_unavailable_explain`) |
| Takeaway | both averages | `charts.key_take` (draft) |
| Details | `RunSummary.basis`, setup breaks, seeds | chips: `simulation.run_basis_per_period` / `simulation.run_basis_continuous` / `simulation.run_basis_continuous_per_date`, `charts.chip_no_breaks` / `charts.chip_breaks_included`, `charts.chip_seed_not_saved` or `simulation.seed` + value |

- Removed: card "Customers served" and card "Still in line or being served at closing" (moved/replaced as above); the `simulation.per_period_totals_note` rendering (`:160, :167-168`) — key kept (§3.4).
- `charts.key_basis` states "the plan simulates one continuous day with breaks". It is true only when the plan basis is `continuous_day` and the setup has breaks. Other differing-basis cases (no breaks; one continuous run per date) need owner wording (slot W12); in those cases the ⓘ is shown with `charts.info_basis_name` only if a true text exists, else the ⓘ is omitted and the two sides still show their basis chips in details.
- `charts.key_unavailable_explain` says "This run simulates one period at a time". True for any side whose `basis = 'per_period'` (Current always, `simulationContext.ts:85-91`; a per-date plan without segments). For a side that is Unavailable for another reason (`summary` missing → existing `simulation.summary_rerun`; not run → `simulation.status_not_run`) the ⓘ is not shown.
- Separate lines, correction (review K-UC-3, 2026-10-29, VERIFIED by reading): the separate Current run is ONE continuous SimPy run over the Setup's segments placed back to back, without breaks, stopping at the end of the last segment (`simulation.py:999-1000` → `_simulate_parallel_segments_core`, one `env.run(until=horizon)` at `:854`); queues carry over between periods. Its `summary.basis` is `per_period` only because the result has no `admitted`/`in_system_at_close` (`workflow.py` `_run_summary`). The plan's continuous day runs until `day_end + 24` h, so staff finish serving everyone in line (`separate_optimization.py:1230`). The shared Current run does simulate one period at a time with queue carry-over (`_simulate_segments_core`), so shared keeps every per-period text. For separate lines the page now uses: basis ⓘ `charts.key_basis_separate` / `_no_breaks_separate` / `_per_date_separate` (W18-W20), Unavailable ⓘ `charts.key_unavailable_explain_separate` for the Current side (W21; a separate plan with basis `per_period` keeps `charts.key_unavailable_explain`, which is true for it), run-basis chip `simulation.run_basis_continuous_no_breaks` (W22; `runBasisKey` for `run === 'current' && separate`; shared unchanged), the Longest Single Line chips reuse the Current chips (so `charts.longest_chip_runs` / `charts.longest_chip_breaks` are no longer shown), `simulation.chart_waiting_needs_plan_day` (W23) for the waiting-chart placeholder, and the Replay notice `simulation.one_run_notice_separate` (W24). Side effect: because `runBasisKey` is no longer `per_period` for separate Current, its Run button and empty state read the existing `simulation.run_full_operation` / `simulation.run_first` ("Run full operation"), matching what the Replay page already said for separate lines.
- D30 fit: reverses D30 (2) "4 headline cards Current → Suggested" for this page: owner decision B (2026-10-28/29), reason in mockup change 7-9 (the two runs are set up differently; the old note asked for an action the user cannot take).
- Kept as is: conservation alert (`:171-175`), `totals_all_dates` note (`:176`), DatePicker (`:177`), the two charts row (`:178-185`), More Results `PeriodTable` and `LaneTable` (with §7.6 tooltips) and `LegacyMore` table (without its Plotly cards, §9).

### 7.4 Longest Single Line table, separate lines (B6)

New `components/queueSimulation/LongestLineTable.tsx`, rendered on Key Results after the cards for separate lines (`context.separate`) when the shown run has lane rows.

| Run shown | Rows | Cell value | Not staffed |
|---|---|---|---|
| Current (per-period DES) | `SimDesOut[]` (`api/types.ts:283-309`): `time`, `queue_id` (`:291`), `max_queue` (`:298`) | `max_queue` | lane absent for that period, or not in the setup segment's `active_queue_ids` (`AnalysisSegment.active_queue_ids`, `:146`) — INFERRED mapping, step 7 verifies |
| Suggested plan (continuous day; per date via DatePicker) | `SelectedDesPeriod.results[]` (`:397-412`): `queue_id`, `max_queue` (`:389`), `active` (`:390`) | `max_queue` (null → `results.unavailable`) | `active === false` or id in `inactive_queue_ids` (`:400`) |

- Columns: Time, one column per cashier in `queue_setup.queue_ids` order, last column = row maximum over staffed lanes. At ≤520 px the cashier headers read `1…n` with the key line `charts.longest_legend_columns` (`{{count}}`, `{{first}}`, `{{last}}`); the last header reads "↑" with its accessible name `simulation.longest_line`.
- Cells: number + light bar tint scaled to the day's maximum (decorative only); hatched + `simulation.state_closed` text alternative for not staffed; roving-tabindex keyboard; tooltip shows time · cashier, `charts.longest_tip_max`, and `results.col_workload` (`fmtPctDecimal(rho_sim)`).
- Visible: heading `simulation.longest_line` (English heading), takeaway, legend (`charts.longest_legend_number`, `simulation.state_closed`, max-column entry), table. Details: run chips (`charts.longest_chip_runs`, `charts.longest_chip_breaks`, `charts.chip_seed_not_saved` — Current run only), `charts.longest_note`.
- Takeaway: `charts.longest_take_current_one/_other` ("today's simulated run") for the Current run only; plan-run takeaway = slot W11. TL drafts are updated to "Pinaka Mahabang Pila" (decision H).
- The max-column legend uses W3 `charts.longest_legend_max` (draft, any cashier count); the mockup's "the largest of the five" is not used.

### 7.5 Shared lines: full-day run (C3, C4, C6)

`ContinuousRun.tsx:209-368`.

- Headline cards (C3): Average wait (`waiting_time.customer_weighted_mean_hours`, with `mean_of_replication_means_hours` min–max as today, `:226-234`) and Longest Single Line (`metrics.max_queue_in_horizon` via `rangeText`, `:246`); no arrow, no basis ⓘ (both sides are full-day runs). Lowest–highest ranges kept (`continuous.cards_note`).
- Customer Served moves into the More Results block of the shown day (it is already a column there, `:341`) and as a Current/Suggested pair with range at the top of More Results.
- "Not served at closing" (`continuous.not_served`, `customers.per_replication.unserved`): the separate closing alert text ("still in line or being served at closing in the plan's simulated day") is not the same fact (shared `unserved` depends on the closing rule and is a per-day mean with min–max). OD-2 DECIDED (§16): it stays as a third card, unchanged; no alert (the value is a mean over repeated days, so an integer `_one`/`_other` alert would be wrong).
- Charts (C6), new design for both:
  - "People waiting through the day" (`continuous.chart_waiting`, `:271-277`): keep the step path from `waitingSteps()`; add a y-axis with integer ticks from 0 to the day's maximum (`max` already computed, `:260`) and the clock x labels; keep the closing line with a legend entry using existing text from `continuous.chart_waiting_axis`'s meaning — legend wording: owner slot (W9 covers the takeaway and the closing-line legend label). Accessible name unchanged (`continuous.chart_waiting_summary`).
  - "Average wait by period" (`simulation.chart_wait_by_period`, `:278-292`): row chart (§5.2 form), one mark per period from `ContinuousPeriod.mean_wait_hours` (`api/continuous.ts:145-153`), null → labelled gap; `continuous.by_period_hint` moves into details.
  - Takeaways for both: owner slots W9.
- Longest line per hour (C4): BLOCKED. `ContinuousPeriod` has no max-queue field; the browser does not compute one from playback events. The whole-day value (card) is shown.
- The older per-period shared section (`QueueSimulationPage.tsx:148-152`) uses `KeyResultsView` (§7.3). Its "Unavailable" ⓘ text must point to the full-day run above: owner slot W6 (`charts.key_unavailable_explain_shared`); until written, the shared older section shows no Unavailable ⓘ. Its Plotly charts are removed (§9).
- Superseded by the merge (K-UC-16, see the §7 merge note): the older per-period shared section no longer renders for shared lines; its texts are reachable only for single-server setups.

### 7.6 Wq and ρ tooltips (A8)

- `KeyResultsView.tsx:92` (LaneTable header "Wq (min)" and "ρ") and `:114` (LegacyMore header "ρ" only). Not `ChecksView.tsx:220, 255` and not `OptimizePage.tsx:110` (owner decision, mapping rows 30-31).
- Trigger = the header label itself, dotted underline (mockup `.tip-trigger`), opens on hover, focus and tap; Escape closes. Implemented with the existing interaction path (`useTooltipInteraction` + `TooltipPopup descriptive`) as an additive `InfoTip` variant (`label` prop replaces the ⓘ glyph; `ariaLabel` prop optional), so the tooltip-pointer-boundaries rules stay one code path (`docs/superpowers/specs/2026-10-27-tooltip-pointer-boundaries.md:10-11`).
- Text keys (owner text): `simulation.tip_wq`, `simulation.tip_rho` (App. A).

### 7.7 Named-staff interval note (F, OD-S3) — CONFLICTING

- Where: `NamedReplicationTable.tsx:96-104`, `simulation.named_agg_mean_of_means_value` ("{{mean}} min (Student-t interval {{lower}} to {{upper}} min; …)").
- Conflict found while specifying (VERIFIED by reading both texts; resolved by OD-1 below): the reusable range-cut text `charts.clip_text` says "This range is shown cut at 0. The lower value the API returned is below 0". For runs stored after `6d17ab9a` the API returns lower = 0 (engine floor), so sentence 2 is false; for runs stored before it the API returns a negative lower and this table prints it as is, so sentence 1 is false.
- A floored run is detectable without new math: `mean − ci_half_width < 0` (`ci_half_width` stays t·SE, shared floor spec §4; field `api/sharedNamed.ts:214`).
- DECIDED (OD-1, §16): display clamp as in §5.2.3. If the stored `ci_lower` < 0 the table prints 0; whenever the printed lower bound is 0 the text is followed by `charts.clip_legend` and an ⓘ (`charts.info_clip_name` / `charts.clip_text`). `charts.clip_text` (W15) is true for old and new runs: "This range does not go below 0, because a wait cannot be negative. Where the calculation gave a lower value, 0 is shown." The `ci_half_width` test is not needed.

## 8. Checks and Decisions: Many variations (B7, B8, C5)

`ChecksView.tsx`. Three places render Many variations results: `SeparatePlanChecks` (`:212-229`, own table), `LegacyPlanChecks` (shared plan, `:400-405`, `McTable`), `CurrentChecks` (`:459-464`, `McTable`). All three get the new chart; the tables stay as the table alternative inside details.

### 8.1 ⓘ "What is Many variations?"

Next to the heading inside the `CheckLine` summary area. Name `charts.mc_info_name`, text `charts.mc_info_text` with `{{trials}}` = `SimMcOut.num_trials` (`:513`), `{{target}}` = `fmtPctDecimal(failure_threshold)` (`:515`), `{{cap}}` = `fmtPctDecimal(failure_rate_cap)` (`:516`), all read from the STORED result rows (C5), never from the editable form fields (memory.md: "Validation presentation ... use parameters persisted with the validation run"). If the rows disagree on a value or a value is absent: the ⓘ is not shown (UNKNOWN parameter; no default substituted). The fixed 20%/10% noise in the text match `backend/queueing_engine/config.py:37-38` (`MC_ARRIVAL_NOISE = 0.20`, `MC_SERVICE_NOISE = 0.10`, VERIFIED this session); if `SimMcOut.arrival_noise_fraction`/`service_noise_fraction` (`api/types.ts:519-520`) are present and differ, the ⓘ is not shown).

### 8.2 Chart: highest risk per hour against the cap

- Rows: one per period. Separate lines (plan and Current): the lane with the highest `failure_rate` (ties: higher `failure_rate_ci_upper`, then queue id), named at the right with its value (`charts.mc_legend_point_separate`). Shared (C5): the period's single row, no cashier label.
- Marks: point = `failure_rate`; range = `failure_rate_ci_lower`–`failure_rate_ci_upper` when present (absent → no range drawn, tooltip "Unavailable"); vertical dashed cap line at `failure_rate_cap` with its `fmtPctDecimal` label; x from 0 to `niceMax(max(cap, max upper, max rate))` (the mockup's fixed 6% is not used: it would hide rates above 6%).
- Tap/Enter on a row (separate) shows all lanes for that period (Queue, Failure rate, 95% range).
- Visible: heading, takeaway, legend, chart. Details: chips (run kind, `simulation.trials`, `simulation.failure_rate_cap`, `simulation.seed`, `charts.mc_chip_fail_plan` for plan runs only), the full table (§8.4).
- Takeaway `charts.mc_take_separate` (draft, names a lane). Shared and Current-run variants that are true: slots W7 (shared: no lane; `mc_chip_fail_plan` says "a cashier's ... the plan's target") and W13 (Current run: no plan target).

Takeaway wording rule (review K-UC-6, 2026-10-29): "Closest to the {{cap}} cap" (`charts.mc_take_separate` / `charts.mc_take_shared`) is used only when the highest stored rate is at or below the stored cap (1e-9 tolerance); above it, the takeaway uses `charts.mc_take_separate_above` / `charts.mc_take_shared_above` (W25/W26). Same for the Current and the plan run (`ManyVariationsChart.tsx`).

### 8.3 Shared stored threshold (C5, OD-T1..T4)

After `344ac9ce` new shared MC runs store `failure_threshold` = plan target; older shared runs store 0.75 (OD-T1: still usable until rerun). The ⓘ and chips print whatever the rows store, so an old run says 75% (true for that run).

### 8.4 Tables and percentages (B8)

- `SeparatePlanChecks` table (`:219-223`): Failure rate `fmt(row.failure_rate)` ("0.03", no %) → `fmtPctDecimal`.
- `McTable` (`:99-112`): `fmtPct` / `fmtFrCi` (integer %) → `fmtPctDecimal` for rate and both bounds; Plotly pair at `:109` removed (§9).
- Validation tables (`:394`, `:476`) and Decision tables: not changed (not part of decision B7/B8 surfaces). Listed in §11.

## 9. Removals

| Item | Location (VERIFIED) | Replaced by |
|---|---|---|
| `WaitByPeriodChart` | `components/results/ResultsCharts.tsx:36-67` | tab 1 Today view (§5.2.1) |
| `BusyStrip` (whole component) | `components/results/BusyStrip.tsx` | tab 2 (§5.3) |
| `PlanTable` | `components/results/PlanChanges.tsx:40-71` | tabs 1-2 (§5.4) |
| Cards "Customers served", "Still in line or being served at closing" | `KeyResultsView.tsx:167-168` | More Results row + closing alert (§7.3) |
| `simulation.chart_breaks_marked` sentence | `KeyResultsView.tsx:37` | legend (§7.2); key stays in catalogues (unused) |
| `simulation.per_period_totals_note` rendering | `KeyResultsView.tsx:160, 167-168` | Unavailable ⓘ; key stays (pinned) |
| LegacyMore Plotly cards (heatmap, ρ/Lq lines, max-queue bars, Lq histogram) | `KeyResultsView.tsx:125-130`, import `:8` | values stay in the LegacyMore table; separate: Longest Single Line table |
| McTable Plotly pair (ρ mean/p95 lines, failure-rate bars) | `ChecksView.tsx:109`, import `:36` | §8.2 chart |
| Unused charts `UtilizationCompareBars`, `ServerCompareBars`, `WaitTimeLines`, `CostWaterfall`, `ScenarioCompareBars` | `Charts.tsx:243-436` (no importer: VERIFIED by grep) | — |
| Their tests | `Charts.test.tsx:84-` ("optimization chart null semantics") | — |
| Consequence: `Charts.tsx:1-242` | after the two removals above it has no importer | file and `Charts.test.tsx` deleted; Plotly mock in `test/setup.ts:10-11` and `.plotly-wrap` CSS (`global.css:724-732`) removed if no other user (grep in plan) |

`package.json` dependencies `plotly.js` / `react-plotly.js` and their types are NOT removed in this build (dependency change → OD-3). With no import, Vite does not bundle them; the build-size change is measured (plan step 0 vs final).

## 10. Locale changes

- Every changed or new string is in both `en` and `tl` with the same key (`lib/translationKeys.test.ts:13-27` enforces it). App. A lists each key, EN, TL, status.
- Status meanings: **owner** = owner's exact text (ulit mockup / ulit.pdf as decided); **drafted** = chart mockup draft placed as drafted (decision H), to be reviewed by the owner later; **drafted (templated)** = draft with a run value turned into a variable (§2.6); **existing** = existing key reused, unchanged.
- No new wording-lock record and no new wording test (A11). `wordingPolicy.test.ts` and `docs/wording/2026-10-27-local-wording-application.json` are not edited.
- Drafts are marked as drafts only in this spec (App. A status column); there is no in-code marker (locale JSON has no comments, and a marker in the string would show on screen).
- Mockup-only text: the chart mockup's "What changed" note 9 ("Customers served moved into More Results") is mockup copy, not app copy. Decision H's update to it ("Customer Served") applies to the mockup if it is regenerated; there is no app key. Likewise the mockup's `tabs.sim.aria` draft is not added: the final mockup has no tablist on Queue Simulation (VERIFIED: only one `role="tablist"`, `chart-redesign/index.html:243`).

## 11. Test strategy

Unit (Vitest): new pure shaping modules, one per chart so parallel steps do not share a file (`lib/waitChart.ts`, `lib/busyLevel.ts`, `lib/longestLine.ts`, `lib/manyVariations.ts`, `lib/costBasis.ts`, `lib/chartScale.ts`), each with a test file. Shaping only (select, group, max, format), no new math.
- Wait rows: kinds kept apart; null → gap; shown lower = max(0, lower), cut flag when the shown lower is 0; highlighted row = max Estimated; minutes conversion matches `minutes()`.
- Busy rows: level word and `fmtPctDecimal` for today/plan; separate plan uses `peak_util`; shared plan uses `rho_optimal` + `optimized_stable`; tolerance edge (0.6 − 1e-12 is Normal, as `utilization.test.ts`).
- MC rows: highest-risk lane per period with the tie rule; shared single row; stored parameters read from rows; disagreeing rows → parameters UNKNOWN; axis max ≥ cap and ≥ max upper.
- Longest-line matrix: staffed/not staffed per run kind; row max over staffed lanes only; null `max_queue` stays null.
- Cost basis label: representative day uses `observation_days`; per_date counts distinct date tokens and uses `data_dates`; aggregate → none.
- `operatingHours()` returns `HH:MM - HH:MM` (new case in `lib/replay.test.ts`).

Component (React Testing Library):
- Results: tablist roles, Arrow/Home/End, `?chart=` read/write, single-tab fallback, D21 (no plan → no Plan view switch, no-plan prompt shown); Today view never draws plan; Plan view never draws Recorded; separate rows whose shown lower bound is 0 get the marker, legend entry and ⓘ (fixture with a v4-style negative lower, which prints 0, and one with lower = 0); a row with lower > 0 has none; the stored negative value is never printed; shared plan view has no range and no "simulated" word in EN.
- Busy Level: every period prints word + %; 0.0019 renders "0.19%"; shared tap shows counters, separate tap shows cashiers.
- Key Results: 2 cards; no "→" glyph; basis ⓘ only when bases differ and `charts.key_basis` is true; closing alert only for `in_system_at_close > 0`, `_one` at 1 and `_other` at 2 in EN; Customer Served in More Results; Unavailable ⓘ on per-period sides only; `per_period_totals_note` not rendered; no Plotly element (`.plotly`) anywhere on Results/Checks.
- Combined Waiting Line legend: 2 entries with breaks, 1 without; `chart_breaks_marked` text absent.
- Wq/ρ tooltips: open on hover, focus and click; Escape closes; text EN/TL.
- Many variations: ⓘ text filled from stored rows (not form fields); fmtPctDecimal in tables; chart rows count = periods.
- Supervisor: auto-name follows a re-check at a new limit; a typed name survives.
- Replay: model name not printed.
- Field guide: field `th` has the scoped class (CSS behaviour itself checked in the browser).

Updated existing tests (text changes only, never to hide behaviour): the 14 files that assert old label text (VERIFIED by grep: `AnalysisWorkspace`, `WorkflowNavigator`, `AppLayout`, `Sidebar`, `SupervisorSchedule`, `CurrentDatasetCache`, `HomePageLearning`, `NewAnalysisPage`, `OptimizePage`, `QueueSimulationPage`, `ReportsPage`, `ResultsPage`, `SetupSemantics`, `routerDataRedirect` tests) plus `QueueSimulationPage.test.tsx:325-326, 697, 844, 1000` (card regions). Removed: `Charts.test.tsx`.

Pinned checks that must stay green untouched: `wordingPolicy.test.ts` (200 records), `translationKeys.test.ts`, `criticalSemantics.test.ts`, `headingText.test.ts`.

Browser (built-in browser, local stack, plan final step): NovaMart xlsx as separate lines (representative day and per_date) and as a shared line; 375/768/1024+ widths; light and dark; EN and TL; keyboard-only pass of tabs, row charts, matrix, ⓘ; no page horizontal scroll at 375 (`document.documentElement.scrollWidth <= 375`). Screenshots named per screen.

Gates: in `frontend/`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build` (bundle size before/after recorded). Backend pytest only if a backend file changes (none planned).

## 12. BLOCKED and UNKNOWN

| Item | Status | Why / what the API would need |
|---|---|---|
| Per-cashier plan utilisation (separate Busy Level plan view, tap detail) | BLOCKED | `GET /analyses/:id/workflow/comparison/separate` returns only `peak_util` per period (`api/types.ts:641`); needs per-lane mean utilisation per period |
| Shared full-day longest line per hour | BLOCKED | `ContinuousPeriod` (`api/continuous.ts:145-153`) has no max-queue field; needs per-period max queue in `by_period` |
| Ranges for Key Results numbers, day-total cost | Not shown (G) | `RunSummary` single values; plan cost has no total CI |
| TL for the two cost labels | Drafted (W1, W2), awaiting owner approval | §16 |
| Step bar overlap geometry (4c) | UNKNOWN until measured | PDF screenshots not extracted |
| Shared cost label semantics | UNKNOWN until plan step 9 | §6.2 |
| `observation_days` present on every representative-day dataset | INFERRED (ingestion writes it, `analysis_ingestion.py:353-354`); older datasets UNKNOWN | if absent, label not shown |
| Field `active_queue_ids` mapping for Current-run hatching | Implemented 2026-10-29 from code (VERIFIED by reading source; browser VERIFIED 2026-10-30 on the separate representative day: cashier_4/5 hatched at 05:00-06:00, cashier_1-3 at 17:00-18:00, as in the Setup) | Hatching comes from Setup staffing, never from a missing row: every `queue_ids` cashier when `staffing_varies_by_period` is false, else the `active_queue_ids` of the segment named by the row's `segment_id` (engine id = segment id, else `segment_<n>`; `simulation.py` `_parallel_schedule`, `queue_lifecycle.scheduled_active_queue_ids`). The Current run also returns rows for closed cashiers (lambda 0). When a period's segment is not known the cell shows "—" without hatching and the hatching key is left out (`lib/longestLine.ts`). Risk: the Setup is read as it is now; a Setup changed after the run is not detected here |
| TL plural forms | RISK | §14 |
| Physical touch, other browser engines, screen readers other than the DOM check | NOT TESTED in this build unless the plan's browser step can do it | — |
| Customer-record count chip (`charts.wait_chip_recorded`, §5.2.1 details) | DEFERRED, owner-visible: chip left out in this build | No API field gives the number of customer records behind the Recorded side; `DatasetOut.row_count` is the number of normalized period records (`backend/api/analyses.py:232`, `row_count=len(records)`), not customer records. Needs a customer-record count from the API |
| Shared plan cost label (§6) | DEFERRED, owner-visible: label left off for shared plans | Day basis of shared plan row costs is UNKNOWN (plan step 9a); shared plans keep `results.cost_basis_shared` / `results.cost_unavailable_shared` |
| Plan cost weighted by period length (review K-UC-1) | DEFERRED — protected cost math | Period costs are hourly rates added up without duration weighting (`workflow.py:2507`). The frontend shows the day-basis label only for all-60-minute Setup segments (§6.2) and never re-weights a value. A true day total for other lengths needs a backend change under its own authorization (AGENTS.md §5) |
| "hour" wording when periods are not 60 minutes or are per-date segments (review K-UC-7 / N1) | OPEN, left alone in this round | `level_take_*`, `range_wait`, `mc_chart_name`, `wait_chart_name`, `longest_*`; needs owner wording |
| N4, N5, N6 (parent's numbering of the remaining review nits; includes K-UC-10 `_shared_plan_target` reads only `results_json["results"]` and K-UC-11 34 px RowChart rows on a coarse pointer) | OPEN, left alone in this round | — |
| Backend items from the browser walk: per_date plan refusal, the 413 response, `segment_N` labels | OPEN — backend, out of frontend scope | Hayato / parent |
| 375 px More Results table squeeze | OPEN — older code, left alone | — |
| Separate Current run vs `simulation.closing_rule_separate` (found 2026-10-29 while fixing K-UC-3; review K-UC-12) | FIXED 2026-10-30 (frontend) | The separate Current run and legacy separate plans stop at closing (`simulation.py:854`, `env.run(until=horizon)`; customers still waiting are counted as `waiting`). `RunBar` now shows the text only for `run === 'suggested' && context.selectedSeparate`, the plan's continuous day that drains the lines. Test: `QueueSimulationPage.test.tsx` K-UC-12 |
| Per-date separate Current run input (found 2026-10-29; review K-UC-13) | OPEN — backend, owner-visible | Probe-verified by review K-UC-13: a per-date separate Current DES uses one date's records, or stitches several dates together (`simulation.py:689-695`, `workflow.py:690-715`). Not changed here (protected simulation input, AGENTS.md §5); needs a backend task |
| `sim_hours` on the separate Current run (review K-UC-14) | OPEN — backend, owner-visible | `sim_hours` has no effect on the separate Current run, although the RunBar's Advanced settings still send it. Needs a backend decision (honour it or drop it from that request); not changed here |
| Older shared run panel removed by the merge (review K-UC-16) | RECORDED 2026-10-30 | See the §7 merge note: owner-directed removal (codex spec `2026-10-29-shared-full-day-visual-replay.md`); the shared-line Key Results texts in §7.3/§7.5 are reachable only for single-server setups |
| Today-view counters, separate lines (review K-UC-5) | Implemented 2026-10-29 from code; browser VERIFIED 2026-10-30 (recheck at `f8bcc380`: separate representative day shows 3, 5 ×11, 2 = the Setup's `active_queue_ids` counts; the shared 14-day CSV shows the file's `c` 3,5,5,5,5,5,2,3,5,5,5,5,2) | The Today view counts the cashiers the Setup staffs in each period with `setupStaffing` (`lib/longestLine.ts`, shared via `setupCountersByPeriod` in `lib/waitChart.ts`); a period is mapped to its segment through the file's records (`time` → `segment_id`). When staffing varies and the period's segment is unknown, "—" is shown. Shared lines keep the rows' `c` |
| Closing alert on per-date plans (§7.3) | DEFERRED, owner-visible: alert shown only for a representative-day plan or a per-date plan with one date | For a per-date plan the server adds `in_system_at_close` over all dates (`backend/api/workflow.py:2916-2946`, `at_close_total`), so `charts.closing_alert` ("in the plan's simulated day") would be false. With more than one date the value is shown in More Results under `simulation.not_served_at_close`, next to the `simulation.totals_all_dates` note. A per-date alert needs owner wording (or the per-date `days[].in_system_at_close`) |

## 13. Owner decisions needed (new, raised by this spec)

These do not reopen any closed decision; they come from code facts found while specifying. All six were DECIDED by the parent session under owner delegation on 2026-10-29 (§16); the "Default" column is kept for the record.

| ID | Question | Options | Recommendation | Default until answered |
|---|---|---|---|---|
| OD-1 (was CONFLICTING; DECIDED §16) | OD-S3 note on the named-staff interval: the reusable `charts.clip_text` is false for both new floored runs and old negative runs (§7.7) | (a) new runs (`mean − ci_half_width < 0`): show `charts.clip_legend` ("Range cut at 0") only, no ⓘ; old runs: no note. (b) as (a) plus an owner-worded ⓘ text for floored runs. (c) also cut old runs' printed lower at 0 with `clip_text` (changes a printed number) | (b) | nothing shipped for F |
| OD-2 | Shared full-day "Not served at closing": alert like separate, or keep as a card/More Results row? | (a) keep card (today) (b) alert when Suggested `per_replication.unserved.max > 0` with owner text (c) move into More Results | (b) | (a) |
| OD-3 | Remove `plotly.js`, `react-plotly.js` and their `@types` from `package.json` once nothing imports them? | yes (separate small change, lockfile diff, bundle measured) / no | yes, as a separate change after this build | keep |
| OD-4 | Tab 1 "What the plan changes" with no selected plan shows the Today view + no-plan prompt. OK? | OK / hide tab 1 without a plan (then recorded-vs-estimated is gone until a plan exists) | OK | OK |
| OD-5 | `CalculatedResult` line `results.suggests_wait` still pairs today's analytical mean with the simulated plan mean (separate) — same mixing the redesign removed from the table | leave / remove line / owner rewording | owner rewording or remove | leave |
| OD-6 | Separate-lines "Average wait by period" (`KeyResultsView.tsx:43-60`) — give it the same row-chart design as the shared one (C6)? | yes / no | yes (same component, consistency) | no (unchanged) |

## 14. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| TL plural rules: i18next uses `Intl.PluralRules('tl')`, where 2 and 3 select `one` | `charts.longest_take_current_one` TL "{{count}} tao" would show for 2 people (draft other-form is "{{count}} na tao") | Test TL with counts 1, 2, 4, 10; report the forms chosen to the owner with the drafts; owner may give one TL form for all counts |
| Drafts with run values | A literal NovaMart value in a string would be false for other stores | §2.6 templating; App. A lists every templated draft |
| `simulation.per_period_totals_note` and `chart_breaks_marked` become unused | translation-key hygiene tools might flag them | keep (pinned / harmless); note in report |
| Wait chart for many periods (per_date: 14 dates × segments) | very tall chart | row height fixed; chart lives in the tab; table alternative; DatePicker is not on Results — INFERRED acceptable, browser step checks the NovaMart per_date case |
| Saved separate plans after `8b0f2eab` deploy | first save check may say "Results do not match" once (handoff, INFERRED) | not a frontend issue; unchanged |
| Help screenshots (`public/help-images`) show the old charts | Help pages out of date | out of scope; listed for a later Help refresh |
| Removing Plotly cards hides heatmap/histogram views some users used | less visual in More Results | values stay in tables (decision B9) |
| InfoTip API extension | other InfoTip users regress | props optional, defaults unchanged; `InfoTip.test.tsx` extended |
| Parallel agents editing `global.css` / locale files | merge conflicts | plan: all locale keys in one step first; all chart CSS lands in a new `styles/charts.css` in one step; `global.css` owned by one step |

## 15. Fit with prior decisions

- Consistent with: headings English (2026-10-27 spec, `headingText.ts:4`); owner-writes-wording (drafts only where owner delegated, decision H); D4 selection flow (unchanged); OD-W1, OD-S1..S3, OD-T1..T4 (engine specs); the decimal display rule (memory `novaq-chart-decimal-rule`); tooltip pointer boundaries (one interaction path).
- Reverses D30 part (2) for Key Results layout (owner decision B; reason §7.3).
- Narrows D21: the plan comparison still appears only with a selected plan, but recorded-vs-estimated now sits in the same tab (OD-4 confirms).
- D19 (busy levels) kept; presentation changes from colour-only strip to word + % grid (owner decision B4).

## Appendix A. Locale keys (new or changed)

EN/TL are exact. `{{x}}` = i18next variable. "←" notes a mechanical change from the draft.

### A.1 Owner wording (ulit, decision A) — changed keys

| Key | EN (new) | TL (new) | Status |
|---|---|---|---|
| `queueing101.combined.title` | How does Queueing works and what to record | Paano gumagana ang Queueing at ano-ano ang ire-record | owner (heading; TL used by video labels and Help search) |
| `analyses.name` | Analysis Name | Pangalan ng Analysis | owner |
| `analyses.service_type` | Service Type (Descriptive Only) | Uri ng Serbisyo (Naglalarawan) | owner |
| `template.guide_title` | Field Guide | Gabay sa Gawain | owner (heading) |
| `template.example_title` | Filled Example | Halimbawa | owner (heading) |
| `template.guide_required` | Required | Kinakailangan | owner (EN overrides PDF "Requisite", owner decision 2026-10-28) |
| `analyses.capacity` | Capacity Mode | Mode ng Kapasidad | owner |
| `analyses.finite` | Limited Total System | Limitadong Total ng System | owner |
| `nav.suggested_plans` | Suggested Plans | Suggested na Plano | owner (shared key, all places) |
| `supervisor.title` | Suggested Schedule | Suggested Schedule | owner (heading) |
| `supervisor.review` | Review the Check | I-review ang Check | owner (heading) |
| `supervisor.break_changes` | Break Changes to Review | Pagsusuri sa Break Changes | owner |
| `supervisor.confirm` | Confirm Changes | Kumpirmahin ang Pagbabago | owner (heading) |
| `optimize.scenario_name` | Scenario Name | Pangalan ng Scenario | owner (shared key) |
| `plans.use_this_plan` | Use this Plan | Gamitin ang Planong ito | owner (shared key) |
| `supervisor.back_review` | Back to Review | Bumalik sa Review | owner |
| `nav.analysis_results` | Analysis Results | Resulta ng Analysis | owner (heading on page title; label in sidebar/step bar) |
| `results.view_from` | View Results from | I-view ang Resulta mula sa | owner |
| `results.day_by_level` | Your day, by Busy Level | Ang iyong araw, kada Busy Level | owner (heading; tab 2) |
| `results.wait_chart` | Recorded vs Estimated Wait, by period | Recorded vs Estimated Wait, by period | owner (also view-1 name, decision H) |
| `simulation.chart_waiting` | Combined Waiting Line | Pinagsama-samang Pila | owner (heading; TL shown in legend) |
| `simulation.more_results` | More Results | Ibang pang Resulta | owner (heading) |
| `simulation.longest_line` | Longest Single Line | Pinaka Mahabang Pila | owner |
| `simulation.served_customers` | Customer Served | Nagsilbi sa Customer | owner (5 places) |

### A.2 Owner wording — new keys

| Key | EN | TL | Status |
|---|---|---|---|
| `simulation.tip_wq` | Average Wait Time a customer spent in queue | Average Wait Time kada customer sa pila | owner |
| `simulation.tip_rho` | Utilization Rate: How busy the counters are. | Utilization Rate: Gaano ka-abala ang mga counter. | owner |
| `results.cost_basis_average_day` | per average day (from {{days}} days of data) | kada average na araw (mula sa {{days}} na araw ng data) | owner EN (decision E); TL drafted (W1) |
| `results.cost_basis_dates` | total for {{days}} days ({{first}} – {{last}}) | kabuuan para sa {{days}} na araw ({{first}} – {{last}}) | owner EN (decision E); TL drafted (W2) |

### A.3 Drafted (chart mockup "Wording review (owner)", decision H)

Mockup id in brackets. TL updated per decision H where marked "(H)".

| Key | EN | TL | Status |
|---|---|---|---|
| `charts.tabs_label` [tabs.results.aria] | Analysis Results charts | Mga chart ng Analysis Results | drafted |
| `charts.view_group` [ui.viewgroup] | Chart view | View ng chart | drafted |
| `charts.info_range_name` [ui.info.range] | About the 95% range | Tungkol sa 95% range | drafted (used as full ⓘ name via `ariaLabel`, §7.6) |
| `charts.info_clip_name` [ui.info.clip] | About the range cut at 0 | Tungkol sa range na pinutol sa 0 | drafted |
| `charts.info_unavailable_name` [ui.info.unavail] | Why this is unavailable | Bakit ito hindi available | drafted |
| `charts.info_basis_name` [ui.info.basis] | Why these are not the same basis | Bakit hindi pareho ang basehan | drafted |
| `charts.range_label` [range.label] | 95% range | 95% range | drafted |
| `charts.range_wait` [range.wait] | 95% confidence range for the plan’s simulated average wait in this hour, from {{runs}} runs. | 95% confidence range ng simulated na average wait ng plano sa oras na ito, mula sa {{runs}} runs. | drafted (templated ← "5") |
| `charts.range_mc` [range.mc] | 95% confidence range for the share of variations that failed, from {{trials}} trials. | 95% confidence range ng bahagi ng mga variation na bumagsak, mula sa {{trials}} trials. | drafted (templated ← "2,000") |
| `charts.clip_legend` [clip.legend] | Range cut at 0 | Pinutol sa 0 ang range | drafted |
| `charts.clip_text` [clip.text → W15] | This range does not go below 0, because a wait cannot be negative. Where the calculation gave a lower value, 0 is shown. | Hindi bumababa sa 0 ang range na ito, dahil hindi puwedeng negatibo ang wait. Kapag mas mababa ang lumabas sa kalkulasyon, 0 ang ipinapakita. | drafted (parent, OD-1/W15; replaces the mockup's "API returned" text) |
| — [clip.tip] | — | — | not added (OD-1: "API" phrasing dropped; tooltip uses `charts.clip_legend`) |
| `charts.conn_during` [conn.during] | during | noong | drafted |
| `charts.conn_or` [conn.or] | or | o | drafted |
| `charts.wait_take_today` [s1.take.today] | {{time}} has the highest calculated estimate today: {{est}} per customer. Recorded: {{rec}}. | Ang {{time}} ang may pinakamataas na Kalkuladong tantiya ngayon: {{est}} kada customer. Naitala: {{rec}}. | drafted |
| `charts.wait_take_plan_separate` [s1.take.plan] | {{time}} has the highest calculated estimate today: {{est}} per customer. Suggested plan, simulated: {{plan}}. | Ang {{time}} ang may pinakamataas na Kalkuladong tantiya ngayon: {{est}} kada customer. Mungkahing plano, simulated: {{plan}}. | drafted (separate only) |
| — [s1.view1] | — | — | not added: replaced by `results.wait_chart` (H) |
| `charts.wait_view_plan` [s1.view2] | Estimate vs suggested plan | Tantiya vs mungkahing plano | drafted |
| `charts.wait_axis` [s1.axis] | Average wait per customer (min) | Average Wait Time kada customer (min) | drafted |
| `charts.wait_legend_plan_simulated` [s1.leg.plan] | Suggested plan (simulated) | Mungkahing plano (simulated) | drafted (separate only) |
| `charts.wait_chip_recorded` [s1.chip.rec] | Recorded: {{records}} customer records over {{days}} dates ({{first}} to {{last}}) | Naitala: {{records}} customer records sa {{days}} na petsa ({{first}} hanggang {{last}}) | drafted (templated ← "1,600", "14", dates) |
| `charts.wait_chip_estimate_separate` [s1.chip.est] | Calculated estimate: queueing formula for each cashier line ({{model}}) | Kalkuladong tantiya: queueing formula sa bawat cashier line ({{model}}) | drafted (templated ← "Parallel M/G/1"; separate only) |
| `charts.wait_chip_plan_simulated` [s1.chip.plan] | Suggested plan, simulated: mean of {{runs}} runs, base seed {{seed}} | Mungkahing plano, simulated: average ng {{runs}} runs, base seed {{seed}} | drafted (templated ← "5", "42") |
| `charts.wait_axis_note` [s1.axisnote] | Each row is one hour; the axis starts at 0. | Isang oras ang bawat row; nagsisimula sa 0 ang axis. | drafted (shown only for 60-minute periods; otherwise W16) |
| `charts.show_table` [s1.tableview] | Show as a table | Ipakita bilang table | drafted |
| `charts.wait_chart_name` [s1.aria] | Wait by hour. Use the arrow keys to read each hour. | Wait kada oras. Gamitin ang arrow keys para basahin ang bawat oras. | drafted |
| `charts.longest_take_current_one` [s2.take_one] | Longest line in today’s simulated run: {{count}} person, at {{where}}. | Pinaka Mahabang Pila sa simulated run ngayon: {{count}} na tao, sa {{where}}. | drafted (H: TL "Pinakamahabang iisang pila" → "Pinaka Mahabang Pila"; TL "{{count}} tao" → "{{count}} na tao" so it reads for any count, parent §16) |
| `charts.longest_take_current_other` [s2.take_other] | Longest line in today’s simulated run: {{count}} people, at {{where}}. | Pinaka Mahabang Pila sa simulated run ngayon: {{count}} na tao, sa {{where}}. | drafted (H, as above) |
| `charts.longest_legend_number` [s2.leg.num] | Most people waiting at once in that cashier’s line during the hour | Pinakamaraming sabay na naghihintay sa pila ng cashier sa oras na iyon | drafted |
| — [s2.leg.max] | — | — | not added (fixed count "five"); replaced by W3 `charts.longest_legend_max` (App. B) |
| `charts.longest_legend_columns` [s2.leg.cols] | Columns 1–{{count}} = {{first}} … {{last}} | Columns 1–{{count}} = {{first}} … {{last}} | drafted (templated ← "5", "cashier_1", "cashier_5") |
| `charts.longest_chip_runs` [s2.chip.runs] | 1 simulation run per period | 1 simulation run kada period | drafted (Current run) |
| `charts.longest_chip_breaks` [s2.chip.breaks] | Breaks not included | Hindi kasama ang break | drafted (Current run) |
| `charts.chip_seed_not_saved` [s2.chip.seed] | Seed not saved | Hindi naka-save ang seed | drafted (only when stored seed is null) |
| `charts.longest_note` [s2.note] | Counts are the simulation’s max_queue for each cashier and hour. Hatched cells are not staffed in your Setup for that hour; they are not zero. | Ang bilang ay ang max_queue ng simulation para sa bawat cashier at oras. Ang may guhit na cell ay walang tauhan sa iyong Setup sa oras na iyon; hindi ito zero. | drafted |
| `charts.longest_tip_max` [s2.tip.max] | Most waiting at once | Pinakamaraming sabay na naghihintay | drafted |
| `charts.mc_take_separate` [s3.take] | Closest to the {{cap}} cap: {{time}}, {{lane}}, with {{rate}} of {{trials}} variations failing. | Pinakamalapit sa {{cap}} cap: {{time}}, {{lane}}, {{rate}} ng {{trials}} na variation ang bumagsak. | drafted (separate only) |
| `charts.mc_legend_point_separate` [s3.leg.point] | Highest failure rate in the hour (cashier named on the right) | Pinakamataas na failure rate sa oras (nakapangalan ang cashier sa kanan) | drafted (separate only) |
| `charts.mc_chip_fail_plan` [s3.chip.fail] | A variation fails when a cashier’s Utilization Rate is above {{threshold}}, the plan’s target. | Bumabagsak ang variation kapag lampas sa {{threshold}} ang Utilization Rate ng cashier, ang Target ng plano. | drafted (separate plan only) |
| `charts.mc_info_name` [s3.info.name] | What is Many variations? | Ano ang Many variations? | drafted |
| `charts.mc_info_text` [s3.info.text] | Many variations tests how well the plan holds up. NovaQ calculates {{trials}} what-if versions of each period: customers arrive up to 20% more or less often, and service is up to 10% faster or slower. A version fails when Utilization Rate is above {{target}}. The period passes when no more than {{cap}} of versions fail. | Sinusubok ng Many variations kung gaano katibay ang plano. Kinakalkula ng NovaQ ang {{trials}} na what-if na bersyon ng bawat period: dumarating ang customer nang hanggang 20% mas madalas o mas madalang, at hanggang 10% mas mabilis o mas mabagal ang serbisyo. Bumabagsak ang isang bersyon kapag lampas sa {{target}} ang Utilization Rate. Pasado ang period kung hindi hihigit sa {{cap}} ng mga bersyon ang bumagsak. | drafted |
| `charts.mc_chart_name` [s3.aria] | Failure rate by hour against the cap. Use the arrow keys to read each hour. | Failure rate kada oras laban sa cap. Gamitin ang arrow keys para basahin ang bawat oras. | drafted |
| `charts.level_take_today` [s4.take.today] | Calculated estimate: every hour is {{levels}}; the busiest line peaks at {{value}} during {{time}}. | Kalkuladong tantiya: {{levels}} ang bawat oras; pinakamataas ang pinaka-abalang linya sa {{value}} noong {{time}}. | drafted (separate; shared slot W8) |
| `charts.level_take_plan_separate` [s4.take.plan] | Suggested plan, simulated: every hour is {{levels}}; the busiest cashier peaks at {{value}} during {{time}}, below the plan’s {{target}} target. | Mungkahing plano, simulated: {{levels}} ang bawat oras; pinakamataas ang pinaka-abalang cashier sa {{value}} noong {{time}}, mas mababa sa {{target}} na Target ng plano. | drafted (only when peak < target) |
| `charts.level_chip_plan_simulated` [s4.chip.plan] | Simulated: busiest cashier’s mean over {{runs}} runs | Simulated: average ng pinaka-abalang cashier sa {{runs}} runs | drafted (templated ← "5") |
| `charts.level_hours` [s4.group] | Hours | Mga oras | drafted |
| `charts.level_plan_no_lanes` [s4.plan.nolanes] | Values for each cashier are not available for the plan. | Walang value para sa bawat cashier sa plano. | drafted |
| `charts.key_take` [s5.take] | Simulated average wait: Current {{current}}, Suggested plan {{plan}}, from two runs set up differently. | Simulated na average wait: Ngayon {{current}}, Mungkahing plano {{plan}}, mula sa dalawang run na magkaiba ang setup. | drafted (only when bases differ; same-basis variant = slot W12) |
| `charts.key_basis` [s5.basis] | Not the same basis: Current simulates one period at a time with no breaks; the plan simulates one continuous day with breaks. | Hindi pareho ang basehan: isang period sa bawat pagkakataon at walang break ang simulation ng Ngayon; iisang tuloy-tuloy na araw na may break ang simulation ng plano. | drafted (only when true, §7.3) |
| `charts.chip_no_breaks` [s5.chip.nobreaks] | No breaks | Walang break | drafted |
| `charts.chip_breaks_included` [s5.chip.breaks] | Breaks included | Kasama ang break | drafted |
| `charts.key_unavailable_explain` [s5.explain] | This run simulates one period at a time, so it has no whole-day total. This is expected, not an error. Compare with Average wait and Longest Single Line. | Isang period sa bawat pagkakataon ang simulation na ito, kaya walang kabuuan para sa buong araw. Inaasahan ito, hindi error. Ihambing gamit ang Karaniwang paghihintay at Pinaka Mahabang Pila. | drafted (owner-delegated text, memory owner-writes-wording) |
| `charts.closing_alert_one` [s5.closing_one] | {{count}} customer still in line or being served at closing in the plan’s simulated day. | {{count}} customer ang nasa pila pa o pinagsisilbihan sa pagsasara sa simulated na araw ng plano. | drafted (owner-delegated) |
| `charts.closing_alert_other` [s5.closing_other] | {{count}} customers still in line or being served at closing in the plan’s simulated day. | {{count}} customer ang nasa pila pa o pinagsisilbihan sa pagsasara sa simulated na araw ng plano. | drafted (owner-delegated) |
| — [tabs.sim.aria] | — | — | not added (no tablist on Queue Simulation in the final mockup) |

Note: drafts with `’` keep the typographic apostrophe exactly as in the mockup.

### A.4 Existing keys reused (unchanged)

`results.plan_changes`, `results.recorded`, `results.estimated`, `results.source_data`, `results.source_estimate`, `results.unavailable`, `results.min`, `results.col_counters`, `results.col_workload`, `results.col_level`, `results.level.*`, `results.range.*`, `results.levels_note`, `results.strip_separate_note`, `results.cant_keep_up_wait`, `results.above_plan_target`, `current.observed_flagged`, `common.time`, `simulation.run_current`, `simulation.run_suggested`, `simulation.average_wait`, `simulation.run_basis_per_period`, `simulation.run_basis_continuous`, `simulation.run_basis_continuous_per_date`, `simulation.state_closed`, `simulation.sep_lane`, `simulation.sep_mc_failure`, `simulation.trials`, `simulation.failure_rate_cap`, `simulation.seed`, `simulation.plan_target`, `simulation.check_details`, `simulation.check_variations`, `simulation.operating_hours` (pinned), `simulation.chart_waiting_summary`, `simulation.chart_waiting_axis`, `simulation.chart_wait_by_period`, `help.guide.simulation.breaks.title`, `continuous.chart_waiting`, `continuous.chart_waiting_summary`, `continuous.chart_waiting_axis`, `continuous.by_period_hint`, `continuous.cards_note`, `continuous.not_served`, `calculator.about`. Kept but no longer rendered: `simulation.per_period_totals_note` (pinned), `simulation.chart_breaks_marked`, `simulation.not_served_at_close` (only reader was `KeyResultsView.tsx:168`, VERIFIED by grep; the closing alert uses new keys).

## 16. Decisions by the parent session under owner delegation (2026-10-29)

Label: REPORTED. The parent session relayed that the owner delegated every remaining authorization, in these words (2026-10-29): "i approve to finish this all need authrizationn i allow you. finish this". Each item below is "DECIDED by parent under owner delegation 2026-10-29". The owner may revisit any of them; drafts stay drafts.

| ID | Decision | Effect in this spec |
|---|---|---|
| OD-1 | Display clamp, the same approach as Part A. A stored lower bound < 0 (older runs) is shown as 0. Whenever the shown lower bound is 0, a small "Range cut at 0" note (`charts.clip_legend`) with an ⓘ (`charts.clip_text`, W15) is shown. The same ⓘ text is used wherever a chart range is cut; the old "API returned" phrasing is dropped everywhere. | §5.2.3, §7.7, App. A (`charts.clip_text` text replaced, `clip.tip` not added); plan step 12 unblocked |
| OD-2 | Shared full-day "Not served at closing" stays a card. The value is a mean over repeated days, so an integer `_one`/`_other` alert would be wrong. | §7.5; W14 not needed |
| OD-3 | Plotly packages stay in `package.json` in this build. Follow-up: remove `plotly.js`, `react-plotly.js`, `@types/plotly.js`, `@types/react-plotly.js` as a separate change, with the lockfile diff and the measured bundle change. | §9 |
| OD-4 | Accepted: with no selected plan, tab 1 shows the Today view plus the no-plan prompt. | §5.1 |
| OD-5 | `CalculatedResult`'s average-wait line stays but must name both kinds with existing words. Shared lines: unchanged (both sides calculated). Separate lines: W17 draft `results.suggests_wait_separate`. | §5.4 |
| OD-6 | No: the separate-lines "Average wait by period" chart (`KeyResultsView.tsx:43-60`) is unchanged. | §7.3 |
| W1-W17 | Drafted by the agent, EN and TL, from verified facts only, marked "Draft — awaiting owner approval" (App. B). Owner text used verbatim where it exists (EN of W1/W2). | App. B; all keys added in plan step 1 |
| Plural | TL is written so the noun reads correctly for any count (for example "{{count}} na tao"); i18next `_one`/`_other` keys are kept for EN. Owner review requested. | App. A/B; §14 |
| Numbers | Every value in a draft comes from an API field. No NovaMart value is hard-coded. The 20% and 10% in `charts.mc_info_text` are engine constants (`backend/queueing_engine/config.py:37-38`, `MC_ARRIVAL_NOISE = 0.20`, `MC_SERVICE_NOISE = 0.10`), not run values. Correction (2026-10-29, build step 13 prep; the earlier sentence here was CONFLICTING): the backend does set `arrival_noise_fraction` and `service_noise_fraction` on every Many variations row, from those constants (`backend/queueing_engine/simulation/simulation.py:1229`, `mc_simulate_segment` metadata), VERIFIED by reading the source. They stay as fixed method text; `lib/manyVariations.ts` shows the ⓘ only when every stored row's fractions equal the method values (or are absent on older rows), so the text must be re-checked if the constants change. | App. A |

The Many variations range needs no clamp note: a failure share and its Wilson bounds are never negative.

## Appendix B. Wording drafted under owner delegation (W1-W26)

All rows: **Draft — awaiting owner approval.** Facts named in the "Facts" column were checked in this session. `{{x}}` values come only from the API fields named.

| Slot | Key | EN | TL | Facts / values |
|---|---|---|---|---|
| W1 | `results.cost_basis_average_day` | per average day (from {{days}} days of data) | kada average na araw (mula sa {{days}} na araw ng data) | EN = owner (decision E). `days` = `validation.observation_days` (`analysis_ingestion.py:353-354`) |
| W2 | `results.cost_basis_dates` | total for {{days}} days ({{first}} – {{last}}) | kabuuan para sa {{days}} na araw ({{first}} – {{last}}) | EN = owner (decision E). `days` = distinct dates in per-date period labels; `first`/`last` = `DatasetOut.data_dates` |
| W3 | `charts.longest_legend_max` | Last column: the largest number among the cashiers on duty in that hour | Huling column: ang pinakamalaking bilang sa mga naka-duty na cashier sa oras na iyon | row max over staffed lanes (§7.4) |
| W4 | `charts.wait_take_plan_shared` | {{time}} has the highest calculated estimate today: {{est}} per customer. Suggested plan, calculated: {{plan}}. | Ang {{time}} ang may pinakamataas na Kalkuladong tantiya ngayon: {{est}} kada customer. Mungkahing plano, kalkulado: {{plan}}. | `Wq_current`, `Wq_optimal`, both analytical (§5.2.4) |
| W5 | `charts.wait_chip_estimate_shared` | Calculated estimate: queueing formula for the shared line ({{model}}) | Kalkuladong tantiya: queueing formula para sa shared line ({{model}}) | `model` = `AnalysisCurrentOut.selected_model` |
| W6 | `charts.key_unavailable_explain_shared` | This run simulates one period at a time, so it has no whole-day total. This is expected, not an error. For whole-day totals, see the full-day run above. | Isang period sa bawat pagkakataon ang simulation na ito, kaya walang kabuuan para sa buong araw. Inaasahan ito, hindi error. Para sa kabuuan ng buong araw, tingnan ang full-day run sa itaas. | the full-day section renders above the older section (`QueueSimulationPage.tsx:147-152`) |
| W7a | `charts.mc_take_shared` | Closest to the {{cap}} cap: {{time}}, with {{rate}} of {{trials}} variations failing. | Pinakamalapit sa {{cap}} cap: {{time}}, {{rate}} ng {{trials}} na variation ang bumagsak. | stored `failure_rate`, `num_trials`, `failure_rate_cap` |
| W7b | `charts.mc_legend_point_shared` | Failure rate in the hour | Failure rate sa oras | one row per period (C5) |
| W7c | `charts.mc_chip_fail_shared` | A variation fails when the counters’ Utilization Rate is above {{threshold}}. | Bumabagsak ang variation kapag lampas sa {{threshold}} ang Utilization Rate ng mga counter. | stored `failure_threshold` (plan target for new runs, 0.75 for old runs: OD-T1) |
| W8a | `charts.level_take_today_shared` | Calculated estimate: every hour is {{levels}}; the line peaks at {{value}} during {{time}}. | Kalkuladong tantiya: {{levels}} ang bawat oras; pinakamataas ang pila sa {{value}} noong {{time}}. | `dayStrip(rows)` |
| W8b | `charts.level_take_plan_shared` | Suggested plan, calculated: every hour is {{levels}}; the line peaks at {{value}} during {{time}}. | Mungkahing plano, kalkulado: {{levels}} ang bawat oras; pinakamataas ang pila sa {{value}} noong {{time}}. | `rho_optimal` (analytical) |
| W9a | `charts.fullday_waiting_take` | Most people waiting at once on day {{day}}: {{max}}, first at {{time}}. | Pinakamaraming sabay na naghihintay sa araw {{day}}: {{max}}, unang naabot noong {{time}}. | `waitingSteps()` of the shown day's playback |
| W9b | `charts.fullday_period_take` | Longest average wait on day {{day}}: {{wait}}, for customers who arrived in {{period}}. | Pinakamahabang average wait sa araw {{day}}: {{wait}}, para sa mga customer na dumating noong {{period}}. | `by_period[].mean_wait_hours`, counted by arrival period (`continuous.by_period_hint`) |
| W9c | `charts.fullday_closing_legend` | Closing time | Oras ng pagsara | `playback.closing.closing_hours` line (`ContinuousRun.tsx:273`) |
| W10 | `charts.level_take_plan_above` | Suggested plan, simulated: {{count}} of {{total}} periods are above the plan’s {{target}} target; the busiest cashier peaks at {{value}} during {{time}}. | Mungkahing plano, simulated: {{count}} sa {{total}} na period ang lampas sa {{target}} na Target ng plano; pinakamataas ang pinaka-abalang cashier sa {{value}} noong {{time}}. | `peak_util` > `target` (strict, as `periodWarnings`); separate only |
| W11 | `charts.longest_take_plan_one` / `charts.longest_take_plan_other` | one: Longest line in the plan’s simulated day: {{count}} person, at {{where}}. other: Longest line in the plan’s simulated day: {{count}} people, at {{where}}. | both: Pinaka Mahabang Pila sa simulated na araw ng plano: {{count}} na tao, sa {{where}}. | `SelectedDesPeriod.results[].max_queue` of the chosen day |
| W12a | `charts.key_basis_no_breaks` | Not the same basis: Current simulates one period at a time; the plan simulates one continuous day. | Hindi pareho ang basehan: isang period sa bawat pagkakataon ang simulation ng Ngayon; iisang tuloy-tuloy na araw ang simulation ng plano. | `RunSummary.basis`; setup has no breaks |
| W12b | `charts.key_basis_per_date` | Not the same basis: Current simulates one period at a time; the plan simulates one continuous run per date. | Hindi pareho ang basehan: isang period sa bawat pagkakataon ang simulation ng Ngayon; isang tuloy-tuloy na takbo bawat petsa ang simulation ng plano. | `runBasisKey` = `simulation.run_basis_continuous_per_date` (`simulationContext.ts:85-91`) |
| W12c | `charts.key_take_same_basis` | Simulated average wait: Current {{current}}, Suggested plan {{plan}}. | Simulated na average wait: Ngayon {{current}}, Mungkahing plano {{plan}}. | both `RunSummary.average_wait_hours`, same basis |
| W13 | `charts.mc_chip_fail_current` | A variation fails when a cashier’s Utilization Rate is above {{threshold}}. | Bumabagsak ang variation kapag lampas sa {{threshold}} ang Utilization Rate ng cashier. | stored `failure_threshold` of the Current run (separate lines; shared Current uses W7c) |
| W14 | — | — | — | not needed (OD-2: card kept) |
| W15 | `charts.clip_text` | This range does not go below 0, because a wait cannot be negative. Where the calculation gave a lower value, 0 is shown. | Hindi bumababa sa 0 ang range na ito, dahil hindi puwedeng negatibo ang wait. Kapag mas mababa ang lumabas sa kalkulasyon, 0 ang ipinapakita. | text given by the parent session (OD-1); same row as App. A |
| W16 | `charts.wait_axis_note_period` | Each row is one period; the axis starts at 0. | Isang period ang bawat row; nagsisimula sa 0 ang axis. | used when the periods are not all 60-minute spans |
| W17 | `results.suggests_wait_separate` | Wait (average of the periods): Calculated estimate {{now}} min → Suggested plan, simulated {{plan}} min. | Paghihintay (average ng mga period): Kalkuladong tantiya {{now}} min → Mungkahing plano, simulated {{plan}} min. | `comparison.current.wait_mean` (analytical), `plan.totals.wait_mean` (simulation); existing words from `results.source_estimate`, `simulation.run_suggested` |
| W18 | `charts.key_basis_separate` | Not the same basis: Current runs the Setup’s periods as one continuous simulation without breaks and stops at closing; the plan runs one continuous day with breaks, and staff finish serving the customers in line at closing. | Hindi pareho ang basehan: iisang tuloy-tuloy na simulation ng mga period sa Setup ang Ngayon, walang break, at humihinto ito sa pagsasara; iisang tuloy-tuloy na araw na may break ang plano, at tinatapos ng mga cashier ang pagsisilbi sa mga nakapilang customer sa pagsasara. | separate only; `_simulate_parallel_segments_core` (one `env.run(until=horizon)`, no breaks); plan day `run_routing_day_des` until `day_end + 24` (`separate_optimization.py:1230`) |
| W19 | `charts.key_basis_no_breaks_separate` | Not the same basis: Current runs the Setup’s periods as one continuous simulation and stops at closing; the plan runs one continuous day, and staff finish serving the customers in line at closing. | Hindi pareho ang basehan: iisang tuloy-tuloy na simulation ng mga period sa Setup ang Ngayon, at humihinto ito sa pagsasara; iisang tuloy-tuloy na araw ang plano, at tinatapos ng mga cashier ang pagsisilbi sa mga nakapilang customer sa pagsasara. | as W18; Setup has no breaks |
| W20 | `charts.key_basis_per_date_separate` | Not the same basis: Current runs the Setup’s periods as one continuous simulation and stops at closing; the plan runs one continuous run per date, and staff finish serving the customers in line at closing. | Hindi pareho ang basehan: iisang tuloy-tuloy na simulation ng mga period sa Setup ang Ngayon, at humihinto ito sa pagsasara; isang tuloy-tuloy na takbo bawat petsa ang plano, at tinatapos ng mga cashier ang pagsisilbi sa mga nakapilang customer sa pagsasara. | as W18; per-date days from `_day_candidate_runner(days=...)`, same day runner |
| W21 | `charts.key_unavailable_explain_separate` | This run does not report whole-day customer totals. This is expected, not an error. Compare with Average wait and Longest Single Line. | Walang kabuuang bilang ng customer para sa buong araw ang run na ito. Inaasahan ito, hindi error. Ihambing gamit ang Karaniwang paghihintay at Pinaka Mahabang Pila. | `_run_summary`: no `admitted`/`in_system_at_close` → only wait and longest line |
| W22 | `simulation.run_basis_continuous_no_breaks` | One continuous run, no breaks | Iisang tuloy-tuloy na takbo, walang break | separate Current run (as W18) |
| W23 | `simulation.chart_waiting_needs_plan_day` | Shown for the Suggested plan’s simulated day. | Ipinapakita para sa simulated na araw ng Mungkahing plano. | the waiting chart is drawn only for a plan's continuous day (`KeyResultsView` `dayTrace`) |
| W24 | `simulation.one_run_notice_separate` | This run simulates the Setup’s periods as one continuous run, without breaks. | Sinisimulate ng takbong ito ang mga period sa Setup bilang iisang tuloy-tuloy na takbo, walang break. | Replay of the separate Current run (as W18) |
| W25 | `charts.mc_take_separate_above` | Highest risk, above the {{cap}} cap: {{time}}, {{lane}}, with {{rate}} of {{trials}} variations failing. | Pinakamataas na risk, lampas sa {{cap}} cap: {{time}}, {{lane}}, {{rate}} ng {{trials}} na variation ang bumagsak. | stored `failure_rate` > stored `failure_rate_cap` |
| W26 | `charts.mc_take_shared_above` | Highest risk, above the {{cap}} cap: {{time}}, with {{rate}} of {{trials}} variations failing. | Pinakamataas na risk, lampas sa {{cap}} cap: {{time}}, {{rate}} ng {{trials}} na variation ang bumagsak. | as W25, shared line |

Plural note for the owner: in TL, i18next picks `_one` for 1, 2 and 3 (`Intl.PluralRules('tl')`). Every TL `_one`/`_other` pair therefore uses the same text with "{{count}} na tao" or "{{count}} customer", which reads for any count.
