# Selected Separate-plan Validation and Decision correction plan

Date: 2026-10-19\
Status: **COMPLETE within the approved two-correction and isolated-verification scope.**\
Approved design: [two-correction specification](../specs/2026-10-19-selected-validation-decision-corrections.md).

## 1. Authorization and result sought

The owner approved the specification with "approve" after reviewing the document. This plan
makes the next source-edit/test action concrete under that specification's sections 7-9.
Preparing this plan is not an implementation, test-run, rebuild, activation, commit or push.

Execution approval received: "approve implementation of the two corrections and isolated
verification under this plan". No excluded action is authorized by that reply.

Under that explicit approval, make only:

1. Selected Validation use valid exact recorded MC counts for cap comparison, without changing
   the separate Current caller's behavior.
2. Selected Decision subtract both failed and inadequate checks from its stated passed count.

All requirements and compatibility limits in the approved specification remain binding.
No additional statistical method or seed-sensitivity correction is part of this plan.

## 2. Verified preparation baseline

Authoritative worktree:

`C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/.claude/worktrees/ux-workflow-audit`

- Branch: `feat/ux-u1-shell`.
- HEAD: `0b9423ec66d32620ed91769ac35a10e51ffae2ec`.
- 869 Git-visible files at preparation start, including the correction specification.
- Original 868 files excluding that specification still have aggregate path/content SHA-256
  `de9a33b3d7dddae47014aa38f1a8841163868e838c336d2551d517b75202ca2c`.
- The index is empty; the tree has preexisting unrelated modifications and untracked files.
- Source inspection still finds both defects: `workflow.py:1322` compares the rounded rate;
  `workflow.py:3345` subtracts only failed checks.
- At preparation, `NOVAQ_TEST_DATABASE_URL` was absent/nonempty-value false. This must be
  rechecked before execution; this historical read is not an execution-time guarantee.

Do not reset, stash, stage, overwrite or attribute the preexisting changes to this correction.
Refresh this baseline immediately before approved implementation; stop if protected inputs drift.

## 3. Edit allowlist and protected files

Future application/test edits are limited to:

| File | Permitted change |
|---|---|
| `backend/api/workflow.py` | Selected-only exact-count option in `_separate_validation_verdict`; enable it in both `validate_selected_plan` calls; correct the failure-branch passed-count expression in `_derive_selected_decision`; adjacent comments only. |
| `tests/test_selected_plan_validation.py` | Behavioral boundary/malformed/legacy cases, consistent synthetic helpers, per-period and overall identity cases, selected API persistence/provenance checks, and an unchanged-default-path check. |
| `tests/test_selected_plan_decision.py` | Mixed-category passed-count regressions and unchanged Decision taxonomy checks. |

The approved spec and this plan may receive truthful execution-status updates. A final verification
record may be created at `docs/superpowers/reports/2026-10-19-selected-validation-decision-corrections-verification.md`
if implementation/verification is approved. No existing report may be replaced.

All other application, test, fixture, configuration, frontend, locale, schema and report source
files are protected. In particular preserve `simulation.py`, `test_selected_mc_load.py`, its strict
xfail, `tests/fixtures/novamart_events.csv`, Current/shared validators, and all existing exports.
If a required fixture or reader outside this list must change, stop for a named scope amendment.

## 4. Approved isolated execution workspace

Proposed new artifact root:

`C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/output/selected-validation-decision-corrections-2026-10-19`

Before writing it, resolve and verify that the path is inside the named root repository and does
not already exist. If it exists, choose a fresh numbered sibling and record it; never reuse or
delete an existing verification directory. Do not create a Git worktree or change branches.

Inside that root, use `baseline/`, `red/`, and `candidate/` source snapshots plus separate `evidence/`
and cache/temp directories. Snapshot the current Git-visible working-tree content, including
approved dirty inputs, not just committed HEAD. Preserve relative paths and record SHA-256 manifests.
Exclude `.git`, `.env` and other secret/env files, application `.db` files and sidecars, old outputs,
virtual environments, dependency directories and existing build/cache directories. Do not copy the
ignored root output tree or `.claude/worktrees` recursively.

Use the existing root Python executable:

`C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/.venv/Scripts/python.exe`

Check dependency/tool availability without installing/upgrading packages. For frontend gates,
copy the existing installed frontend dependencies into the disposable candidate frontend after
checking available space; do not link a writable cache/build location back into the live tree.
Dependency downloads or repairs require a separate decision. If a verification requires Git
metadata unavailable in a snapshot, stop and report it; do not fabricate repository state.

