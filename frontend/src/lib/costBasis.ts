// Plan cost label by day basis (spec 2026-10-29 §6, owner decision E). Labelling only.
//
// Evidence (read 2026-10-29): GET /analyses/:id/workflow/comparison/separate returns
// `totals.total_cost_mean = _sum_all(period total_cost_mean)` for every day basis
// (backend/api/workflow.py:2459-2507). A representative day has one period per configured
// segment with arrivals averaged over `validation.observation_days`
// (backend/data/analysis_ingestion.py:278-310, 351-354); a per-date upload has one period per
// date and segment, labelled "YYYY-MM-DD <segment> UTC" (analysis_ingestion.py:61-77).
// The label is shown only when the response itself is consistent with that reading: the total
// equals the sum of the period costs, and the day count can be read from the API fields.
// Shared-line totals are not labelled: their row costs are not established to cover one day (UNKNOWN).
//
// Duration (review K-UC-1, 2026-10-29): each period's total_cost_mean is an HOURLY rate, not the
// period's cost (lane server cost per hour, backend/queueing_engine/services/optimization.py:79-93;
// separate_optimization.py:613-620 and :1855-1861 add those rates per period), and the total adds
// them without weighting by the period's length (workflow.py:2507). Only when every Setup segment
// is exactly 60 minutes does the sum equal the cost of the day, so the label is shown only then.
// Weighting by duration is protected cost math (deferred, spec §12).
import type { TFunction } from 'i18next'
import type { AnalysisSegment, DatasetOut, EventPeriodBasis, SeparatePlanComparison } from '../api/types'
import { clockMinutes } from './replay'
import { finiteNumber } from './results'

export type CostBasisLabel =
  | { key: 'results.cost_basis_average_day'; days: number }
  | { key: 'results.cost_basis_dates'; days: number; first: string; last: string }

const DATE_LABEL = /^(\d{4}-\d{2}-\d{2}) \S.* UTC$/

/** True when the plan total equals the sum of its period costs (float tolerance) and every period has one. */
export function totalIsPeriodSum(plan: SeparatePlanComparison): boolean {
  const total = finiteNumber(plan.totals?.total_cost_mean)
  const costs = plan.periods.map((period) => finiteNumber(period.total_cost_mean))
  if (total === null || costs.length === 0 || costs.some((cost) => cost === null)) return false
  const sum = (costs as number[]).reduce((acc, cost) => acc + cost, 0)
  return Math.abs(sum - total) <= 1e-9 * Math.max(1, Math.abs(total))
}

/** True when the Setup has segments and every one runs exactly 60 minutes ("HH:MM[:SS]" start and end). */
export function allSegmentsHourLong(segments: readonly AnalysisSegment[] | null | undefined): boolean {
  if (!segments || segments.length === 0) return false
  return segments.every((segment) => {
    const start = clockMinutes(segment.start_time)
    const end = clockMinutes(segment.end_time)
    return start !== null && end !== null && Math.abs(end - start - 60) < 1e-9
  })
}

/** The distinct dates of per-date period labels, in order; null when any label is not a per-date label. */
export function perDateDays(times: string[]): string[] | null {
  const dates: string[] = []
  for (const time of times) {
    const match = DATE_LABEL.exec(time)
    if (!match) return null
    if (!dates.includes(match[1])) dates.push(match[1])
  }
  return dates.length > 0 ? dates : null
}

/** The label's text in the selected language (owner's EN, drafted TL: W1/W2). */
export function basisText(t: TFunction, label: CostBasisLabel): string {
  return label.key === 'results.cost_basis_average_day'
    ? t(label.key, { days: label.days })
    : t(label.key, { days: label.days, first: label.first, last: label.last })
}

/** The cost label for a separate-lines plan of the planning file, or null when it cannot be shown truthfully. */
export function separateCostBasis(
  basis: EventPeriodBasis | undefined,
  dataset: DatasetOut | undefined,
  plan: SeparatePlanComparison,
  segments: readonly AnalysisSegment[] | null | undefined,
): CostBasisLabel | null {
  if (!dataset || plan.dataset_id !== dataset.id || !totalIsPeriodSum(plan)) return null
  // The period costs are hourly rates added up, so the sum is a day's cost only for 60-minute segments.
  if (!allSegmentsHourLong(segments)) return null
  if (basis === 'representative_day') {
    const days = finiteNumber(dataset.validation?.observation_days)
    if (dataset.validation?.period_basis !== 'representative_day' || days === null || !Number.isInteger(days) || days < 1) return null
    // A representative day's periods are its segments, never per-date labels.
    if (plan.periods.some((period) => DATE_LABEL.test(period.time))) return null
    return { key: 'results.cost_basis_average_day', days }
  }
  if (basis === 'per_date') {
    const dates = perDateDays(plan.periods.map((period) => period.time))
    const range = dataset.data_dates
    if (!dates || !range) return null
    const sorted = [...dates].sort()
    if (sorted[0] !== range.first || sorted[sorted.length - 1] !== range.last) return null
    return { key: 'results.cost_basis_dates', days: dates.length, first: range.first, last: range.last }
  }
  return null
}
