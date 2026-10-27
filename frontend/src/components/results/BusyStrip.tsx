import { headingText } from '../../lib/headingText'
import { useTranslation } from 'react-i18next'
import type { UtilizationBand } from '../../lib/utilization'
import { fmtDecimal, fmtPctDecimal } from '../../lib/format'
import {
  busyLevel, cantKeepUp, dayStrip, finiteNumber, levelClass, levelKey, lineOf, minutes, periodWarnings, timeOf,
  type ResultRow,
} from '../../lib/results'

const LEVELS: UtilizationBand[] = ['Lean', 'Normal', 'Peak', 'Critical', 'Unstable']

/** NovaQ's fixed busy levels per period (spec §7.7, D19); clicking a period shows its numbers. */
export function BusyStrip({ rows, planTarget, period, onPeriod, showNumbers = true }: {
  rows: ResultRow[]
  /** The selected plan's target utilization; null when no plan is selected. */
  planTarget: number | null
  period: string | null
  onPeriod: (time: string | null) => void
  /** Results already shows these rows in its operational summary. Other consumers retain their table. */
  showNumbers?: boolean
}) {
  const { t } = useTranslation()
  const strip = dayStrip(rows)
  const warnings = periodWarnings(strip, planTarget)
  const chosen = period !== null ? rows.filter((row) => timeOf(row) === period) : []
  const separate = rows.some((row) => lineOf(row) !== null)
  const unavailable = t('results.unavailable')
  if (strip.length === 0) return null
  return (
    <section className="card" aria-labelledby="busy-strip-title">
      <h2 lang="en" id="busy-strip-title" className="section-title">{headingText(t, 'results.day_by_level')}</h2>
      <div className="busy-strip" role="group" aria-label={t('results.day_by_level')}>
        {strip.map((cell) => (
          <button
            key={cell.time}
            type="button"
            className={`busy-cell ${levelClass(cell.level)}`}
            aria-pressed={period === cell.time}
            aria-label={`${cell.time}: ${t(levelKey(cell.level))}`}
            onClick={() => onPeriod(period === cell.time ? null : cell.time)}
          >
            <span className="busy-cell-time">{cell.time}</span>
          </button>
        ))}
      </div>
      <ul className="busy-legend">
        {LEVELS.map((level) => (
          <li key={level}><i className={`busy-swatch ${levelClass(level)}`} aria-hidden="true" />{t(levelKey(level))} <span className="form-hint">{t(`results.range.${level.toLowerCase()}`)}</span></li>
        ))}
      </ul>
      <p className="form-hint">{t('results.click_period')} {t('results.levels_note')}{separate ? ` ${t('results.strip_separate_note')}` : ''}</p>

      {warnings.length > 0 && (
        <div className="alert alert-warn" role="status">
          <ul className="busy-warnings">
            {warnings.map((warning) => (
              <li key={warning.time}>
                <strong>{warning.time}</strong>: {t(levelKey(warning.level))}
                {warning.level !== null && ` (${t(`results.range.${warning.level.toLowerCase()}`)})`}
                {warning.aboveTarget && planTarget !== null && ` · ${t('results.above_plan_target', { target: fmtPctDecimal(planTarget) })}`}
              </li>
            ))}
          </ul>
        </div>
      )}

      {showNumbers && period !== null && chosen.length > 0 && (
        <div className="busy-period" aria-live="polite">
          <h3 lang="en" className="card-title">{headingText(t, 'results.period_numbers', { period })}</h3>
          <div className="table-scroll" role="region" aria-label={t('results.period_numbers', { period })} tabIndex={0}>
            <table>
              <thead>
                <tr>
                  {separate && <th scope="col">{t('analyses.service_line')}</th>}
                  <th scope="col">{t('results.col_counters')}</th>
                  <th scope="col">{t('results.col_arrivals')}</th>
                  <th scope="col">{t('results.col_estimated_wait')}</th>
                  <th scope="col">{t('results.col_workload')}</th>
                  <th scope="col">{t('results.col_level')}</th>
                </tr>
              </thead>
              <tbody>
                {chosen.map((row, index) => {
                  const wait = minutes(finiteNumber(row.Wq))
                  const rho = finiteNumber(row.rho)
                  const level = busyLevel(row)
                  return (
                    <tr key={`${lineOf(row) ?? ''}-${index}`}>
                      {separate && <th scope="row">{lineOf(row) ?? unavailable}</th>}
                      <td>{finiteNumber(row.c) ?? unavailable}</td>
                      <td>{finiteNumber(row.lambda) !== null ? fmtDecimal(finiteNumber(row.lambda)) : unavailable}</td>
                      <td>{cantKeepUp(row) ? t('results.cant_keep_up_wait') : wait !== null ? `${fmtDecimal(wait, 1)} ${t('results.min')}` : unavailable}</td>
                      <td>{rho !== null ? fmtPctDecimal(rho) : unavailable}</td>
                      <td><span className={`status-badge ${levelClass(level)}`}>{t(levelKey(level))}</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}
