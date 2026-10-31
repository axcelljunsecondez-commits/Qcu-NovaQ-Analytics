# Shared-queue plan selection and blocked-run recovery

Date: 2026-10-29. Scope: owner-requested diagnosis and bounded frontend repair from five
supplied screenshots, on local branch `codex/shared-queue-workflow-20261029`.

## Evidence and requirements

- REPORTED: a first saved plan appears unusable until a second save. The existing isolated
  diagnostic exercised Save/Use this plan, not this exact Results selector sequence. Persistence
  failure is UNKNOWN until independently reproduced; do not insert a speculative backend fix.
- VERIFIED from source: `PlanChanges.Switcher` disables the action when the draft id equals
  the backend-selected id, but displays no selected-state explanation. The screenshots show
  this pattern: one displayed selected plan with a disabled action; another choice enables it.
- VERIFIED from source: Switcher initializes its draft from selectedId only at mount. A change
  to the authoritative selected id, analysis or available options can leave that draft stale.
  Reproduce the observable inconsistency before changing this behavior.
- VERIFIED from screenshots: full-day run is disabled, hours display unavailable, and the
  capacity/abandonment refusal is visible. VERIFIED from `shared_continuous._setup_reasons`
  and `_row_reasons`: finite capacity, modeled abandonment, or supplied K/theta may cause
  that code. The exact saved setup and normalized inputs of the owner's analysis are UNKNOWN.
- VERIFIED from source: Named Shared Queue requires explicit demand, staffing, employee
  availability, roster, shift/break rules, closing policy, repeats and seed. It is a distinct
  configured workforce simulation. The supplied aggregate CSV does not contain the roster.

## Expected observable outcome

1. An eligible plan saved once remains available for selection. Tests must distinguish the
   server-selected plan from a local dropdown choice and from a merely saved plan.
2. The Results selector stays consistent with the active analysis and authoritative selection.
   Removed drafts must not silently display another option while targeting a missing id.
3. A current, usable selected plan is clearly identified using the existing approved
   `compare.selected_for_simulation` wording. Preserve the existing disabled no-reselect
   behavior; do not create duplicate selection evidence just to enable the button.
4. A capacity/abandonment refusal offers an explicit link back to Data and Setup using an
   existing approved locale key. Unsupported input continues to be refused. Do not change
   the operator's setup automatically or direct them to enter inaccurate assumptions.
   When this early gate withholds the horizon, display the hours as unavailable using
   existing locale strings; a withheld horizon does not prove hours were never set.
5. Explain Named Shared Queue's actual inputs and sequence in the report/user handoff. No
   automatic roster, employee, sample, cost or requirement is generated from the averages CSV.

## Scope and safety boundary

Editable implementation: `PlanChanges.tsx`, relevant `ResultsPage.test.tsx` tests, and
`ContinuousRun.tsx` / `QueueSimulationPage.test.tsx` for the recovery link. Only if a separate
test reproduces the save-list defect may the responsible `OptimizePage.tsx` or
`useSelectedPlan.ts` code and its tests be edited. Chrome owns these frontend files; root
owns this specification, implementation plan, final report and isolated verification files.

Reuse existing approved EN/TL keys. New product wording is owner-controlled by Chrome's
role; no new or rewritten locale text is authorized by this specification. Preserve
`wordingPolicy.test.ts` and the approved wording records.

No backend/API/schema/mathematics, auth/Home, numerical output, model selection, data
normalization, evidence/provenance, Decision/report rules or deployment changes. Full-day
finite-capacity/abandonment support would require a separate analytical specification and
explicit mathematical authorization. Existing unknown/unsupported states remain visible.

## Verification

- Reproduce relevant selector failure with behavioral tests before fixing it.
- Verify first saved plan, selected state, switching plans, external selection/analysis changes,
  removed options, stale plans and failed-selection retry where affected.
- Verify the recovery link on the existing capacity/abandonment refusal and retain refusal.
- Run frontend tests, typecheck, lint, build, wording policy and actual browser walkthrough
  with the owner's unchanged CSV in a disposable local database.
- Backend behavior remains unchanged; execute its focused refusal/continuous preview tests
  as regression evidence. Full backend gates are not relabeled as newly run.
- Existing Docker and live authenticated state remain separate verification targets. Do not
  infer production behavior from the disposable browser run.
