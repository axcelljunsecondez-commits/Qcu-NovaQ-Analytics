# Shared aggregate CSV upload review

Status: COMPLETE for scoped source and local acceptance-evidence review.
Stable review ID: shared-upload-20261030.
Reviewer: Kyoya, findings-only; fixes remain with Chrome/Hayato through parent.

## Target and ownership

Checkout: C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ.
Branch codex/shared-queue-workflow-20261029, base HEAD
2e0e360666b2b4302faaddeb955f63e64395aab1. Application changes are uncommitted.
Frontend is still being edited; backend source review is provisionally bound to
the hashes below. No application/test/fixture/docs changes by this reviewer.

Approved target: shared-queue-upload-simplification spec/plan (2026-10-29,
implementation authorization and D4/D8/D9 approval updated 2026-10-30), and the
2026-10-30 implementation report. Root AGENTS.md governs protected behavior.

## Source checks completed

- Existing analyses.py handlers are unchanged: its diff adds only the new router
  import and include_router call. New preview/apply routes are additive.
- New derivation reuses normalization/timeline validation and the existing
  _counter_breaks helper. Explicit supplied extra evidence columns decline;
  saved operational settings are preserved and actual apply normalizes again.
- Preview performs no Dataset/Job/Scenario or analysis update in inspected source.
  Apply checks owned/unarchived analysis, upload limits, file digest, saved/current
  revision, explicit unresolved choices, preserved known choices, break conflicts,
  replacement intent, and updates Dataset/Setup in one transaction.
- Idempotent retries require the existing Dataset to remain current and the applied
  Setup digest to match. New namespaced creation metadata is within parent's
  documented boundary review. No schema migration or existing provenance rewrite.
- PostgreSQL row lock plus timestamp CAS is present; SQLite uses exact whole-second
  alternate encoding only for zero microseconds. It does not round precision away.
- The foundation importer test retains a full backend scan, adding only the exact
  new approved derivation adapter. No broad directory exemption.
- All 45 parent-baselined protected paths matched baseline hashes during this pass.
- Locale diffs contain only the exact three owner-approved EN/TL pairs. Protected
  wording records/test are unchanged in the protected comparison.

## Source identity at initial backend review

| File | SHA256 |
| --- | --- |
| backend/data/shared_aggregate_setup.py | 961c3264f9d6fc4d514acddf56aba216ffec192e25e32898a7dfbfd5fcf6dbaf |
| backend/api/shared_aggregate_schemas.py | 24c81ab3fcee6880a24718e418046f51274dda7f38fb628c4a28100785783fdd |
| backend/api/shared_aggregate_upload.py | bb27b90d379765bb8cf4b11442864fb11d3bd4a965135fc2802440060fb18c09 |
| tests/test_shared_aggregate_setup.py | 693844ba1be99eac64f5fac5eee03aba7430d8aa9ff321b3db1fe5bce379ebe2 |
| tests/test_shared_aggregate_setup_api.py | 019ac4b1f0e4678a14d1e6b1ebd7387375ef0317092f730b559571205e5cd419 |

## Findings ledger

### K-UP-1 — pending closing-policy read can leave a hidden draft to persist

Status: CLOSED in the reviewed source, with targeted regression evidence inspected.
Source: frontend/src/components/setup/MissingChoices.tsx:61 and
frontend/src/pages/AnalysisSetupPage.tsx:126,279 (initial reviewed state).

VERIFIED source: undefined closing-policy query data (including pending/error) is
treated as no saved policy, so the radios are shown. A local selection is later
written unconditionally after Dataset/Setup apply. If the pending read resolves
with an existing policy, the radios disappear but that draft remains in state.
INFERRED reachable impact: a deferred GET can let the user choose DRAIN, then
display saved HARD_CUTOFF while the apply handler still writes hidden DRAIN.
Runtime reproduction: NOT TESTED by reviewer; requested deferred-read and error
regressions. Proposed correction: withhold/disable controls until a successful
read and prevent a hidden draft from overwriting authoritative saved state.
Owner: Chrome. Parent relayed the finding for correction and final closure review.

Closure: MissingChoices now receives `closingReady` and withholds both saved-state
and new-policy controls until the read succeeds. `saveFileClosing` checks the latest
query state through a ref and writes only when the authoritative policy is null.
The deferred-read and read-error regressions in SharedAggregateUpload.test.tsx
assert no policy write; both passed among the 25 passing cases in recovery-final.log.
That whole-file run was NOT a pass: its remaining failure queried nonexistent label
`Capacity` instead of the actual approved `Capacity mode`. Parent was informed to
correct the label while preserving the focus assertion. This is an explained test
query defect. The successful whole-file rerun is recorded in the delta review below;
the final full frontend gate still needs its completed result.

Parent's separate interim flags (not independent new findings here): applied-file
guard after saved -> review -> planning; raw JSON in replacement display; partial
success/retry when closing save fails. Corrected source and regression coverage
were inspected: the guard is consumed once, replacement displays concise clock/
count values, and a failed closing write preserves Dataset success and retries
only the closing endpoint.

