import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import type { ContinuousEvent, ContinuousPlayback } from '../../api/continuous'
import { renderWithProviders } from '../../test/test-utils'
import { continuousFloorAt } from '../../lib/continuousFloor'
import { ContinuousQueueFloor } from './ContinuousQueueFloor'

const event = (seq: number, t: number, type: string, waiting: number, idle: number, busy: number, onBreak = 0): ContinuousEvent => ({
  seq, t, type, queue_len_after: waiting, servers_idle_after: idle, servers_busy_after: busy,
  servers_draining_after: 0, servers_on_break_after: onBreak, breaks_waiting_after: 0,
})

// Synthetic display fixture: the second counter's break ends when staffing drops at hour 1.
// Customer 2 keeps waiting across that boundary; customer 3 is unserved at hard closing.
const playback: ContinuousPlayback = {
  replication_index: 0, by_period: [], preview: true,
  playback: {
    closing: { closing_hours: 2, overrun_hours: 0.4 },
    events: [
      event(0, 0, 'server_open', 0, 1, 0), event(1, 0, 'server_open', 0, 2, 0),
      event(2, 0.1, 'arrival', 1, 2, 0), event(3, 0.1, 'service_start', 0, 1, 1),
      event(4, 0.5, 'break_start', 0, 0, 1, 1), event(5, 0.8, 'arrival', 1, 0, 1, 1),
      event(6, 1, 'break_end', 1, 1, 1), event(7, 1, 'server_close', 1, 0, 1),
      event(8, 1.2, 'service_end', 1, 1, 0), event(9, 1.2, 'service_start', 0, 0, 1),
      event(10, 1.8, 'arrival', 1, 0, 1), event(11, 2, 'closing', 1, 0, 1),
      event(12, 2, 'unserved_at_close', 0, 0, 1),
      event(13, 2.4, 'service_end', 0, 1, 0), event(14, 2.4, 'server_close', 0, 0, 0),
    ],
    customers: [
      { customer_id: 1, arrival_hours: 0.1, service_start_hours: 0.1, service_end_hours: 1.2, server_id: 1, status: 'departed' },
      { customer_id: 2, arrival_hours: 0.8, service_start_hours: 1.2, service_end_hours: 2.4, server_id: 1, status: 'departed' },
      { customer_id: 3, arrival_hours: 1.8, service_start_hours: null, service_end_hours: null, server_id: null, status: 'unserved_at_close' },
    ],
    servers: [
      { server_id: 1, intervals: [
        { state: 'IDLE', customer_id: null, start: 0, end: 0.1 },
        { state: 'BUSY', customer_id: 1, start: 0.1, end: 1.2 },
        { state: 'BUSY', customer_id: 2, start: 1.2, end: 2.4 },
      ] },
      { server_id: 2, intervals: [
        { state: 'IDLE', customer_id: null, start: 0, end: 0.5 },
        { state: 'ON_BREAK', customer_id: null, start: 0.5, end: 1 },
      ] },
    ],
  },
}

