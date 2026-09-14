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
  DEFAULT_OPTIONS: {
    target_utilization: 0.7,
    server_cost_per_hr: 87,
    customer_waiting_cost: 100,
    max_servers: 24,
    cost_per_abandonment: 60,
    abandonment_rate: 0.1,
  },
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

describe('calculation integrity', () => {
  it('blocks saving after the input selection changes', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await screen.findByText('401.31')
    await user.type(screen.getByLabelText('Scenario name'), 'stale plan')
    await user.selectOptions(screen.getByLabelText('Source dataset'), '')
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
    expect(screen.getByRole('alert')).toHaveTextContent('Inputs changed')
  })

  it('saves the effective what-if inputs and factor as a snapshot', async () => {
    const user = userEvent.setup()
    createScenarioMock.mockResolvedValue({ scenario: { id: 3 } })
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await screen.findByText('401.31')
    await user.type(screen.getByLabelText('λ multiplier'), '1.5')
    await user.click(screen.getByRole('button', { name: 'Run what-if' }))
    await user.type(screen.getByLabelText('Scenario name'), 'what if')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(createScenarioMock).toHaveBeenCalledWith(expect.objectContaining({ settings: expect.objectContaining({
      calculation: expect.objectContaining({ what_if_multiplier: 1.5, input_segments: [expect.objectContaining({ lambda: 45 })] }),
    }) }))
  })

  it('does not turn an infeasible row into zero optimized cost', async () => {
    optimizeBatchMock.mockResolvedValue({ results: [{ ...row, c_optimal: null, optimized_stable: false,
      rho_optimal: null, cost_optimal: null, delta_c: null }] })
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Comparison incomplete')
    expect(screen.queryByText('0.00')).not.toBeInTheDocument()
    expect(screen.getByText('Staffing totals are unavailable until every segment has a current, feasible recommendation.')).toBeInTheDocument()
    expect(screen.queryByText('0 cashiers')).not.toBeInTheDocument()
    expect(screen.queryByText(/→ null/)).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Scenario name'), 'Incomplete plan')
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Scenario saved.')).toBeInTheDocument()
    expect(createScenarioMock).toHaveBeenCalledWith(expect.objectContaining({
      results: { results: [expect.objectContaining({ c_optimal: null, optimized_stable: false })] },
      settings: expect.objectContaining({ calculation: expect.objectContaining({ engine_version: 'novaq-2026-09-system-v2' }) }),
    }))
  })
})

