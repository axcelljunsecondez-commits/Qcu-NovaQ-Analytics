import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { buildAggregateCsv, makePeriods, MANUAL_ENTRY_DATASET_NAME, MANUAL_ENTRY_FILE_NAME, manualRowError, MAX_PERIODS, type ManualRow } from '../../lib/periods'

interface ManualEntryProps {
  disabled: boolean
  onUpload: (file: File) => void
}

// B9 (spec §7.6): numbers typed here become the same aggregate CSV the template
// produces, uploaded through the existing upload path. Shared lines only; one-hour periods.
export function ManualEntry({ disabled, onUpload }: ManualEntryProps) {
  const { t } = useTranslation()
  const [firstStart, setFirstStart] = useState('08:00')
  const [hours, setHours] = useState('4')
  const [rows, setRows] = useState<ManualRow[]>([])
  const [error, setError] = useState<string | null>(null)

  function makeRows() {
    const periods = makePeriods(firstStart, Number(hours), 60)
    if (typeof periods === 'string') {
      setError(t(`setup.periods_error_${periods}`, { max: MAX_PERIODS }))
      return
    }
    setError(null)
    setRows(periods.map((period, index) => rows[index] ? { ...rows[index], start: period.start } : { start: period.start, arrivalsPerHour: '', servedPerHourPerCounter: '', counters: '' }))
  }

  function update(index: number, change: Partial<ManualRow>) {
    setRows((old) => old.map((row, rowIndex) => rowIndex === index ? { ...row, ...change } : row))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    const bad = rows.findIndex((row) => manualRowError(row) !== null)
    if (bad >= 0) {
      setError(t(`setup.manual_error_${manualRowError(rows[bad])}`, { row: bad + 1 }))
      return
    }
    setError(null)
    onUpload(new File([buildAggregateCsv(rows)], MANUAL_ENTRY_FILE_NAME, { type: 'text/csv' }))
  }

  return (
    <details className="setup-manual">
      <summary>{t('setup.manual_summary')}</summary>
      <p className="page-caption">{t('setup.manual_help')}</p>
      <div className="form-row">
        <div className="form-field"><label htmlFor="manual-first-start">{t('setup.manual_first_start')}</label><input id="manual-first-start" type="time" step="900" value={firstStart} onChange={(e) => setFirstStart(e.target.value)} /></div>
        <div className="form-field"><label htmlFor="manual-hours">{t('setup.manual_hours')}</label><input id="manual-hours" type="number" min="1" max={MAX_PERIODS} value={hours} onChange={(e) => setHours(e.target.value)} /></div>
        <button type="button" className="btn-ghost" onClick={makeRows}>{t('setup.manual_make_rows')}</button>
      </div>
      {rows.length > 0 && (
        <form onSubmit={submit}>
          <div className="table-scroll" role="region" aria-label={t('setup.manual_table')} tabIndex={0}>
            <table>
              <caption className="sr-only">{t('setup.manual_table')}</caption>
              <thead><tr><th scope="col">{t('setup.manual_period')}</th><th scope="col">{t('setup.manual_arrivals')}</th><th scope="col">{t('setup.manual_served')}</th><th scope="col">{t('setup.manual_counters')}</th></tr></thead>
              <tbody>
                {rows.map((row, index) => {
                  const end = makePeriods(row.start, 1, 60)
                  const label = typeof end === 'string' ? row.start : `${end[0].start}–${end[0].end}`
                  return (
                    <tr key={row.start}>
                      <th scope="row">{label}</th>
                      <td><input aria-label={t('setup.manual_arrivals_for', { period: label })} type="number" min="0" step="any" value={row.arrivalsPerHour} onChange={(e) => update(index, { arrivalsPerHour: e.target.value })} /></td>
                      <td><input aria-label={t('setup.manual_served_for', { period: label })} type="number" min="0" step="any" value={row.servedPerHourPerCounter} onChange={(e) => update(index, { servedPerHourPerCounter: e.target.value })} /></td>
                      <td><input aria-label={t('setup.manual_counters_for', { period: label })} type="number" min="1" step="1" value={row.counters} onChange={(e) => update(index, { counters: e.target.value })} /></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="form-hint">{t('setup.manual_saved_as', { name: MANUAL_ENTRY_DATASET_NAME })}</p>
          <button type="submit" disabled={disabled}>{t('setup.manual_upload')}</button>
        </form>
      )}
      {error && <div className="alert alert-error" role="alert">{error}</div>}
    </details>
  )
}