describe('full-day floor projection', () => {
  it('keeps actual waiting and serving identities across a staffing-period boundary', () => {
    expect(continuousFloorAt(playback, 0)).toMatchObject({ arrived: 0, waiting: [], served: [], unserved: [] })
    const before = continuousFloorAt(playback, 0.9)!
    const after = continuousFloorAt(playback, 1.1)!
    expect(before.waiting).toEqual([2])
    expect(after.waiting).toEqual([2])
    expect(after.counters).toEqual([
      { id: 1, state: 'BUSY', customerId: 1 }, { id: 2, state: 'CLOSED', customerId: null },
    ])
    expect(before.counters[1].state).toBe('ON_BREAK')
    expect(continuousFloorAt(playback, 1.3)!.counters[0].customerId).toBe(2)
    expect(continuousFloorAt(playback, 0.8 - 5e-10)).toMatchObject({ arrived: 2, waiting: [2] })
  })

  it('keeps a draining counter serving its recorded customer until completion', () => {
    const draining: ContinuousPlayback = {
      ...playback, playback: {
        closing: { closing_hours: 2, overrun_hours: 0 },
        customers: [
          { customer_id: 1, arrival_hours: 0.1, service_start_hours: 0.1, service_end_hours: 2, server_id: 1, status: 'departed' },
          { customer_id: 2, arrival_hours: 0.2, service_start_hours: 0.2, service_end_hours: 1.5, server_id: 2, status: 'departed' },
        ],
        servers: [
          { server_id: 1, intervals: [{ state: 'IDLE', customer_id: null, start: 0, end: 0.1 }, { state: 'BUSY', customer_id: 1, start: 0.1, end: 2 }] },
          { server_id: 2, intervals: [{ state: 'IDLE', customer_id: null, start: 0, end: 0.2 }, { state: 'BUSY', customer_id: 2, start: 0.2, end: 1 }, { state: 'DRAINING', customer_id: 2, start: 1, end: 1.5 }] },
        ],
        events: [
          event(0, 0, 'server_open', 0, 1, 0), event(1, 0, 'server_open', 0, 2, 0),
          event(2, 0.1, 'arrival', 1, 2, 0), event(3, 0.1, 'service_start', 0, 1, 1),
          event(4, 0.2, 'arrival', 1, 1, 1), event(5, 0.2, 'service_start', 0, 0, 2),
          { ...event(6, 1, 'server_drain_start', 0, 0, 1), servers_draining_after: 1 },
          event(7, 1.5, 'service_end', 0, 0, 1), event(8, 1.5, 'server_drain_complete', 0, 0, 1),
          event(9, 2, 'service_end', 0, 1, 0), event(10, 2, 'closing', 0, 1, 0), event(11, 2, 'server_close', 0, 0, 0),
        ],
      },
    }
    expect(continuousFloorAt(draining, 1.1)!.counters[1]).toEqual({ id: 2, state: 'DRAINING', customerId: 2 })
    const { rerender } = renderWithProviders(<ContinuousQueueFloor playback={draining} time={1.1} playing={false} />)
    expect(screen.getByTestId('continuous-counter-2')).toHaveTextContent('Serving')
    expect(screen.getByTestId('continuous-counter-2')).toHaveAttribute('data-state', 'DRAINING')
    rerender(<ContinuousQueueFloor playback={draining} time={1.6} playing={false} />)
    expect(screen.getByTestId('continuous-counter-2')).toHaveTextContent('Closed / not staffed')
  })

  it('uses recorded end times and hard-closing outcomes, and supports backward seek', () => {
    expect(continuousFloorAt(playback, 1.9)).toMatchObject({ arrived: 3, waiting: [3], served: [1], unserved: [] })
    expect(continuousFloorAt(playback, 2.1)).toMatchObject({ arrived: 3, waiting: [], served: [1], unserved: [3] })
    expect(continuousFloorAt(playback, 2.5)).toMatchObject({ served: [1, 2], unserved: [3] })
    expect(continuousFloorAt(playback, 0.9)).toMatchObject({ arrived: 2, waiting: [2], served: [], unserved: [] })
  })

  it('keeps customers queued after DRAIN closing until their recorded service starts', () => {
    const drain = structuredClone(playback)
    drain.playback.closing.overrun_hours = 0.5
    drain.playback.customers![2] = { ...drain.playback.customers![2], service_start_hours: 2.4, service_end_hours: 2.5, server_id: 1, status: 'departed' }
    drain.playback.servers![0].intervals.push({ state: 'BUSY', customer_id: 3, start: 2.4, end: 2.5 })
    drain.playback.events = drain.playback.events.slice(0, 12).concat([
      event(12, 2.4, 'service_end', 1, 1, 0), event(13, 2.4, 'service_start', 0, 0, 1),
      event(14, 2.5, 'service_end', 0, 1, 0), event(15, 2.5, 'server_close', 0, 0, 0),
    ])
    expect(continuousFloorAt(drain, 2.1)).toMatchObject({ waiting: [3], served: [1], unserved: [] })
    expect(continuousFloorAt(drain, 2.45)!.counters[0].customerId).toBe(3)
    expect(continuousFloorAt(drain, 2.5)).toMatchObject({ served: [1, 2, 3], unserved: [] })
  })

  it('refuses absent or contradictory timelines instead of inventing customer identities', () => {
    expect(continuousFloorAt({ ...playback, playback: { ...playback.playback, customers: undefined } }, 1)).toBeNull()
    const inconsistent = structuredClone(playback)
    inconsistent.playback.servers![0].intervals[1].customer_id = 999
    expect(continuousFloorAt(inconsistent, 0.9)).toBeNull()
    expect(continuousFloorAt(playback, NaN)).toBeNull()
  })
})

describe('continuous queue-floor visual', () => {
  it('renders actual tokens, break/closure badges and the served/unserved exits', () => {
    const { rerender } = renderWithProviders(<ContinuousQueueFloor playback={playback} time={0.9} playing={false} />)
    const floor = screen.getByRole('region', { name: 'Live queue floor' })
    expect(within(floor).getByTestId('continuous-waiting-customer-2')).toBeInTheDocument()
    expect(within(floor).getByTestId('continuous-serving-customer-1')).toBeInTheDocument()
    expect(within(floor).getByTestId('continuous-counter-2')).toHaveTextContent('On break')
    rerender(<ContinuousQueueFloor playback={playback} time={2.1} playing={false} />)
    expect(within(floor).getByTestId('continuous-serving-customer-2')).toBeInTheDocument()
    expect(within(floor).getByTestId('continuous-served-customer-1')).toBeInTheDocument()
    expect(within(floor).getByTestId('continuous-unserved-customer-3')).toBeInTheDocument()
    expect(within(floor).getByTestId('continuous-counter-2')).toHaveTextContent('Closed / not staffed')
  })

  it('states when visual playback identities are unavailable', () => {
    renderWithProviders(<ContinuousQueueFloor playback={{ ...playback, playback: { ...playback.playback, customers: undefined } }} time={1} playing={false} />)
    expect(screen.getByRole('status')).toHaveTextContent('Playback data is unavailable for this simulation.')
    expect(screen.queryByRole('region', { name: 'Live queue floor' })).not.toBeInTheDocument()
  })
})
