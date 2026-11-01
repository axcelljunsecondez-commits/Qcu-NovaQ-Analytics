import { describe, expect, it } from 'vitest'
import type { SimMcOut } from '../api/types'
import { agreedValue, highestRiskIndex, mcAxisMax, mcPeriods, mcRangeText, storedMcParameters } from './manyVariations'

function row(time: string, queue: string | null, failure: number, extra: Partial<SimMcOut> = {}): SimMcOut {
  return { time, queue_id: queue, lambda: 2, mu: 3, c: 1, rho_mean: 0.5, rho_std: 0.05, rho_p95: 0.6, Lq_mean: 0.2, Wq_mean: 0.05,
    failure_rate: failure, failure_count: 0, status: 'PASS', error: null, ci_Wq_hw: 0.01, ci_Lq_hw: 0.01, adequate_samples: true,
    failure_rate_ci_lower: 0, failure_rate_ci_upper: failure + 0.0019, num_trials: 2000, failure_threshold: 0.85, failure_rate_cap: 0.05,
    arrival_noise_fraction: 0.2, service_noise_fraction: 0.1, ...extra }
}

describe('stored Many variations parameters', () => {
  it('reads trials, threshold and cap from the stored rows', () => {
    expect(storedMcParameters([row('a', 'c1', 0), row('b', 'c1', 0)])).toEqual({ trials: 2000, threshold: 0.85, cap: 0.05, explainable: true })
  })

  it('is UNKNOWN (null) when rows disagree or a value is missing, and then cannot be explained', () => {
    const params = storedMcParameters([row('a', 'c1', 0), row('b', 'c1', 0, { failure_threshold: 0.75 })])
    expect(params.threshold).toBeNull()
    expect(params.explainable).toBe(false)
    expect(storedMcParameters([row('a', 'c1', 0, { num_trials: undefined })]).trials).toBeNull()
    expect(agreedValue([], (item) => item.num_trials)).toBeNull()
  })

  it('cannot explain a run whose noise differs from the method text', () => {
    expect(storedMcParameters([row('a', 'c1', 0, { arrival_noise_fraction: 0.3 })]).explainable).toBe(false)
    // Rows without the noise fields use the engine constants the text states.
    expect(storedMcParameters([row('a', 'c1', 0, { arrival_noise_fraction: undefined, service_noise_fraction: undefined })]).explainable).toBe(true)
  })
})

describe('highest risk per period', () => {
  it('picks the highest failure rate, then the higher upper bound, then the queue id', () => {
    const periods = mcPeriods([
      row('08:00', 'c2', 0.01), row('08:00', 'c1', 0.03),
      row('09:00', 'c2', 0, { failure_rate_ci_upper: 0.002 }), row('09:00', 'c1', 0, { failure_rate_ci_upper: 0.004 }),
      row('10:00', 'c2', 0, { failure_rate_ci_upper: 0.002 }), row('10:00', 'c1', 0, { failure_rate_ci_upper: 0.002 }),
    ])
    expect(periods.map((period) => [period.time, period.worst.queue_id])).toEqual([['08:00', 'c1'], ['09:00', 'c1'], ['10:00', 'c1']])
    expect(periods[0].all).toHaveLength(2)
  })

  it('keeps one row per period for a shared line', () => {
    const periods = mcPeriods([row('08:00', null, 0.02), row('09:00', null, 0.04)])
    expect(periods).toHaveLength(2)
    expect(highestRiskIndex(periods)).toBe(1)
  })

  it('takes the first period on a tie and -1 when nothing has a rate', () => {
    expect(highestRiskIndex(mcPeriods([row('a', null, 0.02), row('b', null, 0.02)]))).toBe(0)
    expect(highestRiskIndex(mcPeriods([row('a', null, Number.NaN)]))).toBe(-1)
  })
})

describe('axis and range text', () => {
  it('covers the cap and every upper bound, from 0', () => {
    expect(mcAxisMax(mcPeriods([row('a', null, 0.003)]), 0.05)).toBe(0.05)
    expect(mcAxisMax(mcPeriods([row('a', null, 0.07, { failure_rate_ci_upper: 0.09 })]), 0.05)).toBe(0.1)
  })

  it('prints both bounds with the decimal rule (0.19%, never 0%)', () => {
    expect(mcRangeText(row('a', null, 0, { failure_rate_ci_lower: 0, failure_rate_ci_upper: 0.0019 }))).toBe('0% – 0.19%')
    expect(mcRangeText(row('a', null, 0, { failure_rate_ci_upper: undefined }))).toBeNull()
  })
})
