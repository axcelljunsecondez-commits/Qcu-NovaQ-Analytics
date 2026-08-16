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
  DEFAULT_OPTIONS: {
    target_utilization: 0.7,
    server_cost_per_hr: 87,
    customer_waiting_cost: 100,
    max_servers: 24,
    cost_per_abandonment: 60,
    abandonment_rate: 0.1,
  },
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
  failure_rate_ci_lower: 0.653,
  failure_rate_ci_upper: 0.761,
  failure_rate_ci_half_width: 0.054,
  failure_rate_precision: 'moderate',
  failure_rate_adequate: false,
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
  mc_failure_rate_ci_lower: 0.04,
  mc_failure_rate_ci_upper: 0.061,
  mc_failure_rate_ci_half_width: 0.0105,
  mc_failure_rate_precision: 'high',
  mc_failure_rate_adequate: true,
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
        seed: null,
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
        num_trials: 2000,
        failure_threshold: 0.75,
        seed: null,
      })
    })
    await screen.findByText('FAIL')
    expect(container.querySelector('[data-testid="chart-rho-mean-p95-lines"]')).toBeInTheDocument()
    expect(container.querySelector('[data-testid="chart-failure-rate-bars"]')).toBeInTheDocument()
  })

  it('counts Unstable and ERROR segments as not stable', async () => {
    const user = userEvent.setup()
    simulateDesMock.mockResolvedValue({
      results: [{ ...desRow, status: 'Unstable' }],
    })
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('button', { name: 'Run DES Simulation' }))
    await screen.findByText('Critical segments')
    expect(within(screen.getByText('Stable segments').closest('.metric-card')!).getByText('0')).toBeInTheDocument()
    expect(within(screen.getByText('Critical segments').closest('.metric-card')!).getByText('0')).toBeInTheDocument()
  })

  it('shows a failed verdict when a segment is Critical or unstable', async () => {
    const user = userEvent.setup()
    validateSimulationMock.mockResolvedValue({
      results: [{ ...validateRow, sim_status: 'Critical', mc_failure_rate: 0.02, mc_adequate: true }],
    })
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Validate' }))
    await user.click(screen.getByRole('button', { name: 'Validate plan' }))
    expect(await screen.findByText('Simulation validation found issues.')).toBeInTheDocument()
    expect(
      await screen.findByText(
        '1 of 1 segments failed — 1 unstable, 0 above the 5% failure threshold.',
      ),
    ).toBeInTheDocument()
  })

  it('explains a failure caused by high failure rate', async () => {
    const user = userEvent.setup()
    validateSimulationMock.mockResolvedValue({
      results: [
        validateRow,
        { ...validateRow, time: '09:00-10:00', sim_status: 'Normal', mc_failure_rate: 0.12 },
      ],
    })
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Validate' }))
    await user.click(screen.getByRole('button', { name: 'Validate plan' }))
    expect(await screen.findByText('Simulation validation found issues.')).toBeInTheDocument()
    expect(
      await screen.findByText(
        '1 of 2 segments failed — 0 unstable, 1 above the 5% failure threshold.',
      ),
    ).toBeInTheDocument()
  })

  it('renders failure-rate CI and precision badge in the MC table', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Monte Carlo' }))
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    await screen.findByText('FAIL')
    expect(await screen.findByText('65%–76%')).toBeInTheDocument()
    expect(screen.getByText('moderate')).toBeInTheDocument()
  })

  it('blocks MC runs when trials exceed 100,000', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Monte Carlo' }))
    const trials = screen.getByLabelText('Trials')
    await user.clear(trials)
    await user.type(trials, '100001')
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    expect(
      await screen.findByText('Trials must be an integer between 1 and 100000.'),
    ).toBeInTheDocument()
    expect(simulateMcMock).not.toHaveBeenCalled()
  })

  it('validates a plan and shows the pass banner and table', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Validate' }))
    await user.click(screen.getByRole('button', { name: 'Validate plan' }))
    await waitFor(() => {
      expect(optimizeBatchMock).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          target_utilization: 0.7,
          server_cost_per_hr: 87,
          customer_waiting_cost: 100,
          max_servers: 24,
          cost_per_abandonment: 60,
          abandonment_rate: 0.1,
        }),
      )
      expect(validateSimulationMock).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({ mc_trials: 10000, mc_failure_threshold: 0.75, seed: null }),
      )
    })
    expect(await screen.findByText('Simulation validation passed.')).toBeInTheDocument()
    expect(screen.getByText('Normal')).toBeInTheDocument()
    expect(screen.getByText('5%')).toBeInTheDocument()
  })

  it('sends edited plan and MC settings from the validate tab', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Validate' }))
    await user.clear(screen.getByLabelText('Trials'))
    await user.type(screen.getByLabelText('Trials'), '20000')
    await user.clear(screen.getByLabelText('Failure threshold (ρ)'))
    await user.type(screen.getByLabelText('Failure threshold (ρ)'), '0.8')
    await user.clear(screen.getByLabelText('Server cost / hr'))
    await user.type(screen.getByLabelText('Server cost / hr'), '120')
    await user.clear(screen.getByLabelText('Waiting cost / hr'))
    await user.type(screen.getByLabelText('Waiting cost / hr'), '80')
    await user.clear(screen.getByLabelText('Abandonment cost / customer'))
    await user.type(screen.getByLabelText('Abandonment cost / customer'), '50')
    await user.clear(screen.getByLabelText('Abandonment rate'))
    await user.type(screen.getByLabelText('Abandonment rate'), '0.2')
    await user.click(screen.getByRole('button', { name: 'Validate plan' }))
    await waitFor(() => {
      expect(optimizeBatchMock).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          server_cost_per_hr: 120,
          customer_waiting_cost: 80,
          cost_per_abandonment: 50,
          abandonment_rate: 0.2,
        }),
      )
      expect(validateSimulationMock).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({ mc_trials: 20000, mc_failure_threshold: 0.8 }),
      )
    })
  })

  it('maps optimizer lambda_ to a lambda key before calling validateSimulation', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Validate' }))
    await user.click(screen.getByRole('button', { name: 'Validate plan' }))
    await waitFor(() => {
      expect(validateSimulationMock).toHaveBeenCalled()
    })
    const payload = validateSimulationMock.mock.calls[0][0]
    expect(payload).toHaveLength(1)
    expect(payload[0].lambda).toBe(30)
    expect(payload[0].lambda_).toBe(30)
  })

  it('renders the failure-rate CI in the Validate table', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Validate' }))
    await user.click(screen.getByRole('button', { name: 'Validate plan' }))
    await screen.findByText('Simulation validation passed.')
    expect(await screen.findByText('4%–6%')).toBeInTheDocument()
  })

  it('renders a dash for missing failure-rate CI values', async () => {
    simulateMcMock.mockResolvedValue({ results: [{ ...mcRow, failure_rate_ci_lower: undefined, failure_rate_ci_upper: undefined, failure_rate_precision: undefined }] })
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Monte Carlo' }))
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    await screen.findByText('FAIL')
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
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

  it('clears DES results and shows a re-run hint when inputs change', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('button', { name: 'Run DES Simulation' }))
    await screen.findByText('Critical segments')
    await user.clear(screen.getByLabelText('Hours per segment'))
    await user.type(screen.getByLabelText('Hours per segment'), '48')
    expect(screen.queryByText('Critical segments')).not.toBeInTheDocument()
    expect(
      screen.getByText('Inputs changed — press Run to update results.'),
    ).toBeInTheDocument()
  })

  it('clears MC results and shows a re-run hint when inputs change', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Monte Carlo' }))
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    await screen.findByText('FAIL')
    await user.clear(screen.getByLabelText('Trials'))
    await user.type(screen.getByLabelText('Trials'), '5000')
    expect(screen.queryByText('FAIL')).not.toBeInTheDocument()
    expect(
      screen.getByText('Inputs changed — press Run to update results.'),
    ).toBeInTheDocument()
  })

  it('clears validate results and shows a re-run hint when inputs change', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Validate' }))
    await user.click(screen.getByRole('button', { name: 'Validate plan' }))
    await screen.findByText('Simulation validation passed.')
    await user.clear(screen.getByLabelText('Failure threshold (ρ)'))
    await user.type(screen.getByLabelText('Failure threshold (ρ)'), '0.8')
    expect(screen.queryByText('Simulation validation passed.')).not.toBeInTheDocument()
    expect(
      screen.getByText('Inputs changed — press Run to update results.'),
    ).toBeInTheDocument()
  })

  it('clears all results when the dataset changes', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('button', { name: 'Run DES Simulation' }))
    await screen.findByText('Critical segments')
    await user.selectOptions(screen.getByLabelText('Source dataset'), '')
    expect(screen.queryByText('Critical segments')).not.toBeInTheDocument()
  })

  it('clears the error when switching tabs', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SimulationPage />, { route: '/simulate' })
    await selectDataset(user)
    await user.click(screen.getByRole('tab', { name: 'Monte Carlo' }))
    const trials = screen.getByLabelText('Trials')
    await user.clear(trials)
    await user.type(trials, '100001')
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    await screen.findByText(/between 1 and 100000/)
    await user.click(screen.getByRole('tab', { name: 'DES (SimPy)' }))
    expect(screen.queryByText(/between 1 and 100000/)).not.toBeInTheDocument()
  })
})
