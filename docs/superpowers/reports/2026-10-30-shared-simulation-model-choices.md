# Shared model choices moved to Simulation

Date: 2026-10-30, Asia/Shanghai. Application implementation: COMPLETE LOCALLY.
Repository-wide validation: PARTIAL because the root tools fail on output
artifacts and the installed mypy reports an error in unchanged backend source.
Docker update: pending at this source checkpoint; see the activation addendum
below when completed. No production release or push.

## Approved scope and identity

The owner chose “Skip upload questions; answer in Simulation” and specified
“Capacity and abandonment controls” for removal from My analyses → Data and
Setup. This is the shared-queue flow discussed in this chat. Existing single,
separate and unknown-structure Setup controls retain their behavior.

Checkout: C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ.
Branch: codex/shared-queue-workflow-20261029. Starting HEAD:
007f59242c94f4340e9bc0d013b923cea3aa3ca7. Tracked tree was initially clean.
Existing .claude/launch.json, .playwright-cli/ and output/ are preserved/excluded.
Evidence: output/simulation-model-choices-20261030/. Baseline covers all 1,006
tracked files and 45 protected paths. The original owner CSV and portable fixture
retain SHA256 236fc05861b4a59ce3216c41fb52b3c529aec6b6f57003f610bd4cc3a91f938e.

## Actual behavior and files

VERIFIED: a supported shared planning upload sends explicit `unknown` for each
unresolved capacity/abandonment answer. No supported assumption is substituted.
Known saved settings and required-number guards remain. The optional closing
choice, confirmation, stale-file/purpose/analysis, conflict and retry protections
remain on the upload path. Unsupported automatic reads still use the old upload.

Both controls are removed from shared Data and Setup, including its Advanced
form. Unknown/incomplete model-choice actions open Simulation Advanced directly.
The Simulation refusal button expands/focuses the controls locally. Existing
approved EN/TL strings are reused verbatim; both locale files are byte-identical.
The shared Setup caption that described the removed fields is omitted there.

Simulation reads the saved analysis and saves through its existing PATCH route.
It fetches the latest Setup, merges the four model-choice fields, and preserves
staffing, periods, breaks and other Setup fields. Finite capacity requires an
integer 1–100000; modeled abandonment requires a positive finite hourly patience
rate. Unknown may be saved; it still blocks the full-day run. Finite capacity and
modeled abandonment remain unsupported by that engine. The Run button blocks
unsaved drafts and pending saves; Save or Cancel resolves the draft. Run also
disables edits while executing. Read/save failures, archived analyses and changing
analysis IDs are guarded. A read-before-PATCH is not an atomic concurrency/CAS
guarantee; the existing API contract is unchanged.

The changes are analysis Setup settings, not run-only overrides. Save refreshes
analysis/current/compatibility/run caches and resets workflow/scenario evidence.
Existing selected-plan and stale-run checks remain authoritative. Changing Setup
can require recalculating a plan. Stored normalized Dataset rows are not rewritten.
No changes to model selection, DES, automatic replications, optimizer, API shapes,
schema, dependencies, auth or ingestion were made.

Application files:

- frontend/src/components/queueSimulation/SimulationModelChoices.tsx and its new
  test file: saved choices, validation, fresh merge, errors, draft/pending guards.
- frontend/src/components/queueSimulation/ContinuousRun.tsx: local Advanced action,
  direct repair-link handling, existing approved unknown note and run gating.
- frontend/src/pages/AnalysisSetupPage.tsx,
  frontend/src/components/setup/MissingChoices.tsx and
  frontend/src/lib/sharedAggregateSetup.ts: defer unresolved answers, closing-only
  upload choice card, remove shared controls, link incomplete known numbers to
  Simulation. Other queue structures retain their controls.
- frontend/src/styles/global.css: five rules scoped to the new editor, using
  existing spacing tokens and 44px radio-label targets.
- SharedAggregateUpload.test.tsx and QueueSimulationPage.test.tsx: updated
  regressions for the approved flow; existing safety guards retained.

