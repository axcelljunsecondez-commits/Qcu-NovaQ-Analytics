import { describe, it, expect } from 'vitest'
import { computeRoi, clampHolidays } from './roi'

describe('computeRoi', () => {
  it('computes daily, monthly and annual savings with Sundays and holidays off', () => {
    const roi = computeRoi({ currentTotal: 5000, optimalTotal: 3000, holidays: 12, closedSundays: true })
    expect(roi.dailySavings).toBe(2000)
    expect(roi.workingDaysPerYear).toBe(301)
    expect(roi.annualSavings).toBe(602000)
    expect(roi.monthlySavings).toBeCloseTo(602000 / 12)
  })

  it('includes Sundays as working days when the store is open', () => {
    const open = computeRoi({ currentTotal: 1000, optimalTotal: 500, holidays: 12, closedSundays: false })
    const closed = computeRoi({ currentTotal: 1000, optimalTotal: 500, holidays: 12, closedSundays: true })
    expect(open.workingDaysPerYear).toBe(353)
    expect(closed.workingDaysPerYear).toBe(301)
    expect(open.annualSavings).toBe(500 * 353)
    expect(closed.annualSavings).toBe(500 * 301)
  })

  it('handles zero savings and zero holidays', () => {
    const roi = computeRoi({ currentTotal: 100, optimalTotal: 100, holidays: 0, closedSundays: true })
    expect(roi.dailySavings).toBe(0)
    expect(roi.annualSavings).toBe(0)
    expect(roi.workingDaysPerYear).toBe(313)
  })
})

describe('clampHolidays', () => {
  it('clamps typed values to the 0-365 range', () => {
    expect(clampHolidays(400)).toBe(365)
    expect(clampHolidays(-5)).toBe(0)
    expect(clampHolidays(12.4)).toBe(12)
  })

  it('treats non-finite input as zero', () => {
    expect(clampHolidays(Number.NaN)).toBe(0)
    expect(clampHolidays(Number.POSITIVE_INFINITY)).toBe(0)
  })
})