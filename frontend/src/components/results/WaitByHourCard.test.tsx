import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ScenarioOut } from '../../api/scenarios'
import type { ObservedWaitPeriod, PeriodArrivals, SeparateComparison, SeparatePlanComparison } from '../../api/types'
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
    // Phase C (owner 2026-11-25): the Today view is a line chart: recorded nodes and estimated nodes.
    expect(chart().querySelectorAll('.cv-node-rec')).toHaveLength(2)
    expect(chart().querySelectorAll('.cv-node-est')).toHaveLength(2)
    expect(chart().querySelectorAll('.cv-m-plan, .cv-l-ci')).toHaveLength(0)
    expect(screen.getByText('09:00-10:00 has the highest calculated estimate today: 12 min per customer. Recorded: 6 min.')).toBeInTheDocument()
    expect([...chart().querySelectorAll('.cv-node.is-highlight')].map((node) => node.getAttribute('class'))).toEqual(['cv-node cv-node-rec is-highlight', 'cv-node cv-node-est is-highlight'])
    expect(screen.getByText('Calculated estimate: queueing formula for each cashier line (Parallel M/G/1)')).toBeInTheDocument()
    expect(screen.getByText('Each point is one hour; the axis starts at 0.')).toBeInTheDocument()
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
    act(() => chart().focus())
    fireEvent.keyDown(chart(), { key: 'Home' })
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('Counters: —')
  })

  it('reads out the same values as the table when moving by keyboard', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WaitByHourCard observed={observed} rows={rows} selectedModel={null} separate staffing={staffing} plan={{ kind: 'none' }} />)
    await user.tab()
    await user.tab()
    await user.tab()
    expect(screen.getByRole('group', { name: 'Wait by period. Use the arrow keys to read each period.' })).toHaveFocus()
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('Recorded (From your data): 6 min')
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('Estimated (Calculated estimate): 12 min')
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('Gap: -6 min')
    await user.keyboard('{Home}')
    expect(screen.getByText('08:00-09:00: Recorded 7.2 min, Estimated 3 min, Much longer than modeled')).toBeInTheDocument()
    // Readout values equal the table cells (7.2 and 3 min); the Gap is from unrounded minutes (7.2 - 3).
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('Gap: 4.2 min')
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
    expect(screen.queryByTestId('wait-chart')).not.toBeInTheDocument()
    expect(screen.getByTestId('wait-unavailable')).toHaveTextContent('Unavailable')
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
    expect(screen.getByRole('heading', { name: 'Waiting time by period' })).toHaveAttribute('lang', 'en')
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

// Phase C (owner decisions OD-C1..C6, 2026-11-25): measure switch, gaps, reveal triggers.
const arrivals: PeriodArrivals[] = [
  { time: '08:00-09:00', arrivals_per_hour: 30 }, { time: '09:00-10:00', arrivals_per_hour: null }, { time: '10:00-11:00', arrivals_per_hour: 12.5 },
]

