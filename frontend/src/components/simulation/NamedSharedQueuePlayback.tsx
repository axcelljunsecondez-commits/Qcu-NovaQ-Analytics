import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { NamedPlayback, NamedPlaybackEvent, PlaybackPeriod } from '../../api/sharedNamed'
import { fmtDecimal } from '../../lib/format'
import { clockFromHours } from '../../lib/namedWorkforce'

interface Props {
  playback: NamedPlayback
  horizonStartMinute: number
}

const PAGE = 100
const SPEEDS = [1, 2, 5, 10, 25]
const PERIOD_STYLE: Record<PlaybackPeriod, string> = {
  before_opening: 'badge-neutral',
  operating_horizon: 'badge-ok',
  closing: 'badge-warn',
  after_closing: 'badge-bad',
}
const STATE_COLOR: Record<string, string> = {
  OFF: 'var(--disabled-bg)',
  WAITING_FOR_REGISTER: 'var(--warning)',
  AVAILABLE: 'var(--success)',
  SERVING: 'var(--info)',
  SERVING_BREAK_DUE: 'var(--purple-700)',
  SERVING_SHIFT_ENDED: 'var(--danger)',
  ON_BREAK: 'var(--gold-500)',
}

/** The meaning of one event, taken from the playback's own vocabulary; never hard-coded. */
function meaningOf(playback: NamedPlayback, event: NamedPlaybackEvent): string {
  if (event.source === 'customer_trace') return playback.event_vocabulary.customer_trace[event.type] ?? ''
  const match = playback.event_vocabulary.employee_transitions.find((item) => item.stage === event.stage
    && item.event === event.type && item.from_state === event.employee_state_before
    && item.to_state === event.employee_state_after)
  return match?.meaning ?? ''
}

/** Each employee's state and register after the given event, read from the recorded transitions only. */
function lanesAt(playback: NamedPlayback, step: number): Array<{ id: string; state: string | null; register: number | null }> {
  return Object.keys(playback.employees).sort().map((id) => {
    let state: string | null = null
    let register: number | null = null
    let seen = false
    for (let index = 0; index < playback.events.length; index += 1) {
      const event = playback.events[index]
      if (event.source !== 'employee_transition' || event.employee_id !== id) continue
      if (index > step) {
        if (!seen) {
          state = event.employee_state_before
          register = event.register_before
        }
        break
      }
      seen = true
      state = event.employee_state_after
      register = event.register_after
    }
    return { id, state, register }
  })
}