## Final scoped source pass (2026-10-30)

Current hashes are in `2026-10-30-shared-upload-source.json` beside this record.
At this pass AnalysisSetupPage.tsx is
53481bb1f692b943a182d791b741f16ebac2af293a2ff7abc9a5c7fb89d470d1 and
shared_aggregate_upload.py is
59e3ac02ae01568fedabc8bf660743cff301f983ba111f4ff0d747ada39ea21a.
These supersede the initial API hash above; HEAD remains the same uncommitted base.

The corrected new XLSX path detects multiple worksheets and declines before
derivation/apply, rather than silently accepting just the first aggregate sheet.
The direct API regression creates a synthetic extra staff sheet, checks declined
preview and apply 422, and verifies saved state unchanged. The existing workbook
validators and routes remain unchanged. Actual focused-final.log records 153 passes
including this test and legacy workbook/ingestion regressions. The old full backend
run was cancelled before this fix; its cancellation record is not a passing gate.

Frontend readonly recovery for `setup_changed`/`file_changed` refreshes analysis
and dataset evidence and increments a read nonce only when a changed Setup has not
already triggered a fresh preview. It never retries the write, clears old answers,
and guards late responses by sequence/file/purpose/keyed analysis. Tests cover
file-only mismatch and an externally changed Setup without duplicate preview/write.
Known finite/modeled settings with missing required numbers now block Apply and
retain a Change action to Advanced; neither UI nor API invents a number.

All 45 protected paths were rechecked and remain unchanged. The legacy test
changes add mocks for the new declined path; changed expectations correspond to
approved upload-first/no-fixed-count-before-file behavior, not changed maths or
weakened old endpoint assertions. No supported open source finding remains in
this inspected target. This is not a runtime or production acceptance claim.

## Confirmation delta review (2026-10-30)

The parent observed that replacing only an existing planning Dataset with no
Setup diff still displayed the old Setup-change confirmation. The corrected page
uses the old Setup title/help/action only for a nonempty diff. An empty diff reuses
`analyses.upload`, `setup.purpose_planning_help`, and `analyses.process`, retaining
explicit confirmation and the same cancel/apply guard. No new wording or request
shape is introduced.

VERIFIED delta identity: replacing those three conditional key expressions with
their previous expressions exactly recreates the prior reviewed page SHA256
53481bb1f692b943a182d791b741f16ebac2af293a2ff7abc9a5c7fb89d470d1.
The new page SHA256 is
5d2cc36dd99ac0f7d8a5af19256a7060b2667f92cb93c911e488c1c25d80fb11.
All other files in the review manifest are unchanged except the corresponding
test file (now 4c8100f8dca26961dbd297f05d6183f26325a1f5a88f5bb6cbfb1f7286090297).
All 45 protected paths still match the original baseline.

The new regression checks the empty-diff planning replacement, truthful prior-
results warning, absence of Setup-change copy, no write before confirmation, and
cancel writing nothing. Actual `chrome/browser-fix-focused.log` records 27/27
passed, covering the new case and the earlier K-UP-1/readonly-recovery cases. No
supported new finding is introduced by this delta. The updated source manifest
preserves previous hashes and records the new ones.

Actual `hayato/backend-full-final.log` completed with 3,331 passed, 125 skipped,
1 existing xfailed, 9 subtests passed and one existing deprecation warning in
2108.33 seconds. The earlier cancelled full run remains explicitly cancelled.
The prior 803-test frontend full pass predates this final page delta and is
historical evidence; a new final frontend run and final built-browser matrix are
parent-owned and still pending at this review update.

## Duplicate conflict-text delta review (2026-10-30)

The parent observed identical break-conflict detail repeated in the nested problem
list. The only application delta is a filter omitting a problem string when that
same full string already occurs in the displayed detail. Distinct additional
problem strings remain rendered. The conflicts collection and Apply guard are not
changed, so a blocked upload remains blocked; no server data is changed.

VERIFIED delta identity: removing this single filter from the current page exactly
recreates the previously reviewed SHA256
5d2cc36dd99ac0f7d8a5af19256a7060b2667f92cb93c911e488c1c25d80fb11.
Current page SHA256:
4f5dae26a5d1acafd763fcad7506c561287a4886c5cf9beab3cb6d0070e83b97.
The corresponding test file is now
ac80baf209a0bda804b844396ee599942f47d6072fa83ffd1be5b8d2ccc158dc.
No other file in the 18-file review manifest changed. All 45 protected paths
remain unchanged. The source identity JSON records this delta and current hashes.

The new test checks one visible occurrence, disabled Apply, and no write when
the server repeats the exact detail. The existing fixture with generic detail
and a distinct additional problem remains, and the inspected filter preserves
that distinct text. No supported new finding in this bounded presentation delta.
The actual 804/92-file frontend pass predates this filter; the new final full
frontend gate and final built-browser matrix are still pending. Their expected
counts are not recorded as passes before execution completes.

## Executed verification and limits

