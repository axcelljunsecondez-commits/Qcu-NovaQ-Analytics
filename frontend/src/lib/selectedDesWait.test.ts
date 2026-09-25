import { describe, expect, it } from 'vitest'
import type { SelectedDesResult } from '../api/types'
import {
  periodWaitCoverage,
  SELECTED_DES_CONTINUOUS_DAY_EXECUTION,
  SELECTED_DES_PER_PERIOD_EXECUTION,
  selectedDesWaitCoverage,
} from './selectedDesWait'

function stored(execution: string | undefined, ...counts: unknown[]): SelectedDesResult {
  return {
    execution,
    periods: counts.map((count, index) => ({
      time: `p${index}`,
      ...(count === 'missing' ? {} : { censored_customers: count }),
    })),
  } as unknown as SelectedDesResult
}

describe('selectedDesWaitCoverage', () => {
  it('keeps verified zero, verified positive, unknown and not-applicable apart', () => {
    const perPeriod = selectedDesWaitCoverage(stored(SELECTED_DES_PER_PERIOD_EXECUTION, 0, 5, 'missing', null))
    expect(perPeriod.basis).toBe('per_period')
    expect(periodWaitCoverage(perPeriod, 'p0')).toEqual({ basis: 'per_period', status: 'recorded', censored: 0 })
    expect(periodWaitCoverage(perPeriod, 'p1')).toEqual({ basis: 'per_period', status: 'recorded', censored: 5 })
    expect(periodWaitCoverage(perPeriod, 'p2')).toEqual({ basis: 'per_period', status: 'unknown', censored: null })
    expect(periodWaitCoverage(perPeriod, 'p3')).toEqual({ basis: 'per_period', status: 'unknown', censored: null })
    const day = selectedDesWaitCoverage(stored(SELECTED_DES_CONTINUOUS_DAY_EXECUTION, 'missing'))
    expect(periodWaitCoverage(day, 'p0')).toEqual({ basis: 'continuous_day', status: 'not_applicable', censored: null })
  })

  it('never infers the basis or a count from values', () => {
    const noBasis = selectedDesWaitCoverage(stored(undefined, 0, 3))
    expect(noBasis.basis).toBe('unknown')
    expect(periodWaitCoverage(noBasis, 'p0').status).toBe('unknown')
    const malformed = selectedDesWaitCoverage(stored(SELECTED_DES_PER_PERIOD_EXECUTION, -1, 2.5, true, '4'))
    for (const time of ['p0', 'p1', 'p2', 'p3']) {
      expect(periodWaitCoverage(malformed, time)).toEqual({ basis: 'per_period', status: 'unknown', censored: null })
    }
    // A period the result does not list is unknown, never zero.
    expect(periodWaitCoverage(malformed, 'absent')).toEqual({ basis: 'per_period', status: 'unknown', censored: null })
  })
})
