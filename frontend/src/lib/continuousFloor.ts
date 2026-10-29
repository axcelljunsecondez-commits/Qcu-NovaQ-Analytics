import type { ContinuousCounter, ContinuousPlayback } from '../api/continuous'
import { stateAt } from './continuous'

export interface ContinuousFloorSnapshot {
  arrived: number
  waiting: number[]
  served: number[]
  unserved: number[]
  counters: Array<{ id: number; state: ContinuousCounter['intervals'][number]['state'] | 'CLOSED'; customerId: number | null }>
}

/** Display projection of one verified execution's timelines; no simulation or generated identities. */
export function continuousFloorAt(playback: ContinuousPlayback, time: number): ContinuousFloorSnapshot | null {
  const { customers, servers, closing, events } = playback.playback
  if (!customers || !servers || !Number.isFinite(time) || time < 0) return null
  const recorded = stateAt(events, time)
  // Use the same applied event boundary as the existing counters, including its clock tolerance.
  const at = recorded.event?.t ?? time
  if (new Set(customers.map((customer) => customer.customer_id)).size !== customers.length
    || new Set(servers.map((server) => server.server_id)).size !== servers.length) return null
  const arrived = customers.filter((customer) => customer.arrival_hours <= at)
  const served = arrived.filter((customer) => customer.service_end_hours !== null && customer.service_end_hours <= at)
  const unserved = arrived.filter((customer) => customer.status === 'unserved_at_close' && at >= closing.closing_hours)
  const serving = arrived.filter((customer) => customer.service_start_hours !== null && customer.service_start_hours <= at
    && customer.service_end_hours !== null && customer.service_end_hours > at)
  const waiting = arrived.filter((customer) => (customer.service_start_hours === null || customer.service_start_hours > at)
    && !(customer.status === 'unserved_at_close' && at >= closing.closing_hours))
  const counters = servers.map((server) => {
    const interval = server.intervals.find((entry) => entry.start <= at && at < entry.end)
    return { id: server.server_id, state: interval?.state ?? 'CLOSED' as const, customerId: interval?.customer_id ?? null }
  })
  const occupied = counters.filter((counter) => counter.customerId !== null)
  const servingById = new Map(serving.map((customer) => [customer.customer_id, customer.server_id]))
  if (arrived.length !== recorded.arrived || served.length !== recorded.served || unserved.length !== recorded.unserved
    || waiting.length !== recorded.waiting || occupied.length !== serving.length
    || counters.filter((counter) => counter.state === 'IDLE').length !== recorded.idle
    || counters.filter((counter) => counter.state === 'BUSY').length !== recorded.serving
    || counters.filter((counter) => counter.state === 'DRAINING').length !== recorded.draining
    || counters.filter((counter) => counter.state === 'ON_BREAK').length !== recorded.onBreak
    || occupied.some((counter) => servingById.get(counter.customerId!) !== counter.id)) return null
  return {
    arrived: arrived.length,
    waiting: waiting.map((customer) => customer.customer_id),
    served: served.map((customer) => customer.customer_id),
    unserved: unserved.map((customer) => customer.customer_id),
    counters,
  }
}
