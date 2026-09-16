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

vi.mock('../api/scenarios', () => ({
  listScenarios: (...args: unknown[]) => listScenariosMock(...args),
  createScenario: vi.fn(),
}))

vi.mock('../api/workflow', () => ({
  getWorkflow: (...args: unknown[]) => getWorkflowMock(...args),
  selectWorkflowScenario: (...args: unknown[]) => selectWorkflowScenarioMock(...args),
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
