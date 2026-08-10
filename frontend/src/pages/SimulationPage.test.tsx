import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { SimulationPage } from './SimulationPage'

const listDatasetsMock = vi.fn()
const getDatasetMock = vi.fn()
const simulateDesMock = vi.fn()
const simulateMcMock = vi.fn()
const validateSimulationMock = vi.fn()
const optimizeBatchMock = vi.fn()

vi.mock('../api/datasets', () => ({
  listDatasets: (...args: unknown[]) => listDatasetsMock(...args),
  getDataset: (...args: unknown[]) => getDatasetMock(...args),
  uploadDataset: vi.fn(),
  deleteDataset: vi.fn(),
}))

vi.mock('../api/simulation', () => ({
  simulateDes: (...args: unknown[]) => simulateDesMock(...args),
  simulateMc: (...args: unknown[]) => simulateMcMock(...args),
  validateSimulation: (...args: unknown[]) => validateSimulationMock(...args),
}))

vi.mock('../api/optimization', () => ({
  optimize: vi.fn(),
  optimizeBatch: (...args: unknown[]) => optimizeBatchMock(...args),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const dataset = {
  id: 1,
  name: 'sample',
  source_filename: 'sample.csv',
  source_format: 'csv',
  row_count: 1,
  validation: { ok: true, message: 'Input data is valid.' },
  created_at: '2026-08-01T10:00:00Z',
  normalized: [{ time: '08:00-09:00', lambda: 30, mu: 12, c: 3 }],
}

const segments = [{ time: '08:00-09:00', lambda: 30, mu: 12, c: 3 }]

const desRow = {
  time: '08:00-09:00',
  lambda: 30,
  mu: 12,
  c: 3,
  rho_sim: 0.899201,
  Lq_sim: 3.869001,
  Wq_sim: 0.133516,
  max_queue: 21,
  served: 609,
  dropped: 0,
  status: 'Critical',
  error: null,
  warmup_fraction: 0.2,
  warmup_end: 4.8,
  initial_queue_depth: 0,
  final_Lq: 0,
}

const mcRow = {
  time: '08:00-09:00',
  lambda: 30,
  mu: 12,
  c: 3,
  rho_mean: 0.82288,
  rho_std: 0.099799,
  rho_p95: 0.986534,
  Lq_mean: 6.515779,
  Wq_mean: 0.202954,
  failure_rate: 0.71,
  failure_count: 71,
  status: 'FAIL',
  error: null,
  ci_Wq_hw: 0.071029,
  ci_Lq_hw: 2.465906,
  adequate_samples: false,
}

const validateRow = {
  time: '08:00-09:00',
  lambda: 30,
  mu: 12,
  c: 3,
  c_optimal: 4,
  rho_current: 0.8333,
  rho_optimal: 0.625,
  Lq_current: 3.51,
  Lq_optimal: 0.53,
  Wq_current: 0.117,
  Wq_optimal: 0.018,
  sim_rho: 0.62736,
  sim_Wq: 0.013876,
  sim_max_queue: 7,
  sim_status: 'Normal',
  mc_failure_rate: 0.05,
  mc_adequate: true,
  mc_rho_mean: 0.621244,
  mc_rho_p95: 0.749728,
  mc_Wq_ci: '1.22 ± 0.10 min (95% CI)',
}

beforeEach(() => {
  listDatasetsMock.mockReset()
  getDatasetMock.mockReset()
  simulateDesMock.mockReset()
  simulateMcMock.mockReset()
  validateSimulationMock.mockReset()
  optimizeBatchMock.mockReset()
  listDatasetsMock.mockResolvedValue({ datasets: [dataset] })
  getDatasetMock.mockResolvedValue({ dataset })
  simulateDesMock.mockResolvedValue({ results: [desRow] })
  simulateMcMock.mockResolvedValue({ results: [mcRow] })
  validateSimulationMock.mockResolvedValue({ results: [validateRow] })
  optimizeBatchMock.mockResolvedValue({
    results: [
      {
        time: '08:00-09:00',
        lambda_: 30,
        mu: 12,
        c_current: 3,
        c_optimal: 4,
        rho_current: 0.8333,
        rho_optimal: 0.625,
      },
    ],
  })
})

async function selectDataset(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
  await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
}

describe('SimulationPage', () => {
  it('shows three tabs with translated labels', async () => {
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    expect(await screen.findByRole('tab', { name: 'DES (SimPy)' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Monte Carlo' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Validate' })).toBeInTheDocument()
  })

  it('runs DES with defaults and renders KPI counts and queue bars', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('button', { name: 'Run DES Simulation' }))
    await waitFor(() => {
      expect(simulateDesMock).toHaveBeenCalledWith(segments, {
        sim_hours: 24,
        queue_overload_threshold: 20,
        seed: 42,
        carryover: true,
      })
    })
    expect(await screen.findByText('Critical segments')).toBeInTheDocument()
    expect(within(screen.getByText('Critical segments').closest('.metric-card')!).getByText('1')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-utilization-heatmap"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-rho-lq-lines"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-max-queue-bars"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-lq-histogram"]')).toBeInTheDocument()
    expect(await screen.findByText('90%')).toBeInTheDocument()
  })

  it('runs Monte Carlo with defaults and renders MC charts', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Monte Carlo' }))
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    await waitFor(() => {
      expect(simulateMcMock).toHaveBeenCalledWith(segments, {
        num_trials: 500,
        failure_threshold: 0.75,
        seed: 42,
      })
    })
    await screen.findByText('FAIL')
    expect(container.querySelector('[data-testid="chart-rho-mean-p95-lines"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-failure-rate-bars"]')).toBeInTheDocument()
  })

  it('validates a plan and shows the pass banner and table', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Validate' }))
    await user.click(screen.getByRole('button', { name: 'Validate plan' }))
    await waitFor(() => {
      expect(optimizeBatchMock).toHaveBeenCalled()
      expect(validateSimulationMock).toHaveBeenCalled()
    })
    expect(await screen.findByText('Simulation validation passed.')).toBeInTheDocument()
    expect(screen.getByText('Normal')).toBeInTheDocument()
    expect(screen.getByText('5%')).toBeInTheDocument()
  })

  it('sends seed null when the seed input is blank', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    const seed = screen.getByLabelText('Random seed')
    await user.clear(seed)
    await user.click(screen.getByRole('button', { name: 'Run DES Simulation' }))
    await waitFor(() => {
      expect(simulateDesMock).toHaveBeenCalledWith(segments, expect.objectContaining({ seed: null }))
    })
  })

  it('renders queue bars without nan% for null rho_sim rows', async () => {
    simulateDesMock.mockResolvedValue({ results: [{ ...desRow, rho_sim: null }] })
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('button', { name: 'Run DES Simulation' }))
    await screen.findByText('Critical segments')
    expect(screen.queryByText('nan%')).not.toBeInTheDocument()
  })
})
