import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { getAnalysisCurrent, listAnalysisDatasets } from '../api/analyses'
import { getObservedWait } from '../api/workflow'
import type { ObservedWaitSummary } from '../api/types'
import { ApiState } from '../components/ui/ApiState'
import { PeriodFilter } from '../components/analysis/PeriodFilter'
import { summarizeCashierWorkload } from '../lib/cashierWorkload'
import { fmtDecimal, fmtPct, fmtPctDecimal } from '../lib/format'
import { groupPeriodDemand, pickLeanPeriod, pickPeakPeriod } from '../lib/periodDemand'
import { ALL, matchesFilter } from '../lib/periodFilter'

function finiteValue(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value !== 'string' || value.trim() === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function statusKind(status: unknown) {
  const normalized = String(status ?? '').trim().toLowerCase()
  if (normalized.includes('critical') || normalized.includes('unstable')) return 'critical'
  if (normalized.includes('peak')) return 'peak'
  if (normalized.includes('normal')) return 'normal'
  if (normalized.includes('lean')) return 'lean'
  return 'neutral'
}

function shown(value: unknown) {
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function barWidth(value: number, max: number | null) {
  return max !== null && max > 0 ? `${Math.max(0, value) / max * 100}%` : '0%'
}

type ObservedRow = { time: string; modeled: number | null; observed: number | null; flagged: boolean }

function minutesText(hours: number | null): string {
  return hours === null || !Number.isFinite(hours) ? '—' : (hours * 60).toFixed(1)
}

/** Modeled vs observed Current wait per period; shared by Current and Comparison. */
export function ObservedWaitTable({ rows, flaggedAny, ratio, gap }: { rows: ObservedRow[]; flaggedAny: boolean; ratio: number; gap: number }) {
  const { t } = useTranslation()
  return (
    <section className="card" aria-labelledby="observed-wait-title">
      <h2 id="observed-wait-title" className="section-title">{t('current.observed_title')}</h2>
      {flaggedAny && <div className="alert alert-warn" role="status">{t('current.observed_banner')}</div>}
      <p className="chart-summary">
        {t('current.observed_caption')}
        {Number.isFinite(ratio) && Number.isFinite(gap) && ` ${t('current.observed_flag_rule', { ratio, gap })}`}
      </p>
      <div className="table-scroll" role="region" aria-labelledby="observed-wait-title" tabIndex={0}>
        <table aria-labelledby="observed-wait-title">
          <thead><tr><th scope="col">{t('common.time')}</th><th scope="col">{t('current.modeled_wait_avg')} ({t('analyses.minutes')})</th><th scope="col">{t('current.observed_wait')} ({t('analyses.minutes')})</th><th scope="col">{t('analyses.status')}</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.time} className={row.flagged ? 'row-warning' : undefined}>
                <th scope="row">{row.time}</th><td>{minutesText(row.modeled)}</td><td>{minutesText(row.observed)}</td><td>{row.flagged ? <span className="status-badge status-critical">{t('current.observed_flagged')}</span> : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function ObservedWaitSection({ summary }: { summary: ObservedWaitSummary }) {
  const rows = summary.periods.map((period) => ({ time: period.time, modeled: period.modeled_wait, observed: period.observed_wait, flagged: period.flagged }))
  return <ObservedWaitTable rows={rows} flaggedAny={summary.flagged_any} ratio={summary.ratio} gap={summary.min_gap_minutes} />
}

export function AnalysisCurrentPage() {
  const { t } = useTranslation()
  const id = Number(useParams().analysisId)
  const datasets = useQuery({ queryKey: ['datasets', id], queryFn: () => listAnalysisDatasets(id) })
  const datasetId = datasets.data?.datasets[0]?.id
  const query = useQuery({ queryKey: ['current', id, datasetId], queryFn: () => getAnalysisCurrent(id), enabled: Boolean(datasetId), retry: false })
  // Only event uploads persist observed waits; aggregate uploads show nothing (never zero).
  const derivedStatistics = query.data?.dataset?.validation?.derived_statistics
  const hasEventData = Array.isArray(derivedStatistics) && derivedStatistics.length > 0
  const observed = useQuery({
    queryKey: ['observed-wait', id, datasetId],
    queryFn: () => getObservedWait(id),
    enabled: hasEventData,
    retry: false,
  })
  const observedSummary = hasEventData && observed.data?.available ? observed.data : null
  const [period, setPeriod] = useState(ALL)
  const [line, setLine] = useState(ALL)

  if (datasets.isLoading || query.isLoading) return <ApiState.Loading />
  if (datasets.isError) return <ApiState.ErrorState error={datasets.error} />
  if (query.isError || !query.data) {
    return (
      <div className="page-stack">
        <header className="page-header">
          <p className="topbar-eyebrow">{t('current.eyebrow')}</p>
          <h1 className="page-title">{t('nav.current')}</h1>
          <p className="page-caption">{t('analyses.current_basis')}</p>
        </header>
        <ApiState.Empty message={t('analyses.no_dataset')} />
        <Link className="button-link" to="../setup">{t('analyses.go_setup')}</Link>
      </div>
    )
  }

  const { selected_model, rows, kpis, explanations } = query.data
  const showQueueColumn = rows.some((row) => typeof row.queue_id === 'string' && row.queue_id.trim() !== '')
  const avgRho = finiteValue(kpis?.avg_utilization)
  const avgWq = finiteValue(kpis?.avg_waiting_time)
  const numericWq = rows.map((row) => finiteValue(row.Wq)).filter((value): value is number => value !== null)
  const numericRho = rows.map((row) => finiteValue(row.rho)).filter((value): value is number => value !== null)
  const maxWq = numericWq.length > 0 ? Math.max(...numericWq) : null
  const maxRho = numericRho.length > 0 ? Math.max(...numericRho) : null
  const arrivalPoints = rows
    .map((row, index) => ({ index, time: shown(row.time), value: finiteValue(row.lambda) }))
    .filter((point): point is { index: number; time: string; value: number } => point.value !== null)
  // Separate scope: compare combined arrival rates per period; shared scope
  // keeps the long-standing single-row extremum so shared results are byte-identical.
  const separateScope = rows.length > 0 && rows.every((row) => row.queue_structure === 'separate_queues')
  const periodDemands = separateScope ? groupPeriodDemand(arrivalPoints) : []
  // One bar per period. Separate lines are summed for display only; a shared
  // row already covers every cashier, so it is charted as is.
  const arrivalBars = separateScope
    ? periodDemands.map((demand) => ({ key: demand.time, time: demand.time, value: demand.totalLambda, lines: demand.queueCount }))
    : arrivalPoints.map((point) => ({ key: `${point.time}-${point.index}`, time: point.time, value: point.value, lines: null }))
  const maxArrival = arrivalBars.length > 0 ? Math.max(...arrivalBars.map((bar) => bar.value)) : null
  const arrivalTableName = separateScope ? t('current.arrivals_combined_table') : t('current.arrivals_table')
  const workload = separateScope
    ? summarizeCashierWorkload(rows.map((row) => ({ queueId: row.queue_id, rho: finiteValue(row.rho), time: shown(row.time), status: row.status })))
    : []
  // ρ can pass 100% on an unstable line, so the scale grows to fit it.
  const workloadScale = Math.max(1, ...workload.map((cashier) => cashier.peakRho))
  const peakPeriod = separateScope
    ? (pickPeakPeriod(periodDemands)?.time ?? null)
    : (arrivalPoints.length > 0 ? arrivalPoints.reduce((peak, point) => point.value > peak.value ? point : peak).time : null)
  const leanPeriod = separateScope
    ? (pickLeanPeriod(periodDemands)?.time ?? null)
    : (arrivalPoints.length > 0 ? arrivalPoints.reduce((lean, point) => point.value < lean.value ? point : lean).time : null)
  const criticalCount = rows.filter((row) => statusKind(row.status) === 'critical').length
  const modelCounts = rows.reduce<Record<string, number>>((counts, row) => {
    const model = typeof row.model === 'string' && row.model.trim() ? row.model : t('common.not_available')
    counts[model] = (counts[model] ?? 0) + 1
    return counts
  }, {})
  const visibleRows = rows.filter((row) => matchesFilter(row.time, row.queue_id, period, line))
  const visibleExplanations = explanations.filter((item) => matchesFilter(item.time, item.queue_id, period, line))
  const filter = (idPrefix: string) => <PeriodFilter idPrefix={idPrefix} periods={rows.map((row) => row.time)} lines={rows.map((row) => row.queue_id)} period={period} line={line} onPeriod={setPeriod} onLine={setLine} />
  const modelEntries = Object.entries(modelCounts).sort((left, right) => right[1] - left[1])

  return (
    <div className="page-stack">
      <header className="page-header">
        <p className="topbar-eyebrow">{t('current.eyebrow')}</p>
        <h1 className="page-title">{t('nav.current')}</h1>
        <p className="page-caption">{t('current.description')}</p>
      </header>

      <div className="kpi-row kpi-row-summary">
        <section className="card kpi-card" aria-labelledby="current-wait-title">
          <h2 id="current-wait-title" className="kpi-group-title">{t('analyses.wait_summary')}</h2>
          <div className="kpi-pair">
            <div><div className="kpi-label">{hasEventData ? t('current.modeled_wait_avg') : t('analyses.avg_wq')}</div><div className="kpi-value state-current">{avgWq !== null ? `${(avgWq * 60).toFixed(1)} ${t('analyses.minutes')}` : t('common.not_available')}</div></div>
            <div><div className="kpi-label">{hasEventData ? t('current.modeled_wait_max') : t('analyses.max_wq')}</div><div className="kpi-value state-current">{maxWq !== null ? `${(maxWq * 60).toFixed(1)} ${t('analyses.minutes')}` : t('common.not_available')}</div></div>
          </div>
          <p className="kpi-hint">{t('current.persisted_baseline')}</p>
        </section>
        <section className="card kpi-card" aria-labelledby="current-util-title">
          <h2 id="current-util-title" className="kpi-group-title">{t('analyses.utilization_summary')}</h2>
          <div className="kpi-pair">
            <div><div className="kpi-label">{t('analyses.avg_rho')}</div><div className="kpi-value state-current">{avgRho !== null ? fmtPct(avgRho) : t('common.not_available')}</div></div>
            <div><div className="kpi-label">{t('analyses.max_rho')}</div><div className="kpi-value state-current">{maxRho !== null ? fmtPct(maxRho) : t('common.not_available')}</div></div>
          </div>
          <p className="kpi-hint">{t('current.utilization_basis', { count: numericRho.length })}</p>
        </section>
        <section className="card kpi-card" aria-labelledby="current-hours-title">
          <h2 id="current-hours-title" className="kpi-group-title">{t('analyses.hour_summary')}</h2>
          <div className="kpi-pair">
            <div><div className="kpi-label">{t('analyses.peak_hour')}</div><div className="kpi-value kpi-value-small">{peakPeriod ?? t('common.not_available')}</div></div>
            <div><div className="kpi-label">{t('analyses.lean_hour')}</div><div className="kpi-value kpi-value-small">{leanPeriod ?? t('common.not_available')}</div></div>
          </div>
          <p className="kpi-hint">{t('current.critical_count', { count: criticalCount })}</p>
        </section>
      </div>

      <div className="grid g2 current-visual-grid">
        <section className="card" aria-labelledby="arrival-chart-title">
          <h2 id="arrival-chart-title" className="section-title">{t('current.arrivals_title')}</h2>
          <p id="arrival-chart-summary" className="chart-summary">
            {arrivalBars.length === 0
              ? t('current.arrivals_unavailable')
              : separateScope ? t('current.arrivals_combined_summary', { count: arrivalBars.length }) : t('current.arrivals_summary', { count: arrivalBars.length })}
          </p>
          {arrivalBars.length > 0 ? (
            <>
              <p id="arrival-chart-axis" className="hbar-axis-note">{t('current.arrivals_axis')}</p>
              <div className="hbar-chart" role="img" aria-labelledby="arrival-chart-title" aria-describedby="arrival-chart-summary arrival-chart-axis">
                {arrivalBars.map((bar) => (
                  <div className="hbar-row" key={bar.key}>
                    <div className="hbar-head"><span className="hbar-label">{bar.time}</span><span className="hbar-value">{fmtDecimal(bar.value)}</span></div>
                    <span className="hbar-track"><span className="hbar-fill" style={{ width: barWidth(bar.value, maxArrival) }} /></span>
                  </div>
                ))}
              </div>
              <div className="table-scroll chart-data-table" role="region" aria-label={arrivalTableName} tabIndex={0}>
                <table>
                  <caption className="sr-only">{arrivalTableName}</caption>
                  <thead><tr><th scope="col">{t('common.time')}</th><th scope="col">{separateScope ? t('current.arrival_rate_combined') : t('current.arrival_rate')}</th>{separateScope && <th scope="col">{t('current.cashier_lines_added')}</th>}</tr></thead>
                  <tbody>{arrivalBars.map((bar) => <tr key={`table-${bar.key}`}><th scope="row">{bar.time}</th><td>{fmtDecimal(bar.value)}</td>{separateScope && <td>{bar.lines}</td>}</tr>)}</tbody>
                </table>
              </div>
            </>
          ) : <ApiState.Empty message={t('current.arrivals_unavailable')} />}
        </section>

        {separateScope ? (
        <section className="card" aria-labelledby="workload-chart-title">
          <h2 id="workload-chart-title" className="section-title">{t('current.workload_title')}</h2>
          {workload.length > 0 ? (
            <>
              <p id="workload-chart-summary" className="chart-summary">{t('current.workload_summary')}</p>
              <ul className="hbar-legend">
                <li><span className="hbar-legend-bar" aria-hidden="true" />{t('current.workload_avg')}</li>
                <li><span className="hbar-legend-marker" aria-hidden="true" />{t('current.workload_peak')}</li>
              </ul>
              <div className="hbar-chart" role="img" aria-labelledby="workload-chart-title" aria-describedby="workload-chart-summary workload-chart-scale">
                {workload.map((cashier) => (
                  <div className="hbar-row" key={cashier.queueId}>
                    <div className="hbar-head"><span className="hbar-label">{cashier.queueId}</span><span className="hbar-value">{t('current.workload_row_values', { avg: fmtPctDecimal(cashier.averageRho), peak: fmtPctDecimal(cashier.peakRho) })}</span></div>
                    <span className="hbar-track">
                      <span className="hbar-fill" style={{ width: barWidth(cashier.averageRho, workloadScale) }} />
                      <span className="hbar-marker" style={{ left: barWidth(cashier.peakRho, workloadScale) }} />
                    </span>
                  </div>
                ))}
              </div>
              <p id="workload-chart-scale" className="hbar-axis-note">{t('current.workload_scale', { max: fmtPctDecimal(workloadScale) })}</p>
              <div className="table-scroll chart-data-table" role="region" aria-label={t('current.workload_table')} tabIndex={0}>
                <table>
                  <caption className="sr-only">{t('current.workload_table')}</caption>
                  <thead><tr><th scope="col">{t('analyses.service_line')}</th><th scope="col">{t('current.workload_avg')}</th><th scope="col">{t('current.workload_peak')}</th><th scope="col">{t('current.workload_peak_time')}</th><th scope="col">{t('current.workload_peak_status')}</th><th scope="col">{t('current.workload_period_count')}</th></tr></thead>
                  <tbody>
                    {workload.map((cashier) => (
                      <tr key={`table-${cashier.queueId}`}>
                        <th scope="row">{cashier.queueId}</th><td>{fmtPctDecimal(cashier.averageRho)}</td><td>{fmtPctDecimal(cashier.peakRho)}</td><td>{cashier.peakTime}</td><td><span className={`status-badge status-${statusKind(cashier.peakStatus)}`}>{shown(cashier.peakStatus)}</span></td><td>{cashier.periodCount}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : <ApiState.Empty message={t('current.workload_unavailable')} />}
        </section>
        ) : (
        <section className="card" aria-labelledby="model-distribution-title">
          <h2 id="model-distribution-title" className="section-title">{t('current.models_title')}</h2>
          <p className="chart-summary">{selected_model ? t('current.selected_model', { model: selected_model }) : t('current.model_unavailable')}</p>
          {modelEntries.length > 0 ? (
            <ul className="model-distribution-list">
              {modelEntries.map(([model, count]) => (
                <li key={model}>
                  <div><strong>{model}</strong><span>{t('current.interval_count', { count })}</span></div>
                  <span className="model-bar-track" aria-hidden="true"><span className="model-bar" style={{ width: `${count / rows.length * 100}%` }} /></span>
                </li>
              ))}
            </ul>
          ) : <ApiState.Empty message={t('current.model_unavailable')} />}
        </section>
        )}
      </div>

      {observedSummary && <ObservedWaitSection summary={observedSummary} />}

      <div className={`alert ${criticalCount > 0 ? 'alert-warn' : 'alert-info'}`} role="status">
        <strong>{criticalCount > 0 ? t('current.pressure_found_title') : t('current.pressure_clear_title')}</strong>{' '}
        {criticalCount > 0 ? t('current.pressure_found', { count: criticalCount }) : t('current.pressure_clear')}
      </div>

      {explanations.length > 0 && (
        <details className="card collapsible-card" aria-labelledby="model-explanation-title">
          <summary><h2 id="model-explanation-title" className="section-title">{t('analyses.model_explanation')}</h2><span className="collapsible-count">{t('filters.showing', { shown: visibleExplanations.length, total: explanations.length })}</span></summary>
          {filter('explanation')}
          {visibleExplanations.length === 0 && <p className="empty-state">{t('filters.no_match')}</p>}
          {visibleExplanations.map((explanation, index) => (
            <details key={`${explanation.time}-${explanation.selected_model}-${typeof explanation.queue_id === 'string' ? explanation.queue_id : ''}-${index}`} className="explanation-block">
              <summary>{explanation.time}{typeof explanation.queue_id === 'string' && explanation.queue_id.trim() !== '' ? ` · ${explanation.queue_id}` : ''}: {explanation.selected_model}</summary>
              <p className="explanation-reason">{explanation.selection_reason}</p>
              {explanation.operational_facts.length > 0 && <div className="explanation-section"><h3>{t('analyses.operational_facts')}</h3><ul>{explanation.operational_facts.map((fact) => <li key={fact}>{fact}</li>)}</ul></div>}
              {explanation.measured_characteristics.length > 0 && <div className="explanation-section"><h3>{t('analyses.measured_characteristics')}</h3><ul>{explanation.measured_characteristics.map((fact) => <li key={fact}>{fact}</li>)}</ul></div>}
              {explanation.model_assumptions.length > 0 && <div className="explanation-section"><h3>{t('analyses.model_assumptions')}</h3><ul>{explanation.model_assumptions.map((fact) => <li key={fact}>{fact}</li>)}</ul></div>}
            </details>
          ))}
        </details>
      )}

      <section className="card" aria-labelledby="current-results-title">
        <h2 id="current-results-title" className="section-title">{t('analyses.detailed_results')}</h2>
        <div className="status-legend" aria-label={t('analyses.status_legend')}>
          <span className="status-legend-title">{t('analyses.status_legend')}</span>
          {['critical', 'peak', 'normal', 'lean'].map((kind) => <span key={kind}><i className={`status-dot status-dot-${kind}`} aria-hidden="true" />{t(`current.status.${kind}`)}</span>)}
        </div>
        {filter('results')}
        <p className="chart-summary" role="status">{t('filters.showing', { shown: visibleRows.length, total: rows.length })}</p>
        {rows.length > 0 && visibleRows.length === 0 ? <p className="empty-state">{t('filters.no_match')}</p> : (
        <div className="table-scroll table-scroll-capped" role="region" aria-labelledby="current-results-title" tabIndex={0}>
          <table>
            <caption className="sr-only">{t('current.results_caption')}</caption>
            <thead><tr><th scope="col">{t('common.time')}</th>{showQueueColumn && <th scope="col">{t('analyses.service_line')}</th>}<th scope="col">λ/h</th><th scope="col">μ/h</th><th scope="col">c</th><th scope="col">{t('analysis.model')}</th><th scope="col">ρ</th><th scope="col">Wq ({t('analyses.minutes')})</th><th scope="col">{t('analyses.status')}</th></tr></thead>
            <tbody>
              {visibleRows.map((row, index) => {
                const rho = finiteValue(row.rho)
                const wq = finiteValue(row.Wq)
                const lambda = finiteValue(row.lambda)
                const mu = finiteValue(row.mu)
                const kind = statusKind(row.status)
                return (
                  <tr key={`${String(row.time ?? index)}-${typeof row.queue_id === 'string' ? row.queue_id : ''}-${index}`} className={kind === 'critical' ? 'row-warning' : undefined}>
                    <th scope="row">{shown(row.time)}</th>{showQueueColumn && <td>{typeof row.queue_id === 'string' && row.queue_id.trim() !== '' ? row.queue_id : t('common.not_available')}</td>}<td>{lambda ?? t('common.not_available')}</td><td>{mu ?? t('common.not_available')}</td><td>{shown(row.c)}</td><td>{shown(row.model)}</td><td>{rho !== null ? fmtPct(rho) : t('common.not_available')}</td><td>{wq !== null ? (wq * 60).toFixed(2) : t('common.not_available')}</td><td><span className={`status-badge status-${kind}`}>{shown(row.status)}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        )}
      </section>
    </div>
  )
}
