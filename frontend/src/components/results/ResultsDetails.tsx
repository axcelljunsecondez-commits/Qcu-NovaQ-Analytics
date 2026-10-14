import { useTranslation } from 'react-i18next'
import type { ModelExplanation } from '../../api/types'
import { PeriodFilter } from '../analysis/PeriodFilter'
import { fmtDecimal, fmtPctDecimal } from '../../lib/format'
import { ALL, matchesFilter } from '../../lib/periodFilter'
import { busyLevel, cantKeepUp, finiteNumber, levelClass, levelKey, lineOf, minutes, timeOf, type ResultRow } from '../../lib/results'

/** Every period's numbers and the model chosen for it, filtered by the URL's period and line. */
export function ResultsDetails({ rows, explanations, selectedModel, period, line, onPeriod, onLine }: {
  rows: ResultRow[]
  explanations: ModelExplanation[]
  selectedModel: string | null
  period: string
  line: string
  onPeriod: (value: string) => void
  onLine: (value: string) => void
}) {
  const { t } = useTranslation()
  const unavailable = t('results.unavailable')
  const separate = rows.some((row) => lineOf(row) !== null)
  const visible = rows.filter((row) => matchesFilter(row.time, row.queue_id, period, line))
  const visibleExplanations = explanations.filter((item) => matchesFilter(item.time, item.queue_id, period, line))
  const filtered = period !== ALL || line !== ALL
  return (
    <details className="card collapsible-card" open={filtered}>
      <summary><h2 className="section-title" id="results-details-title">{t('results.details')}</h2><span className="collapsible-count">{t('filters.showing', { shown: visible.length, total: rows.length })}</span></summary>
      <PeriodFilter idPrefix="results" periods={rows.map((row) => row.time)} lines={rows.map((row) => row.queue_id)} period={period} line={line} onPeriod={onPeriod} onLine={onLine} />
      {rows.length > 0 && visible.length === 0 ? <p className="empty-state">{t('filters.no_match')}</p> : (
        <div className="table-scroll table-scroll-capped" role="region" aria-labelledby="results-details-title" tabIndex={0}>
          <table>
            <caption className="sr-only">{t('results.details')}</caption>
            <thead>
              <tr>
                <th scope="col">{t('common.time')}</th>
                {separate && <th scope="col">{t('analyses.service_line')}</th>}
                <th scope="col">{t('results.col_arrivals')}</th>
                <th scope="col">{t('results.col_service_rate')}</th>
                <th scope="col">{t('results.col_counters')}</th>
                <th scope="col">{t('analysis.model')}</th>
                <th scope="col">{t('results.col_workload')}</th>
                <th scope="col">{t('results.col_estimated_wait')}</th>
                <th scope="col">{t('results.col_level')}</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row, index) => {
                const level = busyLevel(row)
                const wait = minutes(finiteNumber(row.Wq))
                const number = (value: unknown) => (finiteNumber(value) !== null ? fmtDecimal(finiteNumber(value)) : unavailable)
                return (
                  <tr key={`${timeOf(row)}-${lineOf(row) ?? ''}-${index}`} className={level === 'Unstable' || level === 'Critical' ? 'row-warning' : undefined}>
                    <th scope="row">{timeOf(row) || unavailable}</th>
                    {separate && <td>{lineOf(row) ?? unavailable}</td>}
                    <td>{number(row.lambda)}</td>
                    <td>{number(row.mu)}</td>
                    <td>{finiteNumber(row.c) ?? unavailable}</td>
                    <td>{typeof row.model === 'string' && row.model ? row.model : unavailable}</td>
                    <td>{finiteNumber(row.rho) !== null ? fmtPctDecimal(finiteNumber(row.rho)) : unavailable}</td>
                    <td>{cantKeepUp(row) ? t('results.cant_keep_up_wait') : wait !== null ? `${fmtDecimal(wait, 2)} ${t('results.min')}` : unavailable}</td>
                    <td><span className={`status-badge ${levelClass(level)}`}>{t(levelKey(level))}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      {explanations.length > 0 && (
        <div className="results-models">
          <h3 className="card-title">{t('analyses.model_explanation')}</h3>
          <p className="chart-summary">{selectedModel ? t('current.selected_model', { model: selectedModel }) : t('current.model_unavailable')}</p>
          {visibleExplanations.map((explanation, index) => (
            <details key={`${explanation.time}-${explanation.selected_model}-${typeof explanation.queue_id === 'string' ? explanation.queue_id : ''}-${index}`} className="explanation-block">
              <summary>{explanation.time}{typeof explanation.queue_id === 'string' && explanation.queue_id.trim() !== '' ? ` · ${explanation.queue_id}` : ''}: {explanation.selected_model}</summary>
              <p className="explanation-reason">{explanation.selection_reason}</p>
              {explanation.operational_facts.length > 0 && <div className="explanation-section"><h4>{t('analyses.operational_facts')}</h4><ul>{explanation.operational_facts.map((fact) => <li key={fact}>{fact}</li>)}</ul></div>}
              {explanation.measured_characteristics.length > 0 && <div className="explanation-section"><h4>{t('analyses.measured_characteristics')}</h4><ul>{explanation.measured_characteristics.map((fact) => <li key={fact}>{fact}</li>)}</ul></div>}
              {explanation.model_assumptions.length > 0 && <div className="explanation-section"><h4>{t('analyses.model_assumptions')}</h4><ul>{explanation.model_assumptions.map((fact) => <li key={fact}>{fact}</li>)}</ul></div>}
            </details>
          ))}
        </div>
      )}
    </details>
  )
}
