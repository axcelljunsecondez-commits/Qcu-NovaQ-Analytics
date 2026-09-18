# Upload Template with Setup Derivation — Implementation Plan (2026-09-18)

Spec: `docs/superpowers/specs/2026-09-18-upload-template-setup-derivation.md`
(revised 2026-09-18: export = `staff` + `breaks`, `staff` queue order,
arrival-only shift check, segments without `staff` end after the last
arrival).

Test-first: each task writes its failing tests, runs them red, then the code,
then its tests plus the protected tests.

## Files

| File | Change |
|---|---|
| `backend/data/uploads.py` | Add `parse_upload_workbook(...)`. It returns `None` for CSV or a workbook without an `events` sheet (legacy), else `{"events", "staff", "breaks"}` frames (absent or headers-only → `None`). It reuses `_validate_xlsx_archive` once and `_validate_frame` on every sheet read. `parse_upload` is unchanged. |
| `backend/data/setup_derivation.py` | **New.** `derive_setup(sheets, saved_setup) -> DerivedSetup` (Setup, staff/break rows read, errors), `setup_diff(saved, derived)`, and `setup_workbook(setup) -> bytes` for the export. It implements every rule and exact message in spec §Derived Setup and §Validation. |
| `backend/data/templates.py` | The separate-events XLSX becomes `events` / `staff` / `breaks` / `Example` / `Field Guide`. Staff and break fields use a separate guide list, so shared and aggregate guides and templates are unchanged. The CSV template is unchanged. |
| `backend/api/analysis_schemas.py` | `QueueBreak.break_name: str \| None = Field(default=None, max_length=50)`. |
| `backend/api/analyses.py` | `POST /{id}/datasets/preview`. `apply_setup: bool = False` query param on `POST /{id}/datasets`: when true, derive on the server, dry-run normalize, save Setup and dataset in one commit. `GET /{id}/setup/workbook`. The path without `apply_setup` is untouched. |
| `backend/api/templates.py` | No change expected. The download route already serves `template_workbook`. Listed only in case the filename or media type needs it. |
| `backend/api/datasets.py`, `frontend/src/pages/DatasetsPage.tsx` | **No change.** `/datasets` uploads go through aggregate-only `validate_and_normalize` (`datasets.py:92`) into a `legacy` analysis. The spec's flow is the analysis upload. |
| `frontend/src/api/types.ts` | `QueueBreak.break_name?: string \| null`, plus preview response types. |
| `frontend/src/api/analyses.ts` | `previewAnalysisDataset`. `uploadAnalysisDataset(id, file, { applySetup })`. `downloadSetupWorkbook` uses the blob pattern of `downloadTemplate` (`api/templates.ts:35-45`). |
| `frontend/src/pages/AnalysisSetupPage.tsx` | The upload card calls preview for `.xlsx`. For `legacy`, it uploads as today. For `multi_sheet`, it shows errors, or the "what NovaQ read" summary; it applies directly when `needs_confirmation` is false, otherwise it shows the diff and a Confirm button. A "Download setup workbook" button appears for separate queues. CSV is unchanged. |
| `frontend/src/components/analysis/BreakEditor.tsx` | Shows each break's label (`break_name`, or "Break n" by time per queue) and keeps `break_name` on edits. No new name input. |
| `tests/fixtures/novamart_events.csv` | **New, small.** 1,600 NovaMart events stored as `day,arrival,start,end,queue` in whole minutes, generated once from the Downloads file. The tests rebuild full timestamps (2000-01-03 + day) and the three-sheet workbook in memory. |
| `tests/test_setup_derivation.py`, `tests/test_upload_setup_api.py` | **New.** |

Untouched: queueing engine, DES, optimizer (including the uncommitted break
optimizer), reports, migrations, `analysis_ingestion.py`, `.env`, lock files.

## Tests

**`tests/test_setup_derivation.py`** (pure):

1. **NovaMart:** fixture + 5 staff rows + 15 breaks derive:
   - `separate_queues`
   - `queue_ids` = `cashier_1..5` (in `staff` order, although events start
     with `cashier_2`)
   - 13 segments `05:00-06:00` … `17:00-18:00` with the specified active sets
   - `staffing_varies_by_period` true, `fixed_server_count` null,
     `representative_day`
   - 15 breaks, `break_name` null
   - `unlimited`, `not_modeled`
   - no errors

   The result equals the Setup from `setup_to_enter`, restated in the test.
2. Without `staff`: first appearance order, fixed staffing,
   `fixed_server_count` = queue count, `active_queue_ids` null. Segments end
   at the next full hour after the last arrival (17:59 → 18:00). Headers-only
   `staff`/`breaks` = absent.
3. A non-hour shift boundary (for example 06:30) adds a boundary.
4. One-date events → `per_date`.
5. Saved `capacity_mode`/`abandonment_mode` (and their values) are kept.
   Unknown → `unlimited`/`not_modeled`.
