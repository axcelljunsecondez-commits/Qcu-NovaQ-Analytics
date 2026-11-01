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
    expect(screen.getByTestId('longest-line-table')).not.toHaveTextContent(en['charts.longest_chip_runs'])
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
