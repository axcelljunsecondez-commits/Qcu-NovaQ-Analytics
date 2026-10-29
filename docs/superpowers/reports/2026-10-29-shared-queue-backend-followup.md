# Shared-queue backend follow-up — 2026-10-29

Status: COMPLETE for this bounded local backend diagnosis. No backend defect was reproduced
and no backend application repair was applied. The owner's existing authenticated runtime,
saved setup and production database remain unverified.

Branch: `codex/shared-queue-workflow-20261029`, HEAD `e2dbe5d57f859644849a5c445fceb099ff15bfa9`.
The four frontend repair files retain the exact hashes saved by the earlier repair.

## Verified findings

1. `backend/api/scenarios.py:create_scenario` validates calculation provenance, commits and
   refreshes the Scenario before returning it. `list_scenarios` reads the committed owned
   records for the requested analysis; `scenario_out` uses the shared eligibility evaluator.
2. A single real optimization/snapshot save using the supplied CSV returned 201 with
   `verified_snapshot` provenance and `CURRENT` evidence. Three immediate list reads and a
   detail read returned that same current plan. Database counts after the first selection
   were exactly one Scenario and one `workflow_selection` Job. No second save was needed.
3. `backend/api/workflow.py:select_scenario` uses `_own_verified_scenario_and_dataset` before
   persisting selection evidence. The immediate workflow read-back named the selected plan.
   The existing ownership, CSRF, immutable-snapshot and stale-evidence regression cases passed.
4. Current and Suggested full-day requests each persisted successfully with five repeats and
   seed 42. Reloaded runs retained their source dataset/scenario identity, reported customer
   conservation, and regenerated replication-0 playback for the CSV's 13 periods. These are
   actual execution/provenance checks, not an independent proof of every queueing calculation.
5. Under explicitly synthetic finite-capacity and modeled-abandonment configurations, the
   continuous compatibility endpoint identified the existing `capacity_or_abandonment`
   restriction. Create-run returned 422 `not_compatible`; the total Job count did not increase.
   No partial run was saved. Named contract eligibility also refused those configurations.
6. After replacing the planning dataset in the disposable workspace, the old plan reported
   `STALE_DATASET`, reselection returned 422, and the historical run remained readable with
   `dataset_is_current: false`. Its original input provenance was preserved.

The screenshot's capacity/abandonment warning corresponds to an existing engine-scope
restriction, not a newly established server crash. `shared_continuous._setup_reasons` and
`_row_reasons` enforce it; `create_continuous_run` refuses incompatible input before calling
the engine. Named simulation also requires unlimited capacity and abandonment not modeled.
No unsupported configuration was enabled or automatically rewritten by this follow-up.

## Actual execution

- PASS: **147 tests**, 258.96 seconds, exit 0:
  `.venv/Scripts/python.exe -m pytest tests/test_scenarios_api.py tests/test_scenario_integrity.py
  tests/test_scenario_evidence_status.py tests/test_workflow_api.py
  tests/test_b4a_continuous_preview.py -x -q --tb=short --basetemp
  output/shared-queue-backend-followup-20261029/pytest-main`.
- PASS: **14 selected Named API tests**, 134 deselected, 40.97 seconds, exit 0:
  `tests/test_api_shared_named.py -k 'ineligible_setups_are_refused or
  unsupported_dataset_rows_fail_at_the_demand_stage or
  a_dataset_that_was_not_processed_is_refused'`, using the same Python/pytest invocation
  and a separate workspace-local basetemp. The tests also verify no engine call/run record
  is left when those inputs are refused.
- PASS: **37 HTTP checks**, additional database/provenance assertions, exit 0:
  `.venv/Scripts/python.exe output/shared-queue-backend-followup-20261029/probe.py`.
  The saved JSON result says `passed` and records all statuses and expected refusal details.
- Both pytest runs emitted the same existing Starlette/AnyIO deprecation warning; no tests
  failed. Execution used approved operation outside the Windows sandbox because the earlier
  sandbox blocked FastAPI TestClient's local socket pair.
- Test databases were isolated SQLite fixtures. `NOVAQ_TEST_DATABASE_URL` was not set at the
  environment check; the probe explicitly created a unique local SQLite file. PostgreSQL and
  production behavior were NOT TESTED.
- The full backend suite, Ruff and mypy were NOT RERUN: this was a focused diagnosis with no
  backend source edits. The earlier 752-test frontend result is not relabeled as a fresh run.

## Input identity and limits

Dataset: `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/Daily data mmc/Avg_total_data_of_14_days.csv`.
SHA-256: `236fc05861b4a59ce3216c41fb52b3c529aec6b6f57003f610bd4cc3a91f938e`.
The unchanged input has aggregate `time,lambda,mu,c` rows for 13 hourly periods, 05:00–18:00.
Lambda and mu use the application's per-hour convention; the filename's 14-day averaging
method was not independently verified from underlying daily observations.

Supported diagnostic setup: shared queue, staffing varies by period, unlimited capacity,
abandonment not modeled, no breaks, DRAIN closing. Separate refusal fixtures used finite
capacity 20 or patience rate 0.5/hour, respectively. These were explicitly SYNTHETIC TEST
SETTINGS, not facts inferred about the owner's operation. No employee roster was invented.
The Named tests use their existing labeled synthetic fixtures; no run with the owner's real
employee roster is claimed.

## Modifications and preservation

Only this report, the bounded follow-up plan, and owned diagnostic artifacts were added.
No backend, tracked test, schema, API contract, mathematics, frontend or locale file changed
in this follow-up. A hash comparison verified all four earlier frontend repair files unchanged.
No operational database, Docker service, production setting, commit, staging or push action
was performed. There was no scope deviation.

Evidence: `output/shared-queue-backend-followup-20261029/` contains `main-tests.log`,
`named-gates.log`, `probe.py`, `probe.log`, `probe-summary.json`, the uniquely named
disposable database, and `frontend-preservation.json`.
Plan: `../plans/2026-10-29-shared-queue-backend-followup-plan.md`.

Remaining UNKNOWN: the exact backend request and stored setup of the owner's original
reported failure, deployment parity, PostgreSQL behavior, and any input combinations outside
these tests. Supporting full-day finite capacity or abandonment remains a separate analytical
feature requiring its own specification and authorization; passing this diagnosis does not
implement those models.
