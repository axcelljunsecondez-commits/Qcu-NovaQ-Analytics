# Phase 4 Design: React Frontend

**Date:** 2026-08-10
**Status:** Approved
**Branch:** `feature/production-saas`

## Objective

Build the production NovaMart frontend in React (Vite + TypeScript + React Router + TanStack Query + Plotly + i18next) consuming the Phase 3 FastAPI backend as the sole source of business/mathematical truth. No queueing math or business-decision logic in React. `legacy_streamlit/` stays alive until parity is demonstrated; it is never deleted.

## Architecture

- **Location:** `frontend/` (currently holds `public/locales/{en,tl}/translation.json`, the shared translation source).
- **Stack:** React 18, TypeScript strict, React Router v7, TanStack Query v5, react-plotly.js + plotly.js-dist-min, react-i18next + i18next (static JSON imports), axios (`withCredentials` + interceptors), Vitest + Testing Library + jsdom + user-event, ESLint (typescript-eslint flat config).
- **Dev proxy:** Vite :5173, `/api` → `http://localhost:8000` (same-origin cookie flow; production nginx already proxies `/api`).
- **Theme:** plain CSS variables replicating `legacy_streamlit/theme.py` tokens; light/dark via `data-theme`; palette `#E74C3C`, `#27AE60`, `#2E86AB`, `#E8A838`, `#C0392B`, `#5DADE2`; sidebar layout mirrors Streamlit.
- **CI:** new `frontend` job (node 20): npm ci → typecheck → lint → test → build. Python pipeline untouched.

## Auth

- Session/cookie model from Phase 3. `AuthProvider` + `/auth/me` query. `RequireAuth` route guard; `RequireRole("admin")` for `/admin`.
- CSRF: read `novamart_csrf` cookie, send `X-CSRF-Token` on non-GET requests when a session cookie exists.
- 401 interceptor → invalidate `me`, redirect `/login`. Nothing in localStorage except the UI language preference.
- No public signup, no billing, no multi-tenant auth.

## Pages

| Route | Content | API |
|---|---|---|
| `/login` | Email/password form | POST /auth/login, GET /auth/me |
| `/dashboard` | Greeting, workflow quick-actions, dataset stats | GET /datasets |
| `/datasets` | Upload (CSV/XLSX), validation banner, list, details, delete | POST/GET/DELETE /datasets |
| `/analysis` | Tabs: M/M/1, M/M/c, M/G/c, M/M/K, M/G/K, Erlang-A | POST /analysis/{model} |
| `/optimize` | Segments (from dataset or manual), batch optimize, KPI cards, staffing table, recommendations, save scenario, what-if (input scaling only) | POST /optimize, /optimize/batch, POST /scenarios |
| `/simulation` | Tabs: DES, Monte Carlo, Validate | POST /simulation/{des,mc,validate} |
| `/comparison` | Current vs optimized charts; saved-scenario comparison | GET /scenarios |
| `/reports` | Dataset/scenario picker → PDF/Excel blob download | GET /reports/.../{pdf,excel} |
| `/account` | Read-only profile (email, role, created_at), logout | GET /auth/me |
| `/admin` | User list, create, activate/deactivate | GET/POST/PATCH /admin/users |

Sidebar: nav, language selector (en/tl), theme toggle, cost parameters (`server_cost_per_hr`, `customer_waiting_cost`) passed to the API — never computed client-side.

## Charts (Plotly parity)

Exact figure configs from the Streamlit inventory: DES heatmap (RdYlGn_r, λ×c, hovertemplate), ρ/Lq dual-axis lines, max-queue bars, Lq histogram; MC ρ-mean/p95 lines + failure-rate bars; comparison radar (current `#E74C3C` / optimized `#27AE60`), utilization + server-count grouped bars, wait-time lines (×60 min), cost waterfall, scenario grouped bars. Queue-bar CSS color breaks at 0.85/1.0. No thresholds drawn on charts (Streamlit has none).

Radar 0–100 scores are presentation normalizations of API-supplied metrics only — documented chart utility, not business logic.

## i18n

- react-i18next consuming the two existing JSON files statically. ~40 new symmetric keys added to both files (`login.*`, `dashboard.*`, `datasets.*`, `analysis.*`, `simulation.*`, `compare.*`, `reports.*`, `account.*`, `admin.*`, `errors.*`). Additive — legacy loader unaffected.

## Testing

- Vitest + RTL, `vi.mock` on the api module. Coverage: login, route protection, dashboard loading, dataset upload + validation banner, analysis rendering (6 models), optimization rendering, simulation charts, comparison, reports download, account, admin role protection, en/tl switching (~35–45 tests).
- Backend contract verification before simulation/comparison units; backend changes only if a test proves a contract defect. Backend tests never weakened.

## Error states

Loading / empty / validation (422) / 401 / 403 / 5xx / upload-failure UI states via a shared `ApiState` component set.

## Implementation order (commit per unit)

1. Scaffold + theme + i18n + CI — 2. Auth — 3. Dashboard + shell — 4. Datasets — 5. Analysis — 6. Optimization — 7. Simulation — 8. Comparison — 9. Reports + Account — 10. Admin — 11. Final battery + Phase 4 report.

## Known parity gaps (reported, not hidden)

- No password-change endpoint → account is read-only.
- POS/chi-squared/KS ingestion is legacy-only (no backend endpoint) → gap.
- Saved-scenario comparison uses scenarios saved through the new API.
