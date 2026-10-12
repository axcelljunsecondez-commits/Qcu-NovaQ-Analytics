# Compact Workflow and UX Redesign: Implementation Plan

**Status:** PROPOSED, revision 2 (2026-10-09). Owner decisions are recorded in spec §0 (D1–D27). Implementation starts only after the owner's GO; items marked **own spec** start only after their specification is approved.
**Spec:** `docs/superpowers/specs/2026-10-09-compact-workflow-ux-redesign.md` (revision 2)
**Review board:** `docs/superpowers/specs/assets/2026-10-09-compact-workflow-redesign-board.html` (version 6)
**Base:** `origin/main` `6093d78a`. Implement on feature branches in worktrees created from the current `origin/main`, never in the stale main checkout (spec G1). Never push `main` (production release path, `memory.md` Deployment Topology).

## Ground rules for every phase

- Read `AGENTS.md`, `memory.md`, `handoff.md`, MASTER, the spec and (for B items) the item's own spec before the phase.
- UI phases (U) touch only `frontend/` and locale files. Backend phases (B) are listed separately. A UI phase whose B item is not ready ships the control disabled with the limitation text from the spec.
- No change to queueing formulas, `model_selection.py`, optimizer/DES/MC/validation/Decision code, scenario verification, evidence status, generation guards, report calculations, auth/CSRF/ownership, except where an approved own spec says so (B4b, B4c, B8, B10).
- Every new string in `frontend/public/locales/en/translation.json` and `tl/translation.json`.
- Gate set at the end of each phase, with actual results recorded in the phase report (historical results are not evidence):
  - `.venv` Python: `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`.
  - `frontend/`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`.
  - Browser check of changed screens at 375, 768, 1024, 1440 px, light/dark, EN/TL, keyboard only.
- Commit per phase after the owner approves the phase report; no Claude attribution lines in commits (owner rule).

## Order at a glance

| Step | Phase | Depends on |
|---|---|---|
| 0 | Docs: decisions, MASTER amendment, formatting fix | — |
| 1 | U1 Shell, account menu, Settings, redirects | 0 |
| 2 | U2 + B1 Home, sign-in intent, onboarding gate removal | 1 |
| 3 | U3 My analyses, New analysis | 1 |
| 4 | U4 (+ B9) Data and setup | 3 |
| 5 | U5 Suggested plans | 4 |
| 6 | Specs: B4a, B4b, B4c, B8, B10 (written and approved, no code) | 0 |
| 7 | B10 + B11 + B3 + B12 backend | 6 (B10 spec) |
| 8 | U6 Analysis results | 5, 7 |
| 9 | B5 + U7a Queue simulation for separate lines and legacy paths | 5 |
| 10 | B4a + U7b Continuous shared run (preview) | 6 (B4a spec), 9 |
| 10b | B13 Per-date separate-lines plans as one continuous day per date | B13 spec (approved 2026-10-12), 9 |
| 11 | B4b Recorded service times (standard version) | 6 (B4b spec), 10 |
| 12 | B4c Shared-line break modeling | 6 (B4c spec), 11 |
| 13 | U8 Help center | 8, 10 |
| 14 | U9 + B2 Quick calculator | 1 |
| 15 | B8 Reports (PDF summary, Excel calculations) | 6 (B8 spec), 8 |
| 16 | U10 Final verification and Help screenshots | all |

Steps 3, 6 and 14 can run in parallel with others once their dependencies are met.

## Phase 0 — Documentation (docs only)

1. Spec revision 2 and this plan (done 2026-10-09; committed `477ce274` on local branch `docs/ux-workflow-audit`).
2. (Done 2026-10-09.) Record the decisions in `memory.md` and the status in `handoff.md`: onboarding supersession (spec §12), new navigation, D1–D27 summary, and the G8 correction (separate-lines DES already records break events) to the 2026-09-20 "Store Floor Playback View" note.
3. Amend MASTER (version 1.1): amendment log, §7 replay motion (D29), §8.1 hide-sidebar rail (D10), §9.1 navigation, §9.2 order (D4), §9.4 plan-selection and Reports rows (D31), §10.4 report availability. MASTER does not mention onboarding, so no onboarding amendment is needed there. (Done 2026-10-09.)
4. (Done 2026-10-09; script-verified lossless.) Rewrite `design-system/novaq/MASTER.md` and `docs/superpowers/specs/2026-09-13-ui-ux-refinement-product-decisions.md` with real newlines; prove with a script that the only change is `\n` escapes → newlines.

Acceptance: docs-only diff; MASTER renders as Markdown; decisions traceable from `memory.md` to the spec.

## Phase U1 — Shell, account menu, Settings, redirects

Status (2026-10-09): implemented and committed on local branch `feat/ux-u1-shell` after the owner approved the phase report (not pushed). Redirects implemented in U1 are only those whose destination exists (`/dashboard`, `/datasets`, `/analysis`, `/account`, `/admin`); `/onboarding` moves with U2 and the analysis-route redirects with U3–U7. Preferences join Settings in U2 (B1).

Files: `router.tsx`, `components/layout/Sidebar.tsx`, `AppLayout.tsx`, `LanguageSelector.tsx`, `ThemeToggle.tsx`, new `components/layout/AccountMenu.tsx`, `AppHeader.tsx`, `components/ui/Tooltip.tsx`, new `pages/SettingsPage.tsx` (composes existing Account, Datasets, Admin content), `styles/global.css`, locales, tests.

Tasks: sidebar groups (spec §7.3); hide-sidebar icon button with accessible name and tooltip; account menu (email, Settings, Language, Get help, Log out) with menu keyboard semantics; icon rail with focus tooltips; `/settings/:section`; compatibility redirects (spec §5); last-used analysis helper.

Tests: sidebar items/order; hide/show persistence and storage-failure fallback; account menu keyboard (arrows, Escape returns focus) and outside click; logout still clears caches; Settings shows set-password path when `has_password === false`; admin section forbidden for analysts; each redirect lands on its target.

## Phase U2 + B1 — Home, sign-in intent, onboarding gate removal

Status (2026-10-09): implemented and committed on local branch `feat/ux-u1-shell` after the owner approved the phase report (not pushed). Home's header leaves out Quick calculator and Help until they are public (U9/B2, U8), so Home never links signed-out visitors to a sign-in wall labelled as a free tool.

B1: `GET/PUT /account/preferences` (CSRF-protected, not under `/onboarding`, never writes `onboarding_completed`). Tests: 401 without session, 403 without CSRF header, exact save, length/type validation, user isolation; `test_production_hardening` exempt list unchanged.

Frontend: `pages/HomePage.tsx` with the two static line pictures (shared SVG component reused by New analysis), single hero "Start an analysis"; `auth/intent.ts` (`safeNext`, `continueAfterSignIn`); `RequireAuth` keeps search/hash; Login/Google/verification continue to intent; route tree without `RequireOnboarding`; `/onboarding` → `/settings/preferences`; public language selector.

Tests: `safeNext` rejects `//x`, absolute URLs and auth routes; Start → login → New analysis for password and Google; normal sign-in → My analyses; deep link with query survives sign-in; never-onboarded user reaches `/analyses`; Google button hidden when disabled by `/auth/config`; Home has exactly one "Start an analysis".

