import { headingText } from '../../lib/headingText'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { SimulationTrace } from '../../api/types'
import { MetricCard } from '../ui/MetricCard'
import { StoreFloorView } from './StoreFloorView'
import {
  advancePlaybackTime,
  counterState,
  deriveSeparateLaneSnapshots,
  formatSimulationTime,
  nextPlaybackTime,
} from '../../lib/simulationPlayback'
import { hasBreakEvents, runTimeFor, wallClock, type ScheduledBreak } from '../../lib/replay'

const SPEEDS = [0.25, 0.5, 1, 2, 5, 10, 25, 50]
const ANIMATION_SPEED_LIMIT = 5
const MAX_VISIBLE_CUSTOMERS = 8

function LaneTokens({ ids, empty }: { ids: number[]; empty: string }) {
  const visible = ids.slice(-MAX_VISIBLE_CUSTOMERS)
  const hidden = Math.max(0, ids.length - visible.length)
  if (ids.length === 0) return <span className="live-empty">{empty}</span>
  return (
    <div className="live-customer-list">
      {visible.map((id) => (
        <span className="live-customer" key={id} data-testid={`customer-${id}`}>#{id}</span>
      ))}
      {hidden > 0 && <span className="live-customer-more">+{hidden}</span>}
    </div>
  )
}

export interface SeparatePlaybackProps {
  trace: SimulationTrace
  /** Lanes not staffed; a function lets a full-day replay follow each period's staffing. */
  inactiveQueueIds?: string[] | ((hours: number) => string[])
  /** Header label for a merged full-day trace (its hours), instead of the first period's label. */
  periodLabel?: string | null
  /** Store-clock minutes at run time 0; enables "HH:MM" and "Go to time". */
  originMinutes?: number | null
  /** Breaks from the setup, shown on their own row (never as counter states). */
  scheduled?: ScheduledBreak[]
  initialTime?: number
  onTimeChange?: (hours: number) => void
}

