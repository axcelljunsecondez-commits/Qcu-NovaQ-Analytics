import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { OptimizePage } from './OptimizePage'

const listDatasetsMock = vi.fn()
const getDatasetMock = vi.fn()
const optimizeBatchMock = vi.fn()
const createScenarioMock = vi.fn()
const listScenariosMock = vi.fn()

vi.mock('../api/datasets', () => ({
  listDatasets: (...args: unknown[]) => listDatasetsMock(...args),
  getDataset: (...args: unknown[]) => getDatasetMock(...args),
  uploadDataset: vi.fn(),
  deleteDataset: vi.fn(),
}))

vi.mock('../api/optimization', () => ({
  optimize: vi.fn(),
  optimizeBatch: (...args: unknown[]) => optimizeBatchMock(...args),
}))

vi.mock('../api/scenarios', () => ({
  listScenarios: (...args: unknown[]) => listScenariosMock(...args),
  createScenario: (...args: unknown[]) => createScenarioMock(...args),
  updateScenario: vi.fn(),
  deleteScenario: vi.fn(),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const row = {
  time: '08:00-09:00',
  lambda_: 30,
  mu: 12,
  c_current: 3,
  c_optimal: 4,
  rho_current: 0.8333333333333334,
  rho_optimal: 0.625,
  Wq_current: 0.1170411985018727,
  Wq_optimal: 0.017769816899806667,
  Lq_current: 3.511235955056181,
  Lq_optimal: 0.5330945069942,
  cost_current: 612.12,
  cost_optimal: 401.31,
  delta_cost: -210.81,
  delta_Wq: -0.099,
  delta_Lq: -2.978,
  delta_c: 1,
  delta_rho: -0.208,
  waiting_cost_current: 351.12,
  waiting_cost_optimal: 53.31,
  abandonment_cost_current: 0,
  abandonment_cost_optimal: 0,
  cost_per_server: 87,
  current_stable: true,
  optimized_stable: true,
  recommendation: 'Add 1 server at 08:00-09:00.',
  warning: '',
}

const dataset = {
  id: 1,
  name: 'sample',
  source_filename: 'sample.csv',
  source_format: 'csv',
  row_count: 1,
  validation: { ok: true, message: 'Input data is valid.' },
  created_at: '2026-08-01T10:00:00Z',
  normalized: [
    { time: '08:00-09:00', lambda: 30, mu: 12, c: 3 },
  ],
}

beforeEach(() => {
  listDatasetsMock.mockReset()
  getDatasetMock.mockReset()
  optimizeBatchMock.mockReset()
  createScenarioMock.mockReset()
  listScenariosMock.mockReset()
  listDatasetsMock.mockResolvedValue({ datasets: [dataset] })
  getDatasetMock.mockResolvedValue({ dataset })
  optimizeBatchMock.mockResolvedValue({ results: [row] })
  listScenariosMock.mockResolvedValue({ scenarios: [] })
})

describe('OptimizePage', () => {
  it('optimizes segments from a selected dataset and renders KPI cards', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await waitFor(() => {
      expect(getDatasetMock).toHaveBeenCalledWith(1)
    })
    await waitFor(() => {
      expect(optimizeBatchMock).toHaveBeenCalledWith(
        [{ time: '08:00-09:00', lambda: 30, mu: 12, c: 3 }],
        expect.objectContaining({ target_utilization: 0.7 }),
      )
    })
    expect(await screen.findByText('612.12')).toBeInTheDocument()
    expect(screen.getByText('401.31')).toBeInTheDocument()
  })

  it('renders the staffing table with recommendation text', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    expect(await screen.findByText('Add 1 server at 08:00-09:00.')).toBeInTheDocument()
    expect(screen.getByText('08:00-09:00')).toBeInTheDocument()
  })

  it('saves a scenario with the batch results', async () => {
    createScenarioMock.mockResolvedValue({ scenario: { id: 9 } })
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await screen.findByText('Add 1 server at 08:00-09:00.')
    await user.type(screen.getByLabelText('Scenario name'), 'plan A')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => {
      expect(createScenarioMock).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'plan A',
          settings: expect.objectContaining({ target_utilization: 0.7 }),
          results: { results: [row] },
        }),
      )
    })
  })

  it('scales lambda inputs for what-if analysis and sends to the API', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await screen.findByText('Add 1 server at 08:00-09:00.')
    await user.type(screen.getByLabelText('λ multiplier'), '1.5')
    await user.click(screen.getByRole('button', { name: 'Run what-if' }))
    await waitFor(() => {
      expect(optimizeBatchMock).toHaveBeenLastCalledWith(
        [{ time: '08:00-09:00', lambda: 45, mu: 12, c: 3 }],
        expect.anything(),
      )
    })
  })

  it('passes advanced model columns (variance/K/theta) from the dataset to optimizeBatch', async () => {
    getDatasetMock.mockResolvedValue({
      dataset: {
        ...dataset,
        normalized: [
          { time: '08:00-09:00', lambda: 30, mu: 12, c: 3, variance: 4.5, K: 6, theta: 0.5 },
          { time: '09:00-10:00', lambda: 45, mu: 12, c: 4, variance: 3.2, theta: 0.25 },
          { time: '10:00-11:00', lambda: 50, mu: 12, c: 4, K: 5 },
        ],
      },
    })
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await waitFor(() => {
      expect(optimizeBatchMock).toHaveBeenCalledWith(
        [
          { time: '08:00-09:00', lambda: 30, mu: 12, c: 3, variance: 4.5, K: 6, theta: 0.5 },
          { time: '09:00-10:00', lambda: 45, mu: 12, c: 4, variance: 3.2, theta: 0.25 },
          { time: '10:00-11:00', lambda: 50, mu: 12, c: 4, K: 5 },
        ],
        expect.anything(),
      )
    })
  })

  it('sends abandonment cost and rate to the optimizer and renders the abandonment column', async () => {
    optimizeBatchMock.mockResolvedValue({
      results: [{ ...row, abandonment_cost_current: 180, abandonment_cost_optimal: 90 }],
    })
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await waitFor(() => {
      expect(optimizeBatchMock).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({ cost_per_abandonment: 60, abandonment_rate: 0.1 }),
      )
    })
    expect(await screen.findByText('180.00 → 90.00')).toBeInTheDocument()
  })

  it('shows the warning banner when a row has a warning', async () => {
    optimizeBatchMock.mockResolvedValue({
      results: [{ ...row, warning: 'Segment unstable under current staffing.' }],
    })
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    expect(
      await screen.findByText('Segment unstable under current staffing.'),
    ).toBeInTheDocument()
  })
})
