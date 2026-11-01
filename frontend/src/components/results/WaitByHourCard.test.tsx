import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ScenarioOut } from '../../api/scenarios'
import type { ObservedWaitPeriod, SeparateComparison, SeparatePlanComparison } from '../../api/types'
import { renderWithProviders } from '../../test/test-utils'
import type { SelectedPlan } from './useSelectedPlan'
import { WaitByHourCard } from './WaitByHourCard'

// Wait by hour (spec 2026-10-29 §5.2). Fixtures mirror ObservedWaitSummary.periods and
// GET /analyses/:id/workflow/comparison/separate (backend/api/workflow.py:2412-2480); hours in, minutes out.

const observed: ObservedWaitPeriod[] = [
  { time: '08:00-09:00', modeled_wait: 0.05, observed_wait: 0.12, flagged: true },
  { time: '09:00-10:00', modeled_wait: 0.2, observed_wait: 0.1, flagged: false },
]
const rows = [
  { time: '08:00-09:00', queue_id: 'A', c: 1 }, { time: '08:00-09:00', queue_id: 'B', c: 1 },
  { time: '09:00-10:00', queue_id: 'A', c: 1 }, { time: '09:00-10:00', queue_id: 'B', c: 1 },
]

// The Setup staffs both cashiers all day (staffing does not vary by period).
const staffing = { setup: { queue_ids: ['A', 'B'], segments: [], staffing_varies_by_period: false }, records: null }

function separatePlan(lower: number | null): SelectedPlan {
  const comparison = {
    analysis_id: 7, queue_structure: 'separate_queues',
    current: { dataset_id: 11, wait_mean: 0.1, wait_basis: 'analytical', util_max: 0.8, waiting_cost: null, waiting_cost_basis: null, total_cost: null, total_cost_reason: null,
      periods: [
        { time: '08:00-09:00', active_lanes: ['A', 'B'], lambda_total: 10, wait_mean: 0.05, util_max: 0.6 },
        { time: '09:00-10:00', active_lanes: ['A', 'B'], lambda_total: 12, wait_mean: 0.2, util_max: 0.8 },
      ] },
    plans: [],
  } as unknown as SeparateComparison
  const plan = {
    scenario_id: 21, name: 'Plan', dataset_id: 11, target: 0.85, evaluation_method: 'DES_REPLICATIONS', replications: 5, base_seed: 42, overall: null,
    wait_basis_kind: 'simulation', stale: false, valid: true, valid_reason: null, totals: null,
    periods: [
      { time: '08:00-09:00', current_active_lanes: ['A', 'B'], optimal_active_lanes: 2, adjustment: 0, peak_util: 0.5, wait_mean: 0.02, wait_ci: [lower, 0.1],
        waiting_cost_mean: null, total_cost_mean: null, total_cost_ci: null, status: null },
      { time: '09:00-10:00', current_active_lanes: ['A', 'B'], optimal_active_lanes: 3, adjustment: 1, peak_util: 0.6, wait_mean: 0.05, wait_ci: [0.04, 0.06],
        waiting_cost_mean: null, total_cost_mean: null, total_cost_ci: null, status: null },
    ],
  } as unknown as SeparatePlanComparison
  return { kind: 'separate', plan, comparison, usable: true, target: 0.85 }
}

function sharedPlan(): SelectedPlan {
  const scenario = { id: 3, name: 'Plan A', results: { results: [
    { time: '08:00-09:00', c_current: 3, c_optimal: 4, rho_current: 0.8, rho_optimal: 0.6, Wq_current: 0.05, Wq_optimal: 0.01, current_stable: true, optimized_stable: true },
    { time: '09:00-10:00', c_current: 3, c_optimal: 5, rho_current: 0.9, rho_optimal: 0.65, Wq_current: 0.2, Wq_optimal: 0.02, current_stable: true, optimized_stable: true },
  ] } } as unknown as ScenarioOut
  return { kind: 'shared', scenario, scenarios: [scenario], usable: true, target: 0.7 }
}

function chart() {
  return screen.getByTestId('wait-chart')
}

function tableCells() {
  const table = within(screen.getByRole('region', { name: 'Show as a table' })).getByRole('table')
  return within(table).getAllByRole('row').map((row) => within(row).queryAllByRole('cell').map((cell) => cell.textContent))
}

