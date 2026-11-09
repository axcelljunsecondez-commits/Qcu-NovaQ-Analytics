import { describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { AnalysisProjectOut, RunSummary } from '../../api/types'
import type { WorkflowEvidence } from '../../api/workflow'
import { renderWithProviders } from '../../test/test-utils'
import en from '../../../public/locales/en/translation.json'
import tl from '../../../public/locales/tl/translation.json'
import { KeyResultsView } from './KeyResultsView'
import { buildContext, type RunChoice } from './simulationContext'

// Key Results (spec 2026-10-29 §7.3, §7.4; owner decisions B5, B6).

// A6: observe CSV downloads, and fail if Key results ever asks for a day's detail (it must not fetch).
const spies = vi.hoisted(() => ({ downloadCsv: vi.fn(), getCurrentDay: vi.fn() }))
vi.mock('../../lib/format', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../lib/format')>()),
  downloadCsv: (...args: unknown[]) => spies.downloadCsv(...args),
}))
vi.mock('../../api/workflow', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/workflow')>()),
  getCurrentDay: (...args: unknown[]) => spies.getCurrentDay(...args),
}))

const perPeriod: RunSummary = {
  basis: 'per_period', average_wait_hours: 0.1, longest_line: 4, arrivals: null, served: null, in_system_at_close: null,
  periods: [{ time: '08:00', average_wait_hours: 0.1, longest_line: 4, arrivals: null, served: null }],
}
const continuousDay: RunSummary = {
  basis: 'continuous_day', average_wait_hours: 0.05, longest_line: 2, arrivals: 30, served: 29, in_system_at_close: 1,
  periods: [{ time: '08:00', average_wait_hours: 0.05, longest_line: 2, arrivals: 30, served: 29 }],
}

const emptyTrace = { trace: [], trace_hours: 1, total_hours: 1, event_count: 0, truncated: false, abandonment_supported: false, segments: [] }
const laneRow = (queue: string, maxQueue: number | null, active = true) => ({
  time: '08:00', queue_id: queue, server_id: `server:${queue}`, lambda: 2, lambda_routed: 2, mu: 3, c: 1, arrivals: 4, served: 4, waiting: 0,
  in_service: 0, abandoned: null, Wq_sim: 0.05, rho_sim: 0.4, max_queue: maxQueue, active, simulation_supported: true, error: null,
  metric_provenance: 'simulated', customer_conservation: true,
})
const desRow = (queue: string, maxQueue: number) => ({
  time: '08:00', queue_id: queue, lambda: 2, mu: 3, c: 1, rho_sim: 0.4, Lq_sim: 0.2, Wq_sim: 0.05, max_queue: maxQueue, served: 4, dropped: 0,
  status: 'Normal', error: null, simulation_supported: true,
})

function planResult(summary: RunSummary, days?: unknown) {
  return {
    provenance: 'SELECTED', scenario_id: 9, analysis_id: 7, dataset_id: 2, seed: 42, duration_hours: 1, overall_conservation: true, overall_status: 'COMPLETED',
    periods: [{ time: '08:00', start_hours: 0, duration_hours: 1, active_queue_ids: ['c1'], inactive_queue_ids: ['c2'], evaluation_status: 'FEASIBLE', conservation: true,
      total_lambda: 2, total_cost: null, server_cost: null, waiting_cost: null, results: [laneRow('c1', 3), laneRow('c2', 7, false)], trace: emptyTrace }],
    summary, ...(days ? { days } : {}),
  }
}

function job(kind: string, result: unknown, params: Record<string, unknown> = {}) {
  return { id: 1, kind, status: 'completed', params: { analysis_id: 7, ...params }, result, created_at: '2026-10-29T00:00:00Z', finished_at: null }
}

interface Options {
  separate?: boolean
  queueStructure?: 'shared_queue' | 'single_server'
  basis?: 'representative_day' | 'per_date'
  breaks?: boolean
  now?: RunSummary | null
  plan?: RunSummary | null
  /** Per-date plan days (server field `days`). */
  days?: unknown[]
}