describe('wait and arrivals measures', () => {
  it('switches measures with aria-pressed, keeps focus on the pressed button and reads out the arrivals values', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WaitByHourCard observed={observed} rows={rows} selectedModel={null} separate staffing={staffing} plan={{ kind: 'none' }} arrivals={arrivals} />)
    const group = screen.getByRole('group', { name: 'Chart measure' })
    const [wait, arrive] = within(group).getAllByRole('button')
    expect([wait.textContent, arrive.textContent]).toEqual(['Wait', 'Arrivals'])
    expect(wait).toHaveAttribute('aria-pressed', 'true')
    await user.click(arrive)
    expect(arrive).toHaveAttribute('aria-pressed', 'true')
    expect(wait).toHaveAttribute('aria-pressed', 'false')
    expect(arrive).toHaveFocus()
    expect(screen.getByRole('heading', { name: 'Arrivals by period' })).toHaveAttribute('lang', 'en')
    expect(screen.getByText('Customer arrivals per hour (all cashiers combined)')).toBeInTheDocument()
    const chartEl = screen.getByTestId('arrivals-chart')
    expect(chartEl).toHaveAccessibleName('Arrivals by period. Use the arrow keys to read each period.')
    // One blue series: a null period breaks the line and has no node.
    expect(chartEl.querySelectorAll('.cv-node-arr')).toHaveLength(2)
    expect(chartEl.querySelectorAll('[data-testid="line-trace-arr"]')).toHaveLength(2)
    act(() => chartEl.focus())
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('08:00-09:0030 customers per hour')
    fireEvent.keyDown(chartEl, { key: 'ArrowRight' })
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('09:00-10:00Unavailable')
    expect(screen.getByText('09:00-10:00 · Unavailable')).toBeInTheDocument()
    fireEvent.keyDown(chartEl, { key: 'End' })
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('10:00-11:0012.5 customers per hour')
    // The table alternative holds the same values as arrivals_by_period.
    const table = within(screen.getByRole('region', { name: 'Show as a table' })).getByRole('table', { name: 'Customers per hour by period' })
    expect(within(table).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['30', 'Unavailable', '12.5'])
    await user.click(wait)
    expect(wait).toHaveFocus()
    expect(screen.getByRole('heading', { name: 'Waiting time by period' })).toBeInTheDocument()
  })

  it('shows the card for arrivals alone and explains a missing wait by the file contents', async () => {
    const user = userEvent.setup()
    const { unmount } = renderWithProviders(<WaitByHourCard observed={null} rows={[]} selectedModel={null} separate={false} plan={{ kind: 'none' }} arrivals={arrivals} hasRecords={false} />)
    expect(within(screen.getByRole('group', { name: 'Chart measure' })).getByRole('button', { name: 'Arrivals' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'Wait' }))
    expect(screen.getByTestId('wait-unavailable')).toHaveTextContent('Recorded waiting time is unavailable because this file does not contain customer arrival and service-start times.')
    unmount()
    renderWithProviders(<WaitByHourCard observed={null} rows={[]} selectedModel={null} separate={false} plan={{ kind: 'none' }} arrivals={arrivals} hasRecords />)
    await user.click(screen.getByRole('button', { name: 'Wait' }))
    expect(screen.getByTestId('wait-unavailable')).toHaveTextContent(/^Unavailable$/)
  })

  it('renders only the footer when no measure has data, and says Unavailable for all-missing arrivals', async () => {
    const user = userEvent.setup()
    const { unmount } = renderWithProviders(<WaitByHourCard observed={null} rows={[]} selectedModel={null} separate={false} plan={{ kind: 'none' }}
      arrivals={[{ time: '08:00-09:00', arrivals_per_hour: null }]} footer={<p>prompt</p>} />)
    expect(screen.queryByTestId('wait-by-hour')).not.toBeInTheDocument()
    expect(screen.getAllByText('prompt')).toHaveLength(1)
    unmount()
    renderWithProviders(<WaitByHourCard observed={observed} rows={rows} selectedModel={null} separate staffing={staffing} plan={{ kind: 'none' }}
      arrivals={[{ time: '08:00-09:00', arrivals_per_hour: null }]} footer={<p>prompt</p>} />)
    await user.click(screen.getByRole('button', { name: 'Arrivals' }))
    expect(screen.queryByTestId('arrivals-chart')).not.toBeInTheDocument()
    expect(screen.getByTestId('arrivals-unavailable')).toHaveTextContent('Unavailable')
    expect(screen.getAllByText('prompt')).toHaveLength(1)
  })

  it('breaks the line at a single missing period, keeps an isolated value as a node, and shows the Gap only with both values', () => {
    const gappy: ObservedWaitPeriod[] = [
      { time: '08:00-09:00', modeled_wait: 0.05, observed_wait: 0.1, flagged: false },
      { time: '09:00-10:00', modeled_wait: 0.1, observed_wait: null, flagged: false },
      { time: '10:00-11:00', modeled_wait: 0.08, observed_wait: 0.05, flagged: false },
      { time: '11:00-12:00', modeled_wait: null, observed_wait: null, flagged: false },
      { time: '12:00-13:00', modeled_wait: null, observed_wait: 0.2, flagged: false },
      { time: '13:00-14:00', modeled_wait: null, observed_wait: null, flagged: false },
    ]
    renderWithProviders(<WaitByHourCard observed={gappy} rows={[]} selectedModel={null} separate={false} plan={{ kind: 'none' }} />)
    const el = chart()
    // Recorded: 08, gap, 10, gap, 12 (isolated), gap → three runs, three nodes; nothing is drawn at 0 for the gaps.
    expect(el.querySelectorAll('[data-testid="line-trace-rec"]')).toHaveLength(3)
    expect(el.querySelectorAll('.cv-node-rec')).toHaveLength(3)
    expect(el.querySelectorAll('[data-testid="line-trace-est"]')).toHaveLength(1)
    expect(el.querySelectorAll('.cv-node-est')).toHaveLength(3)
    act(() => el.focus())
    fireEvent.keyDown(el, { key: 'Home' })
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('Gap: 3 min')
    fireEvent.keyDown(el, { key: 'ArrowRight' })
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('Recorded (From your data): Unavailable')
    expect(screen.getByTestId('line-chart-readout')).not.toHaveTextContent('Gap')
    fireEvent.keyDown(el, { key: 'ArrowRight' })
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('Gap: -1.8 min')
    fireEvent.keyDown(el, { key: 'End' })
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('Recorded (From your data): UnavailableEstimated (Calculated estimate): Unavailable')
  })

  it('keeps the measure names in Tagalog while the arrivals heading stays English', async () => {
    const user = userEvent.setup()
    renderWithProviders(<WaitByHourCard observed={observed} rows={rows} selectedModel={null} separate staffing={staffing} plan={{ kind: 'none' }} arrivals={arrivals} />, { lang: 'tl' })
    const group = screen.getByRole('group', { name: 'Sukatan ng chart' })
    expect(within(group).getAllByRole('button').map((button) => button.textContent)).toEqual(['Wait', 'Mga pagdating'])
    await user.click(within(group).getByRole('button', { name: 'Mga pagdating' }))
    expect(screen.getByRole('heading', { name: 'Arrivals by period' })).toHaveAttribute('lang', 'en')
    expect(screen.getByText('Isang oras ang bawat punto; nagsisimula sa 0 ang axis.')).toBeInTheDocument()
  })
})

