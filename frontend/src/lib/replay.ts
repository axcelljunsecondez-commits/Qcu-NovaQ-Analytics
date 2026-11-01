// Queue simulation replay helpers (spec 2026-10-09 §7.8, D26, B5). Presentation only: every
// customer and counter state comes from the run's stored events; nothing is re-simulated.
import type { QueueSetup, SelectedDesPeriod, SimulationTrace } from '../api/types'

/** Minutes after midnight, or null for a malformed "HH:MM[:SS]". */
export function clockMinutes(value: string | null | undefined): number | null {
  const match = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/.exec(value ?? '')
  if (!match) return null
  const [hours, minutes, seconds] = [Number(match[1]), Number(match[2]), Number(match[3] ?? 0)]
  if (hours > 23 || minutes > 59 || seconds > 59) return null
  return hours * 60 + minutes + seconds / 60
}

/** The day clock's origin: the earliest configured segment start (as the server's DES uses). */
export function dayOrigin(setup: Pick<QueueSetup, 'segments'> | null | undefined): number | null {
  const starts = (setup?.segments ?? []).map((segment) => clockMinutes(segment.start_time)).filter((value): value is number => value !== null)
  return starts.length > 0 ? Math.min(...starts) : null
}

/** "08:00 - 10:00" (24-hour, owner decision A6): first segment start to last segment end, or null when the setup has no clock times. */
export function operatingHours(setup: Pick<QueueSetup, 'segments'> | null | undefined): string | null {
  const origin = dayOrigin(setup)
  const ends = (setup?.segments ?? []).map((segment) => clockMinutes(segment.end_time)).filter((value): value is number => value !== null)
  if (origin === null || ends.length === 0) return null
  return `${wallClock(0, origin / 60)} - ${wallClock(0, Math.max(...ends) / 60)}`
}

/** "HH:MM" on the store clock for a run time in hours. */
export function wallClock(originMinutes: number, hours: number): string {
  const total = Math.max(0, Math.floor(originMinutes + hours * 60 + 1e-6))
  const hh = Math.floor(total / 60) % 24
  const mm = total % 60
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`
}

/** Run time in hours for a store-clock "HH:MM", or null when it is malformed or before the day. */
export function runTimeFor(originMinutes: number, clock: string): number | null {
  const minutes = clockMinutes(clock)
  if (minutes === null || minutes < originMinutes) return null
  return (minutes - originMinutes) / 60
}

/**
 * The one continuous-day execution as a single trace (D24, B5): every period's events in time
 * order, so the replay never resets between periods. Null unless every period carries its
 * start on the day clock (only the continuous-day run does).
 */
export function mergeDayTrace(periods: SelectedDesPeriod[]): SimulationTrace | null {
  if (periods.length === 0 || periods.some((period) => typeof period.start_hours !== 'number')) return null
  const events = periods.flatMap((period, periodIndex) => period.trace.trace.map((event, index) => ({ event, periodIndex, index })))
  events.sort((left, right) => left.event.t - right.event.t || left.periodIndex - right.periodIndex || left.index - right.index)
  const first = periods[0].trace
  return {
    trace: events.map((item) => item.event),
    trace_hours: first.total_hours,
    total_hours: Math.max(...periods.map((period) => period.trace.total_hours)),
    event_count: events.length,
    truncated: periods.some((period) => period.trace.truncated),
    abandonment_supported: periods.some((period) => period.trace.abandonment_supported),
    segments: periods.flatMap((period) => period.trace.segments),
  }
}

/** B13: a per-date run's periods grouped by the date that starts each label ("YYYY-MM-DD ..."), in order. */
export function periodsByDate(periods: SelectedDesPeriod[]): Array<{ date: string; periods: SelectedDesPeriod[] }> {
  const groups: Array<{ date: string; periods: SelectedDesPeriod[] }> = []
  for (const period of periods) {
    const date = /^(\d{4}-\d{2}-\d{2}) /.exec(period.time)?.[1] ?? ''
    const group = groups.find((item) => item.date === date)
    if (group) group.periods.push(period)
    else groups.push({ date, periods: [period] })
  }
  return groups
}

/** The periods of one continuous day: the chosen date's for a per-date run, otherwise all of them. */
export function dayPeriods(periods: SelectedDesPeriod[], perDate: boolean, date: string | null): { date: string | null; dates: string[]; periods: SelectedDesPeriod[] } {
  if (!perDate) return { date: null, dates: [], periods }
  const groups = periodsByDate(periods)
  const chosen = groups.find((group) => group.date === date) ?? groups[0]
  return { date: chosen?.date ?? null, dates: groups.map((group) => group.date), periods: chosen?.periods ?? [] }
}

/** Counters not staffed at a run time: the inactive lanes of the period that contains it. */
export function inactiveQueueIdsAt(periods: SelectedDesPeriod[], hours: number): string[] {
  const ordered = [...periods].sort((left, right) => (left.start_hours ?? 0) - (right.start_hours ?? 0))
  const current = ordered.filter((period) => (period.start_hours ?? 0) <= hours + 1e-9).at(-1) ?? ordered[0]
  return current?.inactive_queue_ids ?? []
}

export interface ScheduledBreak {
  queueId: string
  startHours: number
  endHours: number
  name: string | null
}

/** Breaks from the setup on the run clock, shown on their own row ("Scheduled break (from your setup)"). */
export function scheduledBreaks(setup: Pick<QueueSetup, 'segments' | 'breaks'> | null | undefined): ScheduledBreak[] {
  const origin = dayOrigin(setup)
  if (origin === null) return []
  return (setup?.breaks ?? []).flatMap((entry) => {
    const start = clockMinutes(entry.scheduled_start_time)
    if (start === null || !(entry.duration_minutes > 0)) return []
    const startHours = (start - origin) / 60
    return [{ queueId: String(entry.queue_id), startHours, endHours: startHours + entry.duration_minutes / 60, name: entry.break_name ?? null }]
  })
}

export function hasBreakEvents(trace: SimulationTrace): boolean {
  return trace.trace.some((event) => event.type === 'draining_start' || event.type === 'break_start' || event.type === 'break_end')
}

export const SAMPLE_MINUTES = 5

/** People waiting through the day, read from one continuous run's events (never re-simulated). */
export function waitingThroughTheDay(trace: SimulationTrace, stepHours = SAMPLE_MINUTES / 60): Array<{ hours: number; waiting: number }> {
  const end = Math.max(trace.total_hours, trace.trace.at(-1)?.t ?? 0)
  const points: Array<{ hours: number; waiting: number }> = []
  let index = 0
  let waiting = 0
  for (let hours = 0; hours <= end + 1e-9; hours += stepHours) {
    while (index < trace.trace.length && trace.trace[index].t <= hours + 1e-9) {
      const type = trace.trace[index].type
      if (type === 'arrival') waiting += 1
      else if (type === 'service_start' || type === 'abandon') waiting -= 1
      index += 1
    }
    points.push({ hours, waiting })
  }
  return points
}
