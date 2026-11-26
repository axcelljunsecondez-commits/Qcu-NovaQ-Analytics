# NovaQ Design System — Master

**Status:** Approved design-system source of truth
**Version:** 1.4 (amended 2026-11-25)
**Date:** 2026-09-13; amended 2026-11-09, 2026-11-24 and 2026-11-25
**Platform:** Responsive web application
**Stack:** React 19, React Router, global CSS, Plotly, i18next
**Implementation state:** Contract defined; migration occurs through the approved refinement plan. The 2026-10-09 amendments (Section 0) describe the owner-approved redesign target; they are not implemented yet, and the current application still follows version 1.0 until each redesign phase ships.

## 0. Amendment log

| Date | Section | Change | Source |
|---|---|---|---|
| 2026-11-25 | 4.1, 4.3, 7 | Results line chart (Phase C): 1.8 s left-to-right clip-path reveal of the data marks only, replayed on first data, on every Wait/Arrivals click and on a file change; reduced motion shows the chart at once. Chart-grid and estimated tokens are now in use (recorded blue, estimated gold dashed, plan aqua); a simulated Current run keeps a blue ring (`cv-m-cur`) | Owner decisions OD-C1..C6, 2026-11-25; `docs/superpowers/reference/NovaQ_Context_Engineering_and_Audit.md` (owner handoff) and `NovaQ_Final_HTML5_Reference.html` (reveal lines 436-437, reduced motion 465-467) |
| 2026-11-24 | 2, 4.1, 4.2, 4.3, 10.1, 11.1, 15.3 | Dark Navy and Brass single fixed theme replaces the light Cobalt and Brass palette (no theme switcher; static `color-scheme: dark`). AA fixes O-A1: control borders `#7890B2`; primary hover keeps `#2664DB` and adds a `#99C0FF` ring/border (never `#3473E8` under white text); pressed `#0F367C`; dark status set. Chart data colors O-A2: current/recorded blue, estimated gold (dashed when drawn as a line), optimized/suggested aqua. Slim theme-matched scrollbars. Replay presentation unchanged | Owner decisions in chat 2026-11-24; palette from `docs/superpowers/reference/NovaQ_Final_HTML5_Reference.html` dark `:root` |
| 2026-11-16 | 7 | Note only: the 205 ms panel entrance now applies to the Quick Calculator situation tabs, because the Results chart tabs were removed; no rule changed | Cobalt review follow-up, owner request 2026-11-16 |
| 2026-11-16 | 4.1, 11.1, 15.3 | Theme selection removed per the owner: no light/dark choice, no `novaq_theme` read/write, no dark CSS; light Cobalt and Brass tokens are the only styles | Owner request 2026-11-16 |
| 2026-11-09 | 2,4,5,7,18 | Cobalt content actions, navy/brass navigation, light-only local theme, self-hosted Inter/Plex numeric fonts and scoped pathname/tab entrance; protected replay unchanged | `docs/superpowers/specs/2026-11-09-cobalt-brass-ui.md`, current owner execution request |
| 2026-10-09 | 7 Motion | Replay speed and smooth customer-marker movement | `docs/superpowers/specs/2026-10-09-compact-workflow-ux-redesign.md` D29 |
| 2026-10-09 | 8.1 Breakpoints | Sidebar can be hidden to an icon rail at 1024 px and above | D10 |
| 2026-10-09 | 9.1 Hierarchy | New global navigation and analysis-level destinations | D3, D10, D28, D32 |
| 2026-10-09 | 9.2 Order | Standalone Compare page removed; plan selection moved; prerequisite kept | D4 |
| 2026-10-09 | 9.4 Predicates | Plan-selection row renamed; Reports row split into plan report and full report | D4, D31 |
| 2026-10-09 | 10.4 Evidence sources | Report availability follows the two report levels | D31 |

The 2026-10-09 amendments were approved by the product owner on 2026-10-09 and are recorded with their reasons in `docs/superpowers/specs/2026-10-09-compact-workflow-ux-redesign.md` Section 0. None of them changes the protected behavior boundary in Section 13.

## 1. Retrieval and precedence

Every NovaQ UI task must read this file before editing a page or shared component. If `design-system/novaq/pages/<page>.md` exists, that file may override this Master only for the named page and only when it cites repository evidence and an approved specification. No override may cross the protected behavior boundary.

Precedence is:

1. current repository behavior and tests;
2. `AGENTS.md`, `memory.md`, and `handoff.md`;
3. approved Superpowers product decisions/specification/plan;
4. this Master;
5. an approved page override.

If this Master conflicts with current analytical, security, provenance, workflow-evidence, Decision, or report semantics, stop and document the conflict.

## 2. Product character

NovaQ is a pilot-deployable queueing analytics and operations-decision tool. Its interface is:

- trustworthy before decorative;
- plain-language-first without hiding technical precision;
- compact enough for operational data but readable at normal zoom;
- minimal, grid-based, high-contrast, and low-motion;
- recognizably NovaQ through the existing navy/gold identity; and
- equally usable in English and Filipino, the approved dark interface (since 2026-11-24), keyboard and touch input.

