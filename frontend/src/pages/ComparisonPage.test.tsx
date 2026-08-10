import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../test/test-utils'
import { ComparisonPage } from './ComparisonPage'
import type { OptimizationOut } from '../api/types'

const listScenariosMock = vi.fn()

vi.mock('../api/scenarios', () => ({
  listScenarios: (...args: unknown[]) => listScenariosMock(...args),
  createScenario: vi.fn(),
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
})

describe('ComparisonPage', () => {
  it('lists saved scenarios in the picker and loads the first one', async () => {
    renderWithProviders(<ComparisonPage />, { route: '/compare' })
    expect((await screen.findAllByRole('option', { name: 'Plan A' })).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('option', { name: 'Plan B' }).length).toBeGreaterThan(0)
    expect(await screen.findByTestId('chart-radar')).toBeInTheDocument()
  })

  it('renders radar, utilization, servers, wait-time and waterfall charts', async () => {
    const { container } = renderWithProviders(<ComparisonPage />, { route: '/compare' })
    await waitFor(() =>
      expect(container.querySelector('[data-testid="chart-radar"]')).toBeInTheDocument(),
    )
    expect(container.querySelector('[data-testid="chart-utilization-compare"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-server-compare"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-wait-time-lines"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-cost-waterfall"]')).toBeInTheDocument()
  })

  it('compares two saved scenarios with the scenario bars chart', async () => {
    const { container } = renderWithProviders(<ComparisonPage />, { route: '/compare' })
    await waitFor(() =>
      expect(container.querySelector('[data-testid="chart-scenario-compare"]')).toBeInTheDocument(),
    )
  })

  it('shows the empty state when no scenarios are saved', async () => {
    listScenariosMock.mockResolvedValue({ scenarios: [] })
    renderWithProviders(<ComparisonPage />, { route: '/compare' })
    expect(
      await screen.findByText('No scenarios yet. Save an optimization to compare plans.'),
    ).toBeInTheDocument()
  })
})