function renderView(run: RunChoice, { separate = true, queueStructure = 'shared_queue', basis = 'representative_day', breaks = true, now = perPeriod, plan = continuousDay, days }: Options = {}, lang: 'en' | 'tl' = 'en') {
  const analysis = {
    id: 7, name: 'Checkout',
    queue_setup: {
      queue_structure: separate ? 'separate_queues' : queueStructure, event_period_basis: basis, queue_ids: ['c1', 'c2'],
      segments: [{ id: 's1', start_time: '08:00', end_time: '09:00', active_queue_ids: null }],
      breaks: breaks ? [{ queue_id: 'c1', scheduled_start_time: '08:30', duration_minutes: 15 }] : [],
    },
  } as unknown as AnalysisProjectOut
  const scenario = separate
    ? { id: 9, name: 'Plan', dataset_id: 2, provenance: 'verified_snapshot', settings: { calculation: { schema_version: 2, options: { target_utilization: 0.85 } } } }
    : { id: 9, name: 'Plan', dataset_id: 2, provenance: 'verified_snapshot' }
  const planRun = plan === null ? null : separate ? planResult(plan, days) : { ...emptyTrace, results: [], summary: plan }
  const workflow = {
    analysis_id: 7, selection: null, scenario,
    des: planRun ? job('workflow_des', planRun, { scenario_id: 9, seed: 42 }) : null,
    des_current: now ? job('workflow_des_current', { ...emptyTrace, results: [desRow('c1', 2), desRow('c2', 5)], summary: now }, { seed: null }) : null,
    mc: null, validation: null, mc_current: null, validation_current: null, decision: null, decision_stale: false,
  } as unknown as WorkflowEvidence
  return renderWithProviders(<KeyResultsView context={buildContext(7, analysis, workflow)} run={run} />, { lang })
}

describe('Key Results cards (B5)', () => {
  it('shows two cards, Current and Suggested plan, with no arrow', () => {
    renderView('suggested')
    const cards = screen.getByRole('group', { name: 'Key Results' })
    expect(within(cards).getAllByRole('region').map((card) => card.getAttribute('aria-label'))).toEqual(['Average wait', 'Longest Single Line'])
    expect(cards).not.toHaveTextContent('→')
    expect(within(cards).getByRole('region', { name: 'Average wait' })).toHaveTextContent('Current: 6 min')
    expect(within(cards).getByRole('region', { name: 'Average wait' })).toHaveTextContent('Suggested plan: 3 min')
  })

  // Separate lines (K-UC-3): the Current run is one continuous run over the Setup's periods without breaks,
  // never "one period at a time" (simulation.py _simulate_parallel_segments_core).
  it.each([
    ['a continuous plan day with breaks', {}, en['charts.key_basis_separate']],
    ['a continuous plan day without breaks', { breaks: false }, en['charts.key_basis_no_breaks_separate']],
    ['one continuous run per date', { basis: 'per_date' as const }, en['charts.key_basis_per_date_separate']],
  ])('explains the different basis for %s (separate lines)', async (_case, options, text) => {
    const user = userEvent.setup()
    renderView('suggested', options)
    const buttons = screen.getAllByRole('button', { name: 'Why these are not the same basis' })
    expect(buttons).toHaveLength(2)
    await user.hover(buttons[0])
    expect(screen.getByRole('tooltip')).toHaveTextContent(text)
    expect(screen.getByRole('tooltip')).not.toHaveTextContent(/one period at a time/i)
    expect(screen.getByTestId('key-take')).toHaveTextContent('Simulated average wait: Current 6 min, Suggested plan 3 min, from two runs set up differently.')
  })

  it('keeps the per-period basis text for a shared line, whose Current run does go one period at a time', async () => {
    const user = userEvent.setup()
    renderView('suggested', { separate: false })
    await user.hover(screen.getAllByRole('button', { name: 'Why these are not the same basis' })[0])
    expect(screen.getByRole('tooltip')).toHaveTextContent(en['charts.key_basis'])
  })

  it('names the separate Current run one continuous run without breaks in its chips; a shared Current run stays per period', () => {
    const { unmount } = renderView('current')
    const chips = within(screen.getByTestId('key-details')).getAllByText((_, element) => element?.classList.contains('cv-chip-cur') ?? false)
    expect(chips[0]).toHaveTextContent(`${en['simulation.run_current']} · ${en['simulation.run_basis_continuous_no_breaks']}`)
    expect(chips[0]).not.toHaveTextContent(en['simulation.run_basis_per_period'])
    expect(screen.getByTestId('longest-line-table')).toHaveTextContent(en['simulation.run_basis_continuous_no_breaks'])
    expect(screen.getByTestId('longest-line-table')).not.toHaveTextContent(/1 simulation run per period/i)
    expect(document.body).not.toHaveTextContent(/one period at a time/i)
    expect(screen.getByText(en['simulation.chart_waiting_needs_plan_day'])).toBeInTheDocument()
    unmount()
    renderView('current', { separate: false, plan: null })
    const shared = within(screen.getByTestId('key-details')).getAllByText((_, element) => element?.classList.contains('cv-chip-cur') ?? false)
    expect(shared[0]).toHaveTextContent(`${en['simulation.run_current']} · ${en['simulation.run_basis_per_period']} · ${en['charts.chip_no_breaks']}`)
  })

  it('has no basis explanation when both runs share a basis or one is missing', () => {
    const { unmount } = renderView('suggested', { plan: { ...perPeriod, average_wait_hours: 0.05 } })
    expect(screen.queryByRole('button', { name: 'Why these are not the same basis' })).not.toBeInTheDocument()
    expect(screen.getByTestId('key-take')).toHaveTextContent('Simulated average wait: Current 6 min, Suggested plan 3 min.')
    unmount()
    renderView('suggested', { now: null })
    expect(screen.queryByRole('button', { name: 'Why these are not the same basis' })).not.toBeInTheDocument()
    expect(screen.queryByTestId('key-take')).not.toBeInTheDocument()
  })
})

