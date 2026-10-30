import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import type { SharedAggregateChoices, SharedAggregatePreviewOut } from '../../api/types'
import type { ClosingPolicy } from '../../api/continuous'

export type ClosingChoice = ClosingPolicy | 'later' | null

export function MissingChoices({ preview, choices, onChange, closing, onClosingChange, savedClosing, closingReady, analysisId, disabled, onEdit }: {
  preview: SharedAggregatePreviewOut
  choices: SharedAggregateChoices
  onChange: (choices: SharedAggregateChoices) => void
  closing: ClosingChoice
  onClosingChange: (choice: ClosingChoice) => void
  savedClosing: ClosingPolicy | null | undefined
  closingReady: boolean
  analysisId: number
  disabled: boolean
  onEdit: (inputId: string) => void
}) {
  const { t } = useTranslation()
  const needsCapacity = preview.unresolved.includes('capacity_mode')
  const needsAbandonment = preview.unresolved.includes('abandonment_mode')
  const capacity = choices.capacity_mode ?? preview.saved_setup.capacity_mode
  const abandonment = choices.abandonment_mode ?? preview.saved_setup.abandonment_mode
  const uncertain = choices.capacity_mode === 'unknown' || choices.abandonment_mode === 'unknown'
  const unsupported = capacity === 'finite' || abandonment === 'modeled'
  return (
    <div className="file-missing-choices">
      {needsCapacity ? (
        <fieldset className="form-field" disabled={disabled}>
          <legend>{t('setup.capacity')}</legend>
          {(['unlimited', 'finite', 'unknown'] as const).map((value) => (
            <label key={value} className="radio-row"><input type="radio" name="file-capacity" checked={choices.capacity_mode === value}
              onChange={() => onChange({ ...choices, capacity_mode: value, total_system_capacity: null })} />
              {t(value === 'unknown' ? 'setup.capacity_not_sure' : `setup.capacity_${value}`)}</label>
          ))}
          {capacity === 'finite' && <div className="form-field"><label htmlFor="file-capacity-total">{t('analyses.total_capacity')}</label>
            <input id="file-capacity-total" type="number" min={1} max={100000} step={1} required value={choices.total_system_capacity ?? ''}
              onChange={(event) => onChange({ ...choices, total_system_capacity: event.target.value === '' ? null : Number(event.target.value) })} /></div>}
          {choices.capacity_mode !== undefined && <p className="form-hint">{t('analyses.capacity')}: {t(capacity === 'unlimited' ? 'analyses.unlimited' : capacity === 'finite' ? 'analyses.finite' : 'analyses.unknown')}</p>}
        </fieldset>
      ) : <p>{t('analyses.capacity')}: <strong>{t(capacity === 'unlimited' ? 'analyses.unlimited' : capacity === 'finite' ? 'analyses.finite' : 'analyses.unknown')}</strong>{capacity === 'finite' && ` (${preview.saved_setup.total_system_capacity ?? t('results.unavailable')})`}{' '}
        <button type="button" className="btn-ghost btn-inline" disabled={disabled} onClick={() => onEdit('capacity-mode')}>{t('continuous.change')}</button></p>}
      {needsAbandonment ? (
        <fieldset className="form-field" disabled={disabled}>
          <legend>{t('setup.abandonment')}</legend>
          {(['not_modeled', 'modeled', 'unknown'] as const).map((value) => (
            <label key={value} className="radio-row"><input type="radio" name="file-abandonment" checked={choices.abandonment_mode === value}
              onChange={() => onChange({ ...choices, abandonment_mode: value, patience_rate_per_hour: null })} />
              {t(value === 'unknown' ? 'setup.abandonment_not_sure' : value === 'modeled' ? 'setup.abandonment_yes' : 'setup.abandonment_no')}</label>
          ))}
          {abandonment === 'modeled' && <div className="form-field"><label htmlFor="file-patience-rate">{t('analyses.theta')}</label>
            <input id="file-patience-rate" type="number" min={0} step="any" required value={choices.patience_rate_per_hour ?? ''}
              onChange={(event) => onChange({ ...choices, patience_rate_per_hour: event.target.value === '' ? null : Number(event.target.value) })} />
            <span className="form-hint">{t('analyses.theta_required')}</span></div>}
          {choices.abandonment_mode !== undefined && <p className="form-hint">{t('analyses.abandonment')}: {t(abandonment === 'not_modeled' ? 'analyses.not_modeled' : abandonment === 'modeled' ? 'analyses.modeled' : 'analyses.unknown')}</p>}
        </fieldset>
      ) : <p>{t('analyses.abandonment')}: <strong>{t(abandonment === 'not_modeled' ? 'analyses.not_modeled' : abandonment === 'modeled' ? 'analyses.modeled' : 'analyses.unknown')}</strong>{abandonment === 'modeled' && ` (${preview.saved_setup.patience_rate_per_hour ?? t('results.unavailable')})`}{' '}
        <button type="button" className="btn-ghost btn-inline" disabled={disabled} onClick={() => onEdit('abandonment-mode')}>{t('continuous.change')}</button></p>}
      {uncertain && <p role="status" className="alert alert-info">{t('setup.read_not_sure_note')}</p>}
      {unsupported && <p role="status" className="alert alert-warn">{t('continuous.reason.capacity_or_abandonment')}</p>}
      {closingReady && (savedClosing ? <p>{t('continuous.closing_title')}: {t(`continuous.closing_${savedClosing}`)}{' '}<Link to={`/simulation/results?analysis=${analysisId}&plan=current`}>{t('continuous.change')}</Link></p> : (
        <fieldset className="form-field" disabled={disabled}>
          <legend>{t('continuous.closing_title')}</legend>
          {(['DRAIN', 'HARD_CUTOFF', 'later'] as const).map((value) => (
            <label key={value} className="radio-row"><input type="radio" name="file-closing" checked={closing === value} onChange={() => onClosingChange(value)} />
              {t(value === 'later' ? 'setup.read_decide_later' : `continuous.closing_option_${value}`)}</label>
          ))}
        </fieldset>
      ))}
    </div>
  )
}
