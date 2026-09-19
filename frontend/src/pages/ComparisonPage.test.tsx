import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { ComparisonPage } from './ComparisonPage'
import type { OptimizationOut } from '../api/types'
import { Route, Routes } from 'react-router-dom'

const listScenariosMock = vi.fn()
const getWorkflowMock = vi.fn()
const selectWorkflowScenarioMock = vi.fn()
const getAnalysisMock = vi.fn()
const getSeparateComparisonMock = vi.fn()
const optimizeBatchSpy = vi.fn()
const optimizeSeparateSpy = vi.fn()

vi.mock('../api/scenarios', () => ({
  listScenarios: (...args: unknown[]) => listScenariosMock(...args),
  createScenario: vi.fn(),
}))

vi.mock('../api/workflow', () => ({
  getWorkflow: (...args: unknown[]) => getWorkflowMock(...args),
  selectWorkflowScenario: (...args: unknown[]) => selectWorkflowScenarioMock(...args),
  getSeparateComparison: (...args: unknown[]) => getSeparateComparisonMock(...args),
}))

vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
}))

vi.mock('../api/optimization', () => ({
  optimizeBatch: (...args: unknown[]) => optimizeBatchSpy(...args),
  optimizeSeparate: (...args: unknown[]) => optimizeSeparateSpy(...args),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const rows: OptimizationOut[] = [
  {
    time: '08:00-09:00',
    lambda_: 30,
    mu: 12,
    c_current: 3,
    c_optimal: 4,
    rho_current: 0.9,
    rho_optimal: 0.7,
    Wq_current: 0.1,
    Wq_optimal: 0.05,
    Lq_current: 3.5,
    Lq_optimal: 0.5,
    cost_current: 800,
    cost_optimal: 500,
    delta_cost: 300,
    delta_Wq: 0.05,
    delta_Lq: 3,
    delta_c: 1,
    delta_rho: -0.2,
    waiting_cost_current: 300,
    waiting_cost_optimal: 150,
    abandonment_cost_current: 100,
    abandonment_cost_optimal: 50,
    cost_per_server: 87,
    current_stable: true,
    optimized_stable: true,
    recommendation: '',
    warning: '',
  },
]

const scenarios = [
  {
    id: 1,
    dataset_id: 1,
    name: 'Plan A',
    settings: {},
    results: { results: rows },
    created_at: '2026-08-01T10:00:00Z',
  },
  {
    id: 2,
    dataset_id: 1,
    name: 'Plan B',
    settings: {},
    results: { results: rows },
    created_at: '2026-08-02T10:00:00Z',
  },
]

beforeEach(() => {
  listScenariosMock.mockReset()
  listScenariosMock.mockResolvedValue({ scenarios })
  getWorkflowMock.mockReset().mockResolvedValue({
    analysis_id: 7,
    selection: null,
    scenario: null,
    des: null,
    mc: null,
    validation: null,
    decision: null,
    decision_stale: false,
  })
  selectWorkflowScenarioMock.mockReset().mockResolvedValue({ selection: { id: 10 } })
  getAnalysisMock.mockReset().mockResolvedValue({
    analysis: { id: 7, queue_setup: { queue_structure: 'shared_queue', queue_ids: [] } },
  })
  getSeparateComparisonMock.mockReset()
  optimizeBatchSpy.mockReset()
  optimizeSeparateSpy.mockReset()
})

describe('ComparisonPage', () => {
  it('lists saved scenarios in the picker and loads the first one', async () => {
    renderWithProviders(<ComparisonPage />, { route: '/compare' })
    expect((await screen.findAllByRole('checkbox', { name: 'Plan A' })).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('checkbox', { name: 'Plan B' }).length).toBeGreaterThan(0)
    expect(await screen.findByTestId('chart-utilization-compare')).toBeInTheDocument()
  })

  it('persists a verified, complete scenario as the simulation selection', async () => {
    const user = userEvent.setup()
    listScenariosMock.mockResolvedValue({
      scenarios: [{
        ...scenarios[0],
        provenance: 'verified_snapshot',
        settings: { calculation: { engine_version: 'test' } },
      }],
    })
    renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/compare" element={<ComparisonPage />} />
      </Routes>,
      { route: '/analyses/7/compare' },
    )
    await user.click(await screen.findByRole('button', { name: 'Select for Simulation' }))
    await waitFor(() => expect(selectWorkflowScenarioMock).toHaveBeenCalledWith(7, 1))
  })

  it('renders only authoritative utilization, server, wait-time and cost charts', async () => {
    const { container } = renderWithProviders(<ComparisonPage />, { route: '/compare' })
    await waitFor(() =>
      expect(container.querySelector('[data-testid="chart-utilization-compare"]')).toBeInTheDocument(),
    )
    expect(container.querySelector('[data-testid="chart-radar"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-utilization-compare"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-server-compare"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-wait-time-lines"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-cost-waterfall"]')).toBeInTheDocument()
  })

  it('starts scenario comparison with no saved scenarios checked', async () => {
    const { container } = renderWithProviders(<ComparisonPage />, { route: '/compare' })
    const planA = await screen.findByRole('checkbox', { name: 'Plan A' })
    const planB = screen.getByRole('checkbox', { name: 'Plan B' })
    expect(planA).not.toBeChecked()
    expect(planB).not.toBeChecked()
    expect(await screen.findByText('Choose at least two saved scenarios.')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-scenario-compare"]')).not.toBeInTheDocument()
  })

  it('compares two checked saved scenarios with the scenario bars chart', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(<ComparisonPage />, { route: '/compare' })
    await screen.findByText('Choose at least two saved scenarios.')
    await user.click(screen.getByRole('checkbox', { name: 'Plan A' }))
    expect(screen.getByText('Choose at least two saved scenarios.')).toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: 'Plan B' }))
    await waitFor(() =>
      expect(container.querySelector('[data-testid="chart-scenario-compare"]')).toBeInTheDocument(),
    )
    expect(screen.queryByText('Choose at least two saved scenarios.')).not.toBeInTheDocument()
  })

  it('removes the comparison when one of two selected scenarios is unchecked', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(<ComparisonPage />, { route: '/compare' })
    const planA = await screen.findByRole('checkbox', { name: 'Plan A' })
    const planB = screen.getByRole('checkbox', { name: 'Plan B' })
    await user.click(planA)
    await user.click(planB)
    await waitFor(() =>
      expect(container.querySelector('[data-testid="chart-scenario-compare"]')).toBeInTheDocument(),
    )
    await user.click(planB)
    expect(container.querySelector('[data-testid="chart-scenario-compare"]')).not.toBeInTheDocument()
    expect(screen.getByText('Choose at least two saved scenarios.')).toBeInTheDocument()
  })

  it('normalizes string scenario IDs for checkbox selection', async () => {
    listScenariosMock.mockResolvedValue({
      scenarios: scenarios.map((scenario) => ({ ...scenario, id: String(scenario.id) })),
    })
    const user = userEvent.setup()
    const { container } = renderWithProviders(<ComparisonPage />, { route: '/compare' })
    await user.click(await screen.findByRole('checkbox', { name: 'Plan A' }))
    await user.click(screen.getByRole('checkbox', { name: 'Plan B' }))
    await waitFor(() =>
      expect(container.querySelector('[data-testid="chart-scenario-compare"]')).toBeInTheDocument(),
    )
  })

  it('uses IDs rather than duplicate names as checkbox identity', async () => {
    listScenariosMock.mockResolvedValue({
      scenarios: scenarios.map((scenario) => ({ ...scenario, name: 'Same plan' })),
    })
    const user = userEvent.setup()
    const { container } = renderWithProviders(<ComparisonPage />, { route: '/compare' })
    const boxes = await screen.findAllByRole('checkbox', { name: 'Same plan' })
    await user.click(boxes[0])
    expect(boxes[0]).toBeChecked()
    expect(boxes[1]).not.toBeChecked()
    await user.click(boxes[1])
    await waitFor(() =>
      expect(container.querySelector('[data-testid="chart-scenario-compare"]')).toBeInTheDocument(),
    )
  })

  it('reports a selected incomplete scenario instead of claiming fewer than two selections', async () => {
    listScenariosMock.mockResolvedValue({
      scenarios: [
        scenarios[0],
        {
          ...scenarios[1],
          results: { results: [{ ...rows[0], c_optimal: null, rho_optimal: null, Wq_optimal: null,
            Lq_optimal: null, optimized_stable: false }] },
        },
      ],
    })
    const user = userEvent.setup()
    const { container } = renderWithProviders(<ComparisonPage />, { route: '/compare' })
    await user.click(await screen.findByRole('checkbox', { name: 'Plan A' }))
    await user.click(screen.getByRole('checkbox', { name: 'Plan B' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Plan B')
    expect(screen.queryByText('Choose at least two saved scenarios.')).not.toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-scenario-compare"]')).not.toBeInTheDocument()
  })

  it('renders same-time queues as distinct comparison rows without key collisions', async () => {
    const errors: unknown[][] = []
    const spy = vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => { errors.push(args) })
    try {
      listScenariosMock.mockResolvedValue({
        scenarios: [{
          ...scenarios[0],
          results: { results: [
            { ...rows[0], c_current: 3, rho_current: 0.9 },
            { ...rows[0], c_current: 2, rho_current: 0.5 },
          ] },
        }],
      })
      renderWithProviders(<ComparisonPage />, { route: '/compare' })
      const table = await screen.findByRole('table')
      expect(within(table).getByText('90.00%')).toBeInTheDocument()
      expect(within(table).getByText('50.00%')).toBeInTheDocument()
      expect(errors.flat().join(' ')).not.toMatch(/same key/)
    } finally {
      spy.mockRestore()
    }
  })

  it('shows unstable Current plus one valid optimized plan without fabricating finance', async () => {
    const unstableRow: OptimizationOut = {
      ...rows[0],
      lambda_: 20.214,
      mu: 10,
      c_current: 2,
      rho_current: 1.0107,
      Wq_current: null,
      Lq_current: null,
      waiting_cost_current: null,
      cost_current: null,
      delta_cost: null,
      delta_Wq: null,
      delta_Lq: null,
      current_stable: false,
      c_optimal: 3,
      rho_optimal: 0.6738,
      Wq_optimal: 0.046446930568118626,
      Lq_optimal: 0.9388782545039499,
      cost_optimal: 354.887825450395,
      optimized_stable: true,
    }
    listScenariosMock.mockResolvedValue({
      scenarios: [{ ...scenarios[0], results: { results: [unstableRow] } }],
    })
    const { container } = renderWithProviders(<ComparisonPage />, { route: '/compare' })
    const table = await screen.findByRole('table')
    const dataRow = within(table).getAllByRole('row')[1]
    expect(within(dataRow).getByText('101.07%')).toBeInTheDocument()
    expect(within(dataRow).getByText('Unstable')).toBeInTheDocument()
    expect(within(dataRow).getAllByText('—').length).toBeGreaterThan(0)
    expect(within(dataRow).getByText('67.38%')).toBeInTheDocument()
    expect(within(dataRow).getByText('2.79')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-utilization-compare"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-server-compare"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-wait-time-lines"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-cost-waterfall"]')).not.toBeInTheDocument()
    expect(screen.queryByText('ROI Projection')).not.toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Aggregate cost savings are unavailable')
    expect(screen.queryByTestId('compare-roi-reason')).not.toBeInTheDocument()
  })

  it('shows the backend ROI reason below the incomplete alert when totals are null', async () => {
    const reason = "ROI can't be declared: in 08:00, customers arrive faster than the current staff can serve them (ρ ≥ 1), so today's waiting cost has no finite value."
    listScenariosMock.mockResolvedValue({
      scenarios: [{
        ...scenarios[0],
        results: { results: [{ ...rows[0], current_stable: false, cost_current: null }] },
        roi_unavailable_reason: reason,
      }],
    })
    renderWithProviders(<ComparisonPage />, { route: '/compare' })
    expect(await screen.findByTestId('compare-roi-reason')).toHaveTextContent(reason)
    expect(screen.getByRole('alert')).toHaveTextContent('Aggregate cost savings are unavailable')
  })

  it('compares two saved optimized plans independently of Current instability', async () => {
    const unstableRows = rows.map((item) => ({
      ...item,
      rho_current: 1.01,
      Wq_current: null,
      Lq_current: null,
      cost_current: null,
      waiting_cost_current: null,
      current_stable: false,
    }))
    listScenariosMock.mockResolvedValue({
      scenarios: scenarios.map((scenario) => ({ ...scenario, results: { results: unstableRows } })),
    })
    const user = userEvent.setup()
    const { container } = renderWithProviders(<ComparisonPage />, { route: '/compare' })
    await user.click(await screen.findByRole('checkbox', { name: 'Plan A' }))
    await user.click(screen.getByRole('checkbox', { name: 'Plan B' }))
    await waitFor(() =>
      expect(container.querySelector('[data-testid="chart-scenario-compare"]')).toBeInTheDocument(),
    )
    expect(screen.queryByText('Choose at least two saved scenarios.')).not.toBeInTheDocument()
  })

  it('shows analyzed-period costs without radar scores, ROI, or calendar projections', async () => {
    const { container } = renderWithProviders(<ComparisonPage />, { route: '/compare' })
    expect(await screen.findByText('Costs below apply only to the operating period represented by this scenario.')).toBeInTheDocument()
    expect(screen.getAllByText('₱300').length).toBeGreaterThan(0)
    expect(container.querySelector('[data-testid="chart-cost-waterfall"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-radar"]')).not.toBeInTheDocument()
    expect(screen.queryByText('ROI Projection')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Legal holidays per year')).not.toBeInTheDocument()
    expect(screen.queryByText('Monthly Savings')).not.toBeInTheDocument()
    expect(screen.queryByText('Annual Savings')).not.toBeInTheDocument()
  })

  it('announces the operating-period cost note as a live status', async () => {
    renderWithProviders(<ComparisonPage />, { route: '/compare' })
    const note = await screen.findByText('Costs below apply only to the operating period represented by this scenario.')
    expect(note.closest('[role="status"]')).not.toBeNull()
  })

  it('keeps a genuine zero current cost distinct from an unavailable savings percentage', async () => {
    listScenariosMock.mockResolvedValue({ scenarios: [{
      ...scenarios[0],
      results: { results: [{ ...rows[0], cost_current: 0, cost_optimal: 0, delta_cost: 0 }] },
    }] })
    renderWithProviders(<ComparisonPage />, { route: '/compare' })
    expect((await screen.findAllByText('₱0')).length).toBeGreaterThan(0)
    expect(screen.getByText('Savings Percent').parentElement).toHaveTextContent('—')
  })

  it('renders a blocked INVALID_INPUT scenario as unavailable without charts or staffing insights', async () => {
    const blockedRow: OptimizationOut = {
      ...rows[0],
      lambda_: 5,
      mu: 4,
      c_current: null,
      c_optimal: null,
      rho_current: null,
      rho_optimal: null,
      Wq_current: null,
      Wq_optimal: null,
      Lq_current: null,
      Lq_optimal: null,
      cost_current: null,
      cost_optimal: null,
      delta_cost: null,
      delta_Wq: null,
      delta_Lq: null,
      delta_c: null,
      delta_rho: null,
      waiting_cost_current: null,
      waiting_cost_optimal: null,
      abandonment_cost_current: null,
      abandonment_cost_optimal: null,
      cost_per_server: null,
      current_stable: false,
      optimized_stable: false,
    }
    listScenariosMock.mockResolvedValue({ scenarios: [{
      ...scenarios[0],
      results: { results: [blockedRow] },
    }] })
    const { container } = renderWithProviders(<ComparisonPage />, { route: '/compare' })
    const table = await screen.findByRole('table')
    const dataRow = within(table).getAllByRole('row')[1]
    // Missing staffing endpoints render as unavailable, never as zero.
    expect(within(dataRow).getAllByText('—').length).toBeGreaterThan(0)
    expect(within(dataRow).queryByText('0')).not.toBeInTheDocument()
    expect(screen.queryByText(/service points/)).not.toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-server-compare"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-utilization-compare"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-cost-waterfall"]')).not.toBeInTheDocument()
  })

  it('shows the empty state when no scenarios are saved', async () => {
    listScenariosMock.mockResolvedValue({ scenarios: [] })
    renderWithProviders(<ComparisonPage />, { route: '/compare' })
    expect(
      await screen.findByText('No scenarios yet. Save an optimization to compare plans.'),
    ).toBeInTheDocument()
  })
})

describe('separate comparison', () => {
  function renderSeparate() {
    getAnalysisMock.mockResolvedValue({
      analysis: { id: 7, queue_setup: { queue_structure: 'separate_queues', queue_ids: ['east-07', 'lane-A'] } },
    })
    return renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/compare" element={<ComparisonPage />} />
      </Routes>,
      { route: '/analyses/7/compare' },
    )
  }

  function plan(id: number, name: string, target: number, overrides = {}) {
    return {
      scenario_id: id, name, dataset_id: 5, target,
      evaluation_method: 'DES_REPLICATIONS', replications: 5, base_seed: 42,
      overall: 'COMPLETE', stale: false, valid: true, valid_reason: null,
      periods: [
        {
          time: '08:00', current_active_lanes: ['east-07', 'lane-A'],
          optimal_active_lanes: 2, adjustment: 0, peak_util: 0.55,
          wait_mean: 0.06, wait_ci: [0.05, 0.07],
          total_cost_mean: 200.0, total_cost_ci: [190.0, 210.0], status: 'OPTIMAL',
        },
        {
          time: '09:00', current_active_lanes: ['east-07', 'checkout_blue'],
          optimal_active_lanes: 1, adjustment: -1, peak_util: 0.3,
          wait_mean: null, wait_ci: null,
          total_cost_mean: 95.0, total_cost_ci: null, status: 'OPTIMAL',
        },
      ],
      totals: { lane_periods: 3, wait_mean: 0.06, peak_util: 0.55, total_cost_mean: 295.0 },
      ...overrides,
    }
  }

  function comparisonResponse(plans: unknown[], selected: number | null = null) {
    return {
      analysis_id: 7,
      queue_structure: 'separate_queues',
      current: {
        dataset_id: 5,
        periods: [
          { time: '08:00', active_lanes: ['east-07', 'lane-A'], lambda_total: 6.0, wait_mean: 0.05, util_max: 0.4 },
          { time: '09:00', active_lanes: ['east-07', 'checkout_blue'], lambda_total: 3.0, wait_mean: null, util_max: 0.2 },
        ],
        wait_mean: 0.05,
        wait_basis: 'lambda-weighted analytical mean over Current rows',
        util_max: 0.4,
        waiting_cost: 30.0,
        waiting_cost_basis: 'Lq-based Current basis; excludes server cost',
        total_cost: null,
        total_cost_reason: 'Current evidence has no server-cost basis; savings are not computed.',
      },
      plans,
      selected_scenario_id: selected,
    }
  }

  it('renders Current beside saved plans with staffing schedules', async () => {
    getSeparateComparisonMock.mockResolvedValue(
      comparisonResponse([plan(11, 'Optimal @ 60%', 0.6), plan(12, 'Optimal @ 70%', 0.7)]),
    )
    renderSeparate()
    expect((await screen.findAllByRole('columnheader', { name: 'Current' })).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('columnheader', { name: 'Optimal @ 60%' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('columnheader', { name: 'Optimal @ 70%' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('rowheader', { name: '08:00' }).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/east-07/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Replicated DES').length).toBeGreaterThan(0)
    expect(optimizeBatchSpy).not.toHaveBeenCalled()
    expect(optimizeSeparateSpy).not.toHaveBeenCalled()
  })

  it('selects exactly one valid plan explicitly and never automatically', async () => {
    const user = userEvent.setup()
    getSeparateComparisonMock.mockResolvedValue(
      comparisonResponse([plan(11, 'Optimal @ 60%', 0.6), plan(12, 'Optimal @ 70%', 0.7)]),
    )
    renderSeparate()
    await screen.findAllByRole('columnheader', { name: 'Optimal @ 70%' })
    expect(selectWorkflowScenarioMock).not.toHaveBeenCalled()
    await user.click(screen.getByRole('radio', { name: /Optimal @ 70%/ }))
    await user.click(screen.getByRole('button', { name: 'Select for Simulation' }))
    await waitFor(() => expect(selectWorkflowScenarioMock).toHaveBeenCalledWith(7, 12))
    expect(optimizeSeparateSpy).not.toHaveBeenCalled()
  })

  it('marks stale plans and blocks their selection', async () => {
    const user = userEvent.setup()
    getSeparateComparisonMock.mockResolvedValue(
      comparisonResponse([
        plan(11, 'Optimal @ 60%', 0.6, { stale: true, valid: false, valid_reason: 'stale for the current dataset' }),
        plan(12, 'Optimal @ 70%', 0.7),
      ]),
    )
    renderSeparate()
    expect((await screen.findAllByText('STALE')).length).toBeGreaterThan(0)
    expect(screen.getByRole('radio', { name: /Optimal @ 60%/ })).toBeDisabled()
    await user.click(screen.getByRole('radio', { name: /Optimal @ 70%/ }))
    await user.click(screen.getByRole('button', { name: 'Select for Simulation' }))
    await waitFor(() => expect(selectWorkflowScenarioMock).toHaveBeenCalledWith(7, 12))
  })

  it('shows invalid plans with reasons and keeps them unselectable', async () => {
    getSeparateComparisonMock.mockResolvedValue(
      comparisonResponse([plan(11, 'Blocked plan', 0.7, {
        overall: 'BLOCKED', valid: false, valid_reason: 'schedule is not COMPLETE',
      })]),
    )
    renderSeparate()
    expect(await screen.findByText(/schedule is not COMPLETE/)).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Blocked plan/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Select for Simulation' })).toBeDisabled()
  })

  it('shows the empty state when no separate plans are saved', async () => {
    getSeparateComparisonMock.mockResolvedValue(comparisonResponse([]))
    renderSeparate()
    expect(await screen.findByText('No saved optimal plans are available for comparison.')).toBeInTheDocument()
  })

  it('renders nulls as em-dash and introduces no synthetic scores', async () => {
    getSeparateComparisonMock.mockResolvedValue(
      comparisonResponse([plan(12, 'Optimal @ 70%', 0.7)]),
    )
    const { container } = renderSeparate()
    await screen.findAllByRole('columnheader', { name: 'Optimal @ 70%' })
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
    expect(container.textContent).not.toMatch(/score|winner|best plan|recommended/i)
  })

  function withBases(response: ReturnType<typeof comparisonResponse>, observed: 'flagged' | 'clear' | 'none') {
    const current = response.current as Record<string, unknown>
    current.wait_basis_kind = 'analytical'
    current.observed_wait_available = observed !== 'none'
    current.observed_wait_flagged_any = observed === 'flagged'
    current.observed_wait_ratio = 2
    current.observed_wait_min_gap_minutes = 5
    current.periods = [
      { time: '08:00', active_lanes: ['east-07', 'lane-A'], lambda_total: 6.0, wait_mean: 0.05, util_max: 0.4,
        observed_wait: observed === 'none' ? null : (observed === 'flagged' ? 0.5 : 0.06),
        observed_flag: observed === 'flagged' },
      { time: '09:00', active_lanes: ['east-07', 'checkout_blue'], lambda_total: 3.0, wait_mean: null, util_max: 0.2,
        observed_wait: null, observed_flag: false },
    ]
    for (const item of response.plans as Record<string, unknown>[]) item.wait_basis_kind = 'simulation'
    return response
  }

  const banner = 'Observed waits are much longer than cashier workload explains. Results describe the modeled system; check how waits were recorded.'

  it('labels the basis of Current and plan waits and computes no difference', async () => {
    getSeparateComparisonMock.mockResolvedValue(
      withBases(comparisonResponse([plan(12, 'Optimal @ 70%', 0.7)]), 'none'),
    )
    const { container } = renderSeparate()
    await screen.findAllByRole('columnheader', { name: 'Optimal @ 70%' })
    const waitRow = screen.getByRole('rowheader', { name: 'Modeled waiting (demand-weighted mean, min)' }).parentElement as HTMLElement
    expect(waitRow).toHaveTextContent('Modeled current wait (analytical)')
    expect(waitRow).toHaveTextContent('Simulation (replicated DES)')
    for (const name of ['Peak utilization', 'Waiting cost']) {
      const row = screen.getByRole('rowheader', { name }).parentElement as HTMLElement
      expect(row).toHaveTextContent('Analytical model (Current)')
      expect(row).toHaveTextContent('Simulation (replicated DES)')
    }
    expect(screen.getByText('Current and plan waits, waiting costs and peak utilization use different methods; they are not subtracted or ranked, and a lower plan value is not a saving.')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/better|improvement|shorter by/i)
    expect(screen.queryByText('Observed wait')).not.toBeInTheDocument()
    expect(screen.queryByText(banner)).not.toBeInTheDocument()
  })

  it('shows observed Current waits and the day banner when a period is flagged', async () => {
    getSeparateComparisonMock.mockResolvedValue(
      withBases(comparisonResponse([plan(12, 'Optimal @ 70%', 0.7)]), 'flagged'),
    )
    renderSeparate()
    expect(await screen.findByText(banner)).toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Modeled vs observed wait by period' })
    expect(table).toHaveTextContent('Observed wait')
    expect(table).toHaveTextContent('30.0')
    expect(table).toHaveTextContent('Much longer than modeled')
    expect(screen.getByText(/more than 2× the modeled wait and more than 5 minutes longer/)).toBeInTheDocument()
  })

  it('shows observed waits without a banner when nothing is flagged', async () => {
    getSeparateComparisonMock.mockResolvedValue(
      withBases(comparisonResponse([plan(12, 'Optimal @ 70%', 0.7)]), 'clear'),
    )
    renderSeparate()
    const table = await screen.findByRole('table', { name: 'Modeled vs observed wait by period' })
    expect(table).toHaveTextContent('3.6')
    expect(table).not.toHaveTextContent('Much longer than modeled')
    expect(screen.queryByText(banner)).not.toBeInTheDocument()
  })
})
