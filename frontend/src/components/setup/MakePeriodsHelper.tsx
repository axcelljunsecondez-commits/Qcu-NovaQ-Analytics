import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { headingText } from '../../lib/headingText'
import { makePeriods, MAX_PERIODS, PERIOD_LENGTHS, type Period } from '../../lib/periods'

interface MakePeriodsHelperProps {
  hasSegments: boolean
  onMake: (periods: Period[]) => void
}

// Writes time segments only (separate lines); the user still saves the Setup.
export function MakePeriodsHelper({ hasSegments, onMake }: MakePeriodsHelperProps) {
  const { t } = useTranslation()
  const [start, setStart] = useState('08:00')
  const [count, setCount] = useState('8')
  const [length, setLength] = useState('60')
  const [error, setError] = useState<string | null>(null)

  function make() {
    const periods = makePeriods(start, Number(count), Number(length))
    if (typeof periods === 'string') {
      setError(t(`setup.periods_error_${periods}`, { max: MAX_PERIODS }))
      return
    }
    setError(null)
    onMake(periods)
  }

  return (
    <fieldset className="form-field setup-make-periods">
      <legend lang="en">{headingText(t, 'setup.make_periods_title')}</legend>
      <p className="page-caption">{t('setup.make_periods_help')}</p>
      <div className="form-row">
        <div className="form-field"><label htmlFor="make-periods-start">{t('setup.make_periods_start')}</label><input id="make-periods-start" type="time" step="900" value={start} onChange={(e) => setStart(e.target.value)} /></div>
        <div className="form-field"><label htmlFor="make-periods-count">{t('setup.make_periods_count')}</label><input id="make-periods-count" type="number" min="1" max={MAX_PERIODS} value={count} onChange={(e) => setCount(e.target.value)} /></div>
        <div className="form-field"><label htmlFor="make-periods-length">{t('setup.make_periods_length')}</label><select id="make-periods-length" value={length} onChange={(e) => setLength(e.target.value)}>{PERIOD_LENGTHS.map((minutes) => <option key={minutes} value={minutes}>{t('setup.make_periods_minutes', { minutes })}</option>)}</select></div>
        <button type="button" className="btn-ghost" onClick={make}>{t(hasSegments ? 'setup.make_periods_replace' : 'setup.make_periods_make')}</button>
      </div>
      {hasSegments && <p className="form-hint">{t('setup.make_periods_replace_note')}</p>}
      {error && <div className="alert alert-error" role="alert">{error}</div>}
    </fieldset>
  )
}
