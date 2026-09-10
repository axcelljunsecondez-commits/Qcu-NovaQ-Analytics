# Phase 4: React Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the production NovaMart React frontend (Vite + TypeScript + React Router + TanStack Query + Plotly + i18next) that reproduces the validated NovaMart workflows through the Phase 3 FastAPI backend, with zero queueing/business logic in the browser.

**Architecture:** React SPA in `frontend/` consuming the FastAPI API on `/api` (Vite dev proxy → localhost:8000; production nginx already proxies). Auth = Phase 3 session cookies + CSRF double-submit. All data fetched via typed api modules called from TanStack Query hooks; charts render API data verbatim; only radar 0–100 score normalization is computed client-side (documented presentation utility). `legacy_streamlit/` untouched.

**Tech Stack:** React 18.3, TypeScript strict, Vite 6, React Router v7, @tanstack/react-query v5, axios, react-plotly.js 2.6 + plotly.js-dist-min, react-i18next + i18next (static JSON imports), Vitest 3 + @testing-library/react 16 + jsdom + user-event, ESLint 9 flat config, GitHub Actions (node 20).

## Global Constraints

- No queueing math or business-decision logic in React — API is the single source of truth.
- Do NOT modify `queueing_engine/` formulas; do NOT change Phase 3 API behavior unless a frontend integration test proves a contract defect.
- Do NOT delete or modify `legacy_streamlit/`; do not remove Streamlit dependencies. Legacy i18n loader must keep working (translation edits are additive only — keys added to BOTH `frontend/public/locales/en/translation.json` and `tl/translation.json` in lockstep).
- Do NOT store passwords or session tokens in localStorage; only the UI language preference may be stored.
- No billing, no public signup, no multi-tenant authorization.
- Do NOT change `validate_with_simulation` behavior (λ/μ/c only; no theta/variance/K from optimized plans).
- Streamlit chart semantics must be preserved: labels, units, series, legends, tooltips, thresholds, utilization indicators, queue/waiting metrics. Exact figure configs in Task 7/8 chart specs.
- Commit per task (each logical unit separately). After each major page group run frontend tests + full Python battery (pytest, ruff, mypy, test_imports).
- Final report must include: architecture, pages, API endpoints consumed, parity status, frontend test count, typecheck/lint/build results, Python 276-test result, Streamlit 15-test result, known parity gaps, exit assessment. Do NOT claim full parity unless verified.

## File Structure (frontend/)

- `package.json`, `package-lock.json`, `vite.config.ts` (react plugin + `/api` proxy + vitest config), `tsconfig.json`, `tsconfig.node.json`, `eslint.config.js`, `index.html`, `.gitignore`
- `public/locales/{en,tl}/translation.json` — MODIFIED (additive new keys)
- `src/main.tsx` — entry; QueryClientProvider + i18n init + RouterProvider
- `src/App.tsx` — route table (createBrowserRouter)
- `src/lib/http.ts` — axios instance (`baseURL: '/api'`, `withCredentials`), 401 interceptor, CSRF header injection
- `src/lib/csrf.ts` — `getCsrfToken()`, `hasSessionCookie()` (document.cookie parsing)
- `src/lib/i18n.ts` — i18next init with static en/tl imports
- `src/auth/AuthProvider.tsx` — `/auth/me` query context; login/logout mutations
- `src/auth/RequireAuth.tsx`, `src/auth/RequireRole.tsx` — route guards
- `src/api/types.ts` — TS mirrors of Pydantic schemas (below)
- `src/api/{auth,datasets,analysis,optimization,simulation,scenarios,reports,users}.ts` — one typed function per endpoint
- `src/components/layout/{AppLayout,Sidebar,LanguageSelector,ThemeToggle}.tsx`
- `src/components/ui/{ApiState,MetricCard,ProgressBar,AlertBanner}.tsx`
- `src/components/charts/{Charts.tsx}` — all Plotly figure components (one file, each chart a named export)
- `src/pages/{LoginPage,DashboardPage,DatasetsPage,AnalysisPage,OptimizePage,SimulationPage,ComparisonPage,ReportsPage,AccountPage,AdminPage}.tsx`
- `src/styles/theme.css` (tokens from `legacy_streamlit/theme.py`), `src/styles/global.css`
- `src/test/setup.ts`, `src/test/test-utils.tsx` — jsdom setup, `renderWithProviders()`, `mockApi()` helper
- `.github/workflows/ci.yml` — MODIFIED: add `frontend` job

## API Type Contracts (verified against Phase 3; extend after Task 5/7 verification steps)

```ts
// types.ts — mirrors of FastAPI schemas
export type Role = "admin" | "analyst";
export interface UserOut { id: number; email: string; role: Role; active: boolean; created_at: string; }
export interface SegmentInput {
  time: string; lambda: number; mu: number; c: number;
  variance?: number; K?: number; theta?: number;
}
export interface OptimizationOut {
  time: string; lambda_: number; mu: number; c_current: number; c_optimal: number;
  rho_current: number | null; rho_optimal: number | null;
  Wq_current: number | null; Wq_optimal: number | null;
  Lq_current: number | null; Lq_optimal: number | null;
  cost_current: number | null; cost_optimal: number | null;
  delta_cost: number | null; delta_Wq: number | null; delta_Lq: number | null;
  delta_c: number; delta_rho: number | null;
  waiting_cost_current: number | null; waiting_cost_optimal: number | null;
  abandonment_cost_current: number | null; abandonment_cost_optimal: number | null;
  cost_per_server: number | null; current_stable: boolean; optimized_stable: boolean;
  recommendation: string; warning: string;
}
export interface DatasetOut {
  id: number; name: string; source_filename: string; source_format: string;
  row_count: number; validation: { ok: boolean; message: string };
  created_at: string; normalized: Record<string, unknown>[] | null;
}
export interface ScenarioOut {
  id: number; user_id: number; dataset_id: number | null; name: string;
  settings: Record<string, unknown>; results: Record<string, unknown>;
  created_at: string; updated_at: string;
}
```

