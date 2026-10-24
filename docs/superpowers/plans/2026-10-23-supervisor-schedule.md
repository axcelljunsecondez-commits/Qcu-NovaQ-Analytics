# Supervisor schedule implementation plan

Specification: ../specs/2026-10-23-supervisor-schedule.md
Base 151486ee04147f013857f69fe8ce77d899388660; branch codex/supervisor-schedule-20261023.

1. Add a thin supervisor orchestration router using existing workflow DTOs/services. Register it; preserve existing routes. Add isolated behavioral tests of read-only preview, guards, concurrency refusal and confirmed persistence.
2. Add typed frontend API calls; extract the existing separate schedule evidence card; replace separate-only page controls with a focused supervisor component. Preserve the shared path and verified scenario save/selection behavior.
3. Add semantic-token responsive styles and symmetric EN/TL strings. Add behavioral UI tests for the new workflow; keep existing shared regressions.
4. Execute focused tests, then backend/frontend repository gates; fix in-scope defects without weakening analytical expectations. Docker is unavailable at initial inspection, so native PostgreSQL verification is not yet established.
5. Run local browser verification with isolated fixtures (never live account mutations). Write a verification record with exact commands/results, known limits and file list. No commit/push/deployment.

Permitted files: these spec/plan and one final verification record; new backend/api/supervisor_schedule.py; backend/api/main.py router registration only; new focused backend tests; frontend/src/api/optimization.ts additive types/functions; frontend/src/pages/OptimizePage.tsx separate-path extraction; new supervisor screen/evidence component and tests; frontend/src/styles/global.css scoped rules; EN/TL translation JSON. Output-only local QA files remain untracked.

## Verification execution refinement
The initial monolithic backend run was progressing slowly with temporary SQLite databases on Windows. The full test-file set will also be run in four isolated process partitions (no new dependency), with a saved file manifest and JUnit results so coverage, counts, skips and failures are auditable. This changes test scheduling only. An incomplete original run is not a passing result.

The broad frontend run identified SetupChangeWorkflowCache.test.tsx as a dependent integration test: its existing no-stale-evidence assertions must be preserved while its mocked API/buttons are migrated to the approved supervisor flow. This test file is included in scope. A separate added backend test initially expected a stale Decision without any prior Decision; its fixture is corrected to include the prior selection/Decision as in the established legacy test.

## Approved tabs follow-up

1. Implement the approved one-panel tabs amendment in the existing supervisor component; retain form/result state and persistence guards. Move final save actions to Confirm, replacing the modal with this explicit confirmation panel.
2. Adapt behavioral tests and the dependent cache-test navigation without removing its evidence invalidation assertions. Add focused navigation, hidden-panel, keyboard, draft-retention and prerequisite cases.
3. Run frontend tests, typing, lint and production build; inspect the compiled local flow against an isolated synthetic API, including actual apply and scenario save/selection. Reuse the earlier backend record only for unchanged backend files; identify it as earlier evidence. Record fresh outcomes and limits. No commit/push/rebuild/deploy.
