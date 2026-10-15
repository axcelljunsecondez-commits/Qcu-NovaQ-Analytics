// Period helpers for Data and setup (spec 2026-10-09 §7.6, §8).
// Periods stay on one calendar day: setup times are HH:MM up to 23:59, so a
// period may not end at 24:00 or later (no overnight support, backend item B7).

export const PERIOD_LENGTHS = [15, 30, 60] as const
export type PeriodLength = (typeof PERIOD_LENGTHS)[number]
export const MAX_PERIODS = 24
// Numbers typed in Data and setup (B9) upload as this file; the server names the
// dataset after the file name without its extension (backend/api/analyses.py:221).
export const MANUAL_ENTRY_DATASET_NAME = 'entered-by-you'
export const MANUAL_ENTRY_FILE_NAME = `${MANUAL_ENTRY_DATASET_NAME}.csv`

export interface Period {
  start: string
  end: string
}

export function toMinutes(value: string): number | null {
  const match = /^(\d{2}):(\d{2})/.exec(value)
  if (!match) return null
  const hours = Number(match[1])
  const minutes = Number(match[2])
  if (hours > 23 || minutes > 59) return null
  return hours * 60 + minutes
}

export function toTime(totalMinutes: number): string {
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

export type MakePeriodsError = 'bad_start' | 'bad_count' | 'bad_length' | 'crosses_midnight'

// Consecutive periods of one length starting at `start`; an error when they would leave the day.
export function makePeriods(start: string, count: number, length: number): Period[] | MakePeriodsError {
  const first = toMinutes(start)
  if (first === null) return 'bad_start'
  if (!Number.isInteger(count) || count < 1 || count > MAX_PERIODS) return 'bad_count'
  if (!(PERIOD_LENGTHS as readonly number[]).includes(length)) return 'bad_length'
  const last = first + count * length
  if (last > 23 * 60 + 59) return 'crosses_midnight'
  return Array.from({ length: count }, (_, index) => ({
    start: toTime(first + index * length),
    end: toTime(first + (index + 1) * length),
  }))
}

export interface ManualRow {
  start: string
  arrivalsPerHour: string
  servedPerHourPerCounter: string
  counters: string
}

export type ManualRowError = 'arrivals' | 'served' | 'counters'

// Mirrors the server's aggregate rules (backend/data/ingestion.py validate_and_normalize):
// lambda finite and >= 0, mu finite and > 0, c an integer from 1 to 100000.
export function manualRowError(row: ManualRow): ManualRowError | null {
  const lambda = Number(row.arrivalsPerHour)
  const mu = Number(row.servedPerHourPerCounter)
  const c = Number(row.counters)
  if (row.arrivalsPerHour.trim() === '' || !Number.isFinite(lambda) || lambda < 0) return 'arrivals'
  if (row.servedPerHourPerCounter.trim() === '' || !Number.isFinite(mu) || mu <= 0) return 'served'
  if (row.counters.trim() === '' || !Number.isInteger(c) || c < 1 || c > 100000) return 'counters'
  return null
}

// Shared aggregate rows carry no duration and costs are summed as hourly rates
// (plan task 4.6), so entered rows are always one hour long.
export function buildAggregateCsv(rows: ManualRow[]): string {
  const lines = rows.map((row) => {
    const start = toMinutes(row.start) ?? 0
    return [`${toTime(start)}-${toTime(start + 60)}`, row.arrivalsPerHour.trim(), row.servedPerHourPerCounter.trim(), row.counters.trim()].join(',')
  })
  return ['time,lambda,mu,c', ...lines].join('\n') + '\n'
}
