import { describe, expect, it } from 'vitest'
import type { AnalysisSegment, DatasetOut, EventPeriodBasis, SeparatePlanComparison, SeparatePlanPeriod } from '../api/types'
import { allSegmentsHourLong, perDateDays, separateCostBasis as labelFor, totalIsPeriodSum } from './costBasis'

// Fixtures mirror GET /analyses/:id/workflow/comparison/separate (backend/api/workflow.py:2459-2507:
// each period's total_cost_mean, and totals.total_cost_mean = _sum_all of them) and DatasetOut
// (backend/api/datasets.py:55-71: validation = the stored validation report, data_dates).

function period(time: string, cost: number | null): SeparatePlanPeriod {
  return { time, current_active_lanes: ['A'], optimal_active_lanes: 1, adjustment: 0, peak_util: 0.5, wait_mean: 0.1, wait_ci: null,
    waiting_cost_mean: 1, total_cost_mean: cost, total_cost_ci: null, status: null }
}

function plan(periods: SeparatePlanPeriod[], total: number | null, datasetId = 11): SeparatePlanComparison {
  return { scenario_id: 1, name: 'p', dataset_id: datasetId, target: 0.85, evaluation_method: 'DES_REPLICATIONS', replications: 5, base_seed: 42, overall: null,
    wait_basis_kind: 'simulation', stale: false, valid: true, valid_reason: null, periods,
    totals: { lane_periods: periods.length, wait_mean: 0.1, peak_util: 0.5, waiting_cost_mean: 1, total_cost_mean: total } }
}

function dataset(validation: Record<string, unknown>, dates: DatasetOut['data_dates'] = { first: '2000-01-03', last: '2000-01-16', source: 'stored_at_upload' }): DatasetOut {
  return { id: 11, analysis_id: 7, name: 'n', source_filename: 'n.xlsx', source_format: 'xlsx', row_count: 13,
    validation: { ok: true, message: 'Input data is valid.', ...validation }, created_at: '', normalized: null, data_dates: dates }
}

function segment(start: string, end: string): AnalysisSegment {
  return { id: null, start_time: start, end_time: end, active_queue_ids: null }
}

// Setup segments: period costs are hourly rates added up (K-UC-1), so only 60-minute segments get a label.
const hourly = [segment('08:00', '09:00'), segment('09:00', '10:00'), segment('10:00', '11:00')]
const separateCostBasis = (basis: EventPeriodBasis | undefined, data: DatasetOut | undefined, chosen: SeparatePlanComparison) => labelFor(basis, data, chosen, hourly)

const representative = dataset({ period_basis: 'representative_day', observation_days: 14, derived_statistics: [{ time: 'morning' }] })
const segmentPeriods = [period('morning', 1200.5), period('noon', 899.25), period('evening', 410.125)]
const segmentTotal = 1200.5 + 899.25 + 410.125

const perDate = dataset({ derived_statistics: [{ time: '2000-01-03 morning UTC' }] })
const datePeriods = [
  period('2000-01-03 morning UTC', 100.1), period('2000-01-03 noon UTC', 200.2),
  period('2000-01-05 morning UTC', 300.3), period('2000-01-16 morning UTC', 0.4),
]
const dateTotal = 100.1 + 200.2 + 300.3 + 0.4