describe('closing alert (B5)', () => {
  it.each([[0], [null]])('is absent when the plan leaves %s customers in line', (value) => {
    renderView('suggested', { plan: { ...continuousDay, in_system_at_close: value } })
    expect(screen.queryByTestId('closing-alert')).not.toBeInTheDocument()
  })

  it('uses the one and other forms in English', () => {
    const { unmount } = renderView('suggested', { plan: { ...continuousDay, in_system_at_close: 1 } })
    expect(screen.getByTestId('closing-alert')).toHaveTextContent('1 customer still in line or being served at closing in the plan’s simulated day.')
    expect(screen.getByTestId('closing-alert')).toHaveAttribute('role', 'status')
    unmount()
    renderView('suggested', { plan: { ...continuousDay, in_system_at_close: 2 } })
    expect(screen.getByTestId('closing-alert')).toHaveTextContent('2 customers still in line or being served at closing in the plan’s simulated day.')
  })

  // A per-date plan's in_system_at_close is the server's total over all dates (workflow.py at_close_total),
  // so the "plan's simulated day" alert is shown only for one simulated day.
  const day = (date: string, atClose: number) => ({ date, admitted: 30, served: 30 - atClose, in_system_at_close: atClose, customer_conservation: true, day_hours: 1 })

  it('is not shown for a per-date plan over several dates; the total stays in More Results', () => {
    renderView('suggested', { basis: 'per_date', plan: { ...continuousDay, in_system_at_close: 3 }, days: [day('2026-10-01', 1), day('2026-10-02', 2)] })
    expect(screen.queryByTestId('closing-alert')).not.toBeInTheDocument()
    const atClose = screen.getByRole('region', { name: en['simulation.not_served_at_close'] })
    expect(atClose.closest('details')).not.toBeNull()
    expect(atClose).toHaveTextContent('Current: Unavailable')
    expect(atClose).toHaveTextContent('Suggested plan: 3')
    expect(atClose).toHaveTextContent(en['simulation.totals_all_dates'].replace('{{dates}}', '2'))
  })

  it('is shown for a per-date plan with one date', () => {
    renderView('suggested', { basis: 'per_date', plan: { ...continuousDay, in_system_at_close: 2 }, days: [day('2026-10-01', 2)] })
    expect(screen.getByTestId('closing-alert')).toHaveTextContent('2 customers still in line or being served at closing in the plan’s simulated day.')
    expect(screen.queryByRole('region', { name: en['simulation.not_served_at_close'] })).not.toBeInTheDocument()
  })

  it('is not shown for a per-date plan whose days are missing', () => {
    renderView('suggested', { basis: 'per_date', plan: { ...continuousDay, in_system_at_close: 2 } })
    expect(screen.queryByTestId('closing-alert')).not.toBeInTheDocument()
  })

  // Spec §14 plural risk: i18next picks the TL "one" form for 1, 2 and 3; both TL forms read for any count.
  it.each([[1], [2], [4]])('prints the Tagalog alert for %s', (count) => {
    renderView('suggested', { plan: { ...continuousDay, in_system_at_close: count } }, 'tl')
    expect(screen.getByTestId('closing-alert')).toHaveTextContent(tl['charts.closing_alert_other'].replace('{{count}}', String(count)))
  })
})