For each test process, use a process-scoped environment with `NOVAQ_TEST_DATABASE_URL` and
`DATABASE_URL_FILE` absent, `NOVAQ_ENV=test`, `NOVAQ_PROXY_MODE=direct`, and a `DATABASE_URL` pointing
only to a disposable SQLite fallback file inside this artifact root. This also bounds a default
connection outside the explicit db fixture (`backend/api/settings.py:13-52,125-129,220`). Do not
inherit application credentials or production-setting files. Any test that needs another database
or external service is outside this execution approval and must remain NOT TESTED.

Set `PYTHONDONTWRITEBYTECODE=1`; ensure imports resolve to the selected snapshot, not a live-tree
`PYTHONPATH`. Use disposable TEMP/TMP, pytest `--basetemp`, mypy cache, `npm_config_cache` and generated
frontend outputs under this artifact root. No environment file, global variable setting, app
database, Docker stack or external service may be used or changed.

`tests/conftest.py:35-62` was inspected: without the test database URL the db fixture uses temporary
SQLite; with a Postgres URL it creates/drops schemas. Explicitly verify absence before every test
phase. The test suite/builds are mutating operations in these disposable directories, not read-only
operations. Execution is covered by the subsequent explicit implementation/verification approval.

## 5. Ordered implementation steps

Execution status (2026-10-19):

| Step | Actual status |
|---|---|
| 1: baseline | COMPLETE: 37 focused existing tests passed outside the Windows sandbox; the sandboxed API attempt stalled in asyncio socket-pair creation and is not a passing result. |
| 2: regressions | COMPLETE: 25 expected pre-fix failures and 17 controls passed, with 27 existing cases deselected. No skip/xfail changes. |
| 3: source patch | COMPLETE within the three-file allowlist. |
| 4: candidate | COMPLETE: 79 focused tests passed; wider regressions 55 passed and 1 unchanged xfail. |
| 5: remaining gates/record | COMPLETE: backend 3270 passed, 123 PostgreSQL skips, 1 unchanged xfail, 9 subtests passed; frontend 683 passed. Ruff, mypy, typecheck, lint and build passed. Diff and preservation checks passed; the new verification report retains failed/interrupted attempts and all limits. |

Evidence root is the exact proposed path in section 4. Command records, logs, snapshots and
interrupted-run notes are under its `evidence/` directory. An XML path typo was caught and its run
interrupted before the mistyped directory existed; the corrected focused run passed. No interrupted
run is counted as passing. Expanded command/environment records distinguish these attempts.

### Step 1: preflight and existing-test baseline

- Re-read the approved spec and relevant current source; confirm the same three-file edit scope.
- Record HEAD, index, status, full protected-file digests, source-snapshot manifests and tool versions.
- Establish the isolation checks in section 4.
- In the baseline snapshot, run the focused existing modules listed below. Capture command,
  environment constraints, UTC start/end, exit code, stdout/stderr and actual pytest summaries.
- Any unexplained baseline failure blocks implementation. Do not fix unrelated work or change
  expectations to obtain a green baseline.

### Step 2: add meaningful regressions in the two allowed test files

Validation cases must call the selected behavioral entry point and assert both per-period and
overall verdicts; do not merely test a new helper signature. Cover the exact table in spec section
4.4, count types/ranges, missing/null counts, count-less legacy selected rows, and preserved
support/adequacy/DES gates. Keep tests proving absent counts remain acceptable on the unchanged
default Current helper path. Same-time different-queue and multi-period inputs must not cross-match.

Create valid synthetic fixtures with explicit consistent `failure_count` and `trials_completed`.
Do not alter CSV/operational data. Preserve null/inadequate assertions and add explicit legacy cases
instead of making every fixture silently acquire success-producing defaults.

Decision cases cover `(N,F,I)` of `(3,1,1)`, `(3,1,2)`, `(3,1,0)` and `(3,3,0)`, with exact expected
passed counts and unchanged `revise` status. Preserve existing conditional, insufficient and
conservation guards.

In the red snapshot (original source plus the proposed test edits), run only the new behavioral
regressions to demonstrate expected failures. Record these as intentional pre-fix reproductions,
not passed gates. Import, harness, environment or unrelated failures are blockers, not acceptable red.
Do not add skip/xfail markers or relax existing assertions.

### Step 3: make the two source corrections

- Add a private keyword-only `use_exact_counts=False` option as specified.
- Preserve the default helper path; enable exact counts only in both selected aggregation calls.
- Validate strict integer count evidence, excluding booleans, with `n>0` and `0<=k<=n`.
- For supported, adequate, otherwise usable selected rows, compare `k/n` directly with the
  persisted cap. No rounding, epsilon, new CI rule, cached-status fallback or guessed denominator.
