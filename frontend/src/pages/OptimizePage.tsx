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
import { optimizeSeparate, optimizeSeparateBreaks, type BreakOptimizeResult } from '../api/optimization'
import { createScenario } from '../api/scenarios'
import type { DatasetOut, OptimizationOut, SegmentRow, SeparateSchedule } from '../api/types'
import { NovaQInsights } from '../components/insights/NovaQInsights'
import { generateOptimizationInsights } from '../lib/insights'
import {
  completeFiniteAverage,
  comparisonComplete,
  comparisonTotals,
} from '../lib/comparison'
import { fmt, fmtPct, messageOf } from '../lib/format'
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

function formatLaneCount(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : String(value)
}

function formatAdjustment(value: number | null | undefined, t: TFunction): string {
  if (value === null || value === undefined) return '—'
  if (value === 0) return t('optimize.sep_keep')
  return value > 0 ? `+${value}` : String(value)
}

function SeparateScheduleCard({ schedule }: { schedule: SeparateSchedule }) {
  const { t } = useTranslation()
  return (
    <div className="card result-card" style={{
      background: 'linear-gradient(135deg, #faf7f2 0%, #fafafa 100%)',
      border: '1px solid #f0ece4',
      borderRadius: '13px',
      padding: '18px',
    }}>
      <h3 className="section-title">{t('optimize.sep_estimated_plan')}</h3>
      <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '4px' }}>
        <span>{t('optimize.sep_target')}: {Math.round(schedule.target_utilization * 100)}%</span>
        {' · '}<span>{t('optimize.sep_method')}</span>
        {' · '}<span>{t('optimize.sep_replications')}: {schedule.des.replications}</span>
      </div>
      {schedule.overall !== 'COMPLETE' && (
        <div role="alert" className="alert alert-warn" style={{ marginTop: '12px' }}>
          <strong>
            {schedule.overall === 'INFEASIBLE'
              ? t('optimize.sep_infeasible')
              : t('optimize.sep_unavailable_title')}
          </strong>
          {schedule.reason && <p style={{ margin: '4px 0 0' }}>{schedule.reason}</p>}
          {schedule.overall !== 'INFEASIBLE' && (
            <p style={{ margin: '4px 0 0' }}>{t('optimize.sep_unavailable_body')}</p>
          )}
        </div>
      )}
      <div className="table-scroll" role="region" aria-label={t('optimize.sep_estimated_plan')} tabIndex={0} style={{ marginTop: '12px' }}>
        <table>
          <thead>
            <tr>
              <th scope="col">{t('optimize.sep_col_time')}</th>
              <th scope="col">{t('optimize.sep_col_current')}</th>
              <th scope="col">{t('optimize.sep_col_optimal')}</th>
              <th scope="col">{t('optimize.sep_col_adjustment')}</th>
              <th scope="col">{t('optimize.sep_col_peak')}</th>
              <th scope="col">{t('optimize.sep_col_cost')}</th>
            </tr>
          </thead>
          <tbody>
            {schedule.periods.map((period) => {
              const uncertainty = period.optimum?.cost_uncertainty
              return (
                <tr key={period.time}>
                  <th scope="row">{period.time}</th>
                  <td>{period.current_active_lanes === null ? '—' : period.current_active_lanes.length}</td>
                  <td>{formatLaneCount(period.optimal_active_lanes)}</td>
                  <td>{formatAdjustment(period.adjustment, t)}</td>
                  <td>{fmtPct(period.optimum?.candidate_utilization ?? null)}</td>
                  <td>
                    {fmt(period.optimum?.total_cost ?? null)}
                    {uncertainty && uncertainty.ci_lower !== null && uncertainty.ci_upper !== null && (
                      <small style={{ display: 'block', color: 'var(--text-secondary)' }}>
                        {t('optimize.sep_cost_ci')}: {fmt(uncertainty.ci_lower)}–{fmt(uncertainty.ci_upper)}
                      </small>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {schedule.periods.map((period) => (
        <details key={period.time} style={{ marginTop: '8px' }}>
          <summary style={{ fontSize: '14px', fontWeight: 700, cursor: 'pointer' }}>
            {t('optimize.sep_candidate_evidence')} · {period.time}
          </summary>
          <table style={{ marginTop: '6px' }}>
            <thead>
              <tr>
                <th scope="col">{t('optimize.sep_col_lanes')}</th>
                <th scope="col">{t('optimize.sep_col_status')}</th>
                <th scope="col">{t('optimize.sep_col_peak')}</th>
                <th scope="col">{t('optimize.sep_col_mean_cost')}</th>
              </tr>
            </thead>
            <tbody>
              {period.candidates.map((candidate) => (
                <tr key={candidate.active_lane_count}>
                  <td>{candidate.active_lane_count}</td>
                  <td>{candidate.status}</td>
                  <td>{fmtPct(candidate.candidate_utilization)}</td>
                  <td>{fmt(candidate.mean_total_cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      ))}
    </div>
  )
}

function breakLabel(label: string, t: TFunction): string {
  const match = /^Break (\d+)$/.exec(label)
  return match ? t('optimize.breaks_label', { number: match[1] }) : label
}

function BreakOptimizerCard({ analysisId, datasetId }: { analysisId: number; datasetId: string }) {
  const { t } = useTranslation()
  const [target, setTarget] = useState(0.85)
  const [maxMove, setMaxMove] = useState(120)
  const [result, setResult] = useState<BreakOptimizeResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const rho = (value: number | null) => (value === null ? t('optimize.breaks_nobody_working') : fmt(value))

  async function runBreaks() {
    setError(null)
    setRunning(true)
    try {
      setResult(await optimizeSeparateBreaks(analysisId, {
        dataset_id: datasetId ? Number(datasetId) : null,
        target_rho: target,
        max_shift_minutes: maxMove,
      }))
    } catch (err) {
      setResult(null)
      setError(messageOf(err, t('errors.server')))
    } finally {
      setRunning(false)
    }
  }

  const changed = result ? result.slots.filter((slot) => slot.rho_before !== slot.rho_after) : []
  return (
    <div className="card" style={{ marginTop: '16px' }}>
      <h2 className="section-title">{t('optimize.breaks_title')}</h2>
      <p className="form-hint">{t('optimize.breaks_help')}</p>
      <div className="form-row" style={{ gap: '12px', alignItems: 'flex-end' }}>
        <div className="form-field">
          <label htmlFor="break-target">{t('optimize.breaks_target')}</label>
          <input id="break-target" type="number" min={0.05} max={1} step={0.05} value={target}
            onChange={(e) => setTarget(Number(e.target.value))} />
        </div>
        <div className="form-field">
          <label htmlFor="break-window">{t('optimize.breaks_window')}</label>
          <input id="break-window" type="number" min={0} max={240} step={15} value={maxMove}
            onChange={(e) => setMaxMove(Number(e.target.value))} />
        </div>
        <button type="button" disabled={running} onClick={() => void runBreaks()}>
          {running ? t('optimize.breaks_running') : t('optimize.breaks_run')}
        </button>
      </div>
      {error && <div role="alert" className="alert alert-error" style={{ marginTop: '12px' }}>{error}</div>}
      {result && (
        <div style={{ marginTop: '12px' }}>
          <p role="status"><strong>{t(result.status === 'improved' ? 'optimize.breaks_status_improved' : 'optimize.breaks_status_no_improvement')}</strong></p>
          <p>{t('optimize.breaks_peak', { before: rho(result.peak_rho.before), after: rho(result.peak_rho.after) })}</p>
          <p>{t('optimize.breaks_above_target', { target: fmt(result.target_rho), before: result.slots_above_target.before, after: result.slots_above_target.after })}</p>
          <div className="table-scroll" role="region" aria-label={t('optimize.breaks_table_label')} tabIndex={0}>
            <table aria-label={t('optimize.breaks_table_label')}>
              <thead>
                <tr>
                  <th scope="col">{t('optimize.breaks_col_cashier')}</th>
                  <th scope="col">{t('optimize.breaks_col_break')}</th>
                  <th scope="col">{t('optimize.breaks_col_current')}</th>
                  <th scope="col">{t('optimize.breaks_col_proposed')}</th>
                  <th scope="col">{t('optimize.breaks_col_minutes')}</th>
                  <th scope="col">{t('optimize.breaks_col_moved')}</th>
                </tr>
              </thead>
              <tbody>
                {result.proposed_breaks.map((entry, index) => (
                  <tr key={`${entry.queue_id}-${index}`}>
                    <th scope="row">{entry.queue_id}</th>
                    <td>{breakLabel(entry.label, t)}</td>
                    <td>{entry.current_start_time.slice(0, 5)}</td>
                    <td>{entry.scheduled_start_time.slice(0, 5)}</td>
                    <td>{entry.duration_minutes}</td>
                    <td>{t(entry.shift_minutes !== 0 ? 'optimize.breaks_moved_yes' : 'optimize.breaks_moved_no')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {changed.length > 0 && (
            <>
              <h3 className="section-title">{t('optimize.breaks_slots_title')}</h3>
              <div className="table-scroll" role="region" aria-label={t('optimize.breaks_slots_title')} tabIndex={0}>
                <table aria-label={t('optimize.breaks_slots_title')}>
                  <thead>
                    <tr>
                      <th scope="col">{t('optimize.breaks_col_slot')}</th>
                      <th scope="col">{t('optimize.breaks_col_rho_before')}</th>
                      <th scope="col">{t('optimize.breaks_col_rho_after')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {changed.map((slot) => (
                      <tr key={slot.start}>
                        <th scope="row">{`${slot.start}–${slot.end}`}</th>
                        <td>{rho(slot.rho_before)}</td>
                        <td>{rho(slot.rho_after)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          <p className="form-hint">{t('optimize.breaks_slot_note')}</p>
          <h3 className="section-title">{t('optimize.breaks_gaps_title')}</h3>
          {result.staffing_gaps.length === 0 ? (
            <p>{t('optimize.breaks_gaps_none')}</p>
          ) : (
            <ul>
              {result.staffing_gaps.map((gap) => (
                <li key={gap.start}>{t('optimize.breaks_gap_item', { start: gap.start, end: gap.end, onShift: gap.on_shift, rho: rho(gap.rho_no_breaks) })}</li>
              ))}
            </ul>
          )}
          <h3 className="section-title">{t('optimize.breaks_des_title')}</h3>
          <div className="table-scroll" role="region" aria-label={t('optimize.breaks_des_title')} tabIndex={0}>
            <table aria-label={t('optimize.breaks_des_title')}>
              <thead>
                <tr>
                  <th scope="col">{t('optimize.breaks_col_metric')}</th>
                  <th scope="col">{t('optimize.breaks_col_current_schedule')}</th>
                  <th scope="col">{t('optimize.breaks_col_proposed_schedule')}</th>
                </tr>
              </thead>
              <tbody>
                {([
                  ['optimize.breaks_des_mean_wait', 'mean_wait_minutes', 2],
                  ['optimize.breaks_des_max_queue', 'max_queue', 1],
                  ['optimize.breaks_des_served', 'served', 1],
                ] as const).map(([label, key, digits]) => (
                  <tr key={key}>
                    <th scope="row">{t(label)}</th>
                    <td>{fmt(result.des.current.summary[key], digits)}</td>
                    <td>{fmt(result.des.proposed.summary[key], digits)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>{t('optimize.breaks_des_better', { better: result.des.comparison.proposed_better_runs, runs: result.des.comparison.runs })}</p>
          <p className="form-hint">{t('optimize.breaks_des_note')}</p>
        </div>
      )}
    </div>
  )
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
  const [sepTarget, setSepTarget] = useState(0.70)
  const [schedule, setSchedule] = useState<SeparateSchedule | null>(null)
  const [sepSnapshot, setSepSnapshot] = useState<{
    signature: string; datasetId: string; rowCount: number; target: number;
    serverCost: number | undefined; waitingCost: number | undefined;
    factor: number; minLanes: number; calculatedAt: string;
  } | null>(null)
  const sepSignature = JSON.stringify({
    datasetId, sepTarget,
    serverCost: options.server_cost_per_hr, waitingCost: options.customer_waiting_cost,
    multiplier,
  })
  const sepStale = sepSnapshot !== null && sepSnapshot.signature !== sepSignature

  const datasets = useQuery({
    queryKey: ['datasets', analysisId],
    queryFn: () => listDatasets(analysisId),
  })
  const analysis = useQuery({
    queryKey: ['analysis', analysisId],
    queryFn: () => getAnalysis(analysisId!),
    enabled: Number.isInteger(analysisId),
  })
  const isSeparateStaffing = analysis.data?.analysis.queue_setup.queue_structure === 'separate_queues'
  // Full coverage: every configured Separate queue stays active in every candidate.
  const separateQueueCount = analysis.data?.analysis.queue_setup.queue_ids.length ?? 0

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

  async function runSeparate(dataset: DatasetOut, factor = 1) {
    if (analysisId === undefined) {
      setError(t('errors.server'))
      return
    }
    setError(null)
    setSaved(false)
    setRunning(true)
    try {
      const out = await optimizeSeparate(analysisId, Number(dataset.id), {
        target_utilization: sepTarget,
        server_cost_per_hr: options.server_cost_per_hr,
        customer_waiting_cost: options.customer_waiting_cost,
        lambda_multiplier: factor,
        min_active_lanes: separateQueueCount,
      })
      setSchedule(out.schedule)
      const rowCount = datasets.data?.datasets.find((d: DatasetOut) => String(d.id) === datasetId)?.row_count ?? 0
      setSepSnapshot({
        signature: sepSignature, datasetId, rowCount, target: sepTarget,
        serverCost: options.server_cost_per_hr, waitingCost: options.customer_waiting_cost,
        factor, minLanes: separateQueueCount, calculatedAt: new Date().toISOString(),
      })
      setScenarioName((prev) => prev || `Optimal @ ${Math.round(sepTarget * 100)}%`)
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
    if (isSeparateStaffing) {
      await runSeparate(dataset)
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
    if (isSeparateStaffing) {
      await runSeparate(dataset, factor)
      return
    }
    if (!rows) {
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

  async function handleSaveSeparate() {
    if (
      !schedule || schedule.overall !== 'COMPLETE' || !sepSnapshot || sepStale ||
      running || saving || !scenarioName.trim()
    ) {
      return
    }
    setSaving(true)
    setSaved(false)
    try {
      const target = schedule.target_utilization
      const inputOptions = {
        target_utilization: target,
        server_cost_per_hr: sepSnapshot.serverCost,
        customer_waiting_cost: sepSnapshot.waitingCost,
        min_active_lanes: sepSnapshot.minLanes,
        max_active_lanes: null,
        lambda_multiplier: sepSnapshot.factor,
        des: { ...schedule.des },
      }
      await createScenario({
        name: scenarioName.trim(),
        analysis_id: analysisId,
        dataset_id: sepSnapshot.datasetId ? Number(sepSnapshot.datasetId) : null,
        settings: {
          ...inputOptions,
          calculation: {
            schema_version: 2,
            engine_version: 'novaq-2026-09-separate-des-v1',
            analysis_id: analysisId,
            dataset_id: sepSnapshot.datasetId ? Number(sepSnapshot.datasetId) : null,
            dataset_row_count: sepSnapshot.rowCount,
            options: inputOptions,
            calculated_at: sepSnapshot.calculatedAt,
          },
        },
        results: { schedule },
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
          <div className="topbar-eyebrow">{t(isSeparateStaffing ? 'optimize.staffing_eyebrow' : 'optimize.eyebrow')}</div>
          <h1 className="page-title">{t(isSeparateStaffing ? 'optimize.staffing_title' : 'optimize.title')}</h1>
          <p className="page-caption">{t(isSeparateStaffing ? 'optimize.staffing_description' : 'optimize.description')}</p>
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
          {/* Goal Presets (shared optimizer only: preset targets sit outside the Separate range) */}
          {!isSeparateStaffing && (
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
          )}

          {/* Utilization target (Separate optimizer: approved 40-90% range) */}
          {isSeparateStaffing && (
          <div className="card" style={{ padding: '18px' }}>
            <h3 className="section-title">{t('optimize.sep_target')}</h3>
            <div className="form-field">
              <label htmlFor="opt-sep-target" style={{ fontSize: '14px', fontWeight: 800 }}>
                {t('optimize.sep_target')} ({Math.round(sepTarget * 100)}%)
              </label>
              <input
                id="opt-sep-target"
                aria-label={t('optimize.sep_target')}
                type="range"
                min={0.4}
                max={0.9}
                step={0.05}
                value={sepTarget}
                onChange={(e) => setSepTarget(Number(e.target.value))}
                style={{ width: '100%' }}
              />
              <span className="form-hint">{t('optimize.sep_target_desc')}</span>
            </div>
          </div>
          )}

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
            {isSeparateStaffing && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div className="form-field">
                <label htmlFor="opt-sep-cost" style={{ fontSize: '14px', fontWeight: 800 }}>{t('optimize.server_cost')}</label>
                <input
                  id="opt-sep-cost"
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
                <label htmlFor="opt-sep-wait" style={{ fontSize: '14px', fontWeight: 800 }}>{t('optimize.waiting_cost')}</label>
                <input
                  id="opt-sep-wait"
                  type="number"
                  step="any"
                  value={options.customer_waiting_cost ?? ''}
                  onChange={(e) =>
                    setOptions((o) => ({ ...o, customer_waiting_cost: Number(e.target.value) }))
                  }
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }}
                />
              </div>
            </div>
            )}
            {isSeparateStaffing ? null : (
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
            )}
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
          {/* Separate result card replaces the shared candidate card */}
          {isSeparateStaffing && schedule && <SeparateScheduleCard schedule={schedule} />}
          {isSeparateStaffing && !schedule && !running && !error && (
            <div className="card result-card" style={{
              border: '1px solid #f0ece4',
              borderRadius: '13px',
              padding: '18px',
            }}>
              <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '14px' }}>
                <p style={{ margin: 0 }}>{t('optimize.empty_result')}</p>
                <p style={{ margin: '4px 0 0', fontSize: '14px' }}>{t('optimize.empty_result_help')}</p>
              </div>
            </div>
          )}
          {/* Result Card */}
          {!isSeparateStaffing && (
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
          )}

          {/* What-If Card */}
          {(rows || (isSeparateStaffing && schedule)) && (
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

          {/* Save Scenario Card (Separate: verified DES snapshot, COMPLETE only) */}
          {isSeparateStaffing && schedule && (
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
                  onClick={handleSaveSeparate}
                  disabled={saving || running || sepStale || !sepSnapshot || schedule.overall !== 'COMPLETE' || !scenarioName.trim()}
                  style={{ padding: '8px 16px', background: 'var(--primary)', color: 'var(--primary-contrast)', border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: 700, cursor: saving || running || sepStale ? 'not-allowed' : 'pointer', height: '35px' }}
                >
                  {t('common.save')}
                </button>
              </div>
              {sepStale && <div role="alert" className="alert alert-warn" style={{ marginTop: '8px' }}>{t('integrity.stale')}</div>}
              {saved && !sepStale && <div className="alert alert-success" style={{ marginTop: '8px' }}>{t('optimize.saved')}</div>}
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
      {analysisId !== undefined && isSeparateStaffing && <BreakOptimizerCard analysisId={analysisId} datasetId={datasetId} />}
      {analysis.data && !isSeparateStaffing && (
        <p className="form-hint" style={{ marginTop: '16px' }}>{t('optimize.breaks_shared_note')}</p>
      )}
    </div>
  )
}