export function SeparateSimulationPlayback(
  { trace, inactiveQueueIds, periodLabel = null, originMinutes = null, scheduled = [], initialTime = 0, onTimeChange }: SeparatePlaybackProps,
) {
  const { t } = useTranslation()
  const [isPlaying, setIsPlaying] = useState(false)
  const [floorLayout, setFloorLayout] = useState<'store' | 'diagram'>('store')
  const [simulationTime, setSimulationTime] = useState(initialTime)
  const [goTo, setGoTo] = useState('')
  const [goToError, setGoToError] = useState(false)
  const [speed, setSpeed] = useState(1)
  const frameRef = useRef<number | null>(null)
  const lastFrameRef = useRef<number | null>(null)
  const lastEventTime = trace.trace.at(-1)?.t ?? 0
  const traceEnd = Math.max(trace.total_hours, lastEventTime)
  const lanes = useMemo(
    () => deriveSeparateLaneSnapshots(trace, simulationTime),
    [trace, simulationTime],
  )
  const segment = trace.segments.find((item) => item.simulation_supported && !item.error)
    ?? trace.segments[0]
  const hasSupportedSegment = trace.segments.some((item) => item.simulation_supported && !item.error)
  const showAbandonment = trace.abandonment_supported || trace.trace.some((event) => event.type === 'abandon')
  const processedCount = trace.trace.filter((event) => event.t <= simulationTime + 1e-9).length
  const totalArrived = lanes.reduce((sum, lane) => sum + lane.arrived, 0)
  const totalWaiting = lanes.reduce((sum, lane) => sum + lane.waitingCustomerIds.length, 0)
  const totalServing = lanes.reduce((sum, lane) => sum + Object.keys(lane.servingByServer).length, 0)
  const totalServed = lanes.reduce((sum, lane) => sum + lane.servedCustomerIds.length, 0)
  const totalAbandoned = lanes.reduce((sum, lane) => sum + lane.abandonedCustomerIds.length, 0)
  const accounted = totalWaiting + totalServing + totalServed + totalAbandoned
  const accountingMatches = totalArrived === accounted
  const closedNow = typeof inactiveQueueIds === 'function' ? inactiveQueueIds(simulationTime) : (inactiveQueueIds ?? [])
  const closedSet = new Set(closedNow.map(String))
  const runLanes = new Set(lanes.map((lane) => lane.queueId))
  const relevantBreaks = scheduled.filter((item) => runLanes.has(item.queueId))
  // D26: break states only from the run's events; scheduled breaks without them are disclosed.
  const breakStateUnavailable = relevantBreaks.length > 0 && !hasBreakEvents(trace)
  const clock = (hours: number) => (originMinutes === null ? formatSimulationTime(hours) : wallClock(originMinutes, hours))
  const lastReportedRef = useRef(simulationTime)
  useEffect(() => {
    if (!onTimeChange || isPlaying || lastReportedRef.current === simulationTime) return
    lastReportedRef.current = simulationTime
    onTimeChange(simulationTime)
  }, [isPlaying, onTimeChange, simulationTime])

  function goToTime() {
    const target = originMinutes === null ? null : runTimeFor(originMinutes, goTo.trim())
    if (target === null || target > traceEnd) {
      setGoToError(true)
      return
    }
    setGoToError(false)
    setIsPlaying(false)
    setSimulationTime(target)
  }

  useEffect(() => {
    if (!isPlaying || traceEnd <= 0) {
      lastFrameRef.current = null
      return
    }

    const tick = (timestamp: number) => {
      const previous = lastFrameRef.current ?? timestamp
      lastFrameRef.current = timestamp
      const elapsedMilliseconds = Math.max(0, timestamp - previous)
      setSimulationTime((current) => {
        const next = advancePlaybackTime(
          current, elapsedMilliseconds, traceEnd, speed,
        )
        if (next >= traceEnd) setIsPlaying(false)
        return next
      })
      frameRef.current = requestAnimationFrame(tick)
    }

    frameRef.current = requestAnimationFrame(tick)
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
      frameRef.current = null
      lastFrameRef.current = null
    }
  }, [isPlaying, speed, traceEnd])

  function play() {
    if (simulationTime >= traceEnd) setSimulationTime(0)
    setIsPlaying(true)
  }

  function pause() {
    setIsPlaying(false)
  }

  function restart() {
    setIsPlaying(false)
    setSimulationTime(0)
  }

  function step() {
    setIsPlaying(false)
    setSimulationTime((current) => nextPlaybackTime(trace, current))
  }

  if (!hasSupportedSegment || !segment) {
    return (
      <div className="alert alert-warn" role="status">
        {t('simulation.live_unavailable')}
        {trace.segments.filter((item) => item.error).map((item) => (
          <div key={String(item.segment_id)}>{item.time}: {item.error}</div>
        ))}
      </div>
    )
  }

  return (
    <div className="live-playback separate-playback" aria-label={t('simulation.playback_view_separate')}>
      <div className="live-kpis">
        <MetricCard label={t('simulation.live_arrived')} value={totalArrived} />
        <MetricCard label={t('simulation.live_waiting')} value={totalWaiting} />
        <MetricCard label={t('simulation.live_serving_count')} value={totalServing} />
        <MetricCard label={t('simulation.live_served')} value={totalServed} />
        {showAbandonment && <MetricCard label={t('simulation.live_abandoned')} value={totalAbandoned} />}
      </div>

      <section className="card live-floor">
        <header className="live-floor-header">
          <div>
            <div className="live-floor-eyebrow" data-testid="replay-period">{periodLabel ?? segment.time} · {segment.selected_model ?? '—'}</div>
            <h3 lang="en" className="section-title">{headingText(t, 'simulation.playback_view_separate')}</h3>
            <p className="form-hint">
              {t('simulation.live_event_progress', { current: processedCount, total: trace.event_count })}
            </p>
          </div>
          <div className="live-clock" aria-live="polite">
            <span>{t(originMinutes === null ? 'simulation.live_simulation_time' : 'simulation.replay_clock')}</span>
            <strong data-testid="replay-clock">{clock(simulationTime)}</strong>
          </div>
          <span className={`badge ${trace.truncated ? 'badge-warn' : 'badge-ok'}`}>
            {trace.truncated ? t('simulation.live_truncated') : t('simulation.live_complete')}
          </span>
        </header>

        {trace.truncated && trace.trace.length > 0 && (
          <div className="alert alert-warn" role="status" data-testid="replay-cut-short">
            {t('simulation.replay_cut_short', { time: clock(trace.trace.at(-1)?.t ?? 0) })}
          </div>
        )}
        {breakStateUnavailable && <div className="alert alert-info" role="status">{t('simulation.break_state_unavailable')}</div>}

        {segment.error && <div className="alert alert-warn">{segment.error}</div>}

        {floorLayout === 'store' ? (
          <StoreFloorView
            lanes={lanes}
            simulationTime={simulationTime}
            showAbandonment={showAbandonment}
            animate={speed < ANIMATION_SPEED_LIMIT}
            inactiveQueueIds={closedNow}
          />
        ) : (
        <div className="live-flow">
          {lanes.map((lane) => {
            const servingEntries = Object.entries(lane.servingByServer)
            const servingCount = servingEntries.length
            const state = counterState(lane, closedSet.has(lane.queueId))
            return (
              <section
                className="live-stage separate-lane"
                key={lane.queueId}
                data-testid={`lane-${lane.queueId}`}
                aria-label={`Queue ${lane.queueId}`}
              >
                <div className="live-stage-heading">
                  <div>
                    <span className="live-stage-label">{t('simulation.live_shared_queue')} {lane.queueId}</span>
                    <strong>{t('simulation.live_waiting_count', { count: lane.waitingCustomerIds.length })}</strong>
                  </div>
                  <span className="badge badge-neutral">{t('simulation.live_fifo')}</span>
                </div>
                <LaneTokens ids={lane.waitingCustomerIds} empty={t('simulation.live_queue_empty')} />

                <div className="live-server-grid">
                  {servingEntries.length === 0 ? (
                    <article
                      className="live-server"
                      data-testid={`server-${String(lane.serverId ?? lane.queueId)}`}
                    >
                      <div className="live-server-heading">
                        <strong>{String(lane.serverId ?? lane.queueId)}</strong>
                        <span className="badge badge-neutral">{t(`simulation.state_${state}`)}</span>
                      </div>
                    </article>
                  ) : (
                    servingEntries.map(([serverKey, customerId]) => (
                      <article
                        className="live-server is-serving"
                        key={serverKey}
                        data-testid={`server-${serverKey}`}
                      >
                        <div className="live-server-heading">
                          <strong>{serverKey}</strong>
                          <span className="badge badge-ok">{t(`simulation.state_${state}`)}</span>
                        </div>
                        <span className="live-customer live-customer-serving" data-testid={`customer-${customerId}`}>
                          #{customerId}
                        </span>
                      </article>
                    ))
                  )}
                </div>

                <div className="live-stage-heading">
                  <span className="live-stage-label">{t('simulation.live_served_exit')}</span>
                  <strong>{lane.servedCustomerIds.length}</strong>
                </div>
                <LaneTokens ids={lane.servedCustomerIds} empty={t('simulation.live_none_yet')} />
                {showAbandonment && lane.abandonedCustomerIds.length > 0 && (
                  <>
                    <div className="live-stage-heading">
                      <span className="live-stage-label">{t('simulation.live_abandoned_exit')}</span>
                      <strong>{lane.abandonedCustomerIds.length}</strong>
                    </div>
                    <LaneTokens ids={lane.abandonedCustomerIds} empty={t('simulation.live_none_yet')} />
                  </>
                )}
                <p className="form-hint">
                  {t('simulation.live_accounting', {
                    arrived: lane.arrived,
                    served: lane.servedCustomerIds.length,
                    waiting: lane.waitingCustomerIds.length,
                    serving: servingCount,
                    abandoned: lane.abandonedCustomerIds.length,
                    accounted: lane.waitingCustomerIds.length + servingCount + lane.servedCustomerIds.length + lane.abandonedCustomerIds.length,
                  })}
                </p>
              </section>
            )
          })}
        </div>
        )}

        <div className={`live-accounting ${accountingMatches ? 'is-valid' : 'is-invalid'}`}>
          {t('simulation.live_accounting', {
            arrived: totalArrived,
            served: totalServed,
            waiting: totalWaiting,
            serving: totalServing,
            abandoned: totalAbandoned,
            accounted,
          })}
        </div>

        <div className="playback-controls live-controls">
          <button type="button" onClick={restart} className="btn-ghost">{t('simulation.playback_restart')}</button>
          <button type="button" onClick={isPlaying ? pause : play} className="btn-primary" disabled={traceEnd <= 0}>
            {isPlaying ? t('simulation.playback_pause') : t('simulation.playback_play')}
          </button>
          <button type="button" onClick={step} className="btn-secondary" disabled={trace.trace.length === 0}>
            {t('simulation.live_step')}
          </button>
          <div className="playback-progress">
            <input
              aria-label={t('simulation.live_event_position')}
              type="range"
              min={0}
              max={Math.max(traceEnd, 0.000001)}
              step="any"
              value={simulationTime}
              onChange={(event) => {
                setIsPlaying(false)
                setSimulationTime(Number(event.target.value))
              }}
            />
          </div>
          {originMinutes !== null && (
            <div className="replay-goto">
              <label htmlFor="replay-goto">{t('simulation.replay_go_to')}</label>
              <input id="replay-goto" type="time" value={goTo} onChange={(event) => setGoTo(event.target.value)} aria-invalid={goToError} />
              <button type="button" className="btn-secondary" onClick={goToTime}>{t('simulation.replay_go')}</button>
              {goToError && <span className="form-error" role="alert">{t('simulation.replay_go_invalid')}</span>}
            </div>
          )}
          <div className="store-view-toggle">
            <label htmlFor="separate-layout">{t('simulation.store_layout')}</label>
            <select
              id="separate-layout"
              value={floorLayout}
              onChange={(event) => setFloorLayout(event.target.value === 'diagram' ? 'diagram' : 'store')}
            >
              <option value="store">{t('simulation.store_view')}</option>
              <option value="diagram">{t('simulation.diagram_view')}</option>
            </select>
          </div>
          <div className="playback-speed">
            <label htmlFor="separate-speed">{t('simulation.playback_speed')}</label>
            <select id="separate-speed" value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
              {SPEEDS.map((value) => <option value={value} key={value}>{value}x</option>)}
            </select>
          </div>
        </div>
        {relevantBreaks.length > 0 && (
          <div className="replay-timeline" role="group" aria-label={t('simulation.scheduled_breaks')}>
            <span className="live-stage-label">{t('simulation.scheduled_breaks')}</span>
            <div className="replay-timeline-row" aria-hidden="true">
              {relevantBreaks.map((item, index) => (
                <span
                  key={`${item.queueId}-${index}`}
                  className="replay-break-marker"
                  style={{
                    left: `${traceEnd > 0 ? Math.min(100, Math.max(0, item.startHours) / traceEnd * 100) : 0}%`,
                    width: `${traceEnd > 0 ? Math.max(0.5, (item.endHours - item.startHours) / traceEnd * 100) : 0}%`,
                  }}
                />
              ))}
            </div>
            <ul className="replay-break-list">
              {relevantBreaks.map((item, index) => (
                <li key={`${item.queueId}-list-${index}`}>
                  {t('simulation.scheduled_break_item', { lane: item.queueId, start: clock(item.startHours), end: clock(item.endHours) })}
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="form-hint live-truth-note">{t('simulation.live_real_trace')}</p>
      </section>
    </div>
  )
}
