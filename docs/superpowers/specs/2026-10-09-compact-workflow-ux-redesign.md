# Compact Workflow and UX Redesign: Audit and Design Specification

**Status:** PROPOSED, revision 2. The owner answered OD-UX-1..7 and the follow-up questions on 2026-10-09 (§0). Implementation still needs the owner's GO, and the backend items marked "own spec" need their own specifications first. No application code is changed by this document.
**Date:** 2026-10-09
**Audited tree:** `origin/main` `6093d78a` (worktree `.claude/worktrees/ux-workflow-audit`, branch `docs/ux-workflow-audit`).
**Plan:** `docs/superpowers/plans/2026-10-09-compact-workflow-ux-redesign-plan.md`
**Reports mockup (D31/D32):** `docs/superpowers/specs/assets/2026-10-09-reports-page.html` (artifact https://claude.ai/artifact/Bu2aMJfSprPMWo3mQRkVjU). Its Excel "Formula check" example (λ 40, μ 15, c 3) was recomputed step by step in Python as the cells would (a = λ/μ, ρ = a/c, Erlang C P(wait), Wq = P(wait)/(cμ − λ)) and matches `mmc` to 6.7e-15 min; it has not been opened in Excel. `SEQUENCE()` needs Excel 2021 / Microsoft 365 (OD-UX-14: older-Excel fallback).
**Full-page Queue simulation mockup:** `docs/superpowers/specs/assets/2026-10-09-queue-simulation-page.html` (artifact https://claude.ai/artifact/YCWcbcvDrHhQbVgZUxVmQg).
**Review board (wireframes, version 6):** `docs/superpowers/specs/assets/2026-10-09-compact-workflow-redesign-board.html` (copy of the private artifact https://claude.ai/artifact/BUyTW7G39BdHu6mGNtL6KA). Wireframes are low-detail; their numbers are blank or labelled examples, except the Quick-calculator example, which was computed with NovaQ's `mmc` (§7.12).
**Design references (offline, not production evidence):** `novaq-home.html`, `novaq-workspace.html` and their screenshots in
`C:\Users\Administrator\.codex\visualizations\2026\10\08\01a11aad-a0a2-7682-8ade-86ec534ab103`.

Evidence labels follow `AGENTS.md` §2: VERIFIED, APPROVED SPECIFICATION, REPORTED, PROPOSED, INFERRED, NOT TESTED, UNKNOWN, CONFLICTING. In this document VERIFIED means *established by source inspection on `6093d78a`* unless a test run is named. **No test, build, browser or production check was executed for this audit**; every runtime behaviour below is NOT TESTED unless stated otherwise.

---

## 0. Decisions log (owner, 2026-10-09)

All answers were given in chat on 2026-10-09 and are APPROVED SPECIFICATION for this redesign. They do not authorize implementation before GO.

| # | Topic | Decision | Consequence |
|---|---|---|---|
| D1 | OD-UX-1 Guest calculator | Yes | B2 public calculator endpoint (§11) |
| D2 | OD-UX-2 Onboarding | Remove the mandatory gate | §12 supersession takes effect; preferences move to Settings (B1) |
| D3 | OD-UX-3 Navigation | Adopt the new sidebar | MASTER §9.1 amended; old routes redirect (§5) |
| D4 | OD-UX-4 Compare and selection | Standalone Compare page removed. Plan selection in both places: "Use this plan" in Suggested plans (save + select in one click) and a saved-plan switcher in Analysis results | Persisted selection stays the simulation prerequisite (G5) |
| D5 | OD-UX-5 Home example | Static diagrams, no numbers | §7.1 |
| D6 | OD-UX-6 Backend scope | Initially B1, B2, B9; extended by D8–D20 to B3, B4a/b/c, B5, B8, B10, B11, B12 | §11 |
| D7 | OD-UX-7 Docs | Fix the literal-`\n` formatting of MASTER and product-decisions | Plan Phase 0 |
| D8 | Home | Redesigned "one line" and "separate lines" pictures in plain words; only one "Start an analysis" button (hero), none in the header | §7.1 |
| D9 | Quick calculator (guest and signed in) | ⓘ explanation on every input and result; plain labels; a "What this means" box after Calculate | §7.12 |
| D10 | Sidebar | Hide-sidebar icon only (no "Collapse" word); Help, Settings, email, Language and Log out collapse into one account menu at the bottom | §7.3 |
| D11 | New analysis | Larger, clearer line pictures with everyday examples | §7.5 |
| D12 | Decision | Plain-language outcomes | §7.9 |
| D13 | Reports | PDF = plain summary of tables for deciding, no formulas. Excel = full "check the math" workbook for technical review | B8 in scope (own spec) |
| D14 | Analysis results reader | Managers and supervisors | §7.7 |
| D15 | Analysis results content | Owner's requirement text: review any processed file read-only ("View results from", Data covers, Uploaded on); plain key results; older-file banner; compare two files later in its own spec | B3, B11, B12; compare = later |
| D16 | Planning file | Upload asks "Use for planning" or "Review only"; a review-only file never becomes the plan's data | B10 (own spec; changes the protected current-dataset rule) |
| D17 | Data dates | Save first/last date at upload; recover from per-date period labels on the server; otherwise "Data period unavailable" | B11 |
| D18 | Older-file results | Recalculate and say so: "Calculated today from the inputs saved with this file. Results from the upload day were not saved." | No result storage added |
| D19 | Warnings | Fixed busy level name and range, plus the selected plan's target when one exists | §7.7 |
| D20 | Money on Analysis results | Only after a plan is chosen | §7.7 |
| D21 | Plan view on Analysis results | "What the plan changes" section appears once a plan is selected (no toggle) | §7.7 |
| D22 | Simulation purpose and layout | See it, then get the decision. One page, three steps: Watch the day · Check different possibilities · Decision | §7.8 |
| D23 | Run settings | Under "Advanced", default values labelled | §7.8 |
| D24 | Continuous shared simulation | B4 prioritized: one start, full operating day, no period resets, customers/order/waits/unfinished service preserved across periods, play/pause/speed/go-to-time, whole-day and per-period results from the same run, compatibility check before start | B4a preview (compatible analyses only), B4b recorded service times = the standard version; waiting-space limits and abandonment each in their own spec |
| D25 | Closing rule | Saved per analysis; no preselected choice; explicit first choice; summary with "Change" before every run; recorded with each run; changes affect future runs only; comparing both rules optional | §7.6, §7.8 |
| D26 | Break states | Available, Serving, Finishing customers before break, On break, Closed / not staffed, from simulation events only; "Scheduled break" shown separately; never inferred from idle counters or staffing drops; disclosed as unavailable when events are missing | B5 (separate lines), B4c (standard shared line, own spec) |
| D27 | Simulation key results | Key results open first (Day summary table + four charts); step 2 has its own key results and chart | §7.8, §9.2 |
| D28 | Simulation pages | Queue simulation is three separate pages, not tabs on one long page: **Key results** (`/simulation/results`), **Replay** (`/simulation/replay`), **Checks and decision** (`/simulation/checks`). They share one header (analysis, Current / Suggested plan, page links) and the run bar with "Run full operation". Supersedes the one-page three-step layout of D22 | §5, §7.8 |
| D30 | Simpler simulation pages | (1) One-row run bar: hours, closing rule + Change, status, "Preview · what does this mean?" chip, Run full operation, Advanced. (2) Key results: 4 headline cards Current → Suggested (average wait, longest line, customers served, not served at closing) and 2 charts (people waiting through the day, average wait by period); the other 4 summary rows, 2 charts and both tables under "More results". (3) Checks and decision: Decision first in plain words; one line per check (status, required/optional, "details"); before any decision a "Check the plan" button runs the required checks and then requests the Decision | §7.8 |
| D31 | Two-level result and report | Level 1 after a plan is chosen: "Calculated result · not yet checked by simulation" shown with the Analysis results key metrics, plus a **plan report** (data, plan, calculated results; "Simulation checks: not run"). Level 2 after the simulation checks: the existing **Decision**, and the same report extended with simulation, checks and Decision. The report cover always states its level. Level 1 never uses Decision words (adopt/go ahead), per product-decisions §3 ("suggested/proposed" until simulation, validation and Decision pass). Amends MASTER §9.4 Reports gate | §7.7, §7.9, B8 |
| D32 | Reports | PDF reader: managers and supervisors (plain words, no ρ/Wq symbols). Plan report (level 1): cover with level stamp; key results now vs plan; period table + break times; charts (each with its table). Full report (level 2) adds: Decision page in plain words; simulation key results (4 headline numbers + 2 charts); checks summary (one line per check with settings); "What is not included". Excel: "check the math" workbook with live Excel formulas where Excel can reproduce the model reliably (start with one counter and several counters / Erlang C), NovaQ value beside the Excel value with a difference column; other models show NovaQ values and intermediate steps marked "formula not available in Excel"; simulations give seeds, settings and results for exact re-runs in NovaQ. One layout for both line types; parts that do not apply say why. Keep the data-only report (from Data and setup). Reports page shows a preview generated from the same rules as the file. Add "Reports" to the sidebar under Insights | §7.3, §7.9, B8 |
| D33 | Reports mockup review | Owner reviewed the Reports page, PDF sample pages and Excel workbook mockup on 2026-10-09 and accepted it as the target design for B8 | `assets/2026-10-09-reports-page.html` |
| D29 | Replay movement | Speeds 0.25×, 0.5×, 1×, 2×, 5×, 10×. Customer dots glide smoothly between arriving, place in line, counter and finished; never teleport or streak across the screen | §7.8 "Replay motion" |

---

## 1. Goal, scope and non-goals

### 1.1 Goal

Give nontechnical users a compact path through NovaQ:

Home → sign in → My analyses → one analysis workspace (Data and setup / Suggested plans) → Analysis results → Queue simulation → Decision and reports,

without removing any verified capability, and without any screen claiming more than the backend computes.

### 1.2 In scope

Navigation, page composition, labels, inline help, Help center, Settings, language selection, the public homepage, intent-preserving authentication, and the frontend arrangement of existing APIs. A small number of **additive** backend changes are specified separately (§11) and each needs its own approval.

### 1.3 Non-goals (unchanged by this work)

- Queueing formulas, central model selection (`backend/queueing_engine/services/model_selection.py`), optimizer objectives/constraints/defaults, DES and Monte Carlo behaviour, validation and Decision rules, scenario immutability and verification, evidence currentness/staleness, generation identity, report calculations and units.
- Authentication, sessions, CSRF, roles, ownership, Google nonce/token verification and account linking.
- Production deployment, Render, Cloudflare Pages, Supabase, or any cloud setting.
- The Named Shared Queue limits and contracts (`memory.md`, Shared-Queue Named Release).

---

## 2. Repository-state findings and document conflicts

| # | Finding | Evidence | Label |
|---|---|---|---|
| G1 | The main checkout's `main` (`1d3294cb`) is 78 commits behind `origin/main` (`6093d78a`). This audit used `origin/main`. Anyone implementing from the main checkout would work on stale code. | `git status -sb` in the main checkout: `main...origin/main [behind 78]` | VERIFIED |
| G2 | `design-system/novaq/MASTER.md` is stored as one physical line with literal `\n` escape sequences instead of newlines. It renders as one paragraph in Markdown viewers. The same defect affects `docs/superpowers/specs/2026-09-13-ui-ux-refinement-product-decisions.md`. Content is readable after unescaping; meaning is unaffected. | `od -c design-system/novaq/MASTER.md` shows `\ n` byte pairs; `wc -l` = 0 | VERIFIED |
| G3 | The mandatory-onboarding product decision (product-decisions §1; `memory.md` "UI/UX Refinement Product Decisions (2026-09-13)"; `handoff.md` "Full UI/UX Refinement Complete") conflicts with the requested experience (no mandatory onboarding). §12 of this spec proposes to supersede it; it stays in force until the owner approves. | `frontend/src/router.tsx:78-84`, `frontend/src/auth/RequireOnboarding.tsx:16-19` | RESOLVED by D2 (2026-10-09) |
| G4 | MASTER §9.1 fixes two navigation levels (Dashboard, Analyses, Datasets, Advanced Analysis, Account, Admin, Help / Setup…Reports). The requested sidebar (Workspace, Insights, Simulation, Tools; account menu with Settings, Language, Get help, Log out) replaces level 1. This spec amends MASTER §9.1; the two-level rule itself is kept. | `frontend/src/components/layout/Sidebar.tsx:23-41` | RESOLVED by D3 (2026-10-09) |
| G5 | MASTER §9.2 and `memory.md` require Compare (scenario selection) before Simulate. The requested design folds plan selection into Suggested plans. This is compatible only if the same persisted selection (`POST /analyses/{id}/workflow/selection`) is still made before simulation; the spec keeps that prerequisite (§7.6). | `backend/api/workflow.py:1256-1279`, `frontend/src/pages/SimulationPage.tsx:772-790` | VERIFIED constraint |
| G6 | Product-decisions §2 ("separate queues unsupported") is superseded by `memory.md` "Separate-Queue Status (2026-09-19)". Current source supports separate-queue Current, staffing optimization, break optimization and selected-plan evidence. | `memory.md` §Separate-Queue Status; `backend/api/workflow.py:1679-1800`, `2390-2990` | VERIFIED supersession (already recorded) |
| G8 | Revision 1 of this spec (B5) and `memory.md` "Store Floor Playback View" say the playback trace emits no break transition. That holds for the legacy shared DES (`simulation.py:300-327`), but the **separate-lines routing DES records `draining_start`, `break_start` and `break_end`** (`backend/queueing_engine/services/separate_optimization.py:959, 976, 982`; continuous-day run `:1156, 1163, 1167`). The frontend reducer ignores them (`frontend/src/lib/simulationPlayback.ts:80-102`). Whether those events reach the stored selected-plan traces end to end is NOT TESTED. | source lines cited | CONFLICTING, corrected in §3.6 and §11 B5 |
| G9 | The separate-lines break rule drains a lane 3 minutes before its scheduled break (`PRE_BREAK_CUTOFF_MINUTES = 3.0`, `backend/queueing_engine/config.py:30`): it stops taking new customers, finishes its line, then takes the full break from the actual start (`separate_optimization.py:862-870`). | source | VERIFIED |
| G10 | The continuous shared engine supports only Poisson arrivals, exponential service, FCFS and unlimited waiting room (`backend/queueing_engine/services/shared_segments.py:39`); `variance`, `K` and `theta` are out of scope (`:53`). Shared customer-record uploads always carry `variance` and service samples (`backend/data/analysis_ingestion.py:296-316`). So B4a cannot run most customer-record uploads; B4b is required for them. | source | VERIFIED |
| G11 | Revision 2 first described "Check different possibilities" as "share of simulated days that broke the rule". That is wrong: the existing Monte Carlo perturbs λ (±20%) and μ (±10%) in analytical evaluations per period and counts trials with utilization above the threshold (`simulation.py:1117-1242`). The continuous shared engine's replications have no verdict (`shared_replications.py:323-324`). | source | CORRECTED in §7.8 |
| G12 | Which checks the Decision needs differs by path. Separate lines (selected plan): the Results check consumes the saved replay and the saved Monte Carlo and refuses without them (`workflow.py:2776-2830`, "Run selected-plan Monte Carlo before validating this scenario."); the Monte Carlo busy limit defaults to the plan's target (`workflow.py:146-149`; `SimulationPage.tsx:156`). Legacy shared path: the Results check runs its own simulation and variations (`simulation.py:1354-1374`) and `_derive_decision` reads only the replay and the validation (`workflow.py:1534-1590`), so a standalone Monte Carlo run is optional there. An earlier chat answer said Monte Carlo is optional in general; that was wrong for separate lines. | source | VERIFIED; applied in D30 |
| G13 | Revision 2 mapped `conditional` to "Go ahead, but watch these times" and the mockups showed "Yes, go ahead" for separate lines. Both were wrong: `conditional` means all checks passed but the plan costs more (one shared line, `workflow.py:1640-1646`) or its saving is unavailable (separate lines, `workflow.py:2972-2988`); separate lines cannot reach `adopt`. | source | CORRECTED in §7.9 |
| G7 | `AGENTS.md` "Constraints" lists `/onboarding` among CSRF-exempt prefixes; `memory.md` (auto-memory, not repo) REPORTS an owner approval on 2026-09-25 to remove that exemption, not yet implemented. A new preferences endpoint must not be placed under `/onboarding` for that reason (§11 B1). | `backend/api/main.py:65` | VERIFIED code; REPORTED approval |

---

## 3. Audit: existing feature → proposed destination

Columns: **Existing feature | Evidence (file:line) | Proposed destination | Prerequisite / gap | Action**. Action codes: **KEEP** (unchanged), **MOVE** (same behaviour, new place), **RELABEL**, **MERGE**, **UI-NEW** (frontend only, existing APIs), **BE-GAP** (needs backend work in §11), **DROP-ENTRY** (route kept for deep links, removed from navigation).

### 3.1 Authentication and account

| Existing feature | Evidence | Proposed destination | Prerequisite / gap | Action |
|---|---|---|---|---|
| Password login; on success returns to `state.from` or `/analyses` | `frontend/src/pages/LoginPage.tsx:26-44` | Sign in page reached from Home "Sign in" | Intent must survive (§7.2) | KEEP behaviour; RELABEL; add language dropdown |
| `RequireAuth` stores only `location.pathname` as `from` (search and hash dropped) | `frontend/src/auth/RequireAuth.tsx:20` | Same guard | Deep links with `?mode=named` or tab query lose state on sign-in | UI-NEW: store `pathname + search + hash`, sanitize to same-origin app paths (same rule as `OnboardingPage.safeDestination`, `OnboardingPage.tsx:33-35`) |
| Registration with confirm password; verification email; "resend" mode | `frontend/src/pages/RegisterPage.tsx:17-34`; `backend/api/auth_routes.py:115-170` | Create account page | No intent hand-off after verification (user must sign in after clicking the email link) | KEEP; carry intent in `sessionStorage` only as a convenience (§7.2) |
| Email verification, forgot/reset password (fragment token) | `frontend/src/pages/VerifyEmailPage.tsx`, `ForgotPasswordPage.tsx`, `ResetPasswordPage.tsx`; `frontend/src/auth/fragmentToken.ts:1-15` | Unchanged routes | — | KEEP |
| Google Sign-In, configuration-gated (`/auth/config`), nonce cookie, ID-token verification, `email_verified` and nonce checks | `frontend/src/auth/GoogleSignInButton.tsx:60-104`; `backend/api/auth_routes.py:105-112`, `259-310` | Sign in and Create account pages, unchanged component | Reference designs omit it: **must be kept** | KEEP (render on Home's auth surface too) |
| `account_link_required` (non-authoritative Google email matching a password account) | `backend/api/auth_routes.py:342-347`; `GoogleSignInButton.tsx:81-83` | Unchanged message | — | KEEP |
| Google linking from Account | `frontend/src/pages/AccountPage.tsx:151-160`; `backend/api/auth_routes.py:416-456` | Settings → Account and sign-in | — | MOVE |
| `has_password === false`: no current-password form; "Set password" sends the reset email | `AccountPage.tsx:96-102`; `backend/api/account.py:38-41` (`password_not_set`) | Settings → Account and sign-in | — | MOVE unchanged |
| Change password (revokes other sessions) | `AccountPage.tsx:29-54`; `backend/api/account.py:25-60` | Settings → Account and sign-in | — | MOVE |
| Logout clears Google auto-select and caches | `frontend/src/auth/AuthProvider.tsx:35-45`; `Sidebar.tsx:77-80` | Account menu "Log out" (D10) | — | MOVE |
| Admin role guard (frontend `RequireRole`, backend `require_role`) | `frontend/src/auth/RequireRole.tsx:5-11`; `backend/api/deps.py:32-40`; `backend/api/users.py:54-111` | Settings → "Users (admin)" link, admin only | — | MOVE entry; KEEP guard |
| Session/CSRF double submit | `frontend/src/lib/http.ts:10-19`; `backend/api/main.py:56-87` | — | — | KEEP |
| Unknown paths redirect to `/login`; there is no `/` page | `frontend/src/router.tsx:121-124` | `/` becomes the public Home | — | UI-NEW |

### 3.2 Onboarding and preferences

| Existing feature | Evidence | Proposed destination | Prerequisite / gap | Action |
|---|---|---|---|---|
| Mandatory onboarding gate for every protected page | `frontend/src/router.tsx:82-84`; `frontend/src/auth/RequireOnboarding.tsx:9-21` | Removed from the route tree | Owner GO superseding §12 | UI change after GO |
| Onboarding wizard: welcome, workflow tour, queue-structure explainer, guide, terminology | `frontend/src/pages/OnboardingPage.tsx:24, 130-312` | Welcome/tour → Help guides; structure explainer → New analysis inline hint; terminology → Settings → Preferences | — | MOVE content |
| Queue-structure choice in the wizard is **local state only, never saved** | `OnboardingPage.tsx:63` (`useState<Structure>('shared')`), `:115` payload has no structure | New analysis (already persists `queue_structure`) | — | No data to migrate (VERIFIED) |
| `operation_type`, `preferred_terminology` stored per user | `backend/db/models.py:40-44`; `backend/api/onboarding.py:40-55` | Settings → Preferences (optional) | No endpoint writes preferences without also setting `onboarding_completed = True` (`onboarding.py:47`) | BE-GAP B1 |
| Terminology preferences are **never read** by any page, export or API other than the wizard itself | `grep preferred_terminology|operation_type` over `frontend/src` and `backend` returns only the wizard, `api/onboarding.ts`, the model and migration `0004` | Settings shows them as "saved, not yet used in labels" | Using them in copy would be a new feature | RELABEL honestly; do not claim effect |
| Replay from Help (`/onboarding?replay=1`) | `frontend/src/pages/HelpPage.tsx:15-21` | Help → "Getting started" guide; `/onboarding` route kept only as a redirect to Settings → Preferences | — | DROP-ENTRY |

### 3.3 Navigation and shell

| Existing feature | Evidence | Proposed destination | Prerequisite / gap | Action |
|---|---|---|---|---|
| Sidebar sections Overview/Operation/Decision/Account | `Sidebar.tsx:23-41` | Workspace → My analyses; Insights → Analysis results; Simulation → Queue simulation; Tools → Quick calculator; account menu at the bottom (email, Settings, Language, Get help, Log out); hide-sidebar icon (D10) | Sidebar targets that need an analysis use the last-opened analysis (§7.3) | UI-NEW |
| Mobile disclosure below 1024 px with `aria-expanded`, Escape and route-change close | `Sidebar.tsx:66-75`, `86-95` | Kept; extended with collapsed (icon-only) desktop state | — | KEEP + UI-NEW |
| Language buttons and theme toggle only inside the authenticated sidebar | `Sidebar.tsx:115-116`; `LoginPage.tsx` has none | Language selector on Home and auth pages (header) and in the account menu after sign-in; theme in the app header and Settings | — | UI-NEW |
| Skip link and main focus on route change | `frontend/src/components/layout/AppLayout.tsx:11-21` | Kept | — | KEEP |
| Dashboard (`/dashboard`) counts datasets/rows and quick links | `frontend/src/pages/DashboardPage.tsx:18-92` | Merged into My analyses (no separate page in navigation) | — | DROP-ENTRY (route redirects to `/analyses`) |
| Datasets (`/datasets`): global upload/delete, unassigned datasets | `frontend/src/pages/DatasetsPage.tsx`; `backend/api/datasets.py:62-165` | Settings → "Uploaded files" (management only) | Deleting a current dataset changes evidence (comment at `DatasetsPage.tsx:41-49`) | MOVE; keep confirmations |
| Workflow stepper (7 steps) with Previous/Next; no evidence status shown | `frontend/src/components/analysis/WorkflowNavigator.tsx:1-49`; `frontend/src/lib/workflow.ts:1-9` | Replaced by workspace tabs plus a compact "Next step" panel driven by `GET /workflow` evidence | MASTER §9.3-9.4 predicates | UI-NEW |
| Analysis switcher in each workspace | `frontend/src/components/analysis/AnalysisWorkspace.tsx:24-31` | Becomes the "Analysis" filter on Results and Simulation | — | MOVE |

### 3.4 Analyses, data and setup

| Existing feature | Evidence | Proposed destination | Prerequisite / gap | Action |
|---|---|---|---|---|
| Analyses list with structure filter and archive; **no search** | `frontend/src/pages/AnalysesPage.tsx:10-99` | My analyses with search (name, location, service type; client-side over `GET /analyses`) | — | UI-NEW |
| New analysis: name, service type, location, shared vs separate, queue IDs, "Help me choose" | `frontend/src/pages/NewAnalysisPage.tsx:9-105` | New analysis; labels "One shared line" / "A separate line for each counter" | — | RELABEL |
| Guided setup (two-question recommender) | `frontend/src/pages/GuidedSetupPage.tsx:20-60` | Inline "Not sure? Answer two questions" disclosure in New analysis | — | MOVE |
| Template guide and download (aggregate/events, CSV/XLSX) | `frontend/src/components/analysis/SetupDataTemplates.tsx:16-132`; `backend/api/templates.py:42-79`; `backend/data/templates.py:121-126, 199-260` | Data and setup, step 1 "Download the template" (XLSX first, CSV secondary) | Shared templates have no staff/breaks sheets (VERIFIED `templates.py:121-126` only for separate events) | MOVE |
| Upload with `.xlsx` preview, read errors, setup diff and explicit replacement confirmation | `frontend/src/pages/AnalysisSetupPage.tsx:83-98, 160-177, 229-254`; `backend/api/analyses.py:178-322` | Data and setup, steps 2-3 "Upload" and "Review what we read" | — | MOVE unchanged |
| Setup workbook export (separate only) | `AnalysisSetupPage.tsx:255-260`; `backend/api/analyses.py:324-340` | Data and setup → "Download my current setup" | — | MOVE |
| Setup form: structure, queue IDs, period basis, breaks, server count, segments, capacity, abandonment | `AnalysisSetupPage.tsx:196-216` | Data and setup → **Advanced settings** disclosure | Segments are separate-only in the form (`:208`) | MOVE; RELABEL |
| Segment rule: end strictly after start, no overlap, same day | Frontend `AnalysisSetupPage.tsx:144-145`; backend `backend/api/analysis_schemas.py:67-70` | Advanced settings | Overnight not supported (§8) | KEEP |
| Model explanation per period | `AnalysisSetupPage.tsx:263` | Analysis results → "How this was calculated" | — | MOVE |
| Current dataset = highest-id dataset with `validation.ok` | `backend/api/current_dataset.py:49-61` | "View results from" on Analysis results; planning file selected by default; any processed file reviewable read-only (D15) | Selecting a non-current dataset for results is not supported by `/current` or `/workflow` (`backend/api/analyses.py:343-366`; `workflow.py:1194-1200`); the "latest file" rule also decides the planning data (D16) | BE-GAP B3, B10, B11 (in scope) |

### 3.5 Plans (Optimize, Compare)

| Existing feature | Evidence | Proposed destination | Prerequisite / gap | Action |
|---|---|---|---|---|
| Shared staffing optimizer via stateless `/optimize/batch`, defaults from `planning-defaults.json` (target 0.7, server cost 94.375/h, waiting cost 100/h, 1-24 servers) | `frontend/src/pages/OptimizePage.tsx:496, 539-556`; `frontend/src/api/planning-defaults.json` | Suggested plans → **Counters to open** | Defaults must be shown as editable assumptions | MOVE; disclose defaults |
| What-if demand multiplier | `OptimizePage.tsx:603-621` | Suggested plans → "Check a busier or quieter day" | — | RELABEL |
| Save scenario (client snapshot; server re-verifies → `verified_snapshot`) | `OptimizePage.tsx:623-697`; `backend/api/scenarios.py:100-115, 222-240, 287-357` | "Use this plan" = save scenario + persist selection | Name required: proposed default "Plan – {date time}", editable | UI-NEW using existing APIs |
| Separate staffing optimizer (routing DES per period; default target 0.70) | `OptimizePage.tsx:508, 558-588`; `backend/api/workflow.py:1679-1736` | Counters to open (separate) | — | MOVE |
| Break optimizer: read-only proposal, apply with `window.confirm`, only on latest dataset; defaults target 0.85, move window 120 min | `OptimizePage.tsx:280-488` (`:289-290`, `:321`, `:349`, `:380`); `workflow.py:1737-1940` | Suggested plans → **Break times** (separate queues only) | `window.confirm` is not an accessible dialog | MOVE; replace confirm with accessible dialog; disclose defaults |
| Compare: scenarios table, evidence badges, select for simulation | `frontend/src/pages/ComparisonPage.tsx:381-702`; separate view `:46-355` | "Use this plan" in Suggested plans + "What the plan changes" section with saved-plan switcher in Analysis results (D4, D21) | Selection API unchanged | MERGE; page removed, route redirects |
| Separate comparison: current analytical vs plan simulated, never subtracted | `memory.md` Separate-Queue Status; `ComparisonPage.tsx:46-355`; `workflow.py:1959` | Analysis results, same basis labels | — | MOVE unchanged |

### 3.6 Results, simulation, Decision and reports

| Existing feature | Evidence | Proposed destination | Prerequisite / gap | Action |
|---|---|---|---|---|
| Current page: KPIs, arrivals chart, workload chart, model distribution, model explanations, detailed table, period/line filter, observed vs modeled wait | `frontend/src/pages/AnalysisCurrentPage.tsx:77-334`; `PeriodFilter.tsx` | Analysis results (Current view) | — | MOVE |
| Shared legacy DES: each period simulated for `sim_hours` (default 24 h) and stacked on one clock; carryover = rounded final queue length only | `backend/queueing_engine/simulation/simulation.py:889-934` (`:932-933`); `workflow.py:127-134`; `SimulationPage.tsx:627` | Replaced as the standard shared simulation by the continuous run (D24) | Not a continuous operating-window run | BE-GAP B4a/B4b (in scope); legacy path kept and labelled until B4b is verified |
| Shared legacy playback shows **one** segment's trace; trace capped at 3,000 events | `SimulationPage.tsx:820-822`; `workflow.py:132` | Queue simulation → Playback | Full-window playback impossible for this engine | Label; BE-GAP B4/B6 |
| Separate selected plan, representative day: **one continuous-day DES**, queues and breaks carry across periods; UI splits events per period | `workflow.py:2458-2569` (`:2522`, `:2545`); `SimulationPage.tsx:154-290` | Queue simulation → Playback over the full window by concatenating the per-period event lists of that one execution | Global trace cap 10,000 events (`separate_optimization.py:91`); `truncated` flag must be shown | UI-NEW |
| Separate selected plan, per-date basis: each period independent over 24 h (K1) | `workflow.py:2234-2245`; `memory.md` K1 | Queue simulation, per-period only, with K1 notice | Continuity not available | Label |
| Separate Current-mode DES (no selection) | `SimulationPage.tsx:746`; `workflow.py:1311-1340` | Queue simulation, "Current" toggle | Endpoint is structure-generic but the UI enables it only for separate (INFERRED from `:746`; shared path NOT TESTED) | KEEP scope |
| Named shared queue (continuous horizon, roster, DRAIN/HARD_CUTOFF) via `?mode=named` | `SimulationPage.tsx:722-740`; `backend/api/shared_named.py:518-788` | Queue simulation → "Staff roster simulation" mode | Limits provisional (memory) | MOVE; keep `?mode=named` deep link |
| Trace event vocabulary handled by playback: `arrival`, `service_start`, `service_end`, `abandon`. The legacy shared DES emits no break events; the separate routing DES also emits `draining_start`, `break_start`, `break_end` (G8), which playback ignores | `frontend/src/lib/simulationPlayback.ts:80-102`; `simulation.py:300-327`; `separate_optimization.py:959-982, 1156-1167` | Replay counter states (D26) | Separate lines: frontend handling + end-to-end check; standard shared line: break modeling does not exist (B4c) | B5 (mostly UI) + B4c (own spec) |
| Store floor view, closed-lane badge, 0.25x speed | `memory.md` Store Floor Playback View; `StoreFloorView.tsx` | Playback | — | KEEP |
| Monte Carlo, validation, selected-plan MC/validation | `SimulationPage.tsx:671-717`, `141-580`; `workflow.py:1342-1440, 2611-2990` | Queue simulation → Simulation results → "Check different possibilities" (MC) and "Results checks" (validation) | — | RELABEL |
| Decision (shared and selected) | `components/analysis/DecisionEndpointPage.tsx`; `components/decision/DecisionEndpoint.tsx`; `workflow.py:2990-3111` | Queue simulation → "Decision" panel + Analysis results summary card | — | MOVE |
| Reports: preview, PDF/Excel (shared scenario; separate selected) | `frontend/src/pages/ReportsPage.tsx:72-445`; `backend/api/reports.py:429-639`; `backend/reports/report_export.py:377-545, 838-990` | PDF becomes a plain summary of tables; Excel becomes the full calculation workbook (D13) | Preview/export parity is protected; content change needs a report spec | B8 (own spec) |
| Advanced Analysis calculator (explicit model tabs; authenticated; per-user rate limit) | `frontend/src/pages/AnalysisPage.tsx:104-216`; `backend/api/analysis.py:13-17, 75-81`; `deps.py:43-67` | Tools → Quick calculator (signed in) | Guest use needs an unauthenticated endpoint | BE-GAP B2 |

### 3.7 Help and language

| Existing feature | Evidence | Proposed destination | Prerequisite / gap | Action |
|---|---|---|---|---|
| Help page: replay onboarding, workflow list, limits | `frontend/src/pages/HelpPage.tsx:4-39` | Help center with search and guides (§7.11) | Annotated screenshots only after screens are final | UI-NEW |
| i18n EN/TL, `novaq_lang`, document language sync, key symmetry test | `frontend/src/lib/i18n.ts:6-31`; `frontend/src/lib/translationKeys.test.ts` (memory) | Unchanged mechanism; dropdown UI | Every new key in both catalogues | KEEP |

---

## 4. Review of the reference designs

Adopted (PROPOSED): homepage hero with two actions; dark navy sidebar with Workspace / Insights / Queue simulation / Tools groups; bottom account menu (changed by D10); hide-sidebar control (icon only, D10); header with theme; My analyses cards with structure label and time window; Playback with Arrived / Waiting / In service / Completed counters and the accounting line *Arrived = waiting + in service + completed*; "Check different possibilities" and "Results checks" cards with an explicit **Not run** state.

Rejected or changed, with reason:

| Reference element | Reason | Evidence |
|---|---|---|
| Counter status "On break" during playback, derived by the reference from its own fixture | Allowed only from real simulation events (D26). Separate lines already record break events (G8); the standard shared line has none until B4c. Planned break times appear separately as "Scheduled break (from your setup)". | §3.6; G8 |
| Manual "Advanced settings" period editor that saves drafts which "require connected backend" | NovaQ's analyses are computed from uploaded data. Rates typed by hand are only accepted through an aggregate upload today. A manual period grid needs an additive backend path (B7) or must generate an aggregate file the user uploads. | `backend/data/ingestion.py:15-16`; `analysis_ingestion.py:115-210` |
| "Backend trace loaded · seed 42" badge, "Example data" | Fine as a pattern; real values must come from the stored job (`seed`, `max_events`, `truncated`, `event_count`). | `workflow.py:2545-2560` |
| Overnight periods (`day` offset in the period editor) | Not supported by segments or the separate day layout (§8). | `analysis_schemas.py:67-70`; `separate_optimization.py:673` |
| Reference's own Excel "Backend calculations" sheet | The reference built it from its own fixture. Real exports are defined by `report_export.py`; additions need B8. | `backend/reports/report_export.py:377-545` |
| No Google Sign-In | Must be kept. | §3.1 |
| Fira/other fonts, new palette | MASTER §2/§5 forbid; keep Inter/system and navy/gold tokens. | MASTER §2, §4, §5 |

---

## 5. Sitemap and routes

```
/                              Home (public)
/calculator                    Quick calculator (guest, B2)
/login  /register  /verify-email  /forgot-password  /reset-password   KEEP
/help, /help/:topic            Help center (public topics + signed-in topics)
── signed in (RequireAuth; no onboarding gate) ──
/analyses                      My analyses (search, cards)
/analyses/new                  New analysis
/analyses/:id                  → /analyses/:id/data
/analyses/:id/data             Workspace tab "Data and setup"
/analyses/:id/plans            Workspace tab "Suggested plans"
/results?analysis=:id&file=:datasetId&period=&line=                          Analysis results
/simulation/results|replay|checks?analysis=:id&plan=current|suggested&t=HH:MM&mode=named   Queue simulation (three pages)
/analyses/:id/decision         Decision (also step 3 of Queue simulation)
/analyses/:id/reports          Reports (PDF summary, Excel calculations)
/tools/calculator              Quick calculator (signed in)
/settings, /settings/:section  account, preferences, appearance, files, users (admin)
── compatibility redirects ──
/dashboard → /analyses ; /datasets → /settings/files ; /analysis → /tools/calculator ;
/account → /settings/account ; /admin → /settings/users (RequireRole kept) ;
/onboarding → /settings/preferences ;
/analyses/:id/setup | guided-setup → /analyses/:id/data ;
/analyses/:id/current → /results?analysis=:id ;
/analyses/:id/optimize → /analyses/:id/plans ;
/analyses/:id/compare → /results?analysis=:id ;
/analyses/:id/simulate[?mode=named] → /simulation?analysis=:id[&mode=named]
```

Unknown paths go to `/` for signed-out users and `/analyses` for signed-in users (today: always `/login`, `router.tsx:121-124`).

---

## 6. Data and evidence flow

```
Template (GET /templates/download) ─► user fills Excel ─► POST /analyses/{id}/datasets/preview
   └─ read errors │ derived setup + diff ─► confirm replacement ─► POST /analyses/{id}/datasets?apply_setup=true
                                                                     │
                       current dataset = highest-id valid dataset (current_dataset.py:49-61)
                                                                     ▼
GET /analyses/{id}/current ──► Analysis results: Current (Calculated estimate; inputs From your data)
GET /workflow/observed-wait ─► observed wait (From your data, event uploads only)
                                                                     ▼
Suggested plans: /optimize/batch (shared) | /workflow/optimize/separate (+ /breaks, /breaks/apply)
   └─ "Use this plan" ─► POST /scenarios (server-verified snapshot) ─► POST /workflow/selection
                                                                     ▼
Queue simulation: /workflow/simulation/des[/current|/selected], /mc*, /validation*  (From a simulation)
   └─ Decision: POST /workflow/decision[/selected]  ─► Reports: /reports/... (PDF/Excel)
Staleness: Setup save, upload, break apply and dataset delete reset ['workflow', id] and ['scenarios', id]
           (AnalysisSetupPage.tsx:67-98, OptimizePage.tsx:334-341, DatasetsPage.tsx:41-49) — preserved.
```

Every arrow above is an existing endpoint (VERIFIED by route listing). The redesign adds no new evidence kind.

---

## 7. Screen and component specifications

Shared rules for every screen: MASTER tokens, Inter/system font, one `h1`, one primary action per region, `ApiState` for loading/empty/error/forbidden, explicit "Unavailable" with a reason for missing values, provenance chip on every number (§9), EN/TL keys added together.

### 7.1 Home (public, `/`) — D5, D8

- Header: logo, How it works, Quick calculator, Help, language selector, theme toggle, **Sign in**. No "Start an analysis" button in the header.
- Hero: "See how long your customers wait. Find a better way to staff your counters." One primary **Start an analysis** button and a secondary "Try the quick calculator", with "The calculator works without an account."
- "How do your customers line up?" — two static SVG pictures with one plain sentence and an everyday example each:
  - **Everyone waits in one line.** The next person walks to whichever counter is free. (Like a bank, a pharmacy, or "next please" service.) The picture shows one line and a free counter taking the next person.
  - **Each counter has its own line.** People pick a line and stay in it, even if another line moves faster. (Like supermarket checkout lanes.)
  - The drawn waiting counts are illustrations, not results, and carry no wait times.
- Three numbered steps (a real sequence): Add your records · See suggested plans · Watch your day.
- "Start an analysis" → signed in: `/analyses/new`; signed out: `/login?next=/analyses/new`. A signed-in visitor sees "Go to My analyses" instead of Sign in.

### 7.2 Sign in and intent preservation

- Intent sources: `location.state.from` (set by `RequireAuth`, now including search and hash) or `?next=` from Home. Both are accepted only when they start with `/`, do not start with `//`, and are not an auth route; otherwise the default is `/analyses`.
- Password login, Google success, and post-verification sign-in all call one `continueAfterSignIn(intent)` helper.
- Registration: the intent is kept in `sessionStorage` (`novaq_intent`, path only, no personal data) so that after the email verification link and sign-in the user reaches New analysis. Storage failure falls back to `/analyses` (MASTER browser-storage rule; never required for correctness).
- Language dropdown on every auth page.

### 7.3 Application shell and sidebar — D10

- Top of the sidebar: logo and a **hide-sidebar icon button** (no text label; accessible name "Hide sidebar" / "Show sidebar", tooltip on hover and focus, `aria-expanded`).
- Groups: **Workspace** → My analyses; **Insights** → Analysis results, Reports (D32); **Simulation** → Queue simulation; **Tools** → Quick calculator.
- Bottom: one **account button** (initials and email) that opens a menu: email (text), Settings, Language ▸, Get help, Log out. Menu semantics: button with `aria-haspopup="menu"`/`aria-expanded`, arrow-key navigation, Escape and outside click close and return focus to the button.
- Hidden sidebar: icon rail; each icon has an accessible name and a tooltip on hover and keyboard focus (WCAG 1.4.13). Remembered in `localStorage` `novaq_sidebar` (try/catch).
- Below 1024 px: existing header + menu disclosure (MASTER §8.1); the account menu items sit at the end of that menu.
- App header: breadcrumb and theme toggle. Language lives in the account menu after sign-in (and in the public header before sign-in).
- Analysis results and Queue simulation open the last-used analysis (`novaq_last_analysis`, validated against `GET /analyses`), else an analysis picker empty state.

### 7.4 My analyses (`/analyses`)

- Search box (label "Search analyses"), structure filter (All / One shared line / Separate lines), count text ("2 analyses"), cards: name, structure, setup status (`analyses.status.*`), operating window and period count **only when derivable** (segments in `queue_setup`, or periods of the current dataset); otherwise "Window not set yet". Card actions: "Open", "Archive" (with confirm dialog; today archive has no confirmation, `AnalysesPage.tsx:91`).
- Primary action "New analysis".
- Empty state: "You have no analyses yet" + New analysis + link to Help "Starting an analysis".

### 7.5 New analysis (`/analyses/new`) — D11

Same fields and API as today. The structure choice is two large picture cards reusing the Home SVGs (§7.1) with radio semantics, plain titles ("Everyone waits in one line" / "Each counter has its own line") and everyday examples (bank, pharmacy, "next please" office / supermarket lanes, toll booths). Only the name is required. Separate lines: counter names editor below the cards. "Not sure which one? Answer two questions" opens the Guided-setup recommender inline. Create → `/analyses/:id/data`.

### 7.6 Workspace (`/analyses/:id/data` and `/plans`)

Header: analysis name, structure, current dataset (name, upload date, validation), a "Next step" panel computed only from `GET /workflow` + `setup_status` (MASTER §9.4), tabs **Data and setup** | **Suggested plans** (WAI-ARIA tabs that are also routes).

**Data and setup** (numbered, each step collapsible once done):

1. *Download the template* — structure-matched; XLSX first. Hint: what each sheet is for; separate event workbooks include `events`, `staff`, `breaks`.
2. *Fill it in Excel* — short example table from `/templates/guide` (existing).
3. *Upload* — existing preview → confirm replacement → upload (unchanged calls), plus the question **"This file is for: Use for planning / Review only"** (D16, B10). A review-only file never becomes the plan's data. Until B10 ships, the upload states "This file will become the data for your plans and simulations."
4. *Review what we read* — existing derived-setup summary + dataset validation message + period list from the current dataset.
5. *At closing time* (D25) — "What happens at closing time?" ○ Finish serving customers already waiting or checking out ○ Stop service at closing; people still waiting are not served. No preselected choice. Saved per analysis and shown beside the operating hours. Required before a continuous simulation can run. Changing it affects future runs only. Wording maps to the engine's `DRAIN` and `HARD_CUTOFF` rules (`shared_continuous_des.py:46-66`).
6. *Advanced settings* (closed by default) — existing Setup form fields regrouped: Queue arrangement (read-only once set), Lines and counters, Operating periods (segments), Breaks (separate), Capacity, Customers leaving (abandonment). Save keeps today's cache resets.
7. "Download my current setup" (separate; existing).

Period editing within current support: 1–24 periods of 15, 30 or 60 minutes, mixed, on one calendar day, each `start < end`, no overlap. The UI offers a "Make periods" helper (start time, count, length) that **writes segments only** (separate) — PROPOSED; for shared analyses segments are not editable in today's form (VERIFIED `AnalysisSetupPage.tsx:208`), so shared period lengths come only from uploaded data (aggregate `time` labels or event segmentation). Whether aggregate rows of different lengths are weighted correctly downstream is UNKNOWN (the aggregate schema has no duration column, `ingestion.py:15-16`); the UI must not claim mixed-duration support for shared aggregate uploads until checked (plan Phase 4, task 4.6).

**Suggested plans** (two sub-sections):

- *Counters to open* — shared: optimizer form with defaults shown as "Assumptions you can change" (target busy share, counter cost per hour, waiting cost per customer-hour, min/max counters, optional max wait). Separate: target and costs as today. Results table per period: current counters (From your data), suggested counters and predicted wait (Calculated estimate; separate plan values From a simulation). Copy: "This plan has the lowest modeled cost among options that meet your limits. It is an estimate, not a guarantee."
- *Break times* (separate only; shared shows "Break suggestions are available for separate lines only"). Read-only proposal, accessible confirm dialog listing moves, apply only on the current dataset; copy: "This is a local improvement found by moving breaks one at a time. A better arrangement may exist." (greedy, `memory.md`).
- Plan actions: **"Use this plan"** = `createScenario` then `selectWorkflowScenario` (two existing calls, sequential, with partial-failure message "Plan saved but not selected — select it in Analysis results"); "Save without using"; "View results"; "Simulate this plan". A plan built on a stale snapshot cannot be used (existing `stale`/`sepStale` guards).

### 7.7 Analysis results (`/results`) — D14–D21

Reader: managers and supervisors.

- **View results from** (file selector): every successfully processed file of the analysis. Each entry shows the filename, **Data covers** (B11; "Data period unavailable" when dates cannot be established; never inferred from a filename) and **Uploaded on**. The planning file is selected by default and tagged; review-only files are tagged "Review only".
- Selecting a non-planning file is read-only. Banner: "You are reviewing a previous file. Your current staffing plan has not changed." plus "Calculated today from the inputs saved with this file. Results from the upload day were not saved." (D18). Switching files clears previous charts and values before the new ones load.
- **Key results** (each answers one question, with source label and "How was this calculated?"):

  | Manager question | Label | Source |
  |---|---|---|
  | How long did customers wait? | Recorded average wait | From your data (customer-record uploads only; otherwise "Recorded waiting time is unavailable because this file does not contain customer arrival and service-start times.") |
  | What wait does NovaQ estimate? | Estimated average wait | Calculated estimate |
  | Which period needs attention? | Period that needs attention: periods where counters can't keep up first, then the period with the highest estimated average wait ("not the longest wait any one customer had") | Calculated estimate |
  | When did demand peak? | Busiest period by customer arrivals | From your data (B12 server field) |
  | How much pressure did each line face? | Estimated cashier-line workload (separate lines only; "not a performance score"; one shared line shows the counter group per period) | Calculated estimate |

- Day strip shaded by NovaQ's fixed busy levels (Lean < 60%, Normal 60–80%, Peak 80–90%, Critical 90–100%, Can't keep up ≥ 100%; `frontend/src/lib/utilization.ts`), with the ranges in the legend and the note "Busy levels are NovaQ's fixed labels, not a target for your store." Warnings name the busy level and, when a plan is selected, "above this plan's target of N%" (D19). Warnings never instruct the manager to add staff.
- Charts: customers per hour by period; recorded vs estimated wait by period (customer-record uploads); cashier-line workload (separate lines).
- **What the plan changes** (appears only once a plan is selected; D21): saved-plan switcher with "Use for simulation", per-period table counters / estimated wait / busy level now → plan, plan-target flags, and **staff cost now vs with the plan** (D20; separate lines show "today's total cost is not available" with the reason). Plans always use the planning file.
- Missing values show "Unavailable", never 0. "Compare with another file" is shown as coming later (own spec).
- **Calculated result (D31, level 1)**: once a plan is selected, a card above "What the plan changes": "The calculation suggests …" (counter changes, estimated wait now → plan, cost now → plan when available) with the label "Calculated result · not yet checked by simulation" and links "Download plan report" and "Check it in Queue simulation". Built only from the saved plan and its comparison fields; no verdict words. For separate lines the plan values already come from the optimizer's routing simulation and the card says so, but it is still not the full check.

### 7.8 Queue simulation (`/simulation`) — D22–D27

Three pages (D28): **Key results** (`/simulation/results`, opens first), **Replay** (`/simulation/replay`, with "Open full screen"), **Checks and decision** (`/simulation/checks`). Shared header: Analysis selector · **Current | Suggested plan** (which run) · page links. Shared run bar: "Run full operation", status, Advanced settings, run label. Full-page mockup: `assets/2026-10-09-queue-simulation-page.html`. Below: "Operating hours: 05:00–18:00 · At closing time: <saved rule> · Change", and a compatibility status ("Ready to run" or the reason it cannot run).

Compatibility check before start (examples of required messages):
- "This simulation does not yet support customers leaving the queue, which is enabled in your setup."
- "Choose what happens at closing time before running."
- B4a only: "Preview: uses a simple service-time assumption. The standard version for customer records is not available yet." (B4a is never presented as the standard full-operation simulation for customer-record uploads.)

Page content (each page shows Not run / Running / Done / Out of date for the shared run; checks unlock after a run exists):

1. **Watch the day.** "Run full operation" starts one continuous run of the configured operating hours (B4).
   - *Key results tab*: Day summary table, Current vs Suggested (§9.2), then four charts: people waiting through the day (with scheduled breaks marked), average wait by period, customers arriving vs starting service, counters open vs busy. All from the same run.
   - *Replay tab*: Arriving → line(s) → counters → finished; counts Arrived / Waiting / Being served / Finished with "Arrived = waiting + being served + finished"; clock; Restart, Play/Pause, speed, "Go to time"; a timeline with "Scheduled break (from your setup)" markers on a separate row; counter states per D26. If the replay is cut short: "The replay stops at HH:MM. The summary still covers the whole run."
   - Run label: "One continuous run · closing rule used: <rule> · seed <n>".
2. **Check different possibilities.** Two cases (G11):
   - *Separate lines and the legacy shared path (exists today):* "Many variations" (Monte Carlo) recalculates each period `num_trials` times (default 2,000) with the arrival rate varied up to ±20% and the service rate up to ±10%; a variation fails when utilization exceeds the busy limit (default 75%); the plan holds up when the failing share is at most the allowed share (default 5%), with a 95% Wilson range (`simulation.py:1117-1242`; `config.py:34-39`). Key results: variations that failed (with range), allowed share, periods (or counters) to watch, result (Holds up / Does not hold up / Not enough variations to tell); one chart by period with ranges and the allowed line. Label: Calculated estimate (many variations), not "simulated days". "Results check" (validation) runs the simulation and the variations on the plan (`simulation.py:1354-1374`) and shows passed / did not pass / not enough data from the saved result only.
   - *One shared line, continuous run (B4):* "Repeat the day" runs the whole day again with new random customers (`shared_replications.py`) and shows ranges only, because the engine returns `verdict: None` and no pass/fail rule is approved (`shared_replications.py:323-324`; `memory.md` Shared-Queue DES Replications).
3. **Decision** (§7.9). For the continuous shared run a Decision is not available until a pass/fail rule is approved (OD-UX-13).

Simplified layout (D30): one-row run bar; Key results leads with 4 headline cards and 2 charts, the rest under "More results"; Checks and decision leads with the Decision, then one line per check. "Check the plan" runs, for separate lines, Many variations → Results check → Decision (three existing requests); for the legacy shared path, Results check → Decision. Required/optional labels follow G12.

Run settings sit under "Advanced" with default values labelled (D23). Saved results always show the settings and closing rule they used; changing the closing rule never relabels old runs.

Engine coverage (stated on screen):

| Analysis | Run used | Status |
|---|---|---|
| One shared line, compatible inputs | Continuous shared run (B4a preview) | Preview label until B4b |
| One shared line, customer-record upload | Continuous run with recorded service times (B4b) | Standard version after B4b is verified; until then the legacy period-by-period run stays available and labelled "one period at a time" |
| One shared line, waiting-space limit or customers leaving enabled | — | Refused with the reason (own specs) |
| Separate lines, typical day | Existing continuous-day routing run (`workflow.py:2458-2569`) | Full-day replay from one execution; break states from its events (B5) |
| Separate lines, one result per date | Per-period runs (K1) | "One period at a time" notice |
| One shared line, staff roster | Named mode (`?mode=named`) | Unchanged |

Replay motion (D29). Root cause of today's "super fast" shared playback (VERIFIED): speed is relative to the whole trace length (`LiveSimulationPlayback.tsx:14` `PLAYBACK_SECONDS_AT_1X = 60`; `simulationPlayback.ts:255` `traceEnd / (60 × 1000)`), and the legacy shared trace stacks 24 h per period, so 13 periods ≈ 312 simulated hours play in 60 s at 1× (≈ 5 simulated hours per real second); tokens also change position without transition. New rules:
- The clock speed is defined against simulated time, not trace length: PROPOSED 1× = 1 simulated minute per real second (13-hour day ≈ 13 min at 1×, ≈ 78 s at 10×, ≈ 52 min at 0.25×). The owner has not chosen a different base rate; this is an assumption until confirmed.
- Each customer dot animates its position (transform/opacity only, eased) between arriving, its place in line, its counter and finished. Glide duration stays within about 0.2–0.9 s at every speed (≈ 650 ms / √speed, clamped), so dots never teleport or streak. The line closes up smoothly when a customer leaves it.
- Counts, clock and states are always exact for the current simulated time (from the existing reducer); the glide only animates how a dot reaches its exact position.
- When more events happen than can be drawn legibly, the line shows the first N dots plus "+N more"; counts stay exact.
- Playback pauses while the browser tab is hidden. With reduced motion, dots move without gliding.
- Demonstrated (with made-up customers, labelled) in the full-page mockup; browser-checked at 1× and 10× on 2026-10-09.

Counter states (D26): Available · Serving · Finishing customers before break · On break · Closed / not staffed — only from events. Separate lines map `draining_start` → Finishing customers before break, `break_start` → On break, `break_end` → Available; the lane drains 3 minutes before the scheduled break (G9). Idle counters or fewer open counters are never shown as breaks. Missing events: "Break state unavailable for this run."

### 7.9 Decision and reports — D12, D13

Decision (step 3 of Queue simulation and `/analyses/:id/decision`): heading "Should we use this plan?"; plain outcomes mapped from the persisted status (never computed in the browser):

| Persisted status | Text |
|---|---|
| adopt | "Yes, go ahead with this plan. It passed every check and costs the same or less." (one shared line only; separate lines never reach adopt) |
| conditional | One shared line: "The plan passed every check, but it costs more than today." Separate lines: "The plan passed every check, but its cost saving can't be calculated for separate lines. Use it only if you accept the cost." |
| revise | Change the plan first. It did not hold up in: <periods> |
| insufficient_evidence | Not enough checks yet. Run: <missing evidence> |
| stale (`decision_stale`) | Out of date. Your data or setup changed after this check. |

"What we checked" uses plain names (Replay of the day, Many variations, Results check).

Decision prerequisites and rule (VERIFIED, G13):
- One shared line (legacy run, `workflow.py:1534-1666`): Setup complete; a verified plan selected; a supported, error-free replay for every plan period; a Results check for every plan period; a complete modeled cost comparison. A period passes when it is supported, has no validation reason, its status is not ERROR/Critical/Unstable, its failing-variation share is at most the saved cap, and the share is adequate. Any failing period → revise; all pass and modeled savings ≥ 0 → adopt; all pass and savings < 0 → conditional.
- Separate lines (selected plan, `workflow.py:2776-2990`): selected replay with customer conservation; selected Many variations for that replay; Results check. Conservation fails → insufficient_evidence ("rerun the simulation"); check failed → revise with failed periods; insufficient → insufficient_evidence; pass → **conditional** because no comparable current cost exists. Separate lines never reach adopt.
- Out of date: `decision_stale` when Setup or data changed after the decision (`workflow.py:1139-1155`).
Reason sentences shown to managers are built from these returned fields (`missing_evidence`, `failed_periods`, `inadequate_periods`, `facts`), never written generically.

Reports (`/reports?analysis=:id`, sidebar Insights → Reports; D32). Reports page: analysis selector, level stamp, a preview listing exactly the sections/sheets the files will contain (generated from the same rules as the files), Download PDF, Download Excel, and the data-only report link. Current (pre-D32) structure, VERIFIED: shared scenario PDF = Executive Summary, Staffing Adjustment Summary, Segment Comparison, Utilization Status Legend, Recommendations (`report_export.py:611-806`); shared Excel = Summary, Segments (raw column dump), Recommendations when a current Decision exists (`:809-989`), no simulation content; separate PDF = Decision, Selected Staffing Schedule, Cost Evidence, Validation, Limitations, Provenance (`:199-212`); separate Excel = Overview, Current, Selected Staffing, DES, MonteCarlo, Validation, Decision, Cost, Limitations, Provenance, Plans (`:377-560`); all Excel values are typed values (no formulas).

Target structure (D32), the same for both line types:

| Part | Plan report (level 1) | Full report (level 2) |
|---|---|---|
| PDF cover | Analysis, data file, data dates, date made, plan; stamp "Calculated only · not checked by simulation" | Stamp "Checked by simulation · Decision: <plain outcome>" |
| PDF key results | Now vs plan (average wait, busiest period, period needing attention, counters, cost when available) | + simulation key results (4 headline numbers, 2 charts) |
| PDF periods | Period table (customers per hour, counters now → plan, estimated wait now → plan, busy level); separate lines: break times now → suggested | same |
| PDF charts | 2–3 charts, each with its table | + simulation charts |
| PDF decision | "Simulation checks: not run" | Decision page in plain words; checks summary with settings; "What is not included" |
| Excel | Read me · Inputs · Model choice · Formula check · Plan search · Costs | + Simulation · Many variations · Results check and decision · Not recalculable in Excel |

Earlier draft: two cards.
- **PDF summary** (for owners and managers): cover with analysis, file, date and decision in plain words; your data per period; now vs plan per period; breaks (separate lines); what was checked and what is not included. No formulas or technical terms.
- **Excel calculations** (for checking the math): Read me · Inputs · Model choice · Formula check (live Excel formulas next to NovaQ's value and a difference column) · Plan search · Costs · Simulation · Many possible days · Results check and decision · Not recalculable in Excel. Details and open questions in §11 B8.

Both are content changes to protected exports: they need the B8 report spec with preview/export parity tests before any change.

Report levels (D31): **Plan report** (available once a plan is selected): cover stamp "Calculated only · not checked by simulation", data, plan, calculated results, "Simulation checks: not run". **Full report** (after a current Decision): cover stamp "Checked by simulation · Decision: <plain outcome>", plus simulation key results, checks and Decision. VERIFIED today: the shared scenario report is already generated without a Decision and adds Recommendations only when a current Decision exists (`backend/api/reports.py:591-605`); the Reports page blocks it until a Decision exists (`frontend/src/pages/ReportsPage.tsx:426-434`). The separate-lines report requires the full chain (`reports.py:156-233`), so its plan report needs B8 backend work.

### 7.10 Settings (`/settings`)

Sections: Account and sign-in (email, verification, sign-in methods, password change **or** set-password email for `has_password === false`, Google link), Preferences (operation type and terminology; optional; saved through B1; note "Saved for future use; NovaQ labels do not change yet"), Appearance (theme, language), Uploaded files (current Datasets page), Users (admin only, existing Admin page). Users who never completed onboarding see empty optional fields; nothing is pre-filled.

### 7.11 Help (`/help`)

"Find help" search over local guide titles/bodies (client-side, both languages). Guides: Starting an analysis; Adding your data (template, upload, review); Reading results (each metric and its source); Comparing plans; Queue simulation (playback, period-by-period vs full-day); Checks (Monte Carlo, validation, Decision); Downloads (PDF/Excel contents); Problems (upload errors, stale results, rate limits, sign-in, Google `account_link_required`). Each guide states Action, Purpose, Next step. Contextual "?" buttons on screens deep-link to `/help/:topic#section`. Annotated screenshots are added only after the screens pass Phase 9 verification (plan).

### 7.12 Quick calculator — D1, D9

Guest (`/calculator`, B2) and signed in (`/tools/calculator`) share one layout.

- Tabs named by situation: Basic · Service time varies · Limited waiting space · Some people leave (mapping to the existing explicit models).
- Plain labels with symbols in the ⓘ text: "Customers arriving per hour (λ)", "Customers one counter serves per hour (μ)", "Counters open (c)". Every input and result has an ⓘ tooltip (button, opens on click, hover and focus; Escape closes).
- Results: Average wait in line (minutes), How busy counters are (%), People waiting on average, Can counters keep up? (Yes / No).
- **What this means**: one sentence built only from the returned fields, plus the same calculation with one fewer and one more counter (two additional calls to the same endpoint). No "you should" advice. When counters cannot keep up the engine returns no wait (`Wq = None`, error text); the screen says "Cannot keep up — the line keeps growing."
- Note: "A quick estimate for one typical hour. It assumes customers arrive at random. Start an analysis to use your real records."
- Example used on the board, computed with NovaQ's `mmc` on 2026-10-09 (λ 40/h, μ 15/h): c = 2 unstable (no wait returned); c = 3: ρ 0.8889, Lq 6.3801, Wq 0.15950 h (9.57 min); c = 4: ρ 0.6667, Lq 0.7568, Wq 0.018921 h (1.14 min). VERIFIED by execution of `backend.queueing_engine.models.queue_models.mmc`.

---

## 8. Period, midnight and overnight compatibility

| Capability | Status | Evidence |
|---|---|---|
| Segments of any length within one day, `start < end`, no overlap | VERIFIED (schema) | `analysis_schemas.py:59-70`; `AnalysisSetupPage.tsx:144-145` |
| 1–24 periods of mixed 15/30/60 minutes for **event uploads** with segments | VERIFIED representable (segments assign events and compute `duration_hours`) ; end-to-end results NOT TESTED | `analysis_ingestion.py:69-112` |
| Mixed durations for **aggregate** uploads | UNKNOWN (no duration column; weighting by duration not verified) | `ingestion.py:15-16` |
| A segment crossing midnight (e.g. 22:00–02:00) | NOT SUPPORTED | `analysis_schemas.py:69` |
| Separate representative day crossing midnight | NOT SUPPORTED ("no midnight wrap is defined") | `separate_optimization.py:673` |
| Period ending exactly at 24:00 | NOT SUPPORTED in setup (`time` max 23:59:59) | INFERRED from `datetime.time` type |
| Named shared horizon in minutes since midnight | Within-day only per its validator (INFERRED; not re-read here) | `shared_named.py:165-180` |

The UI must say "Periods must start and end on the same day" and must not offer a day offset. Overnight support is backend gap B7.

---

## 9. Metric dictionary and provenance labels

### 9.1 Analysis inputs and analytical results

Provenance chips: **From your data** (uploaded values or values counted directly from your records), **Calculated estimate** (analytical model or optimizer), **From a simulation** (DES, Monte Carlo, validation). Wait is stored in hours and displayed in minutes (× 60) everywhere.

| Card / column | API field | Source | Units | Scope | Denominator / aggregation | Chip |
|---|---|---|---|---|---|---|
| Arrivals per hour | `rows[].lambda` (`GET /current`) | Aggregate upload value, or event count ÷ period hours (÷ observation days for representative day) | customers/h | period × line | none (per row) | From your data |
| Service rate | `rows[].mu` | Upload value or estimate from service samples | customers/h per counter | period × line | per row | From your data (estimated from samples when events) |
| Counters | `rows[].c` | Upload / setup | count | period × line | per row | From your data |
| Busy share (utilization) | `rows[].rho` | Model via central selection | 0–1, shown % | period × line | per row | Calculated estimate |
| Average busy share | `kpis.avg_utilization` | `results_df["rho"].mean()` over **all** rows incl. unstable | % | dataset | unweighted mean of rows | Calculated estimate — label "simple average of periods" |
| Highest busy share | `kpis.max_utilization`, `max_utilization_time` | max over **stable** rows only | % | dataset | max | Calculated estimate — note "stable periods only" |
| Average wait in line | `kpis.avg_waiting_time` | Shared: unweighted mean of `Wq` over stable rows (`data_processing.py:292`); separate: arrival-weighted Σλ·Wq/Σλ (`:294`, `_weighted_wait`) | h → min | dataset | as stated; unstable periods excluded (shared) | Calculated estimate — label states the averaging rule |
| Unstable periods | `kpis.unstable_count` | rows with `stable` false | count | dataset | count | Calculated estimate |
| Waiting cost | `kpis.total_waiting_cost` | Lq × waiting cost; unstable rows use λ × penalty × waiting cost (`:286`) with default waiting cost if none | ₱ per analyzed period basis | dataset | sum | Calculated estimate — show "uses an assumed penalty for overloaded periods" |
| Observed wait | `periods[].observed` (`GET /workflow/observed-wait`) | Event uploads' derived statistics, weighted by arrival count; absent for aggregate uploads | h → min | period | arrival-count weighted | From your data |
| Suggested counters, predicted wait, cost | `results[].c_optimal`, `Wq_optimal`, cost fields (`/optimize/batch`) | Optimizer | count, h → min, ₱ | period | per row; totals via existing `comparisonTotals` | Calculated estimate |
| Separate plan lane values | `schedule.periods[].optimum…` | Routing DES replications | % / min | period × lane | mean of replications | From a simulation |
| Playback counters | reducer over `trace.trace` | One DES execution (events) | count | events shown so far | cumulative counts; service starts ≠ completions | From a simulation |
| DES results | `results[]` (`Wq_sim`, `rho_sim`, `max_queue`, `served`) | DES run | min, %, count | period (× lane) | per row | From a simulation |
| Monte Carlo failure rate | `mc_failure_rate`, interval fields | MC trials | proportion | period (× lane) | trials | From a simulation |
| Validation verdict | persisted validation result + saved cap | Validation job | pass/fail/insufficient | plan | per saved rule | From a simulation |

### 9.2 Queue simulation key results (continuous shared run)

From the result returned by `shared_continuous_des.py` (`totals`, `segments`, `closing`; lines 440-523). Hours are converted to minutes at display only.

| Day summary row | Field | Denominator / basis |
|---|---|---|
| Average wait in line | `totals.mean_wait_hours` | Customers who started service (`totals.service_starts`); unserved customers excluded and shown separately |
| Customers who had to wait | `totals.waited_count` "of" `totals.service_starts` | Count of customers with wait > 0; no percentage computed in the browser |
| Longest line | `totals.max_queue` | Maximum queue length in the operating horizon |
| Average line length | `totals.time_average_queue` | Time-average over the operating hours |
| Customers served | `totals.service_starts` "of" `totals.arrivals` | Started service, out of arrivals |
| Not served at closing | `cost_quantities.unserved_customer_count` (also `closing.unserved_customer_ids`) | Applies per closing rule (`closing.unserved_possible`) |
| Service finished at | `closing.last_server_release_hours`, with `closing.overrun_hours` | DRAIN shows the time past closing |
| Counter time used | `totals.busy_server_hours` "of" `totals.present_server_hours` | Modeled service-capacity hours, not paid hours (`SERVER_HOURS_MEANING`) |
| Per period | `segments[]`: `arrivals`, `service_starts`, `mean_wait_hours`, `max_queue`, `time_average_queue`, `scheduled_servers`, `utilization_of_present` | Per staffing segment |

Separate-lines continuous-day run: per counter `Wq_sim`, `rho_sim`, `max_queue`, `served`, `arrivals`; day `admitted`, `served` (`workflow.py:2510-2569`). Any total the browser would have to add up must come from the server (B12 pattern).

No card may compute a new average, ROI, score or trend in the browser (MASTER §10.5). "Completed" in playback counts `service_end` events, not `service_start`.

---

## 10. Charts, states, accessibility, refresh and deep links

**Charts (from verified fields only):** arrivals per period (bar, `lambda`, From your data); busy share per period with current vs suggested (grouped bar or dot plot; current/optimized data tokens + dashed pattern; `rho`); predicted wait per period current vs suggested (line, minutes, gaps for missing); counters per period current vs suggested (step chart, `c` vs `c_optimal`); observed vs modeled wait (paired bars, event uploads only); separate lanes: busy share heat map period × lane (`rho_sim`); simulation (§7.8, same run): people waiting through the day (step line from the replay's events, scheduled breaks as a separate band), average wait by period, customers arriving vs starting service, counters open vs busy (`segments[]` fields, §9.2); MC: share of simulated days that broke the rule by period with range and limit (existing `FailureRateBars` basis). Current vs Suggested use data tokens plus solid/dashed lines, never red/green. No pie charts; no synthetic scores. Each chart has a title, units, source chip and a table alternative (MASTER §10.7).

**State matrix (every screen):** Loading (`role=status`), Empty (what is missing + next action), Error (`role=alert`, retry), Unavailable (reason, never 0), Stale (warning + "Stale" text + what changed + rerun), Blocked (named prerequisite + link, e.g. "Select a plan first"), Not run (MC/validation), Truncated (playback), Forbidden (Settings → Users).

**Accessibility:** WCAG 2.2 AA per MASTER §12: focus-visible rings, tab patterns, tooltips on focus, 44×44 targets below 768 px, no hover-only actions, reduced motion for playback animation, accessible dialog replacing `window.confirm` (`OptimizePage.tsx:321`), labelled language `<select>`.

**Refresh and deep links:** every filter and tab is in the URL; reload restores the same view; React Query keys stay `['analysis', id]`, `['current', id, …]`, `['workflow', id]`, `['scenarios', id]` so existing invalidation keeps working. Old routes redirect (§5).

---

## 11. Backend items (separate from UI work)

Status after the 2026-10-09 decisions. "Own spec" = needs its own specification, protected-behaviour analysis and tests before implementation.

| ID | Item | Status | Change | Protected-contract impact |
|---|---|---|---|---|
| B1 | Save preferences without touching `onboarding_completed` | In scope | `GET/PUT /account/preferences`, CSRF-protected, same limits as onboarding fields | Additive |
| B2 | Guest calculator | In scope | `POST /public/calculator/{model}` reusing `analysis._run_model`; IP-keyed `guest_compute` limit sized for three calls per click; no DB | New unauthenticated compute surface (D1 accepted) |
| B3 | Results for any processed file | In scope | Optional `dataset_id` on read-only `GET /current` and `GET /workflow/observed-wait`, owner-checked, `validation.ok` required; response names the dataset | Read-only; evidence, selection and Decision stay on the planning file |
| B4a | Continuous shared run, preview | In scope, own spec | Route over `shared_continuous_des` (+ `shared_playback` for the replay) from the analysis's segments, staffing and saved closing rule; compatibility refusal for `variance`/`K`/`theta`; labelled preview | New route; engine unchanged (pinned by `tests/test_shared_continuous_des_pin.py`) |
| B4b | Recorded service times in the continuous run | In scope, own spec | Define how recorded service-time variation is represented (e.g. empirical resampling per period), how customers in service and waiting carry across periods, reference cases | **Mathematical change** to a pinned engine or a new engine version: separate authorization, reference cases, regression |
| B4c | Break modeling for the standard shared line | In scope, own spec | Rules for customers in service, break timing, return to service; events for D26 states | Simulation behaviour change; separate authorization |
| B5 | Break states for separate lines | In scope | Mostly frontend: reducer handles `draining_start`, `break_start`, `break_end`; backend check that selected-plan traces carry them; equivalence test that aggregates are unchanged | Trace read-only; no engine change expected |
| B6 | Longer replays | Likely; decide in the B4a spec | Trace caps 3,000 (`workflow.py:132`) and 10,000 (`separate_optimization.py:91`); production result cap 786,432 bytes (memory) | Size limits |
| B7 | Overnight periods | Not scheduled | — | — |
| B8 | PDF summary + Excel calculation workbook | In scope, own spec | See below | Report content change; parity tests |
| B9 | Numbers without a file | In scope (UI-only option A) | Browser builds the existing aggregate CSV and uploads it through the existing path | None |
| B10 | Planning file vs review-only upload | In scope, own spec | Persist a per-dataset "planning" flag (or equivalent) and change `resolve_current_dataset` to honour it | **Protected rule change** (`current_dataset.py`, evidence currentness, generation guards, D7 tests) |
| B11 | Data dates | In scope | Store first/last arrival date at ingestion for customer-record uploads; derive per-date ranges from stored period labels server-side; else null → "Data period unavailable" | Additive fields in `validation_report_json` (no migration expected; to confirm) |
| B12 | Server-side totals the browser must not compute | In scope | e.g. busiest period by arrivals across separate lines; served/unserved counts | Additive response fields |
| — | Compare two files | Later, own spec | Comparable periods, units, settings and missing data | — |

**B8 scope after D32:** both line types share one two-level layout; a separate-lines plan report without the full chain; simulation sections for the shared report; live-formula Formula check sheet (start with M/M/1 and M/M/c Erlang C); preview generated from the export contract; data-only report kept. **B8 open questions (to settle in its spec):** which analytical models can be expressed as live Excel formulas (M/M/1 and M/M/c Erlang C: yes; M/G/c, M/M/c/K, M/G/c/K and Erlang-A: UNKNOWN until the engine formulas are inspected); whether the optimizer can return every candidate it evaluated for the "Plan search" sheet (UNKNOWN); simulations cannot be recomputed in Excel, so the workbook records seeds, settings and results for exact re-runs in NovaQ.

---

## 12. Supersession of the mandatory-onboarding decision (APPROVED by the owner on 2026-10-09, D2)

Superseded: product-decisions §1 "Onboarding is required once for a first-time authenticated user…" and the matching `memory.md` and `handoff.md` lines. (Revision 1 also listed "MASTER §16 references to required onboarding"; that was wrong: MASTER does not mention onboarding.)

Replacement decision: *NovaQ has no mandatory onboarding. First-time users go straight to My analyses or, when they chose "Start an analysis", to New analysis. Orientation is provided by plain wording, inline hints, examples, and contextual Help. Operation type and terminology are optional preferences in Settings, saved only when the user saves them. Existing saved values are kept and shown. `onboarding_completed` is retained in the database, is no longer read by the frontend gate, and is never set by any new flow.*

Retained: the database columns, `GET/POST /onboarding/*` (for compatibility; not linked from the UI), the requirement to never save placeholder preferences.

---

## 13. Owner decisions (answered 2026-10-09)

OD-UX-1..7 are answered (§0 D1–D7). Remaining items that need an owner decision later:

| ID | Question | When |
|---|---|---|
| OD-UX-8 | B6 trace limits for full-day replays | In the B4a spec |
| OD-UX-9 | B4b representation of recorded service times and its reference cases | In the B4b spec |
| OD-UX-10 | B10 storage and migration approach for the planning flag | In the B10 spec |
| OD-UX-11 | Decision reason sentences, after mapping the backend rule | Before Phase U7 |
| OD-UX-12 | B8 Excel formula coverage per model | In the B8 spec |
| OD-UX-14 | Excel compatibility of the Formula check sheet: `SEQUENCE()` needs Excel 2021 / Microsoft 365; provide a helper-table fallback for older Excel and LibreOffice? | In the B8 spec |
| OD-UX-13 | Pass/fail rule (and therefore Decision) for the continuous shared run; until approved, Repeat the day shows ranges only and step 3 says a decision is not available | Before Phase 10 ships its Decision step |

---

## 14. Acceptance criteria (summary; detailed per phase in the plan)

1. Every capability in §3 is reachable from the new navigation or a documented redirect; no route 404s that worked before.
2. Password, Google, registration, verification, reset, linking, set-password and logout behave as before (existing tests unchanged and passing).
3. No protected page is reachable without a session; admin pages still require `admin`; ownership checks untouched.
4. No frontend code computes a queueing quantity; numbers on screen equal the API fields in §9 (fixture-based tests).
5. Selection, staleness and Decision prerequisites behave as before (existing evidence tests pass; new tests for "Use this plan").
6. Playback: Arrived = Waiting + In service + Completed at every step; full-day separate playback replays one execution in time order; truncation and per-period engines are labelled.
7. PDF/Excel exports and previews unchanged (report tests pass).
8. EN/TL key symmetry test passes; language dropdown works before and after sign-in.
9. All gates in `AGENTS.md` run with actual results reported.
10. Analysis results: every value belongs to the selected file; selecting a review-only or older file never changes plan, simulation or Decision inputs; recalculation is labelled.
11. Queue simulation: one start runs the whole operating day; customers, queue order, waits and unfinished services are continuous across periods (tested at period boundaries); Day summary and per-period results equal the run's output; closing rule recorded per run.
12. Counter states appear only from events; scheduled breaks are drawn separately; missing events are disclosed.
