# Selected Validation and Decision corrections: verification record

Date: 2026-10-19\
Status: **COMPLETE for the approved two corrections and isolated verification. Other statistical findings remain open; runtime activation is not included.**

## Authorization and scope

The owner explicitly approved "implementation of the two corrections and isolated verification
under this plan": [approved plan](../plans/2026-10-19-selected-validation-decision-corrections-plan.md),
implementing the [approved specification](../specs/2026-10-19-selected-validation-decision-corrections.md).

Only SEV-001 (selected Validation rounded comparator) and SEV-002 (selected Decision passed count)
are being corrected. Other statistical-audit findings remain open/inconclusive. This is not
Hoeffding integration, paper reproduction, a seed-sensitivity repair, or a deployment.

## Actual modifications

| File | Change |
|---|---|
| `backend/api/workflow.py:1291,3165,3187,3359` | A private exact-count option is enabled in both selected aggregation calls. Strict integer count evidence determines the unrounded comparator; unusable counts make the selected row inadequate. The default Current comparison and output/display fields remain unchanged. Selected Decision's failed branch uses total minus failed minus inadequate for its passed count. |
| `tests/test_selected_plan_validation.py:119,142,156,171,180,195,403` | Added exact boundary, count type/range/missingness, existing evidence-gate, identity, unchanged default Current, and persisted fresh Validation-to-Decision regressions. Existing synthetic helpers now carry consistent explicit completed-trial/count evidence. |
| `tests/test_selected_plan_decision.py:68` | Added four mixed-category count cases with unchanged Decision status checks. |

No other application/test/fixture/configuration/frontend/report source was edited by this task.
The two correction documents receive execution-status updates; this is a new verification report.
All preexisting unrelated dirty-tree work belongs to the starting snapshot, not to these corrections.

The application patch does not change raw MC generation, Wilson intervals, adequacy, utilization
thresholds, failure caps, trial/replication budgets, RNG/seeds, routing/DES traces, optimizer behavior,
Current/shared semantics, public response shapes, schemas or existing reports. Seed 42 remains 42.

## Execution environment and evidence

Source worktree:

`C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/.claude/worktrees/ux-workflow-audit`

Branch/HEAD at execution start: `feat/ux-u1-shell` /
`0b9423ec66d32620ed91769ac35a10e51ffae2ec`.

Isolated artifact root:

`C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/output/selected-validation-decision-corrections-2026-10-19`

The `baseline`, `red` and `candidate` directories are file snapshots, not Git worktrees. Snapshot
manifests include dirty/untracked source inputs and exclude environment/secret files, application
databases, Git metadata, old outputs and caches. Installed frontend dependencies were copied into
the disposable candidate; live dependencies/builds were not used as writable targets.

Every run uses a sanitized process environment: NOVAQ_ENV=test, direct proxy mode, disposable
SQLite fallback, no NOVAQ_TEST_DATABASE_URL or DATABASE_URL_FILE, snapshot PYTHONPATH, disabled
Python bytecode writes, and task-local temporary/cache paths. API tests use temporary fixture
databases. No application or Postgres database is used.

Python: root `.venv/Scripts/python.exe`, with `-B`. Full Python/package versions are in
`evidence/baseline.json`. Node v24.16.0 and npm 11.13.0 were executed and recorded.

Exact expanded argv, working directory, sanitized isolation values, UTC start/end, exit code,
wrapper elapsed time, and stdout/stderr are retained in `evidence/<phase>.json` and `.log`.
Pytest JUnit records retain individual testcase outcomes. Wrapper elapsed time and pytest's own
duration are separate measurements; do not add overlapping test counts together.

## Executed verification

| Phase | Actual result | Evidence under artifact root |
|---|---|---|
| Existing focused baseline | 37 passed, 1 warning; exit 0 | `evidence/baseline-focused-retry.{json,log,xml}` |
| Intentional pre-fix regression reproduction | 25 expected failures, 17 controls passed, 27 deselected; exit 1 | `evidence/red-regressions.{json,log,xml}` |
| Corrected focused candidate | 79 passed, 1 warning; exit 0 | `evidence/candidate-focused-corrected.{json,log,xml}` |
| Wider selected/model-aware/report regressions | 55 passed, 1 existing xfailed, 1 warning; exit 0 | `evidence/candidate-regressions.{json,log,xml}` |
| Ruff | All checks passed; exit 0 | `evidence/candidate-ruff.{json,log}` |
| mypy | No issues in 239 source files; exit 0; informational untyped-body notes retained | `evidence/candidate-mypy.{json,log}` |
| Frontend typecheck | Passed; exit 0 | `evidence/frontend-typecheck.{json,log}` |
| Frontend lint | Zero warnings/errors; exit 0 | `evidence/frontend-lint.{json,log}` |
| Full backend suite, first attempt | INCOMPLETE: interrupted with no final exit code or JUnit result; not a passed gate | `evidence/candidate-backend-suite.{json,log}` |
| Frontend build | Build subprocess passed, exit 0; chunk-size warning retained; wrapper display error described below | `evidence/frontend-build.{json,log}` |
| Frontend tests, first attempt | FAILED: 81 files / 628 tests passed, 1 unhandled worker-start timeout; exit 1 | `evidence/frontend-tests.{json,log}` |
| Optimize page retry alone | FAILED: no tests ran; same forks worker-start timeout; exit 1 | `evidence/frontend-optimize-isolated.{json,log}` |
| Independent frontend worker control | 1 unchanged file / 8 tests passed; exit 0 | `evidence/frontend-control-isolated.{json,log}` |
| Full frontend sequential retry | 82 files / 683 tests passed; exit 0; Vitest 664.65 s, wrapper 667.524 s | `evidence/frontend-tests-sequential-retry.{json,log}` |
| Full backend retry | 3270 passed, 123 skipped, 1 existing xfailed, 9 subtests passed, 1 warning; exit 0. Pytest 2788.15 s, wrapper 2851.240 s | `evidence/candidate-backend-suite-extended.{json,log}` |

