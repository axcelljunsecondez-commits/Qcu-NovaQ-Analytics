# Plan: shared-line Many variations at the plan's target

Spec: `docs/superpowers/specs/2026-10-29-shared-mc-plan-target-threshold.md`. Base `3ee8fe2c`. Not committed, not pushed.

File scope (only these): `backend/api/workflow.py`; `tests/test_shared_mc_plan_target_threshold.py` (new); `tests/test_selected_mc_load.py` (rename/adjust the 0.75 scope-guard test); `frontend/src/components/queueSimulation/ChecksView.tsx`; `frontend/src/api/workflow.ts` (make `failure_threshold` optional on `runWorkflowMc`); `frontend/src/pages/QueueSimulationPage.test.tsx`; these two docs. Not touched: `separate_optimization.py`, `shared_replications.py` (owned by another session), the MC engine, locales.

1. RED backend: write `tests/test_shared_mc_plan_target_threshold.py` (spec §9 R1-R8). Run; R1, R2, R4, R6, R7 must fail on the current code (threshold 0.75, no source).
2. GREEN backend:
   - Add `_resolve_mc_failure_threshold(payload, target) -> (float, source)` and use it in `run_selected_mc` (same behaviour) and `run_mc`.
   - Add `_shared_plan_target(scenario)` per spec §4.2.
   - `run_mc` takes `SelectedMcRequest`; store `failure_threshold` and `failure_threshold_source` in params.
   - Adjust the scope-guard test: `/mc/current` (WorkflowMcRequest) stays 0.75; shared `/mc` uses the optional request.
3. RED frontend: in `QueueSimulationPage.test.tsx`, a shared plan with target 0.7 omits `failure_threshold`, a changed box sends it, no target keeps 0.75.
4. GREEN frontend: `LegacyPlanChecks` passes `planTarget` to `useMcSettings` and `McFields`, and omits the field when it equals the target.
5. Gates: `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`; in `frontend/`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`.
6. Report the diff, results and OD-T1 to OD-T4. No commit.

Status 2026-10-29: steps 1-6 done (uncommitted). OD-T1 to OD-T4 decided by the owner (recommended options, spec §8); no further code change needed. Release note in spec §10. Remaining: owner approval to commit; release is a separate step.
