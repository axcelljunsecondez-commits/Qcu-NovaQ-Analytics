// Analysis results helpers (spec 2026-10-09 §7.7, plan phase U6). Selection and labelling only:
// every number shown comes from a server response; nothing here adds values up.
import type { DataDates, DatasetOut } from '../api/types'
import { THRESHOLD_TOLERANCE, utilizationBand, type UtilizationBand } from './utilization'

export type ResultRow = Record<string, unknown>

const BAND_ORDER: UtilizationBand[] = ['Lean', 'Normal', 'Peak', 'Critical', 'Unstable']

export function finiteNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value !== 'string' || value.trim() === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function lineOf(row: ResultRow): string | null {
  return typeof row.queue_id === 'string' && row.queue_id.trim() !== '' ? row.queue_id : null
}

export function timeOf(row: ResultRow): string {
  return row.time === null || row.time === undefined ? '' : String(row.time)
}

/**
 * Counters can't keep up: the server marks the row unstable and its load reaches capacity (rho >= 1).
 * A row that failed for another reason (an approximation outside its bounds, a calculation that did not
 * converge) is not overloaded; its level is unknown (OD-N2, large server-count numerics spec 2026-10-12).
 */
export function cantKeepUp(row: ResultRow): boolean {
  const rho = finiteNumber(row.rho)
  return row.stable === false && rho !== null && rho >= 1 - THRESHOLD_TOLERANCE
}

/** NovaQ's fixed busy level for one row, or null when it is unknown (shown as "Unavailable"). */
export function busyLevel(row: ResultRow): UtilizationBand | null {
  if (cantKeepUp(row)) return 'Unstable'
  if (row.stable === false) return null
  const rho = finiteNumber(row.rho)
  return rho === null ? null : utilizationBand(rho)
}

function worse(left: UtilizationBand | null, right: UtilizationBand | null): UtilizationBand | null {
  if (left === null) return right
  if (right === null) return left
  return BAND_ORDER.indexOf(right) > BAND_ORDER.indexOf(left) ? right : left
}

export function levelKey(level: UtilizationBand | null): string {
  return level === null ? 'results.unavailable' : `results.level.${level.toLowerCase()}`
}

export function levelClass(level: UtilizationBand | null): string {
  return level === null ? 'busy-unknown' : `busy-${level.toLowerCase()}`
}

export interface StripPeriod {
  time: string
  level: UtilizationBand | null
  /** Highest workload of any line in the period (one shared line: the counter group). */
  rho: number | null
  lines: number
}

/** One cell per period in upload order; separate lines take their busiest line. */
export function dayStrip(rows: ResultRow[]): StripPeriod[] {
  const periods: StripPeriod[] = []
  const byTime = new Map<string, StripPeriod>()
  for (const row of rows) {
    const time = timeOf(row)
    let period = byTime.get(time)
    if (!period) {
      period = { time, level: null, rho: null, lines: 0 }
      byTime.set(time, period)
      periods.push(period)
    }
    period.lines += 1
    period.level = worse(period.level, busyLevel(row))
    const rho = finiteNumber(row.rho)
    if (rho !== null && (period.rho === null || rho > period.rho)) period.rho = rho
  }
  return periods
}

export interface AttentionPeriod {
  time: string
  line: string | null
  waitHours: number | null
}

/** Periods where counters can't keep up first, then the highest estimated wait (spec §7.7). */
export function periodsNeedingAttention(rows: ResultRow[]): { cantKeepUp: AttentionPeriod[]; highestWait: AttentionPeriod | null } {
  const overloaded = rows.filter(cantKeepUp).map((row) => ({ time: timeOf(row), line: lineOf(row), waitHours: null }))
  let highestWait: AttentionPeriod | null = null
  for (const row of rows) {
    if (cantKeepUp(row)) continue
    const wait = finiteNumber(row.Wq)
    if (wait === null) continue
    if (highestWait === null || wait > (highestWait.waitHours ?? -Infinity)) {
      highestWait = { time: timeOf(row), line: lineOf(row), waitHours: wait }
    }
  }
  return { cantKeepUp: overloaded, highestWait }
}

export interface PeriodWarning {
  time: string
  level: UtilizationBand | null
  aboveTarget: boolean
}

/** Critical or can't-keep-up periods, plus periods above the selected plan's target when one exists (D19). */
export function periodWarnings(strip: StripPeriod[], planTarget: number | null): PeriodWarning[] {
  return strip
    .map((period) => ({
      time: period.time,
      level: period.level,
      aboveTarget: planTarget !== null && (period.level === 'Unstable' || (period.rho !== null && period.rho > planTarget)),
    }))
    .filter((warning) => warning.level === 'Critical' || warning.level === 'Unstable' || warning.aboveTarget)
}

export function isProcessed(dataset: DatasetOut): boolean {
  return dataset.validation?.ok === true
}

export function hasCustomerRecords(dataset: DatasetOut | undefined): boolean {
  const stats = dataset?.validation?.derived_statistics
  return Array.isArray(stats) && stats.length > 0
}

function dateFormat(locale: string, withYear: boolean) {
  return new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric', ...(withYear ? { year: 'numeric' } : {}), timeZone: 'UTC' })
}

/** "Mar 1 – Mar 31, 2026"; null when the dates are unknown ("Data period unavailable"). */
export function formatDataDates(dates: DataDates | null | undefined, locale: string): string | null {
  if (!dates) return null
  const first = new Date(`${dates.first}T00:00:00Z`)
  const last = new Date(`${dates.last}T00:00:00Z`)
  if (Number.isNaN(first.getTime()) || Number.isNaN(last.getTime())) return null
  if (dates.first === dates.last) return dateFormat(locale, true).format(first)
  const sameYear = first.getUTCFullYear() === last.getUTCFullYear()
  return `${dateFormat(locale, !sameYear).format(first)} – ${dateFormat(locale, true).format(last)}`
}

export function formatDay(iso: string, locale: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric', year: 'numeric' }).format(date)
}

export function minutes(hours: number | null | undefined): number | null {
  return hours === null || hours === undefined || !Number.isFinite(hours) ? null : hours * 60
}
