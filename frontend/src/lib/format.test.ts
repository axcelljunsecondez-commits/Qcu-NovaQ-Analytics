import { describe, expect, it } from 'vitest'
import { fmtDecimal, fmtPctDecimal } from './format'

describe('fmtDecimal', () => {
  it('shows exactly four decimals', () => {
    expect(fmtDecimal(2.4285714285714284)).toBe('2.4286')
    expect(fmtDecimal(2.5)).toBe('2.5000')
    expect(fmtDecimal(0.00004)).toBe('0.0000')
    expect(fmtDecimal(0.00005)).toBe('0.0001')
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
  it('formats a 0-1 ratio as a four-decimal percentage', () => {
    expect(fmtPctDecimal(0.7142857142857143)).toBe('71.4286%')
    expect(fmtPctDecimal(0.705)).toBe('70.5000%')
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
