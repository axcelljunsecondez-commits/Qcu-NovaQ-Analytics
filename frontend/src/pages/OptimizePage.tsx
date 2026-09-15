/**
 * OptimizePage — Two-column layout matching reference design.
 * Left: controls panel (goal presets, settings, run button)
 * Right: result card (staffing summary, cost delta, recommendation)
 * Below: staffing table, what-if, save scenario
 */
import { useState, type ReactNode } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { listDatasets, getDataset } from '../api/datasets'
import { optimizeBatch, DEFAULT_OPTIONS, type OptimizeOptions } from '../api/optimization'
import { createScenario } from '../api/scenarios'
import type { DatasetOut, OptimizationOut, SegmentRow } from '../api/types'
import { NovaQInsights } from '../components/insights/NovaQInsights'
import { generateOptimizationInsights } from '../lib/insights'
import {
  completeFiniteAverage,
  comparisonComplete,
  comparisonTotals,
} from '../lib/comparison'
import { fmt } from '../lib/format'
import { segmentsOf } from '../lib/queue'
import { ApiState } from '../components/ui/ApiState'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'

interface GoalPreset {
  id: string
  label: string
  description: string
  options: Partial<OptimizeOptions>
}

const GOAL_PRESETS: GoalPreset[] = [
  {
    id: 'minimize_cost',
    label: 'optimize.goal_minimize_cost',
    description: 'optimize.goal_minimize_cost_desc',
    options: { target_utilization: 0.85, max_wait_minutes: null },
  },
  {
    id: 'minimize_wait',
    label: 'optimize.goal_minimize_wait',
    description: 'optimize.goal_minimize_wait_desc',
    options: { target_utilization: 0.65, max_wait_minutes: 2 },
  },
  {
    id: 'balance',
    label: 'optimize.goal_balance',
    description: 'optimize.goal_balance_desc',
    options: { target_utilization: 0.75, max_wait_minutes: 5 },
  },
]

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

function peakOptimizedCashiers(rows: OptimizationOut[] | null): number {
  return rows ? Math.max(...rows.map((r) => r.c_optimal ?? 0), 0) : 0
}

