# B8: Reports — PDF summary and Excel "check the math" workbook

**Status:** APPROVED by the owner on 2026-10-09 (OD-UX-12 = A all closed forms, OD-UX-14 = A helper columns, OD-B8-3 = A add optimizer candidates, OD-B8-4 = A Python re-computation plus one manual Excel check). Report content is a protected export: implementation is plan step 15 and needs the owner's GO for that step.
**Parent spec:** `docs/superpowers/specs/2026-10-09-compact-workflow-ux-redesign.md` (D13, D31, D32, D33, backend item B8, open decisions OD-UX-12 and OD-UX-14). Target design: `docs/superpowers/specs/assets/2026-10-09-reports-page.html` (accepted by the owner, D33).
**Plan:** step 6 (this spec), step 15 (implementation).
**Evidence labels:** VERIFIED (read in code at `ef05827e`, cited), REPORTED, PROPOSED, UNKNOWN, NOT TESTED.

## 1. Goal

Two report levels with one layout for both line types (D31, D32):

- **Plan report** (level 1), available once a current, verified plan is selected: cover with "Calculated result · not yet checked by simulation", key results now vs plan, period table with break times, charts each with its table. No Decision words.
- **Full report** (level 2), available when the existing Decision gate allows export: everything in the plan report plus the Decision page in plain words, simulation key results (four headline numbers and two charts), the checks summary (one line per check with its settings) and "What is not included".

Each level comes as a **PDF** for managers and supervisors (plain words, no ρ or Wq symbols) and an **Excel "check the math" workbook** for technical review. The Reports page shows a preview generated from the same report model. The existing data-only report stays.

## 2. What exists (VERIFIED)

| Fact | Evidence |
|---|---|
| Report routes: selected-plan preview and file, dataset report, scenario report. | `backend/api/reports.py:429, 442, 577, 590` |
| The shared scenario report generates without a Decision; the separate-lines report needs the full chain (selected DES, Monte Carlo, validation, Decision), each current. | `backend/api/reports.py:156-233, 591-605` |
| The frontend blocks the shared report until a Decision exists. | `frontend/src/pages/ReportsPage.tsx:426-434` |
| PDFs use ReportLab and workbooks use openpyxl; every Excel cell today is a typed value, with no formulas. | `backend/reports/report_export.py:11-25, 337-560, 809-989` |
| Today's shared PDF and Excel have no simulation content. | `report_export.py:611-989` |
| Analytical models and their formula type: M/M/1, M/G/1 (exact Pollaczek–Khinchine), M/M/c (Erlang C) and M/G/c (Allen–Cunneen scaling of the M/M/c wait) are closed forms; M/M/c/K and M/G/c/K are finite sums over K+1 states; Erlang-A sums in log space over up to 100,000 states. | `backend/queueing_engine/models/queue_models.py:52, 87-142, 143, 198-205, 262-331, 332-338, 491-499` |
| The optimizer tries every counter count from the minimum to the maximum and returns only the chosen one with an explanation; the candidates are not in its output. | `backend/queueing_engine/services/optimization.py:336-356` |
| No Excel formula evaluator is available in the project or on this machine (no `formulas` package, no LibreOffice). | `requirements*`, `pyproject.toml`; checked 2026-10-09 |
| The Erlang C step formulas in the mockup's Formula check sheet were checked in Python against NovaQ's `mmc` (difference 6.7e-15 min) but never opened in Excel. | REPORTED (`handoff.md`, compact-redesign section) |

## 3. Report model (PROPOSED)

One server-side function builds a **report model** (plain data) for an analysis and level. The PDF, the Excel workbook and the page preview are all rendered from that model, so they cannot disagree. New routes, additive; existing report routes keep their behaviour:

- `GET /analyses/{id}/reports/plan/preview` → model JSON; `GET …/reports/plan.pdf`, `…/reports/plan.xlsx`.
- `GET /analyses/{id}/reports/full/preview`, `…/full.pdf`, `…/full.xlsx` (refused with the existing gate reason until the Decision gate allows export).
- The cover states the level; parts that do not apply to the line type say why (one layout for both, D32).

