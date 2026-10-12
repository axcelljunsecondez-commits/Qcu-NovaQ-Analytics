import { describe, expect, it } from 'vitest'
import type { AnalysisOut } from '../api/types'
import { inputProblems, modelFor, neighbourCounters, requestFor, summarize, type CalculatorInputs } from './quickCalculator'

const inputs = (over: Partial<CalculatorInputs> = {}): CalculatorInputs => ({
  lambda: 40, mu: 15, c: 3, spreadMinutes: null, capacity: null, patienceMinutes: null, ...over,
})
const result = (over: Partial<AnalysisOut> = {}): AnalysisOut => ({
  rho: 0.8889, L: 9.05, Lq: 6.38, W: 0.226, Wq: 0.1595, stable: true, error: null, ...over,
})

describe('quick calculator logic (U9)', () => {
  it('maps each situation onto NovaQ\'s explicit models; one basic counter is M/M/1', () => {
    expect(modelFor('basic', inputs(), 1)).toBe('mm1')
    expect(modelFor('basic', inputs(), 3)).toBe('mmc')
    expect(modelFor('variable', inputs({ spreadMinutes: 2 }), 3)).toBe('mgc')
    expect(modelFor('limited', inputs({ capacity: 6 }), 3)).toBe('mmck')
    expect(modelFor('limited', inputs({ capacity: 6, spreadMinutes: 2 }), 3)).toBe('mgck')
    expect(modelFor('leaving', inputs({ patienceMinutes: 10 }), 3)).toBe('erlang_a')
  })

  it('sends the variance in hours squared and the patience as a rate per hour', () => {
    expect(requestFor('variable', inputs({ spreadMinutes: 6 }), 3)).toEqual({ lambda: 40, mu: 15, c: 3, variance: expect.closeTo(0.01, 12) })
    expect(requestFor('limited', inputs({ capacity: 6 }), 2)).toEqual({ lambda: 40, mu: 15, c: 2, K: 6 })
    expect(requestFor('leaving', inputs({ patienceMinutes: 10 }), 2)).toEqual({ lambda: 40, mu: 15, c: 2, theta: 6 })
    expect(requestFor('basic', inputs({ spreadMinutes: 6, capacity: 6, patienceMinutes: 10 }), 3)).toEqual({ lambda: 40, mu: 15, c: 3 })
  })

  it('never asks for 0 counters or more counters than places', () => {
    expect(neighbourCounters('basic', inputs({ c: 1 }))).toEqual({ fewer: null, more: 2 })
    expect(neighbourCounters('basic', inputs({ c: 3 }))).toEqual({ fewer: 2, more: 4 })
    expect(neighbourCounters('limited', inputs({ c: 3, capacity: 3 }))).toEqual({ fewer: 2, more: null })
    expect(neighbourCounters('limited', inputs({ c: 3, capacity: 4 }))).toEqual({ fewer: 2, more: 4 })
  })

  it('names every unusable input for the situation', () => {
    expect(inputProblems('basic', inputs({ lambda: -1, mu: 0, c: 1.5 }))).toEqual(['lambda', 'mu', 'c'])
    expect(inputProblems('variable', inputs())).toEqual(['spread'])
    expect(inputProblems('limited', inputs({ capacity: 2 }))).toEqual(['capacity'])
    expect(inputProblems('limited', inputs({ capacity: 3, spreadMinutes: -1 }))).toEqual(['spread'])
    expect(inputProblems('leaving', inputs({ patienceMinutes: 0 }))).toEqual(['patience'])
    expect(inputProblems('basic', inputs())).toEqual([])
  })

  it('reads a settled line in minutes and percent, and says the counters keep up', () => {
    expect(summarize('basic', result())).toEqual({ waitMinutes: 0.1595 * 60, busy: 0.8889, waiting: 6.38, keepUp: 'yes',
      turnedAway: null, leaving: null })
  })

  it('says the line keeps growing only when the load reaches capacity', () => {
    const growing = summarize('basic', result({ rho: 1.3333, stable: false, Wq: null, Lq: null, error: 'Unstable system' }))
    expect(growing).toMatchObject({ keepUp: 'no', waitMinutes: null, busy: null })
    // M/G/c with 171 or more counters fails numerically and calls itself "unstable" although rho < 1.
    const failed = summarize('variable', result({ rho: 0.0058, stable: false, Wq: null, Lq: null,
      error: 'Unstable system: lambda must be less than c * mu for M/G/c.' }))
    expect(failed).toMatchObject({ keepUp: 'not_calculated', waitMinutes: null })
  })

  it('reports turned-away and leaving shares, and the served busy share when people leave', () => {
    expect(summarize('limited', result({ rho: 0.9385, blocking_probability: 0.2961 }))).toMatchObject({
      keepUp: null, turnedAway: 0.2961, busy: 0.9385 })
    expect(summarize('leaving', result({ rho: 1.3333, rho_effective: 0.9023, abandonment_rate: 0.3233 }))).toMatchObject({
      keepUp: null, busy: 0.9023, leaving: 0.3233 })
  })
})
