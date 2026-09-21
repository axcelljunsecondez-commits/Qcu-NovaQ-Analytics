import { describe, expect, it } from 'vitest'
import { fmtDecimal, fmtPctDecimal } from './format'

describe('fmtDecimal', () => {
  it('rounds to four decimals', () => {
    expect(fmtDecimal(2.4285714285714284)).toBe('2.4286')
    expect(fmtDecimal(0.00004)).toBe('0.0000')
    expect(fmtDecimal(0.00005)).toBe('0.0001')
  })

  it('drops trailing zeros only when the shorter number is exact', () => {
    expect(fmtDecimal(2.5)).toBe('2.5')
    expect(fmtDecimal(89.51)).toBe('89.51')
    expect(fmtDecimal(0.8951 * 100)).toBe('89.51')
    expect(fmtDecimal(70.49)).toBe('70.49')
    // Rounding happened, so the zeros stay: the value is not exactly 89.51 or 72.5.
    expect(fmtDecimal(89.510002)).toBe('89.5100')
    expect(fmtDecimal(72.50004)).toBe('72.5000')
    expect(fmtDecimal(72.49996)).toBe('72.5000')
  })

  it('drops the decimals only for true whole numbers', () => {
    expect(fmtDecimal(3)).toBe('3')
    expect(fmtDecimal(2.99996)).toBe('3.0000')
    expect(fmtDecimal(3.00004)).toBe('3.0000')
    expect(fmtDecimal(28.999999999999996)).toBe('29')
    expect(fmtDecimal(10)).toBe('10')
    expect(fmtDecimal(0)).toBe('0')
    expect(fmtDecimal(-0.00001)).toBe('0.0000')
    expect(fmtDecimal(-0)).toBe('0')
  })

  it('returns a dash for missing values', () => {
    expect(fmtDecimal(null)).toBe('—')
    expect(fmtDecimal(undefined)).toBe('—')
    expect(fmtDecimal(Number.NaN)).toBe('—')
    expect(fmtDecimal(Number.POSITIVE_INFINITY)).toBe('—')
  })
})

describe('fmtPctDecimal', () => {
  it('formats a 0-1 ratio as a percentage with up to four decimals', () => {
    expect(fmtPctDecimal(0.7142857142857143)).toBe('71.4286%')
    expect(fmtPctDecimal(0.705)).toBe('70.5%')
    expect(fmtPctDecimal(0.8951)).toBe('89.51%')
    // Real ρ just under the 90% Critical line never shows as "90%".
    expect(fmtPctDecimal(0.8999996)).toBe('90.0000%')
    expect(fmtPctDecimal(0.8999999999999999)).toBe('90%')
    expect(fmtPctDecimal(0.5)).toBe('50%')
    expect(fmtPctDecimal(0.29)).toBe('29%')
    expect(fmtPctDecimal(1)).toBe('100%')
    expect(fmtPctDecimal(0)).toBe('0%')
  })

  it('returns a dash for missing values', () => {
    expect(fmtPctDecimal(null)).toBe('—')
    expect(fmtPctDecimal(Number.NaN)).toBe('—')
  })
})