describe('wait by hour', () => {
  it('Today view draws Recorded and Estimated only, with the takeaway on the highest estimate', () => {
    renderWithProviders(<WaitByHourCard observed={observed} rows={rows} selectedModel="Parallel M/G/1" separate staffing={staffing} plan={{ kind: 'none' }} />)
    expect(screen.queryByRole('group', { name: 'Chart view' })).not.toBeInTheDocument()
    expect(chart().querySelectorAll('.cv-m-rec')).toHaveLength(2)
    expect(chart().querySelectorAll('.cv-m-est')).toHaveLength(2)
    expect(chart().querySelectorAll('.cv-m-plan, .cv-l-ci')).toHaveLength(0)
    expect(screen.getByText('09:00-10:00 has the highest calculated estimate today: 12 min per customer. Recorded: 6 min.')).toBeInTheDocument()
    expect(screen.getAllByTestId('row-chart-row')[1]).toHaveClass('hl')
    expect(screen.getByText('Calculated estimate: queueing formula for each cashier line (Parallel M/G/1)')).toBeInTheDocument()
    expect(screen.getByText('Each row is one hour; the axis starts at 0.')).toBeInTheDocument()
    expect(tableCells().slice(1)).toEqual([['2', '7.2 min', '3 min'], ['2', '6 min', '12 min']])
    expect(screen.getByRole('region', { name: 'Show as a table' })).toHaveTextContent('Much longer than modeled')
  })

  it('Today view (separate) counts the cashiers the Setup staffs per period, not the rows with customers (K-UC-5)', () => {
    // Cashier C is staffed in the morning but recorded no customers, so /current has no row for it.
    const varying = {
      setup: { queue_ids: ['A', 'B', 'C'], staffing_varies_by_period: true, segments: [
        { id: 'morning', start_time: '08:00', end_time: '09:00', active_queue_ids: ['A', 'B', 'C'] },
        { id: 'noon', start_time: '09:00', end_time: '10:00', active_queue_ids: ['A'] },
      ] },
      records: [
        { time: '08:00-09:00', segment_id: 'morning', queue_id: 'A' }, { time: '08:00-09:00', segment_id: 'morning', queue_id: 'B' },
        { time: '09:00-10:00', segment_id: 'noon', queue_id: 'A' },
      ],
    }
    const { unmount } = renderWithProviders(<WaitByHourCard observed={observed} rows={rows} selectedModel={null} separate staffing={varying} plan={{ kind: 'none' }} />)
    expect(tableCells().slice(1).map((cells) => cells[0])).toEqual(['3', '1'])
    unmount()
    // Staffing varies but the period names no known segment: "—", never the row count.
    renderWithProviders(<WaitByHourCard observed={observed} rows={rows} selectedModel={null} separate staffing={{ ...varying, records: null }} plan={{ kind: 'none' }} />)
    expect(tableCells().slice(1).map((cells) => cells[0])).toEqual(['—', '—'])
    expect(screen.getAllByTestId('row-chart-row')[0]).toHaveTextContent('Counters: —')
  })

  it('reads out the same values as the table when moving by keyboard', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WaitByHourCard observed={observed} rows={rows} selectedModel={null} separate staffing={staffing} plan={{ kind: 'none' }} />)
    await user.tab()
    expect(screen.getByRole('group', { name: 'Wait by period. Use the arrow keys to read each period.' })).toHaveFocus()
    expect(screen.getByTestId('row-chart-readout')).toHaveTextContent('Recorded (From your data): 6 min')
    expect(screen.getByTestId('row-chart-readout')).toHaveTextContent('Estimated (Calculated estimate): 12 min')
    await user.keyboard('{Home}')
    expect(screen.getByText('08:00-09:00: Recorded 7.2 min, Estimated 3 min, Much longer than modeled')).toBeInTheDocument()
  })

  it('Plan view (separate) draws Estimated vs the simulated plan, never Recorded, and cuts a negative range at 0', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WaitByHourCard observed={observed} rows={rows} selectedModel="Parallel M/G/1" separate staffing={staffing} plan={separatePlan(-0.0239)} />)
    const views = within(screen.getByRole('group', { name: 'Chart view' })).getAllByRole('button')
    expect(views.map((button) => button.textContent)).toEqual(['Recorded vs Estimated Wait, by period', 'Estimate vs suggested plan'])
    await user.click(views[1])
    expect(views[1]).toHaveAttribute('aria-pressed', 'true')
    expect(chart().querySelectorAll('.cv-m-rec')).toHaveLength(0)
    expect(chart().querySelectorAll('.cv-m-plan')).toHaveLength(2)
    expect(chart().querySelectorAll('.cv-l-ci')).toHaveLength(2)
    expect(screen.getAllByTestId('row-chart-cut')).toHaveLength(1)
    expect(screen.getByText('Range cut at 0')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'About the range cut at 0' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'About the 95% range' })).toBeInTheDocument()
    expect(screen.getByText('09:00-10:00 has the highest calculated estimate today: 12 min per customer. Suggested plan, simulated: 3 min.')).toBeInTheDocument()
    expect(tableCells().slice(1)).toEqual([
      ['2 → 2', '3 min', '1.2 min', '0 – 6 min (Range cut at 0)'],
      ['2 → 3', '12 min', '3 min', '2.4 – 3.6 min'],
    ])
    expect(screen.getByText('Suggested plan, simulated: mean of 5 runs, base seed 42')).toBeInTheDocument()
    expect(screen.getByText("Plan's target: 85%")).toBeInTheDocument()
    // The stored negative lower bound (−1.434 min) is never printed.
    expect(document.body.textContent).not.toMatch(/-1\.4|−1\.4|-0\.02/)
  })

  it('marks a range whose lower end is exactly 0, and adds no note when the lower end is above 0', async () => {
    const user = userEvent.setup()
    const { unmount } = renderWithProviders(<WaitByHourCard observed={null} rows={rows} selectedModel={null} separate staffing={staffing} plan={separatePlan(0)} />)
    expect(screen.getAllByTestId('row-chart-cut')).toHaveLength(1)
    expect(screen.getByText('Range cut at 0')).toBeInTheDocument()
    unmount()
    renderWithProviders(<WaitByHourCard observed={null} rows={rows} selectedModel={null} separate staffing={staffing} plan={separatePlan(0.01)} />)
    expect(screen.queryByTestId('row-chart-cut')).not.toBeInTheDocument()
    expect(screen.queryByText('Range cut at 0')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'About the range cut at 0' })).not.toBeInTheDocument()
    // No recorded waits (aggregate upload): the Plan view is the only view.
    expect(screen.queryByRole('group', { name: 'Chart view' })).not.toBeInTheDocument()
    await user.click(screen.getByText('details'))
    expect(tableCells()[1][3]).toBe('0.6 – 6 min')
  })

  it('shows a labelled gap for a period with no values and names no "highest" hour', () => {
    renderWithProviders(<WaitByHourCard observed={[{ time: '07:00-08:00', modeled_wait: null, observed_wait: null, flagged: false }]} rows={[]} selectedModel={null} separate staffing={staffing} plan={{ kind: 'none' }} />)
    expect(within(chart()).getByText('Unavailable')).toBeInTheDocument()
    expect(screen.queryByText(/has the highest calculated estimate/)).not.toBeInTheDocument()
  })

  it('draws no range and prints Unavailable when the plan has none for a period', () => {
    renderWithProviders(<WaitByHourCard observed={null} rows={rows} selectedModel={null} separate staffing={staffing} plan={separatePlan(null)} />)
    expect(chart().querySelectorAll('.cv-l-ci')).toHaveLength(1)
    expect(tableCells()[1][3]).toBe('Unavailable')
    expect(screen.queryByText('Range cut at 0')).not.toBeInTheDocument()
  })

  it('Plan view (shared) is calculated on both sides: no range, no cut marker, no "simulated" wording', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WaitByHourCard observed={observed} rows={[]} selectedModel="M/M/c" separate={false} plan={sharedPlan()} />)
    await user.click(screen.getByRole('button', { name: 'Estimate vs suggested plan' }))
    const card = screen.getByTestId('wait-by-hour')
    expect(chart().querySelectorAll('.cv-l-ci')).toHaveLength(0)
    expect(screen.queryByTestId('row-chart-cut')).not.toBeInTheDocument()
    expect(card.textContent).not.toMatch(/simulated/i)
    expect(screen.queryByText('95% range')).not.toBeInTheDocument()
    expect(screen.getByText('09:00-10:00 has the highest calculated estimate today: 12 min per customer. Suggested plan, calculated: 1.2 min.')).toBeInTheDocument()
    expect(screen.getByText('Calculated estimate: queueing formula for the shared line (M/M/c)')).toBeInTheDocument()
    expect(tableCells().slice(1)).toEqual([['3 → 4', '3 min', '0.6 min'], ['3 → 5', '12 min', '1.2 min']])
  })

  it('keeps the view names and kind words in Tagalog while the heading stays English', () => {
    renderWithProviders(<WaitByHourCard observed={observed} rows={rows} selectedModel={null} separate staffing={staffing} plan={separatePlan(0.01)} />, { lang: 'tl' })
    expect(screen.getByRole('heading', { name: 'What the plan changes' })).toHaveAttribute('lang', 'en')
    expect(screen.getByRole('button', { name: 'Tantiya vs mungkahing plano' })).toBeInTheDocument()
    expect(within(screen.getByTestId('wait-by-hour')).getAllByText('Naitala').length).toBeGreaterThan(0)
  })
})

describe('view switch styling', () => {
  // The base button style is the primary fill, so the unchosen view must set its own neutral fill;
  // before this rule both views looked chosen (browser check 2026-10-29, computed backgrounds equal).
  it('fills only the chosen view with the primary colour', () => {
    const css = readFileSync(resolve(process.cwd(), 'src/styles/charts.css'), 'utf8')
    expect(css).toMatch(/\.cv-view-switch button\s*\{[^}]*background: var\(--color-bg-surface\);[^}]*color: var\(--color-text-primary\);/)
    expect(css).toMatch(/\.cv-view-switch button\[aria-pressed='true'\]\s*\{[^}]*background: var\(--color-action-primary-bg\);/)
  })
})
