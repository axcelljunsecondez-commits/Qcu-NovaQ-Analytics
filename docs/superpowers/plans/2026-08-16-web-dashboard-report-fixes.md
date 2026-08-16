# Web Dashboard Report Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the functional bugs found in the web dashboard review: advanced queueing models silently dropped on the Optimize page, dataset reports generating empty/bogus content, missing abandonment cost support, and a Simulation Validate tab that validates the wrong plan and reports the wrong verdict.

**Architecture:** Frontend-only fix for model-column passthrough (backend `SegmentInput` already supports `variance/K/theta` — frozen contract untouched). Backend fix maps dataset metrics into the comparison-table shape the PDF/Excel generators expect, and makes exec-summary bullets honest when only current (or neither) KPI set is present. Validate tab gains editable plan + MC settings with shared defaults; one additive backend change (`ValidateRequest.seed` nullable).

**Tech Stack:** TypeScript/React 19 + Vitest (frontend); FastAPI + pandas + reportlab/openpyxl (backend); gates per AGENTS.md.

## Global Constraints

- Queueing-engine contracts frozen: no breaking changes to `backend/api/` request/response shapes. Only additive change allowed (and planned): `ValidateRequest.seed: int | None`.
- Model selection stays in `model_selection.py` (never re-implement dispatch inline).
- i18n: any new label/string must be added to BOTH `frontend/public/locales/en/translation.json` and `frontend/public/locales/tl/translation.json` (keys must stay symmetric).
- Reports use minutes for wait times (Wq × 60).
- Legacy Streamlit callers of `generate_pdf_report`/`generate_excel_report` must keep working unchanged (2-positional-arg calls, `segment_df=` keyword). Legacy PDF output must stay byte-identical when both KPI sets are present.
- Legacy behavior parity for validation verdict: pass = no `sim_status` in {Critical, Unstable} AND `mc_failure_rate ≤ 5%` (`legacy_streamlit/pages/2_optimization.py:137-152`).
- Seed semantics in engine: `seed=None` = true stochasticity; `seed=0` = deterministic. Empty seed input → `null` → random.
- Repo branch: `rename/novaq` (never commit to main/master). Commits: one per task, concise messages matching repo style.

---

### Task 1: Optimize page passes `variance`/`K`/`theta` to `/optimize/batch`

**Files:**
- Modify: `frontend/src/pages/OptimizePage.tsx:41-55` (`SegmentRow` interface + `segmentsOf()`)
- Test: `frontend/src/pages/OptimizePage.test.tsx` (add one `it` block)

**Interfaces:**
- Consumes: `DatasetOut.normalized` rows (`Record<string, unknown>[]` with optional `variance/K/theta`), backend `SegmentInput` (`variance: float|None ge=0`, `K: int|None ge=1`, `theta: float|None ge=0`, aliases `lambda` — `backend/api/optimization.py:16-24`).
- Produces: `SegmentRow` with optional `variance?: number`, `K?: number`, `theta?: number` — keys only present when valid, so existing M/M/c payloads are byte-identical.

- [ ] **Step 1: Write the failing test** — append to `OptimizePage.test.tsx`:

```ts
it('passes advanced model columns (variance/K/theta) from the dataset to optimizeBatch', async () => {
  getDatasetMock.mockResolvedValue({
    dataset: {
      ...dataset,
      normalized: [
        { time: '08:00-09:00', lambda: 30, mu: 12, c: 3, variance: 4.5, K: 6, theta: 0.5 },
        { time: '09:00-10:00', lambda: 45, mu: 12, c: 4, variance: 3.2, theta: 0.25 },
        { time: '10:00-11:00', lambda: 50, mu: 12, c: 4, K: 5 },
      ],
    },
  })
  const user = userEvent.setup()
  renderWithProviders(<OptimizePage />, { route: '/optimize' })
  await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
  await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
  await user.click(screen.getByRole('button', { name: 'Optimize' }))
  await waitFor(() => {
    expect(optimizeBatchMock).toHaveBeenCalledWith(
      [
        { time: '08:00-09:00', lambda: 30, mu: 12, c: 3, variance: 4.5, K: 6, theta: 0.5 },
        { time: '09:00-10:00', lambda: 45, mu: 12, c: 4, variance: 3.2, theta: 0.25 },
        { time: '10:00-11:00', lambda: 50, mu: 12, c: 4, K: 5 },
      ],
      expect.anything(),
    )
  })
})
```

