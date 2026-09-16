export interface ArrivalPoint {
  time: string
  value: number
}

export interface PeriodDemand {
  time: string
  totalLambda: number
  queueCount: number
}

/**
 * Group arrival points by exact time label, summing arrival rates within a
 * period. The sum is descriptive demand summarization only: it must never be
 * fed into a queueing model (Problem 1 independence stays intact). Rates are
 * compared, never converted to customer counts, because aggregate segment
 * durations are not reliably derivable.
 */
export function groupPeriodDemand(points: ArrivalPoint[]): PeriodDemand[] {
  const totals = new Map<string, PeriodDemand>()
  for (const point of points) {
    const existing = totals.get(point.time)
    if (existing) {
      existing.totalLambda += point.value
      existing.queueCount += 1
    } else {
      totals.set(point.time, { time: point.time, totalLambda: point.value, queueCount: 1 })
    }
  }
  return [...totals.values()]
}

/**
 * Busiest period = highest combined arrival rate. Ties resolve to the first
 * period in row order (matching the pre-existing strict-comparison behavior).
 */
export function pickPeakPeriod(demands: PeriodDemand[]): PeriodDemand | null {
  let peak: PeriodDemand | null = null
  for (const demand of demands) {
    if (peak === null || demand.totalLambda > peak.totalLambda) peak = demand
  }
  return peak
}

/**
 * Leanest period = lowest combined arrival rate, zero included. Ties resolve
 * to the first period in row order.
 */
export function pickLeanPeriod(demands: PeriodDemand[]): PeriodDemand | null {
  let lean: PeriodDemand | null = null
  for (const demand of demands) {
    if (lean === null || demand.totalLambda < lean.totalLambda) lean = demand
  }
  return lean
}
