import { useTranslation } from 'react-i18next'
import { counterState, type CounterState, type SeparateLaneSnapshot } from '../../lib/simulationPlayback'

const MAX_VISIBLE_IN_LANE = 6
const DENSE_LANE_THRESHOLD = 10
const STATE_BADGE: Record<CounterState, string> = {
  available: 'badge-neutral', serving: 'badge-ok', finishing: 'badge-warn', on_break: 'badge-warn', closed: 'badge-warn',
}

export interface StoreFloorViewProps {
  lanes: SeparateLaneSnapshot[]
  simulationTime: number
  showAbandonment: boolean
  animate: boolean
  inactiveQueueIds?: string[]
}

/**
 * Store-floor rendering of the same lane snapshots the diagram view uses.
 * Presentation-only: every dot, badge and timer is read from the derived
 * snapshot, so it can never disagree with the diagram or the accounting line.
 */
export function StoreFloorView({
  lanes,
  simulationTime,
  showAbandonment,
  animate,
  inactiveQueueIds = [],
}: StoreFloorViewProps) {
  const { t } = useTranslation()
  const closed = new Set(inactiveQueueIds.map((id) => String(id)))
  const totalArrived = lanes.reduce((sum, lane) => sum + lane.arrived, 0)
  const totalServed = lanes.reduce((sum, lane) => sum + lane.servedCustomerIds.length, 0)
  const totalAbandoned = lanes.reduce((sum, lane) => sum + lane.abandonedCustomerIds.length, 0)

  return (
    <div
      className={[
        'store-floor',
        animate ? '' : 'is-static',
        lanes.length > DENSE_LANE_THRESHOLD ? 'is-dense' : '',
      ].filter(Boolean).join(' ')}
      aria-label={t('simulation.store_view')}
    >
      <aside className="store-rail">
        <span className="live-stage-label">{t('simulation.store_arriving')}</span>
        <strong data-testid="store-arrived">{totalArrived}</strong>
        <span className="store-rail-arrow" aria-hidden="true">→</span>
      </aside>

      <div
        className="store-lanes"
        style={{ ['--store-lane-count' as string]: String(Math.max(lanes.length, 1)) }}
      >
        {lanes.map((lane) => {
          const servingEntries = Object.entries(lane.servingByServer)
          const isClosed = closed.has(lane.queueId)
          const state = counterState(lane, isClosed)
          const stateBadge = <span className={`badge ${STATE_BADGE[state]}`} data-testid={`state-${lane.queueId}`}>{t(`simulation.state_${state}`)}</span>
          const waiting = lane.waitingCustomerIds
          const visible = waiting.slice(0, MAX_VISIBLE_IN_LANE)
          const hidden = Math.max(0, waiting.length - visible.length)
          return (
            <section
              className={`store-lane ${state === 'closed' ? 'is-closed' : ''} ${state === 'on_break' ? 'is-on-break' : ''}`}
              key={lane.queueId}
              data-testid={`lane-${lane.queueId}`}
              aria-label={`Queue ${lane.queueId}`}
            >
              <div className="store-queue">
                <span className="store-queue-count">
                  {t('simulation.live_waiting_count', { count: waiting.length })}
                </span>
                {hidden > 0 && <span className="store-queue-more">+{hidden}</span>}
                <div className="store-queue-dots">
                  {visible.map((id) => (
                    <span className="store-dot" key={id} data-testid={`customer-${id}`}>
                      <span className="store-dot-id">{id}</span>
                    </span>
                  ))}
                </div>
              </div>

              {servingEntries.length === 0 ? (
                <article
                  className="store-counter"
                  data-testid={`server-${String(lane.serverId ?? lane.queueId)}`}
                  title={String(lane.serverId ?? lane.queueId)}
                >
                  <strong className="store-counter-name">{lane.queueId}</strong>
                  {stateBadge}
                  {state === 'closed' && <span className="store-counter-meta">{t('simulation.store_closed_hint')}</span>}
                </article>
              ) : (
                servingEntries.map(([serverKey, customerId]) => {
                  const startedAt = lane.serviceStartByServer[serverKey]
                  const elapsedMinutes = startedAt === undefined
                    ? null
                    : Math.max(0, (simulationTime - startedAt) * 60)
                  return (
                    <article
                      className="store-counter is-serving"
                      key={serverKey}
                      data-testid={`server-${serverKey}`}
                      title={serverKey}
                    >
                      <strong className="store-counter-name">{lane.queueId}</strong>
                      {stateBadge}
                      <span className="store-counter-customer" data-testid={`customer-${customerId}`}>
                        <span className="store-dot-id">{customerId}</span>
                      </span>
                      <span className="store-counter-meta">
                        {elapsedMinutes === null
                          ? '—'
                          : t('simulation.store_service_elapsed', { minutes: elapsedMinutes.toFixed(1) })}
                      </span>
                    </article>
                  )
                })
              )}
            </section>
          )
        })}
      </div>

      <aside className="store-rail store-rail-exit">
        <span className="live-stage-label">{t('simulation.store_departing')}</span>
        <strong data-testid="store-served">{totalServed}</strong>
        <span className="store-rail-arrow" aria-hidden="true">→</span>
        {showAbandonment && (
          <span className="store-rail-abandoned" data-testid="store-abandoned">
            {t('simulation.live_abandoned_exit')}: {totalAbandoned}
          </span>
        )}
      </aside>
    </div>
  )
}