Do not adopt the local design search’s Fira fonts, marketing gateway layout, or GSAP. The 2026-11-09 approved amendment introduced locally hosted Inter text and IBM Plex Mono numeric values, while retaining the existing application architecture and chart renderers. The 2026-11-24 amendment replaces the light Cobalt and Brass palette with the single Dark Navy and Brass theme.

## 3. Non-negotiable design principles

1. **Truth is visible.** Labels distinguish observed input, analytical estimate, optimization candidate, simulation evidence, Decision, and projection.
2. **State comes from source.** “Valid,” “verified,” “passed,” “complete,” and “stale” appear only when the corresponding API/provenance rule supplies that state.
3. **Unknown stays unknown.** Missing, unsupported, and non-finite values render as unavailable with an explanation; they are never converted to zero or a supported mode.
4. **Color is redundant.** Every color-coded status also has text and, where useful, a consistent SVG icon or line/pattern treatment.
5. **One hierarchy, one route source.** Top-level navigation and analysis-workflow navigation are separate levels. Workflow destinations and ordering are declared once.
6. **Components do not own domain rules.** Shared UI components display values and states supplied by callers. They do not select models, infer evidence, recalculate Decision, or mutate payload semantics.
7. **Accessibility is a component requirement.** Keyboard, focus, names, errors, status announcements, contrast, text scaling, and reduced motion are defined before visual polish.

## 4. Token architecture

Tokens use three layers:

1. **Primitive values** are the approved palette and size values.
2. **Semantic tokens** describe purpose, such as surface, action, warning, stale, current, or optimized.
3. **Component tokens** alias semantic tokens for a specific control and may not introduce raw colors or arbitrary sizes.

`frontend/src/styles/theme.css` remains the runtime source. Existing variables such as `--bg-page`, `--text-primary`, `--accent`, and `--border` remain as compatibility aliases during migration; new code uses the canonical names below.

### 4.1 Active dark tokens

Amended 2026-11-24 (owner): the UI has one fixed Dark Navy and Brass theme with a static `color-scheme: dark`. There is no theme selection. The light Cobalt and Brass values (2026-11-09) and the older dark mappings are superseded and kept only in Git history. The palette comes from the dark `:root` of `docs/superpowers/reference/NovaQ_Final_HTML5_Reference.html`, with the owner-approved AA fixes (O-A1).

| Canonical token | Dark value | Required use |
|---|---:|---|
| `--color-bg-canvas` | `#0B1221` | Application background |
| `--color-bg-surface` | `#121E33` | Cards, panels, menus |
| `--color-bg-subtle` / `--color-bg-raised` | `#17253E` | Grouped rows, hover layers, tooltips |
| `--color-bg-sidebar` | `#0E192D` | Global navigation |
| `--color-bg-input` | `#0E192D` | Editable control background |
| `--color-bg-hero` | `#172944` | Hero and cover panels |
| `--color-text-primary` | `#F1F5FF` | Body and headings |
| `--color-text-secondary` | `#A8B9D1` | Supporting text; not disabled text |
| `--color-text-inverse` | `#FFFFFF` | Text on the dark navy sidebar/hero |
| `--color-text-on-fill` | `#0B1221` | Text on light fills (brass, status and data colors) |
| `--color-border-subtle` | `#263753` | Decorative separation |
| `--color-border-control` | `#7890B2` | Input/control boundary where 3:1 is required (O-A1; not `#425778`) |
| `--color-action-primary-bg` | `#2664DB` | Primary action fill, white label |
| `--color-action-primary-fg` | `#FFFFFF` | Primary action label/icon |
| `--color-action-primary-hover` | `#2664DB` | Hover keeps the fill (O-A1) |
| `--color-action-primary-hover-ring` | `#99C0FF` | Hover border plus 1 px outer ring |
| `--color-action-primary-pressed` | `#0F367C` | Pressed fill |
| `--color-action-link` | `#83B0FF` | Inline links, secondary-button text, active tab |
| `--color-action-danger` | `#FFA89D` | Destructive action text/border; its hover fill uses on-fill text |
| `--color-focus-ring` | `#99C0FF` | Keyboard focus indicator |
| `--color-disabled-bg` | `#1D2A40` | Disabled fill |
| `--color-disabled-fg` | `#A8B9D1` | Disabled label; always paired with disabled semantics |
| `--color-disabled-border` | `#425778` | Disabled control boundary |
| `--color-chart-grid` | `#2B3D59` | Chart grid lines; in use (Results line chart, 2026-11-25) |
| `--color-scroll-thumb` / `--color-scroll-thumb-active` | `#566D8C` / `#7890B2` | Slim scrollbars, both axes |

