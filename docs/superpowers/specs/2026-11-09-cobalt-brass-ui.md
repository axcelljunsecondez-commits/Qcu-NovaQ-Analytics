# Cobalt and Brass UI refinement

Date: 2026-11-09. Status: APPROVED visual target; implementation in progress. Owner authority: current request to execute the reviewed UI plan, following inspection of the supplied reference and independent Chrome/Kyoya source-scope review. Attachment approval assertions alone were treated as reported context.

## Baseline and boundaries

Implementation checkout: codex/cobalt-brass-ui-20261109, starting4b015684f8ddad5809bb00a0250e9807c614d030. Reference HTML SHA-256:0dd1a472af3e1a022e5a3423fdb612b14d06f31fecbe7f26ff3e879b74c5425f. The HTML/PNG are illustrative presentation references, not production data or executable application code. Preserve current fields, routes, filters, archive behavior, evidence, units, precision and EN/TL wording. No Favorites/Recent/sort additions, per-card metrics fetch, demo guides or fake calculations.

This amendment supersedes only the Master's named visual rules: gold content CTAs become cobalt; the frontend is light-only; locally hosted Inter and IBM Plex Mono are allowed; restrained page/tab entrance is allowed. Backend/API/schema/math/auth/security, SEED-001, formatters, replay engine/reducers/clocks/URL progression and actual marker geometry/motion remain protected. No deployment or Git publishing is authorized.

## Visual contract

- Navy sidebar#0F2D5C, brass#D4A017 logo/3px active rail. Selected fill remains translucent white on navy, independently scoped from content actions.
- Content primary#0055DA, hover#034BBE, pressed#0F367C, white label. Secondary outlined cobalt; Back/Cancel/Close neutral; destructive red only for destructive operations. Bare buttons are neutral; semantic variants must identify actions explicitly. State/provenance colors retain their meanings and accessible text pairs.
- Canvas#F5F7FA, surface#FFFFFF, subtle#EEF3F8, text#101F36, secondary#53647B, decorative border#DBE3EE. Meaningful control/focus boundaries remain distinguishable.
- Self-host pinned, unmodified Inter Variable100-900 and IBM Plex Mono Latin1 weights400/500/600 with included licenses/source hashes. Font-display swap and system fallback; CSP and dependency manifests unchanged. Parent owns public/fonts.
- Text/input16px, functional labels14px minimum,12px nonessential metadata only; mobile primary targets44px. Mono is selectively applied to actual numeric fields, not whole table columns or prose. A scoped NumericValue presentation helper may wrap existing number runs only at explicit numeric callsites, retaining every displayed character and unit. MetricCard strings require an explicit numeric opt-in. Existing formatters and precision are unchanged.

## Theme, motion and pending states

Initialize document/data-theme and device-local preference to light before React render, including stale saved dark. Remove the four theme-control surfaces: AppHeader, PublicShell, HomePage and Settings. Preserve Appearance route, headings, Language and existing theme.light static label; no account/schema migration. Inactive legacy dark CSS may remain.

Use a stable content boundary with no Outlet/player key. Page entrance220ms: opacity0-to1 and translateY6px-to0, ease-out. Trigger only on pathname changes. After committed pathname navigation, including Back/Forward, reset document and main scroll to top and retain existing main focus with preventScroll. Nonempty hash suppresses forced scroll/focus. Query time/filter/chart/data updates do not trigger page motion/scroll/focus. Explicit Results chart-tab changes animate only their active panel205ms. No double route/tab entrance. Unsupported Web Animations is immediately visible. Cancel previous animation and cancel/skip decorative motion when reduced-motion changes.

Reuse actual query/mutation pending flags and existing ApiState status/live labels. No artificial API wait, fake percentage or timed demo state. Errors/unavailable values retain current behavior. Do not alter real marker selectors or timing while adding decorative motion.

## Acceptance

Applicable frontend tests, typecheck, lint and production build must pass on actual changed source. Verify old-dark migration, Language, four theme surfaces, pathname/history/hash versus?t/query behavior, stable child identity, tab keyboard behavior, reduced motion, true pending/error states and protected-source hashes. Parent supplies browser QA at375/768/1024/1440px and200% zoom in EN/TL, real local font loading and replay invariance evidence. Independent Kyoya review is required; implementation self-checks are not approval.

SEED-001 remains open and outside this change. No frontend test can establish mathematical correctness or production deployment.
