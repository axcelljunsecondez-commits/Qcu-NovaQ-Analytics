import { describe, expect, it } from 'vitest'
import { selectPlaybackLayout } from './simulationPlayback'
import type { SimulationTraceEvent, SimulationTraceSegment } from '../api/types'

describe('trace identity (Task 4 widening)', () => {
  it('accepts backend string ids and queue_id', () => {
    const e: SimulationTraceEvent = {
      t: 0.5,
      type: 'service_start',
      segment_id: 'q1-08:00',
      customer_id: 1,
      server_id: 'server:Q1',
      queue_len_after: 0,
      queue_id: 'Q1',
    }
    expect(e.queue_id).toBe('Q1')
    expect(e.server_id).toBe('server:Q1')
    expect(e.segment_id).toBe('q1-08:00')
  })

  it('accepts optional service_time_hours', () => {
    const e: SimulationTraceEvent = {
      t: 0.6,
      type: 'service_end',
      segment_id: 'q1-08:00',
      customer_id: 1,
      server_id: 'server:Q1',
      queue_len_after: 0,
      queue_id: 'Q1',
      service_time_hours: 0.25,
    }
    expect(e.service_time_hours).toBe(0.25)
  })

  it('keeps numeric shared-queue identity backward compatible', () => {
    const e: SimulationTraceEvent = {
      t: 0.1,
      type: 'arrival',
      segment_id: 0,
      customer_id: 2,
      server_id: 0,
      queue_len_after: 1,
    }
    expect(e.server_id).toBe(0)
    expect(e.queue_id).toBeUndefined()
    expect(e.service_time_hours).toBeUndefined()
  })

  it('accepts separate segment identity', () => {
    const s: SimulationTraceSegment = {
      segment_id: 'q1-08:00',
      time: '08:00-09:00',
      lambda: 5,
      mu: 4,
      c: 1,
      selected_model: 'Parallel M/G/1',
      simulation_supported: true,
      error: null,
      queue_structure: 'separate',
      initial_queue_depth: 0,
      final_queue_depth: 0,
    }
    expect(s.queue_structure).toBe('separate')
  })

  it('keeps shared numeric segment identity backward compatible', () => {
    const s: SimulationTraceSegment = {
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
    }
    expect(s.queue_structure).toBe('shared')
  })
})

describe('playback routing (Task 5)', () => {
  it('routes by queue_structure not model_id', () => {
    expect(selectPlaybackLayout('separate')).toBe('separate')
    expect(selectPlaybackLayout('shared')).toBe('shared')
  })

  it('defaults unknown structures to the shared renderer', () => {
    expect(selectPlaybackLayout('unknown')).toBe('shared')
    expect(selectPlaybackLayout('')).toBe('shared')
  })
})