Reviewer executed read-only source/diff inspection, protected SHA256 comparison,
and exact locale-diff inspection. Did not duplicate workers' test suites.
Inspected actual Hayato focused-third.log: 90 tests passed, one existing warning.
Inspected root integration-probe.json: status passed; isolated owner CSV, successful
preview/apply/retry/Current/full-day/replay, with explicit diagnostic settings.
These are evidence checks, not independent execution of those tests by reviewer.

Source-scoped Ruff passed and mypy reports no issues in 235 files in inspected
logs. Whole-folder Ruff reports 1,304 diagnostics across 164 old output paths;
whole-folder mypy stops on the old duplicate backend module under output. These
root failures are explained, not relabeled as passing. Initial final frontend
focused run recorded 51 passes plus two Vitest fork startup timeouts, so was a
failed/incomplete gate. The subsequent serial run recorded 25 passes and the one
incorrect-label test failure described above. The 27/27 targeted rerun supersedes
that whole-file failure; the earlier attempts remain recorded rather than erased.

The replacement full backend suite passed as recorded above. Final full frontend
gates and final built-browser checks are parent-owned and incomplete at this point.
Browser checks remain NOT TESTED by this reviewer independently.
PostgreSQL concurrent transactions, production and operational customer data have
not been exercised by this review. No global security/math-correctness guarantee.

## Acceptance evidence closure (2026-10-30)

The final 18-file source manifest was checked again: no application or test hash
changed from the last reviewed target (page 4f5dae26...e83b97; test ac80baf2...158dc).
No additional application/test edits or suite runs were performed by this reviewer.

Inspected parent-executed final artifacts:

- `chrome/frontend-complete.log`: 805 passed across 92 files, 396.41 seconds.
  Existing jsdom canvas messages remain; no tests failed.
- `chrome/typecheck-complete.log` and `lint-complete.log`: actual final commands
  have no diagnostics; parent recorded exit 0.
- `chrome/build-complete.log`: built successfully in 4.04 seconds. Existing
  large-chunk/plugin-timing warnings remain and were not concealed.
- The unchanged backend final log records 3,331 passed, 125 skipped, one existing
  xfail, nine subtests passed. This does not close the pre-existing selected-load
  statistical finding or turn skipped PostgreSQL checks into passes.
- `preservation-final.json`: all 45 protected paths unchanged, all previous locale
  values unchanged, only the three exact approved keys added to both locales,
  symmetric keys, source/fixture CSV SHA256 unchanged, diff check passed, index empty.
- `staleness-probe.json`: a new planning dataset makes the saved scenario
  STALE_DATASET; the historical run result is unchanged and its dataset is no longer
  current. The probe uses isolated diagnostic settings, not observed costs.
- `browser-cancel.json`: replacement Cancel leaves zero datasets, saved fixed c=3,
  zero segments and null closing policy unchanged.
- `browser-refusals.json`: finite capacity 20 and normalized K preserved; Decide
  later keeps closing null; unsupported setup creates no run Job; the saved 04:15
  break is preserved; conflict/gap/multiple-sheet cases create no dataset.
- Refreshed `integration-probe.json`: existing owner-CSV diagnostic replication
  rows, period utilization and summary remain exactly equal through the new upload
  path; each of the five saved executions replays successfully.

REPORTED by the parent from its actual built-browser interactions: automatic
owner-CSV summary and all 13 rows, first save, fixed-count replacement cancel and
confirm, review/planning reread, full-day run/replay at 11:31, EN/TL responsive
light/dark checks, and keyboard Cancel on the corrected dataset-only confirmation.
Browser operation was executed by the parent, not this reviewer. The saved JSON
and source above were inspected directly; no independent browser session is claimed.

No supported open finding remains in this reviewed feature. K-UP-1 is closed;
the bounded confirmation/dedup presentation deltas preserve write/conflict guards.
Whole-folder Ruff/mypy remain explained failures from old output snapshots; only
the source-scoped passes are passes. Production, operational customer data,
PostgreSQL concurrency and physical touch remain NOT TESTED here. No commit,
push, Docker activation or deployment is implied by this local review.

Next action: parent finalizes the owner-facing implementation report. No further
source action is required by this review. If the application hash manifest changes,
reconcile affected findings/evidence before reusing this conclusion.

## EOF-only cleanup review (2026-10-30)

The parent removed one trailing blank line at EOF from
`frontend/src/components/setup/MissingChoices.tsx` after the staged diff check
found it. VERIFIED: adding exactly one LF back to the current bytes recreates
the previous reviewed SHA256
2398120dfda2b532da6a0e9083018c4f68fb276a9de2f0db15ecd0e739e6231e.
The new SHA256 is
b2006c9b49b54b0a6218ef3815c6fa44f48f51015d1cbc1f764614a876a80aa9.
No other file in the reviewed source manifest changed. The source identity JSON
is updated. This changes no JavaScript tokens, controls, copy or behavior; no
new finding and no test rerun required for this exact whitespace-only delta.
No staging, commit or Docker action was performed by the reviewer. The parent's
separately authorized local activation is outside this source-delta review.