Endpoint signatures used by pages:
- `login({email,password}) → {user: UserOut}` (cookies set by browser)
- `logout()`, `me() → {user: UserOut}`
- `listDatasets() → {datasets: DatasetOut[]}`; `uploadDataset(file, name?) → {dataset: DatasetOut}`; `getDataset(id)`; `deleteDataset(id)`
- `runAnalysis(model: 'mm1'|'mmc'|'mgc'|'mmck'|'mgck'|'erlang_a', segment: SegmentInput) → Record<string, number|string|boolean|null>` (verify exact keys in Task 5)
- `optimize(segment, opts?) → OptimizationOut`; `optimizeBatch(segments, opts?) → {results: OptimizationOut[]}` where opts `{target_utilization?, server_cost_per_hr?, customer_waiting_cost?, max_servers?}`
- `simulateDes(segments, {sim_hours?, queue_overload_threshold?, seed?})`; `simulateMc(segments, {num_trials?, failure_threshold?, seed?})`; `validateSimulation(segments)` — exact response key shapes verified in Task 7
- `listScenarios()`, `createScenario({name, settings, results, dataset_id?})`, `getScenario(id)`, `updateScenario(id, patch)`, `deleteScenario(id)`
- `reportUrl(kind: 'datasets'|'scenarios', id: number, format: 'pdf'|'excel') → '/api/reports/...'` (fetch blob)
- `listUsers()`, `createUser({email,password,role})`, `updateUser(id, {role?, active?})`

---

### Task 1: Scaffold frontend app, theme, i18n, CI job

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/eslint.config.js`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/styles/theme.css`, `frontend/src/styles/global.css`, `frontend/src/lib/i18n.ts`, `frontend/src/test/setup.ts`, `frontend/src/test/test-utils.tsx`, `.github/workflows/ci.yml` (modify)
- Modify: `frontend/public/locales/en/translation.json`, `frontend/public/locales/tl/translation.json`

**Interfaces:**
- Produces: `src/lib/i18n.ts` exporting `initI18n()`; `src/test/test-utils.tsx` exporting `renderWithProviders(ui, {route?, queryClient?})`; theme.css CSS variables `--color-primary/--color-danger/--color-success/--color-info/--color-warning/--bg/--card-bg/--text/--muted/--border`.

- [ ] **Step 1: Scaffold with Vite**

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
npm install @tanstack/react-query react-router-dom axios react-plotly.js@2.6.0 plotly.js-dist-min i18next react-i18next
npm install -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom @types/react-plotly.js @types/plotly.js
```
If `npm create vite` refuses a non-empty `frontend/` (it contains `public/locales/`), scaffold into a temp dir and copy the scaffold files over, keeping `public/locales/` intact. Verify: `frontend/public/locales/en/translation.json` still present.

- [ ] **Step 2: Pin React 18 and configure scripts**

In `frontend/package.json` set `"react": "18.3.1"`, `"react-dom": "18.3.1"`, `"@types/react": "^18"`, `"@types/react-dom": "^18"` (react-plotly.js 2.6 peer compatibility). Scripts: `"typecheck": "tsc --noEmit"`, `"lint": "eslint ."`, `"test": "vitest run"`, `"build": "tsc && vite build"`. Run `npm install`.

- [ ] **Step 3: vite.config.ts with proxy + vitest**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"], globals: true },
});
```

- [ ] **Step 4: tsconfig resolveJsonModule**

Add `"resolveJsonModule": true` to `compilerOptions` in `frontend/tsconfig.json` (needed for static translation imports). Keep scaffold strict settings.

- [ ] **Step 5: theme.css tokens from theme.py**

Read `legacy_streamlit/theme.py`; extract the CSS variable values (light/dark token dicts, palette hex codes). Create `src/styles/theme.css`:

```css
:root { --bg: #ffffff; --card-bg: #f9f9f9; --text: #0f172a; --muted: #64748b;
  --border: #e2e8f0; --primary: #2E86AB; --success: #27AE60; --danger: #C0392B;
  --warning: #E8A838; --red: #E74C3C; --info: #5DADE2; }
[data-theme="dark"] { --bg: #0f172a; --card-bg: #1e293b; --text: #f1f5f9;
  --muted: #94a3b8; --border: #334155; }
```
Overwrite values to match theme.py exactly. `src/styles/global.css`: app layout (sidebar fixed left 240px, content area), card, table, form, button, badge, alert classes, and the queue-bar component class (`.qbar` fill colors at ρ<0.85 `--success`, 0.85≤ρ<1 `--warning`, ρ≥1 `--danger`).

- [ ] **Step 6: Add ~45 new i18n keys to BOTH locale files (symmetric)**