## Phase U3 — My analyses, New analysis

Status (2026-10-09): implemented and committed on local branch `feat/ux-u1-shell` after the owner approved the phase report (not pushed). Cards show the operating window only from saved time segments; when none are saved the card says nothing about the window (not "Window not set yet", which would be wrong for analyses whose uploaded data defines the periods). Period counts are not shown because they would need a dataset request per card.

Search (URL `?q=`), structure filter with Home wording, cards with window/period count only when derivable, archive confirmation, empty state; New analysis picture cards (shared SVG component), inline recommender.

Tests: search restore from URL; recommender answers equal `GuidedSetupPage.recommend`; archive asks first.

## Phase U4 (+ B9) — Data and setup

Behaviour-preserving extraction of `AnalysisSetupPage` first (payload and cache-reset parity tests), then the numbered steps, Advanced settings, "Make periods" helper (1–24 periods of 15/30/60 minutes, same day), B9 "Enter numbers without a file" (browser builds the existing aggregate CSV and uploads it through the existing preview/upload path, labelled "Entered by you").

Placeholders until their B items land: upload purpose question shows the B10 limitation text ("This file will become the data for your plans and simulations."); "At closing time" is rendered from the B4a spec's storage once approved (no frontend-only storage).

Task 4.6 (investigation): are shared aggregate uploads with unequal period lengths weighted correctly downstream? Record VERIFIED or a defect.

Status (2026-10-09): implemented and committed on local branch `feat/ux-u1-shell` after the owner approved the phase report (not pushed). Task 4.6 result (VERIFIED from code, spec §8): unequal aggregate periods are not weighted; totals assume one-hour rows. Not fixed here (protected cost math); B9 therefore offers one-hour rows only. Step 5 "At closing time" is not shown until the B4a spec defines its storage. The page lives at `/analyses/:id/data`; `/setup` redirects there keeping query and hash.

## Phase U5 — Suggested plans

Status (2026-10-09): implemented and committed on local branch `feat/ux-u1-shell` after the owner approved the phase report (not pushed). Page at `/analyses/:id/plans`; `/optimize` redirects. The partial-failure message points to Compare until U6 adds the saved-plan switcher to Analysis results.