Brass `#EFC477` (`--brand-brass`, `--accent`) is the brand accent; text placed on a brass fill uses `--color-text-on-fill`. `#3473E8` must not be used under white text (4.41:1). Measured pairs (WCAG 2.x relative luminance, 2026-11-24): text on canvas 17.14:1, on surface 15.28:1, on raised 14.04:1; secondary text on surface 8.36:1, on raised 7.68:1; link on surface 7.64:1; white on primary 5.35:1, on pressed 11.42:1; control border on surface 5.11:1; focus ring on surface 9.00:1; on-fill text on brass 11.43:1.

### 4.2 Semantic status tokens

Each status has background, border, and text/icon tokens. Border and text may share the listed foreground value, but component code must reference semantic aliases.

| State | Background / foreground (dark, 2026-11-24) | Meaning |
|---|---|---|
| Success | `#0E2F25` / `#81DEB3` | Operation completed or explicit pass |
| Warning | `#33270F` / `#EFC477` | Attention required, not failure |
| Danger | `#3A1620` / `#FFA89D` | Error, invalid, failed, destructive |
| Info | `#102C3B` / `#83B0FF` | Neutral provenance or guidance |
| Stale | warning pair | Saved evidence no longer current; must include “Stale” text |
| Unavailable | subtle background / secondary text | Missing, unsupported, or not calculated |

Canonical names are `--color-success-{bg,border,fg}`, `--color-warning-{bg,border,fg}`, `--color-danger-{bg,border,fg}`, `--color-info-{bg,border,fg}`, `--color-stale-{bg,border,fg}`, and `--color-unavailable-{bg,border,fg}`.

Measured foreground/background contrast for the approved status pairs (2026-11-24) is success 8.98:1, warning 8.92:1, danger 8.62:1 and info 6.65:1; primary text on each status background is at least 13.25:1. Status text must still name the state; color alone is insufficient.

### 4.3 Current and optimized data tokens

Current, estimated and optimized are comparison identities, not success/failure. Amended 2026-11-24 (owner O-A2): recorded/current is blue, estimated is gold (dashed where an estimate is drawn as a line), and the optimized/suggested plan is aqua.

| Token | Dark value | Status |
|---|---:|---|
| `--color-data-current` | `#83B0FF` | In use |
| `--color-data-current-bg` | `#14284A` | In use |
| `--color-data-estimated` | `#EFC477` | In use (estimated marks and dashed line, 2026-11-25) |
| `--color-data-estimated-bg` | `#2E2713` | In use (Estimated legend chip, 2026-11-25) |
| `--color-data-optimized` | `#7CE1D3` | In use |
| `--color-data-optimized-bg` | `#0F2E33` | In use |

The primary data colors exceed 7:1 against the surface (current 7.64:1, estimated 10.19:1, optimized 10.77:1). Charts also differentiate them with direct labels and solid-versus-dashed lines, distinct marker shapes, or patterns. Red/green is reserved for failure/success and must not be the sole Current/Optimized distinction.

## 5. Typography

Use self-hosted Inter for text and IBM Plex Mono only for actual numeric values, with the existing system fallbacks. The approved 2026-11-09 assets include their license notices and pinned provenance under frontend/public/fonts; no external runtime font request or CSP relaxation is allowed.

| Token | Size / line height | Use |
|---|---|---|
| `--text-xs` | 0.75rem / 1rem | Metadata, timestamps, eyebrow text only |
| `--text-sm` | 0.875rem / 1.25rem | Labels, buttons, badges, table cells |
| `--text-md` | 1rem / 1.5rem | Body copy, inputs, select values |
| `--text-lg` | 1.125rem / 1.5rem | Card and subsection headings |
| `--text-xl` | 1.5rem / 2rem | Section title |
| `--text-2xl` | 2rem / 2.5rem | Page h1 |

Use weights 400 for body, 500 for supporting emphasis, 600 for labels/actions, and 700 for headings. Avoid 800 except the NovaQ wordmark or a deliberately compact data label.

Rules:

- The root/body size is 16 px.
- Functional labels, buttons, badges, and table content never fall below 14 px.
- Twelve-pixel text is restricted to nonessential metadata and must still meet 4.5:1 contrast.
- Input values remain 16 px, including mobile, to avoid browser zoom.
- Numeric KPIs, currency, percentages, identifiers, and timers use `font-variant-numeric: tabular-nums`.
- Body copy targets 60–75 characters per line on desktop and 35–60 on narrow screens.
- Headings use semantic `h1`–`h3` order; visual size is controlled by tokens rather than skipped levels.

## 6. Spacing, geometry, elevation, and layering

### 6.1 Spacing

Use a 4 px base:

| Token | Value |
|---|---:|
| `--space-0` | 0 |
| `--space-1` | 4px |
| `--space-2` | 8px |
| `--space-3` | 12px |
| `--space-4` | 16px |
| `--space-6` | 24px |
| `--space-8` | 32px |
| `--space-12` | 48px |
| `--space-16` | 64px |

Existing `--space-xs/sm/md/lg/xl` variables alias 4/8/16/24/32 during migration. Component CSS may not introduce a new spacing value unless the Master is amended.

### 6.2 Geometry and targets