Append to both `frontend/public/locales/en/translation.json` and `tl/translation.json` (English values; Tagalog translations for each — use existing tl file for tone, e.g. `login.title: "Mangyaring mag-login"`):
`login.{title,email,password,submit,error,invalid}`, `nav.{login,dashboard,datasets,analysis,optimize,simulate,compare,reports,account,admin,logout}`, `dashboard.{title,greeting,subtitle,quick_actions,datasets,last_upload,no_data,action}`, `datasets.{title,upload,upload_hint,valid_ok,valid_fail,delete,confirm_delete,empty,rows}`, `analysis.{title,model,tabs.mm1,tabs.mmc,tabs.mgc,tabs.mmck,tabs.mgck,tabs.erlang_a,params,run,results,rho,p0,lq,wq,theta,utilization}`, `simulation.{title,tabs.des,tabs.mc,tabs.validate,run,seed,trials,threshold,hours}`, `compare.{title,radar,utilization,servers,waiting,waterfall,scenarios}`, `reports.{title,pdf,excel,source_dataset,source_scenario,download}`, `account.{title,email,role,created,logout}`, `admin.{title,create,deactivate,activate,role,active,no_users}`, `errors.{unauthorized,forbidden,server,empty,upload}`, `common.{loading,save,cancel,back,current,optimized}`. Verify symmetry with a quick script comparing key sets.

- [ ] **Step 7: i18n.ts**

```ts
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "../../public/locales/en/translation.json";
import tl from "../../public/locales/tl/translation.json";
export function initI18n(): void {
  const saved = localStorage.getItem("novamart_lang");
  void i18n.use(initReactI18next).init({
    resources: { en: { translation: en }, tl: { translation: tl } },
    lng: saved === "tl" ? "tl" : "en", fallbackLng: "en", interpolation: { escapeValue: false },
  });
}
export const setLang = (l: string) => { void i18n.changeLanguage(l); localStorage.setItem("novamart_lang", l); };
```

- [ ] **Step 8: main.tsx + placeholder App**

`src/main.tsx`: `initI18n()`; create `QueryClient` (defaults `{staleTime: 30_000}`); render `<QueryClientProvider>` + `<RouterProvider router={router}/>` from `src/App.tsx` (createBrowserRouter with a single public `<Route path="/" element={<div>NovaMart</div>}/>` placeholder for now; routes grow in Tasks 2–10). `src/test/setup.ts`: `import "@testing-library/jest-dom/vitest"` + cleanup afterEach + `afterEach(() => { window.localStorage.clear(); })`.

- [ ] **Step 9: test-utils.tsx**

```tsx
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
export function renderWithProviders(ui: React.ReactElement, { route = "/", queryClient }: { route?: string; queryClient?: QueryClient } = {}) {
  const qc = queryClient ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter></QueryClientProvider>);
}
```

- [ ] **Step 10: CI frontend job**

In `.github/workflows/ci.yml` append a job (runs on push/PR, same triggers as existing):

```yaml
  frontend:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: frontend } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
      - run: npm run typecheck
      - run: npm run lint
      - run: npm test
      - run: npm run build
```

- [ ] **Step 11: Verify**

Run: `cd frontend; npm run typecheck; npm run lint; npm run build` — all pass (lint may need `eslint.config.js` minimal flat config: `import js from '@eslint/js'; import tseslint from 'typescript-eslint'` with recommended sets, ignores `dist`). Verify legacy still works: `python -c "import sys; sys.path.insert(0,'legacy_streamlit'); import i18n; print(i18n.t('nav.upload'))"` prints the translated string and `frontend/public/locales/{en,tl}/translation.json` key sets are identical.

- [ ] **Step 12: Commit**

```bash
git add frontend .github/workflows/ci.yml
git commit -m "Phase 4 Unit 1: scaffold Vite+React+TS app, theme tokens, i18n keys, frontend CI job"
```

---

### Task 2: Auth (login, session, CSRF, route guards)

**Files:**
- Create: `src/lib/csrf.ts`, `src/lib/http.ts`, `src/api/auth.ts`, `src/api/types.ts`, `src/auth/AuthProvider.tsx`, `src/auth/RequireAuth.tsx`, `src/auth/RequireRole.tsx`, `src/pages/LoginPage.tsx`
- Modify: `src/App.tsx`, `src/test/test-utils.tsx` (add `createTestProviders` with mocked api via `vi.mock`), `public/locales/{en,tl}/translation.json` (login keys from Task 1 already present)

**Interfaces:**
- Produces: `AuthProvider` context value `{user: UserOut | null, isLoading: boolean, login(email,password), logout()}`; `useAuth()` hook; `RequireAuth` (redirect `/login` when unauthenticated, `state.from` preserved); `RequireRole role="admin"` (render 403 page for analysts).

- [ ] **Step 1: Write failing tests — `src/pages/LoginPage.test.tsx`**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/test-utils";
import { LoginPage } from "./LoginPage";

