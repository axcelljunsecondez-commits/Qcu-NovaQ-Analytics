# Shared model-choice relocation plan

Owner-approved scope: [spec](../specs/2026-10-30-shared-simulation-model-choices.md).
Starting HEAD: `007f59242c94f4340e9bc0d013b923cea3aa3ca7` on
`codex/shared-queue-workflow-20261029`. Existing untracked local artifacts retained.

1. Record source/protected/input baseline and current contracts.
2. Add Simulation model-choice editor using existing GET/PATCH and approved labels.
   Merge edited fields into a fresh Setup; refresh all dependent evidence; handle
   errors, pending saves and analysis changes without inventing supported models.
3. Move shared upload choices out of Data and Setup. Defer unresolved answers as
   explicit unknown through the unchanged API; retain known-number safety guards
   and link their repair to Simulation Advanced. Retain optional closing control.
4. Replace remote refusal navigation with a local Advanced/focus action. Preserve
   compatibility, selected-plan, stale-run, limits and automatic-repetition guards.
5. Update meaningful regressions for authorized behavior and new local editor.
   Execute scoped API regressions and full frontend/type/lint/build gates; record
   old-output root-tool failures without changing unrelated config or protected tests.
6. Verify actual isolated browser behavior with owner CSV and saved settings,
   record protected/locale hashes, report exact status and remaining limits.

Expected application files: AnalysisSetupPage, MissingChoices, sharedAggregateSetup,
ContinuousRun, new Simulation model editor, associated frontend regressions. Existing
backend/API contracts, mathematics, package manifests and wording registry are frozen.

Implementation and source validation completed: 817 frontend tests / 93 files,
frontend type/lint/build, 73 scoped backend regressions, isolated API and owner-CSV
browser run. All 96 backend files, 45 protected paths and both locales are unchanged.
Run also blocks unsaved drafts until Save or Cancel. Five automatic replications,
engine support boundaries and stale-plan checks are unchanged. Whole-repository
tool failures and local Docker status are explicitly recorded in the
[verification report](../reports/2026-10-30-shared-simulation-model-choices.md).
