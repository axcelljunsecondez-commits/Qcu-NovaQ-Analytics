import { describe, expect, it } from 'vitest'
import type { SimulationTrace } from '../api/types'
import {
  advancePlaybackTime,
  derivePlaybackSnapshot,
  formatSimulationTime,
  nextPlaybackTime,
} from './simulationPlayback'

const trace: SimulationTrace = {
  trace: [
    { t: 0.1, type: 'arrival', segment_id: 0, customer_id: 1, server_id: null, queue_len_after: 0 },
    { t: 0.1, type: 'service_start', segment_id: 0, customer_id: 1, server_id: 0, queue_len_after: 0 },
    { t: 0.2, type: 'arrival', segment_id: 0, customer_id: 2, server_id: null, queue_len_after: 1 },
    { t: 0.4, type: 'service_end', segment_id: 0, customer_id: 1, server_id: 0, queue_len_after: 0 },
    { t: 0.4, type: 'service_start', segment_id: 0, customer_id: 2, server_id: 0, queue_len_after: 0 },
    { t: 0.6, type: 'service_end', segment_id: 0, customer_id: 2, server_id: 0, queue_len_after: 0 },
  ],
  trace_hours: 1,
  total_hours: 1,
  event_count: 6,
  truncated: false,
  abandonment_supported: false,
  segments: [{
    segment_id: 0,
    time: '08:00-09:00',
    lambda: 2,
    mu: 3,
    c: 1,
    selected_model: 'M/M/1',
    simulation_supported: true,
    error: null,
    queue_structure: 'shared',
    initial_queue_depth: 0,
    final_queue_depth: 0,
  }],
}

describe('simulation playback state', () => {
  it('applies equal-time arrival and service events together', () => {
    const state = derivePlaybackSnapshot(trace, 0.1)
    expect(state.eventCount).toBe(2)
    expect(state.arrived).toBe(1)
    expect(state.waitingCustomerIds).toEqual([])
    expect(state.servingByServer).toEqual({ 0: 1 })
    expect(state.accountingMatches).toBe(true)
  })

  it('moves the actual customer from queue to server to served', () => {
    const queued = derivePlaybackSnapshot(trace, 0.2)
    expect(queued.waitingCustomerIds).toEqual([2])
    expect(queued.servingByServer).toEqual({ 0: 1 })

    const serving = derivePlaybackSnapshot(trace, 0.4)
    expect(serving.waitingCustomerIds).toEqual([])
    expect(serving.servingByServer).toEqual({ 0: 2 })
    expect(serving.servedCustomerIds).toEqual([1])

    const complete = derivePlaybackSnapshot(trace, 1)
    expect(complete.servingByServer).toEqual({})
    expect(complete.servedCustomerIds).toEqual([1, 2])
    expect(complete.averageWaitMinutes).toBeCloseTo(6)
    expect(complete.accountingMatches).toBe(true)
  })

  it('handles an abandonment only when such an event exists', () => {
    const withAbandon: SimulationTrace = {
      ...trace,
      abandonment_supported: true,
      event_count: 2,
      trace: [
        { t: 0.1, type: 'arrival', segment_id: 0, customer_id: 7, server_id: null, queue_len_after: 1 },
        { t: 0.3, type: 'abandon', segment_id: 0, customer_id: 7, server_id: null, queue_len_after: 0 },
      ],
    }
    const state = derivePlaybackSnapshot(withAbandon, 0.3)
    expect(state.waitingCustomerIds).toEqual([])
    expect(state.abandonedCustomerIds).toEqual([7])
    expect(state.accountingMatches).toBe(true)
  })

  it('steps to the next distinct event time and formats a relative clock', () => {
    expect(nextPlaybackTime(trace, 0)).toBe(0.1)
    expect(nextPlaybackTime(trace, 0.1)).toBe(0.2)
    expect(nextPlaybackTime(trace, 1)).toBe(1)
    expect(formatSimulationTime(1.5)).toBe('01:30:00')
  })

  it('changes playback timing without changing the event timeline', () => {
    expect(advancePlaybackTime(0, 1000, 1, 1)).toBeCloseTo(1 / 60)
    expect(advancePlaybackTime(0, 1000, 1, 10)).toBeCloseTo(1 / 6)
    expect(trace.trace.map((event) => event.t)).toEqual([0.1, 0.1, 0.2, 0.4, 0.4, 0.6])
  })
})