vi.mock("../api/auth", () => ({
  login: vi.fn(async () => ({ user: { id: 1, email: "a@b.c", role: "admin", active: true, created_at: "2026-01-01T00:00:00Z" } })),
  me: vi.fn(async () => ({ user: { id: 1, email: "a@b.c", role: "admin", active: true, created_at: "2026-01-01T00:00:00Z" } })),
  logout: vi.fn(async () => {}),
}));
```
Tests: (1) renders email/password fields and submit; (2) submitting valid credentials calls `login` and shows the user's email; (3) login failure (mock rejects 401) shows the translated error message `login.error`; (4) translation: with `initI18n()` + `setLang("tl")` the submit label renders the Tagalog string (assert via `i18n.t`-aware query — render after `await act`). 4 tests.

- [ ] **Step 2: Run to verify failure** — `npm test` → LoginPage tests fail (module missing).

- [ ] **Step 3: Implement csrf.ts, http.ts, api/auth.ts, types.ts**

```ts
// csrf.ts
export function getCsrfToken(): string | null {
  return document.cookie.split("; ").find((c) => c.startsWith("novamart_csrf="))?.split("=")[1] ?? null;
}
export function hasSessionCookie(): boolean {
  return document.cookie.split("; ").some((c) => c.startsWith("novamart_session="));
}
```
```ts
// http.ts
import axios from "axios";
import { getCsrfToken, hasSessionCookie } from "./csrf";
export const http = axios.create({ baseURL: "/api", withCredentials: true });
http.interceptors.request.use((config) => {
  const method = (config.method ?? "get").toUpperCase();
  if (method !== "GET" && hasSessionCookie()) {
    config.headers["X-CSRF-Token"] = getCsrfToken() ?? "";
  }
  return config;
});
```
`api/auth.ts`: `login = (body) => http.post("/auth/login", body).then(r => r.data)`, `logout = () => http.post("/auth/logout").then(r => r.data)`, `me = () => http.get("/auth/me").then(r => r.data)`. All typed via `src/api/types.ts`.

- [ ] **Step 4: AuthProvider + guards + LoginPage**

`AuthProvider`: `useQuery({queryKey:["me"], queryFn: me, retry: false})`; `login` = `useMutation` → on success `queryClient.invalidateQueries({queryKey:["me"]})`; `logout` similar + `navigate("/login")` handled by caller. `RequireAuth`: if `isLoading` → spinner; if `!user` → `<Navigate to="/login" replace state={{from: location}}/>`; else render children via `<Outlet/>`. `LoginPage`: form (email/password), on submit call `login`; on error show `t("login.error")`; on success `navigate(from ?? "/dashboard")`. Wire `login`, `/dashboard` (placeholder), `login` public routes in `App.tsx`. 401 interceptor in `http.ts`: `response.use(undefined, (error) => { if (error.response?.status === 401) { queryClient.invalidateQueries({queryKey:["me"]}); } return Promise.reject(error); })` — implement by exporting a small event or importing a singleton `queryClient` from `src/lib/queryClient.ts` (create `src/lib/queryClient.ts` exporting the QueryClient used in main.tsx and http.ts).

- [ ] **Step 5: Run tests** — `npm test` passes; also `npm run typecheck && npm run lint`.

- [ ] **Step 6: Live smoke test (real backend)**

Backend must be running (Phase 3 compose or `uvicorn backend.api.main:app`). Seed admin `admin@example.com` / `admin123` if not present (`python -m backend.db.seed --email admin@example.com --password admin123 --role admin`). Run `npm run dev`, open http://localhost:5173/login, log in, confirm redirect to /dashboard and `/auth/me` returns the user. Manual check only (no automated e2e for this).

- [ ] **Step 7: Full Python battery** — `python -m pytest tests/ -q` (276 pass), `ruff check .`, `mypy .`.

- [ ] **Step 8: Commit**

```bash
git add frontend/src frontend/public/locales
git commit -m "Phase 4 Unit 2: session auth, CSRF client, route guards, login page"
```

---

### Task 3: App shell (sidebar, theme toggle, language selector) + Dashboard

**Files:**
- Create: `src/components/layout/AppLayout.tsx`, `src/components/layout/Sidebar.tsx`, `src/components/layout/LanguageSelector.tsx`, `src/components/layout/ThemeToggle.tsx`, `src/components/ui/ApiState.tsx`, `src/components/ui/MetricCard.tsx`, `src/components/ui/ProgressBar.tsx`, `src/pages/DashboardPage.tsx`
- Modify: `src/App.tsx` (wrap protected pages in `AppLayout`), `src/styles/global.css`

**Interfaces:**
- Produces: `AppLayout` (sidebar + `<Outlet/>`), `ApiState` exports `Loading`, `Empty({message})`, `ErrorState({error})`, `Forbidden()`; `MetricCard({label, value, sub?, tone?})`; `ProgressBar({value: number(0-1), label?})`.
- Consumes: `useAuth()`, `listDatasets()`.

- [ ] **Step 1: Write failing tests**

`DashboardPage.test.tsx`: mock `../api/datasets` with `listDatasets: vi.fn()`; tests: (1) shows loading spinner then dataset count/stat cards after resolve; (2) empty state renders `dashboard.no_data` when `{datasets: []}`; (3) renders workflow quick-action links (5 links: datasets, analysis, optimize, simulate, comparison). `AppLayout` render check: sidebar contains nav links and the language selector. 5 tests total. Also `MetricCard`/`ProgressBar` snapshot-less render tests.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement shell**

`Sidebar`: brand block ("NovaMart", `t("app.title")`), NavLinks (dashboard/datasets/analysis/optimize/simulation/comparison/reports/account/admin — admin shown only when `user.role==="admin"`), `LanguageSelector` (two buttons EN/TL calling `setLang`, active state), `ThemeToggle` (toggles `document.documentElement.dataset.theme`, persists `localStorage "novamart_theme"`), logout button calling `useAuth().logout` then navigate `/login`. `AppLayout`: flex layout, sidebar fixed, `<main>` renders `<Outlet/>` with `<Suspense>` fallback.

- [ ] **Step 4: Dashboard**

`useQuery({queryKey:["datasets"], queryFn: listDatasets})`; greeting `t("dashboard.greeting")` + user email; stat cards: dataset count, last upload date (max created_at), `MetricCard` for each; quick-action cards (5) linking to pages; empty state via `ApiState.Empty` when no datasets. Dashboard render errors → `ApiState.ErrorState`.

- [ ] **Step 5: Run tests + typecheck + lint; commit** (`git commit -m "Phase 4 Unit 3: app shell, sidebar, theme/language toggles, dashboard page"`).

---

### Task 4: Datasets (upload, validation feedback, list, details, delete)

**Files:**
- Create: `src/api/datasets.ts`, `src/pages/DatasetsPage.tsx`
- Modify: `src/App.tsx` (route), `src/components/ui/` as needed

**Interfaces:**
- Consumes: `DatasetOut`, `listDatasets/uploadDataset/deleteDataset`.
- Produces: `DatasetsPage` with `useMutation(upload)` (multipart `FormData` via `http.post("/datasets", fd, {headers:{"Content-Type":"multipart/form-data"}})`) and `useMutation(delete)`; validation banner component from `dataset.validation`.

- [ ] **Step 1: Write failing tests — `DatasetsPage.test.tsx`**

Mock `../api/datasets`. Tests: (1) renders upload drop zone + file input; (2) `uploadDataset` called with File when a file is chosen (simulate via `fireEvent.change` on input with a `File`), success shows `datasets.valid_ok` banner when `validation.ok`; (3) validation failure banner shows `validation.message`; (4) upload rejection (mock rejects) shows `errors.upload`; (5) dataset list renders name, source_filename, row_count, delete buttons; (6) delete click calls `deleteDataset(id)` and refetches; (7) empty list shows `datasets.empty`. 7 tests.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement `api/datasets.ts`**

```ts
export const listDatasets = () => http.get("/datasets").then(r => r.data);
export const uploadDataset = (file: File, name?: string) => {
  const fd = new FormData();
  fd.append("file", file);
  if (name) fd.append("name", name);
  return http.post("/datasets", fd).then(r => r.data);
};
export const deleteDataset = (id: number) => http.delete(`/datasets/${id}`).then(r => r.data);
```

- [ ] **Step 4: Implement page**

Left panel: file input (accept `.csv,.xlsx,.xls`), upload button (disabled while pending); on success show validation banner (green `datasets.valid_ok` when `ok`, red banner with `message` otherwise) and refetch list. Right panel: table of datasets (name, source_filename, row_count, created_at, validation badge, delete button with `confirm()` dialog). `ApiState.Loading` while fetching; `ErrorState` on failure. Details: expandable row showing `normalized` first 5 rows as a mini table + `validation.message`.

- [ ] **Step 5: Contract verification against live API**

Run backend; `curl -F "file=@tests/fixtures/sample.csv" -b cookies -H "X-CSRF-Token: ..." http://localhost:8000/api/datasets` and confirm the JSON key names match `DatasetOut` (especially list endpoint key `datasets` and upload key `dataset`). If names differ, fix `types.ts` + page accordingly (backend contract intact).

