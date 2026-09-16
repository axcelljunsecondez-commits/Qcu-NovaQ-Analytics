import { useTranslation } from 'react-i18next'

interface QueueIdEditorProps {
  ids: string[]
  onChange: (ids: string[]) => void
  inputIdPrefix?: string
}

/**
 * Dynamic editor for the configured physical queue IDs of a separate-queue
 * Analysis. Names are free-form and authoritative: the backend persists them
 * verbatim (trimmed) and upload validation requires uploaded queue IDs to be
 * a subset of this collection. The editor surfaces blank/duplicate feedback
 * locally, but the API remains the authoritative validator on save.
 */
export function QueueIdEditor({ ids, onChange, inputIdPrefix = 'queue-id' }: QueueIdEditorProps) {
  const { t } = useTranslation()
  const trimmed = ids.map((id) => id.trim())
  const hasBlank = trimmed.some((id) => id === '')
  const hasDuplicate = new Set(trimmed).size !== trimmed.length

  function update(index: number, value: string) {
    onChange(ids.map((id, position) => (position === index ? value : id)))
  }

  function remove(index: number) {
    onChange(ids.filter((_, position) => position !== index))
  }

  return (
    <div className="card">
      <h3 className="card-title">{t('analyses.queue_ids_title')}</h3>
      <p className="form-hint">{t('analyses.queue_ids_help')}</p>
      {ids.map((id, index) => {
        const inputId = `${inputIdPrefix}-${index}`
        const label = t('analyses.queue_id_label', { count: index + 1 })
        return (
          <div className="form-row" key={inputId} style={{ alignItems: 'flex-end', gap: '10px', marginTop: '8px' }}>
            <div className="form-field" style={{ flex: 1 }}>
              <label htmlFor={inputId}>{label}</label>
              <input
                id={inputId}
                value={id}
                placeholder={t('analyses.queue_id_placeholder')}
                onChange={(e) => update(index, e.target.value)}
              />
            </div>
            <button
              type="button"
              className="btn-ghost"
              aria-label={t('analyses.queue_id_remove', { id: id.trim() || label })}
              onClick={() => remove(index)}
            >
              {t('analyses.queue_remove')}
            </button>
          </div>
        )
      })}
      {(hasBlank || hasDuplicate) && (
        <div className="alert alert-error" style={{ marginTop: '8px' }}>
          {hasBlank ? t('analyses.queue_id_blank') : t('analyses.queue_id_duplicate')}
        </div>
      )}
      <button type="button" className="btn-secondary" style={{ marginTop: '8px' }} onClick={() => onChange([...ids, ''])}>
        {t('analyses.queue_id_add')}
      </button>
    </div>
  )
}
