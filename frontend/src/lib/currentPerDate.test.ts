import { describe, expect, it } from 'vitest'
import type { RunSummary, SimulationTrace } from '../api/types'
import {
  CURRENT_COMPACT_EXECUTION,
  chosenCurrentDate,
  compactDates,
  dateCsvName,
  dayDetailErrorKey,
  isCompactCurrent,
  rowsForDate,
  shownSeed,
  summaryForDate,
  tooLargeDates,
  zeroArrivalCount,
} from './currentPerDate'

// A6 helpers for per-date separate-lines Current runs (C-PD, C-PD-C). SYNTHETIC values.

const base: SimulationTrace = { trace: [], trace_hours: 1, total_hours: 2, event_count: 0, truncated: false, abandonment_supported: false, segments: [] }
const day = (date: string) => ({ date, arrivals: 1, served: 1, waiting_at_close: 0, in_service_at_close: 0, customer_conservation: true, day_hours: 2 })
const compact: SimulationTrace = {
  ...base, execution: CURRENT_COMPACT_EXECUTION, days: [day('2000-01-03'), day('2000-01-04')], seed_used: 77,
  zero_arrival_lane_periods: [
    { date: '2000-01-04', time: '2000-01-04 s2 UTC', segment_id: 's2', queue_id: 'c2' },
    { date: '2000-01-04', time: '2000-01-04 s1 UTC', segment_id: 's1', queue_id: 'c1' },
    { date: '2000-01-03', time: '2000-01-03 s1 UTC', segment_id: 's1', queue_id: 'c1' },
  ],
}
const httpError = (status: number, detail?: unknown) => ({ response: { status, data: { detail } } })

describe('compact detection and dates', () => {
  it('recognizes only the compact execution with days', () => {
    expect(isCompactCurrent(compact)).toBe(true)
    expect(isCompactCurrent({ ...compact, execution: 'current_per_date_days' })).toBe(false)
    expect(isCompactCurrent({ ...compact, days: undefined })).toBe(false)
    expect(isCompactCurrent(base)).toBe(false)
    expect(isCompactCurrent(null)).toBe(false)
    expect(isCompactCurrent(undefined)).toBe(false)
  })

  it('lists the dates in the server order and chooses the requested one only when the run has it', () => {
    const dates = compactDates(compact)
    expect(dates).toEqual(['2000-01-03', '2000-01-04'])
    expect(chosenCurrentDate(dates, '2000-01-04')).toBe('2000-01-04')
    expect(chosenCurrentDate(dates, '1999-12-31')).toBe('2000-01-03')
    expect(chosenCurrentDate(dates, null)).toBe('2000-01-03')
    expect(chosenCurrentDate([], '2000-01-03')).toBeNull()
    expect(compactDates(base)).toEqual([])
  })
})

describe('one date of the stored rows and summary', () => {
  it('keeps the rows of that date only', () => {
    const rows = [{ date: '2000-01-03', n: 1 }, { date: '2000-01-04', n: 2 }, { n: 3 }, { date: '2000-01-03', n: 4 }]
    expect(rowsForDate(rows, '2000-01-03').map((row) => row.n)).toEqual([1, 4])
  })

  it('keeps only the periods labelled with that date and leaves the totals as the server sent them', () => {
    const summary: RunSummary = {
      basis: 'per_period', average_wait_hours: 0.1, longest_line: 9, arrivals: null, served: null, in_system_at_close: null,
      periods: ['2000-01-03 s1 UTC', '2000-01-04 s1 UTC', 's2', '2000-01-033 s1 UTC'].map((time) => (
        { time, average_wait_hours: 0.1, longest_line: 1, arrivals: null, served: null })),
    }
    const one = summaryForDate(summary, '2000-01-03')
    expect(one.periods.map((period) => period.time)).toEqual(['2000-01-03 s1 UTC'])
    expect({ ...one, periods: [] }).toEqual({ ...summary, periods: [] })
    expect(summary.periods).toHaveLength(4)
  })

  it('counts the zero-arrival periods of one date, or all of them without a date', () => {
    expect(zeroArrivalCount(compact, '2000-01-04')).toBe(2)
    expect(zeroArrivalCount(compact, '2000-01-03')).toBe(1)
    expect(zeroArrivalCount(compact, '1999-12-31')).toBe(0)
    expect(zeroArrivalCount(compact, null)).toBe(3)
    expect(zeroArrivalCount(base, null)).toBe(0)
  })

  it('names the CSV file after the date', () => {
    expect(dateCsvName('2000-01-03')).toBe('novaq_unified_des_2000-01-03.csv')
  })
})

describe('seed shown', () => {
  it('shows the requested seed, else the seed the server drew, else none', () => {
    expect(shownSeed({ seed: 5 }, compact)).toBe(5)
    expect(shownSeed({ seed: 0 }, compact)).toBe(0)
    expect(shownSeed({ seed: null }, compact)).toBe(77)
    expect(shownSeed(undefined, compact)).toBe(77)
    expect(shownSeed({ seed: null }, base)).toBeNull()
    expect(shownSeed({ seed: '5' }, null)).toBeNull()
  })
})

describe('server errors', () => {
  it('reads the date count of a 413 from the placeholder and from the drafted English detail', () => {
    expect(tooLargeDates(httpError(413, 'PLACEHOLDER: per-date Current result too large (14 dates, 1253317 bytes, limit 524288 bytes).'))).toBe(14)
    expect(tooLargeDates(httpError(413, 'This Current run is too large to save: it covers 26 dates. Upload a file with fewer dates.'))).toBe(26)
  })

  it('reads nothing from another status, a detail without a count, or no response', () => {
    expect(tooLargeDates(httpError(413, 'Workflow evidence is too large. Reduce the playback event cap.'))).toBeNull()
    expect(tooLargeDates(httpError(413, undefined))).toBeNull()
    expect(tooLargeDates(httpError(422, 'Date 2000-01-03 has no records (3 dates).'))).toBeNull()
    expect(tooLargeDates(new Error('Network Error'))).toBeNull()
    expect(tooLargeDates(null)).toBeNull()
  })

  it('maps a day-detail failure to its message key', () => {
    expect(dayDetailErrorKey(httpError(404))).toBe('simulation.current_day_not_found')
    expect(dayDetailErrorKey(httpError(409))).toBe('simulation.current_day_mismatch')
    expect(dayDetailErrorKey(httpError(429))).toBe('errors.server')
    expect(dayDetailErrorKey(httpError(500))).toBe('errors.server')
    expect(dayDetailErrorKey(new Error('Network Error'))).toBe('errors.server')
    expect(dayDetailErrorKey(undefined)).toBe('errors.server')
  })
})
