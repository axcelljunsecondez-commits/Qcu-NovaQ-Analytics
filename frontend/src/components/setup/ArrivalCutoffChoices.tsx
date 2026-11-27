import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { arrivalAllowances, type ArrivalAllowance } from '../../api/continuous'
import { clockOfMinutes } from '../../lib/continuous'

export type OperatingWindow = { start: number; end: number }

interface ArrivalCutoffChoicesProps {
  window: OperatingWindow
  value: ArrivalAllowance
  onChange: (value: ArrivalAllowance) => void
  disabled?: boolean
  showFileHint?: boolean
}

export function ArrivalCutoffChoices({ window, value, onChange, disabled, showFileHint }: ArrivalCutoffChoicesProps) {
  const { t } = useTranslation()
  const id = useId()
  return (
    <fieldset className="form-field shared-arrival-choices" disabled={disabled}>
      <legend>{t('setup.arrival_cutoff_question')}</legend>
      {showFileHint && <p className="form-hint">{t('setup.arrival_cutoff_file_hint')}</p>}
      {arrivalAllowances.map((minutes) => {
        const available = minutes < window.end - window.start
        const label = t(minutes === 0 ? 'setup.arrival_at_closing' : minutes === 60 ? 'setup.arrival_one_hour' : 'setup.arrival_before_closing', { minutes })
        const time = available ? clockOfMinutes(window.end - minutes) : null
        return (
          <label key={minutes} className="radio-row shared-arrival-option">
            <input type="radio" name={id} value={minutes} checked={value === minutes} disabled={!available}
              aria-label={time ? `${label} ${time}` : label} onChange={() => onChange(minutes)} />
            <span>{label}</span>
            {time && <time>{time}</time>}
          </label>
        )
      })}
      <p className="form-hint">{t('setup.arrival_service_continues', { time: clockOfMinutes(window.end) })}</p>
    </fieldset>
  )
}