describe('More results (B5, B9)', () => {
  it('holds Customer Served with the Unavailable explanation on the period-by-period side only', async () => {
    const user = userEvent.setup()
    const { container } = renderView('suggested')
    const served = screen.getByRole('region', { name: 'Customer Served' })
    expect(served.closest('details')).not.toBeNull()
    expect(served).toHaveTextContent('Current: Unavailable')
    expect(served).toHaveTextContent('Suggested plan: 29')
    const why = within(served).getAllByRole('button', { name: 'Why this is unavailable' })
    expect(why).toHaveLength(1)
    await user.hover(why[0])
    // Separate Current is one continuous run without customer totals, not a per-period run (K-UC-3).
    expect(screen.getByRole('tooltip')).toHaveTextContent(en['charts.key_unavailable_explain_separate'])
    expect(container).not.toHaveTextContent(en['simulation.per_period_totals_note'])
    expect(screen.queryByRole('region', { name: en['simulation.not_served_at_close'] })).not.toBeInTheDocument()
  })

  it.each(['shared_queue', 'single_server'] as const)('keeps legacy %s guidance independent of an unsupported full-day run', async (queueStructure) => {
    const user = userEvent.setup()
    renderView('suggested', { separate: false, queueStructure })
    const served = screen.getByRole('region', { name: 'Customer Served' })
    await user.hover(within(served).getAllByRole('button', { name: 'Why this is unavailable' })[0])
    expect(screen.getByRole('tooltip')).toHaveTextContent(en['charts.key_unavailable_explain'])
    expect(screen.getByRole('tooltip')).not.toHaveTextContent('full-day run above')
  })

  it('shows no explanation when the summary is missing (run again instead)', () => {
    renderView('current', { now: null, plan: null })
    expect(screen.queryByRole('button', { name: 'Why this is unavailable' })).not.toBeInTheDocument()
  })

  it('keeps every period when a per-date run lists the same label twice, without a React key warning', () => {
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
    const repeated: RunSummary = {
      ...perPeriod,
      periods: [
        { time: '2000-01-03 11:00-12:00 UTC', average_wait_hours: 0.1, longest_line: 1, arrivals: null, served: null },
        { time: '2000-01-04 11:00-12:00 UTC', average_wait_hours: 0.2, longest_line: 2, arrivals: null, served: null },
        { time: '2000-01-03 11:00-12:00 UTC', average_wait_hours: 0.3, longest_line: 3, arrivals: null, served: null },
      ],
    }
    renderView('current', { now: repeated })
    const table = screen.getByRole('region', { name: en['simulation.period_table'] })
    expect(within(table).getAllByRole('rowheader', { name: '2000-01-03 11:00-12:00 UTC' })).toHaveLength(2)
    expect(within(table).getAllByRole('rowheader')).toHaveLength(3)
    expect(errors.mock.calls.some((call) => String(call[0]).includes('same key'))).toBe(false)
    errors.mockRestore()
  })

  it('draws the SVG wait-by-period chart for the period-by-period run', () => {
    renderView('current', { separate: false, plan: null })
    expect(screen.getByRole('region', { name: en['simulation.des_table_caption'] })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: en['simulation.chart_wait_by_period'] })).toBeInTheDocument()
  })
})

describe('Longest Single Line table (B6)', () => {
  it('reads the plan run per cashier, with the inactive lane not staffed', () => {
    renderView('suggested')
    const table = screen.getByTestId('longest-line-table')
    const row = within(table).getByRole('row', { name: /^08:00/ })
    expect(within(row).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['3', `—${en['simulation.state_closed']}`, '3'])
    expect(within(table).getByTestId('longest-take')).toHaveTextContent('Longest line in the plan’s simulated day: 3 people, at c1 during 08:00.')
  })

  it('reads the Current run per cashier from its own rows', () => {
    renderView('current')
    const table = screen.getByTestId('longest-line-table')
    expect(within(within(table).getByRole('row', { name: /^08:00/ })).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['2', '5', '5'])
    expect(within(table).getByTestId('longest-take')).toHaveTextContent('Longest line in today’s simulated run: 5 people, at c2 during 08:00.')
    expect(table).toHaveTextContent(en['charts.chip_seed_not_saved'])
  })

  it('is not shown for a shared line', () => {
    renderView('current', { separate: false, plan: null })
    expect(screen.queryByTestId('longest-line-table')).not.toBeInTheDocument()
  })
})

