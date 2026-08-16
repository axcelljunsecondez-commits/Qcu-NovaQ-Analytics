import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { listDatasets, getDataset } from '../api/datasets'
import { optimizeBatch, DEFAULT_OPTIONS, type OptimizeOptions } from '../api/optimization'
import { createScenario } from '../api/scenarios'
import type { DatasetOut, OptimizationOut } from '../api/types'
import { MetricCard } from '../components/ui/MetricCard'
import { ApiState } from '../components/ui/ApiState'
import { useQuery } from '@tanstack/react-query'

function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—'
  }
  return value.toFixed(digits)
}

interface Column {
  label: string
  current: (row: OptimizationOut) => string
  optimized: (row: OptimizationOut) => string
}

const COLUMNS: Column[] = [
  { label: 'segment', current: (r) => r.time, optimized: (r) => r.time },
  { label: 'λ', current: (r) => fmt(r.lambda_), optimized: (r) => fmt(r.lambda_) },
  { label: 'ρ', current: (r) => fmt((r.rho_current ?? 0) * 100) + '%', optimized: (r) => fmt((r.rho_optimal ?? 0) * 100) + '%' },
  { label: 'c', current: (r) => String(r.c_current), optimized: (r) => String(r.c_optimal) },
  { label: 'Lq', current: (r) => fmt(r.Lq_current), optimized: (r) => fmt(r.Lq_optimal) },
  { label: 'Wq', current: (r) => fmt(r.Wq_current), optimized: (r) => fmt(r.Wq_optimal) },
  { label: 'Abandon', current: (r) => fmt(r.abandonment_cost_current), optimized: (r) => fmt(r.abandonment_cost_optimal) },
  { label: 'cost', current: (r) => fmt(r.cost_current), optimized: (r) => fmt(r.cost_optimal) },
]

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

function sum(values: number[]): number {
  return values.reduce((acc, v) => acc + v, 0)
}