- [ ] **Step 2: Run to verify it fails** — `npm test -- OptimizePage` in `frontend/`.
- [ ] **Step 3: Implement** — `OptimizePage.tsx`:

```ts
interface SegmentRow {
  time: string
  lambda: number
  mu: number
  c: number
  variance?: number
  K?: number
  theta?: number
}

function finiteOrUndefined(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

function segmentsOf(dataset: DatasetOut): SegmentRow[] {
  return (dataset.normalized ?? []).map((row) => {
    const variance = finiteOrUndefined(row.variance)
    const K = typeof row.K === 'number' && Number.isInteger(row.K) && row.K >= 1 ? row.K : undefined
    const theta = finiteOrUndefined(row.theta)
    return {
      time: String(row.time),
      lambda: Number(row.lambda),
      mu: Number(row.mu),
      c: Number(row.c),
      ...(variance !== undefined ? { variance } : {}),
      ...(K !== undefined ? { K } : {}),
      ...(theta !== undefined && theta >= 0 ? { theta } : {}),
    }
  })
}
```

- [ ] **Step 4: Run to verify it passes** — `npm test -- OptimizePage`; confirm other OptimizePage tests still pass.
- [ ] **Step 5: Commit** — `git add frontend/src/pages/OptimizePage.tsx frontend/src/pages/OptimizePage.test.tsx && git commit -m "fix(optimize): pass variance/K/theta segments to optimizer"`

---

### Task 2: Dataset reports render real content

**Files:**
- Modify: `backend/api/reports.py:54-58` (`_dataset_payload`), `backend/api/reports.py:100-102` (Excel branch passes `current_kpis`)
- Modify: `backend/reports/report_export.py:100-128` (exec summary), `backend/reports/report_export.py:215-280` (Excel `current_kpis` param)
- Test: `tests/test_report_export.py` (3 new tests), `tests/test_reports_api.py` (extend `test_dataset_excel_report`)

**Interfaces:**
- Consumes: `process_segments()` output (columns `time/lambda/mu/c/model/theta/rho/L/Lq/W/Wq/lambda_eff/...`), `compute_kpis()` (`avg_waiting_time`, `avg_utilization`).
- Produces: `_dataset_payload` → `(comparison_df, kpis, [])` where `comparison_df` has ONLY `time/c_current/rho_current/Wq_current` (optimal columns omitted so PDF falls back to `""`/`N/A` — never `"None"`/`"<NA>"`); `_exec_summary_bullets(current_kpis, recommended_kpis) -> list[str]` pure helper; `generate_excel_report(comparison_df, recommended_kpis=None, segment_df=None, current_kpis=None)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_report_export.py` — add (import `_exec_summary_bullets`):

```python
def test_exec_summary_bullets_full_pair() -> None:
    bullets = _exec_summary_bullets(_kpis(), _kpis())
    assert bullets == [
        "• Average customer wait: 9.0 min → 4.8 min (optimized)",
        "• Estimated weekly savings: ₱12,000",
        "• Utilization improvement: 65.0% → 43.0%",
    ]


def test_exec_summary_bullets_current_only() -> None:
    bullets = _exec_summary_bullets(
        {"avg_waiting_time": 0.15, "avg_utilization": 0.65}, {}
    )
    assert bullets == [
        "• Average customer wait: 9.0 min (current)",
        "• Utilization improvement: 65.0% (current)",
    ]


def test_exec_summary_bullets_none() -> None:
    bullets = _exec_summary_bullets({}, {})
    assert bullets == [
        "• Average customer wait: N/A",
        "• Utilization improvement: N/A",
    ]
```

`tests/test_reports_api.py` — add `import io` + `import openpyxl` at top; replace the body of `test_dataset_excel_report`:

```python
def test_dataset_excel_report(db_engine, client):
    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    dataset_id = make_dataset(client)
    response = client.get(f"/reports/datasets/{dataset_id}/excel")
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert len(response.content) > 500

    wb = openpyxl.load_workbook(io.BytesIO(response.content))
    ws = wb["Segments"]
    assert [c.value for c in ws[1]] == ["time", "c_current", "rho_current", "Wq_current"]
    assert ws["A2"].value == "08:00-09:00"
    assert ws["B2"].value == 3
    assert 0 < ws["C2"].value < 1
    assert 0 < ws["D2"].value < 60
    summary_labels = [wb["Summary"].cell(row=r, column=1).value for r in range(1, 8)]
    assert "Avg Wait Current (min)" in summary_labels
    assert "Avg Utilization Current" in summary_labels
```

