# Shared-queue CSV upload simplification — implementation record

Date: 2026-10-30. Implementation: COMPLETE LOCALLY. Verification: PARTIAL at
repository scope because the required whole-folder Ruff/mypy commands fail on
pre-existing output artifacts. The application suites, source checks, build and
isolated browser acceptance passed. No commit, push or deployment was performed
during this implementation verification. Follow-on owner-authorized commit and
the blocked local Docker rebuild are recorded in the
[Docker report](2026-10-30-shared-upload-docker-activation.md).

## Authorization and source identity

The owner approved OD-1 through OD-8 on 2026-10-29 and authorized Chrome and Hayato
to implement on 2026-10-30: "chrome and hayato you can do this?". This supersedes
the plan's old unapproved header. OD-6 still reserves final review of new EN/TL
wording; existing approved wording will be reused where possible.

On 2026-10-30 the owner separately reviewed and approved the exact EN/TL D4, D8
and D9 messages ("Approve these three messages"). Their exact text is recorded in
the specification. Other mockup drafts remain unapplied; no wording registry/test
changes are authorized.

Checkout: C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ.
Branch: codex/shared-queue-workflow-20261029. Starting HEAD:
2e0e360666b2b4302faaddeb955f63e64395aab1. Tracked working tree was clean.
Existing untracked .claude/launch.json, .playwright-cli/ and output/ are preserved.

Baseline: output/shared-upload-simplification-20261030/baseline.json records all
990 tracked file hashes and 45 specifically protected paths. Owner input:
Avg_total_data_of_14_days.csv, SHA256
236fc05861b4a59ce3216c41fb52b3c529aec6b6f57003f610bd4cc3a91f938e.
The input is unchanged. It contains rates and counts per hourly period; the
filename does not independently verify averaging dates or underlying observations.
The portable test fixture `tests/fixtures/shared_aggregate_owner.csv` is a byte-for-byte
copy with the same SHA256, so acceptance tests do not require the owner's C: drive.
Its 13 rows cover 05:00–18:00; c is 3,5,5,5,5,5,2,3,5,5,5,5,2. Lambda and mu retain
the application's per-hour convention. No raw observations or dates are inferred.

## Ownership

- Hayato: new shared aggregate derivation service, additive preview/apply routes
  and schemas, minimal analyses-router wiring, corresponding backend tests.
- Chrome: Data and Setup flow, new summary/missing-choice views, frontend API
  types/client, scoped styles and associated frontend regressions.
- Parent: authorization/spec/plan record, contract/protected-boundary review,
  integration and isolated real-browser verification, final report.

No changes to protected ingestion, workbook derivation, queueing/statistical
methods, existing endpoint contracts, auth, schema, source CSV or operational
data are authorized by this task. Any necessary shared-rule extraction must be
documented and reviewed before editing. No deployment, push or Docker activation.

Parent boundary review (2026-10-30): the existing `_counter_breaks` validator can
be called directly; no extraction or copied rule is required. A bounded additive
`shared_aggregate_apply` dictionary in the Dataset's existing validation JSON is
approved for retry identity at creation only (file digest, original Setup revision,
versioned request fingerprint). No schema or old-upload behavior change is required.
Tests must establish duplicate/concurrency behavior; any unavailable PostgreSQL
concurrency verification remains explicitly NOT TESTED.
An additional derived `applied_setup_digest` in that metadata is approved to refuse
retries after the saved Setup changes. The exact-path foundation-adapter allowlist
in `tests/test_shared_segments.py` may add only this new derivation service; its
full scan and exclusion of legacy consumers are retained. These reviewed extensions
implement the approved additive path without changing mathematical expectations.

## Actual changes and observed outcome

VERIFIED: selecting a supported shared-queue planning CSV now automatically reads
its periods, rates and counter counts on the server. One summary shows those
facts and the proposed Setup. The page asks only for unknown operational choices;
it does not invent waiting-room limits, abandonment or a closing policy. Existing
known choices are reused. Explicit unknown answers can be saved, while the full-day
run remains unavailable when required or supported choices are unresolved.

The first upload into an unconfigured analysis needs no replacement dialog.
Replacing configured Setup or an existing planning dataset requires confirmation.
The dialog lists actual Setup differences; a dataset-only replacement uses the
existing planning-file warning without claiming that Setup changes. Cancel writes
nothing. Review-only files retain the existing upload path. Templates, manual entry
and Advanced settings remain available behind collapsed controls.

Backend files:

- `backend/data/shared_aggregate_setup.py`: new bounded derivation adapter reusing
  the existing normalizer, shared timeline and counter-break rules. It accepts the
  four-column, same-day contiguous hourly slice only. Saved capacity, abandonment,
  period basis and breaks are preserved; conflicts prevent Apply.
