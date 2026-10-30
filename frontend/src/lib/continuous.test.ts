import { describe, expect, it } from 'vitest'
import type { ContinuousEvent, ContinuousRunListItem } from '../api/continuous'
import { automaticReplications, clockAt, clockOfMinutes, hoursAt, latestRunIds, rangeText, stateAt, waitingSteps } from './continuous'

describe('automatic full-day request budget', () => {
  const limits = { max_replications: 9, max_expected_customers_per_run: 2900 }

  it.each([
    [107.5, 5], [580, 5], [580.0000000000001, 4], [600, 4], [2900, 1], [2900.01, 0], [0, 5],
  ])('fits whole replications for %s expected customers per day', (expected, count) => {
    expect(automaticReplications(expected, 5, limits)).toBe(count)
  })

  it('retains a smaller server default and respects a smaller server maximum', () => {
    expect(automaticReplications(100, 2, limits)).toBe(2)
    expect(automaticReplications(100, 5, { ...limits, max_replications: 3 })).toBe(3)
  })

  it.each([null, NaN, Infinity, -1])('does not treat unknown or invalid demand %s as zero', (expected) => {
    expect(automaticReplications(expected, 5, limits)).toBeNull()
  })

  it('refuses invalid defaults and server limits', () => {
    expect(automaticReplications(100, 0, limits)).toBeNull()
    expect(automaticReplications(100, 1.5, limits)).toBeNull()
    expect(automaticReplications(100, 5, { ...limits, max_replications: 0 })).toBeNull()
    expect(automaticReplications(100, 5, { ...limits, max_expected_customers_per_run: NaN })).toBeNull()
  })
})

const event = (seq: number, t: number, type: string, waiting: number, busy: number, idle: number, draining = 0): ContinuousEvent => ({
  seq, t, type, queue_len_after: waiting, servers_busy_after: busy, servers_idle_after: idle, servers_draining_after: draining,
})
const events = [
  event(0, 0, 'server_open', 0, 0, 1),
  event(1, 0.5, 'arrival', 1, 0, 1),
  event(2, 0.5, 'service_start', 0, 1, 0),
  event(3, 0.7, 'arrival', 1, 1, 0),
  event(4, 1, 'closing', 1, 0, 0, 1),
  event(5, 1.1, 'service_end', 1, 0, 0, 1),
  event(6, 1.1, 'unserved_at_close', 0, 0, 0, 1),
]

describe('full-day replay helpers (B4a)', () => {
  it('reads the line and counters after the last event at or before a time', () => {
    expect(stateAt(events, 0.4)).toMatchObject({ waiting: 0, serving: 0, idle: 1, arrived: 0, served: 0 })
    expect(stateAt(events, 0.5)).toMatchObject({ waiting: 0, serving: 1, idle: 0, arrived: 1 })
    expect(stateAt(events, 0.8)).toMatchObject({ waiting: 1, serving: 1, arrived: 2, served: 0 })
    expect(stateAt(events, 1)).toMatchObject({ waiting: 1, serving: 0, draining: 1 })
    expect(stateAt(events, 2)).toMatchObject({ waiting: 0, served: 1, unserved: 1, arrived: 2 })
    expect(stateAt(events, 2).event?.seq).toBe(6)
  })

  it('reads counters on break and breaks waiting, and zero for runs without breaks (B4c)', () => {
    const withBreaks: ContinuousEvent[] = [
      event(0, 0, 'server_open', 0, 0, 1),
      { ...event(1, 0.5, 'break_due', 0, 1, 0), servers_on_break_after: 0, breaks_waiting_after: 1 },
      { ...event(2, 0.75, 'break_start', 0, 0, 0), servers_on_break_after: 1, breaks_waiting_after: 0 },
    ]
    expect(stateAt(withBreaks, 0.6)).toMatchObject({ onBreak: 0, breaksWaiting: 1, serving: 1 })
    expect(stateAt(withBreaks, 0.8)).toMatchObject({ onBreak: 1, breaksWaiting: 0, serving: 0 })
    expect(stateAt(events, 0.5)).toMatchObject({ onBreak: 0, breaksWaiting: 0 })
  })

  it('draws people waiting from every recorded event, never sampled', () => {
    expect(waitingSteps(events).map((step) => [step.hours, step.waiting])).toEqual([[0, 0], [0.5, 1], [0.5, 0], [0.7, 1], [1, 1], [1.1, 1], [1.1, 0]])
  })

  it('keeps the newest run of each staffing source', () => {
    const run = (id: number, plan: 'current' | 'suggested') => ({ id, plan }) as ContinuousRunListItem
    expect(latestRunIds([run(9, 'suggested'), run(8, 'current'), run(5, 'suggested'), run(4, 'current')])).toEqual({ suggested: 9, current: 8 })
    expect(latestRunIds([run(3, 'current')])).toEqual({ current: 3 })
  })

  it('maps the store clock to run time and back', () => {
    expect(clockOfMinutes(480)).toBe('08:00')
    expect(clockAt(480, 1.55)).toBe('09:33')
    expect(hoursAt(480, '09:33')).toBeCloseTo(1.55, 9)
    expect(hoursAt(480, '07:59')).toBeNull()
    expect(hoursAt(480, '25:00')).toBeNull()
    expect(hoursAt(480, 'nine')).toBeNull()
  })

  it('writes a mean with its lowest and highest day, and nothing when the mean is undefined', () => {
    const format = (value: number) => value.toFixed(1)
    expect(rangeText({ mean: 2, min: 1, max: 3, n: 3, n_undefined: 0, ci_lower: null, ci_upper: null }, format)).toBe('2.0 (1.0–3.0)')
    expect(rangeText({ mean: 0.5, min: 0.5, max: 0.5, n: 3, n_undefined: 0, ci_lower: null, ci_upper: null }, format, 60)).toBe('30.0')
    expect(rangeText({ mean: null, min: null, max: null, n: 0, n_undefined: 3, ci_lower: null, ci_upper: null }, format)).toBeNull()
    expect(rangeText(undefined, format)).toBeNull()
  })
})