- [ ] **Step 2: Run to verify they fail** — `python -m pytest tests/test_report_export.py tests/test_reports_api.py -x --tb=short`.
- [ ] **Step 3: Implement `report_export.py`** — add module-level helper:

```python
def _exec_summary_bullets(current_kpis: dict, recommended_kpis: dict) -> list[str]:
    bullets: list[str] = []
    wq_current = current_kpis.get("avg_waiting_time")
    wq_opt = recommended_kpis.get("avg_waiting_optimized")
    if wq_current is not None and wq_opt is not None:
        bullets.append(
            f"• Average customer wait: {wq_current * 60:.1f} min → "
            f"{wq_opt * 60:.1f} min (optimized)"
        )
    elif wq_current is not None:
        bullets.append(f"• Average customer wait: {wq_current * 60:.1f} min (current)")
    else:
        bullets.append("• Average customer wait: N/A")

    if recommended_kpis:
        savings = recommended_kpis.get("total_savings")
        if savings is not None:
            bullets.append(f"• Estimated weekly savings: ₱{savings:,.0f}")
        else:
            bullets.append("• Estimated weekly savings: N/A")

    rho_current = current_kpis.get("avg_utilization")
    rho_opt = recommended_kpis.get("avg_utilization_optimized")
    if rho_current is not None and rho_opt is not None:
        bullets.append(f"• Utilization improvement: {rho_current:.0%} → {rho_opt:.0%}")
    elif rho_current is not None:
        bullets.append(f"• Utilization improvement: {rho_current:.0%} (current)")
    else:
        bullets.append("• Utilization improvement: N/A")
    return bullets
```

In `generate_pdf_report`, replace the `wq_current = ...` through `for item in bullet_items:` block with:

```python
    bullet_items = _exec_summary_bullets(current_kpis, recommended_kpis)
    for item in bullet_items:
        elements.append(Paragraph(item, bullet_style))
```

Change `generate_excel_report` signature to `def generate_excel_report(comparison_df, recommended_kpis=None, segment_df=None, current_kpis=None):` and, after the existing `if recommended_kpis:` branch, add:

```python
    elif current_kpis:
        avg_w_cur = current_kpis.get("avg_waiting_time")
        if avg_w_cur is not None:
            labels_values.append(("Avg Wait Current (min)", f"{avg_w_cur * 60:.2f}"))
        util_cur = current_kpis.get("avg_utilization")
        if util_cur is not None:
            labels_values.append(("Avg Utilization Current", f"{util_cur:.1%}"))
```

- [ ] **Step 4: Implement `reports.py`** — replace `_dataset_payload`:

```python
def _dataset_payload(dataset: Dataset) -> tuple[pd.DataFrame, dict, list[str]]:
    records = dataset.normalized_json or []
    results_df = process_segments(records)
    kpis = compute_kpis(results_df)
    comparison_df = pd.DataFrame(
        {
            "time": results_df["time"],
            "c_current": results_df["c"],
            "rho_current": results_df["rho"],
            "Wq_current": results_df["Wq"],
        }
    )
    return comparison_df, kpis, []
```

And the Excel branch of `_build_report`:

```python
    if format == "excel":
        buffer = generate_excel_report(
            comparison_df, recommended_kpis, current_kpis=current_kpis
        )
```

- [ ] **Step 5: Run the tests to verify they pass** — `python -m pytest tests/test_report_export.py tests/test_reports_api.py -x --tb=short`.
- [ ] **Step 6: Full verification** — `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`.
- [ ] **Step 7: Commit** — `git add backend/reports/report_export.py backend/api/reports.py tests/test_report_export.py tests/test_reports_api.py && git commit -m "fix(reports): render real current metrics in dataset reports"`

---

### Task 3: Abandonment cost support on the Optimize page

**Files:**
- Modify: `frontend/src/api/optimization.ts:4-9` (`OptimizeOptions`)
- Modify: `frontend/src/pages/OptimizePage.tsx` (`DEFAULT_OPTIONS`, form inputs, `COLUMNS`)
- Modify: `frontend/public/locales/en/translation.json` + `frontend/public/locales/tl/translation.json`
- Test: `frontend/src/pages/OptimizePage.test.tsx`

