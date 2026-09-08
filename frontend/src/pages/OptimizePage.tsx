import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { listDatasets, getDataset } from '../api/datasets'
import { optimizeBatch, DEFAULT_OPTIONS, type OptimizeOptions } from '../api/optimization'
import { createScenario } from '../api/scenarios'
import type { DatasetOut, OptimizationOut } from '../api/types'
import { MetricCard } from '../components/ui/MetricCard'
import {
  comparisonComplete,
  comparisonTotals,
  operationalComparisonComplete,
} from '../lib/comparison'
import { ApiState } from '../components/ui/ApiState'
import { useQuery, useQueryClient } from '@tanstack/react-query'

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
  render?: (row: OptimizationOut) => ReactNode
}

type UtilizationStatus = 'Unavailable' | 'Lean' | 'Normal' | 'Peak' | 'Critical' | 'Unstable'

function utilizationStatus(
  rho: number | null | undefined,
  analyticallyStable?: boolean,
): UtilizationStatus {
  if (analyticallyStable === false) return 'Unstable'
  if (rho === null || rho === undefined || !Number.isFinite(rho)) return 'Unavailable'
  if (rho >= 1) return 'Critical'
  if (rho >= 0.9) return 'Critical'
  if (rho > 0.8) return 'Peak'
  if (rho >= 0.6) return 'Normal'
  return 'Lean'
}

function statusBadgeClass(status: UtilizationStatus): string {
  if (status === 'Critical' || status === 'Unstable') return 'badge-bad'
  if (status === 'Peak') return 'badge-warn'
  if (status === 'Normal') return 'badge-ok'
  return 'badge-neutral'
}

function StatusBadge({ status }: { status: UtilizationStatus }) {
  const { t } = useTranslation()
  return <span className={`badge ${statusBadgeClass(status)}`}>{t(`integrity.status.${status}`)}</span>
}

const COLUMNS: Column[] = [
  { label: 'segment', current: (r) => r.time, optimized: (r) => r.time },
  { label: 'λ', current: (r) => fmt(r.lambda_), optimized: (r) => fmt(r.lambda_) },
  { label: 'ρ', current: (r) => fmt(r.rho_current == null ? null : r.rho_current * 100) + '%', optimized: (r) => fmt(r.rho_optimal == null ? null : r.rho_optimal * 100) + '%' },
  {
    label: 'Status',
    current: (r) => utilizationStatus(r.rho_current),
    optimized: (r) => utilizationStatus(r.rho_optimal),
    render: (r) => (
      <div className="status-flow">
        <StatusBadge status={utilizationStatus(r.rho_current, r.current_stable)} />
        <span aria-hidden="true">→</span>
        <StatusBadge status={utilizationStatus(r.rho_optimal, r.optimized_stable)} />
      </div>
    ),
  },
  { label: 'c', current: (r) => String(r.c_current), optimized: (r) => fmt(r.c_optimal, 0) },
  { label: 'Lq', current: (r) => fmt(r.Lq_current), optimized: (r) => fmt(r.Lq_optimal) },
  { label: 'Wq (min)', current: (r) => fmt(r.Wq_current == null ? null : r.Wq_current * 60), optimized: (r) => fmt(r.Wq_optimal == null ? null : r.Wq_optimal * 60) },
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
  server_cost?: number
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
      ...(finiteOrUndefined(row.server_cost) !== undefined ? { server_cost: Number(row.server_cost) } : {}),
    }
  })
}

function sum(values: number[]): number {
  return values.reduce((acc, v) => acc + v, 0)
}

function peakOptimizedCashiers(rows: OptimizationOut[] | null): number {
  return rows ? Math.max(...rows.map((r) => r.c_optimal ?? 0), 0) : 0
}

function formatStaffingChange(change: number): string {
  const absChange = Math.abs(change)
  const label = absChange === 1 ? 'cashier' : 'cashiers'
  return change > 0 ? `Add ${absChange} ${label}` : `Reduce ${absChange} ${label}`
}

function mergeTimeRanges(times: string[]): string[] {
  const ranges: string[] = []
  for (const time of times) {
    const [start, end] = time.split('-')
    const last = ranges[ranges.length - 1]
    if (last && start && end) {
      const [lastStart, lastEnd] = last.split('-')
      if (lastEnd === start) {
        ranges[ranges.length - 1] = `${lastStart}-${end}`
        continue
      }
    }
    ranges.push(time)
  }
  return ranges
}

function staffingChangeLines(rows: OptimizationOut[]): string[] {
  const grouped = new Map<number, string[]>()
  for (const row of rows) {
    const change = row.delta_c ?? 0
    if (change === 0) continue
    grouped.set(change, [...(grouped.get(change) ?? []), row.time])
  }
  return [...grouped.entries()]
    .sort(([a], [b]) => b - a)
    .map(([change, times]) => `${formatStaffingChange(change)}: ${mergeTimeRanges(times).join(', ')}`)
}

