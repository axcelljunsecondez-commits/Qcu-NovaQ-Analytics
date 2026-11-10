import { headingText } from '../../lib/headingText'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { PeriodArrivals } from '../../api/types'
import { Pagination } from '../ui/Pagination'
import { PeriodFilter } from '../analysis/PeriodFilter'
import { InfoTip } from '../ui/InfoTip'
import { fmtDecimal, fmtPctDecimal } from '../../lib/format'
import { ALL, matchesFilter } from '../../lib/periodFilter'
import { busyLevel, cantKeepUp, finiteNumber, levelClass, levelKey, lineOf, minutes, timeOf, type ResultRow } from '../../lib/results'

const ACTION_LEVELS = ['Unstable', 'Critical', 'Peak']
const PAGE_SIZE = 5

/** Operational follow-up, using the same workload bands as the technical reference. */
export function ResultsSummary({ rows, arrivalsByPeriod = [], arrivalRecords, period, line, onPeriod, onLine, referenceLink }: {
  rows: ResultRow[]
  arrivalsByPeriod?: PeriodArrivals[]
  arrivalRecords?: Record<string, unknown>[] | null
  period: string
  line: string
  onPeriod: (value: string) => void
  onLine: (value: string) => void
  referenceLink: ReactNode
}) {
  const { t } = useTranslation()
  const separate = rows.some((row) => lineOf(row) !== null)
  const [paging, setPaging] = useState({ period, line, page: 0 })
  const matching = rows.filter((row) => matchesFilter(row.time, row.queue_id, period, line))
    .map((row) => ({ row, level: busyLevel(row) }))
  const attention = matching.filter(({ level }) => level !== null && ACTION_LEVELS.includes(level))
    .sort((a, b) => ACTION_LEVELS.indexOf(a.level ?? '') - ACTION_LEVELS.indexOf(b.level ?? '')
      || (finiteNumber(b.row.rho) ?? 0) - (finiteNumber(a.row.rho) ?? 0))
  const pageCount = Math.ceil(attention.length / PAGE_SIZE)
  const page = paging.period === period && paging.line === line ? Math.max(0, Math.min(paging.page, pageCount - 1)) : 0
  const visible = attention.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map(({ row }) => row)
  let demand = arrivalsByPeriod
  if (attention.length === 0 && line !== ALL) {
    const rates = new Map<string, number | null>()
    for (const row of arrivalRecords ?? []) {
      if (lineOf(row)?.trim() !== line) continue
      const time = timeOf({ time: row.time ?? row.segment_id })
      // A duplicate cannot establish one arrival rate for this cashier and period.
      if (time) rates.set(time, rates.has(time) ? null : finiteNumber(row.lambda))
    }
    demand = Array.from(rates, ([time, arrivals_per_hour]) => ({ time, arrivals_per_hour }))
  }
  const busiest = attention.length > 0 ? [] : demand
    .filter(({ time }) => period === ALL || time === period)
    .flatMap(({ time, arrivals_per_hour }) => {
      const rate = finiteNumber(arrivals_per_hour)
      return time && rate !== null && rate > 0 ? [{ time, rate }] : []
    })
    .sort((a, b) => b.rate - a.rate)
    .slice(0, PAGE_SIZE)
  const unavailable = t('results.unavailable')
  const emptyKey = matching.length === 0 && busiest.length > 0 ? 'results.workload_incomplete'
    : rows.length === 0 ? 'results.no_periods'
    : matching.length === 0 ? 'filters.no_match'
      : matching.some(({ level }) => level === null) ? 'results.workload_incomplete' : 'results.no_workload_attention'
  const levels = ['lean', 'normal', 'peak', 'critical', 'unstable']
    .map((level) => `${t(`results.level.${level}`)}: ${t(`results.range.${level}`)}`).join('; ')
  const workloadInfo = <InfoTip name={t('results.col_level')} text={`${levels}. ${t('results.levels_note')}`} />
  const fields = (row: ResultRow) => {
    const wait = minutes(finiteNumber(row.Wq))
    const level = busyLevel(row)
    return [
      { label: t('results.summary_period'), value: timeOf(row) || unavailable },
      ...(separate ? [{ label: t('analyses.service_line'), value: lineOf(row) ?? unavailable }] : []),
      { label: t('results.summary_counters'), value: finiteNumber(row.c) ?? unavailable },
      { label: t('results.summary_wait'), value: cantKeepUp(row) ? t('results.cant_keep_up_wait') : wait !== null ? `${fmtDecimal(wait, 2)} ${t('results.min')}` : unavailable },
      { label: t('results.col_level'), value: <span className={`status-badge ${levelClass(level)}`}>{t(levelKey(level))} · {fmtPctDecimal(finiteNumber(row.rho))}</span> },
    ]
  }
  return (
    <section className="card results-summary" aria-labelledby="results-summary-title">
      <div className="results-section-heading">
        <h2 lang="en" id="results-summary-title" className="section-title">{headingText(t, 'results.operation_by_period')}</h2>
        {referenceLink}
      </div>
      <PeriodFilter idPrefix="results" periods={[...rows.map((row) => row.time), ...arrivalsByPeriod.map(({ time }) => time)]} lines={rows.map((row) => row.queue_id)} period={period} line={line} onPeriod={onPeriod} onLine={onLine} />
      {visible.length === 0 ? (
        <>
          <p className={busiest.length > 0 ? 'form-hint' : 'empty-state'}>{t(emptyKey)}{' '}{workloadInfo}</p>
          {busiest.length > 0 && (
            <div>
              <h3 lang="en" id="results-peak-arrivals-title" className="card-title">{headingText(t, 'results.peak_arrival_periods')}</h3>
              <ol aria-labelledby="results-peak-arrivals-title">
                {busiest.map(({ time, rate }) => (
                  <li key={time}><strong>{time}</strong>{' · '}{t('results.customers_per_hour', { count: rate, value: fmtDecimal(rate) })}</li>
                ))}
              </ol>
            </div>
          )}
        </>
      ) : (
        <>
          <p className="form-hint">{t('filters.showing', { shown: visible.length, total: attention.length })}{' '}{workloadInfo}</p>
          <div key={'table-' + page} className="results-summary-table results-page-transition">
            <table>
              <caption className="sr-only">{t('results.operation_by_period')}</caption>
              <thead><tr>{fields(visible[0]).map((field) => <th key={field.label} scope="col">{field.label}</th>)}</tr></thead>
              <tbody>{visible.map((row, index) => <tr key={`${timeOf(row)}-${lineOf(row) ?? ''}-${index}`}>
                {fields(row).map((field, column) => column === 0 ? <th scope="row" key={field.label}>{field.value}</th> : <td key={field.label}>{field.value}</td>)}
              </tr>)}</tbody>
            </table>
          </div>
          <ul key={'list-' + page} className="results-summary-list results-page-transition" aria-label={t('results.operation_by_period')}>
            {visible.map((row, index) => <li key={`${timeOf(row)}-${lineOf(row) ?? ''}-${index}`}>
              <dl>{fields(row).map((field) => <div key={field.label}><dt>{field.label}</dt><dd>{field.value}</dd></div>)}</dl>
            </li>)}
          </ul>
        </>
      )}
      <Pagination page={page} pageCount={pageCount} onPageChange={(next) => setPaging({ period, line, page: next })} />
    </section>
  )
}
