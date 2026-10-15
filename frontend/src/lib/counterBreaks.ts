import type { CounterBreak } from '../api/types'

/** Whether every counter break has a start time and a whole number of minutes, 1 or more. */
export function counterBreaksValid(breaks: CounterBreak[]): boolean {
  return breaks.every((entry) => Boolean(entry.scheduled_start_time)
    && Number.isInteger(entry.duration_minutes) && entry.duration_minutes >= 1 && entry.duration_minutes <= 1440)
}
