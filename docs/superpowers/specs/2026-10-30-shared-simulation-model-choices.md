# Shared-queue model choices on Simulation

Status: IMPLEMENTED and source-verified locally. Docker activation is recorded in
the [verification report](../reports/2026-10-30-shared-simulation-model-choices.md).
Owner request and clarification,
2026-10-30: skip capacity/abandonment questions during upload; answer them in
Simulation Advanced settings; remove both controls from My analyses → Data and
Setup. Applies to the shared-queue flow being discussed.

## Behavior

- Shared aggregate upload sends explicit `unknown` for unresolved model choices
  using the existing apply contract. It does not assume Unlimited/Not modeled.
  Known saved settings and their required-number guards remain unchanged.
- Remove shared capacity/abandonment editing from Data and Setup, including its
  inline upload card and Advanced form. Keep the optional existing closing choice.
- Simulation Advanced settings contains the existing bilingual choices and
  conditional numeric inputs, saved through the existing analysis PATCH route.
  Refusal actions open these local controls; they do not navigate to Data and Setup.
- Existing finite/modeled values without their required numbers still cannot be
  applied by the existing upload API. Their repair link opens Simulation Advanced.
  This exception preserves existing validation; no partial analytical data is invented.
- These remain shared analysis settings, not private run overrides. Read the
  latest Setup before merging only these four edited fields, preserving staffing,
  periods, breaks and other settings. Refresh dependent evidence after Save.
  Existing plan/run staleness checks remain authoritative; changing assumptions
  may require recalculating an earlier plan. Never relabel stale evidence current.
- Unknown still blocks a full-day run. Finite capacity/modeled abandonment remain
  unsupported by that engine. No new defaults or mathematical capabilities.

## Boundaries and wording

Frontend only. No backend, ingestion, model selection, DES, optimizer, API shape,
database schema or package changes. Separate/single/unknown-structure Setup flows
retain their current controls. Reuse existing approved EN/TL strings verbatim;
the old reason that directs users to Data and Setup is not rendered on this flow.
Use the already-approved unknown-answer note and existing local Advanced button.
Any required new wording must be reviewed separately before application.

## Acceptance

Upload with unanswered choices saves unknown; saved finite/modeled settings are
preserved; incomplete known numbers stay guarded with a working Simulation link.
No shared model controls remain on Data and Setup. Simulation can read/edit/save
both choices on the same page, validates numbers, preserves unrelated Setup fields,
handles read/save failures and analysis changes, and refreshes stale evidence.
Run is unavailable for unknown/unsupported choices, unsaved drafts and pending saves.
Check real isolated UI, targeted API regressions, frontend suite/type/lint/build,
protected hashes and exact locale preservation. Production is outside scope.
