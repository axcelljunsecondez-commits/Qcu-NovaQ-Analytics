# Selected Separate-plan Validation and Decision: two bounded corrections

Date: 2026-10-19\
Status: **APPROVED SPECIFICATION; two corrections implemented and approved isolated verification COMPLETE.**\
Scope: audit findings SEV-001 (rounded-rate comparison) and SEV-002 (passed-check count), only.

## 1. Authorization and governing context

The owner's original document request was: "Prepare the correction specification for those two bugs only."
This authorizes preparation of this document, not source/test edits, application test execution,
new simulations, database writes, report replacement, Docker actions, commits, pushes, or deployment.

The subsequent owner reply "approve" approved this specification. The owner then explicitly
approved "implementation of the two corrections and isolated verification under this plan".
That execution is governed by `../plans/2026-10-19-selected-validation-decision-corrections-plan.md`;
activation, commits, pushes and deployment remain excluded.

Governing references:

- Repository `AGENTS.md`, Mandatory Zero-Fabrication Engineering Protocol.
- `C:/Users/Administrator/Downloads/NOVAQ_STATISTICAL_EVIDENCE_AUDIT.md`, especially sections 3, 6, and 7.
- The read-only audit returned in this chat, findings SEV-001 and SEV-002. There is no audit-report
  file being created or implied by this reference.
- `docs/superpowers/specs/2026-09-17-separate-mc-validation-semantics.md`, sections 1, 2, 5, 6, 7, and 9.
  Its initial implementation-status statements describe its historical freeze, not today's source.

Only the two explicit amendments below are approved as a specification. Existing precedence, identity, statistical
method, thresholds, and ownership/currentness contracts otherwise remain authoritative.

## 2. Inspected checkout and evidence

All repository paths below are relative to this exact audited worktree:

`C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/.claude/worktrees/ux-workflow-audit`

- Branch: `feat/ux-u1-shell`.
- HEAD: `0b9423ec66d32620ed91769ac35a10e51ffae2ec`.
- Source is the working tree, including existing uncommitted work, not HEAD alone.
- Preparation baseline: 868 Git-visible files, aggregate path/content SHA-256
  `de9a33b3d7dddae47014aa38f1a8841163868e838c336d2551d517b75202ca2c`.
- Preexisting working-tree changes are unrelated and must be preserved.

Line references describe this preparation snapshot and must be refreshed before implementation.

| Evidence | Verified source fact |
|---|---|
| `backend/queueing_engine/simulation/simulation.py:1297,1337-1340` | MC calculates `failures / num_trials`, stores a four-decimal rate plus exact integer `failure_count` and `trials_completed`, and derives raw PASS/FAIL from the unrounded fraction. |
| `backend/api/workflow.py:145-157` | MC accepts up to 100,000 trials; selected threshold can be omitted in favor of the plan target. |
| `backend/api/workflow.py:1291-1341` | `_separate_validation_verdict` currently compares the stored rate against the cap. |
| `backend/api/workflow.py:1599,3151,3173` | The helper is shared by Current Separate validation and both selected per-period and overall aggregation. A global behavior change would exceed this scope. |
| `backend/api/workflow.py:3231-3251` | Selected Validation reads persisted MC rows directly and creates a new linked validation job. |
| `backend/api/workflow.py:3256-3301,3344-3358` | Selected Decision records inadequate counts but subtracts only failed checks when stating how many passed in its failure branch. |
| `backend/reports/full_report.py:173-184` | The full-report check summary already subtracts both failed and inadequate counts. No report fix is needed for this counting formula. |
| `tests/test_selected_plan_validation.py:35-38,284-290` | Existing synthetic helpers omit completed-trial counts; one hardcodes zero failures independently of the requested rate. Valid exact-count fixture construction must be explicit. |
| `tests/test_separate_validation_current.py:35-76` | Current-path tests exercise the helper's existing behavior, including rows without exact counts. |

### 2.1 Reproduction refreshed during specification preparation

