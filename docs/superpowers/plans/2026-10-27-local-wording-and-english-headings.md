# Local wording implementation plan

Implemented and verified locally on 27 October 2026. See [the application report](../../wording/2026-10-27-local-wording-report.md) for executed gates, local activation, synthetic screenshot coverage and thirteen retained semantic conflicts. No production action or push occurred.

1. Pin the active worktree and preserve its clean baseline and protected paths. Verify the supplied PDF hash and the prior extraction; read current heading consumers and i18n resources.
2. Build a usage-level heading inventory covering native headings, heading-styled labels, titles passed into shared components, dialogs and associated accessible names. Separate KPI/field labels and user-entered names.
3. Apply supplied PDF copy with an explicit manifest, preserving existing placeholders and retaining confirmed conflicting statements without editorial substitutions. Keep duplicate/context decisions documented.
4. Add one English-heading translation helper and update heading consumers without changing ordinary translation behavior. Update Help title searching to use the displayed English titles while preserving Filipino body matching. Scope any result-label case reset to the affected frontend UI.
5. Run focused heading/copy/search tests, then the required frontend and backend gates. Fix actual failures and preserve their logs. Inspect EN/TL, light/dark, responsive and accessible behavior in the real compiled frontend.
6. Refresh Help images against isolated synthetic data when the fixture/runtime is available. Inspect the local stack and preserve existing API/database identity/configuration before any web-only activation. Do not run migrations, seeding, cleanup, push or production actions. Report partial or blocked gates rather than claiming completion prematurely.
