import { headingText } from '../../lib/headingText'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { PeriodFilter } from '../analysis/PeriodFilter'
import { InfoTip } from '../ui/InfoTip'
import { fmtDecimal, fmtPctDecimal } from '../../lib/format'
import { matchesFilter } from '../../lib/periodFilter'
import { busyLevel, cantKeepUp, dayStrip, finiteNumber, levelClass, levelKey, lineOf, minutes, periodWarnings, timeOf, type ResultRow } from '../../lib/results'

/** Operational fields only. Filtering/formatting reuse the technical reference's helpers. */
export function ResultsSummary({ rows, period, line, onPeriod, onLine, referenceLink, planTarget }: {
  rows: ResultRow[]
  period: string
  line: string
  onPeriod: (value: string) => void
  onLine: (value: string) => void
  referenceLink: ReactNode
  planTarget: number | null
}) {
  const { t } = useTranslation()
  const separate = rows.some((row) => lineOf(row) !== null)
  const visible = rows.filter((row) => matchesFilter(row.time, row.queue_id, period, line))
  const unavailable = t('results.unavailable')
  // Multi-period warnings are already in the Busy Level tab (BusyLevelCard); a single period still needs its target warning.
  const strip = dayStrip(rows)
  const warnings = strip.length === 1 ? periodWarnings(strip, planTarget) : []
  const levels = ['lean', 'normal', 'peak', 'critical', 'unstable']
    .map((level) => `${t(`results.level.${level}`)}: ${t(`results.range.${level}`)}`).join('; ')
  const fields = (row: ResultRow) => {
    const wait = minutes(finiteNumber(row.Wq))
    const level = busyLevel(row)
    return [
      { label: t('results.summary_period'), value: timeOf(row) || unavailable },
      ...(separate ? [{ label: t('analyses.service_line'), value: lineOf(row) ?? unavailable }] : []),
      { label: t('results.summary_counters'), value: finiteNumber(row.c) ?? unavailable },
      { label: t('results.summary_wait'), value: cantKeepUp(row) ? t('results.cant_keep_up_wait') : wait !== null ? `${fmtDecimal(wait, 2)} ${t('results.min')}` : unavailable },
      { label: t('results.col_level'), value: <span className={`status-badge ${levelClass(level)}`}>{t(levelKey(level))}</span> },
    ]
  }
  return (
    <section className="card results-summary" aria-labelledby="results-summary-title">
      <div className="results-section-heading">
        <h2 lang="en" id="results-summary-title" className="section-title">{headingText(t, 'results.operation_by_period')}</h2>
        {referenceLink}
      </div>
      <PeriodFilter idPrefix="results" periods={rows.map((row) => row.time)} lines={rows.map((row) => row.queue_id)} period={period} line={line} onPeriod={onPeriod} onLine={onLine} />
      <p className="form-hint">{t('filters.showing', { shown: visible.length, total: rows.length })}{' '}
        <InfoTip name={t('results.col_level')} text={`${levels}. ${t('results.levels_note')}`} />
      </p>
      {visible.length === 0 ? <p className="empty-state">{t(rows.length > 0 ? 'filters.no_match' : 'results.no_periods')}</p> : (
        <>
          <div className="results-summary-table">
            <table>
              <caption className="sr-only">{t('results.operation_by_period')}</caption>
              <thead><tr>{fields(visible[0]).map((field) => <th key={field.label} scope="col">{field.label}</th>)}</tr></thead>
              <tbody>{visible.map((row, index) => <tr key={`${timeOf(row)}-${lineOf(row) ?? ''}-${index}`}>
                {fields(row).map((field, column) => column === 0 ? <th scope="row" key={field.label}>{field.value}</th> : <td key={field.label}>{field.value}</td>)}
              </tr>)}</tbody>
            </table>
          </div>
          <ul className="results-summary-list" aria-label={t('results.operation_by_period')}>
            {visible.map((row, index) => <li key={`${timeOf(row)}-${lineOf(row) ?? ''}-${index}`}>
              <dl>{fields(row).map((field) => <div key={field.label}><dt>{field.label}</dt><dd>{field.value}</dd></div>)}</dl>
            </li>)}
          </ul>
        </>
      )}
      {warnings.length > 0 && <div className="alert alert-warn" role="status">{warnings.map((warning) => <p key={warning.time}>
        <strong>{warning.time}</strong>: {t(levelKey(warning.level))}
        {warning.level !== null && ` (${t(`results.range.${warning.level.toLowerCase()}`)})`}
        {warning.aboveTarget && planTarget !== null && ` · ${t('results.above_plan_target', { target: fmtPctDecimal(planTarget) })}`}
      </p>)}</div>}
    </section>
  )
}
