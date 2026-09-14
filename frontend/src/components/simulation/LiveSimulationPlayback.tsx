import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { SimulationTrace } from '../../api/types'
import { MetricCard } from '../ui/MetricCard'
import {
  advancePlaybackTime,
  derivePlaybackSnapshot,
  formatSimulationTime,
  nextPlaybackTime,
} from '../../lib/simulationPlayback'

const SPEEDS = [0.5, 1, 2, 5, 10, 25, 50]
const MAX_VISIBLE_CUSTOMERS = 8
const PLAYBACK_SECONDS_AT_1X = 60

function CustomerTokens({ ids, empty }: { ids: number[]; empty: string }) {
  const visible = ids.slice(-MAX_VISIBLE_CUSTOMERS)
  const hidden = Math.max(0, ids.length - visible.length)
  if (ids.length === 0) return <span className="live-empty">{empty}</span>
  return (
    <div className="live-customer-list">
      {visible.map((id) => (
        <span className="live-customer" key={id}>#{id}</span>
      ))}
      {hidden > 0 && <span className="live-customer-more">+{hidden}</span>}
    </div>
  )
}

export function LiveSimulationPlayback({ trace }: { trace: SimulationTrace }) {
  const { t } = useTranslation()
  const [isPlaying, setIsPlaying] = useState(false)
  const [simulationTime, setSimulationTime] = useState(0)
  const [speed, setSpeed] = useState(1)
  const frameRef = useRef<number | null>(null)
  const lastFrameRef = useRef<number | null>(null)
  const lastEventTime = trace.trace.at(-1)?.t ?? 0
  const traceEnd = Math.max(trace.total_hours, lastEventTime)
  const snapshot = useMemo(
    () => derivePlaybackSnapshot(trace, simulationTime),
    [trace, simulationTime],
  )
  const segment = trace.segments.find((item) => item.segment_id === snapshot.segmentId)
    ?? trace.segments[0]
  const hasSupportedSegment = trace.segments.some((item) => item.simulation_supported && !item.error)
  const showAbandonment = trace.abandonment_supported || trace.trace.some((event) => event.type === 'abandon')
  const servingCount = Object.keys(snapshot.servingByServer).length
  const accounted = snapshot.waitingCustomerIds.length
    + servingCount
    + snapshot.servedCustomerIds.length
    + snapshot.abandonedCustomerIds.length

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
          current, elapsedMilliseconds, traceEnd, speed, PLAYBACK_SECONDS_AT_1X,
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
          <div key={item.segment_id}>{item.time}: {item.error}</div>
        ))}
      </div>
    )
  }

  const queueIds = snapshot.waitingCustomerIds
  const servedIds = snapshot.servedCustomerIds
  const abandonedIds = snapshot.abandonedCustomerIds

  return (
    <div className="live-playback" aria-label={t('simulation.live_floor_title')}>
      <div className="live-kpis">
        <MetricCard label={t('simulation.live_arrived')} value={snapshot.arrived} />
        <MetricCard label={t('simulation.live_waiting')} value={queueIds.length} />
        <MetricCard label={t('simulation.live_serving_count')} value={servingCount} />
        <MetricCard label={t('simulation.live_served')} value={servedIds.length} />
        {showAbandonment && <MetricCard label={t('simulation.live_abandoned')} value={abandonedIds.length} />}
        <MetricCard
          label={t('simulation.live_average_wait')}
          value={snapshot.averageWaitMinutes === null ? '—' : `${snapshot.averageWaitMinutes.toFixed(2)} min`}
        />
        <MetricCard
          label={t('simulation.live_utilization')}
          value={snapshot.utilization === null ? '—' : `${Math.round(snapshot.utilization * 100)}%`}
        />
      </div>

      <section className="card live-floor">
        <header className="live-floor-header">
          <div>
            <div className="live-floor-eyebrow">{segment.time} · {segment.selected_model ?? '—'}</div>
            <h3 className="section-title">{t('simulation.live_floor_title')}</h3>
            <p className="form-hint">
              {t('simulation.live_event_progress', { current: snapshot.eventCount, total: trace.event_count })}
            </p>
          </div>
          <div className="live-clock" aria-live="polite">
            <span>{t('simulation.live_simulation_time')}</span>
            <strong>{formatSimulationTime(simulationTime)}</strong>
          </div>
          <span className={`badge ${trace.truncated ? 'badge-warn' : 'badge-ok'}`}>
            {trace.truncated ? t('simulation.live_truncated') : t('simulation.live_complete')}
          </span>
        </header>

        {segment.error && <div className="alert alert-warn">{segment.error}</div>}

        <div className="live-flow">
          <section className="live-stage live-arrival-stage">
            <span className="live-stage-label">{t('simulation.live_arrival')}</span>
            <div className="live-arrival-current">
              {snapshot.latestArrivalId === null
                ? t('simulation.live_no_arrivals')
                : t('simulation.live_latest_customer', { id: snapshot.latestArrivalId })}
            </div>
          </section>

          <div className="live-flow-arrow" aria-hidden="true">↓</div>

          <section className="live-stage live-queue-stage">
            <div className="live-stage-heading">
              <div>
                <span className="live-stage-label">{t('simulation.live_shared_queue')}</span>
                <strong>{t('simulation.live_waiting_count', { count: queueIds.length })}</strong>
              </div>
              <span className="badge badge-neutral">{t('simulation.live_fifo')}</span>
            </div>
            <CustomerTokens ids={queueIds} empty={t('simulation.live_queue_empty')} />
          </section>

          <div className="live-flow-arrow" aria-hidden="true">↓</div>

          <section className="live-stage">
            <span className="live-stage-label">{t('simulation.live_server_area')}</span>
            <div className="live-server-grid">
              {Array.from({ length: segment.c }, (_, serverId) => {
                const customerId = snapshot.servingByServer[serverId]
                return (
                  <article className={`live-server ${customerId === undefined ? '' : 'is-serving'}`} key={serverId}>
                    <div className="live-server-heading">
                      <strong>{t('simulation.live_server', { number: serverId + 1 })}</strong>
                      <span className={`badge ${customerId === undefined ? 'badge-neutral' : 'badge-ok'}`}>
                        {customerId === undefined ? t('simulation.live_idle') : t('simulation.live_serving')}
                      </span>
                    </div>
                    {customerId === undefined
                      ? <span className="live-empty">{t('simulation.live_server_available')}</span>
                      : <span className="live-customer live-customer-serving">#{customerId}</span>}
                  </article>
                )
              })}
            </div>
          </section>

          <div className="live-flow-arrow" aria-hidden="true">↓</div>

          <div className={`live-exit-grid ${showAbandonment ? 'has-abandonment' : ''}`}>
            <section className="live-stage live-served-stage">
              <div className="live-stage-heading">
                <span className="live-stage-label">{t('simulation.live_served_exit')}</span>
                <strong>{servedIds.length}</strong>
              </div>
              <CustomerTokens ids={servedIds} empty={t('simulation.live_none_yet')} />
            </section>
            {showAbandonment && (
              <section className="live-stage live-abandoned-stage">
                <div className="live-stage-heading">
                  <span className="live-stage-label">{t('simulation.live_abandoned_exit')}</span>
                  <strong>{abandonedIds.length}</strong>
                </div>
                <CustomerTokens ids={abandonedIds} empty={t('simulation.live_none_yet')} />
              </section>
            )}
          </div>
        </div>

        <div className={`live-accounting ${snapshot.accountingMatches ? 'is-valid' : 'is-invalid'}`}>
          {t('simulation.live_accounting', {
            arrived: snapshot.arrived,
            served: servedIds.length,
            waiting: queueIds.length,
            serving: servingCount,
            abandoned: abandonedIds.length,
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
          <div className="playback-speed">
            <label htmlFor="live-speed">{t('simulation.playback_speed')}</label>
            <select id="live-speed" value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
              {SPEEDS.map((value) => <option value={value} key={value}>{value}x</option>)}
            </select>
          </div>
        </div>
        <p className="form-hint live-truth-note">{t('simulation.live_real_trace')}</p>
      </section>
    </div>
  )
}
