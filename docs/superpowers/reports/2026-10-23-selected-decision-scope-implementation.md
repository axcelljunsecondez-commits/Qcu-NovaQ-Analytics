# Selected Separate Decision: local implementation and verification

Date: 2026-10-23. Status: COMPLETE for the approved wording/context correction and its local verification. SEED-001 remains OPEN. Production deployment remains NO-GO under the owner's repair-first instruction.

## Authorization and candidate

The owner approved the prepared specification and implementation plan. This authorizes the bounded Phase-A correction, not numerical/statistical integration or deployment.

- Candidate: `C:/Users/Administrator/.codex/worktrees/novaq-release/NovaQ`.
- Branch: `codex/supervisor-schedule-20261023`.
- HEAD, unchanged: `151486ee04147f013857f69fe8ce77d899388660`.
- Primary checkout main, distinct and unchanged: `6093d78a5874d8cbdfa0026e9c25bdb5ddc70881`.
- GitHub main and production were NOT inspected in this phase. Local test results do not establish their state.

Evidence directory: `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/output/decision-scope-implementation-20261023/`. The filenames below refer to this directory unless a repository path is given.

## Actual corrections

| Finding | Implemented behavior and source | Disposition |
|---|---|---|
| CONTEXT-001 | `frontend/src/components/analysis/DecisionEndpointPage.tsx:48` passes the actual Separate context. `components/decision/DecisionEndpoint.tsx:60` uses selected root periods and selected lane-period check counts. `lib/decisionPlain.ts:34` uses Separate-specific revise copy. Shared cost/overload messages are preserved. | CLOSED locally for the specified context defect. |
| SCOPE-001 | Selected recommendations in `backend/api/workflow.py:3365` and `:3395` qualify the saved run and ask for review of estimated loads/costs. A visible localized notice outside Details appears on standalone Decision, selected Checks and full Separate Reports. Conditional Separate checks use the existing warning style. | CLOSED locally for the approved interpretation/disclosure scope. |
| Report consistency | `backend/reports/selected_scope.py:6` supplies a current interpretation note. `full_report.py:189` and `separate_report.py:324` add it to final Separate view models. `report_pdf.py:178`, `report_export.py:283` and `:509`, and `plan_report.py:460` render it adjacent to Decision text or append it after existing Excel Decision rows. An identical note already present in saved wording is not duplicated. | VERIFIED in both final Separate report paths. |
| SEED-001 | No statistical correction was integrated. The original strict-xfailed regression executed as XFAIL in the full backend suite. | OPEN; not a passing seed-stability test. |

The notice distinguishes load variation around a simulation average from uncertainty in that estimated average. It does not invent an uncertainty interval or a new validator state. No offline 57/3 result or hardcoded research pair was imported into a live analysis.

Old saved wording, raw statuses, facts, evidence IDs and numerical results are preserved. New selected Decisions receive qualified recommendation text. Shared/basic/data-only outputs retain their existing behavior. Missing/currentness/ownership/conservation gates are unchanged.

## Exact source scope and preservation

`source-integrity.json` and `implementation.diff` compare the pre-edit candidate against the final source, independently of earlier supervisor changes. There are 22 changed existing source/test/configuration files and one new source file, `backend/reports/selected_scope.py`. The full list and SHA-256 values are in the integrity record and artifact manifest.

The existing-file scope consists of six backend workflow/report files; both locale JSON files; frontend workflow/report typings, DecisionEndpointPage, DecisionEndpoint, ChecksView, decisionPlain and ReportsPage; and seven existing backend/frontend test files. No new test module or application component was required.

Of 467 baselined files, 445 are byte-identical. The workflow module's AST is identical after replacing only selected-Decision recommendation expressions with a comparison marker. All numerical rules, branches, status precedence, RNG handling, run limits, DES/MC/model/optimizer/statistics code, API gates, fixtures and the strict seed regression are unchanged. Unrelated locale values and all existing supervisor implementation files are preserved; EN/TL keys remain symmetric. Seed 42 remains unchanged in the relevant application configuration.

## Executed checks