- `--radius-sm: 6px`, `--radius-md: 8px`, `--radius-lg: 12px`, `--radius-pill: 999px`.
- Desktop form controls and buttons are at least 36 px high.
- At viewport widths below 768 px, every primary interactive target is at least 44×44 px with at least 8 px separation.
- Icon sizes are 16, 20, and 24 px; navigation uses one 20 px outline style.
- Cards use subtle border plus `--shadow-sm`; overlays/drawers alone may use `--shadow-md`.
- No decorative glass blur, large gradient shadow, or layout-shifting press transform.

### 6.3 Layering

`--z-base: 0`, `--z-sticky: 20`, `--z-dropdown: 40`, `--z-overlay: 100`, and `--z-toast: 1000`. A component must use the lowest layer that satisfies its behavior.

## 7. Motion

Motion is restrained and never required to understand state:

- `--motion-fast: 120ms` for hover/pressed feedback.
- `--motion-standard: 200ms` for disclosure and theme-state transitions.
- Use transform/opacity only; never animate layout dimensions for decoration.
- Spinners may rotate only while an operation is actually pending.
- Playback time remains controlled by its existing user controls and reducer.
- Amended 2026-10-09 (D29): replay speeds are 0.25×, 0.5×, 1×, 2×, 5× and 10×, measured against simulated time rather than the length of the trace. Customer markers glide between arriving, their place in line, their counter and finished, using transform and opacity only, with each move lasting about 0.2–0.9 s so markers never teleport or streak. Counts, clock and states stay exact from the reducer; the glide only animates how a marker reaches its exact position. Under reduced motion, markers move without gliding. The base rate (proposed: 1× = 1 simulated minute per real second) awaits owner confirmation.
- Under `prefers-reduced-motion: reduce`, nonessential animation and smooth scrolling are disabled; loading and playback status remain understandable without motion.
- Do not add GSAP. The 2026-11-09 amendment permits 220 ms pathname-only content entrance and 205 ms explicit chart-tab-panel entrance, with reduced-motion cancellation. (Note 2026-11-16: the Results chart tabs were later removed; the 205 ms panel entrance is used only by the Quick Calculator situation tabs.) Never animate/rekey playback on ?t/query updates or change marker timing/geometry.
- Amended 2026-11-25 (owner, Phase C): the Results line chart reveals its data marks (the traces and nodes, never the grid, axes, labels or hit areas) left to right with `clip-path: inset(0 100% 0 0)` → `inset(0)` over 1800 ms after a 120 ms delay, `ease-in-out`. This is the one permitted exception to the transform/opacity rule. It replays on the first usable data, on every Wait/Arrivals click (including the measure already shown) and when the shown file changes; hover, focus, the arrow keys, filters, the Today/Plan sub-switch and a refetch of the same file never replay it. Under `prefers-reduced-motion: reduce` no animation runs and the marks are fully visible; a running reveal is cancelled when that setting turns on or the chart unmounts.

## 8. Responsive layout

The existing AppLayout and Sidebar are retained and refined.

### 8.1 Breakpoints and gutters

| Range | Global navigation | Content gutter |
|---|---|---:|
| 0–767 px | Compact header plus explicit menu disclosure | 16px |
| 768–1023 px | Compact header plus explicit menu disclosure | 20px |
| 1024–1439 px | Persistent 200 px Sidebar | 24px |
| 1440 px and above | Persistent 200 px Sidebar; content max 1500 px | 32px |

Amended 2026-10-09 (D10): at 1024 px and above, an icon-only button hides the Sidebar to an icon rail and shows it again. The button has an accessible name and `aria-expanded`; each rail icon keeps its accessible name and shows a tooltip on hover and keyboard focus that Escape dismisses. The choice is remembered on the device. Help, Settings, the user's email, Language and Log out are grouped in one account menu at the bottom of the Sidebar.

At widths below 1024 px, the existing Sidebar becomes an in-flow compact application header with a labelled menu button and collapsible navigation region. It is not a separate modal navigation architecture. The button exposes `aria-expanded` and `aria-controls`; Escape and route changes close the region; focus is not trapped because the region remains in document flow.

Rules:

- `AppLayout` supplies a visible-on-focus “Skip to main content” link and a stable main target.
- The page itself never scrolls horizontally. Wide tables scroll inside a labelled `TableFrame`.
- Cards and grids collapse before values are truncated. Primary actions remain visible.
- Sticky elements reserve space and may not obscure focused content.
- Workflow navigation is static rather than sticky below 640 px if its height could cover page content.
- Verify 375, 768, 1024, and 1440 px, plus 375 px landscape and 200% text zoom.

## 9. Navigation system

### 9.1 Hierarchy

There are exactly two navigation levels:

1. **Global navigation** (amended 2026-10-09, D3, D10, D32): Workspace → My analyses; Insights → Analysis results, Reports; Simulation → Queue simulation; Tools → Quick calculator; an account menu with the user's email, Settings, Language, Get help and Log out. Settings holds Account and sign-in, Preferences, Appearance, Uploaded files, and Users (admin only).
2. **Analysis level** (amended 2026-10-09, D28): the analysis workspace tabs Data and setup | Suggested plans; Analysis results; the Queue simulation pages Key results | Replay | Checks and decision; Reports.