## 4. Excel workbook (PROPOSED)

Sheets: Overview · Your data · Plan · Formula check · Plan search (OD-B8-3) · Simulation (full report) · Checks (full report) · Decision (full report) · Assumptions · Provenance.

**Formula check** sheet: one row per period with the inputs as values and the model's results as **live Excel formulas** where Excel can reproduce the model, next to NovaQ's own value and a difference column. Models without a live formula show NovaQ's values and the intermediate steps, marked "formula not available in Excel".

## 5. Decisions for the owner

### OD-UX-12: which models get live Excel formulas

| Option | Models with live formulas |
|---|---|
| **A. Every closed form (recommended)** | M/M/1, M/G/1, M/M/c, M/G/c. M/M/c/K, M/G/c/K and Erlang-A show values and steps. |
| B. As in the mockup | M/M/1 and M/M/c only. |
| C. Closed forms plus finite-capacity sums | A plus M/M/c/K and M/G/c/K (one row per state up to K; large K makes very long sheets). |

### OD-UX-14: older Excel versions

| Option | What it means |
|---|---|
| **A. Helper columns, no `SEQUENCE()` (recommended)** | The Erlang C sum is written with one helper cell per term (n = 0 to c−1). Works in every Excel version and in LibreOffice and Google Sheets. |
| B. `SEQUENCE()` | Shorter formulas, but needs Excel 2021 or Microsoft 365. |

### OD-B8-3: Plan search sheet (every counter count the optimizer tried)

| Option | What it means |
|---|---|
| **A. Add the candidates to the optimizer output (recommended)** | Additive field on `/optimize/batch` results: each counter count tried, its modeled cost and which limit it failed. A protected contract gains a field; nothing existing changes. |
| B. Leave the sheet out | The workbook explains the chosen count only. |

### OD-B8-4: how the Excel formulas are verified

| Option | What it means |
|---|---|
| **A. Python re-computation plus one manual Excel check (recommended)** | Tests rebuild each formula's steps in Python from the cell contents and compare with NovaQ's values; the owner opens one generated workbook in Excel once and records the result. Until that check, the formulas are labelled NOT TESTED in Excel. |
| B. Add a formula-evaluation tool to the tests | For example the `formulas` Python package or LibreOffice in CI. Needs its own check that the tool computes like Excel. |

## 6. Tests (PROPOSED; written before the code)

1. The preview, the PDF and the workbook are produced from the same model (model equality in tests; PDF text and sheet values match the model).
2. Levels: plan report available exactly when a current verified plan is selected; full report exactly when today's gate allows; the cover states the level; level 1 contains no Decision words.
3. Separate lines get a plan report without the full chain (new); the full separate report keeps today's chain checks.
4. Every live formula: Python re-computation from the cell formula equals NovaQ's value within 1e-9 for each reference case (stable, near-saturated, c = 1, large c).
5. Unstable periods: formulas return a clear "Unstable" text, never a number.
6. Existing report routes and their tests unchanged.
7. Data-only report unchanged.
8. Mutation testing of the level gate and the formula builder.

## 7. Risks

- Report content is a protected export; parity tests guard it.
- Long workbooks for many periods; sheet sizes to be measured (NOT TESTED).
- Excel behaviour is verified only as described in OD-B8-4.

## 8. Acceptance

Owner answers (2026-10-09, in chat): OD-UX-12 = **A** (M/M/1, M/G/1, M/M/c, M/G/c live); OD-UX-14 = **A** (helper columns, no `SEQUENCE()`); OD-B8-3 = **A** (additive `candidates` on optimizer results); OD-B8-4 = **A** (Python re-computation in tests; formulas labelled NOT TESTED in Excel until the owner's one-time check is recorded). Implementation is plan step 15, after U6 (Analysis results) and B10.
