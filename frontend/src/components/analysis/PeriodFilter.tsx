import { useTranslation } from 'react-i18next'
import { ALL } from '../../lib/periodFilter'

function distinct(values: unknown[]): string[] {
  const seen: string[] = []
  for (const value of values) {
    if (typeof value === 'string' && value.trim() !== '' && !seen.includes(value)) seen.push(value)
  }
  return seen
}

/** Period / service-line selects that shrink long per-interval lists. Renders nothing when there is only one of each. */
export function PeriodFilter({ idPrefix, periods, lines, period, line, onPeriod, onLine }: {
  idPrefix: string
  periods: unknown[]
  lines: unknown[]
  period: string
  line: string
  onPeriod: (value: string) => void
  onLine: (value: string) => void
}) {
  const { t } = useTranslation()
  const periodOptions = distinct(periods)
  const lineOptions = distinct(lines)
  if (periodOptions.length < 2 && lineOptions.length < 2) return null
  return (
    <div className="period-filter">
      {periodOptions.length > 1 && (
        <div className="form-field">
          <label htmlFor={`${idPrefix}-period`}>{t('common.time')}</label>
          <select id={`${idPrefix}-period`} value={period} onChange={(event) => onPeriod(event.target.value)}>
            <option value={ALL}>{t('filters.all_periods')}</option>
            {periodOptions.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </div>
      )}
      {lineOptions.length > 1 && (
        <div className="form-field">
          <label htmlFor={`${idPrefix}-line`}>{t('analyses.service_line')}</label>
          <select id={`${idPrefix}-line`} value={line} onChange={(event) => onLine(event.target.value)}>
            <option value={ALL}>{t('filters.all_lines')}</option>
            {lineOptions.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </div>
      )}
    </div>
  )
}
