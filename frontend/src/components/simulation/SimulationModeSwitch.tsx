import { useTranslation } from 'react-i18next'

export type SimulationMode = 'legacy' | 'named'

interface Props {
  mode: SimulationMode
  onChange: (mode: SimulationMode) => void
}

/** Shared-queue analyses only: the legacy shared simulation (the default) or the Named Shared Queue simulation. */
export function SimulationModeSwitch({ mode, onChange }: Props) {
  const { t } = useTranslation()
  const options: Array<{ id: SimulationMode; labelKey: string }> = [
    { id: 'legacy', labelKey: 'simulation.named_mode_legacy' },
    { id: 'named', labelKey: 'simulation.named_mode_named' },
  ]
  return (
    <fieldset className="card" data-testid="simulation-mode-switch" style={{ marginBottom: '12px' }}>
      <legend className="section-title">{t('simulation.named_mode_label')}</legend>
      <div className="form-row">
        {options.map((option) => (
          <label key={option.id} className="form-field" style={{ flexDirection: 'row', alignItems: 'center', gap: '6px' }}>
            <input
              type="radio"
              name="simulation-mode"
              value={option.id}
              checked={mode === option.id}
              onChange={() => onChange(option.id)}
            />
            {t(option.labelKey)}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