- [ ] **Step 6: Run tests + typecheck + lint + Python battery; commit** (`git commit -m "Phase 4 Unit 4: datasets upload/list/delete with validation feedback"`).

---

### Task 5: Analysis (M/M/1, M/M/c, M/G/c, M/M/K, M/G/K, Erlang-A)

**Files:**
- Create: `src/api/analysis.ts`, `src/pages/AnalysisPage.tsx`, `src/components/analysis/AnalysisForm.tsx`, `src/components/analysis/AnalysisResults.tsx`
- Modify: `src/App.tsx` (route), `src/api/types.ts` (AnalysisOut per-model)

**Interfaces:**
- Produces: `runAnalysis(model, segment) → AnalysisOut`; `AnalysisOut = Record<string, number | string | boolean | null>` with at least `time, lambda_, mu, c, rho, P0, Lq, Wq` plus model extras (`service_variance` mgc/mgck, `K` mmck/mgck, `theta` erlang_a).
- Consumes: `SegmentInput`.

- [ ] **Step 1: Contract verification (run BEFORE writing types)**

With backend running: `curl -X POST http://localhost:8000/api/analysis/mm1 -H "Content-Type: application/json" -d '{"segment":{"time":"t","lambda":30,"mu":12,"c":1}}'` (cookies optional — stateless exempt endpoint). Record the exact JSON keys for each of the 6 models (`mm1`, `mmc`, `mgc`, `mmck`, `mgck`, `erlang_a`) into `src/api/types.ts` as `AnalysisOut`. If any model 404s/422s unexpectedly, stop and report the contract defect — do not implement workarounds.

- [ ] **Step 2: Write failing tests — `AnalysisPage.test.tsx`**

Mock `../api/analysis` with `runAnalysis: vi.fn()`. Tests: (1) renders model tabs for all 6 models with translated labels; (2) default M/M/1 form shows λ, μ, c inputs and run button; (3) submitting calls `runAnalysis("mm1", {time, lambda, mu, c: 1})`; (4) results render metric cards: utilization (ρ), P0, Lq, Wq with 2-decimal formatting; (5) Erlang-A tab adds θ input and passes `theta`; (6) M/M/K tab adds K input; (7) API 422 renders field error message. 7 tests.

- [ ] **Step 3: Implement**

`AnalysisForm`: model-dependent extra fields — mm1: λ, μ (c fixed 1); mmc: + c; mgc: + variance; mmck: + c, K; mgck: + c, K, variance; erlang_a: + c, θ. `time` input default `"Segment 1"`. Submit → `runAnalysis` → `AnalysisResults`: `MetricCard` grid (ρ with ProgressBar, P0, Lq, Wq) + model extras row + small note with translated model name. 422 handling: map `detail` array items (loc/msg) to inline field errors.

- [ ] **Step 4: Run tests + typecheck + lint; commit** (`git commit -m "Phase 4 Unit 5: analysis page for all six queueing models"`).

---

### Task 6: Optimization (single/batch, staffing table, recommendations, save scenario, what-if)

**Files:**
- Create: `src/api/optimization.ts`, `src/api/scenarios.ts`, `src/pages/OptimizePage.tsx`
- Modify: `src/App.tsx`, `src/components/ui/` (table styles)