// ── A6: per-date separate-lines Current (C-PD, C-PD-C); SYNTHETIC values ─────────────────────────────────

const D1 = '2000-01-03'
const D2 = '2000-01-04'
const compactRow = (date: string, segment: string, queue: string, maxQueue: number, arrivals = 4) => ({
  time: `${date} ${segment} UTC`, date, segment_id: segment, queue_id: queue, queue_structure: 'separate', simulation_supported: true,
  arrivals, served: arrivals, waiting: 0, in_service: 0, max_queue: maxQueue, Wq_sim: 0.05, rho_sim: 0.4,
})
const compactRows = [
  compactRow(D1, 's1', 'c1', 2), compactRow(D1, 's1', 'c2', 5), compactRow(D1, 's2', 'c1', 1), compactRow(D1, 's2', 'c2', 0),
  compactRow(D2, 's1', 'c1', 9), compactRow(D2, 's1', 'c2', 1), compactRow(D2, 's2', 'c1', 3), compactRow(D2, 's2', 'c2', 0, 0),
]
const allDates: RunSummary = {
  basis: 'per_period', average_wait_hours: 0.1, longest_line: 9, arrivals: null, served: null, in_system_at_close: null,
  periods: [D1, D2].flatMap((date) => ['s1', 's2'].map((segment) => (
    { time: `${date} ${segment} UTC`, average_wait_hours: 0.05, longest_line: 1, arrivals: null, served: null }))),
}
const day = (date: string) => ({
  date, arrivals: 16, served: 16, waiting_at_close: 0, in_service_at_close: 0, customer_conservation: true, day_hours: 2,
  rows_digest: 'a'.repeat(64), trace_digest: 'b'.repeat(64), event_count: 48, truncated: false,
})
const zeroD2 = [{ date: D2, time: `${D2} s2 UTC`, segment_id: 's2', queue_id: 'c2' }]
const compactCurrent = {
  ...emptyTrace, results: compactRows, summary: allDates, execution: 'current_per_date_days_compact',
  days: [day(D1), day(D2)], zero_arrival_lane_periods: zeroD2, seed_used: 77,
}

function renderCurrent(result: unknown, { route = '/simulation/results?analysis=7', lang = 'en' as 'en' | 'tl', seed = null as number | null } = {}) {
  const analysis = {
    id: 7, name: 'Checkout',
    queue_setup: {
      queue_structure: 'separate_queues', event_period_basis: 'per_date', queue_ids: ['c1', 'c2'], breaks: [],
      segments: [{ id: 's1', start_time: '08:00', end_time: '09:00', active_queue_ids: null }, { id: 's2', start_time: '09:00', end_time: '10:00', active_queue_ids: null }],
    },
  } as unknown as AnalysisProjectOut
  const workflow = {
    analysis_id: 7, selection: null, scenario: null, des: null,
    des_current: job('workflow_des_current', result, { seed }),
    mc: null, validation: null, mc_current: null, validation_current: null, decision: null, decision_stale: false,
  } as unknown as WorkflowEvidence
  return renderWithProviders(<KeyResultsView context={buildContext(7, analysis, workflow)} run="current" />, { route, lang })
}

const longestRow = (time: string) => within(within(screen.getByTestId('longest-line-table')).getByRole('row', { name: new RegExp(`^${time}`) }))
  .getAllByRole('cell').map((cell) => cell.textContent)