Version 1.0 listed: global navigation Dashboard, Analyses, Datasets, Advanced Analysis, Account, Admin when authorized, Help, language, theme, and Logout; analysis workflow Setup, Current, Optimize, Compare, Simulate, Decision, Reports. Old routes redirect to their new destinations (`docs/superpowers/specs/2026-10-09-compact-workflow-ux-redesign.md` Section 5).

The Sidebar owns global navigation only. `WorkflowNavigator`, rendered by `AnalysisWorkspace`, owns the workflow stepper and Previous/Next actions. The Sidebar’s current duplicate workflow list is removed only after import, route, usage, and test tracing.

A single shared workflow-step definition supplies path, translation key, order, and prerequisite metadata. Sidebar, pages, and tests must not declare independent copies.

### 9.2 Canonical executable order

Amended 2026-10-09 (D4): the standalone Compare page is removed. The persisted plan selection that simulation requires is made with "Use this plan" in Suggested plans or with the saved-plan switcher in Analysis results. It remains a simulation prerequisite. The executable order is:

Data and setup → Suggested plans → Analysis results → Queue simulation → Decision → Reports.

Version 1.0 text, kept for history:


The requested Simulate-before-Compare order is not executable in the current repository because simulation requires a scenario selection persisted by Compare. Until a separate workflow specification relocates that selection, the canonical order is:

Setup → Current → Optimize → Compare → Simulate → Decision → Reports.

Deep-link routes remain unchanged. Entering a blocked destination gives a specific prerequisite and recovery link rather than silently redirecting to Login or marking the step complete.

### 9.3 Workflow status vocabulary

Workflow status is not browsing history:

- **Active:** the current route. This says nothing about completion.
- **Available:** prerequisites exist and the route may be used.
- **Blocked:** a named prerequisite is missing.
- **Evidence saved:** a persisted job exists; this does not by itself mean the result passed.
- **Complete:** the required valid result is proven by the source listed below.
- **Stale:** the backend reports current saved evidence or Decision is stale.
- **Unavailable:** state could not be loaded; never substitute blocked, failed, or complete.

No localStorage/sessionStorage “visited” flag may drive these labels.

### 9.4 Completion predicates

| Step | May be marked complete only when |
|---|---|
| Setup | `analysis.setup_status` is `ready` or `ready_for_aggregate` |
| Current | `getAnalysisCurrent` succeeds with a valid dataset and nonempty analytical rows |
| Optimize | A saved verified-snapshot scenario has a complete operational comparison; an unsaved mutation result is “Candidate available,” not complete |
| Plan selected (formerly Compare; amended 2026-10-09, D4) | `WorkflowEvidence.selection` and its verified `WorkflowEvidence.scenario` exist |
| Simulate | A current, non-stale, non-insufficient Decision references the current DES and validation evidence IDs; before that, existing jobs are labelled “Evidence saved” |
| Decision | A persisted, non-stale Decision has status `adopt`, `revise`, or `conditional`; `insufficient_evidence` is not complete |
| Reports | No persisted export-completion event exists, so a visit/download must not mark this complete. Amended 2026-10-09 (D31): the plan report is “Available” once a current, verified plan is selected; the full report is “Available” only when the current Decision gate permits export. Each report states its level on its cover. |

The UI may show more detail, but may not weaken these predicates or duplicate backend Decision derivation.

### 9.5 Previous and Next behavior

- Previous returns to the prior canonical step and preserves analysis identity.
- Next names the destination.
- A blocked Next control is semantically disabled and is paired with visible text explaining the exact prerequisite and a recovery action where possible.
- Completing a route does not auto-navigate unless the user initiated the final action and the existing workflow explicitly expects navigation.
- Route changes focus the destination `h1` or main region without disrupting normal browser back behavior.

## 10. Shared component contracts

Shared components are presentation contracts. They receive already-authorized data/state and must not create analytical or workflow truth.

| Pattern | Current basis | Required contract |
|---|---|---|
| App shell | `AppLayout`, `Sidebar` | Skip link, global navigation, main target, responsive disclosure, no page overflow |
| Page header | `.topbar`, `.page-title`, `.page-caption` | One h1, optional source-aware eyebrow/caption, one primary action |
| Surface | `.card` | Surface/background/border/radius/spacing tokens; no domain state inferred |
| Button/action link | global button, `.btn-primary`, `.btn-ghost` | Primary, secondary, ghost, and danger variants with identical semantics for button and Link |
| Form field | `.form-field`, repeated labelled controls | Label, control, optional unit, hint, inline error, required/disabled/read-only semantics |
| Metric card | `MetricCard` | Label/value/unit/supporting text; optional Current/Optimized identity; no automatic trend or pass/fail |
| API state | `ApiState` | Loading, empty, error, forbidden with correct status semantics and optional recovery |
| State badge | `.badge`, `.pill` | Text plus optional SVG; success/warning/danger/info/unavailable; never color alone |
| Evidence banner | current integrity/stale/Decision alerts | Source-labelled provenance/status from API state; no caller-free default |
| Table frame | repeated `.table-wrap > table` | Accessible name/caption, contained overflow, optional description/state, unchanged cells |
| Chart frame | private `ChartFrame` in `Charts.tsx` | Heading, units, source summary, Plotly visual, accessible table/list alternative, loading/empty/error |
| Tabs | `.tab-bar`, `.tabs` | WAI-ARIA tab/tabpanel relationships and keyboard behavior |
| Workflow navigator | current `WorkflowNavigator` | One shared step config, evidence-backed status, Previous/Next, responsive rendering |
| Live playback | `LiveSimulationPlayback` | Existing reducer/events preserved; controls, static summary, reduced-motion and nonvisual event/accounting view |

