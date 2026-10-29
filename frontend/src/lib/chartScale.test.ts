import { describe, expect, it } from 'vitest'
import { axisTicks, countTicks, niceMax } from './chartScale'

describe('niceMax', () => {
  it.each([
    [0, 1], [-3, 1], [Number.NaN, 1], [0.07, 0.1], [0.05, 0.05], [0.06, 0.1], [1.4, 2], [2.2, 2.5], [12, 20], [2.5, 2.5], [100, 100],
  ])('%s -> %s', (value, expected) => {
    expect(niceMax(value)).toBeCloseTo(expected, 12)
  })
})

describe('axisTicks', () => {
  it('starts at 0 and ends exactly at the maximum', () => {
    expect(axisTicks(2.5, 5)).toEqual([0, 0.5, 1, 1.5, 2, 2.5])
    expect(axisTicks(0.1, 4).at(-1)).toBe(0.1)
  })
  it('returns only 0 when there is no range', () => {
    expect(axisTicks(0, 4)).toEqual([0])
  })
})

describe('countTicks', () => {
  it('uses whole numbers from 0 to the maximum', () => {
    expect(countTicks(4)).toEqual([0, 1, 2, 3, 4])
    expect(countTicks(12)).toEqual([0, 3, 6, 9, 12])
    expect(countTicks(0)).toEqual([0, 1])
  })
})