function formatStaffingChange(change: number, t: TFunction): string {
  const absChange = Math.abs(change)
  return t(change > 0 ? 'optimize.add_cashiers' : 'optimize.reduce_cashiers', {
    count: absChange,
  })
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

function staffingChangeLines(rows: OptimizationOut[], t: TFunction): string[] {
  const grouped = new Map<number, string[]>()
  for (const row of rows) {
    const change = row.delta_c ?? 0
    if (change === 0) continue
    grouped.set(change, [...(grouped.get(change) ?? []), row.time])
  }
  return [...grouped.entries()]
    .sort(([a], [b]) => b - a)
    .map(([change, times]) => `${formatStaffingChange(change, t)}: ${mergeTimeRanges(times).join(', ')}`)
}

function staffingTotals(rows: OptimizationOut[]) {
  const removed = rows.reduce((total, row) => total + Math.max(-(row.delta_c ?? 0), 0), 0)
  const added = rows.reduce((total, row) => total + Math.max(row.delta_c ?? 0, 0), 0)
  return { removed, added, net: removed - added }
}

export function OptimizePage() {
  const { t } = useTranslation()
  const analysisParam = useParams().analysisId
  const analysisId = analysisParam ? Number(analysisParam) : undefined
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
    queryKey: ['datasets', analysisId],
    queryFn: () => listDatasets(analysisId),
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
        analysis_id: analysisId,
        dataset_id: snapshot.datasetId ? Number(snapshot.datasetId) : null,
        settings: { ...snapshot.options, calculation: {
          schema_version: 1, engine_version: 'novaq-2026-09-system-v2',
          input_segments: snapshot.segments, options: snapshot.options,
          what_if_multiplier: snapshot.factor, calculated_at: snapshot.calculatedAt,
        } },
        results: { results: rows },
      })
      void queryClient.invalidateQueries({ queryKey: ['scenarios', analysisId] })
      setSaved(true)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('errors.server'))
    } finally {
      setSaving(false)
    }
  }

  const totals = !stale && rows ? comparisonTotals(rows) : null
  const totalCurrent = totals?.current ?? null
  const totalOptimal = totals?.optimal ?? null
  const deltaCost = totals?.savings ?? null
  const peakRequirement = peakOptimizedCashiers(rows)
  const availablePool = Number(availableCashiers)
  const poolIsProvided =
    availableCashiers.trim() !== '' &&
    Number.isInteger(availablePool) &&
    availablePool >= 0
  const poolGap = poolIsProvided ? availablePool - peakRequirement : null
  const staffingLines = rows ? staffingChangeLines(rows, t) : []
  const staffingTotalsValue = rows ? staffingTotals(rows) : null
  const staffingSummaryAvailable = rows !== null && rows.length > 0 && rows.every((row) => row.c_optimal !== null && row.c_optimal !== undefined)
  const warnings = rows?.filter((r) => r.warning) ?? []

  return (
    <div className="optimize-page">
      {/* Topbar */}
      <div className="topbar">
        <div>
          <div className="topbar-eyebrow">{t('optimize.eyebrow')}</div>
          <h1 className="page-title">{t('optimize.title')}</h1>
          <p className="page-caption">{t('optimize.description')}</p>
        </div>
      </div>

      {stale && <div role="alert" className="alert alert-warn">{t('integrity.stale')}</div>}
      {rows && !comparisonComplete(rows) && <div role="alert" className="alert alert-warn">{t('integrity.incomplete')}</div>}
      {rows && !staffingSummaryAvailable && (
        <div className="alert alert-warn">{t('system.staffing_unavailable')}</div>
      )}
      {rows && staffingSummaryAvailable && !totals && staffingTotalsValue && (
        <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
          <div className="form-hint">{t('optimize.net_staffing_reduction')}</div>
          <div style={{ fontWeight: 800 }}>
            {staffingTotalsValue.net > 0
              ? t('optimize.net_reduced', { count: staffingTotalsValue.net })
              : staffingTotalsValue.net < 0
              ? t('optimize.net_added', { count: Math.abs(staffingTotalsValue.net) })
              : t('optimize.net_no_change')}
          </div>
        </div>
      )}

      {/* Two-column layout: Controls + Result */}
      <div className="grid g2" style={{ marginTop: '12px' }}>
        {/* Left Column — Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* Goal Presets */}
          <div className="card" style={{ padding: '18px' }}>
            <h3 className="section-title">{t('optimize.constraint_presets')}</h3>
            <div className="goal-presets">
              {GOAL_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  className={`goal-preset-btn ${options.target_utilization === preset.options.target_utilization && options.max_wait_minutes === preset.options.max_wait_minutes ? 'active' : ''}`}
                  aria-pressed={options.target_utilization === preset.options.target_utilization && options.max_wait_minutes === preset.options.max_wait_minutes}
                  onClick={() => setOptions((o) => ({ ...o, ...preset.options }))}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    border: '1px solid var(--border)',
                    borderRadius: '9px',
                    padding: '12px',
                    cursor: 'pointer',
                    background: options.target_utilization === preset.options.target_utilization && options.max_wait_minutes === preset.options.max_wait_minutes
                      ? 'var(--state-current-bg)' : 'var(--primary-contrast)',
                    borderColor: options.target_utilization === preset.options.target_utilization && options.max_wait_minutes === preset.options.max_wait_minutes
                      ? 'var(--accent)' : 'var(--border)',
                  }}
                >
                  <span className="goal-preset-label" style={{ fontSize: '14px', fontWeight: 800 }}>
                    {t(preset.label)}
                  </span>
                  <span className="goal-preset-desc" style={{ display: 'block', fontSize: '14px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    {t(preset.description)}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Source Dataset */}
          <div className="card" style={{ padding: '18px' }}>
            <h3 className="section-title">{t('page1.data_source')}</h3>
            <div className="form-row">
              <div className="form-field" style={{ flex: 1 }}>
                <label htmlFor="opt-dataset" style={{ fontSize: '14px', fontWeight: 800 }}>{t('optimize.source_dataset')}</label>
                <select
                  id="opt-dataset"
                  aria-label={t('optimize.source_dataset')}
                  value={datasetId}
                  onChange={(e) => setDatasetId(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }}
                >
                  <option value="">—</option>
                  {datasets.data?.datasets.map((d: DatasetOut) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Advanced Settings */}
          <div className="card" style={{ padding: '18px' }}>
            <h3 className="section-title">{t('optimize.advanced_settings')}</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div className="form-field">
                <label htmlFor="opt-util" style={{ fontSize: '14px', fontWeight: 800 }}>{t('system.planning_target')}</label>
                <input
                  id="opt-util"
                  type="number"
                  step="any"
                  value={options.target_utilization ?? ''}
                  onChange={(e) =>
                    setOptions((o) => ({ ...o, target_utilization: Number(e.target.value) }))
                  }
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="opt-min" style={{ fontSize: '14px', fontWeight: 800 }}>{t('system.min_servers')}</label>
                <input id="opt-min" type="number" min={1} max={256} value={options.min_servers ?? 1} onChange={(e) => setOptions((o) => ({ ...o, min_servers: Number(e.target.value) }))} style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }} />
              </div>
              <div className="form-field">
                <label htmlFor="opt-max" style={{ fontSize: '14px', fontWeight: 800 }}>{t('system.max_servers')}</label>
                <input id="opt-max" type="number" min={1} max={256} value={options.max_servers ?? 24} onChange={(e) => setOptions((o) => ({ ...o, max_servers: Number(e.target.value) }))} style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }} />
              </div>
              <div className="form-field">
                <label htmlFor="opt-max-wait" style={{ fontSize: '14px', fontWeight: 800 }}>{t('system.max_wait')}</label>
                <input id="opt-max-wait" type="number" min={0} step="any" value={options.max_wait_minutes ?? ''} onChange={(e) => setOptions((o) => ({ ...o, max_wait_minutes: e.target.value === '' ? null : Number(e.target.value) }))} style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }} />
              </div>
              <div className="form-field">
                <label htmlFor="opt-cost" style={{ fontSize: '14px', fontWeight: 800 }}>{t('optimize.server_cost')}</label>
                <input
                  id="opt-cost"
                  type="number"
                  step="any"
                  value={options.server_cost_per_hr ?? ''}
                  onChange={(e) =>
                    setOptions((o) => ({ ...o, server_cost_per_hr: Number(e.target.value) }))
                  }
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="opt-wait" style={{ fontSize: '14px', fontWeight: 800 }}>{t('optimize.waiting_cost')}</label>
                <input
                  id="opt-wait"
                  type="number"
                  step="any"
                  value={options.customer_waiting_cost ?? ''}
                  onChange={(e) =>
                    setOptions((o) => ({ ...o, customer_waiting_cost: Number(e.target.value) }))
                  }
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="opt-available-cashiers" style={{ fontSize: '14px', fontWeight: 800 }}>{t('optimize.available_cashiers')}</label>
                <input
                  id="opt-available-cashiers"
                  aria-label={t('optimize.available_cashiers')}
                  type="number"
                  step={1}
                  min={0}
                  value={availableCashiers}
                  onChange={(e) => setAvailableCashiers(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }}
                />
                <span className="form-hint">{t('optimize.available_cashiers_help')}</span>
              </div>
              <div className="form-field">
                <label htmlFor="opt-aband-cost" style={{ fontSize: '14px', fontWeight: 800 }}>{t('optimize.abandonment_cost')}</label>
                <input
                  id="opt-aband-cost"
                  type="number"
                  step="any"
                  value={options.cost_per_abandonment ?? ''}
                  onChange={(e) =>
                    setOptions((o) => ({ ...o, cost_per_abandonment: Number(e.target.value) }))
                  }
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="opt-aband-rate" style={{ fontSize: '14px', fontWeight: 800 }}>{t('optimize.abandonment_rate')}</label>
                <input
                  id="opt-aband-rate"
                  type="number"
                  step="any"
                  value={options.abandonment_rate ?? ''}
                  onChange={(e) =>
                    setOptions((o) => ({ ...o, abandonment_rate: Number(e.target.value) }))
                  }
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }}
                />
              </div>
            </div>
            <button
              type="button"
              onClick={handleOptimize}
              disabled={running}
              className="button-primary"
              style={{ width: '100%', marginTop: '14px', padding: '12px 24px', background: running ? 'var(--disabled-bg)' : 'var(--accent)', color: 'var(--primary-contrast)', border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: 800, cursor: running ? 'not-allowed' : 'pointer' }}
            >
              {running ? 'Optimizing...' : t('optimize.run')}
            </button>
          </div>
        </div>

        {/* Right Column — Result Card */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* Result Card */}
          <div className="card result-card" style={{
            background: 'linear-gradient(135deg, #faf7f2 0%, #fafafa 100%)',
            border: '1px solid #f0ece4',
            borderRadius: '13px',
            padding: '18px',
          }}>
            <h3 className="section-title">{t('optimize.candidate_plan')}</h3>
            {rows && totals ? (
              <>
                <div style={{ display: 'flex', gap: '14px', marginTop: '8px' }}>
                  {/* Cost comparison */}
                  <div style={{ flex: 1, textAlign: 'center' }}>
                    <div style={{ fontSize: '14px', color: 'var(--text-secondary)', fontWeight: 700 }}>{t('optimize.current_period_cost')}</div>
                    <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary)', marginTop: '3px' }}>
                      {fmt(totalCurrent)}
                    </div>
                    <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '1px' }}>{t('compare.current')}</div>
                  </div>
                  <div style={{ flex: 1, textAlign: 'center' }}>
                    <div style={{ fontSize: '14px', color: 'var(--text-secondary)', fontWeight: 700 }}>{t('optimize.candidate_period_cost')}</div>
                    <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--accent)', marginTop: '3px' }}>
                      {fmt(totalOptimal)}
                    </div>
                    <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '1px' }}>{t('optimize.candidate_label')}</div>
                  </div>
                </div>

                {/* Savings callout */}
                {deltaCost !== null && (
                  <div style={{
                    marginTop: '12px',
                    padding: '10px',
                    borderRadius: '8px',
                    background: deltaCost > 0 ? '#f0fdf4' : deltaCost < 0 ? '#fef3f2' : '#f8f9fa',
                    border: `1px solid ${deltaCost > 0 ? '#bbf7d0' : deltaCost < 0 ? '#fecdd3' : 'var(--border)'}`,
                    textAlign: 'center',
                  }}>
                    <div style={{ fontSize: '14px', color: 'var(--text-secondary)', fontWeight: 700 }}>{t('optimize.period_cost_difference')}</div>
                    <div style={{ fontSize: '18px', fontWeight: 800, color: deltaCost > 0 ? 'var(--success)' : 'var(--danger)', marginTop: '2px' }}>
                      {deltaCost > 0 ? '↓' : '↑'} {fmt(Math.abs(deltaCost))}
                    </div>
                  </div>
                )}

                {/* Peak requirement + staffing lines */}
                {staffingSummaryAvailable && (
                  <div style={{ marginTop: '12px', borderTop: '1px solid #e9ecef', paddingTop: '10px' }}>
                    {staffingTotalsValue && (
                      <div style={{ marginBottom: '8px' }}>
                        <div className="form-hint">{t('optimize.net_staffing_reduction')}</div>
                        <div style={{ fontWeight: 800 }}>
                          {staffingTotalsValue.net > 0
                            ? t('optimize.net_reduced', { count: staffingTotalsValue.net })
                            : staffingTotalsValue.net < 0
                            ? t('optimize.net_added', { count: Math.abs(staffingTotalsValue.net) })
                            : t('optimize.net_no_change')}
                        </div>
                        <div style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
                          {t('optimize.staffing_formula', {
                            removed: staffingTotalsValue.removed,
                            added: staffingTotalsValue.added,
                          })}
                        </div>
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px', marginBottom: '4px' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>{t('optimize.peak_requirement')}</span>
                      <span style={{ fontWeight: 800 }}>
                        {t(peakRequirement === 1 ? 'optimize.cashier_count' : 'optimize.cashier_count_plural', { count: peakRequirement })}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px', marginBottom: '4px' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>{t('optimize.available_pool')}</span>
                      <span style={{ fontWeight: 800 }}>
                        {poolIsProvided
                          ? t(availablePool === 1 ? 'optimize.cashier_count' : 'optimize.cashier_count_plural', { count: availablePool })
                          : '—'}
                      </span>
                    </div>
                    {poolGap !== null && (
                      <div className={`alert ${poolGap >= 0 ? 'alert-ok' : 'alert-warn'}`} style={{ marginTop: '8px', fontSize: '14px' }}>
                        {poolGap >= 0
                          ? t('optimize.pool_can_cover')
                          : t(Math.abs(poolGap) === 1 ? 'optimize.pool_short' : 'optimize.pool_short_plural', {
                              count: Math.abs(poolGap),
                            })}
                      </div>
                    )}
                    {staffingLines.length > 0 && (
                      <div style={{ marginTop: '8px' }}>
                        {staffingLines.map((line) => (
                          <div key={line} style={{ fontSize: '14px', color: 'var(--text-primary)', padding: '3px 0' }}>{line}</div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {!staffingSummaryAvailable && (
                  <p style={{ marginTop: '12px', color: 'var(--text-secondary)', fontSize: '14px' }}>
                    {t('system.staffing_unavailable')}
                  </p>
                )}

                {/* Recommendation */}
                {rows.length > 0 && (
                  <div style={{
                    marginTop: '12px',
                    padding: '12px',
                    borderRadius: '10px',
                    background: 'var(--info-bg)',
                    border: '1px solid #d6e5f3',
                  }}>
                    <div style={{ fontSize: '14px', color: 'var(--text-secondary)', fontWeight: 700 }}>{t('optimize.candidate_explanation')}</div>
                    <p style={{ fontSize: '14px', color: 'var(--text-primary)', marginTop: '4px', lineHeight: 1.5 }}>
                      {rows[0]?.explanation || rows[0]?.recommendation || t('optimize.review_candidate')}
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '14px' }}>
                <p style={{ margin: 0 }}>{t('optimize.empty_result')}</p>
                <p style={{ margin: '4px 0 0', fontSize: '14px' }}>{t('optimize.empty_result_help')}</p>
              </div>
            )}
          </div>

          {/* What-If Card */}
          {rows && (
            <div className="card" style={{ padding: '18px' }}>
              <h3 className="section-title">{t('page2.what_if')}</h3>
              <div className="form-row" style={{ alignItems: 'flex-end', gap: '10px' }}>
                <div className="form-field" style={{ flex: 1 }}>
                  <label htmlFor="opt-mult" style={{ fontSize: '14px', fontWeight: 800 }}>{t('optimize.lambda_multiplier')}</label>
                  <input
                    id="opt-mult"
                    aria-label={t('optimize.lambda_multiplier')}
                    type="number"
                    step="any"
                    value={multiplier}
                    onChange={(e) => setMultiplier(e.target.value)}
                    style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }}
                  />
                </div>
                <button
                  type="button"
                  onClick={handleWhatIf}
                  disabled={running}
                  style={{ padding: '8px 16px', background: 'var(--accent)', color: 'var(--primary-contrast)', border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: 700, cursor: running ? 'not-allowed' : 'pointer', height: '35px' }}
                >
                  {t('optimize.what_if')}
                </button>
              </div>
            </div>
          )}

          {/* Save Scenario Card */}
          {rows && (
            <div className="card" style={{ padding: '18px' }}>
              <h3 className="section-title">{t('page2.save_scenario')}</h3>
              <div className="form-row" style={{ alignItems: 'flex-end', gap: '10px' }}>
                <div className="form-field" style={{ flex: 1 }}>
                  <label htmlFor="opt-scenario" style={{ fontSize: '14px', fontWeight: 800 }}>{t('optimize.scenario_name')}</label>
                  <input
                    id="opt-scenario"
                    aria-label={t('optimize.scenario_name')}
                    type="text"
                    value={scenarioName}
                    onChange={(e) => setScenarioName(e.target.value)}
                    placeholder={t('optimize.scenario_placeholder')}
                    style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }}
                  />
                </div>
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving || running || stale || !snapshot || !rows?.length || !scenarioName.trim()}
                  style={{ padding: '8px 16px', background: 'var(--primary)', color: 'var(--primary-contrast)', border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: 700, cursor: saving || running || stale ? 'not-allowed' : 'pointer', height: '35px' }}
                >
                  {t('common.save')}
                </button>
              </div>
              {!stale && rows.length > 0 && !comparisonComplete(rows) && <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '6px' }}>{t('system.save_incomplete')}</p>}
              {saved && !stale && <div className="alert alert-success" style={{ marginTop: '8px' }}>{t('optimize.saved')}</div>}
            </div>
          )}
        </div>
      </div>

      {running && <ApiState.Loading />}
      {error && <div className="alert alert-error" style={{ marginTop: '12px' }}>{error}</div>}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="alert alert-warn" style={{ marginTop: '12px' }}>
          {warnings.map((w) => w.feasibility_status === 'NO_FEASIBLE_CONFIGURATION' ? t('system.no_feasible') : w.warning).join(' ')}
        </div>
      )}
      {warnings.some((w) => w.feasibility_status === 'INVALID_INPUT') && (
        <div className="alert alert-warn" style={{ marginTop: '12px' }}>
          {t('optimize.blocked_continue_simulate')}{' '}
          <Link to={`/analyses/${analysisId}/simulate`}>{t('nav.simulate')}</Link>
        </div>
      )}

      {/* NovaQ Insights */}
      {rows && (() => {
        const avgCurrentRho = completeFiniteAverage(rows.map((row) => row.rho_current))
        const avgCurrentWq = completeFiniteAverage(rows.map((row) => row.Wq_current))
        const avgOptWq = completeFiniteAverage(rows.map((row) => row.Wq_optimal))
        const insights = generateOptimizationInsights(
          rows.length > 0 ? Math.round(rows.reduce((s, r) => s + r.c_current, 0) / rows.length) : 0,
          peakRequirement,
          avgCurrentWq !== null ? avgCurrentWq * 60 : null,
          avgOptWq !== null ? avgOptWq * 60 : null,
          avgCurrentRho,
          t,
        )
        return insights.length > 0 ? <NovaQInsights insights={insights} /> : null
      })()}

      {/* Staffing Table */}
      {rows && (
        <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
          <h3 className="section-title">{t('optimize.staffing_table')}</h3>
          <div className="status-legend" aria-label={t('optimize.status_legend')} style={{ marginBottom: '10px' }}>
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
          <div className="table-scroll" role="region" aria-label={t('optimize.staffing_table')} tabIndex={0}>
            <table>
              <caption className="sr-only">{t('optimize.staffing_table')}</caption>
              <thead>
                <tr>
                  {COLUMNS.map((col) => (
                    <th scope="col" key={col.label}>{col.label}</th>
                  ))}
                  <th scope="col">{t('optimize.recommendation')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.time}>
                    {COLUMNS.map((col) => {
                      const content = col.render
                        ? col.render(row)
                        : col.label === 'segment'
                        ? col.current(row)
                        : `${col.current(row)} → ${col.optimized(row)}`
                      return col.label === 'segment'
                        ? <th scope="row" key={col.label}>{content}</th>
                        : <td key={col.label}>{content}</td>
                    })}
                    <td>
                      {row.explanation && row.explanation !== row.recommendation ? (
                        <>
                          <p>{row.explanation}</p>
                          <small>{row.selected_model}</small>
                        </>
                      ) : (
                        <small>{row.selected_model}</small>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