VERIFIED using current AST-extracted pure functions in memory, with synthetic inputs:

1. `k=5001`, `n=100000`, cap `0.05`: `k/n=0.05001`, stored rate `0.05`.
   Raw MC rule gives FAIL; the current Validation function gives `pass` when support and adequacy
   are true. These inputs establish the rounding defect, not an observed production run.
2. Total checks 3, failed 1, inadequate 1: the current Decision remains `revise` but states
   "Validation: 2 of 3 checks passed." The correct passed count is 1.

Execution used inline stdin with
`C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/.venv/Scripts/python.exe -B -X utf8 -`.
Only function ASTs and required standard-library names were loaded; no application imports,
pytest execution, MC/DES execution, or database operations occurred.

## 3. Intended observable outcome

- A newly calculated selected Validation verdict uses exact recorded MC counts for its cap
  comparison, even when the display-rounded rate equals the cap.
- For valid supported adequate evidence, selected row PASS/FAIL agrees with the existing raw MC
  rule at the same recorded cap. This is configured-run consistency, not a new reliability claim.
- A newly derived selected Decision excludes inadequate checks from its passed count.
- Decision taxonomy and FAIL > insufficient > PASS precedence remain unchanged.

These corrections do not repair seed sensitivity, prove operational safety, reproduce the original
paper result, or close any other finding from the statistical audit.

## 4. Correction A: exact selected Validation comparison

### 4.1 Selected-only implementation boundary

APPROVED SPECIFICATION: extend the private `_separate_validation_verdict` helper with a keyword-only
`use_exact_counts: bool = False` option, or an equivalently narrow internal mechanism with the
same acceptance criteria. This is not a public API parameter.

- Current Separate validation keeps the default legacy behavior.
- `validate_selected_plan` explicitly requests exact-count behavior for BOTH the per-period call
  and the overall call. Correcting only one call is unacceptable.
- Do not duplicate the aggregation algorithm, change the Current caller, or alter shared-line
  validators. No new engine/statistical module is needed.

### 4.2 Exact-count requirements

For selected-only evaluation, a usable count pair has:

- `failure_count` and `trials_completed` as integers; booleans are not integers for this contract.
- `trials_completed > 0`.
- `0 <= failure_count <= trials_completed`.

Preserve the existing required-row identity, DES completeness/conservation, support, finite-rate,
and adequacy gates. Exact counts do not override an unsupported or inadequate row.

For a row passing those gates, compare:

`comparison_rate = failure_count / trials_completed`

with the actual persisted `failure_rate_cap`:

- `comparison_rate > cap` => `fail`.
- `comparison_rate <= cap` => `pass`.

Do not round before comparison; do not add epsilon, clamp the fraction, change the cap, use a CI
endpoint as the decision rule, or substitute the cached raw status for exact count evidence.
This is the same fraction/comparison used by the existing MC producer, not a new statistical method.

Keep existing response keys/types and display-rate values unchanged. The stored display-rounded
`failure_rate` and returned `mc_failure_rate` remain presentation values, not the comparator.
No new response field or persisted method marker is proposed in this bounded correction.

### 4.3 Missing, malformed, and legacy selected rows

APPROVED SPECIFICATION: a selected row lacking a usable exact count pair is `inadequate`.
There is no fallback to its rounded rate, raw PASS label, a reconstructed count, a default trial
count, zero, or another lane's evidence. Existing aggregation then produces insufficient evidence
unless another valid required row fails.

This is the explicit selected-only compatibility amendment approved with this specification. A legacy row
with valid recorded counts can be evaluated without rerunning MC. If counts are absent, rerunning
Validation alone cannot recover them; new MC evidence would require separate execution approval.
Current Separate rows without counts retain their existing behavior.

### 4.4 Required reference cases

All PASS/FAIL cases below assume supported, adequate evidence and a cap of 0.05.
Reported rates follow the existing four-decimal producer rounding.

