// Wait-by-hour rows for Analysis Results tab 1 (spec 2026-10-29 §5.2). Selection, unit
// conversion (hours → minutes, as `minutes()`) and the display clamp of a range's lower end
// only (OD-1): every value comes from a server response, kinds are kept apart, and a missing
// value stays null so the chart draws a labelled gap.
import type { ObservedWaitPeriod, OptimizationOut, SeparateComparison, SeparatePlanComparison } from '../api/types'
import { setupStaffing, type StaffingSetup } from './longestLine'
import { finiteNumber, minutes, timeOf, type ResultRow } from './results'

export type WaitView = 'today' | 'plan'

export interface WaitRange {
  /** Shown lower end in minutes: max(0, stored lower). The stored negative value is never shown. */
  low: number
  high: number
  /** The shown lower end is 0, so the row gets the "Range cut at 0" marker and note. */
  cut: boolean
}

export interface WaitRow {
  time: string
  countersNow: number | null
  /** Plan views only. */
  countersPlan: number | null
  /** Minutes; Today view only (current measurement). */
  recorded: number | null
  /** Minutes; analytical model estimate for today's staffing. */
  estimated: number | null
  /** Minutes; Plan views only (separate: simulated mean; shared: calculated). */
  plan: number | null
  /** Separate plan view only; null when the API returned no range or a missing side. */
  range: WaitRange | null
  /** Shared plan view: the side's server status says the counters can't keep up. */
  estimatedUnstable: boolean
  planUnstable: boolean
  flagged: boolean
}

function emptyRow(time: string): WaitRow {
  return {
    time, countersNow: null, countersPlan: null, recorded: null, estimated: null, plan: null,
    range: null, estimatedUnstable: false, planUnstable: false, flagged: false,
  }
}

/** Counters per period from the /current rows: the rows' `c` added up; null when any is missing. */
export function countersByPeriod(rows: ResultRow[]): Map<string, number | null> {
  const counters = new Map<string, number | null>()
  for (const row of rows) {
    const time = timeOf(row)
    const c = finiteNumber(row.c)
    const before = counters.has(time) ? counters.get(time) ?? null : 0
    counters.set(time, before === null || c === null ? null : before + c)
  }
  return counters
}

/**
 * Separate lines, Today view (review K-UC-5): the cashiers the Setup staffs in each period, resolved by
 * setupStaffing (the same resolver as the Current-run table). The /current rows exist only for cashiers
 * with recorded customers, so adding their `c` would undercount. A period is mapped to its Setup segment
 * through the planning file's records (`time` → `segment_id`, analysis_ingestion.py); when staffing varies
 * and the period names no single known segment, its count is null (shown as "—").
 */
export function setupCountersByPeriod(times: readonly string[], setup: StaffingSetup, records: readonly Record<string, unknown>[] | null | undefined): Map<string, number | null> {
  const staffing = setupStaffing(setup)
  const segmentsOf = new Map<string, Set<string>>()
  for (const record of records ?? []) {
    const time = timeOf(record)
    const segment = record.segment_id === undefined || record.segment_id === null ? '' : String(record.segment_id)
    segmentsOf.set(time, (segmentsOf.get(time) ?? new Set<string>()).add(segment))
  }
  const counters = new Map<string, number | null>()
  for (const time of times) {
    if (staffing.all) {
      counters.set(time, staffing.all.size > 0 ? staffing.all.size : null)
      continue
    }
    const ids = [...(segmentsOf.get(time) ?? [])]
    const active = ids.length === 1 && ids[0] !== '' ? staffing.bySegment.get(ids[0]) ?? null : null
    counters.set(time, active ? active.size : null)
  }
  return counters
}

/** Today view: Recorded vs Estimated from the observed-wait summary (both line types). */
export function todayWaitRows(periods: ObservedWaitPeriod[], counters: Map<string, number | null>): WaitRow[] {
  return periods.map((period) => ({
    ...emptyRow(period.time),
    countersNow: counters.get(period.time) ?? null,
    recorded: minutes(period.observed_wait),
    estimated: minutes(period.modeled_wait),
    flagged: period.flagged === true,
  }))
}

/** The plan's 95% range in minutes with the lower end shown as max(0, lower); null when a side is missing. */
export function waitRange(ci: [number | null, number | null] | null | undefined): WaitRange | null {
  if (!ci) return null
  const lower = minutes(finiteNumber(ci[0]))
  const upper = minutes(finiteNumber(ci[1]))
  if (lower === null || upper === null) return null
  const low = Math.max(0, lower)
  return { low, high: upper, cut: low === 0 }
}

/** Separate lines, Plan view: today's analytical estimate vs the plan's simulated mean and range. */
export function separatePlanWaitRows(comparison: SeparateComparison, plan: SeparatePlanComparison): WaitRow[] {
  return comparison.current.periods.map((period) => {
    const match = plan.periods.find((item) => item.time === period.time)
    return {
      ...emptyRow(period.time),
      countersNow: period.active_lanes === null ? null : period.active_lanes.length,
      countersPlan: finiteNumber(match?.optimal_active_lanes),
      estimated: minutes(finiteNumber(period.wait_mean)),
      plan: minutes(finiteNumber(match?.wait_mean)),
      range: waitRange(match?.wait_ci),
    }
  })
}

/** Shared line, Plan view: both sides calculated (M/G/c); no range. An unstable side has no value. */
export function sharedPlanWaitRows(rows: OptimizationOut[]): WaitRow[] {
  return rows.map((row) => {
    const estimatedUnstable = row.current_stable === false
    const planUnstable = row.optimized_stable === false
    return {
      ...emptyRow(row.time),
      countersNow: finiteNumber(row.c_current),
      countersPlan: finiteNumber(row.c_optimal),
      estimated: estimatedUnstable ? null : minutes(finiteNumber(row.Wq_current)),
      plan: planUnstable ? null : minutes(finiteNumber(row.Wq_optimal)),
      estimatedUnstable,
      planUnstable,
    }
  })
}

/** Index of the period with the highest Estimated wait (first on a tie); null when none is known. */
export function highestEstimate(rows: WaitRow[]): number | null {
  let best: number | null = null
  rows.forEach((row, index) => {
    if (row.estimated !== null && (best === null || row.estimated > (rows[best].estimated as number))) best = index
  })
  return best
}

/**
 * The takeaway names "the highest calculated estimate" only when every period has one:
 * a missing or can't-keep-up period could be higher than any value shown.
 */
export function takeawayRow(rows: WaitRow[]): number | null {
  if (rows.length === 0 || rows.some((row) => row.estimated === null)) return null
  return highestEstimate(rows)
}

/** Largest value drawn in the view (minutes), for the axis. */
export function largestShown(rows: WaitRow[], view: WaitView): number {
  let max = 0
  for (const row of rows) {
    const values = view === 'today' ? [row.recorded, row.estimated] : [row.estimated, row.plan, row.range?.high ?? null]
    for (const value of values) if (value !== null && value > max) max = value
  }
  return max
}

export function anyCut(rows: WaitRow[]): boolean {
  return rows.some((row) => row.range?.cut === true)
}

const HOUR_LABEL = /^(\d{2}):(\d{2})-(\d{2}):(\d{2})$/

/** True when every period label is a 60-minute "HH:MM-HH:MM" span (so "each row is one hour" is true). */
export function allHourPeriods(times: string[]): boolean {
  return times.length > 0 && times.every((time) => {
    const match = HOUR_LABEL.exec(time)
    if (!match) return false
    const start = Number(match[1]) * 60 + Number(match[2])
    const end = Number(match[3]) * 60 + Number(match[4])
    return end - start === 60
  })
}
