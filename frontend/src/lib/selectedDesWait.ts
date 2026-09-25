import type {
  SelectedDesCensoringStatus,
  SelectedDesResult,
  SelectedDesWaitBasis,
  SelectedDesWaitDisclosure,
} from '../api/types'

/** The `execution` values the backend records on selected-plan DES results
 * (SELECTED_DES_*_EXECUTION in separate_optimization.py). */
export const SELECTED_DES_PER_PERIOD_EXECUTION =
  'selected-plan routing DES (period-independent, no carryover)'
export const SELECTED_DES_CONTINUOUS_DAY_EXECUTION =
  'selected-plan continuous-day routing DES (queues and breaks carry across periods)'

export interface PeriodWaitCoverage {
  basis: SelectedDesWaitBasis
  status: SelectedDesCensoringStatus
  /** A verified count (zero or positive) only when `status` is `recorded`. */
  censored: number | null
}

export type WaitCoverage = Pick<SelectedDesWaitDisclosure, 'basis' | 'periods'>

/** Who a stored DES result's Wq covers, from its recorded provenance only (the
 * backend's `selected_des_wait_disclosure` rules): never inferred from metric values,
 * and a missing count is unknown, never zero. */
export function selectedDesWaitCoverage(result: SelectedDesResult): WaitCoverage {
  const basis: SelectedDesWaitBasis = result.execution === SELECTED_DES_PER_PERIOD_EXECUTION
    ? 'per_period'
    : result.execution === SELECTED_DES_CONTINUOUS_DAY_EXECUTION ? 'continuous_day' : 'unknown'
  const periods: WaitCoverage['periods'] = {}
  for (const period of result.periods) {
    const count = period.censored_customers
    if (basis === 'continuous_day') {
      periods[period.time] = { censoring_status: 'not_applicable', censored_customers: null }
    } else if (basis === 'per_period' && typeof count === 'number' && Number.isInteger(count) && count >= 0) {
      periods[period.time] = { censoring_status: 'recorded', censored_customers: count }
    } else {
      periods[period.time] = { censoring_status: 'unknown', censored_customers: null }
    }
  }
  return { basis, periods }
}

export function periodWaitCoverage(coverage: WaitCoverage, time: string): PeriodWaitCoverage {
  const item = coverage.periods[time]
  const status: SelectedDesCensoringStatus = item?.censoring_status
    ?? (coverage.basis === 'continuous_day' ? 'not_applicable' : 'unknown')
  const censored = status === 'recorded' && typeof item?.censored_customers === 'number'
    ? item.censored_customers
    : null
  return { basis: coverage.basis, status: censored === null && status === 'recorded' ? 'unknown' : status, censored }
}
