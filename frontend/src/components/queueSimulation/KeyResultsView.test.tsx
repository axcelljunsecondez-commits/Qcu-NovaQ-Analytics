import { describe, expect, it } from 'vitest'
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
  basis?: 'representative_day' | 'per_date'
  breaks?: boolean
  now?: RunSummary | null
  plan?: RunSummary | null
}

function renderView(run: RunChoice, { separate = true, basis = 'representative_day', breaks = true, now = perPeriod, plan = continuousDay }: Options = {}, lang: 'en' | 'tl' = 'en') {
  const analysis = {
    id: 7, name: 'Checkout',
    queue_setup: {
      queue_structure: separate ? 'separate_queues' : 'shared_queue', event_period_basis: basis, queue_ids: ['c1', 'c2'],
      segments: [{ id: 's1', start_time: '08:00', end_time: '09:00', active_queue_ids: null }],
      breaks: breaks ? [{ queue_id: 'c1', scheduled_start_time: '08:30', duration_minutes: 15 }] : [],
    },
  } as unknown as AnalysisProjectOut
  const scenario = separate
    ? { id: 9, name: 'Plan', dataset_id: 2, provenance: 'verified_snapshot', settings: { calculation: { schema_version: 2, options: { target_utilization: 0.85 } } } }
    : { id: 9, name: 'Plan', dataset_id: 2, provenance: 'verified_snapshot' }
  const planRun = plan === null ? null : separate ? planResult(plan) : { ...emptyTrace, results: [], summary: plan }
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

  it.each([
    ['a continuous plan day with breaks', {}, en['charts.key_basis']],
    ['a continuous plan day without breaks', { breaks: false }, en['charts.key_basis_no_breaks']],
    ['one continuous run per date', { basis: 'per_date' as const }, en['charts.key_basis_per_date']],
  ])('explains the different basis for %s', async (_case, options, text) => {
    const user = userEvent.setup()
    renderView('suggested', options)
    const buttons = screen.getAllByRole('button', { name: 'Why these are not the same basis' })
    expect(buttons).toHaveLength(2)
    await user.hover(buttons[0])
    expect(screen.getByRole('tooltip')).toHaveTextContent(text)
    expect(screen.getByTestId('key-take')).toHaveTextContent('Simulated average wait: Current 6 min, Suggested plan 3 min, from two runs set up differently.')
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
    expect(screen.getByRole('tooltip')).toHaveTextContent(en['charts.key_unavailable_explain'])
    expect(container).not.toHaveTextContent(en['simulation.per_period_totals_note'])
    expect(screen.queryByRole('region', { name: en['simulation.not_served_at_close'] })).not.toBeInTheDocument()
  })

  it('shows no explanation when the summary is missing (run again instead)', () => {
    renderView('current', { now: null, plan: null })
    expect(screen.queryByRole('button', { name: 'Why this is unavailable' })).not.toBeInTheDocument()
  })

  it('draws no Plotly chart for the period-by-period run', () => {
    const { container } = renderView('current', { separate: false, plan: null })
    expect(screen.getByRole('region', { name: en['simulation.des_table_caption'] })).toBeInTheDocument()
    expect(container.querySelector('.plotly')).toBeNull()
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
