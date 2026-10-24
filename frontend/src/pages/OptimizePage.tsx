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
import { getAnalysis } from '../api/analyses'
import { optimizeBatch, DEFAULT_OPTIONS, type OptimizeOptions } from '../api/optimization'
import { createScenario } from '../api/scenarios'
import { selectWorkflowScenario } from '../api/workflow'
import { SupervisorSchedule } from '../components/SupervisorSchedule'
import { currentDatasetId, isForPlanning } from '../lib/datasets'
import type { DatasetOut, OptimizationOut, SegmentRow } from '../api/types'
import { NovaQInsights } from '../components/insights/NovaQInsights'
import { generateOptimizationInsights } from '../lib/insights'
import {
  completeFiniteAverage,
  comparisonComplete,
  comparisonTotals,
} from '../lib/comparison'
import { fmt, fmtPctDecimal, messageOf } from '../lib/format'
import { segmentsOf } from '../lib/queue'
import { utilizationBand } from '../lib/utilization'
import { ApiState } from '../components/ui/ApiState'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import { HelpLink } from '../components/ui/HelpLink'

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
  return utilizationBand(rho)
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
  { label: 'ρ', current: (r) => fmtPctDecimal(r.rho_current), optimized: (r) => fmtPctDecimal(r.rho_optimal) },
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
  { label: 'c', current: (r) => (r.c_current === null ? '—' : String(r.c_current)), optimized: (r) => fmt(r.c_optimal, 0) },
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
  const [pickedDatasetId, setDatasetId] = useState<string | null>(null)
  const datasets = useQuery({
    queryKey: ['datasets', analysisId],
    queryFn: () => listDatasets(analysisId),
  })
  // U10 F11: the current planning file is chosen until the user picks one ("—" is a pick too).
  const planningFiles = (datasets.data?.datasets ?? []).filter(isForPlanning)
  const defaultDatasetId = currentDatasetId(datasets.data?.datasets)
  const datasetId = pickedDatasetId !== null ? pickedDatasetId
    : defaultDatasetId !== null && planningFiles.some((d: DatasetOut) => d.id === defaultDatasetId) ? String(defaultDatasetId) : ''
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
  // "Use this plan" (spec §7.6, D4): save, then select for simulation; a refused selection leaves the plan saved.
  const [used, setUsed] = useState(false)
  const [selectionProblem, setSelectionProblem] = useState<string | null>(null)
  const [availableCashiers, setAvailableCashiers] = useState('')
  const analysis = useQuery({
    queryKey: ['analysis', analysisId],
    queryFn: () => getAnalysis(analysisId!),
    enabled: Number.isInteger(analysisId),
  })
  const isSeparateStaffing = analysis.data?.analysis.queue_setup.queue_structure === 'separate_queues'

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
    if (!dataset) {
      return
    }
    const factor = Number(multiplier)
    if (!Number.isFinite(factor) || factor <= 0) {
      setError(t('optimize.multiplier_range_error'))
      return
    }
    if (!rows) {
      return
    }
    await run(dataset, factor)
  }

  async function selectSavedPlan(scenarioId: number | string) {
    try {
      await selectWorkflowScenario(analysisId!, Number(scenarioId))
      void queryClient.invalidateQueries({ queryKey: ['workflow', analysisId] })
      void queryClient.invalidateQueries({ queryKey: ['separate-comparison', analysisId] })
      setUsed(true)
    } catch (err) {
      setSelectionProblem(messageOf(err, t('errors.server')))
    }
  }

  async function handleSave(use = false) {
    if (!rows?.length || !snapshot || stale || running || !scenarioName.trim()) {
      return
    }
    setSaving(true)
    setSaved(false)
    setUsed(false)
    setSelectionProblem(null)
    try {
      const created = await createScenario({
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
      if (use) await selectSavedPlan(created.scenario.id)
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

  if (isSeparateStaffing && analysis.data) return <SupervisorSchedule key={analysisId} analysis={analysis.data.analysis} />

  return (
    <div className="optimize-page">
      {/* Topbar */}
      <div className="topbar">
        <div>
          <div className="topbar-eyebrow">{t('optimize.eyebrow')}</div>
          <div className="title-row"><h1 className="page-title">{t('optimize.title')}</h1><HelpLink topic="plans" /></div>
          <p className="page-caption">{t('optimize.description')}</p>
        </div>
      </div>

      {(analysis.data?.analysis.queue_setup.counter_breaks?.length ?? 0) > 0 && (
        <p className="form-hint" data-testid="counter-breaks-note">{t('optimize.counter_breaks_note')}</p>
      )}
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

      {/* Controls precede full-width results */}
      <div className="optimize-flow" style={{ marginTop: '12px' }}>
        {/* Controls */}
        <div className="optimize-controls">
          {/* Goal Presets (shared optimizer only: preset targets sit outside the Separate range) */}
          {(
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
                      ? 'var(--state-current-bg)' : 'var(--color-bg-surface)',
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
          )}

          {/* Utilization target (Separate optimizer: approved 40-90% range) */}


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
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--color-border-control)', borderRadius: '8px', fontSize: '16px' }}
                >
                  <option value="">—</option>
                  {datasets.data?.datasets.filter(isForPlanning).map((d: DatasetOut) => (
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
            <p className="form-hint">{t('plans.defaults_note', {
              target: fmtPctDecimal(DEFAULT_OPTIONS.target_utilization ?? 0),
              serverCost: DEFAULT_OPTIONS.server_cost_per_hr,
              waitingCost: DEFAULT_OPTIONS.customer_waiting_cost,
            })}</p>

            {(
            <div className="optimize-fields">
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
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--color-border-control)', borderRadius: '8px', fontSize: '16px' }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="opt-min" style={{ fontSize: '14px', fontWeight: 800 }}>{t('system.min_servers')}</label>
                <input id="opt-min" type="number" min={1} max={256} value={options.min_servers ?? 1} onChange={(e) => setOptions((o) => ({ ...o, min_servers: Number(e.target.value) }))} style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--color-border-control)', borderRadius: '8px', fontSize: '16px' }} />
              </div>
              <div className="form-field">
                <label htmlFor="opt-max" style={{ fontSize: '14px', fontWeight: 800 }}>{t('system.max_servers')}</label>
                <input id="opt-max" type="number" min={1} max={256} value={options.max_servers ?? 24} onChange={(e) => setOptions((o) => ({ ...o, max_servers: Number(e.target.value) }))} style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--color-border-control)', borderRadius: '8px', fontSize: '16px' }} />
              </div>
              <div className="form-field">
                <label htmlFor="opt-max-wait" style={{ fontSize: '14px', fontWeight: 800 }}>{t('system.max_wait')}</label>
                <input id="opt-max-wait" type="number" min={0} step="any" value={options.max_wait_minutes ?? ''} onChange={(e) => setOptions((o) => ({ ...o, max_wait_minutes: e.target.value === '' ? null : Number(e.target.value) }))} style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--color-border-control)', borderRadius: '8px', fontSize: '16px' }} />
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
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--color-border-control)', borderRadius: '8px', fontSize: '16px' }}
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
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--color-border-control)', borderRadius: '8px', fontSize: '16px' }}
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
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--color-border-control)', borderRadius: '8px', fontSize: '16px' }}
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
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--color-border-control)', borderRadius: '8px', fontSize: '16px' }}
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
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--color-border-control)', borderRadius: '8px', fontSize: '16px' }}
                />
              </div>
            </div>
            )}
            <button
              type="button"
              onClick={handleOptimize}
              disabled={running}
              className="button-primary"
              style={{ width: '100%', marginTop: '14px', padding: '12px 24px', background: running ? 'var(--disabled-bg)' : 'var(--accent)', color: running ? 'var(--color-disabled-fg)' : 'var(--color-action-primary-fg)', border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: 800, cursor: running ? 'not-allowed' : 'pointer' }}
            >
              {running ? t('common.loading') : t('optimize.run')}
            </button>
          </div>
        </div>

        {/* Results */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* Separate result card replaces the shared candidate card */}


          {/* Result Card */}
          {(
          <div className="card result-card" style={{
            background: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
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
                    <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--color-data-optimized)', marginTop: '3px' }}>
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
                    background: deltaCost > 0 ? 'var(--color-success-bg)' : deltaCost < 0 ? 'var(--color-danger-bg)' : 'var(--color-bg-subtle)',
                    border: `1px solid ${deltaCost > 0 ? 'var(--color-success-border)' : deltaCost < 0 ? 'var(--color-danger-border)' : 'var(--color-border-subtle)'}`,
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
                  <div style={{ marginTop: '12px', borderTop: '1px solid var(--color-border-subtle)', paddingTop: '10px' }}>
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
                      <div role="status" className={`alert ${poolGap >= 0 ? 'alert-ok' : 'alert-warn'}`} style={{ marginTop: '8px', fontSize: '14px' }}>
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
                    border: '1px solid var(--color-info-border)',
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
          )}

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
                    style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--color-border-control)', borderRadius: '8px', fontSize: '16px' }}
                  />
                </div>
                <button
                  type="button"
                  onClick={handleWhatIf}
                  disabled={running}
                  style={{ padding: '8px 16px', background: 'var(--accent)', color: running ? 'var(--color-disabled-fg)' : 'var(--color-action-primary-fg)', border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: 700, cursor: running ? 'not-allowed' : 'pointer', height: '35px' }}
                >
                  {t('optimize.what_if')}
                </button>
              </div>
            </div>
          )}

          {/* Save Scenario Card */}
          {!isSeparateStaffing && rows && (
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
                    style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--color-border-control)', borderRadius: '8px', fontSize: '16px' }}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => void handleSave(true)}
                  disabled={saving || running || stale || !snapshot || !rows?.length || !scenarioName.trim()}
                >
                  {t('plans.use_this_plan')}
                </button>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => void handleSave()}
                  disabled={saving || running || stale || !snapshot || !rows?.length || !scenarioName.trim()}
                >
                  {t('plans.save_without_using')}
                </button>
              </div>
              <p className="form-hint">{t('plans.shared_estimate_note')}</p>
              {!stale && rows.length > 0 && !comparisonComplete(rows) && <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '6px' }}>{t('system.save_incomplete')}</p>}
              {saved && !stale && !used && !selectionProblem && <div className="alert alert-success" role="status" style={{ marginTop: '8px' }}>{t('optimize.saved')}</div>}
              {used && !stale && <div className="alert alert-success" role="status" style={{ marginTop: '8px' }}>{t('plans.used')}</div>}
              {selectionProblem && <div className="alert alert-warn" role="alert" style={{ marginTop: '8px' }}>{t('plans.saved_not_used', { reason: selectionProblem })}</div>}
            </div>
          )}

          {/* Save Scenario Card (Separate: verified DES snapshot, COMPLETE only) */}

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
          <Link to={`/simulation/results?analysis=${analysisId}&plan=suggested`}>{t('nav.queue_simulation')}</Link>
        </div>
      )}

      {/* NovaQ Insights */}
      {rows && (() => {
        const avgCurrentRho = completeFiniteAverage(rows.map((row) => row.rho_current))
        const avgCurrentWq = completeFiniteAverage(rows.map((row) => row.Wq_current))
        const avgOptWq = completeFiniteAverage(rows.map((row) => row.Wq_optimal))
        // Staffing endpoints stay unavailable unless every required source value
        // is present: a blocked (INVALID_INPUT) plan must never read as "0".
        const avgCurrentC = completeFiniteAverage(rows.map((row) => row.c_current))
        const insights = generateOptimizationInsights(
          avgCurrentC !== null ? Math.round(avgCurrentC) : null,
          staffingSummaryAvailable ? peakRequirement : null,
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
                {rows.map((row, index) => (
                  <tr key={`${row.time}-${index}`}>
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

      {analysis.data && !isSeparateStaffing && (
        <p className="form-hint" style={{ marginTop: '16px' }}>{t('optimize.breaks_shared_note')}</p>
      )}
    </div>
  )
}