- `backend/api/shared_aggregate_schemas.py` and `shared_aggregate_upload.py`: new
  preview/apply endpoints under `/analyses/{id}/datasets/shared-aggregate/`.
  Preview is read-only. Apply validates file digest, current Setup revision,
  replacement confirmation and answers, then stores Dataset and Setup atomically.
  A still-current identical retry returns its existing Dataset. Row locking and
  timestamp comparison guard concurrent writes. Additional XLSX sheets decline
  this narrow path so they cannot be silently discarded.
- `backend/api/analyses.py`: additive import and router inclusion only.
- New `tests/test_shared_aggregate_setup.py` and
  `tests/test_shared_aggregate_setup_api.py`, the portable CSV fixture, and the
  exact adapter allowlist addition in `tests/test_shared_segments.py`.

Frontend files:

- `frontend/src/pages/AnalysisSetupPage.tsx`: upload-first shared flow, automatic
  preview, readable replacement confirmation, stale-file/purpose/analysis guards,
  duplicate-submit protection, and read-only refresh after a revision conflict.
  Closing is saved separately using the existing endpoint after Dataset/Setup
  succeeds. A closing failure retains that successful save and allows a
  closing-only retry. Pending/error closing reads cannot overwrite saved policy.
- New `frontend/src/components/setup/FileReadSummary.tsx`, `MissingChoices.tsx`,
  `frontend/src/lib/sharedAggregateSetup.ts` and
  `frontend/src/styles/sharedFileSetup.css`; additive API client/types in
  `frontend/src/api/analyses.ts` and `types.ts`.
- New `frontend/src/pages/SharedAggregateUpload.test.tsx` (28 cases) and scoped
  regressions in AnalysisSetupPage, CurrentDatasetCache, DataSetupSteps,
  DatasetPurpose, SetupChangeWorkflowCache and SetupSemantics tests.
- Exactly the three separately approved new locale keys in EN and TL. Existing
  locale values and the protected wording registry/tests are unchanged.

Task/review records under `.claude/agent-memory/hayato/` and `kyoya/`, this report,
and the approved spec/plan were updated. Local diagnostic evidence is retained
under `output/shared-upload-simplification-20261030/`. Existing unrelated artifacts
were not removed or staged.

## Executed verification

All log paths below are relative to that evidence folder. These are actual
executed results, not expected counts.

| Gate | Actual result | Evidence |
| --- | --- | --- |
| `python -m pytest tests/ -x --tb=short` | PASS: 3,331 passed, 125 skipped, 1 existing xfailed, 9 subtests; 2,108.33 s | `hayato/backend-full-final.log` |
| Focused backend derivation/API/foundation/workbook/upload regression set | PASS: 153 passed; 38.90 s | `hayato/focused-final.log` |
| `ruff check backend tests` | PASS | `hayato/ruff-final.log` |
| `mypy backend tests` | PASS: 235 source files | `hayato/mypy-final.log` |
| Required `ruff check .` | FAIL: 1,304 diagnostics in 164 existing output paths; no application-source diagnostics in that run | `hayato/ruff-root.json`, `ruff-root-summary.json` |
| Required `mypy .` | FAIL: duplicate backend module under old `output/decision-scope-implementation-20261023/original/` | `hayato/mypy-root.log` |
| `npm test -- --maxWorkers=2` on final frozen source | PASS: 805 tests across 92 files; 396.41 s; exit 0 | `chrome/frontend-complete.log` |
| `npm run typecheck` | PASS | `chrome/typecheck-complete.log` |
| `npm run lint` | PASS | `chrome/lint-complete.log` |
| `npm run build` | PASS | `chrome/build-complete.log` |
| Protected/input/locale/diff checks | PASS: 45 protected hashes unchanged, original/fixture CSV hashes match, all previous locale values unchanged, exactly 3 symmetric new keys, no staged files, `git diff --check` passes | `preservation-final.json`, `verify_preservation.py` |

Existing nonfatal warnings were retained: Starlette/AnyIO deprecation, the test
DOM's unavailable Canvas context, a Vite chunk-size warning and plugin timing
notice. No dependency, timeout, lint configuration or mathematical expectation
was weakened to hide these outcomes.

Earlier attempts remain visible in the logs: a backend full run was cancelled at
17% before the multi-sheet correction and replaced by the completed final run.
An initial frontend focused run had 51 passes and two worker-startup failures;
another had an incorrect test label selector. Those selectors were corrected to
the actual approved labels. Earlier 803/804 full passes predate the final display
changes; only the 805-test final run is the final-source full frontend gate.

## Independent review and integration evidence

Kyoya's findings-only source review is recorded in
`.claude/agent-memory/kyoya/reviews/2026-10-30-shared-upload.md` with source hashes.
K-UP-1 (a pending/failed closing read could permit a stale draft write) was fixed
and regression-tested. The final review found no supported open source finding.
The reviewer inspected evidence; browser actions and full-suite execution were
parent-owned, not independently repeated by the reviewer.

