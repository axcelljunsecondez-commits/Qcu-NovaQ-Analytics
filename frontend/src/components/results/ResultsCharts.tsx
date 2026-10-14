import { useTranslation } from 'react-i18next'
import type { ObservedWaitPeriod, PeriodArrivals } from '../../api/types'
import { summarizeCashierWorkload } from '../../lib/cashierWorkload'
import { fmtDecimal, fmtPctDecimal } from '../../lib/format'
import { finiteNumber, lineOf, minutes, timeOf, type ResultRow } from '../../lib/results'

function width(value: number | null, max: number): string {
  return value !== null && max > 0 ? `${Math.max(0, value) / max * 100}%` : '0%'
}

/** Customers per hour by period, every line summed on the server (B12). */
export function ArrivalsChart({ periods }: { periods: PeriodArrivals[] | undefined }) {
  const { t } = useTranslation()
  const unavailable = t('results.unavailable')
  const values = (periods ?? []).map((period) => ({ time: period.time, value: finiteNumber(period.arrivals_per_hour) }))
  const max = Math.max(0, ...values.map((item) => item.value ?? 0))
  return (
    <section className="card" aria-labelledby="results-arrivals-title">
      <h2 id="results-arrivals-title" className="section-title">{t('results.arrivals_chart')}</h2>
      <p className="key-result-source">{t('results.source_data')}</p>
      {values.length === 0 ? <p className="empty-state">{t('results.arrivals_unavailable')}</p> : (
        <>
          <div className="hbar-chart" role="img" aria-labelledby="results-arrivals-title">
            {values.map((item) => (
              <div className="hbar-row" key={item.time}>
                <div className="hbar-head"><span className="hbar-label">{item.time}</span><span className="hbar-value">{item.value !== null ? fmtDecimal(item.value) : unavailable}</span></div>
                <span className="hbar-track"><span className="hbar-fill" style={{ width: width(item.value, max) }} /></span>
              </div>
            ))}
          </div>
          <div className="table-scroll chart-data-table" role="region" aria-label={t('results.arrivals_table')} tabIndex={0}>
            <table>
              <caption className="sr-only">{t('results.arrivals_table')}</caption>
              <thead><tr><th scope="col">{t('common.time')}</th><th scope="col">{t('results.col_arrivals')}</th></tr></thead>
              <tbody>{values.map((item) => <tr key={item.time}><th scope="row">{item.time}</th><td>{item.value !== null ? fmtDecimal(item.value) : unavailable}</td></tr>)}</tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}

/** Recorded vs estimated wait by period (customer-record uploads only). */
export function WaitByPeriodChart({ periods }: { periods: ObservedWaitPeriod[] }) {
  const { t } = useTranslation()
  const unavailable = t('results.unavailable')
  const unit = t('results.min')
  const items = periods.map((period) => ({ time: period.time, recorded: minutes(period.observed_wait), estimated: minutes(period.modeled_wait), flagged: period.flagged }))
  const max = Math.max(0, ...items.flatMap((item) => [item.recorded ?? 0, item.estimated ?? 0]))
  const text = (value: number | null) => (value !== null ? `${fmtDecimal(value, 1)} ${unit}` : unavailable)
  return (
    <section className="card" aria-labelledby="results-wait-title">
      <h2 id="results-wait-title" className="section-title">{t('results.wait_chart')}</h2>
      <ul className="hbar-legend">
        <li><span className="hbar-legend-bar" aria-hidden="true" />{t('results.recorded')}</li>
        <li><span className="hbar-legend-bar hbar-legend-alt" aria-hidden="true" />{t('results.estimated')}</li>
      </ul>
      <div className="hbar-chart" role="img" aria-labelledby="results-wait-title">
        {items.map((item) => (
          <div className="hbar-row" key={item.time}>
            <div className="hbar-head"><span className="hbar-label">{item.time}</span><span className="hbar-value">{text(item.recorded)} · {text(item.estimated)}</span></div>
            <span className="hbar-track"><span className="hbar-fill" style={{ width: width(item.recorded, max) }} /></span>
            <span className="hbar-track"><span className="hbar-fill hbar-fill-alt" style={{ width: width(item.estimated, max) }} /></span>
          </div>
        ))}
      </div>
      <div className="table-scroll chart-data-table" role="region" aria-label={t('results.wait_table')} tabIndex={0}>
        <table>
          <caption className="sr-only">{t('results.wait_table')}</caption>
          <thead><tr><th scope="col">{t('common.time')}</th><th scope="col">{t('results.recorded')}</th><th scope="col">{t('results.estimated')}</th><th scope="col">{t('analyses.status')}</th></tr></thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.time} className={item.flagged ? 'row-warning' : undefined}>
                <th scope="row">{item.time}</th><td>{text(item.recorded)}</td><td>{text(item.estimated)}</td>
                <td>{item.flagged ? <span className="status-badge status-critical">{t('current.observed_flagged')}</span> : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

/** Estimated cashier-line workload (separate lines only; not a performance score). */
export function WorkloadChart({ rows, separate }: { rows: ResultRow[]; separate: boolean }) {
  const { t } = useTranslation()
  if (!separate) {
    return (
      <section className="card" aria-labelledby="results-workload-title">
        <h2 id="results-workload-title" className="section-title">{t('results.workload_chart')}</h2>
        <p className="chart-summary">{t('results.workload_shared')}</p>
      </section>
    )
  }
  const workload = summarizeCashierWorkload(rows.map((row) => ({ queueId: lineOf(row), rho: finiteNumber(row.rho), time: timeOf(row), status: row.status })))
  const scale = Math.max(1, ...workload.map((cashier) => cashier.peakRho))
  return (
    <section className="card" aria-labelledby="results-workload-title">
      <h2 id="results-workload-title" className="section-title">{t('results.workload_chart')}</h2>
      <p className="key-result-source">{t('results.source_estimate')} · {t('results.not_performance_score')}</p>
      {workload.length === 0 ? <p className="empty-state">{t('current.workload_unavailable')}</p> : (
        <>
          <ul className="hbar-legend">
            <li><span className="hbar-legend-bar" aria-hidden="true" />{t('current.workload_avg')}</li>
            <li><span className="hbar-legend-marker" aria-hidden="true" />{t('current.workload_peak')}</li>
          </ul>
          <div className="hbar-chart" role="img" aria-labelledby="results-workload-title">
            {workload.map((cashier) => (
              <div className="hbar-row" key={cashier.queueId}>
                <div className="hbar-head"><span className="hbar-label">{cashier.queueId}</span><span className="hbar-value">{t('current.workload_row_values', { avg: fmtPctDecimal(cashier.averageRho), peak: fmtPctDecimal(cashier.peakRho) })}</span></div>
                <span className="hbar-track">
                  <span className="hbar-fill" style={{ width: width(cashier.averageRho, scale) }} />
                  <span className="hbar-marker" style={{ left: width(cashier.peakRho, scale) }} />
                </span>
              </div>
            ))}
          </div>
          <div className="table-scroll chart-data-table" role="region" aria-label={t('current.workload_table')} tabIndex={0}>
            <table>
              <caption className="sr-only">{t('current.workload_table')}</caption>
              <thead><tr><th scope="col">{t('analyses.service_line')}</th><th scope="col">{t('current.workload_avg')}</th><th scope="col">{t('current.workload_peak')}</th><th scope="col">{t('current.workload_peak_time')}</th></tr></thead>
              <tbody>{workload.map((cashier) => <tr key={cashier.queueId}><th scope="row">{cashier.queueId}</th><td>{fmtPctDecimal(cashier.averageRho)}</td><td>{fmtPctDecimal(cashier.peakRho)}</td><td>{cashier.peakTime}</td></tr>)}</tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
