import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import type { ContinuousPlayback } from '../../api/continuous'
import { continuousFloorAt } from '../../lib/continuousFloor'
import { headingText } from '../../lib/headingText'

const MAX_TOKENS = 8

function CustomerTokens({ ids, stage, empty }: { ids: number[]; stage: string; empty: string }) {
  if (ids.length === 0) return <span className="live-empty">{empty}</span>
  const visible = stage === 'waiting' ? ids.slice(0, MAX_TOKENS) : ids.slice(-MAX_TOKENS)
  return (
    <div className="live-customer-list">
      {visible.map((id) => <span className="live-customer" key={id} data-testid={`continuous-${stage}-customer-${id}`}>#{id}</span>)}
      {ids.length > visible.length && <span className="live-customer-more">+{ids.length - visible.length}</span>}
    </div>
  )
}

/** One common FIFO line and its real counters, at the existing full-day replay clock. */
export function ContinuousQueueFloor({ playback, time, playing }: { playback: ContinuousPlayback; time: number; playing: boolean }) {
  const { t } = useTranslation()
  const floor = useMemo(() => continuousFloorAt(playback, time), [playback, time])
  if (!floor) return <p role="status" className="alert alert-warn">{t('simulation.live_unavailable')}</p>
  return (
    <section className={`live-flow continuous-floor${playing ? '' : ' is-static'}`} aria-label={t('simulation.live_floor_title')}>
      <h3 lang="en" className="section-title">{headingText(t, 'simulation.live_floor_title')}</h3>
      <div className="live-stage live-arrival-stage"><span className="live-stage-label">{t('simulation.live_arrived')}</span><strong>{floor.arrived}</strong></div>
      <div className="live-flow-arrow" aria-hidden="true">↓</div>
      <section className="live-stage">
        <div className="live-stage-heading"><div><span className="live-stage-label">{t('simulation.live_shared_queue')}</span><strong>{t('simulation.live_waiting_count', { count: floor.waiting.length })}</strong></div><span className="badge badge-neutral">{t('simulation.live_fifo')}</span></div>
        <CustomerTokens ids={floor.waiting} stage="waiting" empty={t('simulation.live_queue_empty')} />
      </section>
      <div className="live-flow-arrow" aria-hidden="true">↓</div>
      <section className="live-stage">
        <span className="live-stage-label">{t('simulation.live_server_area')}</span>
        <div className="live-server-grid">
          {floor.counters.map((counter) => {
            const serving = counter.state === 'BUSY' || counter.state === 'DRAINING'
            const state = serving ? 'serving' : counter.state === 'ON_BREAK' ? 'on_break' : counter.state === 'IDLE' ? 'available' : 'closed'
            return (
              <article className={`live-server${serving ? ' is-serving' : ''}`} key={counter.id} data-testid={`continuous-counter-${counter.id}`} data-state={counter.state}>
                <div className="live-server-heading"><strong>{t('simulation.live_server', { number: counter.id })}</strong><span className={`badge ${serving ? 'badge-ok' : state === 'on_break' ? 'badge-warn' : 'badge-neutral'}`}>{t(`simulation.state_${state}`)}</span></div>
                {counter.customerId !== null && <span className="live-customer live-customer-serving" data-testid={`continuous-serving-customer-${counter.customerId}`}>#{counter.customerId}</span>}
              </article>
            )
          })}
        </div>
      </section>
      <div className="live-flow-arrow" aria-hidden="true">↓</div>
      <div className="live-exit-grid has-abandonment">
        <section className="live-stage"><div className="live-stage-heading"><span className="live-stage-label">{t('simulation.live_served_exit')}</span><strong>{floor.served.length}</strong></div><CustomerTokens ids={floor.served} stage="served" empty={t('simulation.live_none_yet')} /></section>
        <section className="live-stage"><div className="live-stage-heading"><span className="live-stage-label">{t('continuous.not_served')}</span><strong>{floor.unserved.length}</strong></div><CustomerTokens ids={floor.unserved} stage="unserved" empty={t('simulation.live_none_yet')} /></section>
      </div>
    </section>
  )
}