- Keep selected rows with unusable count evidence inadequate; keep response shape/display values.
- Change the selected Decision failure-branch expression to `N-F-I`; preserve status and other rules.
- Inspect the patch before running verification. MC/DES/optimizer outputs and settings are not edit
  targets. Seed 42 remains positive integer 42; other existing test seeds also remain unchanged.

### Step 4: candidate behavioral and regression verification

Create a fresh candidate snapshot containing the final three-file patch. Run focused tests first,
then the wider modules below. Verify newly persisted selected Validation/Decision links and that
the corrected chain uses fresh Validation followed by fresh Decision against the same synthetic
MC/DES evidence. No test may claim an old saved Validation was silently repaired.

For valid adequate count rows, assert selected PASS/FAIL matches the existing producer's unrounded
fraction rule. Do not rerun 100,000 MC trials merely to construct the deterministic boundary case.
Verify producer/engine/fixture hashes are unchanged. The known seed-sensitive xfail remains open.

### Step 5: repository gates and final record

Run the remaining repository gates below only after targeted checks pass. Preserve all failed
outputs and distinguish application failures from environment failures. Fix only explained,
in-scope regressions. Do not bypass failed gates or extend the allowlist without approval.

Refresh the original-tree manifests after execution. Only the three permitted source/test files
and truthful correction documents may differ; all other preexisting files, HEAD and index must
match the recorded baseline. Record actual results and limitations in the new verification report.
Do not stage, commit, push, rebuild or activate Docker after completing the checks.

## 6. Command templates and evidence

These templates are not execution results. Actual expanded argv, timings, exit codes and logs
are recorded per phase under the artifact root; see the status table in section 5.

Execute from the appropriate disposable snapshot root. Substitute its resolved paths for the
placeholders below; quote Windows paths. The later execution record must retain the exact expanded
argv and working directory, not only these templates. Use a distinct basetemp/JUnit path per phase.

### Existing baseline and focused candidate modules

```text
<PYTHON> -B -m pytest tests/test_selected_plan_validation.py tests/test_selected_plan_decision.py tests/test_separate_validation_current.py -x --tb=short -p no:cacheprovider --basetemp=<PHASE_TMP> --junitxml=<PHASE_JUNIT>
```

For the intentional red phase, select only the new test node IDs recorded after writing the tests;
do not invent their names in advance or claim this document contains executed red results.

### Wider selected/Current/shared/report regressions

```text
<PYTHON> -B -m pytest tests/test_selected_mc_load.py tests/test_model_aware_workflow.py tests/test_separate_report.py tests/test_b8_full_report.py tests/test_reports_api.py -x --tb=short -p no:cacheprovider --basetemp=<REGRESSION_TMP> --junitxml=<REGRESSION_JUNIT>
```

Do not use `--runxfail` to redefine completion, and do not remove or weaken the strict seed-finding
xfail. An expected-failure count is not closure of that finding.

### Required repository gates

```text
<PYTHON> -B -m pytest tests/ -x --tb=short -p no:cacheprovider --basetemp=<SUITE_TMP> --junitxml=<SUITE_JUNIT>
<PYTHON> -B -m ruff check . --no-cache
<PYTHON> -B -m mypy . --cache-dir=<MYPY_CACHE>
```

From the disposable candidate `frontend/`:

```text
npm test
npm run typecheck
npm run lint
npm run build
```

Do not claim Postgres integration, native Excel, browser themes/accessibility, production, original
paper reproduction, or field validity from these checks. Missing tooling or a required verification
that cannot be safely isolated must be reported NOT TESTED with the exact reason.

## 7. Completion and later activation boundary

Source correction completion requires all spec acceptance criteria, executed tests/gates with
actual outputs, a reviewed three-file diff, and preserved protected-file/Git evidence. This plan
does not promise a passing test count before execution.

Existing saved jobs and exports remain untouched. Older linked Validation/Decision chains can
remain visible under existing currentness rules. A new Decision built from an old Validation can
still reflect that old verdict. Neither installing the patch nor passing isolated tests certifies
those chains. Before any later runtime activation, inventory affected chains and obtain explicit
approval for necessary reruns or a separately scoped compatibility guard.

No Docker/image work, migration, bulk revalidation, method-version rollout, report rewrite,
commit/push or deployment is included. Other audit findings retain their previous open or
inconclusive status.

The owner has approved the named three-file patch, disposable verification artifacts and final
verification record. Execution and isolated verification are complete; see the new verification record for actual results,
123 unavailable PostgreSQL cases, the unchanged seed-sensitivity xfail and compatibility limits.
Activation, commits/pushes and all other excluded actions still require separate authorization.