export function OptimizePage() {
  const { t } = useTranslation()
  const [datasetId, setDatasetId] = useState('')
  const [options, setOptions] = useState<OptimizeOptions>(DEFAULT_OPTIONS)
  const [multiplier, setMultiplier] = useState('')
  const [rows, setRows] = useState<OptimizationOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [saving, setSaving] = useState(false)
  const [scenarioName, setScenarioName] = useState('')
  const [saved, setSaved] = useState(false)

  const datasets = useQuery({
    queryKey: ['datasets'],
    queryFn: () => listDatasets(),
  })

  async function run(segments: SegmentRow[]) {
    setError(null)
    setRunning(true)
    try {
      const out = await optimizeBatch(segments, options)
      setRows(out.results)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('errors.server'))
    } finally {
      setRunning(false)
    }
  }

  async function handleOptimize() {
    const dataset = datasets.data?.datasets.find((d: DatasetOut) => String(d.id) === datasetId)
    if (!dataset) {
      setError(t('optimize.select_dataset_first'))
      return
    }
    const loaded = await getDataset(dataset.id)
    await run(segmentsOf(loaded.dataset))
  }

  async function handleWhatIf() {
    const dataset = datasets.data?.datasets.find((d: DatasetOut) => String(d.id) === datasetId)
    if (!dataset || !rows) {
      return
    }
    const factor = Number(multiplier)
    if (!Number.isFinite(factor) || factor <= 0) {
      setError(t('optimize.multiplier_range_error'))
      return
    }
    const loaded = await getDataset(dataset.id)
    const segments = segmentsOf(loaded.dataset).map((row) => ({
      ...row,
      lambda: row.lambda * factor,
    }))
    await run(segments)
  }

  async function handleSave() {
    if (!rows || !scenarioName.trim()) {
      return
    }
    setSaving(true)
    setSaved(false)
    try {
      await createScenario({
        name: scenarioName.trim(),
        dataset_id: datasetId ? Number(datasetId) : null,
        settings: { ...options },
        results: { results: rows },
      })
      setSaved(true)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('errors.server'))
    } finally {
      setSaving(false)
    }
  }

  const totalCurrent = rows ? sum(rows.map((r) => r.cost_current ?? 0)) : 0
  const totalOptimal = rows ? sum(rows.map((r) => r.cost_optimal ?? 0)) : 0
  const deltaCost = totalCurrent - totalOptimal
  const addedServers = rows ? sum(rows.map((r) => Math.max(0, r.delta_c ?? 0))) : 0
  const warnings = rows?.filter((r) => r.warning) ?? []

  return (
    <div>
      <h1 className="page-title">{t('optimize.title')}</h1>
      <p className="page-caption">{t('page2.caption')}</p>

      <div className="card">
        <h2 className="card-title">{t('page1.data_source')}</h2>
        <div className="form-row">
          <div className="form-field">
            <label htmlFor="opt-dataset">{t('optimize.source_dataset')}</label>
            <select
              id="opt-dataset"
              aria-label={t('optimize.source_dataset')}
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
            >
              <option value="">—</option>
              {datasets.data?.datasets.map((d: DatasetOut) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="opt-util">{t('optimize.target_utilization')}</label>
            <input
              id="opt-util"
              type="number"
              step="any"
              value={options.target_utilization ?? ''}
              onChange={(e) =>
                setOptions((o) => ({ ...o, target_utilization: Number(e.target.value) }))
              }
            />
          </div>
          <div className="form-field">
            <label htmlFor="opt-cost">{t('optimize.server_cost')}</label>
            <input
              id="opt-cost"
              type="number"
              step="any"
              value={options.server_cost_per_hr ?? ''}
              onChange={(e) =>
                setOptions((o) => ({ ...o, server_cost_per_hr: Number(e.target.value) }))
              }
            />
          </div>
          <div className="form-field">
            <label htmlFor="opt-wait">{t('optimize.waiting_cost')}</label>
            <input
              id="opt-wait"
              type="number"
              step="any"
              value={options.customer_waiting_cost ?? ''}
              onChange={(e) =>
                setOptions((o) => ({ ...o, customer_waiting_cost: Number(e.target.value) }))
              }
            />
          </div>
          <div className="form-field">
            <label htmlFor="opt-aband-cost">{t('optimize.abandonment_cost')}</label>
            <input
              id="opt-aband-cost"
              type="number"
              step="any"
              value={options.cost_per_abandonment ?? ''}
              onChange={(e) =>
                setOptions((o) => ({ ...o, cost_per_abandonment: Number(e.target.value) }))
              }
            />
          </div>
          <div className="form-field">
            <label htmlFor="opt-aband-rate">{t('optimize.abandonment_rate')}</label>
            <input
              id="opt-aband-rate"
              type="number"
              step="any"
              value={options.abandonment_rate ?? ''}
              onChange={(e) =>
                setOptions((o) => ({ ...o, abandonment_rate: Number(e.target.value) }))
              }
            />
          </div>
          <button type="button" onClick={handleOptimize} disabled={running}>
            {t('optimize.run')}
          </button>
        </div>
      </div>

      {running && <ApiState.Loading />}
      {error && <div className="alert alert-error">{error}</div>}

      {rows && (
        <>
          {warnings.length > 0 && (
            <div className="alert alert-warn">
              {warnings.map((w) => w.warning).join(' ')}
            </div>
          )}
          <div className="card-grid">
            <MetricCard label={t('optimize.total_cost')} value={fmt(totalCurrent)} />
            <MetricCard label={t('optimize.optimal_cost')} value={fmt(totalOptimal)} />
            <MetricCard label={t('optimize.delta_cost')} value={fmt(deltaCost)} />
            <MetricCard label={t('optimize.added_servers')} value={'+' + String(addedServers)} />
          </div>

          <div className="card">
            <h2 className="card-title">{t('optimize.staffing_table')}</h2>
            <table>
              <thead>
                <tr>
                  {COLUMNS.map((col) => (
                    <th key={col.label}>{col.label}</th>
                  ))}
                  <th>{t('optimize.recommendation')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.time}>
                    {COLUMNS.map((col) => (
                      <td key={col.label}>
                        {col.label === 'segment'
                          ? col.current(row)
                          : `${col.current(row)} → ${col.optimized(row)}`}
                      </td>
                    ))}
                    <td>{row.recommendation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2 className="card-title">{t('page2.what_if')}</h2>
            <div className="form-row">
              <div className="form-field">
                <label htmlFor="opt-mult">{t('optimize.lambda_multiplier')}</label>
                <input
                  id="opt-mult"
                  aria-label={t('optimize.lambda_multiplier')}
                  type="number"
                  step="any"
                  value={multiplier}
                  onChange={(e) => setMultiplier(e.target.value)}
                />
              </div>
              <button type="button" onClick={handleWhatIf} disabled={running}>
                {t('optimize.what_if')}
              </button>
            </div>
          </div>

          <div className="card">
            <h2 className="card-title">{t('page2.save_scenario')}</h2>
            <div className="form-row">
              <div className="form-field">
                <label htmlFor="opt-scenario">{t('optimize.scenario_name')}</label>
                <input
                  id="opt-scenario"
                  aria-label={t('optimize.scenario_name')}
                  type="text"
                  value={scenarioName}
                  onChange={(e) => setScenarioName(e.target.value)}
                />
              </div>
              <button type="button" onClick={handleSave} disabled={saving || !scenarioName.trim()}>
                {t('common.save')}
              </button>
            </div>
            {saved && <div className="alert alert-success">{t('optimize.saved')}</div>}
          </div>
        </>
      )}
    </div>
  )
}
