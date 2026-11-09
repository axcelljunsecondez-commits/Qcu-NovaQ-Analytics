// Per-date separate-lines Current runs (C-PD spec 2026-10-30 §7.4; C-PD-C spec 2026-11-02 §6-§9, A6).
// A run of two or more dates is stored compactly (execution 'current_per_date_days_compact'): rows and the
// server summary cover all dates; one date's trace is fetched on demand from the day-detail route.
import type { RunSummary, SimDesOut, SimulationTrace } from '../api/types'

export const CURRENT_COMPACT_EXECUTION = 'current_per_date_days_compact'

/** Whether a stored Current result is the compact per-date shape (chosen by `execution`, spec §7). */
export function isCompactCurrent(result: SimulationTrace | null | undefined): result is SimulationTrace & { days: NonNullable<SimulationTrace['days']> } {
  return result?.execution === CURRENT_COMPACT_EXECUTION && Array.isArray(result.days)
}

/** The run's dates, in the server's order. */
export function compactDates(result: SimulationTrace): string[] {
  return (result.days ?? []).map((day) => day.date)
}

/** The date the address asks for when it is in the run, else the run's first date (the `date` param is shared with Suggested). */
export function chosenCurrentDate(dates: readonly string[], requested: string | null): string | null {
  return requested !== null && dates.includes(requested) ? requested : dates[0] ?? null
}

/** The stored rows of one date (compact rows carry `date`). */
export function rowsForDate<T extends Pick<SimDesOut, 'date'>>(rows: readonly T[], date: string): T[] {
  return rows.filter((row) => row.date === date)
}

/** The server's summary with only the periods of one date (their label starts with "<date> "). Totals are untouched. */
export function summaryForDate(summary: RunSummary, date: string): RunSummary {
  return { ...summary, periods: summary.periods.filter((period) => period.time.startsWith(`${date} `)) }
}

/** How many open queue periods had no customer record on this date (OD-C2 (i)); null date counts every entry. */
export function zeroArrivalCount(result: SimulationTrace, date: string | null): number {
  return (result.zero_arrival_lane_periods ?? []).filter((item) => date === null || item.date === date).length
}

/** The seed a Current run used: the requested one, else the one the server drew (OD-C12 (i)). */
export function shownSeed(params: Record<string, unknown> | undefined, result: SimulationTrace | null | undefined): number | null {
  const requested = params?.seed
  if (typeof requested === 'number') return requested
  return typeof result?.seed_used === 'number' ? result.seed_used : null
}

/** The CSV file name of one date's rows. */
export function dateCsvName(date: string): string {
  return `novaq_unified_des_${date}.csv`
}

function errorOf(error: unknown): { status?: number; detail?: unknown } {
  const response = (error as { response?: { status?: number; data?: { detail?: unknown } } } | null)?.response
  return { status: response?.status, detail: response?.data?.detail }
}

/**
 * The date count of a per-date Current 413 (W1), read from the server's English detail ("N dates"), or null.
 * Only a 413 is read; the detail itself is never shown.
 */
export function tooLargeDates(error: unknown): number | null {
  const { status, detail } = errorOf(error)
  if (status !== 413 || typeof detail !== 'string') return null
  const match = /(\d+) dates/.exec(detail)
  return match ? Number(match[1]) : null
}

/** The message key of a failed day-detail request: 404 W3, 409 W2, anything else the generic server error. */
export function dayDetailErrorKey(error: unknown): string {
  const { status } = errorOf(error)
  if (status === 404) return 'simulation.current_day_not_found'
  if (status === 409) return 'simulation.current_day_mismatch'
  return 'errors.server'
}
