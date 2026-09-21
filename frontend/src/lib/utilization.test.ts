import { describe, expect, it } from 'vitest'
import { utilizationBand } from './utilization'

describe('utilizationBand', () => {
  it('places exact boundaries in the band their rule names', () => {
    expect(utilizationBand(0.59999)).toBe('Lean')
    expect(utilizationBand(0.6)).toBe('Normal')
    expect(utilizationBand(0.8)).toBe('Normal')
    expect(utilizationBand(0.80001)).toBe('Peak')
    expect(utilizationBand(0.8999)).toBe('Peak')
    expect(utilizationBand(0.9)).toBe('Critical')
    expect(utilizationBand(0.99999)).toBe('Critical')
    expect(utilizationBand(1)).toBe('Unstable')
    expect(utilizationBand(1.00001)).toBe('Unstable')
  })

  it('ignores float noise from λ / (cμ) at every boundary', () => {
    expect(utilizationBand(0.99 / 1.1)).toBe('Critical') // 0.8999999999999999
    expect(utilizationBand(1.12 / 1.4)).toBe('Normal') // 0.8000000000000002
    expect(utilizationBand(2.01 / 3.35)).toBe('Normal') // 0.5999999999999999
    expect(utilizationBand(3.15 / (3 * 1.05))).toBe('Unstable') // 0.9999999999999999
    expect(utilizationBand(3.45 / (3 * 1.15))).toBe('Unstable') // 1.0000000000000002
  })
})