export function OptimizePage() {
  const { t } = useTranslation()
  const [datasetId, setDatasetId] = useState('')
  const queryClient = useQueryClient()
  const [options, setOptions] = useState<OptimizeOptions>(DEFAULT_OPTIONS)
  const [multiplier, setMultiplier] = useState('')
  const [snapshot, setSnapshot] = useState<{ signature: string; datasetId: string; segments: SegmentRow[]; options: OptimizeOptions; factor: number; calculatedAt: string } | null>(null)
  const signature = JSON.stringify({ datasetId, options, multiplier })
  const stale = snapshot !== null && snapshot.signature !== signature
  const [rows, setRows] = useState<OptimizationOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [saving, setSaving] = useState(false)
  const [scenarioName, setScenarioName] = useState('')
  const [saved, setSaved] = useState(false)
  const [availableCashiers, setAvailableCashiers] = useState('')

  const datasets = useQuery({
    queryKey: ['datasets'],
    queryFn: () => listDatasets(),
  })

  async function run(dataset: DatasetOut, factor = 1) {
    setError(null)
    setSaved(false)
    setRunning(true)
    try {
      const loaded = await getDataset(dataset.id)
      const segments = segmentsOf(loaded.dataset).map((row) => ({ ...row, lambda: row.lambda * factor }))
      const out = await optimizeBatch(segments, options)
      queryClient.setQueryData(['optimization-options', datasetId], { ...options })
      setRows(out.results)
      setSnapshot({ signature, datasetId, segments: structuredClone(segments), options: { ...options }, factor, calculatedAt: new Date().toISOString() })
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
    await run(dataset)
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
    await run(dataset, factor)
  }

  async function handleSave() {
    if (!rows?.length || !snapshot || stale || running || !scenarioName.trim()) {
      return
    }
    setSaving(true)
    setSaved(false)
    try {
      await createScenario({
        name: scenarioName.trim(),
        dataset_id: snapshot.datasetId ? Number(snapshot.datasetId) : null,
        settings: { ...snapshot.options, calculation: {
          schema_version: 1, engine_version: 'novaq-2026-09-system-v2',
          input_segments: snapshot.segments, options: snapshot.options,
          what_if_multiplier: snapshot.factor, calculated_at: snapshot.calculatedAt,
        } },
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

  const totals = !stale && rows ? comparisonTotals(rows) : null
  const operationallyComparable = !stale && rows ? operationalComparisonComplete(rows) : false
  const totalCurrent = totals?.current ?? null
  const totalOptimal = totals?.optimal ?? null
  const deltaCost = totals?.savings ?? null
  const addedCashierHours = rows ? sum(rows.map((r) => Math.max(0, r.delta_c ?? 0))) : 0
  const removedCashierHours = rows ? sum(rows.map((r) => Math.max(0, -(r.delta_c ?? 0)))) : 0
  const netCashierHours = removedCashierHours - addedCashierHours
  const peakRequirement = peakOptimizedCashiers(rows)
  const availablePool = Number(availableCashiers)
  const poolIsProvided =
    availableCashiers.trim() !== '' &&
    Number.isInteger(availablePool) &&
    availablePool >= 0
  const poolGap = poolIsProvided && availablePool > 0 ? availablePool - peakRequirement : null
  const staffingLines = rows ? staffingChangeLines(rows) : []
  const warnings = rows?.filter((r) => r.warning) ?? []

  return (
    <div>
      <h1 className="page-title">{t('optimize.title')}</h1>
      <p className="page-caption">{t('page2.caption')}</p>
      {stale && <div role="alert" className="alert alert-warn">{t('integrity.stale')}</div>}
      {rows && !comparisonComplete(rows) && <div role="alert" className="alert alert-warn">{t('integrity.incomplete')}</div>}
      <p className="form-hint">{t('integrity.staffing_basis')}</p>

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
            <label htmlFor="opt-util">{t('system.planning_target')}</label>
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
            <label htmlFor="opt-min">{t('system.min_servers')}</label>
            <input id="opt-min" type="number" min={1} max={256} value={options.min_servers ?? 1} onChange={(e) => setOptions((o) => ({ ...o, min_servers: Number(e.target.value) }))} />
          </div>
          <div className="form-field">
            <label htmlFor="opt-max">{t('system.max_servers')}</label>
            <input id="opt-max" type="number" min={1} max={256} value={options.max_servers ?? 24} onChange={(e) => setOptions((o) => ({ ...o, max_servers: Number(e.target.value) }))} />
          </div>
          <div className="form-field">
            <label htmlFor="opt-max-wait">{t('system.max_wait')}</label>
            <input id="opt-max-wait" type="number" min={0} step="any" value={options.max_wait_minutes ?? ''} onChange={(e) => setOptions((o) => ({ ...o, max_wait_minutes: e.target.value === '' ? null : Number(e.target.value) }))} />
          </div>
          <div className="form-field">
            <p>{t('system.cost_basis')}</p>
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
            <label htmlFor="opt-available-cashiers">{t('optimize.available_cashiers')}</label>
            <input
              id="opt-available-cashiers"
              aria-label={t('optimize.available_cashiers')}
              type="number"
              step={1}
              min={0}
              value={availableCashiers}
              onChange={(e) => setAvailableCashiers(e.target.value)}
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
              {warnings.map((w) => w.feasibility_status === 'NO_FEASIBLE_CONFIGURATION' ? t('system.no_feasible') : w.warning).join(' ')}
            </div>
          )}
          <div className="card-grid">
            <MetricCard label={t('optimize.total_cost')} value={fmt(totalCurrent)} />
            <MetricCard label={t('optimize.optimal_cost')} value={fmt(totalOptimal)} />
            <MetricCard label={t('optimize.delta_cost')} value={fmt(deltaCost)} />
          </div>

          {operationallyComparable ? <div className="card staffing-summary">
            <div>
              <div className="label">{t('optimize.net_staffing_reduction')}</div>
              <div className="staffing-summary-value">
                {netCashierHours > 0
                  ? t('optimize.net_reduced', { count: netCashierHours })
                  : netCashierHours < 0
                    ? t('optimize.net_added', { count: Math.abs(netCashierHours) })
                    : t('optimize.net_no_change')}
              </div>
              <div className="sub">
                {t('optimize.staffing_formula', {
                  removed: removedCashierHours,
                  added: addedCashierHours,
                })}
              </div>
            </div>
            <div className="staffing-summary-grid">
              <div>
                <span>{t('optimize.peak_requirement')}</span>
                <strong>
                  {t(peakRequirement === 1 ? 'optimize.cashier_count' : 'optimize.cashier_count_plural', {
                    count: peakRequirement,
                  })}
                </strong>
              </div>
              <div>
                <span>{t('optimize.available_pool')}</span>
                <strong>
                  {poolIsProvided
                    ? t(availablePool === 1 ? 'optimize.cashier_count' : 'optimize.cashier_count_plural', {
                        count: availablePool,
                      })
                    : t('common.not_available')}
                </strong>
              </div>
            </div>
            {poolGap !== null && (
              <div className={`alert ${poolGap >= 0 ? 'alert-ok' : 'alert-warn'}`}>
                {poolGap >= 0
                  ? t('optimize.pool_can_cover')
                  : t(Math.abs(poolGap) === 1 ? 'optimize.pool_short' : 'optimize.pool_short_plural', {
                      count: Math.abs(poolGap),
                    })}
              </div>
            )}
            {staffingLines.length > 0 && (
              <div className="staffing-lines">
                {staffingLines.map((line) => (
                  <div key={line}>{line}</div>
                ))}
              </div>
            )}
          </div>

          : <p>{t('system.staffing_unavailable')}</p>}
          <div className="card">
            <h2 className="card-title">{t('optimize.staffing_table')}</h2>
            <div className="status-legend" aria-label={t('optimize.status_legend')}>
              <StatusBadge status="Lean" />
              <span>{'< 60%'}</span>
              <StatusBadge status="Normal" />
              <span>{'60%-80%'}</span>
              <StatusBadge status="Peak" />
              <span>{'> 80%-< 90%'}</span>
              <StatusBadge status="Critical" />
              <span>{'>= 90%'}</span>
              <StatusBadge status="Unstable" />
              <span>{'> 100%'}</span>
            </div>
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
                        {col.render
                          ? col.render(row)
                          : col.label === 'segment'
                          ? col.current(row)
                          : `${col.current(row)} → ${col.optimized(row)}`}
                      </td>
                    ))}
                    <td>{row.recommendation}<p>{row.explanation}</p><small>{row.selected_model}</small></td>
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
              <button type="button" onClick={handleSave} disabled={saving || running || stale || !snapshot || !rows?.length || !scenarioName.trim()}>
                {t('common.save')}
              </button>
            </div>
            {!stale && rows.length > 0 && !comparisonComplete(rows) && <p>{t('system.save_incomplete')}</p>}
            {saved && !stale && <div className="alert alert-success">{t('optimize.saved')}</div>}
          </div>
        </>
      )}
    </div>
  )
}