The completed backend run collected 3394 cases: 3270 + 123 + 1 = 3394. Nine passing subtests
are reported separately. JUnit includes them in its suite-level test count (3403) and combines
the 123 skips and one xfail in its skipped attribute (124); these are not contradictory results.
The exact summary, all skipped identities/reasons, the unchanged xfail reason, and the zero-exit
gate records are consolidated in `evidence/completed-gate-review.json`. All 42 added regression
cases passed in the full suite. The single warning is Starlette TestClient's deprecated
`anyio.abc.BlockingPortal` alias in the installed dependency.

All 123 skips require an unavailable PostgreSQL test connection:

| Recorded reason | Cases | Status |
|---|---:|---|
| needs NOVAQ_TEST_DATABASE_URL (PostgreSQL) | 5 | NOT TESTED |
| NOVAQ_TEST_DATABASE_URL is required for the PostgreSQL variant | 115 | NOT TESTED |
| NOVAQ_TEST_DATABASE_URL is required for PostgreSQL migration rehearsal | 3 | NOT TESTED |

These skips were not added by this task. No PostgreSQL service or existing database was used to
make the suite pass. The approved execution scope explicitly omits external database verification.

The intentional red failures reproduced rounded-boundary acceptance, acceptance of unusable exact
counts under the old selected path, the identity/boundary integration case, and incorrect mixed
Decision counts. No import/harness failure was counted as a successful reproduction. There were
42 selected new cases in that run: 25 failed before the patch and 17 controls already passed.

Independent reference arithmetic is recorded in `evidence/independent-references-and-snapshot.json`:
Python Fraction compares each of the six approved synthetic k/n cases against exact 1/20; integer
N-F-I gives the four approved passed counts 1, 0, 2, 0. This is consumer-rule/arithmetic verification,
not a stochastic experiment or a field-validity claim. All 863 candidate snapshot files matched
their captured hashes before the final full backend retry.

The focused candidate includes a synthetic persisted MC row with 5001/100000 failures. A fresh
Validation is `fail`, its linked fresh Decision is `revise`, and the original DES/MC job payloads
remain unchanged. It does not claim a new 100,000-trial stochastic experiment was executed.

## Interrupted/environment attempts (not passing results)

1. The first sandboxed baseline was interrupted after five pure tests passed and the first API
   case stalled. A separate diagnostic timed out with exit 124 after 90 seconds. Its traceback
   shows Windows asyncio in `_fallback_socketpair` / `socket.accept`, before NovaQ handles the
   request. The unchanged isolated baseline passed outside that sandbox. A sandbox IPC restriction
   is the supported explanation/inference; no application workaround or settings change was made.
2. One candidate-focused run was interrupted on discovering a typo in the XML output directory.
   The mistyped directory did not exist when checked. The runner now rejects output paths outside
   the approved artifact root; the corrected focused run completed and passed. The interrupted run
   has no completed pytest result and is not counted as a gate pass.
3. The build subprocess completed with exit 0 and produced the disposable `dist/index.html`.
   Its wrapper then exited 1 while printing a Unicode box-drawing character through cp1252, after
   recording the child exit code. This was a harness display error, not a build failure. UTF-8
   output was enabled in the task-local wrapper; the build was not unnecessarily repeated.
   `evidence/harness-display-error.json` records both exit codes and the output-file hash.

The full backend attempt has no final result. On resume, the former tool session was unknown,
no matching isolated Python/Node processes were found, and no JUnit XML existed. Its stale RUNNING
record is retained; `evidence/resume-process-check.json` classifies it as incomplete. A retry uses
a longer task-harness wall-clock deadline, without changing test or analytical settings.

The frontend retry of OptimizePage alone also timed out before transform/setup/import/test execution.
Concurrent backend load is therefore not a verified explanation. A separate unchanged control file
then passed all 8 tests. The subsequent full sequential retry passed all 683 tests in 82 files,
including OptimizePage's 55 tests, with exit 0 and no unhandled error. The exact cause of the earlier
startup failures remains UNKNOWN. No source, assertion, worker configuration, timeout or error
handling was changed; the passing full retry is the completed frontend gate, and prior failures
remain recorded.

