import { describe, expect, it } from 'vitest'
import { comparisonTotals, completeFiniteAverage, completeFiniteTotal } from './comparison'
import { fmt, fmtFrCi, fmtPct } from './format'
import type { OptimizationOut } from '../api/types'

const completeRow = {
  time: 't',
  c_current: 1,
  c_optimal: 1,
  rho_current: 0,
  rho_optimal: 0,
  Wq_optimal: 0,
  Lq_optimal: 0,
  current_stable: true,
  optimized_stable: true,
  cost_current: 0,
  cost_optimal: 0,
} as OptimizationOut

describe('missing analytical value contract', () => {
  it('keeps genuine zero distinct from null, undefined, NaN, and infinity in formatting', () => {
    expect(fmt(0)).toBe('0.00')
    expect(fmtPct(0)).toBe('0%')
    expect(fmt(null)).toBe('—')
    expect(fmt(undefined)).toBe('—')
    expect(fmt(Number.NaN)).toBe('—')
    expect(fmt(Number.POSITIVE_INFINITY)).toBe('—')
    expect(fmtPct(Number.NEGATIVE_INFINITY)).toBe('—')
    expect(fmtFrCi(0, 0)).toBe('0%–0%')
    expect(fmtFrCi(null, 0)).toBe('—')
  })

  it('does not compute a complete average or total when any source value is unavailable', () => {
    expect(completeFiniteAverage([0, 0])).toBe(0)
    expect(completeFiniteTotal([0, 0])).toBe(0)
    for (const unavailable of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(completeFiniteAverage([0, unavailable])).toBeNull()
      expect(completeFiniteTotal([0, unavailable])).toBeNull()
    }
  })

  it('keeps an all-zero complete comparison valid but rejects a missing cost as incomplete', () => {
    expect(comparisonTotals([completeRow])).toEqual({ current: 0, optimal: 0, savings: 0 })
    expect(comparisonTotals([{ ...completeRow, cost_current: null }])).toBeNull()
  })
})