**Interfaces:**
- Consumes: backend `OptimizeBatchRequest.cost_per_abandonment` (ge=0, default 0) and `abandonment_rate` (ge=0 ≤1, default 0) — `backend/api/optimization.py:59-60`; `OptimizationOut.abandonment_cost_current/optimal`; legacy defaults `DEFAULT_ABANDONMENT_COST = 60.0`, `DEFAULT_ABANDONMENT_RATE = 0.10` (`backend/queueing_engine/config.py:18-19`).
- Produces: `OptimizeOptions` with `cost_per_abandonment?: number`, `abandonment_rate?: number`; two editable inputs defaulting to 60 / 0.10; "Abandon" table column.

- [ ] **Step 1: Write the failing test** — append to `OptimizePage.test.tsx`:

```ts
it('sends abandonment cost and rate to the optimizer and renders the abandonment column', async () => {
  optimizeBatchMock.mockResolvedValue({
    results: [{ ...row, abandonment_cost_current: 180, abandonment_cost_optimal: 90 }],
  })
  const user = userEvent.setup()
  renderWithProviders(<OptimizePage />, { route: '/optimize' })
  await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
  await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
  await user.click(screen.getByRole('button', { name: 'Optimize' }))
  await waitFor(() => {
    expect(optimizeBatchMock).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ cost_per_abandonment: 60, abandonment_rate: 0.1 }),
    )
  })
  expect(await screen.findByText('180.00 → 90.00')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify it fails** — `npm test -- OptimizePage`.
- [ ] **Step 3: Implement `optimization.ts`**:

```ts
export interface OptimizeOptions {
  target_utilization?: number
  server_cost_per_hr?: number
  customer_waiting_cost?: number
  max_servers?: number
  cost_per_abandonment?: number
  abandonment_rate?: number
}
```

- [ ] **Step 4: Implement `OptimizePage.tsx`** — `DEFAULT_OPTIONS` gains `cost_per_abandonment: 60, abandonment_rate: 0.1`; two number inputs after the waiting-cost input (ids `opt-aband-cost` / `opt-aband-rate`, labels `t('optimize.abandonment_cost')` / `t('optimize.abandonment_rate')`, `step="any"`, wired to the options state); `COLUMNS` gains `{ label: 'Abandon', current: (r) => fmt(r.abandonment_cost_current), optimized: (r) => fmt(r.abandonment_cost_optimal) }`.
- [ ] **Step 5: Add i18n keys (BOTH files, symmetric)**

| key | en | tl |
|---|---|---|
| `optimize.abandonment_cost` | `Abandonment cost / customer` | `Gastos sa pag-alis / customer` |
| `optimize.abandonment_rate` | `Abandonment rate` | `Rate ng pag-alis` |

- [ ] **Step 6: Run to verify it passes** — `npm test -- OptimizePage`, then `npm run typecheck`, `npm run lint`.
- [ ] **Step 7: Commit** — `git add frontend/src/api/optimization.ts frontend/src/pages/OptimizePage.tsx frontend/src/pages/OptimizePage.test.tsx frontend/public/locales/en/translation.json frontend/public/locales/tl/translation.json && git commit -m "feat(optimize): support abandonment cost parameters"`

---

### Task 4: Validate tab — editable plan + MC settings

**Files:**
- Modify: `frontend/src/pages/SimulationPage.tsx` (validate tab inputs + `runValidate`)
- Modify: `frontend/src/api/optimization.ts` (export shared `DEFAULT_OPTIONS`)
- Modify: `backend/api/simulation.py:34-38` (`ValidateRequest.seed` → `int | None`) — the only backend contract change, additive
- Modify: `frontend/src/api/simulation.ts` (`ValidateOptions.seed?: number | null`)
- Test: `frontend/src/pages/SimulationPage.test.tsx` (update validate tests)

**Interfaces:**
- Consumes: `optimizeBatch(segments, options)` (options now include abandonment fields), `validateSimulation(segments, { mc_trials, mc_failure_threshold, seed })`, `ValidateRequest` with nullable seed.
- Produces: shared `DEFAULT_OPTIONS` exported from `api/optimization.ts` (`target_utilization: 0.7, server_cost_per_hr: 87, customer_waiting_cost: 100, max_servers: 24, cost_per_abandonment: 60, abandonment_rate: 0.1`); validate tab inputs (trials 10000, threshold ρ 0.75, seed empty, server cost 87, waiting cost 100, abandonment 60 / 0.10) feeding `runValidate`.

- [ ] **Step 1: Write the failing tests** — update `SimulationPage.test.tsx` validate tests: assert `optimizeBatch` called with `expect.objectContaining({ server_cost_per_hr: 87, customer_waiting_cost: 100, cost_per_abandonment: 60, abandonment_rate: 0.1 })` and `validateSimulation` called with `expect.objectContaining({ mc_trials: 10000, mc_failure_threshold: 0.75, seed: null })`; add a test editing the inputs and asserting the edited values are sent.
- [ ] **Step 2: Run to verify they fail** — `npm test -- SimulationPage`.
- [ ] **Step 3: Implement backend** — `backend/api/simulation.py:38`: `seed: int | None = Field(default=None)`.
- [ ] **Step 4: Implement `api/optimization.ts`** — export `DEFAULT_OPTIONS` constant (move from `OptimizePage.tsx`).
- [ ] **Step 5: Implement `api/simulation.ts`** — `ValidateOptions.seed?: number | null`.
- [ ] **Step 6: Implement `SimulationPage.tsx`** — validate tab gains inputs (trials, threshold, seed, server cost, waiting cost, abandonment cost, abandonment rate) pre-filled from shared defaults; `runValidate` sends them.
- [ ] **Step 7: Run to verify** — `npm test -- SimulationPage OptimizePage`, backend `python -m pytest tests/test_simulation.py -x --tb=short` (seed contract) + `ruff check .` + `mypy .`.
- [ ] **Step 8: Commit** — `git add frontend/src/pages/SimulationPage.tsx frontend/src/api/optimization.ts frontend/src/api/simulation.ts frontend/src/pages/SimulationPage.test.tsx backend/api/simulation.py && git commit -m "feat(simulate): editable plan and MC settings on validate tab"`

---

### Task 5: Verdict fix, DES cards fix, empty seed defaults

**Files:**
- Modify: `frontend/src/pages/SimulationPage.tsx` (`desStable`, `allAdequate`, row badge, DES/MC seed state defaults `''`)
- Test: `frontend/src/pages/SimulationPage.test.tsx`

**Interfaces:**
- Consumes: `SimValidateOut` rows (`sim_status`, `mc_failure_rate`, `mc_adequate`), `SimDesOut.status` (`Lean|Normal|Peak|Critical|Unstable|ERROR`).
- Produces: verdict = rows non-empty AND every row passes (`sim_status ∉ {Critical, Unstable}` AND `(mc_failure_rate ?? 0) ≤ 0.05`); per-row pass badge; `desStable` = Lean/Normal/Peak only.

- [ ] **Step 1: Update the failing tests** — `SimulationPage.test.tsx:170-175` and `:193-197` change `seed: 42` → `seed: null`; add a verdict test: validateRow with `sim_status: 'Critical'`, `mc_failure_rate: 0.02`, `mc_adequate: true` → banner shows "found issues"; DES row with `status: 'Unstable'` → Stable card shows 0.
- [ ] **Step 2: Run to verify they fail** — `npm test -- SimulationPage`.
- [ ] **Step 3: Implement** — `SimulationPage.tsx`:

```ts
const desStable = desRows ? desRows.filter((r) => r.status === 'Lean' || r.status === 'Normal' || r.status === 'Peak').length : 0
```
and
```ts
const rowPasses = (r: SimValidateOut) =>
  r.sim_status !== 'Critical' && r.sim_status !== 'Unstable' && (r.mc_failure_rate ?? 0) <= 0.05
const allPassed = validateRows !== null && validateRows.length > 0 && validateRows.every(rowPasses)
```
Use `allPassed` for the banner and `rowPasses(row)` for the per-row badge; DES/MC seed states default to `''`.

- [ ] **Step 4: Run to verify it passes** — `npm test -- SimulationPage`.
- [ ] **Step 5: Commit** — `git add frontend/src/pages/SimulationPage.tsx frontend/src/pages/SimulationPage.test.tsx && git commit -m "fix(simulate): correct validation verdict and DES status counting"`

---

### Final Verification

- [ ] Backend: `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`
- [ ] Frontend: `npm test`, `npm run typecheck`, `npm run lint` (in `frontend/`)
- [ ] Legacy e2e smoke: `python -m pytest tests/test_dashboard_e2e.py -x --tb=short`