Original logs/records and `evidence/execution-interruptions.json` are retained. API runs outside the
sandbox retained the same source snapshot and disposable database/cache isolation. No Docker or
production action was substituted for test execution.

The build's large-chunk and plugin-timing warnings are retained in its log. No frontend source,
bundling configuration, warning threshold or dependency version was changed to suppress them.

## Scope and preservation review

`evidence/source-scope-review.json` verifies that only these workflow function ASTs changed:
`_separate_validation_verdict`, `validate_selected_plan`, and `_derive_selected_decision`.
The candidate's three edited application/test files match the actual source worktree patch.

Verified protected hashes so far:

| File | SHA-256 |
|---|---|
| `backend/queueing_engine/simulation/simulation.py` | `4c80bee3d31c87aef80170b69a16e8d449d4622d640fb7208309832cbffc201d` |
| `backend/queueing_engine/services/separate_optimization.py` | `ec0f58d5c28bad4dcd9fe498cda609f52d0721aca8fd9166c30172412e839115` |
| `tests/fixtures/novamart_events.csv` | `951d8f3d67af77f455396bac8bbb9adc072568ce0a1ac0df67b637e121fb6752` |
| `tests/test_selected_mc_load.py` | `c2fcd05ba3e5afd715df5fb8a6a35d1f3a48554223c55a281b5b71e6d79e31eb` |

Post-gate preservation check PASSED (`evidence/post-gates-preservation.json`), following the
passing resume checks. All 865 protected baseline files, including the preexisting local database,
memory/handoff and unrelated dirty work, are byte-for-byte unchanged. Only the three allowed
source/test files and two correction documents differ from the 870-file baseline. The sole new
Git-visible file is this verification report (871 current files).

HEAD remains `0b9423ec66d32620ed91769ac35a10e51ffae2ec`. The empty index SHA-256 remains
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
The candidate's three source/test files match the real worktree; all 863 captured candidate
inputs still match their snapshot hashes after the full backend run.

The reviewed three-file patch is `evidence/final-application.patch`, SHA-256
`9a6e0cfa519356f660ff8bf750767d3200396c1512eb40af648344228f8210bc`.
`git diff --check` passed; Git's informational LF-to-CRLF warning is retained in
`evidence/final-diff-review.json`. No staging, branch/HEAD changes or unrelated edits occurred.

## Acceptance and disposition

| Criterion | Result | Evidence |
|---|---|---|
| Selected cap equality and both sides of rounding boundary, using recorded counts | PASS | `test_selected_exact_count_boundary`; independent Fraction references |
| Unusable/missing exact counts stay inadequate; existing support/adequacy/DES gates preserved | PASS | Added invalid/missing/gate cases and existing conservation cases |
| Both aggregation levels preserve time/queue identity and FAIL precedence | PASS | Boundary and coordinate-identity cases; existing precedence regressions |
| Default Current and unrelated shared behavior retained | PASS within executed tests | Unchanged Current module; full backend suite and protected-file hashes |
| Decision passed count is N-F-I, with unchanged status | PASS | Four mixed-category cases plus existing taxonomy tests |
| Fresh Validation followed by fresh linked Decision; original synthetic DES/MC payloads unchanged | PASS | `test_selected_exact_counts_persist_and_drive_fresh_decision` |
| Producer/engine, statistical rules, settings, historical data and existing exports unchanged | PASS for source/data preservation | 865 protected-file hashes; source function/diff review |
| Required isolated gates and scope review | PASS with explicit skips/xfail | Completed gate records, final diff and preservation records |

**GO:** review and a separately authorized scoped commit of these two corrections and their
verification documents. Implementation and the approved SQLite-isolated verification are complete.
No additional source correction is justified by the executed in-scope results.

**NO-GO for automatic runtime activation or historical-chain certification:** existing stored chains
must first be inventoried and any required rerun/compatibility action separately approved. The patch
does not settle seed sensitivity or establish operational/field validity. No deviation from the
approved source edit scope occurred. Harness repairs/deadline changes stayed inside the disposable
artifact root; interrupted and failed attempts remain in the evidence.



## Remaining limits

- The seed-sensitive Decision finding is still open; the strict xfail is untouched.
- Displayed MC rates remain rounded presentation values; 5001/100000 can display as 0.05 while
  correctly failing the 0.05 cap. No UI/response-shape change was approved.
- Missing exact counts in a legacy selected MC row require insufficient evidence under the approved
  amendment. Validation cannot reconstruct absent counts from a rounded fraction or cached PASS.
- Existing saved jobs/exports were not rewritten. Old linked Validation/Decision chains can remain
  visible under existing currentness rules, and a new Decision consuming an old Validation can
  reflect that old verdict. These chains are not certified by the new source patch.
- Postgres integration, native Excel, browser light/dark/accessibility, original paper-run
  reproduction, field validity, Docker activation and production behavior are NOT TESTED here.
- No commit, push, image rebuild, runtime activation, migration of an existing application database,
  or deployment was performed. Migration tests in the required suite use disposable test databases.

Completion is limited to the two approved corrections and the executed isolated checks above.
Any later runtime activation must separately identify affected saved chains and obtain approval
for needed reruns or a separately scoped compatibility guard.
