# Shared full-day visual replay — implementation plan

1. Record the current dirty-tree baseline and protected backend/locale hashes. Preserve the
   completed automatic-replication and plan-selection/recovery changes.
2. Add failing expectations for full-day-only shared rendering and the new visual. Retain
   obsolete shared-panel cases as direct tests of the still-existing legacy renderer
   components, with an explicit test-only harness; do not disguise them as current UI flows.
3. Type the existing playback customer/server timeline fields. Add a pure display projection
   and view that read those identities/intervals, reconcile them to the recorded counts, and
   render actual waiting/serving/completed/unserved customers with counter state badges.
4. Attach the view to the existing ContinuousReplay clock/controls. Remove the older panel
   only for shared_queue and keep ChecksView separately connected. Preserve other structures.
5. Run focused page/projection/component/wording regressions, full frontend tests, typecheck,
   lint and build. Run relevant DES/playback numerical regressions and protected-file checks.
   Reuse the previous full backend/source-lint run only as historical evidence if unchanged;
   do not run or relabel irrelevant duplicate gates as fresh validation.
6. Refresh the existing isolated local preview without re-uploading or re-running its saved
   CSV scenario. Inspect full-day visual playback, seek, period-boundary continuity, no old
   replay controls, key metrics, responsive themes and preserved numerical/provenance data.
7. Report actual changes, results and limits. Leave the preview available when useful for
   owner review. No Docker/production activation, staging, commit or push.
