import { describe, expect, it } from 'vitest'
import { busyLevel, dayStrip, formatDataDates, periodWarnings, periodsNeedingAttention } from './results'

describe('busyLevel', () => {
  it('uses NovaQ fixed levels and treats an unstable row at or over capacity as can\'t keep up', () => {
    expect(busyLevel({ rho: 0.59, stable: true })).toBe('Lean')
    expect(busyLevel({ rho: 0.8, stable: true })).toBe('Normal')
    expect(busyLevel({ rho: 0.85, stable: true })).toBe('Peak')
    expect(busyLevel({ rho: 0.9, stable: true })).toBe('Critical')
    expect(busyLevel({ rho: 1.2, stable: false })).toBe('Unstable')
    expect(busyLevel({ rho: 0.9999999999999999, stable: false })).toBe('Unstable') // 3.15 / (3 x 1.05) is rho = 1
    expect(busyLevel({ rho: null, stable: true })).toBeNull()
  })

  it('leaves the level unknown for a row that failed below capacity (OD-N2)', () => {
    // e.g. "M/G/c/K approximation exceeds finite-capacity bounds." at rho 0.49: not overloaded, not calculated
    expect(busyLevel({ rho: 0.49, stable: false })).toBeNull()
    expect(busyLevel({ rho: null, stable: false })).toBeNull()
  })
})

describe('periodsNeedingAttention', () => {
  it('lists can\'t-keep-up periods first and then the highest estimated wait among the rest', () => {
    const result = periodsNeedingAttention([
      { time: '08:00', Wq: 0.2, stable: true },
      { time: '09:00', Wq: null, rho: 1.1, stable: false },
      { time: '10:00', Wq: 0.5, stable: true, queue_id: 'B' },
      { time: '11:00', Wq: 9, rho: 1.3, stable: false },
      { time: '12:00', Wq: null, rho: 0.49, stable: false },
    ])
    expect(result.cantKeepUp.map((item) => item.time)).toEqual(['09:00', '11:00'])
    expect(result.highestWait).toEqual({ time: '10:00', line: 'B', waitHours: 0.5 })
  })

  it('has no highest wait when no period has a finite estimate', () => {
    expect(periodsNeedingAttention([{ time: '08:00', Wq: null, stable: true }]).highestWait).toBeNull()
  })
})

describe('dayStrip', () => {
  it('keeps upload order and takes the busiest line of each period', () => {
    const strip = dayStrip([
      { time: '08:00', queue_id: 'A', rho: 0.5, stable: true },
      { time: '08:00', queue_id: 'B', rho: 0.95, stable: true },
      { time: '07:00', queue_id: 'A', rho: 0.7, stable: true },
      { time: '07:00', queue_id: 'B', rho: 1.05, stable: false },
      { time: '09:00', queue_id: 'A', rho: 0.92, stable: true },
      { time: '09:00', queue_id: 'B', rho: 0.3, stable: true },
    ])
    expect(strip).toEqual([
      { time: '08:00', level: 'Critical', rho: 0.95, lines: 2 },
      { time: '07:00', level: 'Unstable', rho: 1.05, lines: 2 },
      { time: '09:00', level: 'Critical', rho: 0.92, lines: 2 },
    ])
  })

  it('does not raise a period to Unstable for a line that failed below capacity (OD-N2)', () => {
    expect(dayStrip([
      { time: '07:00', queue_id: 'A', rho: 0.7, stable: true },
      { time: '07:00', queue_id: 'B', rho: 0.4, stable: false },
    ])).toEqual([{ time: '07:00', level: 'Normal', rho: 0.7, lines: 2 }])
  })
})

describe('periodWarnings', () => {
  const strip = [
    { time: 'a', level: 'Normal' as const, rho: 0.75, lines: 1 },
    { time: 'b', level: 'Critical' as const, rho: 0.92, lines: 1 },
    { time: 'c', level: 'Lean' as const, rho: 0.3, lines: 1 },
  ]

  it('flags plan targets only when a plan is selected', () => {
    expect(periodWarnings(strip, null)).toEqual([{ time: 'b', level: 'Critical', aboveTarget: false }])
    expect(periodWarnings(strip, 0.7)).toEqual([
      { time: 'a', level: 'Normal', aboveTarget: true },
      { time: 'b', level: 'Critical', aboveTarget: true },
    ])
  })
})

describe('formatDataDates', () => {
  it('formats a range in UTC and returns null when the dates are unknown', () => {
    expect(formatDataDates({ first: '2026-03-01', last: '2026-03-31', source: 'stored_at_upload' }, 'en-US')).toBe('Mar 1 – Mar 31, 2026')
    expect(formatDataDates({ first: '2025-12-30', last: '2026-01-02', source: 'period_labels' }, 'en-US')).toBe('Dec 30, 2025 – Jan 2, 2026')
    expect(formatDataDates({ first: '2026-03-01', last: '2026-03-01', source: 'stored_at_upload' }, 'en-US')).toBe('Mar 1, 2026')
    expect(formatDataDates(null, 'en-US')).toBeNull()
    expect(formatDataDates({ first: 'x', last: 'y', source: 'stored_at_upload' }, 'en-US')).toBeNull()
  })
})