| Failures k | Completed n | Unrounded fraction | Rounded display | Required selected verdict |
|---:|---:|---:|---:|---|
| 4999 | 100000 | 0.04999 | 0.0500 | pass |
| 5000 | 100000 | 0.05000 | 0.0500 | pass |
| 5001 | 100000 | 0.05001 | 0.0500 | fail |
| 5004 | 100000 | 0.05004 | 0.0500 | fail |
| 0 | 2000 | 0 | 0 | pass |
| 2000 | 2000 | 1 | 1 | fail |

Also require inadequate results for missing/null counts, strings, floats in integer fields,
booleans, nonpositive n, negative k, and k > n. Preserve inadequate results when support or
adequacy fails even if valid counts would otherwise pass.

Use explicitly synthetic fixtures with stated k and n. Existing success/failure fixture helpers
may be made internally consistent for this approved input contract; do not weaken expected
verdicts, remove assertions, alter production fixtures, or hide legacy tests by injecting defaults.
Keep explicit count-less fixtures to verify the new selected legacy behavior and unchanged Current
behavior. Add multi-period/queue cases proving exact counts reach both aggregation levels.

## 5. Correction B: count only actual passed checks

For a valid selected validation verdict with total N, F failed identities, and I inadequate
identities, the failure-branch rationale must use:

`passed = N - F - I`

N, F, and I count required `(time, queue_id)` checks, not periods. The existing producer makes
these categories disjoint. Do not add a general verdict-normalization/refactoring project here.

Change only this passed-count calculation in `_derive_selected_decision`. Preserve headline,
recommendation rules, failed/inadequate identities, recorded facts, missing-evidence behavior,
cost caveat, ownership checks, and the existing fallback for non-integer total.
Do not clamp an inconsistent negative count to manufacture a successful explanation; if malformed
verdict handling requires a broader change, stop and report it outside this specification.

| N | F | I | Required passed count | Decision |
|---:|---:|---:|---:|---|
| 3 | 1 | 1 | 1 | revise |
| 3 | 1 | 2 | 0 | revise |
| 3 | 1 | 0 | 2 | revise |
| 3 | 3 | 0 | 0 | revise |

Regressions must preserve all-pass => conditional, insufficient-only => insufficient evidence,
and failed conservation => insufficient evidence. Separate `adopt` remains unreachable without
the existing comparable Current cost basis. This amendment adds no new user-facing string.

## 6. Persistence, readers, and historical limitations

- Do not update or reinterpret any stored MC, Validation, Decision, trace, report, or export.
- The behavioral correction applies when selected Validation is newly evaluated, and the
  explanation correction applies when selected Decision is newly derived.
- A newly derived Decision consumes its linked stored Validation verdict; it does not rerun or
  silently correct an older Validation. Corrected end-to-end verification therefore requires a
  fresh Validation followed by a fresh Decision against the same approved evidence chain.
- Existing GET/currentness/report readers remain unchanged. Consequently an older linked chain
  can remain visible under existing currentness rules; it is not certified by installing a fix.
  This known compatibility limit must appear in any implementation/release report.
- This specification does not approve activation over existing data or automatic invalidation.
  Before any later activation, identify affected stored chains and obtain explicit approval for
  the required reruns or a separately scoped compatibility guard. Do not silently expand scope
  into versioning, migration, bulk revalidation, or report-reader changes.

Readers inspected: `create_selected_decision` (`workflow.py:3399-3487`), workflow evidence/currentness
(`workflow.py:1193-1262`), `_selected_report_chain` (`backend/api/reports.py:153-224`), and
`separate_full_sections` (`backend/reports/full_report.py:167-193`). They consume stored results.
No edits to these readers, frontend types, locales, or report writers are proposed.

## 7. Permitted future implementation file scope

Implementation and isolated verification are now authorized under the plan. The edit allowlist is:

1. `backend/api/workflow.py`: helper's selected-only comparator, the two selected call sites, and
   the selected Decision passed-count expression; necessary adjacent comments only.