| Gate | Actual result | Evidence |
|---|---|---|
| New consumer regressions before correction | 4 expected failures, 8 excluded by the name filter; reproduced Shared text and missing selected detail | `context-before-retry.log` |
| Focused backend Decision/validation/report tests | 105 passed; exit 0 | `backend-focused-final.log` |
| Focused frontend consumers | 91 passed; exit 0 | `frontend-focused.log` |
| `python -m pytest tests/ -x --tb=short` | 3,288 passed, 125 skipped, 1 xfailed, 9 subtests passed, 1 warning; exit 0; 980.99 seconds | `backend-full.log` |
| `npm test` | 711 passed in 84 files; exit 0 | `frontend-full.log` |
| `ruff check .` | All checks passed; exit 0 | `ruff.log` |
| `mypy .` | No issues in 242 source files; exit 0 | `mypy.log` |
| Frontend typecheck, lint and local build | All passed; combined execution returned CHECK_EXIT=0 | `typecheck.log`, `frontend-lint.log`, `build.log` |
| Compiled real-browser matrix | 48 cases passed: Decision/Checks/Reports x EN/TL x light/dark x 375/768/1024/1440. Notice wraps without page overflow, remains outside closed Details, and Details keyboard interaction works. Minimum measured notice contrast 6.2075:1. No JavaScript page errors, browser writes or evidence changes during the matrix. | `browser-matrix-result.json`, original `.log` and script |
| Actual phone viewport visibility | 6 cases passed across the three screens in EN/light and TL/dark at 375 px. After scrolling the note into view, top/middle/bottom hit tests confirm it is unobscured. | `browser-mobile-result.json`, `viewport-*.png` |
| Export preservation | Both final Separate PDF/Excel paths tested. Notice occurs once; original saved fields preserved. Every pre-existing workbook cell value/formula and sheet order compares equal with/without the appended note using an identical report model. New row wraps and has an explicit/automatic usable height. Export makes no engine call and leaves evidence unchanged. | Focused/full backend suites, especially `tests/test_separate_report.py:150` and `tests/test_b8_full_report.py:154` |
| PDF visual review | Synthetic B8 PDF has 4 pages; scope note is on page 3. Rendered Decision page reviewed: note is readable and unclipped. | `SYNTHETIC-scope-full.pdf`, `pdf-decision-page-3.png` |
| Source/Git review | Protected-source comparison passed; final diff reviewed. HEAD unchanged, staging empty, tracked diff whitespace check passed. | `source-integrity.json`, `implementation.diff`, `git-check.json` |

Skipped tests are NOT passed tests. No additional PostgreSQL or native application result is inferred from this run. The retained seed XFAIL remains a defect record.

## Test boundary, failures and cleanup

Browser verification used the compiled candidate and real API through a new loopback-only server on port 5193, backed by a new synthetic SQLite database. Its selected DES and MC evidence both use seed 42. It is not production analysis 18 or a reproduction of historical paper jobs. File examples are explicitly named SYNTHETIC.

Failures encountered and resolved are retained in the evidence:

1. The first frontend attempt could not write Vite's cache outside the sandbox. The normal reviewed execution path succeeded; this was not a test pass or an unsafe-action rejection.
2. An inserted test initially stranded existing assertions in the next function, causing a NameError (72 passed, 1 failed). The assertions were restored to their original test without weakening them.
3. A workbook comparison initially compared different HTTP generation timestamps (93 passed, 1 failed). The layout-preservation comparison now uses one identical model; actual HTTP files and unchanged evidence are checked separately.
4. Browser harness attempts hit Windows argument quoting and an incorrect assumption that light mode always sets a data-theme attribute. The documented file-input option and the source-verified default-light convention resolved these harness issues. No application code changed for them.
5. Full-page mobile screenshots raised a concern about fixed-element overlap. Actual viewport screenshots and element hit tests confirmed that the new note is unobscured after scrolling it into view. This does not certify every existing mobile layout or establish the cause of full-page capture differences.
6. Cleanup initially saw both a Python launcher and interpreter and stopped before terminating anything. The actual port owner's command line was then matched to this task's fixture script and that verified server PID alone was stopped. The dedicated browser was closed. Existing NovaQ stacks were untouched. `local-cleanup.json` records the result. The synthetic DB/artifacts are retained as local evidence.

Warnings retained: deprecated AnyIO alias; existing mypy unchecked-function notes; jsdom canvas support messages; Vite large-chunk/plugin-time warnings; Poppler Symbol/ArialUnicode display-font warnings. The rendered Decision page remains legible. None is presented as a newly resolved finding.

## Remaining status

- COMPLETE: approved disclosure/context correction and bounded local verification.
- OPEN: numerical seed sensitivity. This implementation does not establish a useful, justified numerical repair, seed stability or operational safety.
- NOT TESTED here: native Excel/manual checks, native-language certification, PostgreSQL-specific skipped cases, live account behavior and production cutover. PDF/Excel file checks do not close native Excel verification.
- No commit, push, Docker rebuild, activation, schema migration or deployment was performed. Only the local frontend static build required for browser verification ran.
- No application scope deviation. Temporary test harness/fixtures and documentation records support the approved verification.

GO for accepting this local Phase-A correction. NO-GO for deployment under the repair-first requirement. A later release-scope change would need explicit owner acceptance and release gates; it would not prove SEED-001 repaired.
