import { describe, expect, it } from 'vitest'
import { groupPeriodDemand, pickLeanPeriod, pickPeakPeriod } from './periodDemand'

describe('period demand summarization', () => {
  it('sums arrival rates within a period without touching queue identity', () => {
    const demands = groupPeriodDemand([
      { time: '05:00-06:00', value: 10 },
      { time: '06:00-07:00', value: 6 },
      { time: '06:00-07:00', value: 6 },
    ])
    expect(demands).toEqual([
      { time: '05:00-06:00', totalLambda: 10, queueCount: 1 },
      { time: '06:00-07:00', totalLambda: 12, queueCount: 2 },
    ])
    expect(pickPeakPeriod(demands)?.time).toBe('06:00-07:00')
    expect(pickLeanPeriod(demands)?.time).toBe('05:00-06:00')
  })

  it('handles an arbitrary queue count in one period', () => {
    const demands = groupPeriodDemand([
      { time: '08:00', value: 3 },
      { time: '08:00', value: 3 },
      { time: '08:00', value: 3 },
      { time: '08:00', value: 3 },
    ])
    expect(demands).toEqual([{ time: '08:00', totalLambda: 12, queueCount: 4 }])
  })

  it('resolves ties deterministically to the first period in row order', () => {
    const demands = groupPeriodDemand([
      { time: '08:00', value: 12 },
      { time: '09:00', value: 12 },
    ])
    expect(pickPeakPeriod(demands)?.time).toBe('08:00')
    expect(pickLeanPeriod(demands)?.time).toBe('08:00')
  })

  it('lets a zero-demand period qualify as leanest without fabrication', () => {
    const demands = groupPeriodDemand([
      { time: '08:00', value: 5 },
      { time: '09:00', value: 0 },
    ])
    expect(pickLeanPeriod(demands)).toEqual({ time: '09:00', totalLambda: 0, queueCount: 1 })
    expect(pickPeakPeriod(demands)?.time).toBe('08:00')
  })

  it('returns unavailable when there is nothing to summarize', () => {
    expect(groupPeriodDemand([])).toEqual([])
    expect(pickPeakPeriod([])).toBeNull()
    expect(pickLeanPeriod([])).toBeNull()
  })
})
