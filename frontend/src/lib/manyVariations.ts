// Many variations chart (spec 2026-10-29 §8, owner decisions B7, B8, C5). Shaping only: every value
// is a stored Monte Carlo row field, and the run's parameters are read from the stored rows, never
// from the editable form (memory.md: validation presentation uses the persisted run parameters).
import type { SimMcOut } from '../api/types'
import { niceMax } from './chartScale'
import { fmtPctDecimal } from './format'

/**
 * The arrival and service noise the method text states (20% and 10%). They are the engine's
 * constants (backend/queueing_engine/config.py MC_ARRIVAL_NOISE, MC_SERVICE_NOISE), not run values.
 */
export const METHOD_ARRIVAL_NOISE = 0.2
export const METHOD_SERVICE_NOISE = 0.1

const SAME = 1e-12

/** The value every row stores for a field, or null when a row lacks it or the rows disagree. */
export function agreedValue(rows: readonly SimMcOut[], pick: (row: SimMcOut) => number | null | undefined): number | null {
  if (rows.length === 0) return null
  const values = rows.map(pick)
  const first = values[0]
  if (typeof first !== 'number' || !Number.isFinite(first)) return null
  return values.every((value) => typeof value === 'number' && Number.isFinite(value) && Math.abs(value - first) <= SAME) ? first : null
}

export interface StoredMcParameters {
  trials: number | null
  threshold: number | null
  cap: number | null
  /** All three are stored and agree, and no row states noise other than the method text's. */
  explainable: boolean
}

export function storedMcParameters(rows: readonly SimMcOut[]): StoredMcParameters {
  const trials = agreedValue(rows, (row) => row.num_trials)
  const threshold = agreedValue(rows, (row) => row.failure_threshold)
  const cap = agreedValue(rows, (row) => row.failure_rate_cap)
  const noiseAsText = rows.every((row) => (row.arrival_noise_fraction === undefined || Math.abs(row.arrival_noise_fraction - METHOD_ARRIVAL_NOISE) <= SAME)
    && (row.service_noise_fraction === undefined || Math.abs(row.service_noise_fraction - METHOD_SERVICE_NOISE) <= SAME))
  return { trials, threshold, cap, explainable: trials !== null && threshold !== null && cap !== null && noiseAsText }
}

function rate(row: SimMcOut): number | null {
  return typeof row.failure_rate === 'number' && Number.isFinite(row.failure_rate) ? row.failure_rate : null
}

function upper(row: SimMcOut): number | null {
  return typeof row.failure_rate_ci_upper === 'number' && Number.isFinite(row.failure_rate_ci_upper) ? row.failure_rate_ci_upper : null
}

export interface McPeriod {
  time: string
  /** The row with the highest failure rate (ties: higher upper bound, then queue id). */
  worst: SimMcOut
  all: SimMcOut[]
}

/** Highest-risk first; a row without a failure rate sorts last. */
function compareRisk(left: SimMcOut, right: SimMcOut): number {
  const byRate = (rate(right) ?? -Infinity) - (rate(left) ?? -Infinity)
  if (byRate !== 0 && !Number.isNaN(byRate)) return byRate
  const byUpper = (upper(right) ?? -Infinity) - (upper(left) ?? -Infinity)
  if (byUpper !== 0 && !Number.isNaN(byUpper)) return byUpper
  const leftId = String(left.queue_id ?? '')
  const rightId = String(right.queue_id ?? '')
  return leftId < rightId ? -1 : leftId > rightId ? 1 : 0
}

/** One row per period, in the order the run stored them. */
export function mcPeriods(rows: readonly SimMcOut[]): McPeriod[] {
  const periods: McPeriod[] = []
  for (const row of rows) {
    const period = periods.find((item) => item.time === row.time)
    if (period) period.all.push(row)
    else periods.push({ time: row.time, worst: row, all: [row] })
  }
  for (const period of periods) period.worst = [...period.all].sort(compareRisk)[0]
  return periods
}

/** The period whose highest failure rate is the largest (first one on a tie); -1 when none has a rate. */
export function highestRiskIndex(periods: readonly McPeriod[]): number {
  let best = -1
  periods.forEach((period, index) => {
    const value = rate(period.worst)
    if (value !== null && (best < 0 || value > (rate(periods[best].worst) as number))) best = index
  })
  return best
}

/** Axis end: covers the cap, every upper bound and every rate, so no value is hidden. */
export function mcAxisMax(periods: readonly McPeriod[], cap: number | null): number {
  const values = periods.flatMap((period) => period.all.flatMap((row) => [rate(row), upper(row)]))
    .filter((value): value is number => value !== null)
  return niceMax(Math.max(cap ?? 0, ...values))
}

export function failureRate(row: SimMcOut): number | null {
  return rate(row)
}

/** "0% – 0.19%" with the decimal rule, or null when the run stored no range. */
export function mcRangeText(row: SimMcOut): string | null {
  const low = row.failure_rate_ci_lower
  const high = row.failure_rate_ci_upper
  if (typeof low !== 'number' || typeof high !== 'number' || !Number.isFinite(low) || !Number.isFinite(high)) return null
  return `${fmtPctDecimal(low)} – ${fmtPctDecimal(high)}`
}