2. `tests/test_selected_plan_validation.py`: exact-count boundaries, malformed/legacy rows,
   both aggregation levels, consistent synthetic helpers, and API persistence/provenance checks.
3. `tests/test_selected_plan_decision.py`: mixed-category count cases and unchanged taxonomy.

No other existing file is an implied edit target. If another fixture/reader must change, identify
the exact reason and request a scope amendment before editing it. Preparing an implementation plan
under `docs/superpowers/plans/` is a later step, not a plan file created by this request.

Explicitly excluded: Hoeffding/t/bootstrap integration, selected-load replication guards, new
precision rules, seed-sensitivity repair, threshold/trial/replication changes, queueing mathematics,
DES/RNG/first trace, optimizer/cost behavior, Current/shared semantics, API shapes, schemas,
engine-version bumps, UI redesign/labels/translations, reports, manuscript edits, Docker, Git
commits/pushes, and production actions. Seed 42 means positive integer 42 and is unchanged.

## 8. Verification gates and execution record

No application tests or gates were run during specification preparation. The subsequently authorized
implementation and isolated verification are complete; actual results are recorded in
`../reports/2026-10-19-selected-validation-decision-corrections-verification.md`.

After implementation and isolated test execution are separately authorized:

1. Run focused selected Validation and Decision tests, including all cases above.
2. Run existing `tests/test_separate_validation_current.py` unchanged to prove the default helper
   path still supports its existing contract. Also exercise the selected/default distinction.
3. Run existing selected-load, model-aware workflow, and report/provenance regressions:
   `tests/test_selected_mc_load.py`, `tests/test_model_aware_workflow.py`,
   `tests/test_separate_report.py`, `tests/test_b8_full_report.py`, and `tests/test_reports_api.py`.
4. Run the repository-required backend suite and lint/type gates: `python -m pytest tests/ -x --tb=short`,
   `ruff check .`, and `mypy .`. Account for unrelated preexisting changes explicitly.
5. Complete the repository's frontend gates before any application-completion claim:
   `npm test`, `npm run typecheck`, `npm run lint`, and `npm run build`, from `frontend/`.
   This does not imply frontend edits or native/browser verification.

Test isolation must be reviewed before execution. `tests/conftest.py:35-62` normally uses temporary
SQLite databases but uses Postgres and creates/drops schemas when `NOVAQ_TEST_DATABASE_URL` is set.
The later plan must name fresh disposable output/cache paths, verify that variable is absent for
the SQLite run, and never use the application database. Do not claim tests are read-only.

The existing strict xfail for seed sensitivity must remain untouched. Passing a suite with that
xfail does not close the statistical finding. Do not change trial budgets, seeds, or thresholds
to make it pass. Light/dark, native Excel, production and operational validity remain outside these
two corrections and must not be reported as verified by backend tests.

## 9. Acceptance and handoff

Acceptance requires actual execution evidence for:

- Exact selected verdicts at cap equality and on both sides of the rounding boundary.
- No required selected row with unusable exact counts becoming PASS.
- Identical selected per-period/overall comparison semantics and preserved identity/precedence.
- Unchanged default Current helper behavior and unrelated shared behavior.
- Correct mixed-category passed counts with unchanged Decision status.
- Unchanged producer MC outputs, Wilson/adequacy rules, settings, protected files, historical
  evidence and existing exports.
- A final diff limited to the approved files and an explicit executed/failed/not-tested report.

Current execution state: both defects were reproduced before the source patch. Both source
corrections and approved isolated verification are complete: 79 focused tests passed; wider tests
passed 55 with one existing xfail; the full backend passed 3270 tests and 9 subtests with 123
PostgreSQL skips and one unchanged seed-sensitivity xfail; the full frontend retry passed 683.
Required lint/type/build gates, diff review and protected-file/Git preservation checks passed.
The new verification report retains failed/interrupted attempts, evidence paths and remaining limits.

This is not a runtime repair, source commit, deployment or closure of other statistical findings.
Activation, commits, pushes and deployment remain separate authorization steps.