describe('Key results for a per-date Current run stored compactly (A6)', () => {
  it('keeps the all-dates cards and shows the first date in the tables, chart and More results', async () => {
    const user = userEvent.setup()
    spies.downloadCsv.mockReset()
    spies.getCurrentDay.mockReset()
    renderCurrent(compactCurrent)
    const cards = screen.getByRole('group', { name: 'Key Results' })
    expect(within(cards).getByRole('region', { name: 'Average wait' })).toHaveTextContent('Current: 6 min')
    expect(within(cards).getByRole('region', { name: 'Longest Single Line' })).toHaveTextContent('Current: 9')
    expect(screen.getByTestId('current-dates-note')).toHaveTextContent(
      'Average wait and Longest Single Line cover all 2 dates. The tables and the chart by period show the chosen date.')
    expect(screen.getByLabelText('Date')).toHaveValue(D1)
    expect(longestRow(`${D1} s1 UTC`)).toEqual(['2', '5', '5'])
    expect(screen.getByTestId('longest-line-table')).not.toHaveTextContent(D2)
    const periods = screen.getByRole('region', { name: en['simulation.period_table'] })
    expect(within(periods).getAllByRole('rowheader').map((cell) => cell.textContent)).toEqual([`${D1} s1 UTC`, `${D1} s2 UTC`])
    expect(screen.getByRole('img', { name: en['simulation.chart_wait_by_period'] })).not.toHaveTextContent(D2)
    const more = screen.getByRole('region', { name: en['simulation.des_table_caption'] })
    expect(within(more).getAllByRole('rowheader').map((cell) => cell.textContent)).toEqual(
      [`${D1} s1 UTC`, `${D1} s1 UTC`, `${D1} s2 UTC`, `${D1} s2 UTC`])
    expect(screen.queryByTestId('current-zero-note')).not.toBeInTheDocument()
    expect(screen.getByTestId('key-details')).toHaveTextContent(
      `${en['simulation.run_current']} · ${en['simulation.run_basis_continuous_per_date']} · ${en['charts.chip_no_breaks']} · Random seed: 77`)
    await user.click(screen.getByRole('button', { name: en['simulation.download_csv'] }))
    expect(spies.downloadCsv).toHaveBeenCalledWith(`novaq_unified_des_${D1}.csv`, compactRows.slice(0, 4))
    expect(spies.getCurrentDay).not.toHaveBeenCalled()
  })

  it('follows ?date= and names the zero-arrival periods of that date, in English and Tagalog', () => {
    renderCurrent(compactCurrent, { route: `/simulation/results?analysis=7&date=${D2}` })
    expect(screen.getByLabelText('Date')).toHaveValue(D2)
    expect(longestRow(`${D2} s1 UTC`)).toEqual(['9', '1', '9'])
    expect(screen.getByTestId('current-zero-note')).toHaveTextContent(
      'On this date, 1 open queue period had no customer records; it is shown with zero arrivals.')
  })

  it('renders the draft notes verbatim in Tagalog', () => {
    renderCurrent(compactCurrent, { route: `/simulation/results?analysis=7&date=${D2}`, lang: 'tl' })
    expect(screen.getByTestId('current-dates-note')).toHaveTextContent(tl['simulation.current_all_dates_note'].replace('{{dates}}', '2'))
    expect(screen.getByTestId('current-zero-note')).toHaveTextContent(tl['simulation.current_zero_arrival_note_one'].replace('{{count}}', '1'))
  })

  it('falls back to the first date for a date the run does not have, and shows the requested seed when one was sent', () => {
    renderCurrent(compactCurrent, { route: '/simulation/results?analysis=7&date=1999-12-31', seed: 5 })
    expect(screen.getByLabelText('Date')).toHaveValue(D1)
    expect(screen.getByTestId('key-details')).toHaveTextContent('Random seed: 5')
  })
})

