import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

/** B13: choose which date of a per-date run the charts and the replay show; kept in the address. */
export function DatePicker({ dates, date }: { dates: string[]; date: string | null }) {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  if (dates.length <= 1) return null
  return (
    <div className="form-field inline-field">
      <label htmlFor="run-date">{t('simulation.run_date')}</label>
      <select id="run-date" value={date ?? dates[0]} onChange={(event) => {
        const next = new URLSearchParams(params)
        next.set('date', event.target.value)
        next.delete('t')
        setParams(next, { replace: true })
      }}>
        {dates.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
    </div>
  )
}