**Interfaces:**
- Produces: `optimizeBatch(segments, opts)`, `createScenario({name, settings, results})`; page state: `results: OptimizationOut[]`, `segments` sourced from a selected dataset's `normalized` rows (via `GET /datasets/{id}`) or manual rows.
- Consumes: `OptimizationOut`, `SegmentInput`.

- [ ] **Step 1: Write failing tests — `OptimizePage.test.tsx`**

Mock `../api/optimization` and `../api/scenarios` and `../api/datasets`. Tests: (1) source selector (dataset picker / manual rows); (2) dataset source: selecting a dataset calls `getDataset` and its `normalized` rows are posted to `optimizeBatch` on run; (3) KPI cards render from first result: `cost_current`, `cost_optimal`, `delta_cost` (savings), `delta_c` (server change); (4) staffing table renders rows with time, c_current, c_optimal, rho_current/rho_optimal progress bars, `recommendation` text; (5) save-scenario form calls `createScenario({name, settings: {target_utilization}, results: {results}})`; (6) what-if: λ multiplier 1.5 scales the λ values sent to the API (assert mock called with scaled input, no client math beyond multiplication of user input); (7) warning banner shown when a row has non-empty `warning`. 7 tests.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement api modules**

```ts
// optimization.ts
export const optimizeBatch = (segments: SegmentInput[], opts: { target_utilization?: number; server_cost_per_hr?: number; customer_waiting_cost?: number; max_servers?: number } = {}) =>
  http.post("/optimize/batch", { segments, ...opts }).then(r => r.data);
```
`scenarios.ts`: `listScenarios`, `createScenario`, `updateScenario`, `deleteScenario` via `/scenarios` endpoints.

- [ ] **Step 4: Implement page**

Params panel: target utilization (0.70 default), max servers (24), server cost/hr (87), customer waiting cost/hr (100) — all sent to API. Source: select dataset (fetch `normalized` rows → map to `SegmentInput` preserving variance/K/theta when present) or manual rows table (add row: time, λ, μ, c). Run → batch. Results: KPI cards (Current Cost, Optimized Cost, Savings `delta_cost` absolute + %, Server Change `delta_c`), table (time, c_current→c_optimal with arrow, ρ bars, Wq min both, stable badges), recommendation list from rows' `recommendation`. Save scenario: name input → `createScenario` with `results: {results}`. What-if panel: three multipliers (λ, server cost, wait cost) applied to form values before POST (documented as input scaling, not business logic).

- [ ] **Step 5: Run tests + typecheck + lint + Python battery; commit** (`git commit -m "Phase 4 Unit 6: optimization page with batch results, recommendations, scenario save"`).

---

### Task 7: Simulation (DES, Monte Carlo, Validate) + simulation charts

**Files:**
- Create: `src/api/simulation.ts`, `src/pages/SimulationPage.tsx`, `src/components/charts/Charts.tsx` (DES + MC figures)
- Modify: `src/api/types.ts` (SimDesOut, SimMcOut, SimValidateOut)

**Interfaces:**
- Produces: `simulateDes(segments, opts)`, `simulateMc(segments, opts)`, `validateSimulation(segments)`; typed outputs after contract verification.
- Consumes: `SegmentInput`; charts export `UtilizationHeatmap`, `RhoLqLines`, `MaxQueueBars`, `LqHistogram`, `RhoMeanP95Lines`, `FailureRateBars`.

- [ ] **Step 1: Contract verification (run BEFORE writing types)**