describe('chart reveal (1.8 s, data marks only)', () => {
  let animate: ReturnType<typeof vi.fn>
  beforeEach(() => {
    animate = vi.fn(() => ({ cancel: vi.fn(), playState: 'finished' }))
    Object.defineProperty(Element.prototype, 'animate', { configurable: true, writable: true, value: animate })
  })
  afterEach(() => {
    delete (Element.prototype as { animate?: unknown }).animate
    vi.unstubAllGlobals()
  })

  it('replays on first data, on every measure click and on a file change, and never on hover, keys, focus, plan switch or refetch', async () => {
    const user = userEvent.setup()
    const card = (key: number, periods: ObservedWaitPeriod[] = observed) => (
      <WaitByHourCard observed={periods} rows={[]} selectedModel={null} separate={false} plan={sharedPlan()} arrivals={arrivals} fileKey={key} />
    )
    const { rerender } = renderWithProviders(card(11))
    expect(animate).toHaveBeenCalledTimes(1)
    expect(animate.mock.calls[0]).toEqual([
      [{ clipPath: 'inset(0 100% 0 0)' }, { clipPath: 'inset(0)' }],
      { duration: 1800, delay: 120, easing: 'ease-in-out', fill: 'backwards' },
    ])
    expect((animate.mock.contexts[0] as Element).getAttribute('class')).toBe('cv-curve-layer')
    // Hover, focus and the arrow keys never replay.
    const el = chart()
    fireEvent.mouseEnter(el.querySelectorAll('[data-testid="line-chart-hit"]')[1])
    act(() => el.focus())
    fireEvent.keyDown(el, { key: 'ArrowLeft' })
    expect(animate).toHaveBeenCalledTimes(1)
    // The plan sub-switch (there and back) does not replay.
    await user.click(screen.getByRole('button', { name: 'Estimate vs suggested plan' }))
    await user.click(screen.getByRole('button', { name: 'Recorded vs Estimated Wait, by period' }))
    expect(animate).toHaveBeenCalledTimes(1)
    // Every measure click replays, including the measure already shown.
    await user.click(screen.getByRole('button', { name: 'Wait' }))
    expect(animate).toHaveBeenCalledTimes(2)
    await user.click(screen.getByRole('button', { name: 'Arrivals' }))
    expect(animate).toHaveBeenCalledTimes(3)
    await user.click(screen.getByRole('button', { name: 'Wait' }))
    expect(animate).toHaveBeenCalledTimes(4)
    // A refetch of the same file (new arrays, same file) does not replay; a different file does.
    rerender(card(11, observed.map((period) => ({ ...period }))))
    expect(animate).toHaveBeenCalledTimes(4)
    rerender(card(12))
    expect(animate).toHaveBeenCalledTimes(5)
  })

  it('does not animate under reduced motion and leaves the marks fully visible', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('reduce'), addEventListener: vi.fn(), removeEventListener: vi.fn() }))
    renderWithProviders(<WaitByHourCard observed={observed} rows={rows} selectedModel={null} separate staffing={staffing} plan={{ kind: 'none' }} arrivals={arrivals} fileKey={11} />)
    await user.click(screen.getByRole('button', { name: 'Arrivals' }))
    expect(animate).not.toHaveBeenCalled()
    const layer = screen.getByTestId('line-chart-curves')
    expect(layer.getAttribute('style')).toBeNull()
    expect(layer.querySelectorAll('.cv-node-arr')).toHaveLength(2)
  })
})
