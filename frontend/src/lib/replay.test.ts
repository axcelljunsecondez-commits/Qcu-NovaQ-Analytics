import { describe, expect, it } from 'vitest'
import type { SelectedDesPeriod, SimulationTrace, SimulationTraceEvent } from '../api/types'
import { counterState, deriveSeparateLaneSnapshots } from './simulationPlayback'
import {
  dayOrigin,
  dayPeriods,
  hasBreakEvents,
  inactiveQueueIdsAt,
  mergeDayTrace,
  periodsByDate,
  runTimeFor,
  scheduledBreaks,
  waitingThroughTheDay,
  wallClock,
} from './replay'

function event(t: number, type: SimulationTraceEvent['type'], customer: number | null, queue = 'a'): SimulationTraceEvent {
  return { t, type, segment_id: 's1', customer_id: customer as number, server_id: `server:${queue}`, queue_len_after: 0, queue_id: queue }
}

function trace(events: SimulationTraceEvent[], extra: Partial<SimulationTrace> = {}): SimulationTrace {
  return {
    trace: events, trace_hours: 2, total_hours: 2, event_count: events.length, truncated: false, abandonment_supported: false,
    segments: [{ segment_id: 's1', time: 's1', queue_id: 'a', server_id: 'server:a', lambda: 4, mu: 6, c: 1, selected_model: 'x',
      simulation_supported: true, error: null, queue_structure: 'separate', initial_queue_depth: 0, final_queue_depth: 0 }],
    ...extra,
  }
}

function stateAt(events: SimulationTraceEvent[], hours: number, closed = false) {
  const [lane] = deriveSeparateLaneSnapshots(trace(events), hours)
  return counterState(lane, closed)
}

describe('counter states come from break events only (D26, B5)', () => {
  const events = [
    event(0.1, 'arrival', 1), event(0.2, 'service_start', 1), event(0.5, 'draining_start', null),
    event(0.6, 'service_end', 1), event(0.6, 'break_start', null), event(1.1, 'break_end', null),
  ]

  it.each([
    [0.05, 'available'],
    [0.3, 'serving'],
    [0.55, 'finishing'],
    [0.7, 'on_break'],
    [1.2, 'available'],
  ])('at %s h the counter is %s', (hours, state) => {
    expect(stateAt(events, hours)).toBe(state)
  })

  it('never shows a break for an idle or closed counter without break events', () => {
    const idle = [event(0.1, 'arrival', 1), event(0.2, 'service_start', 1), event(0.3, 'service_end', 1)]
    expect(stateAt(idle, 1)).toBe('available')
    expect(stateAt(idle, 1, true)).toBe('closed')
    expect(stateAt(idle, 0.25, true)).toBe('serving')
  })

  it('keeps arrived = waiting + serving + served after every event', () => {
    const busy = [
      event(0.1, 'arrival', 1), event(0.15, 'arrival', 2), event(0.2, 'service_start', 1), event(0.3, 'draining_start', null),
      event(0.35, 'service_end', 1), event(0.36, 'service_start', 2), event(0.5, 'service_end', 2), event(0.5, 'break_start', null),
      event(0.9, 'break_end', null), event(1.0, 'arrival', 3),
    ]
    for (const item of busy) {
      const [lane] = deriveSeparateLaneSnapshots(trace(busy), item.t)
      const serving = Object.keys(lane.servingByServer).length
      expect(lane.arrived).toBe(lane.waitingCustomerIds.length + serving + lane.servedCustomerIds.length + lane.abandonedCustomerIds.length)
    }
  })

  it('reports whether a run recorded any break', () => {
    expect(hasBreakEvents(trace(events))).toBe(true)
    expect(hasBreakEvents(trace([event(0.1, 'arrival', 1)]))).toBe(false)
  })
})

function period(time: string, start: number, events: SimulationTraceEvent[], inactive: string[] = []): SelectedDesPeriod {
  return {
    time, active_queue_ids: ['a', 'b'].filter((q) => !inactive.includes(q)), inactive_queue_ids: inactive, evaluation_status: 'FEASIBLE',
    conservation: true, total_lambda: 1, total_cost: null, server_cost: null, waiting_cost: null, results: [],
    trace: trace(events, { total_hours: 3 }), start_hours: start, duration_hours: 1,
  }
}