An extraction is created only when at least two current consumers need the same behavior or an approved cross-cutting requirement cannot be satisfied by a class alone.

### 10.1 Buttons and action links

- Use native `button` for actions and React Router `Link/NavLink` for navigation.
- One primary action per task region. Secondary/ghost actions do not compete visually.
- Danger is limited to destructive actions and requires explicit text.
- Icon-only controls require an accessible name; icons next to visible text are `aria-hidden="true"`.
- Pending actions are disabled, retain their width, expose busy state, and show a localized progress label.
- Disabled actions use native `disabled` where possible. An unavailable navigation link uses `aria-disabled`, prevents activation, and is accompanied by the reason.
- Hover, focus, pressed, disabled, and busy states are defined in the dark interface (2026-11-24). Primary hover keeps its fill and adds the hover ring; secondary actions use link-blue text on the surface with a control border.

### 10.2 Fields and numeric inputs with units

The shared field pattern contains:

1. visible label;
2. optional required indicator;
3. native input/select/textarea;
4. visible unit suffix or unit in the label;
5. persistent hint for non-obvious analytical input; and
6. inline error linked with `aria-describedby`.

Rules:

- Units use repository truth: rates per hour, wait/threshold display in minutes, service variance in hours squared, and the explicit cost period when defined.
- A reusable numeric field preserves the caller’s raw editing string and returns it unchanged. Domain code remains responsible for parsing and request construction.
- The component never defaults blank to zero, clamps silently, changes sign, or converts units without an explicit caller function.
- Use `min`, `max`, `step`, and `inputMode` only when they match backend validation.
- Validate on blur or submit, not every keystroke. On a multi-error submission, focus a linked error summary and retain inline errors.
- Unknown/not sure is an explicit value where the API supports it; it is not represented by an unchecked control that serializes a definite answer.
- Read-only and disabled are visually and semantically distinct.

### 10.3 API and content states

| State | Semantics | Required content |
|---|---|---|
| Loading | `role="status"`, polite, atomic; spinner decorative | What is loading; preserve layout where practical |
| Empty | Neutral region, not an error | What is absent and a valid next action |
| Error | `role="alert"` for a newly surfaced failure | Specific failure when available, recovery/retry, no raw object |
| Forbidden | Heading plus explanation; no false server-error message | Permission boundary and safe return action |
| Stale | Warning semantics, visible “Stale” text | What changed, which saved result is affected, required rerun |
| Unavailable | Neutral state | Missing/unsupported reason; never zero |
| Success | Polite status when user-triggered | What completed and what remains; do not steal focus |

Avoid repeated live announcements. Timers, playback clocks, hover values, and continuously updating charts are not live regions. Announce only user-triggered completion/failure or a meaningful state transition.

### 10.4 Badges and evidence banners

Badges identify compact state. Evidence banners explain source and consequence.

An `EvidenceBanner` must receive an explicit source-backed variant and content. Allowed evidence sources are:

- `analysis.setup_status`;
- `dataset.validation.ok/message`;
- scenario `provenance: "verified_snapshot"`;
- persisted `WorkflowJob` identity, kind, status, parameters, and result;
- `WorkflowEvidence.decision_stale`;
- persisted Decision status, missing evidence, evidence IDs, and provenance warning; and
- report availability: the plan report from a current, verified selected plan, and the full report from the current Decision gate (amended 2026-10-09, D31).

Rules:

- “Verified” is reserved for the backend’s verified-snapshot provenance or another explicit verification field.
- “Passed” is displayed only from the relevant persisted validation rule using its saved parameters.
- A saved job may be labelled “Evidence saved,” not automatically “Valid” or “Passed.”
- “Complete” follows Section 9.4 only.
- Stale always includes cause/recovery text and may not be styled as success.
- Unknown API state renders unavailable, not green.
- Banner icons are consistent inline SVG; the text carries the meaning.

### 10.5 Metric cards

`MetricCard` is refined to semantic description markup, preferably `dl/dt/dd`.

- Value and unit are separate when this improves scanning.
- Source identity—Current, Optimized, Simulated, or Projected—is explicit text.
- Current and Optimized use their data tokens but never imply bad/good.
- Delta arrows or signs are shown only when a direct source comparison exists and direction is mathematically defined.
- Missing/non-finite values render “Unavailable”; zero remains zero.
- Cards do not calculate averages, ROI, pass/fail, or trends.

