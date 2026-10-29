import type { ContinuousEvent, ContinuousPlan, ContinuousRunListItem, MetricSummary } from '../api/continuous'

/** Choose whole replications from the server's default and request budget; null means invalid metadata. */
export function automaticReplications(
  expectedCustomers: number | null,
  defaultCount: number,
  limits: { max_replications: number; max_expected_customers_per_run: number },
): number | null {
  const maxCount = limits.max_replications
  const customerBudget = limits.max_expected_customers_per_run
  if (!Number.isInteger(defaultCount) || defaultCount < 1 || !Number.isInteger(maxCount) || maxCount < 1
    || !Number.isFinite(customerBudget) || customerBudget <= 0
    || expectedCustomers === null || !Number.isFinite(expectedCustomers) || expectedCustomers < 0) return null
  const affordable = expectedCustomers === 0 ? maxCount : Math.floor(customerBudget / expectedCustomers)
  const count = Math.min(defaultCount, maxCount, affordable)
  // Match the API's multiplication check at a floating-point budget boundary.
  return count * expectedCustomers > customerBudget ? Math.max(0, count - 1) : count
}

/** "HH:MM" for whole minutes since midnight (the run's horizon). */
export function clockOfMinutes(minutes: number): string {
  const total = Math.max(0, Math.floor(minutes + 1e-6))
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

/** Store clock for a run time in hours from the horizon start. */
export function clockAt(startMinute: number, hours: number): string {
  return clockOfMinutes(startMinute + hours * 60)
}

/** Run time in hours for an "HH:MM" store time, or null when it is not a time on this day's clock. */
export function hoursAt(startMinute: number, value: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim())
  if (!match) return null
  const [hh, mm] = [Number(match[1]), Number(match[2])]
  if (hh > 23 || mm > 59) return null
  const hours = (hh * 60 + mm - startMinute) / 60
  return hours >= 0 ? hours : null
}

/** The newest stored run of each staffing source (runs arrive newest first). */
export function latestRunIds(runs: ContinuousRunListItem[]): Partial<Record<ContinuousPlan, number>> {
  const latest: Partial<Record<ContinuousPlan, number>> = {}
  for (const run of runs) {
    if (latest[run.plan] === undefined) latest[run.plan] = run.id
  }
  return latest
}

/** People waiting after every event, as the engine recorded it (a step line; nothing is sampled or summed). */
export function waitingSteps(events: ContinuousEvent[]): Array<{ hours: number; waiting: number }> {
  return events.map((event) => ({ hours: event.t, waiting: event.queue_len_after }))
}

export interface DayState {
  waiting: number
  serving: number
  idle: number
  draining: number
  onBreak: number
  breaksWaiting: number
  arrived: number
  served: number
  unserved: number
  event: ContinuousEvent | null
}

/** The line and counters after the last event at or before ``hours``, read from the events only. */
export function stateAt(events: ContinuousEvent[], hours: number): DayState {
  const state: DayState = { waiting: 0, serving: 0, idle: 0, draining: 0, onBreak: 0, breaksWaiting: 0, arrived: 0, served: 0, unserved: 0, event: null }
  for (const event of events) {
    if (event.t > hours + 1e-9) break
    if (event.type === 'arrival') state.arrived += 1
    else if (event.type === 'service_end') state.served += 1
    else if (event.type === 'unserved_at_close') state.unserved += 1
    state.waiting = event.queue_len_after
    state.serving = event.servers_busy_after
    state.idle = event.servers_idle_after
    state.draining = event.servers_draining_after
    state.onBreak = event.servers_on_break_after ?? 0
    state.breaksWaiting = event.breaks_waiting_after ?? 0
    state.event = event
  }
  return state
}

/** "mean (min–max)" of a metric, with ``scale`` applied; null when the mean is undefined. */
export function rangeText(metric: MetricSummary | undefined, format: (value: number) => string, scale = 1): string | null {
  if (!metric || metric.mean === null) return null
  const value = format(metric.mean * scale)
  if (metric.min === null || metric.max === null || metric.min === metric.max) return value
  return `${value} (${format(metric.min * scale)}–${format(metric.max * scale)})`
}