export function NamedSharedQueuePlayback({ playback, horizonStartMinute }: Props) {
  const { t } = useTranslation()
  const events = playback.events
  const last = Math.max(events.length - 1, 0)
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(SPEEDS[0])

  useEffect(() => {
    if (!playing) return undefined
    const timer = window.setInterval(() => setStep((current) => Math.min(current + 1, last)), 1000 / speed)
    return () => window.clearInterval(timer)
  }, [playing, speed, last])
  useEffect(() => {
    if (playing && step >= last) setPlaying(false)
  }, [playing, step, last])

  const current = events[step] ?? null
  const lanes = useMemo(() => lanesAt(playback, step), [playback, step])
  const closingHours = playback.closing.closing_hours
  const span = useMemo(() => {
    const times = [0, closingHours, ...events.map((event) => event.t)]
    for (const intervals of Object.values(playback.employees)) {
      for (const item of intervals) times.push(item.start, item.end)
    }
    const low = Math.min(...times)
    const high = Math.max(...times)
    return { low, width: high > low ? high - low : 1 }
  }, [events, playback.employees, closingHours])
  const position = (hours: number) => `${((hours - span.low) / span.width) * 100}%`
  const page = Math.floor(step / PAGE)
  const pageEvents = events.slice(page * PAGE, page * PAGE + PAGE)
  const clock = (hours: number) => clockFromHours(horizonStartMinute, hours)

  return (
    <section className="card" data-testid="named-playback" aria-label={t('simulation.named_playback_title')}>
      <h3 className="section-title">{t('simulation.named_playback_title')}</h3>
      <p className="form-hint">
        <span className={`badge ${playback.validation.valid ? 'badge-ok' : 'badge-bad'}`} data-testid="named-playback-validation">
          {t(playback.validation.valid ? 'simulation.named_playback_valid' : 'simulation.named_playback_invalid')}
        </span>{' '}
        {t('simulation.named_playback_help')}
      </p>

      <div className="form-row" role="group" aria-label={t('simulation.named_playback_controls')}>
        <button type="button" className="btn-ghost" onClick={() => { setPlaying(false); setStep(0) }}>{t('simulation.named_restart')}</button>
        <button type="button" className="btn-ghost" disabled={step <= 0} onClick={() => setStep((value) => Math.max(value - 1, 0))}>
          {t('simulation.named_step_back')}
        </button>
        <button type="button" className="btn-primary" disabled={events.length === 0} onClick={() => setPlaying((value) => !value)}>
          {t(playing ? 'simulation.named_pause' : 'simulation.named_play')}
        </button>
        <button type="button" className="btn-ghost" disabled={step >= last} onClick={() => setStep((value) => Math.min(value + 1, last))}>
          {t('simulation.named_step_forward')}
        </button>
        <label className="form-field" htmlFor="named-playback-speed">
          <span>{t('simulation.named_speed')}</span>
          <select id="named-playback-speed" value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
            {SPEEDS.map((value) => <option key={value} value={value}>{t('simulation.named_speed_value', { value })}</option>)}
          </select>
        </label>
        <label className="form-field" htmlFor="named-playback-scrubber" style={{ flex: 1 }}>
          <span>{t('simulation.named_event_position', { current: events.length ? step + 1 : 0, total: events.length })}</span>
          <input id="named-playback-scrubber" type="range" min={0} max={last} value={step}
            onChange={(event) => { setPlaying(false); setStep(Number(event.target.value)) }} />
        </label>
      </div>

      {current && (
        <div className="card" data-testid="named-current-event" style={{ marginBottom: '8px' }}>
          <p>
            <strong>#{current.seq}</strong> · {clock(current.t)} ·{' '}
            <span className={`badge ${PERIOD_STYLE[current.period]}`} data-testid="named-current-period">
              {t(`simulation.named_period_${current.period}`)}
            </span>{' '}
            · <code>{current.type}</code>
          </p>
          <p className="form-hint">{meaningOf(playback, current)}</p>
          <p className="form-hint">
            {t('simulation.named_state_after', {
              queue: current.queue_len_after,
              accepting: current.accepting_capacity_after,
              busy: current.busy_employees_after,
              registers: current.register_occupancy_after,
              waiting: current.waiting_for_register_after,
            })}
          </p>
        </div>
      )}

      <div data-testid="named-lanes" aria-label={t('simulation.named_lanes_title')}>
        <h4>{t('simulation.named_lanes_title')}</h4>
        {lanes.map((lane) => (
          <div key={lane.id} data-testid="named-lane" style={{ display: 'grid', gridTemplateColumns: '9rem 12rem 1fr', gap: '8px', alignItems: 'center' }}>
            <strong>{lane.id}</strong>
            <span data-testid="named-lane-state">
              {lane.state ?? '—'}{lane.register !== null ? ` · ${t('simulation.named_register_short', { id: lane.register })}` : ''}
            </span>
            <div style={{ position: 'relative', height: '14px', background: 'var(--bg-secondary)' }}>
              {(playback.employees[lane.id] ?? []).map((item, index) => (
                <span key={`${lane.id}-${index}`} title={`${item.state}${item.register_id !== null ? ` · ${item.register_id}` : ''} · ${clock(item.start)}–${clock(item.end)}`}
                  style={{
                    position: 'absolute', top: 0, bottom: 0, left: position(item.start),
                    width: `calc(${position(item.end)} - ${position(item.start)})`,
                    background: STATE_COLOR[item.state] ?? 'var(--border)',
                  }} />
              ))}
              <span data-testid="named-closing-marker" title={t('simulation.named_closing_marker', { time: clock(closingHours) })}
                style={{ position: 'absolute', top: '-2px', bottom: '-2px', left: position(closingHours), width: '2px', background: 'var(--danger)' }} />
              {current && (
                <span aria-hidden="true" style={{ position: 'absolute', top: '-3px', bottom: '-3px', left: position(current.t), width: '2px', background: 'var(--text-primary)' }} />
              )}
            </div>
          </div>
        ))}
        <p className="form-hint">
          {t('simulation.named_closing_marker', { time: clock(closingHours) })} · {t('simulation.named_closing_policy_value', { policy: playback.closing.policy })}
        </p>
      </div>

      <div className="card table-scroll" role="region" aria-label={t('simulation.named_event_log')} tabIndex={0}>
        <p className="form-hint">
          {t('simulation.named_event_log_page', {
            from: events.length ? page * PAGE + 1 : 0,
            to: page * PAGE + pageEvents.length,
            total: events.length,
          })}
        </p>
        <table>
          <caption className="sr-only">{t('simulation.named_event_log')}</caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">{t('simulation.named_col_clock')}</th>
              <th scope="col">{t('simulation.named_col_period')}</th>
              <th scope="col">{t('simulation.named_col_event')}</th>
              <th scope="col">{t('simulation.named_col_customer')}</th>
              <th scope="col">{t('simulation.named_col_employee')}</th>
              <th scope="col">{t('simulation.named_col_state')}</th>
              <th scope="col">{t('simulation.named_col_register')}</th>
              <th scope="col">{t('simulation.named_col_queue_after')}</th>
            </tr>
          </thead>
          <tbody>
            {pageEvents.map((event, offset) => {
              const index = page * PAGE + offset
              return (
                <tr key={event.seq} data-testid="named-event-row" aria-current={index === step ? 'step' : undefined}
                  onClick={() => { setPlaying(false); setStep(index) }} style={index === step ? { fontWeight: 600 } : undefined}>
                  <th scope="row">{event.seq}</th>
                  <td>{clock(event.t)}</td>
                  <td><span className={`badge ${PERIOD_STYLE[event.period]}`}>{t(`simulation.named_period_${event.period}`)}</span></td>
                  <td title={meaningOf(playback, event)}><code>{event.type}</code></td>
                  <td>{event.customer_id ?? '—'}</td>
                  <td>{event.employee_id ?? '—'}</td>
                  <td>{event.employee_state_before ? `${event.employee_state_before} → ${event.employee_state_after}` : '—'}</td>
                  <td>{event.register_before !== null || event.register_after !== null
                    ? `${event.register_before ?? '—'} → ${event.register_after ?? '—'}`
                    : (event.register_id ?? '—')}</td>
                  <td>{event.queue_len_after}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <section className="card" data-testid="named-not-represented" aria-label={t('simulation.named_not_represented_title')}>
        <h4>{t('simulation.named_not_represented_title')}</h4>
        <p className="form-hint">{playback.not_represented_by_events.definition}</p>
        <p>{t('simulation.named_unfulfilled_breaks', { count: playback.not_represented_by_events.unfulfilled_breaks.length })}</p>
        <ul>
          {playback.not_represented_by_events.unfulfilled_breaks.map((item, index) => (
            <li key={`ub-${index}`}><code>{JSON.stringify(item)}</code></li>
          ))}
        </ul>
        <p>{t('simulation.named_shifts_not_activated', { count: playback.not_represented_by_events.shifts_not_activated.length })}</p>
        <ul>
          {playback.not_represented_by_events.shifts_not_activated.map((item, index) => (
            <li key={`sna-${index}`}><code>{JSON.stringify(item)}</code></li>
          ))}
        </ul>
      </section>

      <details>
        <summary>{t('simulation.named_customers_title', { count: playback.customers.length })}</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">{t('simulation.named_col_customer')}</th>
                <th scope="col">{t('simulation.named_col_arrival')}</th>
                <th scope="col">{t('simulation.named_col_service_start')}</th>
                <th scope="col">{t('simulation.named_col_service_end')}</th>
                <th scope="col">{t('simulation.named_col_employee')}</th>
                <th scope="col">{t('simulation.named_col_register')}</th>
                <th scope="col">{t('simulation.named_col_status')}</th>
                <th scope="col">{t('simulation.named_col_wait_min')}</th>
              </tr>
            </thead>
            <tbody>
              {playback.customers.map((customer) => {
                const at = (key: string) => (typeof customer[key] === 'number' ? clock(customer[key] as number) : '—')
                const wait = typeof customer.wait_hours === 'number' ? customer.wait_hours * 60 : null
                return (
                  <tr key={String(customer.customer_id)}>
                    <th scope="row">{String(customer.customer_id)}</th>
                    <td>{at('arrival_hours')}</td>
                    <td>{at('service_start_hours')}</td>
                    <td>{at('service_end_hours')}</td>
                    <td>{customer.employee_id == null ? '—' : String(customer.employee_id)}</td>
                    <td>{customer.register_id == null ? '—' : String(customer.register_id)}</td>
                    <td>{String(customer.status)}{customer.unserved_reason ? ` (${String(customer.unserved_reason)})` : ''}</td>
                    <td>{fmtDecimal(wait)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </details>

      <details>
        <summary>{t('simulation.named_vocabulary_title')}</summary>
        <dl>
          {Object.entries(playback.event_vocabulary.customer_trace).map(([type, meaning]) => (
            <div key={type}><dt><code>{type}</code></dt><dd className="form-hint">{meaning}</dd></div>
          ))}
          {playback.event_vocabulary.employee_transitions.map((item, index) => (
            <div key={`${item.event}-${index}`}>
              <dt><code>{item.event}</code> ({item.from_state} → {item.to_state})</dt>
              <dd className="form-hint">{item.meaning}</dd>
            </div>
          ))}
        </dl>
      </details>

      <details>
        <summary>{t('simulation.named_unsupported_title')}</summary>
        <ul>
          {Object.entries(playback.unsupported).map(([key, note]) => <li key={key}><code>{key}</code>: {note}</li>)}
        </ul>
      </details>
    </section>
  )
}
