import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import type { ClosingPolicy } from '../../api/continuous'

export type ClosingChoice = ClosingPolicy | 'later' | null

/** The upload keeps its optional closing choice; model choices live on Simulation. */
export function MissingChoices({ closing, onClosingChange, savedClosing, closingReady, analysisId, disabled }: {
  closing: ClosingChoice
  onClosingChange: (choice: ClosingChoice) => void
  savedClosing: ClosingPolicy | null | undefined
  closingReady: boolean
  analysisId: number
  disabled: boolean
}) {
  const { t } = useTranslation()
  return closingReady ? (savedClosing ? <p>{t('continuous.closing_title')}: {t(`continuous.closing_${savedClosing}`)}{' '}
    <Link to={`/simulation/results?analysis=${analysisId}&plan=current`}>{t('continuous.change')}</Link>
  </p> : <fieldset className="form-field" disabled={disabled}>
    <legend>{t('continuous.closing_title')}</legend>
    {(['DRAIN', 'HARD_CUTOFF', 'later'] as const).map((value) => (
      <label key={value} className="radio-row"><input type="radio" name="file-closing" checked={closing === value} onChange={() => onClosingChange(value)} />
        {t(value === 'later' ? 'setup.read_decide_later' : `continuous.closing_option_${value}`)}
      </label>
    ))}
  </fieldset>) : null
}
