# NovaQ Current Handoff

## Compact workflow UX redesign (2026-10-12; U1–U6, step 6 specs, B10, B11/B3/B12, steps 9, 10 and 10b committed; step 11 B4b + addendum committed; steps 12, U8 and U9 + B2 committed; steps 15a, 15b and 15c committed; U10 final verification run 2026-10-13; U10 fixes F3-F15 uncommitted, F1/F2/F16 open; production unchanged)

- Phase U1 (owner GO 2026-10-09): implemented on local branch `feat/ux-u1-shell` (same worktree, branched from `docs/ux-workflow-audit` `7180e34e`) and committed there after the owner approved the phase report (local, not pushed). Frontend only: new sidebar groups (Workspace, Insights, Simulation, Tools), icon-only hide-sidebar button with a remembered icon rail (`novaq_sidebar`), focus/hover tooltips, account menu (email, Settings, Language, Get help, Log out), app header with breadcrumb and theme toggle, `/settings/:section` (Account and sign-in, Appearance, Uploaded files, Users for admins under `RequireRole`), `/tools/calculator`, redirects `/dashboard`, `/datasets`, `/analysis`, `/account`, `/admin`, unknown paths to `/analyses` (signed in) or `/login`, last-used analysis (`novaq_last_analysis`, validated against `GET /analyses`). The Dashboard page was removed (route redirects). Interim until U6/U7: Analysis results, Reports and Queue simulation open the last-used analysis's existing Current, Reports and Simulate pages, else My analyses. Not in U1: Preferences (U2 with B1), Home (U2), the `/onboarding` redirect (U2), workspace-route redirects (U3–U7).
- U1 gates (2026-10-09, this worktree): vitest 65 files / 491 tests passed (baseline before U1: 61 / 449); `tsc -b`, oxlint and `vite build` clean; 12/12 targeted mutants killed; backend unchanged, but `python -m pytest tests/ -x` gave 2897 passed / 123 skipped / 1 xfailed, `ruff check .` and `mypy .` clean. Browser check (built-in browser, local Vite + a scratch SQLite backend with the documented seed admin): 1440, 1024, 768 and 375 px, light/dark, EN/TL, keyboard menu and rail; fixed during the check: sidebar footer overflow, account menu clipped by the sidebar, sidebar links not following a newly opened analysis.
- Phase U2 + B1 (owner GO 2026-10-09): implemented on `feat/ux-u1-shell` after U1 commit `1fe1cc05`, committed there after the owner approved the phase report (local, not pushed). B1: `GET/PUT /account/preferences` in `backend/api/account.py` (session required, CSRF-protected, unknown keys and values over 50 characters rejected, values trimmed, never reads or writes `onboarding_completed`); `/onboarding/*` endpoints and the CSRF exempt list unchanged. Frontend: public Home at `/` (one Start an analysis, two static line pictures, three steps, language dropdown, theme), `auth/intent.ts` (`safeNext`, `continueAfterSignIn`, `novaq_intent` in sessionStorage across registration), `RequireAuth` keeps query and hash, Login/Register/Verify/Forgot/Reset pages get the language dropdown, the onboarding gate, wizard page and client were removed, `/onboarding` redirects to Settings → Preferences, unknown signed-out paths go to `/`. Google sign-in now waits for the signed-in user before leaving the sign-in page (in tests the previous immediate navigation bounced back to `/login`; whether that happened in a real browser is NOT TESTED). Deferred: Quick calculator and Help links in the Home header (public only after U9/B2 and U8).
- U2 gates (2026-10-09): vitest 66 files / 524 tests passed; `tsc -b`, oxlint, `vite build` clean; pytest 2908 passed / 123 skipped / 1 xfailed; ruff and mypy clean; mutants 10/11 killed (the survivor is equivalent: the URL-origin check also rejects `//host`). Browser (local Vite + scratch SQLite backend, seed admin with `onboarding_completed` reset to 0): `/onboarding?replay=1` → Preferences, save stored exactly and left `onboarding_completed` = 0 (read from the database), Home signed out and in, Start → sign in → New analysis, Register keeps the intent, 375 px and 1280 px, dark, Tagalog.
- Phase U3 (owner GO 2026-10-09): implemented on `feat/ux-u1-shell` after U2 commit `d8e1b0df`, committed there after the owner approved the phase report (local, not pushed). Frontend only. My analyses: search over name, location and service type (`?q=`, client-side), structure filter in Home wording (`?structure=`), count text, structure badge in Home wording, operating window shown only when time segments are saved (nothing inferred otherwise; spec §7.4's "Window not set yet" text was not used because analyses with uploaded data but no segments would be described wrongly), archive behind an accessible confirmation dialog whose text states the verified effect (hidden from the list, no new uploads, data kept, no restore button). New analysis: Home line pictures as radio cards, two-question helper inline (same `recommend` rule as Guided setup, now in `frontend/src/lib/structureRecommendation.ts`), "Create and decide later" keeps the earlier unknown-structure option. Create still opens `/analyses/:id/setup` until U4 adds `/data`.
- U3 gates (2026-10-09): vitest 67 files / 537 tests passed; `tsc -b`, oxlint, `vite build` clean; 12/12 mutants killed; pytest 2908 passed / 123 skipped / 1 xfailed (no backend change); ruff and mypy clean. Browser: helper selects the recommended structure, create with counter names, search restored from the URL, archive dialog (focus on Cancel, confirm, focus to search), 375 px.
- Phase U4 + B9 (owner GO 2026-10-09): implemented on `feat/ux-u1-shell` after U3 commit `855b1d15`, committed there after the owner approved the phase report (local, not pushed). Frontend only. The Setup page became "Data and setup" at `/analyses/:id/data` (`/setup` redirects with query and hash; the workflow step path is now `data`). Same state, mutations, upload/preview/confirm flow and cache resets; the four existing Setup test files pass unchanged. Numbered steps: Get the template, Add your data (with "This file will become the data for your plans and simulations."), Review what NovaQ read (read summary + Why this model), Advanced settings (the existing form, closed unless the structure is unknown), Download my current setup (separate). Make periods (separate segments, 1–24 periods of 15/30/60 minutes, same day; writes the form only). B9 "Enter numbers without a file" (shared lines only, one-hour rows) builds the template CSV and uploads it through the normal path as `entered-by-you`. Not shown yet: step "At closing time" (waits for the B4a spec). Plan task 4.6 VERIFIED: shared aggregate rows of unequal length are not duration-weighted in costs or totals (spec §8); not changed (protected math).
- U4 gates (2026-10-09): vitest 70 files / 571 tests passed (a first full run overlapped with the mutation run, which rewrites source temporarily, and showed 2 CSV failures; the source was confirmed clean and a clean rerun passed); `tsc -b`, oxlint, `vite build` clean; 12/12 mutants killed; pytest 2908 passed / 123 skipped / 1 xfailed (no backend change); ruff and mypy clean. Browser: `/setup` → `/data`, manual entry upload accepted by the local backend (dataset `entered-by-you`, 2 rows, valid; M/M/c Wq 9.5701 and 9.8609 min, the second recomputed independently with Erlang C), Make periods.
- Phase U5 (owner GO 2026-10-09): implemented on `feat/ux-u1-shell` after U4 commit `c2920058`, committed there after the owner approved the phase report (local, not pushed). Frontend only. Optimize became "Suggested plans" at `/analyses/:id/plans` (`/optimize` redirects keeping query and hash); the analysis header has "Data and setup | Suggested plans" tabs (links that are routes). Optimizer requests and save payloads are unchanged. "Use this plan" saves exactly what "Save without using" saves, then calls the existing selection endpoint; if the server refuses the selection the plan stays saved and the reason is shown with "You can select it on the Compare page" (Compare stays until U6). Break apply uses the accessible confirmation dialog instead of `window.confirm`. Disclaimers verified from code: shared = lowest modeled cost among options meeting the limits (`optimization.py`, every count from min to max servers); separate = lowest simulated average cost among feasible options (`separate_optimization.py:1557, 2037`); breaks = local improvement from one-at-a-time greedy moves (`break_optimization.py:131-194`). Defaults are shown as "Assumptions you can change" from `planning-defaults.json`. Pre-existing defect fixed: the heading key `optimize.advanced_settings` was missing from both locales (shown raw, also on `origin/main`); now "Assumptions and limits".
- U5 gates (2026-10-09): vitest 70 files / 578 tests passed (clean run; an earlier run failed one test only because I edited a test and a locale file while it ran); `tsc -b`, oxlint, `vite build` clean; 10/10 mutants killed after tightening one assertion to `toBeVisible()`; pytest 2908 passed / 123 skipped / 1 xfailed (no backend change); ruff and mypy clean.
- U5 browser check (local Vite + scratch SQLite backend): signed out deep link `/analyses/3/optimize` → sign in → `/analyses/3/plans` with tabs; optimize on the `entered-by-you` data; "Use this plan" → `GET /workflow` reports selection "U5 browser plan" with provenance `verified_snapshot`. The break dialog was not browser-checked (no separate analysis with break data in the scratch database); it is covered by tests.
- Plan step 6 (owner GO 2026-10-09): the five own specs are written and approved (`docs/superpowers/specs/2026-10-09-b10-planning-vs-review-file.md`, `2026-10-09-b4a-continuous-shared-run-preview.md`, `2026-10-09-b4b-recorded-service-times.md`, `2026-10-09-b4c-shared-line-breaks.md`, `2026-10-09-b8-reports-pdf-excel.md`), committed after the owner's approval (local, not pushed). Owner answers: B10 new `datasets.purpose` column, fixed at upload, planning screens refuse review files; B4a closing rule in a separate nullable analysis column, named-run limits reused (provisional), 5 repeats by default; B4b resample recorded durations per period, nearest-period fallback, §5 acceptance checks; B4c per-counter shared break schedule, the named run's approved break rules, simulation only; B8 live formulas for M/M/1, M/G/1, M/M/c, M/G/c with helper columns, optimizer candidates added, Python re-computation plus one manual Excel check. OD-UX-11 (Decision sentences) and OD-UX-13 (continuous-run pass/fail rule) stay open.
- Plan step 7, B10 (owner GO 2026-10-09): committed `598658e6` on `feat/ux-u1-shell` after the owner's approval (2026-10-12; local, not pushed). Migration **0006** adds `datasets.purpose` (`planning`/`review`, not null, default `planning`, CHECK constraint), in place on both dialects (no SQLite table rebuild, so the 0005 generation guards stay installed). The resolver (`backend/api/current_dataset.py`) now picks the highest-id valid **planning** dataset and reports `no_planning_dataset` when only review files exist; endpoint error messages are unchanged. Upload takes `purpose` (`planning` default; `review` + `apply_setup` → 422 `review_cannot_change_setup`); dataset responses carry `purpose` and `is_current`; the separate optimizers and the named shared run refuse review files (422 `dataset_not_for_planning`). Frontend: Data and setup asks "This file is for: Use for planning / Review only" with no preselection; a review upload skips the Setup preview and refreshes only the dataset list; cached results follow `is_current`; Suggested plans list planning files only; Uploaded files show the purpose. Migration tests that hard-coded `0005` as the head now use the code's head or stop at 0005 when they test 0005 itself; the startup-guard tests' fake "newer" revision is now `0099`.
- B10 gates (2026-10-09): pytest 2924 passed / 123 skipped / 1 xfailed (16 new B10 tests); ruff and mypy clean; vitest 71 files / 588 tests; `tsc -b`, oxlint, `vite build` clean; 15/15 mutants killed (9 backend, 6 frontend). **PostgreSQL migration and tests were NOT TESTED** (no PostgreSQL test database in this session; `tests/test_postgres_migration_chain.py` skipped). Browser (scratch SQLite migrated 0005 → 0006): the existing file became planning and the selected plan stayed `CURRENT`; a review-only upload was stored as `review`, not current, `/current` still read the planning file, the plan stayed `CURRENT`; Suggested plans listed only the planning file; Uploaded files showed "Review only" and "Planning (current)".
- **Production:** migration 0006 must be applied deliberately before code that uses it starts (G8 runbook; the production schema guard refuses a database not at the code's head). Nothing was migrated or deployed outside the scratch database.
- Plan step 7, B11 + B3 + B12 (owner GO 2026-10-12): committed `864dff87` on `feat/ux-u1-shell` after the owner's approval (local, not pushed); no migration. **B11**: customer-record uploads store `{"first", "last"}` arrival dates (UTC, the clock of the period labels) in `validation_report_json["data_dates"]` at ingestion (`backend/data/analysis_ingestion.py`, both upload paths); `backend/data/data_dates.py` exposes `data_dates` on every dataset response (`source` = `stored_at_upload`, or `period_labels` when recovered from NovaQ's own per-date labels of earlier customer-record datasets); aggregate files and earlier representative-day datasets give null ("Data period unavailable"); filenames are never read. **B3**: `GET /analyses/{id}/current` and `GET /analyses/{id}/workflow/observed-wait` take optional `dataset_id` (`reviewable_dataset` in `backend/api/analyses.py`: other owner, other analysis or missing → 404 "Dataset not found in this Analysis."; not successfully processed → 409 `dataset_not_processed`; review files allowed, read-only); `/current` now reports the real `is_current` for a named file; omitted, both read the planning file as before. Evidence, selection and Decision endpoints are unchanged. **B12**: `/current` adds `arrivals_by_period` (customers per hour, every line summed on the server; a period with an unknown rate is null, never a partial sum) and `busiest_period` (most arrivals per hour, first on a tie). For per-date customer-record files each period is one date and hour. Served/unserved simulation totals were left for the simulation phases (B5/U7), the screens that show them. Frontend: `getAnalysisCurrent(id, datasetId?)`, `getObservedWait(id, datasetId?)` and the `DataDates`/`PeriodArrivals` types; no screen uses them yet (U6).
- Step 7 B11/B3/B12 gates (2026-10-12): pytest 2949 passed / 123 skipped / 1 xfailed (25 new: `tests/test_b11_data_dates.py`, `tests/test_b3_results_for_any_file.py`); ruff and mypy clean; vitest 72 files / 590 tests run alone (an earlier run alongside the backend suite reported 1 unattributed error; the alone run had none), `tsc -b`, oxlint and `vite build` clean; 16/16 mutants killed. PostgreSQL NOT TESTED. Scratch API check (local SQLite, seed admin, new analysis 4): planning and review customer-record uploads stored their dates (Sept 8–9 planning, Mar 2–4 review); `/current` and observed-wait with the review file's id read that file (`is_current` false) while the default stayed on the planning file; the review file's id under another analysis → 404.
- Plan U6, Analysis results (owner GO 2026-10-12): committed `c09ce3cc` on `feat/ux-u1-shell` after the owner's approval (local, not pushed). New page `frontend/src/pages/ResultsPage.tsx` at `/results?analysis=:id&file=:datasetId&period=&line=` (spec §5, §7.7), built from `frontend/src/components/results/` (FileSelector, KeyResults, BusyStrip, ResultsCharts, PlanChanges, ResultsDetails, useSelectedPlan) and `frontend/src/lib/results.ts`. "View results from" lists every successfully processed file with Data covers (B11), Uploaded on and its tag; the planning file is read exactly as before, any other file through B3 `dataset_id`, with the D18 banner, and never requests workflow, scenarios, separate comparison or selection. Key results: recorded wait (customer records only), estimated wait (the server KPI; for one shared line it leaves out periods where counters can't keep up and says how many), period that needs attention (can't-keep-up first, then highest estimated wait), busiest period (B12 server field). Busy-level strip with legend and ranges; clicking a period puts it in the address and shows its numbers; warnings name the level and, only with a selected current plan, "above this plan's target". Charts: customers per hour (B12 `arrivals_by_period`), recorded vs estimated wait (customer records), cashier-line workload (separate lines; one shared line says so). "What the plan changes" and the level-1 "Calculated result · not yet checked by simulation" card appear only for the planning file once a plan is selected; a plan that is not CURRENT shows only its name and reason (4d), and the switcher offers only verified, CURRENT, complete plans (separate: valid and not stale). `/analyses/:id/current` and `/compare` redirect to `/results?analysis=:id`; the old Current and Compare pages and their tests were removed (49 cases; the stale-plan cache case was ported to Results). The sidebar and the step bar (now 6 steps: Data and setup, Suggested plans, Analysis results, Simulate, Decision, Reports) link to `/results`; Simulation links that pointed at Compare now point at Suggested plans. Deviations to confirm: the cost line is "Total cost (counters and waiting)" from the saved plan rows because no staff-only cost field exists (D20 says staff cost); the card links "Go to Reports" because the plan report is B8; older files use today's Setup although D18's banner says "inputs saved with this file"; the multi-plan comparison chart of the old Compare page is gone (OD-UX-4).
- U6 gates (2026-10-12): vitest 72 files / 557 tests run alone (49 old Current/Compare cases removed; 12 Results page, 6 helper and 2 redirect cases added), `tsc -b`, oxlint and `vite build` clean; 16/16 mutants killed (F15, the strip taking the busiest line, survived the first run and is killed after a stronger strip test). Backend unchanged since `864dff87`. Browser (scratch SQLite, seed admin, analysis 4): planning file showed Sept 8–9 dates and key results; the review file showed the banner and March values, and a fresh load of it made only auth/me, analyses, analysis, datasets, current?dataset_id=4 and observed-wait?dataset_id=4 requests; after "Use this plan" in Suggested plans the page showed the calculated result (2 → 1 counters, ₱379.37 → ₱217.92) and the plan table; a period click set `period=` and showed its numbers; 375 px width had no sideways scroll. Dark mode NOT checked by eye (the app theme switch overrides the emulated system setting).
- Plan step 9, B5 + U7a Queue simulation (owner GO 2026-10-12): committed `ddf03de2` on `feat/ux-u1-shell` after the owner's approval (local, not pushed); no migration and no change to any simulated number. **B5**: VERIFIED that the stored separate-lines day trace already carries `draining_start`, `break_start` and `break_end` from the one continuous-day execution (`tests/test_b5_break_events.py`: each break once and in order; the period traces equal that one execution's events; the trace cap never changes the numbers). Additive fields only: `run_routing_day_des` reports `in_system_at_close` (a read-only process; outputs byte-identical before and after on a scratch snapshot), day periods carry `start_hours`, and every DES run (Current, legacy shared, selected plan) stores a server `summary` (`_run_summary` in `backend/api/workflow.py`: served-weighted average wait, null when any served period's wait is unknown; longest line; arrivals, served and still in line at closing only for one continuous day, never added up from per-period runs). **U7a**: `frontend/src/pages/QueueSimulationPage.tsx` at `/simulation/results|replay|checks?analysis=&plan=current|suggested[&mode=named]`, built from `frontend/src/components/queueSimulation/`: run switch Current | Suggested plan; run bar (operating hours, the separate-lines closing rule without a Change link because its one allowed value is `drain_existing` (`backend/api/analysis_schemas.py:44`), Not run / Running / Done, Run full operation, Advanced settings with labelled defaults, and a break notice: a plan run with one period per calendar date understates breaks, the Current and legacy shared runs leave them out (`simulation.py` has no breaks)); Key results (four cards Current → Suggested from the server summary, the conservation line, the waiting-through-the-day chart for a continuous day only, wait by period, More results); Replay (representative-day separate plans replay the whole day from the one execution with a store clock, Go to time and `t=` in the address; per-date and legacy runs say they replay one period at a time; Closed from `inactive_queue_ids`; scheduled breaks on their own timeline row; Finishing customers before break / On break / Serving / Available from events only, never inferred from idle; "Break state unavailable for this run." when events are absent; a cut-short notice); Checks ("Check the plan" runs Monte Carlo → validation → Decision in that order; legacy and Current checks kept). `/simulation` opens Key results; `/analyses/:id/simulate[?mode=named]` redirects keeping named mode; named mode renders the existing named view unchanged and requests no workflow. The old Simulate page and its two test files were removed (cases ported to `frontend/src/pages/QueueSimulationPage.test.tsx`). A run whose periods the legacy DES cannot simulate (for example M/G/c) is still withheld by the server; the run bar now lists those reasons instead of showing "Not run". Owner review 2026-10-12: the four headline cards and one "Check the plan" button are D30, not deviations; replay speed is unchanged until the D29 base rate is decided (recommended 1× = 1 simulated minute per second, because today 1× plays any trace in 60 s); the closing rule is shown for separate lines only (shared lines get theirs with B4a); "Longest single line" and "People waiting, all lines together (checked every 5 minutes)" name what each number counts; legacy shared plans with service-time variance (M/G/c) stay refused by the legacy DES until B4b.
- Step 9 gates (2026-10-12): pytest 2960 passed / 123 skipped / 1 xfailed (11 new in `tests/test_b5_break_events.py` and `tests/test_simulation_summary.py`); ruff and mypy clean; vitest 73 files / 565 tests run alone, `tsc -b`, oxlint and `vite build` clean (the >500 kB Plotly chunk warning is pre-existing); 29/29 mutants killed (B2 and B5 survived the first run and are killed after two added assertions; three more cover the browser-check fixes below, five the break notice and labels). Browser (scratch SQLite, seed admin): `/analyses/4/simulate` redirected; analysis 3's Current run showed the server cards with customer totals marked unavailable (per-period run); a new analysis 5 (separate lines, representative day 08:00–10:00, lane A break 09:15 for 15 min, plan selected) showed average wait 3.3 min, longest line 4, served 45, 1 still in line at closing, and in Replay lane A was Finishing customers before break at 09:13, On break at 09:20 and Serving at 09:40, with the accounting identity holding (32 = 30 + 1 + 1). Dark mode (app theme switch) checked by eye on Key results, Replay and Checks. At 375 px no page and no main area scrolls sideways, after two fixes found in this check: the per-period lane tables in Checks (carried over from the old Simulate page) now scroll in their own labelled box, and the full-day replay header, which named the first period ("08:00") while the clock was in the 09:00 period, now shows the day's hours ("08:00–10:00"). Both waiting numbers count people waiting, not being served: the chart adds all lines sampled every 5 minutes (peak 6 in this check), the card is the exact longest single line (4); the labels now say so.
- Pre-existing engine issue found in step 9 (VERIFIED from code and by a run of NovaQ's own engine; not fixed): per-date separate-lines runs, both the optimizer (`separate_optimization.py:1870`) and the selected-plan check (`backend/api/workflow.py:2346`), simulate each period alone for the DES horizon (default 24 h, `DES_DEFAULT_DURATION_HOURS`) and place the breaks a period owns at their offset from the operating day's start (`period_des_breaks`, `separate_optimization.py:789`). The main error is dilution, not timing: a break is a small share of a 24 h run. Proof run (SYNTHETIC fixtures of `tests/test_separate_day_feasibility.py`: two lanes, 4.5/h each, mean service 6 min, lane B on break 11:00-12:00; 30 seeds): lane A in the 11:00 hour had utilization 0.477 and wait 1.86 min with today's method, 0.477 and 1.68 min with the break timing corrected only, and 0.749 and 8.34 min as one continuous day (9.03 arrivals; busy time 1.328 h over 11:00-12:00 equals the 1.33 h of arriving work); the continuous day also shows the carry-over into 12:00 (wait 1.71 vs 1.14 min) and simulated 845 customers instead of 19,876 (0.10 s vs 1.62 s on this PC; Render NOT TESTED). Basis: period-by-period stationary models (SIPP) can miss targets through the day and peak congestion lags the arrival peak (Green, Kolesar and Soares, Operations Research 49(4), 2001; Green, Kolesar and Whitt, POM 2007); a store that opens and closes is a terminating simulation (WSC output-analysis tutorials after Law and Kelton). PROPOSED core enhancement B13: simulate each date as one continuous day with the existing day DES, in the optimizer and the check alike; own spec and owner GO first, not part of step 10. Until then the Queue simulation run bar says so (below). Representative-day runs are not affected.
- B13 spec (2026-10-12): `docs/superpowers/specs/2026-10-12-b13-per-date-continuous-day.md`, approved by the owner with the recommended answers (basis-specific engine version: representative-day v2 stays current, per-date plans need v3; refuse a date that cannot be laid out; uploads without operating segments keep today's method with the notice). It extends the representative-day fix ("Finding K", `9b1f95a4`) to per-date plans and resolves known limitation K1. Plan step 10b, after step 10. A day-wide staffing search (B13b, after the ISA of Feldman, Mandelbaum, Massey and Whitt, 2008) is a later option with its own spec.
- Plan step 10, B4a + U7b continuous shared-line run (preview) (owner GO 2026-10-12): committed `7f4c5cd0` on `feat/ux-u1-shell` after the owner's approval (local, not pushed). **Backend**: migration `0007` adds `analysis_projects.shared_closing_policy` (`DRAIN`, `HARD_CUTOFF` or null; added in place with a CHECK constraint; outside the Setup fingerprint, OD-B4a-1 A). New adapter `backend/api/shared_continuous.py`, the second module allowed to import the shared-queue enhancement modules (the isolation guard in `tests/test_shared_segments.py` now names both adapters): `GET`/`PUT /analyses/{id}/closing-policy`; `POST /analyses/{id}/continuous/compatibility` for both staffing sources (Current = the current planning dataset's `c`; Suggested = the selected CURRENT plan's `c_optimal` through `_segments_for`) with reasons `separate_lines`, `not_shared_line`, `capacity_or_abandonment`, `service_time_variation`, `timeline_invalid` (the engine's own messages), `no_planning_dataset`, `no_selected_plan`, `plan_inputs_invalid`, `no_closing_policy`, plus the operating hours and expected customers per day; `POST .../continuous/runs` (repeated days 1-9, default 5; seed default 42; refused before simulating when expected customers x repeated days exceed 2,900, after simulating when the result exceeds `RESULT_JSONB_MAX_BYTES`; archived analyses refused) persists one Job `shared_continuous_preview` with the dataset and plan ids and generations, the closing rule used, engine and method versions, root entropy, inputs digest, Setup hash and `limits_status`; `GET .../runs` and `GET .../runs/{id}` report `setup_matches_current`, `dataset_is_current` and `plan_is_selected`; `GET .../runs/{id}/replications/{i}/playback` regenerates that day from the stored seed, checks it against the stored row (`playback_from_replications`) and adds arrivals, served, not served and mean wait per period of that day. The engine, its pin tests and its boundary tests are unchanged; no verdict is produced (OD-UX-13 open). **Frontend (U7b)**: on shared lines the Queue simulation pages show the "Full-day run" first (`frontend/src/components/queueSimulation/ContinuousRun.tsx`, `frontend/src/api/continuous.ts`, `frontend/src/lib/continuous.ts`): run bar with operating hours, the closing rule (chosen inline when none is saved, then a summary with Change, future runs only), Run full operation, preview label and explanation, refusal reasons, notes when the Setup, data or plan changed after a run, and Advanced (repeated days, seed); Key results with four cards Current -> Suggested from each run's own summary (customer-weighted average wait with the lowest and highest day, longest line, served, not served at closing), the two charts and a per-period table of one chosen repeated day; Replay of a chosen repeated day on the store clock with Go to time, the line and counters read from that day's events; Checks says no Decision is made from the full-day run and lists the ranges. The older period-by-period run stays below, under "Period-by-period run (older method)", with its button renamed "Run period by period". Separate lines are unchanged. Also fixed: the waiting-chart caption "1 people waiting" now reads "most waiting at once: 1" (both charts). Deviations to confirm: the charts and the per-period table describe one repeated day (picker), while the cards average all repeated days; replay speed semantics unchanged (D29 open); the simulation mode switch still calls this mode "Legacy shared queue simulation".
- Step 10 gates (2026-10-12): pytest 2987 passed / 123 skipped / 1 xfailed (27 new: `tests/test_b4a_continuous_preview.py` 24, `tests/test_b4a_migration.py` 3; the PostgreSQL chain's head pin moved to `0007`, PostgreSQL NOT TESTED); ruff and mypy clean; vitest 74 files / 580 tests run alone, `tsc -b`, oxlint and `vite build` clean; 35 mutants: 34 killed and 1 equivalent (dropping the dataset id check leaves the generation check, and generations are unique per dataset row); B16 was killed after an added request for a missing analysis. Browser (scratch SQLite migrated to `0007`, seed admin): analysis 6 (shared line, counts per period 08:00-11:00) asked for the closing rule first, then ran Current: average wait 4.5 min (0.8-7.3), longest line 8 (3-11), served 86.2, none unserved, equal to `run_shared_replications` called directly with the same inputs and seed (4.53 min, 0.75-7.30, 8.0, 86.2). Analysis 7 (stable current staffing; plan saved and selected through Suggested plans) ran Current and Suggested with the stop-at-closing rule (average wait 0.4 vs 0.7 min; 0.2 customers a day not served for the plan; the same arrivals in both because they share the seed); the replay at 09:30 showed 43 arrived = 41 served + 2 serving + 0 waiting; light and dark mode checked; at 375 px no page or main area scrolls sideways. Run time on Render NOT TESTED; the limits stay provisional (OD-B4a-2 A). Note from the check: "Use this plan" on Suggested plans is disabled until the plan has a name.
- Plan step 10b, B13 per-date separate-lines plans as one continuous day per date (owner GO 2026-10-12): committed `94ba3a25` on `feat/ux-u1-shell` (local, not pushed); no migration. **Engine** (`backend/queueing_engine/services/separate_optimization.py`): `per_date_continuous(setup)` (separate lines, `event_period_basis` recorded as `per_date`, operating segments that lay out a day; a Setup that records no basis is never guessed to be per-date), `per_date_days` (groups periods by the date of NovaQ's per-date label and the row `segment_id`; refuses a date that has no records for a configured segment, naming both, OD-B13-2), `_day_candidate_runner(..., days=)` runs each date as its own day from empty (the representative-day path is unchanged and its tests pass as before), `date_seed` gives each date its own seed (date 0 keeps the replication seed; stride 1,000,003) so dates with equal inputs are independent samples. **Versioning (OD-B13-1 Option B)**: `separate_engine_version(setup)` is `novaq-2026-10-separate-des-v3` for per-date-with-segments and `novaq-2026-09-separate-des-v2` otherwise; `POST .../workflow/optimize/separate` returns it (additive `engine_version`) and the Suggested plans page saves it instead of a hardcoded value; save verification (`scenarios.py`) requires it; a per-date plan saved with v2 is reported `HISTORICAL_REQUIRES_RECALCULATION` (`VERSION_HISTORICAL`, "calculated with the earlier per-date method ...") and cannot be selected; representative-day v2 plans stay CURRENT. **Selected-plan check** (`backend/api/workflow.py` `_run_selected_plan_day_des`): per-date plans run one continuous day per date, each period's `start_hours` on its own date's clock, day totals added up on the server plus a `days` list per date. Monte Carlo loads and validation use the same entry point. Per-date uploads without operating segments keep the 24 h period runs and the run-bar notice (OD-B13-3). Report wording now says each date is its own day when the data has one period per calendar date. **Frontend**: run bar "One continuous run per date", no break notice for these runs, a note that customer totals add up all dates, and a Date picker (kept in the address as `date=`) for the waiting chart and the full-day replay of one date. Known limitation K1 is resolved for per-date plans with operating segments.
- Step 10b gates (2026-10-12): pytest 2997 passed / 123 skipped / 1 xfailed (new: tests/test_b13_per_date_day.py 4; tests/test_separate_day_feasibility.py replaces the two K1 pins with 7 B13 tests; step 9 per-date tests moved to dated fixtures); ruff and mypy clean; vitest 74 files / 584 tests run alone, tsc -b, oxlint and vite build clean; 20/20 mutants killed. Budget (spec §7, SYNTHETIC 7 dates x 12 hourly segments x 4 lanes, default 5 replications, this PC): optimizer 4.8 s and 11.7 MB peak with B13 against 50.5 s and 61.2 MB with the old 24 h period runs; Render NOT TESTED. Browser (scratch SQLite, seed admin): analysis 8 (two dates, three hourly segments, lanes A and B, lane A break 09:30-09:45) was optimized and its plan saved with `novaq-2026-10-separate-des-v3` through Suggested plans; the Queue simulation run showed "One continuous run per date", no break notice, the two-date note and Date picker; the replay of 2026-09-09 at 09:40 showed lane A On break and lane B Serving. The check first showed both dates with identical arrivals (same seed per date); that design flaw was fixed with `date_seed` before these gates.
- Plan step 11, B4b recorded service times in the full-day shared run (owner GO 2026-10-12): implemented on `feat/ux-u1-shell` after `94ba3a25`, uncommitted (OD-B4b-3 resolved below). **Engine** (`shared_continuous_des.py`): optional `service_samples` (recorded durations per demand period); each customer draws a quantile u once from its own third stream (`SeedSequence.spawn(3)[2]`; arrivals equal the exponential engine's for the same seed) and service lasts the sorted recorded duration at floor(u x n) of the period where service starts (a uniform draw with replacement, OD-B4b-1 A); after closing the final period's durations; a period without recordings borrows the nearest earlier, else later, period and is listed in `service_fallbacks` (OD-B4b-2 A); engine version `novaq-shared-continuous-des-v2+recorded-v1`; without `service_samples` the output is unchanged (pin test and 120 engine tests pass unchanged). `shared_replications` and `shared_playback` pass the durations through and store them in `provenance.inputs.service_samples_hours`; playback refuses a run whose durations do not match its version. **Adapter** (`backend/api/shared_continuous.py`): a customer-record upload (rows with `service_time_source` = empirical) is laid out on the Setup's operating segments; a segment without customers gets arrival rate 0, the fallback durations and the Setup's fixed counter count for Current staffing, while a plan run names it (`plan_missing_periods`) and does not run; durations too large to store are refused before simulating (413); compatibility and runs report `service_model` and `service_fallbacks`. **Frontend**: the run bar says "Uses your recorded service times." or "Uses estimated service times (counts per period)." (only when the run can go), names borrowed periods, and the preview text no longer says recorded times come later.
- OD-B4b-3 (BLOCKER, VERIFIED 2026-10-12 in the browser): the adapter runs customer records only on the Representative day basis, but Setup validation refuses that basis for shared lines (`backend/api/analysis_schemas.py:151`, "The representative day basis is only supported for separate queues."), so every real shared customer-record upload is per-date and is refused (`per_date_data`). The B4b spec section 2 cited representative-day pooling without this constraint; the API tests wrote the Setup to the database directly and did not catch it. Options: A allow Representative day for shared lines (Setup validation, the Setup page control, ingestion, `data_dates.py`, `setup_derivation.py`, `workflow.py:1976` to check); B run one chosen calendar date per full-day run; C both. Owner chose A on 2026-10-12 and approved the addendum `docs/superpowers/specs/2026-10-12-b4b-addendum-shared-representative-day.md` (OD-B4b-A1; OD-B4b-A2 = reuse the separate-lines wording). Implemented: Setup validation accepts Representative day for shared or separate lines (single-server and unknown still refused); the Setup page shows the basis control and segment times for shared lines (counter lists stay separate-only, shared segments keep `active_queue_ids` null). Two tests now go through the public routes only (create, upload, run; and Suggested plans, period-by-period run, Monte Carlo, data dates, observed waits). Browser (scratch analysis 9, SYNTHETIC 136 customers over 3 dates, 4 segments, none after 11:00): the Setup page shows the basis and four segments; full-day run 39 used `novaq-shared-continuous-des-v2+recorded-v1`, s4 borrowed s3 (named on the page), 229 arrivals = 229 served over 5 repeats.
- Step 11 checks (2026-10-12): B4b tests 34 (`tests/test_b4b_recorded_service.py`: exact checks 2-6, statistical checks 7-10 with fixed seeds, API); mutants 24/24 killed; statistical check 8 (8 h, 400 repeats): exponential 30.649 min (SE 1.376) vs recorded 31.614 min (SE 1.472); check 10 (24 h, 4 counters, gamma durations): simulated 4.862 min vs M/G/c 5.952 min (ratio 0.817, reported, not asserted equal). Budget (SYNTHETIC, 2,902 customers, 5 repeats, this PC): recorded 2.19 s, 1.3 MB peak, 189,230 bytes stored against exponential 0.73 s, 0.9 MB, 16,901 bytes; at full float precision about 37,800 recorded durations fit Render's 786,432-byte cap (REPORTED cap), so larger uploads are refused with 413 (storing a hash instead is PROPOSED). Render NOT TESTED.
- Step 11 committed `e26d82e3` (local, not pushed). Step 12 (B4c, owner GO 2026-10-12): the approved B4c spec assumed counters keep fixed numbers, but the continuous engine closes idle counters first (`shared_continuous_des.py:351-352`), so numbered breaks cannot be built without changing existing results. Owner answered OD-B4c-4/5/6 = A (a break takes any free counter, first free first; a counter on break still counts as staffed; a break a plan cannot staff refuses that run). Addendum `docs/superpowers/specs/2026-10-12-b4c-addendum-anonymous-counter-breaks.md` APPROVED (OD-B4c-A1) and implemented, uncommitted. **Setup**: `counter_breaks` (start, minutes, optional name) for shared lines only, omitted when empty so untouched Setups keep their fingerprint; Setup page "Counter breaks" editor; Suggested plans says suggested counters do not account for them. **Engine** (`shared_continuous_des.py`, optional `counter_breaks`): due breaks wait first in, first out and go to the lowest-numbered free counter before waiting customers; full length from the actual start; a counter on break counts as staffed (drops close idle, then on-break, then drain busy); at closing a break in progress ends and a due one is cancelled; break time counts as present, not busy; `+breaks-v1` engine suffix; events `break_due`, `break_start`, `break_end` (completed, staffing_change, truncated_by_closing), `break_cancelled_at_closing`; runs without breaks unchanged (pin test). Replications and replay pass the breaks through; the replay checker enforces the rules and shows On break and Breaks waiting. **Adapter**: a break outside the operating hours, or more breaks under way than counters at its start, refuses that staffing source's run and names the break. Tests: `tests/test_b4c_counter_breaks.py` (25, hand-computed exact cases, seeded replays with and without recorded service times, a real-route test); mutants 26/27 killed, 1 equivalent (zero minutes, blocked by the field's min=1 and the API's gt=0). Browser (scratch analysis 9, seed admin): break 09:15 for 30 min saved through the Setup page; run 40 used `novaq-shared-continuous-des-v2+recorded-v1+breaks-v1`, same 229 arrivals as run 39, all served; day 0 break due 09:15, started 0.002 h later on counter 1, ended 0.5 h after its start; replay at 09:30 showed 1 on break, 1 serving, 11 waiting; run 39 marked "Data and setup changed after this run".
- Status: design approved by the product owner (decisions D1–D33); U1–U6, the step 6 specs, B10, B11/B3/B12, steps 9, 10, 10b, 11 and 12 committed (12 = `b2a667a8`); step U8 implemented locally, uncommitted; later phases not implemented.
- Plan step U8, Help center (owner GO 2026-10-12): implemented on `feat/ux-u1-shell` after `b2a667a8`, uncommitted. `/help` and `/help/:topic` are public (spec §5): `HelpShell` shows them inside the app when signed in and in the Home page frame otherwise; every guide is public (none holds account data). Eight guides (spec §7.11: starting, data, results, plans, simulation, checks, downloads, problems) including the plan's "Reviewing older files", "Planning vs review-only files", "Closing time" and "Reading the simulation"; each states What to do, Why and Next step; every sentence was checked against the code or an existing label (e.g. the rate-limit text from `backend/api/deps.py:65`). Search matches every word of the query over guide and section text in the current language. Contextual "?" links (beside, not inside, the heading) on Data and setup (and its file-purpose and period-basis fields), Analysis results, Suggested plans, Queue simulation (Checks opens the checks guide, Replay the reading section), the full-day run and its closing rule, and Reports. Home links to Help. Five unused help strings removed from both locales. Downloads describes today's Reports; it must be updated with B8 (Phase 15). Screenshots deferred to U10 (plan). Checks: 6 Help tests plus link assertions; mutants 9/9; gates pytest 3060p/123s/1xf, vitest 599, tsc, oxlint, build clean. Browser (scratch app): signed out, /help shows the public frame and all eight guides; search "closing time" links to /help/simulation#closing, which opens scrolled to that section; the Filipino text renders; signed in, Help shows inside the app and the Checks page's "?" opens /help/checks. The scroll to a #section inside the signed-in app is NOT VERIFIED: the browser pane was hidden and ignored every scroll call, even window.scrollTo. Production, Render, Pages and Supabase are unchanged; nothing was pushed or deployed.
- Documents: `docs/superpowers/specs/2026-10-09-compact-workflow-ux-redesign.md` (audit, decisions log, screens, metric dictionary, backend items B1–B12), `docs/superpowers/plans/2026-10-09-compact-workflow-ux-redesign-plan.md` (16-step order), mockups in `docs/superpowers/specs/assets/`.
- Git: local branch `docs/ux-workflow-audit` (worktree `.claude/worktrees/ux-workflow-audit`, based on `origin/main` `6093d78a`): commit `477ce274` (spec, plan, mockups); Phase 0 documentation (MASTER 1.1 amendments, newline repair of MASTER and the 2026-09-13 product-decisions spec, these `memory.md`/`handoff.md` entries) follows on the same branch. Not pushed.
- The main checkout's local `main` was 78 commits behind `origin/main` on 2026-10-09; branch any implementation from a fresh `origin/main`.
- Verification: documentation and mockups only. No test suite, build or lint was run for this work. The Quick-calculator and Excel Formula-check example values were computed with NovaQ's `mmc` (λ 40, μ 15, c 3: Wq 9.5701 min); the Excel formulas were checked in Python, not in Excel. The mockups were checked in the built-in browser.
- U8 committed `4a4fc58b` (local, not pushed).
- Plan step U9 + B2, Quick calculator (owner GO 2026-10-12): implemented on `feat/ux-u1-shell` after `4a4fc58b`, uncommitted. **B2** `POST /public/calculator/{model}` (`backend/api/public_calculator.py`): no account, no session cookie, no database; the response comes from the same `analysis.model_response` as `POST /analysis/{model}`, so the numbers are identical (test per model); rate bucket `guest_compute` (`RATE_LIMIT_GUEST_COMPUTE`, default 30 per 60 s = 10 Calculates of up to 3 calls; in `pages_signed` mode keyed by the verified forwarded client IP, VERIFIED `rate_limit.py:85-99`; the Pages bridge forwards any /api/* path, `functions/api/[[path]].ts:115`); CSRF applies only with a session cookie, so guests need none. **Frontend**: `QuickCalculatorPage` at /calculator (public, `PublicShell` = the former HelpShell) and /tools/calculator (signed in; the explicit-model AnalysisPage is retired and its 11 strings removed); tabs Basic (M/M/1 for one counter, else M/M/c), Service time varies (M/G/c), Limited waiting space (M/M/c/K, or M/G/c/K with the optional spread, so every former model stays reachable), Some people leave (Erlang-A); inputs in plain units (spread in minutes -> variance (spread/60)^2 h^2; patience in minutes -> theta = 60/patience); accessible InfoTip on every input and result (click, hover, focus; Escape closes; described while open); results wait (min), busy share, people waiting, and "Can counters keep up?" (open models only, from rho >= 1, never from error text), or the share turned away (limited) / leaving (Erlang-A, busy = rho_effective); "What this means" from the returned fields for c, c-1 (never 0) and c+1 (never above K); 44 x 44 px targets below 768 px for InfoTip and Help links. **Finding** (VERIFIED, out of scope, task chip raised): `mmc` fails numerically for c >= 171 and `mgc` then reports the false "Unstable system"; the calculator shows "not calculated" without quoting it. Checks: tests `tests/test_b2_public_calculator.py` (10) plus the signed-IP bucket case, frontend logic 7 and page 7; mutants 14/14; browser: guest call cookie-less 200, no cookie, identical to the signed-in response; /tools/calculator with lambda 40, mu 15, c 3 shows 9.5701 min, 88.8889%, 6.3801, Yes, and c 2 cannot keep up, c 4 1.1353 min (spec board example).
- U9 + B2 committed `d31a527e` (local, not pushed).
- Plan step 15 (B8 Reports, owner GO 2026-10-13) is split into 15a (report model, plan-level preview and workbook with Formula check and Plan search), 15b (PDFs; full report with Decision, simulation and checks) and 15c (Reports page). Pre-check (VERIFIED): the shared Decision uses the period-by-period evidence (`workflow.py:3216-3245`), so the shared full report must show that evidence and say the full-day run (preview) is not part of it; saved plans are verified against a fresh optimizer run only at save time (`scenarios.py:260`). **15a** (implemented after `d31a527e`, uncommitted): optimizer results gain additive `candidates` (every counter count tried, with its busy share, wait, costs, or the limits it failed; OD-B8-3 A); a page loaded before this saves without them and the server stores its own results with them; legacy integrity-v1 saves compare equal with or without them (the full suite caught this; fixed); `GET /analyses/{id}/reports/plan/preview` and `/reports/plan.xlsx` (`backend/api/plan_reports.py`), gated by the existing current-selected-plan check (`no_selected_plan` / `plan_not_current` with that check's reason), report rate limit per user; one report model (`backend/reports/plan_report.py`) for shared lines (saved optimizer rows; Plan search stored, or recomputed for older plans only when it chooses the saved counts) and separate lines (simulated schedule; Plan search = simulated lane counts with cost intervals; Formula check = today's lines, M/G/1 each); workbook sheets Overview, Your data, Plan, Formula check, Plan search, Assumptions, Provenance, with no Decision words. **Formula check** (`backend/reports/formula_check.py`): one live layout for M/M/1, M/M/c, M/G/c and Parallel M/G/1 (Erlang C with one helper cell per term, no SEQUENCE(), times the Allen-Cunneen factor; with one counter this equals Pollaczek-Khinchine; checked against mm1, mg1, mmc, mgc to 3e-15); unstable rows say Unstable; finite-sum models and more than 170 counters show NovaQ's values with the reason. Checks: `tests/excel_formula_eval.py` re-computes the written formulas in Python (lazy IF as in Excel); tests `test_b8_formula_check.py` (12) and `test_b8_plan_report.py` (8); mutants 12/12; gates pytest 3091p/123s/1xf, ruff, mypy, vitest 606, tsc, oxlint, build clean; browser (scratch app): analysis 7 (shared, saved before candidates) recomputed 72 counter counts that choose the saved counts in all 3 periods, analysis 8 (separate) shows the stored simulated lane counts, analysis 9 is refused (no selected plan), the workbook downloads. The formulas are NOT TESTED in Excel: a sample workbook was generated for the owner's one-time check (OD-B8-4 A).
- 15a committed `5bb17e6e` (local, not pushed).
- **15b** (committed `2595c8e0`, local, not pushed): `GET /analyses/{id}/reports/plan.pdf`, `/reports/full/preview`, `/reports/full.pdf`, `/reports/full.xlsx`. The full report is available exactly when today's Decision gate allows export: separate lines through `reports._selected_report_chain` (its own statuses and reasons kept), one shared line when `workflow.current_decision_for_report` returns a current Decision for the selected plan (else 422 `no_current_decision`). It quotes stored evidence only (`backend/reports/full_report.py`): the Decision's headline, recommendation, rationale and facts; the simulation summary (shared: the period-by-period run the Decision uses, with served and at-closing counts "not recorded by this run"; separate: the selected-plan run); one line per check with its stored settings and outcomes (Many variations counted from the stored statuses; the results check from the Decision's facts or the separate verdict); and What is not included (the shared full-day preview, counter breaks in Suggested plans, the provenance warning). PDF (`backend/reports/report_pdf.py`, ReportLab): plain words without rho or Wq, each chart followed by its table, no glyphs the standard fonts cannot draw; plan level has no Decision words. Full workbook adds Simulation, Checks and Decision sheets. Tests `tests/test_b8_full_report.py` (5, reading the PDF text by decompressing its streams); mutants 10/10. Browser (scratch): analysis 7 full report quotes its stored Decision (revise; Many variations not run; results check 1 of 3 from the Decision), analysis 8 is refused with today's chain reason (Monte Carlo not run); plan PDFs valid. **Finding** (VERIFIED, pre-existing, not changed): the shared Decision requires a finite cost for today and the plan (`workflow.py:1570-1573`), so when today's staffing cannot keep up in any period it can only say "insufficient evidence".
- **15c** (committed `caffa6a1`, local, not pushed): the Reports page (D33) at `/reports?analysis=:id` (`frontend/src/pages/ReportsPage.tsx`; without an id it opens the last-used analysis, else My analyses; `/analyses/:id/reports` redirects there; sidebar, Checks and Plan changes link there). The level comes from the two previews only: `no_selected_plan` = "No plan chosen yet" (no files except data), `plan_not_current` = out of date with the server reason, plan preview = "Calculated only · not checked by simulation" with the full report's refusal reason, full preview = "Checked by simulation · Decision: …" with the stored headline; any other refusal is shown as an error. The PDF and Excel cards list `contents` (the PDF headings and workbook sheets, from `report_pdf.pdf_sections` and `plan_report.workbook_sheets`) and, at plan level, `after_checks` (what the full report adds) marked "(after the checks)"; `generate_report_pdf` asserts its headings equal `pdf_sections` as the workbook asserts its sheets. "Your data only" offers processed files only. 23 `reports.page.*` keys added and 53 unused `reports.*` keys removed (en/tl symmetric); Help Downloads text updated. Tests: ReportsPage (8), `test_the_listed_contents_are_exactly_the_files_contents` (both levels, PDF text and sheet names, plus a Setup with breaks); mutants 15/15. Gates: pytest 3097p/123s/1xf (the PDF heading assert was added after that run collected; ruff, mypy and the 253 report tests re-run after it, passed); vitest 599/599 on re-run (the first run, alongside the full pytest, had 1 failure whose name was cut from the output: UNKNOWN cause), tsc, oxlint, build clean. Browser (scratch): analysis 7 full (Decision Revise; full.pdf, full.xlsx and data downloads 200), 8 plan level with "Run selected-plan Monte Carlo before generating the final report." and its Breaks section listed, 9 no plan, old address redirects. **Finding** (VERIFIED in the browser, open): the report limit is 10 requests per user per 60 s (`settings.py:209,212`) and both previews count against it, so a visit costs 2 and each download 1; the 11th request in a minute returned 429 and the page showed "Too many requests". Proposed: a separate per-user preview bucket, and the page saying when to retry.
- **U10 final verification** (2026-10-13, owner GO; no code changed). Gates on `caffa6a1`: ruff, mypy, pytest 3097p/123s/1xf. Output parity (VERIFIED): 20 stateless requests (`/analysis` 6 models incl. unstable and c=170, `/optimize`, `/optimize/batch`, `/simulation/des|des/trace|mc|validate`) on base `6093d78a` vs branch: 0 values changed or removed; only `candidates` added (OD-B8-3 A). Postgres 16 (Compose project `novaq-u10`, separate ports): migrations 0001-0007 ran (0006/0007 first PG run); the API image failed to start on this Windows checkout because `core.autocrlf=true` and no `.gitattributes` write CRLF into `entrypoint.sh` (repo stores LF); Docker Desktop then stopped under memory pressure (7.8 GB machine), which also stopped another session's `novaq-db-1`; not restarted by this session. Deviation: the walkthrough ran on the local dev stack (SQLite API :8000, Vite :5174) in headless Edge with SYNTHETIC files (seeded FIFO generator). VERIFIED on that walkthrough: sign-in intent to New analysis; planning vs review-only upload (review file never current); older-file review banner, no plan section; recorded waits and per-period lambda/rho equal an independent recount; both closing rules saved per run; replay arrived = waiting + in service + served at 4 times; recorded-service (B4b) and estimated-service (B4a) labels; separate-lines chain to Decision revise; shared M/M/c chain to Decision revise; both full reports' PDF sections and sheets equal the listed contents; Tagalog on 10 pages without raw keys; no horizontal scroll at 375 px on 12 pages; guest calculator equals the spec example (9.5701 min, 88.8889%, c=4 1.1353 min, c=2 cannot keep up); Help public; Reports needs sign-in. **Findings (open):** F1 one shared line with customer records (M/G/c) cannot reach a Decision or full report: the period-by-period DES refuses M/G/c (`simulation.py:170`) and the full-day run has no pass/fail rule (OD-UX-13). F2 (protected, pre-existing by diff) the Results check simulates M/G/c plans as M/M/c: saved plan rows carry `service_cv` but no `variance`, and `validate_with_simulation` forwards `variance` only (`workflow.py:1434`, `simulation.py:1391`). F3 the default "One period per calendar date" blocks the full-day shared run and break suggestions without saying so; a new basis needs a re-upload that is not explained; a single-date separate-lanes workbook re-derives per_date (`setup_derivation.py:308`), so break suggestions are unreachable for it. F4 a totals upload leaves `fixed_server_count` empty (Setup incomplete) and nothing says so until the Decision returns "completed Setup"; the Checks page does not show `missing_evidence`. F5 the plain Decision wording of spec §7.9 is not implemented. Labels: F6 closing-rule options have no titles (`ContinuousRun.tsx:88`); F7 the Key results average wait is the customer-weighted mean under the caption "Average of the repeated days", while Checks shows the mean of daily means under the same name (`ContinuousRun.tsx:222-229`, `:443`); F8 Key results compare runs made under different closing rules without saying so; F9 the Reports full-level badge is green for Revise (`ReportsPage.tsx:148`); F10 the fixed-server-count refusal does not point to the collapsed field; F11 the optimizer's source file is not preselected (`OptimizePage.tsx:509`); F12 the full-day refusal blames waiting-room limits and leaving when both are only Unknown; F13 Home lacks "Try the quick calculator" (spec §7.1); F14 previews share the 10-per-minute report limit; F15 "VALIDATION 2 / 12" beside "10 of 12 passed"; F16 (protected) a separate-lanes cost interval with a negative lower bound (-252.20). NOT TESTED: 768/1024/1440 px, dark mode, keyboard-only walkthrough, separate-lanes break replay with new data (the synthetic lanes were infeasible at the 90% maximum target), Help screenshots (deferred: screens with open label findings, storage location undecided).
- **U10 fixes F3-F15** (2026-10-13, owner "A bc"; COMMITTED `dd367b97`, local). F3: a saved Representative day is kept for a single-date file (`setup_derivation.py`); the per-date hint names the full-day run and break limits; saving a new basis says to upload the file again; the break refusal names the setting. F4/F10: Setup shows "Your Setup is not complete" with the missing items (`frontend/src/lib/setupStatus.ts`, mirrors `analysis_schemas.py:292-303`) and a button that opens Advanced settings and focuses the field, also beside a refusal. F5: plain Decision answers (`frontend/src/lib/decisionPlain.ts`, spec §7.9) on Checks and the Decision page; the check's headline and rationale move into "Details from the check". F6 option titles; F7 the Checks row is "Average wait (average of the daily averages)" and the card note says which mean each card uses; F8 a note when the two runs used different closing rules; F9 the full badge colour follows the Decision; F11 the optimizer preselects the current planning file; F12 Unknown capacity or abandonment gets its own reason (`capacity_or_abandonment_unknown`); F13 Home links the calculator; F14 previews use their own per-user limit `RATE_LIMIT_REPORT_PREVIEW` (default 60/min; file downloads keep `report`); F15 "Checks that did not pass 2 of 12". No formula, simulation, optimizer or API shape changed (F12 adds one reason code; F14 adds one setting). Gates: ruff, mypy, pytest 3102p/123s/1xf, vitest 618/618, tsc, oxlint, build. Mutants 26/26 killed. Browser (headless Edge, dev stack, synthetic data): F6/F7/F8 analysis 10, F5 analyses 12 and 8, F9 analysis 12, F11, F15, F3/F4/F10/F12 analysis 13. Still open: F1 and F2 (OD-UX-13; protected), F16 (protected), Help screenshots; NOT TESTED: 768/1024/1440 px, dark mode, keyboard-only, Postgres.
- **U10 F1/F2: checks with recorded service times** (2026-10-13, owner: F2 "choose the best", F1 "verify before apply"; COMMITTED `71e41314`, local; spec `docs/superpowers/specs/2026-10-13-u10-f1-f2-recorded-service-checks.md`). The period-by-period DES simulates M/G/c by drawing each service time from the period's recorded durations (as separate M/G/1 already does), only when their mean and population variance equal the plan's `1/mu` and `variance` (rel. 1e-9); otherwise it refuses and assumes no distribution. Monte Carlo M/G/c uses `mgc` with the variance rescaled by `(mu/m)^2`; its pass/fail equals M/M/c by construction (`mgc` utilization = `mmc`). Validation now takes `variance`, `K`, `theta` from the calculation snapshot (before, every plan was checked as M/M/c) and does not store the durations. M/M/c/K, M/G/c/K, Erlang-A stay refused, now visibly. No pass/fail rule, threshold, cap or Decision rule changed; a shared line from customer records now reaches the existing Decision. Basis VERIFIED in the source text: Green, Kolesar & Whitt 2007 (POM 16(1)), pp. 9-11. Reference cases: M/G/1 skewed durations vs exact Pollaczek-Khinchine 7.1669 min: NovaQ DES 7.1828 +/- 0.0615 (30 seeds x 10,000 h; a 10-seed x 4,000 h run missed by 3.1% and was rechecked), independent Lindley recursion 7.1682 +/- 0.0196; M/D/1 exact 6.0000 vs 6.0233 +/- 0.1724; M/G/4 near-exponential vs Erlang C 3.4213 vs 3.4051 +/- 0.0944; MC M/G/3 vs M/M/3 same seed 776 = 776 failures. Regression: M/M/1, M/M/c, zero-arrival, unstable, M/M/c/K DES/MC/validation/trace outputs identical before/after (only the M/G/c-without-durations refusal text changed). 10 tests, mutants 17/17. OD-UX-13 (pass/fail for the full-day run) is NOT decided: proposal in the spec §5 (separate-lanes rule with the full-day run as DES evidence).
- **U10 F16 fix** (2026-10-13, owner "go", commit "go"; committed after `6a56506a`; gates: ruff, mypy, pytest 3123p/123s/1xf; spec `docs/superpowers/specs/2026-10-13-u10-f16-separate-cost-interval.md`). Both separate-lanes DES evaluators keep a replication's cost when that replication is over the target (status stays INFEASIBLE, feasibility stays the aggregate mean-utilization rule), so the candidate's mean cost uses every replication; the cost intervals (staffing, waiting, total) report max(0, mean - t x SE) as the lower bound (coverage unchanged because cost >= 0). Engine versions v2 -> v4 (representative day) and v3 -> v5 (per-date day); plans saved with v2/v3 are HISTORICAL_REQUIRES_RECALCULATION ("run Suggested plans again"; B13's per-date message kept for v2 on a per-date day). Analysis 11 (scratch, target 90%): 08:00 and 11:00 unchanged (375.74 [289.54, 461.93], 321.61 [304.23, 338.99]); 09:00-10:00 mean 416.11 (n = 1, the cheapest replication, the only one under target) -> 573.66 [405.31, 742.00] (n = 5: 583.84, 774.22, 606.06, 488.06, 416.11), recomputed independently with scipy. 5 existing tests updated (they encoded the old rule or the v2 constant), 6 new, mutants 10/10. Unchanged limitation: customers still waiting at the end of a run are not costed.
- **F16 (explanation, kept for the record; fixed above):** the separate-lanes cost interval is a symmetric Student-t interval over the replications that have a cost (`separate_optimization.py:1281-1289`), and a replication whose own lane utilization exceeds the target returns no cost (`:356-359`, `:1840-1843`, since 2026-09-18). So n can fall below 5 while the candidate stays FEASIBLE on the mean utilization: VERIFIED on analysis 11 today, 09:00-10:00 FEASIBLE at 87.79% with n = 1 of 5. With n = 2, t(0.975, 1) = 12.71, so the -252.20 to 1242.94 interval around 495.37 needs a replication SD of only about 83 (INFERRED; the walkthrough response was not saved and the break change applied afterwards altered that period). Two defects: (a) the mean cost is conditional on the low-utilization replications (biased low) and its n varies; (b) the lower bound is not truncated at 0 although cost >= 0 (truncation keeps coverage exactly). Proposed fix needs the owner's GO.
- Docker (2026-10-13): Docker Desktop was restarted by the owner; `novaq-db-1` stopped cleanly 6 h earlier ("Exited (0)") and was not restarted by this session (free RAM 217 MB; no session waiting on it). The Compose API failure on Windows checkouts is fixed by `.gitattributes` (`*.sh text eol=lf`, committed `71e41314`); the image build itself is NOT TESTED.
- **U10 today-overloaded Decision rule** (2026-10-13, owner "go 2 1st", commit "go"; committed after `71e41314`; gates: ruff, mypy, pytest 3117p/123s/1xf, vitest 620/620, tsc, oxlint, build; browser: analysis 10 Decision page shows the segment_3 reason; spec `docs/superpowers/specs/2026-10-13-u10-today-overloaded-decision.md`). When every plan cost is finite and every missing today cost is in a period the optimizer marked `current_stable` false (rho >= 1, no finite waiting cost), the shared Decision no longer reports a missing cost comparison: any failed period gives `revise` (unchanged), all passing gives `conditional` (never `adopt`: the saving is undefined, so `savings >= 0` cannot be established). Facts: `current_modeled_cost` and `modeled_savings` null, `selected_modeled_cost` the plan total, `today_overloaded_periods`; rationale and recommendation reuse the approved ROI wording (`optimization.py:497-504`); the plain answer says the saving can't be calculated and names the periods (new key `decision.plain.conditional_today_overloaded`, en/tl). Any other cost gap stays insufficient. Analysis 10 (scratch copy) now reaches `revise`: segment_1 Monte Carlo failure 0.0955 > 0.05; plan total 1427.25 = 323.95 + 314.29 + 493.62 + 295.39; segment_3 named. 5 backend + 3 frontend tests; mutants 11/11.
- **OD-UX-13 Decision from the full-day run** (2026-10-13, owner "go 13" + answers: rule "Day run + Monte Carlo", basis "Full-day run first"; committed after `de733c5c` (local, not pushed); spec `docs/superpowers/specs/2026-10-13-od-ux-13-full-day-decision.md`). Per plan period: the full-day run's mean simulated utilization over the repeats must be at or below the plan's recorded target (separate-lanes aggregate rule) and the plan's Many variations job must pass (separate-lanes verdict); FAIL > insufficient > PASS; cost rule unchanged. When the selected plan has an eligible full-day run (latest suggested run whose scenario id+generation, dataset id+generation and Setup hash are current) the shared Decision uses it; otherwise the period-by-period chain, unchanged; never mixed. Engine: `run_shared_replications` adds `period_utilization` outside the replication rows (replays of stored runs unaffected); runs record `period_labels`. Stored Decision gets `basis` and evidence id `continuous`; currentness by comparison with the eligible run (not added to the protected G-A reference list); a period-by-period Decision is stale when an eligible run exists. GET workflow adds `decision_basis`/`full_day_run_id`; Check the plan runs Many variations then the Decision for that basis; the page shows the basis and a per-period table. Found and fixed in the browser: a full-day run did not refresh the workflow (stale Decision shown as current). Analysis 10 (scratch copy, recorded service times, run 70, 5 repeats, Stop service at closing): revise, segment_1 Many variations 9.2% > 5% (day run 64.85% <= 70%); others pass; means recomputed from raw busy/present hours. Note: the simulated day starts empty, so a short first period is gentler than steady state; 5 repeats are noisy (segment_1 had one day at 77.3%). 13 + 3 tests, 1 updated; mutants 24/24 + 1.
- **U10 Help screenshots** (2026-10-14, owner "go screenshots"; committed after `a3b541fa` (local, not pushed); spec `docs/superpowers/specs/2026-10-14-u10-help-screenshots.md`). One annotated picture per guide except Problems (7 guides x EN/TL = 14 WebP files, about 0.8 MB) in `frontend/public/help-images/<lang>/<topic>.webp` (storage chosen here; the owner named none), shown after the guide summary with the note "Sample screen with made-up data" and a numbered list; sizes in `HELP_FIGURES` (`helpGuides.ts`). Taken by `frontend/scripts/help-screenshots.mjs` (headless Edge via DevTools, Node WebSocket, local hosts only, credentials from the environment) from scratch copy `help_shots.db` of the SYNTHETIC analyses (analysis 10). Corrected Help text that contradicted the code: the full-day run now decides (OD-UX-13) and takes the Setup's counter breaks (step 12). Tests: 4 new Help tests (file sizes read from the WebP headers); mutants 7/7. Finding (not changed): the Reports Decision headline is server English in Tagalog (`ReportsPage.tsx:152`).
- Next authorized step: none. The Help screenshots are done above; F16 and OD-UX-13 are done above; the next plan phases and the own specs for B4a, B4b, B4c, B8 and B10 need the owner's GO. Open owner decisions: replay base rate, OD-UX-14 (OD-UX-13 decided and committed `a3b541fa`).

## Named Shared Queue release (2026-10-08; current)

The Named Shared Queue API/UI first slice is released. The step record is
`docs/superpowers/plans/2026-10-07-named-shared-queue-release-plan.md` §9.

- Backend: Render `srv-daiikrbm8hqs73d15rtg` runs `491a9d3` (owner Manual
  Deploy, live 2026-10-08 04:04 UTC). Same settings as below: 18 env keys,
  `RESULT_JSONB_MAX_BYTES=786432`, the same Start Command, Auto-Deploy and PR
  Previews Off. No migration ran; the database stays at `0005`.
- Frontend: Pages production `16a21277` (`main` `285b35e`, serving by 2026-10-08
  04:24:30 UTC, bundle `index-DxMbj5_C.js`). Automatic deployments were switched
  on for that one build and read back Disabled afterwards.
- `main` is `285b35ef` (`491a9d31` plus the docs-only release record).
- VERIFIED after release: `/api/ready` 200; R1 contract through the app
  returns `limits.result_max_bytes = 786432` and
  `max_expected_customers_per_run = 2900` (owner's logged-in read of
  analysis 6, 04:16 UTC); the Named view loads on analysis 17 and the legacy
  pages still return 200; no 5xx or traceback in the Render log. CI green on
  `491a9d31` (PR #28 run 37704686284; push run 37725205872, 11/11 each).
- Release backup: the scheduled `novaq-sched-20261007T141913Z` (owner choice).
- Rollback: Render `1c8e8de` (no database change needed), Pages `b7ac08c8`.
- Open:
  - The limits (9 replications, 52 segments, 24 employees, 48 shifts, 2,900
    expected customers per run) stay provisional and NOT PRODUCTION-APPROVED:
    the owner skipped the production timing run (W9), so production R3/R6
    time near 2,900 customers and the first request after a spin-down are
    NOT TESTED. Startup after the deploy took about 57 s.
  - PR #28 (`ci/verify-491a9d31`, opened for CI only) was marked merged by
    GitHub at 03:57:52 UTC, when W4 pushed its head `491a9d31` to `main`; no
    merge commit was created. The `ci/verify-491a9d31` branch was deleted
    afterwards.
  - Analyses 6 and 11 were archived by the owner on 2026-10-08 (intentional).
- Everything below in the G8 section still holds except its "current"
  backend and Pages deployment lines, which this section supersedes.

## G8 G-A release (2026-10-06)

G-A `2ccb86527a0f48928e4d5c26f3d9bd5f0e6abc35` is released. The full step
record is `docs/superpowers/plans/2026-10-05-g8-go-packet.md` §6; the
runbook is `docs/superpowers/plans/2026-10-05-g8-production-cutover-runbook.md`.

- Production state, VERIFIED 2026-10-06:
  - Supabase `cltvswcopkjvnonjutre` is at revision `0005`, applied 13:16 UTC
    with one-shot `alembic upgrade 0005` from a clean `2ccb8652` tree.
  - Row counts were unchanged by the migration.
  - RLS is on for all 10 public tables, with 0 table or routine grants to
    `anon`/`authenticated`.
  - The Data API is off.
- Backend: Render `srv-daiikrbm8hqs73d15rtg` runs `1c8e8de`: G-A `2ccb8652`
  plus the `event=` logging fix (`0ddefa6`) and the signed Pages ingress
  (`38fa998a`); the other commits in between are docs or frontend only.
  - The release first went live as `2ccb865` at 13:39 UTC on 2026-10-06.
  - The current deploy is `dep-db33kc2d0e5s73f0rf2g` (2026-10-07 12:27 UTC, same
    `1c8e8de`, redeployed after removing `FORWARDED_ALLOW_IPS`), with:
  - `NOVAQ_ENV=production`, so the G7 exact-head guard and `/ready` revision
    check are active;
  - `NOVAQ_PROXY_MODE=pages_signed` and `NOVAQ_PROXY_ASSERTION_SECRET` (also set
    in Pages): only requests signed by the novaq.site bridge are served;
    direct `onrender.com` API calls get 403 `proxy_assertion_required`
    (`/health`, `/ready` and OPTIONS are exempt). Rate limits key on the
    verified client IP;
  - no `FORWARDED_ALLOW_IPS` key (removed 2026-10-07 at the owner's request;
    unused under `--no-proxy-headers`);
  - 18 env keys (read back 12:28 UTC; `RESULT_JSONB_MAX_BYTES=786432` among
    them), auto-deploy off and PR previews off.
- The Start Command is migration-free and has no uvicorn access log:
  `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-proxy-headers --no-access-log`.
  - Each request is logged once, by the app's `event=http_request` line, which
    carries the path without the query string (and no client IP).
  - Ingress rollback: set `NOVAQ_PROXY_MODE=direct`, **re-add
    `FORWARDED_ALLOW_IPS=127.0.0.1`** (otherwise `direct` mode refuses Render's
    injected value at startup), drop `--workers 1 --no-proxy-headers`,
    redeploy; `direct` keeps the pre-ingress rate-limit keys. Record:
    `docs/superpowers/plans/2026-10-07-signed-pages-ingress-plan.md`.
  - Deploys never migrate. A future migration is a deliberate one-shot `alembic upgrade
  <rev>` from a clean checkout, as in GO packet W4. If the database is behind
  the code, the G7 guard refuses to start the app.
- Frontend: the G-A build went live on Cloudflare Pages as `2f88918f`
  (`main` `2ccb865`) at 14:09 UTC. The current Pages deployment is `b7ac08c8`
  (`main` `1c8e8de`, 2026-10-07 11:59 UTC, bundle `index-jBXJZ6bl.js`): the
  G-A app, the Comparison `<label for>` accessibility fix, the signing `/api`
  bridge (`frontend/functions/api/[[path]].ts`), and
  `frontend/public/_headers` (since `64e47b29`/`4feb6f8`), which sends an enforcing
  `Content-Security-Policy` equal to `nginx/production.conf`,
  `X-Frame-Options: DENY` and `Permissions-Policy` (VERIFIED 02:17 UTC).
  Production automatic deployments are disabled (read back 2026-10-07 after
  12:08 UTC). The previous deployment is `a4f60c31` (`574e1a9`, unsigned
  bridge); the pre-G-A rollback deployment is `a69cbebf` (`2d063c9`). The legacy Render
  static site stays suspended.
- Cloudflare Web Analytics is off, both on the Pages project and in the
  `novaq.site` site's Real User Measurements, because the CSP does not allow
  its beacon. Turning it back on would need a CSP change.
- Supabase "Enforce SSL on incoming connections" is ON (2026-10-06 ~17:10 UTC);
  a fresh-connection restart passed and `/ready` returned 200.
- Scheduled backups (since 2026-10-07): the Windows task "NovaQ daily backup"
  runs `output/g8-backup-tools/novaq_scheduled_backup.sh` in WSL daily at
  12:00 local (catch-up after missed runs, allowed on battery). Encrypted to
  the gpg public key `…F4DCFA84E2B2E617`, copied to
  `OneDrive/NovaQ-backups/scheduled` (30-day retention), status in
  `LAST_STATUS.txt`. Restore drill: `novaq_restore_check.sh` (passed
  2026-10-07, 10/10 table counts). The weekly Claude task "NovaQ weekly backup
  check" (Mondays) checks freshness, status and hash read-only. A WSL
  console window shows for about two minutes at each noon run (owner decision
  to keep it; a hidden start was tested and declined).
- Release backup: `20261006T125254Z`, gpg AES256 (passphrase of the manual
  script; its plaintext dump was shredded 2026-10-07), held in WSL `~/novaq-backups`
  and OneDrive `NovaQ-backups`. An isolated restore verified `0004` and the
  counts. The recovery target is the separate Supabase project
  `kjtkkdatiapmzcmhmlbp` (novaq-RECOVERY).
- Smoke test (Render logs): Google login, Analysis 6, calculations,
  Comparison, PDF, Excel and logout all returned 200, with no 5xx.
- SMTP test passed on 2026-10-06 at 15:28 UTC. A password reset for the
  owner's own account was REPORTED delivered. The request returned 200 with no
  delivery error, and reset token `259` was issued (GO packet §6).
- `event=` logging fixed and live (`0ddefa6`, `configure_event_logging` in
  `backend/api/main.py`).
  - Before it, the `novaq` loggers inherited root WARNING, so every INFO
    `event=` line was dropped.
  - CI #98 (37493271324) passed 11/11.
  - Render's logs now show UTC `event=http_request` and
    `event=password_reset_request` lines, verified 16:31 UTC.
  - Details: `docs/superpowers/plans/2026-10-06-api-event-logging.md`.
- Issue found in the window:
  - Render injects a `FORWARDED_ALLOW_IPS` value outside the dashboard keys,
    and the production validator refuses it. The first deploy therefore failed
    at startup, with no data effect.
  - The 2026-10-05 preflight had supplied the variable itself.
- Open:
  - GO packet §3 is closed (all four items fixed; GO packet §6).
  - Backups: a copy of the backup private key (fingerprint
    `B86C89C88962872B2515A2CCF4DCFA84E2B2E617`) off the owner's PC is not yet
    made; without it, losing the PC makes every backup undecryptable.
- `1fbe812c` (signed Pages ingress) was excluded from G-A and released
  separately on 2026-10-07 as the port `38fa998a`, without the client-version
  fence (PR #27, merged). Its branch `feat/signed-pages-ingress` and the
  `ingress-probe` worktree were removed afterwards (2026-10-07).
  - Draft PR #26 (`ci/verify-fcbc8db1`) was closed unmerged on 2026-10-06.
  - Its branch is kept at `1fbe812c` and still holds the unreleased fence
    commits `81bc427a` and `6ef85712`.
- Pushing `main` is a production release path: auto-deploys are off, but
  confirm both Render and Pages settings before any push.

Earlier G8 preparation (2026-10-04/05): the Option A policy is in
`docs/superpowers/specs/2026-10-04-g8-release-policy.md`, and the closure plan
is `docs/superpowers/plans/2026-10-04-g8-g-a-release-closure-plan.md`. Before
the release, Supabase had RLS off and 126 `anon`/`authenticated` grant rows.
The owner revoked those grants and enabled RLS on 2026-10-05, and turned the
Data API off.

Historical entries below describe their own dates and are not the current
release instruction.

## Critical Semantic Regression Gate (2026-09-14)

The mandatory pre-redesign semantic gate is complete and green:

- `docs/superpowers/specs/2026-09-13-critical-semantic-regression-gate.md`
- `docs/superpowers/plans/2026-09-13-critical-semantic-regression-gate-plan.md`
- `docs/superpowers/reports/2026-09-14-critical-semantic-regression-gate-report.md`

Behavior-level coverage now protects unknown setup values, exact optimizer-preset meaning, saved validation parameters, report preview/export parity, canonical route resolution, missing-versus-zero semantics, and scenario-scoped/current Decision evidence. The smallest approved truth repairs were made in Guided Setup, optimizer copy, Simulation validation presentation, report preview, Dashboard route targets, and complete-value frontend aggregation.

No backend production code or protected queueing, model-selection, optimizer, DES/Monte Carlo, Decision, authentication/CSRF, provenance/staleness, API, report-calculation, or report-unit behavior changed.

Verification baseline: backend **466 passed, 3 skipped, 6 subtests passed**; frontend **31 files / 140 tests passed**; Ruff, mypy, TypeScript, frontend lint, production build, 565-key locale symmetry, and diff hygiene passed. Two pre-existing Fast Refresh warnings and the existing large Plotly chunk warning remain non-blocking.

Page-by-page UI refinement may now begin through the approved full refinement plan and `design-system/novaq/MASTER.md`. Retain the executable workflow order `Setup → Current → Optimize → Compare → Simulate → Decision → Reports` because Compare's persisted scenario selection remains a simulation prerequisite.

## Shared Design System Definition (Part 4, 2026-09-13)

The mandatory shared design-system phase is defined and approved:

- `docs/superpowers/specs/2026-09-13-shared-design-system.md`
- `design-system/novaq/MASTER.md`

No application code was changed in Part 4. The Master defines the light/dark semantic token contract, type/spacing scales, responsive shell, shared components, API/content states, evidence banners, workflow completion predicates, chart rules, accessibility requirements, page-override policy, and verification gates.

The current React/global-CSS/Plotly/i18next stack, Inter/system font, and NovaQ navy/gold identity are retained. The generated replacement fonts/palette, GSAP, new UI framework, and component library were rejected as unsupported.

The requested Setup → Current → Optimize → Simulate → Compare order conflicts with the repository: Compare persists the verified scenario selection required by simulation, and the backend/test suite rejects simulation without it. The Master therefore retains Setup → Current → Optimize → Compare → Simulate → Decision → Reports until a separate workflow specification authorizes relocation of that prerequisite.

## Full UI/UX Refinement Specification and Plan (Part 3, 2026-09-13)

The repository-grounded refinement specification and ordered implementation plan are approved:

- `docs/superpowers/specs/2026-09-13-ui-ux-full-refinement.md`
- `docs/superpowers/plans/2026-09-13-ui-ux-full-refinement-plan.md`

No application code was changed in Part 3. Implementation has not started.

The specification verifies eight P0 trust defects: broken entry links/false Login claims, incorrect onboarding flow, divergent Guided Setup, non-data-derived Current conclusions, misleading Optimize semantics, synthetic Comparison/ROI evidence, mutable-threshold Simulation display, and report-preview/export mismatch. Cross-cutting accessibility, responsive, theme, language, icon, and localization work follows only after the P0 gate.

The approved separate-FIFO product intent conflicts with the current repository, which marks separate queues unsupported and runs shared-FIFO DES/playback. This conflict is explicit: the UI may disclose the limitation but must not claim support or change queueing mathematics under the refinement plan. Priority-class queueing remains outside scope.

The earlier “DES equivalence not proven” and “Decision evidence missing” findings are superseded by current source and tests. Unified DES execution, aggregate/playback equivalence, persisted workflow evidence, Decision derivation, and staleness are protected invariants.

## UI/UX Refinement Governance (Part 2, 2026-09-13)

The product owner established a mandatory five-phase refinement sequence:

1. Trust Repair
2. Specification
3. Safety Boundary
4. Implementation
5. Verification

Full UI refinement must not start before the specification and safety boundary are documented. Phase 1 is limited to correcting misleading or inconsistent P0 behavior. Phase 5 must prove both defect removal and non-regression of protected behavior.

The governing document is `docs/superpowers/specs/2026-09-13-ui-ux-refinement-governance.md`. No UI or protected backend behavior was changed while recording Part 2.

## UI/UX Refinement Decision Baseline (Part 1, 2026-09-13)

Part 1 of the UI/UX refinement preparation is complete. The product owner confirmed the following authoritative constraints:

1. Onboarding is required once for first-time authenticated users, is not forced again after completion, is replayable from Help, and must collect real values.
2. The intended product behavior is separate FIFO cashier queues; priority-class queueing is outside scope. The current repository's unsupported/shared-FIFO implementation is a documented conflict and must not be relabeled as separate support.
3. Optimization continues to minimize configured cost subject to constraints; short-wait presets are constraint profiles, not distinct objectives.
4. Costs cover the explicitly analyzed operating period. Monthly/annual values are disclosed projections, not observations, and ROI requires an explicit investment cost.
5. Report previews must exactly match implemented export sections.

These decisions are documented in `docs/superpowers/specs/2026-09-13-ui-ux-refinement-product-decisions.md`. No UI, API, queueing-engine, simulation, or report implementation was changed in this part.

## Simulation Playback (2026-09-12)

- Upgraded the existing Live trace into customer-level playback without changing queueing mathematics or aggregate DES behavior.
- Trace events now include stable recorder-assigned `customer_id` values; responses state `queue_structure: "shared"` and `abandonment_supported: false`.
- The Live tab now shows one truthful shared FIFO queue, exactly the configured number of servers, customer/server assignments, served exits, bounded queue tokens, relative simulation time, event accounting, and play/pause/restart/step/speed controls.
- Playback uses a pure event reducer and simulation-time conversion; it does not generate queueing or random values in React.
- Full verification: backend **450 passed, 3 skipped, 3 subtests**; frontend **24 files / 140 tests passed**; typecheck, Ruff, mypy, lint, build, and locale symmetry passed. Existing chart canvas notices, Fast Refresh warnings, and large-chunk warning remain non-blocking.
- Verified limitations: DES playback supports M/M/1 and M/M/c only, models a shared queue only, has no abandonment transition, and has count-based rather than identity-based cross-segment carryover.

## Current Development State

NovaQ is being prepared as a pilot-deployable web-based capstone.

The repository already uses:

- React frontend
- FastAPI backend
- PostgreSQL
- Docker Compose
- Superpowers workflow
- AGENTS.md repository instructions

## Current Priorities

1. Stabilize the core workflow.
2. Improve onboarding for users without queueing-theory knowledge.
3. Remove redundant setup/input flows.
4. Preserve queueing-engine correctness.
5. Prepare the system for deployment and real-user pilot use.

## Core Workflow

Login
→ Onboarding
→ Setup
→ Upload Data
→ Current Analysis
→ Optimize
→ Save Scenario
→ Comparison
→ Simulation
→ Decision
→ Report

## Before Starting Any Significant Task

Read:

1. `AGENTS.md`
2. `memory.md`
3. `handoff.md`
4. Relevant existing Superpowers spec/plan
5. Relevant source files

Do not assume the repository state from old documentation.

## Execution Rule

For bugs:

Investigate
→ reproduce/trace
→ identify root cause
→ plan
→ implement
→ test
→ verify

For substantial features:

Brainstorm
→ spec
→ plan
→ implement
→ test
→ verify
→ update handoff

## Full UI/UX Refinement Complete (2026-09-14)

The approved page-by-page refinement and shared design system are implemented. See:

- `docs/superpowers/reports/2026-09-14-ui-ux-full-refinement-report.md`
- `design-system/novaq/MASTER.md`

Current verified state:

- Required-once onboarding is enforced after authentication and replayable from Help.
- Guided Setup redirects to canonical analysis Setup.
- Global navigation and the evidence-aware footer use the single canonical workflow: Setup → Current → Optimize → Compare → Simulate → Decision → Reports.
- Current, Optimize, Compare, Simulation, Decision, and Reports no longer advertise synthetic, stale, unsupported, or incorrectly scoped evidence.
- Accessible responsive navigation, focus, reduced motion, table/chart alternatives, keyboard tabs, semantic states, and symmetric EN/TL copy are in place.
- Backend: 466 passed, 3 skipped, 6 subtests. Frontend: 141 passed. Ruff, mypy, TypeScript, lint (0 warnings/errors), build, locale symmetry, diff hygiene, real-browser checks, Docker rebuild, and HTTP health checks passed.
- No protected backend production logic or API contract changed. Separate-queue analytical/DES support remains unimplemented and is not claimed.

## API Image Vulnerability Gate Remediated Locally (2026-09-14)

The approved remediation is implemented and locally verified. See:

- `docs/superpowers/specs/2026-09-14-api-image-vulnerability-remediation.md`
- `docs/superpowers/plans/2026-09-14-api-image-vulnerability-remediation-plan.md`
- `docs/superpowers/reports/2026-09-14-api-image-vulnerability-remediation-report.md`

Current evidence:

- API runtime changed from the blocking Debian base to the verified digest-pinned Python 3.11.16 Alpine 3.24 base; application and dependency-lock contents are unchanged.
- Strict Trivy 0.74.0 result improved from 44 HIGH/0 CRITICAL to 0 HIGH/0 CRITICAL without ignores or policy changes.
- Backend: 466 passed, 3 skipped, 6 subtests. Frontend: 141 passed. Ruff, mypy, TypeScript, lint, build, locale symmetry, production Compose preflight, Docker rebuild, migrations, bootstrap, and HTTP health/readiness checks passed.
- Next: inspect diff, commit/pull/push, wait for green GitHub CI, then identify and verify the authenticated Render service/public URL.
- Supabase is deliberately unchanged: this remediation contains no migration. Do not perform a hosted schema mutation for this work.
- Overall production GO is still separate from this image fix; TLS, SMTP, backup/restore, monitoring, edge, and secret-permission evidence remain required.

## Problem 1 Closed — Separate-Queue Current Independence

`tests/test_current_independence.py` (9 tests) proves Current Analysis keeps each (time, queue_id) an independent analytical entity through centralized model selection, with no pooled λ-total/c-total entity.

- SUPPORTED: configurable separate queue IDs; Current Analysis processes separate queues independently by (time, queue_id); each queue uses centralized model selection independently.
- STILL LIMITED: separate-queue staffing optimization remains blocked where demand redistribution is undefined; separate-queue DES/playback remains unsupported unless current source proves otherwise.

## Separate-Queue Status (2026-09-19, supersedes the "STILL LIMITED" and "unsupported" notes above)

The notes above are kept as history. Verified in source and tests at 9b1f95a4:

- Workflow: Setup → Current → Optimize → Compare → Simulate → Decision → Reports.
- Current: each (time, queue_id) is analysed on its own through centralized model selection (analytical estimate, not a measurement).
- Staffing optimization: `POST /analyses/{id}/workflow/optimize/separate`. Fewer-lane sets have no analytical model, so each period's candidates are judged by replicated routing DES (shortest-queue routing, one server per lane) over the operating day. A candidate is feasible when its highest mean lane utilization is at or below the target. Feasible means meeting the target, not a statistically proven improvement.
- Break optimization (separate from staffing optimization): `POST .../optimize/separate/breaks` (read-only) and `.../breaks/apply`. Placement is greedy, so the result is a local improvement, not a proven global optimum.
- Selected-plan evidence: `.../simulation/des/selected` (with playback trace), `.../simulation/mc/selected`, `.../simulation/validation/selected`, `.../decision/selected`.
- Compare: Current values are analytical and plan values are simulated. Waits, waiting costs and peak utilization are labelled with their basis and never subtracted. Current total cost, savings and ROI are N/A, with the reason shown.
- Model scope: the separate-queue DES has no finite capacity and no abandonment (`abandonment_supported: false`). K and theta affect only the per-lane analytical Current rows.
- Known finding: the selected-plan Monte Carlo Decision depends on the base seed for NovaMart with breaks applied (cashier_2 at 13:00 passes on seeds 7-8 and fails on 9-11). It is recorded as a strict xfail in `tests/test_selected_mc_load.py` and not yet fixed.
- Known limitation (K1, per-date basis): a single-date upload (`event_period_basis: per_date`) still judges each period's staffing candidates, and simulates the selected plan, one period at a time over the 24 h default (`DES_DEFAULT_DURATION_HOURS`). A break that fills a period is only a small part of that run, so break-hour utilization and waits are understated and a break hour can be marked FEASIBLE when the same hour inside a continuous day is not (`tests/test_separate_day_feasibility.py::test_per_date_basis_keeps_the_24_hour_candidate_runs`: below 0.55 per-date vs above 0.70 on the continuous day). Optimizer and selected-plan DES agree with each other on this basis. Not fixed; the representative-day path (NovaMart) is not affected.
- Representative-day layout (K2-a): the optimizer rejects a representative-day schedule with `INVALID_INPUT` (no periods, no `utilization_basis`) when the operating day cannot be laid out: no operating segments, a malformed segment time, or a period label that matches no segment id (e.g. Setup segments renamed without re-uploading). It never falls back to independent 24 h per-period runs. The per-date basis is unchanged (K1).

## Store Floor Playback View (2026-09-20)

The separate-queue playback now renders as a checkout floor by default. Spec and plan:

- `docs/superpowers/specs/2026-09-20-store-floor-playback-view.md`
- `docs/superpowers/plans/2026-09-20-store-floor-playback-view-plan.md`

Current verified state:

- `StoreFloorView` draws lanes as grid columns with the waiting queue stacked toward its
  own counter, the serving customer at the counter, and the elapsed service time computed
  from the traced `service_start`. The panel stays vertically bounded; past ten lanes it
  switches to a dense layout and the lane strip overflows horizontally only.
- The existing stacked diagram is retained behind a "Floor layout" selector. Both views
  read the same `deriveSeparateLaneSnapshots` output and keep the same lane, customer, and
  server test identifiers, so separate-queue isolation stays provable in either view.
- Lane identity is now seeded from `trace.segments` before events. A lane the run declared
  but never used is drawn as a real empty lane instead of disappearing.
- A lane in the period's `inactive_queue_ids` is labeled **Closed / not staffed in this
  plan**. It is deliberately not labeled as a break: the trace schema emits no break
  transition, so an ON_BREAK window cannot be shown truthfully on the playback clock.
- Playback speeds now include 0.25x in both the shared and separate playbacks. Dot
  transitions are disabled at 5x and above.
- Presentation-only: no queueing mathematics, DES behavior, API contract, or aggregate
  field changed.
- Locale catalogues were de-duplicated in the same working tree: four repeated keys in
  `en` and five in `tl` had made the earlier value dead. The shipping (later) value was
  kept in every case and `frontend/src/lib/translationKeys.test.ts` now fails on any
  repeated key and on any en/tl key-set difference.
- Verification: frontend **47 files / 312 tests passed**; typecheck, oxlint, production
  build, and locale symmetry passed. Visual check used a real selected-plan DES payload
  (735 events over 5 lanes and 2054 over 14) in both light and dark themes; the displayed
  service timers matched the traced `service_start` values exactly. The pre-existing large
  Plotly chunk warning and chart canvas notices remain non-blocking.

Resolved after this feature landed: `evaluate_candidate_with_des` now returns the DES
`trace_events` and `trace_truncated` evidence for both FEASIBLE and INFEASIBLE measured
verdicts. The selected-plan endpoint therefore keeps real playback events for periods
above the utilization target; evaluator-level and endpoint regression tests cover it.

## Public Deployment: Cloudflare Pages + novaq.site (2026-09-24)

The public frontend moved from the Render static site to Cloudflare Pages; the Render API is unchanged.

Current verified state:

- Public URL: `https://novaq.site`. `https://www.novaq.site` returns a 301 to the same path and query on `novaq.site` (Cloudflare zone Single Redirect "Redirect from WWW to root"). `http://` upgrades to `https://`.
- Domain registered at Spaceship; nameservers are Cloudflare (`gail.ns.cloudflare.com`, `maxim.ns.cloudflare.com`). DNSSEC is off at Spaceship (it can be re-enabled later through Cloudflare).
- Cloudflare Pages project `novaq-frontend` builds `main` (root `frontend`, `npm run build`, output `dist`) and serves `novaq.site`, `www.novaq.site` and `novaq-frontend.pages.dev`. Every non-`main` branch gets a preview deployment; use the hash URL from the Deployments list (the branch alias URL returned 404).
- `/api` bridge: `frontend/functions/api/[[path]].ts` strips `/api` and forwards to the `NOVAQ_API_ORIGIN` Pages variable (`https://qcu-novaq-analytics.onrender.com`, set for Production and Preview). `frontend/public/_routes.json` limits the Function to `/api` and `/api/*`. See `docs/operations.md` "Cloudflare Pages frontend". Merged to `main` in `2d063c91`.
- Render API service `Qcu-NovaQ-Analytics`: the user set `PUBLIC_APP_URL` to `https://novaq.site` and added `https://novaq.site` to `ALLOWED_ORIGINS`. Neither environment-variable value was inspected directly. Observed externally only: a CORS preflight from the API accepts `https://novaq-frontend.onrender.com` and `https://novaq.site` and rejects `https://www.novaq.site`, `https://novaq-frontend.pages.dev` and an unrelated origin; the user reported that the password-reset email link opens `novaq.site`. `www` and `pages.dev` do not need to be allowed because the bridge makes API calls same-origin.
- Google OAuth client "NovaQ Web" authorized JavaScript origins: `http://localhost:5173`, `http://localhost`, `https://novaq-frontend.onrender.com`, `https://novaq-frontend.pages.dev`, `https://novaq.site`, `https://www.novaq.site`. Local Docker must be opened at `http://localhost`, not `127.0.0.1` (Google returns `origin_mismatch`).
- Verification: frontend 51 files / 350 tests, typecheck, lint and build passed; bridge e2e against the local Docker API (config, Google nonce, password login, session, CSRF-refused and CSRF-accepted logout, M/M/c, M/M/1 and Erlang-A outputs byte-identical to direct calls); live checks on `novaq.site` and `www` (pages, `/api` JSON, `Secure; HttpOnly` cookies, HTTPS). User confirmed password login, Google login, a calculation, logout and a password-reset email linking to `novaq.site`.

Open items:

- The Render static site `novaq-frontend` (`novaq-frontend.onrender.com`) is still live as a fallback. Suspend it after a few stable days; keep `Qcu-NovaQ-Analytics` running.
- Remote branch `feat/cloudflare-pages-api-bridge` is merged and can be deleted.
- Pages Functions are set to fail open: past the free 100,000 requests/day, `/api/*` would fall back to the SPA HTML.
- Pre-login rate limits key on client IP. Through the Worker, many users may reach Render from shared Cloudflare egress IPs, so they can share one auth bucket. Watch for 429s on login.

## Shared Queue Enhancement: Phase 1 Segment Foundation (2026-09-24)

Spec and plan:

- `docs/superpowers/specs/2026-09-24-shared-queue-segment-foundation.md`
- `docs/superpowers/plans/2026-09-24-shared-queue-segment-foundation-plan.md`

Current verified state:

- New pure module `backend/queueing_engine/services/shared_segments.py`. It keeps demand periods (λ, μ per hour) apart from staffing segments (c), in whole minutes inside one day. It rejects gaps, overlaps, out-of-order items, incomplete horizon coverage, and staffing segments that cross a demand boundary. A shorter staffing segment inherits its demand period's rates and is labelled `inherited_from_demand_period`. Each segment is evaluated through `select_model` (M/M/c, or M/M/1 when c = 1), with duration-weighted arrivals, server-hours, offered work, and steady-state waiting customer-hours. Unstable, no-capacity, and failed segments report `None`, never 0.
- Nothing imports it yet (a test enforces this). No API, schema, database, frontend, report, legacy shared DES, or separate-queue code changed.
- Verification: `tests/test_shared_segments.py` has 50 tests, including independent Erlang-B references, exact textbook cases, and the NovaMart 14-day rows. An in-memory mutation check confirmed that five deliberate faults are caught. Backend 1083 passed, 3 skipped, 1 xfailed (the 1033 baseline plus 50). Ruff and mypy are clean. The frontend was not re-run because it was untouched.
- Next (needs approval): Phase 2 dynamic capacity optimization. Workforce inputs, transition and closing policies, and model scope beyond M/M/c remain open decisions.

## Shared Queue Enhancement: Phase 2 Capacity Optimization (2026-09-24)

Spec and plan:

- `docs/superpowers/specs/2026-09-24-shared-queue-capacity-optimization.md`
- `docs/superpowers/plans/2026-09-24-shared-queue-capacity-optimization-plan.md`

Current verified state:

- Pre-Phase 2 review fix `ad8ed236`: segment rows now state `waiting_attribution` and `backlog_represented: false`. The zero-demand and closed notes say that backlog from earlier segments is not represented, and the textbook reference case states its full λ, μ, and c. No value changed.
- New pure module `backend/queueing_engine/services/shared_capacity.py`. For each staffing segment it evaluates every server count in [min, max] through the Phase 1 `evaluate_segment`, and costs each over the segment's duration:
  - server cost = c × server cost per hour × T;
  - waiting cost = λ × Wq × T × waiting cost per customer-hour, with Wq in hours.
  It enforces stability, the utilization ceiling, and the optional maximum wait, all with the 1e-9 `THRESHOLD_TOLERANCE`. It picks the cheapest feasible count; ties within a relative 1e-9 go to fewer servers. Closing (c = 0) is possible only when `min_servers` = 0 and nobody arrives. Undefined costs stay `None`, and totals and the cost change are withheld with a reason. The module holds no operating defaults; the caller supplies every cost, target, and bound. Every candidate, the configuration, and the inputs are kept as provenance.
- Nothing legacy imports either new module; a test enforces this. The legacy optimizer, `/optimize` and `/optimize/batch`, scenario schema versions, Decision, reports, the legacy shared DES, and all separate-queue code are unchanged.
- Verification: `tests/test_shared_capacity.py` has 28 tests, covering hand-computed costs, an exact 14.5/14.5 tie, float noise at the target, the max-wait boundary, zero demand and zero capacity, unstable and infeasible segments, duration scaling, a brute-force optimum from an independent Erlang-B recursion, and agreement with the legacy optimizer's `c_optimal`, `cost_optimal`, and `cost_current` on the NovaMart 14-day average (plan 2,3,3,3,3,4,3,4,4,3,3,2,2 = 39 server-hours versus 55 current). An in-memory mutation check confirmed that seven deliberate faults are caught. Backend 1112 passed, 3 skipped (Postgres migration chain), 1 xfailed. Ruff and mypy are clean.
- Next (needs approval): Phase 3 workforce scheduling. It is blocked on workforce inputs (availability, shift lengths, break rules, labor cost) and on the transition, closing, and sequential-versus-joint decisions.

## Shared Queue Enhancement: Phase 3 Continuous Shared DES (2026-09-24)

The product owner renumbered the phases: Phase 3 is now the continuous DES, and workforce scheduling moves later.

Spec and plan:

- `docs/superpowers/specs/2026-09-24-shared-queue-continuous-des.md`
- `docs/superpowers/plans/2026-09-24-shared-queue-continuous-des-plan.md`

Current verified state:

- New pure module `backend/queueing_engine/simulation/shared_continuous_des.py`. It is one event-driven run over the whole horizon, with no restart, warm-up, or reset at boundaries.
  - Arrivals: Poisson with the demand period's λ, exact by memorylessness.
  - Service: each customer carries unit work Exp(1), drawn once. Service lasts work / μ, with μ from the period in which service starts, and is never redrawn or interrupted.
  - One common first-come-first-served line; the lowest free server number serves first.
  - Capacity decreases close idle servers first and then drain busy ones (no new customer; close at completion). Increases reactivate draining servers before opening others.
  - Same-time order: completions, then capacity changes, then arrivals.
  - Customers keep their ids and waits for the whole run. Conservation is reported, and so are capacity transitions, drain records, and server-hours above schedule.
  - Seeds come from numpy `SeedSequence` with two streams; unseeded runs record their entropy.
  - `simulate_prescribed` runs exact deterministic cases. `staffing_from_capacity_result` feeds a complete Phase 2 plan to the DES.
- Tolerance policy: the new pipeline uses `THRESHOLD_TOLERANCE` (1e-9), the same constant `is_saturated` applies. It is stated in the Phase 2 provenance and pinned by a test. The legacy optimizer keeps its 1e-12.
- **Closing policy is UNRESOLVED.** The engine observes the horizon only and reports customers still waiting or in service at the end. Nobody is served after closing, and nobody is removed. The separate-queue day drains after closing, but that is not approved for shared queues.
- Nothing legacy imports the module; the isolation test covers it. The legacy shared DES, separate-queue code, APIs, scenarios, Decision, and reports are unchanged.
- Verification:
  - `tests/test_shared_continuous_des.py` has 49 tests: exact hand-computed cases (increase, decrease with drain, idle-first closing, zero capacity with backlog, zero demand with backlog, same-time ordering in both directions, a μ change, the horizon end), sample-path identities (∫queue = Σ waits; busy hours = Σ service), conservation, identity and first-come-first-served order on 20 seeded multi-transition runs, reproducibility, and statistical checks.
  - The Erlang C benchmark (λ 40, μ 20, c 3, 100 × 24 h, 95,670 customers) fell within 1.05 standard errors on Lq, P(wait), and Wq.
  - A source-level mutation check caught 9 of 9 faults after one ordering test was strengthened.
  - Backend 1162 passed, 3 skipped, 1 xfailed. Ruff and mypy are clean.

## Shared Queue Enhancement: Phase 3A Closing Policy and Day Cost (2026-09-25)

Spec and plan:

- `docs/superpowers/specs/2026-09-25-shared-queue-closing-policy.md`
- `docs/superpowers/plans/2026-09-25-shared-queue-closing-policy-plan.md`

The product owner approved the closing policy on 2026-09-25. It replaces the Phase 3 UNRESOLVED state.

Current verified state:

- `simulation/shared_continuous_des.py` (engine `novaq-shared-continuous-des-v2`): `simulate_prescribed` and `simulate_shared_day` require `closing_policy` (`DRAIN` or `HARD_CUTOFF`); there is no default. Events before closing are unchanged from Phase 3.
  - At closing, completions at exactly that time are processed first. The at-close state is recorded: waiting customers, customers in service, and accepting and draining servers.
  - HARD_CUTOFF: waiting customers become `unserved_at_close` (`hard_cutoff`). Services already under way finish, and nobody starts service at or after closing.
  - DRAIN: the accepting servers on duty serve the line first come, first served, with no cap. Services that start after closing use the final demand period's μ. A draining server only finishes its own customer. With nobody on duty, waiting customers become `unserved_at_close` (`no_eligible_server`), so draining cannot run forever. The engine asserts that every customer is resolved and every server closed.
  - Outputs: statuses are `departed` and `unserved_at_close`. The `closing` block replaces `horizon_end` and reports overrun, after-close server-hours, and after-close waits. `cost_quantities` holds hours and counts only. Events at or after closing carry `segment_id: None`. In-horizon keys keep their Phase 3 meaning.
- New `services/shared_day_cost.py`: `DayCostRates` takes four required rates, and `None` means not supplied. `cost_shared_day` computes regular server-hours × rate + overtime server-hours × rate + waiting customer-hours × rate + unserved count × rate. The unserved term applies only when `unserved_possible` (HARD_CUTOFF, or DRAIN with 0 servers in the final segment). A missing applicable rate withholds the total with a reason; it is never replaced by 0. Server-hours are modeled capacity hours, not necessarily paid employee-hours.
- Nothing legacy imports either module; the isolation test now covers the cost module too. The legacy shared DES, separate-queue code, APIs, scenarios, reports, config rates, and frontend are unchanged.
- Verification:
  - `tests/test_shared_continuous_des.py` grew from 49 to 111 tests.
    - Every Phase 3 exact case now runs under both policies and must agree.
    - New exact closing cases: an empty system; waiting customers under both policies; a completion exactly at closing; a server draining at closing; a zero-capacity final segment under both policies; a backlog from a zero-capacity period; an increase just before closing; the final-μ rule; arrivals stopping at closing; and a required, validated policy.
    - Whole-run sample-path identities, including overtime = service time after closing.
    - Cross-policy equivalence before closing on 40 seeded multi-transition runs.
    - An independent first-come-first-served recursion from the at-close state agrees on 30 seeded overloaded runs (every run closes with a line; 5 of 15 per policy with a draining server; 144 after-close starts under DRAIN).
    - The Erlang C benchmark passes under both policies.
  - `tests/test_shared_day_cost.py` has 16 tests: hand totals (DRAIN 255, HARD_CUTOFF 247.5 at rates 80, 120, 100, 50), missing and zero rates, the applicability rule, invalid rates, no defaults, and no config import.
  - A source-level mutation check caught 14 of 15 faults. The miss, a max-queue update after closing, is an equivalent mutant: the line cannot grow after closing.
  - Backend 1240 passed, 3 skipped, 1 xfailed (1162 + 78 new). Ruff is clean. `mypy .` reports 5 errors, all in the gitignored, untracked `outputs/technical-paper/build_chapters_4_5.py` (last modified 2026-09-20, imports only docx, matplotlib, and pandas). `mypy . --exclude '^outputs/'` is clean on 157 files. Frontend not run: nothing under `frontend/` changed.
- Next (needs approval): Phase 4. Monte Carlo and playback have not started.

## Shared Queue Enhancement: Phase 4 DES Replications and Event Playback (2026-09-25)

Spec and plan:

- `docs/superpowers/specs/2026-09-25-shared-queue-des-replications-playback.md`
- `docs/superpowers/plans/2026-09-25-shared-queue-des-replications-playback-plan.md`

Current verified state (backend only; no API, frontend, Decision, Report, scenario, or workforce change):

- Engine (`simulation/shared_continuous_des.py`): the random draws moved into `_draw_arrivals`, and `simulate_shared_replication(seed_sequence=...)` was added. `simulate_shared_day` output is byte-identical: a SHA-256 digest of 100 runs (2 policies × 25 seeds × 2 configurations) is unchanged.
- New `simulation/shared_replications.py`, `run_shared_replications(...)`:
  - Every replication runs the Phase 3A continuous DES over the whole horizon with the scenario's own rates. No ±20%/±10% perturbation is applied.
  - `replications` (1..`config.MC_MAX_TRIALS`), `seed`, and `closing_policy` are required. Replication i uses `SeedSequence(entropy=root_entropy, spawn_key=(i,))`.
  - Each replication keeps one scalar row (traces off):
    - customers: arrivals, served, and unserved;
    - waits: the sum and mean over served customers;
    - waiting-hours before and after closing, and the in-horizon time-average queue and maximum;
    - busy and available server-hours in the horizon and after closing (overtime);
    - scheduled hours and hours above schedule;
    - utilization with explicit denominators, and overrun;
    - cost per replication and criterion outcomes, when supplied.
  - Aggregates:
    - Student-t 95% intervals, matching the separate-queue `_summarize_metric` convention, with `n_undefined` counts;
    - the mean of replication mean waits and the customer-weighted wait, with numerator and denominator;
    - summed customer totals and descriptive outcome counts;
    - cost aggregated from per-replication costs; the total is withheld when an applicable rate is missing.
  - `FailureCriteria` (mean wait, utilization, unserved, and overrun) has no default thresholds. Per-criterion and combined proportions carry Wilson intervals with numerator, denominator, and not-evaluable counts. `verdict` is always `None`, because no approved pass/fail rule exists.
- New `simulation/shared_playback.py`: `prepare_shared_playback` and `playback_from_replications` regenerate one identified replication with its full trace.
  - Events are the engine's own trace.
  - An independent replay checks FCFS, legal server transitions, queue length at every event, schedule after staffing changes, the closing phase, and final resolution.
  - The replay recomputes timelines, counts, and time integrals and compares them with the engine. `playback_from_replications` also requires exact equality with the stored replication row and the same engine version.
  - Queue entry and departure are represented by the `arrival` and `service_end` events; the engine has no separate events for them.
- Nothing legacy imports these modules; the isolation test covers both.
- Verification:
  - `tests/test_shared_replications.py` has 46 tests:
    - every replication matches a recomputation from customer rows and transition intervals (both policies, including 0 servers at closing);
    - reproducibility and recorded entropy;
    - distinct, regenerable streams and uncorrelated counts (400 replications);
    - a Poisson dispersion index near 1 (no perturbation);
    - waiting-time denominators by hand;
    - intervals matching `scipy.stats.t.interval`, the separate-queue convention, and `binomtest(...).proportion_ci(method="wilson")`;
    - per-replication and aggregate cost;
    - missing rates, criteria counts, not-evaluable counting, the tolerance boundary, and validation;
    - Erlang C within 4 SE (λ 40, μ 20, c 3; 60 × 24 h).
  - `tests/test_shared_playback.py` has 21 tests:
    - an exact hand-computed playback, and events equal to the engine trace;
    - 72 regenerated replications equal their stored rows (3 configurations × 2 policies);
    - reproducibility;
    - six tampered event streams, each rejected for its intended reason;
    - mismatched rows, foreign engine versions, and invalid requests refused.
  - Fault injection caught 15 of 15 faults.
  - Backend 1307 passed, 3 skipped, 1 xfailed (1240 + 67 new; all 16 separate-queue test files included). The run's 6 h 29 min wall time includes a system sleep from 01:44 to 06:02. Ruff is clean. `mypy . --exclude '^outputs/'` is clean on 161 files; the gitignored `outputs/technical-paper/build_chapters_4_5.py` errors from Phase 3A remain. Frontend not run: nothing under `frontend/` changed.
- Not implemented: a parameter-uncertainty experiment, an acceptance (PASS/FAIL) rule, production API endpoints, the frontend player, Decision and Report integration, and workforce scheduling. Each needs approval.

## Shared Queue Enhancement: Phase 5B-1 Workforce Foundation (2026-09-26)

Spec and plan:

- `docs/superpowers/specs/2026-09-26-shared-queue-workforce-foundation.md`
- `docs/superpowers/plans/2026-09-26-shared-queue-workforce-foundation-plan.md`

Phase 5A (2026-09-25) was a read-only design report delivered in chat. Its decisions D1-D16 remain open.

Current verified state (one pure module; no solver, DES, cost, API, schema, scenario, frontend, Decision, or Report change):

- New `services/shared_workforce.py`:
  - Inputs:
    - `Employee`: a pseudonymous id, availability windows, and `EmployeePay` (regular rate, overtime rate, daily regular paid minutes). Every pay value may be `None` (not supplied) and is never read as 0.
    - `ShiftRules`: boundaries, length range, boundary granularity, maximum shifts, and rest between shifts (required only when split shifts are allowed).
    - `BreakRule` / `BreakRequirement`: a length range, a minimum gap, and named breaks with a duration, an explicit paid flag, and start-offset windows.
    - `WorkforceRules.register_count`.
    - A roster of `ScheduledShift` / `ScheduledBreak`. Break length and paid status come from the rule.
  - Validation:
    - Malformed inputs raise `SharedSegmentError` with every problem listed.
    - Roster rule breaches are returned as 17 coded violations with reasons. Status is INVALID, INCOMPLETE (missing pay values or break-rule coverage), or COMPLETE.
    - Hours are withheld, not guessed, for an employee whose time has no well-defined active/break split: overlapping shifts or breaks, a break outside its shift, or an unknown break length.
  - Outputs, all scheduled (not simulated):
    - scheduled, paid, break (paid and unpaid), and active server minutes (split inside and outside the horizon);
    - regular and overtime paid minutes, with the overtime start minute;
    - active-server steps, the register check, and coverage shortfall and surplus against optional required staffing segments.
  - No cost, no optimized roster. Registers are counted, not identified.
- Nothing legacy imports the module; the isolation test covers it. The separate-queue staff and break sheets, lane breaks, and pre-break cutoff are not used.
- Verification:
  - `tests/test_shared_workforce.py` has 53 tests on labeled synthetic data:
    - hand-computed hours, overtime start, steps, register intervals, and coverage;
    - split shifts;
    - four threshold edges;
    - every violation code with its exact code list;
    - malformed employees, rules, roster, and staffing;
    - identities and an independent minute-by-minute brute force (active count, coverage, register check, active minutes, and overtime start) on 200 generated rosters.
  - A first fault-injection pass caught 10 of 12 faults. The two misses exposed missing tests (an overtime-start boundary and a too-late break); after adding them, 12 of 12 were caught.
  - Backend 1360 passed, 3 skipped, 1 xfailed (1307 + 53; all 16 separate-queue test files included). Ruff is clean. `mypy . --exclude '^outputs/'` is clean on 163 files. Frontend not run: nothing under `frontend/` changed.
- Next (needs approval): Phase 5B-2 and later (sequential and integrated MILP, named-server DES, workforce cost), plus the open Phase 5A decisions.

## Shared Queue Enhancement: Phase 5B-2 Sequential Rostering MILP (2026-09-26)

Spec and plan:

- `docs/superpowers/specs/2026-09-26-shared-queue-sequential-rostering.md`
- `docs/superpowers/plans/2026-09-26-shared-queue-sequential-rostering-plan.md`

Product-owner decisions (2026-09-26):

- Sequential only: Phase 2's selected server counts are a hard coverage target, solved with `scipy.optimize.milp` (HiGHS). No dependency was added.
- Break starts lie on a caller-supplied clock grid, `break_start_granularity_minutes`, with no default.
- Surplus is counted and paid only through wages. There is no surplus rate.
- Solver limits are required inputs with no defaults: time limit, `mip_rel_gap`, and a pattern cap.

Current verified state (one pure module; no DES, cost-integration, API, schema, scenario, frontend, Decision, or Report change):

- New `services/shared_rostering.py`:
  - Patterns: every 5B-1-valid single shift with its breaks on the break grid. Generation stops with `PATTERN_LIMIT_EXCEEDED` rather than truncating.
  - MILP:
    - a binary choice per pattern;
    - on every elementary interval, which is exact in continuous time: active ≥ required inside the horizon, and active ≤ registers all day;
    - maximum shifts per employee, and interval-clique rows for split-shift rest;
    - exact regular and overtime: a per-pattern cost with one shift a day, and a big-M binary switch for split shifts;
    - a wages-only objective.
  - `INCOMPLETE`, with nothing solved and no cost invented, when an admissible shift length has no break rule, or when the objective needs a missing pay value. The overtime rate is needed only when an admissible plan exceeds the threshold, found by an exact maximum-paid recursion.
  - Certificates before solving: a requirement above the registers, and fewer available employees than required in an interval.
  - Statuses: `OPTIMAL`, `FEASIBLE_NOT_PROVEN_OPTIMAL`, `NO_SOLUTION_FOUND`, `INFEASIBLE`, `INCOMPLETE`, `PATTERN_LIMIT_EXCEEDED`, `SOLVER_ERROR`, `VERIFICATION_FAILED`.
  - Feasibility is FEASIBLE only after exact verification:
    - integrality within 1e-6;
    - every row holds in integer arithmetic;
    - 5B-1 `evaluate_roster` finds no violation, shortfall, or register excess;
    - the labor cost from the 5B-1 minutes equals the model objective.
  - Solver status, message, objective, dual bound, gap, nodes, wall time, options, unchanged HiGHS defaults, and versions are reported. Uniqueness is `NOT_ESTABLISHED`.
  - `optimize_roster_for_capacity_plan` takes a Phase 2 plan through `staffing_from_capacity_result`.
- Nothing legacy imports the module; the isolation test covers it.
- Verification:
  - `tests/test_shared_rostering.py` has 88 tests on labeled synthetic data:
    - all 12 required areas;
    - an independent brute force (minute loops plus the 5B-1 oracle) for pattern-set equality and optimal-set membership;
    - 40 seeded random instances;
    - a Phase 2 plan as the target;
    - simulated solver terminations.
  - Fault injection caught 22 of 22 faults, after 3 missing tests were added.
  - Ruff is clean. `mypy . --exclude '^outputs/'` is clean on 165 files.
  - The full backend suite, `python -m pytest tests/ -x`, gave 1448 passed, 3 skipped, and 1 xfailed. That run includes every Separate Queue test file.
- Scale, on this machine with synthetic employees and the NovaMart Phase 2 plan as the target:
  - an 8-employee, 13-hour day is proven optimal in 1.9 s with a 60-minute break grid and in 19.7 s with a 30-minute grid;
  - a 15-minute grid gives 62,568 patterns and no solution within 180 s.
  - Solve time on real inputs is UNKNOWN.
- Next (needs approval):
  - 5B-3 integrated MILP;
  - 5B-4 named-employee DES;
  - 5B-5 workforce cost integration;
  - DES validation of rosters, and an acceptance rule;
  - a formulation that scales to fine break grids.

## Shared Queue Enhancement: Phase 5B-3 Integrated Planning MILP (2026-09-28)

Spec and plan:

- `docs/superpowers/specs/2026-09-28-shared-queue-integrated-planning.md`
- `docs/superpowers/plans/2026-09-28-shared-queue-integrated-planning-plan.md`

Product-owner decision (2026-09-28), capacity semantics "every interval":

- The analytical server count is the number of employees on duty on every elementary interval between shift, break, demand-period, and staffing-segment boundaries.
- Each interval is Phase 1/2's stationary M/M/c evaluation, with its demand period's λ and μ, over its own length.
- Waiting cost = Σ waiting rate × λ × Wq(c) × hours. Stability, the utilization target, and the maximum wait are checked on every interval.
- Staffing segments only group the report.
- The short-interval steady-state approximation is disclosed in the output.

Current verified state (one pure module; no DES, API, schema, scenario, frontend, Decision, or Report change; the 5B-2 sequential optimizer is unchanged):

- New `services/shared_integrated.py`:
  - The objective is scheduled wages (5B-1 regular and overtime minutes at the employee's rates) plus analytical waiting cost. Phase 2's server cost per server-hour is never charged. Every employee on duty is paid and staffs the queue, so surplus is never hidden.
  - The model is 5B-2's `_build_model`, built with zero-requirement pieces. It keeps the pattern columns, register rows, max-shift and split-shift rows, and exact regular and overtime cost. On top of it, for every in-horizon elementary interval i and every admissible count c, it adds:
    - a binary `z[i,c]`;
    - the link row `Σ_q a[q,i] x_q − Σ_c c z[i,c] = 0`;
    - the choose-one row `Σ_c z[i,c] = 1`.
    Admissible counts lie in [min_servers, min(max_servers, registers)] and pass Phase 2's `evaluate_candidate` rule.
  - `PlanningConfig` has no defaults: waiting rate, target, maximum wait, and minimum and maximum servers. A missing waiting rate gives `INCOMPLETE` when some in-horizon λ > 0, never 0.
  - Certificates before solving:
    - `NO_ADMISSIBLE_CAPACITY`, which needs no patterns;
    - `INSUFFICIENT_WORKFORCE`, only with a complete pattern set.
    HiGHS status 2 gives `SOLVER_PROVED_INFEASIBLE`.
  - Statuses are as in 5B-2. A time limit without a solution is `NO_SOLUTION_FOUND` with UNKNOWN feasibility, never INFEASIBLE.
  - Feasibility is FEASIBLE only after exact verification:
    - integrality;
    - every row and bound in integer arithmetic;
    - no 5B-1 violation or register excess;
    - the selected count equals the 5B-1 on-duty count on every interval;
    - the independent `evaluate_planning_cost` places the roster in the feasible set;
    - R/O minutes match;
    - wages and waiting match the model's terms within a relative 1e-9.
  - `evaluate_planning_cost` prices any roster exactly without the MILP and states whether it is in the integrated feasible set.
  - `compare_with_sequential` runs Phase 2 and then 5B-2, and prices both rosters on the same objective. "Integrated no worse" is claimed only when the sequential roster is in the integrated feasible set.
- Nothing legacy imports the module; it joins the isolation list in `tests/test_shared_segments.py`.
- Verification:
  - `tests/test_shared_integrated.py` has 93 collected tests (43 test functions, with parametrization and 40 seeds) on labeled synthetic data:
    - an independent brute force: 5B-2 test enumeration, a minute-by-minute on-duty count, Phase 1 tests' Erlang-B recursion, and its own wage arithmetic;
    - hand-computed optima, including two tied rosters;
    - all 10 required verification points;
    - the comparison logic;
    - 40 seeded random instances;
    - simulated solver terminations and corrupted vectors.
  - Fault injection (28 mutants of the formulation, the verification, the evaluation, and the comparison; scratch script, not committed) caught 28 of 28, after 4 tests and 1 assertion were added. One mutant, register-capped candidate counts, changed only the certificate's reported counts; an assertion now pins them.
  - Ruff is clean. `mypy . --exclude '^outputs/'` is clean on 167 files.
  - The full backend suite, `python -m pytest tests/ -x`, gave 1541 passed, 3 skipped, and 1 xfailed (the 1448 baseline plus 93 new tests). That run includes every Separate Queue test file.
  - `git status` shows no change to any existing backend source file. The only existing test change is one line in `tests/test_shared_segments.py`, which adds the module to the isolation list.
- Benchmark (not a test): NovaMart 14-day-average λ and μ rows (`NOVAMART_AVERAGE_ROWS`); synthetic employees, pay, shift and break rules, and registers (the 5B-2 probe set: 8 employees, 05:00-18:00, 4 registers); waiting 100 per customer-hour, target 0.70, servers 1-24, Phase 2 server cost 94.375 per hour; time limit 300 s; mip_rel_gap 0. Phase 2 selected [2, 3, 3, 3, 3, 4, 3, 4, 4, 3, 3, 2, 2] servers per hour. The comparison prices both rosters with the same exact evaluator.
  - Grid 60 (5,424 patterns):
    - Integrated: OPTIMAL (HiGHS status 0, gap 0) at 3759.24 = wages 3206 + waiting 553.24, in a 4.7 s solve.
    - Sequential: 5B-2 OPTIMAL at wages 3307, which is 3828.02 on the planning objective.
    - The sequential roster is in the integrated feasible set, so the integrated plan is no worse, by 68.77.
  - Grid 30 (19,528 patterns):
    - Integrated: OPTIMAL at 3670.78 = 3047 + 623.78, in 96.5 s.
    - Sequential: OPTIMAL at wages 3124, in 34.4 s. That is 3684.31 on the planning objective.
    - The integrated plan is no worse, by 13.54.
  - Grid 15 (62,568 patterns; integrated model 62,670 columns, 158 rows, 3,306,228 nonzeros): no solution within the 300 s limit, integrated or sequential.
    - Both runs are `NO_SOLUTION_FOUND` with feasibility UNKNOWN, and nothing is compared.
    - The integrated `milp` call returned after 342.4 s, 42 s over the limit; the cause of the overrun is UNKNOWN.
  - Integrated on-duty counts differ from Phase 2's. For example, at grid 60 the count is 2-3 in 06:00-07:00, where Phase 2 selected 3, and 3-4 in 07:00-10:00, where Phase 2 selected 3.
  - The grid-60 optimum is above the grid-30 optimum. That is consistent with the grid-60 patterns being a subset of the grid-30 patterns (INFERRED from the grid definition).
  - Runtimes depend on the machine and its load. The 5B-2 grid-30 solve is recorded at 19.7 s in the 5B-2 section, took 27.6 s in the 15-minute investigation, and took 34.4 s here.
- 15-minute-grid investigation (5B-2 sequential model, same benchmark):
  - The model is 58 rows × 62,568 binary columns with 1,684,296 nonzeros, built in about 5 s.
  - The LP relaxation alone is optimal at 3006.7 in 16.3 s of HiGHS time.
  - MIP with presolve:
    - Presolve ran from 3 s to 187 s. It made only the reductions (1,008 columns, 21,960 nonzeros) that the LP presolve made in 7 s.
    - The root started at 199.7 s, and each root cut round took about 5-10 s.
    - At 303 s there were 0 nodes and no incumbent (dual bound 3007).
  - MIP without presolve: feasibility jump found 3582 at 12.8 s. At the limit the root cut loop was still running, with 0 nodes and a 16.05% gap.
  - The time therefore goes to MIP presolve and then the root cut loop, not to the LP or the build.
  - Which presolve rule takes the time is UNKNOWN. SciPy's HiGHS options reject `presolve_rule_logging`, and `highspy` is not installed and was not added.
  - The grid-30 patterns are a subset of the grid-15 patterns, so the grid-15 optima are at most the grid-30 optima (INFERRED, not solved).
  - No constraint was changed. PROPOSED only:
    - an exact formulation with implicit break placement;
    - dropping the in-horizon register rows of the integrated model. The link and choose-one rows already imply them, since every admissible c ≤ registers. That preserves the feasible set; the runtime effect is UNKNOWN. The link rows repeat the pattern coefficients of those rows, which is why the integrated model has about twice the nonzeros.
- Next (needs approval):
  - 5B-4 named-employee DES;
  - 5B-5 workforce cost integration;
  - DES validation of rosters, and an acceptance rule;
  - a formulation that scales to fine break grids;
  - API and UI exposure.

## Shared Queue Enhancement: Phase 5B-4.0 Anonymous-Engine Pin and 5B-4.1 Named-Employee DES Policy Contract (2026-09-28)

Spec and plan:

- `docs/superpowers/specs/2026-09-28-shared-queue-named-employee-des-policy.md`
- `docs/superpowers/plans/2026-09-28-shared-queue-named-employee-des-policy-plan.md`

Product-owner approval (2026-09-28): "The Phase 5B-4A design is approved using P1–P9 and X1–X7 exactly as supplied by the user." The 5B-4A design was a chat report, and this spec is its first repository record.

- Single rules in the design are APPROVED SPECIFICATION.
- Where the design offered alternatives or open questions, the approval did not choose, so the selection is UNKNOWN with no default:
  - P1, P2, P5, P7, X1, and X5 have unselected alternatives;
  - P3, P4, P6, P8, P9, and X6 have open sub-questions.

  The spec's "Open selections" table maps each to the sub-phase it blocks.
- X7 is mandatory: the named DES takes `required_staffing` as a required input with no default, validated by `validate_timeline`, never empty and never optional.

Current verified state (tests and docs only; no production code change):

- 5B-4.0 (implemented):
  - `tests/test_shared_continuous_des_pin.py` and `tests/fixtures/shared_continuous_des_output_pin.json` pin the complete result dictionary of the anonymous engine's `simulate_prescribed`, key by key with exact equality, on 7 fixed-arrival cases:
    - the main transitions case under DRAIN, under HARD_CUTOFF, and under DRAIN with a trace cap of 7;
    - "no one on duty at closing" under both policies;
    - "no arrivals" under both policies.
  - No seed and no random number are used, and every input is binary-exact.
  - The expected values are the engine's output at `d5723aba` (a characterization). The main case's schedule, transitions, at-close state, and overrun were also derived by hand, and one test asserts that derivation without the fixture.
  - The existing 34 hand-computed test functions (111 collected) in `tests/test_shared_continuous_des.py` are unchanged; the pin adds whole-output coverage.
  - `shared_continuous_des.py` is unchanged.
- 5B-4.1 (documented, not implemented):
  - the employee state machine, capacity definitions, transition rules, invariants 1-14, and the proposed interface;
  - Separate Queue break code is protected and is not reused;
  - the numpy pins CONFLICT (`requirements.txt` <2.3, lock 2.4.6, production lock 2.2.6, local 2.4.6), and cross-version RNG equality is UNKNOWN;
  - the named engine adds no random process, and test reference values come from prescribed arrivals.
- No named-employee DES exists, and `shared_named_des.py` was not created.
- Verification:
  - The new pin file has 9 tests, all passing.
  - Fault injection (15 source-level mutants of an in-memory engine copy; scratch script, not committed): 15 of 15 caught, and the unmutated copy matched.
  - The focused shared anonymous-engine suites gave 254 passed.
  - Ruff is clean. `mypy . --exclude '^outputs/'` is clean on 168 files.
  - The full backend suite, `python -m pytest tests/ -x`, gave 1550 passed, 3 skipped, and 1 xfailed (the 1541 baseline plus 9 new tests). That run includes every Separate Queue test file.
  - `git status` shows no change to any existing backend source file or existing test.
- Next (needs approval): the open selections in the spec, then 5B-4.2 (employee timeline state machine). Superseded: 5B-4.2 is done (next section).

## Shared Queue Enhancement: Phase 5B-4.2 Pure Named-Employee State Machine (2026-09-28)

Spec and plan:

- `docs/superpowers/specs/2026-09-28-shared-queue-employee-state-machine.md`
- `docs/superpowers/plans/2026-09-28-shared-queue-employee-state-machine-plan.md`

The Phase 5B-4.2 request approved P1-P9 and X1-X7 and supplied explicit decisions (quoted in the policy spec, "Explicit decisions of 2026-09-28"):

- P1 (a): a delayed break keeps its full duration from its actual start, and a delay pushes later breaks by the minimum gap.
- No pre-break cutoff and no pre-shift-end cutoff; service is non-preemptive.
- A later split shift activates at its actual release plus the required rest.
- P4: registers are identified 1..K; the wait order is earliest wait start, then employee_id; the lowest-numbered free register is assigned first.
- P5-P7 must be representable without a selection.
- Base states are mutually exclusive, and attributes add no elapsed time.

Current verified state:

- `backend/queueing_engine/simulation/shared_employee_states.py` (new) is the employee, break, shift, and register timeline of a validated 5B-1 roster (X4 precondition).
  - Seven mutually exclusive base states, with identified registers and the X2 employee-only same-time order.
  - `hold_past_shift_end` is required, with no default.
  - The closing inputs `Release`, `EndBreakAtClosing`, and `CancelPendingBreaks` represent every P5, P6, and P7 alternative without choosing one.
  - There are no customers, queue, service-time generation, or random numbers. Service starts and completions are caller inputs.
- No existing production module changed. `tests/test_shared_segments.py` adds the module to the isolation list.
- The policy spec was updated first:
  - the decisions of 2026-09-28;
  - the undetermined cases;
  - the withdrawn capacity bound (below).
- Tests: `tests/test_shared_employee_states.py` (new, synthetic, binary-exact).
  - 33 test functions with hand-computed timelines cover every required case.
  - An independent checker of invariants 1-16 runs on every successful run.
  - The invariants are VERIFIED on these cases only, not proven for every input.
- Fault injection: 35 source-level mutants of a module copy (a scratch script, not committed).
  - The first run killed 32 of 35.
  - Three tests were added for the survivors (completion order, hold before closing, not-activated check order).
  - After that, 35 of 35 were killed.
- Discrepancy with the 5B-4.1 spec: the INFERRED bound "before closing, accepting servers never exceed the 5B-1 scheduled active count" is false under the gap push.
  - `test_gap_push_puts_the_employee_on_duty_in_scheduled_break_time` shows it.
  - The bound is withdrawn in the policy spec. A weaker bound is UNKNOWN (P8).
- Undetermined, recorded in the module's `UNDETERMINED` list:
  - A break due before a delayed split-shift activation: UNKNOWN, and the module raises `UndeterminedPolicyError`.
  - Closing is placed right after completions in the X2 order: INFERRED.
  - A delayed split shift keeps its scheduled end, and is not activated when the delayed activation reaches it: INFERRED.
  - The P5, P6, and P7 selections: UNKNOWN.
- NOT TESTED: tolerances for non-dyadic times. A scratch probe on a 5-minute grid showed a break's end minus start differing from 10/60 at the last binary digit.
- Next (needs explicit approval): 5B-4.3, customer and queue integration. It needs the P5, P6, and P7 selections, X1, the P8 output shape, the X6 output field, and decisions on the undetermined cases. Superseded: 5B-4.3 is done (next section).

## Shared Queue Enhancement: Phase 5B-4.3 Named-Employee Continuous Shared-Queue DES (2026-09-28)

Spec and plan:

- `docs/superpowers/specs/2026-09-28-shared-queue-named-des.md`
- `docs/superpowers/plans/2026-09-28-shared-queue-named-des-plan.md`

The Phase 5B-4.3 request supplied P1-P9 and X1-X7 as rules to use exactly (recorded in the policy spec, "Explicit decisions of 2026-09-28 (Phase 5B-4.3)"): DRAIN crew frozen from employees accepting immediately before closing and serving until the line is empty; HARD_CUTOFF releases idle employees at closing and busy ones at completion; breaks in progress at closing truncated, pending ones cancelled_at_closing; X1 longest available, ties by employee_id; X2 places the closing boundary second; X6 `no_eligible_employee`; P8 six series and two separate gaps; and a new P3 rule for breaks of a delayed split shift.

Current verified state:

- `backend/queueing_engine/simulation/shared_named_des.py` (new): `simulate_named_prescribed` on prescribed (hour, work) arrivals.
  - One FCFS line; named employees driven through the 5B-4.2 state machine; the X2 instant loop; closing inputs chosen by the state immediately before closing; X1 by earliest time of becoming AVAILABLE.
  - Required inputs, no defaults: `closing_policy`, `employee_policy` (`EmployeeDesPolicy`, each field accepts only its approved value, `APPROVED_EMPLOYEE_POLICY`), and `required_staffing` (X7, validated by `validate_timeline`).
  - Output: customer rows (`employee_id`, `register_id` replace `server_id`), counts, the queue integral, `at_close` (frozen crew, closing inputs), P8 staffing timeline and windows, the employee timeline, and a customer trace. No random numbers and no cost.
- `shared_employee_states.py` amended (version v2): the P3 split-shift break rule replaces the 5B-4.2 `UndeterminedPolicyError`; roster-derived instants are computed in whole minutes (float safeguard); read-only `snapshot()`.
  - The whole-minute change fixes a VERIFIED hazard: adding minutes in hours missed the exact conversion for 2,487 of 11,520 (start, duration) pairs; two new tests fail against dfa8fe75 and pass now. Binary-exact results are unchanged.
  - One 5B-4.2 expectation changed because the approved P3 rule changed it (`test_split_shift_overrun_delays_the_next_shift`: the delayed shift's break moves from 2.5 to 3.125 h).
- The anonymous engine `shared_continuous_des.py` is not changed; the 5B-4.0 pin passes. X5 is not exercised (prescribed arrivals only), so no public alias was added.
- Tests: `tests/test_shared_named_des.py` (new; 37 test functions, 59 tests) with `check_named`, an independent checker of invariants 1-19 that also runs the 5B-4.2 checker; every required hand-computed case; the reduction test (fixed crew and growing crew, both policies, 96 generated arrival sets, all identical to the anonymous engine; employee and server identity not compared). `tests/test_shared_employee_states.py`: 38 test functions.
- Fault injection: 28 source-level mutants of both modules (scratch script, not committed); first run killed 26 of 28; two tests added for the survivors (break-due service across closing, DRAIN release order); after that 28 of 28 killed on the final module text.
- Gates: named, state-machine, and pin tests 106 passed; shared suites plus Separate Queue regressions 654 passed (Separate Queue alone 42 passed); ruff clean; mypy clean on 172 files; full backend suite 1647 passed, 3 skipped, 1 xfailed (baseline 1583; +59 named DES, +5 net state machine).
- Undetermined (5B-4.3 spec): a break-due service completing exactly at closing raises `UndeterminedPolicyError` (zero-length truncated break vs cancelled_at_closing); a break ending exactly at closing is recorded completed (INFERRED); "accepting" = AVAILABLE or SERVING (INFERRED); no verified event-time tolerance exists, so instants are compared exactly as in the anonymous engine (UNKNOWN for seeded runs); the P8 window shape is INFERRED.
- Next (needs explicit approval): 5B-4.4 seeded named replications (X5 wrapper and an event-time tolerance decision), 5B-4.5 named playback, 5B-5 workforce cost. Superseded: 5B-4.4 is done (next section).

## Shared Queue Enhancement: Phase 5B-4.4 Seeded Named-Employee DES Replications (2026-09-28)

Spec and plan:

- `docs/superpowers/specs/2026-09-28-shared-queue-named-replications.md`
- `docs/superpowers/plans/2026-09-28-shared-queue-named-replications-plan.md`

The Phase 5B-4.4 request approved five remaining rules and said to freeze them before replications. The spec quotes them, and the policy spec records them ("Explicit decisions of 2026-09-28 (Phase 5B-4.4)"):

1. A break-due service completing exactly at closing completes first, and its break is `cancelled_at_closing`, with no zero-length break.
2. A break ending exactly at closing is `truncated_by_closing`.
3. Accepting capacity = AVAILABLE + SERVING.
4. No event-time epsilon; whole-minute roster arithmetic; no rounding or snapping of stochastic times.
5. Gaps are reported per segment and over the horizon only, none before opening or after closing, and post-close capacity and time are reported separately.

Current verified state:

- Rules 1, 2, and 5 changed behavior; rules 3 and 4 confirm what was implemented.
  - `shared_employee_states.py` v3: a SERVING_BREAK_DUE completion at closing, with that employee's `CancelPendingBreaks` at that instant, goes to AVAILABLE and starts no break.
  - `shared_named_des.py` v2:
    - rule 1 inputs, where 5B-4.3 raised `UndeterminedPolicyError`;
    - EndBreakAtClosing for every employee on a break before closing (rule 2);
    - `schedule_realization_gap` None outside [0, closing), no gaps or required hours in the before-opening and after-closing windows, and `after_closing` always present (rule 5).
  - Three 5B-4.3 test expectations changed because the approved rules changed them; each is documented in the 5B-4.3 spec, "Phase 5B-4.4 amendments":
    - the undetermined test replaced by a rule 1 test;
    - a break at 3.5-4.0 `completed` -> `truncated_by_closing`;
    - an after-closing schedule shortfall of 0.125 replaced by the after-closing series.
- X5: `shared_continuous_des.draw_arrivals` is a public wrapper: the same two checks as `simulate_shared_replication`, then `_draw_arrivals`. No existing function changed, and the 5B-4.0 pin passes without regenerating the fixture. A scratch SHA-256 digest of 100 `simulate_shared_day` runs, 40 `simulate_shared_replication` runs, and 4 `run_shared_replications` runs is identical before and after (`236d87ec...c610`, numpy 2.4.6).
- New `simulation/shared_named_replications.py`:
  - `replication_seed_sequence(root_entropy, i)` implements the Phase 4 scheme.
  - `simulate_named_replication(seed_sequence=...)` returns the unchanged 5B-4.3 result plus a `replication` block: entropy, spawn key, pool size, customer count and SHA-256 digest, and runtime (numpy and Python versions, bit generator).
  - `run_named_replications` keeps one scalar row per replication, regenerable from `(root_entropy, i)`.
  - `aggregate_named_replications` is descriptive: `summarize_metric`, explicit denominators, `verdict: None`. There is no cost, criterion, or threshold.
- Common random numbers: customers depend only on the horizon, the demand, the root entropy, and i. The named engine and the state machine draw nothing.
- Reproducibility is VERIFIED in this runtime only (numpy 2.4.6, Python 3.13.13, PCG64). Cross-version stream equality (production lock 2.2.6, CI `requirements.txt` below 2.3) is UNKNOWN.
- Module location differs from the 5B-4.1 proposed interface (`shared_named_des.py`). The replication entry points are in a new module, so the engine stays free of numpy, as its isolation test requires.
- Tests: `tests/test_shared_named_replications.py` (new; 33 test functions, 73 tests; synthetic data; no seeded golden values). They cover:
  - an independent recomputation of the draws with explicit PCG64 streams;
  - `check_row`, which recomputes every row field from the raw result;
  - `check_named` with `check_invariants(exact=False)` on every replication of 10 scenarios x 2 policies;
  - every draw counted across rosters;
  - the seeded reduction to the anonymous engine;
  - regeneration and common random numbers.

  The spec maps all 12 required points and 14 cases. `tests/test_shared_named_des.py`: 39 functions, 62 tests. `tests/test_shared_employee_states.py`: 39 tests.
- Fault injection: 41 source-level mutants on a scratch copy of `backend/` and `tests/` (script not committed; working tree untouched).
  - First run: 38 of 41 killed. Two survivors were test gaps: a replication with no activated shift, and the unknown-cause guard. Tests were added for both.
  - Final text: 40 of 41 killed. The survivor ("rule 1 cancel at any instant") is equivalent: a probe showed that the original and the mutant raise the same error at 3.9 h and 4.5 h.
- Gates (executed on the final text):
  - named DES, state machine, and pin: 110 passed;
  - 5B-4.4 tests: 73 passed;
  - all `tests/test_shared_*.py`: 691 passed;
  - Separate Queue, all 20 files: 182 passed;
  - ruff: clean;
  - `mypy . --exclude '^outputs/'`: clean on 174 files; plain `mypy .` shows only the 5 known errors in the gitignored `outputs/` script;
  - full backend suite (`python -m pytest tests/ -x --tb=short`): 1724 passed, 3 skipped, 1 xfailed (baseline 1647 + 77).
  - Frontend not run: nothing under `frontend/` changed.
- Undetermined:
  - cross-version stream equality: UNKNOWN;
  - "preserve the 5B-4.3 result" read as scalar rows plus regeneration: INFERRED;
  - no paired roster-comparison output: PROPOSED only;
  - rule 1 is exercised by prescribed tests only, since the event has probability 0 with continuous draws;
  - the acceptance rule: UNKNOWN;
  - DRAIN release order and before-opening window shape: INFERRED, carried over.
- Next (needs explicit approval): 5B-4.5 named playback, 5B-4.6 attribution reporting, 5B-5 workforce cost, an acceptance rule, and API or UI exposure. Superseded: 5B-4.5 is done (next section).

## Shared Queue Enhancement: Phase 5B-4.5 Named-Employee DES Playback (2026-09-29)

Spec and plan:

- `docs/superpowers/specs/2026-09-28-shared-queue-named-playback.md`
- `docs/superpowers/plans/2026-09-28-shared-queue-named-playback-plan.md`

Current verified state:

- New `simulation/shared_named_playback.py`:
  - `replay_named_trace` rebuilds the line, customers, employees, and registers from the named engine's two records and validates the 17 required invariants plus P4, work conservation, service length, the closing rules, and the end state. A failure returns the check, the event, and the evidence; nothing is repaired.
  - `build_named_playback`, `prepare_named_playback`, and `playback_from_named_replications` produce a checked playback of one regenerated replication.
- Named DES engine v3 (`shared_named_des.py`), trace-only:
  - `employee_transitions_before` on every customer trace event;
  - simultaneous DRAIN releases recorded in employee_id order (approved rule). DISCREPANCY: `fd67bbf2` recorded X1 order (B, C, A in the hand case).
  - A scratch comparison with `fd67bbf2` on 500 seeded runs showed identical customers, counts, queue, staffing, and employee intervals, shifts, and breaks.
- Named replications method v2: `provenance.inputs_sha256`, a canonical-JSON SHA-256 of the recorded inputs and both policies. It is not tamper-proof and not semantic equivalence.
- Regeneration refuses (`regeneration_identity`, `stored_row`) on:
  - a version, seed-scheme, row-identity, digest, or rebuild mismatch. A rebuild error was a `TypeError` crash before a fix in this phase.
  - a regenerated row that differs from the stored row.
- Vocabulary: 5 customer types and 22 transition tuples, all reached on prescribed days. Two state-machine tuples are rejected (INFERRED unreachable).
- Tests:
  - `tests/test_shared_named_playback.py`: new, 51 functions, 75 tests. It covers hand-derived event sequences, corrupted traces (including ones with plausible final counts), the digest, the interleaving field, regeneration and refusal, and zero random numbers.
  - `tests/test_shared_named_des.py`: 3 new tests (42 functions, 65 tests).
  - The version assertion in `tests/test_shared_named_replications.py` changed from v2 to v3.
- Fault injection (scratch copy; working tree untouched):
  - First run: 48 of 88 killed. Survivors were real gaps, or checks whose failure point tests did not pin. Tests were added for every reachable one, and provably unreachable checks were removed rather than counted. Analysis also found the rebuild crash above, which was fixed.
  - Final run: 88 of 88 killed.
- Gates on the final tree:
  - focused: playback 75, named replications 73, named DES 65, state machine 39, and pin 9, all passed;
  - all `tests/test_shared_*.py`: 769 passed;
  - Separate Queue (20 files): 182 passed;
  - ruff: clean;
  - `mypy . --exclude '^outputs/'`: clean on 176 files; plain `mypy .` shows only the 5 known errors in the gitignored `outputs/` script;
  - full backend suite (`python -m pytest tests/ -x --tb=short`): 1802 passed, 3 skipped, 1 xfailed (baseline 1724 + 75 + 3).
- Undetermined:
  - cross-version numpy stream equality: UNKNOWN;
  - the rejected tuples' unreachability: INFERRED;
  - which idle DRAIN crew members stay: INFERRED;
  - the before-opening window shape: INFERRED;
  - the acceptance rule: UNKNOWN.
- Next (needs explicit approval): 5B-4.6 attribution reporting, 5B-5 workforce cost, an acceptance rule, and API or UI exposure.

## Shared Queue Enhancement: Phase 5B-4.5 Playback Validation Hardening (2026-09-29)

Recorded in the playback spec, "Follow-up: validation hardening (2026-09-29)". Only `simulation/shared_named_playback.py` and its tests changed; the engine (v3), replications method (v2), digest, merge, and named-DES rules are unchanged.

- Two defects, reproduced on `028917fe` before any change:
  - `replay_named_trace` and `build_named_playback` accepted any closing-policy label (`"FOO"`, `None`, `"drain"`, ...) when the events are the same under both policies.
  - An unhashable value at a set or dict membership test raised `TypeError` (customer `type`; transition `event`, `stage`, `from_state`, `to_state`, `employee_id`; a started engine break's `employee_id` or `actual_start`).
- Fix:
  - New first check `closing_policy`: the engine's exact `CLOSING_POLICIES` test behind a string test. Nothing is normalized or inferred.
  - `playback_from_named_replications` applies it before regeneration (`NamedPlaybackError`, check `closing_policy`).
  - Membership values are tested as strings (or finite reals) first and fail the check a hashable wrong value already failed. Nothing is converted.
  - `PLAYBACK_VERSION` is v2.
- Tests: 22 new (97 in the file). Against the `028917fe` module, all 22 fail and the other 75 pass.
- Gates on the final text:
  - focused: playback 97, named replications 73, named DES 65, state machine 39, pin 9, all passed;
  - all `tests/test_shared_*.py`: 791 passed;
  - Separate Queue (20 files): 182 passed;
  - full backend suite: 1824 passed, 3 skipped, 1 xfailed;
  - `ruff check .`: clean; `mypy . --exclude '^outputs/'`: clean on 176 files; `git diff --check`: clean.
- Open (VERIFIED, not fixed, needs approval): an extra engine break, shift, or interval record naming an employee who is not in the timeline (for example `"Z"`) is still accepted, because the reconciliation compares only the timeline's employees.
- Next (needs explicit approval): the open finding above, 5B-4.6 attribution reporting, 5B-5 workforce cost, an acceptance rule, and API or UI exposure.

## Shared Queue Enhancement: Phase 5B-4.5 Employee Referential Integrity (2026-09-29)

Recorded in the playback spec, "Follow-up: employee referential integrity (2026-09-29)". This resolves the open finding above. Only `simulation/shared_named_playback.py` and its tests changed; `PLAYBACK_VERSION` is v3.

- Defect, reproduced on `086075f7`: an extra record naming an employee outside the timeline was VALID in `replay_named_trace` and `build_named_playback`. It affected intervals, shifts, breaks, and closing inputs (the last was not in the earlier report). A non-string `state_totals` key raised `TypeError`.
- Authoritative employee set: the run's input employees. `evaluate_roster` reports every one, rostered or not, so the timeline's `state_totals` keys are the input employees.
- Rule (new check `employee_identity`):
  - timeline keys are strings;
  - every interval, shift, break, and closing input names one exactly (case-sensitive, never normalized);
  - `prepare_named_playback` (and the stored-run path) requires the timeline's employees to equal the input employees.
  - Existing checks keep their codes.
- Limit (VERIFIED): from a result alone, an extra employee copying an unrostered employee's records cannot be told apart; only the input check rejects it.
- Tests: 20 new (117 in the file); one assertion changed from v2 to v3. Against the `086075f7` module the final test file fails 21 (17 accept the orphan, 1 `TypeError`, 1 no refusal, 2 on the v3 version) and passes the other 96.
- Gates on the final text:
  - focused: playback 117, named replications 73, named DES 65, state machine 39, pin 9, `test_shared_segments.py` 51, all passed;
  - all `tests/test_shared_*.py`: 811 passed;
  - Separate Queue (20 files): 182 passed;
  - full backend suite: 1844 passed, 3 skipped, 1 xfailed;
  - `ruff check .`: clean; `mypy . --exclude '^outputs/'`: clean on 176 files; `git diff --check`: clean.
- Next (needs explicit approval): 5B-4.6 attribution reporting, 5B-5 workforce cost, an acceptance rule, and API or UI exposure.

## Shared Queue Enhancement: Phase 5B-4.6 Named-Employee Attribution Reporting (2026-09-29)

Spec and plan:

- `docs/superpowers/specs/2026-09-29-shared-queue-named-attribution.md` (approved as decisions D1-D8 on 2026-09-29; its section 12 records the implementation)
- `docs/superpowers/plans/2026-09-29-shared-queue-named-attribution-plan.md`

Current verified state:

- New `simulation/shared_named_attribution.py` (`novaq-shared-named-attribution-v1`). `build_named_attribution(result, employees)` is a pure read of one named result's `employee_timeline` and the run's input employees.
  - Its primary record is employee × shift × run. It adds per-employee sums over activated shifts.
  - It adds no aggregation across replications, no verdict, and no pay or cost.
  - Failures raise `NamedAttributionError` (check, message, evidence), through 11 checks. Nothing is repaired.
- Per-shift allocation is exact, by `(employee_id, shift_index)`. The preconditions are checked on every input.
- The quantities:
  - shift timing, on-duty hours by base state, and register wait;
  - after-closing and past-scheduled-end time as four disjoint cells, including `after_closing_and_past_scheduled_end_hours`, summed directly (D3);
  - per break, `delay_from_scheduled_hours` and `delay_from_due_hours` (D2), and shortened and unfulfilled hours.
- Units are hours (D1). `inputs_sha256` is `None`, with the reason (D4). There is no `paid` field (D5). There is no replication runner, and the rows are unchanged (D6).
- D7: a derived duration within the house tolerance below zero is reported as 0.0; beyond the tolerance the call fails. Timing comparisons stay exact.
- Defect found and fixed in the new module: malformed values beyond the float range (for example `10**400`) raised `OverflowError` instead of failing a check. This was VERIFIED before and after the fix.
- Out-of-scope finding: the protected playback `_time()` helper was observed to raise `OverflowError` for `_time(10**400)`. Whether this propagates through `replay_named_trace` was not tested. Playback v3 was not modified during Phase 5B-4.6. A separate task was opened for it. (Resolved 2026-09-30: the propagation was VERIFIED and fixed in playback v4; see "Phase 5B-4.5 Playback Numeric Range Hardening" below.)
- Spec correction: the section 7.4 example "stable day = zero attribution" was wrong. VERIFIED: 24 of 25 seeded stable replications are nonzero under each policy. The test uses `zero_arrivals` and a prescribed quiet day, and the contract is unchanged.
- Docs: the policy spec's stale 5B-4.6 entries (P2 threshold, P8 mapping, P9 question) are corrected, with the original text kept. The named-DES spec's next-steps line is updated.
- Tests: `tests/test_shared_named_attribution.py` is new, with 46 functions and 141 tests. It covers:
  - hand cases H1-H8 and H1b;
  - seeded identities on 10 scenarios × 2 policies × 25 replications, including the 5B-4.4 row;
  - 85 malformed or order-violation cases;
  - the D7 rule and its boundary;
  - purity and isolation.

  `tests/test_shared_segments.py`: the module joins the isolation set.
- Fault injection, on a scratch copy; the working tree was untouched:
  - Final pass on the final attribution implementation: 99 mutants in total. 94 were killed. 3 survived because the guarded conditions are input-unreachable through validated execution paths. 2 were demonstrated to be equivalent mutants. There were 0 timeouts and 0 harness failures.
  - The three defensive checks (on-duty span, closing partition, and base-state partition) were retained, because forced or bypassed validation demonstrated that they still detect real malformed states.
  - Earlier passes: 95 mutants with 55 killed, then 95 with 90 killed.
  - The earlier 900-second mutation timeout did not reproduce, and its cause remains UNKNOWN. A separate scratch restore-path mistake occurred during manual reproduction and was corrected. There is no evidence that it caused the timeout.
- Gates on the final code:
  - focused: attribution 141, state machine 39, named DES 65, named replications 73, playback 117, segments 51, and pin 9, all passed;
  - all `tests/test_shared_*.py` (15 files): 952 passed;
  - Separate Queue (20 files): 182 passed;
  - full backend suite (`python -m pytest tests/ -x --tb=short`): 1985 passed, 3 skipped, 1 xfailed (baseline 1844 + 141). The skips are the PostgreSQL migration rehearsal tests, which need `NOVAQ_TEST_DATABASE_URL`; the xfail is the known 2026-09-19 `test_selected_mc_load` finding.
  - The full backend suite completed in approximately 65 minutes. Other processes were active during the run; whether they caused the longer runtime is UNKNOWN.
  - `ruff check .`: clean.
  - `mypy . --exclude '^outputs/'`: success on 178 files. Plain `mypy .` shows only the 5 known errors in the gitignored `outputs/` script.
  - `git diff --check`: clean.
  - Documentation-only edits came after the gates, and no test reads those files.
- Unchanged (`git diff 5a9738e2`): named DES v3, state machine v3, replications method v2, playback v3, Separate Queue, services, API, database, frontend, dependencies, and fixtures.
- Undetermined:
  - cross-version numpy stream equality: UNKNOWN;
  - whether a derived duration ever takes the D7 zero or failure branch on engine output: NOT TESTED;
  - whether 5B-4.6 must precede 5B-5: UNKNOWN;
  - D15: UNKNOWN (undefined);
  - the before-opening window shape: INFERRED and out of scope.
- Next (needs explicit approval): 5B-5 workforce cost, an acceptance rule, API or UI exposure, and the playback overflow task.

## Shared Queue Enhancement: Phase 5B-4.5 Playback Numeric Range Hardening (2026-09-30)

Recorded in the playback spec, "Follow-up: numeric range (2026-09-30)". Made on branch `fix/named-playback-overflow`, from `156de75f`, as commit `b0040508`. On 2026-09-30 `b0040508` was fast-forwarded into `feat/shared-queue-segments` (`git merge --ff-only fix/named-playback-overflow`, conflict-free), which moved that branch from `156de75f` to `b0040508`. Nothing was pushed. Only `simulation/shared_named_playback.py` and its tests changed. `PLAYBACK_VERSION` is v4. `shared_named_replications.py` is unchanged, and its `METHOD_VERSION` is still v2.

- Defect, VERIFIED on the v3 module (probe 2026-09-29, and the tests below): values beyond the float range raised `OverflowError` instead of failing a check. This covered huge whole-number or `Fraction` times, engine totals, and `unit_work`, and finite floats whose exact sum is beyond the range. Where probed, each escaped `replay_named_trace`, `build_named_playback`, or both. `playback_from_named_replications` with a doctored engine raised for every case probed: times, `unit_work`, a state total, and an after-closing interval. `build_named_playback` also raised from `named_replication_row`, which ran before the replay: `OverflowError`, or `SharedSegmentError` for inconsistent counts. The v2 hardening covered unhashable values only.
- Fix (approved as Part A and B1, 2026-09-30):
  - `_time` and `_close_enough` catch `OverflowError`, and `near` guards its `float()` conversions. The value then fails the existing check.
  - A new `_fsum` wrapper is used at the served-wait sum (`customer_reconciliation`), the state totals, and `_hours_in` (`employee_reconciliation`).
  - `unit_work` is tested before the division (`service_duration`).
  - `_outside_horizon` runs inside the exception boundary of both entry points. Its overflow was reproduced: in the replay with the timeline beginning at -DBL_MAX, and in the build within the replay's tolerance band. That the band is the only route in the build is INFERRED.
  - B1: `build_named_playback` replays first, then builds the row. A row `OverflowError` fails the new check `summary_row`. Corrupted counts now raise `NamedPlaybackError(customer_reconciliation)` instead of `SharedSegmentError`.
- Valid output: a scratch comparison of 276 outputs from the v3 and v4 modules was identical apart from `provenance.playback_version` and the appended `summary_row` check (VERIFIED; not committed).
- Tests: 10 new functions and 50 new tests (167 in the file); two version assertions changed from v3 to v4. Against the v3 module, the final test file fails 52 and passes 115. Of the 52: 43 `OverflowError`, 2 `SharedSegmentError`, 2 `TypeError`, 2 old-message `service_duration`, and 3 on the version. Fault injection: 13 of 13 mutants killed. The first run killed 12; the build `_outside_horizon` mutant was killed after the tolerance-band test was added.
- Gates on the final code (2026-09-30):
  - focused: playback 167, named replications 73, named DES 65, state machine 39, pin 9, segments 51, and attribution 141, all passed;
  - all 15 `tests/test_shared_*.py` files: 1002 passed;
  - Separate Queue (20 files): 182 passed;
  - full backend suite (`python -m pytest tests/ -x --tb=short`): 2035 passed, 3 skipped, 1 xfailed, 6 subtests passed. The skip reasons were not printed in this run. The full suite was not rerun before the change in this worktree, so the difference from the 1985 recorded for 5B-4.6 is not a verified delta;
  - `ruff check .`: clean; `mypy . --exclude '^outputs/'` and plain `mypy .` in this worktree: no issues in 178 files; `git diff --check`: clean.
  - The documentation was edited after the gates. No test reads these files.
- Integration check (2026-09-30, after the fast-forward; separate from the gate runs above):
  - the feature branch's tree was identical to `b0040508`, and `git diff --check` was clean for `156de75f..b0040508` and for the working tree;
  - on that identical tree (run in the fix worktree), focused playback 167, named replications 73, named DES 65, state machine 39, pin 9, segments 51, and attribution 141 passed, and all 15 `tests/test_shared_*.py` files passed (1002);
  - the full backend suite was not rerun after the integration. The full-suite result above is from the gate run before the integration.
- Open (VERIFIED, not fixed; each needs approval):
  - the queue-area accumulation in `_reconcile` still raises `OverflowError` with exact `Fraction` times (present on v3 too);
  - an unknown `unfulfilled_cause` passes the replay, and `build_named_playback` raises `SharedSegmentError` from `named_replication_row` (present on v3 too; not an overflow);
  - non-finite values are accepted: a timeline beginning at -inf, and infinite queue integrals, replay as VALID (`math.isclose(inf, inf)` is True);
  - from the 2026-09-29 probe: a huge or `Fraction` `register_count` (playback `handover`), a caller-supplied service rate beyond the float range (playback `_Replay.__init__`), `shared_segments._is_finite_real`, the named DES `servers` sum, and `shared_employee_states._handover`.
- Next (needs explicit approval): the open items above, 5B-5 workforce cost, an acceptance rule, and API or UI exposure.

## Shared Queue Enhancement: Phase 5B-5 Named Workforce Costing (2026-09-30)

Spec and plan:

- `docs/superpowers/specs/2026-09-30-shared-queue-named-workforce-cost.md` (approved on 2026-09-30 as decisions C1-C16, with C10b and C13 Option U; section 14.1 records the dated implementation-precondition corrections after the playback integration, and section 18 the implementation)
- `docs/superpowers/plans/2026-09-30-shared-queue-named-workforce-cost-plan.md`

Current verified state:

- Base `feat/shared-queue-segments` at `40ee8dbe`. One local commit; not pushed, merged, or deployed. (Superseded 2026-09-30: the implementation `19ff54a1` is followed by the docs-only spec clarification `6777ad3f` and a docs-only `handoff.md` and `memory.md` follow-up; see the owner decisions below. None is pushed, merged, or deployed.)
- New `services/shared_named_cost.py` (`novaq-shared-named-cost-v1`). `cost_named_workforce(result, employees, rates)` costs one named-DES run or one regenerated replication (C12). It is a pure read: no simulation, no random numbers, no input changed.
  - It first runs `build_named_attribution`, whose failures propagate unchanged, and reads every operational quantity from it (C16). It then walks the same validated intervals in time order only to split paid time into regular and overtime.
  - Failures raise `NamedCostError` (check, message, evidence) through 10 checks after attribution's 11. Nothing is repaired.
- Cost = per employee `regular_paid_hours × regular_rate_per_hour + overtime_paid_hours × overtime_rate_per_hour` + `queue.customer_hours_total × waiting_rate` + `counts.unserved_at_close × unserved_customer_rate` when the unserved term applies. Named wages replace the Phase 3A capacity labor terms (C2); `shared_day_cost.py` is unchanged.
- Paid time (C3, C4, C7): WAITING_FOR_REGISTER, AVAILABLE, and the three serving states are paid; OFF (including activation delay and split-shift rest) is unpaid; ON_BREAK is paid only when the engine break record it maps to (exact containment and tiling) has `paid` True. No break penalty or bonus.
- Overtime (C5, C6, C14, C15): an instant past its shift's scheduled end, after closing, or after cumulative actual paid time (all earlier paid time, flagged or not, across split shifts) reaches the daily threshold; one premium per instant. A missing required threshold gives `HOURS_UNDETERMINED` (labor and total `None`), never `RATE_MISSING`. D7 (`derived_duration`) is used only for `R_k` and a crossing's T piece.
- Statuses (C13): `COSTED`, `ZERO_QUANTITY` (an exact zero needs no rate, cost 0.0), `RATE_MISSING`, `HOURS_UNDETERMINED`, `NOT_APPLICABLE`. X6 (C10b): HARD_CUTOFF applies the unserved term even at 0 (`ZERO_QUANTITY`); DRAIN applies it only when the realized count is above 0. No verdict or acceptance field (C11); D15 stays UNKNOWN.
- Implementation choices within the spec (section 18.3): `total_cost` is the fsum of the component costs (sections 9 and 11; section 3's `fsum(L, W, U)` grouping can differ only by rounding: CONFLICTING at rounding level); under DRAIN with an empty crew, the unserved ids must equal the waiting ids (the engine's X6 rule). (Superseded 2026-09-30: the product owner resolved both points in docs commit `6777ad3f`. The grouping is no longer CONFLICTING, and the DRAIN equality is an approved invariant; see the owner decisions below.)
- Tests: `tests/test_shared_named_cost.py` is new, with 53 functions and 137 tests: hand cases HC-A to HC-W3 plus the split-shift threshold regression; seeded identities on 10 scenarios × 2 policies × 25 replications against an exact-arithmetic walk; 78 malformed or overflow cases; rule-level walk tests; purity and isolation. `tests/test_shared_segments.py`: the module joins the isolation set.
- Fault injection on scratch copies (working tree untouched): 106 mutants. First pass 86 killed; eight test gaps got tests. Final pass: 101 killed, 5 equivalent, 0 timeouts, 0 harness failures. `paid_partition`, `overtime_partition`, and `cost_arithmetic` are input-unreachable and kept; direct tests show they fire.
- Gates on the final code:
  - focused: cost 137, attribution 141, state machine 39, named DES 65, named replications 73, playback 167, segments 51, pin 9, and day cost 16, all passed;
  - all 16 `tests/test_shared_*.py` files: 1139 passed;
  - Separate Queue (20 files): 182 passed;
  - full backend suite (`python -m pytest tests/ -x --tb=short`): 2172 passed, 3 skipped, 1 xfailed, 6 subtests passed (734 s), which is the 2035 recorded for playback v4 plus the 137 new tests. The skips are the three `test_real_postgres_upgrade_paths_preserve_ownership` cases (PostgreSQL rehearsal; the reason was not printed); the xfail is the known `test_selected_mc_load::test_novamart_failing_lanes_are_stable_across_base_seeds`.;
  - `ruff check .`: clean; `mypy . --exclude '^outputs/'`: no issues in 180 files; `git diff --check`: clean.
  - The documentation was edited after the gates. No test reads these files.
- Docs: the policy spec's P1, P9, X6, and 5B-5 rows carry dated corrections, with the original text kept.
- Unchanged (`git diff 40ee8dbe`): named DES v3, state machine v3, attribution v1, playback v4, replications method v2, Phase 3A day cost, 5B-1 to 5B-3, Separate Queue, API, database, frontend, dependencies, and fixtures.
- Undetermined: the C14 all-flagged branch and the D7 branches in the walk are INFERRED unreachable; tiny float slices are engine-reachable (tested on a 5-minute roster) but NOT TESTED on the seeded runs; Phase 5A D6 and D8 and D15 are UNKNOWN; cross-version numpy stream equality is UNKNOWN.
- Owner decisions after the implementation (2026-09-30), written into the spec by docs-only commit `6777ad3f` (parent `19ff54a1`). `git diff 19ff54a1 6777ad3f` changes only the spec, so the implementation `19ff54a1` is unchanged.
  - Total-cost grouping, resolved: the canonical `total_cost` is a single flat `fsum` over every applicable component cost (each employee's regular and overtime labor costs, the waiting cost, and the unserved cost when it applies; COSTED and ZERO_QUANTITY components only), as spec sections 9 and 11 define. Section 3 now states this, with its old nested line kept as a dated quote. Employee `labor_cost` (`L_e`) and `labor.total_cost` (`L`) remain reported subtotals. `total_cost` is not recomputed as the nested `fsum(L, W, U)`. The code matches (VERIFIED: `shared_named_cost.py` lines 710-713, and the `cost_arithmetic` check at line 627).
  - DRAIN empty-closing-crew equality, approved as a validation and reconciliation invariant: it applies only in the engine branch where DRAIN has an empty frozen crew (`at_close.drain_crew` empty) and the remaining waiting customers are made unserved (`no_eligible_employee`). It checks that those unserved customers are exactly the waiting population at closing (`at_close.waiting_customer_ids`). This is the `unserved_consistency` branch in `_check_unserved`, lines 518-521.
  - The invariant does not determine cost applicability. C10b stays authoritative: under DRAIN, `counts.unserved_at_close > 0` applies the unserved component, and zero realized unserved gives `NOT_APPLICABLE` (line 701; the crew is not read there). Employee eligibility is not independently recomputed; the module reads the engine's frozen `drain_crew`.
- Phase status (2026-09-30): implementation `19ff54a1`; spec clarification `6777ad3f`. Phase 5B-5 remains closed. API or UI exposure is not approved. Cross-replication cost aggregation is not approved. D15 and the acceptance rule remain UNKNOWN, and no verdict exists.
- Next (needs explicit approval): cross-replication cost aggregation, an acceptance rule, API or UI exposure, and the open playback items listed above.

## Shared Queue Enhancement: Named Shared Queue API/UI First Slice (2026-10-01)

Spec: `docs/superpowers/specs/2026-09-30-shared-queue-named-api-ui-first-slice.md` (A1-A6 and OD-1 to OD-9 approved 2026-09-30; numeric identity B1 and the 422/409 identity codes approved 2026-10-01). Section 21 is the implementation record. No separate plan file was written; the spec's section 20 stages served as the plan.

Current verified state:

- Authorization: the product owner's master continuation prompt (2026-10-01) authorized LOCAL implementation. Production facts stay release blockers, not local blockers. Nothing is pushed, merged to `main`, or deployed.
- G-A integration: `e7e3cdae` (final G-A) merged into `feat/shared-queue-segments` as `a49bb1f1` (`--no-ff`; parents `620f20df`, `e7e3cdae`). No file was changed on both lines. Gates on `a49bb1f1`: SQLite 2719 passed, 118 skipped (all PostgreSQL variants), 1 xfailed; PostgreSQL 16.15 (CI postgres file list plus the 22 G-A test files) 777 passed, 0 skipped; frontend 53 files and 388 tests, typecheck and lint clean. `GENERATION_ENFORCEMENT_ENABLED` stays `False`.
- Implementation commit: `6ecd9c6f` (parent `a49bb1f1`) (local, not pushed).
- Backend: `backend/api/shared_named.py` is the one thin adapter (A6). Routes R1-R6 under `/analyses/{analysis_id}/shared-named/`: `contract`, `validate`, `runs` (create and list), `runs/{run_id}`, `runs/{run_id}/replications/{i}`. Each run is one Job of kind `shared_named_replications` with the unchanged `run_named_replications` output and `params_json.dataset_generation` from the explicitly selected dataset row. No migration, workforce table, stored playback, or cost.
  - B1: insert and flush, re-read `result_json` with a column `SELECT` in the same transaction, and compare the fingerprint, every stored row (int, float, and bool distinct; floats by bits), and the required provenance. Any difference rolls back and returns 422 `persistence_identity_mismatch` with no run id. On PostgreSQL 16.15 a pay rate of `1e16` is refused this way (JSONB returns it as an integer).
  - R6 keeps the protected regeneration contract: 409 `regeneration_identity` (with the domain check, or `attribution_stored_row` for the D6 guard) on an existing run that no longer reproduces; other playback or attribution failures are 500.
  - The named router keeps NaN and ±Infinity bodies at 422 with its own route class. App-wide, such bodies return 500 (pre-existing; not fixed).
  - Limits stay provisional and NOT PRODUCTION-APPROVED: replications 9, required-staffing segments 52, employees 24, roster shifts 48 (availability 3, break rules 3, breaks per rule 2, breaks per shift 2). The 413 backstop reads `RESULT_JSONB_MAX_BYTES` at run time.
- Frontend: `?mode=named` on `/analyses/:analysisId/simulate`, offered only for `shared_queue` analyses. Without the parameter the page renders as before (`SimulationPage.test.tsx` unchanged and passing). The named view covers eligibility, a persistent banner, an explicit dataset selector, the workforce form with no defaults, validation, a run control gated on a runnable validation of the exact form, the runs list with Setup currency, run evidence, the replication table and descriptive aggregate (minutes for waits, "—" for null, no verdict), and the selected replication's playback and attribution. 248 `simulation.named_*` keys in each of `en` and `tl`; the Filipino wording quality is UNKNOWN.
- Findings: PostgreSQL `jsonb` does not keep object key order (a first test version failed on it; the key set is now checked, order only on SQLite); `handoff.md`'s "Separate Queue (20 files)" is not enumerated, and 18 files match `*separate*`.
- Gates on the final code: backend full suite 2856 passed, 123 skipped (all PostgreSQL variants), 1 xfailed; within it the named module 137 passed and 5 skipped, all 16 `tests/test_shared_*.py` files 1139 passed, and the 18 `*separate*` files 168 passed. On PostgreSQL 16.15 the named module had 141 passed and 1 skipped (SQLite-only by design), including B1's five points and the light, maximum-structure, busy, and stress round trips. Frontend 61 files and 443 tests (388 before, 55 new); typecheck, lint, and build exit 0. Ruff clean; mypy clean on 200 files.
- NOT TESTED: the spec's Stage 3 browser and local-stack checks; production behavior of any kind.
- Phase status (2026-10-01): LOCAL IMPLEMENTATION COMPLETE; not production or deployment ready. Out of scope and not started: Compare, Decision verdict, D15, Reports, workforce-cost UI or aggregation, roster-optimizer API or UI, G8 release, G9/G-B, generation enforcement.
- Next (needs approval): Stage 3 browser and local-stack integration; production limit verification (with G8); the app-wide NaN-to-500 defect; owner review of the Filipino wording.

## Shared Queue Enhancement: Stage 3 Local Integration (2026-10-01)

This dated update supersedes only the first-slice section's Stage 3 `NOT TESTED` and "Next" statements above. The previous implementation and gate history remains as recorded there. Detailed evidence is in spec section 21.7; browser screenshots and synthetic fixtures are untracked under `output/playwright/stage3/`.

- VERIFIED: `docker-compose.integration.yml` ran locally as `novaq_stage3` with PostgreSQL 16.15; `/healthz` and `/api/ready` returned 200 at `127.0.0.1:18080`.
- VERIFIED: a new shared queue (`unlimited`, `not_modeled`) accepted a two-period aggregate CSV without variance, K, or theta; named validation was runnable with period-aligned staffing. Seed 7 and 9 replications created one completed `shared_named_replications` Job. Browser list, run detail, R6 replication 0 and 8, playback, attribution, and the `X-CSRF-Token` header on named POSTs were checked.
- VERIFIED: variance-bearing aggregate data produced the named M/M/c scope refusal. An intentional stored-row edit in the disposable database produced R6 409 `regeneration_identity` / `stored_row`; restoration was checked by R6 200.
- VERIFIED: legacy shared DES, Compare, Decision, and Reports worked on the same stack. Separate Queue used a synthetic event-derived fixture for a selectable replicated-DES scenario; its selected-plan DES playback, Monte Carlo, validation, conditional Decision, and Reports rendered. The app withheld unsupported savings and ROI. These outcomes are local test results, not operational conclusions.
- VERIFIED: no first-slice defect was reproduced, so no application or test file was changed. Generation enforcement remains `False`. No production access, push, merge, or deployment occurred.
- UNKNOWN: production result-size cap, Render timeout, Cloudflare `/api` limits, production PostgreSQL version, and Filipino wording quality. The 9/52/24/48 limits remain NOT PRODUCTION-APPROVED. The app-wide NaN-to-500 behavior and NumPy pin conflict remain separate findings.

- VERIFIED final-tree gates: backend 2856 passed, 123 PostgreSQL-variant skips, 1 known xfail, 6 subtests; named API on local PostgreSQL 16.15 141 passed, 1 SQLite-only skip; frontend 61 files / 443 tests passed, typecheck, lint, build exited 0; Ruff passed; mypy had no issues in 200 source files; git diff --check passed. The first bare Ruff command could not resolve on PATH, so the installed .venv Ruff executable ran the same gate. No frontend timeout occurred. Build kept its large-chunk advisory.

## Engineering Governance: Zero-Fabrication Protocol (2026-09-25)

Current verified state:

- `AGENTS.md` holds the only copy of the protocol. The product owner's 2026-09-25 directive was merged into it. It adds evidence citation, three more evidence labels (APPROVED SPECIFICATION, INFERRED, NOT TESTED, next to VERIFIED, REPORTED, PROPOSED, UNKNOWN, CONFLICTING), protected mathematics, data integrity, supported analytical conclusions, scope-controlled commits, and a complete, partial, or blocked status in the final report. Every earlier requirement is kept.
- `CLAUDE.md` no longer repeats the protocol. It imports `AGENTS.md` with `@AGENTS.md`. Reason: with a `CLAUDE.md` present, Claude Code reads `CLAUDE.md` and not `AGENTS.md` under the default Project instructions setting (official memory documentation, read 2026-09-25). The 2026-09-25 session on Claude Code 2.1.281 showed the same: its loaded project instructions held `CLAUDE.md` only. The layout, gates, and constraints in `AGENTS.md` reached Claude only when it chose to open the file.
- Stale `AGENTS.md` statements were corrected against source. Model-selection dispatch now names the separate-queue branch that runs first (`model_selection.py`). The CSRF exemptions now include `/onboarding`, as `backend/api/main.py` and `tests/test_production_hardening.py` show. The frontend line names the Cloudflare Pages public deployment. The Session History now says that the Streamlit files it names were removed in `8b0df382`.
- `memory.md` records the adoption and the role of each governance file.
- Skills: none added. Claude Code loads no project skills here (`.claude/skills/` does not exist; `.agents/skills/` holds design skills for other agents). The proposed `novaq-verification`, `novaq-engineering-audit`, and `novaq-workflow-audit` skills were rejected: the Gates section and protocol sections 1, 2, 9, and 11 already cover their procedures, and no repeatable gap was shown.
- Verification (static only): a script checked encoding and CRLF preservation, trailing whitespace, final newlines, fence and inline-code balance, the single `@AGENTS.md` import, that no nested imports exist, that the protocol exists only in `AGENTS.md`, that section numbering is 1 to 11, that every earlier protocol line is still present or deliberately reworded, that outside the protocol only the three corrected lines and the Session History note changed, that every cited path and commit exists, and that only the four governance files changed. No tests or tools read these files, so application tests were not required and were not run.
- NOT TESTED: runtime loading of the import. Headless `claude -p` runs, including `/context`, failed with "Credit balance is too low" before any answer. In the next interactive session, run `/context` (Memory files) or `/memory` and confirm that `AGENTS.md` is listed through `CLAUDE.md`.
- No application source, test, queueing, optimization, DES, Monte Carlo, authentication, schema, API, or report file changed.

Open items:

- CONFLICTING: `POST /onboarding/complete` writes user state (`backend/api/onboarding.py`), but the CSRF middleware docstring in `backend/api/main.py` says exempt families never mutate server state. The session and CSRF cookies are `SameSite=lax` (`backend/api/auth.py`); whether that is enough was not assessed. The exemption was not changed and needs an owner decision.
- The `fix/d1-replication-costs`, `claude/clever-boyd-87ff32`, and `claude/nervous-hodgkin-2b6ef1` worktrees have their own `AGENTS.md` without the protocol and no `CLAUDE.md`. Merging those branches will need care in `AGENTS.md`.
- Resolved: the Session History moved unchanged to `docs/history/agents-session-history.md`, so the `AGENTS.md` that Claude Code loads at session start is now 220 lines, down from 290. The official guidance targets under 200 lines per `CLAUDE.md` file.
- `.claude/launch.json` is untracked and was left alone.
