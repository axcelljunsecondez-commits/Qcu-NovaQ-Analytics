# B10: Planning file vs review-only file

**Status:** APPROVED by the owner on 2026-10-09 (OD-B10-1 = A new column, OD-B10-2 = A fixed at upload, OD-B10-3 = planning screens refuse review files). Docs only: implementation is plan step 7 and starts only after the owner's GO for that step. No migration is run and nothing is deployed by this document.
**Parent spec:** `docs/superpowers/specs/2026-10-09-compact-workflow-ux-redesign.md` (decision D16, backend item B10, open decision OD-UX-10).
**Plan:** `docs/superpowers/plans/2026-10-09-compact-workflow-ux-redesign-plan.md` step 6 (this spec) and step 7 (implementation).
**Evidence labels:** VERIFIED (read in code at `ef05827e` on 2026-10-09, cited), PROPOSED (this spec's design), UNKNOWN, NOT TESTED.

## 1. Goal

When someone uploads a file, they choose what it is for (D16):

- **Use for planning**: the file becomes the data for plans, simulations, checks, Decision and reports. This is what every upload does today.
- **Review only**: the file can be looked at in Analysis results (B3), but it never becomes the plan's data. Uploading it must not make existing plans, simulations or checks stale.

## 2. What happens today (VERIFIED)

| Fact | Evidence |
|---|---|
| One rule decides the current dataset: among the analysis's datasets owned by the user, the highest id whose validation report has a truthy `ok`. | `backend/api/current_dataset.py:1-16, 49-61` |
| Every server path that needs "the plan's data" calls that resolver: current results, workflow dataset, evidence currentness. | `backend/api/analyses.py:350`; `backend/api/workflow.py:571-573` (used by DES, MC, validation, Decision and break apply at `:1807`); `backend/api/workflow.py:862-866` (evidence context) |
| Evidence and saved plans are current only while their recorded dataset is the current dataset. | `backend/api/evidence_status.py:413-417` |
| So any successful upload today replaces the plan's data and makes earlier evidence and saved plans stale. | follows from the three rows above |
| The named shared run takes an explicitly chosen dataset and only checks that it was processed successfully. It never uses the "current" rule. | `backend/api/shared_named.py:301-308` |
| Datasets have no field that says what they are for. Only `generation` is protected from updates by database guards; other columns can be updated. | `backend/db/models.py:142-165`; `backend/db/generation_guards.py:64-69` (SQLite), `:84` (PostgreSQL) |
| The frontend assumes the newest dataset is the current one when it keys cached results (`datasets[0].id`), and computes "latest valid dataset" itself for break apply. | `frontend/src/pages/AnalysisSetupPage.tsx:63`; `frontend/src/pages/AnalysisCurrentPage.tsx:81-82`; `frontend/src/pages/OptimizePage.tsx` (`latestValidDatasetId`) |
| The resolver's behaviour is pinned by `tests/test_current_dataset.py` (cases 1–10) and used by the D7, evidence and currentness test modules. | `tests/test_current_dataset.py`; `tests/test_d7_current_evidence_dataset.py`; `tests/test_evidence_status.py`; `tests/test_step4_schema1_dataset_currentness.py`; `tests/test_scenario_evidence_status.py`; `tests/test_generation_job_stamping.py` |

## 3. Proposed rule (PROPOSED)

> The current dataset of an analysis is, among the analysis's datasets owned by the user that were uploaded **for planning**, the one with the highest id whose validation report has a truthy `ok`.

Consequences:

- A review-only file is never current, so it never changes evidence currentness. Existing plans, simulations and checks stay current after a review-only upload.
- Every dataset that exists today counts as **for planning** (legacy default), so the current dataset of every existing analysis stays exactly the same. All existing resolver tests must pass unchanged.
- An analysis that has only review-only files has no current dataset. The resolver reports a new status `no_planning_dataset`, distinct from `no_dataset` and `no_valid_dataset`, so the screen can say "You have only review files. Upload a file for planning to make plans." (Additive enum value; today's callers read only `.dataset` / `.dataset_id`, VERIFIED at the three call sites above.)

## 4. Decisions for the owner

### OD-B10-1 (= OD-UX-10): where the purpose is stored

| Option | What it means | For | Against |
|---|---|---|---|
| **A. New column (recommended)** | `datasets.purpose` text, not null, default `'planning'`, allowed values `'planning'` and `'review'`, added by migration 0006. | Explicit and constrained in the database; the resolver filters in SQL; easy to audit. | Needs a database migration. In production that is a manual, planned step: the Render start command no longer runs migrations, and the production schema guard refuses to start the app when the database is not at the code's migration head (REPORTED in `memory.md`, G8 runbook; guard VERIFIED at `backend/api/main.py:219-243`). |
| B. Field inside `validation_report_json` | `{"ok": true, ..., "purpose": "review"}`; absent means planning. | No migration. | Mixes "what the file is for" into "was the file read correctly"; no database constraint; every reader must remember the default. |

### OD-B10-2: can the purpose change after upload?

| Option | What it means |
|---|---|
| **A. Fixed at upload (recommended for the first version)** | To plan with a review file, upload it again as "for planning". Simple and predictable, and it keeps the "highest id" rule meaningful. |
| B. Changeable later | Needs a rule for which planning file wins (highest id would let an old file switched to planning stay hidden behind a newer one, which is confusing) and an audit of the change. Larger scope. |

### OD-B10-3: what other screens do with a review-only file

| Place | Recommendation |
|---|---|
| Suggested plans (optimizer dataset picker) | Offer only planning files. Today a plan saved from a non-current file is already not selectable (evidence not current), so offering review files there only creates plans that cannot be used. |
| Named shared run (explicit dataset) | Refuse review-only files with a clear message (`dataset_not_for_planning`), because named runs are planning work. |
| Setup-changing upload (`apply_setup=true`) | Refuse together with "review only": a review file must never change the Setup. |
| Analysis results (B3) | Any successfully processed file, planning or review, can be viewed read-only (already decided in D15). |
| Uploaded files list | Show the purpose and which file is the current planning file. |

## 5. API changes (PROPOSED, additive)

- `POST /analyses/{id}/datasets` gets an optional query parameter `purpose` with values `planning` (default) and `review`. Omitted means planning, so today's clients behave exactly as now.
  - `purpose=review` with `apply_setup=true` → 422 `review_cannot_change_setup`.
- `POST /analyses/{id}/datasets/preview` is unchanged (it never stores anything).
- Dataset responses (`dataset_out`) gain `purpose` and `is_current` (computed with the resolver), so the frontend stops guessing from list order.
- `GET /analyses/{id}/current` keeps its shape; when the analysis has only review files it reports the new status (exact error shape to match today's `no_valid_dataset` handling; to confirm in implementation).
- Named run endpoints refuse a review-only dataset (OD-B10-3).
- The global `/datasets` upload (files not attached to an analysis) is unchanged; those files belong to no analysis (`current_dataset.py:10`).

## 6. Frontend changes (PROPOSED)

- Data and setup, step 2: the question "This file is for: Use for planning / Review only", with no preselected answer, shown before upload. The existing limitation sentence is replaced by a description of each choice.
- Cache handling after upload:
  - for planning: today's resets (`['workflow', id]`, `['scenarios', id]`, `['current', id]`, `['datasets', id]`);
  - review only: refresh `['datasets', id]` only. Workflow evidence and saved plans stay as they are, because they stay current.
- Replace `datasets[0].id` keys with the dataset whose `is_current` is true (`AnalysisSetupPage.tsx:63`, `AnalysisCurrentPage.tsx:81`).
- Break apply: "latest valid dataset" becomes the current planning dataset (`is_current`), matching the server's check at `workflow.py:1807`.
- Suggested plans: the dataset picker lists planning files only (OD-B10-3).
- Settings → Uploaded files: show the purpose and mark the current planning file.

## 7. Tests (PROPOSED; all must be written before the code that makes them pass)

Backend:

1. Every case in `tests/test_current_dataset.py` passes unchanged (legacy rows are planning).
2. A newer valid review file does not replace the current planning file.
3. A newer valid planning file still replaces it (today's behaviour).
4. Only review files → status `no_planning_dataset`, no dataset.
5. Deleting the current planning file falls back to the next planning file, never to a review file.
6. Evidence recorded on the planning file stays current after a review upload (evidence status module), and becomes stale after a planning upload (unchanged).
7. Upload API: omitted `purpose` stores planning; `purpose=review` stores review; unknown value → 422; `review` + `apply_setup` → 422 and nothing stored.
8. Named run refuses a review file.
9. `dataset_out` reports `purpose` and `is_current` correctly, including after deletions.
10. Migration 0006 (if OD-B10-1 = A): upgrade sets every existing row to planning; downgrade removes the column; the generation guards and registry are untouched (re-run the 0005 guard tests); PostgreSQL gate run as for G1–G7.

Frontend:

11. The upload question has no preselected answer and the upload is blocked until one is chosen.
12. A review upload refreshes only the datasets list; a planning upload performs today's resets (extend `CurrentDatasetCache.test.tsx`).
13. Cached results follow `is_current`, not list order.
14. The optimizer picker lists only planning files; break apply follows `is_current`.

## 8. Risks

- **Protected rule:** this changes the one rule every evidence check depends on. Mitigation: legacy default, unchanged existing tests, new tests 2–6, and mutation testing of the resolver filter.
- **Production migration (option A):** must be run deliberately before the new code starts, per the G8 runbook. No deploy is part of this work.
- **Two writers:** the D7 and evidence modules were built in other worktrees (`memory.md`: G-A milestone). Implementation must start from a fresh `origin/main` and check that no other open branch changes `current_dataset.py`.

## 9. Out of scope

Comparing two files (later, own spec); changing a file's purpose after upload (unless OD-B10-2 = B); B3 itself (reading any file's results), B11 and B12, which are separate step-7 items.

## 10. Acceptance

Owner answers (2026-10-09, in chat): OD-B10-1 = **A, new `purpose` column** (migration 0006); OD-B10-2 = **A, fixed at upload**; OD-B10-3 = **planning screens refuse review-only files** as listed in §4. After that, implementation is plan step 7 (B10 first), on a branch from a fresh `origin/main`, with the gates in the plan and a phase report before commit.
