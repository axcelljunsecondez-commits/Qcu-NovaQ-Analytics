// Longest Single Line table (spec 2026-10-29 §7.4, owner decision B6). Shaping only: every number
// is a stored max_queue of the run shown; a cashier that is not staffed in a period stays "not
// staffed", never zero, and a missing value stays null.
import type { SelectedDesPeriod, SimDesOut } from '../api/types'

export interface LongestCell {
  lane: string
  staffed: boolean
  /** The run's max_queue for this cashier and period; null when the run returned none. */
  value: number | null
  rho: number | null
}

export interface LongestRow {
  time: string
  cells: LongestCell[]
  /** Largest value among the staffed cashiers of the period; null when none has a value. */
  max: number | null
}

export interface LongestMatrix {
  lanes: string[]
  rows: LongestRow[]
  /** Largest value of the whole run shown; null when no cell has a value. */
  dayMax: number | null
  /** Every staffed cell that holds the run's largest value, in table order. */
  peaks: Array<{ time: string; lane: string }>
}

function finite(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** Cashiers in the Setup's order, then any other lane the run returned, in the order it appears. */
export function laneOrder(queueIds: readonly string[], seen: readonly string[]): string[] {
  const lanes = [...queueIds]
  for (const lane of seen) if (!lanes.includes(lane)) lanes.push(lane)
  return lanes
}

function build(lanes: string[], periods: Array<{ time: string; cell: (lane: string) => LongestCell }>): LongestMatrix {
  const rows = periods.map(({ time, cell }) => {
    const cells = lanes.map(cell)
    const values = cells.filter((item) => item.staffed && item.value !== null).map((item) => item.value as number)
    return { time, cells, max: values.length > 0 ? Math.max(...values) : null }
  })
  const maxes = rows.map((row) => row.max).filter((value): value is number => value !== null)
  const dayMax = maxes.length > 0 ? Math.max(...maxes) : null
  const peaks = dayMax === null ? [] : rows.flatMap((row) => row.cells
    .filter((item) => item.staffed && item.value === dayMax)
    .map((item) => ({ time: row.time, lane: item.lane })))
  return { lanes, rows, dayMax, peaks }
}

/**
 * The Current run (one DES per period and cashier). A cashier with no row in a period is shown as
 * not staffed (spec §7.4; the Setup segment mapping is not used until it is checked in the browser).
 * A row whose period could not be simulated has no value.
 */
export function currentMatrix(rows: readonly SimDesOut[], queueIds: readonly string[]): LongestMatrix | null {
  const laneRows = rows.filter((row) => typeof row.queue_id === 'string' && row.queue_id.trim() !== '')
  if (laneRows.length === 0) return null
  const times: string[] = []
  const byKey = new Map<string, SimDesOut>()
  for (const row of laneRows) {
    if (!times.includes(row.time)) times.push(row.time)
    const key = `${row.time}\u0000${row.queue_id as string}`
    if (!byKey.has(key)) byKey.set(key, row)
  }
  const lanes = laneOrder(queueIds, laneRows.map((row) => row.queue_id as string))
  return build(lanes, times.map((time) => ({
    time,
    cell: (lane: string): LongestCell => {
      const row = byKey.get(`${time}\u0000${lane}`)
      if (!row) return { lane, staffed: false, value: null, rho: null }
      const simulated = !row.error && row.simulation_supported !== false
      return { lane, staffed: true, value: simulated ? finite(row.max_queue) : null, rho: simulated ? finite(row.rho_sim) : null }
    },
  })))
}

/** The Suggested plan's continuous day (the chosen date for a per-date plan): its lane rows per period. */
export function planMatrix(periods: readonly SelectedDesPeriod[], queueIds: readonly string[]): LongestMatrix | null {
  const seen = periods.flatMap((period) => period.results.map((row) => row.queue_id).filter((id): id is string => typeof id === 'string' && id !== ''))
  if (seen.length === 0) return null
  const lanes = laneOrder(queueIds, seen)
  return build(lanes, periods.map((period) => ({
    time: period.time,
    cell: (lane: string): LongestCell => {
      const row = period.results.find((item) => item.queue_id === lane)
      const inactive = period.inactive_queue_ids.includes(lane) || row?.active === false
      if (inactive) return { lane, staffed: false, value: null, rho: null }
      if (!row) return period.active_queue_ids.includes(lane) ? { lane, staffed: true, value: null, rho: null } : { lane, staffed: false, value: null, rho: null }
      return { lane, staffed: true, value: finite(row.max_queue), rho: finite(row.rho_sim) }
    },
  })))
}