### 10.6 Tables

`TableFrame` standardizes presentation without owning rows:

- every table has a visible title or programmatic caption;
- column headers use `scope="col"`; row headers use `scope="row"` when applicable;
- numeric columns use tabular figures and consistent alignment;
- units appear in headers;
- missing values render localized unavailable text;
- responsive overflow is contained in a focusable, labelled region with a keyboard-visible focus ring;
- no columns are silently removed on narrow screens; a page may use an approved card/list alternative that contains the same data;
- sorting is added only where current product behavior requires it and must expose `aria-sort`; and
- loading, empty, error, and stale states appear before an empty table shell.

### 10.7 Charts

Plotly remains. The existing internal `ChartFrame` becomes the single chart presentation contract.

Each chart requires:

- a localized title and concise description;
- exact source metric names and units;
- a source-backed visual encoding;
- legend or direct labels;
- keyboard-reachable exact values when interaction is essential;
- a text summary that states facts without unsupported causal interpretation;
- a table/list alternative containing the same important values; and
- loading, empty, error, theme, resize, and reduced-motion behavior.

Rules:

- Never create synthetic 0–100 scores, arbitrary normalization, invented KPI, or unsupported ranking.
- Do not coerce missing values to zero; preserve gaps.
- Current and Optimized use Section 4.3 identities plus labels and line/marker/pattern differences.
- Success/danger colors are not used merely to label Current versus Optimized.
- Axes name units and time granularity. Wait times are converted from hours to minutes only at display time.
- Pie/donut is used only for five or fewer true parts of a whole; otherwise use bars.
- Chart colors come from computed CSS semantic variables through one chart-theme helper. Raw hex values do not remain in chart components.
- Insight text derived in the frontend must have a documented formula, direct input fields, boundary tests, and neutral wording. It must not claim provenance or validation it does not possess.
- The synthetic RadarChart and its frontend scoring helper remain scheduled for removal under the approved full-refinement specification.

### 10.8 Tabs and playback

- A tab has `role="tab"`, stable `id`, `aria-controls`, `aria-selected`, and roving `tabIndex`.
- A panel has `role="tabpanel"`, `aria-labelledby`, and is hidden when inactive.
- Arrow keys move among tabs; Home/End are supported; activation behavior is consistent.
- Playback preserves the existing trace reducer, time conversion, controls, server/customer identities, queue accounting, and shared-FIFO disclosure.
- Playback controls remain usable without motion; a static event/accounting table or summary supplies the nonvisual alternative.

## 11. Theme, icons, and localization

### 11.1 Theme

- Dark only. Theme selection was removed on 2026-11-16 per the owner; on 2026-11-24 the owner replaced the light Cobalt and Brass palette with the single Dark Navy and Brass theme. There is no light/dark mode, ThemeToggle or Settings theme option; the dark tokens in `theme.css` are the only styles, with a static `color-scheme: dark`. No print stylesheet is defined.
- The old `novaq_theme` device key is no longer read or written; stored values are left untouched.
- A component may not read a raw theme color from a page-specific constant.

### 11.2 Icons

- Structural icons use local inline SVG with `currentColor`; no emoji or icon-package dependency is added.
- One outline style, 20 px navigation size, and consistent stroke width is used at the same hierarchy.
- Decorative icons beside visible text are `aria-hidden="true"`.
- Standalone informative icons have a text alternative.
- Icon buttons have an accessible name and expose pressed/expanded state when applicable.
- Language uses text labels such as “EN English” and “TL Filipino,” not national-flag emoji.

### 11.3 Localization

- Every user-visible string is stored in both `frontend/public/locales/en/translation.json` and `frontend/public/locales/tl/translation.json`.
- Keys remain recursively symmetric and are checked by an automated test.
- `document.documentElement.lang` is `en` or `tl` and changes with i18next.
- Number, percentage, date/time, and currency display uses locale-aware formatting while retaining the source value and unit.
- Technical symbols such as λ, μ, ρ, Wq, and Lq may remain when paired with localized plain-language labels/help.
- User/data content is not passed through translation lookup.

## 12. Accessibility requirements

NovaQ targets WCAG 2.2 AA for the refined web interface.

### 12.1 Keyboard and focus

- All interactions use native controls or an equivalent complete keyboard pattern.
- A global `:focus-visible` indicator uses a 3 px `--color-focus-ring` outline with at least 2 px offset. No component removes it without an equal or stronger replacement.
- Focus order follows DOM/visual order.
- Route changes focus the page heading/main region.
- Sticky workflow UI, expanded navigation, dialogs, and banners may not obscure the focused element.
- Escape closes non-destructive disclosures; closing returns focus to the trigger when focus was moved.
- No drag, hover, or pointer-only action is required.

### 12.2 Names, structure, and status