Extract `OptimizePage` panels unchanged in logic; accessible `ConfirmDialog` replacing `window.confirm`; defaults shown as defaults; "Use this plan" = `POST /scenarios` then `POST /workflow/selection` with partial-failure message; "Save without using"; disclaimers (lowest modeled cost among options meeting limits; breaks = local improvement).

Tests: request payload equality with today; selection call sequence and cache invalidation; stale snapshot disables actions; break apply only on the latest dataset; dialog keyboard operable.

## Phase 6 — Own specs (docs only, each approved separately)

Status (2026-10-09): all five written and approved by the owner in chat (answers recorded in each spec): `docs/superpowers/specs/2026-10-09-b10-planning-vs-review-file.md`, `2026-10-09-b4a-continuous-shared-run-preview.md`, `2026-10-09-b4b-recorded-service-times.md`, `2026-10-09-b4c-shared-line-breaks.md`, `2026-10-09-b8-reports-pdf-excel.md`. Docs only; each implementation step still needs its own GO.

- **B10** planning file vs review-only upload: storage (column or `validation_report_json` field), migration need, new `resolve_current_dataset` rule, effects on evidence currentness, generation guards, D7 tests, upload API shape, legacy datasets default (= planning).
- **B4a** continuous shared run preview: route, inputs mapping from analysis segments and staffing, closing-rule storage in `queue_setup` (no default), compatibility refusals, replay via `shared_playback`, result size and trace limits (OD-UX-8 / B6), seeds and replications, pin test untouched.
- **B4b** recorded service times: representation of service-time variation (e.g. per-period empirical resampling), continuity of customers in service and waiting across periods, reference cases and acceptance tests, engine version.
- **B4c** shared-line breaks: break timing, customers in service, return to service, events for counter states.
- **B8** reports: PDF summary contents; Excel sheet list; formula coverage per model (OD-UX-12); optimizer candidate export; parity tests per format.

## Phase 7 — B10, B11, B3, B12 (backend)

Status (2026-10-12): B10 committed `598658e6` (local, not pushed; PostgreSQL not tested). B11, B3 and B12 committed `864dff87` (local, not pushed; no migration: B11 dates live in `validation_report_json`). B12 covers the Analysis results totals (arrivals per period with every line summed, busiest period); served/unserved simulation totals move to the simulation phases (B5/U7), where those numbers are shown.

- B10 per its spec.
- B11: first/last arrival date stored at ingestion for customer-record uploads; server-side derivation for per-date labels; null otherwise. Tests: event file → dates; aggregate → null; representative day → recovered only if stored.
- B3: optional `dataset_id` on `GET /current` and `GET /workflow/observed-wait` (owner check, `validation.ok` required, response names the dataset); evidence/selection/Decision endpoints unchanged. Tests: other user's dataset → 404; invalid dataset → 409/404 as specified; default unchanged when omitted.
- B12: server fields for busiest period by arrivals (separate lines summed server-side) and served/unserved counts where the UI needs totals.

## Phase U6 — Analysis results

Status (2026-10-12): committed `c09ce3cc` on `feat/ux-u1-shell` (local, not pushed). Route `/results` (spec §5); Current and Compare pages removed, their routes redirect. Deviations recorded in `handoff.md` (cost line, report link, older-file Setup, multi-plan chart).

`pages/ResultsPage.tsx` composing extracted Current and Comparison pieces; "View results from" selector (B3/B11), older-file banner and recalculation label, key results table (spec §7.7), busy-level strip with legend, charts, "What the plan changes" section with saved-plan switcher and staff cost (plan only).

Tests: all values come from the selected file's response (fixtures for two files, no leakage on switch); review-only selection never calls selection/scenario/simulation endpoints; recorded wait unavailable message for aggregate uploads; "can't keep up" periods listed before highest-wait period; plan target flag only with a selected plan; missing values show "Unavailable".

## Phase 9 — B5 + U7a Queue simulation (separate lines and legacy paths)

Status (2026-10-12): committed `ddf03de2` on `feat/ux-u1-shell` after the owner's approval (local, not pushed). No engine change to simulated numbers; additive `in_system_at_close`, `start_hours` and run `summary`. Routes `/simulation/results`, `/simulation/replay`, `/simulation/checks`; the old Simulate page is removed and its route redirects. Deviations and the pre-existing per-date break issue (dilution in 24 h period runs) are recorded in `handoff.md`; B13, each date as one continuous day in the optimizer and the check, has its own spec (`docs/superpowers/specs/2026-10-12-b13-per-date-continuous-day.md`, approved 2026-10-12) and is step 10b.

