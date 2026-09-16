import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { getAnalysisCurrent, listAnalysisDatasets } from '../api/analyses'
import { ApiState } from '../components/ui/ApiState'
import { fmtPct } from '../lib/format'
import { groupPeriodDemand, pickLeanPeriod, pickPeakPeriod } from '../lib/periodDemand'

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

export function AnalysisCurrentPage() {
  const { t } = useTranslation()
  const id = Number(useParams().analysisId)
  const datasets = useQuery({ queryKey: ['datasets', id], queryFn: () => listAnalysisDatasets(id) })
  const datasetId = datasets.data?.datasets[0]?.id
  const query = useQuery({ queryKey: ['current', id, datasetId], queryFn: () => getAnalysisCurrent(id), enabled: Boolean(datasetId), retry: false })

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
  const maxArrival = arrivalPoints.length > 0 ? Math.max(...arrivalPoints.map((point) => point.value)) : null
  // Separate scope: compare combined arrival rates per period; shared scope
  // keeps the long-standing single-row extremum so shared results are byte-identical.
  const separateScope = rows.length > 0 && rows.every((row) => row.queue_structure === 'separate_queues')
  const periodDemands = separateScope ? groupPeriodDemand(arrivalPoints) : []
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
            <div><div className="kpi-label">{t('analyses.avg_wq')}</div><div className="kpi-value state-current">{avgWq !== null ? `${(avgWq * 60).toFixed(1)} ${t('analyses.minutes')}` : t('common.not_available')}</div></div>
            <div><div className="kpi-label">{t('analyses.max_wq')}</div><div className="kpi-value state-current">{maxWq !== null ? `${(maxWq * 60).toFixed(1)} ${t('analyses.minutes')}` : t('common.not_available')}</div></div>
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
            {arrivalPoints.length > 0 ? t('current.arrivals_summary', { count: arrivalPoints.length }) : t('current.arrivals_unavailable')}
          </p>
          {arrivalPoints.length > 0 ? (
            <>
              <figure className="arrival-figure" aria-labelledby="arrival-chart-title" aria-describedby="arrival-chart-summary">
                <div className="arrival-bars" role="img">
                  {arrivalPoints.map((point) => (
                    <div className="arrival-bar-item" key={`${point.time}-${point.index}`}>
                      <span className="arrival-value">{point.value}</span>
                      <span className="arrival-bar-track"><span className="arrival-bar" style={{ height: maxArrival && maxArrival > 0 ? `${point.value / maxArrival * 100}%` : '0%' }} /></span>
                      <span className="arrival-label">{point.time}</span>
                    </div>
                  ))}
                </div>
              </figure>
              <div className="table-scroll chart-data-table" role="region" aria-label={t('current.arrivals_table')} tabIndex={0}>
                <table><caption className="sr-only">{t('current.arrivals_table')}</caption><thead><tr><th scope="col">{t('common.time')}</th><th scope="col">{t('current.arrival_rate')}</th></tr></thead><tbody>{arrivalPoints.map((point) => <tr key={`table-${point.time}-${point.index}`}><th scope="row">{point.time}</th><td>{point.value}</td></tr>)}</tbody></table>
              </div>
            </>
          ) : <ApiState.Empty message={t('current.arrivals_unavailable')} />}
        </section>

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
      </div>

      <div className={`alert ${criticalCount > 0 ? 'alert-warn' : 'alert-info'}`} role="status">
        <strong>{criticalCount > 0 ? t('current.pressure_found_title') : t('current.pressure_clear_title')}</strong>{' '}
        {criticalCount > 0 ? t('current.pressure_found', { count: criticalCount }) : t('current.pressure_clear')}
      </div>

      {explanations.length > 0 && (
        <section className="card" aria-labelledby="model-explanation-title">
          <h2 id="model-explanation-title" className="section-title">{t('analyses.model_explanation')}</h2>
          {explanations.map((explanation, index) => (
            <details key={`${explanation.time}-${explanation.selected_model}-${typeof explanation.queue_id === 'string' ? explanation.queue_id : ''}-${index}`} className="explanation-block">
              <summary>{explanation.time}{typeof explanation.queue_id === 'string' && explanation.queue_id.trim() !== '' ? ` · ${explanation.queue_id}` : ''}: {explanation.selected_model}</summary>
              <p className="explanation-reason">{explanation.selection_reason}</p>
              {explanation.operational_facts.length > 0 && <div className="explanation-section"><h3>{t('analyses.operational_facts')}</h3><ul>{explanation.operational_facts.map((fact) => <li key={fact}>{fact}</li>)}</ul></div>}
              {explanation.measured_characteristics.length > 0 && <div className="explanation-section"><h3>{t('analyses.measured_characteristics')}</h3><ul>{explanation.measured_characteristics.map((fact) => <li key={fact}>{fact}</li>)}</ul></div>}
              {explanation.model_assumptions.length > 0 && <div className="explanation-section"><h3>{t('analyses.model_assumptions')}</h3><ul>{explanation.model_assumptions.map((fact) => <li key={fact}>{fact}</li>)}</ul></div>}
            </details>
          ))}
        </section>
      )}

      <section className="card" aria-labelledby="current-results-title">
        <h2 id="current-results-title" className="section-title">{t('analyses.detailed_results')}</h2>
        <div className="status-legend" aria-label={t('analyses.status_legend')}>
          <span className="status-legend-title">{t('analyses.status_legend')}</span>
          {['critical', 'peak', 'normal', 'lean'].map((kind) => <span key={kind}><i className={`status-dot status-dot-${kind}`} aria-hidden="true" />{t(`current.status.${kind}`)}</span>)}
        </div>
        <div className="table-scroll" role="region" aria-labelledby="current-results-title" tabIndex={0}>
          <table>
            <caption className="sr-only">{t('current.results_caption')}</caption>
            <thead><tr><th scope="col">{t('common.time')}</th>{showQueueColumn && <th scope="col">{t('analyses.service_line')}</th>}<th scope="col">λ/h</th><th scope="col">μ/h</th><th scope="col">c</th><th scope="col">{t('analysis.model')}</th><th scope="col">ρ</th><th scope="col">Wq ({t('analyses.minutes')})</th><th scope="col">{t('analyses.status')}</th></tr></thead>
            <tbody>
              {rows.map((row, index) => {
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
      </section>
    </div>
  )
}
