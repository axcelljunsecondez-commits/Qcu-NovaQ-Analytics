---
name: novaq-ui-ux
description: Use when improving Queueing Dashboard UI/UX. Covers Streamlit performance, responsive layout, CSS styling, data visualization for M/M/1–Erlang-A queue models, accessibility, and OpenCode prompt patterns. Trigger when user mentions styling bugs, re-renders, mobile issues, chart types, or queueing analytics design.
---

# Queueing Dashboard UI/UX Guidelines

## Trigger Conditions
- User asks to improve Queueing Dashboard styling, layout, or UI
- User mentions Streamlit re-renders, slow load, or performance
- User requests new chart type for queue model output
- User reports broken layout on mobile or tablet
- User wants to export results or add download functionality
- User mentions a specific page: metrics, optimization, simulation, comparison

## Performance Principles
- Wrap sidebar inputs in `st.form` to prevent re-render cascade
- Use `@st.cache_data` on DataFrame-transforming functions
- Vectorize `.iterrows()` — use boolean indexing or `df.assign()`
- Lazy-import heavy libraries (scipy) inside conditional branches
- Consolidate CSS into one `st.markdown(unsafe_allow_html=True)` block at init
- Use `st.session_state` flags to prevent redundant recomputation
- Profile slow SimPy runs with `cProfile` before caching

## Layout Patterns
- `st.columns([2,1,1])` for metric cards — never markdown hacks
- Sidebar: `#0F172A` bg, `#E2E8F0` text, collapsed by default on mobile
- `st.switch_page()` for navigation, not `st.link_button()`
- `st.caption()` for parameter context under inputs
- Mobile (<640px): single column fallback
- Tablet (640–1024px): 2-column layouts
- Desktop: full 3-column rows + always-visible sidebar

## CSS & Design System
- Page: `#F1F5F9` | Card: `#FFFFFF` | Sidebar: `#0F172A`
- Primary: `#1B2A4A` | Accent: `#E8A838` | Muted: `#64748B`
- Cards: `border-radius: 16px`, `box-shadow: 0 2px 12px rgba(0,0,0,0.08)`
- Fonts: Poppins (headings) + Inter (body)
- Badge classes: .badge-mm1 .badge-mmc .badge-mgc .badge-mmc-k .badge-mgc-k .badge-erlang-a
- Health gauge: #27AE60 → #E8A838 → #C0392B (thresholds: 70%, 40%)
- WCAG AA contrast min 4.5:1 on all text
- Focus ring: `outline: 2px solid #E8A838; outline-offset: 2px`

## Data Visualization
- M/M/1, M/M/c → Line chart: utilization over λ range
- M/G/c, M/G/c/K → Box plot: service time distribution
- M/M/c/K → Heatmap: queue length vs arrival rate vs server count
- Erlang-A → Scatter: abandonment rate vs patience threshold
- SimPy → Time-series: queue length + utilization (dual y-axis)
- Monte Carlo → Histogram with KDE overlay
- Comparison → Grouped bar chart: current vs optimized
- All: `template='plotly_white'`, navy lines, gold highlights

## UX Patterns
- `st.success()` / `st.error()` after every major action
- Data validation before computation with clear messages
- CSV download buttons always visible on results tables
- Empty state: friendly CTA ('Upload your data to get started')
- Loading state: `st.spinner('Running SimPy simulation...')`
- Error recovery: specific fix suggestion, not generic message
- Tooltips on λ, μ, ρ, c via `help=` parameter

## Accessibility (a11y)
- Color-coded info must have text/icon fallback
- ARIA labels on custom chart wrappers
- Contrast: verify all badge colors at webaim.org/resources/contrastchecker
- `st.caption()` descriptions below every chart
- Keyboard: Tab order matches visual reading order
- Respect `prefers-reduced-motion` for Plotly animations
- Font size: min 14px body, 12px caption

## Code Structure
- `streamlit_app.py` — init, CSS, hero, shared sidebar
- `pages/1_current_metrics.py` — upload + compute
- `pages/2_optimization.py` — staffing recommendations
- `pages/3_simulation.py` — Monte Carlo + SimPy
- `pages/4_comparison.py` — current vs optimized
- `app_page_utils.py` — shared helpers
- `models/` — queue math modules
- `tests/` — pytest unit tests

## OpenCode Prompt Patterns
- Specify file path + function name on every request
- Perf: 'Wrap sidebar in `st.form(key="x_form")` in pages/[x].py'
- Style: 'Apply #1B2A4A/#E8A838 palette to [component] in [file]'
- Chart: 'Add dual y-axis SimPy time-series using plotly_white in pages/3_simulation.py'
- A11y: 'Add st.caption() below all Plotly charts in pages/[x].py'
- End all prompts: 'Output only changed code. No explanation unless error occurs.'
