import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import type { QueueBreak } from '../../api/types'

interface BreakEditorProps {
  queueIds: string[]
  breaks: QueueBreak[]
  onChange: (breaks: QueueBreak[]) => void
}

function padTime(value: string): string {
  return value.length === 5 ? `${value}:00` : value
}

/** A break's label: its name, else "Break n" in time order within its queue. */
function breakLabels(breaks: QueueBreak[], t: TFunction): string[] {
  const labels: string[] = new Array(breaks.length).fill('')
  const byQueue = new Map<string, number[]>()
  breaks.forEach((entry, index) => byQueue.set(entry.queue_id, [...(byQueue.get(entry.queue_id) ?? []), index]))
  for (const indices of byQueue.values()) {
    const ordered = [...indices].sort((left, right) =>
      padTime(breaks[left].scheduled_start_time).localeCompare(padTime(breaks[right].scheduled_start_time)) || left - right)
    ordered.forEach((index, position) => {
      labels[index] = breaks[index].break_name || t('analyses.break_label', { number: position + 1 })
    })
  }
  return labels
}

/**
 * Compact editor for explicitly user-configured server breaks on a
 * separate-queue Analysis. Each break names an existing queue, a scheduled
 * start time, and a duration in minutes. Nothing is inferred or generated:
 * an empty list means "no configured breaks". The API remains the
 * authoritative validator on save.
 */
export function BreakEditor({ queueIds, breaks, onChange }: BreakEditorProps) {
  const { t } = useTranslation()
  const labels = breakLabels(breaks, t)

  function update(index: number, update: Partial<QueueBreak>) {
    onChange(breaks.map((entry, position) => (position === index ? { ...entry, ...update } : entry)))
  }

  function remove(index: number) {
    onChange(breaks.filter((_, position) => position !== index))
  }

  return (
    <div className="card">
      <h3 className="card-title">{t('analyses.breaks_title')}</h3>
      <p className="form-hint">{t('analyses.breaks_help')}</p>
      {breaks.map((entry, index) => (
        <div className="form-row" key={`break-${index}`} style={{ alignItems: 'flex-end', gap: '10px', marginTop: '8px' }}>
          <span className="form-hint" data-testid="break-label" style={{ minWidth: '72px', alignSelf: 'center' }}>{labels[index]}</span>
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor={`break-queue-${index}`}>
              {t('analyses.break_queue_label', { count: index + 1 })}
            </label>
            <select
              id={`break-queue-${index}`}
              value={entry.queue_id}
              onChange={(e) => update(index, { queue_id: e.target.value })}
            >
              <option value="">—</option>
              {queueIds.map((queueId) => (
                <option key={queueId} value={queueId}>
                  {queueId}
                </option>
              ))}
            </select>
          </div>
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor={`break-start-${index}`}>
              {t('analyses.break_start_label', { count: index + 1 })}
            </label>
            <input
              id={`break-start-${index}`}
              type="time"
              value={entry.scheduled_start_time}
              onChange={(e) => update(index, { scheduled_start_time: e.target.value })}
            />
          </div>
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor={`break-duration-${index}`}>
              {t('analyses.break_duration_label', { count: index + 1 })}
            </label>
            <input
              id={`break-duration-${index}`}
              type="number"
              min={1}
              step={1}
              value={Number.isFinite(entry.duration_minutes) ? entry.duration_minutes : ''}
              onChange={(e) => update(index, { duration_minutes: e.target.value === '' ? Number.NaN : Number(e.target.value) })}
            />
          </div>
          <button
            type="button"
            className="btn-ghost"
            aria-label={t('analyses.break_remove_label', { count: index + 1 })}
            onClick={() => remove(index)}
          >
            {t('analyses.break_remove')}
          </button>
        </div>
      ))}
      <button
        type="button"
        className="btn-secondary"
        style={{ marginTop: '8px' }}
        onClick={() => onChange([...breaks, { queue_id: '', scheduled_start_time: '', duration_minutes: Number.NaN }])}
      >
        {t('analyses.break_add')}
      </button>
    </div>
  )
}