`integration-probe.json` records a fresh isolated SQLite run using the exact owner
CSV: read-only preview, atomic apply, idempotent retry, Current read-back, explicit
closing choice, a full-day run and all five saved execution playbacks. The
replication results, period utilization and summary exactly match the earlier
owner-CSV diagnostic baseline with the same parameters. This is a regression
comparison, not independent proof of all queueing mathematics.

These five executions are the existing internal simulation methodology, not five
days of observations or a new repetition control. The probe explicitly chose
unlimited capacity, no modeled abandonment, DRAIN and seed 42 as diagnostic
parameters. The CSV does not establish those operational facts.

`staleness-probe.json` records a genuine optimization/saved-scenario diagnostic
followed by replacement of its planning dataset: the saved scenario becomes
`STALE_DATASET`, the historical run is marked not current, and its stored result
remains exactly unchanged. Existing optimization defaults were explicitly used as
diagnostic inputs; no observed operating costs are claimed.

## Actual built-browser acceptance

VERIFIED in the in-app browser against the built SPA and a loopback-only server
at `http://127.0.0.1:18768`, with the task's isolated SQLite database:

- The original CSV automatically showed 13 rows, 05:00–18:00, counters 2–5,
  hourly arrival/service rates and the per-period table without retyping them.
  The first save succeeded and led to results/full-day actions.
- A saved fixed count of 3 did not incorrectly reject the varying-count CSV.
  Cancel preserved the old Setup and created no Dataset; Confirm applied all
  13 periods. `browser-cancel.json` records the cancelled state.
- Review-only to Planning with the same selected File re-read it and reused
  known saved answers. The final built dataset-only confirmation showed the
  correct planning-file warning and keyboard Cancel returned without saving.
- Saved finite capacity 20 and normalized K=20 were preserved. Decide later
  left closing unknown, no run job was created and the unsupported full-day
  run remained disabled. A saved 04:15 counter break conflicting with 05:00
  opening blocked Apply and remained unchanged.
- A deliberately removed hourly row and a workbook with an explicitly synthetic
  extra worksheet declined automatic Setup, with the existing upload fallback.
  Neither created a partial Dataset or changed the conflicting Setup.
  `browser-refusals.json` records the corresponding DB assertions.
- The browser completed a full-day run for the supported diagnostic Setup and
  opened saved visual replay. At 11:31 the replay displayed the real saved
  customer identities and counts (62 arrived, 58 served, 2 waiting, 2 serving,
  0 unserved), matching the diagnostic trace.
- English/Filipino, light/dark and 375/768/1280 viewport checks were inspected.
  No whole-page horizontal overflow was measured; the expanded period table
  has its own scroll region. The viewport override and language/theme were
  restored to default sizing, English and light before handoff. Final browser
  error-log queries for both retained preview tabs returned empty arrays.

The task's upload-summary and replay tabs are retained for local review. UI
screenshots were inspected inline. No screenshot artifact path is claimed: the
available capture returned image bytes inline without a documented file-save
path. Browser stale-response/deferred-read edge cases were executed in regression
tests rather than repeated through a live two-tab browser race.

Commit preflight, owner request on 2026-10-30: the first staged diff check also
covered newly added files and found one extra blank line at the end of
`MissingChoices.tsx`. Only that empty line was removed. Kyoya verified that adding
exactly one LF recreates the tested file hash, recorded the new hash, and found
no semantic change. The 805-test suite predates this whitespace-only cleanup;
the Docker build performs fresh type/lint/build checks on committed content.

## Remaining limits and scope status

NOT TESTED at implementation verification: PostgreSQL transaction concurrency
(no identified disposable PostgreSQL test database at that time), production deployment, operational customer records,
other browsers and physical touch interaction. SQLite forced-concurrent apply
cases passed for whole-second and nonzero-microsecond timestamp encodings.
The later Docker work executed 23 API regressions against an owned disposable
PostgreSQL database; the two forced SQLite cases were skipped. That later run is
recorded in the linked Docker report and does not establish PostgreSQL concurrency.

The existing expected failure in `tests/test_selected_mc_load.py:147` remains
open: selected-plan lane-load Decision varies with the base seed. Its math and
test were preserved and this upload task does not claim to resolve it.

No supported unresolved defect was found in the implemented upload slice.
Whole-folder Ruff/mypy remain failed gates due to the recorded old output
artifacts, so repository-wide verification is PARTIAL. No cleanup or configuration
change was made outside the approved scope to force those commands green.

The bounded first slice declines unsupported formats instead of silently
converting them. Closing remains a separately persisted existing API action;
its partial-save/retry behavior is exposed and tested. No queueing formula,
model selection, simulation algorithm, optimizer, existing endpoint shape,
schema, authentication policy or original data was changed. This is local
implementation evidence, not a global correctness or production-readiness claim.