## Executed verification

| Gate | Actual result | Evidence under the task folder |
| --- | --- | --- |
| Complete frontend suite, final frozen source, one worker | PASS: 817 tests / 93 files, 748.26s, exit 0 | frontend-full-serial-final.log |
| Focused upload/editor/Simulation regressions before final minor guards | PASS: 108 tests / 3 files, 78.94s | targeted-final.log |
| Frontend typecheck, lint, production build on final source | PASS, exit 0; existing chunk-size warning retained | typecheck-final.log, lint-final.log, build-frozen.log |
| Existing shared upload, continuous API and playback tests | PASS: 73 tests, 179.31s | backend-tests-final.log |
| Backend/tests Ruff | PASS | ruff-source-final.log |
| Required root Ruff | FAIL: 1,310 diagnostics, all under output/ at that check | ruff-root.json, preservation.json |
| Required root mypy | FAIL: duplicate backend module in old output/decision-scope-implementation-20261023/original/ | mypy-root.log |
| Backend/tests mypy | FAIL: unchanged backend/api/shared_continuous.py:447 passes str where _assess expects Literal current/suggested | mypy-source-final.log |
| Protected preservation | PASS: all 45 protected paths, all 96 backend files, both locale files and owner CSV unchanged | preservation.json |
| Diff whitespace check | PASS | git diff --check |

CONFLICTING with the earlier task record's source-mypy PASS: this installed-module
execution reports the error above. The exact backend file hash matches the
pre-change baseline. No backend repair, dependency/config change or suppressed
test was introduced to obtain a passing frontend gate. Full backend suite was
not repeated for this frontend-only change; the scoped 73 tests were executed.

Earlier attempts are retained: a two-worker startup timeout; an isolated upload
fallback failure in the new code, fixed by deriving deferred choices only for
shared_aggregate mode; and an unchanged Named Queue timing failure in a parallel
full run. Those full runs were stopped after failure. The final serial full run
passes all cases without changing timeouts, dependencies or protected expectations.
Bare ruff/mypy were unavailable on PATH; installed Python modules were then used.

## Isolated actual-data and browser evidence

The unchanged Avg_total_data_of_14_days.csv contains 13 hourly rate/count rows,
05:00–18:00, using the existing per-hour lambda/mu convention. The filename does
not establish averaging dates or raw observations. No source data was modified.

The isolated SQLite integration probe saved both choices as unknown, verified
the refusal, saved explicit diagnostic Unlimited/Not modeled choices via the
existing PATCH, ran Current using DRAIN/seed42/five executions, then changed Setup
and verified setup_matches_current=false on the stored run. Staffing and periods
were unchanged. Replications, period_utilization and summary exactly matched the
earlier owner-CSV diagnostic run with identical assumptions. These are diagnostic
assumptions, not claims about the real operation. See integration-probe.json.

Actual built-SPA browser check on 127.0.0.1:18769 used a separate analysis in that
disposable database and the original CSV path. It showed no model questions during
upload, saved once, and showed no capacity/abandonment controls in shared Advanced
Setup. Full-day Simulation showed the unknown refusal, the local Advanced button
expanded and focused the choices, Save refreshed the current-run assessment, and
an explicit closing policy could be saved on the same page. Run completed and
displayed all four key metrics and charts. A reload retained the saved choices.
Screenshots were inspected inline; no local screenshot artifact is claimed.

The final unsaved-draft guard is covered by the final full frontend suite; a new
browser execution of that last guard was not completed after resume because the
browser wrapper became unavailable. Responsive/TL visual review, authenticated
operational uploads, multi-user simultaneous PATCH and production behavior are
NOT TESTED in this follow-up. Existing bilingual labels have unit coverage.

## Local Docker activation addendum

Pending at source commit. Initial read-only preflight detected operational rows
changed since the prior verified backup. No container mutation occurred at that
failed preflight. A fresh encrypted backup and disposable restore are being
verified before the frontend-only update. API/db recreation, migrations, seeding,
production changes and pushes are outside this update.
