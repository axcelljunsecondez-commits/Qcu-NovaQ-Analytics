# Run controls above the Simulation tabs

Owner follow-up: full Run operation controls and Advanced settings belong only to
Key Results. Replay and Checks and Decisions retain the selected-plan text and run
status above the three tabs. This supersedes the first local candidate that showed
the full panel on every tab; that candidate was not committed or released.
No fixed/sticky viewport behavior was requested.

Use the existing owned codex/simulation-actions-20261102 checkout. Preserve the
completed action/dialog cleanup and its protected source. No commit/push/release.

## Inspected source and minimal design

QueueSimulationPage currently renders pageLinks in top before the selected-plan
paragraph and separate RunBar. Shared ContinuousSection owns its ContinuousRunBar
and then renders page-specific content. Those are the responsible placement points.

- Order: page header/mode/run selection, selected-plan text where applicable,
  full run panel on Key Results or compact read-only run status on the other pages,
  three page links, selected page content.
- Separate pages: keep the same RunBar above pageLinks; add an optional compact
  presentation prop. The default remains the full controls for existing consumers.
- Shared full-day pages: let ContinuousSection accept an optional navigation node
  and render it after the run header and before page content. Use the same existing
  ContinuousRunBar with compact presentation outside Key Results. Preserve hooks,
  keys, data, mutation order, settings drafts and saved-run behavior.
- Compact means no visible/focusable Run, Advanced settings, closing-rule editor,
  or model Setup controls. Keep existing stale-evidence and run-error warnings
  available; a Done badge must not conceal an existing stale/failed-run warning.
  Use existing status/copy keys without new wording. Keep the stateful controls
  mounted if needed to preserve drafts/pending requests while switching tabs;
  hide them from display, accessibility and keyboard navigation in compact mode.
- Keep tabs available during loading/error and missing-plan states; loading/error
  can stand in for an unavailable run header, with navigation still rendered.
- Named shared mode and the older legacy fallback remain unchanged in behavior.
- Keep all existing labels, route/query parameters, Current/Suggested selection,
  closing-rule scope, request payloads, mathematical/statistical behavior and
  selected-plan evidence unchanged. No new wording, locales, CSS or backend changes.

Scope: frontend/src/pages/QueueSimulationPage.tsx,
frontend/src/components/queueSimulation/ContinuousRun.tsx,
frontend/src/components/queueSimulation/RunBar.tsx,
frontend/src/pages/QueueSimulationPage.test.tsx and, if necessary, the existing
ContinuousRun.test.tsx. The dependent integration test
frontend/src/pages/CurrentDatasetCache.test.tsx may change only its obsolete
Checks-page Run-button presence assertion/comment to the approved absence rule;
preserve all dataset invalidation, Not run, lookup and no-stale-evidence assertions.
Parent owns these two task spec/plan documents.

Acceptance: across all three pages, the eligible run context precedes the tabs,
and page-specific results/replay/checks follow them. Key Results has exactly one
visible Run operation control and Advanced settings; Replay and Checks have none.
They retain the same stored/pending/not-run status and stale/error warnings.
No duplicate visible run context. Draft seed survives Results -> Replay -> Results.
Tabs remain usable on loading/error/no-plan states. Navigation retains analysis,
plan, selected period and supported mode parameters and never creates run/check/
selection evidence. Existing compatibility assessments and saved playback reads
or regeneration remain allowed behavior, not new saved run evidence.
Existing controls still execute exactly the existing request with the same inputs.
Check desktop/375px, English/Filipino and both themes in the isolated browser.

This is an additive internal component prop, not a network API contract change.
The parent provides bounded source/design investigation. Hayato implements; the
parent can independently review application code if Kyoya remains quota-unavailable,
provided the parent does not implement the reviewed application changes.
