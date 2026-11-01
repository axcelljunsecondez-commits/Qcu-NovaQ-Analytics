import { describe, expect, it } from 'vitest'
import type { OptimizationOut, SeparateComparison, SeparatePlanComparison } from '../api/types'
import {
  allHourPeriods, anyCut, countersByPeriod, highestEstimate, setupCountersByPeriod, largestShown, separatePlanWaitRows, sharedPlanWaitRows,
  takeawayRow, todayWaitRows, waitRange,
} from './waitChart'

const comparison = {
  current: { periods: [
    { time: '08:00-09:00', active_lanes: ['A', 'B'], lambda_total: 10, wait_mean: 0.2, util_max: 0.75 },
    { time: '09:00-10:00', active_lanes: null, lambda_total: 10, wait_mean: null, util_max: null },
  ] },
} as unknown as SeparateComparison

function plan(ci: [number | null, number | null] | null): SeparatePlanComparison {
  return { periods: [
    { time: '08:00-09:00', current_active_lanes: ['A', 'B'], optimal_active_lanes: 3, adjustment: 1, peak_util: 0.6, wait_mean: 0.1, wait_ci: ci,
      waiting_cost_mean: 5, total_cost_mean: 320, total_cost_ci: null, status: null },
  ] } as unknown as SeparatePlanComparison
}

describe('wait chart rows', () => {
  it('converts hours to minutes and keeps missing values null', () => {
    const rows = todayWaitRows([
      { time: '08:00-09:00', modeled_wait: 0.05, observed_wait: 0.12, flagged: true },
      { time: '09:00-10:00', modeled_wait: null, observed_wait: null, flagged: false },
    ], countersByPeriod([{ time: '08:00-09:00', c: 3 }, { time: '09:00-10:00', c: null }]))
    expect(rows[0]).toMatchObject({ countersNow: 3, recorded: 0.12 * 60, estimated: 3, flagged: true, plan: null, range: null })
    expect(rows[1]).toMatchObject({ countersNow: null, recorded: null, estimated: null })
  })

  it('adds the counters of separate lane rows and voids the period total when one is missing', () => {
    const counters = countersByPeriod([
      { time: 'a', queue_id: 'A', c: 1 }, { time: 'a', queue_id: 'B', c: 1 },
      { time: 'b', queue_id: 'A', c: 1 }, { time: 'b', queue_id: 'B', c: null },
    ])
    expect(counters.get('a')).toBe(2)
    expect(counters.get('b')).toBeNull()
  })

  it('counts the Setup staffing per period with the shared resolver; unknown staffing is null', () => {
    const fixed = { queue_ids: ['A', 'B', 'C'], segments: [], staffing_varies_by_period: false }
    expect([...setupCountersByPeriod(['a', 'b'], fixed, null).values()]).toEqual([3, 3])
    const varying = { queue_ids: ['A', 'B', 'C'], staffing_varies_by_period: true, segments: [
      { id: 'm', start_time: '08:00', end_time: '09:00', active_queue_ids: ['A', 'B'] },
      { id: null, start_time: '09:00', end_time: '10:00', active_queue_ids: ['C'] },
    ] }
    const records = [{ time: 'a', segment_id: 'm' }, { time: 'b', segment_id: 'segment_2' }, { time: 'c', segment_id: 'm' }, { time: 'c', segment_id: 'segment_2' }]
    const counters = setupCountersByPeriod(['a', 'b', 'c', 'd'], varying, records)
    expect(counters.get('a')).toBe(2)
    expect(counters.get('b')).toBe(1)
    expect(counters.get('c')).toBeNull()
    expect(counters.get('d')).toBeNull()
  })

  it('shows a negative stored lower bound as 0 and marks the range cut; 0 is also cut; a positive lower is not', () => {
    expect(waitRange([-0.0239, 0.3])).toEqual({ low: 0, high: 18, cut: true })
    expect(waitRange([0, 0.3])).toEqual({ low: 0, high: 18, cut: true })
    expect(waitRange([0.05, 0.3])).toEqual({ low: 3, high: 18, cut: false })
    expect(waitRange([null, 0.3])).toBeNull()
    expect(waitRange(null)).toBeNull()
  })

  it('builds separate plan rows from the comparison: analytical estimate, simulated plan and range', () => {
    const rows = separatePlanWaitRows(comparison, plan([-0.0239, 0.3]))
    expect(rows[0]).toMatchObject({ countersNow: 2, countersPlan: 3, estimated: 12, plan: 6, recorded: null, range: { low: 0, high: 18, cut: true } })
    expect(rows[1]).toMatchObject({ countersNow: null, countersPlan: null, estimated: null, plan: null, range: null })
    expect(anyCut(rows)).toBe(true)
    expect(anyCut(separatePlanWaitRows(comparison, plan([0.05, 0.3])))).toBe(false)
  })

  it('builds shared plan rows with no range and no value for an unstable side', () => {
    const rows = sharedPlanWaitRows([
      { time: '08:00-09:00', c_current: 3, c_optimal: 4, Wq_current: 0.05, Wq_optimal: 0.01, current_stable: true, optimized_stable: true },
      { time: '09:00-10:00', c_current: 3, c_optimal: 5, Wq_current: 9, Wq_optimal: 0.01, current_stable: false, optimized_stable: true },
    ] as OptimizationOut[])
    expect(rows[0]).toMatchObject({ countersNow: 3, countersPlan: 4, estimated: 3, plan: 0.6, range: null, estimatedUnstable: false })
    expect(rows[1]).toMatchObject({ estimated: null, estimatedUnstable: true, plan: 0.6, range: null })
  })

  it('highlights the highest estimate and names it in the takeaway only when every period has one', () => {
    const rows = todayWaitRows([
      { time: 'a', modeled_wait: 0.1, observed_wait: 0.2, flagged: false },
      { time: 'b', modeled_wait: 0.3, observed_wait: null, flagged: false },
      { time: 'c', modeled_wait: 0.3, observed_wait: 0.1, flagged: false },
    ], new Map())
    expect(highestEstimate(rows)).toBe(1)
    expect(takeawayRow(rows)).toBe(1)
    const withGap = [...rows, { ...rows[0], time: 'd', estimated: null }]
    expect(highestEstimate(withGap)).toBe(1)
    expect(takeawayRow(withGap)).toBeNull()
    expect(takeawayRow([])).toBeNull()
  })

  it('sizes the axis from the values the view draws only', () => {
    const rows = separatePlanWaitRows(comparison, plan([0.05, 0.5]))
    expect(largestShown(rows, 'plan')).toBe(30)
    const today = todayWaitRows([{ time: 'a', modeled_wait: 0.1, observed_wait: 0.4, flagged: false }], new Map())
    expect(largestShown(today, 'today')).toBe(24)
  })

  it('says "one hour" only when every period is a 60-minute span', () => {
    expect(allHourPeriods(['08:00-09:00', '09:00-10:00'])).toBe(true)
    expect(allHourPeriods(['08:00-09:30'])).toBe(false)
    expect(allHourPeriods(['2026-03-01 08:00 UTC'])).toBe(false)
    expect(allHourPeriods(['morning'])).toBe(false)
    expect(allHourPeriods([])).toBe(false)
  })
})