- Pages have one h1 and sequential headings.
- Landmarks include header where present, labelled navigation, main, and complementary aside only where semantically appropriate.
- Icon-only controls have names; visible labels are programmatically associated.
- Newly surfaced errors use an alert; routine loading/completion uses a polite status region.
- Status updates are atomic, contextual phrases. Continuously changing timers are not announced.
- Tables and charts have accessible names and nonvisual data access.

### 12.3 Contrast, zoom, and touch

- Normal text meets 4.5:1; large text and meaningful non-text UI meet 3:1.
- Focus indicators meet 3:1 against adjacent colors.
- Meaning is never color-only.
- Content remains usable at 200% text zoom and browser zoom without clipped controls or lost data.
- Primary touch targets are at least 44×44 px below 768 px and have 8 px separation.
- The viewport permits zoom; no maximum-scale or user-scalable restriction is added.

### 12.4 Forms and authentication

- Authentication fields retain paste, password-manager, and autocomplete support.
- Errors identify the field and recovery action without requiring memory tests or puzzle-like interaction.
- Required and optional fields are explicit.
- Disabled fields remain discoverable with a reason; read-only data remains selectable.

## 13. Protected behavior boundary

The design system changes presentation and interaction structure only. It may not:

- select or reinterpret queueing models;
- alter analytical formulas, rates, stability, capacity, abandonment, or wait-time units;
- change optimization objective, constraints, tie-breaking, cost composition, or payloads;
- create separate-queue or priority-class behavior;
- alter DES/Monte Carlo generation, playback reducer, event identities, aggregates, validation, or randomness;
- derive or overwrite scenario provenance, workflow evidence, Decision status, or staleness;
- change authentication, authorization, session, CSRF, or user ownership;
- expand report content, change export calculations, or convert report units;
- invent cost periods, projections, ROI, KPIs, scores, or pass/fail thresholds; or
- mark workflow completion from route visits or local browser storage.

Components must accept already-derived values or use a named, tested frontend presentation helper whose formula and source fields are documented. They may not duplicate central model selection or backend Decision logic.

## 14. Page override policy

A page override file is exceptional. Before creating one:

1. trace the page route, imports, shared components, tests, and runtime state;
2. identify the Master rule that cannot satisfy the verified need;
3. document the evidence and smallest override;
4. state protected behavior and tests; and
5. obtain approval through the Superpowers specification/plan flow.

An override may change layout density or a component arrangement. It may not redefine semantic colors, typography, workflow order, evidence vocabulary, accessibility minimums, or protected product behavior.

## 15. Verification contract

### 15.1 Component tests

Testing Library tests use role/name/state queries and cover:

- primary/secondary/danger/disabled/busy controls;
- labels, hints, units, inline errors, and error-summary focus;
- loading/empty/error/forbidden/stale/success semantics;
- evidence-banner source/status mapping and no default “verified” state;
- metric zero versus unavailable;
- table caption/header/overflow semantics;
- chart title, units, exact data alternative, missing-value gaps, and theme change;
- tabs with arrow/Home/End behavior;
- responsive navigation disclosure and route-change close/focus;
- workflow order, prerequisites, active versus complete, stale, and blocked states; and
- locale-key symmetry plus document-language updates.

### 15.2 Repository regression

Run:

- `python -m pytest tests/ -x --tb=short`
- `ruff check .`
- `mypy .`
- `npm test`
- `npm run typecheck`
- `npm run lint`
- `npm run build`

Protected focused tests include model selection, optimization, scenario integrity, simulation trace/aggregate equivalence, workflow evidence/Decision, reports, authentication, production hardening, and frontend CSRF.

### 15.3 Manual verification

Verify representative populated, loading, empty, error, unavailable, stale, blocked, and disabled states:

- at 375, 768, 1024, and 1440 px plus narrow landscape;
- at 200% text zoom;
- with keyboard only;
- with reduced motion;
- in the dark interface (the only interface since 2026-11-24);
- in English and Filipino; and
- with generated PDF/Excel preview fidelity where Reports is involved.

Document contrast measurements for every final semantic foreground/background pair. Verify chart data and tables against the same API fixture. Record that no page-level horizontal scroll or focus obstruction remains.

## 16. Adoption checklist for every page

Before a page is considered refined:

- [ ] It reads this Master and any approved page override.
- [ ] It uses semantic tokens and shared components; no new raw color or arbitrary spacing is introduced.
- [ ] It has one h1 and one primary action per task region.
- [ ] Loading, empty, error, stale, unavailable, disabled, and success states are truthful.
- [ ] Evidence claims cite real API/provenance state.
- [ ] Numeric inputs expose units and preserve blank/unknown correctly.
- [ ] Tables and charts provide nonvisual access and explicit units.
- [ ] Current and Optimized are identities, not red/green judgments.
- [ ] Workflow status is evidence-backed and never visit-backed.
- [ ] Keyboard, focus, contrast, touch, zoom, reduced motion, and responsive checks pass.
- [ ] English and Filipino keys are symmetric.
- [ ] Protected NovaQ behavior and relevant regression tests remain unchanged.
