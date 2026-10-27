import { headingText } from '../../lib/headingText'
import { useTranslation } from 'react-i18next'
import type { CounterBreak } from '../../api/types'

interface CounterBreakEditorProps {
  breaks: CounterBreak[]
  onChange: (breaks: CounterBreak[]) => void
}

/**
 * Breaks on one shared line (B4c addendum, 2026-10-12): each entry is one break of a given length
 * from a given time, taken by whichever counter is free first. Nothing is inferred; the API
 * validates on save, and the full-day run refuses a break its staffing cannot cover.
 */
export function CounterBreakEditor({ breaks, onChange }: CounterBreakEditorProps) {
  const { t } = useTranslation()

  function update(index: number, change: Partial<CounterBreak>) {
    onChange(breaks.map((entry, position) => (position === index ? { ...entry, ...change } : entry)))
  }

  return (
    <div className="card" data-testid="counter-breaks">
      <h3 lang="en" className="card-title">{headingText(t, 'analyses.counter_breaks_title')}</h3>
      <p className="form-hint">{t('analyses.counter_breaks_help')}</p>
      {breaks.map((entry, index) => (
        <div className="form-row" key={`counter-break-${index}`} style={{ alignItems: 'flex-end', gap: '10px', marginTop: '8px' }}>
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor={`counter-break-start-${index}`}>{t('analyses.counter_break_start', { number: index + 1 })}</label>
            <input id={`counter-break-start-${index}`} type="time" value={entry.scheduled_start_time}
              onChange={(event) => update(index, { scheduled_start_time: event.target.value })} />
          </div>
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor={`counter-break-minutes-${index}`}>{t('analyses.counter_break_minutes', { number: index + 1 })}</label>
            <input id={`counter-break-minutes-${index}`} type="number" min={1} step={1}
              value={Number.isFinite(entry.duration_minutes) ? entry.duration_minutes : ''}
              onChange={(event) => update(index, { duration_minutes: event.target.value === '' ? Number.NaN : Number(event.target.value) })} />
          </div>
          <button type="button" className="btn-ghost" aria-label={t('analyses.counter_break_remove', { number: index + 1 })}
            onClick={() => onChange(breaks.filter((_, position) => position !== index))}>
            {t('analyses.break_remove')}
          </button>
        </div>
      ))}
      <button type="button" className="btn-secondary" style={{ marginTop: '8px' }}
        onClick={() => onChange([...breaks, { scheduled_start_time: '', duration_minutes: Number.NaN }])}>
        {t('analyses.counter_break_add')}
      </button>
    </div>
  )
}
