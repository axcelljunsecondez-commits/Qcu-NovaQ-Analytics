# Shared-queue upload simplification — implementation plan

Date: 2026-10-29 (revision 2). Status: PROPOSED; application work NOT STARTED and NOT
AUTHORIZED. Implements [the specification](../specs/2026-10-29-shared-queue-upload-simplification.md)
once the owner closes its §10 decisions. Owners: backend steps = Hayato; frontend steps =
Chrome; independent review = Kyoya. One writer per file; no step starts on a file another
session has uncommitted changes in.

**Protected (do not change; reuse only):** ingestion validation
(`backend/data/analysis_ingestion.py`, `backend/data/ingestion.py`, `backend/data/uploads.py`),
setup derivation for workbooks (`backend/data/setup_derivation.py`), the shared timeline check
(`backend/queueing_engine/services/shared_segments.py`), model selection, engine/DES/MC/
optimizer, existing endpoint request/response shapes, CSRF/auth, wording records
(`docs/wording/`, `frontend/src/lib/wordingPolicy.test.ts`). If a step seems to need a change
there, STOP and raise a separate spec.

## Step 0 — Close decisions and freeze inputs (owner + parent)

- Owner answers OD-1 … OD-8 and approves or replaces the draft EN/TL strings (spec §10, mockup).
- Record the CSV hash `236fc058…938e` and HEAD; preserve all unrelated dirty/untracked work.
- Gate: decisions written into the spec; no code yet.

## Step 1 — Derivation service (Hayato, backend, new file)

Files: new `backend/data/shared_aggregate_setup.py`; new `tests/test_shared_aggregate_setup.py`.

- Input: sanitized frame + saved Setup. Calls `normalize_analysis_input` with a Setup that has
  the saved structure but no fixed-count constraint, so the file's c is validated by the same
  function (no weakened legacy rule), then `timeline_from_aggregate_rows` + `validate_timeline`.
- Accepts only the first slice (shared, aggregate 4 columns, contiguous same-day one-hour rows).
  Anything else returns `declined` with reasons, never partial output.
- Output: file facts, candidate Setup (segments `HH:MM-HH:MM`, varies from distinct c, fixed
  count only when constant), saved Setup untouched fields kept (capacity, abandonment, counter
  breaks, period basis, closure policy), unresolved choices, conflict list including counter
  breaks checked with the same rules as `_counter_breaks` (outside hours / more breaks than
  counters). If that rule lives only in `backend/api/shared_continuous.py`, extract it as a
  pure function in a separately reviewed sub-step — do not copy it.
- Tests (exact owner CSV read from disk, rows compared to independently written expectations):
  varying c; constant-c fixture; gap; overlap; overnight; `5am`; 30-minute rows; non-integer c;
  K/theta/variance columns declined (fields preserved); saved fixed count; saved finite capacity
  kept; saved counter break outside 05:00–18:00 and one needing more counters than scheduled.
- Gate: new tests pass; `python -m pytest tests/test_setup_derivation.py tests/test_uploads.py
  tests/test_upload_setup_api.py` unchanged and passing; ruff, mypy.

## Step 2 — Preview and atomic apply endpoints (Hayato, backend)

Files: `backend/api/analyses.py` (additive routes only), its schema module, new
`tests/test_shared_aggregate_setup_api.py`.

- Define request/response models in the patch before frontend work starts; send to Chrome.
- Preview: owned, not archived, upload rate limit, size limits; no Dataset/Job/Scenario write;
  returns facts, candidate, saved, diff (incl. `counter_breaks`), unresolved, conflicts,
  `setup_revision`, `file_digest`.
- Apply: planning purpose only (review → 422 like today), explicit answers, replacement intent,
  revision and file digest checked; Dataset + Setup in one commit; `setup_status` recomputed;
  today's current-dataset and staleness rules.
- Tests: no writes on preview/failure/cancel/stale revision/changed file; duplicate apply does
  not create two datasets; legacy `POST …/datasets`, `…/datasets/preview`, `apply_setup`
  responses byte-for-byte unchanged on existing fixtures; owner/archive/limits/CSRF.
- Gate: full `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`. Stop if a
  migration or protected contract change appears necessary.

## Step 3 — Presentational reorder (Chrome, frontend, no behaviour change)

Files: `frontend/src/pages/AnalysisSetupPage.tsx`, scoped CSS, page tests.

- Upload card first; template block and Manual entry as disclosures below; Advanced last.
- Hide "Customer data periods" when the current planning file is aggregate (OD-8).
- Banner: omit "Fixed server count" for a shared analysis with no planning file (OD-5); this is
  display only — server `setup_status` is unchanged.
- Gate: existing Setup tests pass unchanged (`AnalysisSetupPage`, `DataSetupSteps`,
  `DatasetPurpose`, `SetupSemantics`, `SetupChangeWorkflowCache`, `CurrentDatasetCache`), plus
  new order/visibility tests; `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`.

## Step 4 — Read, summary, missing choices, one apply (Chrome, frontend)

Files: `frontend/src/api/analyses.ts`, `frontend/src/api/types.ts`, `AnalysisSetupPage.tsx`, new
`components/setup/FileReadSummary.tsx` and `components/setup/MissingChoices.tsx`, both locale
files (owner-approved strings only), tests.

- Planning file chosen → preview (OD-3); pending via `common.loading`; stale-response guard;
  reset on file/purpose/analysis change. Review-only keeps today's button and call.
- Summary renders server facts only (no browser CSV parsing, no browser-derived values); counter
  strip as SVG from the returned per-row c; table alternative.
- Missing choices only for `unknown`; conditional number fields; "not sure" keeps `unknown`;
  optional closing rule saved via existing `PUT …/closing-policy` after apply succeeds (OD-4).
- Apply with double-submit guard; existing confirmation keys for replacement; Cancel writes
  nothing; existing cache resets (`workflow`, `scenarios`, `datasets`, `current`, `analysis`).
- Declined preview → reason + today's upload path.
- Tests: owner CSV fixture through mocked API; each case in spec §7; keyboard/focus; no
  network call on review-only read; EN/TL key symmetry test.
- Gate: all four frontend gates; locale symmetry; `wordingPolicy.test.ts` unchanged and passing.

## Step 5 — Verification on an isolated local stack (Chrome + Kyoya)

- Disposable database. New shared analysis → exact CSV → answers → apply → read-back →
  full-day run and replay. Also: saved fixed count replacement and cancel; counter-break
  conflict; review-only; finite/modeled refusal; declined file; stale revision.
- 375 / 768 / 1280 px, light/dark, EN/TL; no page overflow; screenshots saved.
- Confirm CSV hash, protected files, model selection and engine files unchanged
  (`git diff --stat` on protected paths = empty).
- Kyoya reviews the diff against this plan and the spec.

## Deliverables and stop conditions

Scoped diffs per step with actual gate output. Stop the affected step if source data would be
altered, a missing operational fact would be guessed, a protected file or contract would
change, or a gate fails without explanation. No commit, push, Docker activation or deployment
without separate owner authorization.