B5: confirm stored selected-plan traces contain `draining_start`, `break_start`, `break_end`; add a test that aggregates are identical with and without trace consumption changes (no engine change expected). Frontend: reducer handles the three events → Finishing customers before break / On break / Available; Closed / not staffed from `inactive_queue_ids`; scheduled breaks from setup on a separate timeline row; "Break state unavailable" when events are absent.

U7a: `QueueSimulationPage` with header switch (Current | Suggested plan) and view tabs (Key results | Replay), three steps, Advanced settings, separate-lines full-day replay from the single continuous-day execution, per-date "one period at a time" notice, legacy shared run kept and labelled, named mode unchanged.

Tests: event-to-state mapping table; no break state inferred from idle; accounting identity after every event; full-day replay equals concatenation of one execution's events in time order; truncation notice; URL keeps plan/view/time.

## Phase 10 — B4a + U7b Continuous shared run (preview)

Status (2026-10-12): committed `7f4c5cd0` on `feat/ux-u1-shell` (local, not pushed). Migration 0007 (`analysis_projects.shared_closing_policy`), adapter `backend/api/shared_continuous.py`, full-day section on the Queue simulation pages for shared lines; the older period-by-period run stays, labelled. Key results follow D30 (four cards, two charts, More results) rather than the earlier "Day summary table and four charts". Boundary continuity is covered by the engine's existing tests (`tests/test_shared_continuous_des.py`), unchanged.

Implement per the B4a spec; frontend "Run full operation" for compatible shared analyses, Day summary table (spec §9.2) and four charts, replay with go-to-time, closing-rule summary and "Change", compatibility refusals, preview label.

Tests (backend): continuity across period boundaries (customer identity, order, accumulated wait, in-service customer completes after boundary); closing rules recorded per run; refusal for `variance`/`K`/`theta`; pin test unchanged. Frontend: Day summary equals response fields; preview label present.

## Phase 10b — B13 Per-date separate-lines plans as one continuous day per date

Status (2026-10-12): implemented on `feat/ux-u1-shell` after `7f4c5cd0`, uncommitted pending the owner's approval. One deviation from the spec's text: each date gets its own seed (`date_seed`) rather than the same seed, because the browser check showed equal-input dates replaying identical customers.

Implement per the B13 spec (owner answers 2026-10-12: basis-specific engine version, refuse a date that cannot be laid out, keep today's method with the notice for uploads without operating segments). Tests per spec §10, including the replaced `test_per_date_basis_keeps_the_24_hour_candidate_runs`.

## Phase 11 — B4b Recorded service times

Per its spec. Becomes the standard shared simulation for customer-record uploads only after its reference cases and continuity tests pass; until then the preview label and legacy fallback remain.

## Phase 12 — B4c Shared-line break modeling

Per its spec; then enable D26 states for the standard shared line.

## Phase U8 — Help center

Search, guides (spec §7.11) including "Reviewing older files", "Planning vs review-only files", "Closing time", "Reading the simulation"; contextual "?" links. Screenshots deferred to U10.

## Phase U9 + B2 — Quick calculator

B2 per spec §11 with a limit sized for three calls per click. Frontend guest and signed-in pages: situation tabs, ⓘ tooltips, results, "What this means" with c−1 / c / c+1 from three real calls; unstable case wording.

Tests: B2 numbers identical to `/analysis/{model}`; 429 by client; tooltips reachable by keyboard; c−1 = 0 is not requested; unstable result shows no wait.

## Phase 15 — B8 Reports

Per its spec: PDF summary and Excel calculation workbook, previews derived from the export contract, parity tests per format, formula-check sheet differences within stated tolerance.

## Phase U10 — Final verification

Full gates; browser walkthrough on a local Compose stack with clearly synthetic data covering every path in spec §7 (planning vs review-only upload, older file review, both closing rules, separate-lines breaks, continuous shared preview and standard run, Decision, PDF and Excel); output parity checks for unchanged endpoints; annotated Help screenshots in EN and TL; update `handoff.md` and `memory.md`.

## Risks

| Risk | Mitigation |
|---|---|
| B10 changes the protected "latest file" rule used by evidence and Decision | Own spec, full evidence/generation regression suite, legacy datasets default to planning |
| B4b changes simulation math | Separate authorization, reference cases, new engine version, continuity tests |
| Full-day traces exceed size caps | Decide B6 in the B4a spec before building the replay |
| Extraction of 1,000+ line pages changes behaviour | Extract first with payload-equality tests, then restyle |
| Guest endpoint abuse | Separate low IP limit, no persistence, can be disabled by setting |
| Main checkout stale (G1) | Branch from fresh `origin/main` |
