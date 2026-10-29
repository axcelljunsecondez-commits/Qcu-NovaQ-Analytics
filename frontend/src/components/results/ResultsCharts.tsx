import { headingText } from '../../lib/headingText'
import { useTranslation } from 'react-i18next'
import type { PeriodArrivals } from '../../api/types'
import { summarizeCashierWorkload } from '../../lib/cashierWorkload'
import { fmtDecimal, fmtPctDecimal } from '../../lib/format'
import { finiteNumber, lineOf, timeOf, type ResultRow } from '../../lib/results'

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
      <h2 lang="en" id="results-arrivals-title" className="section-title">{headingText(t, 'results.arrivals_chart')}</h2>
      <p className="key-result-source">{t('results.source_data')}</p>
      {values.length === 0 ? <p className="empty-state">{t('results.arrivals_unavailable')}</p> : (
          <ul className="hbar-chart results-chart-list" aria-labelledby="results-arrivals-title">
            {values.map((item) => (
              <li className="hbar-row" key={item.time}>
                <div className="hbar-head"><span className="hbar-label">{item.time}</span><span className="hbar-value">{item.value !== null ? t('results.customers_per_hour', { count: item.value, value: fmtDecimal(item.value) }) : unavailable}</span></div>
                <span className="hbar-track" aria-hidden="true"><span className="hbar-fill" style={{ width: width(item.value, max) }} /></span>
              </li>
            ))}
          </ul>
      )}
    </section>
  )
}

/** Estimated cashier-line workload (separate lines only; not a performance score). */
export function WorkloadChart({ rows, separate }: { rows: ResultRow[]; separate: boolean }) {
  const { t } = useTranslation()
  if (!separate) {
    return (
      <section className="card" aria-labelledby="results-workload-title">
        <h2 lang="en" id="results-workload-title" className="section-title">{headingText(t, 'results.workload_chart')}</h2>
        <p className="chart-summary">{t('results.workload_shared')}</p>
      </section>
    )
  }
  const workload = summarizeCashierWorkload(rows.map((row) => ({ queueId: lineOf(row), rho: finiteNumber(row.rho), time: timeOf(row), status: row.status })))
  const scale = Math.max(1, ...workload.map((cashier) => cashier.peakRho))
  return (
    <section className="card" aria-labelledby="results-workload-title">
      <h2 lang="en" id="results-workload-title" className="section-title">{headingText(t, 'results.workload_chart')}</h2>
      <p className="key-result-source">{t('results.source_estimate')} · {t('results.not_performance_score')}</p>
      {workload.length === 0 ? <p className="empty-state">{t('current.workload_unavailable')}</p> : (
        <>
          <ul className="hbar-legend">
            <li><span className="hbar-legend-bar" aria-hidden="true" />{t('current.workload_avg')}</li>
            <li><span className="hbar-legend-marker" aria-hidden="true" />{t('current.workload_peak')}</li>
          </ul>
          <ul className="hbar-chart results-chart-list" aria-labelledby="results-workload-title">
            {workload.map((cashier) => (
              <li className="hbar-row" key={cashier.queueId}>
                <div className="hbar-head"><span className="hbar-label">{cashier.queueId}</span><span className="hbar-value">{t('current.workload_row_values', { avg: fmtPctDecimal(cashier.averageRho), peak: fmtPctDecimal(cashier.peakRho) })}</span></div>
                <p className="form-hint">{t('current.workload_peak_time')}: {cashier.peakTime}</p>
                <span className="hbar-track" aria-hidden="true">
                  <span className="hbar-fill" style={{ width: width(cashier.averageRho, scale) }} />
                  <span className="hbar-marker" style={{ left: width(cashier.peakRho, scale) }} />
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
