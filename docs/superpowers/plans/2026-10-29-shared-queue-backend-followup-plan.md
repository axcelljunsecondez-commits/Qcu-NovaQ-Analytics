# Shared-queue backend follow-up

Owner request, 2026-10-29: follow up the screenshot issues in the backend and check for errors.
Branch `codex/shared-queue-workflow-20261029`, starting HEAD `e2dbe5d5`; the four verified
frontend repair files and existing reports/artifacts are preserved.

1. Trace actual save/commit/list, scenario eligibility/selection, continuous compatibility,
   run persistence and playback routes. Compare with the approved shared-queue specifications
   and existing scenario provenance tests. No app changes before a defect is established.
2. Execute the relevant existing scenario CRUD/integrity, eligibility, workflow, continuous
   preview and Named eligibility regressions with isolated databases.
3. With the owner's unchanged CSV, exercise a single save -> immediate list/detail -> selection
   -> workflow read-back -> current/suggested run -> persisted replay in a fresh test database.
   Separately exercise finite-capacity and modeled-abandonment refusals under explicitly
   synthetic test settings, and verify no run record is left on refusal.
4. If a responsible application defect is reproduced, first document exact failure, allowed
   file scope/contracts and regression; repair only within owner authorization. Changes to
   mathematical behavior, API contracts or schemas still require separate authorization.
5. Record actual results and remaining production/saved-runtime unknowns. No operational DB,
   Docker activation, deployment, commit, push or automatic setup changes. If no backend
   defect is established, report that bounded outcome rather than applying a speculative fix.