describe('plan cost label by day basis', () => {
  it('requires the plan total to be the sum of its period costs', () => {
    expect(totalIsPeriodSum(plan(segmentPeriods, segmentTotal))).toBe(true)
    expect(totalIsPeriodSum(plan(segmentPeriods, segmentTotal + 1))).toBe(false)
    expect(totalIsPeriodSum(plan([...segmentPeriods, period('late', null)], segmentTotal))).toBe(false)
    expect(totalIsPeriodSum(plan(segmentPeriods, null))).toBe(false)
    expect(totalIsPeriodSum(plan([], 0))).toBe(false)
  })

  it('labels a representative day with the observation_days of its dataset', () => {
    expect(separateCostBasis('representative_day', representative, plan(segmentPeriods, segmentTotal)))
      .toEqual({ key: 'results.cost_basis_average_day', days: 14 })
  })

  it('shows no representative-day label without observation_days or with a mismatching basis or total', () => {
    expect(separateCostBasis('representative_day', dataset({ period_basis: 'representative_day' }), plan(segmentPeriods, segmentTotal))).toBeNull()
    expect(separateCostBasis('representative_day', dataset({ observation_days: 14 }), plan(segmentPeriods, segmentTotal))).toBeNull()
    expect(separateCostBasis('representative_day', dataset({ period_basis: 'representative_day', observation_days: 0 }), plan(segmentPeriods, segmentTotal))).toBeNull()
    expect(separateCostBasis('representative_day', representative, plan(segmentPeriods, 5))).toBeNull()
    expect(separateCostBasis('representative_day', representative, plan(datePeriods, dateTotal))).toBeNull()
  })

  it('labels per-date plans with the distinct dates of the period labels and the dataset dates', () => {
    expect(perDateDays(datePeriods.map((item) => item.time))).toEqual(['2000-01-03', '2000-01-05', '2000-01-16'])
    expect(separateCostBasis('per_date', perDate, plan(datePeriods, dateTotal)))
      .toEqual({ key: 'results.cost_basis_dates', days: 3, first: '2000-01-03', last: '2000-01-16' })
  })

  it('shows no per-date label when a label is not per-date, the dates disagree or are unknown', () => {
    expect(perDateDays(['2000-01-03 morning UTC', 'morning'])).toBeNull()
    expect(separateCostBasis('per_date', perDate, plan(segmentPeriods, segmentTotal))).toBeNull()
    expect(separateCostBasis('per_date', dataset({}, { first: '2000-01-01', last: '2000-01-16', source: 'stored_at_upload' }), plan(datePeriods, dateTotal))).toBeNull()
    expect(separateCostBasis('per_date', dataset({}, null), plan(datePeriods, dateTotal))).toBeNull()
  })

  it('shows a label only when every Setup segment is exactly 60 minutes', () => {
    expect(allSegmentsHourLong(hourly)).toBe(true)
    expect(allSegmentsHourLong([segment('08:00:00', '09:00:00')])).toBe(true)
    expect(labelFor('representative_day', representative, plan(segmentPeriods, segmentTotal), hourly)).toEqual({ key: 'results.cost_basis_average_day', days: 14 })
    expect(labelFor('per_date', perDate, plan(datePeriods, dateTotal), hourly)).toEqual({ key: 'results.cost_basis_dates', days: 3, first: '2000-01-03', last: '2000-01-16' })
    const thirty = [segment('08:00', '08:30'), segment('08:30', '09:00'), segment('09:00', '09:30')]
    const twoHours = [segment('08:00', '10:00'), segment('10:00', '12:00'), segment('12:00', '14:00')]
    const mixed = [segment('08:00', '09:00'), segment('09:00', '11:00'), segment('11:00', '12:00')]
    for (const segments of [thirty, twoHours, mixed, [segment('08:00', 'late')], [], undefined]) {
      expect(labelFor('representative_day', representative, plan(segmentPeriods, segmentTotal), segments)).toBeNull()
      expect(labelFor('per_date', perDate, plan(datePeriods, dateTotal), segments)).toBeNull()
    }
  })

  it('shows no label for an aggregate upload, another dataset, or no dataset', () => {
    expect(separateCostBasis(undefined, representative, plan(segmentPeriods, segmentTotal))).toBeNull()
    expect(separateCostBasis('representative_day', representative, plan(segmentPeriods, segmentTotal, 99))).toBeNull()
    expect(separateCostBasis('representative_day', undefined, plan(segmentPeriods, segmentTotal))).toBeNull()
  })
})