describe('full-day replay (one continuous execution)', () => {
  // A customer of the first period is still being served in the second: their events are filed
  // under the period they arrived in, so a plain concatenation is not in time order.
  const first = [event(0.2, 'arrival', 1), event(0.3, 'service_start', 1), event(1.4, 'service_end', 1)]
  const second = [{ ...event(1.1, 'arrival', 2, 'b'), segment_id: 's2' }, { ...event(1.2, 'service_start', 2, 'b'), segment_id: 's2' }]
  const periods = [period('s1', 0, first), period('s2', 1, second, ['a'])]

  it('equals the concatenation of the periods\' events in time order', () => {
    const day = mergeDayTrace(periods)!
    expect(day.trace.map((item) => item.t)).toEqual([0.2, 0.3, 1.1, 1.2, 1.4])
    expect(new Set(day.trace)).toEqual(new Set([...first, ...second]))
    expect(day.event_count).toBe(5)
    expect(day.total_hours).toBe(3)
  })

  it('is not built for runs that are not one continuous day', () => {
    expect(mergeDayTrace([{ ...periods[0], start_hours: undefined }])).toBeNull()
    expect(mergeDayTrace([])).toBeNull()
  })

  it('keeps any truncation of the run', () => {
    const cut = [period('s1', 0, first), { ...period('s2', 1, second), trace: trace(second, { truncated: true }) }]
    expect(mergeDayTrace(cut)!.truncated).toBe(true)
  })

  it('closes counters by the staffing of the period that contains the time', () => {
    expect(inactiveQueueIdsAt(periods, 0.5)).toEqual([])
    expect(inactiveQueueIdsAt(periods, 1)).toEqual(['a'])
    expect(inactiveQueueIdsAt(periods, 2.5)).toEqual(['a'])
  })

  it('counts people waiting through the day from the events', () => {
    const points = waitingThroughTheDay(mergeDayTrace(periods)!, 0.25)
    expect(points.find((point) => point.hours === 0.25)?.waiting).toBe(1)
    expect(points.find((point) => point.hours === 0.5)?.waiting).toBe(0)
  })
})

describe('store clock and scheduled breaks', () => {
  const setup = {
    segments: [{ id: 'b', start_time: '09:00:00', end_time: '10:00:00', active_queue_ids: null }, { id: 'a', start_time: '08:30', end_time: '09:00', active_queue_ids: null }],
    breaks: [{ queue_id: 'a', scheduled_start_time: '09:15', duration_minutes: 30 }, { queue_id: 'b', scheduled_start_time: 'later', duration_minutes: 10 }],
  }

  it('starts the day at the earliest segment and converts both ways', () => {
    expect(dayOrigin(setup)).toBe(510)
    expect(wallClock(510, 1.25)).toBe('09:45')
    expect(runTimeFor(510, '09:45')).toBe(1.25)
    expect(runTimeFor(510, '08:00')).toBeNull()
    expect(runTimeFor(510, '25:00')).toBeNull()
  })

  it('places setup breaks on the run clock and skips malformed ones', () => {
    expect(scheduledBreaks(setup)).toEqual([{ queueId: 'a', startHours: 0.75, endHours: 1.25, name: null }])
    expect(scheduledBreaks({ segments: [], breaks: setup.breaks })).toEqual([])
  })
})

describe('per-date days (B13)', () => {
  const period = (time: string) => ({ time } as SelectedDesPeriod)
  const periods = ['2026-09-08 s1 UTC', '2026-09-08 s2 UTC', '2026-09-09 s1 UTC', '2026-09-09 s2 UTC'].map(period)

  it('groups a per-date run by the date that starts each label, in order', () => {
    expect(periodsByDate(periods).map((group) => [group.date, group.periods.map((item) => item.time)])).toEqual([
      ['2026-09-08', ['2026-09-08 s1 UTC', '2026-09-08 s2 UTC']],
      ['2026-09-09', ['2026-09-09 s1 UTC', '2026-09-09 s2 UTC']],
    ])
  })

  it('picks the chosen date, else the first, and keeps a representative day whole', () => {
    expect(dayPeriods(periods, true, '2026-09-09').periods.map((item) => item.time)).toEqual(['2026-09-09 s1 UTC', '2026-09-09 s2 UTC'])
    expect(dayPeriods(periods, true, 'not-a-date')).toMatchObject({ date: '2026-09-08', dates: ['2026-09-08', '2026-09-09'] })
    expect(dayPeriods(periods, false, '2026-09-09')).toEqual({ date: null, dates: [], periods })
  })
})