With backend running, POST sample segments (from an uploaded dataset's normalized rows, or the mm1 sample above) to `/api/simulation/des`, `/api/simulation/mc`, `/api/simulation/validate`. Record exact response key names and structures into `types.ts` (expect DES rows with `time, rho_sim, Lq_sim, max_queue, status`; MC rows with `time, rho_mean, rho_p95, failure_rate`; validate output shape with `sim_status/sim_max_queue/sim_Wq/sim_rho/mc_failure_rate/mc_adequate/mc_rho_mean/mc_rho_p95/mc_Wq_ci` — align with `backend/queueing_engine/services/simulation.py` summary functions). If any endpoint 404s/422s on valid input, stop and report the contract defect.

- [ ] **Step 2: Write failing tests — `SimulationPage.test.tsx`**

Mock `../api/simulation`. Tests: (1) three tabs (DES/MC/Validate) with translated labels; (2) DES run posts segments + defaults (sim_hours 24, threshold 20, seed "42"→42) and renders KPI row (stable/critical counts) — assert from mocked response fields; (3) DES charts render: `UtilizationHeatmap` receives pivot data (assert via container query for `.plotly` class presence, `data-testid="chart-utilization-heatmap"`), `RhoLqLines`, `MaxQueueBars`, `LqHistogram` present; (4) MC run posts `num_trials=500, failure_threshold=0.75` and renders `RhoMeanP95Lines` + `FailureRateBars`; (5) Validate tab posts to `validateSimulation` and renders a table with `sim_status`/`mc_failure_rate` columns and a pass/fail banner (adequate threshold `mc_adequate`); (6) blank/invalid seed sends `seed: null` (parity with legacy test #14); (7) null `rho_sim` rows render queue-bars without "nan%" text (parity with legacy test #15). 7 tests.

- [ ] **Step 3: Implement api module + charts (exact legacy configs)**

```ts
export const simulateDes = (segments: SegmentInput[], opts: { sim_hours?: number; queue_overload_threshold?: number; seed?: number | null } = {}) =>
  http.post("/simulation/des", { segments, ...opts }).then(r => r.data);
// simulateMc, validateSimulation analogous
```
Charts (all via `react-plotly.js` `<Plot data={} layout={} style={{width:"100%"}}/>`, wrapped in a `<div data-testid>`):
- `UtilizationHeatmap`: pivot (index c, columns lambda, values rho_sim*100 mean) → `go.Heatmap`-equivalent `{type:"heatmap", z, x: lambdas, y: cs, colorscale:"RdYlGn_r", zmin:0, zmax:100, hovertemplate:"λ=%{x}<br>c=%{y}<br>ρ=%{z:.1f}%<extra></extra>"}`; layout title `t("simulation.heatmap.title")`, xaxis `t("simulation.heatmap.x")` "Arrival Rate λ", yaxis "Servers c", height 300.
- `RhoLqLines`: two scatter traces — `rho_sim` color `#E8A838`, name "ρ sim", yaxis "y"; `Lq_sim` color `#2E86AB`, yaxis "y2" overlaying right; legend horizontal y 1.12, height 350.
- `MaxQueueBars`: bars color `#C0392B`, height 350.
- `LqHistogram`: histogram nbinsx 20 color `#5DADE2`, height 300.
- `RhoMeanP95Lines`: `rho_mean` `#E8A838` solid w2; `rho_p95` `#C0392B` dashed; height 350.
- `FailureRateBars`: bars `#C0392B`, height 350.
Queue-bar CSS component (`.qbar`): `width: min(rho,1)*100%`, fill `--success` <0.85, `--warning` <1, `--danger` ≥1 — legacy parity.

- [ ] **Step 4: Implement page**

Source segments: reuse OptimizePage source pattern (dataset or manual). DES tab: hours (24), overload threshold (20), seed text (default "42", invalid→null). MC tab: trials (500), failure threshold (0.75). Validate tab: run on chosen segments, table + banner. Layout: controls card, KPIs, charts grid, per-segment queue bars.

- [ ] **Step 5: Run tests + typecheck + lint + Python battery; commit** (`git commit -m "Phase 4 Unit 7: simulation page with DES/MC/validate and plotly chart parity"`).

---

### Task 8: Comparison (current vs optimized charts, saved scenarios)

**Files:**
- Create: `src/pages/ComparisonPage.tsx`; extend `src/components/charts/Charts.tsx` with `RadarChart`, `UtilizationCompareBars`, `ServerCompareBars`, `WaitTimeLines`, `CostWaterfall`, `ScenarioCompareBars`
- Modify: `src/api/scenarios.ts` (already exists), `src/lib/radar.ts` (new — radar score normalization)

**Interfaces:**
- Produces: `computeRadarScores(rows, {current}: {current:boolean})` — pure function returning `{r: number[], theta: string[]}`; charts above.
- Consumes: `listScenarios()`, `OptimizationOut[]` from scenario results.

- [ ] **Step 1: Write failing tests**

`ComparisonPage.test.tsx` (mock `../api/scenarios`): (1) scenario picker lists scenarios and loads first; (2) renders `RadarChart`, `UtilizationCompareBars`, `ServerCompareBars`, `WaitTimeLines`, `CostWaterfall` (assert via data-testid); (3) scenario compare: multi-select 2 scenarios renders `ScenarioCompareBars`; (4) empty state when no scenarios. `radar.test.ts`: exact formula parity — `cost: 100*(1-cost/max)`, `wait: 100*(1-wq/max)`, `utilization: max(0,100*(1-|0.85-rho|))`, `stability: current? 100*(1-mc_fail) : 100*(1-mc_fail*0.6)`, `server: 100*(1-c/max)`, clamped 0–100 (assert a concrete fixture → expected values). 6 tests.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement radar.ts + charts**

`radar.ts` normalizes API-supplied comparison rows only (documented presentation utility — no queueing math). Charts (exact legacy configs): radar two traces `fill:"toself"`, current `#E74C3C`/`rgba(231,76,60,0.15)`, optimized `#27AE60`/`rgba(39,174,96,0.15)`, radialaxis 0–100; utilization + server grouped bars (`barmode:"group"`, red/green, ×100 for ρ); wait-time lines (Wq*60 minutes, red/green w2 marker 4); waterfall (`relative×4 + total`, decreasing `#27AE60`, increasing `#E74C3C`, totals `#2E86AB`, connector `#94A3B8`); scenario bars palette `["#2E86AB","#A23B72","#F18F01","#C73E1D","#3B1F2B"]` mod index.

- [ ] **Step 4: Implement page**

Scenario picker (dropdown of `listScenarios()`); main view computes rows from selected scenario `results.results` (fall back to `results.comparison`); charts grid; saved-scenarios expander with multiselect ≥2 → `ScenarioCompareBars` (Wq_optimal*60). Note: current-vs-optimized data all comes from stored scenario rows — no local computation beyond ×60/×100 unit conversions and radar normalization.

- [ ] **Step 5: Run tests + typecheck + lint; commit** (`git commit -m "Phase 4 Unit 8: comparison page with radar, bars, wait-time, waterfall charts"`).

---

### Task 9: Reports + Account

**Files:**
- Create: `src/api/reports.ts`, `src/pages/ReportsPage.tsx`, `src/pages/AccountPage.tsx`
- Modify: `src/App.tsx`

**Interfaces:**
- Produces: `fetchReport(kind, id, format) → Blob` (via axios `responseType:"blob"`), `downloadReport` helper triggering browser download.
- Consumes: `listDatasets()`, `listScenarios()`, `useAuth()`.

- [ ] **Step 1: Write failing tests**

`ReportsPage.test.tsx` (mock `../api/datasets`, `../api/scenarios`, `../api/reports`): (1) dataset source select → PDF/Excel buttons; (2) clicking PDF calls `fetchReport("datasets", id, "pdf")` and triggers an anchor download (assert `URL.createObjectURL` mocked + anchor click — stub `HTMLAnchorElement.prototype.click`); (3) scenario source select → buttons call `fetchReport("scenarios", id, "excel")`; (4) empty states when no datasets/scenarios. `AccountPage.test.tsx`: (1) renders email, role, created_at from `me()`; (2) logout button calls `logout()` and navigates to `/login`. 6 tests.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

```ts
// reports.ts
export const fetchReport = async (kind: "datasets" | "scenarios", id: number, format: "pdf" | "excel") => {
  const res = await http.get(`/reports/${kind}/${id}/${format}`, { responseType: "blob" });
  return res.data as Blob;
};
```
`downloadReport(blob, filename)`: createObjectURL + temporary `<a download>` click + revoke. `ReportsPage`: two cards (Datasets / Scenarios) each with a select + PDF/Excel buttons; disable while fetching; success → toast `reports.download`. `AccountPage`: profile card (email, role badge, created_at formatted via `Intl.DateTimeFormat`), logout button; note: no password change endpoint exists (parity gap documented in final report).

- [ ] **Step 4: Live smoke check** — with backend up and a dataset present, click through dataset PDF download; verify file opens.

- [ ] **Step 5: Run tests + typecheck + lint; commit** (`git commit -m "Phase 4 Unit 9: reports download page and account profile page"`).

---

### Task 10: Admin (user management, role protection)

**Files:**
- Create: `src/api/users.ts`, `src/pages/AdminPage.tsx`
- Modify: `src/App.tsx` (admin route wrapped in `RequireRole role="admin"`)

**Interfaces:**
- Consumes: `listUsers/createUser/updateUser`; `RequireRole`.
- Produces: AdminPage with users table (email, role, active badge, created_at), create-user form (email/password/role), activate/deactivate toggle.

- [ ] **Step 1: Write failing tests**

`AdminPage.test.tsx` (mock `../api/users`): (1) analyst user sees `Forbidden` (403 component) — render with `useAuth` mocked to analyst; (2) admin sees users table; (3) create-user form calls `createUser({email, password, role})`; (4) deactivate button calls `updateUser(id, {active: false})`; (5) duplicate-email 409 shows translated error. Route-guard test in `RequireRole.test.tsx`: analyst navigating to `/admin` renders Forbidden, admin renders page. 6 tests.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

`api/users.ts`: `listUsers`, `createUser`, `updateUser(id, patch)` — PATCH sends `{role?, active?}` only. AdminPage: table + form; validation errors from 422 rendered inline; 409 duplicate email banner; deactivation confirm dialog. `RequireRole`: reads `useAuth().user?.role`, renders `<Forbidden/>` when insufficient (never redirects — spec: handle 403 correctly).

- [ ] **Step 4: Run tests + typecheck + lint + Python battery; commit** (`git commit -m "Phase 4 Unit 10: admin user management with role-gated route"`).

---

### Task 11: Final battery + Phase 4 report

**Files:**
- Create: `docs/superpowers/reports/2026-08-10-phase4-react-frontend-report.md`

- [ ] **Step 1: Full frontend gates** — `cd frontend && npm run typecheck && npm run lint && npm test && npm run build`. Record counts (expected ~40+ component tests).

- [ ] **Step 2: Full Python battery** — `python -m pytest tests/ -q` (276 passed), `python -m ruff check .`, `python -m mypy .`, `python test_imports.py`, `pip-audit -r requirements.txt --strict`.

- [ ] **Step 3: Streamlit E2E battery** — `python -m pytest tests/test_dashboard_e2e.py -q` (15 passed). Confirm `legacy_streamlit/` files untouched: `git status` clean apart from intended files.

- [ ] **Step 4: Manual parity pass** — with backend running, walk: login → upload sample CSV (reuse `legacy_streamlit` sample generator or a fixture) → analysis M/M/1 → optimize → simulate DES/MC → validate → compare → reports PDF → account → (admin) create user. Note anything that fails; fix within scope (no backend behavior changes unless a contract defect is proven).

- [ ] **Step 5: Write final report** (required sections): frontend architecture; pages implemented (10); API endpoints consumed (table); feature parity status per capability (upload ✓, validation ✓, M/M/1 ✓, M/M/c ✓, M/G/c ✓, M/M/K ✓, M/G/K ✓, Erlang-A ✓, optimization ✓, DES ✓, MC ✓, validation ✓, comparison ✓, scenarios ✓, PDF ✓, Excel ✓, en/tl ✓, account ✓, admin ✓ — each marked verified or gap); frontend test count; typecheck/lint/build results; Python 276-test result; Streamlit 15-test result; screenshots/visual verification notes (browser manual pass); known parity gaps (POS ingestion legacy-only, account password change absent, scenario comparison requires API-saved scenarios); Phase 4 exit assessment. Commit.

- [ ] **Step 6: STOP** — no Phase 5 work.

---

## Self-Review Notes (checked before execution)

- Spec coverage: every page in the approved design maps to Tasks 2–10; i18n parity, error states, CSRF, route guards, CI, and the radar-normalization caveat are explicit tasks/steps.
- Contracts: `SegmentInput`, `OptimizationOut` (27 keys), `DatasetOut`, `ScenarioOut` come from Phase 3 code; `AnalysisOut`/simulation outputs are contract-verified at Task 5/7 step 1 before use — no placeholders.
- Legacy safety: Task 1 step 6 verifies locale key-set symmetry; legacy i18n loader only reads JSON, additive keys are safe.
- No queueing math in React: only radar normalization (Task 8), unit conversions (×60/×100), and user-input scaling (Task 6 what-if) — each documented in plan and code.
