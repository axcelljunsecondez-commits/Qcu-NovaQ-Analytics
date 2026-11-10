import { describe, expect, it } from 'vitest'
import { busyLevel, formatDataDates } from './results'

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

describe('formatDataDates', () => {
  it('formats a range in UTC and returns null when the dates are unknown', () => {
    expect(formatDataDates({ first: '2026-03-01', last: '2026-03-31', source: 'stored_at_upload' }, 'en-US')).toBe('Mar 1 – Mar 31, 2026')
    expect(formatDataDates({ first: '2025-12-30', last: '2026-01-02', source: 'period_labels' }, 'en-US')).toBe('Dec 30, 2025 – Jan 2, 2026')
    expect(formatDataDates({ first: '2026-03-01', last: '2026-03-01', source: 'stored_at_upload' }, 'en-US')).toBe('Mar 1, 2026')
    expect(formatDataDates(null, 'en-US')).toBeNull()
    expect(formatDataDates({ first: 'x', last: 'y', source: 'stored_at_upload' }, 'en-US')).toBeNull()
  })
})