describe('Key results for a one-date per-date Current run (A6)', () => {
  const oneDate = {
    ...emptyTrace, results: compactRows.slice(0, 4).map((row) => ({ ...row, lambda: 2, mu: 3, c: 1, status: 'Normal', error: null })),
    summary: { ...allDates, periods: allDates.periods.slice(0, 2) }, execution: 'current_per_date_days',
    days: [day(D1)], zero_arrival_lane_periods: [{ date: D1, time: `${D1} s2 UTC`, segment_id: 's2', queue_id: 'c2' }],
  }

  it('renders the full result as before: no picker or all-dates note, every row, the usual file; N2 when listed', async () => {
    const user = userEvent.setup()
    spies.downloadCsv.mockReset()
    renderCurrent(oneDate)
    expect(screen.queryByLabelText('Date')).not.toBeInTheDocument()
    expect(screen.queryByTestId('current-dates-note')).not.toBeInTheDocument()
    expect(screen.getByTestId('current-zero-note')).toHaveTextContent('On this date, 1 open queue period had no customer records; it is shown with zero arrivals.')
    expect(within(screen.getByRole('region', { name: en['simulation.des_table_caption'] })).getAllByRole('rowheader')).toHaveLength(4)
    expect(screen.getByTestId('key-details')).toHaveTextContent(en['charts.chip_seed_not_saved'])
    await user.click(screen.getByRole('button', { name: en['simulation.download_csv'] }))
    expect(spies.downloadCsv).toHaveBeenCalledWith('novaq_unified_des.csv', oneDate.results)
  })

  it('keeps today\'s longest-line sentence for a one-date run (no date in it)', () => {
    renderCurrent(oneDate)
    expect(screen.getByTestId('longest-take')).toHaveTextContent(
      `Longest line in today’s simulated run: 5 people, at c2 during ${D1} s1 UTC.`)
  })
})

// ── A6 wording follow-up (B1 N2 plural, B2 per-date sentence; owner delegation 2026-11-03) ───────────────

const zeroOn = (date: string, count: number) => Array.from({ length: count }, (_, index) => (
  { date, time: `${date} s${index + 1} UTC`, segment_id: `s${index + 1}`, queue_id: `c${index + 1}` }))

describe('N2 zero-arrival note, plural forms (B1)', () => {
  it('uses the singular for one period and the plural for two in English', () => {
    const one = renderCurrent({ ...compactCurrent, zero_arrival_lane_periods: zeroOn(D1, 1) })
    expect(screen.getByTestId('current-zero-note')).toHaveTextContent(
      'On this date, 1 open queue period had no customer records; it is shown with zero arrivals.')
    one.unmount()
    renderCurrent({ ...compactCurrent, zero_arrival_lane_periods: zeroOn(D1, 2) })
    expect(screen.getByTestId('current-zero-note')).toHaveTextContent(
      'On this date, 2 open queue periods had no customer records; they are shown with zero arrivals.')
  })

  it.each([1, 2, 3])('reads the same Tagalog text for %s (Intl tl = fil: "one" also covers 2, 3, 5)', (count) => {
    renderCurrent({ ...compactCurrent, zero_arrival_lane_periods: zeroOn(D1, count) }, { lang: 'tl' })
    expect(screen.getByTestId('current-zero-note')).toHaveTextContent(
      `Sa petsang ito, ${count} bukas na queue period ang walang rekord ng customer; ipinapakita ang mga ito na walang pagdating.`)
  })
})

describe('Longest-line sentence of a compact per-date Current run (B2)', () => {
  it('names the chosen date instead of "today", in English and Tagalog', () => {
    const view = renderCurrent(compactCurrent)
    expect(screen.getByTestId('longest-take')).toHaveTextContent(`Longest line on ${D1}: 5 people, at c2 during ${D1} s1 UTC.`)
    expect(screen.getByTestId('longest-take')).not.toHaveTextContent('today')
    view.unmount()
    renderCurrent(compactCurrent, { route: `/simulation/results?analysis=7&date=${D2}`, lang: 'tl' })
    expect(screen.getByTestId('longest-take')).toHaveTextContent(
      tl['charts.longest_take_current_date_other'].replace('{{date}}', D2).replace('{{count}}', '9')
        .replace('{{where}}', `c1 ${tl['charts.conn_during']} ${D2} s1 UTC`))
  })

  it('uses the singular for a longest line of one person', () => {
    const ones = compactRows.map((row) => ({ ...row, max_queue: row.date === D1 ? (row.queue_id === 'c1' && row.segment_id === 's1' ? 1 : 0) : row.max_queue }))
    renderCurrent({ ...compactCurrent, results: ones })
    expect(screen.getByTestId('longest-take')).toHaveTextContent(`Longest line on ${D1}: 1 person, at c1 during ${D1} s1 UTC.`)
  })

  it('keeps the plan sentence for a Suggested run', () => {
    renderView('suggested')
    expect(screen.getByTestId('longest-take')).toHaveTextContent('Longest line in the plan’s simulated day: 3 people, at c1 during 08:00.')
  })
})
