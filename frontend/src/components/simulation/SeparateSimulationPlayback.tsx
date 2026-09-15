import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { SimulationTrace } from '../../api/types'
import { MetricCard } from '../ui/MetricCard'
import {
  advancePlaybackTime,
  deriveSeparateLaneSnapshots,
  formatSimulationTime,
  nextPlaybackTime,
} from '../../lib/simulationPlayback'

const SPEEDS = [0.5, 1, 2, 5, 10, 25, 50]
const MAX_VISIBLE_CUSTOMERS = 8
const PLAYBACK_SECONDS_AT_1X = 60

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

export function SeparateSimulationPlayback({ trace }: { trace: SimulationTrace }) {
  const { t } = useTranslation()
  const [isPlaying, setIsPlaying] = useState(false)
  const [simulationTime, setSimulationTime] = useState(0)
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
            <div className="live-floor-eyebrow">{segment.time} · {segment.selected_model ?? '—'}</div>
            <h3 className="section-title">{t('simulation.playback_view_separate')}</h3>
            <p className="form-hint">
              {t('simulation.live_event_progress', { current: processedCount, total: trace.event_count })}
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
          {lanes.map((lane) => {
            const servingEntries = Object.entries(lane.servingByServer)
            const servingCount = servingEntries.length
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
                        <span className="badge badge-neutral">{t('simulation.live_idle')}</span>
                      </div>
                      <span className="live-empty">{t('simulation.live_server_available')}</span>
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
                          <span className="badge badge-ok">{t('simulation.live_serving')}</span>
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
          <div className="playback-speed">
            <label htmlFor="separate-speed">{t('simulation.playback_speed')}</label>
            <select id="separate-speed" value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
              {SPEEDS.map((value) => <option value={value} key={value}>{value}x</option>)}
            </select>
          </div>
        </div>
        <p className="form-hint live-truth-note">{t('simulation.live_real_trace')}</p>
      </section>
    </div>
  )
}