describe('OptimizePage', () => {
  it.each([
    ['Cost-focused constraints', 'Target utilization 85%; no maximum-wait constraint. Minimizes configured total cost within these constraints.', 0.85, null],
    ['Low-wait constraints', 'Target utilization 65%; maximum analytical wait 2 minutes. Minimizes configured total cost within these constraints.', 0.65, 2],
    ['Balanced constraints', 'Target utilization 75%; maximum analytical wait 5 minutes. Minimizes configured total cost within these constraints.', 0.75, 5],
  ])('binds %s copy to the exact submitted constraints', async (label, description, targetUtilization, maxWaitMinutes) => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    const preset = screen.getByRole('button', { name: new RegExp(label) })
    expect(preset).toHaveTextContent(description)
    await user.click(preset)
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await waitFor(() => expect(optimizeBatchMock).toHaveBeenCalledWith(
      expect.any(Array),
      expect.objectContaining({
        target_utilization: targetUtilization,
        max_wait_minutes: maxWaitMinutes,
      }),
    ))
    expect(screen.queryByText('Minimize Wait Time')).not.toBeInTheDocument()
  })

  it('keeps operational staffing visible when the current baseline is unstable', async () => {
    optimizeBatchMock.mockResolvedValue({
      results: [{ ...row, c_current: 2, rho_current: 1.0107, current_stable: false,
        Wq_current: null, Lq_current: null, waiting_cost_current: null,
        cost_current: null, delta_cost: null, delta_Wq: null, delta_Lq: null,
        c_optimal: 3, rho_optimal: 0.6738, optimized_stable: true,
        warning: 'Unstable system: lambda must be less than c * mu for M/M/c.' }],
    })
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    expect(await screen.findByText('Net staffing reduction')).toBeInTheDocument()
    expect(screen.getByText('101.07% → 67.38%')).toBeInTheDocument()
    expect(screen.getAllByText('Unstable').length).toBeGreaterThan(0)
    expect(screen.getByText('— → 1.07')).toBeInTheDocument()
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('forwards minimum staffing and a wait limit, then invalidates the saved result on change', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.clear(screen.getByLabelText('Minimum cashiers'))
    await user.type(screen.getByLabelText('Minimum cashiers'), '3')
    await user.type(screen.getByLabelText('Maximum analytical wait in minutes (blank disables limit)'), '5')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await waitFor(() => expect(optimizeBatchMock).toHaveBeenCalledWith(expect.any(Array), expect.objectContaining({ min_servers: 3, max_wait_minutes: 5 })))
    await user.clear(screen.getByLabelText('Maximum analytical wait in minutes (blank disables limit)'))
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await waitFor(() => expect(optimizeBatchMock).toHaveBeenLastCalledWith(expect.any(Array), expect.objectContaining({ max_wait_minutes: null })))
  })
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
    expect(screen.getByLabelText('Available cashiers today')).toHaveValue(null)
    expect(screen.getByText('Net staffing reduction')).toBeInTheDocument()
  })

  it('summarizes net cashier-hours, available pool, and grouped time ranges', async () => {
    optimizeBatchMock.mockResolvedValue({
      results: [
        { ...row, time: '05:00-06:00', c_current: 3, c_optimal: 2, delta_c: -1 },
        { ...row, time: '06:00-07:00', c_current: 5, c_optimal: 4, delta_c: -1 },
        { ...row, time: '07:00-08:00', c_current: 5, c_optimal: 3, delta_c: -2 },
        { ...row, time: '08:00-09:00', c_current: 5, c_optimal: 3, delta_c: -2 },
        { ...row, time: '09:00-10:00', c_current: 5, c_optimal: 3, delta_c: -2 },
        { ...row, time: '10:00-11:00', c_current: 5, c_optimal: 4, delta_c: -1 },
        { ...row, time: '11:00-12:00', c_current: 2, c_optimal: 3, delta_c: 1 },
        { ...row, time: '12:00-13:00', c_current: 3, c_optimal: 4, delta_c: 1 },
        { ...row, time: '13:00-14:00', c_current: 5, c_optimal: 4, delta_c: -1 },
        { ...row, time: '14:00-15:00', c_current: 5, c_optimal: 3, delta_c: -2 },
        { ...row, time: '15:00-16:00', c_current: 5, c_optimal: 4, delta_c: -1 },
        { ...row, time: '16:00-17:00', c_current: 5, c_optimal: 4, delta_c: -1 },
        { ...row, time: '17:00-18:00', c_current: 2, c_optimal: 2, delta_c: 0 },
      ],
    })
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))

    expect(await screen.findByText('12 cashier-hours reduced')).toBeInTheDocument()
    expect(screen.getByText('14 removed - 2 added')).toBeInTheDocument()
    expect(screen.getByText('Peak requirement')).toBeInTheDocument()
    expect(screen.getByText('Available pool')).toBeInTheDocument()
    expect(screen.getByText('4 cashiers')).toBeInTheDocument()
    expect(screen.getAllByText('—')).toHaveLength(2)
    expect(screen.queryByText('Available pool can cover the optimized schedule.')).not.toBeInTheDocument()
    expect(screen.getByText('Add 1 cashier: 11:00-13:00')).toBeInTheDocument()
    expect(screen.getByText('Reduce 1 cashier: 05:00-07:00, 10:00-11:00, 13:00-14:00, 15:00-17:00')).toBeInTheDocument()
    expect(screen.getByText('Reduce 2 cashiers: 07:00-10:00, 14:00-15:00')).toBeInTheDocument()
    expect(screen.queryByText('+2')).not.toBeInTheDocument()
    expect(screen.queryByText('-12')).not.toBeInTheDocument()
  })

  it('warns when the available cashier pool cannot cover peak optimized demand', async () => {
    optimizeBatchMock.mockResolvedValue({
      results: [
        { ...row, time: '11:00-12:00', c_current: 2, c_optimal: 3, delta_c: 1 },
        { ...row, time: '12:00-13:00', c_current: 3, c_optimal: 4, delta_c: 1 },
      ],
    })
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    const poolInput = await screen.findByLabelText('Available cashiers today')
    await user.type(poolInput, '3')
    expect(
      screen.getByText('Available pool is short by 1 cashier during peak optimized demand.'),
    ).toBeInTheDocument()
  })

  it('treats an explicit zero available pool as a real shortage without blocking optimization', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.type(screen.getByLabelText('Available cashiers today'), '0')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    expect(await screen.findByText('0 cashiers')).toBeInTheDocument()
    expect(screen.queryByText('Available pool can cover the optimized schedule.')).not.toBeInTheDocument()
    expect(screen.getByText('Available pool is short by 4 cashiers during peak optimized demand.')).toBeInTheDocument()
    expect(optimizeBatchMock).toHaveBeenCalled()
  })

  it('describes every preset as constraints over the configured total-cost objective', async () => {
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    expect(await screen.findByText('Constraint presets')).toBeInTheDocument()
    expect(screen.queryByText(/Ideal Staffing/i)).not.toBeInTheDocument()
    expect(screen.getAllByText(/Minimizes configured total cost within these constraints/)).toHaveLength(3)
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

  it('shows utilization status indicators and threshold legend in the staffing table', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    expect(await screen.findByText('Status')).toBeInTheDocument()
    expect(screen.getByLabelText('Utilization status legend')).toBeInTheDocument()
    expect(screen.getAllByText('Peak').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Normal').length).toBeGreaterThan(0)
    expect(screen.getByText('> 100%')).toBeInTheDocument()
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