6. **Validation:** one test per message in spec §Validation, asserting the
   exact string. Multiple errors are returned together. No rows are dropped:
   the break and staff counts in the output equal the rows read.
7. Arrival-only shift check: a service that ends after the shift is
   accepted; a late arrival gives `{n} events for {queue} arrive outside its
   shift …`.
8. **Export round-trip:**
   - `setup_workbook(derived)` gives sheets `staff` and `breaks` only.
   - Original events + export → identical Setup, both with `staff`
     (NovaMart) and without `staff` (headers-only export).
   - The split-shift export error is exact.
9. `setup_diff` lists only the changed fields.
10. **Upload limits per sheet:** oversized row, column or cell counts on the
    `staff` or `breaks` sheet are rejected with the existing `UploadError`
    messages. The worksheet-count limit still applies.

**`tests/test_upload_setup_api.py`** (API):

1. **Preview:** returns `multi_sheet`, the derived Setup and the diff. It
   stores nothing: no dataset, Setup unchanged.
2. **New/unknown analysis:** `apply_setup=true` saves the derived Setup and
   the dataset in one commit. The dataset is normalized with the derived
   Setup (representative-day records present).
3. **Saved different Setup:**
   - preview gives `needs_confirmation` true, Setup unchanged
   - upload without `apply_setup` leaves Setup unchanged and behaves as
     today (the first sheet is read)
   - upload with `apply_setup` replaces the Setup
4. `apply_setup` with a legacy file → 422, exact message. Derivation errors
   → 422, and nothing is stored.
5. A legacy workbook (`Data Entry` first) and a CSV return `mode: legacy` on
   preview and upload exactly as before.
6. **Export endpoint:** a workbook with `staff`/`breaks`; a shared analysis →
   422 with the exact message. Auth and ownership are enforced (404 for
   another user).
7. The `QueueBreak.break_name` round-trips through PATCH/GET. Old Setups
   without it validate. More than 50 characters → 422.

**Template (existing `tests/test_templates.py` unchanged, new test added
there):** the separate-events XLSX sheet names are `events`, `staff`,
`breaks`, `Example`, `Field Guide`. The shared-events workbook is still
`Data Entry`, `Example`, `Field Guide`.

**Frontend:** preview → summary; confirm flow; legacy path unchanged; export
button; the BreakEditor label. Location: see Needs approval.

**Protected (run after each backend task):** `tests/test_uploads.py`,
`tests/test_templates.py`, `tests/test_analyses_api.py`,
`tests/test_analysis_api.py`, `tests/test_datasets_api.py`,
`tests/test_representative_day.py`, `tests/test_queue_breaks.py`.

## Order

1. Fixture: generate `tests/fixtures/novamart_events.csv` once from
   Downloads. Verify 1,600 rows and that it round-trips to the source
   timestamps.
2. `QueueBreak.break_name` (API test 7).
3. `parse_upload_workbook` (derivation test 10 and the reading cases).
4. `setup_derivation.derive_setup` + `setup_diff` (derivation tests 1–7, 9).
5. `setup_workbook` export (derivation test 8).
6. Endpoints: preview, `apply_setup`, export (API tests 1–6).
7. Template workbook (template test).
8. Frontend: types/client, BreakEditor, AnalysisSetupPage, tests, locale
   keys.
9. Gates: `python -m pytest tests/ -x --tb=short`, `ruff check .`,
   `mypy .`; in `frontend/`: `npm test`, `npm run typecheck`,
   `npm run lint`, `npm run build`.
   - `-x` stops at the known
     `test_parallel_des_long_stable_case_matches_pollaczek_khinchine`, so the
     suite also runs with only that test deselected. Both outputs are quoted.

## Needs approval (outside the listed Scope)

1. **Locale keys:** new UI strings for the preview summary, confirm, export
   button and break label go into both
   `frontend/public/locales/en/translation.json` and `tl/translation.json`
   (add only, symmetric), as AGENTS.md requires.
2. **Frontend test file:** a new `frontend/src/pages/AnalysisSetupPage.test.tsx`.
   The alternative is adding cases to the existing
   `frontend/src/pages/SetupSemantics.test.tsx`, which already renders
   AnalysisSetupPage. Either one is outside the listed Scope.

## Notes

- **Export path:** I set it to `GET /analyses/{id}/setup/workbook` in the
  spec because the export no longer uses any dataset. If you prefer the
  original `/datasets/{dataset_id}/workbook` path, I will keep it and only
  check that the dataset belongs to the analysis.
- **Mixed-version edge case:** a three-sheet file uploaded without
  `apply_setup` (for example by an old client) reads only the first sheet,
  exactly as today. In the new template that sheet is `events`.
