// Longest Single Line table (spec 2026-10-29 §7.4, owner decision B6). Shaping only: every number
// is a stored max_queue of the run shown; a cashier that is not staffed in a period stays "not
// staffed", never zero, and a missing value stays null. "Not staffed" comes from staffing data only.
import type { QueueSetup, SelectedDesPeriod, SimDesOut } from '../api/types'

export interface LongestCell {
  lane: string
  /** false = not staffed (hatched); null = the staffing of this period is not known, so nothing is hatched. */
  staffed: boolean | null
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
  /** Every period's staffing is known (from the Setup or the plan), so "not staffed" can be shown. */
  staffingKnown: boolean
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

function build(lanes: string[], periods: Array<{ time: string; cell: (lane: string) => LongestCell }>, staffingKnown: boolean): LongestMatrix {
  const rows = periods.map(({ time, cell }) => {
    const cells = lanes.map(cell)
    const values = cells.filter((item) => item.staffed === true && item.value !== null).map((item) => item.value as number)
    return { time, cells, max: values.length > 0 ? Math.max(...values) : null }
  })
  const maxes = rows.map((row) => row.max).filter((value): value is number => value !== null)
  const dayMax = maxes.length > 0 ? Math.max(...maxes) : null
  const peaks = dayMax === null ? [] : rows.flatMap((row) => row.cells
    .filter((item) => item.staffed === true && item.value === dayMax)
    .map((item) => ({ time: row.time, lane: item.lane })))
  return { lanes, rows, dayMax, peaks, staffingKnown }
}

export type StaffingSetup = Pick<QueueSetup, 'queue_ids' | 'segments' | 'staffing_varies_by_period'>

/**
 * The cashiers the Setup staffs in each Current-run segment, resolved as the engine does
 * (queue_lifecycle.scheduled_active_queue_ids): every cashier when staffing does not vary, otherwise the
 * segment's active_queue_ids. Keys are the engine's segment ids (the segment's id, else segment_<n>,
 * simulation._parallel_schedule), which the Current run stamps on each row as segment_id.
 */
export function setupStaffing(setup: StaffingSetup): { all: Set<string> | null; bySegment: Map<string, Set<string>> } {
  const queueIds = (setup.queue_ids ?? []).map(String)
  if (!setup.staffing_varies_by_period) return { all: new Set(queueIds), bySegment: new Map() }
  const bySegment = new Map<string, Set<string>>()
  ;(setup.segments ?? []).forEach((segment, index) => {
    if (segment.active_queue_ids) bySegment.set(String(segment.id || `segment_${index + 1}`), new Set(segment.active_queue_ids.map(String)))
  })
  return { all: null, bySegment }
}

/**
 * The Current run (one DES per period and cashier). Whether a cashier is staffed comes from the Setup's
 * staffing for the row's segment (setupStaffing), never from a missing row: the run also returns rows for
 * cashiers it kept closed. When a period's staffing is not known, nothing is hatched and a missing row has
 * no value. A row whose period could not be simulated has no value.
 */
export function currentMatrix(rows: readonly SimDesOut[], setup: StaffingSetup): LongestMatrix | null {
  const laneRows = rows.filter((row) => typeof row.queue_id === 'string' && row.queue_id.trim() !== '')
  if (laneRows.length === 0) return null
  const staffing = setupStaffing(setup)
  const times: string[] = []
  const byKey = new Map<string, SimDesOut>()
  const segmentsOf = new Map<string, Set<string>>()
  for (const row of laneRows) {
    if (!times.includes(row.time)) times.push(row.time)
    const key = `${row.time}\u0000${row.queue_id as string}`
    if (!byKey.has(key)) byKey.set(key, row)
    const segment = row.segment_id === undefined || row.segment_id === null ? '' : String(row.segment_id)
    segmentsOf.set(row.time, (segmentsOf.get(row.time) ?? new Set<string>()).add(segment))
  }
  // A period's staffing is known when staffing does not vary, or its rows name one Setup segment.
  const staffedIn = (time: string): Set<string> | null => {
    if (staffing.all) return staffing.all
    const ids = [...(segmentsOf.get(time) ?? [])]
    return ids.length === 1 && ids[0] !== '' ? staffing.bySegment.get(ids[0]) ?? null : null
  }
  const lanes = laneOrder(setup.queue_ids ?? [], laneRows.map((row) => row.queue_id as string))
  return build(lanes, times.map((time) => ({
    time,
    cell: (lane: string): LongestCell => {
      const active = staffedIn(time)
      if (active && !active.has(lane)) return { lane, staffed: false, value: null, rho: null }
      const row = byKey.get(`${time}\u0000${lane}`)
      if (!row) return { lane, staffed: active ? true : null, value: null, rho: null }
      const simulated = !row.error && row.simulation_supported !== false
      return { lane, staffed: true, value: simulated ? finite(row.max_queue) : null, rho: simulated ? finite(row.rho_sim) : null }
    },
  })), times.every((time) => staffedIn(time) !== null))
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
  })), true)
}
